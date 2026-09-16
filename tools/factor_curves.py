# -*- coding: utf-8 -*-
"""factor_curves.py — 为每个入库因子**离线预算**看板曲线 → `docs/factor_curves/<name>.json`

## 为什么"离线算"（用户之问：加这些图**影响性能吗**？）
网页上"现算"一条曲线 = **一次完整回测**（载面板 + 逐期选股 ≈ 10s）⇒ 点一下卡十秒 ✗
而**入库因子是少数**（当前 51 条）⇒ 离线算一次、存成小 JSON，看板打开详情时**只读一个文件**（几十 KB）
⇒ **对页面性能没有影响** ✓（新增因子用 `--only-new` 增量补算即可）

## 每因子存什么（口径写进 JSON，前端只负责画）
  · **日频**（持有期内逐日 mark）：`d_dates` + 组合净值 `nav_t` / 基准净值 `nav_m` / 超额净值 `nav_e`
    + 超额回撤 `dd_e` / 组合回撤 `dd_t`（面积图）
  · **期频**：`r_dates` + `ic`(Pearson) / `rank_ic`(Spearman，即引擎 IC 口径)
    + `decile`（**十档累计净值**，10 条）/ `ls`（多空=第10档−第1档）/ `turn` 明细
  · **剥风格**（`--stage=strip`）：原 / 剥市值(lncap) / 剥成交额(lnamt) / 剥两者 —— 四条**期频**净值

## 用法（分两段跑，避免一次等太久）
    python tools/factor_curves.py --stage=core            # 核心（~12 分钟）
    python tools/factor_curves.py --stage=strip           # 剥风格四条（~25 分钟）
    python tools/factor_curves.py --only-new --stage=core # 增量：只补没算过的
    python tools/factor_curves.py --limit=2 --stage=core  # 冒烟

★ 复用 `build_facs` 的公共件（`parse_library` / `load_bank_nodes` / `_prep_main` / `load_archive_ic`）
  —— **不复制实现**，避免两处口径漂移 ✓
★ **符号对齐**与 `factor_metrics.py` / `build_facs.py` **同一判据**（用库文档/归档的 IC 定方向）
  ⇒ 曲线方向与明细里的指标**同向**，不会出现"指标正、曲线却在跌" ✗
"""
import argparse
import io
import json
import os
import sys
import time

import numpy as np

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DOCS = os.path.join(ROOT, 'docs')
CURVE_DIR = os.path.join(DOCS, 'factor_curves')
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, 'engine'))

ROUND = 6


def _r(x, n=ROUND):
    try:
        v = float(x)
    except Exception:
        return None
    return round(v, n) if np.isfinite(v) else None


def _rl(seq, n=ROUND):
    return [_r(x, n) for x in np.asarray(seq).ravel()]


def _dates_of(idx):
    return [int(x) for x in idx]


def _aligned(it, B, dates, cols, close, cost, window):
    """求值 + **符号对齐**（与库记录同向）+ 一次完整回测。

    返回 `(fac, rr, sign)`；`fac` 已按 `sign` 取负 ⇒ 下游（十档/多空/剥风格）方向一致 ✓
    """
    import pandas as pd
    import factor_miner as fm
    import loop_engine as LE

    nm = it['_nm']
    nd = it['node']
    if nd is None:
        # ★ 历史编号（已移出当前库）：库里没有 Node ⇒ 从库文档的公式**反向解析**
        #   ⚠⚠ 必须临时放开 `LLM_MAX_SIZE` —— `parse_expr` 对节点数有上限，超限时**静默返回 None** ✗
        _cap = LE.LLM_MAX_SIZE
        LE.LLM_MAX_SIZE = 10 ** 9
        try:
            nd = LE.parse_expr(it['expr'])
        finally:
            LE.LLM_MAX_SIZE = _cap
        if nd is None:
            print('    [!] %s **表达式反解失败**（跳过，不臆造）：%s' % (nm, it['expr'][:60]))
            return None, None, 1
    v = LE.eval_expr(nd, B, {})
    fac = fm.cs_rank(pd.DataFrame(v, index=dates, columns=cols).astype('float64'))
    rr = fm.evaluate_real(fac, close, nm, cost=cost, window=window,
                          with_daily=True, with_ex=True)
    if rr is None:
        return None, None, 1
    sign = 1
    # ★ 符号参照必须与 `factor_metrics.py` / `build_facs.py` **完全同一规则**：
    #   优先用**库记录/归档的带符号 IC**；没有 IC 记录时才退到**文档里的分池超额**（老条目）。
    #   ⚠ 少了这个回退 ⇒ 那 8 个"无 IC 记录"的老因子会**方向反**（指标正、曲线却向下）✗
    ref = it.get('ic_ref')
    if ref in (None, 0):
        ref = it.get('ae_lib')
    if ref not in (None, 0) and np.sign(rr['ic']) != np.sign(ref):
        sign = -1
        fac = -fac
        rr2 = fm.evaluate_real(fac, close, nm, cost=cost, window=window,
                               with_daily=True, with_ex=True)
        if rr2 is not None:
            rr = rr2
    # ★ 期频曲线的公共网格（与 `evaluate_real` 内部一致）：`close.index >= START`
    rr['_close'] = close
    rr['_idx'] = close.index[close.index >= fm.START]
    return fac, rr, sign


