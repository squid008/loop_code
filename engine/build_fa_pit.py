# -*- coding: utf-8 -*-
"""
财报 PIT as-of 展开入叶 —— D:\\rq\\finance\\pit\\*.h5 → fa_pit.h5
======================================================================
PIT 实测结构: 每股票 h5 = keys{fields(组,~394科目)/if_adjusted/info_date/quarter/rice_create_tm}
无 ann_date。同 report_period(quarter) 存在多条版本行(首次披露 + 后续每份报告带一版修正,
同一 (quarter, info_date) 唯一)。=> 版本链规则(t 日可见值 = 该报告期 info_date≤t 的最新版本),
本实现逐事件推进、按季度区间填充, 严格无未来函数。

## 产出（2026-09-15 扩展 8 → 15；★ **2026-10-14 再 +2 → 17** ✓）
##   ★ 2026-10-14 顺带校正记账：原注释写「8 → 20 个」，是把下面「试过但删掉」的也算进去了 ✗
##     ⇒ 当时的真实落地是 **15** 个 ✓

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

### ★ 2026-10-14 再 +2（用户："算子里有没有自由现金流/ROE/ROA？"）
  fa_fcf_yield   **自由现金流收益率** = (经营现金流TTM − 资本开支TTM) / **日总市值**
                 ⚠ 资本开支科目 `cash_paid_for_asset` 源里**没有 TTM 版** ⇒ 本文件新增
                   `_ttm()` 按 YTD 滚 4 季（`TTM = 本期YTD + 上年年报 − 上年同期YTD`）✓
                 实测：与全部旧叶子的最大 |相关| 仅 **0.485**（barra_earnings_yield）✓
  fa_ocf_ta      **现金 ROA** = 经营现金流TTM / 总资产 —— 实测 **0.553**（fa_accrual）✓
  ⚠ 口径**先实测后定**：体检脚本 `ai_test/dedup_check.py`（引擎口径 `rank_rows(v[::FWD])`）✓，
    候选由本文件 `--cand_out` 另写一份 h5（**不动正式输出** ✓）

### ⚠ 试过但**删掉**的（原 5 个 + 2026-10-14 新增第 (c) 类 4 个）
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

**(c) 与既有叶子共线 ⇒ 不加**（2026-10-14 实测，用户要求"避免共线性太高"）
  探的是"**净利润口径的 ROA**"，四个变体全部共线 ⇒ **该口径在本仓无解** ✗：
  ✗ fa_roa_np     np_TTM / 总资产 —— 与 **fa_roe 0.844** · fa_np_margin 0.788 ✗
  ✗ fa_roa_op     营业利润TTM / 总资产 —— 与 fa_roe **0.834** · fa_np_margin 0.768 ✗
  ✗ fa_roa_excash np_TTM / (总资产 − 货币资金)（**净经营性资产**口径）—— 与 fa_roe **0.824**
                  ⇒ **换分母也压不下来** ✗（根因：分子同源 + 分母在截面上高度同步）
  ✗ fa_roa_yoy    ROA 同比 —— 与 fa_np_yoy **0.947**（总资产变化慢 ⇒ 数学上必然）✗
  ⇒ 因此改用**现金流口径**的资产回报率：`fa_ocf_ta`（现金 ROA，0.553）✓

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
3. ★★ **为什么 `fa_pb` 要特殊处理**：其它 14 个都是"**每个报告期一个数**"（`snap` 常量），
   而 PB 的分母 `mktcap` **是日变的** ⇒ 必须在**按日填充**时算，不能进 `_fact` 的标量返回 ✓
4. ★ 资产负债表科目对银行/保险天然 NaN（无毛利/存货/应收）⇒ 交截面排序丢弃（可接受）✓
"""
import os
import sys
import glob
import time
import h5py
import numpy as np
import pandas as pd

# ★ 2026-10-14：**输出重定向到文件时 stdout 编码是 GBK** ⇒ 打印 `⇒`(U+21D2) 会抛
#   UnicodeEncodeError **直接中断构建**（实测：跑到 4800/5567 崩 ✗，且崩在写盘之前）。
#   本仓库其它脚本（release_check / factor_curves / build_panel …）都做了同一件事 ⇒ 补齐 ✓
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:                          # noqa: BLE001
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
PANEL = os.path.join(HERE, 'panel.h5')
OUT = os.path.join(HERE, 'fa_pit.h5')
import loop_env as _E     # ★ 外部数据根的唯一事实源（config.local.json 的 paths 段）
PIT = _E.data('finance', 'pit')

