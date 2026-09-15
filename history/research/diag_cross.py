# -*- coding: utf-8 -*-
"""
逐步诊断: 为什么 decompose 的 rq 日截 0.3661% 与 check_daterange 的 -0.0241% 差这么多。
逐级收紧口径, 看每一级的影响:
  L0 rq 全量面板触发组
  L1 inner join(两边都有该 obid/date)
  L2 + 剔除收益NaN
  L3 + 只用交集日期
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
    rq['date'] = rq['date'].astype('int64')

    print("=== rq signal 列诊断 ===")
    s = rq['signal']
    print(f"  dtype={s.dtype}  NaN={int(s.isna().sum()):,}  True={int((s==True).sum()):,}  "
          f"总数={len(s):,}")
    if s.dtype != bool:
        print(f"  unique(前10)={s.unique()[:10]}")

    # 用显式 ==True 的口径(避免 NaN 被当 True)
    rq_t = rq[s == True]
    print(f"  用 (signal==True) 筛选: {len(rq_t):,} 行")

    def daily(df, ret):
        d = df.dropna(subset=[ret]).groupby('date')[ret].mean()
        return d.mean() * 100, len(d)

    v, n = daily(rq_t, 'fwd_t1_21')
    print(f"\nL0 rq全量(signal==True)          日截={v:+.4f}%  天数={n}")

    # L1 inner join
    j = rq.set_index(['obid', 'date'])[['signal', 'fwd_t1_21']].join(
        qp.set_index(['obid', 'date'])[['F0', 'LABEL']], how='inner')
    j = j[j['signal'] == True]
    v, n = daily(j, 'fwd_t1_21')
    print(f"L1 +inner join                  日截={v:+.4f}%  天数={n}   样本={len(j):,}")

    # L2 剔除收益NaN
    j2 = j.dropna(subset=['fwd_t1_21', 'LABEL'])
    v, n = daily(j2, 'fwd_t1_21')
    print(f"L2 +剔除收益NaN(fwd&LABEL)      日截={v:+.4f}%  天数={n}   样本={len(j2):,}")

    # L2a 只剔 fwd NaN
    j2a = j.dropna(subset=['fwd_t1_21'])
    v, n = daily(j2a, 'fwd_t1_21')
    print(f"L2a +只剔 fwd_t1_21 NaN        日截={v:+.4f}%  天数={n}   样本={len(j2a):,}")

    # L3 只用交集日期
    rd = set(j2a.dropna(subset=['fwd_t1_21'])['fwd_t1_21'].index) if False else \
        set(j2a.dropna(subset=['fwd_t1_21']).reset_index()['date'].unique())
    qt = qp[qp['F0'] > 0.5]
    qd = set(qt.dropna(subset=['LABEL'])['date'].unique())
    inter = rd & qd
    d = j2a.groupby(level='date')['fwd_t1_21'].mean()
    d = d[d.index.isin(inter)]
    print(f"L3 +只用交集日期({len(inter)}天)    日截={d.mean()*100:+.4f}%  天数={len(d)}")

    # qlib 侧同口径
    print("\n=== qlib 侧同口径 ===")
    qt2 = qp[qp['F0'] > 0.5].set_index(['obid', 'date'])[['LABEL']]
    v, n = daily(qt2, 'LABEL')
    print(f"  qlib 全量             日截={v:+.4f}%  天数={n}   样本={len(qt2):,}")
    jq = qt2.join(rq.set_index(['obid', 'date'])[['signal']], how='inner')
    v, n = daily(jq, 'LABEL')
    print(f"  +inner join           日截={v:+.4f}%  天数={n}   样本={len(jq):,}")
    jq2 = jq.dropna(subset=['LABEL'])
    v, n = daily(jq2, 'LABEL')
    print(f"  +剔除LABEL NaN        日截={v:+.4f}%  天数={n}   样本={len(jq2):,}")
    dq = jq2.groupby(level='date')['LABEL'].mean()
    dq = dq[dq.index.isin(inter)]
    print(f"  +交集日期             日截={dq.mean()*100:+.4f}%  天数={len(dq)}")
    print(f"\n  同口径(inner+剔NaN+交集)差距 = {(dq.mean()-d.mean())*100:+.4f} pp")


if __name__ == '__main__':
    main()
