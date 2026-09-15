# -*- coding: utf-8 -*-
"""L1 形状门槛 / novelty 标定 —— 回放 loop_archive.csv 的 1150 条唯一 L2 候选（只读，不改引擎）。
=====================================================================================
目的（P0 批1 第 1 步）：
  Q1 被 L2 判死的候选里, 有多少会在 L1 就被"十档单调性"拦住?（形状门槛是否对症）
  Q2 passed=True 的候选单调性分布如何?（门槛会不会误杀）
  Q3 加 novelty 后, 低 IC 高独立的候选能否进 Top 池?（P1 验证）

口径（与引擎 L1 同源, 差异仅"调仓日采样", 见下）：
  * 子面板 = `base_fields()['B_sub']`（L1_ROWS = 2018 起连续行, L1_COLS = 2000 随机股）
  * **全部指标在 `[::FWD]` 调仓日子样本上算**（418 期 × 2000 股）。
    因 `rank_rows` 逐行独立 => `rank_rows(F)[::FWD] == rank_rows(F[::FWD])`，
    故"先抽样再排名"与"排名后抽样"**完全等价**；与引擎 L1 的唯一差异是
    引擎 IC 用全部 2094 天、此处用 418 个调仓日 — 对"排序/阈值标定"无影响且更快。
  * ic / ic_ir = 调仓日截面 rank-rank Pearson 的均值/IR（同 `batch_ic` 的算法）
  * stab        = `factor_stability(v)`（引擎 L1 原函数）
  * novelty     = 1 - max|corr(rank_rows(v[::FWD]), bank 各因子同口径 rank)|（decorr 池化 Pearson）
  * 形状        = 调仓日"十档单调性"（费前；B_sub 无 limit 字段故不做涨停/停牌过滤）
      -> 用 F25~F29 的完整面板实测值做校验（`validate` 模式）

用法：
  python l1_shape_calib.py collect [--limit=N]   # 慢(可断点续跑), 建议 Start-Process 后台
  python l1_shape_calib.py report                # 快, 读 CSV 出结论
  python l1_shape_calib.py validate              # 用 F25~F29 校验形状代理精度
"""
import gc
import os
import pickle
import shutil
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), 'engine'))
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
import loop_engine as E
import __main__ as _m

_m.Node = E.Node

# ★ 2026-09-15：原为硬编码 `D:\loop_code\...` ⇒ 改为从 `__file__` 派生 ✓
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARCH = os.path.join(_ROOT, 'docs', 'loop_archive.csv')
STATE = os.path.join(_ROOT, 'engine', 'loop_state.pkl')
TMP = os.path.join(_ROOT, 'ai_test', '_state_copy_calib.pkl')
OUT = os.path.join(_ROOT, 'ai_test', 'l1_shape_calib.csv')
N_GRP = 10
FWD = None
# 完整面板(standard_test)实测单调性, 用于校验形状代理
FULL_MONO = {'F25': 0.988, 'F26': 0.988, 'F27': 1.000, 'F28': 0.964, 'F29': 0.988}


def load_ctx():
    """返回 (Bsub, fwd_s, U_s, bank_ranks) —— 全部已在 [::FWD] 调仓日子样本上"""
    global FWD
    base = E.base_fields()
    FWD = E.FWD
    Bsub = base['B_sub']
    cs = pd.DataFrame(Bsub['close'].astype('float64'))
    fwd = (cs.shift(-(1 + FWD)) / cs.shift(-1) - 1.0).values.astype('float32')[::FWD]
    U = E.get_universe().reindex(index=base['dates'], columns=base['cols']).fillna(False).values
    U_s = U[np.ix_(E.L1_ROWS, E.L1_COLS)][::FWD]
    return Bsub, fwd, U_s


def bank_ranks(Bsub):
    shutil.copy2(STATE, TMP)
    with open(TMP, 'rb') as f:
        st = pickle.load(f)
    out = []
    for i, nd in enumerate(st.get('bank', []), 1):
        try:
            v = E.eval_expr(nd, Bsub).astype(np.float32)
        except Exception:
            continue
        out.append((i, E.rank_rows(v[::FWD])))
        del v
        gc.collect()
    try:
        os.remove(TMP)
    except OSError:
        pass
    return out


def pooled_corr(a, b):
    m = np.isfinite(a) & np.isfinite(b)
    if m.sum() < 100:
        return np.nan
    return float(np.corrcoef(a[m], b[m])[0, 1])


