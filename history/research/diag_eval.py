# -*- coding: utf-8 -*-
"""
验证 evaluate() 正确性
测试1: 作弊因子(因子=未来收益) -> IC应接近1, 超额应巨额为正
测试2: 单调性(10组收益应随因子值递增)
测试3: 反向作弊因子 -> 应得巨额负超额
"""
import os
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from factor_miner import (load_panel, prepare, evaluate, cs_rank, FWD, N_GRP, COST)

P = load_panel()
P = prepare(P)
close = P['close']
idx = close.index[close.index >= 20180101]

print(f"数据: {idx.min()} ~ {idx.max()}  {len(idx)}日 x {close.shape[1]}股")
print(f"FWD={FWD} N_GRP={N_GRP} COST={COST}\n")

# ---- 测试1: 作弊因子 ----
fwd = (close.shift(-(1 + FWD)) / close.shift(-1) - 1)
cheat = cs_rank(fwd.astype('float64'))
r1 = evaluate(cheat, close, '作弊(未来收益)')
print("=" * 78)
print("[测试1] 作弊因子 = 未来收益本身")
if r1:
    print(f"  IC={r1['ic']:.4f}  IC胜率={r1['ic_win']:.3f}")
    print(f"  Top组年化={r1['ann_top']*100:+.2f}%  市场={r1['ann_mkt']*100:+.2f}%  "
          f"超额={r1['ann_ex']*100:+.2f}%")
    print(f"  回撤={r1['dd']*100:.2f}%  Calmar={r1['calmar']:.2f}")
else:
    print("  返回 None")

# ---- 测试3: 反向作弊 ----
r3 = evaluate(cs_rank(-fwd.astype('float64')), close, '反向作弊')
print("\n[测试2] 反向作弊因子")
if r3:
    print(f"  IC={r3['ic']:.4f}  超额={r3['ann_ex']*100:+.2f}%  回撤={r3['dd']*100:.2f}%")

# ---- 测试3: 单调性(用真实因子 低波动) ----
ret = P['ret']
vol20 = -ret.rolling(20, min_periods=10).std()
f = cs_rank(vol20.astype('float64')).reindex(index=idx, columns=close.columns)
rebal = idx[::FWD]
grp_ret = {g: [] for g in range(N_GRP)}
for d in rebal[:-1]:
    fv = f.loc[d].dropna()
    if len(fv) < N_GRP * 10:
        continue
    nxt = idx[idx > d]
    if len(nxt) <= FWD:
        continue
    d1, d2 = nxt[0], nxt[FWD]
    rf = close.loc[d2] / close.loc[d1] - 1
    g = pd.qcut(fv.rank(method='first'), N_GRP, labels=False)
    for gi in range(N_GRP):
        grp_ret[gi].append(rf.reindex(fv.index[g == gi]).mean())

print("\n[测试3] 低波动因子(vol20) 10组单调性")
print("  组号(0=最高波动 ... 9=最低波动)   年化收益")
for gi in range(N_GRP):
    s = pd.Series(grp_ret[gi])
    nav = (1 + s).cumprod()
    yrs = len(s) * FWD / 243
    ann = nav.iloc[-1] ** (1 / yrs) - 1 if yrs > 0 else np.nan
    print(f"   G{gi}   {ann*100:+7.2f}%")

# ---- 测试4: 市场基准合理性 ----
print("\n[测试4] 全市场等权基准(用于对照)")
allr = []
for d in rebal[:-1]:
    nxt = idx[idx > d]
    if len(nxt) <= FWD:
        continue
    d1, d2 = nxt[0], nxt[FWD]
    allr.append((close.loc[d2] / close.loc[d1] - 1).mean())
s = pd.Series(allr)
nav = (1 + s).cumprod()
print(f"  年化={(nav.iloc[-1]**(1/(len(s)*FWD/243))-1)*100:+.2f}%  "
      f"期数={len(s)}  单期均值={s.mean()*100:+.3f}%")
