# -*- coding: utf-8 -*-
"""自由流通股本的两条可能路径:
  A) E:\rq\others\ (10927个文件) 里是否有股东持股数据 -> 可自算自由流通
  B) 指数成分 h5 的 weights -> 可反推成分股的自由流通市值
  C) bundle stocks.h5 是否自带股本字段
"""
import os
import glob
import numpy as np
import pandas as pd
import h5py

print("=" * 70)
print("A) E:\\rq\\others\\ 目录")
o = r'E:\rq\others'
if os.path.isdir(o):
    subs = sorted(os.listdir(o))
    print(f"  子目录/文件 {len(subs)} 个, 前 20: {subs[:20]}")
    for s in subs[:6]:
        fp = os.path.join(o, s)
        if os.path.isdir(fp):
            fs = sorted(os.listdir(fp))
            print(f"    {s}/ ({len(fs)} 个) 前5: {fs[:5]}")
        else:
            print(f"    {s}  {os.path.getsize(fp)/1e6:.1f}MB")

print("\n" + "=" * 70)
print("B) 指数成分 weights(中证指数按自由流通市值加权 -> 可反推)")
IP = r'E:\rq\constituents\index'
fs = sorted(glob.glob(os.path.join(IP, '*.h5')))
print(f"  指数文件 {len(fs)} 个: {[os.path.basename(x) for x in fs]}")
for f_ in fs[:3]:
    with h5py.File(f_, 'r') as f:
        cd = f['change_dates'][:].astype(str)
        d0, dlast = cd[0], cd[-1]
        w = f['weights'][d0][:]
        c = f['components'][d0][:]
        c = np.array([x.decode() if isinstance(x, bytes) else str(x) for x in c])
        print(f"\n  {os.path.basename(f_)}  {d0}~{dlast}  期数 {len(cd)}")
        print(f"    {d0}: 成分 {len(c)} 只, 权重和 {np.nansum(w):.6f}, "
              f"最大 {np.nanmax(w):.6f}, 最小 {np.nanmin(w):.6f}")
        o2 = np.argsort(-w)[:5]
        print("    权重前5:", [(c[i], round(float(w[i]), 6)) for i in o2])

print("\n" + "=" * 70)
print("C) bundle stocks.h5 字段")
with h5py.File(r'E:\rq\bundle\stocks.h5', 'r') as f:
    a = f['600519.XSHG'][:]
    print("  字段:", a.dtype.names)

print("\n" + "=" * 70)
print("D) instruments.pk 字段")
try:
    ins = pd.read_pickle(r'E:\rq\bundle\instruments.pk')
    print(f"  {len(ins)} 条, 字段: {list(ins.columns) if hasattr(ins,'columns') else type(ins)}")
    if hasattr(ins, 'columns'):
        print(ins.head(2).to_string())
except Exception as e:
    print("  ", e)
