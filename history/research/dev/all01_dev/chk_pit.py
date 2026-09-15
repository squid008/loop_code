# -*- coding: utf-8 -*-
"""PIT 展开正确性验证: 与原始 parquet 的 as-of 取值逐笔对照"""
import os
import sys
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEV = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from round5_fund import FundPanels

GRID = os.path.join(DEV, 'fund_grid.pkl')
PIT = os.path.join(DEV, 'pit_panel_fund.parquet')
FIELDS = ['total_assets', 'equity_parent_company', 'operating_revenueTTM',
          'np_parent_company_ownersTTM', 'total_shares', 'current_liabilities']
STKS = ['000001.XSHE', '000651.XSHE', '600519.XSHG', '300055.XSHE']
DATES = [20180402, 20200803, 20211008, 20240506, 20260316]


def to_qidx(q):
    return int(q[:4]) * 4 + (int(q[-1]) - 1)


def main():
    with pd.HDFStore(os.path.join(HERE, 'panel.h5'), 'r') as st:
        close = st['close']
    dates = close.index.values
    cols = list(close.columns)
    FP = FundPanels(GRID, dates)
    pit = pd.read_pickle(PIT)
    pit = pit[pit['order_book_id'].isin(STKS)]
    pit['qi'] = pit['quarter'].map(to_qidx)

    pos = {d: int(np.searchsorted(dates, d, side='left')) for d in DATES}
    ok_all = True
    for f in FIELDS:
        V = FP.daily(f)
        for s in STKS:
            if s not in FP.col_of:
                continue
            j = FP.col_of[s]
            sub = pit[(pit['order_book_id'] == s) & pit[f].notna()]
            for d in DATES:
                av = sub[sub['info_date'] <= d]
                if not len(av):
                    continue
                # ground truth: 取公告日在 d 之前、报告期最新的那条
                gt_q = av['qi'].max()
                gt = av.loc[av['qi'].idxmax()][f]
                got = V[pos[d], j]
                good = np.isfinite(got) and abs(got - gt) <= max(abs(gt) * 1e-4, 1e-6)
                if not good:
                    ok_all = False
                    print(f"  X {f:30s} {s} {d}: 期望 {gt:.4g} (q={av.loc[av['qi'].idxmax()]['quarter']}) "
                          f"实际 {got}")
        print(f"{f:30s} 检查完成")
    print("\n全部一致" if ok_all else "\n存在不一致(见上)")


if __name__ == '__main__':
    main()
