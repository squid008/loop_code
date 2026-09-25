# -*- coding: utf-8 -*-
"""★★★★ 守门：并行调度器的**候选公平排队**（2026-09-23 新增；命名 `_test_*` ⇒ 进全量回归 ✓）。

为什么要有它（**真 bug**，用户实测发现 ✓）：
    用户："1000 池跑了 6 代，500 才跑 1 代？出问题了吧"
  病根**不在引擎、不在内存**，而在候选顺序 ✗：
    · 候选来自 `en`（**`set`** ⇒ 迭代顺序任意、同一进程里固定不变 ✗）
    · 启动只取 `cand[0]` ⇒ **排前面那个池每次空槽都抢到** ✗
    · 且**完全不看 `gens`**（谁欠配额、谁等得久，一律不看 ✗）
  实测（09-22 22:47 → 09-23 08:18，9.5 小时）：500 **只 1 代**、300 **连跑 13 代**；
  日志实证"槽位刚空就被抢"：`00:25:07 [END] pool=500` ⇒ `00:25:07 [START] pool=300` ✗
  危害不止不公平：收轮判据是"每池 ≥ `min_gens_per_round` 代" ⇒ 被饿的池永远攒不够
  ⇒ `cand` 永不为空 ⇒ **轮末全局收尾从不执行** ✗✗（v1.21.18 治过的症状换入口复发 ✗）

本守门钉三件：
  【1】静态：候选**不再**遍历 `set`；排序走 `fair_order`；启动时记 `last_start` ✓
  【2】功能：`fair_order` 的规则（欠账优先 / 等得久优先 / 没跑过的先上 / 确定性）
        —— 且**复现 09-23 现场**（同一批输入：旧逻辑选 300 ✗ ⇒ 现在必须选 500 ✓）
  【3】功能：**不改语义**（候选集合不增不减 · 单独一个候选照样返回它 ⇒ 快池照旧一直领 ✓）
"""
import io
import os
import re
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


print('[1] 静态：候选顺序不再靠 `set` 碰运气，且记了 FIFO 时间戳')
chk('有纯函数 fair_order（⇒ 可单测 ✓）', 'def fair_order(' in PR)
chk('★ 候选**从有序名单** `_en_list` 生成（`candidate_pools(_en_list, …)` + `for p in en_list` ✓）',
    re.search(r'cand = candidate_pools\(_en_list, st, launched, deferred, killed_user\)', PR) is not None
    and re.search(r'def candidate_pools\(', PR) is not None
    and re.search(r'for p in en_list', PR) is not None)
chk('★ 不再从 `set` 生成候选（`cand = [p for p in en` 那种老写法必须绝迹 ✗）',
    re.search(r'cand = \[p for p in en\b', PR) is None)
chk('★ 候选排过序（`cand = fair_order(cand, gens, last_start, min_gens_per_round` ✓）',
    re.search(r'cand = fair_order\(cand, gens, last_start, min_gens_per_round', PR) is not None)
chk('★ 启动时记 `last_start[p] = time.time()`（FIFO 的输入 ✓）',
    'last_start[p] = time.time()' in PR)
chk('本轮有 `last_start = {}` 初始化',
    re.search(r'^\s+last_start = \{\}', PR, re.M) is not None)
chk('`_en_list` 是**列表**（保序），`en` 仍是 set（成员判断 ✓）',
    re.search(r'_en_list = list\(ctl\.get\(', PR) is not None
    and re.search(r'^\s+en = set\(_en_list\)', PR, re.M) is not None)

print()
print('[2] 功能：fair_order 的规则（含**复现 09-23 现场**）')
try:
    import parallel_runner as _PRM
    _fo = _PRM.fair_order
    _ok = True
except Exception as _e:                                                       # noqa: BLE001
    _fo, _ok = None, False
    print('  ✗ 导入 parallel_runner 失败：%r' % (_e,))
    FAIL.append('导入 parallel_runner 失败：%r' % (_e,))

