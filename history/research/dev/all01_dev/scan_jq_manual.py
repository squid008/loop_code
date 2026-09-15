# -*- coding: utf-8 -*-
"""扫描聚宽因子手册: 提取因子名/分类, 输出 UTF-8 清单, 供挑选可实现的因子"""
import os
import re
import io

SRC = r'D:\工作\聚宽手册.txt'
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'jq_manual_index.txt')

raw = open(SRC, 'rb').read()
txt = None
for enc in ['gbk', 'gb18030', 'utf-8']:
    try:
        txt = raw.decode(enc)
        break
    except Exception:
        continue
if txt is None:
    txt = raw.decode('gbk', errors='ignore')

lines = txt.splitlines()
print(f"总行数 {len(lines)}, 编码 {enc}")

# 找分类标题(形如 # xxx / ## xxx 或 中文独立行)
heads = []
for i, ln in enumerate(lines):
    s = ln.strip()
    if not s:
        continue
    if re.match(r'^#+\s*\S', s) or re.match(r'^第[一二三四五六七八九十]+[章节]', s):
        heads.append((i, s))
print(f"\n标题/分类 {len(heads)} 处:")
for i, s in heads[:60]:
    print(f"  L{i:>5}: {s[:60]}")

# 因子名: 全小写下划线标识符(长度>=4), 统计出现次数
names = {}
for ln in lines:
    for m in re.findall(r'\b([a-z][a-z0-9_]{3,40})\b', ln):
        names[m] = names.get(m, 0) + 1
cand = sorted([k for k, v in names.items() if v >= 2])
print(f"\n候选因子标识符 {len(cand)} 个(出现>=2次)")
with open(OUT, 'w', encoding='utf-8') as f:
    f.write(f"聚宽手册 {SRC}\n总行数 {len(lines)}\n\n== 分类标题 ==\n")
    for i, s in heads:
        f.write(f"L{i}: {s}\n")
    f.write(f"\n== 候选因子标识符({len(cand)}) ==\n")
    f.write('\n'.join(cand))
print(f"已存 {OUT}")

# 打印前 80 行样本, 了解格式
print("\n---- 前 60 行 ----")
for ln in lines[:60]:
    print(ln[:100])
