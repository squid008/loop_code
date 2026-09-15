# -*- coding: utf-8 -*-
"""_audit_files.py — 【只读】全项目文件清单与"谁在用谁"测绘。

## 为什么需要（2026-09-15，用户要求「项目精简 + 不要两处打架」）

用户问「`loop_journal_50.md` 是啥？CSV 能不能丢历史？`ai_test/` 能不能清空？
`tools/` 有没有过期的？`standard/` 里的 md 能不能归档？」——
★ 这些**不能凭文件名猜**，必须按"**谁引用它**"判定：

| 判据 | 含义 | 处置 |
|---|---|---|
| **LIVE** | 被 `.py` 字面引用 **或** 命中引擎的路径常量 | **绝不能动**（引擎在读/写）|
| **DOC** | 只被 `.md` 引用 | 可归档（但**要同步改文档引用**）|
| **ORPHAN** | 全仓没有任何引用 | ⚠ **先确认不是"运行时拼出来的路径"**，再谈删 |

★★ 特别注意：**路径可能在运行时用 `os.path.join(HERE, ...)` 拼出来** ⇒
  必须先抓"引擎里所有读写路径的表达式"，避免把**活文件当孤儿删掉** ✗

## 输出
1. 引擎的**读写路径清单**（从源码里抓 `os.path.join(...)` 与常量）
2. 各目录的文件表（大小 / 被谁引用）
3. 分类汇总：LIVE / DOC / ORPHAN
"""
import io
import os
import re
import sys
from collections import defaultdict

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = {'.git', '__pycache__', 'node_modules', 'QuantaAlpha-main', '.codebuddy',
             '.vscode', 'generated-images'}
SCAN_EXT = ('.py', '.md', '.json', '.toml', '.txt', '.csv')
WATCH = ('docs', 'tools', 'standard', 'ai_test', 'engine', 'engine/skills', 'research',
         'strategies')


def walk_files(base, dirs_only=False):
    out = []
    for r, ds, fs in os.walk(base):
        ds[:] = [d for d in ds if d not in SKIP_DIRS]
        rel = os.path.relpath(r, ROOT).replace('\\', '/')
        if dirs_only:
            continue
        for f in fs:
            out.append((rel + '/' + f) if rel != '.' else f)
    return out


# ---------- 1) 抓"引擎的读写路径"（防把活文件当孤儿） ----------
print('=' * 108)
print('【1】引擎里的**读写路径**（从源码抓 `os.path.join` / 路径常量）—— 这些文件绝不能动')
print('=' * 108)
pathre = re.compile(r"os\.path\.join\(([^)]*)\)")
hits = defaultdict(set)
for f in walk_files(ROOT):
    if not f.endswith('.py'):
        continue
    parts = f.split('/')
    if parts[0] in ('research', 'strategies'):      # 历史研究代码，不参与生产
        continue
    try:
        t = io.open(os.path.join(ROOT, f), encoding='utf-8', errors='replace').read()
    except Exception:
        continue
    for m in pathre.finditer(t):
        seg = re.sub(r'\s+', ' ', m.group(1))[:120]
        if any(k in seg for k in ('HERE', 'ROOT', "'docs'", '"docs"')):
            hits[seg].add(f)
for seg in sorted(hits):
    srcs = sorted(hits[seg])
    print('  %-58s  ← %s' % (seg[:58], ', '.join(s[:34] for s in srcs[:3])))
print('  合计 %d 个路径表达式' % len(hits))

# ---------- 2) 建引用索引 ----------
print()
print('=' * 108)
print('【2】文件清单（按"谁引用它"分类）')
print('=' * 108)
allf = []
for d in WATCH:
    p = os.path.join(ROOT, d)
    if os.path.isdir(p):
        allf += [f for f in walk_files(p)]
allf = sorted(set(allf))
# 也含根目录关键文件
for f in os.listdir(ROOT):
    fp = os.path.join(ROOT, f)
    if os.path.isfile(fp) and f.endswith(SCAN_EXT):
        allf.append(f)
allf = sorted(set(allf))

# 正文来源（用于搜索引用）
corpus = {}
for f in walk_files(ROOT):
    if not f.endswith(('.py', '.md', '.json', '.toml', '.txt')):
        continue
    try:
        corpus[f] = io.open(os.path.join(ROOT, f), encoding='utf-8', errors='replace').read()
    except Exception:
        pass

rows = []
for f in allf:
    base = os.path.basename(f)
    fp = os.path.join(ROOT, f)
    if not os.path.isfile(fp):
        continue
    kb = os.path.getsize(fp) / 1024.0
    py_ref, md_ref = [], []
    for src, txt in corpus.items():
        if src == f or base not in txt:
            continue
        (py_ref if src.endswith('.py') else md_ref).append(src)
    kind = 'LIVE' if py_ref else ('DOC' if md_ref else 'ORPHAN')
    rows.append((kind, f, kb, py_ref, md_ref))

for kind in ('LIVE', 'DOC', 'ORPHAN'):
    sel = [r for r in rows if r[0] == kind]
    print('\n  ---- %s（%d 个）----' % (kind, len(sel)))
    for k, f, kb, pr, mr in sorted(sel, key=lambda x: -x[2]):
        tag = ''
        if pr:
            tag = ' ←py: ' + ', '.join(os.path.basename(x) for x in pr[:3])
        elif mr:
            tag = ' ←md: ' + ', '.join(os.path.basename(x) for x in mr[:3])
        print('    %8.1f KB  %-52s%s' % (kb, f[:52], tag[:64]))

print()
print('=' * 108)
s = defaultdict(int)
for k, f, kb, pr, mr in rows:
    s[k] += 1
    s[k + '_KB'] += kb
print('  汇总: LIVE %d 个 / %.1f MB   ·   DOC %d 个 / %.1f MB   ·   ORPHAN %d 个 / %.1f MB'
      % (s['LIVE'], s['LIVE_KB'] / 1024, s['DOC'], s['DOC_KB'] / 1024,
         s['ORPHAN'], s['ORPHAN_KB'] / 1024))
print('  ★ ORPHAN 里的**大文件**要优先人工确认（可能是运行时拼路径的活文件）')
