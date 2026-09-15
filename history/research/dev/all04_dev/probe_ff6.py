# -*- coding: utf-8 -*-
"""最后两条路: instruments.pk 字段 / 指数 weights 能否反推自由流通市值"""
import os
import glob
import numpy as np
import pandas as pd
import h5py

# 1) instruments.pk
ins = pd.read_pickle(r'E:\rq\bundle\instruments.pk')
print(f"instruments.pk: {type(ins).__name__}, {len(ins)} 条")
if isinstance(ins, list):
    o = ins[0]
    print("  元素类型:", type(o).__name__)
    print("  属性/字段:", [a for a in dir(o) if not a.startswith('_')][:40])
    for a in ['order_book_id', 'round_lot', 'total_shares', 'circulating_shares',
              'free_float_shares', 'sector_code', 'listed_date']:
        if hasattr(o, a):
            print(f"    {a} = {getattr(o, a)}")
elif hasattr(ins, 'columns'):
    print("  字段:", list(ins.columns))
    print(ins.head(2).to_string())

# 2) 指数 weights
print("\n" + "=" * 70)
IP = r'E:\rq\constituents\index'
for fp in sorted(glob.glob(os.path.join(IP, '*.h5'))):
    with h5py.File(fp, 'r') as f:
        cd = [str(x) for x in f['change_dates'][:]]
        wk = list(f['weights'].keys())
        ck = list(f['components'].keys())
        common = sorted(set(wk) & set(ck))
        d0 = common[-1] if common else None
        if d0 is None:
            print(f"{os.path.basename(fp)}: 无共有日期")
            continue
        w = f['weights'][d0][:]
        c = f['components'][d0][:]
        c = np.array([x.decode() if isinstance(x, bytes) else str(x) for x in c])
        print(f"\n{os.path.basename(fp)}: 期数 {len(cd)}, 最近 {d0}")
        print(f"  成分 {len(c)} 只, 权重和 {np.nansum(w):.8f}, "
              f"范围 [{np.nanmin(w):.8f}, {np.nanmax(w):.8f}]")
        o = np.argsort(-w)[:3]
        print("  权重前3:", [(c[i], round(float(w[i]), 6)) for i in o])
print("\n注: 中证指数(300/500/1000)按【自由流通市值·分级靠档】加权, "
      "可用 权重/收盘价 的相对比例反推成分股自由流通市值(仅成分股, 且受靠档影响)")
