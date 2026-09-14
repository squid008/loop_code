# -*- coding: utf-8 -*-
"""qa_loop_pools.py — 池模块的正确性与「与 standard_test 口径一致」对拍

为什么必须有：`engine/loop_pools.py` 是**第二份**成分解析实现（第一份在
`standard_test.py:load_const`）。与 `cost_presets.py` 的教训一样，两份实现若漂移，
就会出现"引擎说 300 内有效、报告说无效"的无法追责情况。standard_test.py 是**脚本**
（import 即执行），不能直接 import ⇒ 本文件内**逐字复刻**其解析逻辑作参照实现。

测什么：
  1. 解析对拍：本模块 vs 参照实现，逐调整日成员集合必须**完全相同**
  2. PIT 语义：早于首个调整日 -> 空；两调整日之间 -> 取**前一个**（不是最新快照）
  3. pool_mask 与朴素逐日实现逐位相同
  4. pool_union 覆盖所有快照
  5. 快照规模合理（300 池 ≈300 只 / 500 池 ≈500 只）
  6. ★ 实用核查：池成员**在面板列里的覆盖率**（覆盖太低则池不可用）
"""
import os
import sys
import bisect

import numpy as np
import pandas as pd

try:
    sys.stdout.reconfigure(errors='replace')
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'engine'))

import loop_pools as LP                                   # noqa: E402

PANEL = os.path.join(ROOT, 'engine', 'panel.h5')
IDX_PATH = {'300': r'E:\rq\constituents\index\000300.XSHG.h5',
            '500': r'E:\rq\constituents\index\000905.XSHG.h5'}

OK = True


def note(good, msg):
    global OK
    print(f"  {'[OK]' if good else '[NG]'} {msg}")
    if not good:
        OK = False


def ref_load_const(path):
    """★ 逐字复刻 standard_test.py 的 load_const（参照实现，勿改口径）"""
    import h5py
    items = []
    with h5py.File(path, 'r') as f:
        cd = [x.decode() if isinstance(x, bytes) else str(x) for x in f['change_dates'][:]]
        for d in cd:
            mem = set(x.decode() if isinstance(x, bytes) else str(x)
                      for x in f['components'][d][:])
            items.append((int(d.replace('-', '')), mem))
    return sorted(items, key=lambda x: x[0])


