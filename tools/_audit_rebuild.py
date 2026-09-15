# -*- coding: utf-8 -*-
"""【只读】梳理"从零重建"链条：每个大件由哪个脚本生成、读什么外部数据。

用户问：「engine 有 2GB，我 clone 下来只有几 MB 吧？跑起来会生成 2GB 吗？」
⇒ 需要给出**重建清单**：谁生成什么、依赖哪个外部路径。
"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ROOT = r'D:\loop_code'
ENG = os.path.join(ROOT, 'engine')

print('=' * 100)
print('【A】`engine/` 里所有 `build_*.py` / `augment_*.py` 的【输入】与【输出】常量')
print('=' * 100)
for f in sorted(os.listdir(ENG)):
    if not (f.startswith(('build_', 'augment_')) and f.endswith('.py')):
        continue
    t = io.open(os.path.join(ENG, f), encoding='utf-8', errors='replace').read()
    ins, outs = [], []
    for n, l in enumerate(t.splitlines(), 1):
        s = l.strip()
        if re.match(r'^[A-Z_]{2,}\s*=\s*', s):
            if re.search(r"E:\\rq|E:/rq", s):
                ins.append(s[:104])
            elif re.search(r"\.h5|\.pkl|\.csv", s) and re.search(r"join|\br['\"]", s):
                outs.append(s[:104])
    if not ins and not outs:
        continue
    print('  --- %s ---' % f)
    for x in ins:
        print('      [读外部] %s' % x)
    for x in outs:
        print('      [产出  ] %s' % x)

print()
print('=' * 100)
print('【B】`E:\\rq` 下各数据源被哪些脚本依赖（家的前置条件）')
print('=' * 100)
need = {}
for r, ds, fs in os.walk(ENG):
    ds[:] = [x for x in ds if x != '__pycache__']
    for f in fs:
        if not f.endswith('.py'):
            continue
        t = io.open(os.path.join(r, f), encoding='utf-8', errors='replace').read()
        for m in re.finditer(r"[rR]?['\"](E:\\rq\\[^'\"]{0,60})['\"]", t):
            p = m.group(1).replace('\\\\', '\\')
            need.setdefault(p, set()).add(f)
for p in sorted(need):
    exists = os.path.exists(p)
    print('  %-46s %s   ← %s' % (p[:46], '✓存在' if exists else '✗缺失',
                                  ', '.join(sorted(need[p])[:4])))

print()
print('=' * 100)
print('【C】有没有"从零搭建"的说明文档')
print('=' * 100)
for f in ('README.md', 'docs/software_framework.md', 'docs/factor_roadmap.md'):
    p = os.path.join(ROOT, f.replace('/', os.sep))
    if not os.path.exists(p):
        continue
    t = io.open(p, encoding='utf-8', errors='replace').read()
    hits = [l.strip()[:110] for l in t.splitlines()
            if re.search(r'E:\\rq|重建|从零|依赖数据|build_panel|数据源', l)]
    print('  --- %s（%d 处相关）---' % (f, len(hits)))
    for h in hits[:8]:
        print('      %s' % h)
