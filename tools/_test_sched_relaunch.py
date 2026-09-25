# -*- coding: utf-8 -*-
"""★★★★★ 守门：**「本轮启动过、又被停掉」的池，本轮内重新启用必须能回到候选**（2026-09-25；§1.32）。

为什么（用户 2026-09-25 19:5x 实测）：_"我重新开启（沪深300），它怎么要排队了？"_
  ⇒ 300 在 19:31 **已启动过一次**（20 秒后被用户停掉）⇒ 留在 `launched` 里 ✗；
    而 `launched` 原来**只有**两处 `discard`（"跑完一代继续领" / "崩溃重试"）⇒
    "被用户停掉"的池**本轮再也回不来** ✗；同时它 0 代 ⇒ 收轮判据 `_again` 恒 True
    ⇒ **本轮永不收口、轮末全局收尾不执行** ✗✗ ⇒ 死等（不是"排队一会儿"）✓

本守门钉三件：
  【1】功能 `candidate_pools()`：**killed_user 逃逸口**（本次修的点 ✓）
        ★ 负向：无 `killed_user`（= 旧逻辑）⇒ 被 `launched` 挡住 ⇒ 返回 [] ✗
  【2】功能：`deferred` 逃逸口 / `st` 一票否决 仍按原样（回归不破 ✓）
  【3】静态：`_reap` 被停时真的记 `killed_user`；循环真的调 `candidate_pools` ✓
"""
import io
import os
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

PR = io.open(os.path.join(HERE, 'parallel_runner.py'), encoding='utf-8').read()
FAIL = []


def chk(desc, cond, hint=''):
    print('  %s %s' % ('✓' if cond else '✗', desc))
    if not cond:
        FAIL.append(desc + ('（%s）' % hint if hint else ''))


print('[1] 功能 `candidate_pools()`：**killed_user 逃逸口**（本次修的点）')
try:
    import parallel_runner as P
    _ok = True
except Exception as e:                                                          # noqa: BLE001
    _ok = False
    print('  ✗ 导入 parallel_runner 失败：%r' % (e,))
    FAIL.append('导入 parallel_runner 失败：%r' % (e,))

if _ok:
    # ★★ 复现本次现场：all 在跑、300 本轮已启动又被停 ⇒ 用户重新启用（stopped 清空）
    _got = P.candidate_pools(['all', '300'], set(), {'all', '300'}, {}, {'300': {'300'}})
    chk('复现：300 被停后又启用 ⇒ 回到候选（本轮再上）✓', _got == ['300'],
        '期望 [\'300\']，实得 %r' % (_got,))
    # 负向（= 旧逻辑）：没有 killed_user 记录 ⇒ 300 被 launched 挡住 ✗
    _old = P.candidate_pools(['all', '300'], set(), {'all', '300'}, {}, {})
    chk('负向：无 killed_user ⇒ 300 仍被 launched 挡住（这就是旧的 bug ✗）', _old == [],
        '期望 []，实得 %r' % (_old,))
    # killed_user 里没有该池 ⇒ 照样挡住
    _miss = P.candidate_pools(['all', '300'], set(), {'all', '300'}, {}, {'500': {'500'}})
    chk('killed_user 没记它 ⇒ 仍挡住', _miss == [], '期望 []，实得 %r' % (_miss,))

print('\n[2] 功能：`st` 一票否决 / `deferred` 逃逸口 / 正常候选（回归不破）')
if _ok:
    chk('已单独停的池永不进候选（即使 killed_user 记了它、也在 launched 里）',
        P.candidate_pools(['300'], {'300'}, {'300'}, {}, {'300': {'300'}}) == [])
    chk('deferred 逃逸口：你放回来（不在 st）⇒ 上',
        P.candidate_pools(['300'], set(), set(), {'300': {'300'}}, {}) == ['300'])
    chk('deferred 不逃逸：快照里没有它 ⇒ 挡住',
        P.candidate_pools(['300'], set(), set(), {'300': set()}, {}) == [])
    chk('从未启动、未停的池 ⇒ 正常候选',
        P.candidate_pools(['500'], set(), set(), {}, {}) == ['500'])
    chk('仍在 launched 且没被"停-再启用" ⇒ 挡住（= 正在跑 / 已领过活的池，不重复候选）',
        P.candidate_pools(['all'], set(), {'all'}, {}, {}) == [])

print('\n[3] 静态：接线在位')
chk('`_reap` 被停路径真的记 `killed_user[t[\'pool\']]`',
    "killed_user[t['pool']] =" in PR and 'if t.get(\'killed\') and not stopped_by_user:' in PR)
chk('循环真的改调纯函数 `candidate_pools(...)`',
    'cand = candidate_pools(_en_list, st, launched, deferred, killed_user)' in PR)
chk('`killed_user = {}` 每轮初始化在位', 'killed_user = {}' in PR)

print()
if FAIL:
    print('★★ 失败 %d 项：' % len(FAIL))
    for f in FAIL:
        print('   ✗ %s' % f)
    sys.exit(1)
print('★★ 全部通过 ✓')
