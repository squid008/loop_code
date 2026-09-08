# -*- coding: utf-8 -*-
"""临时: dump loop_state.pkl 当前 bank / cfg 明细"""
import os
import sys
import pickle
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import loop_engine as E

# pickle 反序列化需要 Node 在加载方命名空间可见
from loop_engine import Node

st = pickle.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'loop_state.pkl'), 'rb'))
print('bank n =', len(st['bank']))
for i, b in enumerate(st['bank']):
    print('  b%d:' % i, b)
print('seeds n =', len(st['seeds']))
print('n_tested =', st.get('n_tested'))
print('cfg =', st.get('cfg'))
fsa = st.get('fsa', {})
print('fsa entries =', len(fsa))
top = sorted(fsa.items(), key=lambda x: -x[1])[:10]
for k, v in top:
    print('  fsa', k, v)
