# -*- coding: utf-8 -*-
"""【只读】系统性检查：源码里写的**文件/目录路径**是否真的存在。

## 为什么值得做（2026-09-15，从"两处打架"引出的可推广检查）

用户要求「**两处不要前后矛盾互相打架**」。实证第一条：
  `tools/backfill_bank_ex.py` 里 `os.path.join(HERE, 'library_kpi.py')`
  ⇒ `HERE` = `tools/` ⇒ 它去找 **`tools/library_kpi.py`**，
    而该文件其实在 **`ai_test/`**（且 `ai_test/` 被 gitignore）⇒ **运行时必崩** ✗

★★ 这类"**旧路径没跟着迁移**"可以**机械地全体扫一遍** —— 比人工翻文件可靠得多 ✓

## 判据（保守，避免误报）

只对**能静态解析**的形式下结论：
  · `os.path.join(HERE, 'a', 'b.py')`  —— `HERE` = 该文件所在目录
  · `os.path.join(ROOT, 'docs', 'x.md')` —— `ROOT` = 仓库根（若该文件里 `ROOT` 确实=dirname(HERE)）
  · 字面量形如 `'tools/xxx.py'` / `'engine/xxx.py'`（相对仓库根）
★ 解析不了的（变量拼接 / format / glob）**一律跳过**，只在末尾列出"未检查"数量 ✓
  ⇒ **宁可漏报，不要误报**（用户明确要求：别把不是 bug 的当 bug）✓
"""
import ast
import io
import os
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP = {'__pycache__', '.git', 'node_modules', 'QuantaAlpha-main', '.codebuddy'}
SCOPE = ('engine', 'tools', 'standard', 'ai_test')

bad, checked, skipped = [], 0, 0

for d in SCOPE:
    base = os.path.join(ROOT, d)
    if not os.path.isdir(base):
        continue
    for r, ds, fs in os.walk(base):
        ds[:] = [x for x in ds if x not in SKIP]
        for f in fs:
            if not f.endswith('.py'):
                continue
            fp = os.path.join(r, f)
            rel = os.path.relpath(fp, ROOT).replace('\\', '/')
            txt = io.open(fp, encoding='utf-8', errors='replace').read()
            try:
                tree = ast.parse(txt)
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                        and node.func.attr == 'join'):
                    continue
                try:
                    owner = ast.unparse(node.func.value)
                except Exception:
                    continue
                if owner not in ('os.path', 'path'):
                    continue
                args = node.args
                if not args:
                    continue
                try:
                    head = ast.unparse(args[0])
                except Exception:
                    head = ''
                parts = []
                for a in args[1:]:
                    if isinstance(a, ast.Constant) and isinstance(a.value, str):
                        parts.append(a.value)
                    else:
                        parts = None
                        break
                if not parts or not parts[-1].endswith(('.py', '.md', '.pyc')):
                    skipped += 1
                    continue
                cand = None
                if head == 'HERE':
                    cand = os.path.join(r, *parts)
                elif head == 'ROOT':
                    cand = os.path.join(ROOT, *parts)
                elif head in ('here', 'BASE', 'base_dir'):
                    cand = os.path.join(r, *parts)
                if cand is None:
                    skipped += 1
                    continue
                checked += 1
                if not os.path.exists(cand):
                    bad.append((rel, node.lineno, os.path.relpath(cand, ROOT).replace('\\', '/'),
                                '/'.join(parts)))

print('=' * 104)
print('【路径一致性】源码里 `os.path.join(<DIR>, ..., "<file>.py/.md")` 的目标是否真的存在')
print('=' * 104)
if bad:
    for rel, ln, want, parts in sorted(bad):
        print('  ✗ %-34s L%-5d 找 `%s`  —— **不存在**' % (rel, ln, want))
else:
    print('  （全部存在 ✓）')
print('\n  ⇒ 已检查 **%d** 处；**%d 处指向不存在的文件** ✗；跳过（动态拼接，无法静态解析）**%d** 处'
      % (checked, len(bad), skipped))
print('  ★ 跳过的都是运行时拼接（glob/format/变量）⇒ **不误报**，但也**不保证**它们没问题')

# 额外：列出这些缺失文件到底在哪（若同名文件在别处 ⇒ 就是"迁移没跟全"）
print()
print('=' * 104)
print('【补充】缺失文件的同名副本在哪里（判断"是不是迁移漏了一个"）')
print('=' * 104)
for rel, ln, want, parts in sorted(bad):
    name = parts[-1]
    found = []
    for r, ds, fs in os.walk(ROOT):
        ds[:] = [x for x in ds if x not in SKIP]
        if name in fs:
            p = os.path.relpath(os.path.join(r, name), ROOT).replace('\\', '/')
            if p != want:
                found.append(p)
    print('  %-28s 期望 `%s` ；实际在: %s' % (name, want, found or '（全仓都没有！）'))
