# -*- coding: utf-8 -*-
"""抽取中金 Loop Engineering 研报文本到 ai_test/cicc_loop.txt (供检索, 可随时删除)"""
import pdfplumber, re, sys

SRC = r'D:\工作\研报\中金：基于Loop Engineering的自动化因子发现引擎.pdf'
OUT = r'd:\rqalpha_demo\ai_test\cicc_loop.txt'

pages = []
with pdfplumber.open(SRC) as pdf:
    n = len(pdf.pages)
    for i, pg in enumerate(pdf.pages):
        try:
            t = pg.extract_text() or ''
        except Exception:
            t = ''
        pages.append(f'\n===== PAGE {i+1}/{n} =====\n' + t)
    print(f'pages={n} chars={sum(len(p) for p in pages)}')

txt = ''.join(pages)
# 去掉孤立换行, 便于检索中文整句
txt = re.sub(r'(?<=[^。；：\n])\n(?=[^ \t\n])', '', txt)
with open(OUT, 'w', encoding='utf-8') as f:
    f.write(txt)
print('saved ->', OUT)
