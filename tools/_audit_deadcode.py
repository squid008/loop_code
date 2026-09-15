"""死代码精确检测（只读）—— 回答「这个函数到底还有没有人调」。

为什么不能只靠 grep：
  · `fastops.ts_corr(` 会匹配到 `ts_corr(` ⇒ 假阳性（那是另一个模块的函数）
  · `'ts_mean(volume)'` 这种**字符串里**的算子名也会匹配 ⇒ 假阳性
  · 同名函数在多个文件**各自定义**（如 `research/round*.py` 自带一套）⇒ 必须分文件看

做法：ast 解析全仓 .py，统计**每个文件内** `Name`/`Attribute` 的引用，
      再看「引擎内某函数」是否被**本文件之外**的任何文件引用（import 后调用也算）。
输出：死代码候选清单（**只报告，不删除**）。
"""
import ast
import io
import os
import sys
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = ('__pycache__', '.git', 'node_modules', 'QuantaAlpha-main')


def walk_py():
    for r, ds, fs in os.walk(ROOT):
        ds[:] = [d for d in ds if d not in SKIP_DIRS]
        for f in fs:
            if f.endswith('.py'):
                yield os.path.join(r, f)


print('=' * 100)
print('【1】engine/*.py 顶层函数：谁在"本文件之外"被引用？')
print('=' * 100)
print('  ⚠⚠⚠ **重要局限（2026-09-15 实测踩到）**：本检查基于 AST/文本，')
print('       **抓不到"字符串字面量 + 运行时按名查找"的引用** ✗')
print('       实例：`engine/ops_registry.py` 写 `(\'cs_demean\', None, (\'le\', \'cs_demean_op\'), \'core\')`，')
print('             由 `loop_engine.py` 的 `UNARY = _OPS.build_unary(_FO, vars())` **按名取出**')
print('             ⇒ `cs_demean_op`/`cs_scale_op`/`cs_rank_op` 全是**活的**，')
print('               但本工具会报"内外均无引用" ✗✗')
print('       ⇒ **凡疑似死代码，必须再 grep 一遍"它的名字作为字符串"有没有被取用**，')
print('         尤其查 `vars()` / `getattr` / `globals()` / 注册表 `build_*(..., vars())` 这类动态查找 ✓')
print()

# 收集每个文件里定义的顶层函数名
defs = {}          # file -> {name: lineno}
for p in walk_py():
    rel = os.path.relpath(p, ROOT)
    if not rel.startswith('engine' + os.sep):
        continue
    try:
        tree = ast.parse(io.open(p, encoding='utf-8', errors='replace').read())
    except Exception:
        continue
    defs[rel] = {n.name: n.lineno for n in tree.body
                 if isinstance(n, (ast.FunctionDef, ast.ClassDef))}

# 统计"该名字在同文件内的引用"（不含定义行）
used_same = defaultdict(set)     # file -> names
used_any = defaultdict(set)      # name -> files (含外部)
for p in walk_py():
    rel = os.path.relpath(p, ROOT)
    try:
        src = io.open(p, encoding='utf-8', errors='replace').read()
        tree = ast.parse(src)
    except Exception:
        continue
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            used_any[node.id].add(rel)
            used_same[rel].add(node.id)
        elif isinstance(node, ast.Attribute):
            # `LE.ts_mean(...)` / `loop_engine.ts_mean` 这种
            used_any[node.attr].add(rel)

print('  引擎文件：%d 个\n' % len(defs))
dead = []
for rel in sorted(defs):
    file_dead = []
    for name, ln in defs[rel].items():
        if name.startswith('__'):
            continue
        others = used_any[name] - {rel}
        inner = name in used_same[rel]
        if not others and not inner:
            file_dead.append((name, ln))
        elif not others:
            # 只在**自己文件内部**被用（可能是"只被别的死函数调用" —— 见第 2 段再判）
            pass
    if file_dead:
        print('  --- %s ---' % rel)
        for name, ln in sorted(file_dead, key=lambda x: x[1]):
            print('      L%-5d %-28s ** 本文件内外均无引用 **' % (ln, name))
        dead += [(rel, n, l) for n, l in file_dead]

print('\n  → 彻底无引用（本文件内外都没有）：%d 个' % len(dead))

print()
print('=' * 100)
print('【2】★ 只在"自己文件内"被引用 —— 但可能只被**另一个死函数**引用（死链）')
print('=' * 100)
for rel in sorted(defs):
    members = set(defs[rel])
    only_inner = []
    for name in defs[rel]:
        if name.startswith('__'):
            continue
        if (name in used_same[rel]) and not (used_any[name] - {rel}):
            only_inner.append(name)
    if not only_inner:
        continue
    # 只用 AST 看：这些名字被谁引用；如果引用者本身也只被死链引用 ⇒ 整链是真的死
    print('  --- %s ---' % rel)
    for n in sorted(only_inner):
        print('      %-28s 仅本文件内被引用（需人工判断是否死链）' % n)

print()
print('=' * 100)
print('【3】engine/loop_engine.py 算子段落：pandas 老实现 vs fastops 版的**真实调用点**')
print('=' * 100)
p = os.path.join(ROOT, 'engine', 'loop_engine.py')
src = io.open(p, encoding='utf-8', errors='replace').read()
tree = ast.parse(src)
names = ['ts_mean', 'ts_std', 'ts_sum', 'ts_max', 'ts_min', 'ts_rank',
         'ts_corr', 'ts_delay', 'ts_delta',
         'ts_max_op', 'ts_min_op', 'ts_corr20_op', 'ts_corr60_op']
for n in names:
    cs = [x.lineno for x in ast.walk(tree)
          if isinstance(x, ast.Name) and x.id == n and isinstance(x.ctx, ast.Load)]
    # 排除 Attribute 情形（fastops.ts_mean 是 Attribute，不会是 Name）
    dln = [x.lineno for x in tree.body if isinstance(x, ast.FunctionDef) and x.name == n]
    print('    %-14s 定义@%-6s 本文件内调用点 %s' % (
        n, dln or '-', sorted(cs) if cs else '**无**'))
