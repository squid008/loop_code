# -*- coding: utf-8 -*-
"""
给 panel.h5 追加: 资金流(moneyflow3) + 市值(market_cap)
字段:
  mf_net     净流入额(万元)
  mf_xl      大单+特大单净流入(万元)
  mf_net_r   净流入 / 成交额
  mf_xl_r    大单特大单净流入 / 成交额
  mktcap     总市值(元)
"""
import os
import time
import glob
import h5py
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
PANEL = os.path.join(HERE, 'panel.h5')
MF = r'E:\rq\moneyflow3'
MC = r'E:\rq\others\market-cap\market_cap.h5'

t0 = time.time()

with h5py.File(os.path.join(MF, 'sid.h5'), 'r') as f:
    sids = [x.decode() if isinstance(x, bytes) else str(x) for x in f['sid'][:]]
print(f"moneyflow sid 数: {len(sids)}")

rows = []
for y in range(2013, 2027):
    p = os.path.join(MF, f'mf_{y}.h5')
    if not os.path.exists(p):
        continue
    with h5py.File(p, 'r') as f:
        d = f['data'][:]
    df = pd.DataFrame({
        'date': d['date'].astype(np.int64),
        'code': [sids[i] for i in d['sid']],
        'na': d['na'].astype(np.float64),
        'xl': (d['l_ba'] + d['x_ba'] - d['l_sa'] - d['x_sa']).astype(np.float64),
    })
    rows.append(df)
    print(f"  {y}: {len(df):,} 行  {time.time()-t0:.0f}s")
mf = pd.concat(rows, ignore_index=True)
print(f"资金流合计: {len(mf):,} 行  {mf['date'].min()}~{mf['date'].max()}")

print("转宽表 ...")
net = mf.pivot_table(index='date', columns='code', values='na', aggfunc='last')
xl = mf.pivot_table(index='date', columns='code', values='xl', aggfunc='last')
del mf, rows

print("读入成交额用于标准化 ...")
with pd.HDFStore(PANEL, 'r') as st:
    turnover = st['turnover']

common_d = net.index.intersection(turnover.index)
common_c = net.columns.intersection(turnover.columns)
print(f"  对齐: {len(common_d)} 日 x {len(common_c)} 股")

net = net.loc[common_d, common_c]
xl = xl.loc[common_d, common_c]
tv = turnover.loc[common_d, common_c].astype(np.float64)

# 净流入(万元) -> 元, 除以成交额(元)
mf_net_r = (net * 1e4) / tv
mf_xl_r = (xl * 1e4) / tv

print("写入 panel.h5 ...")
with pd.HDFStore(PANEL, 'a', complib='blosc', complevel=5) as st:
    for k, v in [('mf_net', net), ('mf_xl', xl),
                 ('mf_net_r', mf_net_r), ('mf_xl_r', mf_xl_r)]:
        v = v.astype('float32')
        if k in st:
            st.remove(k)
        st[k] = v
        print(f"  {k}: {v.shape}  {v.memory_usage(deep=True).sum()/1e6:.0f}MB")
del net, xl, mf_net_r, mf_xl_r, tv

print("\n" + "=" * 70)
print("市值 market_cap")
try:
    mc = pd.read_hdf(MC, key='data')
    print("  shape:", mc.shape, " index names:", mc.index.names)
    mc_df = mc.unstack() if mc.index.nlevels > 1 else mc
    print("  展开后:", mc_df.shape)
    with pd.HDFStore(PANEL, 'a', complib='blosc', complevel=5) as st:
        mc_df = mc_df.astype('float32')
        if 'mktcap' in st:
            st.remove('mktcap')
        st['mktcap'] = mc_df
    print("  mktcap 已写入")
except Exception as e:
    print("  ERR:", type(e).__name__, str(e)[:200])

print(f"\n总耗时 {time.time()-t0:.0f}s")
with pd.HDFStore(PANEL, 'r') as st:
    print("panel.h5 现有字段:", list(st.keys()))
