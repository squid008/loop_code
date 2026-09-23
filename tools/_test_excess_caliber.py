# -*- coding: utf-8 -*-
"""★★★★ 守门：**超额与年化的「算术 vs 几何」口径**（2026-09-23 新增；进全量回归 ✓）。

为什么要有它（用户 2026-09-23 之问："我们的超额是算术的还是几何的？用哪个科学"）：
  口径事实（`engine/factor_miner.py::evaluate_real`）：
    · 每期超额 `ex = tr - mr`                         ⇒ **算术差**
    · 累计 `nav_e = (1+ex).cumprod()`、`ann_ex = nav_e[-1]**(1/yrs)-1` ⇒ **几何（CAGR）**
    · 年度 `yr_ex[y] = (1+g).prod()-1`                ⇒ **几何**
    · 夏普 `ex.mean()/ex.std()*sqrt(243/FWD)`         ⇒ **算术**
  这是标准分工（报收益用几何；统计推断用算术）。**但它全在代码里"默默成立"** ✗ ——
  一旦有人把年化改成 `ex.mean()*期数`（算术年化）或把夏普改成几何口径，
  库里所有历史指标就**悄悄换了口径**、且新旧数字不再可比 ✗ ⇒ 必须钉住 ✓。

本守门钉三件：
  【1】静态：`evaluate_real` 里四条式子各就各位（算术差 / 复利年化 / 复利年度 / 算术夏普）
  【2】文档：`docs/software_framework.md` 有 §3.0.2 口径说明（含实测数字与"理论可投资超额"的警告 ✓）
  【3】功能：**数值关系** —— 几何 ≤ 算术（σ>0 时），差额随 σ 单调增大、且量级 ≈ `σ²/2`（波动拖累 ✓）
        ⇒ 证明"两种口径确实不同、且差多少是可预期的"，而不是"哪个是 bug" ✓
"""
import io
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FM = io.open(os.path.join(ROOT, 'engine', 'factor_miner.py'), encoding='utf-8').read()
DOC = io.open(os.path.join(ROOT, 'docs', 'software_framework.md'), encoding='utf-8').read()
FWD = 5
PPY = 243.0 / FWD                     # 每年换仓期数（≈48.6 ✓ 与引擎 `243/FWD` 同源）
FAIL = []


def chk(desc, cond, hint=''):
    print('  %s %s' % ('✓' if cond else '✗', desc))
    if not cond:
        FAIL.append(desc + ('（%s）' % hint if hint else ''))


print('[1] 静态：`evaluate_real` 的四条式子（算术差 / 复利年化 / 复利年度 / 算术夏普）')
chk('① 每期超额 = **算术差** `ex = tr - mr`',
    re.search(r"^\s+ex = tr - mr\s*$", FM, re.M) is not None)
chk('② 累计是**复利** `nav_e = (1 + ex).cumprod()`',
    re.search(r"nav_e = \(1 \+ ex\)\.cumprod\(\)", FM) is not None)
chk('★ ③ 年化 = **几何（CAGR）** `nav_e.iloc[-1] ** (1 / yrs) - 1`',
    re.search(r"ann_e = nav_e\.iloc\[-1\] \*\* \(1 / yrs\) - 1", FM) is not None)
chk('★ ④ 夏普 = **算术** `ex.mean() / ex.std() * np.sqrt(243 / FWD)`',
    re.search(r"ex\.mean\(\) / ex\.std\(\) \* np\.sqrt\(243 / FWD\)", FM) is not None)
chk('⑤ 年度超额也是**复利** `yr_ex[y] = (1 + g).prod() - 1`',
    re.search(r"yr_ex\[y\] = \(1 \+ g\)\.prod\(\) - 1", FM) is not None)
chk('★ 年化**没有**被写成算术口径（`mean(...) * 243/FWD` 那种必须绝迹 ✗）',
    re.search(r"ann_e = .*mean\(\).*\*\s*\(", FM) is None)
