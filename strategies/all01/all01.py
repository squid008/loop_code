# -*- coding: utf-8 -*-
"""
最优组合策略(单账户一体化, 一键运行)
================================================================
三策略等权 + 估值择时 + 恐慌期加杠杆

[A] 小市值(周频): 剔ST/停牌/涨停/科创/北交 -> PB最小前50%
                  -> ROE环比增长前10% -> 流通市值升序取10只
[B] 白马攻防(月频): 沪深300成分(历史真实名单), 按市场温度(cold/warm/hot)
                  切换财务条件, 取5只
[C] 红利低波(月频): 股息率>=1.5% 且 市值>=30亿 -> 股息率前30%
                  -> 60日波动升序取10只

组合: A/B/C 各 1/3, 每周调仓(内部等权, 月内自然漂移)
择时: 全市场中位PB 的250日滚动分位 >= 95% -> 总仓位降至 50%
杠杆: "超跌股占比" >= 40% 的恐慌期 -> 1.5倍杠杆(融资利率6%年化)
      用 T-1 日信号作用于 T 日, 无未来函数

无未来函数保证:
  - 财务因子来自 factor_snapshot.pkl, 按【公告日】对齐(PIT)
  - 沪深300用历史成分名单, 调仓日取 <=T 的最近一批
  - 调仓在盘中按当日价成交, 因子用前一日快照

运行: python all01.py
"""
import os
import sys
import time
import bisect
import pickle
import glob
from datetime import datetime
import numpy as np
import pandas as pd

from rqalpha import run_func

# ===================== 策略参数 =====================
start_date = "2014-10-01"
end_date = "2026-08-05"

# ---- 三个子策略的权重(自动归一化) ----
W_SMALL, W_WHITE, W_DIV = 1.0, 1.0, 1.0
N_SMALL, N_WHITE, N_DIV = 10, 5, 10

# ---- 卫星仓: 科创板+创业板科技龙头(688/300/301 市值最大) ----
# 历史检验: 该池2019-2026年化18.27%(基准中证1000仅7.17%), 2020+106%/2025+69%,
#           但单独持有回撤-59%, 故作为卫星小仓位博弹性, 0 表示关闭
W_TECH = 0.0          # 建议 0.12~0.20, 0=关闭
N_TECH = 20

# ---- 小市值参数 ----
PB_TOP = 0.50
ROEINC_TOP = 0.10
MIN_LIST_DAYS = 250      # 新股过滤

# ---- 红利低波参数 ----
DIV_MIN = 1.5            # 股息率下限(%)
DIV_TOP = 0.30
MKT_MIN = 3e9            # 市值下限30亿

# ---- 估值择时 ----
USE_VAL_TIMING = True
VAL_LOOKBACK = 250       # 滚动分位窗口(交易日)
VAL_THRESHOLD = 0.95     # 分位>=95% 视为高估
VAL_FLOOR = 0.50         # 高估时总仓位降至 50%

# ---- 拥挤度动态调权 ----
# 依据: Top10%成交额占比的10年分位越高, 资金越抱团于小盘/题材,
#       未来60日中证1000跑赢沪深300概率59%、价差+5.89%(历史检验)
USE_CROWD_W = True
CROWD_HI = 0.70          # 分位>=70%: 高拥挤, 小市值加码
CROWD_LO = 0.30          # 分位<=30%: 低拥挤, 红利防御
W_CROWD_HI = (0.50, 0.25, 0.25)   # (小市值, 白马, 红利)
W_CROWD_LO = (0.25, 0.30, 0.45)

# ---- 恐慌期加杠杆 ----
USE_PANIC_LEV = True
PANIC_DD = 40.0          # 超跌股占比阈值(%)
PANIC_LEV = 1.5          # 杠杆倍数
FIN_RATE = 0.06          # 融资年利率

# ---- 交易成本 / 撮合 ----
weight_cash_buffer = 0.95
stock_min_commission = 5
stock_commission_multiplier = 2.5      # 万八 x2.5 = 单边千二(含滑点)
tax_multiplier = 1
pit_tax = False
volume_limit = True
volume_percent = 0.25
inactive_limit = True
# ===================================================

HERE = os.path.dirname(os.path.abspath(__file__))
SNAP_PATH = os.path.join(HERE, 'factor_snapshot.pkl')
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
    """板块过滤: 科创板/北交所必剔; 创业板可选"""
    if s.startswith('688') or s.startswith('689'):
        return True
    if s.startswith('8') or s.startswith('4') or s.startswith('920'):
        return True
    if not include_gem and s.startswith('30'):
        return True
    return False


