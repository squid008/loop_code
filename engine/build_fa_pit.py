# -*- coding: utf-8 -*-
"""
二期: 财报 PIT as-of 展开入叶 —— E:\\rq\\finance\\pit\\*.h5 → fa_pit.h5
======================================================================
PIT 实测结构: 每股票 h5 = keys{fields(组,~394科目)/if_adjusted/info_date/quarter/rice_create_tm}
无 ann_date。同 report_period(quarter) 存在多条版本行(首次披露 + 后续每份报告带一版修正,
同一 (quarter, info_date) 唯一)。=> 版本链规则(t 日可见值 = 该报告期 info_date≤t 的最新版本),
本实现逐事件推进、按季度区间填充, 严格无未来函数。

产出 8 个 R 量纲比值叶子(quarter 为最新已披露报告期 q*):
  fa_np_yoy    净利润TTM 同比  (net_profitTTM q* / q*-4)
  fa_rev_yoy   营业总收入TTM 同比
  fa_op_yoy    营业利润TTM 同比
  fa_ocf_yoy   经营现金流TTM 同比
  fa_gm        毛利率 (gross_profitTTM / 营业总收入TTM; 银行无毛利=NaN)
  fa_np_margin 净利率 (net_profitTTM / 营业总收入TTM)
  fa_roe       净资产收益率 (net_profitTTM / 归母权益)
  fa_lev       资产负债率 (总负债/总资产)
说明: 不注册绝对额/绝对股本等非 R 量纲; 资产负债表科目天然 NaN(银行部分)交截面排序丢弃。
"""
import os
import glob
import time
import h5py
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
PANEL = os.path.join(HERE, 'panel.h5')
OUT = os.path.join(HERE, 'fa_pit.h5')
PIT = r'E:\rq\finance\pit'

# 核心输入科目(TTM 字段为 RQ 已算好的 12 月滚动值, 避开 YTD 拼接)
CORE = ['net_profitTTM', 'operating_revenueTTM', 'gross_profitTTM',
        'operating_profitTTM', 'net_operate_cashflowTTM',
        'equity_parent_company', 'total_liabilities', 'total_assets']
# (因子, 计算函数(core array / q* / q*-4 值))
# core 向量按 CORE 索引
def _fact(c, q, q4):
    np_, rev, gp, op, ocf, eq, tl, ta = c  # q* 期 core
    np4, rev4, op4, ocf4 = q4[[0, 1, 3, 4]] if q4 is not None else (np.nan,) * 4
    out = {}
    out['fa_np_yoy'] = np_ / np4 - 1
    out['fa_rev_yoy'] = rev / rev4 - 1
    out['fa_op_yoy'] = op / op4 - 1
    out['fa_ocf_yoy'] = ocf / ocf4 - 1
    out['fa_gm'] = gp / rev
    out['fa_np_margin'] = np_ / rev
    out['fa_roe'] = np_ / eq
    out['fa_lev'] = tl / ta
    return out

with pd.HDFStore(PANEL, 'r') as st:
    close = st['close']
dates = np.asarray(close.index, dtype=np.int64)
nd = len(dates)
cols = list(close.columns)
colpos = {c: i for i, c in enumerate(cols)}
FA_KEYS = ['fa_np_yoy', 'fa_rev_yoy', 'fa_op_yoy', 'fa_ocf_yoy',
           'fa_gm', 'fa_np_margin', 'fa_roe', 'fa_lev']
print(f"坐标: {nd} 日 x {len(cols)} 股")

files = sorted(glob.glob(os.path.join(PIT, '*.h5')))
print(f"pit 文件数: {len(files)}")

