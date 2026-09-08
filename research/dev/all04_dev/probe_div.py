# -*- coding: utf-8 -*-
"""核查 all03 股息率的真实数据来源: E:\rq\bundle\dividends.h5"""
import os
import numpy as np
import pandas as pd
import h5py

DIV_H5 = r'E:\rq\bundle\dividends.h5'
PIT_DIR = r'E:\rq\finance\pit'

print("文件存在:", os.path.exists(DIV_H5), f"({os.path.getsize(DIV_H5)/1e6:.1f} MB)")
with h5py.File(DIV_H5, 'r') as f:
    obids = list(f.keys())
    print(f"股票数: {len(obids)}")
    ob = '600519.XSHG' if '600519.XSHG' in f else obids[0]
    a = f[ob][:]
    print(f"\n样例 {ob}: dtype={a.dtype}")
    print("  字段:", a.dtype.names)
    df = pd.DataFrame({k: a[k] for k in a.dtype.names})
    print(f"  记录数 {len(df)}")
    print(df.tail(6).to_string(index=False))

# PIT 里有没有能算股息率的字段?
with h5py.File(os.path.join(PIT_DIR, '600519.XSHG.h5'), 'r') as f:
    have = list(f['fields'].keys())
    cand = [k for k in have if ('div' in k.lower() or 'payout' in k.lower())]
    print(f"\nPIT 中名字含 div/payout 的字段({len(cand)}):")
    for c in cand:
        v = f['fields'][c][:]
        print(f"  {c:42s} 非空 {np.isfinite(v).sum():>3}/{len(v)}  "
              f"最近值 {np.nan_to_num(v)[-1]:.4g}")
    print("\n结论: PIT 只有【财报科目】(应付股利/已付股利和利息的现金/子公司支付给少数股东的股利等),")
    print("      没有【每股派息】明细 -> 股息率必须来自 bundle 的 dividends.h5")
