# -*- coding: utf-8 -*-
"""
决定性对账: combo_g6 的"超额"到底是谁给的?
研究框架基准 = 可交易池等权(年化8.95%, 本身含小盘beta, 远高于沪深300)
本脚本用**同一个选股逻辑**, 同时对照三个基准:
  A. 可交易池等权(研究口径)
  B. 沪深300
  C. 中证1000(小盘代表)
若 A 超额高而 B 超额低 => 说明"超额"主要来自小盘beta, 而非因子alpha
"""
import os
import sys
import gc
import numpy as np
import pandas as pd
import h5py

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import factor_miner as fm
from factor_miner import load_panel, cs_rank, get_universe, FWD, N_GRP
from round5_fund import FundPanels, BarraNeut, cs_neutralize_lnmc
from round7_growth import build_components, G6

GRID = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    '..', 'all01_dev', 'fund_grid_jq.pkl')
GRID = os.path.abspath(GRID)
IDX_H5 = r'E:\rq\bundle\indexes.h5'


def load_index(code):
    with h5py.File(IDX_H5, 'r') as f:
        if code not in f:
            return None
        a = f[code][:]
        d = (a['datetime'] // 1000000).astype('int64')
        return pd.Series(a['close'].astype(float), index=d).sort_index()


def main():
    START = 20180101
    P = load_panel(['close', 'mktcap'])
    close = P['close'].astype('float64')
    dates = close.index.values
    cols = list(close.columns)
    mkt = P['mktcap'].reindex(index=dates, columns=cols).values.astype(np.float64)

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

    hs300 = load_index('000300.XSHG')
    zz1000 = load_index('000852.XSHG')
    print(f"沪深300 {len(hs300) if hs300 is not None else 0} 日, "
          f"中证1000 {len(zz1000) if zz1000 is not None else 0} 日")

    def run(mode, label):
        rk = cs_rank(pd.DataFrame(combo, index=dates, columns=cols)).values
        if mode == 'barra':
            X = BN(rk)
        elif mode == 'lnmc':
            X = cs_neutralize_lnmc(rk, mkt)
        else:
            X = rk
        fac = cs_rank(pd.DataFrame(X, index=dates, columns=cols))
        del X, rk
        gc.collect()

        tops, pools, dts = [], [], []
        b300, b1000 = [], []
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
            rt = r.reindex(top).mean()
            rm = r.reindex(fv.index).mean()      # 池内等权(研究基准)
            if not (np.isfinite(rt) and np.isfinite(rm)):
                continue
            tops.append(rt)
            pools.append(rm)
            dts.append(d)
            if hs300 is not None and d1 in hs300.index and d2 in hs300.index:
                b300.append(hs300[d2] / hs300[d1] - 1)
            else:
                b300.append(np.nan)
            if zz1000 is not None and d1 in zz1000.index and d2 in zz1000.index:
                b1000.append(zz1000[d2] / zz1000[d1] - 1)
            else:
                b1000.append(np.nan)
        tr = pd.Series(tops, index=dts)
        pr = pd.Series(pools, index=dts)
        h3 = pd.Series(b300, index=dts)
        z1 = pd.Series(b1000, index=dts)

        def ann(nv):
            yrs = len(nv) * FWD / 243
            a = nv.iloc[-1] ** (1 / yrs) - 1
            dd = (nv / nv.cummax() - 1).min()
            return a, dd, (a / abs(dd) if dd < 0 else np.nan)

        out = {}
        # 成本: 研究口径 (1-keep)*0.001*2
        prev, cost = None, []
        for d in dts:
            if prev is None:
                cost.append(0.0)
            else:
                cost.append(0.0)      # 近似: 研究Top10%换手低, 成本约0.85%/年
            prev = d
        tr_net = tr - 0.0085 / (243 / FWD)      # 年化0.85%摊到每期
        at, _, _ = ann((1 + tr).cumprod())
        at_n, dt_n, ct_n = ann((1 + tr_net).cumprod())
        ap, dp, cp = ann((1 + pr).cumprod())
        a3, d3, c3 = ann((1 + h3.fillna(0)).cumprod())
        a1, d1_, c1 = ann((1 + z1.fillna(0)).cumprod())
        ex_pool = ann((1 + (tr_net - pr)).cumprod())
        ex_300 = ann((1 + (tr_net - h3.fillna(0))).cumprod())
        ex_1000 = ann((1 + (tr_net - z1.fillna(0))).cumprod())
        print(f"\n{'='*84}\n[{label}] {mode}  n={len(tr)} 期")
        print(f"  Top组绝对年化     {at_n*100:6.2f}%   回撤 {dt_n*100:6.2f}%  Calmar {ct_n:5.2f}")
        print(f"  基准A 池内等权   {ap*100:6.2f}%   回撤 {dp*100:6.2f}%")
        print(f"  基准B 沪深300    {a3*100:6.2f}%   回撤 {d3*100:6.2f}%")
        print(f"  基准C 中证1000   {a1*100:6.2f}%   回撤 {d1_*100:6.2f}%")
        print(f"  ---- 超额(扣费后) ----")
        print(f"  vs 池内等权(研究口径) {ex_pool[0]*100:+6.2f}%  Calmar {ex_pool[2]:5.2f}")
        print(f"  vs 沪深300           {ex_300[0]*100:+6.2f}%  Calmar {ex_300[2]:5.2f}")
        print(f"  vs 中证1000          {ex_1000[0]*100:+6.2f}%  Calmar {ex_1000[2]:5.2f}")
        return dict(mode=mode, top=at_n, pool=ap, hs300=a3, zz1000=a1,
                    ex_pool=ex_pool[0], ex_300=ex_300[0], ex_1000=ex_1000[0])

    rows = []
    rows.append(run('barra', 'combo_g6'))
    rows.append(run('raw', 'combo_g6'))
    df = pd.DataFrame(rows)
    print("\n" + "=" * 84)
    print("汇总:")
    print(df.round(4).to_string(index=False))
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           'bench_gap.txt'), 'w', encoding='utf-8') as f:
        f.write(df.round(4).to_string(index=False))
    print("\n关键: 若 ex_pool 明显 > ex_300, 说明研究口径的+5%主要来自【小盘beta】")


if __name__ == '__main__':
    main()
