# -*- coding: utf-8 -*-
"""
cd D:\loop_code\strategies\all04; D:\miniconda3\envs\rqdata\python.exe all04_f11_idx.py --idx=300

【F11 指数内增强回测】(rqalpha 真实撮合, 全摩擦)
================================================================
因子: F11 = ts_mean60( (H/L)/low * intraday^2 * ret ), 入库取反方向(正IC)
      (loop 挖掘入库因子, engine 评测: IC 0.0588 / 费后超额+6.4% / Calmar 0.53)
用法:
  python all04_f11_idx.py --idx=300 --n=30   # 沪深300成分内 Top30, 基准沪深300
  python all04_f11_idx.py --idx=500 --n=50   # 中证500成分内 Top50, 基准中证500
  python all04_f11_idx.py --idx=off --n=300  # 全市场宽池(对照), 基准沪深300
无未来函数: 因子取 **T-1 日**面板行(收盘后可知), 周频调仓(周一), 成交用当日盘中价。
成本/撮合与 all03 一致: 佣金万八x2.5(单边千二含滑点) / 印花税 / 成交量限制25% / 停牌禁交易
"""
import os
import sys
import time
import bisect
import numpy as np
import pandas as pd

# rqalpha 的 API 由 run_func 在运行时注入全局, 不能显式 import
from rqalpha import run_func

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bt_utils import basename, load_netval, finish, stats

# ===================== 参数 =====================
start_date = "2017-01-03"
end_date = "2026-08-05"
IDX = "300"                     # '300'/'500'=成分内增强; 'off'=全市场宽池对照
N_HOLD = 30                     # 每期持股数(成分内建议 300->30, 500->50)
MIN_LIST_DAYS = 250
USE_UNIVERSE = False            # True=用 engine/universe.h5 可交易池(研究口径 Top10%)
TOP_PCT = 0.10                  # USE_UNIVERSE=True 时取池内前 TOP_PCT

# ---- 恐慌期加杠杆(与 all03 同参数, 可关) ----
USE_PANIC_LEV = True
PANIC_DD = 40.0
PANIC_LEV = 1.5
FIN_RATE = 0.06

# ---- 交易成本 / 撮合(与 all03 完全一致) ----
weight_cash_buffer = 0.95
stock_min_commission = 5
stock_commission_multiplier = 2.5      # 万八 x2.5 = 单边千二(含滑点)
tax_multiplier = 1
pit_tax = False
volume_limit = True
volume_percent = 0.25
inactive_limit = True
# ===============================================

HERE = os.path.dirname(os.path.abspath(__file__))
F11_PATH = os.path.join(HERE, 'f11_daily.pkl')
REGIME_PATH = os.path.join(HERE, 'market_regime.csv')
IDX_PATH = {'300': r'E:\rq\constituents\index\000300.XSHG.h5',
            '500': r'E:\rq\constituents\index\000905.XSHG.h5'}
IDX_BENCH = {'300': '000300.XSHG', '500': '000905.XSHG'}


def load_index_items(path):
    """返回 [(生效日int, set(obid))] 升序"""
    import h5py
    out = []
    with h5py.File(path, 'r') as f:
        cd = [x.decode() if isinstance(x, bytes) else str(x)
              for x in f['change_dates'][:]]
        for d in cd:
            mem = set(x.decode() if isinstance(x, bytes) else str(x)
                      for x in f['components'][d][:])
            out.append((int(d.replace('-', '')), mem))
    out.sort(key=lambda x: x[0])
    return out
# 迁移后 universe.h5 随引擎放在 D:\loop_code\engine（相对定位，支持整仓搬迁）
UNIV_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'engine', 'universe.h5')


def to_int_date(v, default):
    s = str(v)
    if s in ('nan', 'NaT', 'None', ''):
        return default
    s = s.replace('-', '').replace('/', '')[:8]
    try:
        return int(s)
    except ValueError:
        return default


def blocked_stock(s):
    """科创板/北交所必剔; 创业板保留"""
    if s.startswith('688') or s.startswith('689'):
        return True
    if s.startswith('8') or s.startswith('4') or s.startswith('920'):
        return True
    return False


t = time.time()


def init(context):
    from rqalpha.utils.logger import user_log
    from logbook import StderrHandler
    user_log.handlers = [StderrHandler(
        format_string='{record.time:%Y-%m-%d %H:%M:%S} - {record.level_name}  -  {record.message}',
        bubble=False)]

    fac = pd.read_pickle(F11_PATH)
    if isinstance(fac, dict):
        fac = fac['raw']
    context.g6 = {'raw': fac}
    context.g6_dates = fac.index.values
    context.g6_cols = list(fac.columns)
    context.g6_modes = ['raw']
    logger.info(f"F11 已加载: {len(context.g6_dates)} 日 x {len(context.g6_cols)} 股")

    # 指数成分(成分内增强)
    context.idx_items = None
    context.idx_dates = None
    if IDX in IDX_PATH:
        context.idx_items = load_index_items(IDX_PATH[IDX])
        context.idx_dates = [x[0] for x in context.idx_items]

    if USE_UNIVERSE:
        with pd.HDFStore(UNIV_PATH, 'r') as st:
            U = st['universe']
        U = U.reindex(index=context.g6_dates, columns=context.g6_cols).fillna(False)
        context.univ = U
        context.univ_dates = U.index.values
        logger.info(f"research universe 已加载: {U.shape}, 占比 {U.values.mean()*100:.1f}%")

    ins = all_instruments(type='CS')
    ins = ins[['order_book_id', 'listed_date', 'de_listed_date']].copy()
    ins['listed'] = [to_int_date(v, 19000101) for v in ins['listed_date']]
    ins['delisted'] = [to_int_date(v, 99999999) for v in ins['de_listed_date']]
    context.ins = ins.set_index('order_book_id')

    context.last_pick = None
    scheduler.run_weekly(rebalance, tradingday=1)


