# -*- coding: utf-8 -*-
"""_test_ghost_args.py — 抓「**调用点实参未定义**」的回归测试（P0-2 事故的永久防线）。

## 为什么必须存在（2026-09-15 事故复盘）

P0-2 把 `run()` 拆成 17 个函数时，我**给几个函数补了形参 `e`/`r_`/`_e`**，
但函数体**从不读它们**（只在 `except ... as e:` 里当局部异常变量）⇒
调用点传入的名字在 `run()` 里**从未绑定** ⇒ **`UnboundLocalError`** ✗✗

**实际损失**（有日志与时间戳铁证）：
```
pool=300 gen25 (14:30 启动, P0-2 之前) ✓   pool=300 gen28 (15:48 启动) ✗ 崩
pool=300 gen26 (15:19)                 ✓   pool=500 gen15 (16:04 启动) ✗ 崩
pool=300 gen27 (15:19 启动 → 15:48 结束) ✓  ← 进程在 15:19 已加载旧代码
──────────── 15:43 提交 P0-2 ────────────
```
⇒ **11 个回归测试当时全绿** —— 因为它们**都没覆盖 `run()` 的主循环** ✗
⇒ `tools/smoke_gen_only.py` 是 `--gen_only`，**跳过 L2** ⇒ 也测不到 ✗
⇒ 而**真机跑一代**要 20+ 分钟且**会写 state**（不能与生产并行）⇒ 不适合做日常质检

## 本测试的判据（毫秒级、纯静态、不写任何文件）

对 `run()` 内每个 `Call`，取其**简单名实参**；若该名在
「模块级 / `run()` 形参 / **调用行之前**的绑定（Store / for / with / import / def / global）」里都没有 ⇒ **报警** ✓

★ 特别识别**最阴险的一种**：名字**只**被 `except Exception as x:` 绑过 ——
  Python 3 在 handler 结束时**隐式 `del x`** ⇒ 到调用行**必然未绑定** ⇒ 必崩 ✗
  （这正是 `e` 的形态：全文件有 `except ... as e`，所以 AST 的"未定义名"检查**抓不到**）

★ 假阳性处理：`type(e)` 之类出现在 `except` handler **body 内部**的 ⇒ 那里 `e` 有效 ⇒ **排除** ✓
  （排除法：若该 `Name` 所在的 `Call` 的祖先链里存在 `ExceptHandler`，且 `e` 就是它的 `name`）

## 跑法
```
python tools/_test_ghost_args.py
```
"""
import ast
import builtins
import io
import os
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TARGET = os.path.join(ROOT, 'engine', 'loop_engine.py')

OK = [0, 0]


def chk(cond, msg):
    OK[0] += 1
    if not cond:
        OK[1] += 1
    print('  [{}] {}'.format('OK ' if cond else 'FAIL', msg))


def module_names(tree):
    names = set(dir(builtins))
    for n in tree.body:
        if isinstance(n, ast.Import):
            for a in n.names:
                names.add((a.asname or a.name).split('.')[0])
        elif isinstance(n, ast.ImportFrom):
            for a in n.names:
                names.add(a.asname or a.name)
        elif isinstance(n, (ast.FunctionDef, ast.ClassDef)):
            names.add(n.name)
        elif isinstance(n, ast.Assign):
            for t in n.targets:
                for x in ast.walk(t):
                    if isinstance(x, ast.Name):
                        names.add(x.id)
        elif isinstance(n, (ast.For, ast.AsyncFor)):
            for x in ast.walk(n.target):
                if isinstance(x, ast.Name):
                    names.add(x.id)
        elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name):
            names.add(n.target.id)
    return names


def in_except_handler(node, tree):
    """该节点是否位于某个 `except ... as <name>` 的 **handler body** 内。"""
    for eh in [x for x in ast.walk(tree) if isinstance(x, ast.ExceptHandler)]:
        if eh.name and eh.lineno <= node.lineno <= (eh.end_lineno or eh.lineno):
            for st in eh.body:
                if st.lineno <= node.lineno <= (st.end_lineno or st.lineno):
                    return eh.name
    return None


