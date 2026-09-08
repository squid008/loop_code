# -*- coding: utf-8 -*-
"""找出 Round5 缺失的因子, 并检查 lag4 是否有值"""
import os
import sys
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from round5_fund import FundPanels

ALL = """ep_ttm ep_ttm_all bp sp_ttm cfp_ttm gp_mc ebit_ev roe_ttm roe_waa roa_ttm
roic_ttm gross_margin_ttm net_margin_ttm op_margin_ttm cost_ratio_neg eps_ttm gp_asset
rev_yoy np_yoy npttm_yoy revttm_yoy dednp_yoy eps_yoy cfottm_yoy roe_chg margin_chg
asset_growth_neg equity_growth cfo_np accrual_neg debt_asset_neg current_ratio
equity_liab asset_turnover ar_ratio_neg inv_asset_neg nonrecur_neg ln_assets
ln_equity ln_shares circ_ratio""".split()

df = pd.read_csv(os.path.join(HERE, 'round5_fund.csv'))
have = set(df['name'].unique())
miss = [x for x in ALL if x not in have]
print(f"应有 {len(ALL)}, 结果 {len(have)}, 缺失 {len(miss)}: {miss}")

with pd.HDFStore(os.path.join(HERE, 'panel.h5'), 'r') as st:
    dates = st['close'].index.values
FP = FundPanels(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fund_grid.pkl'), dates)
m = dates >= 20180101
for k in ['total_assets', 'equity_parent_company', 'np_parent_company_ownersTTM',
          'basic_earnings_per_share']:
    v0 = FP.daily(k)
    v4 = FP.daily(k, 4)
    print(f"{k:32s} lag0 有效 {np.isfinite(v0[m]).mean()*100:5.1f}%   "
          f"lag4 有效 {np.isfinite(v4[m]).mean()*100:5.1f}%")
    v0b = FP.daily(k)
    print(f"   再次取 lag0 有效 {np.isfinite(v0b[m]).mean()*100:5.1f}%  (与首次一致:"
          f" {np.array_equal(np.nan_to_num(v0), np.nan_to_num(v0b), equal_nan=False)})")
