# -*- coding: utf-8 -*-
"""★★★★★ 守门：**(丁) 受控补录工具** `tools/horizon_admit_write.py`（2026-09-22 新增）

★ 为什么需要 —— 它已经**真出过两个坑** ✗，而且都是本仓最忌的"**静默出错**"类 ✓：

  ① **下一步清单漏了 `build_facs`** ✗✗（2026-09-21 那次真写之后）
     ⇒ `facs/` 只落到 F41，而 **F43~F46 四个因子进了库却没有 `values.h5`** ✗
     ⇒ 症状：详情页**有曲线**（曲线是现算的 ✓ 不依赖 facs ✗）但"**取用因子值**"那条路**是断的** ✗
     ⇒ 而且**全程不报错** ✗（2026-09-22 才发现并补齐 ✓）
        ★ 本守门的第 ⑤ 条**正是这条**：真发生时当场红 ✓（当时若有它 ⇒ 当天就能发现 ✗）

  ② **去重闸把"已在库"误报成"收益流重复"** ✗✗
     `LE.ex_max_corr(ex, lib_ex, …)` 里 `lib_ex` = **库内全部**收益流 ✗
     ⇒ 候选**已经在库**时，它会与**自己**比 ⇒ |corr| = **1.000** ⇒ 报「收益流重复」✗
     （实录日志：`H12 ✗ 收益流重复 |corr|=1.000（与 ts_mean120(max(fa_np_margin…`
       —— 「对方」那一长串**就是它自己** ✓ 极易读成"5 个因近重复被拒" ✗
       真相是「**它们已经在库里**」✓ —— **两件完全不同的事** ✗）
     ⇒ 且**没有幂等闸**时，重跑会把同一条**再写一遍** ✗（重复总览行 + 重复明细块 ✗
        违反 **D9「因子只入库一次」** ✗）

本守门钉住：静态 ①~④ ＋ 数据不变量 ⑤
"""
import glob
import io
import json
import os
import pickle
import re
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ROOT = r'd:\loop_code'
TOOL = os.path.join(ROOT, 'tools', 'horizon_admit_write.py')
DOCS = os.path.join(ROOT, 'docs')
ENG = os.path.join(ROOT, 'engine')
FAIL = []


def chk(desc, cond, hint=''):
    print('  %s %s' % ('✓' if cond else '✗', desc))
    if not cond:
        FAIL.append(desc + ('（%s）' % hint if hint else ''))


src = io.open(TOOL, encoding='utf-8').read()
# ★ 2026-09-22（我自己的第一条断言就是被它咬的 ✗）：源码里长命令用**跨行的相邻字符串字面量**
#   拼接（`… --fwd 20 '` ＋ 换行 ＋ `'--out …`）⇒ 用 `[^\n]*` 匹配**必然失败** ✗
#   ⇒ 先把这种拼接**接成一行**再匹配 ✓（否则守门会误报"清单里没有 --out" ✗ = 假红 ✓）
src_flat = re.sub(r"'\s*\n\s*'", '', src)

print('【1】下一步清单：**必须**含 `build_facs`（漏了 ⇒ 入库了却没有因子值 ✗ 且静默 ✓）')
chk('清单里有 `tools/build_facs.py --only-new` ✓',
    re.search(r'build_facs\.py --only-new', src) is not None,
    '2026-09-21 就是漏了这句 ⇒ F43~F46 没有 values.h5 ✗')
chk('清单里有 `factor_metrics.py`（5 日）✓', re.search(r'factor_metrics\.py --only-new', src) is not None)
chk('★ 20 日指标**必须配 `--out`**（否则 `factor_metrics.py` 会冲掉 5 日表 ✗）',
    re.search(r'factor_metrics\.py[^\n]*--fwd 20[^\n]*--out[^\n]*factor_metrics_fwd20', src_flat)
    is not None,
    '它自己的注释写着"务必配 --out 写到另一个文件 ✓"')

print('\n【2】`_lib_sync` 调用要**如实标来源** `promote`（不冒充引擎 ✗）')
chk("`source='promote'` 传进了 `_lib_sync` ✓", re.search(r"source\s*=\s*'promote'", src) is not None)
chk('引擎侧 `_lib_sync` 有该可选参数（默认 None ⇒ 行为逐位不变 ✓）',
    re.search(r'def _lib_sync\([^)]*source=None\)', io.open(
        os.path.join(ENG, 'loop_engine.py'), encoding='utf-8').read(), re.S) is not None)

print('\n【3】去重闸**先排除自己**（否则"已在库"会被误报成"收益流重复"✗）')
chk('存在 `_lib_wo_self`（把候选自己从对照集里去掉 ✓）', '_lib_wo_self' in src)
chk('排除判据是**表达式逐字相等**（`str(k).strip() != expr` ✓）',
    re.search(r'str\(k\)\.strip\(\)\s*!=\s*expr', src) is not None,
    '用子串/模糊匹配会误伤别的因子 ✗')

