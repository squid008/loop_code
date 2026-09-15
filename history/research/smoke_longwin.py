# -*- coding: utf-8 -*-
"""冒烟: ①新派生字段 ②长窗口算子分块 vs 整体一致性 ③guided_expr 新族能否求值"""
import os
import sys
import time
import random
import re
import numpy as np
import pandas as pd
import fastops
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import loop_engine as LE

t0 = time.time()
base = LE.base_fields()
B, dates = base['B'], base['dates']
print(f"load {time.time()-t0:.1f}s  T={len(dates)}")


def parse(s):
    """极简表达式解析: op(a,b) 或 leaf"""
    m = re.match(r'^([a-zA-Z_0-9]+)\((.*)\)$', s)
    if not m:
        return LE.Node(s, [])
    op, inner = m.group(1), m.group(2)
    args, d, cur = [], 0, ''
    for ch in inner:
        if ch == '(':
            d += 1
        elif ch == ')':
            d -= 1
        if ch == ',' and d == 0:
            args.append(cur)
            cur = ''
        else:
            cur += ch
    if cur.strip():
        args.append(cur.strip())
    return LE.Node(op, [parse(a) for a in args])


print("\n[1] 派生字段 finite% / 末值:")
for k in ['overnight', 'intraday', 'amplitude', 'up_shadow', 'down_shadow',
          'hl_ratio', 'true_range']:
    v = B[k]
    print(f"  {k:12s} finite={np.isfinite(v).mean()*100:5.1f}%")
o, pc = B['open'][-1], B['close'][-2]
m = np.isfinite(B['overnight'][-1])
print(f"  overnight 手工核对: {np.allclose(B['overnight'][-1][m], (o/pc-1)[m])}")

print("\n[2] 分块 vs 整体 (ts_max/min/rank):")
rng = np.random.default_rng(0)
T, S = 900, 8
x = np.cumsum(rng.standard_normal((T, S)), axis=0).astype(np.float32)
x[rng.random((T, S)) < 0.08] = np.nan
for w in [60, 100, 200]:
    for name in ['max', 'min', 'rank']:
        full = getattr(fastops, '_ts_%s_full' % name)(x, w)
        ch = fastops._chunked(getattr(fastops, '_ts_%s_full' % name), x, w, chunk=64)
        print(f"  w={w:3d} {name:4s} maxdiff={np.nanmax(np.abs(full - ch)):.2e}")

print("\n[3] eval 新池 (L1子面板):")
Bsub = base['B_sub']
rngr = random.Random(7)
cands = [LE.guided_expr(rngr) for _ in range(40)]
okn, bads = 0, []
for nd in cands:
    try:
        v = LE.eval_expr(nd, Bsub, {})
    except Exception as e:
        bads.append(str(nd))
        continue
    if np.isfinite(v).mean() > 0.2 and np.nanstd(v) > 1e-8:
        okn += 1
    else:
        bads.append(str(nd))
print(f"  guide 族有效 {okn}/40  无效: {bads[:6]}")

print("\n[4] 手工长窗表达式:")
for ex in ['ts_mean200(overnight)', 'neg(ts_rank200(amplitude))',
           'sub(ts_mean100(overnight), ts_mean100(close))',
           'ts_max100(overnight)', 'ts_std200(ret)',
           'neg(ts_mean120(down_shadow))', 'ts_delta120(close)',
           'corr100(volume, ret)']:
    v = LE.eval_expr(parse(ex), Bsub, {})
    print(f"  {ex:42s} finite={np.isfinite(v).mean()*100:5.1f}%  std={np.nanstd(v):.4f}")
print(f"\ntotal {time.time()-t0:.1f}s")
