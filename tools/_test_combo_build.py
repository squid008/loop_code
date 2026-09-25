# -*- coding: utf-8 -*-
"""_test_combo_build.py — combo_build 拆分后的纯函数守门（2026-09-25 L2）

守什么：
  1. `_parse_args` 参数解析正确（含 `--neutral`、空 `--pool=` 回退 all）
  2. `_build_weights` 三种权重方案：
     - A = 全样本等权 1/N
     - B = 滚动 IC 加权（每行权重和 = 1，非负，只用过去 IC）
     - C = 滚动去相关等权（每行权重和 = 1，窗口不足 60 期前保持初始 1/N）

★★ 拆分铁律（`docs/maintainability.md` R6/R7）：抽纯函数后**行为必须逐字不变**，
   本守门对"最可能拆坏的"两个纯函数直接断言数值性质。
"""
import os
import sys

import numpy as np
import pandas as pd

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'engine'))

import combo_build as CB          # noqa: E402

OK = [0, 0]


def chk(c, m):
    OK[0] += 1
    if not c:
        OK[1] += 1
    print('  [{}] {}'.format('OK ' if c else 'FAIL', m))


def t_parse_args():
    print('\n[1] _parse_args 参数解析')
    saved = sys.argv[:]
    try:
        sys.argv = ['combo_build.py']
        p, icw, dec, thr, neu = CB._parse_args()
        chk((p, icw, dec, thr, neu) == ('all', 250, 250, 0.70, False),
            '默认值 = (all, 250, 250, 0.70, False)')

        sys.argv = ['combo_build.py', '--pool=300', '--icw_win=120', '--dec_win=200',
                    '--dec_thr=0.5', '--neutral']
        p, icw, dec, thr, neu = CB._parse_args()
        chk(p == '300', 'pool=300')
        chk(icw == 120, 'icw_win=120')
        chk(dec == 200, 'dec_win=200')
        chk(thr == 0.5, 'dec_thr=0.5')
        chk(neu is True, 'neutral=True')

        sys.argv = ['combo_build.py', '--pool=']
        p, *_ = CB._parse_args()
        chk(p == 'all', '空 --pool= 回退 all')
    finally:
        sys.argv = saved


def t_build_weights():
    print('\n[2] _build_weights 三种权重方案')
    rng = np.random.RandomState(0)
    T, N = 120, 3
    names = ['a', 'b', 'c']
    dates = pd.bdate_range('2020-01-01', periods=T)
    ICdf = pd.DataFrame(rng.randn(T, N), index=dates, columns=names)
    # 期频 index 早于 dates 尾部 ⇒ 触发"过去 DEC_WIN 期"去相关路径
    ex_idx = pd.bdate_range('2019-01-01', periods=80)
    EX = pd.DataFrame(rng.randn(80, N), index=ex_idx, columns=names)

    Ws, sel_hist = CB._build_weights(T, N, dates, ICdf, EX, names, 250, 250, 0.70)

    chk(set(Ws) == {'A_全样本等权', 'B_滚动IC加权', 'C_滚动去相关等权'}, '三种方案齐全')

    A = Ws['A_全样本等权']
    chk(A.shape == (T, N) and np.allclose(A, 1.0 / N), 'A = 全样本等权 1/N')

    B = Ws['B_滚动IC加权']
    chk(B.shape == (T, N), 'B 形状 (T,N)')
    chk((B >= 0).all(), 'B 权重非负（clip 后）')
    chk(np.allclose(B.sum(axis=1), 1.0, atol=1e-9), 'B 每行权重和 = 1')

    C = Ws['C_滚动去相关等权']
    chk(C.shape == (T, N), 'C 形状 (T,N)')
    chk(np.allclose(C.sum(axis=1), 1.0, atol=1e-9), 'C 每行权重和 = 1')
    chk(np.allclose(C[0], 1.0 / N), 'C 首日 = 初始 1/N（去相关窗口不足 60 ⇒ 不变）')


if __name__ == '__main__':
    t_parse_args()
    t_build_weights()
    print('\n===== {} 通过 {}/{} ====='.format(
        '全绿' if OK[1] == 0 else '有失败', OK[0] - OK[1], OK[0]))
    sys.exit(1 if OK[1] else 0)
