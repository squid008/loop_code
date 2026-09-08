# -*- coding: utf-8 -*-
"""探针: panel.h5 / universe.h5 / barra.h5 / factor_snapshot 结构与索引格式"""
import os, sys
sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
AI = os.path.dirname(HERE)

def brief(df, nm):
    print(f"  {nm}: shape={df.shape} index_dtype={df.index.dtype} "
          f"col_dtype={df.columns.dtype} idx[{df.index[0]}..{df.index[-1]}]")

print("== panel.h5 ==")
with pd.HDFStore(os.path.join(AI, 'panel.h5'), 'r') as st:
    keys = [k.strip('/') for k in st.keys()]
    print("  keys:", keys)
    for k in keys[:6]:
        brief(st[k], k)

print("\n== universe.h5 ==")
with pd.HDFStore(os.path.join(AI, 'universe.h5'), 'r') as st:
    for k in st.keys():
        d = st[k]
        brief(d, k.strip('/'))
        print("  值类型:", d.values.dtype)

print("\n== barra.h5 ==")
with pd.HDFStore(os.path.join(AI, 'barra.h5'), 'r') as st:
    keys = [k.strip('/') for k in st.keys()]
    print("  共", len(keys), "keys 样例:", keys[:20])
    for k in keys[:2]:
        brief(st[k], k)

print("\n== factor_snapshot.pkl (strategies/all01) ==")
fp = r'D:\rqalpha_demo\strategies\all01\factor_snapshot.pkl'
if os.path.exists(fp):
    snap = pd.read_pickle(fp)
    print("  type:", type(snap).__name__)
    print("  shape:", snap.shape)
    print("  列:", list(snap.columns))
    print("  date 范围:", snap['date'].min(), "~", snap['date'].max(),
          " 调仓日数:", snap['date'].nunique())
    print("  NaN 占比:")
    for c in snap.columns:
        print(f"    {c:<14} {snap[c].isna().mean()*100:5.1f}%")
else:
    print("  不存在")

print("\n== panel 中 close 对齐检查 ==")
with pd.HDFStore(os.path.join(AI, 'panel.h5'), 'r') as st:
    close = st['close']
    print("  close:", close.shape, close.index.dtype, close.columns.dtype)
    print("  close.index 前5:", list(close.index[:5]))
    print("  close.columns 前3:", list(close.columns[:3]))
