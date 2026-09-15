# -*- coding: utf-8 -*-
"""
rqalpha 回测: 科创板+创业板 科技龙头 (688 / 300 / 301)
  选股: 市值最大 N 只(历史检验: 该池内市值龙头年化17.17%, 显著跑赢中证1000的7.17%)
  可选: 估值择时 / 恐慌期加杠杆
用法: python bt_tech.py --num=10 [--val=0.95,0.5,250] [--panic=40,1.5,0.06]
       [--sort=mktcap|mom20|vol60_asc] [--start=2019-01-01]
"""
import os
import sys
import time
import glob
from datetime import datetime
import numpy as np
import pandas as pd

sys.path.insert(0, r'D:\rqalpha_demo\strategies')
from bt_utils import basename, finish, load_netval, stats as bstats

from rqalpha import run_func

start_date = "2019-01-01"
end_date = "2026-08-05"
N = 10
SORT = 'mktcap'
ASC = False
LOWVOL = False

# 估值择时 / 恐慌杠杆 / 拥挤度调仓
val_opt = None
panic_opt = None
crowd_opt = None
ma_opt = None

for a in sys.argv[1:]:
    if a.startswith('--num='):
        N = int(a[6:])
    elif a.startswith('--start='):
        start_date = a[8:]
    elif a.startswith('--sort='):
        v = a[7:]
        SORT, ASC = (v[:-4], True) if v.endswith('_asc') else (v, False)
    elif a.startswith('--val='):
        thr, fl, lb = a[6:].split(',')
        val_opt = (float(thr), float(fl), int(lb))
    elif a.startswith('--panic='):
        dd, lv, rt = a[8:].split(',')
        panic_opt = (float(dd), float(lv), float(rt))
    elif a.startswith('--crowd='):
        hi, lo, fl = a[8:].split(',')
        crowd_opt = (float(hi), float(lo), float(fl))
    elif a.startswith('--ma='):
        w, fl = a[5:].split(',')
        ma_opt = (int(w), float(fl))
    elif a == '--lowvol':
        LOWVOL = True

weight_cash_buffer = 0.95
stock_min_commission = 5
stock_commission_multiplier = 2.5
tax_multiplier = 1
pit_tax = False
volume_limit = True
volume_percent = 0.25
inactive_limit = True
MIN_LIST_DAYS = 250

HERE = os.path.dirname(os.path.abspath(__file__))
SNAP = r'D:\rqalpha_demo\strategies\all01\factor_snapshot.pkl'
REGIME = r'D:\rqalpha_demo\strategies\all01\market_regime.csv'
CROWD = r'D:\rqalpha_demo\strategies\all01\turnover_pctile.csv'
STEM = 'bt_tech'

t = time.time()


