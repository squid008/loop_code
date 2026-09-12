# -*- coding: utf-8 -*-
"""prof_evalreal.py — evaluate_real 耗时剖析(2026-09-12)

用**合成因子**（全样本满覆盖）在真实 panel 上跑一次，cProfile 看时间花在哪。
合成因子只为暴露**结构性成本**（大 DataFrame 的 reindex/shift、逐日循环、对象开销），
与真实因子的数值分布无关（真实因子更稀疏，只会让 `dropna` 更快）。

⚠ 若引擎正在跑，绝对耗时会被 CPU 竞争抬高；看**占比**而非绝对值。

用法: python ai_test\prof_evalreal.py [--window=full|recent600] [--cost=0.004]
"""
import cProfile
import io
import os
import pstats
import sys
import time

import numpy as np
import pandas as pd

ENG = r'D:\loop_code\engine'
PANEL = os.path.join(ENG, 'panel.h5')
sys.path.insert(0, ENG)
os.chdir(ENG)                      # factor_miner 内部用相对路径找 universe.h5 等

import factor_miner as fm          # noqa: E402

WINDOW = 'full'
COST = 0.004
for a in sys.argv[1:]:
    if a.startswith('--window='):
        WINDOW = a[9:]
    elif a.startswith('--cost='):
        COST = float(a[7:])

t0 = time.perf_counter()
with pd.HDFStore(PANEL, 'r') as st:
    close = st['close'].astype('float64')
print(f'panel {close.shape} 载入 {time.perf_counter() - t0:.1f}s '
      f'(START={fm.START} FWD={fm.FWD} N_GRP={fm.N_GRP})')

rng = np.random.default_rng(20260912)
fac = pd.DataFrame(rng.standard_normal(close.shape).astype(np.float32),
                   index=close.index, columns=close.columns)
fac = fm.cs_rank(fac.astype('float64'))          # 与引擎 L2 的入参口径一致
print('合成因子就绪, 开始剖析 ...')

pr = cProfile.Profile()
pr.enable()
r = fm.evaluate_real(fac, close, 'synthetic', cost=COST, window=WINDOW, with_ex=True)
pr.disable()

if r is None:
    print('evaluate_real 返回 None(样本不足)')
else:
    print('结果:', {k: (round(float(v), 4) if isinstance(v, (int, float, np.floating)) else v)
                    for k, v in r.items() if k not in ('ex', 'ic_series', 'yr')})

s = io.StringIO()
st_ = pstats.Stats(pr, stream=s)
st_.sort_stats('tottime').print_stats(22)
print(s.getvalue())
print('--- 按 cumulative(含子调用) top 15 ---')
s2 = io.StringIO()
pstats.Stats(pr, stream=s2).sort_stats('cumulative').print_stats(15)
print(s2.getvalue())