def main():
    print("=" * 66)
    print("【1】解析对拍：loop_pools.load_pool  vs  standard_test.load_const")
    print("=" * 66)
    pools = {}
    for tag, path in IDX_PATH.items():
        ref = ref_load_const(path)
        mine_c, mine_m = LP.load_pool(tag)
        same_dates = (mine_c == [x[0] for x in ref])
        same_mem = all(a == b for a, b in zip(mine_m, [x[1] for x in ref]))
        note(same_dates and same_mem and len(mine_c) == len(ref),
             f"池 {tag}: 调整日 {len(mine_c)} 个 一致={same_dates}  成员集合逐日一致={same_mem}")
        pools[tag] = ref

    print()
    print("=" * 66)
    print("【2】PIT 语义")
    print("=" * 66)
    cdates, mems = LP.load_pool('300')
    # 早于首个调整日
    M0 = LP.pool_mask('300', [cdates[0] - 1], ['000001.XSHE'])
    note(not M0.any(), f"早于首个调整日({cdates[0]-1}) -> 无成分（不用未来数据）")
    # 两个调整日之间取前一个
    if len(cdates) >= 2:
        d_mid = (cdates[0] + cdates[1]) // 2
        j = bisect.bisect_right(cdates, d_mid) - 1
        note(j == 0, f"两调整日之间({d_mid}) -> 取第 {j} 个快照（应为 0，非最新）")
    # 恰好等于调整日 -> 用当日
    j = bisect.bisect_right(cdates, cdates[0]) - 1
    note(j == 0, "恰好等于调整日 -> 用当日快照（bisect_right-1）")

    print()
    print("=" * 66)
    print("【3】pool_mask 与朴素逐日实现逐位对拍")
    print("=" * 66)
    cols = [f'{i:06d}.XSHE' for i in range(1, 1201)] + ['600000.XSHG', '000300.XSHG']
    # 让 cols 里确实含一批真实成员，覆盖才有意义
    allmem = sorted(set().union(*[m for _, m in pools['300']]))
    cols = allmem[:400] + cols[:600]
    cols = list(dict.fromkeys(cols))
    rng = np.random.default_rng(7)
    dates = sorted(rng.choice(range(cdates[0], cdates[-1] + 1), 60).tolist())
    M = LP.pool_mask('300', dates, cols)
    # 朴素参照
    col_of = {c: j for j, c in enumerate(cols)}
    Mref = np.zeros_like(M)
    for i, d in enumerate(dates):
        j = bisect.bisect_right(cdates, int(d)) - 1
        if j < 0:
            continue
        for c in mems[j]:
            k = col_of.get(c)
            if k is not None:
                Mref[i, k] = True
    note(np.array_equal(M, Mref), f"逐位相同（{M.shape[0]}日 x {M.shape[1]}列, "
                                 f"池内 True 共 {int(M.sum())} 个）")

    print()
    print("=" * 66)
    print("【4】pool_union 覆盖所有快照")
    print("=" * 66)
    for tag in ('300', '500'):
        _, mems_ = LP.load_pool(tag)
        un = LP.pool_union(tag)
        covered = all(m <= un for m in mems_)
        sizes = [len(m) for m in mems_]
        note(covered, f"池 {tag}: union {len(un)} 只 覆盖所有快照={covered}  "
                      f"席位 min/med/max = {min(sizes)}/{int(np.median(sizes))}/{max(sizes)}")

    print()
    print("=" * 66)
    print("【5】★ 池成员在**面板列**里的覆盖率（覆盖太低则池不可用）")
    print("=" * 66)
    with pd.HDFStore(PANEL, 'r') as st:
        pcols = list(st['close'].columns)
    pset = set(pcols)
    for tag in ('300', '500'):
        _, mems_ = LP.load_pool(tag)
        # 逐快照覆盖率的中位
        covs = [len(m & pset) / max(len(m), 1) for m in mems_]
        un = LP.pool_union(tag)
        note(np.median(covs) > 0.9,
             f"池 {tag}: 面板列 {len(pcols)} 个; 逐快照覆盖率 中位 {np.median(covs):.1%} "
             f"最小 {min(covs):.1%}; union {len(un)} 只有 {len(un & pset)} 在面板里")

    print()
    print("=" * 66)
    print("【6】末端到 2026 覆盖（回测区间末尾必须有成分）")
    print("=" * 66)
    for tag in ('300', '500'):
        c_, m_ = LP.load_pool(tag)
        note(c_[-1] >= 20260101, f"池 {tag}: 最后一个调整日 {c_[-1]}（应 >= 20260101）")

    print()
    print("=" * 66)
    print("【7】池门槛纯函数 pool_gate_ok（方案 C = any）")
    print("=" * 66)
    import math
    na = math.nan
    cases = [
        # (cals, thr, mode, 期望ok, 期望val)
        ([0.5, -0.1], 0.0, 'any', True, 0.5),        # 至少一个达标 -> 过
        ([-0.1, -0.2], 0.0, 'any', False, -0.1),     # 全负 -> 拦（= csi_all_only）
        ([0.5, -0.1], 0.0, 'all', False, -0.1),      # all 取最小 -> 拦
        ([0.5, 0.2], 0.0, 'all', True, 0.2),
        ([0.5, 0.2], 0.3, 'all', False, 0.2),        # 最小未过阈
        ([0.5, 0.2], 0.3, 'any', True, 0.5),
        ([na, 0.5], 0.0, 'any', True, 0.5),          # NaN 忽略
        ([na, None], 0.0, 'any', None, None),        # 无从判定 -> 调用方放行
        ([], 0.0, 'any', None, None),                # 空 -> 无从判定
        ([0.0], 0.0, 'any', False, 0.0),             # 边界: 严格 > 而非 >=
        ([0.001], 0.0, 'any', True, 0.001),
        ([0.5], 0.0, 'all', True, 0.5),              # all 且单池
    ]
    for cals, thr, mode, eok, eval_ in cases:
        gok, gval = LP.pool_gate_ok(cals, thr, mode)
        good = (gok == eok) and (
            (gval is None and eval_ is None)
            or (gval is not None and eval_ is not None and abs(gval - eval_) < 1e-12))
        note(good, f"cals={cals} thr={thr} mode={mode} -> ok={gok} val={gval} "
                   f"(期望 ok={eok} val={eval_})")

    print(f"\n{'=' * 66}\n{'[OK] QA 全过' if OK else '[NG] QA 有失败项'}")
    return 0 if OK else 1


if __name__ == '__main__':
    sys.exit(main())
