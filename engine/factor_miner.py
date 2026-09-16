# -*- coding: utf-8 -*-
"""
因子挖掘框架(参照中金 Loop Engineering 简化版)
================================================
闭环: 生成(A) -> 审查(B) -> 验证(硬编码)
验证标准(中金11项简化):
  1. |IC| > 0.02
  2. IC胜率 > 50%
  3. 各年度超额 > 0 (年度稳定性)
  4. 近1年超额 > 0
  5. Calmar > 0.5
  6. 与已入库因子 IC相关性 < 0.70 (独立性)
换仓: 5日    成本: 单边千一    分组: 10组, Top组多头
"""
import os
import json
import time
import warnings
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

warnings.filterwarnings('ignore')

HERE = os.path.dirname(os.path.abspath(__file__))
PANEL = os.path.join(HERE, 'panel.h5')
LIB = os.path.join(HERE, 'factor_lib.json')
UNIVERSE = os.path.join(HERE, 'universe.h5')

_UNIV = None


def get_universe():
    """可交易股票池掩码(date x stock, bool)"""
    global _UNIV
    if _UNIV is None:
        with pd.HDFStore(UNIVERSE, 'r') as st:
            _UNIV = st['universe']
    return _UNIV

FWD = 5            # 持有期(交易日)
N_GRP = 10         # 分组数
COST = 0.001       # 单边成本
START = 20180101   # 检验区间


def set_fwd(n):
    """设置换仓周期(交易日): 1=日频 5=周频 20=月频"""
    global FWD
    FWD = int(n)
    return FWD


