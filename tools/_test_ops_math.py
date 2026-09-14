# -*- coding: utf-8 -*-
"""_test_ops_math.py — 新算子族的**数值正确性**回归（`loop_todo §1.26` ②③）

覆盖 2026-09-15 新增的 13 个算子：
  · 回归族 `ts_slope{5,20,60}` / `ts_rsqr{5,20,60}` / `ts_resi{5,20,60}`
  · 分布形状 `ts_skew{20,60}` / `ts_kurt{20,60}`

## 为什么这些必须**对拍外部实现**而不是自己验自己

数值算子最容易出「**公式抄错但自己看着对**」的错 —— 比如中心矩展开写错一项，
不会报错、只是结果偏一点 ⇒ **用手算/`np.polyfit`/`scipy.stats` 三方对拍** ✓

## 四层断言

1. **对拍**：与 `np.polyfit`（回归）/ `scipy.stats.skew·kurtosis`（矩）**逐位一致**
2. **解析解**：纯线性序列 ⇒ `slope`=斜率 · `R²`=1 · `resi`=0；纯噪声 ⇒ `R²`≈0
3. ★★ **`R²` 不含方向**（用户判断的补充，必须固定成测试）：
   **涨得稳 / 跌得稳 的 R² 相同** ⇒ 单用 `rsqr` 会丢方向 ⇒ 必须配合 `ts_slope` 的符号
4. **纪律**：**无未来信息** · 满窗语义 · NaN 不臆造 · 性能不退化
"""
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
sys.path.insert(0, os.path.join(ROOT, 'engine'))

OK = [0, 0]


def chk(cond, msg):
    OK[0] += 1
    if not cond:
        OK[1] += 1
    print('  [{}] {}'.format('OK ' if cond else 'FAIL', msg))


def t_linreg():
    print('\n[1] 回归三件套 vs `np.polyfit`（逐位对拍）')
    import fastops as FO
    rng = np.random.RandomState(11)
    for w in (5, 20, 60):
        x = rng.randn(w, 1)
        xx = np.arange(w, dtype=float)
        a, b = np.polyfit(xx, x[:, 0], 1)
        ss_res = float(((x[:, 0] - (a * xx + b)) ** 2).sum())
        ss_tot = float(((x[:, 0] - x[:, 0].mean()) ** 2).sum())
        r2 = 1.0 - ss_res / ss_tot
        got_s = float(FO.ts_slope(x, w)[-1, 0])
        got_r = float(FO.ts_rsqr(x, w)[-1, 0])
        got_e = float(FO.ts_resi(x, w)[-1, 0])
        exp_e = float(x[-1, 0] - (a * (w - 1) + b))
        # ⚠ 容差必须是 **float32 级**（`fastops` 全部返回 float32，与 `ts_mean` 等一致）
        #   —— 2026-09-15 实录：初版写 `1e-9` ⇒ 3 项假 FAIL（实测差 2.2e-8，**正是 float32 精度**）。
        #   ★ 而 float32(~1e-7) 对我们的用途**完全够**（全程按**截面秩**算 IC）✓
        rel = lambda u, v: abs(u - v) / max(abs(v), 1e-12)
        chk(rel(got_s, a) < 1e-5, 'w=%-2d slope  %.9f ≈ polyfit %.9f（相对差 %.1e）'
            % (w, got_s, a, rel(got_s, a)))
        chk(rel(got_r, r2) < 1e-5, 'w=%-2d rsqr   %.9f ≈ 1-SSres/SStot %.9f（相对差 %.1e）'
            % (w, got_r, r2, rel(got_r, r2)))
        chk(abs(got_e - exp_e) < 1e-4, 'w=%-2d resi   %.6f ≈ 末点偏离 %.6f' % (w, got_e, exp_e))


def t_analytic():
    print('\n[2] 解析解：纯线性 / 纯噪声')
    import fastops as FO
    w, n = 20, 80
    lin = (50.0 + 0.7 * np.arange(n))[:, None].copy()          # 斜率 0.7
    chk(abs(float(FO.ts_slope(lin, w)[-1, 0]) - 0.7) < 1e-5, '纯线性 ⇒ slope == 0.7 ✓')
    chk(abs(float(FO.ts_rsqr(lin, w)[-1, 0]) - 1.0) < 1e-5, '纯线性 ⇒ R² == 1 ✓')
    chk(abs(float(FO.ts_resi(lin, w)[-1, 0])) < 1e-4, '纯线性 ⇒ resi == 0（完全在趋势线上）✓')
    # 完全平 ⇒ SS_tot=0 ⇒ 必须 NaN（0/0 不能给假 1.0）
    flat = np.full((n, 1), 7.0)
    chk(bool(np.isnan(FO.ts_rsqr(flat, w)[-1, 0])),
        '★ 价格**完全不动**（SS_tot=0）⇒ R² 为 0/0 ⇒ 输出 **NaN**（不臆造、不给假 1.0）✓')
    noise = np.random.RandomState(2).randn(n, 1)
    chk(float(FO.ts_rsqr(noise, w)[-1, 0]) < 0.6, '纯噪声 ⇒ R² 低（< 0.6）✓')


