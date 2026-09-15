# -*- coding: utf-8 -*-
"""
130 真实差的精确分类:
  用 qlib 交易日历(day.txt) + instruments(all.txt 上市日)。
  每样本看:
    NEW   : 差异日距上市日 < 250 交易日 (上市不足一年, 窗口/EMA初值未充分)
    REC   : 差异日距上市日 >=250 交易日 (上市已一年以上)
  对 REC 再看:
    SUSP  : 该股在差异日前是否长期停牌(qlib面板在 date 前存在 >=20 交易日无行情段)
"""
import sys
import io
import logging

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
logging.disable(logging.WARNING)

import numpy as np
import pandas as pd

DAY = r'D:\quant\qlib_code\data\cn_data\calendars\day.txt'
INST = r'D:\quant\qlib_code\data\cn_data\instruments\all.txt'


def main():
    rec = pd.read_pickle(r'd:\rqalpha_demo\ai_test\_rec.pkl')
    real = rec[rec['maxd'] >= 1e-3].copy()
    print(f"真实差样本: {len(real)}")

    cal = pd.read_csv(DAY, header=None, names=['day'])['day'].astype(str).str.replace('-', '')
    calpos = {d: i for i, d in enumerate(cal)}
    inst = pd.read_csv(INST, sep='\t', header=None, names=['code', 'start', 'end'])
    inst['start'] = inst['start'].str.replace('-', '')
    # 上市日 (obid: 002711.XSHE -> qlib code: SZ002711)
    def listday(obid):
        code, exch = str(obid).split('.')
        qcode = ('SH' if exch == 'XSHG' else 'SZ') + code
        m = inst[inst['code'] == qcode]
        return m['start'].iloc[0] if len(m) else None

    # 每股票 qlib 面板日期(用于查停牌段)
    qp = pd.read_pickle(r'd:\rqalpha_demo\ai_test\_panel_tam.pkl')
    qp['obid'] = qp.index.get_level_values(0).map(
        lambda q: q[2:] + ('.XSHG' if str(q).startswith('SH') else '.XSHE'))
    qp['date'] = qp.index.get_level_values(1).strftime('%Y%m%d').astype(int)
    qdates = qp.groupby('obid')['date'].apply(lambda s: sorted(set(s)))

    rows = []
    for _, r in real.iterrows():
        obid, date = r['obid'], int(r['date'])
        ld = listday(obid)
        # 差异日距上市日交易天数
        if ld and ld in calpos and str(date) in calpos:
            tn = calpos[str(date)] - calpos[ld]
        else:
            tn = np.nan
        if ld is None:
            cls = 'NO_LIST'
        elif tn < 250:
            cls = 'NEW(<250交易日)'
        else:
            cls = 'REC(>=250交易日)'
        rows.append(dict(obid=obid, date=date, maxd=r['maxd'], tn=tn, cls=cls))

    dd = pd.DataFrame(rows)
    print(f"\n=== 上市不足250交易日 (窗口/EMA初值敏感期) ===")
    new = dd[dd['cls'] == 'NEW(<250交易日)']
    print(f"  {len(new)} / {len(dd)}")
    old = dd[dd['cls'] == 'REC(>=250交易日)']
    print(f"\n=== 上市>=250交易日 的真实差: {len(old)} ===")
    if len(old):
        print(f"  {'obid':<16}{'date':<10}{'上市后交易日':>12}{'maxd':>10}  @worst")
        for _, r in old.sort_values('maxd', ascending=False).iterrows():
            print(f"  {r['obid']:<16}{r['date']:<10}{r['tn']:>10.0f}{r['maxd']:>10.4f}")

    print(f"\n=== 小结 ===")
    print(f"  真实差总数 130 = 上市初期(NEW) {len(new)} + 老股(REC) {len(old)}")

    # 上市后交易天数分布(次新内)
    print(f"\n=== 130 真实差的上市后交易日分布 ===")
    for lo, hi, tag in [(0, 34, '不足34日(HHV34窗口未满)'),
                        (34, 80, '34-80日'),
                        (80, 250, '80-250日'),
                        (250, 10 ** 9, '老股(>=250日)')]:
        n = int(((dd['tn'] >= lo) & (dd['tn'] < hi)).sum())
        print(f"  [{tag}] {n}")


if __name__ == '__main__':
    main()
