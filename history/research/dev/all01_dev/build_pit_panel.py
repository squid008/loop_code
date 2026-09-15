# -*- coding: utf-8 -*-
"""
把米筐本地 PIT 财务数据(E:\\rq\\finance\\pit\\*.h5)整理成一张长表 parquet。

PIT 数据结构(每只股票一个 h5):
    fields/       394 个财务指标, 每个是 (N,) float64, N = 记录数
    info_date     (N,) 公告发布日  <-- 用于避免未来函数
    quarter       (N,) 报告期, 如 '2021q1'
    rice_create_tm(N,) 数据入库时间
    if_adjusted   (N,) 是否修正过

关键: 回测日 T 只能使用 info_date <= T 的记录(按 info_date 取最新一条)。

输出: pit_panel.parquet
    列: order_book_id, info_date(int YYYYMMDD), quarter, 以及各财务字段
"""
import os
import sys
import glob
import time
import logging

sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)

import numpy as np
import pandas as pd
import h5py

PIT_DIR = r'E:\rq\finance\pit'
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pit_panel.parquet')

# 两个策略需要的财务字段(米筐 PIT 命名)
WANT = [
    'total_shares',                 # 总股本
    'circulation_a_shares',         # 流通A股
    'equity_parent_company',        # 归母净资产 -> 算 PB
    'net_profit_parent_company',    # 归母净利润
    'adjusted_net_profit',          # 扣非净利润
    'net_profit',                   # 净利润
    'net_profitTTM',                # 净利润TTM
    'total_assets',                 # 总资产 -> 算 ROA
    'operating_revenue',            # 营业收入
    'operating_revenueTTM',
    'cash_flow_from_operating_activities',   # 经营活动现金流
    'return_on_equity_weighted_average',     # 加权ROE
    'basic_earnings_per_share',     # 基本EPS
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
    # info_date -> int YYYYMMDD
    df['info_date'] = pd.to_datetime(df['info_date'], errors='coerce')
    df = df[df['info_date'].notna()]
    df['info_date'] = df['info_date'].dt.strftime('%Y%m%d').astype(int)
    return df


def main():
    files = glob.glob(os.path.join(PIT_DIR, '*.h5'))
    print(f"PIT 文件数: {len(files)}")
    parts = []
    t0 = time.time()
    for i, p in enumerate(files, 1):
        d = parse_one(p)
        if d is not None and len(d):
            parts.append(d)
        if i % 1000 == 0:
            print(f"  ... {i}/{len(files)}  {time.time()-t0:.0f}s")
    df = pd.concat(parts, ignore_index=True)
    print(f"\n合并后 {len(df):,} 行, 股票 {df['order_book_id'].nunique()} 只")
    print(f"info_date 范围: {df['info_date'].min()} ~ {df['info_date'].max()}")

    # 同一 (股票, 公告日) 可能有多条(不同报告期/修正), 保留每个报告期最新修正
    # 先按 (股票, quarter, info_date) 去重, 再按 (股票, info_date) 合并(取该公告日所有报告期)
    df = df.drop_duplicates(subset=['order_book_id', 'info_date', 'quarter'], keep='last')
    df = df.sort_values(['order_book_id', 'info_date']).reset_index(drop=True)

    # 缺失率
    print("\n各字段非缺失比例:")
    for c in WANT:
        if c in df.columns:
            print(f"  {c:<42} {df[c].notna().mean()*100:5.1f}%")

    with open(OUT, 'wb') as f:
        import pickle
        pickle.dump(df, f, protocol=4)
    print(f"\n已保存: {OUT}  ({len(df):,} 行)")

    # 2014 年之后的数据质量(回测区间)
    sub = df[df['info_date'] >= 20140101]
    print(f"\n2014 年后记录: {len(sub):,} 行, 股票 {sub['order_book_id'].nunique()} 只")
    print("2014 年后各字段非缺失比例:")
    for c in WANT:
        if c in sub.columns:
            print(f"  {c:<42} {sub[c].notna().mean()*100:5.1f}%")
    print(f"耗时 {time.time()-t0:.0f}s")


if __name__ == '__main__':
    main()
