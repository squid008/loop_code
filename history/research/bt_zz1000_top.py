# -*- coding: utf-8 -*-
"""
rqalpha 回测: 中证1000 成分中市值最大的 N 只 (用户所谓"中证1000大市值科技股")
选股用 factor_snapshot 的 mktcap(PIT), 交易用 rqalpha 价格(自动复权)
用法: python bt_zz1000_top.py --num=10 [--weekly]
"""
import os
import sys
import time
import glob
from datetime import datetime
import h5py
import numpy as np
import pandas as pd

from rqalpha import run_func

start_date = "2014-10-01"
end_date = "2026-08-05"
N = 10
WEEKLY = False
SORT = 'mktcap'          # mktcap降序 / mom20 / mom250_20 / vol60升序
ASC = False
for a in sys.argv[1:]:
    if a.startswith('--num='):
        N = int(a[6:])
    elif a == '--weekly':
        WEEKLY = True
    elif a.startswith('--sort='):
        v = a[7:]
        if v.endswith('_asc'):
            SORT, ASC = v[:-4], True
        else:
            SORT, ASC = v, False

weight_cash_buffer = 0.95
stock_min_commission = 5
stock_commission_multiplier = 2.5
tax_multiplier = 1
pit_tax = False
volume_limit = True
volume_percent = 0.25
inactive_limit = True

HERE = os.path.dirname(os.path.abspath(__file__))
SNAP = r'D:\rqalpha_demo\strategies\all01\factor_snapshot.pkl'
IDX = r'E:\rq\constituents\index\000852.XSHG.h5'

STEM = 'bt_zz1000_top'
SD, ED = start_date.replace('-', ''), end_date.replace('-', '')


def load_idx_hist():
    out = []
    with h5py.File(IDX, 'r') as f:
        cd = f['change_dates'][:].astype(str)
        for d in cd:
            mem = set(x.decode() if isinstance(x, bytes) else str(x)
                      for x in f['components'][d][:])
            out.append((int(d.replace('-', '')), mem))
    out.sort()
    return out


t = time.time()


def init(context):
    from rqalpha.utils.logger import user_log
    from logbook import StderrHandler
    user_log.handlers = [StderrHandler(
        format_string='{record.time:%Y-%m-%d} - {record.message}', bubble=False)]
    snap = pd.read_pickle(SNAP)
    snap['date'] = snap['date'].astype(int)
    context.snap = {int(k): v for k, v in snap.groupby('date')}
    context.snap_dates = sorted(context.snap.keys())
    context.hist = load_idx_hist()
    ins = all_instruments(type='CS')
    ins = ins[['order_book_id', 'listed_date', 'de_listed_date']].copy()
    ins['listed'] = [int(str(v).replace('-', '')[:8]) if str(v) not in ('nan', 'NaT') else 19000101
                     for v in ins['listed_date']]
    ins['delisted'] = [int(str(v).replace('-', '')[:8]) if str(v) not in ('nan', 'NaT') else 99999999
                       for v in ins['de_listed_date']]
    context.ins = ins.set_index('order_book_id')
    if WEEKLY:
        scheduler.run_weekly(rebalance, tradingday=1)
    else:
        scheduler.run_monthly(rebalance, tradingday=1)


def handle_bar(context, bar_dict):
    pass


def rebalance(context, bar_dict):
    d = int(context.now.strftime('%Y%m%d'))
    # 取 <= d 的最近快照(快照为周频)
    sd = None
    for x in context.snap_dates:
        if x <= d:
            sd = x
        else:
            break
    if sd is None:
        return
    df = context.snap[sd]

    mem = None
    for eff, m in context.hist:
        if eff <= d:
            mem = m
        else:
            break
    if not mem:
        return

    ins = context.ins
    alive = ins[(ins['listed'] <= d) & (ins['delisted'] >= d)].index
    ok = set(mem) & set(alive)

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

    if SORT == 'mktcap':
        df = df.dropna(subset=['mktcap']).sort_values('mktcap', ascending=False)
    else:
        df = df.dropna(subset=[SORT]).sort_values(SORT, ascending=ASC)
    df = df.head(N)
    if df.empty:
        return

    w = weight_cash_buffer / len(df)
    target = {s: w for s in df['obid']}
    for p in get_positions():
        if p.order_book_id not in target:
            order_target_value(p.order_book_id, 0)
    for s, v in target.items():
        order_target_percent(s, v)
    caps = df['mktcap'] / 1e8
    logger.info(f"{d} 中证1000市值TOP{len(df)}: {caps.min():.0f}~{caps.max():.0f}亿")


if __name__ == '__main__':
    tag = f"{SORT}{'_asc' if ASC else ''}"
    out = os.path.join(HERE, f"{STEM}_{tag}_n{N}_{'_w' if WEEKLY else 'm'}_"
                             f"{datetime.now().strftime('%Y%m%d_%H%M_%S')}_{SD}_{ED}")
    __config__ = {
        "base": {"start_date": start_date, "end_date": end_date,
                 "accounts": {"stock": 10000000}, 'data_bundle_path': r'E:\rq\bundle'},
        "mod": {
            "sys_analyser": {"enabled": True, "plot": False, "benchmark": "000852.XSHG",
                             "output_file": out + ".pkl", "plot_save_file": out + ".png"},
            "sys_transaction_cost": {"cn_stock_min_commission": None,
                                     "stock_min_commission": stock_min_commission,
                                     "stock_commission_multiplier": stock_commission_multiplier,
                                     "futures_commission_multiplier": 1,
                                     "tax_multiplier": tax_multiplier, "pit_tax": pit_tax},
            "sys_simulation": {"volume_limit": volume_limit, "volume_percent": volume_percent,
                               "inactive_limit": inactive_limit},
        }
    }
    run_func(init=init, handle_bar=handle_bar, config=__config__)
    print(f"运行时间: {time.time()-t:.1f}s")
    print("产物:", os.path.basename(out) + ".pkl")
