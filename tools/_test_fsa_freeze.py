# -*- coding: utf-8 -*-
"""_test_fsa_freeze.py — FSA 冻结「2→4→8 代封顶 + 冷却期遗忘 + 日志留痕」守门（2026-09-17 用户拍板）

用户原话：「先按 2→4→8 代封顶 + 日志留痕，时间先暂时不管」

## 为什么必须钉（这类改动**只会静默退化**）
旧规则 =「本代超阈值 ⇒ 冻结；**上代冻结的骨架本代不再出现 ⇒ 立刻解冻**」⇒ 冻结记忆**只活一代** ✗
⇒ 隔几代复发的结构完全拦不住（实测 120 个被冻结骨架里 7 个复发，间隔中位 2 / 最大 10 代 ✓）
新规则的全部价值在**跨代记账**（次数 / 剩余代数 / 冷却计数）⇒ 一旦：
  · 记账**不落盘**（或读不回）、或 · 递减/续期/翻倍的**顺序**抄错一行
⇒ 症状都只是"冻结又悄悄变回一代"，**日志里看不出异常** ✗ ⇒ 必须逐条钉死 ✓

## 钉什么
[1] 首次 ⇒ 冻结 2 代；★ **冻结期内本代不出现也保持冻结**（与旧规则的关键差别）
[2] 冻结期内又霸榜 ⇒ **续期**（回到本期数，**不叠加**）
[3] 冷却期内复发 ⇒ 4 代；再犯 ⇒ 8 代；★ **封顶后不再翻倍**（不是 16 ✗）
[4] 解冻后连续 `FSA_COOL_GENS` 代未超阈值 ⇒ **遗忘**（下次回到 2 代）+ 记账被清理
[5] 老 state 兼容（只有 `frozen` 列表、没有记账）⇒ 当"第 1 次"接管，**不臆造历史次数** ✓
[6] 日志留痕（"第 N 次 ⇒ 冻结 X 代" / 续期 / 到期解冻 / 遗忘计数）
[7] `frozen` 仍是**骨架字符串列表**，`fsa_frz` 才落盘记账（看板 frozen_n 口径不变 ✓）

用法: python tools/_test_fsa_freeze.py
"""
import contextlib
import io
import os
import sys
import types

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'engine'))

import pandas as pd                     # noqa: E402
import loop_engine as LE                # noqa: E402

OK = [0, 0]
N_NEUTRAL = 4          # 每代"无关"候选数
N_HIT = 6              # 每代"含目标骨架"的候选数 ⇒ 覆盖率 6/10 = 60% ≥ 15% ✓


def chk(desc, cond, hint=''):
    OK[0] += 1
    if not cond:
        OK[1] += 1
    print('  [{}] {}{}'.format('OK ' if cond else 'FAIL', desc,
                               '' if cond else ('  ← ' + hint if hint else '')))


def _nodes(with_hit):
    """构造一代 L1 的 node 列：`with_hit=False` ⇒ 本代完全不含目标骨架 ✓"""
    out = [LE.Node('ts_mean20', [LE.Node('sub', ['high', 'low'])]) for _ in range(N_NEUTRAL)]
    if with_hit:
        out += [LE.Node('ts_std20', [LE.Node('add', ['close', 'open'])]) for _ in range(N_HIT)]
    return out


def _step(with_hit, frozen, book):
    """跑一代 `_fsa_stats`（真函数），回 `(frozen, 日志文本)` ✓"""
    _nds = _nodes(with_hit)
    l1 = pd.DataFrame({'node': _nds, 'expr': ['e%d' % i for i in range(len(_nds))]})
    args = types.SimpleNamespace(fsa_th=0.15)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        frozen, _, _, _ = LE._fsa_stats(args, [], frozen, {}, l1, None, None, None, book)
    return frozen, buf.getvalue()