def load_csi300_history():
    """返回 [(生效日int, set(成分))] 升序"""
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
    """全市场中位PB的250日滚动分位 -> {int日期: 分位}"""
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
        logger.info(f"拥挤度指标已加载: {len(context.crowd)} 日 "
                    f"{context.crowd_dates[0]}~{context.crowd_dates[-1]}")
    context.small, context.white, context.div, context.tech = [], [], [], []
    context.last_month = None

    scheduler.run_weekly(rebalance, tradingday=1)


def handle_bar(context, bar_dict):
    pass


def _tradable(context, bar_dict, df, ok, use_limit_up=True):
    """ST/停牌/涨停过滤, 返回过滤后的 obid 列表"""
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


def pick_small(context, bar_dict):
    d = int(context.now.strftime('%Y%m%d'))
    df = context.snap.get(d)
    if df is None:
        return []
    ins = context.ins
    alive = ins[(ins['listed'] <= d) & (ins['delisted'] >= d)].index
    cutoff = int((context.now - pd.Timedelta(days=MIN_LIST_DAYS)).strftime('%Y%m%d'))
    ok = set(s for s in alive if ins.at[s, 'listed'] <= cutoff)
    ok = set(s for s in ok if not blocked_stock(s, True))
    keep = _tradable(context, bar_dict, df, ok)
    df = df[df['obid'].isin(keep)]
    if df.empty:
        return []
    df = df[(df['pb'] > 0) & (df['eps'] > 0)]
    df = df.sort_values('pb').head(max(int(len(df) * PB_TOP), N_SMALL))
    df = df.dropna(subset=['roe_inc']).sort_values('roe_inc', ascending=False)
    df = df.head(max(int(len(df) * ROEINC_TOP), N_SMALL))
    df = df.dropna(subset=['circ_mktcap']).sort_values('circ_mktcap')
    return list(df['obid'].head(N_SMALL))


def pick_div(context, bar_dict):
    d = int(context.now.strftime('%Y%m%d'))
    df = context.snap.get(d)
    if df is None:
        return []
    ins = context.ins
    alive = ins[(ins['listed'] <= d) & (ins['delisted'] >= d)].index
    cutoff = int((context.now - pd.Timedelta(days=MIN_LIST_DAYS)).strftime('%Y%m%d'))
    ok = set(s for s in alive if ins.at[s, 'listed'] <= cutoff)
    ok = set(s for s in ok if not blocked_stock(s, True))
    keep = _tradable(context, bar_dict, df, ok)
    df = df[df['obid'].isin(keep)]
    if df.empty:
        return []
    df = df[(df['div_yield'] >= DIV_MIN) & (df['mktcap'] >= MKT_MIN)]
    df = df.sort_values('div_yield', ascending=False)
    df = df.head(max(int(len(df) * DIV_TOP), N_DIV))
    df = df.dropna(subset=['vol60']).sort_values('vol60')
    return list(df['obid'].head(N_DIV))


def pick_tech(context, bar_dict):
    """科创板+创业板(688/300/301)市值最大的 N 只 = 科技龙头"""
    d = int(context.now.strftime('%Y%m%d'))
    df = context.snap.get(d)
    if df is None:
        return []
    ins = context.ins
    alive = ins[(ins['listed'] <= d) & (ins['delisted'] >= d)].index
    cutoff = int((context.now - pd.Timedelta(days=MIN_LIST_DAYS)).strftime('%Y%m%d'))
    ok = set(s for s in alive
             if (s.startswith('688') or s.startswith('689') or s.startswith('30'))
             and ins.at[s, 'listed'] <= cutoff)
    keep = _tradable(context, bar_dict, df, ok)
    df = df[df['obid'].isin(keep)]
    if df.empty:
        return []
    df = df.dropna(subset=['mktcap']).sort_values('mktcap', ascending=False)
    return list(df['obid'].head(N_TECH))


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
    if df is None:
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
    keep = _tradable(context, bar_dict, df, ok)
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
    context.temp = temp
    return list(df['obid'].head(N_WHITE))


def target_position_coef(context):
    """估值择时: 全市场中位PB 250日分位 >= 95% -> 仓位降至 VAL_FLOOR"""
    if not USE_VAL_TIMING:
        return 1.0
    d = int(context.now.strftime('%Y%m%d'))
    pct = context.pb_pct.get(d, np.nan)
    if np.isnan(pct):
        return 1.0
    return VAL_FLOOR if pct >= VAL_THRESHOLD else 1.0


