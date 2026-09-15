# -*- coding: utf-8 -*-
"""`chk_progress.py` — **一眼看挖掘进度**（含 err 是否非空）。

用法:
    python tools/chk_progress.py               # 自动挑最近更新的一代日志
    python tools/chk_progress.py pool_300_gen30.log

## 为什么需要它
`ai_test/_tracks/` 下每个池每代一个 `pool_<池>_gen<N>.log`，人工翻很累；
而 `_err.log` **非空就代表那一代崩了**（2026-09-15 就吃过亏：两池连崩、err 均 626 字节，
但 `已测候选` 不动 ⇒ 误以为"跑得慢" ✗）。
⇒ 本工具把"进度 + 崩没崩"一次打出来 ✓
"""
import io
import os
import sys
import time

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T = os.path.join(R, 'ai_test', '_tracks')

name = sys.argv[1] if len(sys.argv) > 1 else None
if not name:
    cands = []
    for f in os.listdir(T):
        if f.startswith('pool_') and f.endswith('.log') and '_err' not in f:
            cands.append((os.path.getmtime(os.path.join(T, f)), f))
    if not cands:
        print('  (无 pool_*.log)；也可能挖掘尚未启动')
        sys.exit(0)
    name = sorted(cands)[-1][1]

p = os.path.join(T, name)
ls = io.open(p, encoding='utf-8', errors='replace').read().splitlines()
print('=' * 100)
print('[%s]  %d 行  更新于 %s'
      % (name, len(ls), time.strftime('%m-%d %H:%M:%S', time.localtime(os.path.getmtime(p)))))
print('=' * 100)
print('  尾部 10 行:')
for l in ls[-10:]:
    print('    %s' % l[:118])

print()
print('  ★ 关键标志:')
KEYS = ('保存状态', '诊断已写入', 'L2 通过', 'L2 费后精筛', '入库', 'ERR', 'Traceback')
hit = 0
for l in ls:
    if any(k in l for k in KEYS):
        print('    %s' % l[:118])
        hit += 1
if not hit:
    print('    (无 —— 还在 L1 阶段)')

ep = p.replace('.log', '_err.log')
print()
if os.path.exists(ep):
    sz = os.path.getsize(ep)
    print('  err.log: %d B %s' % (sz, '⚠ **非空 ⇒ 这一代崩了**' if sz else '✓ 空'))
    if sz:
        for l in io.open(ep, encoding='utf-8', errors='replace').read().splitlines()[-10:]:
            print('      %s' % l[:118])
else:
    print('  err.log: (不存在) ✓')

# 顺便汇总最近几代的成败
print()
print('  --- 最近 8 个池-代 的 err 状态 ---')
rows = []
for f in os.listdir(T):
    if f.startswith('pool_') and f.endswith('_err.log'):
        fp = os.path.join(T, f)
        rows.append((os.path.getmtime(fp), f, os.path.getsize(fp)))
for mt, f, sz in sorted(rows)[-8:]:
    print('    %-34s %-6s %s' % (f, '%dB' % sz, '✓' if sz == 0 else '✗ 崩'))