def t_sequence():
    S = LE.skeleton(LE.Node('ts_std20', [LE.Node('add', ['close', 'open'])]))
    print('\n[1] 首次冻结（2 代）+ ★ 冻结期内不出现也保持冻结')
    frozen, book = [], {}
    frozen, log = _step(True, frozen, book)
    chk('首代超阈值 ⇒ 冻结，期为 2 代（次数记 1）',
        S in frozen and book.get(S, {}).get('left') == 2 and book.get(S, {}).get('cnt') == 1,
        '实得 frozen=%s book=%s' % (S in frozen, book.get(S)))
    chk('★ 日志留痕「第 1 次 ⇒ 冻结 2 代」', '第 1 次' in log and '冻结 2 代' in log, log[:120])
    frozen, log = _step(False, frozen, book)
    chk('★★ 本代不再出现 ⇒ **仍然冻结**（旧规则会立刻解冻 ✗ —— 这条就是新机制的全部意义）',
        S in frozen, '实得 frozen=%s' % (frozen,))
    frozen, log = _step(False, frozen, book)
    chk('冻满 2 代 ⇒ 到期解冻，且冷却计数从 0 起',
        S not in frozen and book.get(S, {}).get('cool') == 0, '实得 %s' % book.get(S))
    chk('★ 日志留痕「解冻骨架…期满…再犯就翻倍」', '解冻骨架' in log and '期满' in log, log[:140])

    print('\n[2] 冷却期内复发 ⇒ 翻倍 4 代')
    frozen, log = _step(True, frozen, book)
    chk('复发（冷却期内）⇒ 期数翻倍到 4 代（次数 2）',
        S in frozen and book.get(S, {}).get('left') == 4 and book.get(S, {}).get('cnt') == 2,
        '实得 %s' % book.get(S))

    print('\n[3] 续期不叠加 + 再犯 8 代 + 封顶不再翻倍')
    for _ in range(4):
        frozen, log = _step(False, frozen, book)
    chk('4 代到期后解冻', S not in frozen, '实得 frozen=%s' % (frozen,))
    frozen, log = _step(True, frozen, book)
    chk('第 3 次 ⇒ 8 代', book.get(S, {}).get('left') == 8 and book.get(S, {}).get('cnt') == 3,
        '实得 %s' % book.get(S))
    frozen, log = _step(True, frozen, book)
    chk('★ 冻结期内又霸榜 ⇒ **续期**（回到本期数、**不叠加**，次数不变）',
        book.get(S, {}).get('left') == 8 and book.get(S, {}).get('cnt') == 3,
        '实得 %s（应仍为 8 代 / 第 3 次）' % book.get(S))
    chk('★ 日志留痕「续期骨架…仍超阈值」', '续期骨架' in log, log[:140])
    for _ in range(8):
        frozen, log = _step(False, frozen, book)
    frozen, log = _step(True, frozen, book)
    chk('★★ 封顶后**不再翻倍**（第 4 次仍是 8 代，不是 16 ✗）',
        book.get(S, {}).get('left') == 8 and book.get(S, {}).get('cnt') == 4,
        '实得 %s' % book.get(S))

    print('\n[4] 冷却期满 ⇒ 遗忘（回到 2 代）+ 记账清理')
    # ⚠ 顺序必须是：**先冻满 8 代让它到期**，再数冷却期 —— 冷冻期内 `cool` 不递增（设计如此 ✓）
    for _ in range(8):
        frozen, log = _step(False, frozen, book)
    chk('8 代冻满 ⇒ 到期解冻，冷却计数从 0 起',
        S not in frozen and book.get(S, {}).get('cool') == 0, '实得 %s' % book.get(S))
    for _ in range(LE.FSA_COOL_GENS + 1):
        frozen, log = _step(False, frozen, book)
    chk('★ 冷却期（%d 代）内都没再超阈值 ⇒ 记账被清掉（遗忘 ✓）' % LE.FSA_COOL_GENS,
        S not in book, '实得 book 里还有 %s' % (list(book)[:3],))
    frozen, log = _step(True, frozen, book)
    chk('★ 遗忘后再犯 ⇒ **回到 2 代**（不是继续 8 代 ✗）',
        book.get(S, {}).get('left') == 2 and book.get(S, {}).get('cnt') == 1,
        '实得 %s' % book.get(S))


