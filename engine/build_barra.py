# -*- coding: utf-8 -*-
"""构建 BARRA 因子面板 barra.h5 (date x stock)"""
import os
import glob
import time
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'barra.h5')
SRC = r'E:\rq\others\barra\v1'

t0 = time.time()
files = sorted(glob.glob(os.path.join(SRC, '*.h5')))
print(f"文件数: {len(files)}")

df0 = pd.read_hdf(files[0], key='data')
print(f"样本 {os.path.basename(files[0])}: shape={df0.shape}")
print(f"  index 类型: {type(df0.index)}, 样例 {df0.index[:2].tolist()}")
cols = list(df0.columns)
print(f"  因子({len(cols)}): {cols}")

data = {c: {} for c in cols}
n_ok = 0
for i, f in enumerate(files):
    code = os.path.basename(f)[:-3]
    try:
        df = pd.read_hdf(f, key='data')
    except Exception:
        continue
    if df.empty:
        continue
    for c in cols:
        if c in df.columns:
            data[c][code] = df[c]
    n_ok += 1
    if (i + 1) % 1500 == 0:
        print(f"  {i+1}/{len(files)}  {time.time()-t0:.0f}s")

print(f"有效股票: {n_ok}   读取耗时 {time.time()-t0:.0f}s")

with pd.HDFStore(OUT, 'w', complib='blosc', complevel=5) as st:
    for c in cols:
        d = pd.DataFrame(data[c])
        d.index = pd.to_datetime(d.index).strftime('%Y%m%d').astype('int64')
        d = d.sort_index()
        d = d[~d.index.duplicated()]
        st[c] = d.astype('float32')
print(f"\n已存 {OUT}   {len(cols)} 个因子   总耗时 {time.time()-t0:.0f}s")

with pd.HDFStore(OUT, 'r') as st:
    for c in cols[:6]:
        d = st[c]
        print(f"  {c:22s} {d.shape}  NaN={d.isna().mean().mean()*100:.1f}%")
    print(f"  ... 共 {len(cols)} 个")
