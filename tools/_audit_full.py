# -*- coding: utf-8 -*-
"""_audit_full.py — 【只读】全项目通盘盘点（用户："从头到尾检查一轮，research 里都是啥"）。

## 关心的 5 类问题（都按**证据**判，不凭名字）
1. **规模与时间**：各目录多少文件/多大/最后改动 ⇒ 判断"活的"还是"停更的"
2. **谁在用谁**：被 `engine/`+`tools/`+`standard/` 的 `.py` 引用 ⇒ 生产依赖
3. **两处打架**：同一信息多处定义（常量/路径/名单）
4. **孤儿**：全仓无引用
5. **硬编码绝对路径**（`D:\\loop_code\\...`）⇒ 换机器即崩 ✗
"""
import io
import os
import re
import sys
import time
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP = {'.git', '__pycache__', 'node_modules', '.codebuddy', '.vscode',
        'QuantaAlpha-main', 'generated-images', 'history'}

DIRS = ('engine', 'tools', 'standard', 'docs', 'research', 'strategies', 'facs')
now = time.time()

print('=' * 100)
print('【1】各目录规模 / 活跃度')
print('=' * 100)
for d in DIRS:
    p = os.path.join(ROOT, d)
    if not os.path.isdir(p):
        print('  %-12s (不存在)' % d)
        continue
    n = 0
    tot = 0
    newest = 0
    oldest = now
    by_ext = defaultdict(int)
    for r, ds, fs in os.walk(p):
        ds[:] = [x for x in ds if x not in SKIP]
        for f in fs:
            fp = os.path.join(r, f)
            try:
                m = os.path.getmtime(fp)
                sz = os.path.getsize(fp)
            except OSError:
                continue
            n += 1
            tot += sz
            newest = max(newest, m)
            oldest = min(oldest, m)
            by_ext[os.path.splitext(f)[1] or '(无)'] += 1
    top = sorted(by_ext.items(), key=lambda x: -x[1])[:5]
    print('  %-12s %5d 文件  %8.1f MB   最后改动 %s   最早 %s'
          % (d, n, tot / 1024 / 1024,
             time.strftime('%m-%d %H:%M', time.localtime(newest)),
             time.strftime('%m-%d', time.localtime(oldest))))
    print('               主要类型: %s' % ' · '.join('%s×%d' % (k, v) for k, v in top))

# ---------------------------------------------------------------- 生产语料
prod = {}
for d in ('engine', 'tools', 'standard'):
    for r, ds, fs in os.walk(os.path.join(ROOT, d)):
        ds[:] = [x for x in ds if x not in SKIP]
        for f in fs:
            if f.endswith('.py'):
                fp = os.path.join(r, f)
                prod[os.path.relpath(fp, ROOT).replace('\\', '/')] = io.open(
                    fp, encoding='utf-8', errors='replace').read()
allpy = dict(prod)
for d in ('research', 'strategies'):
    for r, ds, fs in os.walk(os.path.join(ROOT, d)):
        ds[:] = [x for x in ds if x not in SKIP]
        for f in fs:
            if f.endswith('.py'):
                fp = os.path.join(r, f)
                allpy[os.path.relpath(fp, ROOT).replace('\\', '/')] = io.open(
                    fp, encoding='utf-8', errors='replace').read()

# ---------------------------------------------------------------- 2) research/strategies 被引用情况
print()
print('=' * 100)
print('【2】`research/` 与 `strategies/` 的文件**是否被生产代码引用**')
print('=' * 100)
for d in ('research', 'strategies'):
    files = []
    for r, ds, fs in os.walk(os.path.join(ROOT, d)):
        ds[:] = [x for x in ds if x not in SKIP]
        for f in fs:
            if f.endswith('.py'):
                files.append(os.path.relpath(os.path.join(r, f), ROOT).replace('\\', '/'))
    ref, orphan = [], []
    for rel in files:
        b = os.path.basename(rel)
        hit = []
        for src, txt in prod.items():
            if src == rel:
                continue
            if re.search(r'(?<![\w./])%s(?![\w])' % re.escape(b), txt):
                hit.append(src)
        (ref if hit else orphan).append((rel, hit))
    print('  --- %s/ ：%d 个 .py ---' % (d, len(files)))
    print('      被生产代码提到: %d 个' % len(ref))
    for rel, hit in sorted(ref)[:12]:
        print('        %-44s ← %s' % (rel[:44], ', '.join(h.split("/")[-1] for h in hit[:3])))
    print('      无任何引用（孤儿）: %d 个' % len(orphan))
    for rel, _ in sorted(orphan)[:10]:
        print('        %s' % rel[:70])

# ---------------------------------------------------------------- 3) 硬编码绝对路径
print()
print('=' * 100)
print('【3】硬编码绝对路径（换机器即崩）—— 只列 `D:\\loop_code` 之外的，或全项目统计')
print('=' * 100)
pat = re.compile(r"[rR]?['\"]([A-Za-z]:[\\/][^'\"]{2,80})['\"]")
for label, corpus in (('engine/tools/standard', prod), ('research/strategies', {k: v for k, v in allpy.items() if not k.startswith(('engine/', 'tools/', 'standard/'))})):
    hits = defaultdict(list)
    for src, txt in corpus.items():
        for m in pat.finditer(txt):
            p = m.group(1)
            hits[p.replace('\\\\', '\\')].append(src)
    print('  --- %s：%d 个不同的绝对路径 ---' % (label, len(hits)))
    for p in sorted(hits, key=lambda x: -len(hits[x]))[:10]:
        print('    %-46s ×%-3d  %s' % (p[:46], len(hits[p]),
                                       ', '.join(sorted(set(x.split('/')[-1] for x in hits[p]))[:3])))
