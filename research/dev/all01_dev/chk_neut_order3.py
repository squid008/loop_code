# -*- coding: utf-8 -*-
"""
四口径对比: 找出"科学口径"
  A: 中性化(原始值) -> rank                     (现行 round1~5 口径)
  B: rank -> 中性化                             (信息无损变换 + 线性剥离)
  C: 去极值(MAD5)+z-score -> 中性化 -> rank     (业界标准, 但会截断极值)
  D: 市值20层内 rank(非参数, 完全剥离市值) -> 行业内 demean -> rank
样本:
  已log/有界(量价类): ln_mktcap, amt_log, rev_20d, vol60
  裸比率(财报类)    : net_margin_ttm, roe_ttm, sq_margin
  裸厚尾(量价类)    : amt_chg = AMT5/AMT60 (放量, 极值本身有信息)
"""
import os
import sys
import gc
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from factor_miner import load_panel, evaluate, cs_rank
from round5_fund import FundPanels, BarraNeut, cs_neutralize_lnmc, sd, log
from round5b_fund import make_sq, ratio

GRID = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fund_grid.pkl')

P = load_panel(['close', 'mktcap', 'turnover'])
close = P['close'].astype('float64')
dates = close.index.values
cols = list(close.columns)
mkt = P['mktcap'].reindex(index=close.index, columns=cols).values.astype(np.float32)
amt = P['turnover'].reindex(index=close.index, columns=cols).astype('float64')
FP = FundPanels(GRID, dates)
BN = BarraNeut(os.path.join(HERE, 'barra.h5'), dates, cols)
sq, sq_lag = make_sq(FP)
g = FP.daily

NB = 20
# 市值分层(每日 20 层)
mc_rank = pd.DataFrame(mkt, index=dates, columns=cols).rank(axis=1, pct=True).values
bkt = np.where(np.isfinite(mkt), np.minimum((mc_rank * NB).astype(np.int16), NB - 1), NB)
T, S = mkt.shape
NG = NB + 1


def strat_rank(Y):
    """按 (date, 市值层) 分组做组内 rank(0~1); 非参数, 完全剥离市值的任何单调影响"""
    gg = (np.repeat(np.arange(T, dtype=np.int64), S) * NG + bkt.ravel().astype(np.int64))
    y = np.asarray(Y, dtype=np.float64).ravel()
    nan = ~np.isfinite(y)
    y2 = np.where(nan, np.inf, y)
    order = np.lexsort((y2, gg))
    gs = gg[order]
    cnt = np.bincount(gg, minlength=T * NG)
    starts = np.zeros(T * NG, dtype=np.int64)
    np.cumsum(cnt[:-1], out=starts[1:])
    pos = np.arange(len(y), dtype=np.int64) - starts[gs]
    n = cnt[gs]
    r = pos / np.maximum(n - 1, 1)
    out = np.empty(len(y), dtype=np.float64)
    out[order] = r
    out[nan] = np.nan
    del order, gs, cnt, starts, pos, n, r, y, y2, gg
    return out.reshape(T, S)


def ind_demean(Y):
    """行业内 demean(BARRA 每日行业归属)"""
    Y32 = np.asarray(Y, dtype=np.float32)
    m0 = np.isfinite(Y32) & BN.covered
    idx = np.flatnonzero(m0.ravel())
    kk = BN.flat_key[idx]
    fy = Y32.ravel()[idx]
    sy = np.bincount(kk, weights=fy, minlength=T * BN.G)
    cnt = np.maximum(np.bincount(kk, minlength=T * BN.G).astype(np.float64), 1.0)
    my = (sy / cnt).reshape(T, BN.G).ravel()[BN.flat_key].reshape(T, S)
    return np.where(m0, Y32 - my.astype(np.float32), np.nan)


def winsor_z(X):
    med = np.nanmedian(X, axis=1, keepdims=True)
    mad = np.nanmedian(np.abs(X - med), axis=1, keepdims=True) * 1.4826
    lo = med - 5 * np.maximum(mad, 1e-12)
    hi = med + 5 * np.maximum(mad, 1e-12)
    X = np.clip(X, lo, hi)
    mu = np.nanmean(X, axis=1, keepdims=True)
    s = np.nanstd(X, axis=1, keepdims=True)
    return (X - mu) / np.where(s > 1e-12, s, 1.0)


F = {}
F['ln_mktcap'] = (-np.log(np.where(mkt > 0, mkt, np.nan))).astype(np.float32)
F['amt_log'] = (-np.log(amt.rolling(20, min_periods=10).mean() + 1.0)).values.astype(np.float32)
F['rev_20d'] = (-(close / close.shift(20) - 1.0)).values.astype(np.float32)
F['vol60'] = (-close.pct_change().rolling(60, min_periods=30).std()).values.astype(np.float32)
F['amt_chg'] = (amt.rolling(5, min_periods=3).mean() /
                (amt.rolling(60, min_periods=30).mean() + 1e-9)).values.astype(np.float32)
F['net_margin_ttm'] = sd(g('net_profitTTM'), g('operating_revenueTTM'))
F['roe_ttm'] = sd(g('np_parent_company_ownersTTM'), g('equity_parent_company'))
s_np, s_rev = sq('net_profit_parent_company'), sq('operating_revenue')
F['sq_margin'] = ratio(s_np, s_rev)
del s_np, s_rev
gc.collect()

out = []
for nm, arr0 in F.items():
    raw64 = np.asarray(arr0, dtype=np.float64)
    rk = cs_rank(pd.DataFrame(raw64, index=dates, columns=cols)).values.astype(np.float64)
    wz = winsor_z(raw64)
    sr = strat_rank(raw64)                                  # D 第一步: 市值层内 rank
    for mode in ['size', 'size+ind']:
        def neut(X0):
            if mode == 'size':
                return cs_neutralize_lnmc(X0, mkt.astype(np.float64))
            return BN(X0)
        for od, X0 in [('A', raw64), ('B', rk), ('C', wz)]:
            R = neut(X0)
            r = evaluate(cs_rank(pd.DataFrame(R, index=dates, columns=cols)), close, nm)
            del R
            gc.collect()
            if r is None:
                continue
            out.append(dict(name=nm, mode=mode, order=od, ic=r['ic'], ex=r['ann_ex'],
                            calmar=r['calmar'] if r['calmar'] else 0))
        # D: 市值层内 rank (+ 行业内 demean)
        X0 = sr if mode == 'size' else np.asarray(ind_demean(sr), dtype=np.float64)
        r = evaluate(cs_rank(pd.DataFrame(X0, index=dates, columns=cols)), close, nm)
        del X0
        gc.collect()
        if r is None:
            continue
        out.append(dict(name=nm, mode=mode, order='D', ic=r['ic'], ex=r['ann_ex'],
                        calmar=r['calmar'] if r['calmar'] else 0))
    del raw64, rk, wz, sr
    gc.collect()
    log(f"  {nm} 完成")

df = pd.DataFrame(out)
p = df.pivot_table(index=['name', 'mode'], columns='order',
                   values=['ic', 'ex']).round(4)
txt = p.to_string()
log("\n" + txt)
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       'chk_neut_order3.txt'), 'w', encoding='utf-8') as f:
    f.write(txt)
