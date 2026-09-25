# -*- coding: utf-8 -*-
"""【只读】回答：「我 clone 下来只有几 MB 吧？跑起来会生成 2 GB 吗？」

## 做法（精确，不猜）
1. `git ls-tree -r -l HEAD <dir>` ⇒ git **真正存进仓库**的文件 + 其**体积**（这是 clone 会拿到的）
2. 按"是否被 git 跟踪"给工作区文件分类 ⇒ 得出「clone 后有什么 / 跑起来要生成什么」
3. 找每个"大件生成物"的**生成脚本** ⇒ 说明怎么重建、依赖什么
4. 给出「家里 clone 后跑起来」的前置条件清单
"""
import io
import os
import re
import subprocess
import sys
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIRS = ('engine', 'docs', 'facs', 'strategies', 'standard', 'tools', 'history')


def git(*a):
    r = subprocess.run(['git'] + list(a), cwd=ROOT, capture_output=True, text=True,
                       encoding='utf-8', errors='replace')
    return r.stdout


print('=' * 100)
print('【1】git 仓库里**真正存了什么**（= 你 clone 会拿到的体积）')
print('=' * 100)
out = git('ls-tree', '-r', '-l', 'HEAD', '--', *DIRS)
rows = []
for line in out.splitlines():
    # 格式: <mode> blob <sha> <size> \t <path>
    m = re.match(r'^\S+\s+blob\s+\S+\s+(\d+)\s+(.+)$', line)
    if m:
        rows.append((int(m.group(1)), m.group(2).strip()))
print('  --- 各目录（git 跟踪的体积）---')
per = defaultdict(lambda: [0, 0])
for sz, p in rows:
    top = p.split('/')[0]
    per[top][0] += 1
    per[top][1] += sz
tot_n = tot_s = 0
for d, (n, s) in sorted(per.items(), key=lambda x: -x[1][1]):
    print('    %-12s %4d 个文件  %9.2f MB' % (d, n, s / 1024 / 1024))
    tot_n += n
    tot_s += s
print('    %-12s %4d 个文件  %9.2f MB   ← ★ 这就是 clone 的总量' % ('合计', tot_n, tot_s / 1024 / 1024))
print('  --- 其中最大的 12 个 ---')
for sz, p in sorted(rows, reverse=True)[:12]:
    print('    %9.2f MB  %s' % (sz / 1024 / 1024, p))

print()
print('=' * 100)
print('【2】工作区体积 vs git 跟踪体积（差出来的 = 本地生成、不会被 clone）')
print('=' * 100)
for d in DIRS:
    p = os.path.join(ROOT, d)
    if not os.path.isdir(p):
        continue
    work = 0
    for r, ds, fs in os.walk(p):
        ds[:] = [x for x in ds if x != '__pycache__']
        for f in fs:
            try:
                work += os.path.getsize(os.path.join(r, f))
            except OSError:
                pass
    gt = per.get(d, [0, 0])[1]
    print('  %-12s 工作区 %8.1f MB    git 跟踪 %8.2f MB    ⇒ 本地生成 %8.1f MB'
          % (d, work / 1024 / 1024, gt / 1024 / 1024, (work - gt) / 1024 / 1024))

print()
print('=' * 100)
print('【3】引擎"大件"是什么、谁生成、依赖什么')
print('=' * 100)
BIG = ('panel.h5', 'fa_pit.h5', 'barra.h5', 'universe.h5', 'turnover.h5', 'moneyflow*.h5',
       'industry.h5', 'loop_state*.pkl')
for name in BIG:
    hits = []
    for r, ds, fs in os.walk(os.path.join(ROOT, 'engine')):
        for f in fs:
            import fnmatch
            if fnmatch.fnmatch(f, name):
                fp = os.path.join(r, f)
                hits.append((os.path.getsize(fp), f))
    if not hits:
        continue
    for sz, f in sorted(hits, reverse=True):
        # 找生成脚本
        makers = []
        for r2, ds2, fs2 in os.walk(os.path.join(ROOT, 'engine')):
            for f2 in fs2:
                if not f2.endswith('.py'):
                    continue
                t = io.open(os.path.join(r2, f2), encoding='utf-8', errors='replace').read()
                # 写入（to_hdf / HDFStore / save）且提到该文件
                if f.split('.')[0][:6] in t and re.search(
                        r"to_hdf|HDFStore|\.put\(|savez|pickle\.dump|to_pickle", t):
                    makers.append(f2)
        print('  %-20s %8.1f MB   生成者: %s' % (f, sz / 1024 / 1024,
                                                 ', '.join(sorted(set(makers))[:3]) or '（未定位）'))
