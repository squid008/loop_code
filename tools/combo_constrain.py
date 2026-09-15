# -*- coding: utf-8 -*-
"""combo_constrain.py — 组合构建约束：把「合成因子」变成可产品化的组合（roadmap §8.39 瓶颈 B）

**为什么需要它**：合成因子 neu-B 已是产品级（超额 +6.79% / Calmar 1.193 / 剥风格后仍 0.673），
  但**选中股票的市值分位只有 15%**（raw 版 1.7%）⇒ 不过是**小盘暴露**在赚钱，不能直接产品化。
  根因：成分因子虽然已对 `rank(lncap)+rank(lnamt)` 秩中性化，但**最后一步「取全池前 10%」本身
  会重新引入市值倾斜** ⇒ 必须在**组合层**再约束一次。

**⚠ 本工具不改任何引擎代码**（纯组合层）。数据直接读：
  · `engine/panel.h5`    → close / mktcap
  · `engine/universe.h5` → 可交易池
  · `engine/industry.h5` → **申万一级行业编码**（由 `tools/build_industry.py` 从 BARRA 源重建；
     `barra.h5` 里**没有**行业 —— `build_barra.py` 当初把行业丢掉了，见该脚本注释）
  · ⚠ **不用** `ml_common.load()` 的 `G`：它的 `industry_names()` 因前缀不匹配而失效，
    `G` 实际是「11 个风格面板 >0.5 的编码」⇒ **静默错误**（已在 `docs/loop_todo.md` 记录）

**口径对齐 `engine/factor_miner`**：`FWD=5` 调仓 · top-decile · 成本 单边 `0.001`
**方案阶梯**（都是 5 日调仓、选 `top` 比例）：
  | 方案 | 选股 | 需要行业 |
  |---|---|---|
  | **S0** 现状 | 全池分数 top | 否 |
  | **M1** 市值中性 | 分数对 `lnmc` 取残差 → 全池 top | 否 |
  | **S1** 行业中性 | **行业内**按行业市值占比配额选 | ✅ |
  | **S2** S1+市值中性 | 分数对 `[1, lnmc, 行业]` 取残差 → 行业内选 | ✅ |
  | **S3** S2+权重上限 | S2 + 单票 ≤ `--max_w` | ✅ |

输出：`tools/_combo_constrain.md`（**双口径超额** + Calmar/Sharpe/换手 + **选中市值分位** + **行业偏离**）
"""
import argparse
import io
import os
import sys
import time

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ENGINE = os.path.join(ROOT, 'engine')
sys.path.insert(0, ENGINE)        # ★ 必须！否则 `import loop_pools`（引擎的池定义模块）会失败

import numpy as np                                     # noqa: E402
import pandas as pd                                    # noqa: E402

PANEL = os.path.join(ENGINE, 'panel.h5')
UNIV = os.path.join(ENGINE, 'universe.h5')
INDH5 = os.path.join(ENGINE, 'industry.h5')
OUT_MD = os.path.join(HERE, '_combo_constrain.md')
COST_ONE_WAY = 0.001
ANN_DAYS = 243.0

# ★★ 真实指数（用于"指数增强"口径）—— `E:\rq\bundle\indexes.h5` 是 **h5py 结构**：
#   每个 key = 一个指数代码，值 = 结构化数组，字段
#   `('datetime','<i8')` 的**格式是 `YYYYMMDDHHMMSS`**（实测 `20050104000000`）⇒ 取 `//1000000` 得 YYYYMMDD。
INDEXES = r'E:\rq\bundle\indexes.h5'
IDXMAP = {'300': '000300.XSHG', '500': '000905.XSHG', '1000': '000852.XSHG'}


