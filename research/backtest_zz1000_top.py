# -*- coding: utf-8 -*-
"""
快速验证: 中证1000 成分中市值最大的 N 只, 历史表现如何?
(不含交易成本, 仅看方向; 有效再用 rqalpha 精算)
对比: 中证1000 / 沪深300 指数
"""
import os
import h5py
import numpy as np
import pandas as pd

SNAP = r'D:\rqalpha_demo\strategies\all01\factor_snapshot.pkl'
IDX = r'E:\rq\constituents\index\000852.XSHG.h5'
BUNDLE = r'E:\rq\bundle'

snap = pd.read_pickle(SNAP)
snap['date'] = snap['date'].astype(int)
close = snap.pivot(index='date', columns='obid', values='close').sort_index()
mkt = snap.pivot(index='date', columns='obid', values='mktcap').sort_index()
print(f"快照: {len(close)} 天 {close.index.min()} ~ {close.index.max()}  股票 {close.shape[1]}")


def load_idx_hist(path):
    with h5py.File(path, 'r') as f:
        cd = f['change_dates'][:].astype(str)
        out = []
        for d in cd:
            mem = set(x.decode() if isinstance(x, bytes) else str(x)
                      for x in f['components'][d][:])
            out.append((int(d.replace('-', '')), mem))
    out.sort()
    return out


hist = load_idx_hist(IDX)
print(f"中证1000 成分批次: {len(hist)}  {hist[0][0]} ~ {hist[-1][0]}")


def members_at(d):
    m = None
    for eff, mem in hist:
        if eff <= d:
            m = mem
        else:
            break
    return m or set()


def load_index_close(code):
    with h5py.File(os.path.join(BUNDLE, 'indexes.h5'), 'r') as f:
        d = f[code]
        dt = d['datetime'][:] // 1000000
        c = np.asarray(d['close'][:], dtype=float)
    return pd.Series(c, index=dt).sort_index()


bench = {'zz1000': load_index_close('000852.XSHG'),
         'hs300': load_index_close('000300.XSHG')}

# 月度调仓日
ds = pd.Series(sorted(close.index))
reb = ds.groupby(ds.astype(str).str[:6].values).first().tolist()


def run(N, use_mktcap=True, drop_new=True):
    rets = []
    dates_used = []
    for i in range(len(reb) - 1):
        d0, d1 = reb[i], reb[i + 1]
        mem = members_at(d0)
        row = mkt.loc[d0]
        row = row[row.index.isin(mem)].dropna()
        if len(row) < N:
            rets.append(0.0); dates_used.append(d0); continue
        top = row.nlargest(N).index.tolist()
        r = (close.loc[d1, top] / close.loc[d0, top] - 1)
        r = r.dropna()
        rets.append(r.mean() if len(r) else 0.0)
        dates_used.append(d0)
    nav = pd.Series(np.cumprod([1 + x for x in rets]), index=dates_used)
    return nav


def stats(nav):
    nav = nav.dropna()
    years = (pd.to_datetime(str(nav.index[-1]), format='%Y%m%d')
             - pd.to_datetime(str(nav.index[0]), format='%Y%m%d')).days / 365.25
    ann = nav.iloc[-1] ** (1 / years) - 1
    dd = (nav / nav.cummax() - 1).min()
    r = nav.pct_change().replace(0, np.nan).dropna()
    sh = r.mean() / r.std() * np.sqrt(12) if r.std() > 0 else np.nan
    return ann, dd, sh, ann / abs(dd) if dd < 0 else np.nan


print("\n" + "=" * 88)
print("月度调仓, 中证1000 成分按总市值降序取前 N 只 (等权, 未计成本)")
print("=" * 88)
rows = []
for N in [3, 5, 10, 20, 30, 50]:
    nav = run(N)
    a, d, s, c = stats(nav)
    rows.append({'选股': f'TOP{N}', '年化%': a * 100, '最大回撤%': d * 100,
                 'Sharpe': s, 'Calmar': c, '总收益%': (nav.iloc[-1] - 1) * 100})
# 基准
for nm, s in bench.items():
    s2 = s.reindex(sorted(close.index)).ffill()
    s2 = s2 / s2.iloc[0]
    a, d, sh, c = stats(s2)
    rows.append({'选股': nm, '年化%': a * 100, '最大回撤%': d * 100,
                 'Sharpe': sh, 'Calmar': c, '总收益%': (s2.iloc[-1] - 1) * 100})
res = pd.DataFrame(rows).set_index('选股')
print(res.round(2).to_string())

print("\n" + "=" * 88)
print("TOP10 分年度收益(%)  vs  中证1000")
print("=" * 88)
nav = run(10)
b1 = bench['zz1000'].reindex(sorted(close.index)).ffill()
b1 = b1 / b1.iloc[0]
yrs = []
for y in sorted(set(str(i)[:4] for i in nav.index)):
    n = nav[[str(i)[:4] == y for i in nav.index]]
    bb = b1[[str(i)[:4] == y for i in b1.index]]
    if len(n) == 0 or len(bb) == 0:
        continue
    yrs.append({'年份': y,
                'TOP10%': (n.iloc[-1] / n.iloc[0] - 1) * 100,
                '中证1000%': (bb.iloc[-1] / bb.iloc[0] - 1) * 100})
yd = pd.DataFrame(yrs).set_index('年份')
yd['超额%'] = yd['TOP10%'] - yd['中证1000%']
print(yd.round(2).to_string())
print(f"\n  TOP10 跑赢年份: {(yd['超额%'] > 0).sum()} / {len(yd)}")