def t_r2_no_direction():
    print('\n[3] ★★ `R²` **不含方向**（用户判断的必要补充）')
    import fastops as FO
    w, n = 20, 80
    up = (50.0 + 0.7 * np.arange(n))[:, None].copy()
    dn = (50.0 - 0.7 * np.arange(n))[:, None].copy()
    su, sd = float(FO.ts_slope(up, w)[-1, 0]), float(FO.ts_slope(dn, w)[-1, 0])
    ru, rd = float(FO.ts_rsqr(up, w)[-1, 0]), float(FO.ts_rsqr(dn, w)[-1, 0])
    chk(su > 0 > sd, 'slope **带方向**：涨 +{:.2f} / 跌 {:.2f}'.format(su, sd))
    chk(abs(ru - rd) < 1e-9,
        '★★ **「涨得稳」与「跌得稳」的 R² 完全相同**（都是 {:.3f}）⇒ 单用 rsqr 丢方向 ✗'.format(ru))
    # 组合后必须能区分
    cu, cd = ru * su, rd * sd
    chk(cu > 0 > cd,
        '⇒ 必须与 slope 组合：`mul(rsqr, slope)` = {:+.2f} / {:+.2f} **可区分** ✓'.format(cu, cd))
    # 越线性 ⇒ R² 越高（单调性）
    r = []
    for lam in (0.0, 0.3, 1.0, 3.0):
        y = ((50.0 + 0.7 * np.arange(n))[:, None]
             + lam * np.random.RandomState(7).randn(n, 1))
        r.append(float(FO.ts_rsqr(y, w)[-1, 0]))
    chk(all(r[i] > r[i + 1] for i in range(len(r) - 1)),
        '★ 噪声越大 ⇒ R² 越低（单调）：{}'.format([round(v, 3) for v in r]))


def t_moments():
    print('\n[4] 偏度 / 峰度 vs `scipy.stats`（逐位对拍）')
    import fastops as FO
    from scipy import stats
    rng = np.random.RandomState(5)
    for w in (20, 60):
        x = (rng.randn(w, 1) * 2.0 + 1.0)
        x[0, 0] = 9.0                                        # 造点不对称
        exp_s = float(stats.skew(x[:, 0], bias=True))
        exp_k = float(stats.kurtosis(x[:, 0], bias=True, fisher=True))
        got_s = float(FO.ts_skew(x, w)[-1, 0])
        got_k = float(FO.ts_kurt(x, w)[-1, 0])
        chk(abs(got_s - exp_s) < 1e-5, 'w=%-2d skew %.6f == scipy %.6f' % (w, got_s, exp_s))
        chk(abs(got_k - exp_k) < 1e-4, 'w=%-2d kurt %.6f == scipy %.6f' % (w, got_k, exp_k))
    # 正态 ⇒ 超额峰度 ≈ 0
    big = np.random.RandomState(9).randn(500, 1)
    k = float(np.nanmean(FO.ts_kurt(big, 60)))
    chk(abs(k) < 0.5, '正态样本的超额峰度 ≈ 0（实得 {:.3f}）✓'.format(k))
    s = float(np.nanmean(FO.ts_skew(big, 60)))
    chk(abs(s) < 0.5, '对称样本的偏度 ≈ 0（实得 {:.3f}）✓'.format(s))


def t_discipline():
    print('\n[5] 纪律：无未来信息 / 满窗 / 不臆造')
    import fastops as FO
    rng = np.random.RandomState(13)
    n = 200
    x = rng.randn(n, 2).cumsum(axis=0) + 50.0
    y = x.copy()
    y[120:] = rng.randn(80, 2) * 30                        # **只改 t>=120**
    for name, fn in (('ts_slope20', lambda a: FO.ts_slope(a, 20)),
                     ('ts_rsqr20', lambda a: FO.ts_rsqr(a, 20)),
                     ('ts_resi20', lambda a: FO.ts_resi(a, 20)),
                     ('ts_skew20', lambda a: FO.ts_skew(a, 20)),
                     ('ts_kurt20', lambda a: FO.ts_kurt(a, 20))):
        g1, g2 = fn(x), fn(y)
        chk(np.allclose(g1[:120], g2[:120], equal_nan=True),
            '★★ %s：改 t>=120 不影响 t<120 ⇒ **无未来信息** ✓' % name)
    for w in (5, 20):
        v = FO.ts_slope(x, w)
        chk(bool(np.isnan(v[:w - 1]).all()) and bool(np.isfinite(v[w - 1:]).any()),
            'ts_slope%-2d **满窗**语义：前 w-1 期 NaN，第 w 期起有值' % w)
    # 窗口中段有 NaN ⇒ 该窗口不出值（回归需同一批点），但**不是整段 NaN**
    z = x.copy()
    z[100, 0] = np.nan
    vz = FO.ts_slope(z, 20)
    chk(bool(np.isnan(vz[100:120, 0]).all()) and bool(np.isfinite(vz[130:, 0]).any()),
        '窗口内含 NaN ⇒ 该窗口 NaN（不拿 0 当数据），**之后恢复正常** ✓')


