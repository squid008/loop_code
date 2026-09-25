# -*- coding: utf-8 -*-
"""_test_ops_registry.py — ★★★ 算子「单一事实源」结构性验收（P0-1）

## 为什么有这个测试（与 `_test_ops_sync.py` 分工不同）

| 测试 | 守什么 |
|---|---|
| `_test_ops_sync.py` | **结果**：各处的算子名单**当前是否一致**（渲染后覆盖、无副本清单）|
| **本文件** | **结构**：**"只改一处就够"这件事是否成立** —— 即"机制"而不是"当前状态" |

★★★ 关键差别：`_test_ops_sync` 只能证明"**现在**没漂移"；本文件要证明
**"以后也不会漂移"** —— 做法是**真的往声明里插一条算子**，看引擎表和 A角 prompt
是否**自动**多出它（不需要改任何其他文件）。这就是 P0-1 的**验收标准** ✓

## 断言

1. 算子集合 == **重构前金标准快照**（`ai_test/_ops_oracle_before.json`，独立 oracle）
2. **绑定正确**：`('fo', name)` 类算子必须与 `fastops.name` **逐位相同**
   （防"注册表接线时接错函数"—— 这类错不会崩，只会静默算错 ✗）
3. prompt 名单生成物能被 `_expand_abbrev` 完整展开（与消费方互为逆运算）
4. ★★★ **"只改一处"证明**：临时插一条 ⇒ 引擎表 + prompt **双双自动生效**
5. `SLOW_OPS` ⊆ 算子名集合（防出现指向不存在算子的"孤儿偏好"）
"""
import io
import json
import os
import re
import sys

import numpy as np

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'engine'))

OK = [0, 0]


def chk(c, m):
    OK[0] += 1
    if not c:
        OK[1] += 1
    print('  [{}] {}'.format('OK ' if c else 'FAIL', m))


def t_oracle():
    print('\n[1] 算子集合 == 重构前金标准快照（独立 oracle）')
    import ops_registry as OPS
    # ★ 2026-09-15：该快照原在 `ai_test/`，随 `ai_test/` 整体归档而"消失"⇒
    #   **已移回 `tools/`**（它是**长期 oracle 测试资产**，不是一次性产物）✓
    #   ⚠ 教训：`ai_test/` 整体归档时，要先把**被 `tools/` 依赖的资产**挑出来 ✗
    p = os.path.join(HERE, '_ops_oracle_before.json')
    if not os.path.exists(p):
        chk(False, '缺少金标准快照 {}（P0-1 当时抓取；丢了就少一层独立校验）'.format(
            os.path.relpath(p, ROOT)))
        return
    o = json.loads(io.open(p, encoding='utf-8').read())
    chk(sorted(set(OPS.unary_names()) - {'ts_rank10', 'ts_delta10'}) == o['unary'],  # ★ 2026-09-20 有意新增 10 日窗口（ts_rank10/ts_delta10）⇒ 快照保持原样、只放这条增量 ✓
        '单目集合 == 快照（%d 个）' % len(o['unary']))
    chk(sorted(OPS.binary_names()) == o['binary'],
        '双目集合 == 快照（%d 个）' % len(o['binary']))
    chk(sorted(OPS.SLOW_OPS) == o['slow'],
        '`SLOW_OPS` == 快照（%d 个）' % len(o['slow']))


def t_binding():
    print('\n[2] 绑定正确：`("fo", name)` 必须与 `fastops.name` **逐位相同**')
    import fastops as FO
    import loop_engine as LE
    import ops_registry as OPS
    rng = np.random.RandomState(5)
    X = (rng.randn(150, 4).cumsum(axis=0) + 40).astype(np.float32)
    X[31, 1] = np.nan
    Y = (rng.randn(150, 4).cumsum(axis=0) + 20).astype(np.float32)
    n_checked = bad = 0
    for prefix, wins, bind, _g in OPS.UNARY_SPECS:
        if bind[0] != 'fo':
            continue
        for w in (wins or [None]):
            name = prefix if w is None else '%s%d' % (prefix, w)
            fn = getattr(FO, bind[1])
            a = np.asarray(LE.UNARY[name](X), dtype=np.float64)
            b = np.asarray(fn(X) if w is None else fn(X, w), dtype=np.float64)
            n_checked += 1
            if a.shape != b.shape or not np.allclose(a, b, atol=0, rtol=0, equal_nan=True):
                bad += 1
                print('        差异: %s' % name)
    for prefix, wins, bind, _g in OPS.BINARY_SPECS:
        if bind[0] != 'fo':
            continue
        for w in (wins or [None]):
            name = prefix if w is None else '%s%d' % (prefix, w)
            fn = getattr(FO, bind[1])
            a = np.asarray(LE.BINARY[name](X, Y), dtype=np.float64)
            b = np.asarray(fn(X, Y) if w is None else fn(X, Y, w), dtype=np.float64)
            n_checked += 1
            if a.shape != b.shape or not np.allclose(a, b, atol=0, rtol=0, equal_nan=True):
                bad += 1
                print('        差异: %s' % name)
    chk(bad == 0, '%d 个 `fastops` 绑定算子**逐位一致**（差异 %d 个）' % (n_checked, bad))


