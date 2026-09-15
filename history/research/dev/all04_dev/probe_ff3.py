# -*- coding: utf-8 -*-
"""查 E:\rq\others\market-cap\ 下的 7 个文件: 是否含自由流通市值"""
import os
import glob
import numpy as np
import pandas as pd
import h5py

D = r'E:\rq\others\market-cap'
fs = sorted(glob.glob(os.path.join(D, '*')))
for fp in fs:
    print("=" * 78)
    print(f"{os.path.basename(fp)}  {os.path.getsize(fp)/1e6:.1f} MB")
    try:
        with h5py.File(fp, 'r') as f:
            keys = list(f.keys())
            print(f"  顶层键数 {len(keys)}, 前8: {keys[:8]}")
            k0 = keys[0]
            v = f[k0]
            print(f"  [{k0}] type={type(v).__name__}", end='')
            if isinstance(v, h5py.Dataset):
                print(f" shape={v.shape} dtype={v.dtype}")
                if v.dtype.names:
                    print("    复合字段:", v.dtype.names)
                    a = v[:min(3, len(v))]
                    print("    样例:", a)
                else:
                    print("    样例前3:", v[:3])
            else:
                sub = list(v.keys())
                print(f" 子键数 {len(sub)}, 前5: {sub[:5]}")
                if sub:
                    sv = v[sub[0]]
                    if isinstance(sv, h5py.Dataset):
                        print(f"    [{sub[0]}] shape={sv.shape} dtype={sv.dtype}")
                        if sv.dtype.names:
                            print("      复合字段:", sv.dtype.names)
                            print("      样例:", sv[:2])
                        else:
                            print("      样例:", sv[:5])
    except Exception as e:
        print("  ERR", type(e).__name__, e)