def t_legacy_state():
    print('\n[5] 老 state 兼容（只有 `frozen` 列表、没有记账）')
    S = LE.skeleton(LE.Node('ts_std20', [LE.Node('add', ['close', 'open'])]))
    frozen, book = [S], {}
    chk('载入后生成端口径不变（骨架仍在冻结列表里 ✓）', S in frozen)
    frozen, log = _step(False, frozen, book)
    chk('★ 当"第 1 次"接管（不臆造历史次数）⇒ 一代后到期解冻，次数记 1',
        S not in frozen and book.get(S, {}).get('cnt') == 1,
        '实得 frozen=%s book=%s' % (S in frozen, book.get(S)))


def t_static():
    print('\n[6] 常量 / 落盘 / 口径（静态钉住）')
    src = io.open(os.path.join(ROOT, 'engine', 'loop_engine.py'), encoding='utf-8').read()
    expr_src = io.open(os.path.join(ROOT, 'engine', 'loop_expr.py'), encoding='utf-8').read()  # _fsa_stats 已迁 loop_expr
    persist_src = io.open(os.path.join(ROOT, 'engine', 'loop_persist.py'), encoding='utf-8').read()  # _save_state 已迁 loop_persist
    stage_src = io.open(os.path.join(ROOT, 'engine', 'loop_stage.py'), encoding='utf-8').read()  # _run_prepare 已迁 loop_stage
    core = io.open(os.path.join(ROOT, 'dashboard', 'api', 'app', 'sources', 'core.py'),
                   encoding='utf-8').read()
    chk('冻结期序列 = 2→4→8 封顶 · 冷却期 = %d 代' % LE.FSA_COOL_GENS,
        LE.FSA_FREEZE_SEQ == (2, 4, 8) and LE.FSA_COOL_GENS == 4)
    chk('`fsa_period`：1→2 · 2→4 · 3→8 · 4→8 · 9→8（封顶不翻倍）',
        [LE.fsa_period(i) for i in (1, 2, 3, 4, 9)] == [2, 4, 8, 8, 8])
    chk('★★ 记账**落盘**（`fsa_frz=fsa_frz,`）且**读得回**（`st.get(\'fsa_frz\')`）—— 缺一则跨代失效 ✗',
        'fsa_frz=fsa_frz,' in persist_src and "st.get('fsa_frz')" in stage_src)
    chk('★★ `frozen` 仍是**骨架字符串列表**（`frozen = sorted(cur)`）⇒ 看板 `frozen_n` 口径不变 ✓',
        'frozen = sorted(cur)' in expr_src and "len(st.get('frozen') or [])" in core)
    chk('日志留痕四件套齐全（新冻结次数+代数 / 续期 / 到期解冻 / 遗忘计数）',
        all(x in expr_src for x in ('次 ⇒ 冻结', '续期骨架', '到期解冻', '遗忘计数')))
    chk('★ 顺序不变量：**先递减/解冻、再判本代是否超阈值**（否则刚好到期那代会被误判成"续期"✗）',
        expr_src.find('① 先递减 / 到期解冻') > 0
        and expr_src.find('① 先递减 / 到期解冻') < expr_src.find('② 本代超阈值的骨架'))


def main():
    print('=' * 96)
    print('FSA 冻结：2→4→8 代封顶 + 冷却期遗忘（真跑 `_fsa_stats` 逐代模拟）')
    print('=' * 96)
    t_sequence()
    t_legacy_state()
    t_static()
    print('\n' + '=' * 96)
    print('通过 {}/{}'.format(OK[0] - OK[1], OK[0]) + ('' if OK[1] else '  ✓ 全部通过'))
    return 1 if OK[1] else 0


if __name__ == '__main__':
    sys.exit(main())
