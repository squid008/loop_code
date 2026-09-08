# -*- coding: utf-8 -*-
"""检查 panel/universe/barra 的列数与行数(精简易读)"""
import os
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

for fn in ['panel.h5', 'universe.h5']:
    p = os.path.join(ROOT, fn)
    with pd.HDFStore(p, 'r') as st:
        ks = list(st.keys())
        d = st[ks[0]]
        print(f'{fn}: 键={[k.strip("/") for k in ks]} shape={d.shape}')
        print(f'   index: {d.index.min()} ~ {d.index.max()}  ({d.index.dtype})')
        print(f'   columns样例: {list(d.columns[:3])}... 共{len(d.columns)}列')

p = os.path.join(ROOT, 'barra.h5')
with pd.HDFStore(p, 'r') as st:
    ks = list(st.keys())
    print(f'barra.h5: {len(ks)} 键')
    d0 = st[ks[0]]
    print(f'   首键={ks[0].strip("/")} shape={d0.shape} index {d0.index.min()}~{d0.index.max()}')
