# -*- coding: utf-8 -*-
"""检查 BARRA 行业归属是否随时间变化"""
import os
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PANEL = os.path.join(HERE, 'panel.h5')
BARRA = os.path.join(HERE, 'barra.h5')

with pd.HDFStore(PANEL, 'r') as st:
    cols = list(st['close'].columns)


def gid_at(st, inds, cols, t):
    D = np.stack([st[k].reindex(index=None, columns=cols).values[t] for k in inds], axis=1)
    s = np.nan_to_num(D).sum(axis=1)
    return np.where(s > 0.5, np.argmax(np.nan_to_num(D), axis=1), -1)


with pd.HDFStore(BARRA, 'r') as st:
    keys = [k.strip('/') for k in st.keys()]
    STYLE = ['size', 'non_linear_size', 'momentum', 'liquidity', 'book_to_price',
             'leverage', 'growth', 'earnings_yield', 'beta', 'residual_volatility',
             'comovement']
    inds = [k for k in keys if k not in STYLE]
    frames = {k: st[k].reindex(columns=cols) for k in inds}
    T = len(next(iter(frames.values())))
    print("barra T =", T)
    for t in [0, 300, 800, 1300, 1800, T - 1]:
        D = np.stack([frames[k].values[t] for k in inds], axis=1)
        s = np.nan_to_num(D).sum(axis=1)
        g = np.where(s > 0.5, np.argmax(np.nan_to_num(D), axis=1), -1)
        print(f"  t={t}: 有归属 {(g>=0).sum()}, 归属和>1的股票 {int((s>1.5).sum())}")

    ts = [0, 300, 800, 1300, 1800, T - 1]
    gs = {}
    for t in ts:
        D = np.stack([frames[k].values[t] for k in inds], axis=1)
        s = np.nan_to_num(D).sum(axis=1)
        gs[t] = np.where(s > 0.5, np.argmax(np.nan_to_num(D), axis=1), -1)
    print("\n两两一致率(仅比较两天都有归属的股票):")
    for i in range(len(ts)):
        for j in range(i + 1, len(ts)):
            a, b = gs[ts[i]], gs[ts[j]]
            m = (a >= 0) & (b >= 0)
            print(f"  t={ts[i]} vs t={ts[j]}: 共覆盖 {m.sum()}, 一致率 "
                  f"{(a[m]==b[m]).mean()*100:.2f}%")

    # 每只股票: 众数行业 + 是否曾变更
    K = len(inds)
    cnt = np.zeros((len(cols), K), dtype=np.int32)
    for k in inds:
        v = frames[k].values
        j = inds.index(k)
        cnt[:, j] = np.nansum(np.where(v == 1, 1, 0), axis=0)
    mx = cnt.max(axis=1)
    gid = cnt.argmax(axis=1)
    gid[mx == 0] = -1
    share = np.where(mx > 0, cnt.max(axis=1) / np.maximum(cnt.sum(axis=1), 1), 0)
    print("\n众数行业占比分布: 均值 %.4f, <0.9 的股票数 %d, <0.99 的股票数 %d"
          % (share[mx > 0].mean(), int((share < 0.9).sum()), int(((share < 0.99) & (share > 0)).sum())))
    print("从未有行业归属的股票数:", int((mx == 0).sum()))
