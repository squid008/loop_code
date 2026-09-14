# -*- coding: utf-8 -*-
"""_doc_outline.py — 打印文档的结构大纲 + 各节体量（整理 roadmap / 审计文档用）

用法:
    python tools/_doc_outline.py docs/factor_roadmap.md
    python tools/_doc_outline.py docs/factor_roadmap.md --depth=3
"""
import io
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

a = sys.argv[1:]
if not a:
    print(__doc__)
    sys.exit(0)
path = a[0]
depth = 3
for x in a:
    if x.startswith('--depth='):
        depth = int(x.split('=', 1)[1])

t = io.open(path, encoding='utf-8', errors='replace').read()
lines = t.splitlines()
print('=' * 100)
print('{}  —— {} 字符 / {} 行 / {:.0f} KB'.format(
    path, len(t), len(lines), os.path.getsize(path) / 1024.0))
print('=' * 100)

# 标题 -> 行号 -> 体量（到下一个同级或更高级标题）
# ⚠ 必须**跳过 ``` 围栏代码块**：否则代码里的 `# 注释`（shell/python/yaml）会被误判成标题
#   ⇒ 2026-09-14 首次跑时把 `factors/runner.py 等多处` 这类**引用路径**当成了 L1 标题。
heads = []
_infence = False
_fence = ''
for i, l in enumerate(lines):
    s = l.strip()
    if s.startswith('```') or s.startswith('~~~'):
        if not _infence:
            _infence, _fence = True, s[:3]
        elif s.startswith(_fence):
            _infence = False
        continue
    if _infence:
        continue
    m = re.match(r'^(#{1,6})\s+(.+)$', l)
    if m:
        heads.append((i, len(m.group(1)), m.group(2).strip()))
for k, (i, lv, txt) in enumerate(heads):
    if lv > depth:
        continue
    # 结束行：下一个 level <= lv 的标题
    end = len(lines)
    for j, lv2, _ in heads[k + 1:]:
        if lv2 <= lv:
            end = j
            break
    size = sum(len(x) for x in lines[i:end])
    print('{}{:<4s} L{:<6d} {:>6d} 字  {}'.format(
        '  ' * (lv - 1), '#' * lv, i + 1, size, txt[:110]))
print()
print('总标题数: {}（显示 {}/{} 级以内）'.format(len(heads), depth, depth))
