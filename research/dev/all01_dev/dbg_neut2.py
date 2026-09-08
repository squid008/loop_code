# -*- coding: utf-8 -*-
"""单日细查: FWL vs lstsq 的 b / 行业归属 / 组均值 差异"""
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
    cols = np.array(close.columns)
    FP = FundPanels(GRID, dates)
    BN = BarraNeut(BARRA, dates, cols.tolist())
    y_all = FP.daily('net_profitTTM')

    with pd.HDFStore(BARRA, 'r') as st:
        keys = [k.strip('/') for k in st.keys()]
        inds = [k for k in keys if k not in BarraNeut.STYLE]
        t = np.where(dates >= 20180101)[0][0]
        # 该日真实行业归属
        D = np.stack([st[k].reindex(index=dates, columns=cols.tolist()).values[t]
                      for k in inds], axis=1)          # (S,K)
        xsz = st['size'].reindex(index=dates, columns=cols.tolist()).values[t]

    y = y_all[t].astype(np.float64)
    ssum = np.nansum(D, axis=1)
    gid_true = np.where(ssum > 0.5, np.argmax(np.nan_to_num(D), axis=1), -1)
    print(f"date={dates[t]}")
    print("真实行业: 有归属 %d, 无 %d" % ((gid_true >= 0).sum(), (gid_true < 0).sum()))
    print("BN.gid : 有归属 %d, 无 %d" % ((BN.gid < 31).sum(), (BN.gid == 31).sum()))
    same = (gid_true == BN.gid)
    print("两者一致: %d / %d" % (same.sum(), len(same)))
    if same.sum() < len(same):
        bad = np.where(~same)[0][:10]
        print("  不一致样例:", [(cols[j], int(gid_true[j]), int(BN.gid[j])) for j in bad])

    m0 = np.isfinite(y) & np.isfinite(xsz)
    print("有效样本:", m0.sum())

    # --- BN(FWL) ---
    R1 = BN(pd.DataFrame(y_all, index=dates, columns=cols.tolist()).values)[t]

    # --- lstsq ---
    A = np.column_stack([np.ones(m0.sum()), xsz[m0], np.nan_to_num(D)[m0]])
    beta, *_ = np.linalg.lstsq(A, y[m0], rcond=None)
    fitted = A @ beta
    R2 = np.full(len(y), np.nan)
    R2[m0] = y[m0] - fitted
    print("\nb_lstsq = %.6e" % beta[1])

    # 手算 FWL(用真实当日行业)
    gid = np.where(gid_true >= 0, gid_true, 31)
    G = 32
    order = np.argsort(gid, kind='stable')
    bnds = np.minimum(np.searchsorted(gid[order], np.arange(G)), len(gid) - 1)
    Ys = np.where(m0, y, 0.0)[order]
    Xs = np.where(m0, xsz, 0.0)[order]
    Ms = m0[order].astype(np.float64)
    cy = np.add.reduceat(Ys, bnds)
    cx = np.add.reduceat(Xs, bnds)
    cnt = np.maximum(np.add.reduceat(Ms, bnds), 1e-9)
    my = (cy / cnt)[gid]
    mx = (cx / cnt)[gid]
    yd = np.where(m0, y - my, 0.0)
    xd = np.where(m0, xsz - mx, 0.0)
    b = (yd * xd).sum() / (xd * xd).sum()
    print("b_FWL(真实行业) = %.6e" % b)
    R3 = np.where(m0, yd - b * xd, np.nan)
    # 无行业归属股票不做组内去均值(正确做法)
    yd2 = yd.copy()
    yd2[gid == 31] = y[gid == 31]
    xd2 = xd.copy()
    xd2[gid == 31] = xsz[gid == 31]
    mm = m0 & (gid < 31)
    b2 = (np.where(mm, yd2, 0) * np.where(mm, xd2, 0)).sum() / \
         (np.where(mm, xd2, 0) ** 2).sum()
    R4 = np.where(m0, yd2 - b2 * xd2, np.nan)
    print("b_FWL(无行业不demean) = %.6e" % b2)

    for nm, r in [('R1 BN', R1), ('R3 FWL真实行业', R3), ('R4 无行业不demean', R4)]:
        d = np.abs(r - R2)
        v = np.isfinite(d)
        print(f"  {nm:18s} vs lstsq: max|d|={np.nanmax(d):.4e}  median={np.nanmedian(d):.4e}  "
              f"corr={np.corrcoef(r[v & np.isfinite(R2)], R2[v & np.isfinite(R2)])[0,1]:.6f}")


if __name__ == '__main__':
    main()
