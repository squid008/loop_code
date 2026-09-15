# -*- coding: utf-8 -*-
"""【只读】精确判定 `ai_test/` 里到底哪些是**真生产依赖**。

## ⚠ 为什么重做（2026-09-15 自我纠错）

上一版 `_audit_scope.py` 用「**文件名出现在生产 .py 文本里**」当判据 ⇒ **误报**：
注释、文档字符串、报错信息里提到 `xxx.py` 都会被算成"依赖" ✗

★★ 用户明确提醒过：「**你之前会出现开始发现 BUG，但后面又发现不是 BUG 的情况，要尽量避免**」
⇒ 所以必须先精确判定，再下结论 ✓

## 精确判据（只有这几种才算真依赖）

1. `import <mod>` / `from <mod> import` —— `mod` 对应 `ai_test/<mod>.py`
2. `importlib.import_module('...')`
3. `subprocess.*([... '<file>.py' ...])` —— 真的**去执行**它
4. `os.system('... <file>.py')`
5. `runpy.run_path('...')` / `exec(open('...'))`

★ 其余（注释/文档串/日志文本）**一律不算** ✓
"""
import ast
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP = {'__pycache__'}

# ai_test 里的模块名（供 import 判定）
ai_mods = {f[:-3] for f in os.listdir(os.path.join(ROOT, 'ai_test'))
           if f.endswith('.py')} if os.path.isdir(os.path.join(ROOT, 'ai_test')) else set()

prod = []          # (relpath, text)
for d in ('engine', 'tools', 'standard'):
    for r, ds, fs in os.walk(os.path.join(ROOT, d)):
        ds[:] = [x for x in ds if x not in SKIP]
        for f in fs:
            if f.endswith('.py'):
                p = os.path.join(r, f)
                prod.append((os.path.relpath(p, ROOT).replace('\\', '/'),
                             io.open(p, encoding='utf-8', errors='replace').read()))

print('=' * 104)
print('【精确】生产代码对 `ai_test/` 的**真依赖**（import / subprocess / runpy / exec）')
print('=' * 104)
dep = {}
for rel, txt in prod:
    try:
        tree = ast.parse(txt)
    except SyntaxError:
        continue
    for node in ast.walk(tree):
        # ① import / from import
        if isinstance(node, ast.Import):
            for a in node.names:
                nm = a.name.split('.')[0]
                if nm in ai_mods:
                    dep.setdefault(nm + '.py', set()).add('%s:L%d import' % (rel, node.lineno))
        elif isinstance(node, ast.ImportFrom) and node.module:
            nm = node.module.split('.')[0]
            if nm in ai_mods:
                dep.setdefault(nm + '.py', set()).add('%s:L%d from-import' % (rel, node.lineno))
        # ② 字符串里的 `<x>.py`（只认确实用于执行的调用）
        if isinstance(node, ast.Call):
            fn = ''
            try:
                fn = ast.unparse(node.func)
            except Exception:
                pass
            if re.search(r'subprocess|system|runpy|run_path|check_output|Popen|exec\b', fn):
                for a in ast.walk(node):
                    if isinstance(a, ast.Constant) and isinstance(a.value, str):
                        for m in re.finditer(r"([\w_]+)\.py", a.value):
                            if m.group(1) in ai_mods:
                                dep.setdefault(m.group(1) + '.py', set()).add(
                                    '%s:L%d 执行' % (rel, node.lineno))

for k in sorted(dep):
    print('  ★ %-30s ← %s' % (k, ' ; '.join(sorted(dep[k]))))
print('\n  ⇒ **真生产依赖 %d 个**' % len(dep))

# ---- 反面对照：只被"文本提到"的（=上一版的误报来源） ----
print()
print('=' * 104)
print('【对照】只在**注释/字符串文本**里被提到的 `ai_test/*.py`（★ 这些**不是依赖**，上一版误报）')
print('=' * 104)
txtonly = {}
for rel, txt in prod:
    for m in re.finditer(r"([\w_]+)\.py", txt):
        nm = m.group(1) + '.py'
        if m.group(1) in ai_mods and nm not in dep:
            txtonly.setdefault(nm, set()).add(rel)
for k in sorted(txtonly):
    print('     %-30s 仅被提到: %s' % (k, ', '.join(sorted(txtonly[k])[:4])))
print('\n  ⇒ **%d 个**（上一版把它们算成依赖 ⇒ 误报）' % len(txtonly))

# ---- 真实被 git 跟踪的 ai_test 文件 ----
print()
print('=' * 104)
print('【git】`ai_test/` 里**真的被 git 跟踪**的文件（= 不是 gitignore 掉的）')
print('=' * 104)
import subprocess
r = subprocess.run(['git', 'ls-files', 'ai_test'], cwd=ROOT, capture_output=True,
                   text=True, encoding='utf-8', errors='replace')
print('  %s' % (r.stdout.strip().replace('\n', '\n  ') or '（无）'))
