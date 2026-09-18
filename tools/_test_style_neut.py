# -*- coding: utf-8 -*-
"""★★ 回归：**风格画像的"剥后"不许静默变 `—`**（2026-09-17 用户实测 F07_1000 之问）。

用户现象：精选池 F07_1000「很多风格剥后都是 `—`」，而**同一因子的 `对数总市值` 却有值、`规模 size` 没有**
—— 两者秩相关 **0.998**（几乎同一条），同因子同口径**不该一行有一行没有** ⇒ 判定不一致 ⇒ bug ✓

真因（`ai_test/_probe_neut_deg.py` 猴补定位）：
  中性化变量（`lncap` 的秩）在**子集里含 NaN** ⇒ `_neut_size_ind` 的
  `xc[m] -= xr[m].mean()` 把 NaN **传染给整个行业组** ⇒ 残差整列 NaN ⇒ `_rho` 返回 NaN ⇒ 被
  `_summ` 过滤 ⇒ UI 显示 `—` ✗（**退化判定其实是 0%，根本不是"退化"**）

本测试钉住三件事（缺一不可）：
  ① 中性化样本**必须同时要求 `lncap` 有限**（R² 路径与风格路径都要）
  ② 剥后序列长度变了 ⇒ 下游掩码**必须同步换成同子集**的（否则广播报错）
  ③ **兜底**：中性化结果里出现 NaN ⇒ 一律判"不可判定"（不许静默 NaN ⇒ 悄悄变成 `—` 而不留痕）
外加数据侧不变量：现有 JSON 里"剥后无值的风格"**只允许是 `barra_comovement`**（该面板恒定 1.0）✓
"""
import glob
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ROOT = r'D:\loop_code'
FAIL = []
FC = io.open(os.path.join(ROOT, 'tools', 'factor_curves.py'), encoding='utf-8-sig').read()


def chk(desc, cond, hint=''):
    print('  %s %s' % ('✓' if cond else '✗', desc))
    if not cond:
        FAIL.append(desc + ('（%s）' % hint if hint else ''))


print('=' * 96)
print('【1】中性化样本：**必须要求 `lncap` 有限**（否则 NaN 传染整组）')
print('=' * 96)
chk('R² 路径用 `mk = m & _lc`', re.search(r'mk = m & _lc', FC) is not None)
chk('风格路径用 `mmn = mm & _lc`（且都做样本量检查）',
    re.search(r'mmn = mm & _lc', FC) is not None and 'mmn.sum() < 200' in FC)
chk('中性化调用传的是**同子集**的秩与行业码（`xr[_lc[m]]` / `iv[i][mk]`）',
    'xr[_lc[m]]' in FC and 'iv[i][mk]' in FC)

print()
print('=' * 96)
print('【2】长度变了 ⇒ 下游掩码同步换（否则广播报错）')
print('=' * 96)
chk('剥后序列长度按 `mk.sum()` 建（不是 `m.sum()`）',
    'np.full(int(mk.sum()), np.nan)' in FC)
chk('行业块用**同一子集**的掩码 `mjk = g_k == j`（长度与 `xr_n` 一致）',
    'mjk = g_k == j' in FC and 'xr_n[mjk]' in FC)
chk('剥后相关用 `vr_n`（`mmn` 子集），不是 `vr`（`mm` 子集）',
    '_rho(pd.Series(xn).rank(pct=True).values, vr_n)' in FC,
    '用错就广播报错：shapes (2613,) (2615,) ✗')

print()
print('=' * 96)
print('【3】兜底：中性化结果含 NaN ⇒ 判"不可判定"（不许静默）')
print('=' * 96)
chk('有 `np.isfinite(xn).all()` 兜底并把 `deg` 置真',
    re.search(r'not np\.isfinite\(xn\)\.all\(\)', FC) is not None)

print()
print('=' * 96)
print('【3b】★ 2026-09-18：新增「剥全部」（`allsty`）—— 三套口径齐全 + 退化守卫')
print('=' * 96)
chk('三套口径齐全（raw / neut / allsty）',
    "('raw', 'neut', 'allsty')" in FC and "'allsty': {s: _summ(" in FC)
chk('★ 「剥全部」也必须**有退化守卫**（因子被 15 个风格完全解释 ⇒ 判退化，不拿噪声排序 ✗）',
    'np.percentile(np.abs(res), 99.5)' in FC,
    '缺了会给出一条"在数值噪声上排序"的假曲线 ✗')
chk('★ `_allsty_neutral` 写回整行用**位置索引**（子集长度的掩码不能索引宽度 S 的行 ✗）',
    re.search(r'idx = np\.nonzero\(m\)\[0\][\s\S]{0,400}outA\[t, idx\] = A', FC) is not None,
    '实测踩到过：IndexError dimension is 5384 but ... 2621')

print()
print('=' * 96)
print('【4】数据侧不变量：剥后无值的风格**只允许**是 `barra_comovement`')
print('=' * 96)
files = sorted(glob.glob(os.path.join(ROOT, 'docs', 'factor_curves', '*.json')))
if not files:
    print('  [SKIP] 还没有曲线文件')
else:
    bad = {}
    n_none_total = 0
    for p in files:
        try:
            d = json.load(io.open(p, encoding='utf-8'))
        except Exception:
            continue
        sp = d.get('style') or {}
        if not sp.get('styles'):
            continue
        miss = [s for s in sp['styles'] if ((sp.get('neut') or {}).get(s) or {}).get('mean') is None]
        n_none_total += len(miss)
        extra = [s for s in miss if s != 'barra_comovement']
        if extra:
            bad[d.get('name')] = extra
    print('  扫了 %d 个曲线文件 · "剥后无值"合计 %d 处' % (len(files), n_none_total))
    if bad:
        for nm, ss in list(bad.items())[:8]:
            print('    %-14s 剥后缺: %s' % (nm, ' '.join(ss)))
    chk('★ 除 `barra_comovement`（面板恒定 1.0 ⇒ 本该不判定）外，**没有**其他风格的剥后缺失',
        not bad, '缺了就说明 NaN 又在静默污染（回到老 bug）✗')

print()
if FAIL:
    print('★★ 风格剥后回归失败 %d 项：' % len(FAIL))
    for x in FAIL:
        print('   ✗ %s' % x)
    sys.exit(1)
print('★★ 风格剥后回归全部通过 ✓')
sys.exit(0)
