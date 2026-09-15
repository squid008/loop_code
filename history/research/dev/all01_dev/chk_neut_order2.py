# -*- coding: utf-8 -*-
"""
三种中性化口径对比(决定性判定)
  A: 中性化(原始值) -> rank          (round3/4/5 现行口径, 对极端值脆弱)
  B: rank -> 中性化(rank)            (稳健, 但只剔除线性部分)
  C: 去极值(MAD 5倍) + z-score -> 中性化 -> rank   (业界标准口径)
对照 ln_mktcap: A 理论上应退化(残差=0), B 保留非线性市值(+6.3%), C 同 A 应≈0
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

P = load_panel(['close', 'mktcap'])
close = P['close'].astype('float64')
dates = close.index.values
cols = list(close.columns)
mkt = P['mktcap'].reindex(index=close.index, columns=cols).values.astype(np.float32)
FP = FundPanels(GRID, dates)
BN = BarraNeut(os.path.join(HERE, 'barra.h5'), dates, cols)
sq, sq_lag = make_sq(FP)
g = FP.daily


def winsor_z(X):
    """截面 MAD 去极值(5倍) + z-score"""
    med = np.nanmedian(X, axis=1, keepdims=True)
    mad = np.nanmedian(np.abs(X - med), axis=1, keepdims=True) * 1.4826
    lo = med - 5 * np.maximum(mad, 1e-12)
    hi = med + 5 * np.maximum(mad, 1e-12)
    X = np.clip(X, lo, hi)
    mu = np.nanmean(X, axis=1, keepdims=True)
    sd_ = np.nanstd(X, axis=1, keepdims=True)
    return (X - mu) / np.where(sd_ > 1e-12, sd_, 1.0)


F = {}
F['ln_mktcap'] = (-np.log(np.where(mkt > 0, mkt, np.nan))).astype(np.float32)
F['net_margin_ttm'] = sd(g('net_profitTTM'), g('operating_revenueTTM'))
F['op_margin_ttm'] = sd(g('operating_profitTTM'), g('operating_revenueTTM'))
F['roe_ttm'] = sd(g('np_parent_company_ownersTTM'), g('equity_parent_company'))
s_np, s_rev = sq('net_profit_parent_company'), sq('operating_revenue')
F['sq_margin'] = ratio(s_np, s_rev)
del s_np, s_rev
F['rev_20d'] = (-(close / close.shift(20) - 1.0)).values.astype(np.float32)

out = []
for nm, arr0 in F.items():
    fac = pd.DataFrame(arr0, index=dates, columns=cols)
    rk = cs_rank(fac).values
    wz = winsor_z(fac.values.astype(np.float64))
    for mode in ['lnmc', 'barra']:
        for od, X0 in [('A', fac.values.astype(np.float64)),
                       ('B', rk.astype(np.float64)),
                       ('C', wz)]:
            if mode == 'lnmc':
                R = cs_neutralize_lnmc(X0, mkt.astype(np.float64))
            else:
                R = BN(X0)
            r = evaluate(cs_rank(pd.DataFrame(R, index=dates, columns=cols)), close, nm)
            del R
            gc.collect()
            if r is None:
                continue
            out.append(dict(name=nm, mode=mode, order=od, ic=r['ic'],
                            ann_ex=r['ann_ex'],
                            calmar=r['calmar'] if r['calmar'] else 0))
            log(f"  {nm:16s} {mode:5s} {od}  IC={r['ic']:+.4f} "
                f"超额={r['ann_ex']*100:+6.2f}% Calmar={r['calmar'] if r['calmar'] else 0:5.2f}")
    del fac, rk, wz
    gc.collect()

df = pd.DataFrame(out)
p = df.pivot_table(index=['name', 'mode'], columns='order',
                   values=['ic', 'ann_ex']).round(4)
txt = p.to_string()
log("\n" + txt)
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       'chk_neut_order2.txt'), 'w', encoding='utf-8') as f:
    f.write(txt)
