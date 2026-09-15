# -*- coding: utf-8 -*-
"""【只读】查清项目版本号的"权威源"在哪、各处是否一致（用户最在意的"不要打架"）。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
R = r'D:\loop_code'

print('=' * 96)
print('[1] git tag 最新几个（= 实际发布版本，**最权威**）')
print('=' * 96)
r = subprocess.run(['git', 'tag', '--sort=-v:refname'], cwd=R, capture_output=True,
                   text=True, encoding='utf-8', errors='replace')
tags = [t for t in (r.stdout or '').splitlines() if t.strip()]
print('  tag 总数 %d' % len(tags))
print('  最新 6 个: %s' % ' '.join(tags[:6]))

print()
print('=' * 96)
print('[2] change_log.md 的版本条目')
print('=' * 96)
p = os.path.join(R, 'change_log.md')
t = io.open(p, encoding='utf-8').read()
lines = t.splitlines()
print('  总 %d 行' % len(lines))
vs = re.findall(r'^##\s*\[([0-9]+\.[0-9]+\.[0-9]+)\]', t, re.M)
print('  版本条目 %d 个: %s' % (len(vs), ', '.join(vs[:14])))
print('  ⇒ 最新条目 = %s' % (vs[0] if vs else '(无)'))
print('  --- 头部 14 行 ---')
for i, l in enumerate(lines[:14], 1):
    if l.strip():
        print('  %2d| %s' % (i, l[:110]))

print()
print('=' * 96)
print('[3] README.md 的"当前版本"声明')
print('=' * 96)
p2 = os.path.join(R, 'README.md')
t2 = io.open(p2, encoding='utf-8').read()
for i, l in enumerate(t2.splitlines()[:12], 1):
    if '版本' in l or 'v0.' in l:
        print('  L%-3d %s' % (i, l[:118]))
print('  --- README 里的版本表格（前 8 行）---')
n = 0
for l in t2.splitlines():
    if re.match(r'^\|\s*\*\*v0\.', l.strip()) or re.match(r'^\|\s*v0\.', l.strip()):
        print('    %s' % l.strip()[:112])
        n += 1
        if n >= 8:
            break

print()
print('=' * 96)
print('[4] 看板自身版本（独立于项目版本）')
print('=' * 96)
for f, pat in (('dashboard/api/app/main.py', r"version='([^']+)'"),
               ('dashboard/api/app/main.py', r"'version': '([^']+)'"),
               ('dashboard/web/package.json', r'"version":\s*"([^"]+)"')):
    pp = os.path.join(R, f)
    tt = io.open(pp, encoding='utf-8').read()
    for m in re.finditer(pat, tt):
        print('  %-32s %s' % (f, m.group(1)))

print()
print('=' * 96)
print('[5] 结论：三处"当前版本"是否一致？')
print('=' * 96)
tag_latest = tags[0] if tags else '(无)'
cl_latest = vs[0] if vs else '(无)'
m3 = re.search(r'当前版本\s*`?v?([0-9]+\.[0-9]+\.[0-9]+)', t2)
rd_latest = m3.group(1) if m3 else '(未找到)'
print('  git tag 最新      : %s' % tag_latest)
print('  change_log 最新条目: %s' % cl_latest)
print('  README 当前版本    : %s' % rd_latest)
same = (tag_latest.lstrip('v') == cl_latest == rd_latest)
print('  ⇒ %s' % ('✓ 三处一致' if same else '✗ **三处不一致 ⇒ 这就是"两处打架"**'))
