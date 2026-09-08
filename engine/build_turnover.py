# -*- coding: utf-8 -*-
"""
构建"头部虹吸效应"指标面板
============================
从 bundle stocks.h5 读取全市场每日成交额, 计算:
  Top 5% / 10% / 20% 标的吸纳了全市场多少比例的成交额
再算各指标的滚动历史分位(近 N 年)

输出: turnover_concentration.csv
  date, n_stock, total_amount, top5, top10, top20,
  top10_pctile_3y, top10_pctile_10y
"""
import os
import time
import h5py
import numpy as np
import pandas as pd

BUNDLE = r'E:\rq\bundle'
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'turnover_concentration.csv')

t0 = time.time()
codes = None
dates, amounts = [], []

with h5py.File(os.path.join(BUNDLE, 'stocks.h5'), 'r') as f:
    codes = list(f.keys())
    print(f"股票数: {len(codes)}")
    for i, code in enumerate(codes):
        d = f[code]
        dt = d['datetime'][:] // 1000000          # 20050104000000 -> 20050104
        tt = d['total_turnover'][:].astype(np.float64)
        m = tt > 0                                 # 剔除停牌(成交额为0)
        dates.append(dt[m])
        amounts.append(tt[m])
        if (i + 1) % 1000 == 0:
            print(f"  读取 {i+1}/{len(codes)}  {time.time()-t0:.0f}s")

dt = np.concatenate(dates)
tt = np.concatenate(amounts)
print(f"总行数: {len(dt):,}  耗时 {time.time()-t0:.0f}s")

df = pd.DataFrame({'date': dt, 'amt': tt})
df = df.sort_values(['date', 'amt'], ascending=[True, False], kind='mergesort')
grp = df.groupby('date', sort=True)
df['rk'] = grp.cumcount()
df['n'] = grp['amt'].transform('size')
print(f"交易日: {df['date'].nunique()}  区间 {df['date'].min()} ~ {df['date'].max()}")


def top_share(p):
    """前 p 比例标的吸纳的成交额占比"""
    sub = df[df['rk'] < (df['n'] * p).astype(int).clip(lower=1)]
    return sub.groupby('date')['amt'].sum() / grp['amt'].sum()


res = pd.DataFrame({
    'n_stock': grp['amt'].size(),
    'total_amount': grp['amt'].sum(),
})
for p, name in [(0.05, 'top5'), (0.10, 'top10'), (0.20, 'top20'), (0.50, 'top50')]:
    res[name] = top_share(p)
res = res.reset_index()

# 历史分位(3年/10年滚动, 1年=243交易日)
for w, nm in [(243 * 3, '3y'), (243 * 10, '10y')]:
    res[f'top10_pctile_{nm}'] = (
        res['top10'].rolling(w, min_periods=min(w, 243)).rank(pct=True))

res.to_csv(OUT, index=False)
print(f"\n已保存: {OUT}")
print(f"总耗时: {time.time()-t0:.0f}s")

print("\n" + "=" * 70)
print("最近 15 个交易日")
tail = res.tail(15)[['date', 'n_stock', 'top5', 'top10', 'top20',
                     'top10_pctile_3y', 'top10_pctile_10y']].copy()
for c in ['top5', 'top10', 'top20']:
    tail[c] = (tail[c] * 100).round(2)
for c in ['top10_pctile_3y', 'top10_pctile_10y']:
    tail[c] = (tail[c] * 100).round(1)
print(tail.to_string(index=False))

print("\n" + "=" * 70)
print("2026 年内 Top10% 占比: 均值/最高/最低")
y26 = res[res['date'] // 10000 == 2026]
print(f"  均值 {y26['top10'].mean()*100:.2f}%  "
      f"最高 {y26['top10'].max()*100:.2f}%  最低 {y26['top10'].min()*100:.2f}%")
print(f"  最新日 {res['date'].iloc[-1]}: Top10% = {res['top10'].iloc[-1]*100:.2f}%  "
      f"10年分位 = {res['top10_pctile_10y'].iloc[-1]*100:.1f}%")
