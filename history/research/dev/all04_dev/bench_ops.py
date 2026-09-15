# -*- coding: utf-8 -*-
"""对比 pandas rolling 版 vs numpy 版算子的速度与精度"""
import os
import sys
import time
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import loop_engine as LE
import fastops as FO

rng = np.random.default_rng(0)
T, S = 3309, 5384
X = rng.standard_normal((T, S)).astype(np.float32)
Y = rng.standard_normal((T, S)).astype(np.float32)
# 注入 10% NaN 模拟停牌
X[rng.random((T, S)) < 0.10] = np.nan
Y[rng.random((T, S)) < 0.10] = np.nan
print(f"测试矩阵 {X.shape}, NaN {np.isnan(X).mean()*100:.1f}%")

def corr_align(a, b):
    m = np.isfinite(a) & np.isfinite(b)
    if m.sum() < 1000:
        return np.nan
    return float(np.corrcoef(a[m], b[m])[0, 1])

CASES = [
    ('ts_mean20', lambda: LE.ts_mean(X, 20), lambda: FO.ts_mean(X, 20)),
    ('ts_std20', lambda: LE.ts_std(X, 20), lambda: FO.ts_std(X, 20)),
    ('ts_sum20', lambda: LE.ts_sum(X, 20), lambda: FO.ts_sum(X, 20)),
    ('ts_max20', lambda: LE.ts_max(X, 20), lambda: FO.ts_max(X, 20)),
    ('ts_min20', lambda: LE.ts_min(X, 20), lambda: FO.ts_min(X, 20)),
    ('ts_rank20', lambda: LE.ts_rank(X, 20), lambda: FO.ts_rank(X, 20)),
    ('ts_corr20', lambda: LE.ts_corr(X, Y, 20), lambda: FO.ts_corr(X, Y, 20)),
    ('ts_std60', lambda: LE.ts_std(X, 60), lambda: FO.ts_std(X, 60)),
    ('ts_delay1', lambda: LE.ts_delay(X, 1), lambda: FO.ts_delay(X, 1)),
    ('ts_delta5', lambda: LE.ts_delta(X, 5), lambda: FO.ts_delta(X, 5)),
]

tot_old = tot_new = 0.0
print(f"\n{'算子':12s} {'pandas':>9s} {'numpy':>9s} {'提速':>7s}  {'一致性corr':>10s}")
print("-" * 58)
for nm, fo, fn in CASES:
    t0 = time.time(); a = fo(); t1 = time.time()
    b = fn(); t2 = time.time()
    d_old, d_new = t1 - t0, t2 - t1
    tot_old += d_old; tot_new += d_new
    c = corr_align(np.asarray(a, dtype=np.float64), np.asarray(b, dtype=np.float64))
    print(f"{nm:12s} {d_old:8.3f}s {d_new:8.3f}s {d_old/max(d_new,1e-6):6.1f}x  {c:10.6f}")
print("-" * 58)
print(f"{'合计':12s} {tot_old:8.3f}s {tot_new:8.3f}s {tot_old/max(tot_new,1e-6):6.1f}x")
print(f"\n按每表达式 5 个节点估算: 旧 {tot_old/10*5:.2f}s -> 新 {tot_new/10*5:.2f}s")
print(f"1万候选预计: 旧 {tot_old/10*5*10000/3600:.1f}h -> 新 {tot_new/10*5*10000/3600:.1f}h")
