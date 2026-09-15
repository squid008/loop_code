# -*- coding: utf-8 -*-
"""
全量归因: 把 rqalpha 与 qlib 的「每一个」信号差异样本逐一定性,
统计到底有多少是浮点精度边界翻转, 有多少是真实指标差(数据差)。
不再抽查, 对全部差异样本做判定。
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

RP = r'd:\rqalpha_demo\ai_test\_align_panel.pkl'   # rqalpha 面板
QP = r'd:\rqalpha_demo\ai_test\_panel_tam.pkl'     # qlib 信号面板 (mode=none)
OUT = r'd:\rqalpha_demo\ai_test\attribute_all.txt'

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
OUTS = {'LONG': '长期线:长期线;', 'SHORT': '短期线:短期线;',
        'MID': '中期线:中期线;', 'BOT': '底:底;'}

TH_FLOAT = 1e-3   # 指标差小于此值, 视为浮点精度量级


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
    f = open(OUT, 'w', encoding='utf-8')

    def w(*a):
        print(*a, file=out)
        print(*a, file=f)

    # ---------- 1. rqalpha 面板 ----------
    rq = pd.read_pickle(RP)
    rq['date'] = rq['date'].astype('int64')
    rq = rq.set_index(['obid', 'date']).sort_index()
    w(f"[rqalpha] 面板 {len(rq):,} 行  index={rq.index.names}")
    w(f"          列: {rq.columns.tolist()}")

    # ---------- 2. qlib 信号面板 (_panel_tam.pkl) ----------
    qp = pd.read_pickle(QP)
    w(f"[qlib  ] _panel_tam.pkl {len(qp):,} 行")
    w(f"          列: {qp.columns.tolist()}")
    if isinstance(qp.index, pd.MultiIndex):
        w(f"          index: {qp.index.names}")
        w(f"          第一层样例: {qp.index.get_level_values(0)[:3].tolist()}")
    qp['obid'] = qp.index.get_level_values(0).map(to_rqcode)
    qp['date'] = qp.index.get_level_values(1).strftime('%Y%m%d').astype('int64')
    qp = qp.set_index(['obid', 'date']).sort_index()

    # ---------- 3. 对齐, 找全部信号差异 ----------
    j = rq[['signal', 'long', 'short', 'mid', 'bottom']].join(
        qp[['F0']], how='inner')
    j['qsig'] = j['F0'] > 0.5
    j = j[j['signal'].notna() & j['qsig'].notna()]
    w(f"[对齐 ] inner join 后 {len(j):,} 行, 信号两边都有值")

    diff = j[j['signal'].astype(bool) != j['qsig']].copy()
    w(f"\n================ 信号差异样本总数: {len(diff):,} ================")
    rq_only = diff[diff['signal'].astype(bool) & ~diff['qsig']]
    q_only = diff[~diff['signal'].astype(bool) & diff['qsig']]
    w(f"  仅 rqalpha 触发 (rq=1,q=0): {len(rq_only):,}")
    w(f"  仅 qlib   触发 (q=1,rq=0): {len(q_only):,}")
    if len(diff) == 0:
        w("无差异, 结束")
        f.close()
        return

    # ---------- 4. 对涉及股票实时重算 qlib 三根线+底 ----------
    obids = sorted(set(diff.index.get_level_values(0)))
    qcodes = [to_qcode(o) for o in obids]
    w(f"\n[指标 ] 差异涉及 {len(obids):,} 只股票, 调 qlib 计算三根线 ...")
    exprs = {}
    for k, o in OUTS.items():
        t = translate_formula(BASE.format(OUT=o))
        exprs[k] = _sr_wrap_expr(adjust_expr(t.expression, 'none'))
    qind = D.features(qcodes, [exprs['LONG'], exprs['SHORT'], exprs['MID'], exprs['BOT']],
                      start_time='2021-01-01', end_time='2026-08-31')
    qind.columns = ['q_long', 'q_short', 'q_mid', 'q_bot']
    qind['obid'] = qind.index.get_level_values(0).map(to_rqcode)
    qind['date'] = qind.index.get_level_values(1).strftime('%Y%m%d').astype('int64')
    qind = qind.set_index(['obid', 'date']).sort_index()
    w(f"[指标 ] qlib 指标面板 {len(qind):,} 行")

    # 前一日值: qlib 侧
    g = qind.groupby(level=0)
    for c in ['q_long', 'q_short', 'q_mid', 'q_bot']:
        qind[c + '_p1'] = g[c].shift(1)
    # rqalpha 侧前一日值
    gr = j.groupby(level=0)
    for c in ['long', 'short', 'mid', 'bottom']:
        j[c + '_p1'] = gr[c].shift(1)
    # diff 是 shift 前生成的, 需要把 rq 侧前一日补进来(否则归因只有 T 日)
    diff = diff.join(j[['long_p1', 'short_p1', 'mid_p1', 'bottom_p1']], how='left')

    # ---------- 5. 逐样本归因 ----------
    diff = diff.join(qind[['q_long', 'q_short', 'q_mid', 'q_bot',
                           'q_long_p1', 'q_short_p1', 'q_mid_p1', 'q_bot_p1']], how='left')

    PAIRS = [('long', 'q_long'), ('short', 'q_short'), ('mid', 'q_mid')]
    recs = []
    for (obid, date), r in diff.iterrows():
        maxd = 0.0
        worst = ''
        ncmp = 0
        for suf in ['', '_p1']:
            for a, b in PAIRS:
                va, vb = r.get(a + suf), r.get(b + suf)
                if pd.notna(va) and pd.notna(vb):
                    dd = abs(float(va) - float(vb))
                    ncmp += 1
                    if dd > maxd:
                        maxd = dd
                        worst = a + suf
        rq_trig = int(bool(r['signal']))
        q_trig = int(bool(r['qsig']))
        recs.append(dict(obid=obid, date=date, rq_trig=rq_trig, q_trig=q_trig,
                         maxd=maxd, worst=worst, ncmp=ncmp))

    rec = pd.DataFrame(recs)
    float_n = int((rec['maxd'] < TH_FLOAT).sum())
    data_n = int((rec['maxd'] >= TH_FLOAT).sum())
    nan_n = int((rec['ncmp'] == 0).sum())
    w(f"\n================ 全量归因结果 ================")
    w(f"  浮点精度边界翻转 (三根线最大差 < {TH_FLOAT}): {float_n:,}")
    w(f"  真实指标差       (三根线最大差 >= {TH_FLOAT}): {data_n:,}")
    w(f"  缺指标无法判定(ncmp=0): {nan_n:,}")
    w(f"  合计: {len(rec):,}")

    # 指标差分布
    arr = rec['maxd'].values
    w(f"\n================ 指标差分布 ================")
    for lo, hi in [(0, 1e-6), (1e-6, 1e-5), (1e-5, 1e-4), (1e-4, 1e-3),
                   (1e-3, 1e-2), (1e-2, 1e-1), (1e-1, np.inf)]:
        n = int(((arr >= lo) & (arr < hi)).sum())
        w(f"  [{lo:g}, {hi:g}): {n:>5,}   ({n/len(arr)*100:.2f}%)")

    # ---------- 6. 非浮点样本全列出来 ----------
    bad = rec[rec['maxd'] >= TH_FLOAT].sort_values('maxd', ascending=False)
    w(f"\n================ 真实指标差样本 ({len(bad)} 个) 全量明细 ================")
    if len(bad):
        for _, d in bad.iterrows():
            r = diff.loc[(d['obid'], d['date'])]
            w(f"\n  {d['obid']}  {d['date']}   rq触发={d['rq_trig']} q触发={d['q_trig']}"
              f"  最大指标差={d['maxd']:.6f} @ {d['worst']}")
            for suf in ['', '_p1']:
                w(f"    T{suf or ''}:")
                for a, b in PAIRS:
                    va, vb = r.get(a + suf), r.get(b + suf)
                    s = f"{a+suf:<14} rq={va if pd.notna(va) else '-':<}"
                    s += f"   q={vb if pd.notna(vb) else '-':<}"
                    if pd.notna(va) and pd.notna(vb):
                        s += f"   差={abs(float(va)-float(vb)):.6f}"
                    w("      " + s)
                w(f"      bottom: rq={r.get('bottom'+suf)}  q={r.get('q_bot'+suf)}")
    else:
        w("  (无)")

    # ---------- 7. 浮点样本抽样展示 ----------
    fl = rec[rec['maxd'] < TH_FLOAT].sort_values('maxd', ascending=False)
    w(f"\n================ 浮点边界样本抽样 (共 {len(fl):,}, 显示差最大的 20) ================")
    for _, d in fl.head(20).iterrows():
        r = diff.loc[(d['obid'], d['date'])]
        w(f"\n  {d['obid']}  {d['date']}   rq触发={d['rq_trig']} q触发={d['q_trig']}"
          f"  最大指标差={d['maxd']:.3e} @ {d['worst']}")
        for a, b in PAIRS:
            va, vb = r.get(a), r.get(b)
            v1a, v1b = r.get(a + '_p1'), r.get(b + '_p1')
            w(f"      {a:<6} T-1: rq={v1a if pd.notna(v1a) else '-':<}" 
              f"  q={v1b if pd.notna(v1b) else '-':<}"
              f"   |   T: rq={va if pd.notna(va) else '-':<}  q={vb if pd.notna(vb) else '-':<}")
        w(f"      bottom T: rq={r.get('bottom')}  q={r.get('q_bot')}")

    # 保存明细供后续日期/断档分析
    diff.to_pickle(r'd:\rqalpha_demo\ai_test\_diff_detail.pkl')
    qind.to_pickle(r'd:\rqalpha_demo\ai_test\_qind.pkl')
    rec.to_pickle(r'd:\rqalpha_demo\ai_test\_rec.pkl')
    w(f"\n[已保存] _diff_detail.pkl / _qind.pkl / _rec.pkl")

    f.close()


if __name__ == '__main__':
    main()
