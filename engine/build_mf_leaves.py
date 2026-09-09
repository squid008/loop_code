# -*- coding: utf-8 -*-
"""
一期: 资金流原始拆分入叶 —— moneyflow3(E:\\rq\\moneyflow3) → panel.h5
======================================================================
moneyflow3 原始 16 列 = {小s/中m/大l/特大x} × 买b/卖s × {量q(手)/额a(万元)}。
设计决策(v2, 用户评审):
  1. 净额不预焊: 只给原始买/卖拆分列, 挖掘器自行 add/sub/div 组合;
  2. 单位统一到与量价面板一致: 金额 万元→元(×1e4, 与 turnover 同量纲 A),
     量 手→股(×100, 与 volume 同量纲 V), 保证跨量纲审查语义正确;
  3. 停牌/无记录日 fill 0(当日无成交资金流=0), 未上市/已退市区(close NaN) 保持 NaN;
  4. imputed 反推掩码(抽检=0%)仅作日志, 不入列。

旧列 mf_net/mf_xl/mf_net_r/mf_xl_r(净额预焊版) 移除。
新列命名(金额=元 A / 量=股 V):
  mf_{s,m,l,x}_{buy,sell}        金额列 ×1e4 (A)
  mf_{s,m,l,x}_{bqty,sqty}       量列   ×100 (V)
"""
import os
import time
import h5py
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
PANEL = os.path.join(HERE, 'panel.h5')
MF = r'E:\rq\moneyflow3'

# 源字段 → 新叶子名(买额/卖额/买量/卖量 四组, 每档)
# 命名规则: mf_档位_方向(_qty=量, 默认金额)
_BUY_A = {'s': 'mf_s_buy', 'm': 'mf_m_buy', 'l': 'mf_l_buy', 'x': 'mf_x_buy'}
_SELL_A = {'s': 'mf_s_sell', 'm': 'mf_m_sell', 'l': 'mf_l_sell', 'x': 'mf_x_sell'}
_BUY_Q = {'s': 'mf_s_bqty', 'm': 'mf_m_bqty', 'l': 'mf_l_bqty', 'x': 'mf_x_bqty'}
_SELL_Q = {'s': 'mf_s_sqty', 'm': 'mf_m_sqty', 'l': 'mf_l_sqty', 'x': 'mf_x_sqty'}
SRC2LEAF = {}
for g, rng in ((_BUY_A, ('s_ba', 'm_ba', 'l_ba', 'x_ba')),
               (_SELL_A, ('s_sa', 'm_sa', 'l_sa', 'x_sa')),
               (_BUY_Q, ('s_bq', 'm_bq', 'l_bq', 'x_bq')),
               (_SELL_Q, ('s_sq', 'm_sq', 'l_sq', 'x_sq'))):
    for (tier, leaf), src in zip(g.items(), rng):
        SRC2LEAF[src] = leaf
MUL = {src: (1e4 if src.endswith(('_ba', '_sa')) else 100.0)
       for src in SRC2LEAF}   # 额 万→元; 量 手→股

t0 = time.time()
with pd.HDFStore(PANEL, 'r') as st:
    close = st['close']
    old = list(st.keys())
nd, nc = close.shape
dates = np.asarray(close.index, dtype=np.int64)
cols = list(close.columns)
di = {int(d): i for i, d in enumerate(dates)}
ci = {c: i for i, c in enumerate(cols)}
cmask = close.notna().values
print(f"panel: {nd} 日 x {nc} 股  close NaN={cmask.mean()*100:.2f}%")
print(f"旧 panel keys: {old}")

# 读 sid 映射
with h5py.File(os.path.join(MF, 'sid.h5'), 'r') as f:
    sid2code = np.array([x.decode() if isinstance(x, bytes) else str(x)
                         for x in f['sid'][:]])
print(f"moneyflow sid 池: {len(sid2code)}  (panel 股票 {nc})")

# 输出缓冲 (float32, 每新列一张 (nd x nc))
out = {leaf: np.full((nd, nc), np.nan, dtype=np.float32) for leaf in SRC2LEAF.values()}
miss_code = np.zeros(nc, dtype=int)

for y in range(2013, 2027):
    p = os.path.join(MF, f'mf_{y}.h5')
    if not os.path.exists(p):
        continue
    with h5py.File(p, 'r') as f:
        d = f['data'][:]
    dn = d['date'].astype(np.int64)
    codes = sid2code[d['sid']]
    # date -> 行位置 / code -> 行位置(向量化查表)
    dpos = np.array([di.get(x, -1) for x in dn], dtype=np.int64)
    cpos = np.empty(len(codes), dtype=np.int64)
    for i, c in enumerate(codes):
        cpos[i] = ci.get(c, -1)
    m = (dpos >= 0) & (cpos >= 0)
    dp, cp = dpos[m], cpos[m]
    miss_code += np.bincount(cp, minlength=nc)
    for src, leaf in SRC2LEAF.items():
        v = d[src][m].astype(np.float64) * MUL[src]
        out[leaf][dp, cp] = v.astype(np.float32)
    print(f"  {y}: {len(d):,} 行(有效 {m.sum():,})  {time.time()-t0:.0f}s")
    del d

# 停牌(close 有效但无资金流记录) fill 0; 未上市/退市区保持 NaN
for leaf, a in out.items():
    nan = ~np.isfinite(a)
    a[nan & cmask] = 0.0
print(f"覆盖外股票列数(panel 有但 moneyflow 从未出现): {(miss_code==0).sum()}/{nc}")

# ---- 勾稽校验(全市场 买入≈卖出, 单位: 万元? 此处已×1e4 为元) ----
buy_sum = np.zeros(nd); sell_sum = np.zeros(nd)
for src in ('s_ba', 'm_ba', 'l_ba', 'x_ba'):
    buy_sum += np.nansum(out[SRC2LEAF[src]], axis=1)
for src in ('s_sa', 'm_sa', 'l_sa', 'x_sa'):
    sell_sum += np.nansum(out[SRC2LEAF[src]], axis=1)
ratio = np.nanmedian(np.abs(buy_sum - sell_sum) / np.maximum(buy_sum, 1))
print(f"勾稽: |买-卖|/买 全市场日度中位 = {ratio*100:.3f}% (源数据零和缺陷应<2%)")

# ---- 写回 panel.h5 (移除旧净额 4 列) ----
REMOVE = ('mf_net', 'mf_xl', 'mf_net_r', 'mf_xl_r')
with pd.HDFStore(PANEL, 'a', complib='blosc', complevel=5) as st:
    for k in REMOVE:
        if k in st:
            st.remove(k)
            print(f"  移除旧列 {k}")
    for leaf, a in out.items():
        if leaf in st:
            st.remove(leaf)
        st[leaf] = pd.DataFrame(a, index=close.index, columns=cols)
    print("已写入 16 列: ", list(SRC2LEAF.values()))
print(f"\n总耗时 {time.time()-t0:.0f}s")
with pd.HDFStore(PANEL, 'r') as st:
    print("panel.h5 现有:", list(st.keys()))
