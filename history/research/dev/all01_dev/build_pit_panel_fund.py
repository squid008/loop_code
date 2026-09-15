# -*- coding: utf-8 -*-
"""
财报因子批次: PIT 字段扩展抽取 (比 build_pit_panel.py 多 ~19 个字段)
输出: pit_panel_fund.parquet (长表, 不覆盖原 13 字段版, 保持向后兼容)

与 build_pit_panel.py 相同的去重逻辑:
  同 (股票, 公告日, 报告期) 去重保最后; 后续消费方对同 (股票,报告期) 按公告日取首条。
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
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pit_panel_fund.parquet')

# 财报因子批次所需字段(米筐 PIT 命名), 覆盖原13个 + 新增
WANT = [
    # --- 股本/市值 ---
    'total_shares', 'circulation_a_shares', 'total_a_shares',
    # --- 资产负债表: 时点值 ---
    'equity_parent_company', 'total_equity', 'total_assets', 'total_liabilities',
    'current_assets', 'current_liabilities', 'inventory', 'net_accts_receivable',
    # --- 利润表: 累计值(YTD) ---
    'operating_revenue', 'net_profit', 'net_profit_parent_company',
    'net_profit_deduct_non_recurring_pnl', 'non_recurring_pnl',
    'adjusted_net_profit',
    # --- TTM 滚动12月 ---
    'operating_revenueTTM', 'net_profitTTM', 'np_parent_company_ownersTTM',
    'gross_profitTTM', 'operating_profitTTM', 'total_profitTTM',
    'ebitTTM', 'net_operate_cashflowTTM', 'net_cashflowTTM',
    'operating_costTTM',
    # --- 现金流 ---
    'cash_flow_from_operating_activities',
    # --- 每股/ROE ---
    'return_on_equity_weighted_average', 'basic_earnings_per_share',
]


def parse_one(path):
    """解析单只股票, 返回 DataFrame(可能为空)"""
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
            if 'if_adjusted' in f:
                data['if_adjusted'] = f['if_adjusted'][:]
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
