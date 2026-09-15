# -*- coding: utf-8 -*-
"""
Round 5: 财报/基本面因子 (PIT)
=============================
数据: fund_grid.pkl (quarter 级 30 字段 + 公告日) -> 按 info_date 展开为日频面板(无未来函数)
三组检验:
  A. raw                     原始因子
  B. lnmc                    对 ln(市值) 横截面回归取残差
  C. barra                   对 BARRA size + 31 申万行业 回归取残差(FWL 向量化, 与 round4 等价)

框架: factor_miner (2018-01起, FWD=5, 成本单边千一, 10分组 Top组多头)
用法: python round5_fund.py
"""
import os
import sys
import gc
import time
import pickle
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from factor_miner import (load_panel, prepare, evaluate, pass_filter,
                          cs_rank, START)

DEV = os.path.join(HERE, 'all01_dev')
GRID = os.path.join(DEV, 'fund_grid.pkl')
PANEL = os.path.join(HERE, 'panel.h5')
BARRA = os.path.join(HERE, 'barra.h5')
OUT_CSV = os.path.join(HERE, 'round5_fund.csv')
OUT_IC = os.path.join(HERE, 'ic_round5.pkl')

t0 = time.time()


def log(*a):
    print(*a, flush=True)


# ==================== PIT -> 日频面板 ====================
class FundPanels(object):
    """quarter 级网格 -> 日频(按公告日激活, 严格无未来函数)"""

    def __init__(self, grid_path, dates):
        with open(grid_path, 'rb') as f:
            G = pickle.load(f)
        self.qs = G['qs']
        self.val = G['val']
        self.avail = G['avail']
        self.col_of = G['col_of']
        S = len(self.col_of)
        self.S = S
        self.cols = [''] * S
        for obid, j in self.col_of.items():
            self.cols[j] = obid
        self.dates = np.asarray(dates)
        self.T = len(self.dates)
        self.Q = len(self.qs)
        self._idx = {}
        self._q1 = None

    def is_q1(self, k):
        """(T,S) bool: 当前生效的报告期是否为 Q1(单季值=YTD 本身)"""
        idx = self._idx.get(k)
        if idx is None:
            idx = self._build_idx(k)
        if self._q1 is None:
            self._q1 = np.array([q.endswith('1') for q in self.qs], dtype=bool)
        return np.where(idx >= 0, self._q1[np.clip(idx, 0, self.Q - 1)], False)

    def _build_idx(self, k):
        """返回 (T,S) int16: 每个交易日每只股票"最新已披露"的 quarter 下标, -1 表示无"""
        # 注意: STOCK 类字段的 val 做过 quarter 间 ffill, 但 avail 没有
        # -> 必须把"真实披露日"也沿 quarter 轴前向累积, 否则 ffill 出的格子
        #    公告日是 99999999(永不激活), 值会冻结在首次披露值
        ok = np.isfinite(self.val[k])                       # (Q,S)
        real = np.where(self.avail[k] < 99999999, self.avail[k], 0)
        av_ff = np.maximum.accumulate(real, axis=0)         # 取"最近一次真实披露日"
        av = np.where(ok, av_ff, 0).astype(np.int64)
        T, S, Q = self.T, self.S, self.Q
        idx = np.full((T, S), -1, dtype=np.int16)
        ar = np.arange(T)
        dts = self.dates
        for s in range(S):
            qv = np.flatnonzero(ok[:, s])
            if len(qv) == 0:
                continue
            pos = np.searchsorted(dts, av[qv, s], side='left')   # 首个 >= 公告日 的交易日
            np.maximum.accumulate(pos, out=pos)                  # 防极少数倒序披露
            kk = np.searchsorted(pos, ar, side='right') - 1
            idx[:, s] = np.where(kk >= 0, qv[np.maximum(kk, 0)], -1)
        if len(self._idx) > 12:
            self._idx.clear()
        self._idx[k] = idx
        return idx

    def daily(self, k, lag=0):
        """(T,S) float32 日频值; lag=n 表示取 n 个季度之前(去年同期)"""
        idx = self._idx.get(k)
        if idx is None:
            idx = self._build_idx(k)
        ii = idx - lag
        ii = np.clip(ii, 0, self.Q - 1)
        out = np.take_along_axis(self.val[k], ii, axis=0)
        out = np.where(idx - lag >= 0, out, np.nan).astype(np.float32)
        return out


