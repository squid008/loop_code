# -*- coding: utf-8 -*-
"""
构建可交易股票池掩码 universe.h5 (date x stock, bool)
过滤: 非ST / 非停牌 / 上市>=250交易日 / 20日日均成交额>=1000万 / 当日非涨跌停

数据结构(已核实):
  st_stock_days.h5 : key=股票代码, value=ST日期数组(YYYYMMDD, float64)
  suspended_days.h5: key=股票代码, value=停牌日期数组(YYYYMMDD, int32)
  instruments.json : listed_date='1991-04-03', de_listed_date='0000-00-00'表示未退市
"""
import os
import time
import json
import h5py
import numpy as np
import pandas as pd

B = r'E:\rq\bundle'
HERE = os.path.dirname(os.path.abspath(__file__))
PANEL = os.path.join(HERE, 'panel.h5')
OUT = os.path.join(HERE, 'universe.h5')
MIN_AMT = 1e7
MIN_AGE = 250

t0 = time.time()

with pd.HDFStore(PANEL, 'r') as st:
    close = st['close']
    turnover = st['turnover'].astype('float64')
    limit_up = st['limit_up'].astype('float64')
    limit_down = st['limit_down'].astype('float64')
dates = close.index.values
codes = list(close.columns)
n_d, n_c = len(dates), len(codes)
print(f"面板: {n_d}日 x {n_c}股   {dates[0]}~{dates[-1]}")

# 日期 -> 行号, 便于快速定位
pos_of_date = pd.Series(np.arange(n_d), index=dates)
code_pos = {c: i for i, c in enumerate(codes)}

# ---- ST / 停牌 (key=code, value=dates) ----
def load_flag(fn):
    mat = np.zeros((n_d, n_c), dtype=bool)
    with h5py.File(os.path.join(B, fn), 'r') as f:
        for code in f.keys():
            j = code_pos.get(code)
            if j is None:
                continue
            v = np.asarray(f[code][:])
            if len(v) == 0:
                continue
            ds = v.astype('int64')
            ds = ds[(ds >= dates[0]) & (ds <= dates[-1])]
            if len(ds) == 0:
                continue
            rows = pos_of_date.reindex(ds).values
            rows = rows[np.isfinite(rows)].astype('int64')
            mat[rows, j] = True
    return pd.DataFrame(mat, index=dates, columns=codes)


print("[1] ST / 停牌")
st_mask = load_flag('st_stock_days.h5')
sus_mask = load_flag('suspended_days.h5')
print(f"  ST占比 {st_mask.values.mean()*100:.2f}%   停牌占比 {sus_mask.values.mean()*100:.2f}%")

# ---- 上市 / 退市 ----
print("[2] 上市退市")
with open(os.path.join(B, 'instruments.json'), 'r', encoding='utf-8') as f:
    ins = pd.DataFrame(json.load(f))
ins = ins[ins['type'] == 'CS'].set_index('order_book_id')
li = ins['listed_date'].reindex(codes)
di = ins['de_listed_date'].reindex(codes)


def to_yyyymmdd(s, default):
    s = s.astype(str).replace({'0000-00-00': None, 'nan': None, 'NaT': None})
    d = pd.to_datetime(s, errors='coerce')
    out = d.dt.strftime('%Y%m%d')
    out = out.fillna(str(default)).astype('int64')
    return out.values


listed_i = to_yyyymmdd(li, 19000101)
delist_i = to_yyyymmdd(di, 20991231)
print(f"  上市日样例: {listed_i[:3]}  退市日样例: {delist_i[:3]}")

pos_listed = np.searchsorted(dates, listed_i, side='right')     # 上市后第一个交易日位置
age = np.arange(n_d)[:, None] - pos_listed[None, :]
ok_age = pd.DataFrame(age >= MIN_AGE, index=dates, columns=codes)

D = np.tile(dates.reshape(-1, 1), (1, n_c))
ok_alive = pd.DataFrame((D <= delist_i[None, :]) & close.notna().values,
                        index=dates, columns=codes)
print(f"  上市>={MIN_AGE}日: {ok_age.values.mean()*100:.1f}%   存续: {ok_alive.values.mean()*100:.1f}%")

# ---- 流动性 ----
print("[3] 流动性 20日日均成交额 >= 1000万")
amt20 = turnover.rolling(20, min_periods=10).mean()
ok_amt = (amt20 >= MIN_AMT).fillna(False)
print(f"  通过: {ok_amt.values.mean()*100:.1f}%")

# ---- 当日可成交 ----
ok_lim = ((close < limit_up - 1e-6) & (close > limit_down + 1e-6)).fillna(False)

universe = (ok_age & ok_alive & (~st_mask) & (~sus_mask) & ok_amt & ok_lim).fillna(False)
cnt = universe.sum(axis=1)
print(f"\n[4] 可交易池占比 {universe.values.mean()*100:.1f}%")
print(f"  每日股票数 均值{cnt.mean():.0f} 最小{cnt.min():.0f} 最大{cnt.max():.0f}")
print(cnt.groupby(cnt.index // 10000).mean().round(0).to_string())

with pd.HDFStore(OUT, 'w', complib='blosc', complevel=5) as st:
    st['universe'] = universe
    st['st'] = st_mask
    st['suspended'] = sus_mask
print(f"\n已存 {OUT}   耗时 {time.time()-t0:.0f}s")
