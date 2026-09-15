# -*- coding: utf-8 -*-
"""
米筐(rqalpha)回测: 小市值 + ROE增长 多因子 (移植聚宽 01.txt, 本地 PIT 无未来函数)

选股逻辑(每周一调仓):
  1. 过滤: 上市>250天 / 非ST / 非停牌 / 非涨停 / 非科创板(688) / 非北交所
  2. PB>0 且 EPS>0, 按 PB 升序取前 50%
  3. ROE环比增长 = 4*最新季ROE - 前4季ROE之和, 降序取前 10%
  4. 按【流通市值】升序取前 select_num 只

无未来函数保证:
  - 财务因子来自 factor_snapshot.pkl, 构建时按【公告日 info_date】对齐
  - A股年报4月底才披露完, 绝不用报告期(3-31/6-30)直接对齐
  - 调仓用当日 9:31 价格成交, 因子用前一日收盘
"""
import os
import sys
import time
import numpy as np
import pandas as pd

from rqalpha import run_func

# ===================== 策略参数 =====================
start_date = "2014-10-01"
end_date = "2026-08-05"
# ---- 选股 ----
select_num = 10
top_pb_pct = 0.5          # PB 最小的前 50%
top_roeinc_pct = 0.10     # ROE增长前 10%
min_list_days = 250       # 新股过滤
rank_col = 'circ_mktcap'  # 流通市值排序
weight_cash_buffer = 0.95
# ---- 交易成本 ----
stock_min_commission = 5
stock_commission_multiplier = 2.5      # 万八 x 2.5 = 单边千二(含滑点)
tax_multiplier = 1
pit_tax = False
# ---- 撮合 ----
volume_limit = True
volume_percent = 0.25
inactive_limit = True
# ===================================================

HERE = os.path.dirname(os.path.abspath(__file__))
SNAP_PATH = os.path.join(HERE, 'factor_snapshot.pkl')


def to_int_date(v, default):
    s = str(v)
    if s in ('nan', 'NaT', 'None', ''):
        return default
    s = s.replace('-', '').replace('/', '')[:8]
    try:
        return int(s)
    except ValueError:
        return default


t = time.time()


def init(context):
    from rqalpha.utils.logger import user_log
    from logbook import StderrHandler
    user_log.handlers = [StderrHandler(
        format_string='{record.time:%Y-%m-%d %H:%M:%S} - {record.level_name}  -  {record.message}',
        bubble=False)]

    with open(SNAP_PATH, 'rb') as f:
        snap = pickle.load(f) if False else pd.read_pickle(f)
    context.snap = {int(k): v for k, v in snap.groupby('date')}

    ins = all_instruments(type='CS')
    ins = ins[['order_book_id', 'listed_date', 'de_listed_date']].copy()
    ins['listed'] = [to_int_date(v, 19000101) for v in ins['listed_date']]
    ins['delisted'] = [to_int_date(v, 99999999) for v in ins['de_listed_date']]
    context.ins = ins.set_index('order_book_id')

    context.select_num = select_num
    scheduler.run_weekly(rebalance, tradingday=1)


def handle_bar(context, bar_dict):
    pass


def rebalance(context, bar_dict):
    d = int(context.now.strftime('%Y%m%d'))
    df = context.snap.get(d)
    if df is None:
        return

    ins = context.ins
    # 基础过滤
    alive = ins[(ins['listed'] <= d) & (ins['delisted'] >= d)].index
    cutoff = int((context.now - pd.Timedelta(days=min_list_days)).strftime('%Y%m%d'))
    ok = set(s for s in alive if ins.at[s, 'listed'] <= cutoff)
    # 板块过滤: 科创 688 / 北交 8xx、4xx
    ok = set(s for s in ok if not s.startswith('688')
             and not s.startswith('8') and not s.startswith('4'))

    rows = []
    for s in df['obid'].values:
        if s not in ok:
            continue
        try:
            if is_st_stock(s) or is_suspended(s):
                continue
        except Exception:
            continue
        bar = bar_dict[s]
        if bar is None:
            continue
        px = bar.last if bar.last else bar.close
        if not px or px <= 0:
            continue
        lu = getattr(bar, 'limit_up', None)
        if lu and px >= lu - 1e-6:
            continue
        rows.append(s)
    df = df[df['obid'].isin(rows)]
    if df.empty:
        return

    # ---- 01.txt 选股 ----
    df = df[(df['pb'] > 0) & (df['eps'] > 0)]
    df = df.sort_values('pb').head(max(int(len(df) * top_pb_pct), select_num))
    df = df.dropna(subset=['roe_inc'])
    df = df.sort_values('roe_inc', ascending=False)
    df = df.head(max(int(len(df) * top_roeinc_pct), select_num))
    df = df.dropna(subset=[rank_col])
    df = df.sort_values(rank_col).head(context.select_num)
    if df.empty:
        return

    df = df.copy()
    df['weight'] = weight_cash_buffer / len(df)
    target = dict(zip(df['obid'], df['weight']))

    for p in get_positions():
        if p.order_book_id not in target:
            order_target_value(p.order_book_id, 0)
    for s in target:
        order_target_percent(s, target[s])

    caps = df[rank_col] / 1e8
    logger.info(f"{d} 调仓 {len(df)} 只 | 流通市值 {caps.min():.1f}~{caps.max():.1f}亿 | "
                f"PB {df['pb'].min():.2f}~{df['pb'].max():.2f}")


if __name__ == '__main__':
    import pickle
    output_path = os.path.join(HERE, os.path.splitext(os.path.basename(__file__))[0]
                               + "_roe_" + start_date + "-" + end_date)
    __config__ = {
        "base": {
            "start_date": start_date,
            "end_date": end_date,
            "accounts": {"stock": 10000000},
            'data_bundle_path': r'E:\rq\bundle',
        },
        "mod": {
            "sys_analyser": {
                "enabled": True,
                "plot": False,
                "benchmark": "000300.XSHG",
                "output_file": output_path + ".pkl",
                "plot_save_file": output_path + ".png",
            },
            "sys_transaction_cost": {
                "cn_stock_min_commission": None,
                "stock_min_commission": stock_min_commission,
                "stock_commission_multiplier": stock_commission_multiplier,
                "futures_commission_multiplier": 1,
                "tax_multiplier": tax_multiplier,
                "pit_tax": pit_tax,
            },
            "sys_simulation": {
                "volume_limit": volume_limit,
                "volume_percent": volume_percent,
                "inactive_limit": inactive_limit,
            },
        }
    }
    run_func(init=init, handle_bar=handle_bar, config=__config__)
    print(f"运行时间: {time.time() - t:.1f} 秒")