def t_perf():
    """性能**量级哨兵** —— 判据是「**不是排序/位置型**」，不是「绝对几秒」。

    ⚠ 2026-09-15 实录（两次教训叠在一起）：
      ① 初版写**绝对阈值** `dt < 2.0`，而实测 1.4~1.8s ⇒ 余量仅 10~30%
         ⇒ **机器负载一波动就假 FAIL**（负向验证的"还原后仍 FAIL"就是这么来的）✗
      ② 而这条断言**本来要守的东西**是「前缀和级 vs 排序/位置级」——
         后两者差 **10× ~ 164×**（见 `ai_test/_bench_newops.py`）
    ⇒ 改用**相对基准**：同面板跑一次 `ts_mean20` 作分母 ⇒ 机器慢时基准也慢 ⇒ **比值稳定** ✓
      量级参考（3309×2000）：前缀和 ~1.5s · `rolling.quantile` ~4.2s · `rolling.apply(argmax)` ~69s
    """
    print('\n[6] 性能**量级**：新算子必须是**前缀和级**（同基准比值 + 宽容上限）')
    import fastops as FO
    big = np.random.RandomState(3).randn(3309, 2000).cumsum(axis=0)
    t0 = time.time()
    FO.ts_mean(big, 20)
    base = max(time.time() - t0, 1e-3)
    print('      基准 `ts_mean20` 用时 {:.2f}s（本机当前速度）'.format(base))
    for name, fn in (('ts_slope20', lambda a: FO.ts_slope(a, 20)),
                     ('ts_rsqr20', lambda a: FO.ts_rsqr(a, 20)),
                     ('ts_resi20', lambda a: FO.ts_resi(a, 20)),
                     ('ts_skew20', lambda a: FO.ts_skew(a, 20)),
                     ('ts_kurt20', lambda a: FO.ts_kurt(a, 20))):
        t0 = time.time()
        fn(big)
        dt = time.time() - t0
        ratio = dt / base
        chk(ratio < 8.0 and dt < 10.0,
            '%-12s %.2fs = 基准 ×%.1f（判据：比值 < 8 且 < 10s；'
            '排序型约 ×8+、位置型约 ×140）' % (name, dt, ratio))


def t_engine():
    print('\n[7] 引擎接通 + A角 prompt 同步')
    import loop_engine as LE
    import loop_critic as C
    need = ('ts_slope5', 'ts_slope10', 'ts_slope20', 'ts_slope60',
            'ts_rsqr5', 'ts_rsqr10', 'ts_rsqr20', 'ts_rsqr60',
            'ts_resi5', 'ts_resi10', 'ts_resi20', 'ts_resi60',
            'ts_skew20', 'ts_skew60', 'ts_kurt20', 'ts_kurt60')
    miss = [k for k in need if k not in LE.UNARY]
    chk(not miss, '16 个新算子全部注册进 `UNARY`（缺 {}）'.format(miss or '无'))
    chk(set(C._ops_of('mul(ts_rsqr20(close), ts_slope20(close))')) >=
        {'mul', 'ts_rsqr20', 'ts_slope20'},
        'B角 `_ops_of` 能认出（已改成派生 ⇒ 自动覆盖）✓')
    # ⚠⚠ **prompt 覆盖检查不在这里做**（2026-09-15 实录）：
    #   我在本文件里写了朴素的 `k in src`，而 prompt 用的是**斜杠简写**
    #   （`ts_slope5/10/20/60`）⇒ `ts_slope20` **不是 literal 子串** ⇒ **误报"缺失"** ✗
    #   ★★★ 这**正是** `roadmap §8.48` 记下的那个坑 —— **我第二次犯了** ✗
    #   ⇒ 该检查**只在 `tools/_test_ops_sync.py [3]` 做一次**（那里有 `_expand_abbrev` 展开器 ✓）
    #   ⇒ **教训：同一件事别写两个检查** —— 弱的那份只会制造假警报。
    chk(True, 'A角 prompt 覆盖检查见 `tools/_test_ops_sync.py [3]`（含斜杠简写展开）')
    B = {'close': np.random.RandomState(1).randn(400, 3).astype('float32').cumsum(axis=0) + 50}
    for ex in ('ts_rsqr20(close)', 'mul(ts_rsqr20(close), ts_slope20(close))',
               'ts_rsqr10(close)', 'ts_resi20(log(close))', 'ts_skew60(ts_delta5(close))'):
        nd = LE.parse_expr(ex)
        chk(nd is not None and LE.eval_expr(nd, B, {}).shape == (400, 3),
            '引擎解析+求值：%s ✓' % ex)


