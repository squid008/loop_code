# -*- coding: utf-8 -*-
"""
因子快照 v3: 在 v2(财务PIT) 基础上增加
  - 后复权收盘价(消除除权跳空, 动量必须用)
  - 动量: mom_20(1月) / mom_250_20(12月剔除最近1月)
  - 波动率: vol_60(60日收益标准差)
  - 股息率: div_yield(过去12个月每股派息/现价, 用公告日对齐)
无未来函数: 财务按公告日; 分红按公告日; 行情只用 T 日及之前。
"""
import os
import time
import pickle
import numpy as np
import pandas as pd
import h5py

HERE = os.path.dirname(os.path.abspath(__file__))
STOCKS_H5 = r'E:\rq\bundle\stocks.h5'
EXFAC_H5 = r'E:\rq\bundle\ex_cum_factor.h5'
DIV_H5 = r'E:\rq\bundle\dividends.h5'
PIT_PKL = os.path.join(HERE, 'pit_panel.parquet')
OUT = os.path.join(HERE, 'factor_snapshot.pkl')

START, END = 20140901, 20260831
WEEKDAY = 0


def to_qidx(q):
    return int(q[:4]) * 4 + (int(q[-1]) - 1)


def ffill2d(m):
    Q, S = m.shape
    idx = np.where(~np.isnan(m), np.arange(Q)[:, None], -1)
    np.maximum.accumulate(idx, axis=0, out=idx)
    safe = np.maximum(idx, 0)
    out = m[safe, np.arange(S)[None, :]]
    out[idx < 0] = np.nan
    return out


