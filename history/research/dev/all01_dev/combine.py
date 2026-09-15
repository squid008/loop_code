# -*- coding: utf-8 -*-
"""
组合回测(后处理) + 趋势择时模拟。
组合: 多策略 pkl 净值按月度再平衡合成。
择时: 指数收盘价与均线关系控制总仓位(用 T-1 日信号作用于 T 日, 无未来函数)。
  规则1 年线  : close < MA200  -> 仓位 floor
  规则2 双均线: MA20 < MA60   -> 仓位 floor
用法: python combine.py <pkl...> [w...] [--ma=200,0.3 | --dual=20,60,0.3]
"""
import os
import sys
import pickle
import numpy as np
import pandas as pd

args = sys.argv[1:]
paths = [a for a in args if a.endswith('.pkl')]
rest = [a for a in args if not a.endswith('.pkl')]
ma_opt = None
dual_opt = None
val_opt = None
crowd_opt = None
panic_opt = None
pos_rest = []
for a in rest:
    if a.startswith('--ma='):
        w, f = a[5:].split(',')
        ma_opt = (int(w), float(f))
    elif a.startswith('--dual='):
        p1, p2, f = a[7:].split(',')
        dual_opt = (int(p1), int(p2), float(f))
    elif a.startswith('--val='):
        thr, f, lookback = a[6:].split(',')
        val_opt = (float(thr), float(f), int(lookback))
    elif a.startswith('--panic='):
        # 恐慌期加杠杆: dd_hi(超跌占比阈值%), lev(杠杆倍数), rate(融资年利率)
        dd_hi, lev, rate = a[8:].split(',')
        panic_opt = (float(dd_hi), float(lev), float(rate))
    elif a.startswith('--crowd='):
        # 泡沫减仓 + 恐慌加仓: dd_hi,dd_lo,idx_pos_thr,floor,base
        dd_hi, dd_lo, pos_thr, floor, base = a[8:].split(',')
        crowd_opt = (float(dd_hi), float(dd_lo), float(pos_thr), float(floor), float(base))
    elif not a.startswith('--'):
        pos_rest.append(float(a))
ws = np.array(pos_rest if len(pos_rest) >= len(paths) else [1.0] * len(paths))
ws = ws[:len(paths)] / ws[:len(paths)].sum()


def netval(p):
    with open(p, 'rb') as f:
        r = pickle.load(f)
    df = r['portfolio']
    return (df['unit_net_value'] if 'unit_net_value' in df.columns
            else df['total_value'] / df['total_value'].iloc[0])


nvs = [netval(p) for p in paths]
idx = None
for nv in nvs:
    idx = nv.index if idx is None else idx.intersection(nv.index)

# 择时信号源: 默认沪深300基准; --self 用组合自身净值(策略自适应风控)
use_self = '--self' in rest
month = idx.to_period('M')
with open(paths[0], 'rb') as f:
    bp = pickle.load(f)['benchmark_portfolio']
bench = (bp['unit_net_value'] if 'unit_net_value' in bp.columns
         else bp['total_value'] / bp['total_value'].iloc[0])
bench = bench.loc[idx].ffill()

if ma_opt:
    w, floor = ma_opt
    ma = bench.rolling(w).mean()
    sig = (bench > ma).astype(float)
    sig = sig.where(bench.rolling(w).count() >= w, 1.0)
    tag = f"年线 MA{w} 破位仓位{floor:.0%}"
elif dual_opt:
    p1, p2, floor = dual_opt
    sig = (bench.rolling(p1).mean() > bench.rolling(p2).mean()).astype(float)
    sig = sig.where(bench.rolling(p2).count() >= p2, 1.0)
    tag = f"双均线 MA{p1}/MA{p2} 死叉仓位{floor:.0%}"
elif val_opt:
    # 估值择时: 全市场中位数PB 的滚动分位(周频, 前向填充到日频)
    thr, floor, lb = val_opt
    snap = pd.read_pickle(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                       'factor_snapshot.pkl'))
    med = snap.groupby('date')['pb'].median()
    med.index = pd.to_datetime(med.index.astype(str))
    med = med.reindex(med.index.union(idx)).ffill().loc[idx]
    pct = med.rolling(lb, min_periods=lb // 2).rank(pct=True)
    sig = (pct < thr).astype(float).where(pct.notna(), 1.0)
    tag = f"估值择时: 全市场中位PB {lb}周分位>={thr:.0%} -> 仓位{floor:.0%}"
elif crowd_opt:
    # 泡沫减仓(指数高位+无超跌股) + 恐慌加仓(超跌股占比高)
    dd_hi, dd_lo, pos_thr, floor, base = crowd_opt
    rg = pd.read_csv(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  'market_regime.csv'), index_col=0)
    rg.index = pd.to_datetime(rg.index)
    rg = rg.reindex(rg.index.union(idx)).ffill().loc[idx]
    dd = rg['dd25'].ffill()
    pos = rg['idx_pos250'].ffill() if 'idx_pos250' in rg else pd.Series(np.nan, index=idx)
    hot = (pos >= pos_thr) & (dd <= dd_lo)
    panic = dd >= dd_hi
    lev = pd.Series(base, index=idx)
    lev[hot] = floor
    lev[panic] = 1.0
    sig = lev.ffill().fillna(base)
    tag = (f"拥挤/超跌择时: 恐慌(超跌>={dd_hi:.0f}%)满仓 | "
           f"泡沫(指数>={pos_thr:.0f}%高点且超跌<={dd_lo:.0f}%)仓位{floor:.0%} | 常态{base:.0%}")
