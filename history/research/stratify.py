# -*- coding: utf-8 -*-
"""
按「当日触发信号数」分层, 对比 rqalpha 与 qlib 的当日收益。
若差异集中在信号数很少的交易日(薄日), 则证明 0.30pp 的分歧来自
少量临界样本翻转被日截面等权放大, 而非算法/数据问题。
"""
import sys
import io
import os

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, r'D:\quant\qlib_code\backend')

try:
    from app.factors.ops_ext import ensure_ops_registered
    ensure_ops_registered(force=True)
except Exception as _e:
    sys.stdout.write(f"[warn] {_e}\n")

PANEL = r'd:\rqalpha_demo\ai_test\_align_panel.pkl'
START, END = '2021-01-01', '2026-08-31'

BASE = """A:=MA(-100*(HHV(HIGH,34)-CLOSE)/(HHV(HIGH,34)-LLV(LOW,34)),19);
B:=-100*(HHV(HIGH,14)-CLOSE)/(HHV(HIGH,14)-LLV(LOW,14));
d:=EMA(-100*(HHV(HIGH,34)-CLOSE)/(HHV(HIGH,34)-LLV(LOW,34)),4);
长期线:=A+100;
短期线:=B+100;
中期线:=d+100;
底:=(长期线<12 and 中期线<8 and (短期线<7.2 or ref(短期线,1)<5) and (中期线>ref(中期线,1) or 短期线>ref(短期线,1)))
or (长期线<8 and 中期线<7 and 短期线<15 and 短期线>ref(短期线,1)) or (长期线<10 and 中期线<7 and 短期线<1);
{OUT}
"""


def to_qcode(obid):
    code, exch = str(obid).split('.')
    return ('SH' if exch == 'XSHG' else 'SZ') + code


def to_rqcode(q):
    q = str(q)
    return q[2:] + ('.XSHG' if q.startswith('SH') else '.XSHE')


def main():
    import numpy as np
    import pandas as pd
    import qlib
    qlib.init(provider_uri=r'D:\quant\qlib_code\data\cn_data', region='cn')
    from qlib.data import D
    from app.factors.parser import translate_formula
    from app.engine.adjust import adjust_expr
    from app.engine.feature_cache import _sr_wrap_expr

    out = sys.stdout
    pan = pd.read_pickle(PANEL)
    codes = sorted(set(pan['obid']))
    qcodes = [to_qcode(o) for o in codes]

    t = translate_formula(BASE.format(OUT='信号:ref(底,1)=1 and 底=0;'))
    e = _sr_wrap_expr(adjust_expr(t.expression, 'none'))
    lab = adjust_expr("Ref($close, -21)/Ref($close, -1) - 1", 'none')

    print(f"计算 qlib 侧 ({len(qcodes)} 只) ...", file=out)
    df = D.features(qcodes, [e, lab], start_time=START, end_time=END)
    df.columns = ['sig', 'LABEL']
    df.index = pd.MultiIndex.from_arrays(
        [df.index.get_level_values(0).map(to_rqcode),
         df.index.get_level_values(1).strftime('%Y%m%d').astype('int64')],
        names=['obid', 'date'])
    df = df.sort_index()

    # 逐日
    qd = df[df['sig'] > 0.5].groupby(level='date')
    rq = pan[pan['signal']].groupby('date')

    cmp = pd.DataFrame({
        'n_q': qd.size(),
        'r_q': qd['LABEL'].mean(),
        'n_rq': rq.size(),
        'r_rq': rq['fwd_t1_21'].mean(),
    }).fillna({'n_rq': 0, 'n_q': 0})
    cmp['d_ret'] = (cmp['r_q'] - cmp['r_rq']) * 100      # 单日收益差(pp)
    cmp['n_diff'] = (cmp['n_q'] - cmp['n_rq']).abs()

    print(f"\n交易日数: {len(cmp)}")
    print(f"日截面: rqalpha {cmp['r_rq'].mean()*100:.4f}%   qlib {cmp['r_q'].mean()*100:.4f}%   "
          f"差 {(cmp['r_q']-cmp['r_rq']).mean()*100:+.4f}pp", file=out)

    # ---- 按 qlib 当日信号数分层 ----
    bins = [0, 2, 5, 10, 20, 50, 10 ** 9]
    labels = ['1-2', '3-5', '6-10', '11-20', '21-50', '50+']
    cmp['band'] = pd.cut(cmp['n_q'], bins=bins, labels=labels)

    print("\n" + "=" * 104, file=out)
    print("按当日信号数分层 (不剔涨跌停, 纯信号口径)")
    print("=" * 104, file=out)
    print(f"  {'信号数档':<10}{'天数':>7}{'占比':>8}{'rq日收':>11}{'qlib日收':>11}"
          f"{'单日差':>11}{'对总差贡献':>13}{'信号数差异':>11}")
    print("-" * 104, file=out)
    tot = cmp['d_ret'].sum()
    for band, g in cmp.groupby('band', observed=True):
        contrib = g['d_ret'].sum() / len(cmp)
        print(f"  {str(band):<10}{len(g):>7}{len(g)/len(cmp)*100:>7.1f}%"
              f"{g['r_rq'].mean()*100:>10.3f}%{g['r_q'].mean()*100:>10.3f}%"
              f"{g['d_ret'].mean():>10.3f}{contrib:>+12.4f}{g['n_diff'].mean():>11.2f}", file=out)
    print("-" * 104, file=out)
    print(f"  总差异 = {tot/len(cmp):+.4f}pp")

    # ---- 只看两边信号数完全相同的日子 ----
    same = cmp[cmp['n_diff'] == 0]
    print(f"\n【信号数完全相同的交易日】{len(same)} 天 (占 {len(same)/len(cmp)*100:.1f}%)")
    print(f"  rq日截 = {same['r_rq'].mean()*100:.4f}%   qlib日截 = {same['r_q'].mean()*100:.4f}%   "
          f"差 = {(same['r_q']-same['r_rq']).mean()*100:+.4f}pp")
    for band, g in same.groupby('band', observed=True):
        if len(g):
            print(f"    {str(band):<8} 天数={len(g):>5}  rq={g['r_rq'].mean()*100:>9.3f}%  "
                  f"q={g['r_q'].mean()*100:>9.3f}%  差={(g['r_q']-g['r_rq']).mean()*100:>+8.3f}pp")

    # ---- 若只统计信号数较多的日子 ----
    for thr in [5, 10, 20]:
        sub = cmp[cmp['n_q'] >= thr]
        if len(sub):
            print(f"\n【仅统计当日信号数 >= {thr} 的交易日】{len(sub)} 天")
            print(f"  rq日截 = {sub['r_rq'].mean()*100:.4f}%   qlib日截 = {sub['r_q'].mean()*100:.4f}%   "
                  f"差 = {(sub['r_q']-sub['r_rq']).mean()*100:+.4f}pp")


if __name__ == '__main__':
    main()
