# -*- coding: utf-8 -*-
"""判定 market-cap 下各文件的口径: 与自有总市值/流通市值对比"""
import os
import numpy as np
import pandas as pd

D = r'E:\rq\others\market-cap'
NAMES = ['market_cap', 'market_cap_2', 'market_cap_3', 'market_cap_4']

snap = pd.read_pickle(r'd:\rqalpha_demo\strategies\all01\factor_snapshot.pkl')
last = int(snap['date'].max())
s = snap[snap['date'] == last].set_index('obid')
ours = pd.DataFrame({'总市值(自有)': s['mktcap'], '流通市值(自有)': s['circ_mktcap']})
print(f"快照末日 {last}: {len(ours)} 只")
print(f"  自有流通市值覆盖 {ours['流通市值(自有)'].notna().mean()*100:.1f}%")

store = {}
for nm in NAMES:
    p = os.path.join(D, nm + '.h5')
    df = pd.read_hdf(p)
    ser = df.iloc[:, 0]
    d = ser.unstack(level=0)                     # index=date, columns=obid
    d.index = [int(pd.Timestamp(x).strftime('%Y%m%d')) for x in d.index]
    store[nm] = d.sort_index()
    print(f"\n{nm}: unstack -> {d.shape}  {d.index[0]}~{d.index[-1]}")

cmp = ours.copy()
for nm in NAMES:
    d = store[nm]
    if last in d.index:
        cmp[nm] = d.loc[last].reindex(cmp.index)
    else:
        prev = d.index[d.index <= last][-1]
        cmp[nm] = d.loc[prev].reindex(cmp.index)
        print(f"  {nm}: 用 {prev} 代替 {last}")

sub = cmp.dropna(subset=['总市值(自有)'])
print(f"\n末日对比样本 {len(sub)} 只")
print("\n各文件市值 / 自有总市值 的分位数:")
for nm in NAMES:
    r = (sub[nm] / sub['总市值(自有)']).replace([np.inf, -np.inf], np.nan).dropna()
    print(f"  {nm:16s} n={len(r):5d} 中位 {r.median():7.4f}  "
          f"p5={r.quantile(0.05):6.3f} p25={r.quantile(0.25):6.3f} "
          f"p75={r.quantile(0.75):6.3f} p95={r.quantile(0.95):6.3f}")

print("\n各文件市值 / 自有流通市值 的分位数:")
for nm in NAMES:
    r = (sub[nm] / sub['流通市值(自有)']).replace([np.inf, -np.inf], np.nan).dropna()
    print(f"  {nm:16s} n={len(r):5d} 中位 {r.median():7.4f}  "
          f"p5={r.quantile(0.05):6.3f} p25={r.quantile(0.25):6.3f} "
          f"p75={r.quantile(0.75):6.3f} p95={r.quantile(0.95):6.3f}")

print("\n文件之间比值(判断谁更小=更接近自由流通):")
for i in range(len(NAMES)):
    for j in range(i + 1, len(NAMES)):
        a, b = NAMES[i], NAMES[j]
        r = (sub[a] / sub[b]).replace([np.inf, -np.inf], np.nan).dropna()
        print(f"  {a}/{b}: 中位 {r.median():7.4f}  p25={r.quantile(0.25):6.3f} "
              f"p75={r.quantile(0.75):6.3f}")

# 工行/茅台/中石油 这类大票的自由流通比例
print("\n个案(自由流通比例应显著低于1):")
for ob in ['601398.XSHG', '600519.XSHG', '601857.XSHG', '000651.XSHE', '300750.XSHE']:
    if ob in sub.index:
        row = sub.loc[ob]
        print(f"  {ob}: 总市值={row['总市值(自有)']:.4g} 流通={row['流通市值(自有)']:.4g} | "
              + "  ".join(f"{nm.split('_')[-1]}={row[nm]:.4g}" for nm in NAMES))