def crowd_weights(context, d):
    """按拥挤度历史分位决定三策略权重; 用 T 日之前最后交易日的分位(盘中不可得T日值)"""
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
        if W_TECH > 0:
            context.tech = pick_tech(context, bar_dict)
        context.last_month = m

    coef = target_position_coef(context) * weight_cash_buffer
    r3 = crowd_weights(context, d)                  # 三主力内部比例(和为1)
    if W_TECH > 0 and context.tech:
        rest = 1.0 - W_TECH
        ws = np.array([r3[0] * rest, r3[1] * rest, r3[2] * rest, W_TECH])
        pools = [context.small, context.white, context.div, context.tech]
    else:
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
                f"红利{len(context.div)}"
                + (f" 科技{len(context.tech)}" if W_TECH > 0 else "")
                + f" -> 持仓{len(target)}只")


# ===================== 恐慌期加杠杆(回测后处理) =====================
def apply_panic_leverage(nv, dd_hi=PANIC_DD, lev_v=PANIC_LEV, rate=FIN_RATE):
    """用 T-1 日超跌信号作用于 T 日; 借入部分按日计息"""
    rg = pd.read_csv(REGIME_PATH, index_col=0)
    rg.index = pd.to_datetime(rg.index)
    dd = rg['dd25'].reindex(rg.index.union(nv.index)).ffill().loc[nv.index]
    lev = pd.Series(1.0, index=nv.index)
    lev[dd >= dd_hi] = lev_v
    lev_lag = lev.shift(1).fillna(1.0)
    r = nv.pct_change().fillna(0.0)
    net = (1 + r * lev_lag - (lev_lag - 1.0) * rate / 252).cumprod()
    net = net / net.iloc[0]
    return net, int((lev > 1.0).sum())


def stats(nv, bench=None):
    r = nv.pct_change()
    years = (nv.index[-1] - nv.index[0]).days / 365.25
    ann = nv.iloc[-1] ** (1 / years) - 1
    dd = (nv / nv.cummax() - 1).min()
    sharpe = r.mean() / r.std() * np.sqrt(252) if r.std() > 0 else np.nan
    return ann, dd, sharpe, (ann / abs(dd) if dd < 0 else np.nan)


def load_results(path_pkl):
    with open(path_pkl, 'rb') as f:
        res = pickle.load(f)
    pf = res['portfolio']
    nv = (pf['unit_net_value'] if 'unit_net_value' in pf.columns
          else pf['total_value'] / pf['total_value'].iloc[0])
    bp = res['benchmark_portfolio']
    bench = (bp['unit_net_value'] if 'unit_net_value' in bp.columns
             else bp['total_value'] / bp['total_value'].iloc[0])
    return nv, bench


def plot_curves(nv, net, bench, path):
    """净值曲线(对数) + 回撤填充, 保存为 png"""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False

    a0, d0, s0, _ = stats(nv)
    ab, db, _, _ = stats(bench)
    fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=True,
                             gridspec_kw={'height_ratios': [3, 1]})
    ax = axes[0]
    ax.plot(nv.index, nv.values, lw=1.3, color='#1f77b4',
            label=u'组合+择时(无杠杆)  年化%.2f%%  回撤%.1f%%' % (a0 * 100, d0 * 100))
    if net is not None:
        a1, d1, s1, _ = stats(net)
        ax.plot(net.index, net.values, lw=1.3, color='#d62728',
                label=u'+恐慌杠杆%.1fx  年化%.2f%%  回撤%.1f%%'
                      % (PANIC_LEV, a1 * 100, d1 * 100))
    ax.plot(bench.index, bench.values, lw=1.1, color='#7f7f7f', alpha=0.85,
            label=u'沪深300  年化%.2f%%  回撤%.1f%%' % (ab * 100, db * 100))
    ax.set_yscale('log')
    ax.set_ylabel(u'净值(对数坐标)')
    ax.set_title(u'最优组合策略: 小市值1/3 + 白马1/3 + 红利低波1/3', fontsize=13)
    ax.legend(loc='upper left', fontsize=9)
    ax.grid(alpha=0.3)

    fin = net if net is not None else nv
    dser = (fin / fin.cummax() - 1) * 100
    axes[1].fill_between(dser.index, dser.values, 0, color='#d62728', alpha=0.35)
    axes[1].set_ylabel(u'回撤 %')
    axes[1].grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