else:
    sig = pd.Series(1.0, index=idx)
    tag = "无择时"

if use_self:
    # 先合成无择时组合净值, 用它自身做信号(组合自适应回撤控制)
    r0 = pd.DataFrame({i: nv.loc[idx].pct_change() for i, nv in enumerate(nvs)})
    c0 = pd.Series(np.nan, index=idx)
    vals = np.array([1.0] * len(paths))
    port = 1.0
    prev_m = None
    for i in range(len(idx)):
        m = month[i]
        if prev_m is not None and m != prev_m:
            vals = np.array([port * x for x in ws])
        vals = vals * (1 + r0.iloc[i].fillna(0).values)
        port = vals.sum()
        c0.iloc[i] = port
        prev_m = m
    c0 = c0 / c0.iloc[0]
    bench = c0
    if ma_opt:
        w, floor = ma_opt
        ma = bench.rolling(w).mean()
        sig = (bench > ma).astype(float)
        sig = sig.where(bench.rolling(w).count() >= w, 1.0)
        tag = f"[自身净值] 年线 MA{w} 破位仓位{floor:.0%}"
    elif dual_opt:
        p1, p2, floor = dual_opt
        sig = (bench.rolling(p1).mean() > bench.rolling(p2).mean()).astype(float)
        sig = sig.where(bench.rolling(p2).count() >= p2, 1.0)
        tag = f"[自身净值] 双均线 MA{p1}/MA{p2} 死叉仓位{floor:.0%}"

# 恐慌期加杠杆(用 T-1 日超跌信号, 无未来函数; 借入部分按融资利率计息)
lev = pd.Series(1.0, index=idx)
fin_rate = 0.0
if panic_opt:
    dd_hi, lev_v, fin_rate = panic_opt
    _rg = pd.read_csv(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   'market_regime.csv'), index_col=0)
    _rg.index = pd.to_datetime(_rg.index)
    _dd = _rg['dd25'].reindex(_rg.index.union(idx)).ffill().loc[idx]
    lev[_dd >= dd_hi] = lev_v
    n_days = int((lev > 1.0).sum())
    tag = (tag + f" | 恐慌加杠杆: 超跌>={dd_hi:.0f}% -> {lev_v:.1f}倍"
                 f"(融资{fin_rate:.0%}, 触发{n_days}日)")
lev_lag = lev.shift(1).fillna(1.0)   # T-1 信号作用于 T 日

# 组合收益(月度再平衡)
rets = pd.DataFrame({i: nv.loc[idx].pct_change() for i, nv in enumerate(nvs)})
month = idx.to_period('M')
combo = pd.Series(np.nan, index=idx)
vals = np.array([1.0] * len(paths))
port = 1.0
prev_m = None
for i in range(len(idx)):
    m = month[i]
    if prev_m is not None and m != prev_m:
        vals = np.array([port * x for x in ws])
    # 择时(空仓部分得0收益) + 恐慌杠杆(借入部分按日计息)
    _l = lev_lag.iloc[i]
    g = (1 + rets.iloc[i].fillna(0).values * sig.iloc[i] * _l
         - (_l - 1.0) * fin_rate / 252)
    vals = vals * g
    port = vals.sum()
    combo.iloc[i] = port
    prev_m = m
combo = combo / combo.iloc[0]
r = combo.pct_change()

years = (idx[-1] - idx[0]).days / 365.25
ann = combo.iloc[-1] ** (1 / years) - 1
dd = (combo / combo.cummax() - 1).min()
sharpe = r.mean() / r.std() * np.sqrt(252) if r.std() > 0 else np.nan

print("=" * 76)
print("组合: " + " + ".join(f"{os.path.basename(p)[6:12]}({x:.0%})" for p, x in zip(paths, ws)))
print(f"择时: {tag}")
print("=" * 76)
print(f"  年化收益   {ann*100:8.2f}%")
print(f"  最大回撤   {dd*100:8.2f}%")
print(f"  Calmar     {ann/abs(dd):8.3f}")
print(f"  Sharpe     {sharpe:8.3f}")
print(f"  总收益     {(combo.iloc[-1]-1)*100:8.2f}%")

print("\n年度:   组合收益    组合年内回撤")
for y, g in combo.groupby(combo.index.year):
    print(f"  {y}   {(g.iloc[-1]/g.iloc[0]-1)*100:8.2f}%   {(g/g.cummax()-1).min()*100:8.2f}%")
