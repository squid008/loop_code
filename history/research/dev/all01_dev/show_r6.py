# -*- coding: utf-8 -*-
import os
import pandas as pd

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
d = pd.read_csv(os.path.join(HERE, 'round6_jq.csv'))
out = []
for m in ['raw', 'lnmc', 'barra', 'strat']:
    s = d[d['mode'] == m].sort_values('ann_ex', ascending=False)
    out.append('=' * 100)
    out.append('[%s]  n=%d  通过 %d' % (m, len(s), int((s['pass'] == 'PASS').sum())))
    out.append('=' * 100)
    out.append(s[['name', 'ic', 'ic_ir', 'ic_win', 'ann_ex', 'dd', 'calmar',
                  'last_yr', 'cov', 'pass']].round(4).to_string(index=False))
    out.append('')
p = d.pivot_table(index='name', columns='mode', values='ann_ex')
for c in ['ic', 'ic_ir', 'calmar']:
    q = d[d['mode'] == 'barra'].set_index('name')[c]
    p[c + '_barra'] = q
p = p.sort_values('barra', ascending=False)
out.append('=' * 100)
out.append('四口径对比(按 barra 超额排序)')
out.append('=' * 100)
out.append(p.round(4).to_string())
both = p[(p.get('barra', 0) > 0) & (p.get('strat', 0) > 0)]
out.append('\n== barra 与 strat 双口径同为正(候选) ==')
out.append(both.round(4).to_string())
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'r6_summary.txt'),
          'w', encoding='utf-8') as f:
    f.write('\n'.join(out))
print('ok')