def main():
    print('=' * 96)
    print('_test_ghost_args.py — 「调用点实参未定义」静态检查（P0-2 事故防线）')
    print('=' * 96)
    src = io.open(TARGET, encoding='utf-8').read()
    tree = ast.parse(src)
    MOD = module_names(tree)

    target = None
    for n in tree.body:
        if isinstance(n, ast.FunctionDef) and n.name == 'run':
            target = n
    chk(target is not None, '找得到 `run()`')
    if target is None:
        return

    params = {a.arg for a in list(target.args.args) + list(target.args.kwonlyargs)}
    bind_ln = {}
    for sub in ast.walk(target):
        if isinstance(sub, ast.Name) and isinstance(sub.ctx, (ast.Store, ast.Del)):
            bind_ln.setdefault(sub.id, []).append((sub.lineno, 'store'))
        elif isinstance(sub, ast.ExceptHandler) and sub.name:
            bind_ln.setdefault(sub.name, []).append((sub.lineno, 'except-as'))
        elif isinstance(sub, (ast.Import, ast.ImportFrom)):
            for a in sub.names:
                bind_ln.setdefault((a.asname or a.name).split('.')[0], []).append(
                    (sub.lineno, 'import'))
        elif isinstance(sub, (ast.FunctionDef, ast.ClassDef)) and sub is not target:
            bind_ln.setdefault(sub.name, []).append((sub.lineno, 'def'))
        elif isinstance(sub, (ast.For, ast.AsyncFor)):
            for x in ast.walk(sub.target):
                if isinstance(x, ast.Name):
                    bind_ln.setdefault(x.id, []).append((sub.lineno, 'for'))
        elif isinstance(sub, (ast.With, ast.AsyncWith)):
            for it in sub.items:
                if it.optional_vars is not None:
                    for x in ast.walk(it.optional_vars):
                        if isinstance(x, ast.Name):
                            bind_ln.setdefault(x.id, []).append((sub.lineno, 'with'))

    ghosts = []
    for call in [x for x in ast.walk(target) if isinstance(x, ast.Call)]:
        ln = call.lineno
        for a in call.args:
            if not isinstance(a, ast.Name):
                continue
            nm = a.id
            if nm in params or nm in MOD:
                continue
            # 排除：位于 `except ... as nm` handler body 内 ⇒ nm 有效
            if in_except_handler(a, target) == nm:
                continue
            # ★★★ 关键判据（2026-09-15 负向验证发现漏了它 ⇒ 测试曾**抓不到** bug ✗）
            #   Python 3 的 `except Exception as x:` 会在 handler 结束时**隐式 `del x`**
            #   ⇒ 那种绑定**不构成调用行的有效绑定** ⇒ 必须排除，否则 `e` 会被误放行 ✗
            #   （原版 `ai_test/_diag_args.py` 有这条；我搬到本测试时漏了 ⇒ 负向验证立刻暴露 ✓）
            before = [(l, k) for l, k in bind_ln.get(nm, [])
                      if l < ln and k != 'except-as']
            if before:
                continue
            fn = (call.func.id if isinstance(call.func, ast.Name)
                  else getattr(call.func, 'attr', '?'))
            ghosts.append((ln, fn, nm))

    print()
    if ghosts:
        for ln, fn, nm in sorted(ghosts):
            print('    ✗ L%-5d %s(...)  ← 实参 `%s` 在调用行之前**从未绑定**' % (ln, fn, nm))
    chk(not ghosts,
        '`run()` 里所有调用实参都已定义（幽灵实参 %d 个）' % len(ghosts))

    print()
    print('通过 %d/%d  %s' % (OK[0] - OK[1], OK[0], '✓ 全部通过' if not OK[1] else '✗ 有失败'))
    return OK[1]


if __name__ == '__main__':
    sys.exit(0 if main() == 0 else 1)
