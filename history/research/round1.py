# -*- coding: utf-8 -*-
"""Round 1: 首批量子候选(~32个), 覆盖中金提到的机制族"""
import os
import sys
import time
import pickle
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from factor_miner import (load_panel, prepare, evaluate, pass_filter,
                          ts_mean, ts_std, ts_sum, ts_max, ts_min, ts_pos,
                          ts_corr, ts_delay, ts_delta, cs_rank, LIB)

HERE = os.path.dirname(os.path.abspath(__file__))
IC_CACHE = os.path.join(HERE, 'ic_round1.pkl')


def build_factors(P):
    ret = P['ret']
    close, open_, high, low = P['close'], P['open'], P['high'], P['low']
    vol = P['volume']
    turn = P['turnover']
    pc = P['prev_close']
    vwap = P['vwap']
    tr = P.get('turn_ratio')
    mf_xl = P.get('mf_xl_r')
    mf_net = P.get('mf_net_r')

    rng = (high - low).replace(0, np.nan)
    F = {}

    # ---- 动量/反转 ----
    F['rev_1d'] = -ret
    F['rev_5d'] = -ts_mean(ret, 5)
    F['mom20_rev'] = -ts_mean(ret, 20)
    F['mom60'] = ts_mean(ret, 60)
    F['price_pos20'] = -ts_pos(close, 20)
    F['price_pos60'] = -ts_pos(close, 60)

    # ---- 波动率 ----
    F['vol20'] = -ts_std(ret, 20)
    F['vol60'] = -ts_std(ret, 60)
    F['vol_ratio'] = -(ts_std(ret, 20) / (ts_std(ret, 60) + 1e-12))
    F['vol_chg'] = -(ts_std(ret, 20) / (ts_std(ret, 20).shift(20) + 1e-12))

    # ---- 流动性/换手 ----
    F['amt_log'] = -np.log(ts_mean(turn, 20) + 1)
    F['amt_chg'] = ts_mean(turn, 5) / (ts_mean(turn, 60) + 1e-12)
    if tr is not None:
        F['turn20'] = -ts_mean(tr, 20)
        F['turn_vol'] = -ts_std(tr, 20)
        F['turn_chg'] = ts_mean(tr, 5) / (ts_mean(tr, 60) + 1e-12)

    # ---- 量价关系 ----
    F['corr_vr20'] = -ts_corr(vol, ret, 20)
    F['corr_vr60'] = -ts_corr(vol, ret, 60)
    F['corr_cp20'] = -ts_corr(close, vol, 20)
    F['vol_ret_div'] = -(ts_std(ret, 20) / (ts_mean(tr, 20) + 1e-12) if tr is not None
                         else ts_std(ret, 20))

    # ---- 资金流(用户数据特色) ----
    if mf_xl is not None:
        F['mf_xl5'] = ts_mean(mf_xl, 5)
        F['mf_xl10'] = ts_mean(mf_xl, 10)
        F['mf_xl20'] = ts_mean(mf_xl, 20)
        F['mf_xl_trd'] = ts_delta(ts_mean(mf_xl, 10), 10)
        F['mf_xl_vol'] = -ts_std(mf_xl, 20)
    if mf_net is not None:
        F['mf_net10'] = ts_mean(mf_net, 10)
        F['mf_net20'] = ts_mean(mf_net, 20)
        F['mf_net_trd'] = ts_delta(ts_mean(mf_net, 10), 10)

    # ---- 价格结构/影线 ----
    F['upper_shadow'] = -(high - np.maximum(open_, close)) / rng
    F['lower_shadow'] = (np.minimum(open_, close) - low) / rng
    F['close_pos'] = (close - low) / rng
    F['hl_range'] = -rng / close
    F['amp20'] = -ts_mean(rng / close, 20)
    F['down_shadow'] = ts_mean((np.minimum(open_, close) - low) / rng, 20)

    # ---- 跳空 ----
    gap = (open_ - pc) / pc
    F['gap'] = -gap
    F['gap20'] = -ts_mean(gap, 20)

    # ---- 日内反转 / VWAP ----
    F['intraday'] = (close - open_) / open_
    F['intraday20'] = ts_mean((close - open_) / open_, 20)
    F['vwap_dev'] = (close - vwap) / vwap
    F['vwap_dev20'] = ts_mean((close - vwap) / vwap, 20)

    return F


if __name__ == '__main__':
    t0 = time.time()
    print("加载面板 ...")
    P = load_panel()
    P = prepare(P)
    close = P['close']
    print(f"  字段: {list(P.keys())}")
    print(f"  区间: {close.index.min()} ~ {close.index.max()}  {close.shape}")

    print("\n构建因子 ...")
    F = build_factors(P)
    print(f"  候选因子数: {len(F)}")

    print("\n逐个检验 ...")
    rows, ic_store = [], {}
    for i, (nm, fac) in enumerate(F.items(), 1):
        try:
            f = cs_rank(fac.astype('float64'))
            r = evaluate(f, close, nm)
            del f
        except Exception as e:
            print(f"  [{i}/{len(F)}] {nm} ERR {type(e).__name__}: {str(e)[:60]}")
            continue
        if r is None:
            print(f"  [{i}/{len(F)}] {nm} 样本不足")
            continue
        ic_store[nm] = r.pop('ic_series')
        ok, msg = pass_filter(r)
        r['pass'] = 'PASS' if ok else msg[:28]
        rows.append(r)
        print(f"  [{i}/{len(F)}] {nm:16s} IC={r['ic']:+.4f} IR={r['ic_ir']:+.3f} "
              f"年化超额={r['ann_ex']*100:+6.2f}% Calmar={r['calmar'] if r['calmar'] else 0:5.2f} "
              f"| {r['pass']}")

    res = pd.DataFrame(rows)
    if len(res):
        res = res.sort_values('ic', key=abs, ascending=False)
        print("\n" + "=" * 100)
        print("Round 1 结果(按|IC|排序)")
        print("=" * 100)
        cols = ['name', 'ic', 'ic_ir', 'ann_top', 'ann_mkt', 'ann_ex', 'dd', 'sharpe', 'calmar']
        print(res[cols].round(4).to_string(index=False))
        print("\n(ann_top=Top组绝对年化, ann_mkt=全市场等权年化, ann_ex=超额)")
        npass = (res['pass'] == 'PASS').sum()
        print(f"\n通过过滤: {npass}/{len(res)}")

        print("\n通过因子的年度超额:")
        for _, r in res[res['pass'] == 'PASS'].iterrows():
            yr = {k: f"{v*100:+.1f}%" for k, v in sorted(r['yr'].items())}
            print(f"  {r['name']:16s} IC={r['ic']:+.4f}  {yr}")

    with open(IC_CACHE, 'wb') as f:
        pickle.dump(ic_store, f)
    print(f"\nIC序列已存 {IC_CACHE}   总耗时 {time.time()-t0:.0f}s")
