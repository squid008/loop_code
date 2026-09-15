# -*- coding: utf-8 -*-
"""
聚宽因子批次: 构建 quarter 级网格(字段扩展到 45)
输出: fund_grid_jq.pkl
"""
import os
import time
import pickle
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PIT_PKL = os.path.join(HERE, 'pit_panel_jq.parquet')
PANEL_H5 = os.path.join(ROOT, 'panel.h5')
OUT = os.path.join(HERE, 'fund_grid_jq.pkl')


def to_qidx(q):
    return int(q[:4]) * 4 + (int(q[-1]) - 1)


def ffill2d(m):
    Q, S = m.shape
    idx = np.where(~np.isnan(m), np.arange(Q)[:, None], -1)
    np.maximum.accumulate(idx, axis=0, out=idx)
    safe = np.maximum(idx, 0)
    out = m[safe, np.arange(S)[None, :]]
    out[idx < 0] = np.nan
    return out


# 时点类(STOCK): 资产负债表/股本 -> 跨期沿用
STOCK_F = ['total_shares', 'circulation_a_shares', 'total_a_shares',
           'equity_parent_company', 'total_equity', 'total_assets',
           'total_liabilities', 'current_assets', 'current_liabilities',
           'inventory', 'net_accts_receivable',
           'short_term_loans', 'long_term_loans', 'bond_payable',
           'goodwill', 'cash_equivalent']
# 流量/累计/TTM/比例类(FLOW): 不 ffill
FLOW_F = ['operating_revenue', 'net_profit', 'net_profit_parent_company',
          'net_profit_deduct_non_recurring_pnl', 'non_recurring_pnl',
          'adjusted_net_profit', 'operating_revenueTTM', 'net_profitTTM',
          'np_parent_company_ownersTTM', 'gross_profitTTM',
          'operating_profitTTM', 'total_profitTTM', 'ebitTTM',
          'net_operate_cashflowTTM', 'net_cashflowTTM', 'operating_costTTM',
          'cash_flow_from_operating_activities',
          'return_on_equity_weighted_average', 'basic_earnings_per_share',
          # --- 聚宽批次新增 ---
          'selling_expense', 'administration_expenseTTM', 'financial_expenseTTM',
          'operating_expenseTTM', 'total_operating_costTTM',
          'total_operating_revenueTTM', 'cash_received_from_sales_of_goods',
          'ni_from_value_changeTTM', 'rnd_to_revenue', 'interest_expense']


def main():
    t0 = time.time()
    with pd.HDFStore(PANEL_H5, 'r') as st:
        cols = list(st['close'].columns)
    col_of = {o: j for j, o in enumerate(cols)}
    S = len(cols)
    print(f"panel 列 {S}, {time.time()-t0:.0f}s", flush=True)

    pit = pd.read_pickle(PIT_PKL)
    print(f"pit {len(pit):,} 行, {time.time()-t0:.0f}s", flush=True)
    pit = pit[pit['info_date'] <= 20260831]
    pit = pit[pit['order_book_id'].isin(col_of)]
    qs = sorted(pit['quarter'].unique(), key=to_qidx)
    qmap = {q: i for i, q in enumerate(qs)}
    Q = len(qs)
    print(f"quarter {Q} 个, 股票 {pit['order_book_id'].nunique()}, "
          f"{time.time()-t0:.0f}s", flush=True)

    pit['qi'] = pit['quarter'].map(qmap)
    pit['si'] = pit['order_book_id'].map(col_of)
    ar = np.arange(S)

    val, avail = {}, {}
    FIELDS = STOCK_F + FLOW_F
    for k in FIELDS:
        sub = pit[pit[k].notna()].sort_values('info_date')
        sub = sub.drop_duplicates(['order_book_id', 'quarter'], keep='first')
        v = np.full((Q, S), np.nan, dtype=np.float32)
        a = np.full((Q, S), 99999999, dtype=np.int64)
        v[sub['qi'].values, sub['si'].values] = sub[k].values.astype(np.float32)
        a[sub['qi'].values, sub['si'].values] = sub['info_date'].values.astype(np.int64)
        val[k], avail[k] = v, a
    for k in STOCK_F:
        val[k] = ffill2d(val[k]).astype(np.float32)

    print("\n字段覆盖(quarter 级非空格数):", flush=True)
    for k in FIELDS:
        print(f"  {k:<40} {np.isfinite(val[k]).sum():>9,}", flush=True)

    with open(OUT, 'wb') as f:
        pickle.dump({'qs': qs, 'col_of': col_of, 'val': val, 'avail': avail},
                    f, protocol=4)
    print(f"\n已保存 {OUT}  {time.time()-t0:.0f}s", flush=True)


if __name__ == '__main__':
    main()
