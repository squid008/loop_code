# -*- coding: utf-8 -*-
"""终极验证: 用 qlib 真实执行该公式, 对比「观测加权」与「日截面」两种口径
   (Windows 下必须 main guard, 否则 joblib spawn 子进程会递归重跑)
"""
import sys
import io
import os

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, r'D:\quant\qlib_code\backend')

# 必须在【顶层】注册: joblib 在 Windows 用 spawn, 子进程会重新导入本模块,
# 若注册只发生在 main() 内, 子进程将看不到 SR/DYN_* 算子。
try:
    from app.factors.ops_ext import ensure_ops_registered
    ensure_ops_registered(force=True)
except Exception as _e:
    sys.stdout.write(f"[warn] 算子注册失败: {_e}\n")

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

OUTS = {
    'LONG': '长期线:长期线;',
    'SHORT': '短期线:短期线;',
    'MID': '中期线:中期线;',
    'BOTTOM': '底:底;',
    'SIG': '信号:ref(底,1)=1 and 底=0;',
}

START, END = '2021-01-01', '2026-08-12'
N_SAMPLE = int(os.environ.get('NS', '400'))


def stat(df, tag, out):
    if df is None:
        return
    sub = df[['SIG', 'LABEL']].dropna()
    trig = sub[sub['SIG'] > 0.5]['LABEL']
    notrig = sub[sub['SIG'] <= 0.5]['LABEL']
    print(f"  [{tag}] 样本={len(sub):,}  触发={len(trig):,} ({len(trig)/max(len(sub),1)*100:.2f}%)", file=out)
    print(f"        观测加权: 触发={trig.mean()*100:.4f}%  未触发={notrig.mean()*100:.4f}%  "
          f"差={(trig.mean()-notrig.mean())*100:.4f}%", file=out)
    dpos = sub.index.names.index('datetime')
    d_t = sub[sub['SIG'] > 0.5].groupby(level=dpos)['LABEL'].mean()
    d_n = sub[sub['SIG'] <= 0.5].groupby(level=dpos)['LABEL'].mean()
    print(f"        日截面  : 触发={d_t.mean()*100:.4f}%  未触发={d_n.mean()*100:.4f}%  "
          f"差={(d_t.mean()-d_n.mean())*100:.4f}%  (触发参与天数={len(d_t)})", file=out)
    cnt = sub[sub['SIG'] > 0.5].groupby(level=dpos).size()
    print(f"        每日触发数: 均值={cnt.mean():.1f} 中位={cnt.median():.0f} "
          f"最大={cnt.max()} 最小={cnt.min()}", file=out)
    top = cnt.sort_values(ascending=False).head(5)
    print(f"        触发最集中5天: {dict(zip([str(i)[:10] for i in top.index], top.values))}", file=out)


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
    print("=" * 100, file=out)
    print("1) 公式编译", file=out)
    print("=" * 100, file=out)
    exprs = {}
    for key, o in OUTS.items():
        t = translate_formula(BASE.format(OUT=o))
        exprs[key] = t.expression
        print(f"  [{key}] {len(t.expression)} 字符", file=out)
    print(f"\n  SIG 原始表达式(前300字符):\n    {exprs['SIG'][:300]}", file=out)

    e_adj = adjust_expr(exprs['SIG'], 'none')
    e_sr = _sr_wrap_expr(e_adj)
    print(f"\n  SIG +none复权 +SR (前300字符):\n    {e_sr[:300]}", file=out)

    insts = D.instruments(market='all')
    codes = [str(c) for c in D.list_instruments(insts, start_time=START, as_list=True)]
    codes = [c for c in codes if not c.startswith('BJ')
             and not c.startswith(('SH000', 'SH88', 'SH89', 'SZ39'))]
    if N_SAMPLE:
        codes = codes[::max(1, len(codes) // N_SAMPLE)][:N_SAMPLE]
    print(f"\n  参与计算股票数: {len(codes)}", file=out)

    label = adjust_expr("Ref($close, -21)/Ref($close, -1) - 1", 'none')

    def run(sig_expr):
        fields = [sig_expr, label,
                  adjust_expr("$close/$factor", 'none'), "$change",
                  "Ref($close/$factor, -1)", "Ref($change, -1)"]
        names = ['SIG', 'LABEL', 'CLOSE', 'CHANGE', 'T1_CLOSE', 'T1_CHANGE']
        try:
            df = D.features(codes, fields, start_time=START, end_time=END)
            df.columns = names
            return df
        except Exception as e:
            print(f"    计算失败: {type(e).__name__}: {e}", file=out)
            return None

    print("\n" + "=" * 100, file=out)
    print("2) 两种统计口径对比 (qlib 真实执行)", file=out)
    print("=" * 100, file=out)
    df_nosr = run(adjust_expr(exprs['SIG'], 'none'))
    stat(df_nosr, '不包SR', out)
    df_sr = run(e_sr)
    stat(df_sr, '包SR(现网口径)', out)

    print("\n" + "=" * 100, file=out)
    print("3) 中间量: 包SR vs 不包SR", file=out)
    print("=" * 100, file=out)
    for key in ['LONG', 'SHORT', 'MID']:
        e1 = adjust_expr(exprs[key], 'none')
        e2 = _sr_wrap_expr(e1)
        try:
            a = D.features(codes, [e1], start_time=START, end_time=END)
            b = D.features(codes, [e2], start_time=START, end_time=END)
            a.columns = ['v']
            b.columns = ['v']
            j = a.join(b, how='inner', lsuffix='_nosr', rsuffix='_sr')
            d = (j['v_nosr'] - j['v_sr']).abs()
            print(f"  [{key}] 对齐={len(j):,} 一致={(int((d<1e-9).sum())):,} "
                  f"最大差={d.max():.6f} 平均差={d.mean():.8f}", file=out)
        except Exception as e:
            print(f"  [{key}] 失败: {type(e).__name__}: {e}", file=out)

    print("\n" + "=" * 100, file=out)
    print("4) 信号样本差异", file=out)
    print("=" * 100, file=out)
    if df_nosr is not None and df_sr is not None:
        j = pd.concat([df_nosr['SIG'].rename('a'), df_sr['SIG'].rename('b')],
                      axis=1, join='inner').dropna()
        both = int(((j['a'] > 0.5) & (j['b'] > 0.5)).sum())
        onlya = int(((j['a'] > 0.5) & (j['b'] <= 0.5)).sum())
        onlyb = int(((j['a'] <= 0.5) & (j['b'] > 0.5)).sum())
        print(f"  共同触发={both:,}  仅不包SR={onlya:,}  仅包SR={onlyb:,}", file=out)


if __name__ == '__main__':
    main()
