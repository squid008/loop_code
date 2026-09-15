# -*- coding: utf-8 -*-
"""定位聚宽手册中的因子清单章节(质量/成长/风险/每股/情绪/基础/估值/技术)"""
import os
import re

SRC = r'D:\工作\聚宽手册.txt'
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'jq_factor_sections.txt')

raw = open(SRC, 'rb').read()
txt = None
for enc in ['gbk', 'gb18030', 'utf-8']:
    try:
        txt = raw.decode(enc)
        break
    except Exception:
        continue
lines = txt.splitlines()

KW = ['质量因子', '成长因子', '风险因子', '每股因子', '情绪因子', '基础因子',
      '估值因子', '技术指标', '财务指标', '因子名', 'valuation', 'indicator',
      'quality', 'growth', 'per_share', 'emotion', 'basal', 'risk']
hits = []
for i, ln in enumerate(lines):
    for k in KW:
        if k in ln:
            hits.append((i, k, ln.strip()[:80]))
            break

out = [f'命中 {len(hits)} 处']
for i, k, s in hits:
    out.append(f'L{i}: [{k}] {s}')

# 输出前 8 个命中位置的上下文(各 45 行)
out.append('\n' + '=' * 80)
for i, k, s in hits[:8]:
    out.append(f'\n----- L{i} [{k}] {s} -----')
    for j in range(i, min(i + 45, len(lines))):
        out.append(f'{j}: {lines[j][:160]}')

with open(OUT, 'w', encoding='utf-8') as f:
    f.write('\n'.join(out))
print('ok', len(hits))
