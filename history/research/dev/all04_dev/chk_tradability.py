# -*- coding: utf-8 -*-
"""
追查实盘 vs 研究的 8pp 缺口: 研究框架的"可实现性"假设
研究 evaluate(): T日选股 -> 以 close[T+1] 买入, 默认【想买就能按收盘价买到】
实盘: T+1 日涨停买不进 / 停牌买不了 / 有佣金印花税
本脚本在研究框架里逐步加约束, 看收益如何被吃掉:
  L0 研究原版(无约束)
  L1 +买入日(T+1)涨停不可买
  L2 +买入日停牌不可买
  L3 +真实成本(往返0.5% x 换手)
"""
import os
import sys
import gc
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from factor_miner import load_panel, cs_rank, get_universe, FWD, N_GRP
from round5_fund import FundPanels, BarraNeut
from round7_growth import build_components, G6

GRID = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    '..', 'all01_dev', 'fund_grid_jq.pkl'))
START = 20180101


def main():
    P = load_panel(['close', 'mktcap', 'limit_up', 'limit_down', 'turnover'])
    close = P['close'].astype('float64')
    dates = close.index.values
    cols = list(close.columns)
    lu = P['limit_up'].reindex(index=dates, columns=cols)
    vol = P['turnover'].reindex(index=dates, columns=cols)

    FP = FundPanels(GRID, dates)
    F = build_components(FP)
    acc, n = None, None
    for c in G6:
        rk = cs_rank(pd.DataFrame(F[c], index=dates, columns=cols)).values
        good = np.isfinite(rk)
        acc = np.where(good, rk, 0.0) if acc is None else acc + np.where(good, rk, 0.0)
        n = good.astype(np.float64) if n is None else n + good.astype(np.float64)
    combo = (acc / np.maximum(n, 1.0)).astype(np.float32)
    combo[n < 1] = np.nan
    del F, acc, n
    gc.collect()

    BN = BarraNeut(os.path.join(HERE, 'barra.h5'), dates, cols)
    U = get_universe().reindex(index=dates, columns=cols).fillna(False)
    idx = dates[dates >= START]

    X = BN(cs_rank(pd.DataFrame(combo, index=dates, columns=cols)).values)
    fac = cs_rank(pd.DataFrame(X, index=dates, columns=cols))
    del X
    gc.collect()

    # 逐日: 涨停/停牌掩码
    lu_up = (close >= lu - 1e-6) & lu.notna()          # 涨停
    suspended = vol.fillna(0) <= 0                      # 无成交=停牌

    res = {}
    prev_top = None
    tops_L0, tops_L1, tops_L2, dts, turn = [], [], [], [], []
    for d in idx[::FWD][:-1]:
        u = U.loc[d]
        fv = fac.loc[d][u].dropna()
        if len(fv) < N_GRP * 10:
            continue
        nxt = idx[idx > d]
        if len(nxt) <= FWD:
            continue
        d1, d2 = nxt[0], nxt[FWD]
        grp = pd.qcut(fv.rank(method='first'), N_GRP, labels=False)
        top = fv.index[grp == N_GRP - 1]
        r = close.loc[d2] / close.loc[d1] - 1

        rt0 = r.reindex(top).mean()
        # L1: 剔除买入日(T+1)涨停
        ok1 = top[~lu_up.loc[d1].reindex(top).fillna(False)]
        rt1 = r.reindex(ok1).mean() if len(ok1) > 10 else np.nan
        # L2: 再剔除买入日停牌
        ok2 = ok1[~suspended.loc[d1].reindex(ok1).fillna(True)]
        rt2 = r.reindex(ok2).mean() if len(ok2) > 10 else np.nan

        if not (np.isfinite(rt0)):
            continue
        tops_L0.append(rt0)
        tops_L1.append(rt1)
        tops_L2.append(rt2)
        dts.append(d)
        if prev_top is not None:
            turn.append(1 - len(set(top) & prev_top) / max(len(prev_top), 1))
        prev_top = set(top)

    s0 = pd.Series(tops_L0, index=dts)
    s1 = pd.Series(tops_L1, index=dts).fillna(0.0)
    s2 = pd.Series(tops_L2, index=dts).fillna(0.0)
    tr = np.mean(turn) if turn else np.nan

    def ann(nv):
        yrs = len(nv) * FWD / 243
        a = nv.iloc[-1] ** (1 / yrs) - 1
        dd = (nv / nv.cummax() - 1).min()
        return a, dd, (a / abs(dd) if dd < 0 else np.nan)

    print(f"单次调仓平均换手率: {tr*100:.1f}%  -> 年化换手 {tr*243/FWD*100:.0f}%")
    cost_study = tr * 0.001 * 2          # 研究口径
    cost_real = tr * 0.005               # 实盘往返(佣金千二x2 + 印花税千一)
    print(f"每期成本: 研究 {cost_study*100:.3f}%  实盘 {cost_real*100:.3f}%")

    out = []
    for lab, s, cost in [('L0 研究原版(无成本)', s0, 0.0),
                         ('L1 +次日涨停不可买', s1, 0.0),
                         ('L2 +次日停牌不可买', s2, 0.0),
                         ('L3 +研究成本(千一双边)', s2, cost_study),
                         ('L4 +实盘成本(往返0.5%)', s2, cost_real)]:
        nv = (1 + s - cost).cumprod()
        a, dd, c = ann(nv)
        out.append(dict(层级=lab, 年化=a, 回撤=dd, Calmar=c))
        print(f"  {lab:26s} 年化 {a*100:6.2f}%  回撤 {dd*100:6.2f}%  Calmar {c:5.2f}")
    df = pd.DataFrame(out)
    print("\n实盘(N=400 universe) 2017起 5.72%; 2018起需另算 —— 用同一脚本切 2018 起:")
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           'tradability.txt'), 'w', encoding='utf-8') as f:
        f.write(df.round(4).to_string(index=False))


if __name__ == '__main__':
    main()
