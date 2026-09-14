# -*- coding: utf-8 -*-
"""_test_ok_gate.py — `loop_engine.combine_ok()` 的真值表回归测试（loop_todo §1.17）

## 这个测试守的是什么

`--pool_gate_or_all` 的 OR 语义要**重建** `ok`（撤掉 `_ok_q`，否则退化成 AND）。
旧实现的快照点取错了：

```python
_ok_prev = ok            # 快照取在 _ok_q **之前**
ok = ok and _ok_q
ok = ok and seg_ok       # 分段独立验证
ok = ok and strip_ok     # 剥风格门槛
...
elif _pool_gate_or_all:
    ok = _ok_prev and (_ok_q or _pok)    # ★ 用旧快照整个重建 ⇒ seg/strip 被一起撤掉
```

⇒ **一旦走 OR 分支，「剥风格门槛」与「分段独立验证」就完全失效**（且无告警）。
实测后果：池轨道 13 个入库因子里 **8 个是「纯风格」**（`strip_calmar` 全为负），
本该被 `--min_strip_calmar=0.15` 全部拦下。

**本测试的核心用例**（`t_or_but_hard_fail`）：`ok_q=False, ok_pool=True, ok_hard=False`
⇒ **必须判定不通过**（旧实现会给"通过"＝漏拦）。

用法: python tools/_test_ok_gate.py
"""
import os
import sys

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


def t_truth_table(combine_ok):
    print('\n[1] 真值表（ok_base / ok_q / ok_pool / ok_hard / pool_gate_on / or_all  ->  期望）')
    # (ok_base, ok_q, ok_pool, ok_hard, gate_on, or_all, expect, 说明)
    T, F, N = True, False, None
    cases = [
        # --- 无池门槛：退化为 ok_base && ok_q && ok_hard ---
        (T, T, N, T, F, F, T, '无池门槛 · 全A达标 · 硬门槛过 -> 通过'),
        (T, F, N, T, F, F, F, '无池门槛 · 全A不达标 -> 不通过'),
        (T, T, N, F, F, F, F, '无池门槛 · 硬门槛不过 -> 不通过'),
        # --- 池门槛 AND 语义 ---
        (T, T, T, T, T, F, T, 'AND · 全A与池都达标 -> 通过'),
        (T, T, F, T, T, F, F, 'AND · 池不达标 -> 不通过'),
        (T, F, T, T, T, F, F, 'AND · 全A不达标 -> 不通过'),
        (T, T, T, F, T, F, F, 'AND · 硬门槛不过 -> 不通过'),
        # --- 池门槛 OR 语义（只作用于 _ok_q vs _ok_pool）---
        (T, T, T, T, T, T, T, 'OR · 两者都达标 -> 通过'),
        (T, F, T, T, T, T, T, 'OR · 仅池内达标 -> 通过（OR 的意义所在）'),
        (T, T, F, T, T, T, T, 'OR · 仅全A达标 -> 通过'),
        (T, F, F, T, T, T, F, 'OR · 两者都不达标 -> 不通过'),
        # ★★★ 核心用例：走 OR 分支但硬门槛失败 —— 旧实现会漏拦
        (T, F, T, F, T, T, F, '★ OR · 池内达标但【硬门槛失败】-> 必须不通过（旧实现漏拦！）'),
        (T, T, T, F, T, T, F, '★ OR · 两者都达标但【硬门槛失败】-> 必须不通过'),
        # --- ok_pool is None：放行不误杀，但硬门槛仍生效 ---
        (T, T, N, T, T, T, T, 'OR · 池结果不可用 -> 放行不误杀'),
        (T, T, N, F, T, T, F, '★ OR · 池结果不可用 但【硬门槛失败】-> 仍不通过'),
        (T, F, N, T, T, T, F, 'OR · 池结果不可用 且 全A不达标 -> 不通过'),
    ]
    for ob, oq, op, oh, g, oa, exp, desc in cases:
        got = combine_ok(ob, oq, op, oh, g, oa)
        chk(bool(got) == exp, '{}   (得 {})'.format(desc, got))


def t_repro_old_bug(combine_ok):
    """★ 用**旧实现的公式**复现同一个输入，证明这就是当年的漏拦。"""
    print('\n[2] 复现旧实现的漏拦（同一输入，两种公式对比）')

    def old(ok_base, ok_q, ok_pool, ok_hard, gate_on, or_all):
        # 旧实现：_ok_prev = ok_base（快照取在 _ok_q 之前）；OR 分支重建时丢掉 seg/strip
        _ok_prev = ok_base
        if not gate_on or ok_pool is None:
            return bool(ok_base and ok_q and ok_hard)
        if or_all:
            return bool(_ok_prev and (ok_q or ok_pool))     # ★ 没带 ok_hard
        return bool(ok_base and ok_q and ok_pool and ok_hard)

    T, F = True, False
    # 场景：候选在池内达标（ok_pool=True）、全A 不达标（ok_q=False）、
    #       但**剥风格后转负**（ok_hard=False）—— 正是那 8 个 C 档因子的形态
    inp = (T, F, T, F, T, T)
    o, n = old(*inp), combine_ok(*inp)
    chk(o is True, '旧实现：池内达标 ⇒ **放行**（这就是当年 8 个纯风格因子入库的原因）')
    chk(bool(n) is False, '新实现：**拦下** ✓')
    chk(o != bool(n), '★ 两者结论不同 ⇒ 本修复确实改变了行为')


def t_signature():
    print('\n[3] 接口与文档')
    import loop_engine as LE
    chk(callable(getattr(LE, 'combine_ok', None)), 'loop_engine.combine_ok 存在且可调用')
    doc = (LE.combine_ok.__doc__ or '')
    chk('ok_hard' in doc and 'OR' in doc, 'docstring 写清了 ok_hard 与 OR 的关系')
    chk('§1.17' in doc, 'docstring 指回 loop_todo §1.17（可追溯）')


def main():
    print('=' * 88)
    print('combine_ok 真值表回归测试（loop_todo §1.17）')
    print('=' * 88)
    import loop_engine as LE
    t_truth_table(LE.combine_ok)
    t_repro_old_bug(LE.combine_ok)
    t_signature()
    print('\n' + '=' * 88)
    print('通过 {}/{}'.format(OK[0] - OK[1], OK[0]) + ('' if OK[1] else '  ✓ 全部通过'))
    return 1 if OK[1] else 0


if __name__ == '__main__':
    sys.exit(main())
