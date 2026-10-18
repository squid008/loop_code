# -*- coding: utf-8 -*-
"""L1 指标层（形状 / 排序分）—— 单一事实源（2026-09-11 建立，批1 P0）
=====================================================================
来源：批1 标定（`tools/l1_shape_calib.py` + `l1_score_formula.py`，回放 1150 条历史 L2 候选）。
结论（详见 `docs/log/2026-09.md` §8）：
  * 现状排序分 `|IC_IR|×(0.25+0.75·stab)` 与 L2 Calmar 仅 **+0.167**，
    Top70 里 L2 曾通过 **4/70**、Top70 的 L2 Calmar 中位 **−0.014（≈0，几乎选不出赚钱的）**。
  * 因 `ic_ir` 与 L2 结果**负相关（−0.317）**，乘进去在**稀释 `stab` 的正信号**（`stab` 单独 +0.546）。
  * **`stab × (0.5+0.5·shape_pos)` → +0.668**（最优）；`shape_pos` 单独 +0.539。
  * **19 个入库因子 `mono` 最小值 = 0.770** → `mono ≥ 0.75` 零误杀、拦 ~27% 判死候选。
  * `novelty` 与 L2 **负相关（−0.505）** → **不进排序分**；反冗余用既有 `--decorr`（0.65~0.75）。

⚠ 本模块**不 import loop_engine**（避免循环依赖）；`rank_rows` 由本模块提供、由 `loop_engine`
  import 使用，故 `loop_engine.rank_rows` / `E.rank_rows` 对外接口保持不变。
⚠ 所有函数对 `NaN` 宽容（返回 NaN 而非抛错），由调用方决定门槛/丢弃。
"""
import numpy as np

N_GRP = 10            # 十档（与 standard_test 一致；D1 = 因子值最高档）

# 风格暴露观测四项（与 `standard_test.py`【3】风格归因同口径）
STYLE_KEYS = ('lncap', 'lnamt', 'lntr', 'lnpx')


def rank_rows(X):
    """逐行排名(0~1), NaN 置 NaN；两次 argsort。
    （原 `loop_engine.rank_rows`，2026-09-11 移入此处作单一事实源，实现逐位不变。）"""
    Xf = np.where(np.isfinite(X), X, np.inf)
    order = np.argsort(np.argsort(Xf, axis=1), axis=1).astype(np.float32)
    n = np.isfinite(X).sum(axis=1, keepdims=True)
    r = order / np.maximum(n - 1, 1)
    r[~np.isfinite(X)] = np.nan
    return r


