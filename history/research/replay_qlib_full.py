# -*- coding: utf-8 -*-
"""
精确复现 qlib_code 单因子测试(single_test.py)对「趋势顶底离开底部」的结果。
完全照抄其流程: 编译 → none复权 → SR包装 → label → 三重剔除 → 两种口径统计。
Windows 下必须 main guard。
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
    sys.stdout.write(f"[warn] 算子注册失败: {_e}\n")

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

START, END = '2021-01-01', '2026-08-12'
LIMIT = int(os.environ.get('LIM', '0'))   # 0 = 全量


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
    sig_expr = _sr_wrap_expr(adjust_expr(t.expression, 'none'))
    label_expr = adjust_expr("Ref($close, -21)/Ref($close, -1) - 1", 'none')
    print(f"输出因子名: {t.name}", file=out)
    print(f"表达式长度: {len(sig_expr)}", file=out)

    codes = _resolve_instruments('all', START)
    if LIMIT:
        codes = codes[::max(1, len(codes) // LIMIT)][:LIMIT]
    print(f"股票池: {len(codes)} 只", file=out)

    # 注意: 涨停/停牌判定字段恒用【真实价】且必须是未处理的原始串。
    # 切勿对其调用 adjust_expr —— 它会把串里的 $close 再替换成 ($close/$factor),
    # 使 "$close/$factor" 变成 "($close/$factor)/$factor" = close/factor² (双重除)。
    fields = [sig_expr, label_expr,
              "$close/$factor", "$change",
              "Ref($close/$factor, -1)", "Ref($change, -1)"]
    names = ['F0', 'LABEL', 'CLOSE', 'CHANGE', 'T1_CLOSE', 'T1_CHANGE']
    df = D.features(codes, fields, start_time=START, end_time=END)
    df.columns = names
    print(f"原始样本: {len(df):,}", file=out)

    def exclude(g):
        """照抄 single_test._test_one 的 _exclude（三开关全开）"""
        if len(g) == 0:
            return g
        m = mark_limit_up(df.loc[g.index], 'CLOSE', 'CHANGE')
        g = g[~m]
        m = mark_limit_up(df.loc[g.index], 'T1_CLOSE', 'T1_CHANGE')
        g = g[~m]
        m = df.loc[g.index, 'T1_CLOSE'].isna()
        g = g[~m]
        return g

    sub = df[['F0', 'LABEL']].dropna()
    trig = exclude(sub[sub['F0'] > 0.5])
    notr = exclude(sub[sub['F0'] <= 0.5])
    print(f"有效配对: {len(sub):,}   触发(剔除后)={len(trig):,}   "
          f"未触发(剔除后)={len(notr):,}", file=out)

    dpos = sub.index.names.index('datetime')
    pooled_t = trig['LABEL'].mean() * 100
    pooled_n = notr['LABEL'].mean() * 100
    d_t = trig.groupby(level=dpos)['LABEL'].mean()
    d_n = notr.groupby(level=dpos)['LABEL'].mean()

    print("\n" + "=" * 88, file=out)
    print("复现结果 (qlib_code 现网口径: none复权 + SR + 三重剔除)", file=out)
    print("=" * 88, file=out)
    print(f"  {'口径':<26}{'触发组':>13}{'未触发组':>13}{'差值':>13}", file=out)
    print("-" * 88, file=out)
    print(f"  {'观测加权 mean_ret':<26}{pooled_t:>12.4f}%{pooled_n:>12.4f}%"
          f"{pooled_t-pooled_n:>12.4f}%", file=out)
    print(f"  {'日截面 daily_trig_mean':<26}{d_t.mean()*100:>12.4f}%{d_n.mean()*100:>12.4f}%"
          f"{(d_t.mean()-d_n.mean())*100:>12.4f}%", file=out)
    print("-" * 88, file=out)
    print(f"  {'【前端显示】':<26}{0.498:>12.4f}%{0.770:>12.4f}%{-0.272:>12.4f}%", file=out)
    print(f"\n  触发参与天数={len(d_t)}  未触发参与天数={len(d_n)}", file=out)

    cnt = trig.groupby(level=dpos).size()
    print(f"  每日触发数: 均值={cnt.mean():.1f} 中位={cnt.median():.0f} "
          f"最大={cnt.max()} 最小={cnt.min()}", file=out)
    # 日截面的标准误（说明该口径估计有多不稳）
    se = d_t.std(ddof=1) / np.sqrt(len(d_t)) * 100
    print(f"  日截面标准误 SE = {se:.4f}%  (即触发组日截面的抽样误差约 ±{1.96*se:.3f}%)", file=out)


if __name__ == '__main__':
    main()