print('\n【4】幂等闸：**已在库 ⇒ 跳过**，且要在**求值之前**（别白算 ~1 分钟/个 ✗）')
_i_skip = src.find('已在库')
_i_eval = src.find('evaluate_real(')
chk('源码里有"已在库 ⇒ 跳过"这条闸 ✓', _i_skip > 0)
chk('它出现在 `evaluate_real(` **之前**（省掉整个回测 ✓）', 0 < _i_skip < _i_eval,
    '放在求值之后就等于每个候选白跑一遍回测 ✗')
chk('日志把「已在库」与「收益流重复」**分开**（两件不同的事 ✗）',
    '已在库' in src and '收益流重复' in src)
chk('汇总行同时报"已在库跳过 N 个" ✓', re.search(r'已在库跳过\s*%\s*d|已在库跳过 %d', src) is not None
    or 'len(skipped)' in src)

print('\n【5】★ 数据不变量：(丁) 交付物必须**真的齐**（这条正是"漏 build_facs"会当场红的 ✓）')
try:
    sys.path.insert(0, ENG)
    import loop_engine as LE
    sys.modules['__main__'].Node = LE.Node                 # pkl 是引擎以 __main__ 身份写的 ✓

    jp = os.path.join(ROOT, 'ai_test', '_admit_final.json')
    chk('定稿文件存在（%s）' % os.path.relpath(jp, ROOT), os.path.exists(jp))
    dump = json.load(io.open(jp, encoding='utf-8')) if os.path.exists(jp) else []

    md = {}
    for pool in ('all', '300', '500', '1000'):
        p = os.path.join(DOCS, 'factor_library%s.md' % ('' if pool == 'all' else '_' + pool))
        md[pool] = io.open(p, encoding='utf-8').read() if os.path.exists(p) else ''
    bex = {}
    for pool in ('all', '300', '500', '1000'):
        p = os.path.join(ENG, 'loop_state%s.pkl' % ('' if pool == 'all' else '_' + pool))
        if os.path.exists(p):
            st = pickle.load(open(p, 'rb'))
            bex[pool] = {str(k).strip() for k in (st.get('bank_ex') or {})}

    n_no_md, n_no_hz, n_no_vals, n_no_bex = [], [], [], []
    for r in dump:
        e = (r.get('expr') or '').strip()
        pool = r.get('pool') or 'all'
        t = md.get(pool, '')
        m = re.search(r'(?m)^### (F\d+) · [^\n]*\n```\n' + re.escape(e) + r'\n```', t)
        if not m:
            n_no_md.append(r.get('name'))
            continue
        code = m.group(1)
        nxt = t.find('\n### ', m.start() + 5)
        blk = t[m.start():nxt if nxt > 0 else len(t)]
        if re.search(r'口径：\*\*\d+ 日调仓\*\*', blk) is None:
            n_no_hz.append(r.get('name'))
        names = [code, '%s_%s' % (code, pool)]
        if not any(glob.glob(os.path.join(ROOT, 'facs', '*', n, 'values.h5')) for n in names):
            n_no_vals.append('%s(%s)' % (r.get('name'), code))
        if e not in bex.get(pool, set()):
            n_no_bex.append(r.get('name'))

    chk('① 每个候选在该池 md 里都有**明细块**（缺 %s）' % (n_no_md or '无 ✓'), not n_no_md)
    chk('② 每块都有「口径：**N 日调仓**」行（缺 %s）' % (n_no_hz or '无 ✓'), not n_no_hz)
    chk('③ ★ 每个候选都有 **`facs/…/values.h5`**（缺 %s）✗ 漏 build_facs 就是这条红' % (n_no_vals or '无 ✓'),
        not n_no_vals, '2026-09-21 实录：F43~F46 入库却没有值 ✗')
    chk('④ 每个候选都在该池 `bank_ex` 里（收益流去重要用 ✓）（缺 %s）' % (n_no_bex or '无 ✓'), not n_no_bex)

    # 取一个实例验证 bank_ex 的**口径线索**（20 日 ≈ 104 期 / 5 日 ≈ 418 期 ✓）
    if dump:
        r0 = dump[0]
        p0 = os.path.join(ENG, 'loop_state%s.pkl' % (
            '' if (r0.get('pool') or 'all') == 'all' else '_' + r0['pool']))
        if os.path.exists(p0):
            st = pickle.load(open(p0, 'rb'))
            ex = (st.get('bank_ex') or {}).get(r0['expr'].strip())
            n = len(ex) if ex is not None and hasattr(ex, '__len__') else 0
            chk('⑤ 抽查 %s 的 bank_ex 期数 = %d（20 日口径应 ≈104，5 日应 ≈418 ✓）'
                % (r0.get('name'), n), 50 <= n <= 200,
                '期数不对 ⇒ 补录时口径没切到副口径 ✗')
except Exception as e:                                           # noqa: BLE001
    chk('能做数据不变量检查', False, '%s: %s' % (type(e).__name__, str(e)[:110]))

print()
print('★ 全过 ✓ (丁) 工具的两处坑都在守门之下（清单含 build_facs ✓ 去重排除自己 ✓ 幂等 ✓ 交付物齐 ✓）'
      if not FAIL else '✗ 有 %d 项没过：\n  - %s' % (len(FAIL), '\n  - '.join(FAIL)))
sys.exit(1 if FAIL else 0)
