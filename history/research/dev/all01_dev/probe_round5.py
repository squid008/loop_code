# -*- coding: utf-8 -*-
"""构造财报因子前的最后核查: panel/barra/fund_grid 三者能否对齐 + PIT 时序无未来函数"""
import os
import pickle
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

PANEL = os.path.join(ROOT, 'panel.h5')
BARRA = os.path.join(ROOT, 'barra.h5')
GRID = os.path.join(HERE, 'fund_grid.pkl')


def main():
    with pd.HDFStore(PANEL, 'r') as st:
        print("panel keys:", [k.strip('/') for k in st.keys()])
        close = st['close']
    print("close", close.shape, "index", close.index.dtype,
          close.index.min(), "~", close.index.max())
    print("cols sample:", list(close.columns[:3]), "... n=", len(close.columns))

    with pd.HDFStore(BARRA, 'r') as st:
        print("\nbarra keys:", [k.strip('/') for k in st.keys()][:40])
        size = st['size']
    print("barra size", size.shape, size.index.min(), "~", size.index.max())
    inter = close.index.intersection(size.index)
    print("面板与BARRA共有日期:", len(inter), inter.min() if len(inter) else None,
          "~", inter.max() if len(inter) else None)

    with open(GRID, 'rb') as f:
        G = pickle.load(f)
    qs = G['qs']
    val, avail = G['val'], G['avail']
    print(f"\nfund_grid: Q={len(qs)}  {qs[0]} ~ {qs[-1]}")
    print("fields:", len(val), sorted(val.keys())[:5], "...")
    k = 'net_profitTTM'
    v, a = val[k], avail[k]
    print(f"{k}: non-nan {np.isfinite(v).sum():,}")
    # 公告日是否随 quarter 单调(每只股票)
    a2 = a.copy()
    a2[~np.isfinite(v)] = -1
    mono = (np.diff(a2, axis=0) >= 0)
    print("公告日随quarter单调比例: %.3f" % (mono.mean()))
    print("avail 有值范围:", a[a < 99999999].min(), "~", a[a < 99999999].max())

    # PIT 抽查: 000001.XSHE 最后几个 quarter 的 net_profitTTM 与公告日
    cols = list(close.columns)
    if '000001.XSHE' in G['col_of']:
        j = G['col_of']['000001.XSHE']
        print("\n000001.XSHE 最近6期 net_profitTTM / 公告日:")
        for i in range(len(qs) - 6, len(qs)):
            print(f"  {qs[i]}  val={v[i, j]}  avail={a[i, j]}")
    else:
        print("\n000001.XSHE 不在panel列, 列样例:", cols[:3])

    # 覆盖率: 检验区间(2018起)每期非空格数
    print("\n2018年后各年 有 net_profitTTM 的股票数(取每年最后一期):")
    for i, q in enumerate(qs):
        if q.endswith('4') and q[:4] >= '2017':
            print(f"  {q}: {np.isfinite(v[i]).sum()}")

    # 市值字段
    with pd.HDFStore(PANEL, 'r') as st:
        if '/mktcap' in st.keys():
            mc = st['mktcap']
            print("\nmktcap", mc.shape, "NaN%", round(mc.isna().mean().mean() * 100, 1))


if __name__ == '__main__':
    main()
