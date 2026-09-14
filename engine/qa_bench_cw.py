# -*- coding: utf-8 -*-
"""qa_bench_cw.py — 「市值加权基准」口径的 QA（roadmap §8.28）

背景：我们把池内回测**同时**记两个基准口径：
  · 等权(现状)   = `nanmean(keep_all)`          -> 规模中性, 是**主判据**
  · 市值加权(新) = 按 mktcap 加权(≈真实指数)    -> 产品口径
  · tilt = 市值口径超额 − 等权口径超额           -> 「池内规模倾斜」贡献

测试（**关键是不变量测试** —— 它能在不重复实现回测的前提下验出新代码路径与老路径一致）：
  [1] 恒等测试 ★: 把 mcap 传成**常数** ⇒ `ann_ex_cw` 必须**逐位等于** `ann_ex`
      （常数时按市值加权 == 等权, 数学上必然成立; 任何偏差都说明新代码写错了）
  [2] 真实市值: 报 ann_ex / ann_ex_cw / tilt，检查符号（等权组合通常**超配小盘** ⇒ tilt 多为正）
  [3] 边界: mcap 全 NaN ⇒ 不得崩溃（应退化为"无该口径"）

用法: python engine/qa_bench_cw.py
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

import factor_miner as FM          # noqa: E402
import loop_engine as LE           # noqa: E402

NOK = 0


def chk(cond, msg):
    global NOK
    print(("  [OK]   " if cond else "  [FAIL] ") + msg)
    if not cond:
        NOK += 1


def main():
    global NOK
    print("=" * 76)
    print("[1] 载面板 + 取一个真实因子（用入库因子 pkl, 没有则用 -lnamt）")
    base = LE.base_fields()
    B, dates, cols, close = base['B'], base['dates'], base['cols'], base['close']
    print(f"  面板 {len(dates)} 日 x {len(cols)} 股")

    fac = None
    bk = os.path.join(ROOT, 'ai_test', '_bank_fac')
    if os.path.isdir(bk):
        fs = sorted(f for f in os.listdir(bk) if f.endswith('.pkl'))
        if fs:
            try:
                arr = pd.read_pickle(os.path.join(bk, fs[0]))
                if hasattr(arr, 'reindex'):
                    arr = arr.reindex(index=dates, columns=cols)
                fac = pd.DataFrame(np.asarray(arr, dtype='float64'),
                                   index=dates, columns=cols)
                print(f"  用入库因子 pkl: {fs[0]}")
            except Exception as e:
                print(f"  pkl 读失败({type(e).__name__}), 退化为 -lnamt")
    if fac is None:
        sf = LE.style_features(B)
        fac = pd.DataFrame(-sf['lnamt'].astype('float64'), index=dates, columns=cols)
        print("  用 -lnamt 合成因子")

    fac = FM.cs_rank(fac)
    # ★ 定向(2026-09-13, 解开「bank00 疑点」): 引擎与 standard_test 都**按 IC 符号自动定向**因子
    #   (`loop_engine.py:1268` `sign = np.sign(mu)`; `standard_test.py:123` `sign = _s`)。
    #   而 evaluate_real **不做**定向(它假定调用方已定好方向 —— 引擎是在调用前乘 sign 的)
    #   ⇒ 不定向地喂**原始 pkl** 会跑在**亏损方向**:
    #      实测 bank00 不定向 = **-28.41%**, 而 §8.13 诊断(经 standard_test 定向) = **+1.33%**。
    #   ⇒ 差距**全部**来自定向约定, 不是两条管线不一致(这是「待查疑点」的答案)。
    from scipy.stats import spearmanr as _spr
    try:
        _U = FM.get_universe().reindex(index=dates, columns=cols).fillna(False).values
        _fw = (close.shift(-(1 + FM.FWD)) / close.shift(-1) - 1).values
        _fv = fac.values
        _ics = []
        for _i in range(0, len(dates), 5):
            _u = _U[_i]
            _a, _b = _fv[_i][_u], _fw[_i][_u]
            _m = np.isfinite(_a) & np.isfinite(_b)
            if _m.sum() >= 50:
                _ics.append(_spr(_a[_m], _b[_m])[0])
        _mu = float(np.nanmean(_ics))
    except Exception as _e:
        _mu = np.nan
        print(f"  定向计算失败({type(_e).__name__}), 不定向")
    if np.isfinite(_mu) and _mu < 0:
        fac = -fac
        print(f"  按样本 IC {_mu:+.4f} **取反**定向(与 standard_test/引擎 同约定)")
    else:
        print(f"  样本 IC {_mu:+.4f} -> 保持原方向")
    MCAP = np.where(B['mktcap'] > 0, B['mktcap'].astype('float64'), np.nan)
    print(f"  市值面板 有效比例 {np.isfinite(MCAP).mean():.1%}")

    print("=" * 76)
    print("[2] ★ 恒等测试: mcap = 常数 ⇒ 市值加权必须逐位等于等权")
    const = np.full_like(MCAP, 1.0e10)
    r_ew = FM.evaluate_real(fac, close, 'qa_ew', mcap=None)
    r_cw = FM.evaluate_real(fac, close, 'qa_cw', mcap=const)
    chk(r_ew is not None and r_cw is not None, "两次回测都成功")
    if r_ew and r_cw:
        d = abs(r_cw['ann_ex_cw'] - r_ew['ann_ex'])
        chk(d < 1e-12, f"ann_ex_cw == ann_ex（差 {d:.3e}）")
        chk(abs(r_cw['tilt']) < 1e-12, f"tilt == 0（值 {r_cw['tilt']:.3e}）")
        chk(abs(r_cw['calmar_cw'] - r_ew['calmar']) < 1e-12, "calmar_cw == calmar")

    print("=" * 76)
    print("[3] 真实市值: 两个口径对照")
    r_real = FM.evaluate_real(fac, close, 'qa_real', mcap=MCAP)
    if r_real is None:
        chk(False, "真实市值回测失败")
    else:
        has = np.isfinite(r_real.get('tilt', np.nan))
        chk(has, "tilt 已产出（非 NaN）")
        if has:
            print(f"    等权基准  : 年化超额 {r_real['ann_ex']*100:+6.2f}%  "
                  f"Calmar {r_real['calmar']:+.3f}  回撤 {r_real['dd']*100:6.2f}%")
            print(f"    市值加权  : 年化超额 {r_real['ann_ex_cw']*100:+6.2f}%  "
                  f"Calmar {r_real['calmar_cw']:+.3f}  回撤 {r_real['dd_cw']*100:6.2f}%")
            print(f"    ★ tilt   : {r_real['tilt']*100:+.2f}%  "
                  f"(= 市值口径 − 等权口径 = 「池内规模倾斜」贡献)")
            chk(abs(r_real['tilt']) > 1e-9, "真实市值下 tilt 非零（口径确实不同）")

    print("=" * 76)
    print("[4] 边界: mcap 全 NaN ⇒ 不得崩溃, 应退化为无该口径")
    try:
        r_nan = FM.evaluate_real(fac, close, 'qa_nan', mcap=np.full_like(MCAP, np.nan))
        ok = (r_nan is None) or (not np.isfinite(r_nan.get('tilt', np.nan)))
        chk(ok, "全 NaN 市值 -> 不崩且不出 tilt(或整体 None)")
    except Exception as e:
        chk(False, f"全 NaN 市值导致异常: {type(e).__name__}: {e}")

    print("=" * 76)
    print(f"结论: {'全部通过 ✓' if NOK == 0 else f'{NOK} 项失败 ✗'}")
    return 1 if NOK else 0


if __name__ == '__main__':
    sys.exit(main())
