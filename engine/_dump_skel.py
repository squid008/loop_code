# -*- coding: utf-8 -*-
"""一次性: dump state.bank 的骨架(skeleton)分布, 为"同骨架归并+初始化FSA冻结"做准备
用法: D:\\miniconda3\\envs\\rqdata\\python.exe _dump_skel.py
"""
import os
import pickle
from loop_engine import Node, skeleton

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, 'loop_state.pkl')

with open(STATE, 'rb') as f:
    st = pickle.load(f)

print(f"bank 因子数: {len(st.get('bank', []))}")
print(f"fsa keys: {len(st.get('fsa', {}))}  cfg: {st.get('cfg', {})}")
print()
sk = {}
for i, nd in enumerate(st.get('bank', [])):
    e = str(nd)
    s = skeleton(nd)
    sk.setdefault(s, []).append(i)
    print(f"  bank[{i}] skel={s}")
    print(f"         expr={e}")
print()
print("骨架分组:")
for s, idx in sorted(sk.items(), key=lambda kv: -len(kv[1])):
    print(f"  {len(idx)}x  {s}  <- bank{idx}")
