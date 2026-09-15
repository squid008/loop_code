# -*- coding: utf-8 -*-
"""
生成因子挖掘档案: 汇总各轮 -> 关联公式 -> 输出 CSV + Markdown
供复盘/质疑使用, 记录每个因子"测了什么、公式是什么、结果如何"
"""
import os
import re
import sys
import pandas as pd
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from factor_registry import get_formula

LOGS = [('r1.log', 'Round1', '价量/资金流初探(39因子)'),
        ('r2.log', 'Round2', '参数扰动+资金流族+交叉(55因子)'),
        ('r3.log', 'Round3', 'ln(市值)单变量中性化后(93因子)'),
        ('r4.log', 'Round4', 'BARRA风格因子 + BARRA(size+31行业)中性化(105因子)')]

# Round5 起结果直接落 CSV(三组检验 x 多批次), 不再靠解析日志
CSVS = [('round5_fund.csv', 'Round5', '财报/基本面41因子(PIT按公告日对齐)'),
        ('round5b_fund.csv', 'Round5b', '单季口径+业绩超预期12因子'),
        ('round5c_combo.csv', 'Round5c', '盈利/成长复合因子'),
        ('round6_jq.csv', 'Round6', '聚宽JQ indicator/valuation风格因子'),
        ('round7_growth.csv', 'Round7', '基本面成长复合(合成+分段+小市值池内)')]

NAME_RE = re.compile(r'^[A-Za-z_][\w\.]*$')


def parse_row(s):
    """自适应两种表格格式
    A(r1): name ic ic_ir ann_top ann_mkt ann_ex dd sharpe calmar
    B(r2/r3): name ic ic_ir ann_top ann_mkt ann_ex dd calmar pass
    """
    parts = s.split()
    if len(parts) < 6:
        return None
    nm = parts[0]
    if not NAME_RE.match(nm):
        return None
    nums, rest = [], []
    for p in parts[1:]:
        try:
            nums.append(float(p))
        except ValueError:
            rest.append(p)
    if len(nums) < 7:
        return None
    sharpe = nums[6] if len(nums) >= 8 else np.nan
    calmar = nums[7] if len(nums) >= 8 else nums[6]
    return dict(name=nm, ic=nums[0], ic_ir=nums[1], top=nums[2], mkt=nums[3],
                ex=nums[4], dd=nums[5], sharpe=sharpe, calmar=calmar,
                raw=' '.join(rest))


def judge(ic, ex, calmar):
    if abs(ic) < 0.02:
        return '|IC|<0.02'
    if ex <= 0:
        return '超额为负'
    if calmar < 0.5:
        return f'Calmar={calmar:.2f}<0.5'
    return '通过'

def read_log(p):
    """PowerShell '>' 重定向默认写UTF-16, 需自动识别编码"""
    raw = open(p, 'rb').read()
    for enc in ['utf-16', 'utf-16-le', 'utf-8', 'gbk', 'gb18030']:
        try:
            txt = raw.decode(enc)
            if '\x00' not in txt[:2000]:
                return txt
        except Exception:
            continue
    return raw.decode('utf-8', errors='ignore')


rows = []
for fn, rnd, desc in LOGS:
    p = os.path.join(HERE, fn)
    if not os.path.exists(p):
        print(f"缺 {fn}")
        continue
    in_table = False
    n = 0
    for line in read_log(p).splitlines():
        s = line.rstrip()
        if s.strip().startswith('name') and 'ann_ex' in s:
            in_table = True
            continue
        if in_table:
            if s.startswith('=') or not s.strip():
                continue
            m = parse_row(s)
            if m:
                nm = m['name']
                cat, formula, note = get_formula(nm)
                rows.append({
                    '轮次': rnd, '因子': nm, '分类': cat, '公式': formula, '含义': note,
                    'IC': m['ic'], 'IC_IR': m['ic_ir'],
                    'Top组年化': m['top'], '市场年化': m['mkt'],
                    '超额年化': m['ex'], '回撤': m['dd'],
                    'Sharpe': m['sharpe'], 'Calmar': m['calmar'],
                    '判定': judge(m['ic'], m['ex'], m['calmar']),
                })
                n += 1
    print(f"  {fn}: 解析 {n} 个因子")

# ---------- Round5+: 直接读结果 CSV(raw/lnmc/barra 三组) ----------
for fn, rnd, desc in CSVS:
    p = os.path.join(HERE, fn)
    if not os.path.exists(p):
        print(f"缺 {fn}")
        continue
    d = pd.read_csv(p)
    n = 0
    for _, r in d.iterrows():
        nm = str(r['name'])
        tag = r.get('tag', None)
        if isinstance(tag, str) and tag.strip():
            nm = f"{nm}[{tag}]"
        cat, formula, note = get_formula(str(r['name']))
        rows.append({
            '轮次': f"{rnd}-{r['mode']}", '因子': nm, '分类': cat,
            '公式': formula, '含义': note,
            'IC': r['ic'], 'IC_IR': r['ic_ir'],
            'Top组年化': r.get('ann_top', np.nan),
            '市场年化': r.get('ann_mkt', np.nan),
            '超额年化': r['ann_ex'], '回撤': r['dd'],
            'Sharpe': r.get('sharpe', np.nan), 'Calmar': r['calmar'],
            '判定': judge(r['ic'], r['ann_ex'], r['calmar']),
        })
        n += 1
    print(f"  {fn}: 解析 {n} 条")

df = pd.DataFrame(rows)
if not len(df):
    print("无数据")
    sys.exit(0)