def core_for(nm, fac, rr, cost, window, verbose=True):
    """核心曲线：日频净值/回撤 + 期频 IC(Pearson)/RankIC/十档/多空。"""
    import pandas as pd
    import factor_miner as fm

    # ---- ★★ 期频曲线**必须全部对齐到"换仓日网格"** `rb`（= `rr['ex'].index`，418 个）----
    #   ⚠⚠ 2026-09-16 实测踩坑：原实现把 IC/十档算在**全日频网格**（3309 个日期）上，
    #      却用 418 个换仓日当横轴 ⇒ 前 418 天被拉满整张图，**图与数不对应** ✗（长度不等也会误画）
    #   ⇒ 现在：IC(Pearson)/RankIC/十档/多空/换手**一律只取换仓日**的那一行 ✓ 且省 87% 计算量
    idx = rr['_idx']
    close = rr['_close']
    rb = rr['ex'].index
    pos = {int(d): i for i, d in enumerate(idx)}
    fwd_ret = (close.shift(-(1 + fm.FWD)) / close.shift(-1) - 1).reindex(index=idx)
    U = fm.get_universe().reindex(index=idx, columns=close.columns).fillna(False)
    fac_i = fac.reindex(index=idx, columns=close.columns)
    fv, rv, uv = fac_i.values, fwd_ret.values, U.values
    n_grp = fm.N_GRP
    ics_p, dec_parts, turns = [], [], []
    prev_top = None
    for d in rb:
        i = pos.get(int(d))
        if i is None:
            ics_p.append(np.nan)
            dec_parts.append([np.nan] * n_grp)
            turns.append(None)
            continue
        u = uv[i]
        f_, r_ = fv[i][u], rv[i][u]
        m = np.isfinite(f_) & np.isfinite(r_)
        if m.sum() < 50:
            ics_p.append(np.nan)
            dec_parts.append([np.nan] * n_grp)
            continue
        ff, rr_ = f_[m], r_[m]
        ics_p.append(float(np.corrcoef(ff, rr_)[0, 1]))             # Pearson IC
        pct = pd.Series(ff).rank(pct=True).values                   # 0~1 分位
        grp = np.clip((pct * n_grp).astype(int), 0, n_grp - 1)
        dec_parts.append([float(np.mean(rr_[grp == g])) if (grp == g).any() else np.nan
                          for g in range(n_grp)])
        # 逐期换手（引擎同义：Top 组换掉的比例）—— ★ 用**列位置当股票 id**，
        #   ⚠ 不能用 `ff` 的下标（它是 universe∩有限 的子集）去索引整行，那是两个长度 ✗
        pos_m = np.nonzero(u)[0][m]
        k = max(10, len(pos_m) // 10)
        top = set(pos_m[np.argsort(-ff)[:k]].tolist())
        # ★ 每期都 append（第一期没有"上期" ⇒ None）—— 否则 `turn_series` 会比日期轴**少一条** ✗
        turns.append((1.0 - len(top & prev_top) / max(len(prev_top), 1)) if prev_top else None)
        prev_top = top
    dec = np.array(dec_parts, dtype='float64')
    dec_nav = np.cumprod(1.0 + np.nan_to_num(dec, nan=0.0), axis=0)

    exd = np.asarray(rr.get('ex_d'), dtype='float64')
    trd = np.asarray(rr.get('tr_d'), dtype='float64')
    d_dates = rr.get('d_dates') or []
    if len(d_dates) != len(exd) or len(trd) != len(exd):
        print('    [!] %s 日频序列长度不符 ⇒ 跳过日频曲线' % nm)
        return None
    mrd = trd - exd
    nav_t = np.cumprod(1.0 + trd)
    nav_m = np.cumprod(1.0 + mrd)
    nav_e = np.cumprod(1.0 + exd)
    dd_e = nav_e / np.maximum.accumulate(nav_e) - 1.0
    dd_t = nav_t / np.maximum.accumulate(nav_t) - 1.0
    ls = np.cumprod(1.0 + np.nan_to_num(dec[:, -1] - dec[:, 0], nan=0.0))

    out = {
        'name': nm, 'cost': cost, 'window': window,
        'start': int(rr['ex'].index[0]), 'end': int(rr['ex'].index[-1]),
        'n_rebal': int(rr['n_rebal']),
        'r_dates': _dates_of(rb),
        'd_dates': [int(x) for x in d_dates],
        'nav_t': _rl(nav_t), 'nav_m': _rl(nav_m), 'nav_e': _rl(nav_e),
        'dd_e': _rl(dd_e), 'dd_t': _rl(dd_t),
        'ic': _rl(ics_p),
        # ★ RankIC 也只取**换仓日**那条（与横轴同长）；引擎的 `ic_series` 是全日频的 ⇒ 这里 reindex
        'rank_ic': _rl(rr['ic_series'].reindex(rb).values),
        'decile': [_rl(dec_nav[:, g]) for g in range(n_grp)],
        'ls': _rl(ls), 'turn_series': _rl(turns),
        'caliber': ('日频=持有期内逐日 mark；期频=每 %d 交易日一条；'
                    '十档/多空=费前（与 IC 同一套前视收益，未做涨跌停/停牌可交易性处理）'
                    % fm.FWD),
    }
    if verbose:
        print('    core ✓ 日频 %d 点 · 期频 %d 期 · PearsonIC %+.4f · RankIC %+.4f'
              % (len(d_dates), len(rr['ex']), float(np.nanmean(ics_p)),
                 float(np.nanmean(rr['ic_series'].values))))
    return out


def strip_for(nm, fac, rr, B, dates, cols, close, cost, window, STYLE, verbose=True):
    """剥风格四条净值（原 / 剥市值 / 剥成交额 / 剥两者）—— 期频；`raw` 直接复用已算好的 `rr`。"""
    import pandas as pd
    import factor_miner as fm
    from loop_metrics import neutral_rank

    fv = fac.values.astype('float64')
    variants = {}
    for k, sty in (('lncap', ['lncap']), ('lnamt', ['lnamt']), ('both', ['lncap', 'lnamt'])):
        variants[k] = pd.DataFrame(
            neutral_rank(fv, [STYLE[x] for x in sty]), index=dates, columns=cols)
    navs = {'raw': _rl(np.cumprod(1.0 + np.asarray(rr['ex'], dtype='float64')))}
    calmars = {'raw': _r(rr['calmar'])}
    for k, x in variants.items():
        r = fm.evaluate_real(x, close, nm + '#' + k, cost=cost, window=window, with_ex=True)
        if r is None:
            return None
        navs[k] = _rl(np.cumprod(1.0 + np.asarray(r['ex'], dtype='float64')))
        calmars[k] = _r(r['calmar'])
    if verbose:
        print('    strip ✓ 剥Calmar 原 %s / 市值 %s / 成交额 %s / 两者 %s'
              % (calmars.get('raw'), calmars.get('lncap'), calmars.get('lnamt'),
                 calmars.get('both')))
    return {'dates': _dates_of(rr['ex'].index), 'navs': navs, 'calmars': calmars,
            'caliber': '期频超额净值（成本已扣）；剥市值=对 lncap 截面秩中性化，'
                       '剥成交额=lnamt，剥两者=同时做'}


# ================================================================ 风格相关性（2026-09-16 用户要求）
# ★ 用户之问：「跟 barra 那些风格的相关性图，比如做了行业、市值中性化后，跟成长的相关性 0.01、
#   XX 相关性 0.29、beta 的日度相关系数均值这样。这个是不是比较科学？能不能看出它跟哪个风格接近？」
# ★★ 口径（我选的"更科学"那套，用户已同意）：
#   ① **逐期截面 Spearman**（换仓日 418 期；同一时点跨股票）—— 不用"日度相关系数均值"（日度自相关 ⇒
#      t 值虚高）。
#   ② 报 **mean / meanAbs / IR(=mean·std⁻¹) / 胜率 / t=IR·√T**，并把 **lag-1 自相关**一起存出来供审计：
#      ★ 本项目的换仓期**互不重叠**（每 5 个交易日一期）⇒ ρ_t 近似独立 ⇒ `t = IR·√T` 是站得住的 ✓
#      （若 ac1 很大，就该改用 Newey-West —— 先把它显示出来，让判断有依据）
#   ③ ⚠ **mean 会被符号翻转互相抵消**（一半期 +0.5 / 一半 −0.5 ⇒ mean≈0，其实非常相关）
#      ⇒ 所以**必须同时看 meanAbs**（强度）与 IR（稳定性）✓
#   ④ **行业**不用"哑变量相关"堆 31 条：报 **R²**（因子对 31 个行业哑变量的解释力）+ 各行业 |相关| 排行 ✓
#   ⑤ 两套口径：**raw**（原始）与 **neut**（剥总市值 + 行业 —— 就是"做了行业市值中性化后"）✓

STYLE_SELF = ('lncap', 'lnamt', 'lntr', 'lnpx')


def _rho(a, b):
    """Pearson-on-ranks（= Spearman）。a/b 都已是 0~1 的秩；常数向量 ⇒ 返回 0.0（退化）"""
    a = np.asarray(a, dtype='float64')
    b = np.asarray(b, dtype='float64')
    sa, sb = a.std(), b.std()
    if sa <= 1e-12 or sb <= 1e-12:
        return 0.0
    return float(((a - a.mean()) * (b - b.mean())).mean() / (sa * sb))


def _summ(pairs):
    """把一条 `[(年份, ρ_t)]` 序列压成一组稳健统计量（用户要的"科学口径"）
    ⚠ `None`/NaN 一律先剔掉（那是"退化/不可判定"，不能当 0 混进来 ✗）
    ★ 显著性给**三个**（都不完美，摆出来让人自己判断）：
      · `t`    朴素 IR·√T —— ⚠ 相关序列自相关高时**放大数倍**（实测 ac1≈0.93~0.97）✗
      · `tAdj` AR(1) 有效样本量（T_eff = T·(1−ac1)/(1+ac1)）—— 对"近随机游走"的序列**过度保守** ⚠
      · `tYr`  **分年度块**：先算每年的均值（9 个块），再对 9 个年均值算 IR·√n_year ⇐ **最直观** ✓
      三者一致时结论最稳；不一致时说明"相关是慢变量"，此时**看年同号率**最实在 ✓
    """
    vals = [(y, v) for y, v in pairs if v is not None and np.isfinite(v)]
    x = np.asarray([v for _, v in vals], dtype='float64')
    n = len(x)
    if n < 3:
        return dict(mean=None, meanAbs=None, ir=None, t=None, win=None, ac1=None)
    sd = x.std()
    ir = float(x.mean() / sd) if sd > 1e-12 else None
    win = float(max((x > 0).mean(), (x < 0).mean()))
    ac1 = float(np.corrcoef(x[:-1], x[1:])[0, 1]) if sd > 1e-12 and n > 5 else None
    t = ir * np.sqrt(n) if ir is not None else None
    # ★★ t 必须做**自相关校正**！2026-09-16 实测教训：我原以为"换仓期不重叠 ⇒ ρ_t 近似独立"，
    #   把 `ac1` 显示出来后看到它 **+0.93~0.97** ⇒ 那个假设**是错的**，朴素 `t=IR·√T` 把 t 放大到
    #   −220（荒谬）。改用 **AR(1) 有效样本量**：`T_eff = T·(1−ac1)/(1+ac1)` ⇒ `t_adj = IR·√T_eff` ✓
    #   （风格暴露变化慢 ⇒ 相关序列高度持续，这是**结构性**的，不是这个因子特殊）
    tadj = None
    if ir is not None and ac1 is not None and abs(ac1) < 0.999:
        tadj = ir * np.sqrt(max(1.0, n * (1.0 - ac1) / (1.0 + ac1)))
    # ★ 分年度块（抗自相关、最直观）：每年一个均值 ⇒ 对年序列算 IR·√n_year
    _by = {}
    for y, v in vals:
        _by.setdefault(y, []).append(v)
    ymean = np.asarray([float(np.mean(v)) for y, v in sorted(_by.items()) if len(v) >= 10])
    t_yr = ir_yr = win_yr = None
    if len(ymean) >= 4:
        sd_y = ymean.std()
        ir_yr = float(ymean.mean() / sd_y) if sd_y > 1e-12 else None
        if ir_yr is not None:
            t_yr = ir_yr * np.sqrt(len(ymean))
        win_yr = float(max((ymean > 0).mean(), (ymean < 0).mean()))
    return dict(mean=_r(x.mean()), meanAbs=_r(np.abs(x).mean()), ir=_r(ir),
                t=_r(t), tAdj=_r(tadj), tYr=_r(t_yr), win=_r(win), winYr=_r(win_yr),
                nYr=len(ymean) if len(ymean) else None, ac1=_r(ac1))


def _ind_r2(x, g):
    """行业哑变量的解释力 R²（组间方差占比）；退化为 1 组 ⇒ 0"""
    ok = g >= 0
    if ok.sum() < 50:
        return 0.0
    xx, gg = x[ok], g[ok]
    tot = xx.var()
    if tot <= 1e-12:
        return 0.0
    within = 0.0
    for gi in np.unique(gg):
        v = xx[gg == gi]
        within += len(v) * v.var()
    return float(max(0.0, 1.0 - (within / len(xx)) / tot))


def _neut_size_ind(xr, mr, g, u):
    """**总市值 + 行业 同时**中性化（FWL）：先各自组内去均值，再对去均值后的市值回归取残差。
    等价于 `x ~ [1, 31 行业哑变量, lncap]` 的 OLS 残差 ✓（比堆 31 列设计矩阵便宜得多）
    ⚠ 退化：某组只有 1 只 / 去均值后市值方差为 0 ⇒ 该部分退化为"只去行业均值"（不臆造）
    ★★ 返回 `(残差, 是否退化)`：**残差 ≈ 0** 时必须**判定为退化**（工程上等于"完全被解释了"）——
      否则对一堆浮点噪声取秩，会算出**看起来很像样但毫无意义**的相关/R²（实测踩到过：本项目铁律
      "缺失/退化时一律不判定，不臆造"）✓
    """
    xc = xr.copy()
    mc = mr.copy()
    # ★★ `g == -1`（**没有行业编码**的股票）也**必须当成一个组**去均值！
    #   原实现只处理 `g >= 0` ⇒ 那批股票保留原值混进残差 ⇒ 残差里还带着它们的（大多是市值/流动性）
    #   结构 ⇒ **"行业中性化"结果被污染**（自检 A 案例实测：中性化后行业 R² 仍 0.59，本该≈0）✗
    #   数学上：把 -1 也当一个组 = 多一个哑变量，与 `Y ~ [1, 31 哑变量, lncap]` 等价 ✓
    for gi in np.unique(g):
        m = g == gi
        if m.sum() >= 5:
            xc[m] -= xr[m].mean()
            mc[m] -= mr[m].mean()
    # ⚠ 退化阈值取 **1e-5·std(x)**：风格特征是 **float32**（相对精度 ~1e-7）⇒
    #   拿 lncap 去剥 −ln(mktcap) 时残差约 1e-8 量级（**不是 0**），若阈值卡 1e-9 就会
    #   把"float32 取整噪声"当成信号 ⇒ 实测算出行业 R²=0.590 这种**看着很像样但毫无意义**的数 ✗
    #   真实因子的残差是 O(0.1~1)·std ⇒ 与 1e-5 阈值差 4 个数量级，**不会误判** ✓
    # ⚠⚠ 退化判据要用**分位数**而不是 std：实测残差是"**99% 精确为 0** + 极少数 1e-6"
    #   ⇒ std 会被那少数几个值撑起来（误判"还没剥干净"），而真实情况是**已经完全解释掉了** ✗
    #   这里看"残差 99.5 分位"相对因子秩的尺度：< 1e-3 ⇒ 剩下的东西比原信号小 3 个数量级 ⇒ 退化 ✓
    def _deg_of(r):
        return bool(np.percentile(np.abs(r), 99.5) <= 1e-3 * (xr.std() + 1e-18))
    if mc.std() <= 1e-12:
        return xc, _deg_of(xc)
    beta = float(((xc - xc.mean()) * (mc - mc.mean())).mean() / (mc.var() + 1e-18))
    res = xc - beta * mc
    return res, _deg_of(res)


def style_for(nm, fac, B, dates, cols, close, rb, STYLE, verbose=True):
    """风格相关性画像（raw / neut 两套 + 行业 R²/排行）。全部在**换仓日**上算。"""
    import pandas as pd
    import factor_miner as fm

    idx = close.index[close.index >= fm.START]
    pos = {int(d): i for i, d in enumerate(idx)}
    fv = fac.reindex(index=idx, columns=close.columns).values
    uv = (fm.get_universe().reindex(index=idx, columns=cols).fillna(False)).values
    # ⚠ 风格/行业面板是**整块面板网格**(dates)，这里的行号是 **idx 子网格**的 ⇒ 必须显式对齐 ✗
    _full = {int(d): j for j, d in enumerate(dates)}
    _rows = [_full[int(d)] for d in idx]
    sv = {}
    for k, v in STYLE['feat'].items():
        arr = v if isinstance(v, np.ndarray) else np.asarray(v)
        arr = np.asarray(arr, dtype='float32')
        if arr.shape != (len(dates), len(cols)):
            arr = pd.DataFrame(arr).reindex(index=range(len(dates)), columns=range(len(cols))).values
        sv[k] = arr[_rows]
    iv = np.asarray(STYLE['ind'])[_rows]                # (T_idx,S) int16 行业编码
    names = STYLE['styles']                             # 15 个连续风格名
    ind_names = STYLE['ind_names']

    # ★★ 先定"合格期"：**行业覆盖率 ≥ 50%** —— raw 与 neut 必须在**同一批期**上算，
    #   否则"中性化前后"的对比被**样本差异**混淆 ✗（实测：行业面板早期覆盖率 0%，
    #   那些期数里"剥总市值+行业"其实退化成"只剥市值"）
    _cov = {}
    for d in rb:
        i = pos.get(int(d))
        if i is not None:
            _cov[int(d)] = float((iv[i] >= 0).mean())
    _elig = [d for d in rb if _cov.get(int(d), 0.0) >= 0.5]
    ind_ok = len(_elig) >= 30
    periods = _elig if ind_ok else list(rb)

    series = {k: {s: [] for s in names} for k in ('raw', 'neut')}
    ind_series = {k: {j: [] for j in range(len(ind_names))} for k in ('raw', 'neut')}
    r2s = {'raw': [], 'neut': []}
    for d in periods:
        i = pos.get(int(d))
        if i is None:
            continue
        u = uv[i]
        x = fv[i]
        m = u & np.isfinite(x)
        if m.sum() < 200:
            continue
        g = iv[i][m]
        yr = int(str(int(d))[:4])                           # ★ 年份（供"分年度块"显著性）
        xr = pd.Series(x[m]).rank(pct=True).values          # 因子秩（子集内）
        _xn, _deg = _neut_size_ind(xr, pd.Series(sv['lncap'][i][m]).rank(pct=True).values, g, m)
        xr_n = np.full(len(xr), np.nan) if _deg else pd.Series(_xn).rank(pct=True).values
        r2s['raw'].append(_ind_r2(xr, g))
        # ★ 退化（中性化后≈0）⇒ **记 NaN 不臆造**（见 `_neut_size_ind` 注释）
        r2s['neut'].append(np.nan if _deg else _ind_r2(xr_n, g))
        # 行业 |相关|：把"行业哑变量"当 0/1 变量，与因子秩做点双列相关 = 组均值差
        gm, sx = xr.mean(), xr.std()
        for j in range(len(ind_names)):
            mj = g == j
            if mj.sum() < 5:
                ind_series['raw'][j].append((yr, np.nan))
                ind_series['neut'][j].append((yr, np.nan))
                continue
            ind_series['raw'][j].append(
                (yr, float((xr[mj].mean() - gm) / (sx + 1e-12)
                           * np.sqrt(mj.mean() * (1 - mj.mean())))))
            ind_series['neut'][j].append(
                (yr, np.nan if _deg else
                 float((xr_n[mj].mean() - np.nanmean(xr_n)) / (np.nanstd(xr_n) + 1e-12)
                       * np.sqrt(mj.mean() * (1 - mj.mean())))))
        for s in names:
            v = sv[s][i]
            mm = m & np.isfinite(v)
            if mm.sum() < 200:
                continue
            # ★★ 退化守卫（2026-09-16 实测）：`barra_comovement` 面板是**常数**（全 0）⇒
            #   逐期 Spearman 恒为 0 ⇒ 存出来是 `mean 0.000 / ir None`，看着像"完全无暴露"，
            #   其实是"**不可判定**" ✗ ⇒ 一律记 `(年份, None)`（本项目铁律：退化不判定、不臆造）✓
            #   ⚠⚠ 这里存的是 **(yr, 值) 二元组**（下游要按年做块显著性）⇒ **必须同样塞二元组**；
            #     塞裸 `None` 会让下游解包炸掉：`TypeError: cannot unpack non-iterable NoneType` ✗（实测踩到）
            #   ⚠ raw / neut **各 append 一次**（两条序列要等长，否则错位 ✗）
            if float(np.nanstd(v[mm])) <= 1e-12:
                series['raw'][s].append((yr, None))
                series['neut'][s].append((yr, None))
                continue
            vr = pd.Series(v[mm]).rank(pct=True).values
            xr2 = pd.Series(x[mm]).rank(pct=True).values
            series['raw'][s].append((yr, _rho(xr2, vr)))
            g2 = iv[i][mm]
            xn, deg = _neut_size_ind(xr2, pd.Series(sv['lncap'][i][mm]).rank(pct=True).values, g2, mm)
            if deg:
                series['neut'][s].append((yr, np.nan))      # ★ 退化 ⇒ 不判定
                continue
            series['neut'][s].append((yr, _rho(pd.Series(xn).rank(pct=True).values, vr)))
    out = {'n_periods': len(series['raw'][names[0]]), 'styles': list(names),
           # ★ 行业面板的**覆盖情况必须让人看见**（没行业编码的股票按"自成一组"处理）
           'indCover': _r(float((iv >= 0).mean())) if iv.size else None,
           'indOk': bool(ind_ok),
           'nPeriodsAll': len(list(rb)), 'nPeriodsInd': len(_elig),
           'indFrom': (int(min(_elig)) if (_elig and ind_ok) else None),
           'ind_names': list(ind_names),            'caliber': (
              # ★ 这段会**原样显示在看板上** ⇒ 一律自然语言 + 普通标点（不许 `**`/`★`/`⚠`/引号）✓
              #   （另有一道出口清洗 `factors._plain()` 兜底，两道都做）
              '逐期截面 Spearman（换仓日）· 中性化 = 总市值 + 申万一级行业（FWL；'
              'raw 与 neut 用同一批期）· 行业面板覆盖率 %.0f%%（自 %s 起）· '
              '均值会被符号翻转抵消，须同时看 |均值| 与 IR · ' % (
                  (float((iv >= 0).mean()) * 100) if iv.size else 0.0,
                  int(min(_elig)) if (_elig and ind_ok) else '全程不足') +
              't 用 AR(1) 有效样本量校正（T_eff = T 乘 (1−ac1)/(1+ac1)）：'
              '实测相关序列 ac1 约 0.93~0.97（风格暴露变化慢），'
              '朴素 t = IR 乘根号 T 会放大数倍，别直接看它'),
           'raw': {s: _summ(series['raw'][s]) for s in names},
           'neut': {s: _summ(series['neut'][s]) for s in names},
           'ind': {'raw': [_summ(ind_series['raw'][j]) for j in range(len(ind_names))],
                   'neut': [_summ(ind_series['neut'][j]) for j in range(len(ind_names))]},
           'r2': {'raw': _r(float(np.nanmean(r2s['raw'])) if r2s['raw'] else None),
                  'neut': _r(float(np.nanmean(r2s['neut'])) if r2s['neut'] else None)}}
    if verbose:
        top = sorted(names, key=lambda s: -abs(out['raw'][s]['mean'] or 0))[:4]
        print('    style ✓ %d 期 · 最强原始相关: %s' % (
            out['n_periods'], ' · '.join(
                '%s %+.3f' % (s.replace('barra_', ''), out['raw'][s]['mean'] or 0) for s in top))
              + ' | 行业R² raw %.3f → neut %.3f' % (out['r2']['raw'] or 0, out['r2']['neut'] or 0))
    return out


def strip2_for(nm, fac, rr, dates, cols, close, cost, window, LIM, verbose=True):
    """★ 追加两个剥法（直接回答用户「用流通市值剥总市值剥不干净」在**因子层**的影响）：
       · `floatcap` = 剥**流通市值**（market_cap_2）
       · `caplimit` = 剥**总市值 + 限售比例** ln(总/流通)   ← 理论上应该最干净
    二者对比 ⇒ 能不能看出"用流通代替总市值"漏掉的东西。"""
    import pandas as pd
    import factor_miner as fm
    from loop_metrics import neutral_rank

    fv = fac.values.astype('float64')
    variants = {
        'floatcap': neutral_rank(fv, [LIM['lnfloat']]),
        'caplimit': neutral_rank(fv, [LIM['lncap'], LIM['lnlimit']]),
    }
    navs, calmars = {}, {}
    for k, x in variants.items():
        r = fm.evaluate_real(pd.DataFrame(x, index=dates, columns=cols), close,
                             nm + '#' + k, cost=cost, window=window, with_ex=True)
        if r is None:
            return None, None
        navs[k] = _rl(np.cumprod(1.0 + np.asarray(r['ex'], dtype='float64')))
        calmars[k] = _r(r['calmar'])
    if verbose:
        print('    strip2 ✓ 剥Calmar 流通市值 %s / 总市值+限售 %s'
              % (calmars.get('floatcap'), calmars.get('caplimit')))
    return navs, calmars


def _self_test(B, dates, cols, close, STYLE_PROF):
    """★ 恒等不变量自检（**不写任何文件**）——"凡新增计算路径，先找一个退化时必须成立的不变量"：
      [A] `-ln(mktcap)`（纯小市值因子）⇒ 与 `barra_size` 原始相关 ≈ **−1.00**，中性化后 ≈ **0**
      [B] 某行业哑变量本身 ⇒ 原始 **行业 R² 应很高**；中性化后 **行业 R² ≈ 0**
          （★ 这条最要紧：它证明"行业中性化"真的在起作用，而不是写了个摆设）
      [C] 随机噪声 ⇒ 所有相关 ≈ 0（|mean| < 0.05）
    """
    import pandas as pd
    import factor_miner as fm

    idx = close.index[close.index >= fm.START]
    rb = idx[::fm.FWD][:-1]                       # 名义换仓网格（自检只需网格，不需要真回测）
    mc = np.where(B['mktcap'] > 0, B['mktcap'].astype('float64'), np.nan)
    g0 = STYLE_PROF['ind'] == 0
    tests = [
        ('A 纯小市值 -ln(mktcap)', -np.log(mc)),
        ('B 行业#0 的哑变量', g0.astype('float64')),
        ('C 随机噪声', np.random.RandomState(20260916).uniform(size=mc.shape)),
    ]
    fails = []
    print('=' * 100)
    print('恒等不变量自检（风格相关性画像）')
    print('=' * 100)
    for tag, v in tests:
        f = pd.DataFrame(np.asarray(v, dtype='float64'), index=dates, columns=cols)
        p = style_for('selftest', f, B, dates, cols, close, rb, STYLE_PROF, verbose=False)
        raw_sz = (p['raw'].get('barra_size') or {}).get('mean')
        neu_sz = (p['neut'].get('barra_size') or {}).get('mean')
        r2r, r2n = p['r2']['raw'], p['r2']['neut']
        top = sorted(p['styles'], key=lambda s: -abs((p['raw'][s] or {}).get('mean') or 0))[:3]
        print('  [%s] barra_size raw %s / neut %s · 行业R² raw %.3f → neut %.3f'
              % (tag, _r(raw_sz), _r(neu_sz), r2r or 0, r2n or 0))
        print('        原始最强相关: %s' % ' · '.join(
            '%s %+.3f' % (s.replace('barra_', ''), (p['raw'][s] or {}).get('mean') or 0)
            for s in top))
        if tag.startswith('A'):
            if raw_sz is None or abs(raw_sz + 1.0) > 0.05:
                fails.append('%s: 与 barra_size 原始相关应≈−1，实测 %s' % (tag, raw_sz))
            if neu_sz is not None and abs(neu_sz) > 0.15:
                fails.append('%s: 中性化后 barra_size 相关应≈0，实测 %s' % (tag, neu_sz))
        if tag.startswith('B'):
            if (r2r or 0) < 0.30:
                fails.append('%s: 原始行业 R² 应很高，实测 %.3f' % (tag, r2r or 0))
            if (r2n or 0) > 0.02:
                fails.append('%s: ★ 中性化后行业 R² 应≈0，实测 %.3f（行业中性化没生效！）' % (tag, r2n or 0))
        if tag.startswith('C'):
            for s in p['styles']:
                mm = abs((p['raw'][s] or {}).get('mean') or 0)
                if mm > 0.06:
                    fails.append('%s: 噪声因子与 %s 相关 %.3f（应≈0）' % (tag, s, mm))
    print()
    if fails:
        print('★★ 自检失败 %d 项：' % len(fails))
        for x in fails:
            print('   ✗ %s' % x)
        return 1
    print('★★ 自检全部通过 ✓（小市值→size≈−1 · 行业哑变量→中性化后 R²≈0 · 噪声→相关≈0）')
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pools', default='all,300,500,1000')
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--only-new', action='store_true', help='只补缺该段数据的因子')
    # ★ `style+strip2`：两段**合并一趟跑**（共用同一次回测）⇒ 省掉一半时间 ✓
    ap.add_argument('--stage', default='all',
                    choices=['core', 'strip', 'style', 'strip2', 'style+strip2', 'all'])
    ap.add_argument('--self-test', action='store_true',
                    help='★ 只做**恒等不变量自检**（不写任何文件）：拿"已知答案"的合成因子上验风格画像')
    ap.add_argument('--include_history', action='store_true',
                    help='★ 也给**已移出当前库的历史编号**出曲线（从库文档取公式反向解析；'
                         '默认只算 state.bank = 当前有效库）')
    ap.add_argument('--cost', type=float, default=0.004)
    ap.add_argument('--window', type=int, default=5)
    ap.add_argument('--panel_cache', default='off', choices=['off', 'use', 'build'])
    a = ap.parse_args()

    import build_facs as BF
    LE = BF._prep_main()
    LE.set_panel_cache(a.panel_cache)
    os.makedirs(CURVE_DIR, exist_ok=True)

    items = []
    n_hist = 0
    for p in [x.strip() for x in a.pools.split(',') if x.strip()]:
        nodes = BF.load_bank_nodes(p)
        if not nodes:
            continue
        ics = BF.load_archive_ic(p)
        lib_rows = BF.parse_library(p)
        lib = {r['expr']: r for r in lib_rows}
        for expr, nd in nodes.items():
            L = lib.get(expr) or {}
            items.append(dict(pool=p, no=L.get('no') or BF._fallback_name(expr), expr=expr,
                              node=nd, gen=L.get('gen') or '',
                              ic_ref=(ics.get(expr) if ics.get(expr) is not None else L.get('ic')),
                              ae_lib=L.get('ann_ex'), _nm=None))
        if not a.include_history:
            continue
        # ★ 2026-09-17（用户："想看历史编号的费后指标/曲线"）：
        #   库文档里有、bank 里没有 ⇒ **已移出当前库的历史编号** ⇒ 也给它出曲线 ✓
        for r in lib_rows:
            if r['expr'] in nodes:
                continue
            items.append(dict(pool=p, no=r.get('no') or BF._fallback_name(r['expr']),
                              expr=r['expr'], node=None, gen=r.get('gen') or '',
                              ic_ref=(ics.get(r['expr']) if ics.get(r['expr']) is not None
                                      else r.get('ic')),
                              ae_lib=r.get('ann_ex'), _nm=None))
            n_hist += 1
    if a.include_history:
        print('  ★ --include_history：额外补 **%d 个已移出当前库的历史编号**' % n_hist)
    # ★★ 2026-09-17（配合用户要的"历史编号也要有曲线"）：
    #   **同一表达式可能挂着多个名字** —— 历史编号与别的池的在库因子"同式不同名"（实测 9 个历史里有 2 个）
    #   ⇒ 计算只做一次（省时间），但**每个名字都要落一份文件**；否则按名字查会显示"暂无曲线数据"
    #     （明明算过、只是存在别的名字下）✗
    alias = {}
    seen, uniq = set(), []
    for it in items:
        _nm_i = BF._name_of(it)
        it['_nm'] = _nm_i
        alias.setdefault(it['expr'], []).append(_nm_i)
        if it['expr'] in seen:
            continue
        seen.add(it['expr'])
        uniq.append(it)

    def _path(nm):
        return os.path.join(CURVE_DIR, '%s.json' % nm)

    def _need_one(p):
        if not os.path.exists(p):
            return True
        if not a.only_new:
            return True
        try:
            d = json.load(io.open(p, encoding='utf-8'))
        except Exception:
            return True
        if a.stage == 'core':
            return 'nav_e' not in d
        if a.stage == 'strip':
            return 'strip' not in d
        def _style_ok(dd):
            """★ 不只检查"有没有 style"，还要**统计量齐全**（老版本没 `tAdj`/`tYr`
            ⇒ 必须视为"要重算"，否则新旧混在一张表里 ✗ —— 2026-09-16 实测漏过 4 个）"""
            st = dd.get('style') or {}
            if not st.get('styles'):
                return False
            return all({'tAdj', 'tYr', 'winYr'} <= set((st.get('raw') or {}).get(s, {}))
                       for s in st['styles'])

        def _need2(dd):
            return not all(k in ((dd.get('strip') or {}).get('navs') or {})
                           for k in ('floatcap', 'caplimit'))

        if a.stage == 'style':
            return not _style_ok(d)
        if a.stage == 'strip2':
            return _need2(d)
        if a.stage == 'style+strip2':
            return (not _style_ok(d)) or _need2(d)
        return (('nav_e' not in d) or ('strip' not in d) or (not _style_ok(d))
                or _need2(d))

    def _need(it):
        # ★ 该表达式的**任一名字**缺文件/缺阶段 ⇒ 都要重算（保证每个名字都有文件）✓
        return any(_need_one(_path(x)) for x in (alias.get(it['expr']) or [it['_nm']]))

    uniq = [it for it in uniq if _need(it)]
    if a.limit:
        uniq = uniq[:a.limit]
    print('=' * 96)
    print('因子曲线离线预算 → %s' % os.path.relpath(CURVE_DIR, ROOT))
    print('  stage=%s · 待算 %d 个%s' % (a.stage, len(uniq),
                                        '  [增量 --only-new]' if a.only_new else ''))
    print('=' * 96)
    if not uniq:
        print('  ⇒ 无待算因子')
        return 0

    t0 = time.time()
    bf = LE.base_fields()
    B, dates, cols, close = bf['B'], bf['dates'], bf['cols'], bf['close']
    print('面板载入完成: %d 日 x %d 股 (%.0fs)' % (len(dates), len(cols), time.time() - t0))

    STYLE = None
    if a.stage in ('strip', 'all'):
        sf = LE.style_features(B)
        STYLE = {k: sf[k] for k in ('lncap', 'lnamt')}
        del sf
        print('风格特征(lncap/lnamt) 就绪')

    # ★★ 风格相关性画像（stage=style）：15 个连续风格 + 31 个申万一级行业
    STYLE_PROF = None
    if a.stage in ('style', 'style+strip2', 'all') or a.self_test:
        import pandas as pd
        sf = LE.style_features(B)
        feat = {k: sf[k].astype('float32') for k in STYLE_SELF}
        styles = list(STYLE_SELF)
        for k in ('size', 'non_linear_size', 'momentum', 'liquidity', 'book_to_price',
                  'leverage', 'growth', 'earnings_yield', 'beta', 'residual_volatility',
                  'comovement'):
            if 'barra_' + k in B:
                feat['barra_' + k] = np.asarray(B['barra_' + k], dtype='float32')
                styles.append('barra_' + k)
        del sf
        INDH5 = os.path.join(ROOT, 'engine', 'industry.h5')
        ind_names, ind_code = [], None
        try:
            with pd.HDFStore(INDH5, 'r') as st:
                ic = st['code']
                ind_names = [str(x) for x in st['names']['name'].tolist()]
            ind = ic.reindex(index=dates, columns=cols).fillna(99.0).values
            ind_code = np.where((ind >= 0) & (ind < len(ind_names)), ind, -1).astype('int16')
            print('行业面板就绪: %d 个申万一级（industry.h5）' % len(ind_names))
        except Exception as e:
            print('[!] 行业面板不可用（%s: %s）⇒ 行业部分留空' % (type(e).__name__, e))
            ind_code = np.full((len(dates), len(cols)), -1, dtype='int16')
        STYLE_PROF = dict(feat=feat, styles=styles, ind=ind_code, ind_names=ind_names)
        print('风格画像输入就绪: %d 个连续风格（4 自有 + 11 Barra）' % len(styles))

    # ★★ 限售比例（stage=strip2）：market_cap_2 = **流通市值**（与总市值同源同目录）
    LIM = None
    if a.stage in ('strip2', 'style+strip2', 'all'):
        import pandas as pd
        cap2 = os.path.join(r'E:\rq\others\market-cap', 'market_cap_2.h5')
        try:
            df = pd.read_hdf(cap2)
            flo = df.iloc[:, 0].unstack(level=0)
            flo.index = [int(pd.Timestamp(x).strftime('%Y%m%d')) for x in flo.index]
            flo = flo.sort_index().reindex(index=dates, columns=cols).astype('float64')
            tot = np.where(B['mktcap'] > 0, B['mktcap'].astype('float64'), np.nan)
            fl = np.where(flo.values > 0, flo.values, np.nan)
            with np.errstate(invalid='ignore', divide='ignore'):
                LIM = {'lnfloat': np.log(fl).astype('float32'),
                       'lncap': np.log(tot).astype('float32'),
                       # ★ 限售比例 = ln(总市值/流通市值) ≥ 0；平均约 1.41 倍 ⇒ 约 0.34
                       'lnlimit': np.log(np.where((tot > 0) & (fl > 0), tot / fl, np.nan)).astype('float32')}
            print('限售比例(ln 总/流通) 就绪: 有效 %.1f%%' % (np.isfinite(LIM['lnlimit']).mean() * 100))
        except Exception as e:
            print('[!] 流通市值不可用（%s: %s）⇒ 跳过 strip2' % (type(e).__name__, e))
            LIM = None

    # ★★ 自检模式：只跑不变量检查，**不碰任何因子 JSON** ⇒ 立刻返回
    if a.self_test:
        return _self_test(B, dates, cols, close, STYLE_PROF)

    ok, bad = 0, []
    for i, it in enumerate(uniq, 1):
        nm = it['_nm']
        t1 = time.time()
        print('[%d/%d] %s  %s' % (i, len(uniq), nm, it['expr'][:56]))
        p = _path(nm)
        cur = {}
        if os.path.exists(p):
            try:
                cur = json.load(io.open(p, encoding='utf-8'))
            except Exception:
                cur = {}
        try:
            fac, rr, sign = _aligned(it, B, dates, cols, close, a.cost, a.window)
            if rr is None:
                bad.append(nm)
                continue
            if a.stage in ('core', 'all'):
                c = core_for(nm, fac, rr, a.cost, a.window)
                if c is None:
                    bad.append(nm)
                    continue
                c.update(pool=it['pool'], expr=it['expr'], sign=sign, gen=it['gen'])
                cur.update(c)
            if a.stage in ('strip', 'all'):
                s = strip_for(nm, fac, rr, B, dates, cols, close, a.cost, a.window, STYLE)
                if s is not None:
                    cur['strip'] = s
            # ★ 风格相关性画像（15 连续风格 × raw/neut + 31 行业 R²/排行）
            if a.stage in ('style', 'style+strip2', 'all') and STYLE_PROF is not None:
                cur['style'] = style_for(nm, fac, B, dates, cols, close,
                                         rr['ex'].index, STYLE_PROF)
            # ★ 追加剥法：剥流通市值 / 剥总市值+限售比例（并入现有 strip 的 navs）
            if a.stage in ('strip2', 'style+strip2', 'all') and LIM is not None:
                navs2, cal2 = strip2_for(nm, fac, rr, dates, cols, close,
                                         a.cost, a.window, LIM)
                if navs2:
                    st = cur.get('strip') or {'dates': _dates_of(rr['ex'].index),
                                              'navs': {}, 'calmars': {},
                                              'caliber': '期频超额净值（成本已扣）'}
                    st['navs'].update(navs2)
                    st['calmars'].update(cal2)
                    st['caliber'] = (st.get('caliber') or '') + \
                        '；floatcap=剥流通市值、caplimit=剥总市值+限售比例 ln(总/流通)'
                    cur['strip'] = st
            cur.setdefault('pool', it['pool'])
            cur.setdefault('expr', it['expr'])
            cur.setdefault('sign', sign)
            # ★ 每个名字各写一份（别名副本把 `name` 改成**它自己的编号**，免得详情页显示别人的名字）✓
            for nm_o in (alias.get(it['expr']) or [nm]):
                cc = cur if nm_o == nm else dict(cur, name=nm_o)
                cc.setdefault('name', nm_o)
                with io.open(_path(nm_o), 'w', encoding='utf-8') as f:
                    json.dump(cc, f, ensure_ascii=False, separators=(',', ':'))
            ok += 1
        except Exception as e:
            print('    [!] 失败 %s: %s: %s' % (nm, type(e).__name__, e))
            bad.append(nm)
        print('    （%.0fs · 文件 %.1f KB）'
              % (time.time() - t1, os.path.getsize(p) / 1024.0 if os.path.exists(p) else 0))
    print()
    print('完成 %d 个 · 失败 %d 个 · 用时 %.0fs' % (ok, len(bad), time.time() - t0))
    if bad:
        print('  失败清单: %s' % ', '.join(bad[:12]))
    return 0


if __name__ == '__main__':
    sys.exit(main())
