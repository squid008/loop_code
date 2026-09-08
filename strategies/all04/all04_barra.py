# -*- coding: utf-8 -*-
"""
cd D:\loop_code\strategies\all04; D:\miniconda3\envs\rqdata\python.exe all04_barra.py

【纯因子回测】combo_g6 (barra 口径) 单因子选股
================================================================
不做任何风格/行业叠加, 每周在全市场可交易池里按 combo_g6(barra) 降序取前 N 只等权持有,
用来直接观察因子本身的净值曲线(而不是在 all03 里做增量)。

因子: combo_g6 = 等权 rank(营业利润TTM环比, 营业总收入TTM环比, 单季营业利润同比,
                          单季净利同比, 经营现金流/总资产)
口径: barra = 对 BARRA size + 31 申万行业 中性化后的截面排序
      研究框架(2018-2026, 周频, 池内等权)结果:
        raw   +2.83%  回撤-22.8%  Calmar 0.12  (Top组市值分位0.588, 偏大盘)
        barra +5.25%  回撤 -6.6%  Calmar 0.79  (九个年度超额全部为正)
        strat +4.79%  回撤 -8.4%  Calmar 0.57

区间: 2017-01-03 ~ 2026-08-05  (barra 行业数据起点, 保证"纯 barra"无回退污染)

交易成本与 all03 完全一致:
  佣金 万八 x2.5 = 单边千二(含滑点) / 印花税1 / 成交量限制25% / 停牌不可交易

无未来函数: g6 由 PIT 按公告日(info_date)展开; 取 **T-1 日**因子行(盘中不可知当日公告)

==================== 实测结果(2017-01-03 ~ 2026-08-05, 成本同 all03) ====================
| 持股数 | 全区间年化 | 2018起年化 | 回撤 | Sharpe | vs沪深300(2018起) |
|---|---|---|---|---|---|
| N=30  | 1.97%  | 2.20%  | -39.7% | 0.313 | **-1.86pp** |
| N=300 | 5.17%  | 5.79%  | -36.6% | 0.442 | **+1.73pp** |
| (基准沪深300) | 3.63% | 4.06% | -45.6% | 0.286 | — |
| **对照 all03** | **24.20%**(2017起) | **27.36%** | -25.6% | **0.958** | **+19.60pp** |

**结论: 纯 combo_g6 单因子无法兑现研究里的 +5.25%, 单独用不构成好策略。**
研究框架 Top组绝对年化 14.37%(2018起), 实盘 N=300 只有 5.79%, 差 8.6pp。差异来源:
  1. **集中度**: N=30 → N=300 年化从 2.20% 升到 5.79%(+3.6pp), 证实集中度是最大单一因素
  2. **交易成本**: 研究按 (1-换手)×0.001×2 计(往返0.2%); 实盘佣金千二单边+印花税千一
     (往返0.5%), 按年换手~420% 算, 成本差约 1.3pp/年
  3. **低流动性个股**: 研究只在 universe(占57.9%, 剔ST/停牌/新股/20日均成交额<1000万/
     涨跌停)内选; 本策略池更宽, 实盘出现"跌停无法卖出"被拒单, 拖累明显
     (注: 诊断显示 Top300 有65~92%本就落在 universe 内, 故此项非主因但是负贡献)
  4. 研究基准是"可交易池等权"(年化8.95%, 本身跑赢沪深300约4.9pp);
     本策略 5.79% 相对该基准实为**负超额**, 与研究的正超额结论相反

=> combo_g6 是"统计上显著、实盘上不可用"的因子: 它在严格控制的研究环境下有 +5% 超额,
   但在真实交易约束(真实成本/集中度/流动性)下无法兑现。**生产策略维持 all03。**

运行: python all04_barra.py            (默认 N=30)
      python all04_barra.py --n=300    (贴近研究口径 Top10%)
      python all04_barra.py --n=10 --nolev
"""
import os
import sys
import time
import numpy as np
import pandas as pd

# rqalpha 的 API 由 run_func 在运行时注入全局, 不能显式 import
from rqalpha import run_func

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bt_utils import basename, load_netval, finish, stats

# ===================== 参数 =====================
start_date = "2017-01-03"       # barra 行业数据起点
end_date = "2026-08-05"
N_HOLD = 30                     # 持股数(研究框架为 universe 内 Top10%≈435只)
MIN_LIST_DAYS = 250
# 严格复刻研究口径: 只在 research universe 内选股, 并取该池的 Top10%
USE_UNIVERSE = False            # True=用 ai_test/universe.h5 的可交易池
TOP_PCT = 0.10                  # 取池内前 10%(与研究 evaluate 一致)

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
G6_PATH = os.path.join(HERE, 'g6_daily.pkl')
REGIME_PATH = os.path.join(HERE, 'market_regime.csv')
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

    g6 = pd.read_pickle(G6_PATH)
    context.g6 = g6
    context.g6_dates = g6['raw'].index.values
    context.g6_cols = list(g6['raw'].columns)
    context.g6_modes = ['barra']                 # 纯 barra, 不回退
    logger.info(f"combo_g6 已加载: {len(context.g6_dates)} 日 x {len(context.g6_cols)} 股 "
                f"(口径 barra)")

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
    """取 T-1 日的 barra 口径 g6 行"""
    i = int(np.searchsorted(context.g6_dates, d, 'left')) - 1
    if i < 0:
        return None
    v = context.g6['barra'].values[i]
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
    # 可交易过滤: 在上市/未退市/非科创北交/新股 范围内, 再剔 ST/停牌/涨停/无成交
    cands = [s for s in g.index
             if s in alive and not blocked_stock(s)
             and ins.at[s, 'listed'] <= cutoff]
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
        if a.startswith('--n='):
            N_HOLD = int(a[4:])
        elif a == '--universe':
            USE_UNIVERSE = True
        elif a.startswith('--top='):
            TOP_PCT = float(a[6:])
        elif a == '--nolev':
            USE_PANIC_LEV = False

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
    print(f"\n回测运行时间: {time.time() - t:.1f} 秒")

    nv, bench = load_netval(output_path + ".pkl")
    curves = {f'combo_g6(barra) N={N_HOLD}': nv}
    if USE_PANIC_LEV:
        net, n_days = apply_panic_leverage(nv)
        curves[f'+恐慌杠杆{PANIC_LEV}x'] = net
        print(f"(超跌股占比>={PANIC_DD:.0f}% 触发 {n_days} 个交易日, 融资利率 {FIN_RATE:.0%})")

    finish(__file__, start_date, end_date, output_path + ".pkl",
           curves=curves, bench=bench,
           title=f'纯因子回测: combo_g6 (barra中性化) 等权持有{N_HOLD}只',
           extra_tag=f'选股: 全市场可交易池内按 combo_g6(barra) 降序取 {N_HOLD} 只, 周频等权; '
                     f'成本与 all03 一致(单边千二含滑点)')

    final = net if USE_PANIC_LEV else nv
    print("\n年度:     收益率     年内回撤")
    for y, g in final.groupby(final.index.year):
        print(f"  {y}    {(g.iloc[-1]/g.iloc[0]-1)*100:7.2f}%   "
              f"{(g/g.cummax()-1).min()*100:7.2f}%")
