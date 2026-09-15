# -*- coding: utf-8 -*-
"""
米筐(rqalpha)回测: 白马攻防 (移植聚宽 02.txt, 本地 PIT 无未来函数)
- 股票池: 沪深300成分, 剔除创业/科创/北交/ST/停牌
- 市场温度(cold/warm/hot)按沪深300的220日位置判断
- 不同温度用不同财务条件, 月频调仓 5 只
"""
import os
import time
import numpy as np
import pandas as pd

from rqalpha import run_func

start_date = "2014-10-01"
end_date = "2026-08-05"
select_num = 5
weight_cash_buffer = 0.95
stock_min_commission = 5
stock_commission_multiplier = 2.5
tax_multiplier = 1
pit_tax = False
volume_limit = True
volume_percent = 0.25
inactive_limit = True

HERE = os.path.dirname(os.path.abspath(__file__))
SNAP_PATH = os.path.join(HERE, 'factor_snapshot.pkl')
CSI300_H5 = r'E:\rq\constituents\index\000300.XSHG.h5'


def load_csi300_history():
    """返回 [(生效日int, set(成分))] 升序; 调仓日取 <=T 的最近一批(历史真实成分, 无未来函数)"""
    import h5py
    out = []
    with h5py.File(CSI300_H5, 'r') as f:
        cd = f['change_dates'][:].astype(str)
        comp = f['components']
        for d in cd:
            members = set(x.decode() if isinstance(x, bytes) else str(x)
                          for x in comp[d][:])
            out.append((int(d.replace('-', '')), members))
    out.sort(key=lambda x: x[0])
    return out


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
    context.csi300_hist = load_csi300_history()

    ins = all_instruments(type='CS')
    ins = ins[['order_book_id', 'listed_date', 'de_listed_date']].copy()
    ins['listed'] = [to_int_date(v, 19000101) for v in ins['listed_date']]
    ins['delisted'] = [to_int_date(v, 99999999) for v in ins['de_listed_date']]
    context.ins = ins.set_index('order_book_id')

    scheduler.run_monthly(rebalance, tradingday=1)


def handle_bar(context, bar_dict):
    pass


def market_temperature(context):
    p = history_bars('000300.XSHG', 220, '1d', 'close')
    if p is None or len(p) < 220:
        return "warm"
    lo, hi = p.min(), p.max()
    if hi <= lo:
        return "warm"
    h = (p[-5:].mean() - lo) / (hi - lo)
    if h < 0.20:
        return "cold"
    if h > 0.90:
        return "hot"
    return "warm"


def rebalance(context, bar_dict):
    d = int(context.now.strftime('%Y%m%d'))
    df = context.snap.get(d)
    if df is None:
        return
    temp = market_temperature(context)

    # 当时生效的沪深300成分(历史名单, 无未来函数)
    members = None
    for eff, m in context.csi300_hist:
        if eff <= d:
            members = m
        else:
            break
    if not members:
        return

    ins = context.ins
    alive = ins[(ins['listed'] <= d) & (ins['delisted'] >= d)].index
    ok = set(s for s in members & set(alive)
             if not s.startswith('30') and not s.startswith('68')
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
        rows.append(s)
    df = df[df['obid'].isin(rows)]
    if df.empty:
        return

    if temp == "cold":
        df = df[(df['pb'] > 0) & (df['pb'] < 1) & (df['ocf_np'] > 2.0)
                & (df['roe'] > 1.5) & (df['np_yoy'] > -0.15)]
        df = df.assign(score=df['roa'] / df['pb']).sort_values('score', ascending=False)
    elif temp == "hot":
        df = df[(df['pb'] > 3) & (df['ocf_np'] > 0.5)
                & (df['roe'] > 3.0) & (df['np_yoy'] > 0.20)]
        df = df.sort_values('roa', ascending=False)
    else:
        df = df[(df['pb'] > 0) & (df['pb'] < 1) & (df['ocf_np'] > 1.0)
                & (df['roe'] > 2.0) & (df['np_yoy'] > 0)]
        df = df.assign(score=df['roa'] / df['pb']).sort_values('score', ascending=False)

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
    logger.info(f"{d} [{temp}] 调仓 {len(df)} 只: {list(df['obid'])}")


if __name__ == '__main__':
    output_path = os.path.join(HERE, os.path.splitext(os.path.basename(__file__))[0]
                               + "_" + start_date + "-" + end_date)
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
