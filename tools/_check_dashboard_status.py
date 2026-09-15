# -*- coding: utf-8 -*-
"""【只读】查 `dashboard/` 在 git 里的真实状态：
① 是否有未跟踪/未提交的文件（IDE 里"绿色"通常就是**未跟踪**或**新增**）
② 有哪些被 `.gitignore` 忽略（如 node_modules / dist / __pycache__）
③ 已跟踪文件清单
"""
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
R = r'D:\loop_code'


def git(*args):
    r = subprocess.run(['git'] + list(args), cwd=R, capture_output=True,
                       text=True, encoding='utf-8', errors='replace')
    return (r.stdout or '').strip()


print('=' * 96)
print('[1] `git status --short dashboard/`（空 = 干净；?? = 未跟踪；M/A = 改动）')
print('=' * 96)
s = git('status', '--short', 'dashboard/')
print(s if s else '  （空）⇒ ✓ dashboard/ 无任何未提交/未跟踪项')

print()
print('=' * 96)
print('[2] 未跟踪文件（含被忽略）—— `git status --short --ignored dashboard/`')
print('=' * 96)
si = git('status', '--short', '--ignored', 'dashboard/')
for l in (si or '（空）').splitlines()[:30]:
    print('  %s' % l)

print()
print('=' * 96)
print('[3] 已跟踪文件数 + 清单（前 30）')
print('=' * 96)
tracked = [x for x in git('ls-files', 'dashboard/').splitlines() if x.strip()]
print('  已跟踪 %d 个' % len(tracked))
for t in tracked[:30]:
    print('    %s' % t)

print()
print('=' * 96)
print('[4] 磁盘上的真实文件（排除 node_modules / __pycache__）—— 与上面比对可发现"漏跟踪"')
print('=' * 96)
disk = []
for d, ds, fs in os.walk(os.path.join(R, 'dashboard')):
    ds[:] = [x for x in ds if x not in ('node_modules', '__pycache__', 'dist', '.vite')]
    for f in fs:
        if f.endswith('.pyc'):
            continue
        p = os.path.join(d, f)
        disk.append(os.path.relpath(p, R).replace('\\', '/'))
print('  磁盘 %d 个' % len(disk))
missing = sorted(set(disk) - set(tracked))
if missing:
    print('  ⚠ **未被 git 跟踪** 的 %d 个：' % len(missing))
    for m in missing[:20]:
        print('    %s' % m)
else:
    print('  ✓ 磁盘文件全部已被跟踪')
