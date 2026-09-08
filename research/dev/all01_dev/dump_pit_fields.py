# -*- coding: utf-8 -*-
"""导出 PIT 单文件全部字段名到 utf-8 文本"""
import os
import sys
import h5py

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pit_fields_full.txt')
with h5py.File(r'E:\rq\finance\pit\000001.XSHE.h5', 'r') as f:
    ks = sorted(f['fields'].keys())
with open(OUT, 'w', encoding='utf-8') as g:
    for k in ks:
        g.write(k + '\n')
print(len(ks), 'fields ->', OUT)
