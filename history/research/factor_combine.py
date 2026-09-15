# -*- coding: utf-8 -*-
"""
多因子合成: 用已算出的IC序列挑选低相关因子, 等权/IC加权合成后检验
中金做法: 因子间IC相关性<0.70, Top5等权复合 -> 超额夏普3.14
"""
import os
import sys
import time
import pickle
import itertools
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from factor_miner import (load_panel, prepare, evaluate, run_round, show,
                          cs_rank, pass_filter)
from round1 import build_factors as bf1
from round2 import build_factors as bf2

HERE = os.path.dirname(os.path.abspath(__file__))

t0 = time.time()
print("[1] 载入两轮IC序列")
ics = {}
for fn in ['ic_round1.pkl', 'ic_round2.pkl']:
    p = os.path.join(HERE, fn)
    if os.path.exists(p):
        with open(p, 'rb') as f:
            ics.update(pickle.load(f))
print(f"  共 {len(ics)} 个因子的IC序列")

ic_df = pd.DataFrame({k: v for k, v in ics.items()}).dropna(how='all')
ic_mean = ic_df.mean()
ic_std = ic_df.std()
ic_ir = ic_mean / ic_std

cand = ic_mean[ic_mean.abs() >= 0.02].index.tolist()
print(f"  |IC|>=0.02 的候选: {len(cand)} 个")

print("\n[2] 候选因子IC相关性矩阵(取相关性<0.7的独立组合)")
sub = ic_df[cand]
corr = sub.corr()
np.fill_diagonal(corr.values, np.nan)

# 贪心: 按|IC*IR|排序, 依次加入与已选因子相关性<0.7的
score = (ic_mean[cand].abs() * ic_ir[cand].abs()).sort_values(ascending=False)
selected = []
for nm in score.index:
    if all(abs(corr.loc[nm, s]) < 0.70 for s in selected):
        selected.append(nm)
    if len(selected) >= 12:
        break
print(f"  选出 {len(selected)} 个低相关因子:")
for nm in selected:
    print(f"    {nm:18s} IC={ic_mean[nm]:+.4f} IR={ic_ir[nm]:+.3f}")

print("\n[3] 重建因子值并合成")
P = load_panel()
P = prepare(P)
close = P['close']
F = {}
F.update(bf1(P))
F.update(bf2(P))
print(f"  因子池: {len(F)}")

# 方向统一: 按IC符号取正
def signed(nm):
    f = F[nm].astype('float64')
    return f if ic_mean[nm] >= 0 else -f

combos = {}
# 逐个选中的因子
for nm in selected:
    if nm in F:
        combos[f'S:{nm}'] = cs_rank(signed(nm))

# 累积合成: Top2/3/5/8/全部
for k in [2, 3, 5, 8, len(selected)]:
    ss = selected[:k]
    if not all(s in F for s in ss):
        continue
    acc = sum(cs_rank(signed(s)) for s in ss) / len(ss)
    combos[f'TOP{k}等权'] = acc

# IC加权合成(全部选中因子)
w = ic_mean[selected].abs()
w = w / w.sum()
acc = sum(cs_rank(signed(s)) * w[s] for s in selected if s in F)
combos['IC加权'] = acc

print(f"\n[4] 检验 {len(combos)} 个组合")
res, ic_new = run_round(combos, close, tag='CB', verbose=False)
show(res, '多因子合成结果(按超额排序)')

with open(os.path.join(HERE, 'ic_combine.pkl'), 'wb') as f:
    pickle.dump(ic_new, f)
print(f"\n耗时 {time.time()-t0:.0f}s")
