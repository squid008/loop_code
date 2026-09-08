# -*- coding: utf-8 -*-
"""验证 失败模式库 + 跨量纲审查 两个新机制(dry-run, 不跑回测)"""
import os
import pickle
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import loop_engine as E
import __main__
__main__.Node = E.Node
__main__.collect = E.collect

def leaf(f): return E.Node(f, [])
def op(o, a, b=None): return E.Node(o, [a] if b is None else [a, b])

print('== 1) 跨量纲审查: 荒谬组合应被拒 ==')
for name, nd in [
    ('close+volume(拒)', op('add', leaf('close'), leaf('volume'))),
    ('close-ret(拒)', op('sub', leaf('close'), leaf('ret'))),
    ('mktcap+turnover(拒, M vs A)', op('add', leaf('mktcap'), leaf('turnover'))),
    ('div(x,x)(拒)', op('div', leaf('turn_ratio'), leaf('turn_ratio'))),
    ('sub(x,x)(拒)', op('sub', leaf('close'), leaf('close'))),
    ('corr(close,volume)(应过)', op('corr20', leaf('close'), leaf('volume'))),
    ('mul(turn_ratio,ts_mean(volume))(应过)', op('mul', leaf('turn_ratio'), op('ts_mean5', leaf('volume')))),
    ('add(rank(close),rank(volume))(应过,Z+Z)', op('add', op('cs_rank', leaf('close')), op('cs_rank', leaf('volume')))),
    ('log(turnover)+log(mktcap)(应过,L+L)', op('add', op('log', leaf('turnover')), op('log', leaf('mktcap')))),
    ('add(cs_demean(log(turnover)),ts_std(volume))(Z vs V拒)', op('add', op('cs_demean', op('log', leaf('turnover'))), op('ts_std5', leaf('volume')))),
]:
    why = E.review_expr(nd)
    print(f"  {name}: {'通过' if why is None else '拒绝 -> ' + why[:60]}")

print('\n== 2) 跨量纲审查: gen11 已入库 5 个同骨架不误杀 ==')
with open(E.STATE, 'rb') as f:
    st = pickle.load(f)
bank = st.get('bank', [])
bad_hit = 0
for i, x in enumerate(bank):
    why = E.review_expr(x)
    if why:
        bad_hit += 1
        print(f"  !! 误杀 #{i}: {why[:80]}")
        print(f"     expr: {x}")
print(f"  bank {len(bank)} 个中误杀 {bad_hit} 个", 'OK' if bad_hit == 0 else '!!')

print('\n== 3) 失败模式库逻辑 ==')
flib = {}
for _ in range(3):
    E.flib_mark(flib, op('add', leaf('close'), leaf('close')), 3, False, 'ic')  # 同骨架3次失败
E.flib_mark(flib, op('sub', leaf('ret'), leaf('overnight')), 3, False, 'ic')
E.flib_mark(flib, op('sub', leaf('ret'), leaf('overnight')), 3, False, 'ic')
E.flib_mark(flib, op('sub', leaf('ret'), leaf('overnight')), 4, True, '')       # 第4代成功1次
print('  样例1 (3次全败): bad?', 'add(close,close)' in E.bad_skels(flib, 3))
print('  样例2 (2败1成):  bad?', 'sub(ret,overnight)' in E.bad_skels(flib, 4))
flib2 = E.fail_lib_cleanup(flib, 10)   # keep_gen=5, 样例在代3/4 -> 10-5=5, 3/4>=5? 否
print('  清理(keep5, 在代10): 样例1保留?', 'add(close,close)' in flib2, '(应False=已淘汰)')
print('  bad_skels 在代10:', len(E.bad_skels(flib, 10)), '(应0, 全过期)')
print('\n  flib 内容:')
for s, e in flib.items():
    print('   ', s, e)
