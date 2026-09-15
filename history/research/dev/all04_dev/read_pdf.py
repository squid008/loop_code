# -*- coding: utf-8 -*-
"""提取研报 PDF 全文 -> UTF-8 文本, 便于检索因子公式/生成机制"""
import os
import sys
import pdfplumber

SRC = sys.argv[1]
OUT = sys.argv[2]
ONLY = None
if len(sys.argv) > 3:
    ONLY = [int(x) for x in sys.argv[3].split(',')]      # 1-based 页码

os.makedirs(os.path.dirname(OUT), exist_ok=True)
parts = []
with pdfplumber.open(SRC) as pdf:
    n = len(pdf.pages)
    print(f"总页数 {n}")
    rng = ONLY if ONLY else range(1, n + 1)
    for i in rng:
        p = pdf.pages[i - 1]
        t = p.extract_text() or ''
        parts.append(f"\n\n===== [第 {i} 页] =====\n{t}")

txt = ''.join(parts)
with open(OUT, 'w', encoding='utf-8') as f:
    f.write(txt)
print(f"已存 {OUT}  ({len(txt):,} 字符)")
