# -*- coding: utf-8 -*-
"""调试: BARRA 中性化 FWL 向量化版 vs lstsq 版 差异来源"""
import os
import sys
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from round5_fund import BarraNeut, FundPanels

DEV = os.path.dirname(os.path.abspath(__file__))
GRID = os.path.join(DEV, 'fund_grid.pkl')
PANEL = os.path.join(HERE, 'panel.h5')
BARRA = os.path.join(HERE, 'barra.h5')


def main():
    with pd.HDFStore(PANEL, 'r') as st:
        close = st['close']
    dates = close.index.values
    cols = list(close.columns)
    FP = FundPanels(GRID, dates)
    BN = BarraNeut(BARRA, dates, cols)

    y = pd.DataFrame(FP.daily('net_profitTTM'), index=dates, columns=cols)
    sub = np.where(dates >= 20180101)[0][:20]
    R1 = BN(y.values)[sub]

    with pd.HDFStore(BARRA, 'r') as st:
        keys = [k.strip('/') for k in st.keys()]
        inds = [k for k in keys if k not in BarraNeut.STYLE]
        print("行业数:", len(inds))
        size_f = st['size'].reindex(index=dates, columns=cols)
        print("size NaN%:", round(size_f.isna().mean().mean() * 100, 1))
        dum0 = st[inds[0]].reindex(index=dates, columns=cols)
        print(f"行业例[{inds[0]}] NaN%:", round(dum0.isna().mean().mean() * 100, 1),
              " 取值:", np.unique(np.nan_to_num(dum0.values[sub[0]]))[:6])
        row = dum0.values[sub[0]]
        print("  该日该行业 非0数:", int((row == 1).sum()), " 非nan非0数:",
              int(np.isfinite(row).sum() - (row == 1).sum()))
        mats = [st[c].reindex(index=dates, columns=cols).values[sub] for c in ['size'] + inds]

    X = np.stack(mats, axis=2)
    Y = y.values[sub]
    R2 = np.full(Y.shape, np.nan)
    for i in range(len(sub)):
        Xi, yi = X[i], Y[i]
        m = np.isfinite(yi) & np.isfinite(Xi).all(axis=1)
        if m.sum() < 100:
            continue
        A = np.column_stack([np.ones(m.sum()), Xi[m]])
        beta, *_ = np.linalg.lstsq(A, yi[m], rcond=None)
        R2[i, m] = yi[m] - A @ beta

    d = np.abs(R1 - R2)
    print("\nfinite R1:", int(np.isfinite(R1).sum()), " R2:", int(np.isfinite(R2).sum()))
    print("max|diff|:", np.nanmax(d), " median:", np.nanmedian(d))
    i, j = np.unravel_index(np.nanargmax(d), d.shape)
    print(f"\n最大差异位置: date={dates[sub[i]]} stock={cols[j]}")
    print("  y =", Y[i, j])
    print("  R1(FWL) =", R1[i, j], "  R2(lstsq) =", R2[i, j])
    print("  size =", X[i, j, 0], " 行业dummy和 =", np.nansum(X[i, j, 1:]))
    print("  gid =", BN.gid[j])
    # 该股票所在组: 组内样本数与均值
    gg = BN.gid[j]
    same = np.where(BN.gid == gg)[0]
    print(f"  同组股票数 {len(same)}, R1均值 {np.nanmean(R1[i, same]):.3e}")
    print("  该日 R1 全市场均值:", np.nanmean(R1[i]), " R2:", np.nanmean(R2[i]))
    print("  该日 R1 std:", np.nanstd(R1[i]), " R2 std:", np.nanstd(R2[i]))
    # 检查 R1 是否整体偏离0(应接近0均值)
    print("\nR1 每日均值(前5):", np.round(np.nanmean(R1, axis=1)[:5], 2))
    print("R2 每日均值(前5):", np.round(np.nanmean(R2, axis=1)[:5], 2))
    print("R1 每日std(前5):", np.round(np.nanstd(R1, axis=1)[:5], 2))
    print("R2 每日std(前5):", np.round(np.nanstd(R2, axis=1)[:5], 2))
    # 相关性
    v = np.isfinite(R1) & np.isfinite(R2)
    print("\n两者相关系数:", np.corrcoef(R1[v], R2[v])[0, 1])


if __name__ == '__main__':
    main()
