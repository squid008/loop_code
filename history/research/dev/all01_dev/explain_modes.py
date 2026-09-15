# -*- coding: utf-8 -*-
"""
把四个口径"翻译"成可观察的组合特征: 每个口径选出的 Top 组到底是什么股票?
输出: 平均市值分位 / 行业集中度 / 逐年超额 / 与基准(可交易池等权)对比
"""
import os
import sys
import gc
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import factor_miner as fm
from factor_miner import load_panel, cs_rank, get_universe, FWD, N_GRP, START
from round5_fund import (FundPanels, BarraNeut, cs_neutralize_lnmc,
                         build_size_bucket, strat_rank, ind_demean)
from round7_growth import build_components, G6, NB

DEV = os.path.dirname(os.path.abspath(__file__))
GRID = os.path.join(DEV, 'fund_grid_jq.pkl')
OUT = os.path.join(DEV, 'explain_modes.txt')


def main():
    log = []
    P = load_panel(['close', 'mktcap'])
    close = P['close'].astype('float64')
    dates = close.index.values
    cols = list(close.columns)
    mkt = P['mktcap'].reindex(index=dates, columns=cols).values.astype(np.float64)
    FP = FundPanels(GRID, dates)
    BN = BarraNeut(os.path.join(HERE, 'barra.h5'), dates, cols)
    bkt = build_size_bucket(mkt.astype(np.float32), NB)

    F = build_components(FP)
    acc, n = None, None
    for c in G6:
        rk = cs_rank(pd.DataFrame(F[c], index=dates, columns=cols)).values
        good = np.isfinite(rk)
        v = np.where(good, rk, 0.0)
        acc = v if acc is None else acc + v
        n = good.astype(np.float64) if n is None else n + good.astype(np.float64)
    combo = pd.DataFrame((acc / np.maximum(n, 1)).astype(np.float32),
                         index=dates, columns=cols)
    del F, acc, n
    gc.collect()

    U = get_universe().reindex(index=dates, columns=cols).fillna(False)
    idx = dates[dates >= START]
    # 市值分位(每日横截面, 1=最大)
    mc_pct = pd.DataFrame(mkt, index=dates, columns=cols).rank(axis=1, pct=True)
    gid = pd.DataFrame(BN.gid, index=dates, columns=cols)

    def transform(mode):
        rk = cs_rank(combo).values
        if mode == 'raw':
            return rk
        if mode == 'lnmc':
            return cs_neutralize_lnmc(rk, mkt)
        if mode == 'barra':
            return BN(rk)
        return ind_demean(strat_rank(rk, bkt, NB), BN)

    rows = []
    for mode in ['raw', 'lnmc', 'barra', 'strat']:
        X = np.asarray(transform(mode), dtype=np.float64)
        fac = pd.DataFrame(X, index=dates, columns=cols)
        f = cs_rank(fac)
        mcp, inds, tops, mkts, dts = [], [], [], [], []
        prev = None
        turn = []
        for d in idx[::FWD][:-1]:
            u = U.loc[d]
            fv = f.loc[d][u].dropna()
            if len(fv) < N_GRP * 10:
                continue
            nxt = idx[idx > d]
            if len(nxt) <= FWD:
                continue
            d1, d2 = nxt[0], nxt[FWD]
            grp = pd.qcut(fv.rank(method='first'), N_GRP, labels=False)
            top = fv.index[grp == N_GRP - 1]
            r = (close.loc[d2] / close.loc[d1] - 1)
            rt = r.reindex(top).mean()
            rm = r.reindex(fv.index).mean()
            if not (np.isfinite(rt) and np.isfinite(rm)):
                continue
            mcp.append(mc_pct.loc[d, top].mean())
            vc = gid.loc[d, top].value_counts(normalize=True)
            inds.append(vc.iloc[0] if len(vc) else np.nan)
            tops.append(rt)
            mkts.append(rm)
            dts.append(d)
            if prev is not None:
                turn.append(1 - len(set(top) & prev) / len(prev))
            prev = set(top)
        tr = pd.Series(tops, index=dts)
        mr = pd.Series(mkts, index=dts)
        ex = tr - mr
        yr = ex.groupby(ex.index // 10000).apply(lambda s: (1 + s).prod() - 1)
        nav = (1 + ex).cumprod()
        dd = (nav / nav.cummax() - 1).min()
        yrs = len(tr) * FWD / 243
        rows.append(dict(mode=mode,
                         平均市值分位=np.mean(mcp),
                         最大行业占比=np.nanmean(inds),
                         年换手率=np.mean(turn) if turn else np.nan,
                         超额年化=nav.iloc[-1] ** (1 / yrs) - 1,
                         回撤=dd,
                         Calmar=(nav.iloc[-1] ** (1 / yrs) - 1) / abs(dd),
                         **{str(k): v for k, v in yr.items()}))
        log.append(f"{mode} 完成  n_rebal={len(tr)}")

    df = pd.DataFrame(rows).set_index('mode')
    pct_cols = [c for c in df.columns if c.isdigit()]
    out = []
    out.append('== 各口径 Top 组的组合特征 (combo_g6, 2018-2026) ==')
    out.append(df[['平均市值分位', '最大行业占比', '年换手率',
                   '超额年化', '回撤', 'Calmar']].round(4).to_string())
    out.append('')
    out.append('== 逐年超额收益 ==')
    out.append((df[pct_cols] * 100).round(2).to_string())
    out.append('')
    out.append('\n'.join(log))
    txt = '\n'.join(out)
    print(txt)
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write(txt)


if __name__ == '__main__':
    main()
