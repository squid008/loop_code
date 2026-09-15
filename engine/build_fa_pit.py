# -*- coding: utf-8 -*-
"""
财报 PIT as-of 展开入叶 —— E:\\rq\\finance\\pit\\*.h5 → fa_pit.h5
======================================================================
PIT 实测结构: 每股票 h5 = keys{fields(组,~394科目)/if_adjusted/info_date/quarter/rice_create_tm}
无 ann_date。同 report_period(quarter) 存在多条版本行(首次披露 + 后续每份报告带一版修正,
同一 (quarter, info_date) 唯一)。=> 版本链规则(t 日可见值 = 该报告期 info_date≤t 的最新版本),
本实现逐事件推进、按季度区间填充, 严格无未来函数。

## 产出（2026-09-15 扩展：8 → **20** 个叶子）

### 原有 8 个（**公式自 2026-09-09 起未改动，逐字节保留**）
  fa_np_yoy    净利润TTM 同比      fa_rev_yoy   营业总收入TTM 同比
  fa_op_yoy    营业利润TTM 同比    fa_ocf_yoy   经营现金流TTM 同比
  fa_gm        毛利率              fa_np_margin 净利率
  fa_roe       净资产收益率        fa_lev       资产负债率

### ★ 新增 7 个（2026-09-15，用户问起「财报数据不是有一堆吗」）
  fa_pb         **PB**（= 归母权益 / 总市值，**按日 mktcap** ⇒ 见下方「为什么它要特殊处理」）
                ★★ 实测**最独立**：与所有旧叶子的截面 rank 相关最高才 **+0.063** ✓
  fa_accrual    **盈利质量** net_operate_cashflowTTM / net_profitTTM（识别"利润有没有现金支撑"）
  fa_asset_turn **资产周转率** operating_revenueTTM / total_assets
  fa_gw         **商誉占比** goodwill / total_assets（减值风险）
  fa_inv_turn   存货周转 operating_revenueTTM / inventory
  fa_recv_turn  应收周转 operating_revenueTTM / bill_accts_receivable
  fa_sell_exp   销售费用率 selling_expense / operating_revenueTTM

### ⚠ 试过但**删掉**的 5 个（两类原因，都实测过）
**(a) 覆盖率不够**（判据：近 3 年 < 30% ⇒ 截面样本太少，IC 极不稳）
  ✗ fa_int_cov   利息保障 ebitTTM/interest_expense —— 有效 **0.01%**
  ✗ fa_rnd       研发/营收（`rnd_to_revenue`）—— 有效 **9.95%**（研发披露不全）
  ✗ fa_rnd_cap   资本化研发比例（`capitalized_rnd_ratio`）—— 有效 **2.29%**
  ⇒ 现实：A 股研发/利息科目**普遍不披露**（非全量强制）⇒ 这两族暂时做不了 ⚠
**(b) 信息重复**（判据：与既有叶子的**逐日截面 rank 相关** > 0.85）
  ✗ fa_roe_wa    **加权平均 ROE**（源 `return_on_equity_weighted_average`）
     · 与 `fa_roe` 截面相关 **+0.855** ⇒ 重复 ✗
     · ⚠ 且**口径是「报告期累积」不是 TTM**（实测按月底截面中位：Q1 0.015 → 中报 0.018
       → Q3 0.037 → 年报 0.053 呈阶梯）⇒ **`ts_delta` 会读出"假变化"** ⚠
     · 而 `fa_roe` 已是 TTM（无锯齿）⇒ **留 `fa_roe` 更干净** ✓
     （量表：源是**百分数**，平安银行 2016 = 11.02 vs 自算 0.1190 —— 若要重启用须 /100）
  ✗ fa_roa       总资产收益率 np/TT / total_assets —— 与 `fa_np_margin` 截面相关 **+0.867** ⇒ 重复 ✗
     （且 `fa_roe_wa ~ fa_roa = 0.807` ⇒ roe/roe_wa/roa/np_margin 是**同一族**）

### ★★ 判重复用**逐日截面 rank 相关**，不用 pooled
  pooled（全样本堆一起）会**虚高** —— 它混进了"跨时间的水平变化"（如全市场 ROE 逐年下滑），
  而那部分**截面选股用不到**；引擎的 IC/组合都是**同日截面比较** ⇒ 必须用截面口径 ✓
  （自检：旧的那两对"已知偏高"测得截面 `fa_np_yoy~fa_op_yoy=+0.877`、
   `fa_np_margin~fa_roe=+0.762`，与独立算法一致 ✓）

### ★★ 为什么 `fa_pb` 要特殊处理
  其它 6 个都是"**每个报告期一个数**"（`snap` 常量），而 PB 的分母 `mktcap` **是日变的**
  ⇒ 必须在**按日填充**时算，不能进 `_fact` 的标量返回 ✓

## 设计决定（沿用，勿轻易改）
1. ★ **只注册 R 量纲（比率）**，不收绝对额/绝对股本 —— 绝对额与 `mktcap` 强相关，
   挖出来是"规模因子"，与已有 `barra_size`/`ln_mktcap` 重复 ✗
2. ★★ **2026-09-15 修：科目缺失改为「容忍」** ——
   旧版 `if not all(have): continue` ⇒ **任一新科目缺失就整只股票被跳过** ⇒ 覆盖率暴跌 ⚠
   现在：缺的科目置 NaN，**其余照算**（`interest_expense`/`inventory` 对部分公司天然没有）✓
3. ★★ **为什么 `fa_pb` 要特殊处理**：其它 19 个都是"**每个报告期一个数**"（`snap` 常量），
   而 PB 的分母 `mktcap` **是日变的** ⇒ 必须在**按日填充**时算，不能进 `_fact` 的标量返回 ✓
4. ★ 资产负债表科目对银行/保险天然 NaN（无毛利/存货/应收）⇒ 交截面排序丢弃（可接受）✓
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

# ---- 核心输入科目（TTM 字段为 RQ 已算好的 12 月滚动值, 避开 YTD 拼接）----
CORE8 = ['net_profitTTM', 'operating_revenueTTM', 'gross_profitTTM',
         'operating_profitTTM', 'net_operate_cashflowTTM',
         'equity_parent_company', 'total_liabilities', 'total_assets']
CORE_NEW = [
    # 派生比率所需的科目
    'goodwill', 'inventory', 'bill_accts_receivable', 'selling_expense',
]
CORE = CORE8 + CORE_NEW
CI = {c: i for i, c in enumerate(CORE)}          # ★ 按名字索引，不再硬编码位置

# ---- 输出叶子（顺序 = 写入 h5 的顺序）----
FA8 = ['fa_np_yoy', 'fa_rev_yoy', 'fa_op_yoy', 'fa_ocf_yoy',
       'fa_gm', 'fa_np_margin', 'fa_roe', 'fa_lev']
FA_NEW = ['fa_pb', 'fa_accrual', 'fa_asset_turn', 'fa_gw',
          'fa_inv_turn', 'fa_recv_turn', 'fa_sell_exp']
FA_KEYS = FA8 + FA_NEW
PB_IDX = FA_KEYS.index('fa_pb')                  # ★ PB 特殊处理（按日 mktcap）


def _g(c, k):
    """从 core 向量按名字取值（缺科目 ⇒ NaN）。"""
    return c[CI[k]]


def _safe(a, b):
    """a/b，任何一边非有限 ⇒ NaN（不产生 inf）。"""
    with np.errstate(invalid='ignore', divide='ignore'):
        r = a / b
    return r if np.isfinite(r) else np.nan


def _fact(c, q4):
    """由 q* 期 core 向量（及 q*-4 期的）算出**全部标量型**比率。

    :param c:  q* 期 core 向量（长度 = len(CORE)，缺科目为 NaN）
    :param q4: q*-4 期 core 向量（可为 None）
    :return: dict {叶子名: 标量}
    """
    np_, rev, gp, op, ocf = _g(c, 'net_profitTTM'), _g(c, 'operating_revenueTTM'), \
        _g(c, 'gross_profitTTM'), _g(c, 'operating_profitTTM'), \
        _g(c, 'net_operate_cashflowTTM')
    eq, tl, ta = _g(c, 'equity_parent_company'), _g(c, 'total_liabilities'), \
        _g(c, 'total_assets')
    out = {}
    # ==================== 原有 8 个：公式**逐字未改** ====================
    if q4 is None:
        np4 = rev4 = op4 = ocf4 = np.nan
    else:
        np4, rev4, op4, ocf4 = (_g(q4, 'net_profitTTM'), _g(q4, 'operating_revenueTTM'),
                                _g(q4, 'operating_profitTTM'),
                                _g(q4, 'net_operate_cashflowTTM'))
    out['fa_np_yoy'] = _safe(np_, np4) - 1 if np.isfinite(_safe(np_, np4)) else np.nan
    out['fa_rev_yoy'] = _safe(rev, rev4) - 1 if np.isfinite(_safe(rev, rev4)) else np.nan
    out['fa_op_yoy'] = _safe(op, op4) - 1 if np.isfinite(_safe(op, op4)) else np.nan
    out['fa_ocf_yoy'] = _safe(ocf, ocf4) - 1 if np.isfinite(_safe(ocf, ocf4)) else np.nan
    out['fa_gm'] = _safe(gp, rev)
    out['fa_np_margin'] = _safe(np_, rev)
    out['fa_roe'] = _safe(np_, eq)
    out['fa_lev'] = _safe(tl, ta)
    # ==================== ★ 新增 7 个 ====================
    out['fa_accrual'] = _safe(ocf, np_)
    out['fa_asset_turn'] = _safe(rev, ta)
    out['fa_gw'] = _safe(_g(c, 'goodwill'), ta)
    out['fa_inv_turn'] = _safe(rev, _g(c, 'inventory'))
    out['fa_recv_turn'] = _safe(rev, _g(c, 'bill_accts_receivable'))
    out['fa_sell_exp'] = _safe(_g(c, 'selling_expense'), rev)
    out['fa_pb'] = np.nan          # ★ 占位：真正计算在按日填充处（分母 mktcap 日变）
    return out


def main():
    with pd.HDFStore(PANEL, 'r') as st:
        close = st['close']
        mk_all = st['mktcap']                     # ★ PB 用（按日）
    dates = np.asarray(close.index, dtype=np.int64)
    nd = len(dates)
    cols = list(close.columns)
    colpos = {c: i for i, c in enumerate(cols)}
    print('坐标: %d 日 x %d 股' % (nd, len(cols)))
    print('叶子 %d 个（原 %d + 新 %d）' % (len(FA_KEYS), len(FA8), len(FA_NEW)))

    files = sorted(glob.glob(os.path.join(PIT, '*.h5')))
    print('pit 文件数: %d' % len(files))

    t0 = time.time()
    outs = {k: [] for k in FA_KEYS}
    codes_out = []
    n_ok = n_skip_col = n_miss_any = 0
    miss_cnt = {c: 0 for c in CORE}

    for fi, fp in enumerate(files):
        code = os.path.basename(fp)[:-3]
        if code not in colpos:
            continue
        with h5py.File(fp, 'r') as f:
            g = f['fields']
            # ★★ 2026-09-15 修：**不再要求全部科目都在**（缺的置 NaN，其余照算）
            #    旧版 `if not all(have): continue` ⇒ 任一新科目缺失就整只股票被跳过
            #    ⇒ 覆盖率会暴跌（实测 `interest_expense`/`inventory` 并非所有公司都有）✗
            have = [c in g for c in CORE]
            if not any(have):
                continue
            for c, h in zip(CORE, have):
                if not h:
                    miss_cnt[c] += 1
            if not all(have):
                n_miss_any += 1
            core_raw = np.full((len(f['quarter'][:]), len(CORE)), np.nan, dtype=np.float64)
            for c, h in zip(CORE, have):
                if h:
                    v = g[c][:].astype(np.float64)
                    core_raw[:len(v), CI[c]] = v
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
            n_skip_col += 1
            continue
        core_raw, qk, info = core_raw[ok], qk[ok], info[ok]
        fin = info <= int(dates[-1])
        core_raw, qk, info = core_raw[fin], qk[fin], info[fin]
        if not len(info):
            n_skip_col += 1
            continue

        pos = np.searchsorted(dates, info, side='right')
        order = np.argsort(pos, kind='stable')
        pos, core_raw, qk = pos[order], core_raw[order], qk[order]

        mk = np.asarray(mk_all[code].values, dtype=np.float64)   # ★ 该股按日总市值
        out = np.full((len(FA_KEYS), nd), np.nan, dtype=np.float32)
        val = {}
        qmax = -1
        snap = np.full(len(FA_KEYS), np.nan)
        snap_eq = np.nan                    # ★ PB 的分子（归母权益），按日除 mktcap
        prev, i, nn = 0, 0, len(pos)
        while i < nn:
            p = int(pos[i])
            if p > prev:
                out[:, prev:p] = snap[:, None]
                # ★ PB 特殊处理：分母 mktcap 日变 ⇒ 在按日填充时算
                if np.isfinite(snap_eq):
                    out[PB_IDX, prev:p] = snap_eq / mk[prev:p]
            p_end = p
            while i < nn and pos[i] == p_end:
                q, v = int(qk[i]), core_raw[i]
                vals = np.asarray(v, dtype=np.float64).copy()
                vals[~np.isfinite(vals)] = np.nan
                val[q] = vals
                if q > qmax:
                    qmax = q
                i += 1
            if qmax >= 0:
                c = val[qmax]
                q4 = val.get(qmax - 4)
                d = _fact(c, q4)
                snap = np.array([d[k] for k in FA_KEYS], dtype=np.float64)
                snap[~np.isfinite(snap)] = np.nan
                snap_eq = _g(c, 'equity_parent_company')
                if not np.isfinite(snap_eq):
                    snap_eq = np.nan
            else:
                snap = np.full(len(FA_KEYS), np.nan)
                snap_eq = np.nan
            prev = p_end
        out[:, prev:] = snap[:, None]
        if np.isfinite(snap_eq) and prev < nd:
            out[PB_IDX, prev:] = snap_eq / mk[prev:]
        for j, k in enumerate(FA_KEYS):
            outs[k].append(out[j])
        codes_out.append(code)
        n_ok += 1
        if (fi + 1) % 800 == 0:
            print('  %d/%d  n_ok=%d  %.0fs' % (fi + 1, len(files), n_ok, time.time() - t0))

    print('有效股票: %d（其中 %d 只缺部分科目 ⇒ 已按 NaN 容忍）  跳过 %d  耗时 %.0fs'
          % (n_ok, n_miss_any, n_skip_col, time.time() - t0))
    if n_miss_any:
        top = sorted((v, k) for k, v in miss_cnt.items() if v)[-6:]
        print('  最常缺的科目: %s' % ', '.join('%s(%d 只)' % (k, v) for v, k in reversed(top)))

    with pd.HDFStore(OUT, 'w', complib='blosc', complevel=5) as st:
        for k in FA_KEYS:
            df = pd.DataFrame(np.stack(outs[k], axis=1), index=close.index,
                              columns=codes_out)
            st[k] = df.astype('float32')
            v = np.asarray(df.values)
            print('  %-14s %s  NaN=%5.1f%%   中位=%9.4f'
                  % (k, df.shape, np.isnan(v).mean() * 100, np.nanmedian(v)))
    print('\n已存 %s   %.0fs' % (OUT, time.time() - t0))

    # sanity: 000001 银行 资产负债率应~0.9, gm 应全 NaN, 利息保障应很低
    if '000001.XSHE' in codes_out:
        with pd.HDFStore(OUT, 'r') as st:
            lev = st['fa_lev']['000001.XSHE']
            gm = st['fa_gm']['000001.XSHE']
        print('\nsanity 000001 fa_lev 2016中位=%.3f (期望~0.9)  gm NaN=%.0f%% (期望~100)'
              % (np.nanmedian(lev[lev.index < 20170101]),
                 gm.isna().sum() / len(gm) * 100))


if __name__ == '__main__':
    main()
