# -*- coding: utf-8 -*-
"""
详细分解 —— 「观测加权」与「日截面」两种统计口径为何会给出完全不同的数字。

背景:
    rqalpha 本地:  观测加权 触发 3.3714% / 未触发 0.6630%
                  日截面   触发 -0.0764% / 未触发 0.6791%
    qlib 抽样1500: 日截面   触发 0.3971% / 未触发 0.8193%
    qlib 前端:     日截面   触发 0.498%  / 未触发 0.770%
本脚本把两种口径的数学定义、逐日权重、贡献分解逐项算出。
"""
import os
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd
import h5py
from test import compute_one, STOCKS_H5

START, END, FWD = 20210101, 20260812, 20
WARMUP = 120

print("=" * 104)
print("一、两种口径的数学定义")
print("=" * 104)
print("""
  设第 t 个交易日的触发样本数为 n_t，该日触发组的平均 20 日收益为 m_t；
  有触发样本的交易日共 T 天，触发样本总数 N = Σ n_t。

  【观测加权 pooled】—— 把所有样本混在一起求平均
        M_pooled = (Σ n_t·m_t) / (Σ n_t) = Σ (n_t / N)·m_t
        第 t 天的权重  w_t = n_t / N          ← 样本越多的日子，权重越高

  【日截面 daily】—— 先每天内部平均，再把「天」当样本求平均
        M_daily  = (Σ m_t) / T = Σ (1 / T)·m_t
        第 t 天的权重  w_t = 1 / T            ← 每天等权，与该日样本数无关

  ⇒ 只有当每天的触发数 n_t 都相等、或 m_t 与 n_t 无关时，两者才会相等。
     本因子恰恰是「信号扎堆在少数几天，且那几天收益极高」，于是两者严重背离。
""")

