# -*- coding: utf-8 -*-
"""★★★ 守门：收尾"该算谁"的口径必须含**曾入库过的全部历史** ✓

背景（2026-09-20 用户之问）：
  「刚入库又被移出的因子，都不会自动算指标/出曲线吗？」
  ⇒ 真因：收尾三工具（facs / 指标 / 曲线）的名单原来只有两个来源
    ① `docs/factor_registry.json` ② `loop_state_*.pkl` 的 `bank`
    —— **两者都只反映"现在的归属"** ✗ ⇒ 因子若在「**入库** → 收尾」这段空窗里离开 bank
    （且库文档 md 还没登记它 ✗）⇒ **三工具都看不见它** ✗ ⇒ 指标/曲线永久缺失 ✗
  ⇒ 修：新增第三源 **`docs/library_entries.jsonl`**（引擎在**入库那一刻**写的 append-only 日志 ✓）
     ⇒ "曾入库过"的因子**永远**会被补算 ✓（`--only-new` 保证不重复算 ✓）

本守门钉住：
  1. `build_facs` 里必须有第三源 `_entries_nodes()`，且 `load_bank_nodes` 真的合并了它 ✓
  2. 解析历史 expr **必须给 `max_size=10**9`** ✓
     （`parse_expr` 默认上限本是防 LLM 超大式子的护栏 ✗ —— 对已入库因子没意义，
      却会让合法公式**静默返回 None** ✗；2026-09-14 全A `F01` 就栽在这 ✓）
  3. **功能校验**：对每个池，`load_bank_nodes()` 必须覆盖 JSONL 里该池**全部** expr ✓
  4. JSONL 由**引擎入库那一刻**写（不是收尾补写 ✓）
"""
import io
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ROOT = r'D:\loop_code'
BF = io.open(os.path.join(ROOT, 'tools', 'build_facs.py'), encoding='utf-8').read()
ENG = io.open(os.path.join(ROOT, 'engine', 'loop_engine.py'), encoding='utf-8').read()
J = os.path.join(ROOT, 'docs', 'library_entries.jsonl')

FAIL = []


def chk(desc, cond, hint=''):
    print('  %s %s' % ('✓' if cond else '✗', desc))
    if not cond:
        FAIL.append(desc + ('（%s）' % hint if hint else ''))


print('[1] 代码：三源合并 + 解析放开尺寸上限')
chk('build_facs 有第三源 `_entries_nodes()`', 'def _entries_nodes()' in BF)
chk('load_bank_nodes 合并了它', '_ent = _entries_nodes().get(pool) or {}' in BF
    and 'out.setdefault(k, v)' in BF)
chk('★ 解析历史 expr 用 `max_size=10 ** 9`（否则合法公式会被静默丢弃 ✗）',
    'parse_expr(str(expr), max_size=10 ** 9)' in BF)
chk('失败只告警不炸（与 registry 同纪律）', 'n_bad' in BF)

print()
print('[2] 数据：JSONL 是**入库那一刻**写的（引擎侧）')
chk('引擎有入库事件日志写入', 'library_entries.jsonl' in ENG or 'LIB_ENTRIES' in ENG)
chk('写入点是"入库那一刻"（docstring 写明 ✓）', '入库那一刻' in ENG or '入库那一刻写' in BF)

print()
print('[3] ★ 功能校验：收尾名单覆盖"入库历史"里的每个池、每个因子')
sys.path.insert(0, os.path.join(ROOT, 'engine'))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
try:
    import build_facs as B
    rows = [json.loads(l) for l in io.open(J, encoding='utf-8') if l.strip()]
    pools = sorted(set(r['pool'] for r in rows if r.get('pool') and r.get('expr')))
    print('     JSONL 共 %d 条，涉及池：%s' % (len(rows), pools))
    for pool in pools:
        got = B.load_bank_nodes(pool)
        want = set(r['expr'] for r in rows if r.get('pool') == pool)
        miss = want - set(got.keys())
        chk('池 %-5s：名单 %d 个 ⊇ 入库历史 %d 个（缺 %d）'
            % (pool, len(got), len(want), len(miss)), not miss,
            '缺：%s' % list(miss)[:2])
except Exception as e:
    chk('功能校验可运行', False, '%s: %s' % (type(e).__name__, e))

print()
if FAIL:
    print('✗ 失败 %d 项：' % len(FAIL))
    for f in FAIL:
        print('   - %s' % f)
    sys.exit(1)
print('✓ 全过：收尾口径已含"曾入库过的全部历史" ⇒ 不会再有"刚入库就被移出 ⇒ 没指标没曲线" ✗')
sys.exit(0)
