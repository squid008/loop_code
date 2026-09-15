# -*- coding: utf-8 -*-
"""导出精简版拥挤度指标 -> strategies/all01/turnover_pctile.csv (策略运行依赖)"""
import os
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DST = r'D:\rqalpha_demo\strategies\all01\turnover_pctile.csv'

tc = pd.read_csv(os.path.join(HERE, 'turnover_concentration.csv'))
out = tc[['date', 'top10', 'top10_pctile_3y', 'top10_pctile_10y']].copy()
out['top10'] = out['top10'].round(6)
for c in ['top10_pctile_3y', 'top10_pctile_10y']:
    out[c] = out[c].round(6)
out.to_csv(DST, index=False)
print(f"已导出 {len(out)} 行 -> {DST}")
print(out.tail(3).to_string(index=False))
print(f"\n文件大小: {os.path.getsize(DST)/1024:.0f} KB")