# ==================== 新口径工具(B主口径 / D分层交叉验证) ====================
def build_size_bucket(mkt, nb=20):
    """市值分层: 每日 nb 层, 返回 (T,S) int16, 缺失市值 -> nb(单独一组)"""
    T, S = mkt.shape
    rk = pd.DataFrame(mkt).rank(axis=1, pct=True).values
    return np.where(np.isfinite(mkt),
                    np.minimum((rk * nb).astype(np.int16), nb - 1), nb)


def strat_rank(Y, bkt, nb=20):
    """按 (日期, 市值层) 分组做组内 rank(0~1): 非参数, 完全剥离市值的任何单调影响"""
    T, S = Y.shape
    NG = nb + 1
    gg = (np.repeat(np.arange(T, dtype=np.int64), S) * NG + bkt.ravel().astype(np.int64))
    y = np.asarray(Y, dtype=np.float64).ravel()
    nan = ~np.isfinite(y)
    y2 = np.where(nan, np.inf, y)
    order = np.lexsort((y2, gg))
    gs = gg[order]
    cnt = np.bincount(gg, minlength=T * NG)
    starts = np.zeros(T * NG, dtype=np.int64)
    np.cumsum(cnt[:-1], out=starts[1:])
    n = cnt[gs]
    r = (np.arange(len(y), dtype=np.int64) - starts[gs]) / np.maximum(n - 1, 1)
    out = np.empty(len(y), dtype=np.float64)
    out[order] = r
    out[nan] = np.nan
    return out.reshape(T, S)


def ind_demean(Y, BN):
    """行业内 demean(用 BARRA 每日行业归属); Y: (T,S)"""
    T, S = Y.shape
    Y32 = np.asarray(Y, dtype=np.float32)
    m0 = np.isfinite(Y32) & BN.covered
    idx = np.flatnonzero(m0.ravel())
    kk = BN.flat_key[idx]
    sy = np.bincount(kk, weights=Y32.ravel()[idx], minlength=T * BN.G)
    cnt = np.maximum(np.bincount(kk, minlength=T * BN.G).astype(np.float64), 1.0)
    my = (sy / cnt).reshape(T, BN.G).ravel()[BN.flat_key].reshape(T, S)
    return np.where(m0, Y32 - my.astype(np.float32), np.nan)


def sd(a, b):
    """安全除法"""
    with np.errstate(divide='ignore', invalid='ignore'):
        r = a / b
    r = np.where(np.isfinite(r), r, np.nan)
    return r.astype(np.float32)


# ==================== 中性化 ====================
def cs_neutralize_lnmc(Y, X):
    """Y ~ ln(X) 横截面取残差 (Y,X: (T,S) ndarray)"""
    x = np.log(np.where(X > 0, X, np.nan))
    m = np.isfinite(Y) & np.isfinite(x)
    x0 = np.where(m, x, 0.0)
    y0 = np.where(m, Y, 0.0)
    n = m.sum(axis=1)
    sx = x0.sum(axis=1)
    sy = y0.sum(axis=1)
    sxx = (x0 * x0).sum(axis=1)
    sxy = (x0 * y0).sum(axis=1)
    den = n * sxx - sx * sx
    b = np.where(np.abs(den) > 1e-9, (n * sxy - sx * sy) / np.where(den == 0, 1, den), 0.0)
    a = (sy - b * sx) / np.maximum(n, 1)
    r = np.where(m, Y - (a[:, None] + b[:, None] * x), np.nan)
    return r


