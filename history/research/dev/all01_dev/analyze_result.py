# -*- coding: utf-8 -*-
"""分析 rqalpha 回测结果 pkl: 关键指标 + 年度收益/回撤 + 最深回撤时点"""
import sys
import pickle
import numpy as np
import pandas as pd

path = sys.argv[1] if len(sys.argv) > 1 else None
if not path:
    print("用法: python analyze_result.py <result.pkl>")
    sys.exit(1)

with open(path, 'rb') as f:
    r = pickle.load(f)

s = r['summary']


def pct(x):
    return f"{x*100:8.2f}%"


print("=" * 78)
print(f"回测区间: {s['start_date']} ~ {s['end_date']}   基准: {s['benchmark_symbol']}")
print("=" * 78)
print(f"  总收益        {pct(s['total_returns'])}      基准 {pct(s['benchmark_total_returns'])}")
print(f"  年化收益      {pct(s['annualized_returns'])}      基准 {pct(s['benchmark_annualized_returns'])}")
print(f"  最大回撤      {pct(s['max_drawdown'])}")
print(f"  Sharpe        {s['sharpe']:.3f}")
print(f"  Sortino       {s['sortino']:.3f}")
print(f"  波动率        {pct(s['volatility'])}")
print(f"  Alpha / Beta  {s['alpha']:.4f} / {s['beta']:.3f}")
print(f"  Calmar        {s['annualized_returns']/max(s['max_drawdown'],1e-9):.3f}")
print(f"  换手率(双侧年化) {s.get('annualized_twoside_turnover', float('nan')):.2f}")

pf, bp = r['portfolio'], r['benchmark_portfolio']


def netval(df):
    if 'unit_net_value' in df.columns:
        return df['unit_net_value']
    return df['total_value'] / df['total_value'].iloc[0]


nv = netval(pf)
bnv = netval(bp)

print("\n" + "=" * 78)
print("年度表现")
print("=" * 78)
print(f"  {'年份':<6}{'策略收益':>11}{'基准收益':>11}{'超额':>11}{'策略年内最大回撤':>16}")
rows = []
for y, g in nv.groupby(nv.index.year):
    ret = g.iloc[-1] / g.iloc[0] - 1
    dd = (g / g.cummax() - 1).min()
    bg = bnv[bnv.index.year == y]
    bret = (bg.iloc[-1] / bg.iloc[0] - 1) if len(bg) else np.nan
    print(f"  {y:<6}{ret*100:>10.2f}%{bret*100:>10.2f}%{(ret-bret)*100:>10.2f}%{dd*100:>15.2f}%")
    rows.append((y, ret, bret, dd))

dd_all = nv / nv.cummax() - 1
print("\n最深回撤时点 (Top 10):")
peak = nv.iloc[0]
for d, v in dd_all.nsmallest(10).sort_index().items():
    print(f"  {str(d)[:10]}  {v*100:7.2f}%")

# 回撤 >20% 的持续区间统计
print("\n回撤超过 20% 的交易日占比: "
      f"{(dd_all < -0.20).mean()*100:.1f}%")
print(f"回撤超过 30% 的交易日占比: {(dd_all < -0.30).mean()*100:.1f}%")
print(f"回撤超过 40% 的交易日占比: {(dd_all < -0.40).mean()*100:.1f}%")