def handle_bar(context, bar_dict):
    pass


def g6_row(context, d):
    """取 T-1 日的 F11(入库方向) 行"""
    i = int(np.searchsorted(context.g6_dates, d, 'left')) - 1
    if i < 0:
        return None
    v = context.g6['raw'].values[i]
    if np.isfinite(v).sum() < 100:
        return None
    return pd.Series(v, index=context.g6_cols, name=context.g6_dates[i])


def pick(context, bar_dict):
    d = int(context.now.strftime('%Y%m%d'))
    row = g6_row(context, d)
    if row is None:
        return []
    g = row.dropna()
    if USE_UNIVERSE:
        # 严格复刻研究: 只在 research universe 内选, 取池内前 TOP_PCT
        i = int(np.searchsorted(context.univ_dates, d, 'left')) - 1
        if i >= 0:
            u = context.univ.values[i]
            g = g[np.array([u[context.g6_cols.index(s)] for s in g.index])]
        n = max(N_HOLD, int(len(g) * TOP_PCT))
    else:
        n = N_HOLD
    ins = context.ins
    alive = ins[(ins['listed'] <= d) & (ins['delisted'] >= d)].index
    cutoff = int((context.now - pd.Timedelta(days=MIN_LIST_DAYS)).strftime('%Y%m%d'))
    # 指数成分内约束(可选)
    members = None
    if context.idx_items is not None:
        j = bisect.bisect_right(context.idx_dates, d) - 1
        if j >= 0:
            members = context.idx_items[j][1]
    # 可交易过滤: 在上市/未退市/非科创北交/新股 范围内, 再剔 ST/停牌/涨停/无成交
    cands = [s for s in g.index
             if s in alive and not blocked_stock(s)
             and ins.at[s, 'listed'] <= cutoff
             and (members is None or s in members)]
    keep = []
    for s in cands:
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
        if lu and px >= lu - 1e-6:      # 涨停不可买
            continue
        keep.append(s)
    if not keep:
        return []
    g = g.reindex(keep).dropna().sort_values(ascending=False)
    return list(g.index[:n])


def rebalance(context, bar_dict):
    d = int(context.now.strftime('%Y%m%d'))
    picks = pick(context, bar_dict)
    if not picks:
        return
    each = weight_cash_buffer / len(picks)
    for p in get_positions():
        if p.order_book_id not in picks:
            order_target_value(p.order_book_id, 0)
    for s in picks:
        order_target_percent(s, each)
    context.last_pick = picks
    logger.info(f"{d} 持仓 {len(picks)} 只")


def apply_panic_leverage(nv, dd_hi=PANIC_DD, lev_v=PANIC_LEV, rate=FIN_RATE):
    """与 all03 相同: T-1 日超跌信号作用于 T 日, 借入部分按日计息"""
    rg = pd.read_csv(REGIME_PATH, index_col=0)
    rg.index = pd.to_datetime(rg.index)
    dd = rg['dd25'].reindex(rg.index.union(nv.index)).ffill().loc[nv.index]
    lev = pd.Series(1.0, index=nv.index)
    lev[dd >= dd_hi] = lev_v
    lev_lag = lev.shift(1).fillna(1.0)
    r = nv.pct_change().fillna(0.0)
    net = (1 + r * lev_lag - (lev_lag - 1.0) * rate / 252).cumprod()
    return net / net.iloc[0], int((lev > 1.0).sum())


if __name__ == '__main__':
    for a in sys.argv[1:]:
        if a.startswith('--idx='):
            IDX = a[6:]
        elif a.startswith('--n='):
            N_HOLD = int(a[4:])
        elif a == '--universe':
            USE_UNIVERSE = True
        elif a.startswith('--top='):
            TOP_PCT = float(a[6:])
        elif a == '--nolev':
            USE_PANIC_LEV = False
    if '--idx' not in ''.join(sys.argv[1:]) and N_HOLD == 30:
        IDX = 'off'          # 未指定 idx 且未改 n -> 全市场对照(与原模板一致)
    scope = ('全市场' if IDX == 'off' else ('沪深300成分内' if IDX == '300'
                                            else '中证500成分内'))
    bench_sym = IDX_BENCH.get(IDX, '000300.XSHG')

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
                "enabled": True,
                "plot": False,
                "benchmark": bench_sym,
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
    print(f"\n回测运行时间: {time.time() - t:.1f} 秒")

    nv, bench = load_netval(output_path + ".pkl")
    curves = {f'F11 {scope} N={N_HOLD}': nv}
    if USE_PANIC_LEV:
        net, n_days = apply_panic_leverage(nv)
        curves[f'+恐慌杠杆{PANIC_LEV}x'] = net
        print(f"(超跌股占比>={PANIC_DD:.0f}% 触发 {n_days} 个交易日, 融资利率 {FIN_RATE:.0%})")

    finish(__file__, start_date, end_date, output_path + ".pkl",
           curves=curves, bench=bench,
           title=f'F11 因子回测: {scope} 按因子降序等权取{N_HOLD}只',
           extra_tag=f'因子: F11=ts_mean60[(H/L)/low*intraday^2*ret](入库取反); '
                     f'{scope}选股, 周频等权; 成本与 all03 一致(单边千二含滑点); '
                     f'基准 {bench_sym}')

    final = net if USE_PANIC_LEV else nv
    print("\n年度:     收益率     年内回撤")
    for y, g in final.groupby(final.index.year):
        print(f"  {y}    {(g.iloc[-1]/g.iloc[0]-1)*100:7.2f}%   "
              f"{(g/g.cummax()-1).min()*100:7.2f}%")
