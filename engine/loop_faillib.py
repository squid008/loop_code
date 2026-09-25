# -*- coding: utf-8 -*-
"""loop_faillib.py — 失败模式库（中金：失败表达式写入失败库，生成阶段自动排除，2026-09-26 L3 拆分）

fail_lib = {骨架: dict(try_=参与测试数, ok=通过L1数, fail=失败数, rs={原因:计数}, last=最近代)}
★ 只依赖 loop_expr.skeleton，不 import loop_engine（无循环依赖）✓
"""
from loop_expr import skeleton


def flib_mark(fail_lib, node, gen, ok, reason=''):
    e = fail_lib.setdefault(skeleton(node),
                            dict(try_=0, ok=0, fail=0, rs={}, last=gen))
    e['try_'] += 1
    e['last'] = gen
    if ok:
        e['ok'] += 1
    else:
        e['fail'] += 1
        e['rs'][reason] = e['rs'].get(reason, 0) + 1


def fail_lib_cleanup(fail_lib, gen, keep_gen=5):
    """滚动: 超过 keep_gen 代未再出现的骨架淘汰, 防库膨胀"""
    return {s: e for s, e in fail_lib.items() if e['last'] >= gen - keep_gen}


def bad_skels(fail_lib, gen, min_fail=3, rate=0.6, keep_gen=5):
    """失败模式 = 骨架试了 min_fail 次以上、从未通过L1、失败率>=rate -> 生成阶段排除"""
    return {s for s, e in fail_lib.items()
            if e['last'] >= gen - keep_gen and e['fail'] >= min_fail
            and e['ok'] == 0 and e['fail'] / max(e['try_'], 1) >= rate}

