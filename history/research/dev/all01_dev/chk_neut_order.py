# -*- coding: utf-8 -*-
"""
稳健性检验: 中性化与截面排序的先后次序
  A(现行, round3/4/5口径): 中性化(原始值) -> rank -> 检验
  B(稳健口径)            : rank -> 中性化(rank) -> 检验
若两者结论差异大, 说明 A 的超额由极端值驱动的 OLS 残差贡献, 不可靠。
对照: ln_mktcap(小市值, 已知最强单因子) 应不受次序影响。
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
from round5b_fund import make_sq, growth, ratio

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

F = {}
F['ln_mktcap'] = np.log(np.where(mkt > 0, mkt, np.nan)).astype(np.float32) * -1.0
F['net_margin_ttm'] = sd(g('net_profitTTM'), g('operating_revenueTTM'))
F['op_margin_ttm'] = sd(g('operating_profitTTM'), g('operating_revenueTTM'))
F['roe_ttm'] = sd(g('np_parent_company_ownersTTM'), g('equity_parent_company'))
s_np, s_rev = sq('net_profit_parent_company'), sq('operating_revenue')
F['sq_margin'] = ratio(s_np, s_rev)
# 量价类对照: 20日反转
F['rev_20d'] = (-(close / close.shift(20) - 1.0)).values.astype(np.float32)

out = []
for nm, arr0 in F.items():
    fac = pd.DataFrame(arr0, index=dates, columns=cols)
    rk = cs_rank(fac).values
    for mode in ['lnmc', 'barra']:
        for order in ['A中性后rank', 'B先rank再中性']:
            X = (rk if order.startswith('B') else fac.values).astype(np.float64)
            if mode == 'lnmc':
                R = cs_neutralize_lnmc(X, mkt.astype(np.float64))
            else:
                R = BN(X)
            f = cs_rank(pd.DataFrame(R, index=dates, columns=cols))
            r = evaluate(f, close, nm)
            del f, R
            gc.collect()
            if r is None:
                out.append((nm, mode, order, np.nan, np.nan, np.nan))
                continue
            out.append((nm, mode, order, r['ic'], r['ann_ex'],
                        r['calmar'] if r['calmar'] else 0))
            log(f"  {nm:16s} {mode:5s} {order:12s} IC={r['ic']:+.4f} "
                f"超额={r['ann_ex']*100:+6.2f}% Calmar={r['calmar'] if r['calmar'] else 0:5.2f}")

df = pd.DataFrame(out, columns=['name', 'mode', 'order', 'ic', 'ann_ex', 'calmar'])
p = df.pivot_table(index=['name', 'mode'], columns='order',
                   values=['ic', 'ann_ex']).round(4)
log("\n" + p.to_string())
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       'chk_neut_order.txt'), 'w', encoding='utf-8') as f:
    f.write(p.to_string())