def decile_shape(RS, R, U, n_grp=N_GRP):
    """十档单调性（**费前**；子面板近似，用于 L1 决策而非最终报告）。

    参数
      RS : (T,S) 已 `rank_rows` 的因子截面（0~1）。**调用方须已做方向对齐**（统一成"越大越好"，
           否则单调性符号会反）；本模块不做方向判断。
      R  : (T,S) 远期收益（原始值，非 rank）
      U  : (T,S) 可交易掩码(bool)
      ⚠ R/U 必须与 RS 同行。调用方可自行 `[::FWD]` 抽样：
        `rank_rows` 逐行独立 ⇒ `rank_rows(F)[::FWD] ≡ rank_rows(F[::FWD])`，两者等价。

    返回 dict(mono, best_grp, d1, d10, shape_pos, n_period, std_top, std_spread)
      mono      : Spearman(档序 D1..D10, 各档平均收益)；>0 表示"因子值越高收益越高"
      best_grp  : 最优档下标（0 = D1）
      shape_pos : clip(mono,0,1) × (最优档==D1 ? 1.0 : 0.5)  ← 顶档污染降权；排序分用这个
      d1 / d10  : **D1（因子值最高档，即多头档）** / D10（最低档）的每期平均收益
                  （费前；×252/FWD 即年化）。⚠ 分档是 `floor((1-RS)*n_grp)` ⇒
                  **D1 = RS 最大**，别把 d10 当顶档（2026-10-17 差点搞反）
      std_top   : D1（多头档）收益的**时序标准差**（每期口径；×√(252/FWD) 即年化波动）
      std_spread: 多空（**D1−D10**）收益的时序标准差
      top20_ret / top20_std : **Top20%（D1+D2）**每期平均收益 / 时序标准差
                  —— 比单档 D1 样本大一倍（≈60 只/期），降顶档噪声 ✓
      turn_top  : **D1 名单的跨期换手**（= 1 − 相邻两期名单 Jaccard 重叠率，均值）
                  —— 这是**真换手代理**，用来替代 `1−stab`（实测后者与 L2 结果无关 ✗）
                  ⚠ 若中间有期被跳过（样本不足），相邻两期可能跨了更长间隔 ⇒ 换手略偏高
    ★ 2026-10-17（用户：目标是费后年化收益，不是 IC）：d1/d10 本来就算了，只是此前
      没返回给调用方 ⇒ 现补齐 + 两个波动量，供 L1 侧计算费后收益代理。**不改变任何
      既有返回值语义**（只增键），故对现有 score/门槛**零行为影响** ✓
    """
    T = RS.shape[0]
    rows, rows20, tops = [], [], []
    for t in range(T):
        f = R[t]
        if not np.isfinite(f).any():
            continue
        m = U[t] & np.isfinite(RS[t]) & np.isfinite(f)
        if m.sum() < 100:
            continue
        dec = np.minimum((np.floor((1.0 - RS[t][m]) * n_grp)).astype(int), n_grp - 1)
        rr = f[m].astype('float64')
        rows.append([rr[dec == g].mean() if (dec == g).sum() >= 5 else np.nan
                     for g in range(n_grp)])
        _m20 = dec < 2                                  # D1 + D2 = Top20%
        rows20.append(float(rr[_m20].mean()) if _m20.sum() >= 10 else np.nan)
        tops.append(set(np.flatnonzero(m)[dec == 0].tolist()))   # D1 名单（子面板列号）
    if not rows:
        return dict(mono=np.nan, best_grp=-1, d1=np.nan, d10=np.nan,
                    shape_pos=np.nan, n_period=0, std_top=np.nan, std_spread=np.nan,
                    top20_ret=np.nan, top20_std=np.nan, turn_top=np.nan)
    arr = np.array(rows, dtype='float64')
    ex = np.nanmean(arr, axis=0)
    _top = arr[:, 0]            # ★ D1 = 因子值最高档（多头档），不是 d10
    _spr = arr[:, 0] - arr[:, -1]
    std_top = float(np.nanstd(_top)) if np.isfinite(_top).sum() >= 5 else np.nan
    std_spread = float(np.nanstd(_spr)) if np.isfinite(_spr).sum() >= 5 else np.nan
    _a20 = np.array(rows20, dtype='float64')
    top20_ret = float(np.nanmean(_a20)) if np.isfinite(_a20).any() else np.nan
    top20_std = float(np.nanstd(_a20)) if np.isfinite(_a20).sum() >= 5 else np.nan
    _ovs = [len(a & b) / max(len(a | b), 1)
            for a, b in zip(tops, tops[1:]) if a and b]
    turn_top = float(1.0 - np.mean(_ovs)) if _ovs else np.nan
    # 档序 D1..D10 = 10,9,...,1（无并列）⇒ 与 ex 的 Pearson 即 Spearman
    mono = (float(np.corrcoef(np.arange(n_grp, 0, -1, dtype=float), ex)[0, 1])
            if np.isfinite(ex).all() else np.nan)
    best = int(np.nanargmax(ex)) if np.isfinite(ex).any() else -1
    sp = (min(max(mono, 0.0), 1.0) * (1.0 if best == 0 else 0.5)) \
        if np.isfinite(mono) else np.nan
    return dict(mono=mono, best_grp=best, d1=float(ex[0]), d10=float(ex[-1]),
                shape_pos=(float(sp) if np.isfinite(sp) else np.nan), n_period=len(rows),
                std_top=std_top, std_spread=std_spread,
                top20_ret=top20_ret, top20_std=top20_std, turn_top=turn_top)


def l1_score(stab, ic_ir, shape_pos=None, mode='old'):
    """L1 排序分。

    mode='old'  : `|IC_IR| × (0.25 + 0.75·clip(stab,0,1))` —— **现状，逐位不变**（保留供对拍）
    mode='new'  : `clip(stab,0,1) × (0.5 + 0.5·clip(shape_pos,0,1))` —— 2026-09-11 标定选中
                  （相关性 +0.167 → +0.668；**不含 `ic_ir`**，IC 只留作准入门槛）
    """
    st = np.clip(np.asarray(stab, dtype='float64'), 0, 1)
    if mode == 'new':
        sp = np.clip(np.asarray(shape_pos, dtype='float64'), 0, 1)
        return np.nan_to_num(st, nan=0.0) * (0.5 + 0.5 * np.nan_to_num(sp, nan=0.0))
    return np.abs(np.asarray(ic_ir, dtype='float64')) * (0.25 + 0.75 * st)


