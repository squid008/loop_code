# -*- coding: utf-8 -*-
"""检查 PIT 字段语义: 000001.XSHE 累计/单季/TTM 量纲规律"""
import os, sys
sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)
import numpy as np
import h5py

fp = r'E:\rq\finance\pit\000001.XSHE.h5'
with h5py.File(fp, 'r') as f:
    info = np.array([x.decode() if isinstance(x, bytes) else str(x) for x in f['info_date'][:]])
    q = np.array([x.decode() if isinstance(x, bytes) else str(x) for x in f['quarter'][:]])
    ks = list(f['fields'].keys())
    print("记录数:", len(q), " 字段数:", len(ks))
    def qkey(x):
        return int(x[:4]) * 4 + int(x[-1])
    order = np.argsort([qkey(x) for x in q])
    info, q = info[order], q[order]
    seen = {}
    for i in range(len(q)):
        if q[i] >= '2021q1':
            seen[q[i]] = i
    picks = sorted(seen.values())
    print("\nquarter\tinfo_date")
    for i in picks:
        print(q[i], info[i])
    fields_want = ['operating_revenue', 'net_profit_parent_company',
                   'operating_profitTTM', 'gross_profit', 'net_profitTTM',
                   'operating_revenueTTM', 'total_assets', 'total_liabilities',
                   'equity_parent_company', 'current_assets', 'current_liabilities',
                   'cash_flow_from_operating_activities', 'net_operate_cashflowTTM']
    print("\n字段:")
    head = "".join(f"{q[i][2:]:>11}" for i in picks)
    print(f"{'field':<34}" + head)
    for w in fields_want:
        if w not in f['fields']:
            print(f"{w:<34} 缺失")
            continue
        v = f['fields'][w][:]
        row = []
        for i in picks:
            val = v[i]
            row.append(f"{val:>12.0f}" if np.isfinite(val) else f"{'NaN':>12}")
        print(f"{w:<34}" + "".join(row))
