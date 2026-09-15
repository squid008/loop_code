# -*- coding: utf-8 -*-
"""指数 weights 长表: 成分数量与覆盖范围(能否反推自由流通市值)"""
import os
import glob
import numpy as np
import pandas as pd
import h5py

for fp in sorted(glob.glob(r'E:\rq\constituents\index\*.h5')):
    with h5py.File(fp, 'r') as f:
        g = f['weights']
        ob = [x.decode() if isinstance(x, bytes) else str(x) for x in g['order_book_id'][:]]
        df = pd.DataFrame({'d': g['date'][:].astype(str), 'ob': ob,
                           'w': g['weight'][:]})
    last = df['d'].max()
    s = df[df['d'] == last]
    print("%-16s 记录%9d 期数%5d 最近%s 成分%5d只 权重和%.4f"
          % (os.path.basename(fp), len(df), df['d'].nunique(), last,
             len(s), s['w'].sum()))

# 用沪深300 权重反推自由流通市值, 与自有流通市值比较
print("\n" + "=" * 70)
fp = r'E:\rq\constituents\index\000300.XSHG.h5'
with h5py.File(fp, 'r') as f:
    g = f['weights']
    ob = [x.decode() if isinstance(x, bytes) else str(x) for x in g['order_book_id'][:]]
    df = pd.DataFrame({'d': g['date'][:].astype(str), 'ob': ob, 'w': g['weight'][:]})
snap = pd.read_pickle(r'd:\rqalpha_demo\strategies\all01\factor_snapshot.pkl')
last_snap = int(snap['date'].max())
s0 = snap[snap['date'] == last_snap].set_index('obid')
# 找最接近的指数调仓日
idx_dates = sorted(df['d'].unique())
d = [x for x in idx_dates if x.replace('-', '') <= str(last_snap)]
d = d[-1] if d else idx_dates[0]
sub = df[df['d'] == d].set_index('ob')
print(f"指数日 {d}, 快照日 {last_snap}, 成分 {len(sub)} 只")
j = sub.join(s0[['close', 'mktcap', 'circ_mktcap']], how='inner')
print(f"  可比对 {len(j)} 只")
j['ff_implied'] = j['w'] / j['close']          # 权重/价格 ∝ 自由流通股数(未定标)
j['ratio_ff_circ'] = j['ff_implied'] / (j['circ_mktcap'] / j['close'])
print("  隐含自由流通股数 / 流通股数 的分位:")
print(j['ratio_ff_circ'].describe(percentiles=[.05, .25, .5, .75, .95]).round(5).to_string())
print("\n  注: 该比值应= (自由流通比例 × 靠档系数) / 指数总自由流通市值常数;")
print("      若各股票比值差异大 => 确实含自由流通信息(可定标后使用)")
