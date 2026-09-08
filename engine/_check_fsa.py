# -*- coding: utf-8 -*-
"""dry-run 验证 FSA 改造: 用 gen11 现场 state 检查
1) bank 骨架分布(是否存在同骨架参数变体堆叠)
2) 若按新逻辑以 l1 为样本统计, 会冻结哪些骨架
3) 新入库闸门(冻结禁入 + 同骨架上限)是否会拦住后续堆叠
"""
import os
import pickle
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import loop_engine as E
import __main__
__main__.Node = E.Node     # state 由 python loop_engine.py(主模块) 写入, 类名是 __main__.Node
__main__.collect = E.collect

with open(E.STATE, 'rb') as f:
    st = pickle.load(f)

bank = st.get('bank', [])
l1 = st.get('last_l1', None)
print('bank 入库因子:', len(bank))
from collections import Counter
bc = Counter(E.skeleton(x) for x in bank)
print('bank 骨架分布:')
for s, c in bc.most_common():
    print(f'  {c:2d}  {s}')

print('\nl1 候选数:', 0 if l1 is None else len(l1))
if l1 is not None:
    cov = Counter()
    for _, r in l1.iterrows():
        cov.update(E.subtree_skels(r['node']))
    thr = max(2, round(len(l1) * 0.15))
    print(f'冻结阈值 thr>={thr}/{len(l1)} (15%)')
    print('超限骨架(会被冻结):')
    hit = 0
    for s, c in cov.most_common(20):
        flag = '  <== 冻结' if c >= thr else ''
        if c >= thr:
            hit += 1
        print(f'  {c:3d}  {s}{flag}')
    if not hit:
        print('  (无)')

# 模拟入库闸门: 若 gen11 的通过者再入一次库
print('\n入库闸门 dry-run(bank_skel_max=1):')
skel_cnt = Counter(E.skeleton(x) for x in bank)
for x in bank:
    s = E.skeleton(x)
    if skel_cnt[s] > 1:
        print(f'  骨架已有 {skel_cnt[s]} 个(上限1), 新同骨架通过者将被拦下: {s}')
        break
