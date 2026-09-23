# -*- coding: utf-8 -*-
"""★★★★★ 守门：**"单独停池"时的补位规则 + 收轮判据**（2026-09-23 新增；进全量回归 ✓）。

为什么（用户 2026-09-23 实测）：
  _"我一键开启了全部，然后把全A停止了，为啥上证50池没有马上启动起来，一直显示并行中？"_
  ⇒ 两处叠加的**真问题** ✗：
    ① **补位规则写宽了** ✗：本意是"我停一个池，**别自动把闲置池顶上来**"（用户 09-16 的诉求 ✓），
       实现却把**所有还没启动的池**都记进 `deferred` ✗ —— 连"**正在排队等槽位**"的 50 也一起挡住 ✗
       （50 那会儿是 `待启动 1` = 合法排队 ✓）⇒ "停一个 ⇒ 排队的顶上"这个**本该发生**的行为消失 ✗
    ② **收轮判据被 deferred 卡死** ✗：判据是"每个启用池都完成 >= `min_gens` 代"，
       而 deferred 池**本轮永远跑不了** ⇒ 永远 0 代 ⇒ 判据永不成立 ⇒ **本轮永远收不了口** ✗✗
       ⇒ `cand` 永不为空 ⇒ **轮末全局收尾（跨池审查/精选池/指标表/登记表）永不执行** ✗
       （与 v1.21.20「1 代判据」、v1.21.38「被饿的池」是**同一类**问题，这次入口是 `deferred` ✗）

本守门钉四件：
  【1】功能 `topup_defer_list()`：**只 defer 真闲置**；**在排队的池不 defer** ✓
        ★ 复现今天现场：`waiting={50}` ⇒ 必须返回 **[]**（旧逻辑会返回 `['50']` ✗）
  【2】功能 `pending_pools()`：**排掉 deferred** ✓ ⇒ 收轮判据不再被卡死
        ★ 复现：`deferred={'50':…}` ⇒ 结果**不含 50**（旧判据含 50 ✗）
  【3】静态：两处接线真的用上了这两个纯函数 ✓；`waiting` 真的被记录 ✓
  【4】静态：内存闸门**不再在内层空转**（`time.sleep(15)` 必须绝迹 ✗）——
        它会让调度器"永远不去收割已跑完的引擎" ⇒ 内存腾不出来 ⇒ 死等 ✗
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


print('[1] 功能 `topup_defer_list()`：只 defer 真闲置；**在排队的池不 defer** ✓')
try:
    import parallel_runner as P
    _ok = True
except Exception as e:                                                          # noqa: BLE001
    _ok = False
    print('  ✗ 导入 parallel_runner 失败：%r' % (e,))
    FAIL.append('导入 parallel_runner 失败：%r' % (e,))

if _ok:
    EN5 = ['all', '300', '500', '1000', '50']
    # ★★ 复现今天现场：5 池抢 4 槽 ⇒ 50 是"待启动 1"（合法排队 ✓）⇒ 用户停掉 all
    _r = P.topup_defer_list(EN5, {'all', '300', '500', '1000'}, {'50'})
    chk('★ 现场复现：停 all 时，**排队的 50 不被 defer**（返回空）✓',
        _r == [], '得到 %r' % (_r,))
    # 旧实现（不看 waiting）会得到 ['50'] ✗ ⇒ 用来证明"差异真的存在"
    _old = P.topup_defer_list(EN5, {'all', '300', '500', '1000'}, set())
    chk('★ 旧口径对照：不区分排队 ⇒ 会把 50 也 defer（`["50"]`）✗（两者结论相反 ✓）',
        _old == ['50'], '得到 %r' % (_old,))
    # 真闲置：本轮从没进过队列 ⇒ 照旧不自动补位（保住用户 09-16 的诉求 ✓）
    _r = P.topup_defer_list(['300', '500'], {'300'}, set())
    chk('真闲置的池**仍然不自动补位**（09-16 的诉求不丢 ✓）', _r == ['500'],
        '得到 %r' % (_r,))
    # 混合：300 已启动、500 在排队、all 闲置 ⇒ 只 defer all ✓
    _r = P.topup_defer_list(['all', '300', '500'], {'300'}, {'500'})
    chk('混合场景：只 defer `all`（闲置），**不 defer 排队的 500** ✓', _r == ['all'],
        '得到 %r' % (_r,))
    chk('全部已启动 ⇒ 没得 defer（返回空 ✓）',
        P.topup_defer_list(['300', '500'], {'300', '500'}, set()) == [])
    chk('空启用集 ⇒ 空（不炸 ✓）', P.topup_defer_list([], set(), set()) == [])

    print()
    print('[2] 功能 `pending_pools()`：**排掉 deferred** ⇒ 收轮判据不再被卡死 ✓')
    _pp = P.pending_pools(EN5, {'all'}, {'50': {'all'}})
    chk('★ 复现：`deferred={50}` ⇒ 待收轮名单**不含 50**（它能卡住收轮 ✗）',
        _pp == ['300', '500', '1000'], '得到 %r' % (_pp,))
    _old_pp = [x for x in EN5 if x not in {'all'}]          # 旧判据（不看 deferred）
    chk('★ 旧判据对照：**含 50** ✗（`50` 永远 0 代 ⇒ 判据永不成立 ⇒ 轮收不了口 ✗）',
        '50' in _old_pp)
    chk('有池被单独停 ⇒ 也不等它（`st` 里的一律排除 ✓）',
        P.pending_pools(['300', '500'], {'500'}, {}) == ['300'])
    chk('deferred 不影响别的池（没被 defer 的照旧欠账 ✓）',
        P.pending_pools(['300', '500'], set(), {'500': set()}) == ['300'])
    # 收轮判据的语义：待收轮名单里的池都攒够 K 代 ⇒ 才收口 ✓
    _g = {'300': 3, '500': 3, '1000': 3}
    _need = P.pending_pools(EN5, {'all'}, {'50': {'all'}})
    chk('★ 收口判定：三个在跑的池都到 3 代 ⇒ `any(<3)` 为 **False** ⇒ 能收口 ✓',
        not any(_g.get(x, 0) < 3 for x in _need))

print()
print('[3] 静态：两处接线真的用上了（否则纯函数是死代码 ✗）')
chk('`defer` 块用 `topup_defer_list(en, launched, waiting)` ✓',
    'topup_defer_list(en, launched, waiting)' in PR)
chk('收轮判据用 `pending_pools(en, st, deferred)` ✓',
    'pending_pools(en, st, deferred)' in PR)
chk('★ `waiting` 真的被记录（`waiting |= set(cand)` ✓）', 'waiting |= set(cand)' in PR)
chk('★ `waiting` 在**轮内**初始化（`waiting = set()` ✓）',
    'waiting = set()' in PR)
chk('日志会说清"在排队的池照旧顶上" ✓（用户看得见的解释 ✗ 不能只改行为）',
    '照旧顶上' in PR)

print()
print('[4] 静态：内存闸门**不再在内层空转**（`time.sleep(15)` 必须绝迹 ✗）')
# ⚠ 判据用带模块名的 `time.sleep(15)`：注释里引用的是不带前缀的写法（避免"被自己的注释绊倒" ✗）
chk('★ 内存不足时是 `break`（回外层收割 + 重算上限）而不是 `sleep(15); continue` ✗',
    'time.sleep(15)' not in PR)
chk('★ 日志里说清"本轮先不起，等内存腾出来"（看得见 ✓）',
    '等内存腾出来再试' in PR)

print()
if FAIL:
    print('✗ 失败 %d 项：' % len(FAIL))
    for x in FAIL:
        print('   - %s' % x)
    sys.exit(1)
print('✓ 全部通过：停池补位（只拦真闲置 / 排队中的照旧顶上）+ 收轮不被 deferred 卡死 + 内存闸门不空转')
