# -*- coding: utf-8 -*-
"""把几个研报 txt 的前几页摘要打印到 utf-8 文件(避免控制台 gbk 报错)"""
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'digest.txt')
files = [('广发 机器学习选股训练手册', r'D:\ai_test\all04_dev\gf_ml.txt', 3),
         ('兴业 图谱系列二十', r'D:\ai_test\all04_dev\xy_graph.txt', 3),
         ('华泰 行业资金流向图', r'D:\ai_test\all04_dev\ht_flow.txt', 3)]

lines = []
for nm, f, np_ in files:
    if not os.path.exists(f):
        lines.append(f"\n########## {nm}: 文件不存在")
        continue
    t = open(f, encoding='utf-8').read()
    t = re.sub(r'https?://\S+', '', t)
    pages = t.split('===== [第 ')
    lines.append('\n' + '#' * 74)
    lines.append(f"## {nm}  ({len(t):,} 字符, {len(pages)-1} 页)")
    lines.append('#' * 74)
    for p in pages[1:np_ + 1]:
        body = p.split('] =====')[-1].strip()
        body = re.sub(r'\n{3,}', '\n\n', body)
        lines.append(f"\n--- 第{p.split(' 页')[0]}页 ---")
        lines.append(body[:1200])
with open(OUT, 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))
print('ok', OUT)