class BarraNeut(object):
    """BARRA size + 行业 中性化 (FWL: 组内去均值后对 size 去均值回归)

    行业归属取**每日**实际哑变量(申万行业会调整, 近5%股票变更过),
    分组求和用 bincount(day*G+gid) 向量化实现, 与逐日 lstsq 等价(已自检)。
    """

    STYLE = ['size', 'non_linear_size', 'momentum', 'liquidity', 'book_to_price',
             'leverage', 'growth', 'earnings_yield', 'beta', 'residual_volatility',
             'comovement']

    def __init__(self, barra_path, dates, cols):
        S = len(cols)
        T = len(dates)
        with pd.HDFStore(barra_path, 'r') as st:
            keys = [k.strip('/') for k in st.keys()]
            inds = [k for k in keys if k not in self.STYLE]
            X = st['size'].reindex(index=dates, columns=cols).values.astype(np.float32)
            K = len(inds)
            gid = np.full((T, S), K, dtype=np.int8)     # K = 无行业归属
            for j, k in enumerate(inds):
                v = st[k].reindex(index=dates, columns=cols).values
                gid[v == 1] = j
        self.X = X
        self.K = K
        self.G = K + 1
        self.T, self.S = T, S
        self.gid = gid
        self.covered = gid < K
        self.flat_key = (np.repeat(np.arange(T, dtype=np.int64) * self.G, S)
                         + gid.ravel().astype(np.int64))
        log(f"  BARRA: 行业 {K} 个; 每日有行业归属的股票数 "
            f"{int(self.covered[0].sum())}(首日) ~ {int(self.covered[-1].sum())}(末日) / {S}")

    def __call__(self, Y):
        T, S, G = self.T, self.S, self.G
        Y = np.asarray(Y, dtype=np.float32)
        m0 = np.isfinite(Y) & np.isfinite(self.X) & self.covered
        idx = np.flatnonzero(m0.ravel())
        kk = self.flat_key[idx]
        fy = Y.ravel()[idx]
        fx = self.X.ravel()[idx]
        sy = np.bincount(kk, weights=fy, minlength=T * G)
        sx = np.bincount(kk, weights=fx, minlength=T * G)
        cnt = np.bincount(kk, minlength=T * G).astype(np.float64)
        c = np.maximum(cnt, 1.0)
        grp_y = (sy / c).reshape(T, G)
        grp_x = (sx / c).reshape(T, G)
        my = grp_y.ravel()[self.flat_key].reshape(T, S).astype(np.float32)
        mx = grp_x.ravel()[self.flat_key].reshape(T, S).astype(np.float32)
        del idx, kk, fy, fx
        yd = np.where(m0, Y - my, np.float32(0.0))
        xd = np.where(m0, self.X - mx, np.float32(0.0))
        num = np.sum(yd * xd, axis=1, dtype=np.float64)
        den = np.sum(xd * xd, axis=1, dtype=np.float64)
        b = np.where(den > 1e-9, num / np.where(den == 0, 1, den), 0.0)
        out = np.where(m0, yd - (b[:, None] * xd).astype(np.float32), np.nan)
        del yd, xd
        return out