chk('卡玛 = 几何年化 / 回撤（分子用 `ann_e` ✓）',
    re.search(r"calmar = ann_e / abs\(dd_e\)", FM) is not None)

print()
print('[2] 文档：§3.0.2 口径说明在位（含实测数字 + "理论可投资超额"警告）')
chk('`docs/software_framework.md` 有 `### 3.0.2` 小节', '### 3.0.2' in DOC)
chk('写明"每期算术 · 累计/年化几何 · 风险统计量算术"',
    '每期是算术' in DOC and '几何' in DOC and '算术' in DOC)
chk('带实测数字（几何 +5.16% vs 算术 +5.29% / Spearman +0.9968 ✓）',
    '5.16' in DOC and '5.29' in DOC and '0.9968' in DOC)
chk('★ 写明"超额复利 = **理论可投资超额**"（不能读成"真能拿到"✓）',
    '理论可投资超额' in DOC)
chk('指向守门脚本 `tools/_test_excess_caliber.py` ✓',
    '_test_excess_caliber.py' in DOC)

print()
print('[3] 功能：几何 ≤ 算术，差额随 σ 单调、量级 ≈ σ²/2（波动拖累）')
import numpy as np


def geo_ann(r, ppy=PPY):
    """复利年化（与引擎同式：先 cumprod、再开 (1/yrs) 次方 ✓）"""
    nav = np.cumprod(1.0 + np.asarray(r, dtype='float64'))
    yrs = len(r) / ppy
    return float(nav[-1] ** (1.0 / yrs) - 1.0)


def ari_ann(r, ppy=PPY):
    """算术年化 = 每期均值 × 每年期数（这是"如果改成算术口径"会长什么样 ✓）"""
    return float(np.mean(r) * ppy)


rng = np.random.default_rng(20260923)          # 固定种子 ⇒ 可复现 ✓
N = 600                                        # 600 期（≈12 年，与库内量级同阶 ✓）
MU = 0.001                                     # 每期均值 0.1%（年化 ≈ +4.9% ✓）
rows = []
for sd in (0.005, 0.010, 0.020, 0.040):
    r = rng.normal(MU, sd, N)
    g, a = geo_ann(r), ari_ann(r)
    rows.append((sd, g, a, a - g))
    print('    σ=%.1f%%/期 ⇒ 几何 %+6.2f%% · 算术 %+6.2f%% · 差 %+5.2fpp · σ²/2 年化 %.2fpp'
          % (sd * 100, g * 100, a * 100, (a - g) * 100, (sd ** 2 / 2) * PPY * 100))

chk('每个 σ 下都满足 **几何 ≤ 算术**（σ>0 ⇒ 复利必然被波动拖累 ✓）',
    all(a >= g - 1e-12 for _sd, g, a, _d in rows))
chk('差额**随 σ 单调增大**（波动越大、拖累越多 ✓）',
    all(rows[i][3] < rows[i + 1][3] for i in range(len(rows) - 1)),
    '得到 %r' % ([round(x[3] * 100, 3) for x in rows],))
chk('差额量级与 `σ²/2` 同阶（比值落在 0.4~2.5 倍内 ✓）',
    all(0.4 <= (d / ((sd ** 2 / 2) * PPY)) <= 2.5 for sd, _g, _a, d in rows),
    '得到 %r' % ([round(d / ((sd ** 2 / 2) * PPY), 2) for sd, _g, _a, d in rows],))
chk('★ 两种口径**确实给出不同的数**（不是同一个东西的两个名字 ✓）',
    all(abs(a - g) > 1e-6 for _sd, g, a, _d in rows))

print()
if FAIL:
    print('✗ 失败 %d 项：' % len(FAIL))
    for x in FAIL:
        print('   - %s' % x)
    sys.exit(1)
print('✓ 全部通过：超出口径（每期算术 / 累计年化几何 / 夏普算术）+ 文档 §3.0.2 + 波动拖累关系')
