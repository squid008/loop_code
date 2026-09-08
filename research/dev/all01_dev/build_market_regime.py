# -*- coding: utf-8 -*-
"""
计算日频【市场状态/拥挤度-超跌】指标(用于择时, 无未来函数: 只用 T 日及之前的数据)。

指标(每日对全A股统计占比):
  below_ma60 : 收盘价 < 60日均线 的股票占比
  dd25       : 相对20日最高回撤 >25% 的股票占比(黄金坑/超跌股)
  dd40       : 相对20日最高回撤 >40% (深度坑)
  newlow60   : 收盘价创60日新低 的占比
  med_pb_pct : 全市场中位PB 的 250周(5年)滚动分位

用途:
  顶部(过热/拥挤): 超跌股占比极低 + 估值分位极高 -> 降仓
  底部(恐慌):      超跌股占比飙升 -> 加仓(用户公式: 纯度>20 后回落2天 = 见底)
"""
import os
import sys
import time
import numpy as np
import pandas as pd
import h5py

HERE = os.path.dirname(os.path.abspath(__file__))
STOCKS_H5 = r'E:\rq\bundle\stocks.h5'
OUT = os.path.join(HERE, 'market_regime.csv')
START, END = 20140101, 20260831

t0 = time.time()
print("读取行情 ...")
with h5py.File(STOCKS_H5, 'r') as f:
    obids = list(f.keys())
    base = (f['000001.XSHE']['datetime'][:] // 1000000).astype('int64')
    cal = base[(base >= START) & (base <= END)]
    pos = {d: i for i, d in enumerate(cal)}
    close = np.full((len(cal), len(obids)), np.nan)
    for j, ob in enumerate(obids):
        arr = f[ob][:]
        d = (arr['datetime'] // 1000000).astype('int64')
        m = (d >= START) & (d <= END)
        idx = np.array([pos.get(x, -1) for x in d[m]], dtype=np.int64)
        ok = idx >= 0
        close[idx[ok], j] = arr['close'][m][ok]
print(f"  {len(cal)} 天 x {len(obids)} 股, {time.time()-t0:.0f}s")

df = pd.DataFrame(close, index=pd.to_datetime(cal.astype(str)), columns=obids)

print("计算指标 ...")
ma60 = df.rolling(60, min_periods=20).mean()
max20 = df.rolling(20, min_periods=10).max()
min60 = df.rolling(60, min_periods=30).min()

with np.errstate(invalid='ignore', divide='ignore'):
    dd = df / max20 - 1.0

reg = pd.DataFrame({
    'below_ma60': (df < ma60).mean(axis=1),
    'dd25': (dd < -0.25).mean(axis=1),
    'dd40': (dd < -0.40).mean(axis=1),
    'newlow60': (df <= min60).mean(axis=1),
    'n_stocks': df.notna().sum(axis=1),
})
reg = (reg * 100).round(2)  # 转成百分比

# 估值分位(周频快照的中位PB)
snap_path = os.path.join(HERE, 'factor_snapshot.pkl')
if os.path.exists(snap_path):
    snap = pd.read_pickle(snap_path)
    med = snap.groupby('date')['pb'].median()
    med.index = pd.to_datetime(med.index.astype(str))
    pct = med.rolling(250, min_periods=125).rank(pct=True) * 100
    pct = pct.reindex(pct.index.union(reg.index)).ffill().loc[reg.index]
    reg['med_pb_pct'] = pct.round(1)

# 中证1000(小盘代表) 自身位置: 当前 / N日最高、N日最低
try:
    with h5py.File(r'E:\rq\bundle\indexes.h5', 'r') as f:
        arr = f['000852.XSHG'][:]
        d = (arr['datetime'] // 1000000).astype('int64')
        s = pd.Series(arr['close'].astype(float),
                      index=pd.to_datetime(d.astype(str)))
        s = s[(s.index.year >= START // 10000) & (s.index.year <= END // 10000)]
        s = s[~s.index.duplicated()]
        hi = s.rolling(250, min_periods=120).max()
        lo = s.rolling(250, min_periods=120).min()
        pos250 = (s / hi).reindex(reg.index).ffill()
        pos_lo = (s / lo).reindex(reg.index).ffill()
        reg['idx_pos250'] = (pos250 * 100).round(1)   # 距250日高点的位置%
        reg['idx_gain250'] = (pos_lo * 100).round(1)  # 相对250日低点涨幅%
except Exception as e:
    print(f"  [warn] 中证1000 位置计算失败: {e}")

reg.index.name = 'date'
reg.to_csv(OUT, encoding='utf-8-sig')
print(f"已保存: {OUT}   {time.time()-t0:.0f}s")

# ---------------- 关键时点检查 ----------------
keys = [
    ('2015-06-12', '2015股灾顶'), ('2015-07-08', '股灾急跌中'), ('2015-08-26', '股灾底'),
    ('2016-01-28', '熔断底'),
    ('2018-01-26', '2018顶'), ('2018-10-18', '2018底'), ('2018-12-28', '2018年末'),
    ('2020-03-23', '疫情底'), ('2021-02-10', '核心资产顶'),
    ('2022-04-26', '2022底'), ('2023-01-30', '2023初'),
    ('2024-02-05', '小盘股灾底'), ('2024-09-18', '2024-9底'),
    ('2025-01-06', '2025初'), ('2026-03-30', '近期'),
]
print("\n" + "=" * 96)
print("关键时点指标 (单位 %, 超跌股占比越高=越恐慌; med_pb_pct 越高=估值越贵)")
print("=" * 96)
print(f"  {'日期':<12}{'说明':<14}{'超跌>25%':>10}{'创新低':>9}{'PB分位':>8}{'指距高点':>10}{'指涨/低':>9}")
for d, tag in keys:
    if d in reg.index.strftime('%Y-%m-%d').values:
        r = reg.loc[d]
        pbf = f"{r.get('med_pb_pct', np.nan):>7.0f}%" if 'med_pb_pct' in reg and pd.notna(r.get('med_pb_pct')) else "      -"
        ip = f"{r.get('idx_pos250', np.nan):>9.1f}%" if 'idx_pos250' in reg and pd.notna(r.get('idx_pos250')) else "        -"
        ig = f"{r.get('idx_gain250', np.nan):>8.0f}%" if 'idx_gain250' in reg and pd.notna(r.get('idx_gain250')) else "       -"
        print(f"  {d:<12}{tag:<14}{r['dd25']:>9.1f}%{r['newlow60']:>8.1f}%{pbf}{ip}{ig}")
    else:
        print(f"  {d:<12}{tag:<14}(非交易日)")
