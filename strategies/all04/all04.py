# -*- coding: utf-8 -*-
"""
cd D:\loop_code\strategies\all04; D:\miniconda3\envs\rqdata\python.exe all04.py

组合策略 all04 = all03 + 【小市值池内用 combo_g6 选股】
================================================================
相对 all03 的**唯一改动**: 小市值子策略[A]的最后一步排序因子
  all03: PB最小前50% -> ROE环比前10% -> (总市值60% + 成交额40%) 升序取10只
  all04: 小市值池(总市值最小前30%) -> 池内按 combo_g6【降序】取10只
其余(白马攻防 / 红利低波 / 估值择时 / 拥挤度调权 / 恐慌杠杆)与 all03 完全一致,
便于直接对比"选股因子"这一处的增量。

combo_g6 是什么(见 strategies/all01/factor_roadmap.md Round7):
  等权 rank(营业利润TTM环比, 营业总收入TTM环比, 单季营业利润同比,
            单季净利同比, 经营现金流/总资产)
  —— 六轮因子挖掘(量价/资金流/BARRA/财报/聚宽, 共600+因子)中**唯一**在新门槛下
     (IC_IR>0.15 + 四口径同向 + Calmar>0.5)通过的因子。

为什么用中性化口径(barra)而不是裸因子:
  裸 g6 有大盘倾斜(Top组平均市值分位0.588), 2018-2026 小市值占优期会被风格拖累:
    raw   +2.83% 回撤-22.8%  <- 2021/2022/2023 连续三年负超额
    barra +5.25% 回撤 -6.6%  <- 九个年度超额全部为正
  小市值池内对比更明显: raw +3.13%(Calmar0.32) vs barra +5.88%(Calmar0.94)
  => 本策略取 barra 口径(2017-01 前有行业数据时回退 lnmc 口径)

无未来函数保证:
  - g6 由 PIT 财报按【公告日 info_date】展开(见 ai_test/round5_fund.FundPanels)
  - 中性化用的市值与申万行业哑变量均为**当日**值(barra.h5 逐日行业归属)
  - 调仓日取 **T-1 日**的因子行(盘中不可知当日公告)
  - 财务快照 factor_snapshot.pkl 按公告日对齐(PIT), 沿用 all03

==================== A/B 实验结果(2014-10-01 ~ 2026-08-05) ====================
对照组 `--pool=all03 --no-g6` 精确复现了 all03 的 19.69%/-26.61%/1.120, 说明框架无误。

| 实验 | 小市值池 | 池内排序 | 年化(无杠杆) | 回撤 | Sharpe |
|---|---|---|---|---|---|
| 对照(=all03) | PB前50%→ROE环比前10% | 市值60%+成交额40% | **19.20%** | -28.82% | 1.111 |
| g6 当排序器 | 同上(精选池) | combo_g6(barra) | 12.81% | -32.32% | 0.795 |
| g6 当排序器 | 市值最小30%(宽池) | combo_g6(barra) | 13.51% | -32.70% | 0.819 |
| g6 当筛选器 | PB前50%→g6前30% | 市值60%+成交额40% | 17.81% | -30.28% | 1.051 |
| g6 当筛选器 | PB前50%→g6前10% | 市值60%+成交额40% | 19.10% | **-27.65%** | **1.127** |

**结论: combo_g6 对 all03 无增量(负面结果, 但信息量很大)**
1. **不能当"精选10只"的排序因子**: 年化掉 6.4pp、回撤还扩大 4pp。
   研究框架选的是 Top **10%**(约150只, 分散), 策略只选 **10只**;
   g6 的极端尾部多为会计噪声/基数效应巨变(如利润 1万→100万, 环比+9900%),
   rank 变换保留序 → 顶部全是极值 → 集中持仓把噪声放大成亏损。
   **"因子在分组层面有效" ≠ "推到极致选10只有效"**。
2. 当筛选器(g6前10%)与 all03 原有的"ROE环比前10%"**效果相当**:
   年化 19.10% vs 19.20%(持平)、回撤改善 1.2pp、Sharpe 1.127 vs 1.111(略升)。
3. 根因: all03 的 ROE环比筛选与 combo_g6 高度共线, 信号已被既有条件吃掉。
=> **生产策略维持 all03**(若偏好更低回撤, 可用 --pool=g6filt --gfilt=0.10)

运行: python all04.py --pool=g6filt --gfilt=0.10   (推荐)
      python all04.py --pool=all03 --no-g6          (对照, 复现 all03)
"""
import os
import sys
import time
import bisect
import pickle
import numpy as np
import pandas as pd

