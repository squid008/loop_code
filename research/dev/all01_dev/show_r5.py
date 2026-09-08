# -*- coding: utf-8 -*-
"""把 Round5 结果(CSV) 输出为 UTF-8 文本, 便于查看"""
import os
import pandas as pd

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
df = pd.read_csv(os.path.join(HERE, 'round5_fund.csv'))
out = []
for mode in ['raw', 'lnmc', 'barra']:
    sub = df[df['mode'] == mode].sort_values('ann_ex', ascending=False)
    out.append('=' * 96)
    out.append(f'Round5 财报因子 [{mode}]  共 {len(sub)} 个, 通过 {(sub["pass"]=="PASS").sum()} 个')
    out.append('=' * 96)
    cc = ['name', 'ic', 'ic_ir', 'ic_win', 'ann_ex', 'dd', 'calmar', 'last_yr', 'cov', 'pass']
    out.append(sub[cc].round(4).to_string(index=False))
    out.append('')
# 三模式对比透视
p = df.pivot_table(index='name', columns='mode', values='ann_ex')
p['ic_barra'] = df[df['mode'] == 'barra'].set_index('name')['ic']
p['cal_barra'] = df[df['mode'] == 'barra'].set_index('name')['calmar']
out.append('=' * 96)
out.append('三模式超额年化对比 (按 barra 超额排序)')
out.append('=' * 96)
out.append((p.sort_values('barra', ascending=False) * 1).round(4).to_string())
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'r5_summary.txt'),
          'w', encoding='utf-8') as f:
    f.write('\n'.join(out))
print('ok')