def ic_series(Rs, Rr, U_s):
    """调仓日截面 rank-rank Pearson（同 batch_ic 算法）"""
    X = np.where(U_s, Rs, np.nan)
    Y = np.where(U_s, Rr, np.nan)
    cnt = np.isfinite(X) & np.isfinite(Y)
    n = cnt.sum(axis=1)
    X0, Y0 = np.where(cnt, X, 0.0), np.where(cnt, Y, 0.0)
    Xm = X0.sum(axis=1) / np.maximum(n, 1)
    Ym = Y0.sum(axis=1) / np.maximum(n, 1)
    Xz = np.where(cnt, X - Xm[:, None], 0.0)
    Yz = np.where(cnt, Y - Ym[:, None], 0.0)
    d1 = np.sqrt((Xz ** 2).sum(axis=1))
    d2 = np.sqrt((Yz ** 2).sum(axis=1))
    with np.errstate(invalid='ignore', divide='ignore'):
        return np.where((d1 > 0) & (d2 > 0) & (n >= 50),
                        (Xz * Yz).sum(axis=1) / (d1 * d2 + 1e-12), np.nan)


def decile_shape(RS, fwd, U_s):
    """RS = 已排名(0~1)的调仓日截面。返回 (每档收益, 单调性, 最优档idx, 期数)"""
    T = RS.shape[0]
    rows = []
    for t in range(T):
        if not np.isfinite(fwd[t]).any():
            continue
        m = U_s[t] & np.isfinite(RS[t]) & np.isfinite(fwd[t])
        if m.sum() < 100:
            continue
        dec = np.minimum((np.floor((1.0 - RS[t][m]) * N_GRP)).astype(int), N_GRP - 1)
        rr = fwd[t][m].astype('float64')
        rows.append([rr[dec == g].mean() if (dec == g).sum() >= 5 else np.nan
                     for g in range(N_GRP)])
    if not rows:
        return [np.nan] * N_GRP, np.nan, -1, 0
    ex = np.nanmean(np.array(rows), axis=0)
    mono = float(spearmanr(np.arange(N_GRP, 0, -1), ex)[0]) if np.isfinite(ex).all() else np.nan
    best = int(np.nanargmax(ex)) if np.isfinite(ex).any() else -1
    return [float(x) for x in ex], mono, best, len(rows)


def measure(v, fwd, U_s, Rr, bankr):
    """一条候选的全部标定量。
    ⚠ 方向: archive 的 expr 是**原始表达式**(未翻转), 而引擎 L2 会按 IC 符号翻转后回测
    (`if r['sign'] < 0: v = -v`)。故此处把形状量按 IC 方向定向, 与 archive 的 l2_* 可比。"""
    Rs = E.rank_rows(v[::FWD])
    ics = ic_series(Rs, Rr, U_s)
    mu = float(np.nanmean(ics))
    sd = float(np.nanstd(ics))
    ir = mu / sd if sd > 0 else np.nan
    rec = dict(ic=mu, ic_ir=ir, stab=E.factor_stability(v))
    cs = [abs(pooled_corr(Rs, br)) for _, br in bankr]
    cs = [c for c in cs if np.isfinite(c)]
    rec['maxcorr_bank'] = max(cs) if cs else np.nan
    rec['novelty'] = 1.0 - rec['maxcorr_bank'] if cs else np.nan
    ex_, mono, best, nper = decile_shape(Rs, fwd, U_s)
    sgn = 1.0 if (not np.isfinite(mu) or mu >= 0) else -1.0     # 按 IC 方向定向
    rec['flipped'] = int(sgn < 0)
    if np.isfinite(mono):
        mono = mono * sgn
    if best >= 0 and sgn < 0:
        best = N_GRP - 1 - best
    rec.update(mono=mono, best_grp=best, n_period=nper,
               d1=ex_[0 if sgn > 0 else -1], d10=ex_[-1 if sgn > 0 else 0])
    st = rec['stab'] if np.isfinite(rec['stab']) else 0.0
    wo = abs(ir) * (0.25 + 0.75 * min(max(st, 0.0), 1.0)) if np.isfinite(ir) else np.nan
    rec['score_old'] = wo
    shape_pos = (min(max(mono, 0.0), 1.0) if np.isfinite(mono) else np.nan)
    rec['shape_pos'] = (shape_pos * (1.0 if best == 0 else 0.5)
                        if np.isfinite(shape_pos) else np.nan)
    rec['score_new'] = (wo * rec['shape_pos'] * rec['novelty']
                        if np.isfinite(wo) and np.isfinite(rec['shape_pos'])
                        and np.isfinite(rec['novelty']) else np.nan)
    del Rs, ics
    return rec