# ---- 核心输入科目（TTM 字段为 RQ 已算好的 12 月滚动值, 避开 YTD 拼接）----
CORE8 = ['net_profitTTM', 'operating_revenueTTM', 'gross_profitTTM',
         'operating_profitTTM', 'net_operate_cashflowTTM',
         'equity_parent_company', 'total_liabilities', 'total_assets']
CORE_NEW = [
    # 派生比率所需的科目
    'goodwill', 'inventory', 'bill_accts_receivable', 'selling_expense',
]
# ★ 2026-10-14（用户：算子里有没有自由现金流/ROE/ROA？⇒ 加 FCF + 换口径 ROA）：
#   `cash_paid_for_asset` = 购建固定资产/无形资产和其他长期资产支付的现金（= 资本开支 CapEx）
#   ⚠ 源里**没有 *TTM 版本**（394 科目里只有不带 TTM 的 YTD 版）⇒ 必须自己滚 4 季，
#     见下面的 `_ttm()`。该科目**只服务于 `--cand_out` 体检模式**，不参与正式 15 列计算 ✓
CORE_CAND = ['cash_paid_for_asset', 'cash_equivalent']
CORE = CORE8 + CORE_NEW + CORE_CAND
CI = {c: i for i, c in enumerate(CORE)}          # ★ 按名字索引，不再硬编码位置

# ---- ★ 2026-10-14 候选口径（体检专用；仅 `--cand_out` 时写盘，不改 fa_pit.h5）----
#   命名 `cand_*` 与正式叶子区分；`*_yield` 两个的分母是**日变 mktcap** ⇒ 与 fa_pb 同款，
#   由主循环在「按日填充」处算（`CAND_MK_DIV`）。
CAND_KEYS = ['cand_fcf_yield', 'cand_ocf_yield', 'cand_fcf_ta', 'cand_fcf_margin',
             'cand_ocf_ta', 'cand_roa_op', 'cand_roa_yoy', 'cand_roa_np',
             # ★ 第二轮（2026-10-14）：实测**水平 ROA 口径与 fa_roe 0.83+ 共线** ✗
             #   ⇒ 试"把资产里的**冗余现金**剔除"（净经营性资产口径），看能否拉低 ✓
             'cand_roa_excash', 'cand_ocf_excash']
CAND_MK_DIV = [i for i, k in enumerate(CAND_KEYS) if k.endswith('_yield')]

# ---- 输出叶子（顺序 = 写入 h5 的顺序）----
FA8 = ['fa_np_yoy', 'fa_rev_yoy', 'fa_op_yoy', 'fa_ocf_yoy',
       'fa_gm', 'fa_np_margin', 'fa_roe', 'fa_lev']
FA_NEW = ['fa_pb', 'fa_accrual', 'fa_asset_turn', 'fa_gw',
          'fa_inv_turn', 'fa_recv_turn', 'fa_sell_exp']
# ★ 2026-10-14 +2（用户："算子里有没有自由现金流/ROE/ROA？"）—— 口径先实测后定，
#   体检脚本见 ai_test/dedup_check.py（引擎口径 rank 相关）：
#   · fa_fcf_yield = (经营现金流TTM − 资本开支TTM) / **日 mktcap** ⇒ 与 fa_pb 同款按日除 ✓
#   · fa_ocf_ta    = 经营现金流TTM / 总资产（**现金 ROA**）⇒ 普通 per-report 常量 ✓
FA_NEW2 = ['fa_fcf_yield', 'fa_ocf_ta']
FA_KEYS = FA8 + FA_NEW + FA_NEW2
PB_IDX = FA_KEYS.index('fa_pb')                  # ★ PB 特殊处理（按日 mktcap）
FCF_IDX = FA_KEYS.index('fa_fcf_yield')          # ★ FCF 收益率特殊处理（同上，分子不同）


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
    out['fa_ocf_ta'] = _safe(ocf, ta)     # ★ 现金 ROA（2026-10-14）
    out['fa_pb'] = np.nan          # ★ 占位：真正计算在按日填充处（分母 mktcap 日变）
    out['fa_fcf_yield'] = np.nan   # ★ 占位：同上（分子 = FCF_TTM，由主循环备好）
    return out


