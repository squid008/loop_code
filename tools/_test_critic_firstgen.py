# -*- coding: utf-8 -*-
"""★★★★ 「**首代（无上一代 L1）不许崩**」回归测试（2026-09-19 新增；`_test_*` ⇒ 进全量回归）。

## 为什么必须有它（真事故）
用户报「上证50怎么崩了」 ⇒ 实测 `ai_test/_tracks/pool_50_gen8_err.log`（**640 B，有 traceback** ✗）：

```
File engine/loop_engine.py, line 1452, in _critic_review_prev
    return (cfg, critic, diag, r, reasons)
UnboundLocalError: cannot access local variable 'diag' where it is not associated with a value
```

**根因**：`diag` / `reasons` / `r` 只在"有上一代"分支里绑定 ✗，而 **首代（该池种子/bank 为空，
如 `50` 池 bank=0）会走 else** ⇒ return 时引用未绑定变量 ⇒ 引擎**起来即死** ✗（看板显示"启动即崩"）
★ 溯源：v0.17.0「P0-2 拆 run()」把内联代码抽成函数时**新增了 return 这三个值** ✗ ——
  原内联版里它们只在后面被重新赋值，所以"不崩"只是因为没人当场读它 ✗

## 本测试钉住两条契约
① **行为**：`prev_l1` 为 `None` / 空 DataFrame 时，调用必须**正常返回 5 元组**（不抛异常 ✓），
   且默认值为**同形**的空值（`{}` / `[]` / `''`）✓，`cfg` 原样返回 ✓
② **静态**：函数体内、`if prev_l1 is not None` **之前**必须出现初始化那行 ✓
   （防以后有人"清理"掉它 ✗）

⚠ 本测试**不跑挖掘、不写任何文件、不连网**（`loop_critic` 只在函数内 import ✓）⇒ 线上挖掘时可安全跑 ✓
"""
import io
import os
import re
import sys

import pandas as pd

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'engine'))

import loop_engine as LE          # noqa: E402

FAIL = []


def chk(desc, cond, hint=''):
    print('  %s %s' % ('✓' if cond else '✗', desc))
    if not cond:
        FAIL.append(desc + ('（%s）' % hint if hint else ''))


class FakeArgs:
    gen = 8                       # 首代场景下 gen 不会被真正用到 ✓


CFG = dict(LE.DEFAULT_CFG)

print('[1] 首代：prev_l1 = None ⇒ 必须正常返回（旧代码在这里 UnboundLocalError ✗）')
out = LE._critic_review_prev(None, FakeArgs(), CFG, None, None)
chk('返回 5 元组', isinstance(out, tuple) and len(out) == 5, 'out=%r' % (out,))
cfg2, critic, diag, r, reasons = out
chk('cfg 原样返回（首代不改策略）', cfg2 is CFG)
chk('diag 是空 dict（同形默认值）', diag == {}, 'diag=%r' % (diag,))
chk('reasons 是空 list', reasons == [], 'reasons=%r' % (reasons,))
chk('r 是空串（下游 _agg_style_diag 的 r 是死参，不会用到）', r == '', 'r=%r' % (r,))
chk('critic 模块已返回（供下游 critic.report 等使用）', hasattr(critic, 'suggest'))

print()
print('[2] 首代的另一种形态：prev_l1 = 空 DataFrame ⇒ 同样不许崩')
out2 = LE._critic_review_prev(None, FakeArgs(), CFG, pd.DataFrame(), None)
chk('返回 5 元组且 diag 为空', isinstance(out2, tuple) and len(out2) == 5 and out2[2] == {},
    'out2=%r' % (out2,))

print()
print('[2b] 同批隐患：`_build_fam_blacklist` 首代（prev_l1 空）也不许崩')
print('     （v1.21.7 前：`return (block_fams, f, fam_black_txt, nd)` ⇒ UnboundLocalError: nd ✗）')


class FakeArgs2:
    gen = 8
    fam_block_thr = 0.5
    decorr = 0.75
    fsa_th = 0.15
    min_stab = 0.30
    bank_skel_max = 1
    parent_sel = 'uniform'
    parent_top_pct = 0.30


CFG2 = dict(LE.DEFAULT_CFG)
import loop_critic as _LC      # noqa: E402  （引擎内部也是函数内 import ✓）
_bf, _f2, _txt, _nd = LE._build_fam_blacklist(FakeArgs2(), CFG2, _LC, {'fake': 'panel'},
                                              set(), None, [])
chk('首代返回 (block_fams=空集, panel 原样返回, 文本空, nd=None)',
    _bf == set() and _f2 == {'fake': 'panel'} and _txt == '' and _nd is None,
    'got=(%r, %r, %r, %r)' % (_bf, _f2, _txt, _nd))

print()
print('[3] 静态守门：初始化必须写在 `if prev_l1 is not None` **之前**')
src = io.open(os.path.join(ROOT, 'engine', 'loop_engine.py'), encoding='utf-8').read()
i = src.index('def _critic_review_prev(')
j = src.index('\ndef ', i + 1)
seg = src[i:j]
m_init = re.search(r'^\s*diag,\s*reasons,\s*r\s*=\s*\{\},\s*\[\],\s*[\'"]{2}\s*$', seg, re.M)
m_if = re.search(r'^\s*if prev_l1 is not None', seg, re.M)
chk('函数里存在 `diag, reasons, r = {}, [], \'\'` 初始化', bool(m_init))
chk('该初始化在 `if prev_l1 is not None` 之前', bool(m_init) and bool(m_if)
    and m_init.start() < m_if.start())

print()
if FAIL:
    print('✗ 失败 %d 项：' % len(FAIL))
    for f in FAIL:
        print('   - %s' % f)
    sys.exit(1)
print('✓ 全过：首代（无上一代 L1 / 空 bank 池）不再崩溃')
sys.exit(0)
