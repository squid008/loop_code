# -*- coding: utf-8 -*-
"""
拥挤度(头部虹吸)指标有效性检验
================================
问题: Top10%成交额占比的历史分位, 对未来收益有没有预测力?
     是"越高越危险(该减仓)" 还是 "越高越强势(该追)"?
     对中证1000 和 沪深300 的结论是否不同(决定能否做大小盘轮动)?
"""
import os
import h5py
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
BUNDLE = r'E:\rq\bundle'

tc = pd.read_csv(os.path.join(HERE, 'turnover_concentration.csv'))
tc['date'] = tc['date'].astype(int)
print(f"集中度数据: {len(tc)} 行  {tc['date'].min()} ~ {tc['date'].max()}")


def load_index(code):
    with h5py.File(os.path.join(BUNDLE, 'indexes.h5'), 'r') as f:
        d = f[code]
        dt = d['datetime'][:] // 1000000
        close = np.asarray(d['close'][:], dtype=float)
    s = pd.Series(close, index=pd.Index(dt, name='date')).sort_index()
    return s[~s.index.duplicated()]


idx = {}
for code, name in [('000852.XSHG', 'zz1000'), ('000300.XSHG', 'hs300'),
                   ('000905.XSHG', 'zz500')]:
    try:
        idx[name] = load_index(code)
        print(f"  {name}: {len(idx[name])} 日  {idx[name].index.min()}~{idx[name].index.max()}")
    except KeyError:
        print(f"  {name}({code}) 缺失")

tc = tc.set_index('date')
# 未来 N 日收益
for h in [20, 60, 120]:
    for name, s in idx.items():
        fwd = (s.shift(-h) / s - 1)
        tc[f'fwd{h}_{name}'] = fwd.reindex(tc.index).values

tc = tc.reset_index()

# 只看指标有值的区间(需要10年分位, 故从2015起)
d = tc.dropna(subset=['top10_pctile_10y']).copy()
d = d[d['date'] >= 20150101]
print(f"\n有效样本: {len(d)} 日  {d['date'].min()} ~ {d['date'].max()}")

print("\n" + "=" * 96)
print("[1] 按 拥挤度10年分位 分5组, 各组之后的表现(均值%)")
print("=" * 96)
d['grp'] = pd.cut(d['top10_pctile_10y'], [0, .2, .4, .6, .8, 1.0],
                  labels=['Q1最低0-20%', 'Q2 20-40%', 'Q3 40-60%', 'Q4 60-80%', 'Q5最高80-100%'])
cols = [c for c in d.columns if c.startswith('fwd')]
g = d.groupby('grp', observed=True)[cols].mean() * 100
g.insert(0, '天数', d.groupby('grp', observed=True).size())
g.insert(1, 'Top10均值%', d.groupby('grp', observed=True)['top10'].mean() * 100)
print(g.round(2).to_string())

d['spread'] = d['fwd60_zz1000'] - d['fwd60_hs300']

print("\n" + "=" * 96)
print("[2] 极端分组对比: 高拥挤(分位>=95%) vs 低拥挤(分位<=20%)")
print("=" * 96)
hi = d[d['top10_pctile_10y'] >= 0.95]
lo = d[d['top10_pctile_10y'] <= 0.20]
mid = d[(d['top10_pctile_10y'] > 0.4) & (d['top10_pctile_10y'] < 0.6)]
rows = []
for nm, sub in [('高拥挤 >=95%', hi), ('低拥挤 <=20%', lo), ('中性 40-60%', mid)]:
    r = {'分组': nm, '天数': len(sub)}
    for c in cols:
        r[c] = sub[c].mean() * 100
        r[c + '_胜率'] = (sub[c] > 0).mean() * 100
    rows.append(r)
res = pd.DataFrame(rows).set_index('分组')
print(res.round(2).to_string())

print("\n" + "=" * 96)
print("[3] 大小盘价差: 拥挤度能否指导 中证1000 vs 沪深300 轮动")
print("=" * 96)
if d['spread'].notna().any():
    print("  未来60日 (中证1000 - 沪深300) 超额, 按拥挤度分组:")
    s = d.groupby('grp', observed=True).agg(
        天数=('spread', 'size'),
        价差均值=('spread', lambda x: x.mean() * 100),
        中位=('spread', lambda x: x.median() * 100),
        小盘跑赢概率=('spread', lambda x: (x > 0).mean() * 100))
    print(s.round(2).to_string())
    print("\n  极端对比(未来60日小盘跑赢大盘的概率):")
    for nm, sub in [('高拥挤>=95%', hi), ('低拥挤<=20%', lo)]:
        print(f"    {nm}: {(sub['spread'] > 0).mean()*100:5.1f}%   价差均值 {sub['spread'].mean()*100:+.2f}%")

print("\n" + "=" * 96)
print("[4] 拥挤度 与 同期/下期 中证1000 收益的相关系数")
print("=" * 96)
for h in [20, 60, 120]:
    c = f'fwd{h}_zz1000'
    if c in d:
        print(f"  未来{h:3d}日:  pearson {d['top10_pctile_10y'].corr(d[c]):+.3f}   "
              f"spearman {d['top10_pctile_10y'].corr(d[c], method='spearman'):+.3f}")

print("\n" + "=" * 96)
print("[5] 历史几次极端高拥挤(分位>=99%)时点及之后表现")
print("=" * 96)
ex = d[d['top10_pctile_10y'] >= 0.99].copy()
if len(ex):
    ex['dt'] = pd.to_datetime(ex['date'].astype(str), format='%Y%m%d')
    show = ex[['dt', 'top10', 'top10_pctile_10y', 'fwd20_zz1000', 'fwd60_zz1000',
               'fwd60_hs300']].copy()
    show['top10'] = (show['top10'] * 100).round(2)
    for c in ['fwd20_zz1000', 'fwd60_zz1000', 'fwd60_hs300']:
        show[c] = (show[c] * 100).round(2)
    # 同一波段只显示首次触发
    show = show[show['dt'].diff().dt.days.fillna(999) > 30]
    print(show.to_string(index=False))
else:
    print("  无样本")

print("\n" + "=" * 96)
print("[6] 分年度稳定性: 高拥挤(>=95%)日 与 低拥挤(<=20%)日 之后60日中证1000表现")
print("=" * 96)
d['year'] = d['date'] // 10000
rows = []
for y, sub in d.groupby('year'):
    h = sub[sub['top10_pctile_10y'] >= 0.95]
    l = sub[sub['top10_pctile_10y'] <= 0.20]
    if len(h) == 0 and len(l) == 0:
        continue
    rows.append({
        '年份': y,
        '高拥挤天数': len(h),
        '高拥挤后60日%': h['fwd60_zz1000'].mean() * 100 if len(h) else np.nan,
        '低拥挤天数': len(l),
        '低拥挤后60日%': l['fwd60_zz1000'].mean() * 100 if len(l) else np.nan,
        '全年zz1000涨幅%': sub['fwd60_zz1000'].mean() * 100,
    })
yr = pd.DataFrame(rows).set_index('年份')
yr['高-低价差'] = yr['高拥挤后60日%'] - yr['低拥挤后60日%']
print(yr.round(2).to_string())
print(f"\n  高拥挤占优年份: {(yr['高-低价差'] > 0).sum()} / {yr['高-低价差'].notna().sum()}")