def _ttm(val, q, name):
    """把「YTD 累积」科目滚动成 **TTM**（12 个月）。

    中国财报是**年内累积**（Q1=1~3 月 … 年报=全年）⇒
        TTM(q) = YTD(q) + 上年年报 − 上年同期 YTD
    q 为年报时「上年年报」与「上年同期」是同一期 ⇒ 两项相消，TTM 就是当年年报 ✓
    （公式统一，无需按季度分支 ✓）

    ★ 为什么需要它（2026-10-14）：项目原有 15 个叶子**全部只用 RQ 已算好的 `*TTM` 字段**
    （就是为了避开 YTD 拼接这个易错点）；而 `cash_paid_for_asset` 源里**没有 TTM 版**，
    做 FCF 只能自己滚 ⇒ 本函数只服务候选体检与新叶子 ✓

    :param val: `{quarter_key: core 向量}`（主循环里逐事件累积的 dict ✓）
    :param q:   当前 quarter key（`year*4 + 季度-1`）
    :return:    TTM 标量；任一期缺失 ⇒ NaN（不臆造 ✓）
    """
    cur = val.get(q)
    if cur is None:
        return np.nan
    q_ye = q - (q % 4) - 1          # 上年年报（q 为年报时 == 上年同期 ⇒ 相消 ✓）
    q_ps = q - 4                    # 上年同期
    a = _g(cur, name)
    b = _g(val[q_ye], name) if q_ye in val else np.nan
    c = _g(val[q_ps], name) if q_ps in val else np.nan
    if not (np.isfinite(a) and np.isfinite(b) and np.isfinite(c)):
        return np.nan
    return a + b - c


def _cand_fact(val, q):
    """★ 2026-10-14 候选口径（体检用，**不进正式输出**）。

    每个候选都是「每个报告期一个数」（`snap` 型）⇒ 直接进主循环的按日填充；
    其中 `*_yield` 两个的分母是日变 mktcap ⇒ 主循环再按日相除（同 fa_pb 的做法 ✓）。
    返回 `{候选名: 标量}`（缺科目 ⇒ NaN ✓）。
    """
    cur = val.get(q)
    if cur is None:
        return {}
    q4 = val.get(q - 4)

    def _vv(vec, k):
        return _g(vec, k) if vec is not None else np.nan

    ocf = _g(cur, 'net_operate_cashflowTTM')
    capex = _ttm(val, q, 'cash_paid_for_asset')
    ta = _g(cur, 'total_assets')
    _cash = _g(cur, 'cash_equivalent')
    ta_ex = (ta - _cash) if (np.isfinite(ta) and np.isfinite(_cash)) else np.nan
    rev = _g(cur, 'operating_revenueTTM')
    np_, op = _g(cur, 'net_profitTTM'), _g(cur, 'operating_profitTTM')
    fcf = ocf - capex if (np.isfinite(ocf) and np.isfinite(capex)) else np.nan
    roa_now = _safe(np_, ta)
    roa_pre = _safe(_vv(q4, 'net_profitTTM'), _vv(q4, 'total_assets'))
    yoy = _safe(roa_now, roa_pre)
    return {
        'cand_fcf_yield': fcf,                     # 分子；主循环除以 mktcap
        'cand_ocf_yield': ocf,                     # 同上
        'cand_fcf_ta': _safe(fcf, ta),
        'cand_fcf_margin': _safe(fcf, rev),
        'cand_ocf_ta': _safe(ocf, ta),
        'cand_roa_op': _safe(op, ta),
        'cand_roa_yoy': (yoy - 1 if np.isfinite(yoy) else np.nan),
        'cand_roa_np': roa_now,
        # ★ 第二轮：分母换「总资产 − 货币资金」（净经营性资产）
        'cand_roa_excash': _safe(np_, ta_ex),
        'cand_ocf_excash': _safe(ocf, ta_ex),
    }


