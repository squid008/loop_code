# -*- coding: utf-8 -*-
"""
Round 4: BARRA
  A. BARRA 风格因子自身的 alpha(11个)
  B. BARRA 中性化(size + 31行业) 后, 重验 Round1/2 的量价因子
     —— 之前只做 ln(市值) 单变量中性化, 本轮加上行业, 更严谨
"""
import os
import sys
import time
import pickle
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from factor_miner import (load_panel, prepare, run_round, show, cs_rank)
from round1 import build_factors as bf1
from round2 import build_factors as bf2

HERE = os.path.dirname(os.path.abspath(__file__))
BARRA = os.path.join(HERE, 'barra.h5')

STYLE = ['size', 'non_linear_size', 'momentum', 'liquidity', 'book_to_price',
         'leverage', 'growth', 'earnings_yield', 'beta', 'residual_volatility',
         'comovement']

t0 = time.time()
print("[1] 载入 BARRA")
with pd.HDFStore(BARRA, 'r') as st:
    keys = list(st.keys())
    inds = [k.strip('/') for k in keys if k.strip('/') not in STYLE]
    barra = {c: st[c] for c in STYLE + inds}
print(f"  风格因子 {len(STYLE)} 个, 行业 {len(inds)} 个")
d0 = barra['size']
print(f"  BARRA 区间: {d0.index.min()} ~ {d0.index.max()}  {d0.shape}")

P = load_panel()
P = prepare(P)
close = P['close']
idx = close.index[close.index >= 20180101]
print(f"  面板区间(2018起): {idx.min()} ~ {idx.max()}  共{len(idx)}日")


def align(df):
    return df.reindex(index=close.index, columns=close.columns)


# ---------- A. BARRA 风格因子自身 alpha ----------
print("\n[2] A. BARRA 风格因子 alpha")
FA = {}
for c in STYLE:
    FA[f'barra_{c}'] = align(barra[c].astype('float64'))
resA, icA = run_round(FA, close, tag='R4A', verbose=False)
show(resA, 'Round4-A  BARRA风格因子(按超额排序)')

# ---------- B. BARRA 中性化 (size + 行业) ----------
print("\n[3] B. 构建 BARRA 中性化矩阵")
Xs = [align(barra[c].astype('float64')) for c in STYLE[:1]]      # size
Xi = [align(barra[c].astype('float64')) for c in inds]           # 行业哑变量
# 只用 size + 行业(其余风格因子可能与alpha重叠, 故不纳入中性化)
NEUT = Xs + Xi
print(f"  中性化变量: size + {len(inds)} 行业 = {len(NEUT)} 个")


def barra_neutralize(fac):
    """逐日 OLS: fac ~ 1 + size + 行业哑变量, 取残差"""
    mats = [m.loc[idx] for m in NEUT]
    f = fac.loc[idx]
    out = pd.DataFrame(np.nan, index=idx, columns=fac.columns)
    X = np.stack([m.values for m in mats], axis=2)     # (T, N, K)
    Y = f.values
    for i in range(len(idx)):
        Xi_ = X[i]                                     # (N, K)
        yi = Y[i]
        m = np.isfinite(yi) & np.isfinite(Xi_).all(axis=1)
        if m.sum() < 100:
            continue
        A = np.column_stack([np.ones(m.sum()), Xi_[m]])
        try:
            beta, *_ = np.linalg.lstsq(A, yi[m], rcond=None)
            out.values[i, m] = yi[m] - A @ beta
        except Exception:
            continue
    return out


F = {}
F.update(bf1(P))
F.update(bf2(P))
print(f"  待中性化因子: {len(F)}")

print("\n[4] 逐个中性化并检验(较慢) ...")
FN = {}
for i, (nm, fac) in enumerate(F.items(), 1):
    try:
        FN[nm] = barra_neutralize(fac.astype('float64'))
    except Exception as e:
        print(f"   {nm} ERR {e}")
    if i % 20 == 0:
        print(f"   {i}/{len(F)}  {time.time()-t0:.0f}s")

print("\n[5] 检验中性化后因子 ...")
resB, icB = run_round(FN, close, tag='R4B', verbose=False)
show(resB, 'Round4-B  BARRA(size+行业)中性化后(按超额排序)')

with open(os.path.join(HERE, 'ic_round4.pkl'), 'wb') as f:
    pickle.dump({**icA, **icB}, f)
print(f"\n耗时 {time.time()-t0:.0f}s")
