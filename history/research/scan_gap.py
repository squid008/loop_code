# -*- coding: utf-8 -*-
"""
全市场扫描: rqalpha 有正常交易(vol>0)但 qlib CLOSE 缺失的行。
这类"qlib 数据缺口"若与信号差异样本重叠, 则证明真实差来自 qlib 数据缺失。
"""
import sys
import io
import logging

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
logging.disable(logging.WARNING)

import numpy as np
import pandas as pd


def main():
    rq = pd.read_pickle(r'd:\rqalpha_demo\ai_test\_align_panel.pkl')
    qp = pd.read_pickle(r'd:\rqalpha_demo\ai_test\_panel_tam.pkl')
    qp['obid'] = qp.index.get_level_values(0).map(
        lambda q: q[2:] + ('.XSHG' if str(q).startswith('SH') else '.XSHE'))
    qp['date'] = qp.index.get_level_values(1).strftime('%Y%m%d').astype('int64')

    # qlib CLOSE 有效/缺失
    qok = qp.reset_index()[['obid', 'date', 'CLOSE']].copy()
    qok['q_has'] = qok['CLOSE'].notna()
    qok = qok.drop(columns=['CLOSE'])
    rq2 = rq[['obid', 'date', 'volume']].copy()
    rq2['rq_trade'] = rq2['volume'] > 0

    j = rq2.merge(qok, on=['obid', 'date'], how='inner')
    gap = j[j['rq_trade'] & ~j['q_has']]
    print(f"rq 有交易但 qlib CLOSE 缺失的行: {len(gap):,} / {len(j):,}  "
          f"({len(gap)/len(j)*100:.3f}%)")
    print(f"涉及股票数: {gap['obid'].nunique()}")
    # 按股票 top
    top = gap.groupby('obid').size().sort_values(ascending=False)
    print("\n缺口最集中的股票 top 30:")
    print(top.head(30).to_string())
    # 按年份
    print(f"\n按年份: \n{(gap['date']//10000).value_counts().sort_index().to_string()}")

    # 与信号差异样本重叠?
    rec = pd.read_pickle(r'd:\rqalpha_demo\ai_test\_rec.pkl')
    rec['obid'] = rec['obid']
    real = rec[rec['maxd'] >= 1e-3]
    # 该股票在其信号差异日附近 30 天内是否有数据缺口
    gset = gap.groupby('obid')['date'].apply(lambda s: set(s))
    n_overlap = 0
    for _, r in real.iterrows():
        obid, date = r['obid'], r['date']
        dates = gset.get(obid)
        if dates:
            near = [d for d in dates if abs(d - date) < 5000]
            if near:
                n_overlap += 1
    print(f"\n130 真差样本中, 该股票在差异日前后~13个月内有 qlib 数据缺口的: {n_overlap}")
    gap.save = None


if __name__ == '__main__':
    main()
