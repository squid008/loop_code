# -*- coding: utf-8 -*-
"""qa_pool_tag.py -- 池标签的 QA（roadmap §8.42）

为什么（2026-09-13）：池标签原先有**两份实现**（`standard/pool_tags.py:tag_of` 与引擎要写进
`factor_library.md` 的版本）⇒ 必然漂移。已统一到 `loop_pools.derive_tag`（单一事实源），
本脚本负责：
  [1] `derive_tag` 的**全部分支**都要有合成用例（8 种标签全跑一遍）
  [2] ★ **一致性**：`standard/pool_tags.py:tag_of`（转发版）与 `loop_pools.derive_tag` 对
      **同一批输入必须逐位相同** —— 这是"防漂移"的核心断言
  [3] `tag_desc` 对**任意**标签都要能出中文（不得抛异常 / 返回空）
  [4] 阈值常数只有一处定义（`TAG_CAL_MIN` / `TAG_POOL_FLOOR`）

用法: python engine/qa_pool_tag.py
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
sys.path.insert(0, HERE)

import loop_pools as LP            # noqa: E402

NOK = 0


def chk(cond, msg):
    global NOK
    print(('  [OK]   ' if cond else '  [FAIL] ') + msg)
    if not cond:
        NOK += 1


def main():
    global NOK
    pools = ['300', '500', '1000']

    print('=' * 74)
    print('[1] derive_tag 全分支')
    cases = [
        # (ok_all, {池: 是否通过}, 期望标签, 说明)
        (False, {'300': False, '500': False, '1000': False}, 'none', '全不通过'),
        (True, {'300': True, '500': True, '1000': True}, 'all3', '全A+所有池'),
        (True, {'300': False, '500': False, '1000': False}, 'csi_all_only', '只有全A'),
        (True, {'300': True, '500': False, '1000': False}, 'csi300_all', '全A+300'),
        (False, {'300': True, '500': False, '1000': False}, 'csi300_only', '仅300'),
        (False, {'300': True, '500': True, '1000': False}, 'csi300_500', '300+500(全A不通过)'),
        (False, {'300': True, '500': False, '1000': True}, 'csi300_1000', '300+1000'),
        (True, {'300': True, '500': True, '1000': False}, 'csi300_500_all', '全A+300+500'),
    ]
    for ok_all, okp, exp, why in cases:
        got = LP.derive_tag(ok_all, okp, pools)
        chk(got == exp, '{} -> {} (期望 {})'.format(why, got, exp))

    print('=' * 74)
    print('[2] ★ 一致性：standard/pool_tags.py 的 tag_of 必须与 derive_tag 逐位相同')
    try:
        sys.path.insert(0, os.path.join(ROOT, 'standard'))
        import pool_tags as PT
        bad = []
        for ok_all, okp, exp, why in cases:
            a = LP.derive_tag(ok_all, okp, pools)
            b = PT.tag_of(ok_all, okp, pools)
            if a != b:
                bad.append((why, a, b))
        chk(not bad, '8 个用例全部一致' if not bad else '不一致: {}'.format(bad))
        # 阈值也必须同源
        chk(abs(PT.CAL_MIN - LP.TAG_CAL_MIN) < 1e-12 and
            abs(PT.POOL_FLOOR - LP.TAG_POOL_FLOOR) < 1e-12,
            '阈值同源: CAL_MIN={} POOL_FLOOR={}'.format(PT.CAL_MIN, PT.POOL_FLOOR))
    except Exception as e:
        chk(False, '导入 standard/pool_tags.py 失败: {}: {}'.format(type(e).__name__, e))

    print('=' * 74)
    print('[3] tag_desc 对任意标签都能出中文')
    all_tags = [c[2] for c in cases] + ['csi500_1000', 'csi1000_only', 'x']
    for t in all_tags:
        try:
            d = LP.tag_desc(t)
            ok = isinstance(d, str) and len(d) > 0
        except Exception as e:
            d, ok = '{}: {}'.format(type(e).__name__, e), False
        chk(ok, '{:<18s} -> {}'.format(t, d[:56]))

    print('=' * 74)
    print('[4] 阈值常量存在且为数值')
    chk(isinstance(LP.TAG_CAL_MIN, float) and isinstance(LP.TAG_POOL_FLOOR, float),
        'TAG_CAL_MIN={}  TAG_POOL_FLOOR={}'.format(LP.TAG_CAL_MIN, LP.TAG_POOL_FLOOR))

    print('=' * 74)
    print('结论: ' + ('全部通过 ✓' if NOK == 0 else '{} 项失败 ✗'.format(NOK)))
    return 1 if NOK else 0


if __name__ == '__main__':
    sys.exit(main())
