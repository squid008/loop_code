# -*- coding: utf-8 -*-
"""守门测试：**`del X` 之后又使用 `X`** ⇒ `UnboundLocalError`（确定性崩溃）。

## 为什么要它 —— 2026-09-15 真实事故（v0.20.0 修 `e` 时漏掉的"第二个幽灵"）
`engine/loop_engine.py` 的 `run()`：
- **L2519 `del f`**（在 `for` 候选循环体内，释放候选面板 + `gc.collect()`）⇒ 循环后 `f` 已删除
- **L2663** 的 `_save_state(..., cands, **f**, fail_lib, ...)` 仍在传 `f` ⇒ **每代必崩** ✗✗
- 实测：`pool=300 gen28` / `pool=500 gen15` **两池都崩**，`err` 均 **626 字节**（同一处）✓

★ **为什么 `_test_ghost_args.py` 没抓到**：
  它只检查"实参在调用行**之前**是否有**绑定点**" ⇒ `f` 在 L1793/L1858 **有绑定点** ⇒ 它认为"已绑定" ✗
  ⇒ **没把 `del` 算作"解除绑定"** ✗

★ **附带发现的第二个盲区**（本测试不覆盖，但记在这里）：
  判"形参有没有被用"时，若函数体内**把形参局部重绑定**（如 `with open(..) as f:`），
  之后的"读 `f`"**不是读形参** ⇒ 用"函数体内是否出现 Name(Load)"判会**假阳性** ✗
  （本次 `_save_state` 的形参 `f` 就是这样被误判为"有用"的）

## 判据
对每个函数内每个 `del X`：在它**之后**、**下一次 `X = ...` 之前**，若 `X` 出现在 `Name(Load)` ⇒ 报警。
（若之后有新的 Store ⇒ 属"先删后重建"的正常用法，不算错）
"""
import ast
import io
import os
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_TARGETS = [
    os.path.join(R, 'engine', 'loop_engine.py'),
    os.path.join(R, 'engine', 'loop_pools.py'),
    os.path.join(R, 'engine', 'loop_metrics.py'),
    os.path.join(R, 'tools', 'run_tracks.py'),
]
targets = sys.argv[1:] or [p for p in DEFAULT_TARGETS if os.path.exists(p)]

total = 0
for P in targets:
    src = io.open(P, encoding='utf-8').read()
    tree = ast.parse(src)
    ls = src.splitlines()
    rel = os.path.relpath(P, R)
    found = 0
    for fn in [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]:
        dels = []
        for n in ast.walk(fn):
            if isinstance(n, ast.Delete):
                for t in n.targets:
                    if isinstance(t, ast.Name):
                        dels.append((n.lineno, t.id))
        for dl_ln, name in dels:
            stores = [n.lineno for n in ast.walk(fn)
                      if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)
                      and n.id == name and n.lineno > dl_ln]
            next_store = min(stores) if stores else 10 ** 9
            bad = sorted({n.lineno for n in ast.walk(fn)
                          if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)
                          and n.id == name and dl_ln < n.lineno < next_store})
            if bad:
                found += 1
                total += 1
                print('  ✗ %s  %s()  L%-5d `del %s` ⇒ 之后 **仍在读它**: L%s'
                      % (rel, fn.name, dl_ln, name, bad))
                for ln in bad[:3]:
                    print('        L%-5d %s' % (ln, ls[ln - 1].strip()[:100] if ln - 1 < len(ls) else ''))
    print('  %s %-40s `del` %d 处%s'
          % ('✓' if found == 0 else '✗', rel,
             sum(1 for n in ast.walk(tree) if isinstance(n, ast.Delete)
                 for t in n.targets if isinstance(t, ast.Name)),
             '' if found == 0 else '  ⇒ **%d 处有问题**' % found))

print()
if total:
    print('  ✗ 发现 %d 处「del 后又用」⇒ 运行时 `UnboundLocalError`（确定性崩溃）' % total)
    print('  ⇒ 修法：把 `del` 移到所有使用点**之后**，或删掉多余的实参/形参 ✓')
    sys.exit(1)
print('  ✓ 通过：未发现「del 后又用」')
sys.exit(0)
