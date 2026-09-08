# -*- coding: utf-8 -*-
"""
把 rq 与 qlib 的日截面差距做定量分解:
  总差 = (qlib信号 + qlib收益) - (rq信号 + rq收益)
  信号贡献 = (qlib信号 + rq收益) - (rq信号 + rq收益)   [固定收益, 只换信号]
  收益贡献 = (rq信号 + qlib收益) - (rq信号 + rq收益)   [固定信号, 只换收益]
同时统计 278 个"浮点边界"样本到最近阈值的距离, 验证它们是否真的在精度量级。
"""
import sys
import io
import logging

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
logging.disable(logging.WARNING)

import numpy as np
import pandas as pd

THR = {'long': [12.0, 8.0, 10.0], 'mid': [8.0, 7.0], 'short': [7.2, 5.0, 15.0, 1.0]}


def main():
    rq = pd.read_pickle(r'd:\rqalpha_demo\ai_test\_align_panel.pkl')
    qp = pd.read_pickle(r'd:\rqalpha_demo\ai_test\_panel_tam.pkl')
    qp['obid'] = qp.index.get_level_values(0).map(
        lambda q: q[2:] + ('.XSHG' if str(q).startswith('SH') else '.XSHE'))
    qp['date'] = qp.index.get_level_values(1).strftime('%Y%m%d').astype('int64')
    rq['date'] = rq['date'].astype('int64')

    j = rq.set_index(['obid', 'date'])[['signal', 'fwd_t1_21', 'long', 'short', 'mid']].join(
        qp.set_index(['obid', 'date'])[['F0', 'LABEL']], how='inner')
    j = j.dropna(subset=['signal', 'F0'])
    j['q_sig'] = j['F0'] > 0.5
    j['rq_sig'] = j['signal'].astype(bool)
    # 收益两边都有才算
    j = j.dropna(subset=['fwd_t1_21', 'LABEL'])
    print(f"对齐样本 {len(j):,} 行")

    def cross(sig_col, ret_col, tag):
        sub = j[j[sig_col]]
        d = sub.groupby(level='date')[ret_col].mean()
        n = int((j[sig_col]).sum())
        print(f"  {tag:<26} 触发样本={n:>7,}  日截={d.mean()*100:>8.4f}%  天数={len(d)}")
        return d.mean() * 100

    print("\n================= 日截面四组合分解 (纯信号口径, 不剔除涨跌停) =================")
    a = cross('rq_sig', 'fwd_t1_21', 'rq信号 + rq收益')
    b = cross('q_sig', 'LABEL', 'qlib信号 + qlib收益')
    c = cross('q_sig', 'fwd_t1_21', 'qlib信号 + rq收益')
    d = cross('rq_sig', 'LABEL', 'rq信号 + qlib收益')

    print("\n" + "-" * 80)
    print(f"  总差距            = {(b-a):+.4f} pp")
    print(f"  仅换信号的贡献    = {(c-a):+.4f} pp   (占 {abs(c-a)/max(abs(b-a),1e-9)*100:.1f}%)")
    print(f"  仅换收益的贡献    = {(d-a):+.4f} pp   (占 {abs(d-a)/max(abs(b-a),1e-9)*100:.1f}%)")
    print(f"  交互项(残余)      = {(b-a)-(c-a)-(d-a):+.4f} pp")

    # ---------- 收益本身的一致性 ----------
    dd = (j['fwd_t1_21'] - j['LABEL']).abs()
    print(f"\n================= 收益(价格)一致性 =================")
    print(f"  两边收益完全一致的样本: {int((dd<1e-9).sum()):,} / {len(j):,}  "
          f"({(dd<1e-9).mean()*100:.2f}%)")
    print(f"  |收益差| > 1e-6 : {int((dd>1e-6).sum()):,}")
    print(f"  |收益差| > 1e-4 : {int((dd>1e-4).sum()):,}")
    print(f"  |收益差| > 0.01 : {int((dd>0.01).sum()):,}")
    print(f"  收益差 最大={dd.max():.6f}  平均={dd.mean():.9f}")
    bad = j[dd > 1e-4]
    if len(bad):
        print(f"\n  收益差 >1e-4 的样本示例 (前 10):")
        print(bad[['fwd_t1_21', 'LABEL', 'rq_sig', 'q_sig']].head(10).assign(
            diff=dd[dd > 1e-4]).to_string(float_format=lambda x: f"{x:12.6f}"))

    # ---------- 278 个浮点边界样本: 到最近阈值的距离 ----------
    rec = pd.read_pickle(r'd:\rqalpha_demo\ai_test\_rec.pkl')
    fl = rec[rec['maxd'] < 1e-3]
    print(f"\n================= 浮点边界样本({len(fl)}) 到最近阈值的距离 =================")
    j2 = j.reset_index()
    m = j2.merge(fl[['obid', 'date']], on=['obid', 'date'], how='inner')
    if len(m):
        dists = []
        for _, r in m.iterrows():
            ds = []
            for c in ['long', 'mid', 'short']:
                v = r[c]
                if pd.notna(v):
                    ds += [abs(v - t) for t in THR[c]]
            for c in ['long', 'mid', 'short']:
                v = r.get(c + '_p1')
                if pd.notna(v):
                    ds += [abs(v - t) for t in THR[c]]
            dists.append(min(ds) if ds else np.nan)
        m['dist'] = dists
        print(f"  距离 < 1e-6      : {int((m['dist']<1e-6).sum())}")
        print(f"  距离 < 1e-4      : {int((m['dist']<1e-4).sum())}")
        print(f"  距离 < 0.01      : {int((m['dist']<0.01).sum())}")
        print(f"  距离 >= 0.01     : {int((m['dist']>=0.01).sum())}")
        print(f"  距离 中位={m['dist'].median():.8f}  最大={m['dist'].max():.6f}")
        print(f"\n  距离最大的 15 个 (这些不是'精度翻转', 另有原因):")
        print(m.nlargest(15, 'dist')[['obid', 'date', 'dist', 'maxd']].to_string(index=False))


if __name__ == '__main__':
    main()
