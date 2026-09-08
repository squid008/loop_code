# -*- coding: utf-8 -*-
"""
130 真实差的最终分类。判断依据:
  A. 该股 qlib 数据缺口: qlib CLOSE 缺失 >= 3 天
  B. 长期停牌后复牌: rq 面板该股 date 有 >= 20 交易日的断档(在 T 之前 500 天内)
  C. 上市初期: T 距该股首行(qlib 面板) < 90 日历天
  D. 未复权除权跳变: T 当日 q/rq 涨跌幅>10% (涨跌停/除权)
  每样本可能多标签。
"""
import sys
import io
import logging

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
logging.disable(logging.WARNING)

import numpy as np
import pandas as pd


def main():
    rec = pd.read_pickle(r'd:\rqalpha_demo\ai_test\_rec.pkl')
    real = rec[rec['maxd'] >= 1e-3].copy()
    print(f"真实差样本: {len(real)}")

    rq = pd.read_pickle(r'd:\rqalpha_demo\ai_test\_align_panel.pkl')
    qp = pd.read_pickle(r'd:\rqalpha_demo\ai_test\_panel_tam.pkl')
    qp['obid'] = qp.index.get_level_values(0).map(
        lambda q: q[2:] + ('.XSHG' if str(q).startswith('SH') else '.XSHE'))
    qp['date'] = qp.index.get_level_values(1).strftime('%Y%m%d').astype('int64')

    # 每股票 qlib 数据: 该股日期集合 & CLOSE 缺失天数
    qd = qp.reset_index()[['obid', 'date', 'CLOSE']]
    q_has_date = qd[qd['CLOSE'].notna()].groupby('obid')['date'].apply(set)
    q_first = qd.groupby('obid')['date'].min()

    # rq 面板日期集合(按股票), 找 >=20 交易日断档
    rd = rq[['obid', 'date']].sort_values(['obid', 'date'])
    susp_stocks = set()   # 有过长停牌的股票
    for obid, g in rd.groupby('obid'):
        dts = g['date'].values
        if len(dts) > 2:
            # 交易日近似间隔 (<=8 为连续)
            gaps = np.diff(dts)
            if (gaps >= 20).sum() > 0:
                susp_stocks.add(obid)

    def near_susp(obid, date):
        if obid not in susp_stocks:
            return False
        dts = sorted(rd[rd['obid'] == obid]['date'].values)
        idx = np.searchsorted(dts, date)
        for i in range(max(0, idx - 250), min(len(dts), idx + 60)):
            d = dts[i]
            if abs(d - date) < 2000:   # 前后约5个月
                return True
        return False

    tags = []
    for _, r in real.iterrows():
        obid, date = r['obid'], r['date']
        t = []
        # A qlib 数据缺口
        hd = q_has_date.get(obid)
        qmiss = 0
        if hd is not None and obid in q_first:
            dts = sorted(hd)
            if len(dts) > 30:
                # 估算缺口: 用交易日历近似
                all_dates = set(pd.bdate_range('2021-01-01', '2026-08-31').strftime('%Y%m%d').astype(int))
                qmiss = len([d for d in all_dates if d not in hd])
        if qmiss >= 3:
            t.append('QLIB_GAP')
        # B 长期停牌
        if near_susp(obid, date):
            t.append('SUSPEND')
        # C 上市初期
        qf = q_first.get(obid)
        if qf is not None and (date - qf) < 90:
            t.append('NEW')
        if not t:
            t.append('NO_TAG')
        tags.append('+'.join(t))

    real['cls'] = tags
    print("\n分类分布:")
    for c, g in real.groupby('cls'):
        print(f"  {c:<40} {len(g):>4}")
    print(f"\n  QLIB_GAP 样本: {int(real['cls'].str.contains('QLIB_GAP').sum())}")
    print(f"  SUSPEND  样本: {int(real['cls'].str.contains('SUSPEND').sum())}")
    print(f"  NEW      样本: {int(real['cls'].str.contains('NEW').sum())}")
    print(f"  NO_TAG   样本: {int(real['cls'].str.contains('NO_TAG').sum())}")

    nt = real[real['cls'] == 'NO_TAG'].sort_values('maxd', ascending=False)
    print(f"\n=== NO_TAG 全部 {len(nt)} 个 ===")
    for _, r in nt.iterrows():
        print(f"  {r['obid']}  {r['date']}  maxd={r['maxd']:.4f}@{r['worst']}")


if __name__ == '__main__':
    main()