# ===================== 算子 =====================
def ts_mean(df, w): return df.rolling(w, min_periods=max(2, w // 2)).mean()
def ts_std(df, w): return df.rolling(w, min_periods=max(2, w // 2)).std()
def ts_sum(df, w): return df.rolling(w, min_periods=max(2, w // 2)).sum()
def ts_max(df, w): return df.rolling(w, min_periods=max(2, w // 2)).max()
def ts_min(df, w): return df.rolling(w, min_periods=max(2, w // 2)).min()


def ts_pos(df, w):
    """当前值在过去w日区间中的相对位置 0~1 (快, 替代 ts_rank)"""
    mn = ts_min(df, w)
    mx = ts_max(df, w)
    return (df - mn) / (mx - mn + 1e-12)


def ts_decay(df, w):
    """线性衰减加权均值(近期权重高)"""
    wt = np.arange(1, w + 1, dtype=np.float64)
    wt /= wt.sum()
    return df.rolling(w, min_periods=max(2, w // 2)).apply(
        lambda x: np.dot(x, wt[-len(x):] / wt[-len(x):].sum()), raw=True)


def ts_corr(x, y, w):
    return x.rolling(w, min_periods=max(3, w // 2)).corr(y)


def ts_delay(df, n): return df.shift(n)
def ts_delta(df, n): return df - df.shift(n)


def cs_rank(df):
    """截面排名 0~1"""
    return df.rank(axis=1, pct=True)


def cs_zscore(df):
    mu = df.mean(axis=1)
    sd = df.std(axis=1)
    return df.sub(mu, axis=0).div(sd + 1e-12, axis=0)


def cs_demean(df):
    return df.sub(df.mean(axis=1), axis=0)


# ===================== 数据 =====================
def load_panel(fields=None):
    with pd.HDFStore(PANEL, 'r') as st:
        keys = fields or [k.strip('/') for k in st.keys()]
        P = {k: st[k] for k in keys}
    return P


def prepare(P):
    """计算衍生基础字段"""
    close = P['close'].astype('float64')
    P['ret'] = close.pct_change()
    P['open'] = P['open'].astype('float64')
    P['high'] = P['high'].astype('float64')
    P['low'] = P['low'].astype('float64')
    P['volume'] = P['volume'].astype('float64')
    P['turnover'] = P['turnover'].astype('float64')
    P['close'] = close
    P['prev_close'] = close.shift(1)
    # 换手率(成交额/市值)
    mc = P.get('mktcap')
    if mc is not None:
        mc = mc.astype('float64').reindex_like(close)
        P['mktcap'] = mc
        P['turn_ratio'] = P['turnover'] / (mc + 1e-12)
    P['vwap'] = P['turnover'] / (P['volume'] + 1e-12)
    return P


# ===================== 可实现性(贴近实盘) =====================
# 成本档位已抽到 cost_presets.py（单一事实源, 2026-09-11）；此处仅转出以兼容既有引用。
# 语义: 均为「往返成本」, 扣在「单向换手率」上; 构成见 engine/cost_presets.py 顶部注释。
from cost_presets import COST_PRESETS, COST_RT   # noqa: E402  (转出, 勿在此再定义)
_TRADE = None


def get_tradability():
    """一次性预计算可交易性矩阵(缓存)
    buyable[t,s]  : t 日能否买入(非涨停/非停牌/有价)
    next_sell[t,s]: t 日(含)起第一个能卖出的交易日索引(跌停/停牌则顺延)
    """
    global _TRADE
    if _TRADE is not None:
        return _TRADE
    with pd.HDFStore(PANEL, 'r') as st:
        keys = [k.strip('/') for k in st.keys()]
        need = ['close', 'limit_up', 'limit_down', 'turnover']
        miss = [k for k in need if k not in keys]
        if miss:
            raise KeyError(f"panel.h5 缺少 {miss}, 无法实现可实现性约束")
        P = {k: st[k] for k in need}
    close = P['close'].astype('float64')
    cv = close.values
    T, S = cv.shape
    vol = P['turnover'].astype('float64').values
    lu = P['limit_up'].astype('float64').values
    ld = P['limit_down'].astype('float64').values
    bad = ~(np.isfinite(cv) & (cv > 0)) | ~(vol > 0)      # 停牌/无数据
    up = np.isfinite(lu) & (cv >= lu - 1e-6)              # 涨停: 买不进
    dn = np.isfinite(ld) & (cv <= ld + 1e-6)              # 跌停: 卖不出
    buyable = (~up) & (~bad)
    sellable = (~dn) & (~bad)
    big = T - 1
    b = np.where(sellable, np.arange(T)[:, None], big)
    # next_sell[t] = min{t' >= t : sellable[t']}  (反向 minimum accumulate)
    next_sell = np.minimum.accumulate(b[::-1], axis=0)[::-1].astype(np.int32)
    _TRADE = dict(dates=close.index.values, cols=list(close.columns),
                  close=cv, buyable=buyable, next_sell=next_sell)
    return _TRADE


def evaluate_real(fac, close, name='', cost=COST_RT, cash=1.0, verbose=False,
                  window='full', with_ex=False, mcap=None, with_daily=False):
    """【可实现性版检验(费后)】与 evaluate() 的差别:
      1. T+1 买入日: 剔除涨停/停牌 -> 买不进的不算
      2. 卖出日: 跌停/停牌则顺延到下一个可卖日(实盘卖不出的真实处理)
      3. 成本: 按实际换手率 x 往返成本(默认0.5% = 佣金千二双边 + 印花税千一)
      4. cash: 仓位现金比例(等权时为1.0; 若策略留5%现金, 传0.95)
      5. window: 'full'=START(2018)起九年口径; 'recent600'=最近600交易日
         (对齐中金研报口径: 回测只用最近600日, 过滤只要求最近2年正)
      6. with_ex: 默认False(行为/返回结构完全不变); True时额外返回 'ex'=
          费后日度超额序列(每换仓期一条), 供上层做【分段独立验证】——
          把该序列按时间均分成K个不相交子区间, 各段须方向同号稳定。
      7. mcap: 默认None(行为完全不变)。给**市值面板**((T x N), 与 close 同轴)时, 额外返回
          **市值加权基准**下的指标('ann_ex_cw'/'dd_cw'/'calmar_cw'/'sharpe_cw')与
          'tilt' = ann_ex_cw - ann_ex。为什么(2026-09-13, roadmap §8.28):
            · **组合腿永远是"Top10% 等权"**(策略本身, 不改)；
            · 基准腿有两种口径          —— 现状 = **池内等权**(`nanmean(keep_all)`)；
              新增 = **市值加权**(≈真实指数, 沪深300 就是自由流通市值加权)；
            · 两者**同为等权**时 ⇒ 规模中性 ⇒ 差额 = **纯选股 alpha**；
              组合等权 vs 基准市值加权 ⇒ 组合**天然超配池内小盘** ⇒ 多出一块
              「**池内规模倾斜**」收益, 那不是 alpha。
            · 所以 'tilt' 就是**这块倾斜的贡献**: 它越大, 说明"超额"里越多不是选股能力
              (与 §8.13「全A超额 vs 剥风格后超额」同一逻辑, 只是从"全A 小盘"缩到"池内小盘")。
          ⚠ 成本: **零额外回测** —— 组合腿 tr 不变, 只是基准腿换个加权平均。
      8. with_daily: 默认False(行为/返回结构完全不变); True 时额外返回**日频 mark-to-market**
         的风险指标 'dd_d'/'calmar_d'/'sharpe_d'（with_ex 时另给 'ex_d' 日度超额序列）。
         为什么必须补这一口径（2026-09-14, `docs/loop_todo.md` §1.19）:
           现状 `nav_e=(1+ex).cumprod()` 而 `ex` 是**每换仓期**一条 ⇒ 净值**只在期末打点**
           ⇒ **漏掉持有期内的日内回撤** ⇒ 回撤**系统性低估 ~3.6pp**、Calmar **高估 ~1.4x**。
           实测(F10_1000): 期频 dd −7.8%/Calmar 0.891 → 日频 dd **−11.42%**/Calmar **0.627**。
         ⚠⚠ **不要用 `set_fwd(1)` 来得到日频**！那会变成「**每天调仓**」(换手 x5、成本 x5)
           ⇒ 那是**另一个策略**, 不是"同一策略的日频回撤"(方法学错误, 会既改收益又改成本)。
           **正确做法**：保持 `FWD` 调仓, 在**持有期内逐日 mark** —— 即本参数做的事
           (复用同一个 `keep_top`/`keep_all` 持仓, 只把 d1→d2 拆成逐日; **不必重新选股**) ✓
      其余(IC/分组/年度)与 evaluate 一致, 便于对照。
    """
    TR = get_tradability()
    idx_all = close.index[(close.index >= START)]
    if window == 'recent600':
        idx = idx_all[-600:]                 # 中金口径: 只看最近600交易日(~2.5年)
        if len(idx) < 300:                   # 数据不足时退回全口径
            idx = idx_all
    else:
        idx = idx_all
    fac = fac.reindex(index=idx, columns=close.columns)
    col_of = {c: j for j, c in enumerate(close.columns)}
    dates_all = close.index.values
    pos_of = {d: i for i, d in enumerate(dates_all)}
    cv = TR['close']

    U = get_universe().reindex(index=idx, columns=close.columns).fillna(False)
    fwd_ret = (close.shift(-(1 + FWD)) / close.shift(-1) - 1).reindex(index=idx)
    ics = []
    # IC 仍用(不受可实现性影响的)原始口径, 便于与历史结果对照
    fv_all, rv_all, uv_all = fac.values, fwd_ret.values, U.values
    for i in range(len(idx)):
        u = uv_all[i]
        f_ = fv_all[i][u]
        r_ = rv_all[i][u]
        m = np.isfinite(f_) & np.isfinite(r_)
        if m.sum() < 50:
            ics.append(np.nan)
            continue
        try:
            c = spearmanr(f_[m], r_[m])[0]
        except Exception:
            c = np.nan
        ics.append(c)
    ic = pd.Series(ics, index=idx)
    ic_mean = ic.mean()
    ic_ir = ic.mean() / ic.std() if ic.std() > 0 else np.nan
    ic_win = (ic > 0).sum() / ic.notna().sum() if ic.notna().sum() else np.nan

    buyable = TR['buyable']
    next_sell = TR['next_sell']
    ar = np.arange(len(close.columns))
    mc_ = None if mcap is None else np.asarray(mcap, dtype='float64')   # 市值面板(可选, 见 docstring 7)
    top_r, mkt_r, mkt_cw, dates_l, turns = [], [], [], [], []
    ex_d_parts = []          # ★ 日频超额(§1.19, with_daily 时才填): 持有期内逐日 mark
    # ★ 2026-09-16 新增「**组合自身**的日频序列」—— 起因：用户看到明细里「组合自身最大回撤 −34.7%」
    #   与「日频打点最大回撤 −13.1%」并列，直觉认为后者**不可能更浅**。
    #   ★★ 真因是**口径不同**：`dd_d` 一直是**超额**口径的日频（与 `dd` 对应），而 `dd_top` 是**组合自身**口径
    #     ⇒ 两者本来就不可比（`dd_d ≤ dd` 才是恒等式）。这里把**组合自身**的日频也补上，
    #     让「期频 vs 日频」在同一口径内可比 ⇒ 用户想问的那个数（组合日频回撤）终于有地方看 ✓
    tr_d_parts = []
    prev_top = None
    for d in idx[::FWD][:-1]:
        u = U.loc[d]
        f = fac.loc[d][u].dropna()
        if len(f) < N_GRP * 10:
            continue
        nxt = idx[idx > d]
        if len(nxt) <= FWD:
            continue
        d1, d2 = nxt[0], nxt[FWD]
        i1, i2 = pos_of[d1], pos_of[d2]
        grp = pd.qcut(f.rank(method='first'), N_GRP, labels=False)
        top = list(f.index[grp == N_GRP - 1])
        j_top = np.array([col_of[s] for s in top])
        j_all = np.array([col_of[s] for s in f.index])
        ok_buy = buyable[i1]
        keep_top = j_top[ok_buy[j_top]]
        keep_all = j_all[ok_buy[j_all]]
        if len(keep_top) < 10 or len(keep_all) < N_GRP * 5:
            continue
        si = next_sell[i2]                       # 每只股票自己的可卖日
        buy_px = cv[i1]
        sell_px = cv[si, ar]
        r_all = sell_px / buy_px - 1.0
        rt = np.nanmean(r_all[keep_top])
        rm = np.nanmean(r_all[keep_all])
        if not (np.isfinite(rt) and np.isfinite(rm)):
            continue
        if prev_top:
            keep = len(set(top) & prev_top) / max(len(prev_top), 1)
        else:
            keep = 0.0
        turn = 1.0 - keep
        top_r.append(rt * cash - turn * cost)
        mkt_r.append(rm * cash)
        # ★ 日频 mark-to-market（2026-09-14, §1.19；with_daily 时才做）
        #   复用**同一个持仓**(本期的 keep_top/keep_all) ⇒ 不重新选股、成本几乎为零。
        #   ⚠ 不能用 set_fwd(1) 代替：那会变成每天调仓（换手 x5）= 另一个策略。
        if with_daily:
            seg = []
            seg_t = []                        # ★ 组合自身（Top 组等权）的逐日收益
            for t in range(i1, i2):
                _r = cv[t + 1] / cv[t] - 1.0
                _t = np.nanmean(_r[keep_top])
                _m = np.nanmean(_r[keep_all])
                if np.isfinite(_t) and np.isfinite(_m):
                    seg.append((_t - _m) * cash)
                    seg_t.append(_t * cash)
            if seg:
                seg[0] -= turn * cost        # 调仓成本在买入日一次性扣（与期频口径一致）
                seg_t[0] -= turn * cost      # 组合同样在买入日扣成本（与期频 `tr` 口径一致）
                # ★★ **锚定到期频值**（关键！否则两条净值路径不是子采样关系，dd 不可比）
                #   期频 ex_e 是该期的"真实"超额（含复利）；日频只是把它**摊到每一天**。
                #   强制 `prod(1+seg) == 1+ex_e` ⇒ **期频净值 = 日频净值在每个期末的取值**
                #   ⇒ `dd_d <= dd_e` **严格成立**（子采样只能看到更少的极值）✓ 可被单元测试钉死。
                _target = 1.0 + (rt * cash - turn * cost) - rm * cash
                _got = float(np.prod(1.0 + np.asarray(seg, dtype='float64')))
                if _got > 0 and np.isfinite(_target) and _target > 0:
                    _adj = (_target / _got) ** (1.0 / len(seg))
                    seg = [((1.0 + _s) * _adj - 1.0) for _s in seg]
                ex_d_parts.extend(seg)
                # ★ 组合自身日频：**同样锚定到期频的 `tr`**（期末取值 = 期频净值 ⇒ 两条路径是子采样关系）
                _tt = 1.0 + (rt * cash - turn * cost)
                _gt = float(np.prod(1.0 + np.asarray(seg_t, dtype='float64')))
                if _gt > 0 and np.isfinite(_tt) and _tt > 0:
                    _adjt = (_tt / _gt) ** (1.0 / len(seg_t))
                    seg_t = [((1.0 + _s) * _adjt - 1.0) for _s in seg_t]
                tr_d_parts.extend(seg_t)
        if mc_ is not None:
            # 市值加权基准(≈真实指数): 同一批 keep_all, 按市值加权平均。
            # ⚠ 分子分母**必须用同一组有限值掩码** —— 否则 NaN 收益/NaN 市值两者口径不一致:
            #   分子 nansum 跳过 NaN, 分母若把 NaN 的权重也算进去 -> 结果系统性偏低。
            #   (2026-09-13 QA 实录: 恒等测试「mcap=常数 ⇒ 市值加权==等权」据此抓出 5.1e-06 偏差)
            w = mc_[i1][keep_all]
            rr_ = r_all[keep_all]
            m_ = np.isfinite(rr_) & np.isfinite(w)
            ws = float(np.sum(w[m_]))
            rc = float(np.sum(rr_[m_] * w[m_]) / ws) if ws > 0 else np.nan
            mkt_cw.append(rc * cash)
        dates_l.append(d)
        turns.append(turn)
        prev_top = set(top)
    if len(top_r) < 30:
        return None
    tr = pd.Series(top_r, index=dates_l)
    mr = pd.Series(mkt_r, index=dates_l)
    ex = tr - mr
    nav_t = (1 + tr).cumprod()
    nav_m = (1 + mr).cumprod()
    nav_e = (1 + ex).cumprod()
    yrs = len(tr) * FWD / 243
    ann_e = nav_e.iloc[-1] ** (1 / yrs) - 1 if yrs > 0 else np.nan
    dd_e = (nav_e / nav_e.cummax() - 1).min()
    calmar = ann_e / abs(dd_e) if dd_e < 0 else np.nan
    sharpe = ex.mean() / ex.std() * np.sqrt(243 / FWD) if ex.std() > 0 else np.nan
    ann_t = nav_t.iloc[-1] ** (1 / yrs) - 1
    ann_m = nav_m.iloc[-1] ** (1 / yrs) - 1
    # ★ 2026-09-16 新增「**组合自身（非超额）**」的风险三件套（用户要"本身的年化/卡玛/夏普/最大回撤"）：
    #   原来只返回 `ann_top`（组合年化），而下游（因子明细/看板）拿不到组合自己的回撤/卡玛/夏普
    #   ⇒ 口径与 `dd`/`calmar`/`sharpe`（**超额**口径）**严格对应**，只是换成 `tr` 那条腿：
    #     dd_top      = 组合净值 `nav_t` 的最大回撤
    #     calmar_top  = ann_top / |dd_top|
    #     sharpe_top  = tr.mean()/tr.std() × sqrt(243/FWD)（与超额夏普同式）
    #   ⇒ **纯新增字段，不改任何既有返回值**（旧调用方行为逐位不变）✓
    dd_t = (nav_t / nav_t.cummax() - 1).min()
    calmar_t = ann_t / abs(dd_t) if dd_t < 0 else np.nan
    sharpe_t = (tr.mean() / tr.std() * np.sqrt(243 / FWD)) if tr.std() > 0 else np.nan
    yr_ex = {}
    for y, g in ex.groupby(ex.index // 10000):
        yr_ex[y] = (1 + g).prod() - 1
    recent = sorted(yr_ex.keys())[-1]
    recent_2 = sorted(yr_ex.keys())[-2] if len(yr_ex) > 1 else recent
    res = {
        'name': name, 'window': window, 'ic': ic_mean, 'ic_ir': ic_ir,
        'ic_win': ic_win, 'ic_series': ic, 'ann_top': ann_t, 'ann_mkt': ann_m,
        # ★ 2026-09-16：组合自身口径的风险三件套（新增字段，旧调用方不受影响）
        'dd_top': dd_t, 'calmar_top': calmar_t, 'sharpe_top': sharpe_t,
        'ann_ex': ann_e, 'dd': dd_e, 'sharpe': sharpe, 'calmar': calmar,
        'yr': yr_ex, 'last_yr': yr_ex.get(recent, np.nan),
        'last2_yr': yr_ex.get(recent_2, np.nan), 'n_rebal': len(tr),
        'turn': float(np.mean(turns)) if turns else np.nan,
        # with_ex 时额外给 'ex'(每期费后超额) 与 'tr'(每期组合费后收益)。
        #  'tr' 供**多因子合成**用（2026-09-13, roadmap §8.33）：把多个因子的组合收益等权平均
        #  ⇒ 直接得到组合的收益序列, 不必重跑回测。默认(False)行为不变。
        **({'ex': ex, 'tr': tr} if with_ex else {}),
    }
    # ---- 市值加权基准口径(2026-09-13, roadmap §8.28; 仅当传了 mcap) ----
    #  组合腿 tr 不变(仍是 Top10% 等权), 只换基准腿: 等权 -> 市值加权(≈真实指数)。
    #  'tilt' = ann_ex_cw - ann_ex = 「池内规模倾斜」的贡献(见 docstring 7)。
    if mc_ is not None and len(mkt_cw) == len(mkt_r) and len(mkt_cw) >= 30:
        mrc = pd.Series(mkt_cw, index=dates_l)
        exc = tr - mrc
        nav_ec = (1 + exc).cumprod()
        ann_ec = nav_ec.iloc[-1] ** (1 / yrs) - 1 if yrs > 0 else np.nan
        dd_ec = (nav_ec / nav_ec.cummax() - 1).min()
        nav_mc = (1 + mrc).cumprod()
        res.update(
            ann_ex_cw=ann_ec, dd_cw=dd_ec,
            calmar_cw=(ann_ec / abs(dd_ec) if dd_ec < 0 else np.nan),
            sharpe_cw=(exc.mean() / exc.std() * np.sqrt(243 / FWD)
                       if exc.std() > 0 else np.nan),
            tilt=ann_ec - ann_e,
            ann_mkt_cw=(nav_mc.iloc[-1] ** (1 / yrs) - 1 if yrs > 0 else np.nan),
        )
    # ---- ★★ 日频 mark-to-market 风险指标（2026-09-14, §1.19；with_daily 时）----
    #   口径 = **同一策略**（同一持仓、同一调仓日、同一成本）的**日频**净值 ⇒ 回撤不再被低估。
    #   ⚠ 与'期频'对比时看的是**风险**（dd/calmar/sharpe）；'ann_ex' 两者**本就相同**
    #     （终值一样、年数一样），所以 `calmar_d = ann_ex / |dd_d|` 与 `calmar = ann_ex / |dd|`
    #     的差别**只来自回撤** ✓（实测 F10_1000: 0.0685/0.078=0.878 → 0.0685/0.1142=0.600，
    #     与外部独立审查的 0.627 吻合。）
    if with_daily and ex_d_parts:
        ex_d = pd.Series(ex_d_parts, dtype='float64')
        nav_d = (1 + ex_d).cumprod()
        dd_d = float((nav_d / nav_d.cummax() - 1).min())
        # ★ 年化**直接沿用期频的 `ann_e`**（锚定后两者终值相同 ⇒ 本就应相等；
        #   显式复用可让 `calmar_d == ann_ex/|dd_d|` **严格成立**，口径也更清晰：
        #   「**只有回撤换成日频的**」）。
        res.update(
            dd_d=dd_d,
            calmar_d=(ann_e / abs(dd_d) if (dd_d < 0 and np.isfinite(ann_e)) else np.nan),
            sharpe_d=(ex_d.mean() / ex_d.std() * np.sqrt(243.0)
                      if ex_d.std() > 0 else np.nan),
        )
        # ⚠ 口径提醒：`dd_d / calmar_d / sharpe_d` 是「**超额**」的日频（与 `dd / calmar / sharpe` 配对），
        #   与 `dd_top / calmar_top / sharpe_top`（**组合自身**）**不可比** ——
        #   恒等式是 `dd_d <= dd` 与 `dd_top_d <= dd_top`，**不是** `dd_d <= dd_top` ✗
        if with_ex:
            res['ex_d'] = ex_d
    # ★★ 组合自身的**日频**风险（2026-09-16 新增；口径与 `dd_top/calmar_top/sharpe_top` 配对）：
    #   恒等式 `dd_top_d <= dd_top`（日频是期频的子采样 ⇒ 只能看到更深的回撤）⇒ 可被测试钉死 ✓
    if with_daily and tr_d_parts:
        tr_d = pd.Series(tr_d_parts, dtype='float64')
        nav_td = (1 + tr_d).cumprod()
        dd_td = float((nav_td / nav_td.cummax() - 1).min())
        res.update(
            dd_top_d=dd_td,
            calmar_top_d=(ann_t / abs(dd_td) if (dd_td < 0 and np.isfinite(ann_t)) else np.nan),
            sharpe_top_d=(tr_d.mean() / tr_d.std() * np.sqrt(243.0)
                          if tr_d.std() > 0 else np.nan),
        )
        if with_ex:
            res['tr_d'] = tr_d
    return res


def evaluate_dual(fac, close, name='', cost=COST_RT, cash=1.0):
    """双口径并行: 九年(full) vs 最近600交易日(recent600), 返回 (r_full, r_600)"""
    r_full = evaluate_real(fac, close, name, cost=cost, cash=cash, window='full')
    r_600 = evaluate_real(fac, close, name, cost=cost, cash=cash, window='recent600')
    return r_full, r_600


def fmt_dual(r, extra=''):
    """单行双口径报告文本"""
    def _s(x):
        if x is None:
            return 'N/A'
        return (f"IC={x['ic']:+.4f} 费后超额={x['ann_ex']*100:+6.2f}% "
                f"Calmar={x['calmar'] if x['calmar'] else 0:5.2f} "
                f"夏普={x['sharpe']:5.2f} 换手={x.get('turn', np.nan)*100:4.1f}% "
                f"负年={sum(1 for v in x['yr'].values() if v <= 0)} "
                f"最近2年={x['last2_yr']*100:+.1f}%/{x['last_yr']*100:+.1f}%")
    return (f"{r[0]['name']:26s}{extra:6s} | full : {_s(r[0])}\n"
            f"{'':26s}{'':6s} | 近600: {_s(r[1])}")


def run_round_real(F, close, tag='', min_ic=0.02, verbose=True, **kw):
    """用 evaluate_real 批量检验"""
    rows, ic_store = [], {}
    for i, (nm, fac) in enumerate(F.items(), 1):
        try:
            f = cs_rank(fac.astype('float64'))
            r = evaluate_real(f, close, nm, **kw)
            del f
        except Exception as e:
            if verbose:
                print(f"  [{i}/{len(F)}] {nm} ERR {type(e).__name__}: {str(e)[:60]}")
            continue
        if r is None:
            if verbose:
                print(f"  [{i}/{len(F)}] {nm} 样本不足")
            continue
        ic_store[nm] = r.pop('ic_series')
        ok, msg = pass_filter(r, min_ic)
        r['pass'] = 'PASS' if ok else msg[:30]
        rows.append(r)
        if verbose:
            print(f"  [{i}/{len(F)}] {nm:18s} IC={r['ic']:+.4f} IR={r['ic_ir']:+.3f} "
                  f"超额={r['ann_ex']*100:+6.2f}% Calmar={r['calmar'] if r['calmar'] else 0:5.2f} "
                  f"换手={r.get('turn', np.nan)*100:4.1f}% | {r['pass']}")
    res = pd.DataFrame(rows)
    if len(res):
        res = res.sort_values('ann_ex', ascending=False)
    return res, ic_store


# ===================== 验证 =====================
def evaluate(fac, close, name='', verbose=False):
    """单因子检验: IC / 分组 / 年度稳定性
    fac: 因子宽表(date x stock), T日值预测 T+1..T+FWD 收益
    """
    idx = close.index[(close.index >= START)]
    fac = fac.reindex(index=idx, columns=close.columns)
    # 未来收益: T+1 买入, T+1+FWD 卖出
    fwd_ret = (close.shift(-(1 + FWD)) / close.shift(-1) - 1).reindex(index=idx)

    U = get_universe().reindex(index=idx, columns=close.columns).fillna(False)
    fv = fac.values
    rv = fwd_ret.values
    uv = U.values

    # 每日 Spearman IC (仅在可交易池内)
    ics = []
    for i in range(len(idx)):
        u = uv[i]
        f = fv[i][u]
        r = rv[i][u]
        m = np.isfinite(f) & np.isfinite(r)
        if m.sum() < 50:
            ics.append(np.nan)
            continue
        try:
            c = spearmanr(f[m], r[m])[0]
        except Exception:
            c = np.nan
        ics.append(c)
    ic = pd.Series(ics, index=idx)
    ic_mean = ic.mean()
    ic_ir = ic.mean() / ic.std() if ic.std() > 0 else np.nan
    ic_win = (ic > 0).sum() / ic.notna().sum() if ic.notna().sum() else np.nan

    # 分组: 每5日调仓, Top组 vs 全市场等权
    # 注意: 与IC口径一致 —— 用 T 日因子, T+1 日买入, 持满 FWD 天后卖出
    rebal = idx[::FWD]
    top_r, mkt_r, dates = [], [], []
    prev_top = None
    for d in rebal[:-1]:
        # 只在可交易池内选股
        u = U.loc[d]
        f = fac.loc[d][u].dropna()
        if len(f) < N_GRP * 10:
            continue
        nxt = idx[idx > d]
        if len(nxt) <= FWD:
            continue
        d1 = nxt[0]              # T+1 买入
        d2 = nxt[FWD]            # T+1+FWD 卖出
        grp = pd.qcut(f.rank(method='first'), N_GRP, labels=False)
        top = f.index[grp == N_GRP - 1]
        r_fwd = (close.loc[d2] / close.loc[d1] - 1)
        rt = r_fwd.reindex(top).mean()
        rm = r_fwd.reindex(f.index).mean()
        if np.isfinite(rt) and np.isfinite(rm):
            # 成本按实际换手率: 与上期持仓的差异(卖出部分需卖出+买入各付一次)
            if prev_top:
                keep = len(set(top) & prev_top) / max(len(prev_top), 1)
            else:
                keep = 0.0
            top_r.append(rt - (1.0 - keep) * COST * 2)
            mkt_r.append(rm)
            dates.append(d)
            prev_top = set(top)
    if len(top_r) < 30:
        return None
    tr = pd.Series(top_r, index=dates)
    mr = pd.Series(mkt_r, index=dates)
    ex = tr - mr
    nav_t = (1 + tr).cumprod()
    nav_m = (1 + mr).cumprod()
    nav_e = (1 + ex).cumprod()
    yrs = len(tr) * FWD / 243
    ann_e = nav_e.iloc[-1] ** (1 / yrs) - 1 if yrs > 0 else np.nan
    dd_e = (nav_e / nav_e.cummax() - 1).min()
    calmar = ann_e / abs(dd_e) if dd_e < 0 else np.nan
    sharpe = ex.mean() / ex.std() * np.sqrt(243 / FWD) if ex.std() > 0 else np.nan
    ann_t = nav_t.iloc[-1] ** (1 / yrs) - 1

    # 年度超额
    yr_ex = {}
    for y, g in ex.groupby(ex.index // 10000):
        yr_ex[y] = (1 + g).prod() - 1
    recent = sorted(yr_ex.keys())[-1]
    recent_2 = sorted(yr_ex.keys())[-2] if len(yr_ex) > 1 else recent

    ann_m = nav_m.iloc[-1] ** (1 / yrs) - 1 if yrs > 0 else np.nan

    return {
        'name': name, 'ic': ic_mean, 'ic_ir': ic_ir, 'ic_win': ic_win,
        'ic_series': ic, 'ann_top': ann_t, 'ann_mkt': ann_m, 'ann_ex': ann_e,
        'dd': dd_e, 'sharpe': sharpe, 'calmar': calmar,
        'yr': yr_ex, 'last_yr': yr_ex.get(recent, np.nan),
        'last2_yr': yr_ex.get(recent_2, np.nan),
        'n_rebal': len(tr),
    }


def pass_filter(r, min_ic=0.02):
    """11项过滤简化版"""
    if r is None:
        return False, '检验失败'
    if abs(r['ic']) < min_ic:
        return False, f"|IC|={r['ic']:.4f}<{min_ic}"
    if r['ic_win'] < 0.52:
        return False, f"IC胜率={r['ic_win']:.2f}<0.52"
    if r['calmar'] is None or not np.isfinite(r['calmar']) or r['calmar'] < 0.5:
        return False, f"Calmar={r['calmar'] if r['calmar'] else 0:.2f}<0.5"
    if not np.isfinite(r['last_yr']) or r['last_yr'] <= 0:
        return False, f"最近年超额={r['last_yr']:.3f}<=0"
    bad = [y for y, v in r['yr'].items() if v <= -0.02]
    if len(bad) > 1:
        return False, f"亏损年{len(bad)}个:{bad}"
    return True, 'OK'


def run_round(F, close, tag='', min_ic=0.02, verbose=True):
    """批量检验一批候选因子, 返回 (结果DataFrame, IC序列字典)"""
    rows, ic_store = [], {}
    for i, (nm, fac) in enumerate(F.items(), 1):
        try:
            f = cs_rank(fac.astype('float64'))
            r = evaluate(f, close, nm)
            del f
        except Exception as e:
            if verbose:
                print(f"  [{i}/{len(F)}] {nm} ERR {type(e).__name__}: {str(e)[:50]}")
            continue
        if r is None:
            if verbose:
                print(f"  [{i}/{len(F)}] {nm} 样本不足")
            continue
        ic_store[nm] = r.pop('ic_series')
        ok, msg = pass_filter(r, min_ic)
        r['pass'] = 'PASS' if ok else msg[:30]
        rows.append(r)
        if verbose:
            print(f"  [{i}/{len(F)}] {nm:18s} IC={r['ic']:+.4f} IR={r['ic_ir']:+.3f} "
                  f"超额={r['ann_ex']*100:+6.2f}% Calmar={r['calmar'] if r['calmar'] else 0:5.2f} "
                  f"| {r['pass']}")
    res = pd.DataFrame(rows)
    if len(res):
        res = res.sort_values('ann_ex', ascending=False)
    return res, ic_store


def show(res, title=''):
    if not len(res):
        print("无结果")
        return
    print("\n" + "=" * 104)
    print(title)
    print("=" * 104)
    cols = ['name', 'ic', 'ic_ir', 'ann_top', 'ann_mkt', 'ann_ex', 'dd', 'calmar', 'pass']
    print(res[cols].round(4).to_string(index=False))
    npass = (res['pass'] == 'PASS').sum()
    print(f"\n通过: {npass}/{len(res)}")
    if npass:
        print("\n通过因子年度超额:")
        for _, r in res[res['pass'] == 'PASS'].iterrows():
            yr = {k: f"{v*100:+.1f}%" for k, v in sorted(r['yr'].items())}
            print(f"  {r['name']:18s} IC={r['ic']:+.4f} 超额={r['ann_ex']*100:+.2f}%  {yr}")


def load_lib():
    if os.path.exists(LIB):
        with open(LIB, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'kept': [], 'tested': [], 'rejected': {}, 'round': 0}


def save_lib(lib):
    with open(LIB, 'w', encoding='utf-8') as f:
        json.dump(lib, f, ensure_ascii=False, indent=1,
                  default=lambda o: None if isinstance(o, (pd.Series, np.ndarray)) else str(o))
