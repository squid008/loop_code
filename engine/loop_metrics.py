# -*- coding: utf-8 -*-
"""L1 指标层（形状 / 排序分）—— 单一事实源（2026-09-11 建立，批1 P0）
=====================================================================
来源：批1 标定（`ai_test/l1_shape_calib.py` + `l1_score_formula.py`，回放 1150 条历史 L2 候选）。
结论（详见 `docs/factor_roadmap.md` §8）：
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

    返回 dict(mono, best_grp, d1, d10, shape_pos, n_period)
      mono      : Spearman(档序 D1..D10, 各档平均收益)；>0 表示"因子值越高收益越高"
      best_grp  : 最优档下标（0 = D1）
      shape_pos : clip(mono,0,1) × (最优档==D1 ? 1.0 : 0.5)  ← 顶档污染降权；排序分用这个
    """
    T = RS.shape[0]
    rows = []
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
    if not rows:
        return dict(mono=np.nan, best_grp=-1, d1=np.nan, d10=np.nan,
                    shape_pos=np.nan, n_period=0)
    ex = np.nanmean(np.array(rows), axis=0)
    # 档序 D1..D10 = 10,9,...,1（无并列）⇒ 与 ex 的 Pearson 即 Spearman
    mono = (float(np.corrcoef(np.arange(n_grp, 0, -1, dtype=float), ex)[0, 1])
            if np.isfinite(ex).all() else np.nan)
    best = int(np.nanargmax(ex)) if np.isfinite(ex).any() else -1
    sp = (min(max(mono, 0.0), 1.0) * (1.0 if best == 0 else 0.5)) \
        if np.isfinite(mono) else np.nan
    return dict(mono=mono, best_grp=best, d1=float(ex[0]), d10=float(ex[-1]),
                shape_pos=(float(sp) if np.isfinite(sp) else np.nan), n_period=len(rows))


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
