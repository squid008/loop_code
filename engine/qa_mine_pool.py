# -*- coding: utf-8 -*-
"""qa_mine_pool.py — 三池并行挖掘(`--mine_pool`)的校验(roadmap §8.19)

分两段：
  [轻]  路径派生 / 幂等 / 未知池报错 / `--mine_pool` 参数默认值      —— 秒级, 默认跑
  [重]  L1 子面板 = 池并集 + PIT 池掩码当期成分数(300 应≈300)      —— 需载面板, 加 --heavy
另外校验 `loop_watch.py` 能否跟随池后缀(否则无人值守会读错日志 -> 静默停摆)。

用法:
  python engine/qa_mine_pool.py            # 轻
  python engine/qa_mine_pool.py --heavy    # 含面板(约 2 分钟)
"""
import io
import os
import sys
import time

try:
    sys.stdout.reconfigure(errors='replace')
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import loop_engine as LE          # noqa: E402

FAIL = []


def chk(cond, msg):
    print(('  PASS  ' if cond else '  FAIL  ') + msg)
    if not cond:
        FAIL.append(msg)


def main():
    heavy = '--heavy' in sys.argv
    print("=" * 74)
    print("[1] 路径派生 / 幂等")
    base = dict(STATE=LE.STATE, ARCHIVE=LE.ARCHIVE, JOURNAL=LE.JOURNAL,
                LIBRARY=LE.LIBRARY, STRIP_OBS=LE.STRIP_OBS,
                POOL_OBS=LE.POOL_OBS, STYLE_OBS=LE.STYLE_OBS)
    chk(LE.MINE_POOL == 'all', "初始 MINE_POOL = 'all'")
    chk(LE.STATE == base['STATE'], "初始不带后缀(向后兼容)")

    LE.set_mine_pool('300')
    chk(LE.MINE_POOL == '300', "set_mine_pool('300') 生效")
    chk(LE.STATE.endswith('loop_state_300.pkl'), f"STATE 加后缀 -> {os.path.basename(LE.STATE)}")
    chk(LE.ARCHIVE.endswith('loop_archive_300.csv'), "ARCHIVE 加后缀")
    chk(LE.JOURNAL.endswith('loop_journal_300.md'), "JOURNAL 加后缀")
    chk(LE.LIBRARY.endswith('factor_library_300.md'), "LIBRARY 加后缀")
    chk(LE.STRIP_OBS.endswith('loop_strip_style_300.csv'), "STRIP_OBS 加后缀")

    LE.set_mine_pool('500')
    chk(LE.STATE.endswith('loop_state_500.pkl'), "切到 500 后**不叠加** _300_500(幂等)")
    LE.set_mine_pool('300')                      # 重复调用同一池
    chk(LE.STATE.endswith('loop_state_300.pkl'), "重复调 '300' 仍不叠后缀")
    LE.set_mine_pool('all')
    chk(LE.STATE == base['STATE'] and LE.MINE_POOL == 'all', "切回 'all' 恢复原始路径")

    print("  --- 未知池必须早失败 ---")
    try:
        LE.set_mine_pool('999')
        chk(False, "未知池 '999' 应报错")
    except SystemExit as e:
        chk('999' in str(e), f"未知池报错: {str(e)[:70]}")

    print("=" * 74)
    print("[2] --mine_pool 参数(与 __main__ 的 parser 一致)")
    import argparse
    src = io.open(os.path.join(HERE, 'loop_engine.py'), encoding='utf-8').read()
    chk("add_argument('--mine_pool'" in src, "parser 已注册 --mine_pool")
    chk("set_mine_pool(_args.mine_pool)" in src, "main 里在 run() 之前调用了 set_mine_pool")
    chk("Usub = Usub & L1_POOL_MASK" in src, "L1 的 IC 已加池掩码(池内 IC)")
    chk("L1_POOL_MASK = _LP.pool_mask" in src, "L1 池掩码按 PIT 构建")

    print("=" * 74)
    print("[3] loop_watch.py 是否跟随池后缀")
    w = os.path.join(HERE, 'loop_watch.py')
    wt = io.open(w, encoding='utf-8').read()
    follows = ('mine_pool' in wt) or ('_POOL' in wt) or ('set_mine_pool' in wt)
    chk(follows, "loop_watch.py 跟随 --mine_pool(否则无人值守会读错日志、静默停摆)")

    if heavy:
        print("=" * 74)
        print("[4] L1 子面板 = 池并集 + PIT 池掩码(需载面板, 约 2 分钟)")
        import numpy as np
        import loop_pools as LP
        t0 = time.time()
        for tag, expect in (('300', 300), ('500', 500)):
            LE.set_mine_pool(tag)
            LE._BASE = None          # ★base_fields() 有缓存; 不清会拿到上一个池的 L1_COLS/掩码
            LE.base_fields()
            n_col = LE.L1_COLS.size
            m = LE.L1_POOL_MASK
            med = float(np.median(m.sum(1)))
            print(f"  [{tag}] L1 列 {n_col} 只 / 掩码 {m.shape} / "
                  f"当期成分: 中位 {med:.0f} 最小 {m.sum(1).min()} 最大 {m.sum(1).max()}"
                  f"  ({time.time()-t0:.0f}s)")
            # 当期成分数应在池规模附近(池每半年调整, 300 池约 300 只)
            chk(abs(med - expect) <= 0.12 * expect,
                f"[{tag}] 当期成分中位 {med:.0f} 应≈{expect}(±12%)")
            chk(m.sum(1).min() > 0, f"[{tag}] 掩码无全空行")
            chk(n_col >= expect, f"[{tag}] L1 列数 {n_col} ≥ 池规模 {expect}")
            chk(LP.pool_union(tag) >= set(), f"[{tag}] 池并集可读")

    print("=" * 74)
    if FAIL:
        print(f"结果: **{len(FAIL)} 项未通过**")
        for m in FAIL:
            print("  - " + m)
        return 1
    print("结果: 全部通过 ✓" + ("" if heavy else "   （面板段未跑, 加 --heavy）"))
    return 0


if __name__ == '__main__':
    sys.exit(main())
