# -*- coding: utf-8 -*-
"""导出聚宽手册关键章节(估值表/财务指标表/因子库说明/示例因子)为 UTF-8"""
import os

SRC = r'D:\工作\聚宽手册.txt'
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'jq_dump.txt')
raw = open(SRC, 'rb').read()
txt = None
for enc in ['gbk', 'gb18030', 'utf-8']:
    try:
        txt = raw.decode(enc)
        break
    except Exception:
        continue
lines = txt.splitlines()

SECS = [('估值表 valuation', 2232, 2340),
        ('财务指标表 indicator', 2451, 2620),
        ('因子库/中性化说明', 5090, 5270),
        ('示例因子', 5940, 6100)]
out = []
for name, a, b in SECS:
    out.append('\n' + '=' * 90)
    out.append(f'== {name}  L{a}~{b} ==')
    out.append('=' * 90)
    for j in range(a, min(b, len(lines))):
        out.append(f'{j}: {lines[j][:200]}')
with open(OUT, 'w', encoding='utf-8') as f:
    f.write('\n'.join(out))
print('ok')
