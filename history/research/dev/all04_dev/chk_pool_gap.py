# -*- coding: utf-8 -*-
"""
诊断: 策略选股池 vs 研究 universe 的差距
研究 evaluate() 只在 universe.h5(非ST/非停牌/上市≥250日/20日均成交额≥1000万/非涨跌停, 占57.9%)
内选股; all04_barra.py 的过滤更松(仅剔ST/停牌/涨停/新股/科创北交)
-> 看 g6(barra) Top300 里有多少落在研究 universe 内
"""
import os
import sys
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from factor_miner import get_universe, load_panel

G6 = r'd:\rqalpha_demo\strategies\all04\g6_daily.pkl'

g6 = pd.read_pickle(G6)['barra']
U = get_universe().reindex(index=g6.index, columns=g6.columns).fillna(False)
P = load_panel(['turnover', 'mktcap'])
amt20 = P['turnover'].rolling(20, min_periods=10).mean().reindex(
    index=g6.index, columns=g6.columns)
mc = P['mktcap'].reindex(index=g6.index, columns=g6.columns)
print(f"g6 {g6.shape}, universe 占比 {U.values.mean()*100:.1f}%")

rows = []
for d in [20180102, 20190603, 20210301, 20230601, 20250303]:
    i = g6.index.searchsorted(d)
    if i >= len(g6.index):
        continue
    dd = g6.index[i]
    row = g6.loc[dd].dropna().sort_values(ascending=False)
    top = row.index[:300]
    inU = U.loc[dd, top]
    a20 = amt20.loc[dd, top]
    mcv = mc.loc[dd, top]
    rows.append(dict(日期=dd, Top300在universe内=f"{inU.mean()*100:.0f}%",
                     Top300中位20日均成交额=f"{a20.median()/1e8:.2f}亿",
                     Top300中位市值=f"{mcv.median()/1e8:.1f}亿",
                     全市场中位20日均成交额=f"{amt20.loc[dd].median()/1e8:.2f}亿",
                     全市场中位市值=f"{mc.loc[dd].median()/1e8:.1f}亿"))
df = pd.DataFrame(rows)
print("\ng6(barra) Top300 的特征:")
print(df.to_string(index=False))

# 全市场 vs universe 的对比(同一天)
d = 20230601
i = g6.index.searchsorted(d)
dd = g6.index[i]
u = U.loc[dd]
print(f"\n{dd}: universe 内 {int(u.sum())} 只 / 全市场有限值 {int(np.isfinite(g6.loc[dd]).sum())} 只")
print(f"  universe内 中位20日均成交额 {amt20.loc[dd][u].median()/1e8:.2f}亿, "
      f"中位市值 {mc.loc[dd][u].median()/1e8:.1f}亿")
print(f"  universe外 中位20日均成交额 {amt20.loc[dd][~u].median()/1e8:.2f}亿, "
      f"中位市值 {mc.loc[dd][~u].median()/1e8:.1f}亿")
