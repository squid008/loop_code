# -*- coding: utf-8 -*-
"""
Round 2 (~45个)
A 参数扰动: 对Round1唯一有效的 amt_log 做窗口扰动 (中金15%)
B 机制引导: 资金流族 moneyflow3 (用户数据特色, 中金20%)
C 交叉: 有效因子 x 其他信号 (中金25%)
D 随机探索: 新结构 (中金15%)
"""
import os
import sys
import time
import pickle
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from factor_miner import (load_panel, prepare, run_round, show,
                          ts_mean, ts_std, ts_max, ts_min, ts_pos,
                          ts_corr, ts_delta, cs_rank)

HERE = os.path.dirname(os.path.abspath(__file__))
IC_CACHE = os.path.join(HERE, 'ic_round2.pkl')


def build_factors(P):
    ret, close = P['ret'], P['close']
    open_, high, low = P['open'], P['high'], P['low']
    vol, turn = P['volume'], P['turnover']
    tr = P.get('turn_ratio')
    mc = P.get('mktcap')
    mf_xl = P.get('mf_xl_r')
    mf_net = P.get('mf_net_r')
    rng = (high - low).replace(0, np.nan)
    F = {}

    # ===== A 参数扰动: 成交额窗口 =====
    for w in [3, 5, 10, 20, 40, 60, 120]:
        F[f'amt_log{w}'] = -np.log(ts_mean(turn, w) + 1)
    F['amt_rank20'] = -ts_pos(turn, 20)
    F['amt_std20'] = -ts_std(turn, 20)
    F['amt_cv20'] = -(ts_std(turn, 20) / (ts_mean(turn, 20) + 1e-12))

    # 换手率(成交额/市值) —— Round1 因市值方向错误而失效, 现已修复
    if tr is not None:
        for w in [5, 10, 20, 60]:
            F[f'turnmc{w}'] = -np.log(ts_mean(tr, w) + 1e-8)
        F['turnmc_rank20'] = -ts_pos(tr, 20)
        F['turnmc_std20'] = -ts_std(tr, 20)
        F['turnmc_chg'] = -(ts_mean(tr, 5) / (ts_mean(tr, 60) + 1e-12))
    if mc is not None:
        F['ln_mktcap'] = -np.log(mc + 1e-8)          # 小市值(对照基准)

    # ===== B 机制引导: 资金流族 =====
    if mf_xl is not None:
        for w in [3, 5, 10, 20, 60]:
            F[f'mfxl{w}'] = ts_mean(mf_xl, w)
        F['mfxl_pos20'] = ts_pos(mf_xl, 20)
        F['mfxl_pos60'] = ts_pos(mf_xl, 60)
        F['mfxl_std20'] = -ts_std(mf_xl, 20)
        F['mfxl_div'] = ts_mean(mf_xl, 5) / (ts_std(mf_xl, 20) + 1e-8)
        F['mfxl_max20'] = ts_max(mf_xl, 20)
        F['mfxl_min20'] = ts_min(mf_xl, 20)
        F['mfxl_trd20'] = ts_delta(ts_mean(mf_xl, 10), 10)
        # 资金流一致性: 20日中净流入为正的天数占比
        pos = (mf_xl > 0).astype('float64')
        F['mfxl_cons20'] = ts_mean(pos, 20)
        F['mfxl_cons60'] = ts_mean(pos, 60)
        # 资金流强度 x 持续性
        F['mfxl_str'] = ts_mean(mf_xl, 20) * ts_mean(pos, 20)
    if mf_net is not None:
        for w in [5, 10, 20, 60]:
            F[f'mfnet{w}'] = ts_mean(mf_net, w)
        F['mfnet_pos20'] = ts_pos(mf_net, 20)
        F['mfnet_cons20'] = ts_mean((mf_net > 0).astype('float64'), 20)

    # ===== C 交叉: 有效因子 x 其他 =====
    a20 = cs_rank(-np.log(ts_mean(turn, 20) + 1))       # 小成交额
    F['ix_amt_rev5'] = a20 * cs_rank(-ts_mean(ret, 5))
    F['ix_amt_mom20'] = a20 * cs_rank(ts_mean(ret, 20))
    if mf_xl is not None:
        F['ix_amt_mfxl'] = a20 * cs_rank(ts_mean(mf_xl, 20))
        F['ix_mfxl_rev'] = cs_rank(ts_mean(mf_xl, 10)) * cs_rank(-ts_mean(ret, 5))
    if tr is not None:
        F['ix_amt_turnmc'] = a20 * cs_rank(-np.log(ts_mean(tr, 20) + 1e-8))
    # 加权合成(而非乘积)
    F['mix_amt_rev'] = 0.5 * a20 + 0.5 * cs_rank(-ts_mean(ret, 5))

    # ===== D 随机探索: 新结构 =====
    up = ret.clip(lower=0)
    dn = (-ret).clip(lower=0)
    F['up_dn_vol'] = -(ts_mean(up, 20) / (ts_mean(dn, 20) + 1e-8))
    F['ret_pos20'] = ts_pos(close, 20)
    F['accel'] = ts_mean(ret, 5) - ts_mean(ret, 20)     # 动量加速度
    F['vol_price_corr'] = -ts_corr(vol, close, 20)
    F['amt_price_corr'] = -ts_corr(turn, close, 20)
    F['body_ratio'] = ts_mean((close - open_).abs() / rng, 20)
    F['close_high'] = -ts_mean((high - close) / rng, 20)
    F['close_low'] = ts_mean((close - low) / rng, 20)
    F['ret_vol20'] = -ts_std(ret, 20) * np.log(ts_mean(turn, 20) + 1)
    F['turn_amp'] = -ts_mean(tr if tr is not None else vol, 20) * ts_mean(rng / close, 20)

    return F


if __name__ == '__main__':
    t0 = time.time()
    P = load_panel()
    P = prepare(P)
    close = P['close']
    print(f"字段: {list(P.keys())}")
    if P.get('turn_ratio') is not None:
        print(f"换手率可用, NaN占比 {P['turn_ratio'].isna().mean().mean()*100:.1f}%")

    F = build_factors(P)
    print(f"\n候选因子: {len(F)} 个\n")
    res, ic_store = run_round(F, close, tag='R2')
    show(res, 'Round 2 结果(按超额排序)')

    with open(IC_CACHE, 'wb') as f:
        pickle.dump(ic_store, f)
    print(f"\nIC序列已存  耗时 {time.time()-t0:.0f}s")
