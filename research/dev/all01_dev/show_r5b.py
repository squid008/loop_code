# -*- coding: utf-8 -*-
import os
import pandas as pd

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
d = pd.read_csv(os.path.join(HERE, 'round5b_fund.csv'))
out = []
for m in ['raw', 'lnmc', 'barra']:
    s = d[d['mode'] == m].sort_values('ann_ex', ascending=False)
    npass = int((s['pass'] == 'PASS').sum())
    out.append('=' * 92)
    out.append('[%s]  n=%d  通过 %d' % (m, len(s), npass))
    out.append('=' * 92)
    out.append(s[['name', 'ic', 'ic_ir', 'ic_win', 'ann_ex', 'dd', 'calmar',
                  'last_yr', 'cov', 'pass']].round(4).to_string(index=False))
    out.append('')
p = d.pivot_table(index='name', columns='mode', values='ann_ex')
p['ic_raw'] = d[d['mode'] == 'raw'].set_index('name')['ic']
p['ic_barra'] = d[d['mode'] == 'barra'].set_index('name')['ic']
p['cal_barra'] = d[d['mode'] == 'barra'].set_index('name')['calmar']
out.append('=' * 92)
out.append('三模式对比(按 raw 超额排序)')
out.append('=' * 92)
out.append(p.sort_values('raw', ascending=False).round(4).to_string())
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'r5b_summary.txt'),
          'w', encoding='utf-8') as f:
    f.write('\n'.join(out))
print('ok')
