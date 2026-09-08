# -*- coding: utf-8 -*-
"""
构建前复权价量面板 panel.h5
============================
数据: E:\rq\bundle\stocks.h5 (未复权OHLCV) + ex_cum_factor.h5 (累计除权因子)
前复权: price_adj(t) = price_raw(t) * F(t) / F(last)
        volume_adj(t) = volume_raw(t) * F(last) / F(t)   (保持成交额不变)
说明: rqalpha 回测用"动态前复权"(以回测当日为基准), 与本面板固定基准前复权
      在收益率层面完全等价(基准因子相除时抵消), 截面排序不受影响。
输出: panel.h5  宽表 index=date(int) columns=obid
      close/open/high/low/volume/turnover/limit_up/limit_down
"""
import os
import time
import h5py
import numpy as np
import pandas as pd

B = r'E:\rq\bundle'
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'panel.h5')
START = 20130101

t0 = time.time()
FIELDS = ['close', 'open', 'high', 'low', 'volume', 'turnover', 'limit_up', 'limit_down']
data = {k: {} for k in FIELDS}
codes_used = []

with h5py.File(os.path.join(B, 'stocks.h5'), 'r') as fs, \
        h5py.File(os.path.join(B, 'ex_cum_factor.h5'), 'r') as ff:
    codes = [c for c in fs.keys() if c in ff]
    print(f"股票数(有复权因子): {len(codes)}")
    for i, code in enumerate(codes):
        d = fs[code]
        dt = d['datetime'][:] // 1000000
        m = dt >= START
        if m.sum() < 20:
            continue
        dt = dt[m]

        fd = ff[code]
        starts = fd['start_date'][:] // 1000000
        facs = np.asarray(fd['ex_cum_factor'][:], dtype=np.float64)
        if len(facs) == 0:
            continue
        idx = np.clip(np.searchsorted(starts, dt, side='right') - 1, 0, len(facs) - 1)
        r = facs[idx] / facs[-1]              # 前复权系数 <= 1

        data['close'][code] = pd.Series(d['close'][:][m] * r, index=dt)
        data['open'][code] = pd.Series(d['open'][:][m] * r, index=dt)
        data['high'][code] = pd.Series(d['high'][:][m] * r, index=dt)
        data['low'][code] = pd.Series(d['low'][:][m] * r, index=dt)
        data['volume'][code] = pd.Series(d['volume'][:][m] / r, index=dt)
        data['turnover'][code] = pd.Series(d['total_turnover'][:][m], index=dt)
        data['limit_up'][code] = pd.Series(d['limit_up'][:][m] * r, index=dt)
        data['limit_down'][code] = pd.Series(d['limit_down'][:][m] * r, index=dt)
        codes_used.append(code)

        if (i + 1) % 1500 == 0:
            print(f"  {i+1}/{len(codes)}  {time.time()-t0:.0f}s")

print(f"有效股票: {len(codes_used)}   读取耗时 {time.time()-t0:.0f}s")

print("转宽表并写入 ...")
n = 0
with pd.HDFStore(OUT, 'w', complib='blosc', complevel=5) as store:
    for k in FIELDS:
        df = pd.DataFrame(data[k]).sort_index()
        df.index = df.index.astype('int64')
        df = df.astype('float32')
        store[k] = df
        n += 1
        print(f"  {k}: {df.shape[0]}日 x {df.shape[1]}股  "
              f"{df.memory_usage(deep=True).sum()/1e6:.0f}MB")
print(f"已存 {OUT}  总耗时 {time.time()-t0:.0f}s")

print("\n" + "=" * 70)
print("验证 000001.XSHE")
with h5py.File(os.path.join(B, 'stocks.h5'), 'r') as fs, \
        h5py.File(os.path.join(B, 'ex_cum_factor.h5'), 'r') as ff:
    d = fs['000001.XSHE']
    dt = d['datetime'][:] // 1000000
    c_raw = pd.Series(np.asarray(d['close'][:], dtype=float), index=dt)
    fd = ff['000001.XSHE']
    starts = fd['start_date'][:] // 1000000
    facs = np.asarray(fd['ex_cum_factor'][:], dtype=float)
    idx = np.clip(np.searchsorted(starts, dt, side='right') - 1, 0, len(facs) - 1)
    c_adj = c_raw * (facs[idx] / facs[-1])
with pd.HDFStore(OUT, 'r') as store:
    p_close = store['close']['000001.XSHE'].dropna()
chk = pd.DataFrame({'raw': c_raw, 'adj_calc': c_adj, 'adj_panel': p_close})
chk = chk.loc[chk.index >= 20130101]
print(chk.loc[chk.index.isin([20130104, 20150601, 20180102, 20210104, 20240102])].round(3).to_string())
print(f"\n  最新日: raw={c_raw.iloc[-1]:.3f} adj={c_adj.iloc[-1]:.3f} (应相等)")
print(f"  面板末值: {p_close.iloc[-1]:.3f}  面板首值: {p_close.iloc[0]:.3f}")
print(f"  区间涨幅(前复权, 真实回报): {(p_close.iloc[-1]/p_close.iloc[0]-1)*100:.1f}%")
print(f"  区间涨幅(未复权, 会低估):   {(c_raw.loc[20130101:].iloc[-1]/c_raw.loc[20130101:].iloc[0]-1)*100:.1f}%")