# ==================== 因子构造 ====================
def gen_factors(FP, mkt):
    """逐产出 (name, (T,S) float32), 方向已按"越大越好"校正"""
    g = FP.daily

    # ---------- 估值 ----------
    np_ttm = g('np_parent_company_ownersTTM')
    ni_ttm = g('net_profitTTM')
    rev_ttm = g('operating_revenueTTM')
    cfo_ttm = g('net_operate_cashflowTTM')
    ebit_ttm = g('ebitTTM')
    gp_ttm = g('gross_profitTTM')
    eq = g('equity_parent_company')
    ta = g('total_assets')
    tl = g('total_liabilities')

    yield 'ep_ttm', sd(np_ttm, mkt)
    yield 'ep_ttm_all', sd(ni_ttm, mkt)
    yield 'bp', sd(eq, mkt)
    yield 'sp_ttm', sd(rev_ttm, mkt)
    yield 'cfp_ttm', sd(cfo_ttm, mkt)
    yield 'gp_mc', sd(gp_ttm, mkt)
    yield 'ebit_ev', sd(ebit_ttm, mkt + tl)

    # ---------- 盈利 ----------
    yield 'roe_ttm', sd(np_ttm, eq)
    yield 'roe_waa', g('return_on_equity_weighted_average')
    yield 'roa_ttm', sd(ni_ttm, ta)
    yield 'roic_ttm', sd(ebit_ttm, ta - np.where(np.isfinite(g('current_liabilities')),
                                                 g('current_liabilities'), 0.0))
    yield 'gross_margin_ttm', sd(gp_ttm, rev_ttm)
    yield 'net_margin_ttm', sd(ni_ttm, rev_ttm)
    yield 'op_margin_ttm', sd(g('operating_profitTTM'), rev_ttm)
    yield 'cost_ratio_neg', -sd(g('operating_costTTM'), rev_ttm)
    yield 'eps_ttm', sd(np_ttm, g('total_shares'))
    yield 'gp_asset', sd(gp_ttm, ta)

    # ---------- 成长 (q vs q-4) ----------
    rev = g('operating_revenue')
    npq = g('net_profit_parent_company')
    ded = g('net_profit_deduct_non_recurring_pnl')
    eps = g('basic_earnings_per_share')
    roe = sd(np_ttm, eq)
    nmg = sd(ni_ttm, rev_ttm)
    yield 'rev_yoy', sd(rev, g('operating_revenue', 4)) - 1.0
    yield 'np_yoy', sd(npq, g('net_profit_parent_company', 4)) - 1.0
    yield 'npttm_yoy', sd(ni_ttm, g('net_profitTTM', 4)) - 1.0
    yield 'revttm_yoy', sd(rev_ttm, g('operating_revenueTTM', 4)) - 1.0
    yield 'dednp_yoy', sd(ded, g('net_profit_deduct_non_recurring_pnl', 4)) - 1.0
    yield 'eps_yoy', sd(eps, g('basic_earnings_per_share', 4)) - 1.0
    yield 'cfottm_yoy', sd(cfo_ttm, g('net_operate_cashflowTTM', 4)) - 1.0
    yield 'roe_chg', roe - sd(g('np_parent_company_ownersTTM', 4), g('equity_parent_company', 4))
    yield 'margin_chg', nmg - sd(g('net_profitTTM', 4), g('operating_revenueTTM', 4))
    yield 'asset_growth_neg', -(sd(ta, g('total_assets', 4)) - 1.0)
    yield 'equity_growth', sd(eq, g('equity_parent_company', 4)) - 1.0

    # ---------- 质量 ----------
    ca = g('current_assets')
    cl = g('current_liabilities')
    ar = g('net_accts_receivable')
    inv = g('inventory')
    npt = g('net_profit')
    nrc = g('non_recurring_pnl')
    yield 'cfo_np', sd(cfo_ttm, ni_ttm)
    yield 'accrual_neg', -sd(ni_ttm - cfo_ttm, ta)
    yield 'debt_asset_neg', -sd(tl, ta)
    yield 'current_ratio', sd(ca, cl)
    yield 'equity_liab', sd(g('total_equity'), tl)
    yield 'asset_turnover', sd(rev_ttm, ta)
    yield 'ar_ratio_neg', -sd(ar, rev_ttm)
    yield 'inv_asset_neg', -sd(inv, ta)
    yield 'nonrecur_neg', -sd(nrc, npt)

    # ---------- 规模 (sanity check: 中性化后应归零) ----------
    yield 'ln_assets', np.log(np.where(ta > 0, ta, np.nan)).astype(np.float32)
    yield 'ln_equity', np.log(np.where(eq > 0, eq, np.nan)).astype(np.float32)
    yield 'ln_shares', np.log(np.where(g('total_shares') > 0,
                                       g('total_shares'), np.nan)).astype(np.float32)
    yield 'circ_ratio', sd(g('circulation_a_shares'), g('total_shares'))


