# -*- coding: utf-8 -*-
"""核查流通股本数据: PIT 字段覆盖率 + 量纲正确性 + 快照里的流通市值"""
import os
import glob
import numpy as np
import pandas as pd
import h5py

PIT_DIR = r'E:\rq\finance\pit'
SNAP = r'd:\rqalpha_demo\strategies\all01\factor_snapshot.pkl'
FIELDS = ['circulation_a_shares', 'total_a_shares', 'non_circulation_a_shares',
          'total_shares', 'paid_in_capital']
SAMPLE = ['600519.XSHG', '000001.XSHE', '000651.XSHE', '601398.XSHG', '300750.XSHE']

files = glob.glob(os.path.join(PIT_DIR, '*.h5'))
print(f"PIT 文件数 {len(files)}")

rows = []
for s in SAMPLE:
    p = os.path.join(PIT_DIR, s + '.h5')
    if not os.path.exists(p):
        continue
    with h5py.File(p, 'r') as f:
        have = set(f['fields'].keys())
        info = f['info_date'][:].astype(str)
        q = f['quarter'][:].astype(str)
        qs = sorted(set(q.tolist()))
        rec = {'obid': s, '记录数': len(info),
               'quarter范围': f"{qs[0]}~{qs[-1]}" if qs else '-'}
        for k in FIELDS:
            if k in have:
                v = f['fields'][k][:]
                rec[k] = v[np.isfinite(v)][-1] if np.isfinite(v).any() else np.nan
                rec[k + '_覆盖'] = f"{np.isfinite(v).mean()*100:.0f}%"
            else:
                rec[k] = np.nan
                rec[k + '_覆盖'] = '字段缺失'
        rows.append(rec)
df = pd.DataFrame(rows)
print("\n样例股票(最近一期值, 单位: 股):")
print(df.to_string(index=False))

# 全市场覆盖率(抽样 400 只)
np.random.seed(0)
sub = np.random.choice(files, 400, replace=False)
cnt = {k: 0 for k in FIELDS}
tot = 0
for p in sub:
    tot += 1
    with h5py.File(p, 'r') as f:
        have = set(f['fields'].keys())
        for k in FIELDS:
            if k in have:
                v = f['fields'][k][:]
                if np.isfinite(v).any():
                    cnt[k] += 1
print(f"\n全市场抽样 {tot} 只, 字段可得率(至少一期有值):")
for k in FIELDS:
    print(f"  {k:28s} {cnt[k]/tot*100:5.1f}%")

# 快照里的流通市值
if os.path.exists(SNAP):
    snap = pd.read_pickle(SNAP)
    print(f"\nfactor_snapshot.pkl: {len(snap):,} 行, {snap['date'].nunique()} 个调仓日")
    for c in ['mktcap', 'circ_mktcap', 'close']:
        if c in snap.columns:
            print(f"  {c:12s} 覆盖 {snap[c].notna().mean()*100:5.1f}%  "
                  f"中位 {snap[c].median():.4g}")
    if 'circ_mktcap' in snap.columns and 'mktcap' in snap.columns:
        r = (snap['circ_mktcap'] / snap['mktcap']).replace([np.inf, -np.inf], np.nan)
        print(f"  流通市值/总市值: 中位 {r.median():.3f}, "
              f"分位 p5={r.quantile(0.05):.3f} p25={r.quantile(0.25):.3f} "
              f"p75={r.quantile(0.75):.3f} p95={r.quantile(0.95):.3f}")
    # 逐年流通比例(看股改进程)
    if 'circ_mktcap' in snap.columns:
        snap['yr'] = snap['date'] // 10000
        g = snap.groupby('yr').apply(
            lambda d: (d['circ_mktcap'] / d['mktcap']).replace([np.inf, -np.inf], np.nan).median())
        print("\n  流通市值/总市值 中位数 逐年:")
        print(g.round(3).to_string())