def main(cand_out=''):
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
    do_cand = bool(cand_out)                  # ★ 2026-10-14：候选体检模式门控
    outs = {k: [] for k in FA_KEYS}
    cands = {k: [] for k in CAND_KEYS}        # ★ 候选列容器（仅 do_cand 时填充 ✓）
    codes_out = []
    n_ok = n_skip_col = n_miss_any = 0
    miss_cnt = {c: 0 for c in CORE}

    _stat = [n_skip_col, n_miss_any]              # ★ 可就地累加：[n_skip_col, n_miss_any]
    for fi, fp in enumerate(files):
        got = _load_pit_stock(fp, colpos, dates, miss_cnt, _stat)
        if got is None:
            continue
        code, core_raw, qk, info = got

        pos = np.searchsorted(dates, info, side='right')
        order = np.argsort(pos, kind='stable')
        pos, core_raw, qk = pos[order], core_raw[order], qk[order]

        mk = np.asarray(mk_all[code].values, dtype=np.float64)   # ★ 该股按日总市值
        out = np.full((len(FA_KEYS), nd), np.nan, dtype=np.float32)
        # ★ 2026-10-14 候选列（仅体检模式分配 ⇒ 正式模式零开销、零行为变化 ✓）
        cand = (np.full((len(CAND_KEYS), nd), np.nan, dtype=np.float32)
                if do_cand else None)
        val = {}
        qmax = -1
        snap = np.full(len(FA_KEYS), np.nan)
        c_snap = np.full(len(CAND_KEYS), np.nan)     # ★ 候选的 per-report 值
        snap_eq = np.nan                    # ★ PB 的分子（归母权益），按日除 mktcap
        snap_fcf = np.nan                   # ★ FCF 收益率的分子（FCF_TTM），按日除 mktcap
        prev, i, nn = 0, 0, len(pos)
        while i < nn:
            p = int(pos[i])
            if p > prev:
                out[:, prev:p] = snap[:, None]
                # ★ PB 特殊处理：分母 mktcap 日变 ⇒ 在按日填充时算
                if np.isfinite(snap_eq):
                    out[PB_IDX, prev:p] = snap_eq / mk[prev:p]
                if np.isfinite(snap_fcf):                      # ★ 2026-10-14：FCF 收益率
                    out[FCF_IDX, prev:p] = snap_fcf / mk[prev:p]
                if do_cand:
                    cand[:, prev:p] = c_snap[:, None]
                    for _j in CAND_MK_DIV:       # ★ 收益率族：分子 / 按日 mktcap
                        if np.isfinite(c_snap[_j]):
                            cand[_j, prev:p] = c_snap[_j] / mk[prev:p]
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
                # ★ 2026-10-14：备好 FCF 收益率的**分子**（FCF_TTM = 经营现金流TTM − 资本开支TTM）
                #   分母 mktcap 日变 ⇒ 与 fa_pb 同款，在按日填充处再相除 ✓
                _ocf = _g(c, 'net_operate_cashflowTTM')
                _cap = _ttm(val, qmax, 'cash_paid_for_asset')
                snap_fcf = ((_ocf - _cap)
                            if (np.isfinite(_ocf) and np.isfinite(_cap)) else np.nan)
                if do_cand:
                    dc = _cand_fact(val, qmax)
                    c_snap = np.array([dc.get(k, np.nan) for k in CAND_KEYS],
                                      dtype=np.float64)
                    c_snap[~np.isfinite(c_snap)] = np.nan
            else:
                snap = np.full(len(FA_KEYS), np.nan)
                c_snap = np.full(len(CAND_KEYS), np.nan)
                snap_eq = np.nan
                snap_fcf = np.nan
            prev = p_end
        out[:, prev:] = snap[:, None]
        if np.isfinite(snap_eq) and prev < nd:
            out[PB_IDX, prev:] = snap_eq / mk[prev:]
        if np.isfinite(snap_fcf) and prev < nd:                # ★ 2026-10-14：FCF 收益率
            out[FCF_IDX, prev:] = snap_fcf / mk[prev:]
        if do_cand and prev < nd:                    # ★ 尾部区间同样填候选
            cand[:, prev:] = c_snap[:, None]
            for _j in CAND_MK_DIV:
                if np.isfinite(c_snap[_j]):
                    cand[_j, prev:] = c_snap[_j] / mk[prev:]
        for j, k in enumerate(FA_KEYS):
            outs[k].append(out[j])
        if do_cand:
            for j, k in enumerate(CAND_KEYS):
                cands[k].append(cand[j])
        codes_out.append(code)
        n_ok += 1
        if (fi + 1) % 800 == 0:
            print('  %d/%d  n_ok=%d  %.0fs' % (fi + 1, len(files), n_ok, time.time() - t0))

    n_skip_col, n_miss_any = _stat
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
    if do_cand:
        with pd.HDFStore(cand_out, 'w', complib='blosc', complevel=5) as st:
            for k in CAND_KEYS:
                df = pd.DataFrame(np.stack(cands[k], axis=1), index=close.index,
                                  columns=codes_out)
                st[k] = df.astype('float32')
                v = np.asarray(df.values)
                print('  [cand] %-18s NaN=%5.1f%%   中位=%14.6f'
                      % (k, np.isnan(v).mean() * 100, np.nanmedian(v)))
        print('已存候选列 %s' % cand_out)

    print('\n已存 %s   %.0fs' % (OUT, time.time() - t0))

    # sanity: 000001 银行 资产负债率应~0.9, gm 应全 NaN, 利息保障应很低
    if '000001.XSHE' in codes_out:
        with pd.HDFStore(OUT, 'r') as st:
            lev = st['fa_lev']['000001.XSHE']
            gm = st['fa_gm']['000001.XSHE']
        print('\nsanity 000001 fa_lev 2016中位=%.3f (期望~0.9)  gm NaN=%.0f%% (期望~100)'
              % (np.nanmedian(lev[lev.index < 20170101]),
                 gm.isna().sum() / len(gm) * 100))




