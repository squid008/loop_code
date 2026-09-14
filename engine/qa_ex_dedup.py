# -*- coding: utf-8 -*-
"""qa_ex_dedup.py -- 「收益流去重」的 QA（roadmap §8.34）

被测：`loop_engine.ex_max_corr(ex_new, bank_ex)`。
设计原则（同 §8.28）：**优先用"退化时必须逐位相等"的不变量**，而不是肉眼看数值。

测试：
  [1] 恒等 : 同一条序列 vs 自己          -> |corr| == 1.0（逐位）
  [2] 反向 : 取负号后 vs 原序列          -> |corr| == 1.0（判重必须**与方向无关**！
                                             bank 只存 Node 不存 sign, 靠的就是这一点）
  [3] 独立 : 随机噪声 vs 原序列          -> |corr| 很小（< 0.2）
  [4] 偏相关: 与原序列共享 30% 成分      -> 明显 0 < c < 1
  [5] 边界 : 空库 / 期数不足(重叠<30) / 含 NaN -> 不得崩溃, 且"无从判定"时返回 (None, None)
  [6] 选最大: 库里有多个, 必须返回**最大的那个**及其键

用法: python engine/qa_ex_dedup.py
"""
import io
import os
import sys

import numpy as np
import pandas as pd

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = os.path.dirname(HERE)

import loop_engine as LE          # noqa: E402

NOK = 0


def chk(cond, msg):
    global NOK
    print(('  [OK]   ' if cond else '  [FAIL] ') + msg)
    if not cond:
        NOK += 1


def main():
    global NOK
    rng = np.random.default_rng(20240913)
    idx = pd.date_range('2020-01-01', periods=300, freq='B')
    base = pd.Series(rng.normal(0, 0.01, 300), index=idx)

    print('=' * 74)
    print('[1] 恒等：自己 vs 自己 ⇒ |corr| == 1.0')
    c, k = LE.ex_max_corr(base, {'A': base})
    chk(c is not None and abs(c - 1.0) < 1e-9, '|corr| = {} (键 {})'.format(c, k))

    print('=' * 74)
    print('[2] 方向无关：-x vs x ⇒ |corr| 仍 == 1.0（关键！bank 不存 sign）')
    c, k = LE.ex_max_corr(-base, {'A': base})
    chk(c is not None and abs(c - 1.0) < 1e-9, '|corr| = {}'.format(c))

    print('=' * 74)
    print('[3] 独立：随机噪声 ⇒ |corr| 很小')
    noise = pd.Series(rng.normal(0, 0.01, 300), index=idx)
    c, k = LE.ex_max_corr(noise, {'A': base})
    chk(c is not None and c < 0.2, '|corr| = {}'.format(c))

    print('=' * 74)
    print('[4] 偏相关：共享 30% 成分 ⇒ 居中且非 0')
    mix = 0.7 * base + 0.3 * noise
    c, k = LE.ex_max_corr(mix, {'A': base})
    chk(c is not None and 0.4 < c < 1.0, '|corr| = {}'.format(c))

    print('=' * 74)
    print('[5] 边界')
    c, k = LE.ex_max_corr(base, {})
    chk(c is None and k is None, '空库 -> (None, None)')
    c, k = LE.ex_max_corr(base, None)
    chk(c is None and k is None, '库为 None -> (None, None)')
    c, k = LE.ex_max_corr(None, {'A': base})
    chk(c is None and k is None, '新序列 None -> (None, None)')
    short = base.iloc[:10]                      # 重叠 10 < min_overlap(30)
    c, k = LE.ex_max_corr(short, {'A': base})
    chk(c is None, '重叠期数不足 ⇒ 不当成重复（返回 None），实得 {}'.format(c))
    withnan = base.copy()
    withnan.iloc[::7] = np.nan
    c, k = LE.ex_max_corr(withnan, {'A': base})
    chk(c is not None and abs(c - 1.0) < 1e-9,
        '含 NaN 时只比对有限值对 ⇒ 仍为 1.0，实得 {}'.format(c))
    # 错位索引（共同日期为空）
    other_idx = pd.date_range('2030-01-01', periods=300, freq='B')
    off = pd.Series(rng.normal(0, 0.01, 300), index=other_idx)
    c, k = LE.ex_max_corr(off, {'A': base})
    chk(c is None, '无共同日期 ⇒ None，实得 {}'.format(c))

    print('=' * 74)
    print('[6] 选最大：库里多个 ⇒ 返回 max 及其键')
    bank = {'A_same': base, 'B_mix': mix, 'C_noise': noise}
    c, k = LE.ex_max_corr(base, bank)
    chk(c is not None and abs(c - 1.0) < 1e-9 and k == 'A_same',
        '|corr| = {} 键 = {}'.format(c, k))

    print('=' * 74)
    print('结论: ' + ('全部通过 ✓' if NOK == 0 else '{} 项失败 ✗'.format(NOK)))
    return 1 if NOK else 0


if __name__ == '__main__':
    sys.exit(main())
