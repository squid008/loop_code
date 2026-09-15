# -*- coding: utf-8 -*-
"""
快速扫描: 拥挤度动态调整三策略权重, 能否改善组合?
(后处理框架, 秒级; 相对比较有效, 最终仍用 rqalpha 全回测定稿)

规则: 拥挤度10年分位
  >= hi  -> 小市值加码 w_hi
  <= lo  -> 小市值减码, 红利防御 w_lo
  中间   -> 等权
"""
import os
import pickle
import itertools
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DEV = os.path.join(HERE, 'all01_dev')

PATHS = {
    'small': os.path.join(DEV, 'all01_roe_2014-10-01-2026-08-05.pkl'),
    'white': os.path.join(DEV, 'all02_2014-10-01-2026-08-05.pkl'),
    'div': os.path.join(DEV, 'all_div_lowvol_2014-10-01-2026-08-05.pkl'),
}


def netval(p):
    with open(p, 'rb') as f:
        r = pickle.load(f)
    df = r['portfolio']
    return (df['unit_net_value'] if 'unit_net_value' in df.columns
            else df['total_value'] / df['total_value'].iloc[0])


nvs = {k: netval(v) for k, v in PATHS.items()}
idx = None
for v in nvs.values():
    idx = v.index if idx is None else idx.intersection(v.index)
idx = idx.sort_values()
print(f"共同区间: {idx[0].date()} ~ {idx[-1].date()}  ({len(idx)} 日)")

tc = pd.read_csv(os.path.join(HERE, 'turnover_concentration.csv'))
tc['dt'] = pd.to_datetime(tc['date'].astype(str), format='%Y%m%d')
tc = tc.set_index('dt')['top10_pctile_10y'].reindex(
    tc['dt'].index.union(idx)).ffill().loc[idx]
tc = tc.shift(1)      # T-1 信号作用于 T 日

rets = pd.DataFrame({k: v.loc[idx].pct_change() for k, v in nvs.items()})
per = idx.to_period('W')     # 周频再平衡, 贴近 all01.py


def run(ws):
    """ws: DataFrame(每日 x 3)目标权重"""
    vals = np.asarray(ws.iloc[0].values, dtype=float)
    port = 1.0
    out = np.empty(len(idx))
    prev = None
    w = vals
    for i in range(len(idx)):
        p = per[i]
        if prev is not None and p != prev:
            w = np.asarray(ws.iloc[i].values, dtype=float)
            vals = port * w
        vals = vals * (1 + rets.iloc[i].fillna(0).values)
        port = vals.sum()
        out[i] = port
        prev = p
    combo = pd.Series(out, index=idx)
    return combo / combo.iloc[0]


def stats(nav, bench=None):
    r = nav.pct_change()
    years = (nav.index[-1] - nav.index[0]).days / 365.25
    ann = nav.iloc[-1] ** (1 / years) - 1
    dd = (nav / nav.cummax() - 1).min()
    sh = r.mean() / r.std() * np.sqrt(252) if r.std() > 0 else np.nan
    return ann, dd, sh, (ann / abs(dd) if dd < 0 else np.nan)


def make_ws(hi, lo, w_hi, w_lo):
    base = np.array([1 / 3, 1 / 3, 1 / 3])
    w = np.tile(base, (len(idx), 1))
    w[tc.values >= hi] = w_hi
    w[tc.values <= lo] = w_lo
    w[np.isnan(tc.values)] = base
    return pd.DataFrame(w, index=idx, columns=['small', 'white', 'div'])


rows = []
# 基准: 固定等权
eq = pd.DataFrame(np.tile([1 / 3, 1 / 3, 1 / 3], (len(idx), 1)),
                  index=idx, columns=['small', 'white', 'div'])
nav = run(eq)
a, d, s, c = stats(nav)
rows.append({'hi': '-', 'lo': '-', 'w_hi': '等权基准', 'w_lo': '-',
             '年化%': a * 100, '回撤%': d * 100, 'Sharpe': s, 'Calmar': c})

WH = {'A小盘50': [0.50, 0.25, 0.25], 'B小盘45': [0.45, 0.30, 0.25],
      'C小盘40': [0.40, 0.30, 0.30]}
WL = {'a小盘20红利50': [0.20, 0.30, 0.50], 'b小盘25红利45': [0.25, 0.30, 0.45],
      'c小盘25均衡': [0.25, 0.375, 0.375]}

for hi, lo, (kn, wh), (ln, wl) in itertools.product(
        [0.70, 0.80, 0.90], [0.20, 0.30], WH.items(), WL.items()):
    nav = run(make_ws(hi, lo, wh, wl))
    a, d, s, c = stats(nav)
    rows.append({'hi': hi, 'lo': lo, 'w_hi': kn, 'w_lo': ln,
                 '年化%': a * 100, '回撤%': d * 100, 'Sharpe': s, 'Calmar': c})

res = pd.DataFrame(rows)
print("\n" + "=" * 100)
print("拥挤度动态调权 参数扫描 (后处理, 周频再平衡)")
print("=" * 100)
print(res.sort_values('Sharpe', ascending=False).head(15).round(3).to_string(index=False))
print("\n按年化排序 Top10:")
print(res.sort_values('年化%', ascending=False).head(10).round(3).to_string(index=False))

print("\n" + "=" * 100)
print("[基准] 固定等权(无拥挤度调权, 无估值择时)")
nav0 = run(eq)
a0, d0, s0, c0 = stats(nav0)
print(f"  年化 {a0*100:.2f}%   回撤 {d0*100:.2f}%   Sharpe {s0:.3f}   Calmar {c0:.3f}")
best = res[res['w_hi'] != '等权基准'].sort_values('Sharpe', ascending=False).iloc[0]
print(f"\n[最优] hi={best['hi']} lo={best['lo']} {best['w_hi']} / {best['w_lo']}")
print(f"  年化 {best['年化%']:.2f}%   回撤 {best['回撤%']:.2f}%   "
      f"Sharpe {best['Sharpe']:.3f}   Calmar {best['Calmar']:.3f}")
print(f"  -> 相对等权: 年化 {best['年化%']-a0*100:+.2f}pp   "
      f"回撤 {best['回撤%']-d0*100:+.2f}pp   Sharpe {best['Sharpe']-s0:+.3f}")
print("=" * 100)