# ==================== 主流程 ====================
def main():
    log("[1] 载入面板")
    P = load_panel(['close', 'mktcap'])
    close = P['close'].astype('float64')
    dates = close.index.values
    cols = list(close.columns)
    mkt = P['mktcap'].reindex(index=close.index, columns=cols).values.astype(np.float32)
    log(f"  close {close.shape}  {dates.min()}~{dates.max()}  mktcap NaN%={np.isnan(mkt).mean()*100:.1f}")

    FP = FundPanels(GRID, dates)
    log(f"  fund_grid: Q={FP.Q} {FP.qs[0]}~{FP.qs[-1]}, S={FP.S}, 字段 {len(FP.val)}")

    log("[2] BARRA 中性化器")
    BN = BarraNeut(BARRA, dates, cols)

    # 一致性自检: 与 round4 的 lstsq 版本对比
    _check(BN, FP, dates, cols)

    log("[3] 三组检验 (raw / lnmc / barra)")
    rows, ic_store = [], {}
    nf = 0
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    for name, arr in gen_factors(FP, mkt):
        nf += 1
        if lim and nf > lim:
            break
        fac = pd.DataFrame(arr, index=dates, columns=cols)
        cov = float(np.isfinite(arr).mean())
        if np.isfinite(arr[dates >= START]).sum() == 0:
            log(f"  [{nf}] {name} 无数据, 跳过")
            del fac, arr
            continue
        for mode in ['raw', 'lnmc', 'barra']:
            if mode == 'raw':
                X = fac.values
            elif mode == 'lnmc':
                X = cs_neutralize_lnmc(fac.values, mkt.astype(np.float64))
            else:
                X = BN(fac.values)
            if not np.isfinite(X).any():
                continue
            f = cs_rank(pd.DataFrame(X, index=dates, columns=cols))
            r = evaluate(f, close, name)
            del f, X
            if r is None:
                continue
            ic_store[f'{name}|{mode}'] = r.pop('ic_series')
            ok, msg = pass_filter(r)
            r['mode'] = mode
            r['cov'] = cov
            r['pass'] = 'PASS' if ok else msg[:36]
            rows.append(r)
            gc.collect()
        rr = [x for x in rows if x['name'] == name]
        for x in rr:
            log(f"  [{nf:>2}] {name:18s} {x['mode']:5s} cov={cov*100:4.1f}% "
                f"IC={x['ic']:+.4f} IR={x['ic_ir']:+.3f} 超额={x['ann_ex']*100:+6.2f}% "
                f"Calmar={x['calmar'] if x['calmar'] else 0:5.2f} | {x['pass']}")
        del fac, arr
        gc.collect()

    res = pd.DataFrame(rows)
    res.to_csv(OUT_CSV, index=False, encoding='utf-8-sig')
    with open(OUT_IC, 'wb') as f:
        pickle.dump(ic_store, f)

    for mode in ['raw', 'lnmc', 'barra']:
        sub = res[res['mode'] == mode].sort_values('ann_ex', ascending=False)
        if not len(sub):
            continue
        log("\n" + "=" * 100)
        log(f"Round5 财报因子 [{mode}] 按超额排序")
        log("=" * 100)
        cc = ['name', 'ic', 'ic_ir', 'ic_win', 'ann_ex', 'dd', 'calmar', 'last_yr', 'pass']
        log(sub[cc].round(4).to_string(index=False))
        log(f"  通过: {(sub['pass'] == 'PASS').sum()}/{len(sub)}")

    log(f"\n已保存 {OUT_CSV} / {OUT_IC}   耗时 {time.time()-t0:.0f}s")


def _check(BN, FP, dates, cols):
    """用 40 个交易日核对 FWL 向量化版 == lstsq 版"""
    y = FP.daily('net_profitTTM')
    sub = np.where(dates >= 20180101)[0][:40]
    R1 = BN(pd.DataFrame(y, index=dates, columns=cols).values)[sub]
    with pd.HDFStore(BARRA, 'r') as st:
        keys = [k.strip('/') for k in st.keys()]
        inds = [k for k in keys if k not in BarraNeut.STYLE]
        mats = [st[c].reindex(index=dates, columns=cols).values[sub]
                for c in ['size'] + inds]
    X = np.stack(mats, axis=2)
    Y = pd.DataFrame(y, index=dates, columns=cols).values[sub]
    R2 = np.full(Y.shape, np.nan)
    for i in range(len(sub)):
        Xi, yi = X[i], Y[i]
        m = np.isfinite(yi) & np.isfinite(Xi).all(axis=1)
        if m.sum() < 100:
            continue
        A = np.column_stack([np.ones(m.sum()), Xi[m]])
        beta, *_ = np.linalg.lstsq(A, yi[m], rcond=None)
        R2[i, m] = yi[m] - A @ beta
    d = np.nanmax(np.abs(R1 - R2))
    log(f"  中性化一致性自检: max|diff| = {d:.3e}  (样本 {np.isfinite(R1).sum()})")


if __name__ == '__main__':
    main()