def _load_pit_stock(fp, colpos, dates, miss_cnt, stat):
    """读一只股票的 PIT h5 ⇒ 展开成「按 (quarter, info_date) 紧凑排列」的数组。

    ★ 2026-09-28：**逐字**自 `main()` 搬出（R1 收官：`main` 145 → ~103 行 ✓）——
      只把 4 处 `continue` 换成 `return None` ✓，其余零改名 ✓。

    :param colpos:    `{股票代码: 列号}`；**不在其中 ⇒ 静默跳过**（原 `continue` ✓，不计任何数 ✓）
    :param dates:     **完整日期轴**（块里只用 `dates[-1]` 当"数据末端"✓）——
                      ⚠ 特意传整根数组而不是单个 `last_date`：这样块内 `dates[-1]` **一个字都不用改** ✓
                      （初版我写成 `last_date` 形参 ⇒ 块里 `dates[-1]` 就成了 NameError ✗，靠 `--dump` 审阅抓到 ✓）
    :param miss_cnt:  **就地累加**「科目缺失」的股票数 `{科目: 只数}`（可变 dict ✓）
    :param stat:      `[n_skip_col, n_miss_any]`，**就地累加**（list 才可变 ✓）
    :return:          `(code, core_raw, qk, info)`；**静默跳过**（不在 colpos / 一个核心科目都没有）
                      ⇒ `None` ✓；**计入跳过**（quarter/info 全解析失败、或 info 早于起点后为空）
                      ⇒ 不返回（`stat[0]` 已加 1，由调用方 `continue` ✓）

    ⚠ **顺序有讲究**（照搬原文 ✓）：科目缺失的计数发生在**解析失败之前** ⇒
      即使这只股票随后被计入 `n_skip_col`，它的缺科目数**已经计过了** ✓
      ⇒ 所以计数留在本函数里、**不能挪到调用方**（挪了就漏计这一类 ✗）。
    """
    code = os.path.basename(fp)[:-3]
    if code not in colpos:
        return None
    with h5py.File(fp, 'r') as f:
        g = f['fields']
        # ★★ 2026-09-15 修：**不再要求全部科目都在**（缺的置 NaN，其余照算）
        #    旧版 `if not all(have): continue` ⇒ 任一新科目缺失就整只股票被跳过
        #    ⇒ 覆盖率会暴跌（实测 `interest_expense`/`inventory` 并非所有公司都有）✗
        have = [c in g for c in CORE]
        if not any(have):
            return None
        for c, h in zip(CORE, have):
            if not h:
                miss_cnt[c] += 1
        if not all(have):
            stat[1] += 1
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
        stat[0] += 1
        return None
    core_raw, qk, info = core_raw[ok], qk[ok], info[ok]
    fin = info <= int(dates[-1])
    core_raw, qk, info = core_raw[fin], qk[fin], info[fin]
    if not len(info):
        stat[0] += 1
        return None
    return code, core_raw, qk, info


if __name__ == '__main__':
    import argparse
    _ap = argparse.ArgumentParser(
        description='财报 PIT 展开 → fa_pit.h5（正式 15 列）；'
                    '★ --cand_out 另写一份「FCF / ROA 候选」h5 供相关性体检（不改 fa_pit.h5）')
    _ap.add_argument('--cand_out', default='', metavar='PATH',
                     help='★ 体检用：把 cand_* 候选列写到该 h5（例 ai_test/fa_candidates.h5）')
    _a = _ap.parse_args()
    main(cand_out=_a.cand_out)