def t_abbrev():
    print('\n[3] prompt 名单生成物与消费方 `_expand_abbrev` **互为逆运算**')
    import ops_registry as OPS
    import _test_ops_sync as TS
    built = ' '.join(OPS.prompt_unary(g) for g in ('core', 'ema', 'reg', 'moment')) \
        + ' ' + OPS.prompt_binary()
    got = TS._expand_abbrev(built)
    need = set(OPS.unary_names()) | set(OPS.binary_names())
    miss = sorted(k for k in need - got if k not in built)
    chk(not miss, '全部 %d 个算子名可被展开器还原（缺 %s）' % (len(need), miss or '无'))


def t_one_place_add():
    """★★★★★ **验收核心**：只在声明里插 1 条 ⇒ 引擎表 + prompt 双双自动生效。"""
    print('\n[4] ★★★ "只改一处就够" 的**行为证明**（P0-1 的验收标准）')
    import fastops as FO
    import loop_engine as LE
    import loop_llm as LL
    import ops_registry as OPS
    # 用一个**绝不存在的档位** 137，且复用已有实现（只为验证"通路"，不引入新语义）
    probe = ('ts_mean', [137], ('fo', 'ts_mean'), 'core')
    probe_name = 'ts_mean137'
    try:
        OPS.UNARY_SPECS.append(probe)
        u = OPS.build_unary(FO, vars(LE))
        # 直接读**磁盘上的 .md**（生效版）并渲染 —— 模拟"真跑一代"时的取值路径
        txt = LL.render_prompt(LL._load_skill('gen_skill', LL._GEN_SYSTEM_FALLBACK))
        chk(probe_name in u,
            '① 引擎 `UNARY` 自动多出 `%s`（**没改 loop_engine**）' % probe_name)
        chk(probe_name in txt,
            '② A角 prompt 自动列出 `%s`（**没改 prompt 的 2 份副本**）' % probe_name)
        x1 = np.arange(200, dtype=np.float32).reshape(-1, 1)
        v = np.asarray(u[probe_name](x1))
        chk(v.shape == (200, 1) and bool(np.isfinite(v).any()),
            '③ 新算子**真的可调用**（不是空壳）：形状 %s' % (v.shape,))
    finally:
        OPS.UNARY_SPECS.remove(probe)
    # 还原后必须回到原状
    u2 = OPS.build_unary(FO, vars(LE))
    chk(probe_name not in u2, '④ 探针已移除、注册表回到原状（清理干净）')


def t_slow_subset():
    print('\n[5] `SLOW_OPS` ⊆ 算子名集合（防"孤儿偏好"指向不存在的算子）')
    import ops_registry as OPS
    alln = set(OPS.unary_names()) | set(OPS.binary_names())
    orphan = sorted(k for k in OPS.SLOW_OPS if k not in alln)
    chk(not orphan, '无孤儿（实得 %s）' % (orphan or '无'))
    chk(len(OPS.SLOW_OPS) == len(set(OPS.SLOW_OPS)), '无重复项')


def t_docs_consistency():
    """算子表的**文档一致性**：README/change_log 里的算子计数不应与注册表矛盾。"""
    print('\n[6] 引擎表已由注册表接管（结构性断言）')
    import loop_engine as LE
    import loop_critic as C
    import ops_registry as OPS
    src = io.open(os.path.join(ROOT, 'engine', 'loop_engine.py'), encoding='utf-8').read()
    ops_src = io.open(os.path.join(ROOT, 'engine', 'loop_ops.py'), encoding='utf-8').read()
    # ★ L3 拆分后：派生接线移到 loop_ops.py；loop_engine 从 loop_ops 引入（仍非手写）
    chk('UNARY = _OPS.build_unary' in ops_src and 'BINARY = _OPS.build_binary' in ops_src,
        '`loop_ops` 的 `UNARY/BINARY` 是**派生**（不是手写字面量）')
    chk('from loop_ops import' in src,
        '`loop_engine` 从 `loop_ops` 引入派生表（不是本地手写）')
    chk(set(LE.UNARY) == set(OPS.unary_names()),
        '`LE.UNARY` == 注册表单目名（%d 个）' % len(OPS.unary_names()))
    chk(set(LE.BINARY) == set(OPS.binary_names()),
        '`LE.BINARY` == 注册表双目名（%d 个）' % len(OPS.binary_names()))
    chk(list(C.SLOW_OPS) == list(OPS.SLOW_OPS), '`C.SLOW_OPS` 是注册表**同一对象**的拷贝')
    # 旧的每算子 helper（`_m/_sl/...`）必须彻底消失（它们曾是"表"的一部分）
    left = re.findall(r'\ndef (_m|_s|_r|_mx|_mn|_sm|_cr|_e|_sl|_rq|_rs|_sk|_ku)\(', src)
    chk(not left, '13 个旧 helper 已清除（残留 %s）' % (left or '无'))


def main():
    print('=' * 96)
    print('算子「单一事实源」结构性验收（架构清扫 P0-1）')
    print('=' * 96)
    t_oracle()
    t_binding()
    t_abbrev()
    t_one_place_add()
    t_slow_subset()
    t_docs_consistency()
    print('\n' + '=' * 96)
    print('通过 {}/{}'.format(OK[0] - OK[1], OK[0]) + ('' if OK[1] else '  ✓ 全部通过'))
    return 1 if OK[1] else 0


if __name__ == '__main__':
    sys.exit(main())