# ---------------- 加载 ----------------
t0 = __import__('time').time()
with h5py.File(STOCKS_H5, 'r') as f:
    keys = list(f.keys())
    base_dates = (f['000001.XSHE']['datetime'][:] // 1000000).astype('int64')
pos = int(np.searchsorted(base_dates, START))
data_start = base_dates[max(0, pos - WARMUP)]
print(f"数据加载: {len(keys)} 只, 读取起点 {data_start}")

parts = []
with h5py.File(STOCKS_H5, 'r') as f:
    for obid in keys:
        arr = f[obid][:]
        d = arr['datetime'] // 1000000
        m = (d >= data_start) & (d <= END)
        if m.sum() < WARMUP // 2:
            continue
        df = compute_one(arr[m], drop_suspended=False, fwd=FWD)
        df['obid'] = obid
        parts.append(df[(df['date'] >= START) & (df['date'] <= END)])
keep = pd.concat(parts, ignore_index=True)
print(f"样本行 {len(keep):,}，耗时 {__import__('time').time()-t0:.0f}s")

sub = keep[['date', 'signal', 'fwd_t1_21']].dropna()
trig = sub[sub['signal']]
notr = sub[~sub['signal']]
N = len(trig)
T = trig['date'].nunique()
print(f"触发样本 N={N:,}，有触发的交易日 T={T:,}")

# ---------------- 逐日统计 ----------------
by_day = trig.groupby('date')['fwd_t1_21'].agg(['size', 'mean'])
by_day.columns = ['n_t', 'm_t']
by_day['w_pooled'] = by_day['n_t'] / N
by_day['w_daily'] = 1.0 / T
by_day['contrib_pooled'] = by_day['w_pooled'] * by_day['m_t']
by_day['contrib_daily'] = by_day['w_daily'] * by_day['m_t']
by_day = by_day.sort_values('n_t', ascending=False)

print("\n" + "=" * 104)
print("二、逐日权重对比（信号最集中的 15 天）")
print("=" * 104)
print(f"  {'日期':<10}{'触发数n_t':>10}{'当日均值m_t':>13}"
      f"{'权重·观测加权':>15}{'权重·日截面':>14}{'倍数':>9}")
print("-" * 104)
for d, r in by_day.head(15).iterrows():
    print(f"  {d:<10}{int(r['n_t']):>10}{r['m_t']*100:>12.2f}%"
          f"{r['w_pooled']*100:>14.3f}%{r['w_daily']*100:>13.3f}%"
          f"{r['w_pooled']/r['w_daily']:>8.1f}x")
print("-" * 104)
h = by_day.head(15)
print(f"  {'前15天合计':<10}{int(h['n_t'].sum()):>10}{'':>13}"
      f"{h['w_pooled'].sum()*100:>14.2f}%{h['w_daily'].sum()*100:>13.2f}%")

print(f"\n  每日触发数分布:")
print(f"    均值={by_day['n_t'].mean():.1f}  中位={by_day['n_t'].median():.0f}  "
      f"最大={by_day['n_t'].max()}  最小={by_day['n_t'].min()}")
print(f"    触发数 ≤5 只的交易日: {(by_day['n_t'] <= 5).sum()} 天 "
      f"(占 {T} 天的 {(by_day['n_t'] <= 5).mean()*100:.1f}%)，"
      f"但这些天在日截面里占同样权重")

# ---------------- 贡献分解 ----------------
print("\n" + "=" * 104)
print("三、贡献分解：3.37% 与 -0.08% 分别是怎么加出来的")
print("=" * 104)
M_pooled = (by_day['n_t'] * by_day['m_t']).sum() / N
M_daily = by_day['m_t'].mean()
print(f"\n  观测加权 M_pooled = {M_pooled*100:.4f}%")
print(f"  日截面   M_daily  = {M_daily*100:.4f}%")
print(f"  两者相差 {(M_pooled-M_daily)*100:.4f} 个百分点\n")

for K in (5, 10, 20):
    top = by_day.head(K)
    rest = by_day.iloc[K:]
    tp = (top['n_t'] * top['m_t']).sum() / N
    rp = (rest['n_t'] * rest['m_t']).sum() / N
    td = top['m_t'].mean() * (K / T)
    rd = rest['m_t'].mean() * (len(rest) / T)
    print(f"  ── 按「信号最多的前 {K} 天」切分 ──")
    print(f"     观测加权: 前{K}天 权重{top['w_pooled'].sum()*100:5.2f}% × 均值{top['m_t'].mean()*100:6.2f}% "
          f"= {tp*100:+6.3f}%")
    print(f"               其余天 权重{rest['w_pooled'].sum()*100:5.2f}% × 均值{rest['m_t'].mean()*100:6.2f}% "
          f"= {rp*100:+6.3f}%   合计 {M_pooled*100:+.3f}%")
    print(f"     日截面  : 前{K}天 权重{K/T*100:5.2f}% × 均值{top['m_t'].mean()*100:6.2f}% "
          f"= {td*100:+6.3f}%")
    print(f"               其余天 权重{len(rest)/T*100:5.2f}% × 均值{rest['m_t'].mean()*100:6.2f}% "
          f"= {rd*100:+6.3f}%   合计 {M_daily*100:+.3f}%")
    print()

print("  结论: 信号最多的少数几天，m_t 显著高于其余天（例如前 10 天均值 "
      f"{by_day.head(10)['m_t'].mean()*100:.2f}% vs 其余 {by_day.iloc[10:]['m_t'].mean()*100:.2f}%）。")
print("        观测加权给它们 ~13% 的权重，日截面只给 ~0.8%，于是结果天差地别。")

# ---------------- 未触发组 ----------------
n_by_day = notr.groupby('date')['fwd_t1_21'].agg(['size', 'mean'])
print("\n" + "=" * 104)
print("四、为什么「未触发组」两种口径差别不大")
print("=" * 104)
Nn = len(notr)
Tn = n_by_day.shape[0]
n_by_day['w_pooled'] = n_by_day['size'] / Nn
print(f"  未触发样本 {Nn:,}，交易日 {Tn}")
print(f"  每日未触发数: 均值={n_by_day['size'].mean():.0f}  中位={n_by_day['size'].median():.0f}  "
      f"最小={n_by_day['size'].min()}  最大={n_by_day['size'].max()}")
print(f"  观测加权 = {(n_by_day['size']*n_by_day['mean']).sum()/Nn*100:.4f}%")
print(f"  日截面   = {n_by_day['mean'].mean()*100:.4f}%")
print("\n  ⇒ 未触发组每天样本数都在数千只、分布均匀（n_t 近似常数），")
print("     所以 n_t/N ≈ 1/T，两种口径自然收敛 —— 这正是两组数字能对上的原因。")

# ---------------- 涨停剔除的影响 ----------------
print("\n" + "=" * 104)
print("五、叠加 qlib 默认的三重剔除后，日截面如何变化")
print("=" * 104)
lu_t, lu_t1, sp_t1 = keep['is_lu'], keep['is_lu_t1'], keep['susp_t1']
combos = [
    ('不剔除', pd.Series(False, index=keep.index)),
    ('剔除T涨停', lu_t),
    ('+T+1涨停', lu_t | lu_t1),
    ('qlib完整口径(再+T+1停牌)', lu_t | lu_t1 | sp_t1),
]
print(f"  {'口径':<30}{'触发样本':>10}{'观测加权':>11}{'日截面':>11}{'未触发日截面':>14}")
print("-" * 104)
for name, ex in combos:
    d = keep[~ex]
    t2 = d[d['signal'] & d['fwd_t1_21'].notna()]
    n2 = d[~d['signal'] & d['fwd_t1_21'].notna()]
    if not len(t2):
        continue
    pooled = t2['fwd_t1_21'].mean() * 100
    dm = t2.groupby('date')['fwd_t1_21'].mean()
    dn = n2.groupby('date')['fwd_t1_21'].mean()
    print(f"  {name:<30}{len(t2):>10,}{pooled:>10.4f}%{dm.mean()*100:>10.4f}%{dn.mean()*100:>13.4f}%")

print("\n" + "=" * 104)
print("六、与 qlib 前端数字对照")
print("=" * 104)
print(f"  {'来源':<34}{'触发组(日截面)':>16}{'未触发组(日截面)':>18}")
print("-" * 104)
print(f"  {'rqalpha全量 5403只(本脚本)':<34}{M_daily*100:>15.4f}%{n_by_day['mean'].mean()*100:>17.4f}%")
print(f"  {'qlib 抽样1500只':<34}{0.3971:>15.4f}%{0.8193:>17.4f}%")
print(f"  {'qlib 前端显示':<34}{0.498:>15.4f}%{0.770:>17.4f}%")
print("\n  三者同为「日截面」口径，未触发组 0.68~0.82 彼此接近；")
print("  触发组差异(0.68 / 0.40 / 0.50)来自: 股票池范围、是否做剔除、以及")
print("  日截面对「小样本日」高度敏感（中位每天仅数只，个别天的 m_t 波动极大）。")