# 注意: rqalpha 的 API(all_instruments / is_st_stock / scheduler / logger /
#       order_target_* 等)由 run_func 在运行时注入全局, 不能显式 import(与 all03 一致)
from rqalpha import run_func

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bt_utils import basename, load_netval, finish, stats

# ===================== 策略参数 =====================
start_date = "2014-10-01"
end_date = "2026-08-05"

W_SMALL, W_WHITE, W_DIV = 1.0, 1.0, 1.0
N_SMALL, N_WHITE, N_DIV = 10, 5, 10

# ---- 【all04 新增】小市值选股方式 ----
USE_G6 = True            # True=小市值池内按 combo_g6 排序; False=回退 all03 原逻辑(对照)
SMALL_POOL = 'all03'     # 'all03'=沿用all03精选池(PB前50%->ROE环比前10%, 纯因子A/B)
                         # 'mc30' =总市值最小前30%(贴合Round7研究口径, 但会改动池定义)
SMALL_MC_TOP = 0.30      # 仅 SMALL_POOL='mc30' 时生效
G6_FILT_TOP = 0.30       # 仅 SMALL_POOL='g6filt' 时生效: 保留 g6 最高的前 30%
                         # (不取极端尾部: g6 顶部常是会计噪声/基数效应巨变)
G6_MODE = 'barra'        # 'barra'(size+行业, 2017起) / 'lnmc'(size, 2013起) / 'raw'(对照)

# ---- all03 原小市值参数(USE_G6=False 时生效) ----
PB_TOP = 0.50
ROEINC_TOP = 0.10
SMALL_W_MC = 0.60
SMALL_W_AMT = 0.40
MIN_LIST_DAYS = 250

# ---- 红利低波 ----
DIV_MIN = 1.5
DIV_TOP = 0.30
MKT_MIN = 3e9

# ---- 估值择时 ----
USE_VAL_TIMING = True
VAL_LOOKBACK = 250
VAL_THRESHOLD = 0.95
VAL_FLOOR = 0.50

# ---- 拥挤度动态调权 ----
USE_CROWD_W = True
CROWD_HI = 0.70
CROWD_LO = 0.30
W_CROWD_HI = (0.50, 0.25, 0.25)
W_CROWD_LO = (0.25, 0.30, 0.45)

# ---- 恐慌期加杠杆 ----
USE_PANIC_LEV = True
PANIC_DD = 40.0
PANIC_LEV = 1.5
FIN_RATE = 0.06

# ---- 交易成本 / 撮合(与 all03 一致) ----
weight_cash_buffer = 0.95
stock_min_commission = 5
stock_commission_multiplier = 2.5
tax_multiplier = 1
pit_tax = False
volume_limit = True
volume_percent = 0.25
inactive_limit = True
# ===================================================

HERE = os.path.dirname(os.path.abspath(__file__))
ALL01 = os.path.join(os.path.dirname(HERE), 'all01')
SNAP_PATH = os.path.join(ALL01, 'factor_snapshot.pkl')   # 与 all01/all03 共用(344MB)
G6_PATH = os.path.join(HERE, 'g6_daily.pkl')
REGIME_PATH = os.path.join(HERE, 'market_regime.csv')
CROWD_PATH = os.path.join(HERE, 'turnover_pctile.csv')
CSI300_H5 = r'E:\rq\constituents\index\000300.XSHG.h5'


def to_int_date(v, default):
    s = str(v)
    if s in ('nan', 'NaT', 'None', ''):
        return default
    s = s.replace('-', '').replace('/', '')[:8]
    try:
        return int(s)
    except ValueError:
        return default


def blocked_stock(s, include_gem=True):
    if s.startswith('688') or s.startswith('689'):
        return True
    if s.startswith('8') or s.startswith('4') or s.startswith('920'):
        return True
    if not include_gem and s.startswith('30'):
        return True
    return False