# ---------------------------------------------------------------- collect
def collect(limit=None):
    done = set()
    if os.path.exists(OUT):
        done = set(pd.read_csv(OUT, encoding='utf-8-sig')['expr'].astype(str))
        print(f'续跑: 已有 {len(done)} 条', flush=True)
    Bsub, fwd, U_s = load_ctx()
    print(f'调仓日子样本 {U_s.shape}; FWD={FWD}  bank: ', end='', flush=True)
    Br = bank_ranks(Bsub)
    print(f'{len(Br)} 个; 预计算 fwd rank ...', end='', flush=True)
    Rr = E.rank_rows(fwd)
    print('ok', flush=True)

    arch = pd.read_csv(ARCH)
    arch['expr'] = arch['expr'].astype(str)
    # ★入库优先: L2 曾通过的排在最前 -> 即使只跑一部分, Q2(passed 分布) 也完整
    order = (arch.groupby('expr')['passed'].max()
             .sort_values(ascending=False, kind='stable'))
    seq = [e for e in order.index if e not in done]
    print(f'待算 {len(seq)} 条 (其中 L2 曾通过 {int(order.reindex(seq).sum())} 条优先)', flush=True)
    todo = seq[:limit] if limit else seq
    print(f'本次计划 {len(todo)} 条', flush=True)

    t0 = time.time()
    for k, ex in enumerate(todo, 1):
        rec = {'expr': ex}
        try:
            nd = E.parse_expr(ex)
            if nd is None:
                rec['err'] = 'parse'
            else:
                v = E.eval_expr(nd, Bsub).astype(np.float32)
                rec.update(measure(v, fwd, U_s, Rr, Br))
                del v
        except Exception as e:
            rec['err'] = type(e).__name__
        pd.DataFrame([rec]).to_csv(OUT, mode='a', header=not os.path.exists(OUT),
                                   index=False, encoding='utf-8-sig')
        if k % 50 == 0 or k == len(todo):
            el = time.time() - t0
            print(f'  {k}/{len(todo)}  {el:.0f}s  ({el / max(k, 1):.2f}s/条, '
                  f'剩约 {el / max(k, 1) * (len(todo) - k) / 60:.0f}min)', flush=True)
        gc.collect()
    print(f'collect 完成 共 {time.time() - t0:.0f}s', flush=True)


# ---------------------------------------------------------------- validate
def validate():
    """用 F25~F29(完整面板实测单调性已知)校验"调仓日十档"代理的精度"""
    Bsub, fwd, U_s = load_ctx()
    Rr = E.rank_rows(fwd)
    print(f"{'因子':>5}{'完整面板实测':>14}{'本代理':>10}{'差':>9}")
    for tag, full in FULL_MONO.items():
        f = tag[1:]
        try:
            d = pd.read_pickle(os.path.join(_ROOT, 'ai_test', f'F{f}_fac.pkl'))
            v = d.values.astype(np.float32)[E.L1_ROWS][:, E.L1_COLS]
            Rs = E.rank_rows(v[::FWD])
            _, mono, best, n = decile_shape(Rs, fwd, U_s)
            mu = float(np.nanmean(ic_series(Rs, Rr, U_s)))
            if mu < 0:                      # standard_test 会按 IC 方向翻转 -> 此处同口径定向
                mono, best = -mono, (N_GRP - 1 - best if best >= 0 else -1)
            print(f"{tag:>5}{full:>14.3f}{mono:>10.3f}{mono - full:>+9.3f}"
                  f"   (最优档 D{best + 1}, {n}期)")
        except Exception as e:
            print(f'{tag}: {type(e).__name__} {e}')


