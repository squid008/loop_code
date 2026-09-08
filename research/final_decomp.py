# -*- coding: utf-8 -*-
"""
最终定量分解: 在「交集日期」内, 把 rq 与 qlib 的日截面差距拆成:
  总差 = 共同样本上的差(信号差+收益差) + rq单边样本的影响 + qlib单边样本的影响
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

    j = rq.set_index(['obid', 'date'])[['signal', 'fwd_t1_21']].join(
        qp.set_index(['obid', 'date'])[['F0', 'LABEL']], how='inner')
    j['rq_sig'] = j['signal'] == True
    j['q_sig'] = j['F0'] > 0.5
    j = j.dropna(subset=['signal', 'F0'])

    # ---- 交集日期 ----
    rd = set(j[j['rq_sig']].dropna(subset=['fwd_t1_21']).reset_index()['date'])
    qd = set(j[j['q_sig']].dropna(subset=['LABEL']).reset_index()['date'])
    inter = sorted(rd & qd)
    print(f"rq 有效日期 {len(rd)}  qlib 有效日期 {len(qd)}  交集 {len(inter)}")

    def dcross(sig_col, ret_col, dates=None):
        sub = j[j[sig_col]].dropna(subset=[ret_col])
        d = sub.groupby(level='date')[ret_col].mean()
        if dates is not None:
            d = d[d.index.isin(dates)]
        return d.mean() * 100

    # 各自完整样本(单边样本保留)
    rq_all = dcross('rq_sig', 'fwd_t1_21', inter)
    q_all = dcross('q_sig', 'LABEL', inter)
    print(f"\n【交集日期 {len(inter)} 天, 各自完整样本】")
    print(f"  rqalpha = {rq_all:+.4f}%      qlib = {q_all:+.4f}%      差 = {q_all-rq_all:+.4f} pp")

    # 双边样本集: 两边收益都有效
    bi = j.dropna(subset=['fwd_t1_21', 'LABEL'])
    def dcross_bi(sig_col, ret_col, frame):
        sub = frame[frame[sig_col]]
        d = sub.groupby(level='date')[ret_col].mean()
        return d[d.index.isin(inter)].mean() * 100

    rq_sig_bi = dcross_bi('rq_sig', 'fwd_t1_21', bi)
    q_sig_bi = dcross_bi('q_sig', 'LABEL', bi)
    rq_sig_bi_qret = dcross_bi('rq_sig', 'LABEL', bi)
    q_sig_bi_rqret = dcross_bi('q_sig', 'fwd_t1_21', bi)
    print(f"\n【仅双边样本(两边收益都有效)】")
    print(f"  rq信号+rq收益 = {rq_sig_bi:+.4f}%")
    print(f"  qlib信号+qlib收益 = {q_sig_bi:+.4f}%   差 = {q_sig_bi-rq_sig_bi:+.4f} pp")
    print(f"    ├ 仅换信号(qlib信号+rq收益) = {q_sig_bi_rqret:+.4f}%   "
          f"信号贡献 = {q_sig_bi_rqret-rq_sig_bi:+.4f} pp")
    print(f"    └ 仅换收益(rq信号+qlib收益) = {rq_sig_bi_qret:+.4f}%   "
          f"收益贡献 = {rq_sig_bi_qret-rq_sig_bi:+.4f} pp")

    print(f"\n【单边样本的影响】")
    print(f"  rq 单边(qlib无收益)样本使 rq 日截面变化 : {rq_all-rq_sig_bi:+.4f} pp")
    print(f"  qlib 单边(rq无收益)样本使 qlib 日截面变化: {q_all-q_sig_bi:+.4f} pp")

    print(f"\n================ 分解汇总 ================")
    print(f"  总差距(交集日期, 各自完整口径)      = {q_all-rq_all:+.4f} pp")
    print(f"  ├ 单边样本/日期覆盖差异贡献         = "
          f"{(q_all-q_sig_bi)-(rq_all-rq_sig_bi):+.4f} pp")
    print(f"  ├ 信号差异贡献(278浮点+16真实差)    = {q_sig_bi_rqret-rq_sig_bi:+.4f} pp")
    print(f"  └ 收益(价格)差异贡献                = {rq_sig_bi_qret-rq_sig_bi:+.4f} pp")

    # 单边样本都是哪些股票
    oneside = j[j['rq_sig'] & j['fwd_t1_21'].notna() & j['LABEL'].isna()]
    if len(oneside):
        print(f"\n【rq 单边样本 {len(oneside)} 个] 涉及股票:")
        os_df = oneside.reset_index()
        print(os_df.groupby('obid').size().sort_values(ascending=False).head(20).to_string())
        print(f"\n  涉及股票数: {os_df['obid'].nunique()}   "
              f"这些股票在 qlib 面板中是否存在:")
        qstocks = set(qp['obid'].unique())
        has = [o for o in os_df['obid'].unique() if o in qstocks]
        print(f"    在 qlib 面板中存在的: {len(has)} / {os_df['obid'].nunique()}")
        missing = [o for o in os_df['obid'].unique() if o not in qstocks]
        print(f"    不在 qlib 面板中的  : {len(missing)}  样例 {missing[:10]}")


if __name__ == '__main__':
    main()