def t_window_policy():
    """★★ 窗口档位**原则**（2026-09-15 用户问「为啥不做 10/15/30」后定下来，固定成测试）。

    ## 三条原则（为什么不是"档位越多越好"）

    ① **近似等比**（短端密、长端疏）—— 因为**短端的相对差异才是信息**
       （`5` vs `10` 差 2 倍；`60` vs `65` 没意义）⇒ 回归族 `5/10/20/60` 间距 `2×/2×/3×` ✓
    ② **优先复用项目已有档位**，别引入新档 ——
       实测（本项目 `UNARY`）：`w=20` 被 **13** 个算子用 · `w=60` 被 **10** 个 · `w=5` 被 **6** 个；
       而 **`w=15` / `w=30` 全项目从未出现** ⇒ 加了就是**引入新档** ⇒ **不加** ✓
    ③ **别加冗余档**：趋势类在**相邻窗口高度相关**（`slope10` ≈ `slope5`/`slope20` 的混合），
       不像 `ts_mean` 那样正交 ⇒ 间距不能太密 ✓
       （对比：`ts_mean` 有 8 档是因为它要做**比值/叠加**，如 `ts_mean(x,5)/ts_mean(x,200)`）
    ④ **短窗对高阶矩无意义**：偏度/峰度是**高阶矩**，样本太少估计极不稳
       ⇒ `ts_skew`/`ts_kurt` **只给 20/60，不给 5** ✓

    ★ 本质：**窗口档位不是"越多越好"，而是"尺度分得开 + 不引入新档"** ✓
    """
    print('\n[8] ★ 窗口档位原则（防"随手加档位"）')
    import re
    import loop_engine as LE
    fam = {}
    for k in LE.UNARY:
        m = re.match(r'^([a-z_]+?)(\d+)$', k)
        if m:
            fam.setdefault(m.group(1), []).append(int(m.group(2)))
    # ① 回归族必须是 5/10/20/60（等比序列）
    for f in ('ts_slope', 'ts_rsqr', 'ts_resi'):
        got = sorted(fam.get(f, []))
        chk(got == [5, 10, 20, 60],
            '`%s` 窗口 = %s（**等比序列 5/10/20/60**，间距 2×/2×/3×）' % (f, got))
    # ② 全项目不该出现 15 / 30（从未有算子用过 ⇒ 加了就是引入新档）
    allw = sorted({w for v in fam.values() for w in v})
    chk(15 not in allw and 30 not in allw,
        '★ 全项目**没有** `w=15`/`w=30`（从未出现过的档位；实得全部档位 %s）' % allw)
    # ③ 高阶矩不给短窗（样本太少估计不稳）
    chk(5 not in fam.get('ts_skew', []) and 5 not in fam.get('ts_kurt', []),
        '★ `ts_skew`/`ts_kurt` **不给 w=5**（高阶矩需要足够样本；实得 %s / %s）'
        % (sorted(fam.get('ts_skew', [])), sorted(fam.get('ts_kurt', []))))
    # ④ 项目"默认档"必须覆盖（w=20 是事实默认档，13 个算子用）
    chk(all(20 in fam.get(f, []) for f in ('ts_slope', 'ts_rsqr', 'ts_resi',
                                          'ts_skew', 'ts_kurt')),
        '★ `w=20`（项目事实默认档，13 个算子用）必须覆盖全部 5 个新族 ✓')


def main():
    print('=' * 96)
    print('新算子族数值回归（loop_todo §1.26 ②③：回归三件套 + 偏度/峰度）')
    print('=' * 96)
    t_linreg()
    t_analytic()
    t_r2_no_direction()
    t_moments()
    t_discipline()
    t_perf()
    t_engine()
    t_window_policy()
    print('\n' + '=' * 96)
    print('通过 {}/{}'.format(OK[0] - OK[1], OK[0]) + ('' if OK[1] else '  ✓ 全部通过'))
    return 1 if OK[1] else 0


if __name__ == '__main__':
    sys.exit(main())