def neutralize_rows(Y, F, min_n=50):
    """逐行(截面)对风格做 OLS 回归取残差：`Y - X·β`，`X = [1, F...]`。

    参数
      Y : (T,S) 被中性化的量（如**远期收益**，原始值）
      F : (T,S) 或 [F1, F2, ...]，风格暴露（如 lncap / lnamt）
    返回 (T,S) 残差；NaN 位置仍为 NaN。

    退化处理：某行有效样本 < `min_n`、或设计矩阵奇异 -> **该行保留原值**（退化为原始口径），
    而不是返回 NaN —— 否则会连带丢掉 `decile_shape` 的整期样本。"""
    Y = np.asarray(Y, dtype='float64')
    Fs = [np.asarray(f, dtype='float64') for f in
          (F if isinstance(F, (list, tuple)) else [F])]
    out = Y.copy()
    for t in range(Y.shape[0]):
        cols = [Y[t]] + [f[t] for f in Fs]
        m = np.isfinite(cols[0])
        for c in cols[1:]:
            m &= np.isfinite(c)
        if m.sum() < min_n:
            continue
        X = np.column_stack([np.ones(int(m.sum()))] + [c[m] for c in cols[1:]])
        y = cols[0][m]
        try:
            beta, *_ = np.linalg.lstsq(X, y, rcond=None)
        except np.linalg.LinAlgError:
            continue
        out[t, m] = y - X @ beta
    return out


def neutral_rank(X, Zs, min_n=100):
    """逐行(截面)**秩中性化** —— 与 `standard_test.py`【6】`neutralize()` **逐位同口径**。

    步骤（严格对齐 standard_test）：
      1. `Y = rank_rows(X)`；`Zk = rank_rows(Zs[k])`
      2. 逐行 OLS：`Y_t ≈ [1, Z_t]·β`  →  残差 `e_t = Y_t − Ŷ_t`
      3. **对残差再 `rank_rows`**（★关键差别：本模块既有 `neutralize_rows` 不重排，
         那是用于"中性化远期收益"；剥风格判据必须重排，否则与 standard_test 报告对不上）
    某行有效样本 < `min_n` -> 该行留 NaN（standard_test 的 `continue` 行为）。

    参数
      X : (T,S) 因子值（**调用方须已方向对齐**；rank 后回归，故原尺度无影响）
      Zs: [(T,S), ...] 风格特征（如 lncap / lnamt），同样 rank 化后作回归量
    返回 (T,S) float32 —— 已重排的残差(0~1)，可直接喂回测/`evaluate_real`。
    """
    Y = rank_rows(np.asarray(X, dtype='float64')).astype('float64')
    Zl = [rank_rows(np.asarray(z, dtype='float64')).astype('float64') for z in Zs]
    out = np.full(Y.shape, np.nan)
    for t in range(Y.shape[0]):
        m = np.isfinite(Y[t])
        for z in Zl:
            m &= np.isfinite(z[t])
        k = int(m.sum())
        if k < min_n:
            continue
        A = np.column_stack([np.ones(k)] + [z[t][m] for z in Zl])
        try:
            coef, *_ = np.linalg.lstsq(A, Y[t][m], rcond=None)
        except np.linalg.LinAlgError:
            continue
        out[t, m] = Y[t][m] - A @ coef
    return rank_rows(out)


def style_expo(RS, SS, min_n=30):
    """逐期截面秩相关(因子 vs 风格)的期均值 —— 与 `standard_test.py`【3】风格归因同口径。

    参数
      RS : (T,S) 因子秩(0~1; **调用方须已方向对齐**)
      SS : (T,S) 风格特征秩(0~1), 由 `STYLE_KEYS` 四项各一
    返回 float; 有效期不足 -> NaN。
      负值 = 因子偏「小市值 / 低成交额 / 低换手 / 低价」；正相反。

    全向量化(逐期去均值后按行求 Pearson, NaN 位不参与) —— 避免 T 次 python 循环,
    也避免每期调一次 np.corrcoef(见 `ai_test/qa_style_obs.py` 与朴素实现逐位对拍)。
    """
    m = np.isfinite(RS) & np.isfinite(SS)
    n = m.sum(axis=1).astype('float64')
    nn = np.maximum(n, 1.0)
    A = np.where(m, RS, 0.0).astype('float64')
    Bm = np.where(m, SS, 0.0).astype('float64')
    ca = np.where(m, A - (A.sum(axis=1) / nn)[:, None], 0.0)
    cb = np.where(m, Bm - (Bm.sum(axis=1) / nn)[:, None], 0.0)
    num = (ca * cb).sum(axis=1)
    den = np.sqrt((ca ** 2).sum(axis=1) * (cb ** 2).sum(axis=1))
    ok = (n >= min_n) & (den > 1e-12)
    if not ok.any():
        return np.nan
    return float(np.mean(num[ok] / den[ok]))
