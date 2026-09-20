# -*- coding: utf-8 -*-
"""真·Alpha143（研报原式，递归）—— 四池只读评测 ✓
用户 2026-09-20：\"你看下 alpha143 因子是不是找错公式了… 然后用它的再算算看，
然后注意方向，可能 4 分位是最好的\"

研报原文（`20170615-国泰君安-数量化专题之九十三` 第 812 行）：
    Alpha143  CLOSE>DELAY(CLOSE,1)?(CLOSE-DELAY(CLOSE,1))/DELAY(CLOSE,1)*SELF:SELF
研报第 1669 行：
    SELF 特殊变量，出现在 Alpha143，表示 **t-1 日的 Alpha143 因子计算结果**

⇒ 即递归式（逐股沿时间）：
    a_t = close_t > close_{t-1} ? (close_t/close_{t-1} - 1) * a_{t-1} : a_{t-1}

⚠ 数值口径（必须说清 ✓）：
  · `log a_t` = `log a_{t-1}` + `log r_t`（只在上涨日 ✓）⇒ 我把逐日 log 收益**累加**求值
    （**与连乘的截面排序完全等价** ✓ —— log 单调 ⇒ 不会改变任何 rank ✓）
    这样做是为了避免连乘下溢（日收益都小于 1 ⇒ 连乘会退化成 0 ✗ 数值上不可算 ✗）
  · 初值 `a_0 = 1`（⇒ `log a_0 = 0`）—— 研报只给出递推，未给初值；取 1 是唯一非退化选择 ✓
    （取 0 会让整列恒为 0 ✗）
  · 两个变体都算：
      ① `full`  全程累积（研报字面口径 ✓ —— 从面板起点累计 ⇒ 会带很长历史 ✓）
      ② `roll20` 只回看最近 20 个交易日（＝短周期版本 ✓，研报标题即\"短周期价量\" ✓）

输出：五档分层（**每 5 日不重叠**调仓 = 项目口径 ✓；**每 20 日不重叠** = 研报口径 ✓）
      + 20 日 rank-IC（均值 / t 值）+ 方向结论 ⇒ 打印 + 落 CSV ✓
全程只读：不写 state / facs / 库文档 ✓
"""
import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, r'd:\loop_code\engine')
sys.path.insert(0, r'd:\loop_code\tools')

import loop_engine as LE            # noqa: E402
import loop_pools as LP             # noqa: E402
import factor_miner as FM           # noqa: E402

OUT = os.path.join(r'd:\loop_code\ai_test', 'alpha143_true')
os.makedirs(OUT, exist_ok=True)
POOLS = ['all', '1000', '500', '300']
POOL_CN = {'all': '全A', '1000': '中证1000', '500': '中证500', '300': '沪深300'}
VARIANTS = [('full', '全程累积（研报字面）'), ('roll20', '近 20 日（短周期）')]
NQ = 5


def rank_pct_row(a):
    """逐行（逐日）百分位秩（NaN 保持 NaN）"""
    s = pd.DataFrame(a)
    return s.rank(axis=1, pct=True).values


def col_corr(a, b):
    """逐行相关（a/b 为已去均值的矩阵 ⇒ 直接算）"""
    return np.nansum(a * b, axis=1) / np.sqrt(
        np.nansum(a * a, axis=1) * np.nansum(b * b, axis=1))