if _ok:
    T0, T1, T2, T3 = 1000.0, 2000.0, 3000.0, 4000.0
    EN = ['1000', '300', '500']          # 控制文件里的书写顺序（= 排序的最后一道 tie-break ✓）

    # ★★ 规则①：**欠账优先** —— 已跑够配额的（300 已 13 代）要给还欠的（500 只 1 代）让位
    #    ⚠ 关键：这里故意让 300 的 last_start **更早**（它等得更久）⇒ 若没有规则①，300 会赢 ✗
    _r = _fo(['300', '500'], {'1000': 6, '300': 13, '500': 1},
             {'1000': T0, '300': T1, '500': T2}, 3, EN)
    chk('① 欠账优先：500（1/3 代）排在 300（13/3 代）前 ✓（即使 300 等得更久）',
        _r == ['500', '300'], '得到 %r' % (_r,))

    # ★★ 规则②：**等得久优先（FIFO）** —— 复现 09-23 00:25 现场：
    #    500 于 00:25 跑完被挤出候选（last_start 更早），300 是**刚启动**的那个（last_start 最新）
    #    gens：300=1、500=1（都欠配额）⇒ 必须选 **500** ✓（旧逻辑选 300 ✗ 就是这个 bug ✓）
    _r = _fo(['300', '500'], {'300': 1, '500': 1},
             {'500': T1, '300': T2}, 3, EN)
    chk('② FIFO：500（早就在等）排在**刚启动过的** 300 前 ✓（09-23 现场复现 ✓）',
        _r[0] == '500', '得到 %r' % (_r,))

    # ★★ 规则③：**没跑过的先上**（`last_start` 缺省 = 0.0 ✓）
    _r = _fo(['300', '500'], {'500': 1}, {'500': T3}, 3, EN)
    chk('③ 没跑过的 300（last_start 缺省）排在 500 前 ✓',
        _r[0] == '300', '得到 %r' % (_r,))

    # ★★ 同分时的**确定性**：打乱输入顺序 ⇒ 结果一样（不许再看运气 ✗）
    _a = _fo(['300', '500', '1000'], {}, {}, 3, EN)
    _b = _fo(['500', '1000', '300'], {}, {}, 3, EN)
    chk('④ 确定性：输入顺序打乱 ⇒ 输出一致（tie-break 走 `order` ✓）',
        _a == _b == EN, '得到 %r / %r' % (_a, _b))

    # ★★★ 规则⑤：**慢池在跑 ⇒ 快池照旧一直领**（09-19 的诉求不能丢 ✗）
    #    50 单独在候选（300/500 都在跑 ⇒ 压根不在候选里）⇒ 必须原样返回它 ✓
    _r = _fo(['50'], {'50': 7}, {'50': T0}, 3, EN)
    chk('⑤ 单候选原样返回（快池不因排序而空转 ✓）', _r == ['50'], '得到 %r' % (_r,))

    # ★★★ 规则⑥：**不改语义** —— 候选集合一个不增不减 ✓
    _in = ['1000', '300', '500']
    chk('⑥ 候选**集合**不变（只排序，不新增/不剔除 ✓）',
        sorted(_fo(_in, {'300': 5}, {'1000': T1}, 3, EN)) == sorted(_in))

    # ★★ 规则⑦：同在"欠账组"里 ⇒ 按 last_start（等得久先）；**不是**按"欠得多先" ✗
    _r = _fo(['500', '1000'], {'500': 1, '1000': 2}, {'500': T1, '1000': T0}, 3, EN)
    chk('⑦ 欠账组内按 FIFO（1000 等得更久 ⇒ 1000 先 ✓，而非"欠得多先" ✗）',
        _r[0] == '1000', '得到 %r' % (_r,))

print()
if FAIL:
    print('✗ 候选公平排队守门失败 %d 项：' % len(FAIL))
    for f in FAIL:
        print('   [FAIL] %s' % f)
    sys.exit(1)
print('✓ 候选公平排队：全过（欠账优先 + FIFO + 确定性，且不改既有语义 ✓）')
sys.exit(0)