# 归档文件放策略目录(all01)根下, 与 factor_roadmap.md 一起供随时复盘
ARCHIVE_DIR = r'd:\rqalpha_demo\strategies\all01'
out_csv = os.path.join(ARCHIVE_DIR, 'factor_archive.csv')
df.to_csv(out_csv, index=False, encoding='utf-8-sig')
print(f"\n已存 {out_csv}  共 {len(df)} 条")

# ---------- Markdown ----------
md = []
md.append('# 因子挖掘档案\n')
md.append('> 检验区间 2018-01 ~ 2026-08(面板2013起); 换仓5日; 成本单边千一; '
          '分组10组取Top组; 基准=可交易池等权\n')
md.append('> 股票池: 非ST/非停牌/上市≥250日/20日均成交额≥1000万/非涨跌停(占比57.9%)\n')
md.append('> 价格: 前复权(与rqalpha动态前复权收益率等价)\n')
md.append('> **口径提示**: Round1~5 的中性化为"先中性化原始因子值再截面排序"(A口径)。'
          '该口径对**财报比率类**(极端值多)不稳定: Round5 盈利因子 A口径 +5%~+8%, '
          '改去极值+z-score(C口径)后全部转负; 量价因子三口径差异<0.15%, 不受影响。'
          '详见 `strategies/all01/factor_roadmap.md`\n')
md.append('\n## 筛选标准(中金11项简化)\n')
md.append('| 条件 | 阈值 |\n|---|---|\n')
md.append('| 绝对值IC | > 0.02 |\n| IC胜率 | > 52% |\n| Calmar | > 0.5 |\n')
md.append('| 最近年度超额 | > 0 |\n| 亏损年份(<-2%) | ≤ 1个 |\n| 与已入库因子IC相关 | < 0.70 |\n')

DESC = {r[1]: r[2] for r in LOGS}
MODES = ['raw', 'lnmc', 'barra', 'strat']
for fn, rnd, desc in CSVS:
    for m in MODES:
        DESC[f'{rnd}-{m}'] = f'{desc} [{m}]'
SEC = [(r[1], r[2]) for r in LOGS]
for fn, rnd, desc in CSVS:
    SEC += [(f'{rnd}-{m}', DESC[f'{rnd}-{m}']) for m in MODES]

for rnd, desc in SEC:
    sub = df[df['轮次'] == rnd].sort_values('超额年化', ascending=False)
    if not len(sub):
        continue
    md.append(f'\n## {rnd}  {desc}\n')
    md.append(f'测试 {len(sub)} 个, 通过 {(sub["判定"]=="通过").sum()} 个\n')
    md.append('| 因子 | 分类 | 公式 | IC | IC_IR | 超额年化 | 回撤 | Calmar | 判定 |\n')
    md.append('|---|---|---|---|---|---|---|---|---|\n')
    for _, r in sub.iterrows():
        md.append(f"| {r['因子']} | {r['分类']} | `{r['公式']}` | {r['IC']:+.4f} | "
                  f"{r['IC_IR']:+.3f} | {r['超额年化']*100:+.2f}% | {r['回撤']*100:.1f}% | "
                  f"{r['Calmar']:.2f} | {r['判定']} |\n")

md.append('\n## 关键结论\n')
md.append('1. **小市值 ln_mktcap 是最强单因子**(超额+6.88%), 但IC仅0.026 —— '
          'IC排序与分组超额不一致, 不能用IC挑因子\n')
md.append('2. **小成交额族**(amt_log/amt_std)超额+3.4~3.8%, 与市值高度相关\n')
md.append('3. **低波动类因子在A股无效**(Top组-12%~-14%), 与美股相反, A股给高弹性溢价\n')
md.append('4. **资金流因子全部无效**(IC<0.01, 超额-5%~-7%)\n')
md.append('5. **市值中性化后93个因子通过0个** —— 所有量价因子的预测力几乎全部来自市值暴露\n')
md.append('6. 多因子等权合成反而跑输单因子(TOP5等权-2.27%), 因混入大量无效因子\n')
md.append('7. **Round5 财报批次(53因子)通过0个**: 估值类 IC 0.02~0.035 但超额为负; '
          '成长/质量类 IC<0.01 无效; 盈利类在"先中性化原始值"口径下 +5%~+8%, '
          '**改用去极值+z-score标准口径后全部转负(-2.3%~-3.0%, 属极端值假象)**\n')
md.append('8. **中性化口径坑**: 财报比率类极端值多, 必须先去极值+z-score 再中性化; '
          '量价因子不受影响(三口径差<0.15%), 故结论1~6 不受影响\n')
md.append('9. **唯一稳健正信号**: 单季成长复合 `combo_growth`(BARRA中性后 +4.02%, '
          '回撤-7.1%, Calmar 0.57), 仅因 IC=0.0142<0.02 未过门槛; '
          '单季口径明显优于YTD累计口径(+4.31% vs -1.37%)\n')

out_md = os.path.join(ARCHIVE_DIR, 'factor_archive.md')
with open(out_md, 'w', encoding='utf-8') as f:
    f.write(''.join(md))
print(f"已存 {out_md}")

print("\n各轮通过数:")
print(df.groupby('轮次')['判定'].apply(lambda s: (s == '通过').sum()).to_string())
print("\n超额年化 Top10:")
print(df.sort_values('超额年化', ascending=False)[
    ['轮次', '因子', '公式', 'IC', '超额年化', 'Calmar']].head(10).to_string(index=False))
