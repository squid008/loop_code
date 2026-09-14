# -*- coding: utf-8 -*-
"""
中金 Loop Engineering 自动化因子发现引擎(我方实现)
=====================================================
闭环: 生成 -> L1粗筛(批量IC) -> L2精筛(费后回测+11项过滤) -> L3入库(去重) -> 下一代
参考中金《基于Loop Engineering的自动化因子发现引擎》:
  16939 候选 -> 69 因子(成功率0.41%), Top5等权超额夏普3.14 / 年化超额18.3%

与中金原版的差异(我方改进):
  1. **验证端用费后口径** evaluate_real(): 扣往返成本0.5% + 涨停不可买 + 跌停顺延卖出
     (中金的夏普>0.5 / Calmar>1.0 本就是费后标准, 必须配套费后验证端)
  2. L1 用**批量向量化IC**粗筛(比逐因子 evaluate 快30倍), 否则规模上不去
  3. FSA(频繁子树规避) 用子树哈希计数, 抑制重复表达式

五维演化(中金配比): 变异25% / 交叉25% / 参数扰动15% / 随机探索15% / 语义引导20%

用法:
    python loop_engine.py --gen=1 --n=600        # 第1代 600 个候选
    python loop_engine.py --gen=2 --n=600        # 第2代(读上一代种子池)
"""
import os
import re
import sys
import io
import gc
import json
import time
import random
import pickle
import argparse
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from factor_miner import (load_panel, prepare, get_universe, cs_rank,
                          evaluate_real, START, FWD, COST_PRESETS)
from cost_presets import DEFAULT_COST, cost_label      # 成本档单一事实源(2026-09-11)
from loop_metrics import (rank_rows, decile_shape, l1_score,   # L1 指标层(2026-09-11, 含 rank_rows)
                          style_expo, STYLE_KEYS,              # 风格暴露观测(2026-09-11, --style_obs)
                          neutralize_rows,                     # 风格中性收益(2026-09-11, 仅观测)
                          neutral_rank)                        # 秩中性化(2026-09-12, --strip_style)
from loop_pools import (pool_mask, parse_pools,                 # 池成员PIT掩码(2026-09-12, --pool_obs)
                        pool_gate_ok)                           # 池门槛纯函数(2026-09-12, --min_pool_calmar)

# ★ 输出编码兜底(2026-09-12 实录): 中文 Windows 控制台/重定向默认 **GBK**, 而本项目注释/文案里
#  常出现 GBK 编不出的字符(⚠ ✅ ⇒ − ² Ŷ 等)。一旦某个 print/help 带这类字符:
#    · `--help` 直接抛 UnicodeEncodeError 全挂;
#    · **更严重**: 无人值守跑到那个分支时抛错中断整代。
#  errors='replace' 让这类字符退化为 '?' 而不是抛错 —— 是把"整轮跑挂"降级为"一个字显示不出"。
#  同时新代码仍应尽量用 GBK 安全字符(见 tools/scan_non_gbk.py 与 qa_engine_cli.py)。
try:
    sys.stdout.reconfigure(errors='replace')
    sys.stderr.reconfigure(errors='replace')
except Exception:
    pass

STATE = os.path.join(HERE, 'loop_state.pkl')
ARCHIVE = os.path.join(os.path.dirname(HERE), 'docs', 'loop_archive.csv')
# 风格暴露观测独立成文件(2026-09-11): 不进 ARCHIVE 表头 —— 追加模式下加列会让历史行错位
STYLE_OBS = os.path.join(os.path.dirname(HERE), 'docs', 'loop_style_obs.csv')
# 剥风格入库判据的逐代明细(2026-09-12, --strip_style)。同样独立成文件, 理由同 STYLE_OBS。
STRIP_OBS = os.path.join(os.path.dirname(HERE), 'docs', 'loop_strip_style.csv')
# 池内指标(2026-09-12, --pool_obs)。**长表**(每候选 x 每池一行) —— 不用宽表是因为
# 池集合由 --pools 决定, 宽表换池集合会导致追加时表头错位(与 archive 同一个坑)。
POOL_OBS = os.path.join(os.path.dirname(HERE), 'docs', 'loop_pool_obs.csv')
JOURNAL = os.path.join(os.path.dirname(HERE), 'docs', 'loop_journal.md')  # B角诊断日志(loop_code/docs)
LIBRARY = os.path.join(os.path.dirname(HERE), 'docs', 'factor_library.md')  # 入库因子文档(代末自动同步新增)

# ===================== 三池并行挖掘(2026-09-12, roadmap §8.19) =====================
# 用户方案: 全A / 沪深300 / 中证500 三条**完全独立**的轨迹(各自 state/bank/种子/冻结/失败库)。
# 依据: 全A 含微盘 -> "低流动性溢价"让风格因子轻松过关, 且 L1 的单一 IC 排序也奖励它
#   (§8.13 实测 30/30 的 lnamt/lntr 全负、剥成交额后仅 3/30 为正; §8.19 实测 ic_all 与真信号
#    **负相关 -0.317**)。在 300/500 池内挖, 该溢价不存在 -> 风格暴露自然挣不到分 -> 引擎必须
#   去找真信号。(QuantaAlpha 正是如此: `market: csi300` + benchmark SH000300, §8.8/§8.19)
# 实现: 'all' = 现状(不加后缀; 现有 loop_state.pkl / loop_archive.csv 即全A轨迹的既有历史);
#       '300'/'500' = 全新独立轨迹(文件加 _300/_500 后缀)。可选池见 engine/loop_pools.py 的 POOLS。
MINE_POOL = 'all'
L1_POOL_MASK = None       # (len(L1_ROWS), len(L1_COLS)) bool; None = 不加池约束(全A现状)
# 原始路径快照: set_mine_pool 永远**从快照派生** -> 重复调用不会叠后缀(_300_500)
_ORIG_PATHS = {}


def set_mine_pool(tag):
    """把引擎切到指定池的**独立轨迹**。

    ① 状态 / 输出文件全部加池后缀 -> 三条轨迹互不读写对方的 bank/archive/journal/library;
    ② L1 子面板列 = 该池**并集**(历史上出现过的全部成分, 保证任一时点的成分都在面板里);
    ③ L1 的 IC 按 **PIT 池掩码**算 -> 目标函数从"全A IC"变成"**池内 IC**"。

    tag='all' 时**完全不动**(向后兼容)。幂等(可从原始路径重复派生)。返回实际生效的 tag。
    """
    global MINE_POOL, STATE, ARCHIVE, STYLE_OBS, STRIP_OBS, POOL_OBS, JOURNAL, LIBRARY
    if not _ORIG_PATHS:                          # 首次调用时快照原始路径
        _ORIG_PATHS.update(STATE=STATE, ARCHIVE=ARCHIVE, STYLE_OBS=STYLE_OBS,
                           STRIP_OBS=STRIP_OBS, POOL_OBS=POOL_OBS,
                           JOURNAL=JOURNAL, LIBRARY=LIBRARY)

    def _apply(sfx):
        for k in _ORIG_PATHS:
            r, e = os.path.splitext(_ORIG_PATHS[k])   # 后缀加在扩展名前: a/b.md -> a/b_300.md
            globals()[k] = r + sfx + e

    if not tag or tag == 'all':
        MINE_POOL = 'all'
        _apply('')
        return 'all'
    import loop_pools as _LP
    if tag not in _LP.POOLS:
        raise SystemExit(f"[--mine_pool] 未知池 '{tag}'; 可选: all / {sorted(_LP.POOLS)}")
    MINE_POOL = tag
    _apply('_' + tag)
    return tag


# 默认搜索策略(B角可动态调整)
# 中金五策略配比: 变异25 / 交叉25 / 扰动15 / 随机探索15 / LLM机制引导20
# 本表键序=变异/交叉/扰动/引导/随机 -> mix=[0.25,0.25,0.15,0.20,0.15] 即引导20随机15
DEFAULT_CFG = dict(leaf_w={}, op_bias={}, depth=[2, 3, 4],
                   mix=[0.25, 0.25, 0.15, 0.20, 0.15],
                   min_stab=0.30, decorr=0.75, fsa_th=0.15)

# ===================== 1. 基础字段 =====================
# ---- 叶子字段单一事实源 = loop_fields.py (引擎A角/B角critic/量纲/写档共用) ----
# 新增字段族只改 loop_fields.py 一处, 勿在本文件硬编码叶子名(防再漂移)。
# 资金流 moneyflow3 原始拆分16列: 金额(×1e4元,量纲A)+量(×100股,量纲V), 净额不预焊由GP自组合;
# BARRA 连续风格11(barra.h5,行业哑不入叶) / 财报PIT as-of比率8(fa_pit.h5,按info_date无未来函数)
from loop_fields import MF16, BARRA_LEAVES, FA_LEAVES, LEAVES, FIELDS

_BASE = None
L1_STOCKS = 2000          # L1 粗筛抽样的股票数(越小越快, 但IC估计误差越大)
L1_ROWS = None
L1_COLS = None
_LRU = {}                 # 跨批次复用子树求值结果(种子演化共享大量子树)
LRU_MAX = 400             # L1 每批结束把 _LRU 裁到该条数上限(防 L1 段 OOM)
CACHE2_MAX = 150          # 去相关/去重阶段 cache2 的子树缓存上限
                          # (该段每候选只需算1次、无跨批复用, 缓存仅服务邻近候选共享,
                          #  故宜小; 实测 gen37 该段无界累积导致内存从9G单调涨到20G+)
# ★跨阶段复用缓存(2026-09-12): L1 已算过的因子值, 供**去相关/去重**直接取用, 免二次 eval。
#   实测依据: 一代 52min 里 L1 占 44%、去相关+去重占 **43%**(499 个候选各重算约 2.7s),
#   而 L2 只占 10%(evaluate_real 单次仅 ~7s) -> **重复 eval 才是最大浪费**, 不是 L2。
#   只存"过 ic/stab 门槛"的候选, 且只存 [::FWD] 调仓日视图(419×2000 float32 ≈ 3.35MB/个);
#   存的是**符号对齐后**的同一数组 -> 下游 rank_rows 结果逐位不变(行为等价, 非近似)。
VCACHE = {}
_VREUSE_MB = [0.0]        # 已占用 MB(list 便于就地累加)
_VREUSE_CAP_MB = 2000.0   # 上限 2GB; 超了就不再存(未命中者在去相关/去重处回退为现场 eval)


def base_fields():
    """返回 {name: (T,S) float32} 基础字段 + 日期/列"""
    global _BASE
    if _BASE is not None:
        return _BASE
    P = load_panel(FIELDS)
    P = prepare(P)
    close = P['close'].astype('float64')
    dates = close.index.values
    cols = list(close.columns)
    B = {
        'close': close.values.astype(np.float32),
        'open': P['open'].reindex(index=dates, columns=cols).values.astype(np.float32),
        'high': P['high'].reindex(index=dates, columns=cols).values.astype(np.float32),
        'low': P['low'].reindex(index=dates, columns=cols).values.astype(np.float32),
        'volume': P['volume'].reindex(index=dates, columns=cols).values.astype(np.float32),
        'turnover': P['turnover'].reindex(index=dates, columns=cols).values.astype(np.float32),
        'mktcap': P['mktcap'].reindex(index=dates, columns=cols).values.astype(np.float32),
    }
    # ---- 扩展叶子(mf16 随 FIELDS 已入 P; barra/fa 独立 store) ----
    for name in MF16:
        B[name] = P[name].reindex(index=dates, columns=cols).values.astype(np.float32)
    for fn, names in (('barra.h5', BARRA_LEAVES), ('fa_pit.h5', FA_LEAVES)):
        with pd.HDFStore(os.path.join(HERE, fn), 'r') as st:
            for name in names:
                B[name] = st[name].reindex(index=dates, columns=cols).values.astype(np.float32)
    # 衍生
    B['vwap'] = (B['turnover'] / np.maximum(B['volume'], 1e-9)).astype(np.float32)
    B['ret'] = (pd.DataFrame(B['close']).pct_change().values).astype(np.float32)
    B['amt'] = B['turnover']
    B['ln_mktcap'] = np.log(np.maximum(B['mktcap'], 1e-9)).astype(np.float32)
    B['ln_volume'] = np.log(np.maximum(B['volume'], 1e-9)).astype(np.float32)
    B['turn_ratio'] = (B['turnover'] / np.maximum(B['mktcap'], 1e-9)).astype(np.float32)
    # ---- 派生字段(★中金研报: overnight 出现率 85% / amplitude 63%, 是核心信号源) ----
    c, o, h, l = B['close'], B['open'], B['high'], B['low']
    pc = np.vstack([np.full((1, c.shape[1]), np.nan), c[:-1]]).astype(np.float32)  # 昨收
    rng = (h - l).astype(np.float32)
    with np.errstate(invalid='ignore', divide='ignore'):
        B['overnight'] = (o / pc - 1.0).astype(np.float32)          # 隔夜跳空 ★
        B['intraday'] = (c / o - 1.0).astype(np.float32)            # 日内收益
        B['amplitude'] = (rng / pc).astype(np.float32)              # 振幅 ★
        B['up_shadow'] = ((h - np.maximum(o, c)) /
                          np.where(rng > 1e-9, rng, np.nan)).astype(np.float32)
        B['down_shadow'] = ((np.minimum(o, c) - l) /
                            np.where(rng > 1e-9, rng, np.nan)).astype(np.float32)
        B['hl_ratio'] = (h / np.where(l > 1e-9, l, np.nan)).astype(np.float32)
        B['true_range'] = (np.maximum(
            rng, np.maximum(np.abs(h - pc), np.abs(l - pc))) / pc).astype(np.float32)
    del pc, rng
    # ★L1 子面板: 粗筛不需要全样本(瓶颈是内存带宽, 不是计算)。
    #   时间只取 START 之后 + 截面随机抽样 -> 数据量降到 ~1/4, 实测整体提速 3~4 倍。
    #   L1 只是排序用, 抽样误差可接受; L2 精筛仍用全样本。
    global L1_ROWS, L1_COLS, L1_POOL_MASK
    L1_ROWS = np.where(dates >= START)[0]
    if MINE_POOL != 'all':
        # ★池内挖掘(§8.19): L1 列 = 池**并集**(不随机抽样 —— 必须保证任一时点的成分都在)。
        #   掩码另按 PIT 生效, 故并集稍大不影响口径。
        import loop_pools as _LP
        uni = _LP.pool_union(MINE_POOL)
        L1_COLS = np.array([i for i, c in enumerate(cols) if c in uni], dtype=np.int64)
        if L1_COLS.size == 0:
            raise SystemExit(f"[--mine_pool={MINE_POOL}] 池并集与面板列无交集, 检查股票代码格式")
        L1_POOL_MASK = _LP.pool_mask(MINE_POOL, dates, cols)[np.ix_(L1_ROWS, L1_COLS)]
        print(f"[--mine_pool={MINE_POOL}] L1 子面板列 = 池并集 {L1_COLS.size} 只; "
              f"当期池成分中位 {int(np.median(L1_POOL_MASK.sum(1)))} 只 "
              f"(面板共 {close.shape[1]} 列)")
    else:
        nsub = min(close.shape[1], L1_STOCKS)
        L1_COLS = np.sort(np.random.default_rng(20240917).choice(
            close.shape[1], nsub, replace=False))
        L1_POOL_MASK = None
    B_sub = {k: v[np.ix_(L1_ROWS, L1_COLS)] for k, v in B.items()}
    _BASE = dict(B=B, B_sub=B_sub, dates=dates, cols=cols, close=close)
    return _BASE


def append_csv_schema_safe(path, df=None, new_cols=None):
    """**Schema-aware** 追加写 CSV；发现 schema 变化就重写整文件（旧行对齐到新 schema）。

    为什么必须这样（2026-09-13 实录, roadmap §8.30）：
      原先各处的写法是 `_need_h = 文件不存在或为空` + `to_csv(mode='a', header=_need_h)`，
      即**默认 schema 永远不变**。而 2026-09-13 我给 `--pool_obs` 加了 5 列
      （ann_ex_cw/calmar_cw/dd_cw/sharpe_cw/tilt）⇒ 文件变成「**表头 10 列 + 旧行 10 列 +
      新行 15 列**」⇒ `pd.read_csv` 直接报
        `ParserError: Expected 10 fields in line 222, saw 15`
      ⇒ **所有下游报告全崩**，而且崩在**离线脚本**里，引擎自己毫无察觉（静默数据损坏）。
      ★ 本项目其实早就知道这个坑（见 `STYLE_OBS`/`STRIP_OBS` 的注释「追加模式下加列会让历史行
        错位」），解法一直是"**另开一个文件**"。那次我改的正是**已有文件** ⇒ 违反了这条规则。
      ⇒ 根治：写入端**必须与当前 schema 对账**；不一致就重写（这些文件只有几百~几万行，成本可忽略）。
        并且**尽量救回已有数据** —— 混合宽度时按行宽判断该行属于旧头还是新 schema。

    df=None 时 = **只修复**（用 new_cols 对账现有文件）。
    返回 (状态字符串, 修复/写入的行数)。
    """
    import csv
    if new_cols is None:
        new_cols = list(df.columns) if df is not None else None
    if not new_cols:
        return ('skip: 无列信息', 0)

    if (not os.path.exists(path)) or os.path.getsize(path) == 0:
        if df is None:
            return ('absent', 0)
        df.to_csv(path, index=False, header=True, encoding='utf-8-sig')
        return ('created', len(df))

    with io.open(path, encoding='utf-8-sig', newline='') as fh:
        rr = [r for r in csv.reader(fh) if r]
    if not rr:
        if df is None:
            return ('empty', 0)
        df.to_csv(path, index=False, header=True, encoding='utf-8-sig')
        return ('created', len(df))
    hdr, body = rr[0], rr[1:]

    if hdr == list(new_cols):                       # schema 一致 -> 直接追加
        if df is None:
            return ('ok(无需修复)', 0)
        df.to_csv(path, index=False, mode='a', header=False, encoding='utf-8-sig')
        return ('appended', len(df))

    # ---- schema 变了(或文件已混合宽度) -> 重写 ----
    # 救数据: 行宽 == 旧表头列数 -> 按旧头对齐; 行宽 == 新 schema 列数 -> 按新 schema 对齐
    rows, dropped = [], 0
    for parts in body:
        if len(parts) == len(hdr):
            d = dict(zip(hdr, parts))
        elif len(parts) == len(new_cols):
            d = dict(zip(new_cols, parts))
        else:
            dropped += 1
            continue
        rows.append({c: d.get(c, '') for c in new_cols})
    old = pd.DataFrame(rows, columns=list(new_cols))
    out = pd.concat([old, df], ignore_index=True) if df is not None else old
    out.to_csv(path, index=False, header=True, encoding='utf-8-sig')
    msg = (f'rewritten(旧{len(old)}行{"+新" + str(len(df)) + "行" if df is not None else ""}'
           f'{"，丢弃" + str(dropped) + "行无法识别" if dropped else ""})')
    return (msg, len(out))


def ex_max_corr(ex_new, bank_ex, min_overlap=30):
    """新因子的**费后超额序列** vs 库内全部收益流的**最大 |Spearman 相关|**。

    为什么用"收益流"而不是"表达式/因子值"做去重（2026-09-13, roadmap §8.33 实测）：
      · 库内 30 个入库因子的**组合收益序列两两相关中位 0.967**（max 0.994）——
        **它们是同一块钱的不同写法**；等权合成的 Calmar(0.978) 还**低于**最好的单因子(1.146)
        ⇒ 合成无效 ⇒ 库里其实只有"一个因子"。
      · 同时结构层面**极其多样**（`tools/analyze_diversity.py`：全A 1439 条候选里
        结构骨架 1181 个唯一、Top5 仅占 1.9%）⇒ **表达式去重挡不住"同一块钱"**。
      ⇒ ⇒ 所以"重复"必须**按收益流判**：换叶子/换窗口/换外壳赚同一块钱的，应当归为同族。

    返回 (max|corr|, 命中的库内表达式)；无从判定返回 (None, None)。
    口径: 只取两条序列**共同日期**上的有限值对；重叠期数 < min_overlap 则跳过(不当成重复)。
    """
    if ex_new is None or not bank_ex:
        return None, None
    try:
        en = pd.Series(ex_new).astype('float64')
    except Exception:
        return None, None
    if len(en) < min_overlap:
        return None, None
    best, who = 0.0, None
    for k, ex_old in bank_ex.items():
        try:
            eo = pd.Series(ex_old).astype('float64')
            a, b = en.align(eo, join='inner')
            m = np.isfinite(a.values) & np.isfinite(b.values)
            if int(m.sum()) < min_overlap:
                continue
            # 用两个"新建的 Series"(默认 RangeIndex)对齐后算 Spearman, 避免索引不一致
            c = abs(float(pd.Series(a.values[m]).corr(pd.Series(b.values[m]),
                                                      method='spearman')))
            if np.isfinite(c) and c > best:
                best, who = c, k
        except Exception:
            continue
    return (best if who is not None else None), who


def style_features(B):
    """风格观测四项(与 `standard_test.py`【3】风格归因同口径, 20 日均值 + log):
    lncap=log(市值) / lnamt=log(20日均成交额) / lntr=log(20日均换手率) / lnpx=log(收盘价)。
    0/非正 -> NaN(与 standard_test 的 replace(0,nan) 一致), 由 rank_rows/style_expo 跳过。"""
    mc = np.where(B['mktcap'] > 0, B['mktcap'].astype('float64'), np.nan)
    turn = B['turnover'].astype('float64')
    amt20 = pd.DataFrame(turn).rolling(20, min_periods=5).mean().values
    tr20 = pd.DataFrame(turn / mc).rolling(20, min_periods=5).mean().values
    px = np.where(B['close'] > 0, B['close'].astype('float64'), np.nan)
    with np.errstate(invalid='ignore', divide='ignore'):
        out = {'lncap': np.log(mc),
               'lnamt': np.log(np.where(amt20 > 0, amt20, np.nan)),
               'lntr': np.log(np.where(tr20 > 0, tr20, np.nan)),
               'lnpx': np.log(px)}
    return {k: v.astype(np.float32) for k, v in out.items()}


