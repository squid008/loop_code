# -*- coding: utf-8 -*-
"""读 E:\rq\others\market-cap\ 各文件, 判断口径(总市值/流通市值/自由流通市值?)"""
import os
import numpy as np
import pandas as pd

D = r'E:\rq\others\market-cap'
NAMES = ['market_cap', 'market_cap_2', 'market_cap_3', 'market_cap_4',
         'market_leverage_lf', 'market_leverage_lyr', 'market_leverage_ttm']

# 参照: 我们自己算的总市值 / 流通市值
with pd.HDFStore(r'd:\rqalpha_demo\ai_test\panel.h5', 'r') as st:
    close = st['close']
    mc_ours = st['mktcap']
print(f"自有 panel: close {close.shape}, mktcap {mc_ours.shape}")

for nm in NAMES:
    p = os.path.join(D, nm + '.h5')
    if not os.path.exists(p):
        print(f"\n{nm}: 文件不存在")
        continue
    try:
        df = pd.read_hdf(p)
    except Exception as e:
        print(f"\n{nm}: 读取失败 {e}")
        continue
    print("=" * 78)
    print(f"{nm}: shape={df.shape}")
    print(f"  index(前3) {list(df.index[:3])} ... {list(df.index[-2:])}   "
          f"类型 {type(df.index).__name__}")
    print(f"  columns(前6) {list(df.columns[:6])}")
    # 转置为 日期 x 股票 后与自有市值比较
    try:
        d = df.T if df.index[0].startswith(('0', '3', '6')) else df
        d = d.copy()
        d.index = [int(str(x).replace('-', '')[:8]) for x in d.index]
        d = d.sort_index()
        d = d.reindex(columns=close.columns)
        last = d.index[-1]
        sub = d.loc[last]
        ours = mc_ours.loc[last] if last in mc_ours.index else None
        print(f"  末日 {last}: 有值 {int(sub.notna().sum())} 只, 中位 {sub.median():.4g}")
        if ours is not None:
            r = (sub / ours).replace([np.inf, -np.inf], np.nan).dropna()
            print(f"  /自有总市值: 中位 {r.median():.4f}  "
                  f"p5={r.quantile(0.05):.4f} p25={r.quantile(0.25):.4f} "
                  f"p75={r.quantile(0.75):.4f} p95={r.quantile(0.95):.4f}")
            # 与流通市值比
            print(f"  (判断: ≈1.0=总市值; <1 且波动大=流通/自由流通市值)")
    except Exception as e:
        print("  比较失败:", type(e).__name__, e)