STEM = os.path.splitext(os.path.basename(os.path.abspath(__file__)))[0]
SD = start_date.replace('-', '')
ED = end_date.replace('-', '')


def run_basename():
    """产物命名: 策略名_回测时间戳_开始日_结束日
    时间戳前置, 使同一策略的多次回测按文件名排序即为时间先后
    例: all01_20260905_1833_45_20141001_20260805
    """
    return f"{STEM}_{datetime.now().strftime('%Y%m%d_%H%M_%S')}_{SD}_{ED}"


def latest_result():
    """--plot-only 时取出最近一次回测产物(不含扩展名), 没有则返回 None"""
    import glob
    fs = sorted(glob.glob(os.path.join(HERE, f"{STEM}_*_{SD}_{ED}.pkl")))
    return fs[-1][:-4] if fs else None


if __name__ == '__main__':
    for a in sys.argv[1:]:
        if a.startswith('--tech='):        # 卫星仓权重, 如 --tech=0.15
            W_TECH = float(a[7:])
        elif a.startswith('--ntech='):
            N_TECH = int(a[8:])
    if '--plot-only' in sys.argv:
        output_path = latest_result()
        if output_path is None:
            print(f"未找到历史产物 {STEM}_{SD}_{ED}_*.pkl, 请先运行: python {STEM}.py")
            sys.exit(1)
        print(f"[plot-only] 读取: {os.path.basename(output_path)}.pkl")
    else:
        output_path = os.path.join(HERE, run_basename())
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
    if '--plot-only' not in sys.argv:
        run_func(init=init, handle_bar=handle_bar, config=__config__)
        print(f"\n回测运行时间: {time.time() - t:.1f} 秒")

    nv, bench = load_results(output_path + ".pkl")
    net = None

    print("=" * 78)
    print("最终组合: 小市值 + 白马 + 红利低波"
          + (f" + 科技龙头卫星{W_TECH:.0%}(科创创业市值TOP{N_TECH})" if W_TECH > 0 else ""))
    if USE_CROWD_W:
        print(f"  拥挤度调权: 成交额Top10%占比10年分位 >={CROWD_HI:.0%} -> "
              f"小市值{W_CROWD_HI[0]:.0%}/红利{W_CROWD_HI[2]:.0%} | "
              f"<={CROWD_LO:.0%} -> 小市值{W_CROWD_LO[0]:.0%}/红利{W_CROWD_LO[2]:.0%}")
    else:
        print("  权重: 三者固定等权")
    if USE_VAL_TIMING:
        print(f"  估值择时: 全市场中位PB {VAL_LOOKBACK}日分位>={VAL_THRESHOLD:.0%}"
              f" -> 仓位降至{VAL_FLOOR:.0%}")
    print("=" * 78)

    a0, d0, s0, c0 = stats(nv)
    print(f"  [组合+择时, 无杠杆]  年化 {a0*100:6.2f}%   回撤 {d0*100:7.2f}%   "
          f"Sharpe {s0:5.3f}   Calmar {c0:5.3f}")

    if USE_PANIC_LEV:
        net, n_days = apply_panic_leverage(nv)
        a1, d1, s1, c1 = stats(net)
        print(f"  [+恐慌杠杆 {PANIC_LEV}x]     年化 {a1*100:6.2f}%   回撤 {d1*100:7.2f}%   "
              f"Sharpe {s1:5.3f}   Calmar {c1:5.3f}")
        print(f"  (超跌股占比>={PANIC_DD:.0f}% 触发 {n_days} 个交易日, 融资利率 {FIN_RATE:.0%})")

    ab, db, sb, cb = stats(bench)
    print(f"  [基准 沪深300]        年化 {ab*100:6.2f}%   回撤 {db*100:7.2f}%   "
          f"Sharpe {sb:5.3f}   Calmar {cb:5.3f}")

    final = net if USE_PANIC_LEV else nv
    print("\n年度:     收益率     年内回撤")
    for y, g in final.groupby(final.index.year):
        print(f"  {y}    {(g.iloc[-1]/g.iloc[0]-1)*100:7.2f}%   {(g/g.cummax()-1).min()*100:7.2f}%")

    plot_curves(nv, net, bench, output_path + "_final.png")

    print("\n产物文件:")
    for f in [output_path + ".pkl", output_path + ".png", output_path + "_final.png"]:
        print(f"  {os.path.basename(f)}" + ("" if os.path.exists(f) else "  (缺失)"))
    print("=" * 78)
