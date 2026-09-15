# -*- coding: utf-8 -*-
"""抽查候选财报字段在 PIT 里的覆盖率与量纲(抽样股票 + 2014后)"""
import os, sys, glob, random
sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)
import numpy as np
import pandas as pd
import h5py

PIT = r'E:\rq\finance\pit'

CAND = [
    'gross_profit', 'gross_profitTTM', 'operating_profitTTM', 'total_profitTTM',
    'ebitTTM', 'ebitda', 'net_profit_parent_company', 'net_profitTTM',
    'np_parent_company_ownersTTM', 'adjusted_net_profit',
    'net_profit_deduct_non_recurring_pnl', 'non_recurring_pnl',
    'net_operate_cashflowTTM', 'cash_flow_from_operating_activities',
    'operating_revenue', 'operating_revenueTTM', 'operating_costTTM',
    'return_on_equity_weighted_average', 'return_on_assets',
    'basic_earnings_per_share', 'total_assets', 'total_liabilities',
    'equity_parent_company', 'total_equity', 'current_assets',
    'current_liabilities', 'inventory', 'net_accts_receivable',
    'total_shares', 'circulation_a_shares', 'assets_liabilities_ratio',
]

files = sorted(glob.glob(os.path.join(PIT, '*.h5')))
random.seed(1)
pick = [files[0]] + random.sample(files, 39)

cnt = {c: 0 for c in CAND}
vmin = {c: None for c in CAND}
vmax = {c: None for c in CAND}
q_cov = {c: 0 for c in CAND}
for fp in pick:
    with h5py.File(fp, 'r') as f:
        fk = set(f['fields'].keys())
        for c in CAND:
            if c not in fk:
                continue
            v = f['fields'][c][:]
            if v.dtype.kind in 'OSU':
                continue
            v = np.asarray(v, dtype=np.float64)
            ok = ~np.isnan(v)
            if not ok.any():
                continue
            cnt[c] += 1
            arr = np.abs(v[ok])
            nz = arr[arr > 0]
            if len(nz) > 0:
                vmin[c] = nz.min() if vmin[c] is None else min(vmin[c], nz.min())
                vmax[c] = nz.max() if vmax[c] is None else max(vmax[c], nz.max())
            q = np.array([x.decode() if isinstance(x, bytes) else str(x) for x in f['quarter'][:]])
            q_cov[c] = max(q_cov[c], len(set(q[ok])))

print("字段\t抽样覆盖(40)\tquarter覆盖\tabs值范围")
for c in CAND:
    print(f"{c:<42}{cnt[c]:>4}/40\t{q_cov[c]:>4}\t{vmin[c]} ~ {vmax[c]}")
