# -*- coding: utf-8 -*-
"""探测环境 + PIT 目录 + pit_panel 结构(输出精简, 避免刷屏)"""
import os, sys, glob, time
sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)
import numpy as np
import pandas as pd

t0 = time.time()
print("== python ==", sys.version.split()[0])
import h5py
print("h5py", h5py.__version__)

PIT = r'E:\rq\finance\pit'
files = glob.glob(os.path.join(PIT, '*.h5'))
print("PIT 文件数:", len(files))
if files:
    with h5py.File(files[0], 'r') as f:
        print("样例文件:", os.path.basename(files[0]))
        print("  keys:", list(f.keys())[:12])
        print("  fields 数:", len(f['fields'].keys()))
        q = np.array([x.decode() if isinstance(x, bytes) else str(x) for x in f['quarter'][:]])
        print("  记录数:", len(q), "  quarter 样例:", q[:5])
        print("  quarter 范围:", min(q), "~", max(q))
        if 'info_date' in f:
            ida = f['info_date'][:]
            print("  info_date dtype:", ida.dtype, "样例:", ida[:3])
        if 'if_adjusted' in f:
            print("  if_adjusted dtype:", f['if_adjusted'].dtype)
        ks = list(f['fields'].keys())
        print("  fields 前20:", ks[:20])

p = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pit_panel.parquet')
print("\npit_panel.parquet:", p, os.path.exists(p))
if os.path.exists(p):
    df = pd.read_pickle(p)
    print("  行数:", len(df), " 列:", list(df.columns))
    print("  股票数:", df['order_book_id'].nunique() if 'order_book_id' in df.columns else '?')
    print("  info_date 范围:", df['info_date'].min(), "~", df['info_date'].max())
    print("  quarter 数:", df['quarter'].nunique())
    print("  head:")
    print(df.head(2).to_string())
print("\n耗时 %.0fs" % (time.time() - t0))
