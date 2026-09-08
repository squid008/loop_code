# -*- coding: utf-8 -*-
"""
财报因子批次: 构建 quarter 级网格矩阵
从 pit_panel_fund.parquet(33字段) 构建:
  qs   : sorted quarter 列表
  col_of: 对齐 panel 列(只保留 panel 内股票)
  val  : {字段: (Q,S) 值矩阵}   float32
  avail: {字段: (Q,S) 公告日矩阵} int64
对时点类(STOCK)字段做 quarter 间 ffill2d(股本/权益/资产/负债/存货/应收等)
流量/累计/TTM 字段(FLOW)不做 ffill。
每 quarter 只保留最早披露版本(keep='first' by info_date) -> 无未来函数且保守。

输出: fund_grid.pkl
"""
import os
import time
import pickle
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PIT_PKL = os.path.join(HERE, 'pit_panel_fund.parquet')
PANEL_H5 = os.path.join(ROOT, 'panel.h5')
OUT = os.path.join(HERE, 'fund_grid.pkl')


def to_qidx(q):
    return int(q[:4]) * 4 + (int(q[-1]) - 1)


def ffill2d(m):
    """沿 quarter 轴前向填充(时点字段: 最新披露值沿用至新披露出现)"""
    Q, S = m.shape
    idx = np.where(~np.isnan(m), np.arange(Q)[:, None], -1)
    np.maximum.accumulate(idx, axis=0, out=idx)
    safe = np.maximum(idx, 0)
    out = m[safe, np.arange(S)[None, :]]
    out[idx < 0] = np.nan
    return out


# 时点类(STOCK): 资产负债表/股本 (跨期沿用)
STOCK_F = ['total_shares', 'circulation_a_shares', 'total_a_shares',
           'equity_parent_company', 'total_equity', 'total_assets',
           'total_liabilities', 'current_assets', 'current_liabilities',
           'inventory', 'net_accts_receivable']
# 流量/累计/TTM 类 (不 ffill)
FLOW_F = ['operating_revenue', 'net_profit', 'net_profit_parent_company',
          'net_profit_deduct_non_recurring_pnl', 'non_recurring_pnl',
          'adjusted_net_profit', 'operating_revenueTTM', 'net_profitTTM',
          'np_parent_company_ownersTTM', 'gross_profitTTM',
          'operating_profitTTM', 'total_profitTTM', 'ebitTTM',
          'net_operate_cashflowTTM', 'net_cashflowTTM', 'operating_costTTM',
          'cash_flow_from_operating_activities',
          'return_on_equity_weighted_average', 'basic_earnings_per_share']


def main():
    t0 = time.time()
    # panel 列 -> 索引
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
        # 同股票同报告期保留最早披露版
        sub = sub.drop_duplicates(['order_book_id', 'quarter'], keep='first')
        v = np.full((Q, S), np.nan, dtype=np.float32)
        a = np.full((Q, S), 99999999, dtype=np.int64)
        i = sub['qi'].values
        j = sub['si'].values
        v[i, j] = sub[k].values.astype(np.float32)
        a[i, j] = sub['info_date'].values.astype(np.int64)
        val[k], avail[k] = v, a
    for k in STOCK_F:
        val[k] = ffill2d(val[k]).astype(np.float32)

    print("\n字段覆盖(quarter 级非空格数):", flush=True)
    for k in FIELDS:
        cnt = np.isfinite(val[k]).sum()
        print(f"  {k:<42} {cnt:>9,}", flush=True)

    with open(OUT, 'wb') as f:
        pickle.dump({'qs': qs, 'col_of': col_of, 'val': val, 'avail': avail},
                    f, protocol=4)
    print(f"\n已保存 {OUT}  {time.time()-t0:.0f}s", flush=True)


if __name__ == '__main__':
    main()