# ---------------------------------------------------------------- report
def report():
    d = pd.read_csv(OUT, encoding='utf-8-sig')
    arch = pd.read_csv(ARCH)
    arch['expr'] = arch['expr'].astype(str)
    agg = arch.groupby('expr').agg(l2_passed=('passed', 'max'),
                                   l2_calmar=('calmar', 'max'),
                                   l2_ann=('ann_ex', 'max'),
                                   l2_ic=('ic', 'max'),
                                   gen_min=('gen', 'min')).reset_index()
    m = d.merge(agg, on='expr', how='left')
    m = m[np.isfinite(m['mono'])]
    print(f'\n样本 {len(m)} 条（唯一表达式, 有形状值）; 其中 L2 曾通过 '
          f'{int(m["l2_passed"].fillna(0).sum())} 条')

    dead = m[m['l2_passed'].fillna(0) == 0]
    live = m[m['l2_passed'].fillna(0) == 1]

    print('\n' + '=' * 96)
    print('Q1/Q2 十档单调性分布 × L2 结果')
    print('=' * 96)
    for lab, sub in (('L2 判死', dead), ('L2 通过', live)):
        q = sub['mono'].describe(percentiles=[.1, .25, .5, .75, .9])
        print(f"{lab}  n={len(sub):>5}  mono: min{q['min']:+.3f} p10{q['10%']:+.3f} "
              f"p25{q['25%']:+.3f} **中位{q['50%']:+.3f}** p75{q['75%']:+.3f} "
              f"p90{q['90%']:+.3f} max{q['max']:+.3f}"
              f"   |最优档=D1 {100 * (sub['best_grp'] == 0).mean():.1f}%")

    print('\n' + '=' * 96)
    print('Q1 各阈值: 拦下多少 L2 判死 / 误杀多少 L2 通过')
    print('=' * 96)
    print(f"{'门槛':>14}{'拦下(判死)':>12}{'占判死':>9}{'误杀(通过)':>12}{'占通过':>9}")
    for thr in (-1.0, 0.0, 0.3, 0.5, 0.6, 0.7, 0.8, 0.9):
        nd = int((dead['mono'] < thr).sum())
        nl = int((live['mono'] < thr).sum())
        print(f"{'mono < %.1f' % thr:>14}{nd:>12}{100 * nd / max(len(dead), 1):>8.1f}%"
              f"{nl:>12}{100 * nl / max(len(live), 1):>8.1f}%")
    nd = int((dead['best_grp'] != 0).sum()); nl = int((live['best_grp'] != 0).sum())
    print(f"{'最优档 != D1':>14}{nd:>12}{100 * nd / max(len(dead), 1):>8.1f}%"
          f"{nl:>12}{100 * nl / max(len(live), 1):>8.1f}%")

    print('\n' + '=' * 96)
    print('Q3 各指标与 L2 结果(Calmar/超额) 的 Spearman 相关')
    print('=' * 96)
    mm = m[np.isfinite(m['l2_calmar'])]
    for col in ('ic', 'ic_ir', 'stab', 'score_old', 'mono', 'novelty',
                'shape_pos', 'score_new', 'maxcorr_bank'):
        s = mm[[col, 'l2_calmar']].dropna()
        s2 = mm[[col, 'l2_ann']].dropna()
        if len(s) < 10:
            continue
        print(f"{col:>13}: vs Calmar {spearmanr(s[col], s['l2_calmar'])[0]:+.3f}   "
              f"vs 超额 {spearmanr(s2[col], s2['l2_ann'])[0]:+.3f}   (n={len(s)})")

    print('\n' + '=' * 96)
    print('Q3 novelty 分布 (1 - max|corr vs bank|)')
    print('=' * 96)
    q = m['novelty'].describe(percentiles=[.1, .5, .9])
    print(f"min{q['min']:.3f} p10{q['10%']:.3f} 中位{q['50%']:.3f} p90{q['90%']:.3f} "
          f"max{q['max']:.3f}   (通过与判死的中位: {live['novelty'].median():.3f} vs "
          f"{dead['novelty'].median():.3f})")

    print('\n' + '=' * 96)
    print('Q3 新旧 score 各取 Top70 的对比')
    print('=' * 96)
    for col in ('score_old', 'score_new'):
        t = m.dropna(subset=[col]).sort_values(col, ascending=False).head(70)
        npass = int(t['l2_passed'].fillna(0).sum())
        print(f"{col:>10} Top70: L2 曾通过 {npass:>3} 条 ({100 * npass / len(t):5.1f}%)  "
              f"mono中位{t['mono'].median():+.3f}  novelty中位{t['novelty'].median():.3f}  "
              f"L2 Calmar中位{t['l2_calmar'].median():+.3f}")

    print('\n' + '=' * 96)
    print('novelty 最高 / 最低 各 8 条（看是否把"独立但 IC 低"的排上来）')
    print('=' * 96)
    cols = ['ic_ir', 'mono', 'novelty', 'score_old', 'score_new', 'l2_passed', 'l2_calmar']
    print('--- novelty Top8 ---')
    print(m.nlargest(8, 'novelty')[cols].round(4).to_string(index=False))
    print('--- score_new Top8 ---')
    print(m.nlargest(8, 'score_new')[cols].round(4).to_string(index=False))


if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'report'
    _lim = None
    for a in sys.argv[2:]:
        if a.startswith('--limit='):
            _lim = int(a[8:])
    {'collect': lambda: collect(limit=_lim),
     'validate': validate,
     'report': report}[mode]()
