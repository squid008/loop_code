# -*- coding: utf-8 -*-
"""
换仓频率扫描: FWD = 1 / 5 / 20 (日/周/月频)
代表因子覆盖各机制族, 成本按实际换手率计
"""
import os
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from factor_miner import (load_panel, prepare, run_round, set_fwd)
from round1 import build_factors as bf1
from round2 import build_factors as bf2

P = load_panel()
P = prepare(P)
close = P['close']
F = {}
F.update(bf1(P))
F.update(bf2(P))

REP = ['ln_mktcap', 'amt_log10', 'amt_log20', 'amt_std20', 'turnmc_std20',
       'rev_5d', 'rev_1d', 'mom20_rev', 'vol20', 'corr_cp20', 'mfxl10',
       'ix_amt_rev5', 'amt_log3', 'amt_cv20']
REP = [r for r in REP if r in F]
print(f"代表因子 {len(REP)} 个: {REP}\n")

summ = []
for fwd in [1, 5, 20]:
    set_fwd(fwd)
    res, _ = run_round({r: F[r] for r in REP}, close, tag=f'FWD{fwd}', verbose=False)
    if not len(res):
        continue
    res = res.copy()
    # factor_miner 返回英文列名, 此处映射回中文便于展示/筛选
    res = res.rename(columns={'ann_ex': '超额年化', 'calmar': 'Calmar'})
    res['fwd'] = fwd
    summ.append(res)
    top = res.sort_values('超额年化', ascending=False).iloc[0]
    print(f"== FWD={fwd} ==")
    cm = top['Calmar'] if pd.notna(top['Calmar']) else float('nan')
    print(f"  最好: {top['name']}  超额={top['超额年化']*100:+.2f}%  "
          f"IC={top['ic']:+.4f}  Calmar={cm:.2f}")
    print(f"  正超额: {(res['超额年化'] > 0).sum()}/{len(res)}")

allres = pd.concat(summ)
pv = allres.pivot_table(index='name', columns='fwd', values='超额年化') * 100
cv = allres.pivot_table(index='name', columns='fwd', values='Calmar')

print("\n" + "=" * 92)
print("超额年化% 按 因子 x 频率")
print(pv.round(2).to_string())
print("\nCalmar 按 因子 x 频率")
print(cv.round(3).to_string())
print("\n平均超额% by 频率:")
print(allres.groupby('fwd')['超额年化'].mean().mul(100).round(2).to_string())
print("\n正超额因子数 by 频率:")
print(allres.groupby('fwd').apply(lambda d: int((d['超额年化'] > 0).sum())).to_string())