def build_pb_percentile(lb):
    snap = pd.read_pickle(SNAP)
    med = snap.groupby('date')['pb'].median()
    pct = med.rolling(lb, min_periods=lb // 2).rank(pct=True)
    return {int(k): v for k, v in pct.items()}


def init(context):
    from rqalpha.utils.logger import user_log
    from logbook import StderrHandler
    user_log.handlers = [StderrHandler(
        format_string='{record.time:%Y-%m-%d} - {record.message}', bubble=False)]
    snap = pd.read_pickle(SNAP)
    snap['date'] = snap['date'].astype(int)
    context.snap = {int(k): v for k, v in snap.groupby('date')}
    context.snap_dates = sorted(context.snap.keys())
    if val_opt:
        context.pb_pct = build_pb_percentile(val_opt[2])
    if crowd_opt:
        cw = pd.read_csv(CROWD)
        context.crowd = dict(zip(cw['date'].astype(int), cw['top10_pctile_10y']))
        context.crowd_dates = sorted(context.crowd.keys())
    ins = all_instruments(type='CS')
    ins = ins[['order_book_id', 'listed_date', 'de_listed_date']].copy()
    ins['listed'] = [int(str(v).replace('-', '')[:8]) if str(v) not in ('nan', 'NaT') else 19000101
                     for v in ins['listed_date']]
    ins['delisted'] = [int(str(v).replace('-', '')[:8]) if str(v) not in ('nan', 'NaT') else 99999999
                       for v in ins['de_listed_date']]
    context.ins = ins.set_index('order_book_id')
    scheduler.run_monthly(rebalance, tradingday=1)


def handle_bar(context, bar_dict):
    pass


def rebalance(context, bar_dict):
    d = int(context.now.strftime('%Y%m%d'))
    sd = None
    for x in context.snap_dates:
        if x <= d:
            sd = x
        else:
            break
    if sd is None:
        return
    df = context.snap[sd]
    ins = context.ins
    alive = ins[(ins['listed'] <= d) & (ins['delisted'] >= d)].index
    cutoff = int((context.now - pd.Timedelta(days=MIN_LIST_DAYS)).strftime('%Y%m%d'))
    ok = set(s for s in alive
             if (s.startswith('688') or s.startswith('689') or s.startswith('30'))
             and ins.at[s, 'listed'] <= cutoff)

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

    if LOWVOL:
        # 先取市值最大的 N*3 只, 再在其中选波动最低的 N 只(降回撤)
        df = (df.dropna(subset=['mktcap']).sort_values('mktcap', ascending=False)
                .head(N * 3).dropna(subset=['vol60']).sort_values('vol60'))
    elif SORT == 'mktcap':
        df = df.dropna(subset=['mktcap']).sort_values('mktcap', ascending=False)
    else:
        df = df.dropna(subset=[SORT]).sort_values(SORT, ascending=ASC)
    df = df.head(N)
    if df.empty:
        return

    coef = weight_cash_buffer
    if val_opt and context.pb_pct.get(d, np.nan) >= val_opt[0]:
        coef *= val_opt[1]
    if crowd_opt:
        # 数据结论: 拥挤度高时资金抱团小盘/题材, 后续小盘跑赢概率59%
        # 故 高拥挤->维持满仓, 低拥挤->减仓防御
        hi, lo, fl = crowd_opt
        i = None
        for j, x in enumerate(context.crowd_dates):
            if x < d:
                i = j
            else:
                break
        if i is not None:
            p = context.crowd[context.crowd_dates[i]]
            if not np.isnan(p) and p <= lo:
                coef *= fl
    if ma_opt:
        _w, _fl = ma_opt
        _p = history_bars('000852.XSHG', _w, '1d', 'close')
        if _p is not None and len(_p) >= _w and _p[-1] < _p.mean():
            coef *= _fl

    w = coef / len(df)
    target = {s: w for s in df['obid']}
    for p in get_positions():
        if p.order_book_id not in target:
            order_target_value(p.order_book_id, 0)
    for s, v in target.items():
        order_target_percent(s, v)
    logger.info(f"{d} 仓位{coef/weight_cash_buffer:.0%} {len(df)}只 "
                f"市值{(df['mktcap']/1e8).min():.0f}~{(df['mktcap']/1e8).max():.0f}亿")


if __name__ == '__main__':
    out = os.path.join(HERE, basename(__file__, start_date, end_date))
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

    nv, bench = load_netval(out + ".pkl")
    curves = {f'科创创业市值TOP{N}': nv}
    tag = (f"选股: 科创板+创业板(688/300/301) 按{SORT}取前{N}只 | "
           f"调仓: 月频")
    if val_opt:
        tag += f"\n估值择时: 全市场中位PB {val_opt[2]}日分位>={val_opt[0]:.0%} -> 仓位{val_opt[1]:.0%}"
    if crowd_opt:
        tag += (f"\n拥挤度择时: 成交额Top10%占比10年分位<={crowd_opt[1]:.0%} -> "
                f"减仓至{crowd_opt[2]:.0%} (高拥挤维持满仓)")
    if ma_opt:
        tag += f"\n趋势择时: 中证1000 收盘<MA{ma_opt[0]} -> 仓位{ma_opt[1]:.0%}"

    if panic_opt:
        dd_hi, lev_v, rate = panic_opt
        rg = pd.read_csv(REGIME, index_col=0)
        rg.index = pd.to_datetime(rg.index)
        dd = rg['dd25'].reindex(rg.index.union(nv.index)).ffill().loc[nv.index]
        lev = pd.Series(1.0, index=nv.index)
        lev[dd >= dd_hi] = lev_v
        lag = lev.shift(1).fillna(1.0)
        net = (1 + nv.pct_change().fillna(0) * lag - (lag - 1) * rate / 252).cumprod()
        net = net / net.iloc[0]
        curves[f'+恐慌杠杆{lev_v}x'] = net
        tag += f"\n恐慌加杠杆: 超跌股>={dd_hi:.0f}% -> {lev_v}x (触发{int((lev>1).sum())}日, 融资{rate:.0%})"

    finish(__file__, start_date, end_date, out + ".pkl",
           curves=curves, bench=bench, title=f'科创板+创业板科技龙头 TOP{N}',
           extra_tag=tag)
