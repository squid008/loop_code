# -*- coding: utf-8 -*-
"""
多模式策略(本地 PIT/行情因子, 无未来函数)
  mode=roe_small   : 小市值 + ROE环比增长 + PB过滤 (周频)   [聚宽01.txt]
  mode=div_lowvol  : 红利低波: 高股息 + 低波动 (月频, 防御)
  mode=momentum    : 动量: 12月动量剔除最近1月 (月频, 进攻)
用法: python all_multi.py --mode=div_lowvol
"""
import os
import sys
import time
import numpy as np
import pandas as pd

from rqalpha import run_func
from bt_utils import basename, finish, load_netval

mode = 'roe_small'
select_num = 10
USE_REV = False      # 是否加 1 月反转增强
INCLUDE_GEM = True   # 是否含创业板(300/301)
for a in sys.argv[1:]:
    if a.startswith('--mode='):
        mode = a[7:]
    elif a.startswith('--num='):
        select_num = int(a[6:])
    elif a == '--rev':
        USE_REV = True
    elif a == '--nogem':
        INCLUDE_GEM = False

start_date = "2014-10-01"
end_date = "2026-08-05"
weight_cash_buffer = 0.95
min_list_days = 250
stock_min_commission = 5
stock_commission_multiplier = 2.5
tax_multiplier = 1
pit_tax = False
volume_limit = True
volume_percent = 0.25
inactive_limit = True

# 红利低波参数
DIV_MIN = 1.5        # 股息率下限(%)
DIV_TOP = 0.30       # 先取股息率前 30%
MKT_MIN = 3e9        # 市值下限 30亿(避开微盘, 红利股偏大中盘)
REV_POOL = 3         # 反转增强: 先取市值最小 N*REV_POOL 只, 再按1月动量升序取 N
PB_TOP = 0.50        # PB 最小的前 50%
ROEINC_TOP = 0.10    # ROE环比增长前 10%


def blocked_stock(s, include_gem=True):
    """板块过滤: 科创板/北交所必剔; 创业板可选"""
    if s.startswith('688') or s.startswith('689'):   # 科创板
        return True
    if s.startswith('8') or s.startswith('4') or s.startswith('920'):  # 北交所
        return True
    if not include_gem and s.startswith('30'):       # 创业板 300/301
        return True
    return False

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
    snap = pd.read_pickle(SNAP_PATH)
    context.snap = {int(k): v for k, v in snap.groupby('date')}
    ins = all_instruments(type='CS')
    ins = ins[['order_book_id', 'listed_date', 'de_listed_date']].copy()
    ins['listed'] = [to_int_date(v, 19000101) for v in ins['listed_date']]
    ins['delisted'] = [to_int_date(v, 99999999) for v in ins['de_listed_date']]
    context.ins = ins.set_index('order_book_id')
    if mode == 'roe_small':
        scheduler.run_weekly(rebalance, tradingday=1)
    else:
        scheduler.run_monthly(rebalance, tradingday=1)


def handle_bar(context, bar_dict):
    pass


def rebalance(context, bar_dict):
    d = int(context.now.strftime('%Y%m%d'))
    df = context.snap.get(d)
    if df is None:
        return
    ins = context.ins
    alive = ins[(ins['listed'] <= d) & (ins['delisted'] >= d)].index
    cutoff = int((context.now - pd.Timedelta(days=min_list_days)).strftime('%Y%m%d'))
    ok = set(s for s in alive if ins.at[s, 'listed'] <= cutoff)
    ok = set(s for s in ok if not blocked_stock(s, INCLUDE_GEM))

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

    if mode == 'roe_small':
        df = df[(df['pb'] > 0) & (df['eps'] > 0)]
        df = df.sort_values('pb').head(max(int(len(df) * PB_TOP), select_num))
        df = df.dropna(subset=['roe_inc']).sort_values('roe_inc', ascending=False)
        df = df.head(max(int(len(df) * ROEINC_TOP), select_num))
        df = df.dropna(subset=['circ_mktcap']).sort_values('circ_mktcap')
        if USE_REV:
            # 1月反转增强: 在市值最小的 N*REV_POOL 里, 买近1月跌幅最大的(不追高)
            df = (df.head(select_num * REV_POOL)
                    .dropna(subset=['mom20'])
                    .sort_values('mom20'))
    elif mode == 'div_lowvol':
        df = df[(df['div_yield'] >= DIV_MIN) & (df['mktcap'] >= MKT_MIN)]
        df = df.sort_values('div_yield', ascending=False)
        df = df.head(max(int(len(df) * DIV_TOP), select_num))
        df = df.dropna(subset=['vol60']).sort_values('vol60')
    else:  # momentum
        df = df.dropna(subset=['mom250_20'])
        df = df[df['mktcap'] >= MKT_MIN]
        df = df.sort_values('mom250_20', ascending=False)

    df = df.head(select_num)
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
    logger.info(f"{d} [{mode}] 调仓 {len(df)} 只: {list(df['obid'])[:6]}")


if __name__ == '__main__':
    tag = mode + ('_rev' if USE_REV else '') + ('_nogem' if not INCLUDE_GEM else '') + f"_n{select_num}"
    output_path = os.path.join(HERE, basename(__file__, start_date, end_date))
    __config__ = {
        "base": {
            "start_date": start_date,
            "end_date": end_date,
            "accounts": {"stock": 10000000},
            'data_bundle_path': r'E:\rq\bundle',
        },
        "mod": {
            "sys_analyser": {
                "enabled": True, "plot": False, "benchmark": "000300.XSHG",
                "output_file": output_path + ".pkl",
                "plot_save_file": output_path + ".png",
            },
            "sys_transaction_cost": {
                "cn_stock_min_commission": None,
                "stock_min_commission": stock_min_commission,
                "stock_commission_multiplier": stock_commission_multiplier,
                "futures_commission_multiplier": 1,
                "tax_multiplier": tax_multiplier, "pit_tax": pit_tax,
            },
            "sys_simulation": {
                "volume_limit": volume_limit, "volume_percent": volume_percent,
                "inactive_limit": inactive_limit,
            },
        }
    }
    run_func(init=init, handle_bar=handle_bar, config=__config__)
    print(f"运行时间: {time.time() - t:.1f} 秒")

    nv, bench = load_netval(output_path + ".pkl")
    finish(__file__, start_date, end_date, output_path + ".pkl",
           curves={tag: nv}, bench=bench,
           title=f"{tag} 净值曲线", extra_tag=f"模式: {tag}")
