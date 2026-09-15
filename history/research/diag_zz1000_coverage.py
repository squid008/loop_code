# -*- coding: utf-8 -*-
"""诊断: 中证1000 成分在 factor_snapshot 中的覆盖率, 及快照本身密度"""
import h5py
import numpy as np
import pandas as pd

SNAP = r'D:\rqalpha_demo\strategies\all01\factor_snapshot.pkl'
IDX = r'E:\rq\constituents\index\000852.XSHG.h5'

snap = pd.read_pickle(SNAP)
snap['date'] = snap['date'].astype(int)
dates = sorted(snap['date'].unique())
print(f"快照日期数: {len(dates)}  {dates[0]} ~ {dates[-1]}")

cnt = snap.groupby('date').size()
print(f"\n每年快照日期数 / 每日股票数:")
yr = pd.DataFrame({'n_day': cnt})
yr['year'] = [d // 10000 for d in yr.index]
g = yr.groupby('year').agg(快照天数=('n_day', 'size'), 平均股票数=('n_day', 'mean'))
print(g.round(0).to_string())

with h5py.File(IDX, 'r') as f:
    cd = f['change_dates'][:].astype(str)
    hist = []
    for d in cd:
        mem = set(x.decode() if isinstance(x, bytes) else str(x)
                  for x in f['components'][d][:])
        hist.append((int(d.replace('-', '')), mem))
hist.sort()


def members_at(d):
    m = None
    for eff, mem in hist:
        if eff <= d:
            m = mem
        else:
            break
    return m or set()


print(f"\n中证1000 成分批次: {len(hist)}  {hist[0][0]} ~ {hist[-1][0]}")

print(f"\n覆盖率检查(中证1000成分 在 当日快照中的数量):")
rows = []
for d in dates[::20] + [dates[-1]]:
    mem = members_at(d)
    sub = snap[snap['date'] == d]
    in_snap = sub[sub['obid'].isin(mem)]
    has_mkt = in_snap['mktcap'].notna().sum()
    rows.append({'date': d, '成分数': len(mem), '在快照中': len(in_snap),
                 '有市值': has_mkt, '覆盖率%': len(in_snap) / max(len(mem), 1) * 100})
print(pd.DataFrame(rows).round(1).to_string(index=False))

print(f"\n关键列缺失率(最新日):")
last = snap[snap['date'] == dates[-1]]
for c in ['mktcap', 'close', 'mom20', 'mom250_20', 'vol60', 'pb']:
    if c in last:
        print(f"  {c:12s} 缺失 {last[c].isna().mean()*100:5.1f}%")

# 检查: 中证1000 市值TOP10 的历史表现(用快照close, 仅看是否能复现rqalpha的量级)
print(f"\n用快照收盘价粗算: 中证1000市值TOP10 月度调仓 年收益(未复权, 仅供参照)")
close = snap.pivot(index='date', columns='obid', values='close').sort_index()
mkt = snap.pivot(index='date', columns='obid', values='mktcap').sort_index()
ds = pd.Series(sorted(close.index))
reb = ds.groupby(ds.astype(str).str[:6].values).first().tolist()
rets = []
for i in range(len(reb) - 1):
    d0, d1 = reb[i], reb[i + 1]
    mem = members_at(d0)
    row = mkt.loc[d0]
    row = row[row.index.isin(mem)].dropna()
    if len(row) < 10:
        rets.append(0.0); continue
    top = row.nlargest(10).index.tolist()
    r = (close.loc[d1, top] / close.loc[d0, top] - 1).dropna()
    rets.append(r.mean() if len(r) else 0.0)
nav = pd.Series(np.cumprod([1 + x for x in rets]), index=reb[:-1])
nav.index = pd.to_datetime(nav.index.astype(str), format='%Y%m%d')
for y, gg in nav.groupby(nav.index.year):
    print(f"  {y}: {(gg.iloc[-1]/gg.iloc[0]-1)*100:8.2f}%")
