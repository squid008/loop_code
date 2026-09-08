# -*- coding: utf-8 -*-
"""
定位 0.4840% 与 qlib 前端 0.4980% 之间 0.014pp 的系统性偏移。

观察: 触发组 -0.014pp、未触发组 -0.012pp —— 两组同向偏移、差值几乎不变(差 0.002pp),
     说明是「全体样本层面的口径/范围差异」, 而非信号口径问题。

候选成因:
  A. 日期范围(END 取到哪天, 影响最后 21 天 LABEL 是否能算)
  B. 三重剔除开关组合(前端可勾选, 未必全开)
  C. SR 包装与否(1.6.5 前后语义)
  D. 股票池 universe
  E. 数据版本

策略: 一次算好因子(SR 版 / 无SR 版), 之后纯后处理快速枚举 A/B, 避免重复 D.features。
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

FORMULA = """A:=MA(-100*(HHV(HIGH,34)-CLOSE)/(HHV(HIGH,34)-LLV(LOW,34)),19);
B:=-100*(HHV(HIGH,14)-CLOSE)/(HHV(HIGH,14)-LLV(LOW,14));
d:=EMA(-100*(HHV(HIGH,34)-CLOSE)/(HHV(HIGH,34)-LLV(LOW,34)),4);
长期线:=A+100;
短期线:=B+100;
中期线:=d+100;
底:=(长期线<12 and 中期线<8 and (短期线<7.2 or ref(短期线,1)<5) and (中期线>ref(中期线,1) or 短期线>ref(短期线,1)))
or (长期线<8 and 中期线<7 and 短期线<15 and 短期线>ref(短期线,1)) or (长期线<10 and 中期线<7 and 短期线<1);
趋势顶底离开底部:ref(底,1)=1 and 底=0;
"""

START = '2021-01-01'
T_T, T_N = 0.4980, 0.7700          # 前端目标


def main():
    import numpy as np
    import pandas as pd
    import qlib
    qlib.init(provider_uri=r'D:\quant\qlib_code\data\cn_data', region='cn')
    from qlib.data import D
    from app.factors.parser import translate_formula
    from app.engine.adjust import adjust_expr
    from app.engine.feature_cache import _sr_wrap_expr
    from app.engine.limits import mark_limit_up
    from app.factors.single_test import _resolve_instruments

    out = sys.stdout
    t = translate_formula(FORMULA)
    e_nosr = adjust_expr(t.expression, 'none')
    e_sr = _sr_wrap_expr(e_nosr)
    label_expr = adjust_expr("Ref($close, -21)/Ref($close, -1) - 1", 'none')

    # 数据末尾尽量靠后, 让 LABEL 覆盖最全
    codes = _resolve_instruments('all', START)
    DATA_END = os.environ.get('DEND', '2026-08-31')
    print(f"股票池 {len(codes)} 只   取数区间 {START} ~ {DATA_END}", file=out)

    # 元数据恒用真实价原始串, 不可过 adjust_expr(否则 close/factor² 双重除)
    fields = [e_sr, e_nosr, label_expr,
              "$close/$factor", "$change",
              "Ref($close/$factor, -1)", "Ref($change, -1)"]
    names = ['SR', 'NOSR', 'LABEL', 'CLOSE', 'CHANGE', 'T1_CLOSE', 'T1_CHANGE']
    df = D.features(codes, fields, start_time=START, end_time=DATA_END)
    df.columns = names
    df.to_pickle(r'd:\rqalpha_demo\ai_test\_panel.pkl')
    print(f"面板已缓存: {len(df):,} 行", file=out)

    dpos = df.index.names.index('datetime')
    all_dates = sorted(set(df.index.get_level_values(dpos)))
    print(f"交易日范围: {all_dates[0]} ~ {all_dates[-1]}  共 {len(all_dates)} 天", file=out)

    # LABEL 非空的最大日期(决定信号可统计到哪天)
    lab_ok = df['LABEL'].notna()
    if lab_ok.any():
        last_ok = df.index.get_level_values(dpos)[lab_ok].max()
        print(f"LABEL 可计算到的最后日期: {last_ok}", file=out)

    def evaluate(col, end_date, excl):
        """col: 'SR'/'NOSR';  end_date: 信号统计截止;  excl: (lu_t, lu_t1, susp)"""
        d = df
        if end_date is not None:
            d = d[d.index.get_level_values(dpos) <= pd.Timestamp(end_date)]
        sub = d[[col, 'LABEL']].dropna()
        trig = sub[sub[col] > 0.5]
        notr = sub[sub[col] <= 0.5]
        lu_t, lu_t1, susp = excl
        if lu_t:
            m = mark_limit_up(d.loc[trig.index], 'CLOSE', 'CHANGE')
            trig = trig[~m]
            m = mark_limit_up(d.loc[notr.index], 'CLOSE', 'CHANGE')
            notr = notr[~m]
        if lu_t1:
            m = mark_limit_up(d.loc[trig.index], 'T1_CLOSE', 'T1_CHANGE')
            trig = trig[~m]
            m = mark_limit_up(d.loc[notr.index], 'T1_CLOSE', 'T1_CHANGE')
            notr = notr[~m]
        if susp:
            trig = trig[~d.loc[trig.index, 'T1_CLOSE'].isna()]
            notr = notr[~d.loc[notr.index, 'T1_CLOSE'].isna()]
        if len(trig) == 0 or len(notr) == 0:
            return None
        dt = trig.groupby(level=dpos)['LABEL'].mean()
        dn = notr.groupby(level=dpos)['LABEL'].mean()
        return {
            'n_trig': len(trig), 'n_notr': len(notr),
            'pooled_t': trig['LABEL'].mean() * 100,
            'pooled_n': notr['LABEL'].mean() * 100,
            'daily_t': dt.mean() * 100,
            'daily_n': dn.mean() * 100,
            'days_t': len(dt), 'days_n': len(dn),
            'last_t': str(dt.index.max())[:10],
        }

    ENDS = [None, '2026-08-12', '2026-07-31', '2026-08-19']
    EXCLS = [
        ('剔除全开(T,T+1,停牌)', (True, True, True)),
        ('仅T涨停', (True, False, False)),
        ('仅T+1涨停+停牌', (False, True, True)),
        ('全不剔除', (False, False, False)),
    ]

    print("\n" + "=" * 108, file=out)
    print("枚举: SR × 截止日 × 剔除组合   (目标 触发 0.4980% / 未触发 0.7700%)", file=out)
    print("=" * 108, file=out)
    print(f"  {'SR':<5}{'截止日':<12}{'剔除':<20}{'触发日截':>10}{'未触发日截':>11}"
          f"{'Δ触发':>9}{'Δ未触发':>9}{'天数':>7}", file=out)
    print("-" * 108, file=out)

    best = None
    for col in ['SR', 'NOSR']:
        for end in ENDS:
            for ename, ex in EXCLS:
                r = evaluate(col, end, ex)
                if r is None:
                    continue
                dT = r['daily_t'] - T_T
                dN = r['daily_n'] - T_N
                gap = abs(dT) + abs(dN)
                if best is None or gap < best[0]:
                    best = (gap, col, end, ename, r)
                print(f"  {col:<5}{str(end):<12}{ename:<20}{r['daily_t']:>9.4f}%"
                      f"{r['daily_n']:>10.4f}%{dT:>+8.4f}{dN:>+9.4f}{r['days_t']:>7}", file=out)

    print("-" * 108, file=out)
    if best:
        gap, col, end, ename, r = best
        print(f"\n  最匹配: SR={col}  截止={end}  剔除={ename}")
        print(f"     触发日截面={r['daily_t']:.4f}%  (目标 {T_T}%, Δ={r['daily_t']-T_T:+.4f})")
        print(f"     未触发日截面={r['daily_n']:.4f}%  (目标 {T_N}%, Δ={r['daily_n']-T_N:+.4f})")
        print(f"     观测加权: 触发={r['pooled_t']:.4f}%  未触发={r['pooled_n']:.4f}%")
        print(f"     样本: 触发={r['n_trig']:,} 未触发={r['n_notr']:,}  天数={r['days_t']}/{r['days_n']}")

    # 基准组合的逐年日截面, 看偏移分布在哪一年
    print("\n" + "=" * 108, file=out)
    print("基准组合(SR + 全剔除 + 截止2026-08-12)的逐年日截面", file=out)
    print("=" * 108, file=out)
    d = df[df.index.get_level_values(dpos) <= pd.Timestamp('2026-08-12')]
    sub = d[['SR', 'LABEL']].dropna()
    trig = sub[sub['SR'] > 0.5]
    notr = sub[sub['SR'] <= 0.5]
    for name, g in (('trig', trig), ('notr', notr)):
        m = mark_limit_up(d.loc[g.index], 'CLOSE', 'CHANGE')
        g = g[~m]
        m = mark_limit_up(d.loc[g.index], 'T1_CLOSE', 'T1_CHANGE')
        g = g[~m]
        g = g[~d.loc[g.index, 'T1_CLOSE'].isna()]
        if name == 'trig':
            trig = g
        else:
            notr = g
    dt = trig.groupby(level=dpos)['LABEL'].mean()
    dn = notr.groupby(level=dpos)['LABEL'].mean()
    dt.index = pd.to_datetime(dt.index)
    dn.index = pd.to_datetime(dn.index)
    yr = pd.DataFrame({'触发': dt, '未触发': dn}).dropna()
    yr['年'] = yr.index.year
    g2 = yr.groupby('年').agg(天数=('触发', 'size'), 触发均值=('触发', 'mean'),
                             未触发均值=('未触发', 'mean'))
    g2['触发均值'] *= 100
    g2['未触发均值'] *= 100
    print(g2.to_string(float_format=lambda x: f"{x:.4f}"), file=out)
    print(f"\n  全期: 触发={dt.mean()*100:.4f}%  未触发={dn.mean()*100:.4f}%  "
          f"天数={len(dt)}", file=out)


if __name__ == '__main__':
    main()