def load_csi300_history():
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


def build_pb_percentile():
    snap = pd.read_pickle(SNAP_PATH)
    med = snap.groupby('date')['pb'].median()
    pct = med.rolling(VAL_LOOKBACK, min_periods=VAL_LOOKBACK // 2).rank(pct=True)
    return {int(k): v for k, v in pct.items()}


t = time.time()


def init(context):
    from rqalpha.utils.logger import user_log
    from logbook import StderrHandler
    user_log.handlers = [StderrHandler(
        format_string='{record.time:%Y-%m-%d %H:%M:%S} - {record.level_name}  -  {record.message}',
        bubble=False)]

    snap = pd.read_pickle(SNAP_PATH)
    context.snap = {int(k): v for k, v in snap.groupby('date')}
    context.pb_pct = build_pb_percentile()
    context.csi300_hist = load_csi300_history()

    # ---- combo_g6 日频面板(交易日 x 股票), 三口径 ----
    # 注意: 'g6filt' 池把 g6 当筛选器, 此时即使 USE_G6=False(排序用原版)也要加载
    if USE_G6 or SMALL_POOL == 'g6filt':
        g6 = pd.read_pickle(G6_PATH)
        context.g6 = g6
        context.g6_dates = g6['raw'].index.values
        context.g6_cols = list(g6['raw'].columns)
        context.g6_modes = [G6_MODE] + [m for m in ['barra', 'lnmc', 'raw']
                                        if m != G6_MODE]
        logger.info(f"combo_g6 已加载: {len(context.g6_dates)} 日 x "
                    f"{len(context.g6_cols)} 股, 口径顺序 {context.g6_modes}")

    ins = all_instruments(type='CS')
    ins = ins[['order_book_id', 'listed_date', 'de_listed_date']].copy()
    ins['listed'] = [to_int_date(v, 19000101) for v in ins['listed_date']]
    ins['delisted'] = [to_int_date(v, 99999999) for v in ins['de_listed_date']]
    context.ins = ins.set_index('order_book_id')

    _w = np.array([W_SMALL, W_WHITE, W_DIV], dtype=float)
    context.ws = _w / _w.sum()
    if USE_CROWD_W:
        _cw = pd.read_csv(CROWD_PATH)
        context.crowd = dict(zip(_cw['date'].astype(int),
                                 _cw['top10_pctile_10y'].astype(float)))
        context.crowd_dates = sorted(context.crowd.keys())
    context.small, context.white, context.div = [], [], []
    context.last_month = None

    scheduler.run_weekly(rebalance, tradingday=1)


def handle_bar(context, bar_dict):
    pass


def g6_row(context, d):
    """取 T-1 日(盘中不可知当日公告)的 g6 行; 优先 G6_MODE, 缺数据按序回退"""
    i = int(np.searchsorted(context.g6_dates, d, 'left')) - 1   # T-1
    if i < 0:
        return None
    for m in context.g6_modes:
        v = context.g6[m].values[i]
        if np.isfinite(v).sum() > 100:
            return pd.Series(v, index=context.g6_cols, name=context.g6_dates[i])
    return None


def _tradable(context, bar_dict, df, ok, use_limit_up=True):
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
        if use_limit_up:
            lu = getattr(bar, 'limit_up', None)
            if lu and px >= lu - 1e-6:
                continue
        rows.append(s)
    return rows


def _base_pool(context, df, bar_dict):
    """剔ST/停牌/新股/科创北交/涨停 -> 返回过滤后的 df"""
    d = int(context.now.strftime('%Y%m%d'))
    ins = context.ins
    alive = ins[(ins['listed'] <= d) & (ins['delisted'] >= d)].index
    cutoff = int((context.now - pd.Timedelta(days=MIN_LIST_DAYS)).strftime('%Y%m%d'))
    ok = set(s for s in alive if ins.at[s, 'listed'] <= cutoff)
    ok = set(s for s in ok if not blocked_stock(s, True))
    keep = _tradable(context, bar_dict, df, ok)
    return df[df['obid'].isin(keep)]


def pick_small(context, bar_dict):
    d = int(context.now.strftime('%Y%m%d'))
    df = context.snap.get(d)
    if df is None or df.empty:
        return []
    df = _base_pool(context, df, bar_dict)
    if df.empty:
        return []
    df = df[(df['pb'] > 0) & (df['eps'] > 0)]

    # ===== 候选池定义 =====
    if SMALL_POOL == 'mc30':        # 纯小市值池(贴合 Round7 研究口径)
        df = df.dropna(subset=['mktcap']).sort_values('mktcap')
        df = df.head(max(int(len(df) * SMALL_MC_TOP), N_SMALL))
    elif SMALL_POOL == 'g6filt':    # PB前50% -> 【g6 前 G6_FILT_TOP】当筛选器
        df = df.sort_values('pb').head(max(int(len(df) * PB_TOP), N_SMALL))
        row = g6_row(context, d)
        if row is not None:
            g = row.reindex(df['obid'].values)
            df = df.assign(g6=g.values).dropna(subset=['g6'])
            df = df.sort_values('g6', ascending=False)
            df = df.head(max(int(len(df) * G6_FILT_TOP), N_SMALL))
    else:                           # 'all03': 沿用 all03 精选池(PB前50% -> ROE环比前10%)
        df = df.sort_values('pb').head(max(int(len(df) * PB_TOP), N_SMALL))
        df = df.dropna(subset=['roe_inc']).sort_values('roe_inc', ascending=False)
        df = df.head(max(int(len(df) * ROEINC_TOP), N_SMALL))
    if df.empty:
        return []

    # ===== 池内排序因子 =====
    if USE_G6:
        row = g6_row(context, d)
        if row is None:
            return list(df['obid'].head(N_SMALL))
        g = row.reindex(df['obid'].values)
        df = df.assign(g6=g.values).dropna(subset=['g6'])
        df = df.sort_values('g6', ascending=False)
        return list(df['obid'].head(N_SMALL))

    # all03 原排序: 总市值60% + 成交额40%
    df = df.dropna(subset=['mktcap', 'volume', 'close']).copy()
    amt = (df['volume'] * df['close']).replace(0, np.nan)
    df['r_mc'] = df['mktcap'].rank(pct=True)
    df['r_amt'] = np.log(amt).rank(pct=True)
    df['score'] = SMALL_W_MC * df['r_mc'] + SMALL_W_AMT * df['r_amt']
    df = df.sort_values('score')
    return list(df['obid'].head(N_SMALL))


def pick_div(context, bar_dict):
    d = int(context.now.strftime('%Y%m%d'))
    df = context.snap.get(d)
    if df is None or df.empty:
        return []
    df = _base_pool(context, df, bar_dict)
    if df.empty:
        return []
    df = df[(df['div_yield'] >= DIV_MIN) & (df['mktcap'] >= MKT_MIN)]
    df = df.sort_values('div_yield', ascending=False)
    df = df.head(max(int(len(df) * DIV_TOP), N_DIV))
    df = df.dropna(subset=['vol60']).sort_values('vol60')
    return list(df['obid'].head(N_DIV))


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


def pick_white(context, bar_dict):
    d = int(context.now.strftime('%Y%m%d'))
    df = context.snap.get(d)
    if df is None or df.empty:
        return []
    members = None
    for eff, m in context.csi300_hist:
        if eff <= d:
            members = m
        else:
            break
    if not members:
        return []
    ins = context.ins
    alive = ins[(ins['listed'] <= d) & (ins['delisted'] >= d)].index
    ok = set(s for s in members & set(alive)
             if not s.startswith('30') and not s.startswith('68')
             and not s.startswith('8') and not s.startswith('4'))
    keep = []
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
        keep.append(s)
    df = df[df['obid'].isin(keep)]
    if df.empty:
        return []

    temp = market_temperature(context)
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
    return list(df['obid'].head(N_WHITE))


def target_position_coef(context):
    if not USE_VAL_TIMING:
        return 1.0
    d = int(context.now.strftime('%Y%m%d'))
    pct = context.pb_pct.get(d, np.nan)
    if np.isnan(pct):
        return 1.0
    return VAL_FLOOR if pct >= VAL_THRESHOLD else 1.0


def crowd_weights(context, d):
    base = context.ws
    if not USE_CROWD_W:
        return base
    i = bisect.bisect_left(context.crowd_dates, d) - 1
    if i < 0:
        return base
    pct = context.crowd[context.crowd_dates[i]]
    if np.isnan(pct):
        return base
    if pct >= CROWD_HI:
        w = np.array(W_CROWD_HI, dtype=float)
    elif pct <= CROWD_LO:
        w = np.array(W_CROWD_LO, dtype=float)
    else:
        w = base
    return w / w.sum()


def rebalance(context, bar_dict):
    d = int(context.now.strftime('%Y%m%d'))
    m = context.now.strftime('%Y%m')

    context.small = pick_small(context, bar_dict)
    if context.last_month != m:
        context.white = pick_white(context, bar_dict)
        context.div = pick_div(context, bar_dict)
        context.last_month = m

    coef = target_position_coef(context) * weight_cash_buffer
    r3 = crowd_weights(context, d)
    ws = np.asarray(r3)
    pools = [context.small, context.white, context.div]

    target = {}
    for pool, w in zip(pools, ws):
        if not pool:
            continue
        each = w / len(pool) * coef
        for s in pool:
            target[s] = target.get(s, 0.0) + each
    if not target:
        return

    for p in get_positions():
        if p.order_book_id not in target:
            order_target_value(p.order_book_id, 0)
    for s, w in target.items():
        order_target_percent(s, w)

    wstr = "/".join(f"{x:.0%}" for x in ws)
    logger.info(f"{d} [仓位{coef/weight_cash_buffer:.0%} 权重{wstr}] "
                f"小市值{len(context.small)} 白马{len(context.white)} "
                f"红利{len(context.div)} -> 持仓{len(target)}只")


# ===================== 恐慌期加杠杆(回测后处理) =====================
def apply_panic_leverage(nv, dd_hi=PANIC_DD, lev_v=PANIC_LEV, rate=FIN_RATE):
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
        if a == '--no-g6':
            USE_G6 = False
        elif a.startswith('--mode='):
            G6_MODE = a[7:]
        elif a.startswith('--pool='):
            SMALL_POOL = a[7:]
        elif a.startswith('--mctop='):
            SMALL_MC_TOP = float(a[8:])
        elif a.startswith('--gfilt='):
            G6_FILT_TOP = float(a[8:])

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
    curves = {'all04 无杠杆': nv}
    if USE_PANIC_LEV:
        net, n_days = apply_panic_leverage(nv)
        curves['all04 +恐慌杠杆1.5x'] = net
        print(f"(超跌股占比>={PANIC_DD:.0f}% 触发 {n_days} 个交易日, 融资利率 {FIN_RATE:.0%})")

    pool_desc = {'all03': 'all03精选池(PB前%.0f%%->ROE环比前%.0f%%)'
                          % (PB_TOP * 100, ROEINC_TOP * 100),
                 'mc30': '总市值最小前%.0f%%' % (SMALL_MC_TOP * 100),
                 'g6filt': 'PB前%.0f%%->g6前%.0f%%' % (PB_TOP * 100, G6_FILT_TOP * 100),
                 }.get(SMALL_POOL, SMALL_POOL)
    rank_desc = ('combo_g6(%s口径)降序' % G6_MODE if USE_G6
                 else 'all03原版(市值%.0f%%+成交额%.0f%%)'
                      % (SMALL_W_MC * 100, SMALL_W_AMT * 100))
    tag = f"小市值选股: 池={pool_desc}  排序={rank_desc}"
    finish(__file__, start_date, end_date, output_path + ".pkl",
           curves=curves, bench=bench,
           title='all04 = all03 + 小市值池内 combo_g6 选股', extra_tag=tag)

    final = net if USE_PANIC_LEV else nv
    print("\n年度:     收益率     年内回撤")
    for y, g in final.groupby(final.index.year):
        print(f"  {y}    {(g.iloc[-1]/g.iloc[0]-1)*100:7.2f}%   "
              f"{(g/g.cummax()-1).min()*100:7.2f}%")
