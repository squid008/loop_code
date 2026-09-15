# -*- coding: utf-8 -*-
"""
Round 3: 市值中性化 —— 剔除 ln(市值) 影响后, 哪些因子仍有增量?
做法: 横截面 daily 回归 factor ~ a + b*ln(mktcap), 取残差作为中性化因子
目的: 小市值已知是最强信号, 本轮找"不是市值马甲"的独立信号
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
t0 = time.time()


def cs_neutralize(fac, mc):
    """横截面回归 fac ~ ln(mc) 取残差(向量化)"""
    x = np.log(mc.astype('float64').replace(0, np.nan))
    x = x.reindex(index=fac.index, columns=fac.columns)
    xm = x.sub(x.mean(axis=1), axis=0)
    ym = fac.sub(fac.mean(axis=1), axis=0)
    num = (xm * ym).sum(axis=1, min_count=10)
    den = (xm ** 2).sum(axis=1, min_count=10)
    b = num / den.replace(0, np.nan)
    resid = ym.sub(xm.mul(b, axis=0), axis=0)
    return resid.where(np.isfinite(fac))


if __name__ == '__main__':
    P = load_panel()
    P = prepare(P)
    close = P['close']
    mc = P['mktcap']
    print(f"市值可用, NaN占比 {mc.isna().mean().mean()*100:.1f}%")

    F = {}
    F.update(bf1(P))
    F.update(bf2(P))
    print(f"原始因子: {len(F)}")

    print("市值中性化 ...")
    NF = {}
    for nm, fac in F.items():
        try:
            NF[nm] = cs_neutralize(fac.astype('float64'), mc)
        except Exception:
            continue
    print(f"中性化后: {len(NF)}")

    print("\n检验(中性化后) ...")
    res, ic_store = run_round(NF, close, tag='R3', verbose=False)
    show(res, 'Round 3 市值中性化后(按超额排序)')

    with open(os.path.join(HERE, 'ic_round3.pkl'), 'wb') as f:
        pickle.dump(ic_store, f)
    print(f"\n耗时 {time.time()-t0:.0f}s")