t0 = time.time()
outs = {k: [] for k in FA_KEYS}
codes_out = []
n_ok = 0
for fi, fp in enumerate(files):
    code = os.path.basename(fp)[:-3]
    if code not in colpos:
        continue
    with h5py.File(fp, 'r') as f:
        g = f['fields']
        have = [c in g for c in CORE]
        if not all(have):
            continue
        core_raw = np.stack([g[c][:].astype(np.float64) for c in CORE], axis=1)  # (n, 8)
        # quarter -> qkey(年*4+季-1), 只保 1990q1 起
        qs = [x.decode('utf-8', 'replace') if isinstance(x, bytes) else str(x)
              for x in f['quarter'][:]]
        infos = [x.decode('utf-8', 'replace') if isinstance(x, bytes) else str(x)
                 for x in f['info_date'][:]]
    n = len(qs)
    qk = np.empty(n, dtype=np.int64)
    ok = np.ones(n, dtype=bool)
    for i, s in enumerate(qs):
        try:
            y, qq = s.split('q')
            qk[i] = int(y) * 4 + int(qq) - 1
        except Exception:
            ok[i] = False
    info = np.empty(n, dtype=np.int64)
    for i, s in enumerate(infos):
        try:
            info[i] = int(s.replace('-', ''))
        except Exception:
            ok[i] = False
    if not ok.any():
        continue
    core_raw, qk, info = core_raw[ok], qk[ok], info[ok]
    # 剔除超出面板日期范围(晚于最后交易日) 的事件
    fin = info <= int(dates[-1])
    core_raw, qk, info = core_raw[fin], qk[fin], info[fin]
    if not len(info):
        continue

    # 事件按生效交易日(公告日后一交易日) 排序推进
    pos = np.searchsorted(dates, info, side='right')          # 0..nd, =nd 若晚于末日(已滤)
    order = np.argsort(pos, kind='stable')
    pos, core_raw, qk = pos[order], core_raw[order], qk[order]

    out = np.full((8, nd), np.nan, dtype=np.float32)
    val = {}          # qkey -> core(8,)
    qmax = -1
    snap = np.full(8, np.nan)
    prev, i, nn = 0, 0, len(pos)
    while i < nn:
        p = int(pos[i])
        if p > prev:
            out[:, prev:p] = snap[:, None]
        p_end = p
        while i < nn and pos[i] == p_end:
            q, v = int(qk[i]), core_raw[i]
            np_ = np.asarray(v)
            np_.ravel()[~np.isfinite(np_)] = np.nan
            val[q] = np_
            if q > qmax:
                qmax = q
            i += 1
        if qmax >= 0:
            c = val[qmax]
            q4 = val.get(qmax - 4)
            if q4 is None:
                c4 = None
            else:
                c4 = q4
            snap = np.array([_fact(c, qmax, c4)[k] for k in FA_KEYS])
            snap[~np.isfinite(snap)] = np.nan
        else:
            snap = np.full(8, np.nan)
        prev = p_end
    out[:, prev:] = snap[:, None]
    for j, k in enumerate(FA_KEYS):
        outs[k].append(out[j])
    codes_out.append(code)
    n_ok += 1
    if (fi + 1) % 800 == 0:
        print(f"  {fi+1}/{len(files)}  n_ok={n_ok}  {time.time()-t0:.0f}s")

print(f"有效股票: {n_ok}   耗时 {time.time()-t0:.0f}s")

with pd.HDFStore(OUT, 'w', complib='blosc', complevel=5) as st:
    for k in FA_KEYS:
        df = pd.DataFrame(np.stack(outs[k], axis=1), index=close.index, columns=codes_out)
        st[k] = df.astype('float32')
        v = np.asarray(df.values)
        print(f"  {k:14s} {df.shape}  NaN={np.isnan(v).mean()*100:.1f}%"
              f"   |IC备检| 中位={np.nanmedian(v):.4f}")
print(f"\n已存 {OUT}   {time.time()-t0:.0f}s")

# sanity: 000001 银行 资产负债率应~0.9, gm 应全 NaN
with pd.HDFStore(OUT, 'r') as st:
    c = st['fa_lev']['000001.XSHE']
    c2 = st['fa_gm']['000001.XSHE']
print(f"\nsanity 000001 fa_lev 2016中位={np.nanmedian(c[c.index<20170101]):.3f}"
      f" (期望~0.9)  gm NaN={c2.isna().sum()/len(c2)*100:.0f}% (期望~100)")