# ===================== 2. 算子 =====================
def ts_mean(x, w):
    return pd.DataFrame(x).rolling(w, min_periods=max(2, w // 2)).mean().values


def ts_std(x, w):
    return pd.DataFrame(x).rolling(w, min_periods=max(2, w // 2)).std().values


def ts_sum(x, w):
    return pd.DataFrame(x).rolling(w, min_periods=max(2, w // 2)).sum().values


def ts_max(x, w):
    return pd.DataFrame(x).rolling(w, min_periods=max(2, w // 2)).max().values


def ts_min(x, w):
    return pd.DataFrame(x).rolling(w, min_periods=max(2, w // 2)).min().values


def ts_rank(x, w):
    """过去w日当前值的分位(快)"""
    mn = ts_min(x, w)
    mx = ts_max(x, w)
    return (x - mn) / (mx - mn + 1e-12)


def ts_delay(x, n):
    return pd.DataFrame(x).shift(n).values


def ts_delta(x, n):
    return x - pd.DataFrame(x).shift(n).values


def ts_corr(x, y, w):
    return pd.DataFrame(x).rolling(w, min_periods=max(3, w // 2)).corr(
        pd.DataFrame(y)).values


def ts_max_op(x):
    import fastops
    return fastops.ts_max(x, 20)


def ts_min_op(x):
    import fastops
    return fastops.ts_min(x, 20)


def ts_corr20_op(a, b):
    import fastops
    return fastops.ts_corr(a, b, 20)


def ts_corr60_op(a, b):
    import fastops
    return fastops.ts_corr(a, b, 60)


def cs_rank_op(x):
    return cs_rank(pd.DataFrame(x)).values


def cs_demean_op(x):
    df = pd.DataFrame(x)
    return df.sub(df.mean(axis=1), axis=0).values


def cs_scale_op(x):
    r = cs_rank_op(x)
    return (r - 0.5) * 2


def _m(x, w):
    import fastops
    return fastops.ts_mean(x, w)


def _s(x, w):
    import fastops
    return fastops.ts_std(x, w)


def _r(x, w):
    import fastops
    return fastops.ts_rank(x, w)


def _mx(x, w):
    import fastops
    return fastops.ts_max(x, w)


def _mn(x, w):
    import fastops
    return fastops.ts_min(x, w)


def _sm(x, w):
    import fastops
    return fastops.ts_sum(x, w)


def _cr(a, b, w):
    import fastops
    return fastops.ts_corr(a, b, w)


UNARY = {
    # 短中窗口(原)
    'ts_mean5': lambda x: _m(x, 5),
    'ts_mean10': lambda x: _m(x, 10),
    'ts_mean20': lambda x: _m(x, 20),
    'ts_std20': lambda x: _s(x, 20),
    'ts_std60': lambda x: _s(x, 60),
    'ts_max20': lambda x: _mx(x, 20),
    'ts_min20': lambda x: _mn(x, 20),
    'ts_rank20': lambda x: _r(x, 20),
    'ts_rank60': lambda x: _r(x, 60),
    'ts_delay1': lambda x: ts_delay(x, 1),
    'ts_delta5': lambda x: ts_delta(x, 5),
    'ts_delta20': lambda x: ts_delta(x, 20),
    'ts_sum20': lambda x: _sm(x, 20),
    # ★长窗口(中金: 51-100天52次 / 151-200天23次, 明显中长窗口偏好)
    'ts_mean60': lambda x: _m(x, 60),
    'ts_mean100': lambda x: _m(x, 100),
    'ts_mean120': lambda x: _m(x, 120),
    'ts_mean150': lambda x: _m(x, 150),
    'ts_mean200': lambda x: _m(x, 200),
    'ts_std100': lambda x: _s(x, 100),
    'ts_std150': lambda x: _s(x, 150),
    'ts_std200': lambda x: _s(x, 200),
    'ts_rank100': lambda x: _r(x, 100),
    'ts_rank200': lambda x: _r(x, 200),
    'ts_max100': lambda x: _mx(x, 100),
    'ts_min100': lambda x: _mn(x, 100),
    'ts_delta60': lambda x: ts_delta(x, 60),
    'ts_delta120': lambda x: ts_delta(x, 120),
    'ts_sum100': lambda x: _sm(x, 100),
    'log': lambda x: np.log(np.maximum(x, 1e-9)),
    'abs': np.abs,
    'neg': lambda x: -x,
    'sign': np.sign,
    'cs_rank': cs_rank_op,
    'cs_demean': cs_demean_op,
    'cs_scale': cs_scale_op,
}

BINARY = {
    'add': lambda a, b: a + b,
    'sub': lambda a, b: a - b,            # 中金: sub 出现率 94%(差值/背离结构为主)
    'mul': lambda a, b: a * b,
    'div': lambda a, b: a / np.where(np.abs(b) > 1e-9, b, np.nan),
    'corr20': lambda a, b: _cr(a, b, 20),
    'corr60': lambda a, b: _cr(a, b, 60),
    'corr100': lambda a, b: _cr(a, b, 100),
    'corr200': lambda a, b: _cr(a, b, 200),
    'min': lambda a, b: np.minimum(a, b),
    'max': lambda a, b: np.maximum(a, b),
}

# ★LEAVES 完整叶子池已由顶部 `from loop_fields import LEAVES` 提供
#   (基础7 + 派生12 + MF16资金流 + BARRA11风格 + FA8财报 = 54), 勿在此重复硬编码(防漂移)

# ===================== 3. 表达式 =====================
class Node(object):
    __slots__ = ('op', 'args')

    def __init__(self, op, args):
        self.op = op
        self.args = args

    def __str__(self):
        if not self.args:
            return self.op
        return f"{self.op}({', '.join(str(a) for a in self.args)})"

    def key(self):
        """结构哈希(用于FSA), 忽略叶子名差异时可用 op-only"""
        if not self.args:
            return self.op
        return (self.op, tuple(a.key() if isinstance(a, Node) else a
                               for a in self.args))

    def size(self):
        return 1 + sum(a.size() for a in self.args if isinstance(a, Node))


def norm_op(op):
    """算子族归一化: ts_mean20 -> ts_mean / corr60 -> corr (剥窗口数字, 保留算子族)"""
    for p in ('ts_mean', 'ts_std', 'ts_sum', 'ts_max', 'ts_min',
              'ts_rank', 'ts_delay', 'ts_delta', 'corr'):
        if op.startswith(p):
            return p
    return op


def skeleton(node):
    """骨架键 = 算子族名 + 树结构 + 叶子身份(保留叶子名), 完全剥离窗口数字。
    对齐中金 FSA 的'抽象因子结构': ts_std60/ts_std100/ts_std150 视为同一骨架,
    只换窗口的同族候选会被识别为重复骨架, 由冻结/入库上限机制拦下。"""
    if not node.args:
        return node.op
    return norm_op(node.op) + '(' + ','.join(
        skeleton(a) if isinstance(a, Node) else str(a)
        for a in node.args) + ')'


def skeleton_freq(nodes):
    """统计一组表达式的完整骨架频次(用于FSA冻结与库内骨架去重)"""
    c = {}
    for nd in nodes:
        s = skeleton(nd)
        c[s] = c.get(s, 0) + 1
    return c


def subtree_skels(node):
    """候选的全部【非叶子】子树骨架集合(叶子/字段名不算结构, 防'某字段出现>15%'误冻结)"""
    out = set()
    for x in collect(node):
        if x.args:
            out.add(skeleton(x))
    return out


def has_frozen_skel(node, frozen):
    """候选是否含任一已冻结的结构骨架(中金: 冻结骨架禁止复用 -> 生成端丢弃/入库端审查)"""
    return bool(frozen and (subtree_skels(node) & set(frozen)))


# ---- 结构族聚类(QuantaAlpha 冗余检测移植): 拦"外层模板固定、内层微调"的同构霸榜族 ----
FAM_CUT = 3          # 模板指纹展开算子层数(cut 层以下折叠)
FAM_QUOTA = 2        # L1 同模板族候选进 L2/种子池上限
FAM_BLOCK_THR = 0.5  # 上代 L1 同模板族占比 >= 该值 -> 本代生成端禁产该模板族


def sole_leaf(node):
    """若 node 经"纯单目算子链"化简后恰为单一叶子, 返回该叶名; 否则 None。
    ts_min20(cs_rank(barra_leverage)) -> 'barra_leverage'; div(leverage, gm) -> None。"""
    cur = node
    while isinstance(cur, Node) and cur.args:
        if len(cur.args) != 1:
            return None
        cur = cur.args[0]
    return cur.op if isinstance(cur, Node) else None


def leaf_proxy_key(node):
    """gen51 叶子代理族键: 顶层 max/min 若有一支经"纯单目算子链"化简后恰为单一叶子,
    则该候选信息量≈该叶(numerically 也确如此: ts_min20(cs_rank(barra_leverage)) 与
    barra_leverage 相关 0.997), 只是"某叶套壳+地板" -> 返回族键, 把"同叶不同壳"的候选
    合并为一族, 由 fam_quota 拦重复(防不同外壳反复重发现同一叶、制造虚假多样性)。
    键含另一支(地板)若为裸叶则一并纳入, 避免把不同地板结构误并。
    返回 None 表示非叶子代理, 回落常规 root_fam 指纹。"""
    if not isinstance(node, Node) or node.op not in ('max', 'min') or len(node.args) != 2:
        return None
    a, b = node.args
    for inner, other in ((a, b), (b, a)):
        if isinstance(inner, Node) and inner.args:
            sl = sole_leaf(inner)
            if sl is not None:
                ol = other.op if (isinstance(other, Node) and not other.args) else ''
                return '~' + sl + ('|' + ol if ol else '')
    return None


def root_fam(node, cut=FAM_CUT, use_sole=True):
    """模板族指纹: 叶子统一'X'(身份无关) + 窗口剥除 + 距根cut层以下折叠'#'。
    mul(turnover,ts_min100(corr100(overnight, <任意深>))) 成员 -> 同一指纹, 判同族。
    gen51 起增补"单叶变换"维度: 顶层 max/min 的内层若只是某叶的单目变换(=叶子代理),
    直接返回 '~<叶名>[|<地板叶>]' 作为族键 -> 同叶不同壳的代理候选合并同族。"""
    if use_sole:
        pk = leaf_proxy_key(node)
        if pk is not None:
            return pk

    def rec(nd, d):
        if not nd.args:
            return 'X'
        if d >= cut:
            return '#'
        return norm_op(nd.op) + '(' + ','.join(
            rec(a, d + 1) if isinstance(a, Node) else 'X' for a in nd.args) + ')'
    return rec(node, 0)


def fam_quota_rows(rows, quota=FAM_QUOTA, use_sole=True):
    """score 降序的 L1 行上做模板族配额: 同族至多保留 quota 条(保跨族多样), 返回过滤后行集"""
    cnt, keep, n_block = {}, [], 0
    for _, r in rows.iterrows():
        f = root_fam(r['node'], use_sole=use_sole)
        c = cnt.get(f, 0)
        if c >= quota:
            n_block += 1
            continue
        cnt[f] = c + 1
        keep.append(r)
    return pd.DataFrame(keep), len(cnt), n_block


def _tag_desc(tag):
    """池标签的中文含义（转发到单一事实源 loop_pools.tag_desc）。"""
    import loop_pools as _lp
    return _lp.tag_desc(tag)


def _gate_of(args):
    """从命令行参数提取**实际生效的判定门槛**（供 `loop_critic.diagnose` 对账）。

    ★★★ 为什么必须有这个函数（2026-09-14，`docs/loop_todo.md` §1.1 问题②）：

      `loop_critic.py:94` 曾写死 `fail_calmar = (fail['calmar'] <= 0.5).mean()` ——
      **硬编码 0.5 且取全A 口径**；而**池内模式**的判定用的是**池口径**
      （`任一池 Calmar > --min_pool_calmar`）⇒ **传感器测的不是真正卡住候选的那道门**
      ⇒ 实测 `1000 gen1` 报 `fail_calmar=1.000`，而同代**确有 2 个候选 Calmar 0.661/0.561 入库**
      （指标自相矛盾），且 **96/96 代**都触发规则5 ⇒ `depth` 被**永久**推到 `[3,4,4]`。

    **单一事实源纪律**：门槛**只从 `args` 读一次**（本函数），引擎自己那份 `_pool_gate_on`
    也由同一逻辑推出 ⇒ 两侧不会再漂移。改门槛相关的 flag 时，**只改这里**。
    """
    _mpc = float(getattr(args, 'min_pool_calmar', -1.0) or -1.0)
    return dict(min_calmar=float(getattr(args, 'min_calmar', 0.0)),
                min_sharpe=float(getattr(args, 'min_sharpe', 0.5)),
                min_pool_calmar=_mpc,
                pool_gate_on=(_mpc >= 0),          # 默认 -1 = 关; >=0 启用(0 是合法阈值)
                pool_mode=getattr(args, 'pool_gate_mode', 'any') or 'any',
                or_all=bool(getattr(args, 'pool_gate_or_all', False)))


def _pool_best(pool_rows):
    """把 `pool_rows`（逐候选 × 逐池的长表）压成 `{expr: 该候选**最好**的池 calmar}`。

    这是 `loop_critic.diagnose` 的**池口径传感器**输入。
    ★ 为什么取 **max**：池门槛的默认语义是 `any`（**任一池**达标即达标），
      而诊断要回答的是"**离最近的那条通道差多远**" ⇒ max 正确。
      （`all` 语义下 max 不足以判定，但那属于"判定"的职责，不是"诊断"的 ——
       诊断只需指出**有没有一条通道够得着**。）
    ⚠ 缺数据时返回 `{}`（而不是臆造 0）⇒ `diagnose` 会**不产出** `fail_pool_calmar`
      （与 strip / 池门槛 / LLM 同一条"缺失即不臆造"的铁律）。
    """
    out = {}
    for r in (pool_rows or []):
        try:
            e = str(r['expr'])
            c = float(r['calmar'])
        except Exception:
            continue
        if not np.isfinite(c):
            continue
        if e not in out or c > out[e]:
            out[e] = c
    return out


def combine_ok(ok_base, ok_q, ok_pool, ok_hard, pool_gate_on, or_all):
    """L2 入库判定的组合逻辑 —— **单一事实源**（2026-09-14 从内联代码提取，见 loop_todo §1.17）

    :param ok_base: `factor_miner.pass_filter` 的结果（11 项基础标准）
    :param ok_q:    「全A 量化口径」= `calmar>min_calmar 且 sharpe>min_sharpe`（+分段，见调用点）
    :param ok_pool: 「池内量化口径」= 任一/全部池 `calmar > min_pool_calmar`；**`None` = 无从判定**
    :param ok_hard: **硬门槛**（剥风格 + 分段独立验证）—— 与"选哪个口径"**无关**，必须**无条件**生效
    :param pool_gate_on: `--min_pool_calmar >= 0`
    :param or_all:       `--pool_gate_or_all`

    ★★★ 为什么必须把 `ok_hard` 独立出来（本次修的 bug）：

    原实现（L2015-2024）：
    ```python
    _ok_prev = ok                     # 快照取在 _ok_q **之前**
    ok = ok and _ok_q
    ...
    ok = ok and seg_ok                # 分段独立验证
    ok = ok and strip_ok              # 剥风格门槛
    ...
    elif _pool_gate_or_all:
        ok = _ok_prev and (_ok_q or _pok)      # ★ 用旧快照**整个重建**
    ```
    注释本意是「**只撤掉 `_ok_q`**」（否则 OR 退化成 AND），但 `_ok_prev` 取在 `_ok_q` 之前
    ⇒ 它**同时撤掉了后面才 AND 进去的 `seg_ok` 与 `strip_ok`**。

    **实测后果**：`--pool_gate_or_all` 一旦开启（§8.26，2026-09-13 起），池轨道的
    「剥风格门槛」与「分段独立验证」**完全失效且无告警** —— 池后缀 13 个入库因子里
    **8 个是「纯风格」（C 档，`strip_calmar` 全为负）**，本该被 `--min_strip_calmar=0.15` 全部拦下。

    ⇒ **OR 只该作用于「全A 口径 **vs** 池内口径」这个二选一**；
      剥风格 / 分段验证是**因子本身的品质关**，与选哪个口径无关 ⇒ 记进 `ok_hard`，
      在池门槛段**之后**统一 AND 回来，**不参与 OR**。

    ⚠ `ok_pool is None`（未开 `--pool_obs` / 计算失败）⇒ **放行不误杀**（与 strip/LLM 同一铁律），
      但调用点要计数并在代末上报，否则门槛静默失效而无人察觉。
    """
    if not pool_gate_on or ok_pool is None:
        ok = bool(ok_base and ok_q)
    elif or_all:
        ok = bool(ok_base and (ok_q or ok_pool))
    else:
        ok = bool(ok_base and ok_q and ok_pool)
    return bool(ok and ok_hard)          # ★ 硬门槛最后统一 AND，**不参与 OR**


def _mk_library_skeleton(fname):
    """为某个池创建 `factor_library_{pool}.md` 的最小骨架（2026-09-13, roadmap §8.44）。

    为什么必须自动建：per-pool 路径由 `set_mine_pool` 派生，但这三个文件**从未被创建**
    ⇒ `_lib_sync` 原先遇到不存在就 `return`，把失败**完全吞掉** ⇒ 池轨道入库的因子
    **一个都没进文档**（实测 1000 池 2 代 3 个因子、300 池 1 个因子全丢）。

    ⚠ 骨架**必须含三个锚点**，否则 `_lib_sync` 的插入逻辑不成立（会再次静默出错）：
      ① `> 当前 **N 个入库**`  —— 供其 `re.sub` 更新计数
      ② `## 因子明细`          —— 明细小节插在它之前
      ③ `## 相关文件导航`      —— 明细插在它之前
    """
    tag = 'all'
    m = re.search(r'factor_library_(.+)\.md$', fname)
    if m:
        tag = m.group(1)
    sfx = '' if tag == 'all' else '_' + tag
    txt = (
        '# 因子库（池 = {t}）\n\n'
        '> 当前 **0 个入库**\n'
        '> 本文件由引擎在**每代末尾自动同步**（`--mine_pool={t}` 时生效；实现见 `_lib_sync`）。\n'
        '> ⚠ 与全A 轨道的 `docs/factor_library.md` **互不读写**（池隔离，见 roadmap §8.42）。\n\n'
        '---\n\n'
        '## 因子总览\n\n'
        '| 编号 | 入库代数 | 家族 | 一句话 | 状态 |\n'
        '|---|---|---|---|---|\n\n'
        '## 因子明细\n\n'
        '## 相关文件导航\n\n'
        '| 文件 | 内容 |\n|---|---|\n'
        '| `docs/factor_library{s}.md`（本文件） | 池 **{t}** 的入库因子（只增不改） |\n'
        '| `docs/factor_library.md` | 全A 轨道的入库因子 |\n'
        '| **`docs/factor_library_crosspool.md`** | ★ **跨池派生视图**：各池库里**全A 有效**的因子'
        '去重 + 池标签并集修正（`python tools/build_crosspool_view.py` 生成） |\n'
        '| `docs/loop_journal{s}.md` | 池 **{t}** 的每代诊断 + B角下一代参数 |\n'
        '| `docs/loop_pool_obs{s}.csv` | 池 **{t}** 候选的**三池池内指标**宽表 |\n'
        '| `docs/loop_archive{s}.csv` | 池 **{t}** 每代 L2 全量候选流水 |\n'
    ).format(t=tag, s=sfx)
    io.open(LIBRARY, 'w', encoding='utf-8').write(txt)


def _lib_sync(gen, res, n_total, added_exprs, expr2nd, pool_tags=None, strip_grades=None):
    """本代新入库因子自动同步追加进 docs/factor_library.md(只增不改历史, 家族命名留待人工精炼)。
    幂等: 编号取文本现有最大 F{nn}+1; 任何失败仅告警, 绝不影响入库主流程。
    added_exprs: 本代真正 append 进 bank 的 expr 列表; expr2nd: {str(node): node}(模块已有 Node/skeleton)。
    pool_tags  : ★ 2026-09-13 新增 {expr: pool_tag} —— 用户要"一眼看出这个因子是全A+哪个池好用、
                 还是只有全A好用"。规则来自 `loop_pools.derive_tag`（单一事实源），
                 与 `standard/pool_tags.py` 派生出的 `docs/pool_tags.csv` **同一套口径**。
                 没跑到 `--pool_obs` 时字典为空 -> 该行写"未测(--pool_obs 未开)"，**不写未知标签**。"""
    import re
    import io
    try:
        if not added_exprs:
            return
        if not os.path.exists(LIBRARY):
            # ★★ 不再静默跳过（2026-09-13 实录, roadmap §8.44）：
            #   per-pool 的 LIBRARY 路径是 `set_mine_pool` 派生的（`factor_library_{pool}.md`），
            #   而这三个文件**从来没被创建过** ⇒ 原先的 `return` 把失败**完全吞掉**
            #   （不报错、不告警、不留痕）⇒ 实测 `--mine_pool=1000` 连跑 2 代入库 **3 个因子**，
            #   文档**一个都没写**；300 池入库的那 1 个也从没写进 `factor_library_300.md`。
            #   ⚠ 这与今天修的 `--pool_obs` 是**同一类坑**：新功能只做了一半（路径派生了、
            #     文件没人建），而且**失败无声**。⇒ 修法：**自动创建骨架 + 明确打印**。
            _mk_library_skeleton(os.path.basename(LIBRARY))
            print(f"  [文档] {os.path.basename(LIBRARY)} 不存在 -> **已自动创建骨架**"
                  f"（首次同步；此前该池的入库因子从未写进文档）")
        rows = {str(r['expr']): r for _, r in res.iterrows()} if len(res) else {}
        txt = io.open(LIBRARY, encoding='utf-8').read()
        nos = [int(x) for x in re.findall(r'\bF(\d{2})\b', txt)]
        no = (max(nos) + 1) if nos else 1
        tbl_rows, det_rows = [], []
        for expr in added_exprs:
            r = rows.get(expr)
            if r is None:
                continue
            nd = expr2nd.get(expr)
            cat_s = str(r['cat']); leaf_s = str(r['leaf'])
            fam = (cat_s[:20] + '…') if len(cat_s) > 20 else (cat_s or '未分类')
            short = expr if len(expr) <= 44 else expr[:41] + '…'
            met = ('IC %.4f / IC_IR %.3f / 年化超额 %+.1f%% / 回撤 %.1f%% / '
                   'Calmar %.3f / Sharpe %.3f / 最近年 %+.1f%% / 单期换手 %.1f%% / 负年 %d'
                   % (r['ic'], r['ic_ir'], r['ann_ex'] * 100, r['dd'] * 100,
                      r['calmar'], r['sharpe'], r['last_yr'] * 100, r['turn'] * 100,
                      int(r['neg_yr'])))
            skel = skeleton(nd) if nd is not None else '?'
            _tg = (pool_tags or {}).get(expr)
            _tg_line = ('- 池标签：**`%s`** —— %s\n' % (_tg, _tag_desc(_tg))
                        if _tg else '- 池标签：未测（本代未开 `--pool_obs`）\n')
            # ★ 剥风格档（2026-09-14, §1.9）：**并列**于池标签，不替代它。
            #   为什么要写进文档：实测约一半入库因子是"纯风格"（全A 口径漂亮、剥掉
            #   lncap+lnamt 后转负），而**下游拿到文档就该一眼看出**，不能靠回头翻 CSV。
            _sg = (strip_grades or {}).get(expr)
            if _sg:
                _sg_k, _sg_txt = _sg[0], _sg[1]
                #  ★ 2026-09-14（§1.19）：判据已改**日频** ⇒ 文档里同时给日频（可缺）
                _scd, _sddd = (_sg[4] if len(_sg) > 4 else None,
                               _sg[5] if len(_sg) > 5 else None)
                _ddtxt = ''
                if _scd is not None and np.isfinite(_scd):
                    _ddtxt = '；**日频** 剥后 Calmar %.3f' % _scd
                    if _sddd is not None and np.isfinite(_sddd):
                        _ddtxt += '，日频回撤 %.1f%%' % (_sddd * 100)
                        if _sddd <= _lp.TAG_STRIP_DD_MIN:
                            _ddtxt += ' ⚠（劣于上限 %.2f ⇒ 只给 B）' % _lp.TAG_STRIP_DD_MIN
                _sg_line = ('- 剥风格：**`%s`** %s'
                            '（原 Calmar %.3f → 剥后 %.3f；超额 %+.1f%% → %+.1f%%%s）\n'
                            % (_sg_k, _sg_txt, r['calmar'], _sg[2],
                               r['ann_ex'] * 100, _sg[3] * 100, _ddtxt))
            else:
                _sg_line = ('- 剥风格：**未测**（本代未开 `--strip_style`）'
                            '⇒ ⚠ **不可断言它是独立 alpha**（见 roadmap §8.45 / loop_todo §1.9）\n')
            # ⚠ **不加表格列**（2026-09-13 实录）：总览表头是**固定 5 列**
            #   `| 编号 | 入库代数 | 家族 | 一句话 | 状态 |`，而本文件是 append-only、
            #   表头只写一次 ⇒ 加列会让**历史行全部错位**（与 §8.30 的 CSV 同一个坑）。
            #   ⇒ 池标签只写进**明细块**（用户正是看那里）。
            tbl_rows.append('| F%02d | gen%d | %s | %s | 已入库(auto) |'
                            % (no, gen, fam, short))
            det_rows.append(
                '\n### F%02d · gen%d 入库（引擎自动同步，家族命名待人工精炼）\n'
                '```\n%s\n```\n'
                '- 家族：%s（auto）\n- 叶子：%s\n- 骨架：`%s`\n'
                '%s%s'
                '- 费后指标（full，成本 %s）：%s\n'
                % (no, gen, expr, fam, leaf_s, skel, _tg_line, _sg_line,
                   cost_label(r['cost']), met))
            no += 1
        if not det_rows:
            return
        add_tbl = '\n'.join(tbl_rows)
        add_det = ''.join(det_rows)
        # 1) 头部计数行(自动同步计数)
        txt = re.sub(r'> 当前 \*\*\d+ 个入库\*\*', '> 当前 **%d 个入库**' % n_total,
                     txt, count=1)
        # 2) 总览表格末尾(## 因子明细 前最后一个 '| F' 数据行)后插入新行
        j = txt.find('\n## 因子明细')
        i = txt.rfind('\n| F', 0, j) if j > 0 else -1
        if i >= 0:
            k = txt.find('\n', i + 2)
            if k >= 0:
                txt = txt[:k] + '\n' + add_tbl + txt[k:]
        elif j > 0:
            # ★ 该池文档还没有任何数据行(刚建的骨架) -> 表行插在 '## 因子明细' 之前
            #   否则 `rfind('\n| F')` 返回 -1, 总览表**永远不会有数据行**(静默)。
            #   ⚠ 这里要**补两个换行**：`txt[j:]` 只带一个 `\n`，少一个空白行会让
            #     `## 因子明细` 被 markdown 当成表格的一部分（渲染错乱）。
            txt = txt[:j] + '\n' + add_tbl + '\n\n' + txt[j + 1:]
        # 3) 明细小节插在 '## 相关文件导航' 前(原 --- 分节保留, 新条目自带分隔)
        nav = '\n## 相关文件导航'
        p = txt.find(nav)
        if p < 0:
            txt = txt.rstrip('\n') + add_det + '\n'
        else:
            txt = txt[:p] + add_det + '\n---\n\n' + txt[p:]
        io.open(LIBRARY, 'w', encoding='utf-8').write(txt)
        # ⚠ 打印**真实文件名**（2026-09-13）：原先硬编码写 `factor_library.md`，
        #   池轨道跑时也在报 `factor_library.md`，**指到了别的文件** ⇒ 排查时误导。
        print(f"  [文档] {os.path.basename(LIBRARY)} 已自动追加 {len(det_rows)} 条新入库 "
              f"(F{nos and max(nos)+1 or 1}~F{no-1}, 累计 {n_total})")
    except Exception as e:
        # ⚠ 失败路径也要报**真实文件名**（2026-09-14 修）：成功路径早已改成 basename，
        #   失败路径却还硬编码 `factor_library.md` ⇒ 池轨道出错时会**指错文件**（§8.44 的孪生坑）。
        print(f"  [文档] {os.path.basename(LIBRARY)} 自动同步失败(不影响入库): "
              f"{type(e).__name__}: {e}")


# ===================== 跨量纲审查(中金审查规则之一) =====================
# 量纲族: P=价格元 / R=比率与收益率(无量纲) / V=股数 / A=成交额元 / M=市值元 /
#         L=对数标尺(ln) / Z=截面标准化(cs_rank/cs_demean/cs_scale) / C=复合(mul/div)
_FIELD_DIM = {
    'close': 'P', 'open': 'P', 'high': 'P', 'low': 'P', 'vwap': 'P',
    'ret': 'R', 'overnight': 'R', 'intraday': 'R', 'amplitude': 'R',
    'up_shadow': 'R', 'down_shadow': 'R', 'hl_ratio': 'R', 'true_range': 'R',
    'turn_ratio': 'R', 'volume': 'V', 'ln_volume': 'L', 'ln_mktcap': 'L',
    'turnover': 'A', 'mktcap': 'M',
    # 资金流金额列(×1e4 元, 与 turnover 同量纲 A) / 量列(×100 股, 与 volume 同 V)
    **{k: 'A' for k in MF16 if k.endswith(('_buy', '_sell'))},
    **{k: 'V' for k in MF16 if k.endswith(('_bqty', '_sqty'))},
    # BARRA 风格(Z化后相对值) / 财报 PIT 比率 -> R
    **{k: 'R' for k in BARRA_LEAVES},
    **{k: 'R' for k in FA_LEAVES},
}


def dim_of(node):
    """表达式(树)的'主导量纲'; 用于 add/sub/min/max 的同量纲审查"""
    if not node.args:
        return _FIELD_DIM.get(node.op, 'X')
    op = node.op
    if op in ('cs_rank', 'cs_demean', 'cs_scale'):
        return 'Z'
    if op == 'log':
        return 'L'
    if op.startswith('corr'):
        return 'R'
    if op in ('mul', 'div'):
        return 'C'
    if op in ('add', 'sub', 'min', 'max'):
        a, b = dim_of(node.args[0]), dim_of(node.args[1])
        if a == 'Z' or b == 'Z' or a == 'C' or b == 'C':
            return 'C'
        return a if a == b else 'X'
    if isinstance(node.args[0], Node):
        return dim_of(node.args[0])
    return 'X'


def review_expr(node):
    """静态审查(中金'审查规则'之一'跨量纲运算拒绝'): None=通过, str=拒绝原因。
    不同量纲的原始尺度直接 add/sub/min/max 无金融意义(如 close+volume), 纯浪费
    回测预算 -> 生成端拦截。mul/div/corr 放行(金融常见), cs_* 后(Z)可任意组合。
    顺带毙 div(x,x)/sub(x,x) 常数退化。"""
    for x in collect(node):
        if not x.args:
            continue
        if x.op in ('add', 'sub', 'min', 'max'):
            da, db = dim_of(x.args[0]), dim_of(x.args[1])
            if da not in ('Z', 'C') and db not in ('Z', 'C') and da != db:
                return f"跨量纲{x.op}({da} vs {db}): {x}"
        if x.op in ('sub', 'div') and str(x.args[0]) == str(x.args[1]):
            return f"{x.op}(x,x) 退化为常数: {x}"
    return None


# ===================== 失败模式库(中金: 失败表达式写入失败库, 生成阶段自动排除) =====================
# fail_lib = {骨架: dict(try_=参与测试数, ok=通过L1数, fail=失败数, rs={原因:计数}, last=最近代)}
def flib_mark(fail_lib, node, gen, ok, reason=''):
    e = fail_lib.setdefault(skeleton(node),
                            dict(try_=0, ok=0, fail=0, rs={}, last=gen))
    e['try_'] += 1
    e['last'] = gen
    if ok:
        e['ok'] += 1
    else:
        e['fail'] += 1
        e['rs'][reason] = e['rs'].get(reason, 0) + 1


def fail_lib_cleanup(fail_lib, gen, keep_gen=5):
    """滚动: 超过 keep_gen 代未再出现的骨架淘汰, 防库膨胀"""
    return {s: e for s, e in fail_lib.items() if e['last'] >= gen - keep_gen}


def bad_skels(fail_lib, gen, min_fail=3, rate=0.6, keep_gen=5):
    """失败模式 = 骨架试了 min_fail 次以上、从未通过L1、失败率>=rate -> 生成阶段排除"""
    return {s for s, e in fail_lib.items()
            if e['last'] >= gen - keep_gen and e['fail'] >= min_fail
            and e['ok'] == 0 and e['fail'] / max(e['try_'], 1) >= rate}


def pick_leaf(rng, cfg):
    w = [cfg['leaf_w'].get(l, 1.0) for l in LEAVES]
    return rng.choices(LEAVES, weights=w, k=1)[0]


def pick_op(rng, cfg, pool):
    w = [cfg['op_bias'].get(o, 1.0) for o in pool]
    return rng.choices(pool, weights=w, k=1)[0]


def rand_expr(rng, depth=3, cfg=None):
    cfg = cfg or DEFAULT_CFG
    if depth <= 0 or rng.random() < 0.25:
        return Node(pick_leaf(rng, cfg), [])
    r = rng.random()
    if r < 0.45:
        return Node(pick_op(rng, cfg, list(UNARY.keys())),
                    [rand_expr(rng, depth - 1, cfg)])
    return Node(pick_op(rng, cfg, list(BINARY.keys())),
                [rand_expr(rng, depth - 1, cfg), rand_expr(rng, depth - 1, cfg)])


def eval_expr(node, B, cache=None):
    if cache is not None and node.key() in cache:
        return cache[node.key()]
    if not node.args:
        v = B[node.op]
    elif len(node.args) == 1:
        v = UNARY[node.op](eval_expr(node.args[0], B, cache))
    else:
        a = eval_expr(node.args[0], B, cache)
        b = eval_expr(node.args[1], B, cache)
        v = BINARY[node.op](a, b)
    v = np.asarray(v, dtype=np.float32)
    if cache is not None:
        cache[node.key()] = v
    return v


def mutate(node, rng):
    """随机替换一个子树"""
    nodes = collect(node)
    tgt = rng.choice(nodes)
    tgt.op = rng.choice(list(UNARY.keys())) if len(tgt.args) == 1 else \
        (rng.choice(list(BINARY.keys())) if len(tgt.args) == 2
         else rng.choice(LEAVES))
    return node


def collect(node, out=None):
    out = [] if out is None else out
    out.append(node)
    for a in node.args:
        if isinstance(a, Node):
            collect(a, out)
    return out


# ---- 叶子字段族(写档用: loop_archive.csv 的 cat/leaf 列, 保证人读可筛) ----
LEAF_CAT = {
    'close': '价格', 'open': '价格', 'high': '价格', 'low': '价格', 'vwap': '价格',
    'ret': '收益率', 'overnight': '跳空', 'intraday': '日内收益',
    'amplitude': '振幅', 'hl_ratio': '振幅', 'true_range': '振幅',
    'up_shadow': '影线', 'down_shadow': '影线',
    'volume': '量', 'ln_volume': '量',
    'turnover': '成交额', 'turn_ratio': '换手率',
    'mktcap': '市值', 'ln_mktcap': '市值',
    # 扩展: 资金流 / 风格 / 财报
    **{k: '资金流' for k in MF16},
    **{k: '风格' for k in BARRA_LEAVES},
    **{k: '财报' for k in FA_LEAVES},
}


def leaf_parts(node):
    """按出现顺序提取去重叶子字段; 返回 (字段顿号串, 分类顿号串)"""
    cats, names = [], []
    for x in collect(node):
        if not x.args and x.op not in names:
            names.append(x.op)
            cats.append(LEAF_CAT.get(x.op, x.op))
    return '、'.join(names), '、'.join(cats)


def crossover(n1, n2, rng):
    a = rng.choice(collect(n1))
    b = rng.choice(collect(n2))
    a.op, a.args = b.op, b.args
    return n1


def perturb(node, rng):
    """参数扰动: 换一个同族算子(如 ts_mean20 -> ts_mean60)"""
    nodes = collect(node)
    tgt = rng.choice(nodes)
    if tgt.op.startswith('ts_') and any(c.isdigit() for c in tgt.op):
        fam = ''.join(c for c in tgt.op if not c.isdigit())
        alt = [k for k in list(UNARY.keys()) + list(BINARY.keys())
               if k.startswith(fam)]
        if alt:
            tgt.op = rng.choice(alt)
    return node


# ===================== 4. L1 批量 IC =====================
def trim_cache(cache, cap):
    """子树缓存容量控制: 条目超过 cap 时淘汰最早插入的键(dict 保插入序)。
    子树缓存只是加速(命中失败会重算), 淘汰不影响正确性。"""
    if cache is not None and len(cache) > cap:
        for k in list(cache.keys())[:len(cache) - cap]:
            cache.pop(k, None)


# rank_rows 已移至 loop_metrics.py（单一事实源, 2026-09-11）; 顶部 import 引入,
# 故本模块内 `rank_rows(...)` 与外部的 `loop_engine.rank_rows` 接口保持不变。


def factor_stability(V, dates=None, start=START, fwd=FWD):
    """因子稳定性 = 相邻调仓日截面rank的相关性(均值)
    稳定性低 -> 每次调仓Top组大换血 -> 换手高 -> 费后被成本吃光
    这是 L1 必须看、只看IC会漏掉的关键指标
    """
    sub = V[::fwd] if dates is None else V[dates >= start][::fwd]
    R = rank_rows(sub)
    cs = []
    for i in range(len(R) - 1):
        a, b = R[i], R[i + 1]
        m = np.isfinite(a) & np.isfinite(b)
        if m.sum() < 50:
            continue
        sa, sb = a[m].std(), b[m].std()
        if sa > 0 and sb > 0:
            cs.append(np.corrcoef(a[m], b[m])[0, 1])
    return float(np.nanmean(cs)) if cs else np.nan


def seg_verify(ex, k=3, need=2, min_pts=40):
    """分段独立验证(防"单段行情撑全样本"的伪稳健):
    把费后日度超额序列按时间均分 k 个不相交子区间, 每段累计费后超额>0 记 1 段达标,
    达标段数 >= need 才通过。数据太短不足以分段时保守放行(避免小样本误杀),
    但入库文档会以 seg_na 标注"未分段(样本不足)"。
    返回 (ok, n_pos, n_k, detail)。detail 形如 '段1+1.2%/段2-0.4%/段3+0.8%'。
    """
    if ex is None or len(ex) < k * min_pts:
        return True, -1, k, '未分段(样本不足)'
    need = min(need, k)          # 参数自洽: need 不能大于段数
    segs = np.array_split(ex, k)
    pos, n_pos = 0, []
    detail = []
    for i, s in enumerate(segs, 1):
        s = pd.Series(s).dropna()
        cum = float((1 + s).prod() - 1) if len(s) else float('nan')
        n_pos.append(cum)
        detail.append(f"段{i}{cum*100:+.1f}%")
        if cum > 0:
            pos += 1
    return (pos >= need), pos, k, '/'.join(detail)


def batch_ic(Fs, fwd_ret, U, dates=None, start=START):
    """Fs: list of (T,S); 返回 IC均值 / IC_IR / IC矩阵。
    dates=None 时按已切好的(子)面板直接使用。"""
    if dates is None:
        Uv, Rv = U, fwd_ret
        Fs_ = Fs
    else:
        m = (dates >= start)
        Uv, Rv = U[m], fwd_ret[m]
        Fs_ = [F[m] for F in Fs]
    Rr = rank_rows(Rv)
    ics = []
    for F in Fs_:
        Fr = rank_rows(F)
        X = np.where(Uv, Fr, np.nan)
        Y = np.where(Uv, Rr, np.nan)
        cnt = np.isfinite(X) & np.isfinite(Y)
        n = cnt.sum(axis=1)
        X0 = np.where(cnt, X, 0.0)
        Y0 = np.where(cnt, Y, 0.0)
        Xm = X0.sum(axis=1) / np.maximum(n, 1)
        Ym = Y0.sum(axis=1) / np.maximum(n, 1)
        Xz = np.where(cnt, X - Xm[:, None], 0.0)
        Yz = np.where(cnt, Y - Ym[:, None], 0.0)
        num = (Xz * Yz).sum(axis=1)
        d1 = np.sqrt((Xz ** 2).sum(axis=1))
        d2 = np.sqrt((Yz ** 2).sum(axis=1))
        c = np.where((d1 > 0) & (d2 > 0) & (n >= 50), num / (d1 * d2 + 1e-12), np.nan)
        ics.append(c)
    IC = np.array(ics)                       # (n_factors, n_days)
    mu = np.nanmean(IC, axis=1)
    sd = np.nanstd(IC, axis=1)
    ir = mu / np.where(sd > 0, sd, np.nan)
    return mu, ir, IC


# ===================== 5. 主循环 =====================
def run(args):
    t0 = time.time()
    rng = random.Random(args.seed)
    np.random.seed(args.seed)
    # ---- LLM 对话录音: 本代 A角/B角 与 DeepSeek 的全部往返落盘(ai_test, gitignore) ----
    # automation 无人值守, 人看不到实时 LLM 对话; 录音文件供跑代后随时回溯/本窗口转述。
    try:
        import loop_llm as _llm
        _conv_dir = os.path.join(os.path.dirname(HERE), 'ai_test', 'loop_conv')
        _llm.set_conv_path(os.path.join(_conv_dir, 'gen%02dC_conv.md' % args.gen))
        print(f"  LLM 对话录音 -> ai_test/loop_conv/gen{args.gen:02d}C_conv.md", flush=True)
    except Exception as _e:
        print(f"  (LLM 对话录音初始化失败: {_e})", flush=True)
    base = base_fields()
    B, dates, cols, close = base['B'], base['dates'], base['cols'], base['close']
    T, S = close.shape

    U = get_universe().reindex(index=dates, columns=cols).fillna(False).values
    fwd_ret = (close.shift(-(1 + FWD)) / close.shift(-1) - 1).values

    # 载入上一代: 种子 + B角建议
    seeds, fsa, prev_l1, prev_l2, bank = [], {}, None, None, []
    # ★ 收益流库(2026-09-13, roadmap §8.34): {表达式: 每期费后超额 Series} —— 收益流去重的对照集。
    #   缺它的旧 state 也能跑(只与"本次运行新入库的"比), 但要立即见效请先跑
    #   `tools/backfill_bank_ex.py` 补齐历史。
    bank_ex = {}
    frozen = []                # FSA冻结骨架列表(中金: 超15%被禁止复用)
    fail_lib = {}              # 失败模式库(骨架级成败滚动统计, 中金: 生成阶段排除)
    cfg = dict(DEFAULT_CFG)
    # ★ n_tested 的基准必须在**写盘之前**取好(2026-09-12 修 —— 这是一个崩在整代末尾的隐蔽 bug):
    #   原写法 `n_tested=st.get('n_tested',0)+len(cands) if os.path.exists(STATE) else len(cands)`
    #   的三元条件是在 `with open(STATE,'wb')` **之后**求值的 —— 而那一步已经把文件创建出来了
    #   ⇒ 条件**恒为 True**; 全新轨迹(无既有 state)时 `st` 从未绑定 ⇒ UnboundLocalError
    #   ⇒ 崩在**整代最后一行**(30 分钟计算白做, 且 state 被 0 字节覆盖)。
    #   实录: `--mine_pool=300` 首次全新轨迹即崩(loop_state_300.pkl 被创建为 0 字节)。
    n_tested_prev = 0
    # ★ 上一代的「池口径」传感器数据（2026-09-14, §1.1 修法②）：代首要**重审上一代**，
    #   而池结果不在 `last_l2` 里（那是全A 口径的表）⇒ 必须随 state 一起存。
    #   ⚠ 无 state 时必须能保持为 None（否则 `st` 未绑定 -> UnboundLocalError，
    #     这正是 §8.23 那个"崩在整代最后一行"的同类坑）。
    _prev_pool_map = None
    if os.path.exists(STATE):
        with open(STATE, 'rb') as f:
            st = pickle.load(f)
        n_tested_prev = st.get('n_tested', 0)
        seeds = st.get('seeds', [])
        fsa = st.get('fsa', {})
        if not fsa.pop('v2', False):
            fsa = {}      # 旧格式(md5子树哈希键)与骨架口径不兼容 -> 重新累计
        prev_l1 = st.get('last_l1', None)
        prev_l2 = st.get('last_l2', None)
        bank = st.get('bank', [])          # 历代入库因子(node) —— decorr 的对比对象
        bank_ex = st.get('bank_ex', {})    # ★ 收益流库(§8.34): {表达式: 每期费后超额 Series}
        if not isinstance(bank_ex, dict):
            bank_ex = {}
        frozen = st.get('frozen', [])
        fail_lib = st.get('fail_lib', {})  # 失败模式库
        cfg = st.get('cfg', cfg)
        _prev_pool_map = st.get('last_pool_map', None)
        print(f"载入上一代种子 {len(seeds)} 个, 入库因子 {len(bank)} 个, "
              f"冻结骨架 {len(frozen)} 个, 失败库 {len(fail_lib)} 条, "
              f"已测 {st.get('n_tested', 0)} 个候选")

    # ---- B角: 先审查上一代, 再据此定本代搜索策略 ----
    import loop_critic as critic
    if prev_l1 is not None and len(prev_l1):
        # ★ 传 gate + pool_map（2026-09-14, §1.1 修法①②）：让 B角 的传感器与**实际生效的门槛**对账，
        #   并在池内模式下改看**池口径**（那才是真实卡点）。代首用上一代存的 `last_pool_map`。
        diag = critic.diagnose(prev_l1, prev_l2, args.gen - 1,
                               gate=_gate_of(args), pool_map=_prev_pool_map)
        cfg, reasons = critic.suggest(diag, cfg)
        print("\n[B角建议] 本代搜索策略:")
        for r in reasons:
            print("  -", r)
    else:
        print("\n[B角] 首代, 使用默认策略")
    # ---- 结构族黑名单(QuantaAlpha 正交思想, gen31): 上代 L1 霸榜模板族 ----
    # 上代同模板族(叶子身份无关指纹)占比 >= FAM_BLOCK_THR -> 本代生成端禁产(硬闸换血);
    # top2 模板文本另注入 A角 LLM 提示词(软约束)。根治"同族霸榜 -> 0 通过"空转。
    block_fams, fam_black_txt = set(), ''
    if prev_l1 is not None and len(prev_l1):
        fam_cnt = {}
        for nd in list(prev_l1['node']):
            f = root_fam(nd)
            fam_cnt[f] = fam_cnt.get(f, 0) + 1
        n_pv = len(prev_l1)
        tops = sorted(fam_cnt.items(), key=lambda x: -x[1])
        if args.fam_block_thr > 0 and tops and tops[0][1] / n_pv >= args.fam_block_thr:
            block_fams = {tops[0][0]}
        fam_black_txt = '；'.join(f'「{f}」({c}/{n_pv}条)' for f, c in tops[:2])
    if block_fams:
        print(f"  [族黑名单] 上代 L1 同模板族占比>={args.fam_block_thr:.0%} -> "
              f"本代生成端禁产该模板族, 强制结构换血")
    # 五维配比护栏(与 critic.suggest 出口同源): 即使旧state cfg 漂移且本轮无规则触发
    # (如无上一代), 本代实际生效 mix 也强制回到中金规格内(变异/交叉≥10%、槽位15/20/15)
    cfg['mix'] = critic.guard_mix(cfg.get('mix'))
    print(f"  五维配比 mix={[round(x, 3) for x in cfg['mix']]} "
          f"(变异/交叉自适应≥{critic.MIX_MIN:.0%}, 扰动/引导/随机=15/20/15)")
    # B角建议落地(命令行显式指定则优先)
    if args.decorr < 0:
        args.decorr = cfg.get('decorr', 0.0)
    if args.fsa_th < 0:
        args.fsa_th = cfg.get('fsa_th', 0.0)   # 0=关闭FSA冻结
    args.min_stab = cfg.get('min_stab', args.min_stab)
    args.bank_skel_max = cfg.get('bank_skel_max', args.bank_skel_max)
    print(f"  本代参数: min_stab={args.min_stab:.2f}  decorr={args.decorr:.2f}  "
          f"fsa_th={args.fsa_th:.2f}  bank同骨架上限={args.bank_skel_max}  "
          f"depth={cfg['depth']}")
    if frozen:
        print(f"  [FSA] 本代生效冻结骨架 {len(frozen)} 个(生成时禁止复用)")

    # ---- 失败模式库: 载入后按滚动窗口算出本代应排除的'坏骨架' ----
    if args.dim_review < 0:
        args.dim_review = 1                      # 跨量纲审查默认开启
    # 命令行显式指定则优先, 否则用 B角cfg(默认开: fail_rate=0.6, min_fail=3)
    if args.fail_rate < 0:
        args.fail_rate = cfg.get('fail_rate', 0.6)
    if args.min_fail <= 0:
        args.min_fail = cfg.get('min_fail', 3)
    bad = bad_skels(fail_lib, args.gen, min_fail=args.min_fail,
                    rate=args.fail_rate) if args.fail_rate > 0 else set()
    if bad:
        print(f"  [失败库] 本代排除坏骨架 {len(bad)} 个"
              f"(失败>={args.min_fail}次 全败率>={args.fail_rate:.0%})")

    # ---- 随机探索: 数据驱动特征分布引导(中金"随机探索15%=数据驱动分布, 防局部最优") ----
    # 证据分布 = 历代入库因子 + 上一代 L1 通过候选 的叶子/算子族频率;
    # 随机位按该分布抽样(探索有苗头方向的新组合), 无证据时退化为 cfg 权重(均匀)。
    ev_nodes = list(bank) + (list(prev_l1['node'])
                             if prev_l1 is not None and len(prev_l1) else [])
    cfg_r = dict(cfg)
    prof = data_profile(ev_nodes)
    if prof:
        cfg_r['leaf_w'] = _mix_weights(cfg.get('leaf_w', {}), prof['leaf'], LEAVES)
        cfg_r['op_bias'] = _mix_weights(cfg.get('op_bias', {}), prof['op'],
                                        list(UNARY.keys()) + list(BINARY.keys()),
                                        family=True)
        print(f"  [随机探索] 数据驱动特征分布: 叶子证据{len(prof['leaf'])}种 / "
              f"算子族{len(prof['op'])}种 -> 随机位按证据加权探索")
    else:
        print("  [随机探索] 无历史证据(首代) -> 随机位退化均匀")

    # ---- 生成候选(按B角给的五维配比) ----
    # ★gen13修复: cut为累积上界, 判重/分支原来写成 cut[i] 相加 -> 数值>1恒真,
    # 使 r<cut0+cut1+cut2 永远成立: guided(引导族)与rand(纯随机)从不会被执行,
    # 代代只在seeds内打转 -> 重复爆炸。 现改回 r<cut[2](seed三操作) / r<cut[3](引导) / 否则随机。
    m = cfg['mix']
    cut = [m[0], m[0] + m[1], m[0] + m[1] + m[2], m[0] + m[1] + m[2] + m[3]]
    # ---- 生成侧 LLM 引导(A角子代理, 中金"生成预算~20%语义引导"): ----
    # 引导位 r∈[cut2,cut3) 的候选来源 = LLM 解析池; 池空且调用未超限则按需补一次;
    # 无 key/超时/解析失败/超限 -> 回退本地 guided_expr。LLM 候选与规则候选走
    # 同一条守卫链(跨量纲/失败库/FSA/判重), 不产生旁路。
    llm_on = (getattr(args, 'llm_guide', 'auto') != 'off')
    llm_pool, llm_hyp = [], ''
    n_llm_call = n_llm_parse = n_llm_hit = 0
    if llm_on:
        import loop_llm
        if not loop_llm.api_key():
            if getattr(args, 'llm_guide', 'auto') == 'on':
                print("  [LLM引导] --llm_guide=on 但未找到 DeepSeek key -> 回退本地引导")
            llm_on = False
        else:
            print("  [LLM引导] 生成侧 A角 LLM 引导已启用(模型="
                  f"{getattr(args, 'llm_model', None) or loop_llm.DEFAULT_MODEL}), "
                  f"上限 {args.llm_max_calls} 次/代, 引导位命中按需补池")
    cands, seen = [], set()        # seen: 表达式级判重(原[in list] O(n²) -> O(1))
    n_skip_fsa = n_skip_dim = n_skip_bad = n_skip_dup = n_skip_fam = 0
    n_tries = dup_streak = 0
    rand_only = False              # 兜底: 连续重复过多/超时 -> 纯随机硬凑产量
    MAX_TRY = args.n * 30
    while len(cands) < args.n and n_tries < MAX_TRY:
        n_tries += 1
        if not rand_only and n_tries > args.n * 12:
            print(f"  [生成] 达{args.n*12}次仍差{args.n-len(cands)}个 -> 转纯随机兜底",
                  flush=True)
            rand_only = True
        if rand_only:
            node = rand_expr(rng, depth=rng.choice(cfg['depth']), cfg=cfg_r)
        else:
            r = rng.random()
            if seeds and r < cut[2]:
                s = rng.choice(seeds)
                node = clone(s)
                q = rng.random()
                den = max(m[0] + m[1] + m[2], 1e-9)
                if q < m[0] / den:
                    node = mutate(node, rng)
                elif q < (m[0] + m[1]) / den:
                    node = crossover(node, clone(rng.choice(seeds)), rng)
                else:
                    node = perturb(node, rng)
            elif r < cut[3]:
                # 引导位: LLM(A角)候选优先, 池空则按需补一次; 无 key/失败 -> 本地引导
                if llm_on and not llm_pool and n_llm_call < args.llm_max_calls:
                    n_llm_call += 1
                    _ok, llm_hyp, _ns = llm_fetch(args, cfg, seeds, bank,
                                                  frozen, fail_lib,
                                                  fam_black=fam_black_txt)
                    n_llm_parse += len(_ns)
                    llm_pool = _ns
                if llm_pool:
                    node = llm_pool.pop()
                    n_llm_hit += 1
                else:
                    node = guided_expr(rng, cfg)
            else:
                node = rand_expr(rng, depth=rng.choice(cfg['depth']), cfg=cfg_r)
        # 跨量纲审查(中金: 跨量纲运算拒绝): close+volume 之类荒谬组合直接重抽
        if args.dim_review > 0 and review_expr(node):
            n_skip_dim += 1
            continue
        # 失败模式库: 多次全败的坏骨架 -> 生成阶段自动排除(中金)
        if args.fail_rate > 0 and bad and has_frozen_skel(node, bad):
            n_skip_bad += 1
            continue
        # FSA: 含已冻结骨架的候选禁止复用(中金"冻结骨架不再生成"); 至多重试2次随机探索
        if args.fsa_th > 0 and frozen and has_frozen_skel(node, frozen):
            for _ in range(2):
                n2 = rand_expr(rng, depth=rng.choice(cfg['depth']), cfg=cfg_r)
                if args.dim_review > 0 and review_expr(n2):
                    continue
                if not has_frozen_skel(n2, frozen):
                    node = n2
                    break
            else:
                n_skip_fsa += 1
                continue
        # 结构族黑名单闸(gen31): 命中上代垄断模板族 -> 重抽(rand_only 兜底豁免防死锁)
        if not rand_only and block_fams and root_fam(node) in block_fams:
            n_skip_fam += 1
            continue
        k = str(node)
        if k in seen:              # 重复: 计数 + 连续重到阈值切纯随机
            n_skip_dup += 1
            dup_streak += 1
            if dup_streak > 100 and not rand_only:
                print(f"  [生成] 连续{dup_streak}次重复 -> 切纯随机兜底", flush=True)
                rand_only = True
            continue
        dup_streak = 0
        seen.add(k)
        cands.append(node)
    mode = '随机兜底' if rand_only else '正常'
    print(f"生成候选 {len(cands)}/{args.n} 个[{mode}]"
          f"(跨量纲拦{n_skip_dim} 失败库拦{n_skip_bad} FSA拦{n_skip_fsa} "
          f"族黑名单拦{n_skip_fam} 重复拦{n_skip_dup}, 尝试{n_tries}), "
          f"耗时 {time.time()-t0:.0f}s")
    if llm_on and n_llm_call:
        print(f"  [LLM引导] 调用{n_llm_call}次, 解析通过{n_llm_parse}条, "
              f"引导位出队{n_llm_hit}条"
              + (f" | hyp: {llm_hyp[:110]}" if llm_hyp else ""))
    if getattr(args, 'gen_only', False):
        print("[gen_only] 仅验证候选生成产量, 停在此处(不跑L1/L2/不写状态)")
        return

    # ---- L1 批量 IC(★分批处理 + 子面板 + 跨批LRU) ----
    Bsub = base['B_sub']
    Usub = U[np.ix_(L1_ROWS, L1_COLS)]
    if L1_POOL_MASK is not None:
        # ★池内挖掘(§8.19): L1 的 IC = **池内 IC**。这一步是"三池并行"起作用的核心 ——
        #   目标函数里不再有全A 的小盘/低流动性溢价, 风格暴露因子在 L1 就挣不到分。
        Usub = Usub & L1_POOL_MASK
    Rsub = fwd_ret[np.ix_(L1_ROWS, L1_COLS)]
    print(f"L1 子面板 {len(L1_ROWS)}日 x {len(L1_COLS)}股 "
          f"(全量 {U.shape[0]}x{U.shape[1]}) -> 数据量约 1/{U.size/max(Usub.size,1):.0f}")
    # ---- 形状量(十档单调性)所需的调仓日抽样视图: 只算一次 ----
    # rank_rows 逐行独立 => rank_rows(F)[::FWD] ≡ rank_rows(F[::FWD])，抽样与不抽样等价(更快)
    Rsub_s, Usub_s = Rsub[::FWD], Usub[::FWD]
    _min_mono = float(getattr(args, 'min_mono', 0.0) or 0.0)      # 缺字段=关闭(默认行为)
    _score_mode = getattr(args, 'score_mode', 'old') or 'old'
    _style_obs = bool(getattr(args, 'style_obs', False))
    _shape_neutral = bool(getattr(args, 'shape_neutral', 0))   # 形状量用风格中性收益(§8.5.1 行动①)
    # 剥风格入库判据(2026-09-12, 见 docs/factor_roadmap.md §8.13): L2 记录(可选门槛)
    # 把因子对 lncap+lnamt 秩中性化后重跑回测 —— 判"超额是否只是市值/成交额风格暴露"。
    _strip_style = bool(getattr(args, 'strip_style', False))
    # 池内指标(2026-09-12, 见 docs/factor_roadmap.md §8.9 B+B′): L2 在**池内**重跑回测,
    # 用于给入库因子打「300好用/300+500好用/全都好用/只有全A好用」标签, 供将来因子库 PG 筛选。
    # ★关键: L2 用的是**全量面板**(5384列), 池股天然都在里面 -> **不需要扩 L1 子面板列**
    #  (那是 L1 层池感知才需要的代价: 随机2000 ∪ 池union2701 ≈ 3700 列 = +85% 成本)。
    _min_pool_calmar = float(getattr(args, 'min_pool_calmar', -1.0))
    _pool_gate_mode = getattr(args, 'pool_gate_mode', 'any') or 'any'
    # ★ 全A 口径的夏普门槛(2026-09-13, §8.26): 原先是**硬编码 0.5**;
    #   默认 0.5 = 行为完全不变(向后兼容)。与 --pool_gate_or_all 配合才有意义。
    _min_sharpe = float(getattr(args, 'min_sharpe', 0.5))
    # ★ 池门槛与全A 口径改 **OR** 语义(2026-09-13, §8.26; 默认关=保持原 AND 行为)。
    #   依据: 池内有效与全A 有效基本不同源(300 池"池内有效但全A无效"31 个 vs "都有效"15 个)
    #   ⇒ 对"只在池内有效"的因子, AND 等于自相矛盾。组合标定: OR 保留量约为 AND 的 8 倍。
    _pool_gate_or_all = bool(getattr(args, 'pool_gate_or_all', False))
    # ★ 收益流去重阈值(2026-09-13, roadmap §8.34; 0=关)。见 loop_engine.ex_max_corr 的 docstring。
    _dup_ex_corr = float(getattr(args, 'dup_ex_corr', 0.0) or 0.0)
    _ex_by_expr = {}       # {表达式: 本代 L2 的每期费后超额 Series} —— 供入库段做收益流去重
    _n_dup_ex = 0
    # ★ 池标签(2026-09-13, §8.42): {表达式: pool_tag} —— 入库文档要写"适用哪个池"
    _tag_by_expr = {}
    # ★ 剥风格档（2026-09-14, §1.9）：{表达式: (档位, 说明, 剥后calmar, 剥后超额)}
    #   与 `_tag_by_expr` **并列**（不替代）—— 入库文档里两者都写。
    _strip_by_expr = {}
    _pool_gate_on = (_min_pool_calmar >= 0)      # 默认 -1 = 关; >=0 启用(0 是合法阈值)
    _pool_obs = bool(getattr(args, 'pool_obs', False)) or _pool_gate_on
    if _pool_gate_on and not getattr(args, 'pool_obs', False):
        print(f"  [池门槛] 已启用(min_pool_calmar={_min_pool_calmar:g}, "
              f"mode={_pool_gate_mode}) -> 自动打开池指标(否则门槛无从判定)")
    _pools = []
    if _pool_obs:
        try:
            _pools = parse_pools(getattr(args, 'pools', '300,500'))
        except KeyError as e:
            print(f"  [池指标] [!] --pools 非法({e}) -> 本代跳过池指标")
            _pool_obs = False
            if _pool_gate_on:
                print("  [池门槛] [!] 池不可用 -> 本代池门槛失效(放行不误杀)")
                _pool_gate_on = False
    _reuse_v = bool(getattr(args, 'reuse_v', 1))       # 跨阶段复用 L1 值(默认开, 行为等价)
    VCACHE.clear()
    _VREUSE_MB[0] = 0.0
    # ★need_shape 必须把 --style_obs / --shape_neutral 也算进来(2026-09-11 实测踩坑):
    #  否则单独开 --style_obs(默认 old 排序)时 mono/shape_pos 不计算 -> 观测文件这两列全 NaN,
    #  离线就无法复算 score_new = stab×(0.5+0.5·shape_pos), 整轮观测作废。
    #  这**不改变选择压力**(need_shape 只管"算不算"), 只是让观测/中性化自足。
    need_shape = ((_min_mono > 0) or (_score_mode == 'new')
                  or _style_obs or _shape_neutral)
    if _style_obs and _shape_neutral:
        print("  [!] --style_obs 与 --shape_neutral 同时开: 观测文件里 shape_pos 与 shape_pos_n "
              "都会是中性化版(拿不到原始变体)。**做测量请只用 --style_obs**。")
    if need_shape:
        print(f"  [形状] 已启用十档单调性计算 (min_mono={_min_mono:g}, "
              f"score_mode={_score_mode}, style_obs={_style_obs}, "
              f"shape_neutral={_shape_neutral}; "
              f"调仓日视图 {Rsub_s.shape[0]}期)")
    # ---- 风格暴露观测(2026-09-11, --style_obs 默认关) ----
    #  口径 = standard_test【3】风格归因的四项特征定义; 取 **L1 子面板 + [::FWD] 调仓日视图**
    #  (与 decile_shape 同视图 -> 两者共用一次 rank_rows); 快, 但只是"相对比较用代理",
    #  绝对值以 standard_test 全量报告为准。用途: 验证批1 是否让因子更往低换手/低成交额挤。
    STYLE_S, FEAT_S = {}, {}
    # ★ L2 剥风格需要**全面板**风格值(§8.13): 与 L1 子面板版共用一次 `style_features`
    #  (该函数两次 rolling 较贵 -> 一代只算一次)。只在 --strip_style 时保留全量
    #  (lncap+lnamt 各 71MB) —— 不用时零额外开销。
    STYLE_FULL = {}
    if _style_obs or _shape_neutral or _strip_style:
        _sf = style_features(B)
        for _k in STYLE_KEYS:
            if _strip_style and _k in ('lncap', 'lnamt'):
                STYLE_FULL[_k] = _sf[_k]                             # 全面板(供 L2 剥除)
            if _style_obs or _shape_neutral:
                FEAT_S[_k] = _sf[_k][np.ix_(L1_ROWS, L1_COLS)][::FWD]    # 原始值(供中性化)
                if _style_obs:
                    STYLE_S[_k] = rank_rows(FEAT_S[_k])              # 秩(供 style_expo)
        del _sf
        if _style_obs:
            print(f"  [风格观测] 已启用 ({', '.join(STYLE_KEYS)}; 子面板[::FWD] "
                  f"{Rsub_s.shape[0]}期) -> {STYLE_OBS}")
        if _strip_style:
            print(f"  [剥风格] L2 将记录剥 lncap+lnamt 后的 IC/超额/Calmar -> {STRIP_OBS}"
                  + (f"; **入库门槛 strip_calmar>{args.min_strip_calmar:g}**"
                     if args.min_strip_calmar > 0 else "; 仅记录不设门槛(默认)"))
    # ★风格中性收益: 把远期收益对 lncap/lnamt 逐期回归取残差。两种用途——
    #   ① --style_obs:     只落观测(记 shape_pos_n), 供**离线**配对比较 old/new/new_n
    #   ② --shape_neutral: 作为**主形状量**的收益入参 -> shape_pos 即"风格中性后的档位单调性",
    #                       直接进入 --min_mono 与 l1_score(new)。§8.5.1 判定 ✅ 后的行动①。
    Rsub_s_n = None
    if _style_obs or _shape_neutral:
        try:
            Rsub_s_n = neutralize_rows(Rsub_s, [FEAT_S['lncap'], FEAT_S['lnamt']], min_n=50)
            print(f"  [形状] 已算风格中性收益(对 lncap/lnamt 逐期回归残差) -> "
                  f"{'★参与选择(--shape_neutral)' if _shape_neutral else '仅观测(shape_pos_n)'}")
        except Exception as e:
            Rsub_s_n = None
            print(f"  [形状] 中性收益失败(仅缺中性化能力): {type(e).__name__}: {e}")
    # 主形状量用哪套收益(原始 / 中性化)
    R_SHAPE = Rsub_s_n if (_shape_neutral and Rsub_s_n is not None) else Rsub_s
    stats = []
    BATCH = args.batch
    n_eval = 0
    t_l1 = time.time()
    for b0 in range(0, len(cands), BATCH):
        print(f"  L1 批 {min(b0 + BATCH, len(cands))}/{len(cands)} 开始 "
              f"(已用 {time.time()-t_l1:.0f}s)", flush=True)
        chunk = cands[b0:b0 + BATCH]
        vals, kidx = [], []
        for i, nd in enumerate(chunk):
            try:
                v = eval_expr(nd, Bsub, _LRU)         # 子面板 + 全局LRU(跨批复用)
            except Exception:
                flib_mark(fail_lib, nd, args.gen, False, 'eval')  # 求值异常
                continue
            if not np.isfinite(v).any():
                flib_mark(fail_lib, nd, args.gen, False, 'nan')
                continue
            if nd.size() < 2 and not nd.args:          # 退化的纯叶子
                continue
            if np.isfinite(v).mean() < 0.30:           # 覆盖率过低
                flib_mark(fail_lib, nd, args.gen, False, 'cov')
                continue
            if not np.isfinite(np.nanstd(v)) or np.nanstd(v) < 1e-10:
                flib_mark(fail_lib, nd, args.gen, False, 'const')
                continue
            vals.append(v)
            kidx.append(b0 + i)
        if not vals:
            gc.collect()
            continue
        mu, ir, IC = batch_ic(vals, Rsub, Usub, None)
        # ★方向对齐: 统一成"因子越大越好"(IC>0); 否则负IC因子取Top组等于做空它
        sign = np.sign(mu)
        vals = [(-v if s < 0 else v) for v, s in zip(vals, sign)]
        mu, ir = np.abs(mu), np.abs(ir)
        stab = [factor_stability(v, None) for v in vals]
        # 形状量: 仅在需要时算(默认 --min_mono 0 + score_mode old -> 零额外开销)
        # 防御: 单个候选形状计算异常不应拖垮整代(引擎常无人值守), 记 None 即等同"无形状值"
        # 形状量 / 风格暴露: 仅在需要时算(默认 --min_mono 0 + score_mode old + 无 --style_obs
        # -> 零额外开销)。防御: 单个候选异常不应拖垮整代(引擎常无人值守), 记 None 即等同"无值"
        shp, sty, shn = [], [], []
        for v in vals:
            if not need_shape and not _style_obs:
                shp.append(None)
                sty.append(None)
                shn.append(None)
                continue
            # 秩视图只算一次: decile_shape 与风格观测共用(两者都基于 [::FWD] 调仓日视图)
            try:
                rs = rank_rows(v[::FWD])
            except Exception:
                shp.append(None)
                sty.append(None)
                shn.append(None)
                continue
            if need_shape:
                try:
                    shp.append(decile_shape(rs, R_SHAPE, Usub_s))
                except Exception:
                    shp.append(None)
            else:
                shp.append(None)
            # 第二套形状量: 收益换成"风格中性后的残差收益"(仅 --style_obs, 只落观测不影响选择)
            if _style_obs and Rsub_s_n is not None:
                try:
                    shn.append(decile_shape(rs, Rsub_s_n, Usub_s))
                except Exception:
                    shn.append(None)
            else:
                shn.append(None)
            if _style_obs:
                try:
                    sty.append({k: style_expo(rs, STYLE_S[k]) for k in STYLE_KEYS})
                except Exception:
                    sty.append(None)
            else:
                sty.append(None)
        for m_, i_, s_, k_, sg, sh, sy, sn in zip(mu, ir, stab, kidx, sign, shp, sty, shn):
            d = dict(idx=int(k_), node=cands[int(k_)],
                     expr=str(cands[int(k_)]), ic=float(m_),
                     ic_ir=float(i_), stab=float(s_), sign=float(sg))
            if sh is not None:
                d['mono'] = sh['mono']
                d['best_grp'] = sh['best_grp']
                d['shape_pos'] = sh['shape_pos']
            if sn is not None:                      # 风格中性后的第二套形状量(仅观测)
                d['mono_n'] = sn['mono']
                d['shape_pos_n'] = sn['shape_pos']
            if sy is not None:                      # 风格观测(仅 --style_obs 时非空)
                for _k in STYLE_KEYS:
                    d['st_' + _k] = sy[_k]
            stats.append(d)
        # ---- 跨阶段复用 L1 值(2026-09-12): 只存**过 ic/stab 门槛**候选的 [::FWD] 视图。
        #  存的是符号对齐后的同一数组 -> 去相关/去重的 rank_rows 结果逐位不变(行为等价)。
        #  成本仅一次 memcpy(~3.35MB/个); 省下的是一次完整 eval_expr + rank_rows(~2.5s/个)。
        if _reuse_v and vals:
            for _d_, _v in zip(stats[-len(vals):], vals):
                if _VREUSE_MB[0] >= _VREUSE_CAP_MB:
                    break
                if _d_['ic'] > args.min_ic and _d_['stab'] > args.min_stab:
                    _arr = np.ascontiguousarray(_v[::FWD])
                    VCACHE[_d_['expr']] = _arr
                    _VREUSE_MB[0] += _arr.nbytes / 1e6
        n_eval += len(vals)
        del vals, IC
        gc.collect()
        trim_cache(_LRU, LRU_MAX)                      # LRU 容量控制(防OOM)
    print(f"L1 求值完成 {n_eval} 个, 用时 {time.time()-t_l1:.0f}s "
          f"({(time.time()-t_l1)/max(n_eval,1):.2f}s/候选)")
    _LRU.clear()                                       # L1 结束: 释放跨批子树缓存
    l1 = pd.DataFrame(stats)
    # ---- 风格暴露观测落盘(2026-09-11, --style_obs; 失败只告警不拖垮主流程) ----
    #  ★位置很关键: **紧跟 L1 求值**。引擎在 L1 之后有多处早退(无候选通过 / 形状门槛全灭 /
    #   去相关全灭), 若放到代末则这些代的样本全丢(试点已实测: n=40 时 17->10 后仍可能全灭)。
    #  观测样本 = 本代**被求值的全部候选**(含未过门槛者), 这正是离线配对比较需要的总体。
    #  每行 = 一个候选: ic/ic_ir/stab/mono/shape_pos + 4 项风格暴露(见 roadmap §8.4)。
    #  是否进 L2 / 是否通过 L2: 用 (gen, expr) 与 docs/loop_archive.csv 离线 join 即可。
    obs_df = None
    if _style_obs and stats:
        try:
            obs_df = pd.DataFrame([dict(
                gen=args.gen, expr=d_['expr'], sign=d_['sign'],
                ic=d_['ic'], ic_ir=d_['ic_ir'], stab=d_['stab'],
                mono=d_.get('mono', np.nan), shape_pos=d_.get('shape_pos', np.nan),
                mono_n=d_.get('mono_n', np.nan), shape_pos_n=d_.get('shape_pos_n', np.nan),
                **{'st_' + k: d_['st_' + k] for k in STYLE_KEYS})
                for d_ in stats if ('st_' + STYLE_KEYS[0]) in d_])
            need_h = (not os.path.exists(STYLE_OBS)) or os.path.getsize(STYLE_OBS) == 0
            obs_df.to_csv(STYLE_OBS, index=False, mode='a', header=need_h,
                          encoding='utf-8-sig')
            print(f"已存 {STYLE_OBS} (追加, 本代 {len(obs_df)} 条候选)")
            if obs_df['shape_pos'].isna().all():          # 自检: 见上方 need_shape 的踩坑注释
                print("  [风格观测] [!] shape_pos 全为 NaN -> need_shape 未生效, "
                      "本轮观测无法复算 score_new, 请检查 --score_mode/--min_mono/--style_obs")
        except Exception as e:
            obs_df = None
            print(f"  [风格观测] 落盘失败(不影响主流程): {type(e).__name__}: {e}")
    # 失败模式库: IC/稳定性不过线的候选按骨架记失败(过线者待 L2 后记 ok)
    for r_ in stats:
        nd = r_['node']
        if r_['ic'] <= args.min_ic:
            flib_mark(fail_lib, nd, args.gen, False, 'ic')
        elif r_['stab'] <= args.min_stab:
            flib_mark(fail_lib, nd, args.gen, False, 'stab')
    cache2 = {}
    if not len(l1):
        print("L1 无候选通过, 退出")
        return
    l1 = l1[(l1['ic'] > args.min_ic) & (l1['stab'] > args.min_stab)]
    # ---- 形状门槛(gen52+, 批1 P0; --min_mono 默认 0=关闭 -> 默认零行为变化) ----
    # 标定(1150 条历史 L2 候选): L2 通过者 mono 中位 0.964 / 最小 0.770; 判死者中位 0.867。
    # 故 `mono >= 0.75` 可拦下 ~27% 判死候选且对 19 个入库因子**零误杀**。
    if _min_mono > 0 and 'mono' in l1.columns:
        n_pre_mono = len(l1)
        l1 = l1[np.isfinite(l1['mono']) & (l1['mono'] >= _min_mono)]
        print(f"  [形状门槛] 十档单调性 mono>={_min_mono:g} 后剩 {len(l1)} 个 "
              f"(原 {n_pre_mono}, 拦 {n_pre_mono - len(l1)})")
        if not len(l1):
            print("L1 形状门槛后无候选, 退出")
            return
    # ★去相关: 与【已入库已知因子】相关性过高的丢弃, 强迫引擎探索新方向
    #   (中金的"IC相关性<0.70"; 否则引擎会反复重新发现 ln_mktcap / amt_log)
    if args.decorr > 0:
        _t_dec = time.time()
        # 对比对象 = 人工基准 + 【历代入库因子(state.bank)】 —— 对齐中金
        # "与已入库因子IC相关<0.70"的结果闸门: 不是固定两个基准, 库扩大后
        # 与新入库因子相似的候选会被拦在L2外(不靠禁叶子字段)
        KNOWN = {
            'ln_mktcap': np.log(np.maximum(B['mktcap'], 1e-9)),
            'amt_log': -np.log(ts_mean(B['turnover'], 20) + 1.0),
        }
        # 用子面板算相关性(快); 已知因子也取对应子面板
        Kr = {}
        for k, v in KNOWN.items():
            vs = v[np.ix_(L1_ROWS, L1_COLS)]
            Kr[k] = rank_rows(vs[::FWD])
        for bi, bnd in enumerate(bank):
            try:
                vb = eval_expr(bnd, Bsub, cache2)
                Kr[f'bank{bi}'] = rank_rows(vb[::FWD])
                del vb
            except Exception:
                pass
        keep_rows = []
        n_hit = 0
        for _, r in l1.iterrows():
            # ★复用 L1 已算的 [::FWD] 值视图(命中则完全跳过 eval_expr, 结果逐位不变)
            v0 = VCACHE.get(r['expr']) if _reuse_v else None
            if v0 is not None:
                n_hit += 1
            else:
                v0 = eval_expr(r['node'], Bsub, cache2)
                if r['sign'] < 0:
                    v0 = -v0
                v0 = v0[::FWD]
            v = rank_rows(v0)
            del v0
            mx = 0.0
            fv = np.isfinite(v)          # ★ 提到循环外: 与 w 无关, 此前每个已知因子都重算一次
            for w in Kr.values():
                m = fv & np.isfinite(w)
                if m.sum() < 100:
                    continue
                c = abs(np.corrcoef(v[m], w[m])[0, 1])
                mx = max(mx, c if np.isfinite(c) else 0.0)
            if mx <= args.decorr:
                keep_rows.append(r)
            trim_cache(cache2, CACHE2_MAX)             # 去相关缓存容量控制(防OOM)
        print(f"去相关(|corr|<={args.decorr} vs {len(Kr)}个已知因子) 后剩 "
              f"{len(keep_rows)} 个 (原 {len(l1)})")
        print(f"  [计时] 去相关 用时 {time.time() - _t_dec:.0f}s "
              f"(复用 L1 值 {n_hit}/{len(l1)} 个, 缓存 {_VREUSE_MB[0]:.0f}MB)", flush=True)
        if keep_rows:
            l1 = pd.DataFrame(keep_rows)
    # 关键: 不能只按 |IC_IR| 排! 低稳定性(高换手)因子费后必亏
    # L1评分 = |IC_IR| x 稳定性权重; 换手代理 turn_est = 1 - stab
    l1['turn_est'] = 1.0 - l1['stab']
    if _score_mode == 'new':
        # 批1 P0(gen52+): score = stab × (0.5 + 0.5·shape_pos)，**去掉 |ic_ir|**
        # 依据: 标定 1150 条历史 L2 候选, 与 L2 Calmar 的相关性 old +0.167 -> new +0.668;
        #       ic_ir 本身与 L2 负相关(-0.317), 乘进去在稀释 stab 的正信号(stab 单独 +0.546)。
        #       IC 仍由 `ic > min_ic` 当准入门槛, 只是不再当排序驱动。
        l1['score'] = l1_score(l1['stab'], l1['ic_ir'],
                               l1['shape_pos'] if 'shape_pos' in l1.columns else None, 'new')
    else:
        l1['score'] = l1['ic_ir'].abs() * (0.25 + 0.75 * l1['stab'].clip(0, 1))
    l1 = l1.sort_values('score', ascending=False)
    # 数值近重复去重(只对 TopN 做, 用采样指纹加速, 否则 O(n^2) 跑不动)
    # gen51: 阈值 0.99 -> args.dedup_corr(默认0.85)。0.99 过松: 实测同代 F20~F23 两两
    # |corr| 0.93/0.88 全数放行(4 个近重复因子同代入库)。标定: 全库 23 因子在此口径下
    # 仅这两对>0.85(其余<=0.744) -> 0.85 既能拦下两对、又不误杀历史入库因子。
    _t_dd = time.time()
    TOPN = min(len(l1), args.dedup_n)
    dedup, seen_v = [], []
    n_dup = 0
    samp = slice(None, None, max(1, 418 // args.dedup_days))   # 抽样调仓日
    cache2 = {}
    n_hit2 = 0
    for _, r in l1.head(TOPN).iterrows():
        vc = VCACHE.get(r['expr']) if _reuse_v else None
        if vc is not None:                              # 复用 L1 值, 免二次 eval
            v = rank_rows(vc)[samp]
            n_hit2 += 1
        else:
            v = eval_expr(r['node'], Bsub, cache2)
            if r['sign'] < 0:
                v = -v
            v = rank_rows(v[::FWD])[samp]
        dup = False
        for w in seen_v:
            m = np.isfinite(v) & np.isfinite(w)
            if m.sum() < 100:
                continue
            if abs(np.corrcoef(v[m], w[m])[0, 1]) > args.dedup_corr:
                dup = True
                break
        if not dup:
            seen_v.append(v)
            dedup.append(r)
        else:
            n_dup += 1
        trim_cache(cache2, CACHE2_MAX)                 # 去重缓存容量控制(防OOM)
    print(f"\nL1 通过 {len(l1)} 个, 取Top{TOPN}近重复去重(|corr|>{args.dedup_corr:g})"
          f"拦 {n_dup} -> 剩 {len(dedup)} 个")
    print(f"  [计时] 近重复去重 用时 {time.time() - _t_dd:.0f}s "
          f"(复用 L1 值 {n_hit2}/{TOPN} 个)", flush=True)
    VCACHE.clear()                                      # 去相关/去重用完即释放(防与 L2 叠加占内存)
    _VREUSE_MB[0] = 0.0
    l1 = pd.DataFrame(dedup) if dedup else l1.head(TOPN)
    print(l1[['expr', 'ic', 'ic_ir', 'stab']].head(15).round(4).to_string(index=False))
    # ---- 结构族配额(QuantaAlpha 冗余检测移植, gen31) ----
    # 数值去重(|corr|>dedup_corr) 只拦"数值近重复"; FSA 冻结只拦"完整串复用"。同族"外层模板
    # 固定、内层微调"的候选(score 各异、公共结构巨大)会继续挤满 L2 名额与下代种子池, 费后全灭 ->
    # 每模板族最多放 fam_quota 条进 L2/种子池(保结构多样性), FSA/下代种子池因此天然跨族。
    # gen51: 族指纹增补"单叶变换"维度(floor_sole_leaf) -> max(<某叶单目变换>, <地板>) 的
    # "同叶不同壳"代理候选归为同族, 由配额拦重复(防 F23 型"leverage 套壳+地板"反复重发现)。
    fam_blocked = 0
    if args.fam_quota > 0 and len(l1):
        n_pre = len(l1)
        l1, nfam, n_blocked = fam_quota_rows(l1, quota=args.fam_quota,
                                             use_sole=args.fam_sole)
        fam_blocked = n_blocked
        if n_blocked:
            print(f"  [族配额] 模板族 {nfam} 个(含单叶变换维度={'开' if args.fam_sole else '关'})"
                  f" -> 结构冗余拦 {n_blocked}/{n_pre} (剩 {len(l1)}, 每族<={args.fam_quota})")

    # ---- FSA 骨架统计(对齐中金: 抽象因子结构/剥离窗口参数) ----
    # 观察样本 = 本代L1通过者 + 前50候选; 统计对象 = 非叶子结构骨架(剥掉窗口数字)
    fsa['v2'] = True
    for nd in list(l1['node']) + [c for c in cands[:50]]:
        for s in subtree_skels(nd):
            fsa[s] = fsa.get(s, 0) + 1
    # 冻结判定(滚动口径, 对齐中金"定期扫描>15%即禁复用"):
    #   ①本代L1候选中覆盖占比 >= fsa_th 的骨架 -> 新冻结
    #   ②上代冻结骨架若本代已完全不再出现 -> 自动解冻(防冻结集永久膨胀、搜索空间缩死)
    if args.fsa_th > 0 and len(l1):
        thr = max(2, int(round(len(l1) * args.fsa_th)))
        cov = {}
        for _, r in l1.iterrows():
            for s in subtree_skels(r['node']):
                cov[s] = cov.get(s, 0) + 1
        old = set(frozen)
        new_frozen = sorted(s for s, c in cov.items() if c >= thr)
        frozen = sorted((old & set(cov)) | set(new_frozen))
        if new_frozen or len(old - set(frozen)):
            print(f"  [FSA] 覆盖>={thr}/{len(l1)}候选({args.fsa_th:.0%}): "
                  f"新冻结{len(new_frozen)} 解冻{len(old - set(frozen))} "
                  f"冻结中{len(frozen)}")
            for s in new_frozen[:6]:
                print(f"     冻结骨架: {s}")

    # ---- 中金【审查】环节: B角候选级 LLM 精判(硬滤后抽5深判, 与生成侧隔离防自证) ----
    # 硬规则已在上方先滤(IC/稳定/去相关/去重/跨量纲/FSA) -> 剩余候选随机抽 --jury_n 个,
    # 由审查侧 Sub-agent LLM(loop_llm.jury_verdict)判经济含义/过拟合边界/已知族嫌疑,
    # verdict=KILL 者剔除出 L2 费后回测; 无 key/调用失败一律放行不误杀(无人值守铁律)。
    kills_j, n_jury_rev, n_jury_kill, jury_lines = set(), 0, 0, []
    jury_on = getattr(args, 'ai_jury', 'auto')
    if jury_on != 'off' and len(l1):
        import loop_llm
        if not loop_llm.api_key():
            if jury_on == 'on':
                print("  [LLM审查] --ai_jury=on 但未找到 key -> 跳过(纯硬规则审查)")
        else:
            jmodel = getattr(args, 'ai_jury_model', None) or loop_llm.DEFAULT_MODEL
            kills_j, n_jury_rev, n_jury_kill, jury_lines = \
                llm_jury(args, rng, l1, model=jmodel)
            if kills_j:
                l1 = l1[~l1['expr'].isin(kills_j)]
                print(f"  [LLM审查] KILL {len(kills_j)} 个候选剔除出 L2, "
                      f"剩余 {len(l1)} 个进入费后回测")

    # ---- L2 费后精筛 ----
    top = l1.head(args.l2)
    _t_l2 = time.time()
    print(f"\nL2 费后精筛 {len(top)} 个 ...")
    # 池成员 PIT 掩码(2026-09-12, --pool_obs; 见 docs/factor_roadmap.md §8.9 B+B′)
    #  ★ 建在**全量面板**上(池股天然都在, 面板覆盖率 99.3%/99.8%) ⇒ **不需要扩 L1 子面板列**。
    #   (L1 层池感知才需要"随机2000 ∪ 池union2701 ≈ 3700 列 = +85% 成本", 那是后续的事。)
    POOL_M = {}
    import loop_pools as _lp          # ★ 池标签派生用(§8.42); 本地 import 避免与顶层名冲突
    if _pool_obs:
        try:
            _t_pool = time.time()
            for _tg in _pools:
                POOL_M[_tg] = pool_mask(_tg, dates, cols)
            _sz = ', '.join(f"{t}:{int(POOL_M[t].sum())}格" for t in _pools)
            _gate_txt = ((f"**入库门槛: {'任一' if _pool_gate_mode == 'any' else '全部'}池 "
                          f"Calmar > {_min_pool_calmar:g}"
                          + ("　**或**　全A 口径(calmar>%.2f & sharpe>%.2f & 分段)**"
                             % (args.min_calmar, _min_sharpe) if _pool_gate_or_all
                             else "**（与全A 口径 AND）") )
                         if _pool_gate_on else "仅记录不设门槛(默认)")
            print(f"  [池指标] 已启用 池={_pools} (PIT掩码 {_sz}; "
                  f"用时 {time.time() - _t_pool:.0f}s) -> {POOL_OBS}; {_gate_txt}")
        except Exception as e:
            print(f"  [池指标] [!] 掩码构建失败 -> 本代跳过池指标: {type(e).__name__}: {e}")
            POOL_M = {}
    # ---- 市值面板(2026-09-13, roadmap §8.28): 供"**市值加权基准**"口径 ----
    #  为什么: 组合腿是 Top10% **等权**; 基准腿现状是"池内**等权**" ⇒ 两腿同为等权 ⇒ 规模中性
    #   ⇒ 差额 = 纯选股 alpha。而**真实指数**(沪深300)是**自由流通市值加权** ⇒ 若用它当基准,
    #   等权组合**天然超配池内小盘** ⇒ 多出一块「池内规模倾斜」收益(不是 alpha)。
    #  ⇒ 因此**两个都记**: 等权基准作主判据(干净), 市值基准作产品口径 + tilt 诊断。
    #  ⚠ 成本 = 0 额外回测(组合腿不变, 只换基准的加权平均)。
    MCAP = None
    if POOL_M:
        try:
            MCAP = np.where(B['mktcap'] > 0, B['mktcap'].astype('float64'), np.nan)
        except Exception as e:
            print(f"  [池指标] [!] 市值加权基准不可用(只影响该列, 主流程不受影响): "
                  f"{type(e).__name__}: {e}")
            MCAP = None
    rows = []
    seg_ok_list = []   # 与 rows 同步, 供 critic 统计 seg_kill(不入 archive 表头)
    strip_rows = []    # 剥风格明细(2026-09-12, --strip_style) -> 独立文件, 不进 archive 表头
    pool_rows = []     # 池内明细(2026-09-12, --pool_obs) -> 独立文件(长表), 理由同上
    n_pool_nogate = 0  # 池门槛「无池结果 -> 放行不误杀」的次数(代末上报, 防静默失效)
    for j, (_, r) in enumerate(top.iterrows(), 1):
        t_one = time.time()
        nd = r['node']
        strip_rec = None
        pool_rec = []      # 本候选的各池结果(供池门槛用; 同时 extend 进 pool_rows)
        try:
            v = eval_expr(nd, B, {})
            if r['sign'] < 0:
                v = -v
            fac = pd.DataFrame(v, index=dates, columns=cols)
            f = cs_rank(fac.astype('float64'))
            # ★ with_daily(2026-09-14, §1.19): 同时产出**日频**风险口径(dd_d/calmar_d) ——
            #   档位阈值与池门槛已改用日频（期频漏掉持有期内回撤、回撤被低估，实测折比中位 0.928）。
            #   成本：只多算一条净值序列（不重新选股），每候选 +~4s。
            rr = evaluate_real(f, close, str(nd), cost=args.cost,
                               window=args.window, with_ex=True, with_daily=True)
            # ---- 剥风格(2026-09-12, --strip_style; 见 docs/factor_roadmap.md §8.13) ----
            #  口径与 standard_test.py【6】逐位一致: rank(因子) 对 rank(lncap)+rank(lnamt)
            #  逐日截面 OLS 取残差 -> **再 rank** -> 重跑同一套费后回测。
            #  为什么: 30 个入库因子剥成交额后**仅 3 个**超额仍为正、沪深300 内**仅 3/30** 有效
            #  ⇒ "全A 超额"主要来自小市值+低成交额暴露, 不是独立 alpha。
            #  口径微差(已知): 时间轴是**全样本**(L2 用 full panel), 与 standard_test 同;
            #  但成本/窗口取 args 的设置, 故绝对数值与报告不一定逐位相同, 判"衰减"看相对。
            if _strip_style and rr is not None:
                try:
                    _fn = neutral_rank(f.values.astype('float64'),
                                       [STYLE_FULL['lncap'], STYLE_FULL['lnamt']])
                    rr_s = evaluate_real(pd.DataFrame(_fn, index=dates, columns=cols),
                                         close, str(nd) + '#strip',
                                         cost=args.cost, window=args.window, with_daily=True)
                    if rr_s is not None:
                        strip_rec = dict(
                            gen=args.gen, expr=str(nd),
                            ic=rr['ic'], calmar=rr['calmar'], ann_ex=rr['ann_ex'],
                            dd_d=rr.get('dd_d'), calmar_d=rr.get('calmar_d'),
                            strip_ic=rr_s['ic'], strip_calmar=rr_s['calmar'],
                            strip_ann_ex=rr_s['ann_ex'], strip_sharpe=rr_s['sharpe'],
                            # ★ 剥风格后的**日频**口径（§1.19）—— 档位阈值现在就吃这几个
                            strip_dd_d=rr_s.get('dd_d'),
                            strip_calmar_d=rr_s.get('calmar_d'),
                            strip_sharpe_d=rr_s.get('sharpe_d'))
                except Exception as e_s:
                    # 无人值守铁律: 剥风格失败**不得**影响主流程, 也不得据此拦候选
                    print(f"  [{j}] 剥风格失败(不影响主流程): {type(e_s).__name__}: {e_s}")
            # ---- 池内指标(2026-09-12, --pool_obs; 见 roadmap §8.9 B+B′) ----
            #  口径 = **池内排名**(对齐 standard_test 默认的 --pool_mode=A):
            #    因子池外置 NaN -> cs_rank(逐行只在池内有效值上排名) -> 同一套费后回测。
            #  ⚠ evaluate_real 选股是 `fac.loc[d][U].dropna()` ⇒ 池外 NaN 自动被排除;
            #    且"池等权"基准随之变成**同池等权**(与 standard_test 口径一致, 不是全A等权)。
            if POOL_M and rr is not None:
                for _tg, _M in POOL_M.items():
                    try:
                        _vp = np.where(_M, fac.values, np.nan)
                        _fp = cs_rank(pd.DataFrame(_vp, index=dates, columns=cols))
                        _rp = evaluate_real(_fp, close, f"{nd}#pool{_tg}",
                                            cost=args.cost, window=args.window,
                                            mcap=MCAP,   # ★同时给「市值加权基准」(§8.28)
                                            with_daily=True)   # ★池门槛/池标签也吃日频(§1.19)
                        if _rp is not None:
                            pool_rec.append(dict(
                                gen=args.gen, expr=str(nd), pool=_tg,
                                # ★ `pools_scope`(2026-09-14, §1.5)：记录**当次 `--pools` 集合** ——
                                #   否则"只在两池测过"会被误读成"池内无效"（跨批次比标签会错）。
                                #   以后任何时候都能还原"这行标签是在哪些池上算的"。
                                pools_scope=','.join(_pools),
                                ic=_rp['ic'], ic_ir=_rp['ic_ir'], calmar=_rp['calmar'],
                                ann_ex=_rp['ann_ex'], dd=_rp['dd'],
                                # ★ 日频口径（§1.19）：池门槛/池标签用这几个
                                dd_d=_rp.get('dd_d'), calmar_d=_rp.get('calmar_d'),
                                sharpe=_rp['sharpe'], turn=_rp.get('turn', np.nan),
                                # 市值加权基准口径(§8.28): calmar_cw ≈ 对真实指数的超额
                                #  tilt = ann_ex_cw - ann_ex = 「池内规模倾斜」贡献(越大越可疑)
                                ann_ex_cw=_rp.get('ann_ex_cw', np.nan),
                                calmar_cw=_rp.get('calmar_cw', np.nan),
                                dd_cw=_rp.get('dd_cw', np.nan),
                                sharpe_cw=_rp.get('sharpe_cw', np.nan),
                                tilt=_rp.get('tilt', np.nan)))
                        del _fp
                    except Exception as e_p:
                        print(f"  [{j}] 池 {_tg} 计算失败(不影响主流程): "
                              f"{type(e_p).__name__}: {e_p}")
                pool_rows.extend(pool_rec)
                # ★ 池标签(2026-09-13, §8.42): 规则取自 `loop_pools.derive_tag`(**单一事实源**,
                #   与 `standard/pool_tags.py` 派生 docs/pool_tags.csv 同口径)。
                #   用户诉求:「一眼看出这个因子是全A+哪个池好用、还是只有全A好用」。
                try:
                    # ★★ 2026-09-14（§1.18 用户拍板 B + §1.19 用户拍板 ③）：
                    #   ① **修判据不对称** —— 原来「全A 要 calmar>=0.30、池内**只要超额>0**」
                    #      ⇒ `all3`（"所有池都通过 = 真 alpha"）名不副实（实测 F10_1000 误标）。
                    #   ② **口径统一到日频** —— 期频漏掉持有期内回撤，回撤被低估（折比中位 0.928）。
                    #      日频缺失时**回退期频**（旧数据/未开 with_daily 时不炸、不误杀）。
                    def _cal_d(_d):
                        """取日频 Calmar，缺失则回退期频（**回退要留痕**在 CSV 列里可辨）。"""
                        _v = _d.get('calmar_d')
                        return _v if (_v is not None and np.isfinite(_v)) else _d.get('calmar')
                    _okp = {q['pool']: bool(np.isfinite(q['ann_ex'])
                                            and q['ann_ex'] > _lp.TAG_POOL_FLOOR
                                            and np.isfinite(_cal_d(q))
                                            and _cal_d(q) >= _lp.TAG_POOL_FLOOR_CAL)
                            for q in pool_rec}
                    _oka = bool(np.isfinite(rr['ann_ex']) and rr['ann_ex'] > 0
                                and np.isfinite(_cal_d(rr))
                                and _cal_d(rr) >= _lp.TAG_CAL_MIN)
                    _tag_by_expr[str(nd)] = _lp.derive_tag(_oka, _okp, _pools)
                    # ★ 剥风格档（**并列**记录，不改池标签语义）—— 分档规则在
                    #   `loop_pools.strip_grade`（单一事实源，脚本与引擎共用一套）。
                    #   ⚠ 传**日频**口径 + 日频回撤（§1.19 ③：A 档 = 日频 calmar>=0.30 且 dd_d>-0.20）
                    if strip_rec is not None:
                        _sg_k, _sg_t = _lp.strip_grade(strip_rec.get('strip_calmar_d'),
                                                       strip_rec.get('strip_ann_ex'),
                                                       strip_rec.get('strip_dd_d'))
                        # 元组：档位 / 说明 / 期频剥后 Calmar / 剥后超额 / **日频剥后 Calmar** / **日频剥后回撤**
                        #   ★ 后两项 2026-09-14（§1.19）新增 —— 判据已改日频 ⇒ 文档要能看见它。
                        _strip_by_expr[str(nd)] = (_sg_k, _sg_t,
                                                   strip_rec.get('strip_calmar'),
                                                   strip_rec.get('strip_ann_ex'),
                                                   strip_rec.get('strip_calmar_d'),
                                                   strip_rec.get('strip_dd_d'))
                except Exception as e_t:
                    print(f"  [{j}] 池标签派生失败(不影响主流程): {type(e_t).__name__}: {e_t}")
            del f
            gc.collect()
        except Exception as e:
            print(f"  [{j}] ERR {type(e).__name__}")
            continue
        if rr is None:
            continue
        yr = rr['yr']
        # 统一用 factor_miner.pass_filter 的11项标准(亏损年<-2% <=1, 而非"所有年>0")
        from factor_miner import pass_filter
        ok, _ = pass_filter(rr, args.min_ic)
        # ★「全A 量化口径」单独记一份 _ok_q, 供 --pool_gate_or_all 做 OR(见下方池门槛段)。
        #   为什么必须分开: OR 语义要求"全A 口径达标 **或** 池内达标", 若把 _ok_q 提前 AND 进
        #   ok, 后面再写 `ok and (_ok_q or _pok)` 会退化成 AND(ok 里已含 _ok_q)。
        #   (2026-09-13, roadmap §8.26)
        _ok_q = (rr['calmar'] > args.min_calmar and rr['sharpe'] > _min_sharpe)
        _ok_prev = ok          # 快照: 仅含 pass_filter(尚未并入 _ok_q) —— OR 语义重建的**基底**
        ok = ok and _ok_q
        # ★★★ 2026-09-14（loop_todo §1.17）：「硬门槛」与「可参与 OR 的量化口径」**分开存**。
        #   为什么：`--pool_gate_or_all` 用 `_ok_prev and (_ok_q or _pok)` 重建 ok，
        #   而 `_ok_prev` 取在 `_ok_q` 之前 ⇒ 它会把**后面才 AND 进去的 seg/strip 一起撤掉**
        #   （实测：池库 13 个入库因子里 8 个是纯风格，本该被 `--min_strip_calmar` 拦下）。
        #   ⇒ 剥风格 / 分段验证记进 `_ok_hard`，在池门槛段**之后**统一 AND 回来，**不参与 OR**。
        #   判定组合的**单一事实源** = `combine_ok()`（上方，可单元测试）。
        _ok_hard = True
        # ★分段独立验证(防伪衰减): 把费后日超额序列均分 N 个不相交子区间,
        #   各段须同号(累计费后超额>0)的段数达标才通过 —— 拦"靠单段大行情撑
        #   全样本高t、一出该段即失效"的候选(F12 型)。样本不足自动放行不误杀。
        seg_ok, n_seg_pos, n_seg_k, seg_txt = (True, -1, args.seg_n, 'off')
        if args.seg_n > 1:
            seg_ok, n_seg_pos, n_seg_k, seg_txt = seg_verify(
                rr.get('ex'), args.seg_n, args.seg_need)
            ok = ok and seg_ok
            _ok_q = _ok_q and seg_ok        # 分段也算「全A 量化口径」的一部分(供 OR 用)
            _ok_hard = _ok_hard and seg_ok  # ★ 同时记进硬门槛(§1.17: OR 不该撤掉它)
        # ---- 剥风格入库门槛(2026-09-12, 默认关) ----
        #  args.min_strip_calmar <= 0 -> 只记录不拦(默认行为不变)。
        #  ⚠ strip_rec is None(未开/计算失败)时**放行不误杀** —— 与 LLM 审查同一条铁律。
        if _strip_style and args.min_strip_calmar > 0 and strip_rec is not None:
            _pass_strip = bool(strip_rec['strip_calmar'] > args.min_strip_calmar)
            ok = ok and _pass_strip
            _ok_hard = _ok_hard and _pass_strip   # ★ 同时记进硬门槛(§1.17: OR 不该撤掉它)
        # ---- 池门槛(2026-09-12, 默认关; **用户选定 C** = 排除 csi_all_only) ----
        #  语义: --pool_gate_mode=any(默认) 要求**至少一个池**达标(=C, 滤掉"只在全A有效");
        #        all 要求**所有池**都达标(=更严, "真 alpha")。
        #  口径: 池内 Calmar vs --min_pool_calmar(与 --min_calmar 同口径; Calmar>0 = 该池有效)。
        #  ⚠ 无池结果(未开 --pool_obs / 计算失败) -> **放行不误杀**(与 strip/LLM 同一铁律),
        #    但要计数并在代末上报, 否则门槛静默失效而无人察觉。
        _pok = None
        if _pool_gate_on:
            _pok, _pv = pool_gate_ok([q.get('calmar') for q in pool_rec],
                                     _min_pool_calmar, _pool_gate_mode)
            if _pok is None:                 # 无从判定 -> 放行不误杀, 但计数上报
                n_pool_nogate += 1
        # ★★★ 判定组合逻辑统一走 `combine_ok()`（**单一事实源**，可单元测试）。
        #   语义（roadmap §8.26 + loop_todo §1.17）：
        #     · 无池门槛 / `_pok is None`   -> `_ok_prev && _ok_q`（放行不误杀）
        #     · `--pool_gate_or_all` 且可用 -> `_ok_prev && (_ok_q || _pok)`  ← OR 只作用于这两个口径
        #     · 否则                        -> `_ok_prev && _ok_q && _pok`
        #     · **最后无条件 `&& _ok_hard`**（剥风格 + 分段）—— 见函数 docstring 的 bug 说明
        #
        #   ⚠ 原实现在 `elif _pool_gate_or_all:` 分支里写 `ok = _ok_prev and (_ok_q or _pok)`，
        #     而 `_ok_prev` 取在 `_ok_q` **之前** ⇒ 把**之后**才 AND 进去的 seg/strip **一起撤掉**
        #     ⇒ 池轨道 13 个入库因子里 8 个是「纯风格」（本该被 `--min_strip_calmar=0.15` 拦下）。
        ok = combine_ok(_ok_prev, _ok_q, _pok, _ok_hard,
                        bool(_pool_gate_on), bool(_pool_gate_or_all))
        # ★ 收益流去重(2026-09-13, roadmap §8.34, --dup_ex_corr): 算本候选 vs 历史库收益流的
        #   最大 |相关|。**止血**机制 —— 实测库内 30 个因子的收益流两两相关中位 **0.967**
        #   ⇒ 再攒同类因子等于没攒(合成 Calmar 还低于最好的单因子)。
        #   ⚠ 这里**只记录**(落 archive 的 max_ex_corr 列), 拦入库在下方 bank 追加段做
        #     —— 那里能拿到"本代已入库者"的最新库, 从而同时防"同代内近重复"。
        _mec, _mew = None, None
        _ex = rr.get('ex') if isinstance(rr, dict) else None
        if _dup_ex_corr > 0 and _ex is not None:
            _mec, _mew = ex_max_corr(_ex, bank_ex)
        if _ex is not None:
            _ex_by_expr[str(nd)] = _ex
        leaf_s, cat_s = leaf_parts(nd)
        rows.append(dict(expr=str(nd), cat=cat_s, leaf=leaf_s,
                         window=args.window, cost=args.cost,
                         ic=rr['ic'], ic_ir=rr['ic_ir'],
                         ann_ex=rr['ann_ex'], dd=rr['dd'], calmar=rr['calmar'],
                         # ★ 日频口径（§1.19）：供**离线重算池标签**用（判据已改用日频）。
                         #   ⚠ 加列安全：本文件走 `append_csv_schema_safe`（§8.30 根治）。
                         dd_d=rr.get('dd_d'), calmar_d=rr.get('calmar_d'),
                         sharpe=rr['sharpe'], last_yr=rr['last_yr'],
                         turn=rr.get('turn', np.nan),
                         neg_yr=sum(1 for v in yr.values() if v <= 0),
                         max_ex_corr=(-1.0 if _mec is None else float(_mec)),
                         passed=ok))
        seg_ok_list.append(seg_ok)
        if strip_rec is not None:
            strip_rows.append(strip_rec)
        _sstr = ''
        if strip_rec is not None:
            _sstr = (f" | 剥风格 IC={strip_rec['strip_ic']:+.4f} "
                     f"超额={strip_rec['strip_ann_ex']*100:+6.2f}% "
                     f"Calmar={strip_rec['strip_calmar']:5.2f}")
        # 池内一行汇总(用本候选的 pool_rec: 便于肉眼对比 300/500, 并显示门槛判定)
        _pstr = ''
        if pool_rec:
            _pstr = ' | 池内 ' + ' '.join(
                f"{q['pool']}:{q['ann_ex']*100:+.2f}%/Cal{q['calmar']:+.2f}"
                + (f"(市值{q['ann_ex_cw']*100:+.2f}%/倾斜{q['tilt']*100:+.2f}%)"
                   if np.isfinite(q.get('tilt', np.nan)) else '')
                for q in pool_rec)
            if _pool_gate_on:
                _pok_, _pv_ = pool_gate_ok([q.get('calmar') for q in pool_rec],
                                           _min_pool_calmar, _pool_gate_mode)
                if _pv_ is not None:
                    _pstr += f" [池门槛{'过' if _pok_ else '拦'}({_pv_:+.3f})]"
        print(f"  [{j}] IC={rr['ic']:+.4f} 费后超额={rr['ann_ex']*100:+6.2f}% "
              f"Calmar={rr['calmar'] if rr['calmar'] else 0:5.2f} "
              f"夏普={rr['sharpe']:5.2f} 换手={rr.get('turn', np.nan)*100:4.1f}% "
              f"负年{sum(1 for v in yr.values() if v <= 0)} "
              f"[cost={cost_label(args.cost)} win={args.window}] "
              f"分段{seg_txt} "
              f"耗时{time.time() - t_one:.0f}s "
              f"{'PASS' if ok else ''}{_sstr}{_pstr}")
    print(f"  [计时] L2 费后精筛 {len(top)} 个 用时 {time.time() - _t_l2:.0f}s", flush=True)
    if _pool_gate_on and n_pool_nogate:
        # 门槛静默失效是"无人值守"最危险的失败模式 -> 必须上报(拿不到池结果就放行)
        print(f"  [池门槛] [!] {n_pool_nogate} 个候选无池结果 -> 已放行(未参与门槛判定)")
    # ---- 剥风格明细落盘(2026-09-12, --strip_style; 独立文件, 不进 archive 表头) ----
    if _strip_style and strip_rows:
        try:
            _sd = pd.DataFrame(strip_rows)
            # ★ schema-aware 追加(2026-09-13, §8.30): 加列时会**重写并救回旧行**, 不再产生混合宽度
            _st, _sn = append_csv_schema_safe(STRIP_OBS, _sd)
            _n_pos = int((_sd['strip_ann_ex'] > 0).sum())
            print(f"已存 {STRIP_OBS} ({_st}, 本代 {len(_sd)} 条 L2 候选; "
                  f"剥风格后超额仍为正 {_n_pos}/{len(_sd)})")
        except Exception as e:
            print(f"  [剥风格] 落盘失败(不影响主流程): {type(e).__name__}: {e}")
    # ---- 池内指标落盘(2026-09-12, --pool_obs; **长表**, 独立文件) ----
    #  为什么长表: 池集合由 --pools 决定, 宽表(ic_300/ic_500...)一旦换池集合就会
    #  在追加时表头错位(与 loop_archive.csv 同一个坑)。长表 = (gen,expr,pool) 三键, schema 恒定。
    #  `pool_tag`(300好用/300+500好用/全都好用/只有全A好用) 由**离线**派生(阈值可改后重算)。
    if POOL_M and pool_rows:
        try:
            _pdd = pd.DataFrame(pool_rows)
            # ★ schema-aware 追加(2026-09-13, §8.30): 见 append_csv_schema_safe 的 docstring
            _pst, _psn = append_csv_schema_safe(POOL_OBS, _pdd)
            if 'rewritten' in _pst:
                print(f"  [池指标] schema 变化 -> 已重写 {os.path.basename(POOL_OBS)}: {_pst}")
            _n_cand = len(_pdd) // max(len(_pools), 1)
            _msg = ', '.join(
                f"{t}: 超额>0 {int((_pdd.loc[_pdd['pool'] == t, 'ann_ex'] > 0).sum())}"
                f"/{int((_pdd['pool'] == t).sum())}" for t in _pools)
            print(f"已存 {POOL_OBS} (追加, 本代 {len(_pdd)} 行 = {_n_cand} 候选 x "
                  f"{len(_pools)} 池; 池内超额>0 -> {_msg})")
        except Exception as e:
            print(f"  [池指标] 落盘失败(不影响主流程): {type(e).__name__}: {e}")
    res = pd.DataFrame(rows)
    # 失败模式库: L2 费后结果落地成败(中金: 失败表达式写入失败库, 生成阶段排除)
    top_node = {str(r['node']): r['node'] for _, r in top.iterrows()}
    for _, r_ in res.iterrows():
        nd = top_node.get(r_['expr'])
        if nd is not None:
            flib_mark(fail_lib, nd, args.gen, bool(r_['passed']),
                      '' if r_['passed'] else 'l2')
    if len(res):
        # 逐代累积流水(带 gen/cat/leaf 列): 文件缺失/为空时写表头, 其后追加
        # —— 每代 L2 明细永久留档(gen16 前旧快照已归 docs/history/loop_archive.legacy_pre_gen16.csv)
        res.insert(0, 'gen', args.gen)
        # ★ schema-aware 追加(2026-09-13, §8.44): 原先是"只判文件有无/为空"决定写不写表头,
        #   而 §8.34 给本表加了 `max_ex_corr`(第 17 列) ⇒ `loop_archive_300/500.csv` 变成
        #   「16列旧行 + 17列新行」混合宽度 ⇒ `pd.read_csv` 报
        #   `Expected 16 fields in line 165, saw 17`。**同一个坑的第三处**
        #   (前两处: loop_pool_obs_* / loop_strip_style_*, 见 `tools/fix_csv_schema.py`)。
        _ast, _asn = append_csv_schema_safe(ARCHIVE, res)
        if 'rewritten' in _ast:
            print(f"  [流水] schema 变化 -> 已重写 {os.path.basename(ARCHIVE)}: {_ast}")
        print(f"\n已存 {ARCHIVE} ({_ast}, 本代 {len(res)} 条)")
        p = res[res['passed']]
        print(f"L2 通过 {len(p)}/{len(res)} 个")
        if len(p):
            print(p.round(4).to_string(index=False))

    # ---- B角: 诊断本代 + 给出下一代策略 + 写日志 ----
    import loop_critic as critic
    # 给 critic 的副本附 seg_ok 列(不进 archive, 避免破坏累积流水表头)
    res_c = res.copy() if len(res) else res
    if len(seg_ok_list) == len(res_c):
        res_c['seg_ok'] = seg_ok_list
    # ★ 传 gate + pool_map（2026-09-14, §1.1 修法①②）：代末用**本代刚算出的**池结果，
    #   这样 `fail_pool_calmar` 反映的是"刚才那批候选离池门槛差多远"（真实卡点）。
    diag = critic.diagnose(l1, res_c if len(res_c) else None, args.gen,
                           gate=_gate_of(args), pool_map=_pool_best(pool_rows))
    diag['fam_blocked'] = fam_blocked
    # ---- 风格暴露诊断聚合(2026-09-11, --style_obs): 落盘已在 L1 求值后完成, 此处只做分组聚合 ----
    #  判读(见 docs/factor_roadmap.md §8.3/§8.4): new vs old 两组对比, 若 L2 候选/通过集的
    #  |lntr|、|lnamt| 中位显著上升 -> 确诊"新排序分在低换手/低成交额方向加倍下注"。
    if obs_df is not None and len(obs_df):
        try:
            _grp = {'st_l1_': set(l1['expr']) if len(l1) else set()}
            if 'expr' in getattr(res, 'columns', []):     # --l2=0 时 res 无列, 只报 L1 组
                _grp['st_l2_'] = set(res['expr'])
                if 'passed' in res.columns:
                    _grp['st_ok_'] = set(res.loc[res['passed'], 'expr'])
            for _tag, _es in _grp.items():
                _df = obs_df[obs_df['expr'].isin(_es)]
                if not len(_df):
                    continue
                for _k in STYLE_KEYS:
                    diag[_tag + _k] = float(np.nanmedian(np.abs(_df['st_' + _k])))
        except Exception as e:
            print(f"  [风格观测] 聚合失败(不影响主流程): {type(e).__name__}: {e}")
    next_cfg, reasons = critic.suggest(diag, cfg)
    print("\n[B角建议] 下一代:")
    for r in reasons:
        print("  -", r)
    critic.report(diag, next_cfg, reasons, JOURNAL)
    print(f"诊断已写入 {JOURNAL}")
    # ---- 生成侧 LLM 引导留痕(独立引用体小节, 与 ai_review 块同风格) ----
    if llm_on and n_llm_call:
        llm_journal_block(args.gen, n_llm_call, n_llm_parse, n_llm_hit,
                          llm_hyp, JOURNAL)
        print(f"LLM 引导小结已写入 {JOURNAL}")
    if n_jury_rev:
        llm_jury_block(args.gen, n_jury_rev, n_jury_kill, jury_lines, JOURNAL)
        print(f"LLM 候选审查小结已写入 {JOURNAL}")

    # ---- B角 LLM 审查(DeepSeek, --ai_critic auto/on/off, 默认auto=有key即启用) ----
    ai = getattr(args, 'ai_critic', 'auto')
    if ai != 'off':
        _airv = critic.ai_review(diag, l1, res_c if len(res_c) else None, args.gen,
                                 JOURNAL, reasons=reasons, sug=next_cfg, force=(ai == 'on'))
        # ★★★ 把 LLM 的否决**真正交回决策链**（2026-09-14, §1.1 修法④）——
        #   此前 `ai_review()` 的返回值**只用于打印、从不回写 `sug`**
        #   ⇒ 实测 **85/98 次**独立、跨池一致的反驳（"深度加深会加剧过拟合"）**全部被浪费**。
        #   现在写进 `next_cfg['_veto']`（键=**目标代**），下一代 `suggest()` 会**真的跳过**该动作；
        #   连续否决达 `critic.LLM_MUTE_N` 次则升级为**永久哨兵**（用户原话:「让它永久闭嘴」）。
        _vt = (_airv or {}).get('veto') or []
        if _vt:
            _tgt = args.gen + 1
            _v = next_cfg.setdefault('_veto', {})
            for _aid in _vt:
                _g = _v.setdefault(_aid, [])
                if not isinstance(_g, list):        # 防御: 旧 state 里的脏数据
                    _g = _v[_aid] = []
                if critic.MUTE not in _g and _tgt not in _g:
                    _g.append(_tgt)
            print("  [否决] 第 {} 代将跳过: {}".format(
                _tgt, ', '.join('{}（{}）'.format(a, critic.RULE_NAMES.get(a, '?')) for a in _vt)))

    # ---- 保存状态 ----
    new_seeds = list(l1.head(30)['node'])
    if len(res) and res['passed'].any():
        new_seeds = list(l1.head(20)['node'])
    # 入库因子库 bank: 本代通过者入列(node级去重), 供下代 decorr 对比
    # 对齐中金: ①冻结骨架禁入 ②同结构参数变体上限有限(bank_skel_max) 防窗口变体堆叠
    if len(res) and res['passed'].any():
        by_expr = {str(r['node']): r['node'] for _, r in top.iterrows()}
        skel_cnt = skeleton_freq(bank)
        fset = set(frozen) if args.fsa_th > 0 else set()
        n_bank_old = len(bank)
        lib_added = []
        for expr in res.loc[res['passed'], 'expr'].tolist():
            nd = by_expr.get(expr)
            if nd is None or any(str(x) == expr for x in bank):
                continue
            s = skeleton(nd)
            if s in fset:
                print(f"  [FSA] 通过但不入库: 骨架已冻结 -> {s}")
                continue
            if skel_cnt.get(s, 0) >= args.bank_skel_max:
                print(f"  [FSA] 通过但不入库: 骨架 {s} 已有 {skel_cnt.get(s,0)} "
                      f"个(上限{args.bank_skel_max})")
                continue
            # ★ 收益流去重(2026-09-13, roadmap §8.34, --dup_ex_corr): **止血**闸门。
            #   bank_ex 会在本循环里随入库增长 ⇒ 同时防"与历史库重复"与"同代内近重复"。
            #   ⚠ 拿不到收益流(旧 state / 回测失败)则**放行不误杀**(与本项目其它闸门同一铁律)。
            _ex_i = _ex_by_expr.get(expr)
            if _dup_ex_corr > 0 and _ex_i is not None:
                _mc2, _mw2 = ex_max_corr(_ex_i, bank_ex)
                if _mc2 is not None and _mc2 > _dup_ex_corr:
                    _n_dup_ex += 1
                    print(f"  [收益流去重] 不入库: 与库内收益流相关 {_mc2:.3f} > "
                          f"{_dup_ex_corr:.2f}（对方 {str(_mw2)[:66]}）")
                    continue
            bank.append(nd)
            skel_cnt[s] = skel_cnt.get(s, 0) + 1
            lib_added.append(expr)
            if _ex_i is not None:
                bank_ex[expr] = _ex_i          # 入库 -> 其收益流进对照集
        if _n_dup_ex:
            print(f"  [收益流去重] 本代拦下 {_n_dup_ex} 个「与库内赚同一块钱」的因子"
                  f"(阈值 |corr|>{_dup_ex_corr:.2f})")
        if len(bank) > n_bank_old:
            print(f"  入库 {len(bank)-n_bank_old} 个新因子, 累计 {len(bank)} 个")
            # 入库文档自动同步(factor_library.md): 只增不改, 失败不影响入库
            # ★ 带池标签(§8.42): 入库条目里写明"适用哪个池"
            _lib_sync(args.gen, res, len(bank), lib_added, by_expr,
                      pool_tags=_tag_by_expr, strip_grades=_strip_by_expr)
            # ★ 剥风格档汇总（2026-09-14, §1.9）：**"纯风格"必须吼出来** —— 它是"全A 口径漂亮
            #   但剥掉 lncap+lnamt 后转负"的因子，入库后**指数增强不可用**，不吼会被忽略。
            if _strip_by_expr:
                _sc_cnt = {}
                for _e in lib_added:
                    _v = _strip_by_expr.get(_e)
                    if _v:
                        _sc_cnt[_v[0]] = _sc_cnt.get(_v[0], 0) + 1
                if _sc_cnt:
                    print("  [剥风格档] 本代入库因子: " + ", ".join(
                        "{}x{}".format(k, v) for k, v in sorted(_sc_cnt.items())))
                _n_c = sum(v for k, v in _sc_cnt.items() if k == 'C')
                if _n_c:
                    print("  [!][剥风格档] **{} 个是「纯风格」**（剥掉 lncap+lnamt 后超额/Calmar 转负）"
                          "⇒ 指数增强不可用 ⇒ 检查 `--min_strip_calmar` 是否已设".format(_n_c))
            if _tag_by_expr:
                _tg_cnt = {}
                for _e in lib_added:
                    _t = _tag_by_expr.get(_e)
                    if _t:
                        _tg_cnt[_t] = _tg_cnt.get(_t, 0) + 1
                if _tg_cnt:
                    print("  [池标签] 本代入库因子: " + ", ".join(
                        "{}x{}".format(k, v) for k, v in sorted(_tg_cnt.items())))
    for k, v in DEFAULT_CFG.items():
        next_cfg.setdefault(k, v)      # critic.suggest 重建dict可能丢键 -> 兜底补齐
    next_cfg.setdefault('bank_skel_max', args.bank_skel_max)
    fail_lib = fail_lib_cleanup(fail_lib, args.gen)
    # ★ 原子写(2026-09-12 加固): 先写 .tmp 再 os.replace 原子替换。
    #   原因: 原 `open(STATE,'wb')` 会**立刻把旧 state 截断成 0 字节**, 一旦 dump 中途异常
    #   (或进程被杀), 就得到一个 0 字节坏状态 —— 而 journal 已写了"第 N 代完成"
    #   ⇒ 下次续跑会拿坏状态接代数, 静默错乱。实录见 roadmap §8.23。
    _tmp = STATE + '.tmp'
    with open(_tmp, 'wb') as f:
        pickle.dump(dict(seeds=new_seeds[:60], fsa=fsa,
                         # ★ 入库库**全量保存**(2026-09-12 去掉 `bank[-30:]` 上限, 用户选定):
                         #  截断会丢掉最老的入库因子 -> ①--decorr 不再对照它们 ->
                         #  引擎可能重新发现旧因子("打转"的隐藏成因); ②引擎 bank 与
                         #  docs/factor_library.md(append-only) 数量不一致(实录 30 vs 32)。
                         #  代价: --decorr 每候选要跟整库逐个比, 成本 O(len(bank)) ->
                         #  若库显著增长, 见去相关段的计时输出(实测 30 库/432 候选 = 276s)。
                         bank=bank,
                         # ★ 收益流库(§8.34): {表达式: 每期费后超额 Series}。
                         #   体积很小(每条 ~400 期 float64 ≈ 3KB; 100 个因子 ≈ 0.3MB)。
                         bank_ex=bank_ex,
                         frozen=frozen,
                         fail_lib=fail_lib,
                         n_tested=n_tested_prev + len(cands),
                         last_l1=l1, last_l2=res if len(res) else None,
                        # ★ 池口径传感器（2026-09-14, §1.1 修法②）: {expr: 最好的池 calmar}。
                        #   代首"重审上一代"时必须用它才能算出**池口径**失败率 ——
                        #   `last_l2` 只有全A 口径，回答不了"离池门槛差多远"。
                        #   体积很小（每代候选数个小 float），可忽略。
                        last_pool_map=_pool_best(pool_rows),
                         cfg=next_cfg), f)
    os.replace(_tmp, STATE)        # 原子替换: 要么全新状态, 要么保持旧状态, 不会出现半成品
    # ⚠ 日志口径: 打印的必须是**实际持久化**的数量(此前截断时打内存值 -> 与落盘不一致)
    print(f"\n保存状态: 种子 {len(new_seeds[:60])} 个, 入库因子 {len(bank)} 个(全量), "
          f"收益流库 {len(bank_ex)} 条, 冻结骨架 {len(frozen)} 个, 失败库 {len(fail_lib)} 条, "
          f"耗时 {time.time()-t0:.0f}s")


def clone(n):
    return Node(n.op, [clone(a) if isinstance(a, Node) else a for a in n.args])


def guided_expr(rng, cfg=None):
    """语义引导: 按【机制族】生成。中金 LLM 机制引导位定义 13 个机制族,
    核心为跳空溢价/振幅/影线/价格结构(实证 overnight 85% / amplitude 63%)。
    13族 = gap / gap_trend / gap_decay / amp / amp_vol / shadow / price_struct /
           mom / rev / vol / liq / turn_anom / vpin
    (此函数仅在引导位 LLM 候选不足时回退使用, 与 A角 Skill 的族口径同源。)
    """
    cfg = cfg or DEFAULT_CFG
    kind = rng.choice(['gap', 'gap_trend', 'gap_decay', 'amp', 'amp_vol',
                       'shadow', 'price_struct', 'mom', 'rev', 'vol', 'liq',
                       'turn_anom', 'vpin'])
    N = rng.choice([60, 100, 120, 150, 200])   # 长窗口(与中金 51~200 对齐)
    M = rng.choice([5, 20, 60])                # 短窗口
    VW = rng.choice([60, 100, 150, 200])       # ts_std 无120窗口
    leaf = lambda: pick_leaf(rng, cfg)
    if kind == 'gap':                          # 跳空溢价(中金第一大族)
        return Node('ts_mean%d' % N, [Node('overnight', [])])
    if kind == 'gap_trend':                    # 跳空趋势背离: sub(ma(overnight,N), 别字段)
        return Node('sub', [Node('ts_mean%d' % N, [Node('overnight', [])]),
                            Node('ts_mean%d' % N, [Node(leaf(), [])])])
    if kind == 'gap_decay':                    # 隔夜溢价衰减: 短-长均值差
        return Node('sub', [Node('ts_mean%d' % M, [Node('overnight', [])]),
                            Node('ts_mean%d' % N, [Node('overnight', [])])])
    if kind == 'amp':                          # 振幅(中金实证 63%)
        return Node(rng.choice(['ts_mean%d' % N, 'neg']), [Node('amplitude', [])])
    if kind == 'amp_vol':                      # 振幅波动聚集(波动率聚族变体)
        return Node('ts_std%d' % VW, [Node('amplitude', [])])
    if kind == 'shadow':                       # 影线支撑(中金 FSA 后被迫转向的方向)
        return Node(rng.choice(['ts_mean%d' % N, 'neg']),
                    [Node(rng.choice(['down_shadow', 'up_shadow']), [])])
    if kind == 'price_struct':                 # 价格结构 hl_ratio / true_range
        return Node('ts_mean%d' % N,
                    [Node(rng.choice(['hl_ratio', 'true_range', 'intraday']), [])])
    if kind == 'mom':                          # 动量
        return Node('ts_delta%d' % M, [Node(rng.choice(['close', 'vwap']), [])])
    if kind == 'rev':                          # 反转
        return Node('neg', [Node('ts_delta%d' % M,
                                 [Node(rng.choice(['close', 'vwap']), [])])])
    if kind == 'vol':                          # 波动率风险溢价
        return Node('neg', [Node('ts_std%d' % VW, [Node('ret', [])])])
    if kind == 'liq':                          # 流动性
        return Node('neg', [Node('log', [Node('ts_mean%d' % N, [Node(leaf(), [])])])])
    if kind == 'turn_anom':                    # 量能/换手异动: 短-长换手偏离
        return Node('sub', [Node('ts_mean%d' % M, [Node('turn_ratio', [])]),
                            Node('ts_mean%d' % N, [Node('turn_ratio', [])])])
    return Node('corr%d' % min(N, 100), [Node('volume', []), Node('ret', [])])  # vpin


# ===================== 生成侧 LLM 引导(A角子代理, 中金"生成预算20%语义引导") =====================
# loop_llm.GEN_SYSTEM/gen_candidates 已定义 A角 Skill 与调用封装; 此处只补两件事:
#   ① parse_expr: LLM 返回的表达式文本 -> 引擎 Node(严格反向解析, 任一不合规返回 None);
#   ② llm_fetch: 拼本代上下文 -> 调 gen_candidates -> 解析成 Node 池供引导位使用。
# 失败安全: 无 key/超时/JSON坏/语法不合规 -> 一律静默回退本地 guided_expr, 绝不阻塞迭代;
# 解析产物与规则候选走同一条守卫链(跨量纲/失败库/FSA/判重), 口径一致不产生旁路。
LLM_MAX_SIZE = 15         # 解析上限: 超过该节点总数的巨型表达式视为 LLM 失控, 丢弃
_EXPR_TOK = re.compile(r'[A-Za-z_][A-Za-z0-9_]*|[(),]')


def tokenize_expr(text):
    """分词并校验: token 间只允许空白, 出现其它字符(如 + 1 中缀残留)返回 None
    (防止 LLM 输出 'cs_rank(volume) + 1' 时非法尾部被静默吞掉而误收)。"""
    s = str(text)
    toks, pos = [], 0
    for mt in _EXPR_TOK.finditer(s):
        if s[pos:mt.start()].strip():
            return None
        toks.append(mt.group(0))
        pos = mt.end()
    if s[pos:].strip():
        return None
    return toks


def _parse_sexp(toks, i):
    """递归下降单元素: 返回 (Node|None, 下一token下标)"""
    if i >= len(toks):
        return None, i
    name = toks[i]
    i += 1
    if i < len(toks) and toks[i] == '(':
        i += 1
        args = []
        while True:
            nd, i = _parse_sexp(toks, i)
            if nd is None:
                return None, i
            args.append(nd)
            if i < len(toks) and toks[i] == ',':
                i += 1
                continue
            if i < len(toks) and toks[i] == ')':
                return Node(name, args), i + 1
            return None, i
    return Node(name, []), i


def parse_expr(text):
    """LLM 表达式文本 -> Node(与 Node.__str__ 前缀式 op(a, b) 严格对齐)。
    校验: 叶子名∈LEAVES / 函数名∈UNARY∪BINARY / 参数个数匹配 / size≤LLM_MAX_SIZE;
    任一不合规返回 None, 由调用方静默丢弃(不修复不猜测)。"""
    toks = tokenize_expr(text)
    if not toks:
        return None
    nd, i = _parse_sexp(toks, 0)
    if nd is None or i != len(toks):
        return None
    for x in collect(nd):
        if not x.args:
            if x.op not in LEAVES:
                return None
            continue
        if len(x.args) == 1:
            if x.op not in UNARY:
                return None
        elif x.op not in BINARY:          # len(x.args)==2
            return None
    if nd.size() > LLM_MAX_SIZE:
        return None
    return nd


def llm_fetch(args, cfg, seeds, bank, frozen, fail_lib, fam_black=''):
    """A角 LLM 拉一批候选: 拼上下文 -> loop_llm.gen_candidates -> 文本解析回 Node。
    返回 (ok, hyp, nodes); 任何失败 ok=False 且 nodes=[] (内部已打印原因)。"""
    import loop_llm
    diag = (f"第{args.gen}代搜索, 目标候选数{args.n}, 种子池{len(seeds)}个(上一代L1头部)。\n"
            f"当前已知: 入库因子{len(bank)}个(同骨架上限{args.bank_skel_max}), "
            f"冻结骨架{len(frozen)}个(禁止复用), "
            f"失败库{len(fail_lib)}条(多次全败骨架生成端排除)。\n"
            f"本代策略: mix(变异/交叉/扰动/引导/随机)={cfg['mix']}, depth={cfg['depth']}, "
            f"min_stab={cfg.get('min_stab')}, decorr={cfg.get('decorr')}, "
            f"fsa_th={cfg.get('fsa_th')}。\n"
            f"叶子权重: {cfg.get('leaf_w') or '(均匀)'}。")
    hint = ("请避开易重复结构: 纯市值/成交额/换手率的旧故事表达、同骨架只换窗口的参数变体"
            "都算重复; 优先给出有独立金融机制的表达式(跳空溢价/价量背离/波动结构/日内形态/"
            "流动性等), 宁少勿滥。")
    if fam_black:
        hint += ("\n[结构族黑名单] 上一代 L1 通过集被下列外层模板垄断(L1 高分但费后全灭), "
                 "本代请勿再产出同构模板(换内层参数/叶子不算新结构): " + fam_black)
    model = getattr(args, 'llm_model', None) or loop_llm.DEFAULT_MODEL
    ok, d = loop_llm.gen_candidates(diag, hint, n=args.llm_n, model=model)
    if not ok:
        print(f"  [LLM引导] 调用失败({d}) -> 回退本地引导")
        return False, '', []
    nodes = []
    for t in (d.get('exprs') or []):
        nd = parse_expr(t)
        if nd is not None:
            nodes.append(nd)
    print(f"  [LLM引导] 回复 {len(d.get('exprs') or [])} 条, "
          f"语法解析通过 {len(nodes)} 条")
    return True, (d.get('hyp') or '').strip(), nodes


def data_profile(nodes):
    """随机探索的'数据驱动特征分布'(中金): 统计证据候选的叶子字段与(去窗口)算子族频率。
    证据 = 历代入库因子 + 上一代 L1 通过候选;
    返回 {'leaf': {叶: cnt}, 'op': {算子族: cnt}} 或 None(无证据)。"""
    if not nodes:
        return None
    leaf, op = {}, {}
    for nd in nodes:
        try:
            for n in collect(nd):
                if not n.args:
                    leaf[n.op] = leaf.get(n.op, 0) + 1
                else:
                    fam = ''.join(c for c in n.op if not c.isdigit())
                    op[fam] = op.get(fam, 0) + 1
        except Exception:
            continue
    return {'leaf': leaf, 'op': op} if (leaf or op) else None


def _mix_weights(base, freq, universe, family=False):
    """把证据频率(按最大归一化)加权到 universe 每个候选名的抽样权重, 保留既有下限(0.3x)。
    family=True: freq 键为'去窗口算子族', 同族所有具体算子共享该族证据权重。"""
    if not freq:
        return dict(base)
    mx = max(freq.values()) or 1.0
    out = {}
    for k in universe:
        if family:
            n = freq.get(''.join(c for c in k if not c.isdigit()), 0.0) / mx
        else:
            n = freq.get(k, 0.0) / mx
        out[k] = base.get(k, 1.0) * (0.3 + 0.7 * n)
    return out


def node_stat_txt(nd):
    """候选级审查输入的结构统计(中金: 审查侧只给'表达式+结构统计', 不知来源/IC/假设)"""
    nodes = collect(nd)
    leaves = sorted({n.op for n in nodes if not n.args})
    ops = sorted({''.join(c for c in n.op if not c.isdigit()) for n in nodes if n.args})
    wins = sorted({int(x) for n in nodes for x in re.findall(r'\d+', n.op)})
    return (f"叶子字段: {','.join(leaves) or '无'}; 算子族: {','.join(ops) or '无'}; "
            f"节点数: {nd.size()}; 窗口参数: {wins or '无'}")


def llm_jury(args, rng, l1, model=None):
    """中金【审查】环节: L1 硬规则过滤后, 随机抽 --jury_n 个做 Sub-agent LLM 精判
    (与生成侧隔离防自证): verdict=KILL 者剔除出 L2; 调用失败/超时一律放行不误杀。
    返回 (kills:set[str], n_rev:int, n_kill:int, kill_lines:list[str])。"""
    import loop_llm
    kills, kill_lines, n_rev, n_kill = set(), [], 0, 0
    pool = list(l1['node'])
    n = min(max(0, int(getattr(args, 'jury_n', 5))), len(pool))
    if n <= 0:
        return kills, 0, 0, []
    print(f"  [LLM审查] 随机抽 {n} 个候选做 Sub-agent 精判 ...", flush=True)
    for i in rng.sample(range(len(pool)), n):
        nd = pool[i]
        ok, d = loop_llm.jury_verdict(str(nd), node_stat_txt(nd), model=model)
        if not ok:
            print(f"  [LLM审查] 判定失败({d}) -> 放行")
            continue
        n_rev += 1
        if d.get('verdict') == 'KILL':
            n_kill += 1
            kills.add(str(nd))
            reason = (d.get('reason') or '').replace('\n', ' ')
            kill_lines.append(f"- KILL `{nd}`\n  > 理由: {reason}")
            print(f"  [LLM审查] KILL {str(nd)[:72]} | {reason[:40]}")
        else:
            print(f"  [LLM审查] PASS {str(nd)[:72]}")
    return kills, n_rev, n_kill, kill_lines


def llm_jury_block(gen, n_rev, n_kill, kill_lines, path):
    """B角候选级审查小结追加 journal(引用体, 不干扰 _journal_format 的表格处理)"""
    body = [f"\n**LLM 候选审查(B角 {gen}代)**: 深判 {n_rev} 个, "
            f"KILL {n_kill} 个(剔除出 L2 费后回测)"]
    body += kill_lines if kill_lines else ['> (全部 PASS)']
    body.append('')
    with open(path, 'a', encoding='utf-8') as f:
        f.write('\n'.join(body) + '\n')


def llm_journal_block(gen, calls, parsed, used, hyp, path):
    """A角 LLM 引导小结追加 journal(引用体, 不干扰 _journal_format 的表格处理)"""
    body = [f"\n**LLM 引导(A角 {gen}代)**: 调用{calls}次, 解析通过{parsed}条, "
            f"引导位使用{used}条"]
    if hyp:
        body += ['> ' + x for x in hyp.splitlines()]
    else:
        body.append('> (本次无机制族假设)')
    body.append('')
    with open(path, 'a', encoding='utf-8') as f:
        f.write('\n'.join(body) + '\n')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--gen', type=int, default=1)
    ap.add_argument('--n', type=int, default=600)
    ap.add_argument('--gen_only', action='store_true',
                    help='dry-run: 只跑候选生成段验证产量, 不跑L1/L2/不写状态')
    ap.add_argument('--min_ic', type=float, default=0.02)
    ap.add_argument('--min_calmar', type=float, default=0.5)
    ap.add_argument('--min_stab', type=float, default=0.30)
    ap.add_argument('--batch', type=int, default=40,
                    help='L1 每批候选数(控内存: 每个(T,S)面板约71MB)')
    ap.add_argument('--dedup_n', type=int, default=70)
    ap.add_argument('--dedup_days', type=int, default=60)
    ap.add_argument('--dedup_corr', type=float, default=0.85,
                    help='同代数值近重复去重阈值: L1 TopN 内两两 rank|corr|>该值则丢弃后者; '
                         'gen51 由硬编码 0.99 放宽到此(0.99 拦不住 0.88~0.93 的近重复因子)')
    ap.add_argument('--decorr', type=float, default=-1,
                    help='与已知因子(ln_mktcap/amt_log + 历代入库 bank)的最大|corr|, 超过则丢弃; '
                         '负数=跟随B角建议(实际 0.65~0.75), 0=关闭。'
                         '**这即是「反冗余闸门」**(2026-09-11 批1 结论: novelty 不进排序分, 反冗余靠它)')
    ap.add_argument('--min_mono', type=float, default=0.0,
                    help='L1 形状门槛(批1 P0, 2026-09-11): 十档单调性 mono 低于该值则丢弃; 0=关闭(默认)。'
                         '标定(1150 条历史 L2 候选): 入库因子 mono 最小 0.770 -> 取 0.75 可拦下约 27%% '
                         '被判死的候选, 且对入库因子零误杀')
    ap.add_argument('--score_mode', choices=['old', 'new'], default='old',
                    help='L1 排序分(批1 P0, 2026-09-11): old=|IC_IR|×(0.25+0.75·stab) (默认, 原行为); '
                         'new=stab×(0.5+0.5·shape_pos)。标定: 与 L2 Calmar 的相关性 old +0.167 -> '
                         'new +0.668; new 不含 ic_ir(IC 仅留作 ic>min_ic 准入门槛)')
    ap.add_argument('--style_obs', action='store_true',
                    help='风格暴露观测(2026-09-11, 默认关): 记录**每个被求值的 L1 候选**对 '
                         'lncap/lnamt/lntr/lnpx 的截面秩相关(L1 子面板[::FWD] 视图), 紧跟 L1 求值 '
                         '落 docs/loop_style_obs.csv(故 L1 之后的任何早退都不丢样本); '
                         '是否进 L2/通过 L2 可与 loop_archive.csv 按 (gen, expr) 离线 join。'
                         '用途: 验证 --score_mode=new / --min_mono 是否让因子更往'
                         '「低换手/低成交额」挤(stab 即低换手代理)。关闭时零额外开销')
    ap.add_argument('--reuse_v', type=int, default=1,
                    help='跨阶段复用 L1 已算的因子值(2026-09-12, 默认 1=开): 去相关/去重不再'
                         '重复 eval_expr, 直接取 L1 缓存(只存过 ic/stab 门槛者的 [::FWD] 视图,'
                         '上限 2GB)。存的是符号对齐后的同一数组 -> 结果**逐位不变**, 只省时间。'
                         '--reuse_v=0 可关闭(供对拍验证)')
    ap.add_argument('--shape_neutral', type=int, default=0,
                    help='形状量改用风格中性收益(2026-09-12, 默认 0=关; roadmap §8.5.1 判定 [OK] 的行动①): '
                         '把 decile_shape 的收益入参换成**对 lncap/lnamt 逐期回归后的残差收益**, '
                         '于是 shape_pos 衡量"风格中性后的档位单调性"(同时影响 --min_mono)。'
                         '实测(3 代/2137 候选): 可把 --score_mode=new 的市值暴露**增幅砍掉 69%%**, '
                         '而低换手下降的好处不变。[!] 做测量时请只用 --style_obs(同时开会拿不到原始变体)')
    ap.add_argument('--strip_style', action='store_true',
                    help='剥风格入库判据(2026-09-12, 默认关; roadmap §8.13): L2 对每个候选额外'
                         '计算"剥 lncap+lnamt 后"的 IC/超额/Calmar(口径与 standard_test【6】'
                         '逐位一致: rank 对 rank 逐日截面 OLS 取残差 -> 再 rank -> 重跑回测), '
                         '落 docs/loop_strip_style.csv(独立文件, 不进 archive 表头)。'
                         '依据: 30 个历史入库因子剥成交额后**仅 3 个**超额仍为正、'
                         '沪深300 成分内**仅 3/30** 有效 -> 原"全A 超额"主要来自小市值+低成交额暴露。'
                         '[!] 只在开启时才有开销(每候选 +1 次回测)。')
    ap.add_argument('--min_strip_calmar', type=float, default=-1.0,
                    help='剥风格后 Calmar 的入库门槛(2026-09-12, 默认 -1=不设门槛): >0 时'
                         'L2 要求 strip_calmar 超过该值才判 PASS(与现有门槛是 AND 关系)。'
                         '[!] 需配合 --strip_style; 计算失败时放行不误杀(无人值守铁律)。'
                         '先建议用 --strip_style 只记录一代, 看分布再定阈值。')
    ap.add_argument('--mine_pool', default='all',
                    help='三池并行挖掘(2026-09-12, roadmap §8.19; 默认 all = 不加后缀, 向后兼容): '
                         '"all"=全A / "300"=沪深300 / "500"=中证500(可选池见 engine/loop_pools.py 的 POOLS)。'
                         '非 all 时: ①状态/输出文件**全部加 _<池> 后缀** -> 与其它池完全独立'
                         '(各自 state/bank/种子/冻结/失败库/archive/journal/library/观测表); '
                         '②L1 子面板列 = 该池并集(不随机抽样); ③L1 的 IC 按 **PIT 池掩码**算 = 池内 IC。'
                         '依据: 全A 含微盘 -> 低流动性溢价让风格因子轻松过关(§8.13: 30/30 的 lnamt/lntr'
                         '全负、剥成交额后仅 3/30 为正; §8.19: ic_all 与真信号**负相关 -0.317**); '
                         '池内不存在该溢价 -> 风格暴露自然挣不到分 -> 引擎必须去找真信号。'
                         '[!] 池内 IC 的截面样本更少、且无小盘溢价 -> --min_ic 等门槛**需重新标定**, '
                         '不要照搬全A 的取值。')
    ap.add_argument('--pool_obs', action='store_true',
                    help='池内指标(2026-09-12, 默认关; roadmap §8.9 的 B+B′): L2 在**指数成分内**'
                         '重跑一遍费后回测(口径 = 池内排名, 对齐 standard_test 默认的 --pool_mode=A; '
                         '基准随之变同池等权), 落 docs/loop_pool_obs.csv(**长表**: 每候选 x 每池一行)。'
                         '用途: 给入库因子打标签(300好用/300+500好用/全都好用/只有全A好用), '
                         '供将来因子库 PG 按标签筛选。'
                         '[!] 零列扩张成本: L2 用全量面板, 池股天然都在; 只在开启时才有开销'
                         '(每候选 x 每池 +1 次回测)。')
    ap.add_argument('--pools', default='300,500',
                    help='--pool_obs 要算哪些池(默认 300,500; 逗号分隔)。可选见 '
                         'engine/loop_pools.py 的 POOLS(300/500/1000/50)。')
    ap.add_argument('--dup_ex_corr', type=float, default=0.0,
                    help='★ 收益流去重阈值(2026-09-13, roadmap §8.34; 0=关, 默认关=行为不变)：'
                         '候选的**每期费后超额序列**与库内任一因子收益流的 |Spearman 相关| '
                         '超过该值时**不入库**。为什么用收益流而不是表达式：实测库内 30 个入库'
                         '因子的组合收益两两相关**中位 0.967**（它们是同一块钱的不同写法，'
                         '等权合成 Calmar 0.978 还**低于**最好的单因子 1.146），'
                         '而结构层面极多样（骨架 1181 个唯一、Top5 仅 1.9%%）'
                         '⇒ **表达式/因子值去重挡不住"同一块钱"，只有收益流能识别**。'
                         '建议 0.90（越严格库越"独立"但入库越少）。'
                         '[!] 需 state 里有 bank_ex；旧 state 先跑 tools/backfill_bank_ex.py 补齐。')
    ap.add_argument('--min_sharpe', type=float, default=0.5,
                    help='L2 全A 口径的夏普门槛(2026-09-13, roadmap §8.26)。'
                         '**默认 0.5 = 与原硬编码值相同, 行为完全不变**。'
                         '原先是写死的 `rr["sharpe"] > 0.5`; 逐门诊断(§8.25-③)显示它在 **AND** 组合下'
                         '是最大卡点(300 池砍掉 83%%、500 砍 71%%), 但在 **OR** 组合下它是合理的'
                         '全A 分支门槛 ⇒ **改 OR 比删它更对**。')
    ap.add_argument('--pool_gate_or_all', action='store_true',
                    help='★把池门槛与全A 量化口径改成 **OR** 语义(2026-09-13, roadmap §8.26; 默认关,'
                         '关=保持原 AND 行为)。开启后判定变为: '
                         '「全A 口径(calmar/sharpe/分段)达标」**或**「池内 Calmar 达 --min_pool_calmar」。'
                         '依据: 池内有效与全A 有效**基本不同源** —— 300 池"池内有效但全A 无效"有 31 个,'
                         '是"两者都有效"15 个的两倍 ⇒ AND 会把它们全砍掉(对"只在池内有效"的因子,'
                         '同时要求全A 达标是自相矛盾)。组合标定(ai_test/combo_calib.py): '
                         'AND 最优只保留 5/167(召回 8%%), OR 可保留 41/167(精率 59%%、召回 49%%)'
                         '⇒ **保留量约 6 倍**。')
    ap.add_argument('--min_pool_calmar', type=float, default=-1.0,
                    help='★池门槛(2026-09-12, 默认 -1=关; **用户选定方案 C = 排除 csi_all_only**): '
                         '>=0 时启用, 用池内 Calmar 与 --min_pool_calmar 比较(与 --min_calmar 同口径, '
                         'Calmar>0 即"该池有效")。配合 --pool_gate_mode 决定语义。'
                         '[!] 会自动打开 --pool_obs; 无池结果时放行不误杀并计数上报。'
                         '实测基准(gen71): 池内 Calmar>0 仅 2/21 候选, 且这 2 个全A Calmar 都<0.5 '
                         '-> 与 --min_calmar=0.5 叠加后**本代入库 0 个**(原为 2)。')
    ap.add_argument('--pool_gate_mode', default='any', choices=['any', 'all'],
                    help='池门槛语义: any(默认, =方案C) 要求**至少一个池**达标 —— 滤掉"只在全A有效"的; '
                         'all 要求**所有池**达标 —— 更严, 要"真 alpha"(实测 gen71 下 all 会 0/21)。')
    ap.add_argument('--fsa_th', type=float, default=-1,
                    help='FSA骨架冻结阈值: bank中同骨架占比超过该值即冻结该骨架, '
                         '后续候选不再生成/入库(中金>15%%冻结); 负数=跟随B角建议, 0=关闭')
    ap.add_argument('--bank_skel_max', type=int, default=1,
                    help='bank中每个骨架允许的最大入库数(同结构参数变体上限, 中金FSA)')
    ap.add_argument('--dim_review', type=float, default=-1,
                    help='跨量纲静态审查(中金审查规则): 拦截价格+成交量等异量纲add/sub; '
                         '负数=开启(默认), 0=关闭')
    ap.add_argument('--fail_rate', type=float, default=-1,
                    help='失败模式库排除阈值: 全败率>=该值且失败>=min_fail的骨架生成时排除; '
                         '负数=跟随B角cfg(默认0.6), 0=关闭')
    ap.add_argument('--min_fail', type=int, default=-1,
                    help='失败模式库最小失败次数(默认3)')
    ap.add_argument('--ai_critic', default='auto', choices=['auto', 'on', 'off'],
                    help='B角LLM审查(DeepSeek): auto=找到key(环境变量DEEPSEEK_API_KEY或桌面1.txt)'
                         '即每代末尾自动AI审查并写journal; on=强制(无key仅告警跳过); off=纯规则B角')
    ap.add_argument('--llm_guide', default='auto', choices=['auto', 'on', 'off'],
                    help='A角生成侧LLM引导(中金生成预算~20%%语义引导位): '
                         'auto=找到DeepSeek key即启用(引导位候选=LLM表达式); '
                         'on=强制(无key告警后回退本地引导); off=纯本地规则引导')
    ap.add_argument('--llm_n', type=int, default=12,
                    help='每次A角LLM调用请求的表达式条数(建议8~16, loop_llm上限)')
    ap.add_argument('--llm_max_calls', type=int, default=3,
                    help='每代最多A角LLM调用次数(超限回退本地 guided_expr, 防拖慢无人值守)')
    ap.add_argument('--llm_model', default=None,
                    help='A角生成侧模型名(缺省与B角审查同款 loop_llm.DEFAULT_MODEL=deepseek-flash; '
                         '可选 deepseek-v4-pro 做物理隔离。[!] 名单以 tools/probe_models.py 实测为准)')
    ap.add_argument('--ai_jury', default='auto', choices=['auto', 'on', 'off'],
                    help='B角候选级LLM审查(中金【审查】环节, L1硬滤后随机抽--jury_n深判, '
                         '与生成侧隔离防自证): KILL者剔除出L2; auto=找到DeepSeek key即启用; '
                         'on=强制(无key告警跳过); off=纯硬规则审查')
    ap.add_argument('--jury_n', type=int, default=5,
                    help='LLM候选精判每代抽样个数(中金随机抽5)')
    ap.add_argument('--ai_jury_model', default=None,
                    help='审查侧模型名(缺省同loop_llm.DEFAULT_MODEL=deepseek-flash; '
                         '可选 deepseek-v4-pro 与生成侧做物理隔离)')
    ap.add_argument('--l2', type=int, default=40)
    ap.add_argument('--fam_quota', type=int, default=FAM_QUOTA,
                    help='结构族配额(QuantaAlpha冗余检测, gen31): L1通过集同模板族'
                         '(外层结构相同仅内层微调)最多保留N条进L2/种子池; 0=关闭')
    ap.add_argument('--fam_block_thr', type=float, default=FAM_BLOCK_THR,
                    help='结构族黑名单: 上代L1同模板族占比>=该值则本代生成端禁产该模板族'
                         '(强制结构换血); 0=关闭')
    ap.add_argument('--fam_sole', type=int, default=1,
                    help='族指纹是否并入"单叶变换"维度(gen51 叶子代理闸门): 顶层 max/min 的'
                         '内层若只是某叶的单目变换(如 ts_min20(cs_rank(barra_leverage))≡leverage), '
                         '族键追加 |~<叶名> -> 同叶不同壳的代理候选判同族、按 fam_quota 拦重复; 0=关闭')
    ap.add_argument('--seed', type=int, default=42)
    ap.add_argument('--cost', type=float, default=DEFAULT_COST,
                    help='往返成本(扣在单向换手率上): 默认主用档 %.4f = 实盘(0.0046)略宽松取整; '
                         '预设: 实盘(滑点千1.5)=0.0046 / 实盘(滑点千2)=0.0056 / 主用档=0.004 / '
                         '压力档=0.007; 定义与构成见 engine/cost_presets.py' % DEFAULT_COST)
    ap.add_argument('--window', choices=['full', 'recent600'], default='full',
                    help='回测口径: full=2018起九年; recent600=最近600交易日(中金口径)')
    ap.add_argument('--seg_n', type=int, default=3,
                    help='分段独立验证: 费后日超额序列均分成多少个不相交子区间; '
                         '0/1=关闭(默认3: 约3年一段); 样本不足自动放行不误杀')
    ap.add_argument('--seg_need', type=int, default=2,
                    help='分段独立验证: 至少几个子区间累计费后超额>0 才通过 '
                         '(默认2: 3段中≥2段为正, 拦"靠单段行情撑全样本"候选)')
    _args = ap.parse_args()
    set_mine_pool(_args.mine_pool)   # ★必须在 run() 之前: 路径后缀 & L1 池掩码都在 run 内部生效
    run(_args)