def main():
    t0 = time.time()
    print("读取行情 + 复权因子 ...")
    with h5py.File(STOCKS_H5, 'r') as f, h5py.File(EXFAC_H5, 'r') as fe:
        obids = list(f.keys())
        base = (f['000001.XSHE']['datetime'][:] // 1000000).astype('int64')
        cal = base[(base >= START) & (base <= END)]
        pos_of = {d: i for i, d in enumerate(cal)}
        n, S = len(cal), len(obids)
        close = np.full((n, S), np.nan)
        adj = np.full((n, S), np.nan)
        vol_m = np.zeros((n, S))
        for j, ob in enumerate(obids):
            arr = f[ob][:]
            d = (arr['datetime'] // 1000000).astype('int64')
            m = (d >= START) & (d <= END)
            idx = np.array([pos_of.get(x, -1) for x in d[m]], dtype=np.int64)
            ok = idx >= 0
            close[idx[ok], j] = arr['close'][m][ok]
            vol_m[idx[ok], j] = arr['volume'][m][ok]
            if ob in fe:
                fa = fe[ob][:]
                sd = (fa['start_date'] // 1000000).astype('int64')
                fac = fa['ex_cum_factor'].astype(float)
                pf = np.searchsorted(sd, cal, side='right') - 1
                fday = np.where(pf >= 0, fac[np.clip(pf, 0, len(fac) - 1)], 1.0)
                with np.errstate(invalid='ignore'):
                    adj[:, j] = close[:, j] * fday
            else:
                adj[:, j] = close[:, j]
    print(f"  {n} 天 x {S} 股, {time.time()-t0:.0f}s")

    # 动量/波动率(后复权)
    print("计算动量/波动率 ...")
    adjdf = pd.DataFrame(adj, index=range(n))
    mom20 = (adjdf / adjdf.shift(20) - 1).values
    mom250_20 = (adjdf.shift(20) / adjdf.shift(250) - 1).values
    ret1 = adjdf.pct_change()
    vol60 = ret1.rolling(60, min_periods=30).std().values * np.sqrt(252)

    # 股息率(TTM, 按公告日)
    print("计算股息率 ...")
    div_ttm = np.zeros((n, S))
    with h5py.File(DIV_H5, 'r') as fd:
        reb_pos = None
        for j, ob in enumerate(obids):
            if ob not in fd:
                continue
            a = fd[ob][:]
            ad = a['announcement_date'].astype('int64')
            if len(ad) == 0:
                continue
            o = np.argsort(ad)
            ad, amt = ad[o], (a['dividend_cash_before_tax'] /
                              np.where(a['round_lot'] > 0, a['round_lot'], 10.0))[o]
            cum = np.concatenate([[0.0], np.cumsum(amt)])
            dates_int = np.array([int(pd.Timestamp(str(d)).strftime('%Y%m%d')) for d in cal])
            i1 = np.searchsorted(ad, dates_int, side='right')
            prev = dates_int - 10000  # 一年前
            i0 = np.searchsorted(ad, prev, side='right')
            div_ttm[:, j] = cum[i1] - cum[i0]
    print(f"  {time.time()-t0:.0f}s")

    wd = np.array([pd.Timestamp(str(d)).weekday() for d in cal])
    reb_pos = np.where(wd == WEEKDAY)[0]
    reb_dates = cal[reb_pos]
    dates_int = np.array([int(pd.Timestamp(str(d)).strftime('%Y%m%d')) for d in cal])

    # ---------------- PIT 财务 ----------------
    print("读取 PIT ...")
    pit = pd.read_pickle(PIT_PKL)
    pit = pit[pit['info_date'] <= END]
    col_of = {o: j for j, o in enumerate(obids)}
    pit = pit[pit['order_book_id'].isin(col_of)]
    qs = sorted(pit['quarter'].unique(), key=to_qidx)
    qmap = {q: i for i, q in enumerate(qs)}
    Q = len(qs)
    ar = np.arange(S)
    pit['qi'] = pit['quarter'].map(qmap)
    pit['si'] = pit['order_book_id'].map(col_of)

    FLOW = ['return_on_equity_weighted_average', 'basic_earnings_per_share',
            'net_profit_parent_company', 'net_profitTTM', 'adjusted_net_profit',
            'cash_flow_from_operating_activities', 'operating_revenueTTM']
    STOCK_F = ['total_shares', 'circulation_a_shares', 'equity_parent_company', 'total_assets']
    val, avail = {}, {}
    for k in FLOW + STOCK_F:
        sub = pit[pit[k].notna()].sort_values('info_date')
        sub = sub.drop_duplicates(['order_book_id', 'quarter'], keep='first')
        v = np.full((Q, S), np.nan)
        a = np.full((Q, S), 99999999, dtype=np.int64)
        v[sub['qi'].values, sub['si'].values] = sub[k].values.astype(float)
        a[sub['qi'].values, sub['si'].values] = sub['info_date'].values
        val[k], avail[k] = v, a
    for k in STOCK_F:
        val[k] = ffill2d(val[k])
    print(f"  quarter {Q} 个, {time.time()-t0:.0f}s")

    # ---------------- 逐调仓日 ----------------
    print("生成快照 ...")
    out = []
    for rp, d_int in zip(reb_pos, reb_dates):
        last = {}
        for k in FLOW + STOCK_F:
            mk = avail[k] <= d_int
            has = mk.any(axis=0)
            lk = np.where(has, Q - 1 - np.argmax(mk[::-1], axis=0), 0)
            last[k] = (lk, has)
        c = close[rp]
        shares = val['total_shares'][last['total_shares'][0], ar]
        circ = val['circulation_a_shares'][last['circulation_a_shares'][0], ar]
        eq = val['equity_parent_company'][last['equity_parent_company'][0], ar]
        has_any = last['total_shares'][1] & last['equity_parent_company'][1]
        with np.errstate(invalid='ignore', divide='ignore'):
            mktcap = shares * c
            circ_cap = circ * c
            pb = np.where(np.abs(eq) > 1e-6, mktcap / eq, np.nan)
            dy = np.where((c > 0) & np.isfinite(c), div_ttm[rp] / c * 100, np.nan)

        lk_roe, has_roe = last['return_on_equity_weighted_average']
        win = lk_roe[None, :] + np.arange(-4, 1)[:, None]
        clipw = np.clip(win, 0, Q - 1)
        win_ok = (win >= 0) & (avail['return_on_equity_weighted_average'][clipw, ar] <= d_int)
        roe_w = val['return_on_equity_weighted_average'][clipw, ar]
        roe_w = np.where(win_ok, roe_w, np.nan)
        roe_inc = 4 * roe_w[4] - roe_w[0] - roe_w[1] - roe_w[2] - roe_w[3]
        roe_inc[~(win_ok.all(axis=0) & has_roe)] = np.nan

        lk_np, has_np = last['net_profit_parent_company']
        i4 = np.clip(lk_np - 4, 0, Q - 1)
        np4 = val['net_profit_parent_company'][i4, ar]
        ok4 = has_np & (avail['net_profit_parent_company'][i4, ar] <= d_int) & (np.abs(np4) > 1e-6)
        np_cur = val['net_profit_parent_company'][lk_np, ar]
        np_yoy = np.where(ok4, np_cur / np4 - 1, np.nan)
        ta = val['total_assets'][last['total_assets'][0], ar]
        with np.errstate(invalid='ignore', divide='ignore'):
            roa = np.where(np.abs(ta) > 1e-6, np_cur / ta, np.nan)
            anp = val['adjusted_net_profit'][last['adjusted_net_profit'][0], ar]
            ocf = val['cash_flow_from_operating_activities'][
                last['cash_flow_from_operating_activities'][0], ar]
            ocf_np = np.where(np.abs(anp) > 1e-6, ocf / anp, np.nan)
            rev = val['operating_revenueTTM'][last['operating_revenueTTM'][0], ar]

        sel = has_any & ~np.isnan(c) & (c > 0)
        out.append(pd.DataFrame({
            'date': d_int,
            'obid': np.array(obids)[sel],
            'close': c[sel],
            'mktcap': mktcap[sel],
            'circ_mktcap': circ_cap[sel],
            'pb': pb[sel],
            'eps': val['basic_earnings_per_share'][last['basic_earnings_per_share'][0], ar][sel],
            'roe': val['return_on_equity_weighted_average'][lk_roe, ar][sel],
            'roe_inc': roe_inc[sel],
            'np_yoy': np_yoy[sel],
            'roa': roa[sel],
            'ocf_np': ocf_np[sel],
            'revenue_ttm': rev[sel],
            'div_yield': dy[sel],
            'mom20': mom20[rp][sel],
            'mom250_20': mom250_20[rp][sel],
            'vol60': vol60[rp][sel],
            'volume': vol_m[rp][sel],
        }))

    snap = pd.concat(out, ignore_index=True)
    print(f"快照 {len(snap):,} 行, 调仓日 {snap['date'].nunique()} 个, {time.time()-t0:.0f}s")
    print("\n字段覆盖率:")
    for c in ['mktcap', 'pb', 'roe', 'roe_inc', 'np_yoy', 'roa', 'div_yield',
              'mom20', 'mom250_20', 'vol60']:
        print(f"  {c:<12} {snap[c].notna().mean()*100:5.1f}%")
    with open(OUT, 'wb') as f:
        pickle.dump(snap, f, protocol=4)
    print(f"\n已保存: {OUT}   {time.time()-t0:.0f}s")


if __name__ == '__main__':
    main()
