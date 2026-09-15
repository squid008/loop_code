# -*- coding: utf-8 -*-
"""
聚宽因子批次: PIT 字段抽取(在财报批次30字段基础上扩展 ~15 个)
新增用途: JQ indicator 风格的费用率/现金流质量/平均余额ROE/有息负债/利息保障等
输出: pit_panel_jq.parquet(实际为 pickle, 沿用 build_pit_panel_fund.py 约定)
"""
import os
import glob
import time
import pickle
import logging
import numpy as np
import pandas as pd
import h5py

PIT_DIR = r'E:\rq\finance\pit'
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pit_panel_jq.parquet')

# ============ 财报批次已有 30 字段 ============
WANT = [
    # 股本
    'total_shares', 'circulation_a_shares', 'total_a_shares',
    # 资产负债表(时点)
    'equity_parent_company', 'total_equity', 'total_assets', 'total_liabilities',
    'current_assets', 'current_liabilities', 'inventory', 'net_accts_receivable',
    # 利润表(累计YTD)
    'operating_revenue', 'net_profit', 'net_profit_parent_company',
    'net_profit_deduct_non_recurring_pnl', 'non_recurring_pnl',
    'adjusted_net_profit',
    # TTM
    'operating_revenueTTM', 'net_profitTTM', 'np_parent_company_ownersTTM',
    'gross_profitTTM', 'operating_profitTTM', 'total_profitTTM',
    'ebitTTM', 'net_operate_cashflowTTM', 'net_cashflowTTM', 'operating_costTTM',
    # 现金流
    'cash_flow_from_operating_activities',
    # 每股/ROE
    'return_on_equity_weighted_average', 'basic_earnings_per_share',
    # ============ 聚宽批次新增 ============
    # 费用(费用率族)
    'selling_expense', 'administration_expenseTTM', 'financial_expenseTTM',
    'operating_expenseTTM', 'total_operating_costTTM',
    # 营业总收入/总成本(TTM, JQ indicator 口径的分母)
    'total_operating_revenueTTM',
    # 现金流质量
    'cash_received_from_sales_of_goods',
    # 价值变动净收益(投资净收益/利润总额)
    'ni_from_value_changeTTM',
    # 有息负债(财务杠杆)
    'short_term_loans', 'long_term_loans', 'bond_payable', 'interest_expense',
    # 其他
    'rnd_to_revenue', 'goodwill', 'cash_equivalent',
]


def parse_one(path):
    obid = os.path.splitext(os.path.basename(path))[0]
    try:
        with h5py.File(path, 'r') as f:
            if 'info_date' not in f:
                return None
            info = f['info_date'][:].astype(str)
            quarter = f['quarter'][:].astype(str)
            n = len(info)
            data = {'info_date': info, 'quarter': quarter}
            have = set(f['fields'].keys())
            for w in WANT:
                if w in have:
                    d = f['fields'][w]
                    data[w] = d[:] if d.shape == (n,) else np.full(n, np.nan)
                else:
                    data[w] = np.full(n, np.nan)
    except Exception as e:
        logging.warning(f"{obid}: {e}")
        return None
    df = pd.DataFrame(data)
    df['order_book_id'] = obid
    df['info_date'] = pd.to_datetime(df['info_date'], errors='coerce')
    df = df[df['info_date'].notna()]
    df['info_date'] = df['info_date'].dt.strftime('%Y%m%d').astype(int)
    return df


def main():
    files = glob.glob(os.path.join(PIT_DIR, '*.h5'))
    print(f"PIT 文件数: {len(files)}", flush=True)
    parts = []
    t0 = time.time()
    for i, p in enumerate(files, 1):
        d = parse_one(p)
        if d is not None and len(d):
            parts.append(d)
        if i % 500 == 0:
            print(f"  ... {i}/{len(files)}  {time.time()-t0:.0f}s", flush=True)
    df = pd.concat(parts, ignore_index=True)
    print(f"\n合并后 {len(df):,} 行, 股票 {df['order_book_id'].nunique()} 只", flush=True)
    print(f"info_date 范围: {df['info_date'].min()} ~ {df['info_date'].max()}", flush=True)

    df = df.drop_duplicates(subset=['order_book_id', 'info_date', 'quarter'], keep='last')
    df = df.sort_values(['order_book_id', 'info_date']).reset_index(drop=True)

    print("\n各字段非缺失比例(全区间):", flush=True)
    for c in WANT:
        if c in df.columns:
            print(f"  {c:<40} {df[c].notna().mean()*100:5.1f}%", flush=True)

    with open(OUT, 'wb') as f:
        pickle.dump(df, f, protocol=4)
    print(f"\n已保存: {OUT}  ({len(df):,} 行)  耗时 {time.time()-t0:.0f}s", flush=True)


if __name__ == '__main__':
    main()
