# -*- coding: utf-8 -*-
"""找自由流通股本(free float)数据: 搜 PIT 字段 / PIT 顶层结构 / bundle / E:\rq 其他目录"""
import os
import glob
import numpy as np
import h5py

PIT_DIR = r'E:\rq\finance\pit'
RQ = r'E:\rq'
BUNDLE = r'E:\rq\bundle'

KW = ['free', 'float', 'tradable', 'negotiable', 'liquid', 'public']

# 1) PIT 顶层结构 + 字段名搜索
p = os.path.join(PIT_DIR, '600519.XSHG.h5')
with h5py.File(p, 'r') as f:
    print("PIT 单文件顶层键:", list(f.keys()))
    have = list(f['fields'].keys())
    print(f"fields 字段数: {len(have)}")
    hits = [k for k in have if any(w in k.lower() for w in KW)]
    print(f"含 free/float/tradable 等的字段: {hits}")
    # 股本相关全部字段
    share_kw = ['share', 'capital', 'equity_share']
    print("含 share/capital 的字段:",
          [k for k in have if any(w in k.lower() for w in share_kw)])

# 2) 全量字段文件里再搜一遍
for fn in [r'd:\rqalpha_demo\ai_test\all01_dev\pit_fields_full.txt',
           r'd:\rqalpha_demo\ai_test\pit_fields.txt']:
    if os.path.exists(fn):
        txt = open(fn, 'rb').read().decode('utf-8', 'ignore')
        hits = sorted(set(w for w in txt.replace("'", ' ').replace('[', ' ')
                          .replace(']', ' ').split()
                          if any(k in w.lower() for k in KW)))
        print(f"\n{os.path.basename(fn)} 命中: {hits}")

# 3) E:\rq 下有哪些数据集
print("\nE:\\rq 目录:")
for x in sorted(os.listdir(RQ)):
    fp = os.path.join(RQ, x)
    n = len(glob.glob(os.path.join(fp, '**', '*.*'), recursive=True)) if os.path.isdir(fp) else 0
    print(f"  {x:20s} {'<dir>' if os.path.isdir(fp) else '<file>'}  文件数~{n}")

# 4) bundle 里有什么
print("\nbundle 目录:")
for x in sorted(os.listdir(BUNDLE))[:40]:
    fp = os.path.join(BUNDLE, x)
    sz = os.path.getsize(fp) / 1e6 if os.path.isfile(fp) else -1
    print(f"  {x:34s} {sz:9.1f} MB" if sz >= 0 else f"  {x:34s} <dir>")

# 5) 指数成分文件里有没有权重(可反推自由流通)
IDX = r'E:\rq\constituents\index'
if os.path.isdir(IDX):
    fs = sorted(glob.glob(os.path.join(IDX, '*.h5')))[:3]
    for f_ in fs:
        with h5py.File(f_, 'r') as f:
            print(f"\n{os.path.basename(f_)} 键: {list(f.keys())}")
            if 'components' in f:
                cd = f['change_dates'][:].astype(str)
                d0 = cd[0]
                print("  components 子键样例:", list(f['components'][d0].keys())
                      if hasattr(f['components'][d0], 'keys') else type(f['components'][d0]))