def load_index_close(code):
    """读指数收盘价 → Series(index=YYYYMMDD int, value=close)。读不到返回 None。"""
    if not code or not os.path.exists(INDEXES):
        return None
    try:
        import h5py
        with h5py.File(INDEXES, 'r') as f:
            if code not in f:
                return None
            a = f[code][()]
        ymd = (a['datetime'] // 1000000).astype('int64')
        s = pd.Series(a['close'].astype('float64'), index=ymd)
        s = s[~s.index.duplicated()].sort_index()
        return s
    except Exception as e:
        print('  [!] 指数 %s 读取失败(%s: %s)' % (code, type(e).__name__, e))
        return None


def load_data():
    with pd.HDFStore(PANEL, 'r') as st:
        close = st['close']
        mktcap = st['mktcap']
    with pd.HDFStore(UNIV, 'r') as st:
        U = st['universe']
    U = U.reindex(index=close.index, columns=close.columns).fillna(False)
    ind, names = None, []
    if os.path.exists(INDH5):
        with pd.HDFStore(INDH5, 'r') as st:
            ind = st['code'].reindex(index=close.index, columns=close.columns)
            names = [str(x) for x in st['names']['name'].tolist()]
    return close, mktcap, U, ind, names


def size_pct_of(mc_row, picks):
    """选中股票在**全池**里的市值分位均值（0~1；越小越偏小盘）。"""
    if len(picks) == 0:
        return np.nan
    m = mc_row[np.isfinite(mc_row) & (mc_row > 0)]
    if m.size < 50:
        return np.nan
    p = pd.Series(m).rank(pct=True)
    sel = mc_row[picks]
    ok = np.isfinite(sel) & (sel > 0)
    if not ok.any():
        return np.nan
    return float(pd.Series(sel[ok]).rank(pct=True).mean())


def run():
    ap = argparse.ArgumentParser()
    ap.add_argument('--fac', default=os.path.join(HERE, '_combo_all_neu_B.pkl'))
    ap.add_argument('--modes', default='s0,s05,m1,s1,s2,s3')
    ap.add_argument('--top', type=float, default=0.10)
    ap.add_argument('--fwd', type=int, default=5)
    ap.add_argument('--max_w', type=float, default=0.02)
    ap.add_argument('--cost', type=float, default=COST_ONE_WAY)
    # ★ 样本起点必须与 `engine/factor_miner.START`（=20180101）对齐 ——
    #   否则本工具的数字与 `evaluate_real` / roadmap 里的数字**不可比**
    #   （2026-09-14 实录：全样本起点下 S0 得 +9.77%，与 §8.39 的 +6.79% 看着冲突，
    #     其实只是**样本期不同**）。
    ap.add_argument('--start', type=int, default=20180101)
    # ★ 持仓缓冲：降换手的标准做法。`0` = 关（默认，便于与历史数字对齐）；
    #   例如 `--buffer=0.5` ⇒ 上期持仓只要分数还在 top 15% 内就保留，不必回到 top 10%。
    ap.add_argument('--buffer', type=float, default=0.0)
    # ★★ `--pool`：把可交易域**限制在某个指数成分股内**（`all` = 不限制）。
    #   为什么必须做这件事（2026-09-14）：「市值加权基准」是**全A 可交易股的市值加权**，
    #   **不等于沪深300/中证500** —— 组合持有全A top-decile（含大量小盘），与 300 成分几乎不重叠。
    #   ⇒ 要回答「能不能做**指数增强**」，必须用**成分内**口径（这正是 `_combo_check_report.md` 的做法，
    #     那里给出的结论是：**300 成分内 −0.81%（无效）/ 500 成分内 +5.91%（可用）**）。
    #   实现：直接复用引擎的 **`loop_pools.pool_mask`**（只读，**不修改引擎**，不影响在跑的进程）。
    ap.add_argument('--pool', default='all')
    # ★ 显式指定基准指数（默认按 `--pool` 自动取 300/500/1000 对应指数）
    ap.add_argument('--index', default='')
    a = ap.parse_args()

    t0 = time.time()
    close, mktcap, U, ind, INAMES = load_data()
    dates, cols = close.index.values, close.columns
    print('=' * 88)
    print('组合构建约束  因子=%s' % os.path.basename(a.fac))
    print('=' * 88)
    print('  面板 %d 日 x %d 股 · 行业面板 %s'
          % (len(dates), len(cols),
             ('%d 个行业 ✓' % len(INAMES)) if ind is not None else '**缺失**（行业中性不可用）'))
    F = pd.read_pickle(a.fac)
    F = F.reindex(index=dates, columns=cols)
    if not isinstance(F, pd.DataFrame):
        F = pd.DataFrame(np.asarray(F, dtype='float64'), index=dates, columns=cols)
    print('  因子有效值 %.1f%% · 载入 %.0fs'
          % (100 * np.isfinite(F.values).mean(), time.time() - t0))

    # ★ 成分股掩码（`--pool != all` 时把域限制在成分内）
    Pv = None
    if a.pool and a.pool != 'all':
        try:
            import loop_pools as LP
            Pm = LP.pool_mask(a.pool, close.index.values, list(close.columns))
            Pv = Pm.values if hasattr(Pm, 'values') else Pm
            print('  池=%s 成分掩码：覆盖 %.1f%% 的 面板格' % (a.pool, 100 * Pv.mean()))
        except Exception as e:
            print('  [!] 池掩码失败(%s: %s) -> 退回全A' % (type(e).__name__, e))
            Pv = None

    # ★ 真实指数基准（"指数增强"口径）—— 自动按池选：300→000300 / 500→000905 / 1000→000852
    icode = a.index or IDXMAP.get(a.pool, '')
    ISER = load_index_close(icode) if icode else None
    RIDX = None
    if ISER is not None:
        ISER = ISER.reindex(dates)
        RIDX = (ISER.shift(-(1 + a.fwd)) / ISER.shift(-1) - 1.0).values
        print('  基准指数 %s：%d/%d 日有效' % (
            icode, int(np.isfinite(RIDX).sum()), len(dates)))
    else:
        print('  （无基准指数 → 只有"池内等权/池内市值加权"两个口径）')

    Fv = F.values.astype('float64')
    Uv = U.values
    if Pv is not None:
        Uv = Uv & Pv
    MCv = mktcap.values
    lnmc = np.log(np.where(MCv > 0, MCv, np.nan))
    Gv = (ind.values if ind is not None else None)

    t_start = int(np.searchsorted(dates, a.start))
    rb = list(range(t_start, len(dates) - a.fwd - 2, a.fwd))
    print('  样本期 %d ~ %d（对齐 factor_miner.START=%d）· 调仓期 %d'
          % (int(dates[t_start]), int(dates[-1]), a.start, len(rb)))
    modes = [m.strip().lower() for m in a.modes.split(',') if m.strip()]
    need_ind = any(m in ('s1', 's2', 's3') for m in modes)
    if need_ind and Gv is None:
        print('  ⚠ 行业面板缺失 ⇒ 自动去掉 s1/s2/s3（先跑 build_industry.py）')
        modes = [m for m in modes if m not in ('s1', 's2', 's3')]

    rec = {m: dict(pn=[], ben=[], bmc=[], bidx=[], turn=[], spct=[], idev=[], nh=[], ov0=[])
           for m in modes}
    prev = {m: set() for m in modes}
    n_used = 0

    for t in rb:
        univ = Uv[t] & np.isfinite(Fv[t])
        if univ.sum() < 100:
            continue
        r = (close.shift(-(1 + a.fwd)) / close.shift(-1) - 1.0).values[t]
        ok = univ & np.isfinite(r)
        if ok.sum() < 100:
            continue
        n_used += 1
        ix = np.where(ok)[0]
        f_t = Fv[t][ix]
        mc_t = lnmc[t][ix]
        mc_raw = MCv[t][ix]
        # ⚠ NaN 不能直接 astype('int32')（会出 RuntimeWarning 且值不可预期）
        #   ⇒ 先填 -1 再转（-1 = 无行业）
        g_t = (np.nan_to_num(Gv[t][ix], nan=-1.0).astype('int32')
               if Gv is not None else np.full(len(ix), -1, dtype='int32'))
        n_hold = max(int(len(ix) * a.top), 20)
        rr = r[ix]

        # 基准权重（该调仓日可交易池内）
        w_cap = np.where(np.isfinite(mc_raw) & (mc_raw > 0), mc_raw, 0.0)
        w_cap = w_cap / w_cap.sum() if w_cap.sum() > 0 else np.full(len(ix), 1 / len(ix))
        w_ew = np.full(len(ix), 1 / len(ix))
        gname_idx = range(len(INAMES)) if INAMES else range(32)

        def resid(y, use_ind):
            X = np.ones((len(y), 2 + (len(INAMES) if use_ind else 0)))
            X[:, 1] = np.nan_to_num(mc_t, nan=float(np.nanmean(mc_t)))
            if use_ind:
                gg = np.where(g_t >= 0, np.minimum(g_t, len(INAMES) - 1), 0)
                X[np.arange(len(y)), 2 + gg] = 1.0
            m = np.isfinite(y)
            if m.sum() < 100:
                return None
            coef, *_ = np.linalg.lstsq(X[m], y[m], rcond=None)
            out = np.full_like(y, np.nan)
            out[m] = y[m] - X[m] @ coef
            return out

        def pick_all(fs):
            if fs is None or not np.isfinite(fs).any():
                return None
            o = np.argsort(-np.nan_to_num(fs, nan=-1e18))[:n_hold]
            return np.array(sorted(o.tolist())), np.full(len(o), 1.0 / len(o))

        def pick_by_ind(fs):
            if fs is None or not np.isfinite(fs).any():
                return None
            sel = []
            tot = max(w_cap.sum(), 1e-12)
            for gi in gname_idx:
                m = g_t == gi
                if not m.any():
                    continue
                q = int(round(n_hold * w_cap[m].sum() / tot))
                q = max(0, min(q, int(m.sum())))
                if q == 0:
                    continue
                sub = np.where(m)[0]
                sel.extend(sub[np.argsort(-np.nan_to_num(fs[sub], nan=-1e18))][:q].tolist())
            if not sel:
                return None
            sel = np.array(sorted(set(sel)))
            if len(sel) > n_hold:
                sel = np.array(sorted(sel[np.argsort(-np.nan_to_num(fs[sel], nan=-1e18))][:n_hold].tolist()))
            return sel, np.full(len(sel), 1.0 / len(sel))

        f_min = resid(f_t, use_ind=False)                  # 仅 lnmc 中性
        f_both = resid(f_t, use_ind=True) if Gv is not None else None
        plans = {
            's0': pick_all(f_t),
            'm1': pick_all(f_min),
            's1': pick_by_ind(f_t),
            's2': pick_by_ind(f_both),
            's3': pick_by_ind(f_both),
        }

        # ★★ S05 = **只做行业权重校正，不动选股**（用于把 S0→S1 的差**分解**成两个效应）：
        #   效应 A「行业配比倾斜」= S0 − S05（只放开行业约束就能吃到的那块）
        #   效应 B「行业内选股被截断」= S05 − S1（因为名额限制而选不到最强信号）
        #   ⚠ 近似：只对**组合已覆盖**的行业做缩放；未覆盖行业的基准权重按比例分摊给已覆盖行业
        #     （若某行业组合一只都没选，则**无法**靠缩放实现，那部分必须靠 S1 的"补名额"）
        pl0 = plans.get('s0')
        if pl0 is not None and len(INAMES):
            sel0, _ = pl0
            wi = np.zeros(len(INAMES))
            for o in sel0:
                if g_t[o] >= 0:
                    wi[min(g_t[o], len(INAMES) - 1)] += 1.0
            wi = wi / max(wi.sum(), 1e-12)
            wb = np.zeros(len(INAMES))
            for o in range(len(ix)):
                if g_t[o] >= 0:
                    wb[min(g_t[o], len(INAMES) - 1)] += w_cap[o]
            wb = wb / max(wb.sum(), 1e-12)
            cov = wi > 0
            if cov.any():
                scale = np.zeros(len(INAMES))
                scale[cov] = wb[cov] / wi[cov]           # 行业内缩放系数
                w05 = np.array([(1.0 / len(sel0)) * (scale[g_t[o]] if g_t[o] >= 0 and cov[g_t[o]] else 0.0)
                                for o in sel0])
                if w05.sum() > 0:
                    # 把"未覆盖行业"该有的权重按比例补回已覆盖行业 ⇒ 权重和归 1
                    w05 = w05 * (wb[cov].sum() / max(w05.sum(), 1e-12))
                    w05 = w05 / w05.sum()
                    plans['s05'] = (sel0, w05)

        for m in modes:
            pl = plans.get(m)
            if pl is None:                     # ⚠ `pick_*` 失败时返回的是 `None`（不是二元组）
                continue                       #   ⇒ 不能 `plans.get(m, (None,None))` 解包
            sel, w = pl
            if sel is None:
                continue
            if m == 's3':
                w = np.minimum(w, a.max_w)
                w = w / w.sum()
            # ★ 持仓缓冲（降换手）：上期持仓里"分数仍在 top(1+buffer)"的**保留**，
            #   只有当它跌出这个更宽的带子才卖 ⇒ 减少边界反复进出。
            #
            # ★★★ 2026-09-15 修「**索引空间混淆**」BUG（`--buffer` 从未跑通的原因）：
            #   · 本函数内有**两套索引**（务必分清，我误判过一次，见下）：
            #       ① **池内索引**：`0..len(ix)-1` —— `f_t`/`mc_t`/`g_t`/`rr`/`w_cap`/`sel` 用它
            #          （注意 `f_t = Fv[t][ix]` **已先行索引**，所以 `f_t` 是池内的！）
            #       ② **全局行号**：`ix[站]` 的值 —— `prev[m]`/`hold` 存的是它
            #   · **真 BUG**：`cand` 直接拿**池内** `sel` 去和**全局** `held` 比 ⇒ `newsel` 混两套空间
            #     ⇒ 下面 `ix[sel]` **越界** ⇒ `IndexError: index 901 is out of bounds for axis 0
            #     with size 893`（实测 `--buffer=0.25` 必崩）✗
            #   · 修法：把 `cand` 的来源转成**全局行号**（`ix[sel]`），全程统一；
            #     最后用**逆映射**还原成池内索引（`ix` 未必有序 ⇒ 不能用 `searchsorted`）✓
            #   · ⚠ **我误报过一次**：曾以为 `keep_top` 的 `argsort(-f_t)` 排序的是"全局 f"而 `thr` 是池内
            #     语义 ⇒ 改动后 `f_t[ix]` 立刻**越界**（`f_t` 是池内的，长度 893）⇒ 证明**原写法正确**，
            #     已改回 ✓ ⇒ **教训：改代码前必须确认每个数组是「池内还是全局」**，别凭名字猜 ✗
            if a.buffer > 0 and prev[m]:
                thr = max(int(len(ix) * a.top * (1.0 + a.buffer)), 20)
                # `f_t` 是**池内**数组 ⇒ `argsort` 得池内序号，`ix[...]` 转全局行号 ✓（原写法即正确）
                keep_top = set(ix[np.argsort(-np.nan_to_num(f_t, nan=-1e18))[:thr]].tolist())
                held = sorted(prev[m] & keep_top)        # 全局 ∩ 全局 ✓
                sel_g = ix[sel]                          # ★ 唯一修复点：池内 → 全局
                cand = [o for o in sel_g.tolist() if o not in held]
                need = max(n_hold - len(held), 0)
                newsel = held + cand[:need]
                if len(newsel) < n_hold:                 # 不够就从上期持仓里补（保持仓位）
                    extra = [o for o in prev[m] if o not in newsel][:n_hold - len(newsel)]
                    newsel += extra
                if newsel:
                    # ★ 全局行号 → 池内索引 逆映射
                    _pos = {int(g): i for i, g in enumerate(ix)}
                    sel = np.array(sorted(_pos[int(g)] for g in set(newsel) if int(g) in _pos))
                    w = np.full(len(sel), 1.0 / len(sel))
            hold = set(ix[sel].tolist())
            turn = 1.0 if not prev[m] else 1.0 - len(hold & prev[m]) / max(len(hold), 1)
            prev[m] = hold
            gr = float(np.nansum(w * np.nan_to_num(rr[sel], nan=0.0)))
            rec[m]['pn'].append(gr - turn * (a.cost * 2))
            rec[m]['ben'].append(float(np.nansum(w_ew * np.nan_to_num(rr, nan=0.0))))
            rec[m]['bmc'].append(float(np.nansum(w_cap * np.nan_to_num(rr, nan=0.0))))
            # ⚠ 一律 append（缺的时候记 nan）—— 这样各列**长度对齐**，
            #   汇总时用 `isfinite` 掩码取共同可用期，不会因为错位算错。
            rec[m]['bidx'].append(float(RIDX[t]) if RIDX is not None else np.nan)
            rec[m]['turn'].append(turn)
            # 与 S0（无行业约束）的**持仓重叠率** —— 直观反映"行业约束改掉了多少选股"
            _p0 = plans.get('s0')
            if _p0 is not None:
                h0 = set(ix[_p0[0]].tolist())
                rec[m]['ov0'].append(len(hold & h0) / max(len(hold), 1))
            rec[m]['spct'].append(size_pct_of(MCv[t], ix[sel]))
            rec[m]['nh'].append(len(hold))
            # 行业偏离（组合 vs 基准：都按行业归总权重）
            wi = np.zeros(max(len(INAMES), 1))
            wb = np.zeros(max(len(INAMES), 1))
            for o, ww in zip(sel, w):
                if g_t[o] >= 0:
                    wi[min(g_t[o], len(INAMES) - 1)] += ww
            for o in range(len(ix)):
                if g_t[o] >= 0:
                    wb[min(g_t[o], len(INAMES) - 1)] += w_cap[o]
            rec[m]['idev'].append(float(np.abs(wi - wb).max()))

    # ---------- 汇总 ----------
    NAME = {'s0': 'S0 现状(全池 top)', 's05': 'S05 仅行业权重校正', 'm1': 'M1 市值中性',
            's1': 'S1 行业中性', 's2': 'S2 +市值中性', 's3': 'S3 +权重上限%.1f%%' % (a.max_w * 100)}
    L = ['# 组合构建约束对照（roadmap §8.39 瓶颈 B）', '',
         '因子 `%s` · `FWD=%d` · top `%.0f%%` · 成本单边 `%.4f` · 调仓期数 `%d`'
         % (os.path.basename(a.fac), a.fwd, a.top * 100, a.cost, n_used), '',
         '| 方案 | 年化超额(池内等权) | **年化超额(真实指数)** | 年化超额(池内市值) | Calmar(等权) | Sharpe(等权) | 换手 | **选中市值分位** | 行业最大偏离 | 与S0重叠 | 持仓 |',
         '|---|---|---|---|---|---|---|---|---|---|---|']
    print('\n' + '=' * 112)
    print('%-22s %13s %15s %14s %10s %9s %7s %11s %10s %9s %5s'
          % ('方案', '超额(池等权)', '**超额(真实指数)**', '超额(池市值)', 'Calmar', 'Sharpe',
             '换手', '市值分位', '行业偏离', '与S0重叠', '持仓'))
    print('-' * 112)
    for m in modes:
        v = rec[m]
        if not v['pn']:
            continue
        pn, ben, bmc = np.array(v['pn']), np.array(v['ben']), np.array(v['bmc'])
        ex = pn - ben
        ne = (1 + ex).cumprod()
        exm = (1 + pn).cumprod() / (1 + bmc).cumprod() - 1
        yrs = len(pn) * a.fwd / ANN_DAYS
        ann_e = ne[-1] ** (1 / yrs) - 1
        # ⚠ 池内（票少）时"池内市值加权基准"可能被少数大盘股主导 ⇒ 净值甚至**归负**
        #   ⇒ 那种情况下这个口径**不可信**，标出来而不是给个假的 nan
        if exm[-1] <= 0:
            ann_m = np.nan
            _mk_bad = True
        else:
            ann_m = exm[-1] ** (1 / yrs) - 1
            _mk_bad = False
        dd = (ne / np.maximum.accumulate(ne) - 1).min()
        cal = ann_e / abs(dd) if dd < 0 else np.nan
        shp = ex.mean() / ex.std() * np.sqrt(ANN_DAYS / a.fwd) if ex.std() > 0 else np.nan
        turn = float(np.mean(v['turn']))
        spct = float(np.nanmean(v['spct']))
        idev = float(np.nanmean(v['idev']))
        ov0 = float(np.nanmean(v['ov0'])) if v['ov0'] else np.nan
        _ms = ('不可信' if _mk_bad else '%+.2f%%' % (ann_m * 100))
        # ★ 真实指数口径（"能不能做指数增强"的**直接答案**）
        ann_i, _is = np.nan, '—'
        bi = np.array(v['bidx']) if v['bidx'] else np.array([])
        if bi.size and np.isfinite(bi).any():
            mk = np.isfinite(bi)
            n = int(mk.sum())
            ni = (1 + pn[mk]).cumprod() / (1 + bi[mk]).cumprod() - 1
            yi = n * a.fwd / ANN_DAYS
            if ni[-1] > -1 and yi > 0:
                ann_i = (1 + ni[-1]) ** (1 / yi) - 1
                _is = '%+.2f%%' % (ann_i * 100)
        print('%-22s %12.2f%% %14s %13s %10.3f %9.3f %6.1f%% %10.1f%% %9.1f%% %8.1f%% %5.0f'
              % (NAME.get(m, m), ann_e * 100, _is, _ms, cal, shp, turn * 100,
                 spct * 100, idev * 100, ov0 * 100, np.mean(v['nh'])))
        L.append('| %s | **%+.2f%%** | **%s** | %s | %.3f | %.3f | %.1f%% | **%.1f%%** | %.1f%% | %.1f%% | %.0f |'
                 % (NAME.get(m, m), ann_e * 100, _is, _ms, cal, shp, turn * 100,
                    spct * 100, idev * 100, ov0 * 100, np.mean(v['nh'])))
    L += ['', '读法：`超额(等权)` = 组合 − 全池**等权**基准（**规模中性，主判据**）；'
          '`超额(市值)` = 组合 − **市值加权**基准（≈真实指数口径）。',
          '`选中市值分位` 越低越偏小盘；`行业最大偏离` 越小越接近行业中性。']

    # ★★ 代价分解：把 S0→S1 的差拆成「行业配比倾斜」与「行业内选股被截断」
    def _ann(m):
        v = rec[m]
        if not v['pn']:
            return None
        pn, ben, bmc = np.array(v['pn']), np.array(v['ben']), np.array(v['bmc'])
        yrs = len(pn) * a.fwd / ANN_DAYS
        return (float(((1 + pn - ben).cumprod()[-1]) ** (1 / yrs) - 1),
                float((((1 + pn).cumprod() / (1 + bmc).cumprod())[-1]) ** (1 / yrs) - 1))
    # ★ 2026-09-15 修：原先硬编码 `('s0','s05','s1')` ⇒ 用 `--modes` 指定不含 s05 的组合时
    #   `_ann('s05')` 会 `rec['s05']` ⇒ **KeyError 崩掉**（`--modes=s0,s1` 实测复现）✗
    #   ⇒ 改为先判键存在（`and` 短路）⇒ 只有三个模式都在时才输出「代价分解」表 ✓
    if all(m in rec and _ann(m) for m in ('s0', 's05', 's1')):
        s0, s05, s1 = _ann('s0'), _ann('s05'), _ann('s1')
        L += ['', '## ★★ 代价分解：S0 → S1 的差来自哪里', '',
              '| 环节 | 超额(等权) | 超额(市值) | 说明 |', '|---|---|---|---|',
              '| **S0** 无行业约束 | **%+.2f%%** | **%+.2f%%** | 现状 |' % (s0[0] * 100, s0[1] * 100),
              '| **S05** 只校正行业权重（选股不变） | %+.2f%% | %+.2f%% | 去掉「行业配比倾斜」 |'
              % (s05[0] * 100, s05[1] * 100),
              '| **S1** 行业内选股 + 行业配额 | %+.2f%% | %+.2f%% | 再去掉「行业内选股自由度」 |'
              % (s1[0] * 100, s1[1] * 100),
              '',
              '- **效应 A「行业配比倾斜」= S0 − S05 = 等权 %+.2f pct / 市值 %+.2f pct**'
              % ((s0[0] - s05[0]) * 100, (s0[1] - s05[1]) * 100),
              '- **效应 B「行业内选股被截断」= S05 − S1 = 等权 %+.2f pct / 市值 %+.2f pct**'
              % ((s05[0] - s1[0]) * 100, (s05[1] - s1[1]) * 100),
              '',
              '> 读法：**A 大** ⇒ 超额主要靠"敢押某几个行业"（指数增强里会被基准扣回去）；'
              '**B 大** ⇒ 超额靠"全池自由挑最强信号"（行业中性会截断这部分）。',
              '> ⚠ S05 是**近似**：只对组合已覆盖的行业做缩放，未覆盖行业的基准权重按比例分摊回已覆盖行业。']
    L += ['', '（`与S0重叠` = 持仓与 S0 的重叠率，反映"行业约束改掉了多少选股"）']
    # 输出按池分文件（否则多池并行会互相覆盖）
    out_md = (OUT_MD if a.pool == 'all'
              else OUT_MD.replace('.md', '_pool%s.md' % a.pool))
    L.insert(0, '> **可交易域**：`--pool=%s`%s\n'
             % (a.pool, '（全A）' if a.pool == 'all' else '（**成分股内**）'))
    io.open(out_md, 'w', encoding='utf-8').write('\n'.join(L))
    print('\n[DONE] -> %s   （%d 期, 用时 %.0fs）' % (out_md, n_used, time.time() - t0))
    return 0


if __name__ == '__main__':
    sys.exit(run())