def main():
    t0 = time.time()
    base = LE.base_fields()
    dates, cols, close = base['dates'], base['cols'], base['close']
    C = close.values.astype('float64')
    T, N = C.shape
    print('面板 = %d 日 x %d 股（载入 %.1fs）' % (T, N, time.time() - t0))

    # ---- 逐日收益 & 上涨日 log 收益 ----
    r = np.full((T, N), np.nan)
    r[1:] = C[1:] / C[:-1] - 1.0
    up = C[1:] > C[:-1]
    with np.errstate(invalid='ignore', divide='ignore'):
        lr = np.where(up, np.log(np.maximum(r[1:], 1e-12)), 0.0)
    lr = np.nan_to_num(lr, nan=0.0, posinf=0.0, neginf=0.0)

    S = np.zeros((T, N))                 # S[t] = 第 1..t 日的上涨 log 收益之和
    S[1:] = np.cumsum(lr, axis=0)

    L = {}
    L['full'] = S.copy()                 # ① 全程累积
    lo = np.maximum(0, np.arange(1, T) - 20)
    L['roll20'] = np.full((T, N), np.nan)
    L['roll20'][1:] = S[1:] - S[lo]      # ② 只回看 20 日（S[0] = 0 ✓）
    print('递归列算完（%.1fs）' % (time.time() - t0))

    # ---- 前瞻收益（不重叠采样用 ✓）----
    for hz in (5, 20):
        globals()['fwd%d' % hz] = (close.shift(-(1 + hz)) / close.shift(-1) - 1.0).values

    rows_out = []
    for pool in POOLS:
        if pool == 'all':
            UM = FM.get_universe().reindex(index=dates, columns=cols).fillna(False).values
            sub = np.arange(N)
        else:
            uni = set(LP.pool_union(pool))
            sub = np.asarray([k for k, c in enumerate(cols) if c in uni], dtype=int)
            UM = np.ones((T, N), dtype=bool)
        U = UM[:, sub]
        print('\n======== 池 %s（%d 只成分并集）========' % (POOL_CN[pool], len(sub)))
        for tag, cn in VARIANTS:
            F = L[tag][:, sub]
            ok = U & np.isfinite(F)
            rk = rank_pct_row(np.where(ok, F, np.nan))
            # ---- 20 日 rank-IC（覆盖与非重叠两种都给 ✓）----
            for hz in (20,):
                Y = globals()['fwd%d' % hz][:, sub]
                oky = ok & np.isfinite(Y)
                ry = rank_pct_row(np.where(oky, Y, np.nan))
                m = np.isfinite(rk) & np.isfinite(ry)
                rk2 = np.where(m, rk - np.nanmean(np.where(m, rk, np.nan), axis=1, keepdims=True), np.nan)
                ry2 = np.where(m, ry - np.nanmean(np.where(m, ry, np.nan), axis=1, keepdims=True), np.nan)
                n_ok = m.sum(axis=1)
                c = col_corr(rk2, ry2)
                c = np.where(n_ok >= 30, c, np.nan)
                ics = c[np.isfinite(c)]
                ic, tstat = (ics.mean(), ics.mean() / ics.std(ddof=1) * np.sqrt(len(ics))
                             if len(ics) > 2 and ics.std(ddof=1) > 0 else (np.nan, np.nan))
                print('  [%s] %d 日 rank-IC 均值 %+.4f · t = %+.1f · 有效 %d 天'
                      % (cn, hz, ic, tstat, len(ics)))
            # ---- 五档（不重叠采样 ✓ 两个窗口都算 ✓）----
            for hz in (5, 20):
                Y = globals()['fwd%d' % hz][:, sub]
                idx = np.arange(0, T - 1 - hz, hz)            # 每 hz 天一笔、不重叠 ✓
                # ★ 必须**下取整**成 0..NQ-1 的整数档位 ✓（第一版忘了 floor ⇒ 3.7 这种值
                #   永远撞不上 `== k` ⇒ 只有被 clip 成整数的最高档有数据 ✗）
                grp = np.clip(np.floor(rk[idx] * NQ), 0, NQ - 1)
                ys = Y[idx]
                gret = np.full((len(idx), NQ), np.nan)
                for k in range(NQ):
                    gk = np.where(np.isfinite(grp) & (grp == k), ys, np.nan)
                    s = np.nansum(gk, axis=1)
                    n = np.isfinite(gk).sum(axis=1)
                    gret[:, k] = np.where(n >= 20, s / np.maximum(n, 1), np.nan)
                anns = []
                for k in range(NQ):
                    x = gret[:, k]
                    x = x[np.isfinite(x)]
                    tot = np.prod(1.0 + x) if x.size else np.nan
                    anns.append((tot ** (252.0 / (hz * x.size)) - 1.0) * 100 if x.size and tot > 0 else np.nan)
                ls = [np.nanmean(gret[:, 0] - gret[:, k]) * 252.0 / hz * 100 for k in (NQ - 1,)]
                print('  [%s] %2d 日五档年化 %%：Q1 %+.1f | Q2 %+.1f | Q3 %+.1f | Q4 %+.1f | Q5 %+.1f'
                      % (cn, hz, anns[0], anns[1], anns[2], anns[3], anns[4]))
                best = int(np.nanargmax(anns))
                print('        最好档 = Q%d（%+.1f%%）· 最低档 = Q%d（%+.1f%%）· Q1−Q5 年化 %+.1f%%'
                      % (best + 1, anns[best], int(np.nanargmin(anns)) + 1, anns[int(np.nanargmin(anns))],
                         ls[0]))
                rows_out.append({
                    'pool': pool, 'variant': tag, 'window': hz,
                    **{'Q%d' % (k + 1): round(anns[k], 3) for k in range(NQ)},
                    'best': 'Q%d' % (best + 1), 'Q1_minus_Q5': round(ls[0], 3),
                })
    df = pd.DataFrame(rows_out)
    csv_p = os.path.join(OUT, 'alpha143_true_quantiles.csv')
    df.to_csv(csv_p, index=False, encoding='utf-8-sig')
    print('\n落表 → %s（用时 %.1fs）' % (csv_p, time.time() - t0))


if __name__ == '__main__':
    main()
