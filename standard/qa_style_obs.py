# -*- coding: utf-8 -*-
"""qa_style_obs.py — --style_obs 风格观测链路自检(2026-09-11)

1) style_expo 向量化实现 vs 朴素逐期实现(含 NaN) 逐位对拍
2) 自相关=1 / 反对称 / 常数与全 NaN 退化安全 / min_n 生效
3) style_features 的形状与口径(20 日滚动在**时间轴**上, 不是截面)
4) 默认关: loop_engine.py --help 冒烟 + 含 --style_obs
"""
import os
import subprocess
import sys

import numpy as np

ENG = r'D:\loop_code\engine'
sys.path.insert(0, ENG)
from loop_metrics import STYLE_KEYS, rank_rows, style_expo   # noqa: E402

RNG = np.random.default_rng(20260911)
FAILS = []


def chk(name, cond, extra=''):
    if not cond:
        FAILS.append(name)
    print(f"  [{'OK  ' if cond else 'FAIL'}] {name} {extra}")


def naive(RS, SS, min_n=30):
    """朴素实现: 逐期 np.corrcoef(作为对拍基准)"""
    out = []
    for t in range(RS.shape[0]):
        a, b = RS[t], SS[t]
        m = np.isfinite(a) & np.isfinite(b)
        if m.sum() < min_n:
            continue
        aa, bb = a[m], b[m]
        if aa.std() < 1e-12 or bb.std() < 1e-12:
            continue
        out.append(np.corrcoef(aa, bb)[0, 1])
    return float(np.mean(out)) if out else np.nan


print("== 1. 向量化 vs 朴素逐期(含 NaN, T=200 S=300) ==")
T, S = 200, 300
RS = RNG.normal(size=(T, S))
SS = 0.6 * RS + 0.8 * RNG.normal(size=(T, S))          # 有真实相关
mask = RNG.random((T, S)) < 0.10                        # 10% 缺失(模拟停牌)
RS_n = np.where(mask, np.nan, RS)
SS_n = np.where(RNG.random((T, S)) < 0.07, np.nan, SS)
v_fast, v_slow = style_expo(RS_n, SS_n), naive(RS_n, SS_n)
chk('向量化 == 朴素', np.isclose(v_fast, v_slow, rtol=0, atol=1e-10),
    f'fast={v_fast:.12f} slow={v_slow:.12f}')

print("== 2. 语义(自相关 / 反对称 / 退化) ==")
RSr = rank_rows(RS)
chk('自相关 = +1', np.isclose(style_expo(RSr, RSr), 1.0, atol=1e-12),
    f'{style_expo(RSr, RSr):.12f}')
chk('反对称 = -1', np.isclose(style_expo(RSr, 1.0 - RSr), -1.0, atol=1e-12),
    f'{style_expo(RSr, 1.0 - RSr):.12f}')
const = np.ones((T, S), dtype='float64')
chk('风格常数 -> NaN', np.isnan(style_expo(RSr, const)))
chk('因子全 NaN -> NaN', np.isnan(style_expo(np.full((T, S), np.nan), SS_n)))
chk('有效样本不足 -> NaN',
    np.isnan(style_expo(np.where(RNG.random((T, S)) < 0.99, np.nan, RS_n), SS_n)))
chk('min_n 可放宽', np.isfinite(style_expo(RS_n, SS_n, min_n=10)))

print("== 3. style_features 形状与 20 日滚动口径 ==")
import pandas as pd                                            # noqa: E402
from loop_engine import style_features                         # noqa: E402

T2, S2 = 60, 12
mktcap = RNG.uniform(1e9, 1e11, size=(T2, S2)).astype(np.float32)
turnover = RNG.uniform(1e7, 1e9, size=(T2, S2)).astype(np.float32)
close = RNG.uniform(5, 80, size=(T2, S2)).astype(np.float32)
mktcap[0, 0] = 0.0                                            # 0 -> NaN 分支
fake_B = {'mktcap': mktcap, 'turnover': turnover, 'close': close}
sf = style_features(fake_B)
chk('四项齐备', set(sf) == set(STYLE_KEYS), sorted(sf))
chk('形状一致', all(v.shape == (T2, S2) for v in sf.values()))
# lnamt 应等于 log(20 日均成交额)(时间轴滚动, 与 standard_test 同口径)
ref_amt = pd.DataFrame(turnover.astype('float64')).rolling(20, min_periods=5).mean().values
chk('lnamt == log(20日均成交额)',
    np.allclose(sf['lnamt'], np.log(ref_amt), rtol=1e-5, equal_nan=True))
# lntr = log(20 日均 (成交额/市值))
mc = np.where(mktcap > 0, mktcap.astype('float64'), np.nan)
ref_tr = pd.DataFrame(turnover.astype('float64') / mc).rolling(20, min_periods=5).mean().values
chk('lntr == log(20日均换手率)',
    np.allclose(sf['lntr'], np.log(ref_tr), rtol=1e-5, equal_nan=True))
chk('市值0 -> lncap NaN', np.isnan(sf['lncap'][0, 0]))
chk('前 4 期不足 5 日 -> NaN(rolling min_periods)',
    np.isnan(sf['lnamt'][:4]).all() and np.isfinite(sf['lnamt'][4:]).all())

print("== 4. 默认关: --help 冒烟 ==")
r = subprocess.run([sys.executable, os.path.join(ENG, 'loop_engine.py'), '--help'],
                   capture_output=True, text=True, encoding='utf-8', errors='replace')
chk('--help 退出码 0', r.returncode == 0, f'rc={r.returncode}')
out = (r.stdout or '') + (r.stderr or '')
for arg in ('--style_obs', '--min_mono', '--score_mode'):
    chk(f'--help 含 {arg}', arg in out)

print('=' * 62)
print('全部通过' if not FAILS else f'失败 {len(FAILS)} 项: {FAILS}')
sys.exit(0 if not FAILS else 1)
