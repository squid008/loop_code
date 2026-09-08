# -*- coding: utf-8 -*-
"""
对账: 纯 combo_g6(barra) 策略 vs 研究框架(Round7)
研究框架口径: 2018-01起, 周频, 可交易池内 Top10%(≈350只) 等权, 成本千一(按换手率)
  基准=可交易池等权 年化 8.95%   Top组绝对年化 14.37%   超额 +5.25%
策略口径(all04_barra): 2017-01起, 成本千二含滑点+真实撮合, 基准=沪深300
本脚本按不同起始年切分, 定位差异来源
"""
import os
import glob
import sys
import pickle
import numpy as np
import pandas as pd

HERE = r'd:\rqalpha_demo\strategies\all04'


def stats(nv):
    r = nv.pct_change()
    yrs = (nv.index[-1] - nv.index[0]).days / 365.25
    ann = nv.iloc[-1] ** (1 / yrs) - 1
    dd = (nv / nv.cummax() - 1).min()
    sh = r.mean() / r.std() * np.sqrt(252) if r.std() > 0 else np.nan
    return ann, dd, sh


def load(pkl):
    with open(pkl, 'rb') as f:
        res = pickle.load(f)
    pf = res['portfolio']
    nv = (pf['unit_net_value'] if 'unit_net_value' in pf.columns
          else pf['total_value'] / pf['total_value'].iloc[0])
    bp = res['benchmark_portfolio']
    bench = (bp['unit_net_value'] if 'unit_net_value' in bp.columns
             else bp['total_value'] / bp['total_value'].iloc[0])
    return nv, bench


def show(tag, pkl, cuts=('2017-01-01', '2018-01-01', '2021-01-01')):
    nv, bench = load(pkl)
    print(f"\n{'='*78}\n{tag}\n  文件 {os.path.basename(pkl)}")
    print(f"  全区间 {nv.index[0].date()}~{nv.index[-1].date()}: "
          f"年化 {stats(nv)[0]*100:6.2f}%  回撤 {stats(nv)[1]*100:7.2f}%  "
          f"Sharpe {stats(nv)[2]:5.3f}   | 沪深300 {stats(bench)[0]*100:6.2f}%")
    for c in cuts:
        a = nv[nv.index >= c]
        b = bench[bench.index >= c]
        if len(a) < 100:
            continue
        sa, sb = stats(a), stats(b)
        print(f"  {c}起:  年化 {sa[0]*100:6.2f}%  回撤 {sa[1]*100:7.2f}%  "
              f"Sharpe {sa[2]:5.3f}   | 沪深300 {sb[0]*100:6.2f}%   "
              f"超额 {(sa[0]-sb[0])*100:+6.2f}pp")
    print("  年度:")
    for y, g in nv.groupby(nv.index.year):
        bg = bench[bench.index.year == y]
        r1 = (g.iloc[-1] / g.iloc[0] - 1) * 100
        r2 = ((bg.iloc[-1] / bg.iloc[0] - 1) * 100) if len(bg) else np.nan
        print(f"    {y}  策略 {r1:7.2f}%   沪深300 {r2:7.2f}%   差 {r1-r2:+7.2f}pp")


if __name__ == '__main__':
    # 纯 g6: N=30 / N=300
    for n in [30, 300]:
        fs = sorted(glob.glob(os.path.join(HERE, f'all04_barra_*_20170103_20260805.pkl')))
        # 用文件内的持股数区分: 从同名 log 不好取, 改用修改时间顺序 + 手工指定
    fs = sorted(glob.glob(os.path.join(HERE, 'all04_barra_*_20170103_20260805.pkl')))
    for p in fs:
        # 从结果里推断持股数
        with open(p, 'rb') as f:
            res = pickle.load(f)
        pos = max(len(v) for v in [res.get('positions', [])]) if isinstance(
            res.get('positions'), list) else 0
        show(f"纯 combo_g6(barra)  持股≈{pos if pos else '?'}", p)
    # all03 对照(同区间需要重跑, 这里用全区间 2014 起的作参考)
    fs2 = sorted(glob.glob(os.path.join(HERE, 'all04_20260907_1559_35_*.pkl')))
    for p in fs2:
        show("对照 all03(=all04 --pool=all03 --no-g6)", p)
