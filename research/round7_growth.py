# -*- coding: utf-8 -*-
"""
Round 7: 「基本面成长复合」合成 + 稳健性/正交性检验
====================================================
成分(Round6 四口径同向为正的5个 + Round5c combo_growth 的5个):
  G6 : inc_op_profit_qoq, inc_total_rev_qoq, sq_op_yoy, sq_np_yoy2, ocf_to_asset
  G5b: sq_np_yoy, sq_rev_yoy, ttm_np_chg, ttm_rev_chg, sue_np
复合:
  combo_g6   G6 等权rank
  combo_g5b  G5b 等权rank(=Round5c combo_growth)
  combo_all  10个等权rank
  combo_qoq  纯环比族(4个)
  combo_sq   单季同比族(5个)
检验:
  1) 四口径 raw / lnmc(B) / barra(B) / strat(D)
  2) 分段 2018-2021 / 2022-2026 (barra + strat)
  3) 小市值池内(市值最小30%/50%内选股 vs 该池等权) —— 贴合 all03 的实际使用场景
  4) 与 ln_mktcap(小市值因子) 的 IC 相关性 —— 正交性
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
import factor_miner as fm
from factor_miner import load_panel, evaluate, pass_filter, cs_rank
from round5_fund import (FundPanels, BarraNeut, cs_neutralize_lnmc, sd, log,
                         build_size_bucket, strat_rank, ind_demean)
from round5b_fund import make_sq, growth, ratio

DEV = os.path.join(HERE, 'all01_dev')
GRID = os.path.join(DEV, 'fund_grid_jq.pkl')
OUT_CSV = os.path.join(HERE, 'round7_growth.csv')
OUT_IC = os.path.join(HERE, 'ic_round7.pkl')
NB = 20

G6 = ['inc_op_profit_qoq', 'inc_total_rev_qoq', 'sq_op_yoy', 'sq_np_yoy2', 'ocf_to_asset']
G5B = ['sq_np_yoy', 'sq_rev_yoy', 'ttm_np_chg', 'ttm_rev_chg', 'sue_np']
QOQ = ['inc_op_profit_qoq', 'inc_total_rev_qoq', 'ttm_np_chg', 'ttm_rev_chg']
SQ = ['sq_op_yoy', 'sq_np_yoy2', 'sq_np_yoy', 'sq_rev_yoy', 'sue_np']

t0 = time.time()


def build_components(FP):
    g = FP.daily
    sq, sq_lag = make_sq(FP)

    def ttm_sq(fld, lag=0):
        return g(fld, lag) - g(fld, lag + 1)

    F = {}
    # ---- Round6 五虎 ----
    F['inc_op_profit_qoq'] = growth(g('operating_profitTTM'),
                                    g('operating_profitTTM', 1))
    F['inc_total_rev_qoq'] = growth(g('total_operating_revenueTTM'),
                                    g('total_operating_revenueTTM', 1))
    F['sq_op_yoy'] = growth(ttm_sq('operating_profitTTM', 0),
                            ttm_sq('operating_profitTTM', 4))
    F['sq_np_yoy2'] = growth(ttm_sq('net_profitTTM', 0),
                             ttm_sq('net_profitTTM', 4))
    F['ocf_to_asset'] = ratio(g('net_operate_cashflowTTM'), g('total_assets'))
    gc.collect()
    # ---- Round5b combo_growth 成分 ----
    F['sq_np_yoy'] = growth(sq('net_profit_parent_company'),
                            sq_lag('net_profit_parent_company', 4))
    F['sq_rev_yoy'] = growth(sq('operating_revenue'),
                             sq_lag('operating_revenue', 4))
    F['ttm_np_chg'] = growth(g('net_profitTTM'), g('net_profitTTM', 1))
    F['ttm_rev_chg'] = growth(g('operating_revenueTTM'), g('operating_revenueTTM', 1))
    s0 = sq('net_profit_parent_company')
    s4 = sq_lag('net_profit_parent_company', 4)
    acc = np.zeros_like(s0)
    acc2 = np.zeros_like(s0)
    cnt = np.zeros_like(s0)
    for n in range(1, 9):
        v = sq_lag('net_profit_parent_company', n)
        m = np.isfinite(v)
        acc += np.where(m, v, 0.0)
        acc2 += np.where(m, v * v, 0.0)
        cnt += m
        del v, m
    cnt = np.maximum(cnt, 1)
    mean = acc / cnt
    std = np.sqrt(np.maximum(acc2 / cnt - mean * mean, 0))
    F['sue_np'] = np.where(std > 1e-6, (s0 - s4) / np.where(std > 1e-6, std, 1),
                           np.nan).astype(np.float32)
    del s0, s4, acc, acc2, cnt, mean, std
    gc.collect()
    return F


class Runner(object):
    def __init__(self, close, mkt, BN, bkt):
        self.close = close
        self.dates = close.index.values
        self.cols = list(close.columns)
        self.mkt = mkt
        self.mkt64 = mkt.astype(np.float64)
        self.BN = BN
        self.bkt = bkt
        self.rows = []
        self.ic = {}

    def transform(self, arr, mode):
        fac = pd.DataFrame(arr, index=self.dates, columns=self.cols)
        rk = cs_rank(fac).values
        if mode == 'raw':
            return rk
        if mode == 'lnmc':
            return cs_neutralize_lnmc(rk, self.mkt64)
        if mode == 'barra':
            return self.BN(rk)
        if mode == 'strat':
            return ind_demean(strat_rank(rk, self.bkt, NB), self.BN)
        raise ValueError(mode)

    def run(self, name, arr, mode, tag='', start=None, end=None, extra=None):
        """extra: (T,S) bool 额外样本限制(如小市值池)"""
        X = self.transform(arr, mode)
        if extra is not None:
            X = np.where(extra, X, np.nan)
        X = np.asarray(X, dtype=np.float64)
        if start is not None:
            X = np.where((self.dates >= start)[:, None], X, np.nan)
        if end is not None:
            X = np.where((self.dates <= end)[:, None], X, np.nan)
        r = evaluate(cs_rank(pd.DataFrame(X, index=self.dates, columns=self.cols)),
                     self.close, name)
        del X
        gc.collect()
        if r is None:
            log(f"  {name:16s} {mode:5s} {tag} 样本不足")
            return None
        self.ic[f'{name}|{mode}|{tag}'] = r.pop('ic_series')
        ok, msg = pass_filter(r)
        r['mode'] = mode
        r['tag'] = tag
        r['pass'] = 'PASS' if ok else msg[:40]
        self.rows.append(r)
        log(f"  {name:16s} {mode:5s} {tag:12s} IC={r['ic']:+.4f} IR={r['ic_ir']:+.3f} "
            f"超额={r['ann_ex']*100:+6.2f}% 回撤={r['dd']*100:5.1f}% "
            f"Calmar={r['calmar'] if r['calmar'] else 0:5.2f} 最近年={r['last_yr']*100:+5.1f}% "
            f"| {r['pass']}")
        return r


def main():
    log("[1] 载入")
    P = load_panel(['close', 'mktcap'])
    close = P['close'].astype('float64')
    dates = close.index.values
    cols = list(close.columns)
    mkt = P['mktcap'].reindex(index=dates, columns=cols).values.astype(np.float32)
    FP = FundPanels(GRID, dates)
    BN = BarraNeut(os.path.join(HERE, 'barra.h5'), dates, cols)
    bkt = build_size_bucket(mkt, NB)
    R = Runner(close, mkt, BN, bkt)

    log("[2] 构造成分")
    F = build_components(FP)

    def combo(names):
        acc, n = None, None
        for c in names:
            rk = cs_rank(pd.DataFrame(F[c], index=dates, columns=cols)).values
            good = np.isfinite(rk)
            v = np.where(good, rk, 0.0)
            acc = v if acc is None else acc + v
            n = good.astype(np.float32) if n is None else n + good.astype(np.float32)
            del rk, v, good
        return (acc / np.maximum(n, 1.0)).astype(np.float32)

    C = {}
    C['combo_g6'] = combo(G6)
    C['combo_g5b'] = combo(G5B)
    C['combo_all'] = combo(G6 + G5B)
    C['combo_qoq'] = combo(QOQ)
    C['combo_sq'] = combo(SQ)
    del F
    gc.collect()

    log("\n[3] 四口径检验")
    for nm in ['combo_all', 'combo_g6', 'combo_g5b', 'combo_qoq', 'combo_sq']:
        for mode in ['raw', 'lnmc', 'barra', 'strat']:
            R.run(nm, C[nm], mode)

    log("\n[4] 分段稳健性(barra / strat)")
    for nm in ['combo_all', 'combo_g6']:
        for (s, e, tg) in [(20180101, 20211231, '2018-2021'),
                           (20220101, 20260831, '2022-2026')]:
            for mode in ['barra', 'strat']:
                R.run(nm, C[nm], mode, tag=tg, start=s, end=e)

    log("\n[5] 小市值池内选股(贴合 all03: 池内选股 vs 该池等权)")
    mc = pd.DataFrame(mkt, index=dates, columns=cols)
    pct30 = mc.rank(axis=1, pct=True) <= 0.30
    pct50 = mc.rank(axis=1, pct=True) <= 0.50
    for nm in ['combo_all', 'combo_g6']:
        for q, msk in [(0.3, pct30), (0.5, pct50)]:
            for mode in ['raw', 'barra']:
                R.run(nm, C[nm], mode, tag=f'小市值{int(q*100)}%', extra=msk.values)

    res = pd.DataFrame(R.rows)
    res.to_csv(OUT_CSV, index=False, encoding='utf-8-sig')
    with open(OUT_IC, 'wb') as f:
        pickle.dump(R.ic, f)

    log("\n[6] 正交性: 与 ln_mktcap(小市值因子) 的 IC 相关性")
    lnmc = (-np.log(np.where(mkt > 0, mkt, np.nan))).astype(np.float32)
    for mode in ['raw', 'barra']:
        r = R.run('ln_mktcap', lnmc, mode, tag='正交对照')
        if r is None:
            continue
        key_g = f'combo_all|{mode}|'
        key_m = f'ln_mktcap|{mode}|正交对照'
        if key_g in R.ic and key_m in R.ic:
            a, b = R.ic[key_g].align(R.ic[key_m], join='inner')
            c = a.corr(b)
            log(f"  corr(IC_combo_all, IC_ln_mktcap) [{mode}] = {c:+.3f}")

    log("\n[7] 汇总")
    sub = res[~res['tag'].astype(str).str.contains('小市值')]
    log(sub[['name', 'mode', 'tag', 'ic', 'ic_ir', 'ann_ex', 'dd', 'calmar',
             'last_yr', 'pass']].round(4).to_string(index=False))
    sm = res[res['tag'].astype(str).str.contains('小市值')]
    log("\n小市值池内:")
    log(sm[['name', 'mode', 'tag', 'ic', 'ic_ir', 'ann_ex', 'dd', 'calmar',
            'pass']].round(4).to_string(index=False))
    log(f"\n已保存 {OUT_CSV}  耗时 {time.time()-t0:.0f}s")


if __name__ == '__main__':
    main()
