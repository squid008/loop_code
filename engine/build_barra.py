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
# 只保留连续风格(入叶, 量纲 R); 行业哑变量不入叶/不入盘
STYLES = ['size', 'non_linear_size', 'momentum', 'liquidity', 'book_to_price',
          'leverage', 'growth', 'earnings_yield', 'beta', 'residual_volatility',
          'comovement']

t0 = time.time()
files = sorted(glob.glob(os.path.join(SRC, '*.h5')))
print(f"文件数: {len(files)}")

df0 = pd.read_hdf(files[0], key='data')
print(f"样本 {os.path.basename(files[0])}: shape={df0.shape}")
print(f"  index 类型: {type(df0.index)}, 样例 {df0.index[:2].tolist()}")
cols = [c for c in STYLES if c in df0.columns]
print(f"  入盘风格({len(cols)}): {cols}")

# 对齐 panel.h5 的 date(int) x code 坐标(2013-2026), 超范围/缺失一律 NaN
PANEL = os.path.join(HERE, 'panel.h5')
with pd.HDFStore(PANEL, 'r') as st:
    _c = st['close']
    TARGET_IDX = np.asarray(_c.index, dtype=np.int64)
    TARGET_COLS = list(_c.columns)
print(f"对齐坐标: {len(TARGET_IDX)} 日 x {len(TARGET_COLS)} 股")

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
        d = d.reindex(index=TARGET_IDX, columns=TARGET_COLS).astype('float32')
        st['barra_' + c] = d   # key 必须带 barra_ 前缀 = 叶子名(loop_fields.BARRA_LEAVES 单一事实源)
print(f"\n已存 {OUT}   {len(cols)} 个风格因子   总耗时 {time.time()-t0:.0f}s")

with pd.HDFStore(OUT, 'r') as st:
    for c in cols:
        d = st['barra_' + c]
        print(f"  barra_{c:20s} {d.shape}  NaN={d.isna().mean().mean()*100:.1f}%")
