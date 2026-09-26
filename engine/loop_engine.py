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
# ★★★★★ 2026-09-25（用户实测："这 F47 为啥会显示未分类"）：**「两份 `Node` 类」的修复**
#   在**文件末尾**的 `if __name__ == '__main__':` 块里（那里有完整说明 ✓）
#   ⚠ 为什么**不**放这里：`tools/_test_fwd_wiring.py` 用 AST 取**第一个** `__main__` 块，
#     并在其中断言 `set_panel_cache` / `set_mem_budget` / `run(_args)` 是**直接语句** ✗
#     ⇒ 在顶部另起一个 `__main__` 块会把它的"目标块"抢走（实测该守门当场失败 ✗）
import factor_miner as _FM          # ★ 口径**单一事实源**（FWD 走运行期取值 ✗ 见下）
from factor_miner import (load_panel, prepare, get_universe, cs_rank,
                          evaluate_real, START, COST_PRESETS, pass_filter)
# ★★ 2026-09-22 修（**真 bug** ✗✗，2026-09-22 14:25 那次跑的日志里两池都命中 ✓）：
#   `pass_filter` 原来**只在 `run()` 函数内部** import（在副口径判定**之后** ✗）⇒
#   ① 函数内 import ⇒ 该名字在 `run()` 里是**局部名** ✓
#   ② 而副口径判定（L3026 一带）**先用**了它 ✗ ⇒ `UnboundLocalError` ⇒ 被 except 吞掉
#      ⇒ 只打一行「副口径判定失败(按未过处理)」✗ ⇒ **`ok2` 恒为 False** ✗✗
#   ⇒ 后果：**双口径的副口径通道自 v1.21.29 上线起从未通过一次** ✗（而生产一直开着 ✓
#     `tools/run_tracks.py` 传 `--dual_fwd=20` ✓）⇒ 所有"只有 20 日才通过"的因子**一条都没能
#     自动入库** ✗（今天那 11 个是事后**受控补录**进去的 ✓ 由此也能解释 ✓）
#   ⇒ 修法：**只留这一个模块级 import 点** ✓ —— 关键是"全函数不得再有任何本地绑定" ✗
#     （位置本身不关键 ✓；本地绑定才是病根 ✓ 见 `tools/_test_dual_horizon.py` 的 AST 断言 ✓）

# ★★★★★ 2026-09-21（用户拍板：(C) 双口径挖掘的**前置改造**）——
#   `FWD` 原来是 `from factor_miner import FWD` = **import 时的值拷贝** ✗
#   ⇒ `factor_miner.set_fwd()` 改的是 fm 的全局、**改不到本模块** ✗（`factor_metrics.py` 则直接用
#     `factor_miner` 模块 ⇒ 所以重评能换口径、引擎不能 ✓ 就是这个原因 ✓）
#   ⇒ 现在：本模块保留**模块全局 `FWD`**（14 处 `[::FWD]` 切片照旧 ✓ 一行都不用改 ✓），
#     但它的值**由 `main()` 在解析完 `--fwd` 后同步一次** ✓（见文件末尾的同步块 ✓）
#   ⚠⚠ **只能"加口径"、不能"换口径"** ✗：把 5 改成 20 ⇒ 现有库数字/阈值/曲线全部错位 ✓
#     ⇒ 生产上用**独立轨道 + `horizon` 标签** ✓
FWD = _FM.FWD
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


# ===================== 三池并行挖掘(2026-09-12, roadmap §8.19) =====================
# 用户方案: 全A / 沪深300 / 中证500 三条**完全独立**的轨迹(各自 state/bank/种子/冻结/失败库)。
# 依据: 全A 含微盘 -> "低流动性溢价"让风格因子轻松过关, 且 L1 的单一 IC 排序也奖励它
#   (§8.13 实测 30/30 的 lnamt/lntr 全负、剥成交额后仅 3/30 为正; §8.19 实测 ic_all 与真信号
#    **负相关 -0.317**)。在 300/500 池内挖, 该溢价不存在 -> 风格暴露自然挣不到分 -> 引擎必须
#   去找真信号。(QuantaAlpha 正是如此: `market: csi300` + benchmark SH000300, §8.8/§8.19)
# 实现: 'all' = 现状(不加后缀; 现有 loop_state.pkl / loop_archive.csv 即全A轨迹的既有历史);
#       '300'/'500' = 全新独立轨迹(文件加 _300/_500 后缀)。可选池见 engine/loop_pools.py 的 POOLS。
L1_POOL_MASK = None       # (len(L1_ROWS), len(L1_COLS)) bool; None = 不加池约束(全A现状)


def set_mine_pool(tag):
    """把引擎切到指定池的**独立轨迹**。

    ① 状态 / 输出文件全部加池后缀 -> 三条轨迹互不读写对方的 bank/archive/journal/library;
    ② L1 子面板列 = 该池**并集**(历史上出现过的全部成分, 保证任一时点的成分都在面板里);
    ③ L1 的 IC 按 **PIT 池掩码**算 -> 目标函数从"全A IC"变成"**池内 IC**"。

    tag='all' 时**完全不动**(向后兼容)。幂等(可从原始路径重复派生)。返回实际生效的 tag。
    """
    if not tag or tag == 'all':
        _P.MINE_POOL = 'all'
        _P.apply_suffix('')
        return 'all'
    import loop_pools as _LP
    if tag not in _LP.POOLS:
        raise SystemExit(f"[--mine_pool] 未知池 '{tag}'; 可选: all / {sorted(_LP.POOLS)}")
    _P.MINE_POOL = tag
    _P.apply_suffix('_' + tag)
    return tag


# 默认搜索策略(B角可动态调整)
# ===================== 1. 基础字段 =====================
# ---- 叶子字段单一事实源 = loop_fields.py (引擎A角/B角critic/量纲/写档共用) ----
# 新增字段族只改 loop_fields.py 一处, 勿在本文件硬编码叶子名(防再漂移)。
# 资金流 moneyflow3 原始拆分16列: 金额(×1e4元,量纲A)+量(×100股,量纲V), 净额不预焊由GP自组合;
# BARRA 连续风格11(barra.h5,行业哑不入叶) / 财报PIT as-of比率8(fa_pit.h5,按info_date无未来函数)
from loop_fields import MF16, BARRA_LEAVES, FA_LEAVES, LEAVES, FIELDS
from loop_expr import Node, collect            # ★ L3 拆分：表达式核心类型/遍历单一事实源
from loop_dims import review_expr, dim_of      # ★ L3 拆分：跨量纲审查单一事实源
from loop_expr import _fsa_stats  # ★ 文件级拆分：FSA 骨架统计
from loop_gen import _build_fam_blacklist  # ★ 文件级拆分：结构族黑名单
from loop_data import _build_panel_fresh, _panel_sha1  # ★ 文件级拆分：面板构造
import loop_paths as _P  # ★ 文件级拆分：路径常量单一事实源（用 _P.STATE 运行时取，勿值拷贝）
from loop_persist import (append_csv_schema_safe, _real_mb,
                         _dump_strip_detail, _dump_pool_obs,
                         _cmp_lib, ex_max_corr, _tag_desc, _gate_of, _pool_best,
                         combine_ok, _mk_library_skeleton, append_library_entries,
                         _lib_sync, _save_state)  # ★ 文件级拆分：库文档/收益流/保存
from loop_llm_guide import llm_fetch, parse_expr  # ★ L3 拆分：LLM 引导

LLM_MAX_SIZE = 15         # 解析上限: 超过该节点总数的巨型表达式视为 LLM 失控, 丢弃
# ★ 2026-09-26 L3：留在 loop_engine 而非 loop_llm_guide —— 多个 tools 会运行期临时放开
#   `LE.LLM_MAX_SIZE=10**9`，若抽到 loop_llm_guide 则「值拷贝」改不到 parse_expr 读的那份 ✗
from loop_gen import (DEFAULT_CFG, _wt, _clean_cfg, pick_leaf, pick_op,
                     rand_expr, eval_expr, mutate, LEAF_CAT, leaf_parts,
                     crossover, PARENT_SEL_MODES, pick_parent, perturb)
from loop_ops import (UNARY, BINARY, ts_delay, ts_delta, cs_rank_op,
                     cs_demean_op, cs_scale_op)  # ★ L3 拆分：算子表+le算子
from loop_faillib import flib_mark, fail_lib_cleanup, bad_skels  # ★ L3 拆分：失败模式库
from loop_expr import (norm_op, skeleton, skeleton_freq, subtree_skels,
                        has_frozen_skel, fsa_period, sole_leaf,
                        leaf_proxy_key, root_fam, FSA_FREEZE_SEQ,
                        FSA_COOL_GENS, FAM_CUT, FAM_QUOTA, FAM_BLOCK_THR)

# ★★★ 2026-09-16 新增「面板只读缓存」模式（`--panel_cache`，**默认 off ⇒ 与改造前逐位不变**）
#   实测：面板 B = 4.42 GB 且**构造完成后只读**；而 Windows 是 spawn(无 fork) ⇒
#   每个引擎进程各建一份。落成只读 memmap 后多进程共享同一批物理页（省内存 + 免重建）✓
#   实现见 `engine/panel_cache.py`（含过期检测/只读保护 → 不会静默用旧面板）。
PANEL_CACHE = 'off'


def set_panel_cache(mode):
    """切换面板缓存模式：`off`(默认, 现状) / `use`(必须命中) / `build`(构造并落盘)。

    ★ 必须在 `run()` 之前调用（与 `set_mine_pool` 同理）：`base_fields()` 在 run 内首次被调用。
    """
    global PANEL_CACHE
    m = (mode or 'off').strip().lower()
    if m not in ('off', 'use', 'build'):
        raise SystemExit('[--panel_cache] 非法取值 %r（可选: off/use/build）' % (mode,))
    PANEL_CACHE = m
    return PANEL_CACHE


def set_mem_budget(lru_max=400, cache2_max=150, vreuse_cap_mb=800.0,
                   lru_mb=1200.0, cache2_mb=800.0, batch_mb=1500.0):
    """调「**每进程私有缓存**」的上限。

    ★ 为什么需要它：并行跑 N 个池时，**面板**可以靠 `--panel_cache=use` 跨进程共享，
      但 `_LRU` / `cache2` / `VCACHE` 是**每进程私有**的（私有脏写，不能共享）⇒
      它们才是"并行时的内存地板"。要把总占用压到某个数（如 ≤10 GB），
      就得按 N 把这份预算切小 ✓
    ★ 代价：缓存越小 ⇒ 越多的子树要**现场重算** ⇒ 每代变慢（时间换内存）。

    ★★★★★ 2026-09-21 **治本**（用户："走治本的方案A吧"）：**条数上限管不住内存** ✗
      —— 实测（`ai_test/_memprof_1000.py` 外部采样 · 1000 池单代）：
        · `--n=800` 一代里，私有内存 **1 分钟到 4.9 GB、8 分钟到 14.6 GB（工作集 16.6 GB）** ✗
        · 而且是**锯齿式上台阶**（12.5 ↔ 14.8 GB 反复 ✓）⇒ 回不到基线 = **缓存在囤** ✗
        · 根因：`LRU_MAX = 400`、`CACHE2_MAX = 150` 都是**条数** ✗，而单条的体积随**池宽**变：
          1000 池的 L1 子面板 = **2094 日 × 2818 股**（池并集 ✓ 实测日志 ✓）⇒ 单条 ≈ **47 MB** ✗
          ⇒ `400 条 × 47 MB ≈ 18.8 GB` ✗✗（引擎日志里 VCACHE 早就按 MB 算了 ✓，
             只有这两个缓存漏了 ✗）
        · 池越大 ⇒ 单条越大 ⇒ 越容易把机器压到换页（1000 池单代 110~172 分钟 ✗ = 嫌疑根因 ✓）
      ⇒ 修法（**只改"缓存回收"，不动任何数值口径 ✓**）：
        ① `trim_cache_mb()`：按 `arr.nbytes` 累计，超预算从**最旧**开始淘汰 ⇒ **硬上限** ✓
        ② `--lru_mb / --cache2_mb`：字节预算（条数上限**保留作兜底** ✓）
        ③ `--batch_mb`：L1 批大小**按字节自适应** ✗（固定 40 个时，宽池一批就 ≈1.9 GB ✗）
    """
    global LRU_MAX, CACHE2_MAX, _VREUSE_CAP_MB, LRU_MB, CACHE2_MB, BATCH_MB
    LRU_MAX = max(20, int(lru_max))
    CACHE2_MAX = max(20, int(cache2_max))
    _VREUSE_CAP_MB = max(0.0, float(vreuse_cap_mb))
    LRU_MB = max(50.0, float(lru_mb))
    CACHE2_MB = max(50.0, float(cache2_mb))
    BATCH_MB = max(100.0, float(batch_mb))
    print('[内存预算] 每进程私有缓存: LRU=%d 条 / ≤%.0f MB · cache2=%d 条 / ≤%.0f MB · '
          'VCACHE≤%.0f MB · L1 单批≤%.0f MB (面板是否共享见 --panel_cache)'
          % (LRU_MAX, LRU_MB, CACHE2_MAX, CACHE2_MB, _VREUSE_CAP_MB, BATCH_MB), flush=True)
    return LRU_MAX, CACHE2_MAX, _VREUSE_CAP_MB


_BASE = None
L1_STOCKS = 2000          # L1 粗筛抽样的股票数(越小越快, 但IC估计误差越大)
L1_ROWS = None
L1_COLS = None
_LRU = {}                 # 跨批次复用子树求值结果(种子演化共享大量子树)
LRU_MAX = 400             # L1 每批结束把 _LRU 裁到该条数上限(防 L1 段 OOM)
CACHE2_MAX = 150          # 去相关/去重阶段 cache2 的子树缓存上限
# ★★★★★ 2026-09-21（治本）：**字节预算**（条数上限管不住内存 ✗ —— 单条体积随池宽变：
#   1000 池子面板 2094×2818 ⇒ 单条 ≈47 MB ⇒ 400 条 ≈18.8 GB ✗；实测私有内存峰值 14.6 GB ✓）
#   ⇒ 这三条是**主控**（条数上限保留作兜底 ✓），由 `--lru_mb / --cache2_mb / --batch_mb` 调 ✓
LRU_MB = 1200.0           # ★ 2026-09-21 收紧 2500 → 1200（A/B 实测见下 ✓）
CACHE2_MB = 800.0         # 去相关/去重阶段 cache2 ≤ 该 MB
BATCH_MB = 1500.0         # L1 单批候选的**数组总量**上限（批大小按它自适应 ✓）
                          # (该段每候选只需算1次、无跨批复用, 缓存仅服务邻近候选共享,
                          #  故宜小; 实测 gen37 该段无界累积导致内存从9G单调涨到20G+)
# ★跨阶段复用缓存(2026-09-12): L1 已算过的因子值, 供**去相关/去重**直接取用, 免二次 eval。
#   实测依据: 一代 52min 里 L1 占 44%、去相关+去重占 **43%**(499 个候选各重算约 2.7s),
#   而 L2 只占 10%(evaluate_real 单次仅 ~7s) -> **重复 eval 才是最大浪费**, 不是 L2。
#   只存"过 ic/stab 门槛"的候选, 且只存 [::FWD] 调仓日视图(419×2000 float32 ≈ 3.35MB/个);
#   存的是**符号对齐后**的同一数组 -> 下游 rank_rows 结果逐位不变(行为等价, 非近似)。
VCACHE = {}
_VREUSE_MB = [0.0]        # 已占用 MB(list 便于就地累加)
# ★ 2026-09-21 收紧 2000 → 800（A/B 实测见下 ✓）
_VREUSE_CAP_MB = 800.0    # 上限; 超了就不再存(未命中者在去相关/去重处回退为现场 eval)


def base_fields():
    """返回 {name: (T,S) float32} 基础字段 + 日期/列"""
    global _BASE
    if _BASE is not None:
        return _BASE
    # ★★★ 2026-09-16「面板只读缓存」（`--panel_cache`，**默认 off ⇒ 与改造前逐位不变**）：
    #   面板 4.42 GB 且构造后只读 ⇒ 落成只读 memmap 后多进程共享同一批物理页（spawn 下也能省内存）。
    #   · `use`   = 必须命中；缺失/过期**直接报错**（绝不偷偷重建，更不会拿旧面板算新结果）
    #   · `build` = 现场构造一份并落盘，随后继续用（结果与 off **逐位相同**）
    #   ⚠ 只有"面板从哪来"变了；`B_sub` / `L1_POOL_MASK` 等派生逻辑**保持逐字不变** ✓
    if PANEL_CACHE == 'off':
        B, dates, cols, close = _build_panel_fresh()
    else:
        import panel_cache as _pc
        if PANEL_CACHE == 'use':
            B, dates, cols, _cv, _man = _pc.load(_panel_sha1())
            # close 只有 0.14 GB，**拷一份**避免"pandas 直接操作只读块"的一类意外
            close = pd.DataFrame(np.array(_cv), index=pd.Index(dates), columns=cols)
            print('[面板缓存] 只读映射命中: %d 字段 / %.2f GB -> %s'
                  % (len(B), _pc.size_gb(B), _pc.CACHE_DIR), flush=True)
        else:
            B, dates, cols, close = _build_panel_fresh()
            _pc.save(B, dates, cols, close.values, _panel_sha1())
    # ★L1 子面板: 粗筛不需要全样本(瓶颈是内存带宽, 不是计算)。
    #   时间只取 START 之后 + 截面随机抽样 -> 数据量降到 ~1/4, 实测整体提速 3~4 倍。
    #   L1 只是排序用, 抽样误差可接受; L2 精筛仍用全样本。
    global L1_ROWS, L1_COLS, L1_POOL_MASK
    L1_ROWS = np.where(dates >= START)[0]
    if _P.MINE_POOL != 'all':
        # ★池内挖掘(§8.19): L1 列 = 池**并集**(不随机抽样 —— 必须保证任一时点的成分都在)。
        #   掩码另按 PIT 生效, 故并集稍大不影响口径。
        import loop_pools as _LP
        uni = _LP.pool_union(_P.MINE_POOL)
        L1_COLS = np.array([i for i, c in enumerate(cols) if c in uni], dtype=np.int64)
        if L1_COLS.size == 0:
            raise SystemExit(f"[--mine_pool={_P.MINE_POOL}] 池并集与面板列无交集, 检查股票代码格式")
        L1_POOL_MASK = _LP.pool_mask(_P.MINE_POOL, dates, cols)[np.ix_(L1_ROWS, L1_COLS)]
        print(f"[--mine_pool={_P.MINE_POOL}] L1 子面板列 = 池并集 {L1_COLS.size} 只; "
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


# ⚠ 2026-09-15（架构清扫 P0-1）删除 4 个**死代码**：`ts_max_op` / `ts_min_op` /
#   `ts_corr20_op` / `ts_corr60_op` —— 早期实现残留（当时算子表还没统一用
#   `_mx`/`_mn`/`_cr`），经 `tools/_audit_deadcode.py` 实测：**本文件内外均无引用** ✗
#   且与 `UNARY` 里的 `ts_max20`/`ts_min20`/`corr20`/`corr60` 功能重复 ✓



# ★LEAVES 完整叶子池已由顶部 `from loop_fields import LEAVES` 提供
#   (基础7 + 派生12 + MF16资金流 + BARRA11风格 + FA8财报 = 54), 勿在此重复硬编码(防漂移)

# ===================== 3. 表达式 =====================
class _StateUnpickler(pickle.Unpickler):
    """★★★★★ 2026-09-25：读 state 时把**历史上误存的** `loop_engine.Node` 一并归一成本类 ✓

    背景（完整说明见**文件末尾** `__main__` 块里那行注册）：引擎直跑时曾并存**两个 `Node` 类**
    （`__main__.Node` 与 `loop_engine.Node`）⇒ 旧 state 的 `bank` / `seeds` / `last_l1`
    里混着两份类 ✗

    ⚠ 为什么必须归一：`isinstance(x, Node)` 是**类身份**判定 ⇒ 对第二份实例恒为 False ✗
      ⇒ `collect` / `leaf_parts` / **`skeleton`（骨架去重 / FSA 冻结）** / `key` / `size` /
      `crossover` / `mutate` / `dim_of` **全部对那批因子失效** ✗✗
      （实测：`bank` 439 个 Node 里 **438 个**是第二份 ⇒ 去重与 FSA 一直没对它们生效 ✗）

    修法：**只认类名** —— 不管 pickle 里记的是 `__main__.Node` 还是 `loop_engine.Node`，
      一律还原成**本模块**的 `Node` ✓（结构逐字一致，差的只是类身份 ✓）
    """

    def find_class(self, module, name):
        if name == 'Node':
            return Node
        return super().find_class(module, name)


def _jscalar(v):
    """Node 的非 Node 参数 ⇒ **JSON 安全标量**（numpy 标量/自定义类一律降级，别让 `json.dump` 炸）✓"""
    if v is None or isinstance(v, (bool, int, str)):
        return v
    try:
        return float(v)
    except Exception:
        return str(v)


def node_to_dict(nd):
    """`Node` ⇒ **纯 JSON 树**（`Node.__slots__ = ('op','args')`）。

    ★ 2026-09-17（用户之问："家里 pull 库是空的，怎么自动识别并重跑出 facs/曲线？"）：
      `state.pkl` **不进 git** ⇒ 换机器就没有"入库 Node"这个权威口径 ✗
      ⇒ 把它导出成**结构**（而不是只存公式文本）：
        文本重解析走 `parse_expr`，会被 `LLM_MAX_SIZE` 尺寸上限**静默判 None**（全A F01 就中过招 ✗）；
        结构则**精确重建**、不受任何生成侧护栏影响 ✓
    """
    return {'op': str(nd.op), 'args': [node_to_dict(a) if isinstance(a, Node) else _jscalar(a)
                                       for a in (nd.args or [])]}


def node_from_dict(d):
    """JSON 树 ⇒ `Node`（**精确重建**；与 `node_to_dict` 往返恒等 ✓ 见 `tools/_test_registry.py`）"""
    return Node(d['op'], [node_from_dict(a) if isinstance(a, dict) else a
                          for a in (d.get('args') or [])])




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












# ★★★★ 2026-09-17（用户："我发现又入库了一个新因子，但**找不到什么时候入库的、入的哪个库**"
#   ⇒ 要求看板池状态区加一张"新入库日志"卡片）：
#   入库事件日志（**append-only JSONL**，进 git ⇒ 换机器也看得到）——
#   · 一行 = 一次入库：时间 / 池 / 代数 / 编号 / 公式 / 家族 / 一句话
#   · 由**引擎入库那一刻**写（真实时间 ✓）；历史条目由
#     `tools/backfill_library_entries.py` **回填**（时间取自该代引擎日志的 mtime，
#     并标 `tsSource` —— 推算出来的时间**必须标明来路**，不许冒充"记录时间" ✗）








# ===================== 4. L1 批量 IC =====================
def trim_cache(cache, cap):
    """子树缓存容量控制: 条目超过 cap 时淘汰最早插入的键(dict 保插入序)。
    子树缓存只是加速(命中失败会重算), 淘汰不影响正确性。"""
    if cache is not None and len(cache) > cap:
        for k in list(cache.keys())[:len(cache) - cap]:
            cache.pop(k, None)




def _cache_real_mb(cache):
    """整个缓存的**真实**占用 MB（共用一份 `seen` ⇒ 多份视图共享的底座只计一次 ✓）。"""
    seen = set()
    return sum(_real_mb(v, seen) for v in cache.values())


def trim_cache_mb(cache, max_mb):
    """★★★★★ 2026-09-21（治本）：按**真实字节**裁缓存 ⇒ 内存有**硬上限** ✓

    ★ 为什么必须按字节（实测见 `set_mem_budget` 的注释 ✓）：
      `trim_cache` 只管"条数"✗，而单条大小随**池宽**变化 ——
      1000 池的 L1 子面板是 2094 日 × 2818 股 ⇒ 单条 ≈ **47 MB** ✗
      ⇒ 400 条 ≈ **18.8 GB** ✗（实测这一代的私有内存峰值 14.6 GB ✓ 工作集 16.6 GB ✓）
      ⇒ 三个池并行就把 47.9 GB 的机器压到只剩 1.7 GB ⇒ 换页 ⇒ 单代 110~172 分钟 ✗
    ★★ 第二刀（2026-09-21）：**"按字节"还不够 —— 要按"真实钉住的字节"** ✗
      见 `_real_mb`：只数视图自己的 nbytes ⇒ 账实不符 ⇒ 预算**形同虚设** ✗
    ★ 淘汰策略：dict 保插入序 ⇒ 从**最旧**开始丢 ✓（缓存只是加速、丢了会重算 ⇒ 不影响正确性 ✓）
    ★ 返回：裁完之后的**真实**总 MB（便于日志/守门核验 ✓）
    """
    if cache is None:
        return 0.0
    try:
        tot = _cache_real_mb(cache)
        if tot <= max_mb:
            return tot
        n0 = len(cache)
        for k in list(cache.keys()):
            if tot <= max_mb:
                break
            cache.pop(k, None)
            # ⚠ 必须**重算**而不是"减掉刚才那份" ✗ —— 底座可能被**多份视图共享** ✓
            #   （减掉就会重复扣，把预算算成"早就达标"⇒ 又会提前停手 ✗）
            tot = _cache_real_mb(cache)
        if n0 > len(cache):
            print('  [内存预算] 缓存裁至 %.0f MB（丢最旧 %d 个 ✓ 口径=**含视图底座**的真实占用 ✓）'
                  % (tot, n0 - len(cache)), flush=True)
        return max(tot, 0.0)
    except Exception:                                        # noqa: BLE001
        return 0.0                                           # 裁不动也不能影响主流程 ✓


# rank_rows 已移至 loop_metrics.py（单一事实源, 2026-09-11）; 顶部 import 引入,
# 故本模块内 `rank_rows(...)` 与外部的 `loop_engine.rank_rows` 接口保持不变。


def factor_stability(V, dates=None, start=START, fwd=None):
    """因子稳定性 = 相邻调仓日截面rank的相关性(均值)
    稳定性低 -> 每次调仓Top组大换血 -> 换手高 -> 费后被成本吃光
    这是 L1 必须看、只看IC会漏掉的关键指标

    ★★ 2026-09-21（前置改造）：`fwd` 原来是 `fwd=FWD` —— **默认值在 `def` 那一刻就固化了** ✗
      （Python 的经典坑 ✓）⇒ 就算 `set_fwd(20)` 改了模块全局，这个函数**还是拿 5** ✗
      ⇒ 改成 `fwd=None` + 函数内取**当前**全局 ✓（调用方传值时仍以显式值为准 ✓）
    """
    fwd = FWD if fwd is None else fwd
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
def _critic_review_prev(_prev_pool_map, args, cfg, prev_l1, prev_l2):
    """P0-2 纯提取自 `run()`（逐字搬运，语义不变）。

    原段落: B角: 先审查上一代, 再据此定本代搜索策略
    """
    import loop_critic as critic
    # ★★★★ 2026-09-19 修真 BUG（用户报"上证50怎么崩了" ⇒ 实测 `pool_50_gen8_err.log` 640B traceback）：
    #   `diag` / `reasons` / `r` **只在"有上一代"的分支里被绑定** ✗，而 **首代会走 else** ⇒
    #   下面 return 引用未绑定变量 ⇒ `UnboundLocalError: cannot access local variable 'diag'` ✗✗
    #   ⇒ 引擎**起来即死**（500 多字节日志 + rc=1）⇒ 看板显示"启动即崩" ✗
    #   ⚠ 什么时候会走首代：`prev_l1` 为空 ⇒ 该池 **bank/种子为空**（如 `50` 池 bank=0 ✓）
    #   ★ 溯源：v0.17.0「P0-2 拆 run()」把这段内联代码抽成函数时，**新增了 return 这三个值** ✗；
    #     而原内联版里它们只在**后面**被重新赋值（`critic.diagnose(...)` / `critic.suggest(...)`）
    #     ⇒ 老代码"不崩"只是因为没人当场读它 ✗ ⇒ **抽函数才暴露**（那次提交标题写着"顺带修潜伏
    #     NameError"，结果是引入了这一个 ✗）
    #   ⇒ 修法：给**与"有上一代"分支同形**的默认值（空 dict / 空 list / 空串）✓
    #     下游 `_agg_style_diag(..., r, ...)` 的 `r` 参数其实**未被使用**（死参）✓，
    #     `diag` / `reasons` 也会在 L2935/L2939 被重新赋值 ⇒ **语义不变** ✓
    diag, reasons, r = {}, [], ''
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
    return (cfg, critic, diag, r, reasons)




def _load_fail_lib(args, cfg, fail_lib):
    """P0-2 纯提取自 `run()`（逐字搬运，语义不变）。

    原段落: 失败模式库: 载入后按滚动窗口算出本代应排除的'坏骨架'
    """
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
    return bad


def _rand_explore(bank, cfg, prev_l1):
    """P0-2 纯提取自 `run()`（逐字搬运，语义不变）。

    原段落: 随机探索: 数据驱动特征分布引导(中金"随机探索15%=数据驱动分布, 防局部最优")
    """
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
    return cfg_r


def _gen_candidates(args, cfg, seeds):
    """P0-2 纯提取自 `run()`（逐字搬运，语义不变）。

    原段落: 生成候选(按B角给的五维配比)
    """
    m = cfg['mix']
    cut = [m[0], m[0] + m[1], m[0] + m[1] + m[2], m[0] + m[1] + m[2] + m[3]]
    # ★ 亲本选择策略（2026-09-14, §1.3-C）—— `uniform` 是默认 = **现状行为不变**
    _psel = getattr(args, 'parent_sel', None) or 'uniform'
    if _psel not in PARENT_SEL_MODES:
        print(f"  [亲本] [!] 未知 --parent_sel={_psel!r} -> 回退 uniform（可选: "
              f"{'/'.join(PARENT_SEL_MODES)}）")
        _psel = 'uniform'
    _ptop = float(getattr(args, 'parent_top_pct', 0.30) or 0.30)
    if _psel != 'uniform':
        print(f"  [亲本] 策略={_psel}"
              + (f"（top {_ptop:.0%} 保底 + 余量随机；种子池 {len(seeds)} 个"
                 f" ⇒ top 段 {max(1, int(len(seeds) * _ptop))} 个）"
                 if _psel == 'top_percent_plus_random' else "（纯取第 1 名）")
              + " —— ⚠ 与 `uniform` 是**不同搜索行为**，跨代对比时勿混用")
    return (_psel, _ptop, cut, m)


def _run_l1(U, base, fwd_ret):
    """P0-2 纯提取自 `run()`（逐字搬运，语义不变）。

    原段落: L1 批量 IC(★分批处理 + 子面板 + 跨批LRU)
    """
    Bsub = base['B_sub']
    Usub = U[np.ix_(L1_ROWS, L1_COLS)]
    if L1_POOL_MASK is not None:
        # ★池内挖掘(§8.19): L1 的 IC = **池内 IC**。这一步是"三池并行"起作用的核心 ——
        #   目标函数里不再有全A 的小盘/低流动性溢价, 风格暴露因子在 L1 就挣不到分。
        Usub = Usub & L1_POOL_MASK
    Rsub = fwd_ret[np.ix_(L1_ROWS, L1_COLS)]
    print(f"L1 子面板 {len(L1_ROWS)}日 x {len(L1_COLS)}股 "
          f"(全量 {U.shape[0]}x{U.shape[1]}) -> 数据量约 1/{U.size/max(Usub.size,1):.0f}")
    return (Bsub, Rsub, Usub)


def _apply_fam_quota(args, l1):
    """P0-2 纯提取自 `run()`（逐字搬运，语义不变）。

    原段落: 结构族配额(QuantaAlpha 冗余检测移植, gen31)
    """
    fam_blocked = 0
    if args.fam_quota > 0 and len(l1):
        n_pre = len(l1)
        l1, nfam, n_blocked = fam_quota_rows(l1, quota=args.fam_quota,
                                             use_sole=args.fam_sole)
        fam_blocked = n_blocked
        if n_blocked:
            print(f"  [族配额] 模板族 {nfam} 个(含单叶变换维度={'开' if args.fam_sole else '关'})"
                  f" -> 结构冗余拦 {n_blocked}/{n_pre} (剩 {len(l1)}, 每族<={args.fam_quota})")
    return (fam_blocked, l1)




def _jury_deep_review(args, l1, loop_llm, rng):
    """P0-2 纯提取自 `run()`（逐字搬运，语义不变）。

    原段落: 中金【审查】环节: B角候选级 LLM 精判(硬滤后抽5深判, 与生成侧隔离防自证)
    """
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
    return (jury_lines, l1, n_jury_kill, n_jury_rev)


def _run_l2(_min_pool_calmar, _min_sharpe, _pool_gate_mode, _pool_gate_on, _pool_gate_or_all, _pool_obs, _pools, args, cols, dates, l1):
    """P0-2 纯提取自 `run()`（逐字搬运，语义不变）。

    原段落: L2 费后精筛
    """
    top = l1.head(args.l2)
    _t_l2 = time.time()
    print(f"\nL2 费后精筛 {len(top)} 个 ...")
    # 池成员 PIT 掩码(2026-09-12, --pool_obs; 见 docs/log/2026-09.md §8.9 B+B′)
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
                  f"用时 {time.time() - _t_pool:.0f}s) -> {_P.POOL_OBS}; {_gate_txt}")
        except Exception as e:
            print(f"  [池指标] [!] 掩码构建失败 -> 本代跳过池指标: {type(e).__name__}: {e}")
            POOL_M = {}
    # ⚠ 2026-09-15 修：原先 return 里带 `_tg`/`e`，两者都**不是本函数产生的** ——
    #   `e` 是 P0-2 提取时凭空补的形参（函数体从不读）；`_tg` 只在 `if _pool_obs:` 内绑定
    #   ⇒ 关掉 `--pool_obs` 时会 UnboundLocal。两者都已从签名/返回值移除 ✓
    #   `_tg` 在 `run()` 里本就由 `for _tg, _M in POOL_M.items()` 重新绑定，不依赖本返回值。
    return (POOL_M, _lp, _t_l2, top)




def _critic_diagnose(args, fam_blocked, l1, pool_rows, res, seg_ok_list):
    """P0-2 纯提取自 `run()`（逐字搬运，语义不变）。

    原段落: B角: 诊断本代 + 给出下一代策略 + 写日志
    """
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
    return (critic, diag, res_c)


def _agg_style_diag(cfg, critic, diag, l1, obs_df, r, res):
    """P0-2 纯提取自 `run()`（逐字搬运，语义不变）。

    原段落: 风格暴露诊断聚合(2026-09-11, --style_obs): 落盘已在 L1 求值后完成, 此处只做分组聚合
    """
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
    critic.report(diag, next_cfg, reasons, _P.JOURNAL)
    print(f"诊断已写入 {_P.JOURNAL}")
    return (next_cfg, reasons)


def _log_llm_hint(args, jury_lines, llm_hyp, llm_on, n_jury_kill, n_jury_rev, n_llm_call, n_llm_hit, n_llm_parse):
    """P0-2 纯提取自 `run()`（逐字搬运，语义不变）。

    原段落: 生成侧 LLM 引导留痕(独立引用体小节, 与 ai_review 块同风格)
    """
    if llm_on and n_llm_call:
        llm_journal_block(args.gen, n_llm_call, n_llm_parse, n_llm_hit,
                          llm_hyp, _P.JOURNAL)
        print(f"LLM 引导小结已写入 {_P.JOURNAL}")
    if n_jury_rev:
        llm_jury_block(args.gen, n_jury_rev, n_jury_kill, jury_lines, _P.JOURNAL)
        print(f"LLM 候选审查小结已写入 {_P.JOURNAL}")


def _critic_llm_review(_v, args, critic, diag, l1, next_cfg, reasons, res_c):
    """P0-2 纯提取自 `run()`（逐字搬运，语义不变）。

    原段落: B角 LLM 审查(DeepSeek, --ai_critic auto/on/off, 默认auto=有key即启用)
    """
    ai = getattr(args, 'ai_critic', 'auto')
    if ai != 'off':
        _airv = critic.ai_review(diag, l1, res_c if len(res_c) else None, args.gen,
                                 _P.JOURNAL, reasons=reasons, sug=next_cfg, force=(ai == 'on'))
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
    return _v




def _run_prepare(args):
    """准备阶段：初始化 + 数据准备 + 载入上一代 state + 审查/黑名单/失败库/随机探索 -> ctx"""
    t0 = time.time()
    rng = random.Random(args.seed)
    np.random.seed(args.seed)
    # ★ 无条件 import loop_llm：下方 `_jury_deep_review`（L2471）无论 --llm_guide 是否 off 都要用，
    #   否则 --llm_guide=off 时 `loop_llm` 未绑定 -> UnboundLocalError（2026-09-26 基线跑暴露 ✓）
    import loop_llm
    # ---- LLM 对话录音: 本代 A角/B角 与 DeepSeek 的全部往返落盘(ai_test, gitignore) ----
    # automation 无人值守, 人看不到实时 LLM 对话; 录音文件供跑代后随时回溯/本窗口转述。
    try:
        _conv_dir = os.path.join(os.path.dirname(HERE), 'ai_test', 'loop_conv')
        loop_llm.set_conv_path(os.path.join(_conv_dir, 'gen%02dC_conv.md' % args.gen))
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
    # ★★ 外部池库对照集（2026-09-14, `loop_todo §1.8`）—— **只读，绝不写回 state / 因子库**。
    #   为什么需要：`--decorr`/`--dup_ex_corr` 的对照集原本只是"**本轨道自己的 bank**"
    #   ⇒ 跑全A 时它不知道池库挖到了什么 ⇒ 把同一批重挖一遍（实测收益流 |相关| 中位 0.767、>0.7 占 82%）。
    #   ★ 与 `bank`/`bank_ex` 的区别：那两个是**本轨道的产出**（会持久化 + 进 `docs/factor_library*.md`）；
    #     这两个只是"**告诉我这些已经挖过了**"的对照来源。
    bank_ext, bank_ex_ext = [], {}
    _inject_tags = [x.strip() for x in
                    str(getattr(args, 'inject_pools', '') or '').split(',') if x.strip()]
    frozen = []                # FSA冻结骨架列表(中金: 超15%被禁止复用)
    # ★ 2026-09-17：冻结**记账**（{骨架: {'cnt': 第几次, 'left': 剩余代数, 'cool': 冷却计数}}）
    #   —— 有它才能做"2→4→8 代封顶 + 冷却期遗忘"；`frozen` 仍是骨架字符串列表（口径不变 ✓）
    fsa_frz = {}
    fail_lib = {}              # 失败模式库(骨架级成败滚动统计, 中金: 生成阶段排除)
    cfg = dict(DEFAULT_CFG)
    # ★ n_tested 的基准必须在**写盘之前**取好(2026-09-12 修 —— 这是一个崩在整代末尾的隐蔽 bug):
    #   原写法 `n_tested=st.get('n_tested',0)+len(cands) if os.path.exists(_P.STATE) else len(cands)`
    #   的三元条件是在 `with open(_P.STATE,'wb')` **之后**求值的 —— 而那一步已经把文件创建出来了
    #   ⇒ 条件**恒为 True**; 全新轨迹(无既有 state)时 `st` 从未绑定 ⇒ UnboundLocalError
    #   ⇒ 崩在**整代最后一行**(30 分钟计算白做, 且 state 被 0 字节覆盖)。
    #   实录: `--mine_pool=300` 首次全新轨迹即崩(loop_state_300.pkl 被创建为 0 字节)。
    n_tested_prev = 0
    # ★ 上一代的「池口径」传感器数据（2026-09-14, §1.1 修法②）：代首要**重审上一代**，
    #   而池结果不在 `last_l2` 里（那是全A 口径的表）⇒ 必须随 state 一起存。
    #   ⚠ 无 state 时必须能保持为 None（否则 `st` 未绑定 -> UnboundLocalError，
    #     这正是 §8.23 那个"崩在整代最后一行"的同类坑）。
    _prev_pool_map = None
    if os.path.exists(_P.STATE):
        with open(_P.STATE, 'rb') as f:
            # ★★★★★ 2026-09-25：走**归一** Unpickler —— 把历史上误存的 `loop_engine.Node`
            #   也还原成本模块的 `Node`（详见**文件末尾** `__main__` 块的注册处 / `_StateUnpickler`）✓
            #   ⚠ 不加这一句：`bank`/`seeds`/`last_l1` 里的那批"第二份"Node 会让
            #     `skeleton`/`collect`/`key` 全部失效（骨架去重与 FSA 对它们形同虚设）✗
            st = _StateUnpickler(f).load()
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
        # ★ 2026-09-17：冻结记账（老 state 没有这个键 ⇒ 空字典，`_fsa_stats` 会按"第 1 次"接管 ✓）
        fsa_frz = st.get('fsa_frz') or {}
        fail_lib = st.get('fail_lib', {})  # 失败模式库
        cfg = _clean_cfg(st.get('cfg', cfg))     # ★ 洗掉历史脏值（None 权重）—— 见 `_clean_cfg`
        _prev_pool_map = st.get('last_pool_map', None)
        print(f"载入上一代种子 {len(seeds)} 个, 入库因子 {len(bank)} 个, "
              f"冻结骨架 {len(frozen)} 个, 失败库 {len(fail_lib)} 条, "
              f"已测 {st.get('n_tested', 0)} 个候选")
        # ★★★ 外部池库注入对照集（2026-09-14, `loop_todo §1.8`）----
        #   问题：`--decorr` / `--dup_ex_corr` 的对照集是**各自轨道自己的 bank**
        #   ⇒ 跑全A 时它**根本不知道池库挖到了什么** ⇒ 会把同一批重挖一遍。
        #   实测（`tools/check_pool_vs_allA.py`）：池因子 vs 全A 库(41) 的收益流最大 |相关|
        #   **中位 0.767**，>0.7 占 **82%**，而 `--dup_ex_corr=0.90` 只挡得住 18%
        #   ⇒ **不做注入 ≈ 把 82% 的算力花在重挖上**。
        #   ★ 语义：外部池库只能"**告诉我这些已经挖过了**"，**不能算我的产出**
        #     ⇒ 单独存 `bank_ext`/`bank_ex_ext`，**绝不写回自己的 state / 因子库** ✓
        if _inject_tags:
            _n_bi, _n_be, _srcs = 0, 0, []
            for _tp in _inject_tags:
                _sp = os.path.join(HERE, 'loop_state{}.pkl'.format(
                    '' if _tp == 'all' else '_' + _tp))
                if not os.path.exists(_sp):
                    print(f"  [外部库] [!] 池 {_tp} 无 state（{os.path.basename(_sp)}），跳过")
                    continue
                try:
                    with open(_sp, 'rb') as _f:
                        # ★ 2026-09-25：同样走归一 Unpickler（别的池 state 里也可能有"第二份" Node）✓
                        _stp = _StateUnpickler(_f).load()
                except Exception as _e:
                    print(f"  [外部库] [!] 池 {_tp} state 读取失败（不影响主流程）: "
                          f"{type(_e).__name__}: {_e}")
                    continue
                _bp = _stp.get('bank', []) or []
                _bep = _stp.get('bank_ex', {}) or {}
                if not isinstance(_bep, dict):
                    _bep = {}
                bank_ext.extend(_bp)
                for _k, _v in _bep.items():
                    if _k not in bank_ex:            # 自己已有的优先
                        bank_ex_ext.setdefault(_k, _v)
                _n_bi += len(_bp)
                _n_be += len(_bep)
                _srcs.append('{}={}(收益流{})'.format(_tp, len(_bp), len(_bep)))
            print(f"  [外部库] 已注入对照集: {', '.join(_srcs) if _srcs else '（无）'}"
                  f" ⇒ 对照集 node {len(bank)}+{_n_bi}={len(bank)+len(bank_ext)} 个, "
                  f"收益流 {len(bank_ex)}+{len(bank_ex_ext)}={len(bank_ex)+len(bank_ex_ext)} 条")
            print("  [外部库] ⚠ 仅作**对照**；**不会**写回本轨道的 state / 因子库 "
                  "（外部池库不算本轨道的产出）")

    # ---- B角: 先审查上一代, 再据此定本代搜索策略 ----
    cfg, critic, diag, r, reasons = _critic_review_prev(_prev_pool_map, args, cfg, prev_l1, prev_l2)
    # ---- 结构族黑名单(QuantaAlpha 正交思想, gen31): 上代 L1 霸榜模板族 ----
    # 上代同模板族(叶子身份无关指纹)占比 >= FAM_BLOCK_THR -> 本代生成端禁产(硬闸换血);
    # top2 模板文本另注入 A角 LLM 提示词(软约束)。根治"同族霸榜 -> 0 通过"空转。
    f = None  # ★ 死透传：_build_fam_blacklist 内覆盖 f；避免「等号两边同名（右边先读）」的静态隐患
    block_fams, f, fam_black_txt, nd = _build_fam_blacklist(args, cfg, critic, f, frozen, prev_l1, seeds)

    # ---- 失败模式库: 载入后按滚动窗口算出本代应排除的'坏骨架' ----
    bad = _load_fail_lib(args, cfg, fail_lib)

    # ---- 随机探索: 数据驱动特征分布引导(中金"随机探索15%=数据驱动分布, 防局部最优") ----
    # 证据分布 = 历代入库因子 + 上一代 L1 通过候选 的叶子/算子族频率;
    # 随机位按该分布抽样(探索有苗头方向的新组合), 无证据时退化为 cfg 权重(均匀)。
    cfg_r = _rand_explore(bank, cfg, prev_l1)


    return dict(
        t0=t0, rng=rng, base=base, B=B, dates=dates, cols=cols, close=close,
        T=T, S=S, U=U, fwd_ret=fwd_ret, seeds=seeds, fsa=fsa,
        prev_l1=prev_l1, prev_l2=prev_l2, bank=bank, bank_ex=bank_ex,
        bank_ext=bank_ext, bank_ex_ext=bank_ex_ext, frozen=frozen,
        fsa_frz=fsa_frz, fail_lib=fail_lib, cfg=cfg,
        _prev_pool_map=_prev_pool_map, n_tested_prev=n_tested_prev,
        critic=critic, diag=diag, r=r, reasons=reasons,
        block_fams=block_fams, f=f, fam_black_txt=fam_black_txt, nd=nd,
        bad=bad, cfg_r=cfg_r,
        loop_llm=loop_llm)


def _run_gen(ctx, args):
    """生成候选（按 B角五维配比 + LLM 引导 + 守卫链）-> 写回 ctx；gen_only 返回 True"""
    cfg = ctx['cfg']
    seeds = ctx['seeds']
    loop_llm = ctx['loop_llm']
    rng = ctx['rng']
    cfg_r = ctx['cfg_r']
    bank = ctx['bank']
    frozen = ctx['frozen']
    fail_lib = ctx['fail_lib']
    fam_black_txt = ctx['fam_black_txt']
    bad = ctx['bad']
    block_fams = ctx['block_fams']
    t0 = ctx['t0']

    # ---- 生成候选(按B角给的五维配比) ----
    # ★gen13修复: cut为累积上界, 判重/分支原来写成 cut[i] 相加 -> 数值>1恒真,
    # 使 r<cut0+cut1+cut2 永远成立: guided(引导族)与rand(纯随机)从不会被执行,
    # 代代只在seeds内打转 -> 重复爆炸。 现改回 r<cut[2](seed三操作) / r<cut[3](引导) / 否则随机。
    _psel, _ptop, cut, m = _gen_candidates(args, cfg, seeds)
    # ---- 生成侧 LLM 引导(A角子代理, 中金"生成预算~20%语义引导"): ----
    # 引导位 r∈[cut2,cut3) 的候选来源 = LLM 解析池; 池空且调用未超限则按需补一次;
    # 无 key/超时/解析失败/超限 -> 回退本地 guided_expr。LLM 候选与规则候选走
    # 同一条守卫链(跨量纲/失败库/FSA/判重), 不产生旁路。
    llm_on = (getattr(args, 'llm_guide', 'auto') != 'off')
    llm_pool, llm_hyp = [], ''
    n_llm_call = n_llm_parse = n_llm_hit = 0
    if llm_on:
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
                s = pick_parent(rng, seeds, _psel, _ptop)     # ★ §1.3-C（原 rng.choice(seeds)）
                node = clone(s)
                q = rng.random()
                den = max(m[0] + m[1] + m[2], 1e-9)
                if q < m[0] / den:
                    node = mutate(node, rng)
                elif q < (m[0] + m[1]) / den:
                    node = crossover(node, clone(pick_parent(rng, seeds, _psel, _ptop)), rng)
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
        return True


    ctx['cands'] = cands
    ctx['llm_on'] = llm_on
    ctx['llm_pool'] = llm_pool
    ctx['llm_hyp'] = llm_hyp
    ctx['n_llm_call'] = n_llm_call
    ctx['n_llm_parse'] = n_llm_parse
    ctx['n_llm_hit'] = n_llm_hit
    return False


def _l1_filter(l1, Bsub, B, bank, bank_ext, args, _reuse_v, _min_mono, _score_mode):
    """L1 过滤：ic/stab 门槛 + 形状门槛 + 去相关 + 评分 + 近重复去重 -> 返回 l1（空则 None）"""
    cache2 = {}
    if not len(l1):
        print("L1 无候选通过, 退出")
        return None
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
            return None
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
        # ★ 2026-09-14（§1.8）：对照集 = 自己的 bank **+ 外部池库**（`bank_ext`，只读注入）
        #   不注入的话，跑全A 时这一层"看不见池库" ⇒ 重挖。
        for bi, bnd in enumerate(bank + bank_ext):
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
            trim_cache_mb(cache2, CACHE2_MB)           # ★ 治本: 字节上限 ✓
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
        trim_cache_mb(cache2, CACHE2_MB)               # ★ 治本: 字节上限 ✓
    print(f"\nL1 通过 {len(l1)} 个, 取Top{TOPN}近重复去重(|corr|>{args.dedup_corr:g})"
          f"拦 {n_dup} -> 剩 {len(dedup)} 个")
    print(f"  [计时] 近重复去重 用时 {time.time() - _t_dd:.0f}s "
          f"(复用 L1 值 {n_hit2}/{TOPN} 个)", flush=True)
    VCACHE.clear()                                      # 去相关/去重用完即释放(防与 L2 叠加占内存)
    _VREUSE_MB[0] = 0.0
    l1 = pd.DataFrame(dedup) if dedup else l1.head(TOPN)
    print(l1[['expr', 'ic', 'ic_ir', 'stab']].head(15).round(4).to_string(index=False))
    return l1



def _l1_eval(cands, Bsub, Rsub, Usub, args, fail_lib, need_shape, _style_obs,
             _reuse_v, STYLE_S, R_SHAPE, Usub_s, Rsub_s_n):
    """L1 批量求值 + 形状量/风格暴露 + 风格观测落盘 + 失败库记录 -> (l1, obs_df)"""
    stats = []
    BATCH = args.batch
    # ★★★★★ 2026-09-21（治本）：批次大小**按字节自适应** ✗ —— 固定 40 个候选时，
    #   单条面板的体积随**池宽**变化（1000 池子面板 2094×2818 ≈ 47 MB ⇒ 一批 ≈ 1.9 GB ✗）
    #   ⇒ 取"子面板里任一字段"的真实 dtype/形状算单条 MB，再把批大小压到 `BATCH_MB` 以内 ✓
    try:
        _k0 = next(iter(Bsub))
        _a0 = np.asarray(Bsub[_k0])
        _per_mb = float(_a0.size) * float(_a0.dtype.itemsize) / 1048576.0
        if _per_mb > 0:
            _cap = int(max(4, BATCH_MB / _per_mb))
            if BATCH > _cap:
                print('  [内存预算] L1 批 %d → %d（单条 %.1f MB × 批 ≤ %.0f MB ✓ 治本: 宽池不再一批吃 2 GB ✗）'
                      % (BATCH, _cap, _per_mb, BATCH_MB), flush=True)
                BATCH = _cap
    except Exception as _e_b:                                # noqa: BLE001
        print('  [内存预算] 批次自适应跳过（%s: %s）⇒ 沿用 %d'
              % (type(_e_b).__name__, str(_e_b)[:60], BATCH), flush=True)
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
            # ★★★★★ 2026-09-21（治本·第二步）：**批内也裁** ✗
            #   原来只在"**每批结束**"裁一次（下面 `trim_cache(_LRU, LRU_MAX)` ✓）
            #   ⇒ 一批之内 `_LRU` 能一路涨到第一个峰值（实测第一批就顶到 8.9 GB ✗，
            #     改之前更是 12.5~14.8 GB 反复 ✗）⇒ 每 8 个候选就裁一次 ✓
            #   代价：`trim_cache_mb` 只是把 `nbytes` 加起来（O(条数) ✓）⇒ 可忽略 ✓
            if i and (i % 8) == 0:
                trim_cache_mb(_LRU, LRU_MB)
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
        trim_cache_mb(_LRU, LRU_MB)                    # ★ 治本: 字节上限(池越宽单条越大 ✗)
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
            need_h = (not os.path.exists(_P.STYLE_OBS)) or os.path.getsize(_P.STYLE_OBS) == 0
            obs_df.to_csv(_P.STYLE_OBS, index=False, mode='a', header=need_h,
                          encoding='utf-8-sig')
            print(f"已存 {_P.STYLE_OBS} (追加, 本代 {len(obs_df)} 条候选)")
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

    return l1, obs_df


def _run_l1_phase(ctx, args):
    """L1 批量 IC + 过滤（形状/去相关/去重/族配额/FSA/jury）-> 写回 ctx；早退返回 True"""
    U = ctx['U']
    base = ctx['base']
    fwd_ret = ctx['fwd_ret']
    B = ctx['B']
    cands = ctx['cands']
    fail_lib = ctx['fail_lib']
    frozen = ctx['frozen']
    fsa = ctx['fsa']
    rng = ctx['rng']
    loop_llm = ctx['loop_llm']
    bank = ctx['bank']
    bank_ext = ctx['bank_ext']
    nd = ctx['nd']
    r = ctx['r']
    fsa_frz = ctx['fsa_frz']

    Bsub, Rsub, Usub = _run_l1(U, base, fwd_ret)
    # ---- 形状量(十档单调性)所需的调仓日抽样视图: 只算一次 ----
    # rank_rows 逐行独立 => rank_rows(F)[::FWD] ≡ rank_rows(F[::FWD])，抽样与不抽样等价(更快)
    Rsub_s, Usub_s = Rsub[::FWD], Usub[::FWD]
    _min_mono = float(getattr(args, 'min_mono', 0.0) or 0.0)      # 缺字段=关闭(默认行为)
    _score_mode = getattr(args, 'score_mode', 'old') or 'old'
    _style_obs = bool(getattr(args, 'style_obs', False))
    _shape_neutral = bool(getattr(args, 'shape_neutral', 0))   # 形状量用风格中性收益(§8.5.1 行动①)
    # 剥风格入库判据(2026-09-12, 见 docs/log/2026-09.md §8.13): L2 记录(可选门槛)
    # 把因子对 lncap+lnamt 秩中性化后重跑回测 —— 判"超额是否只是市值/成交额风格暴露"。
    _strip_style = bool(getattr(args, 'strip_style', False))
    # 池内指标(2026-09-12, 见 docs/log/2026-09.md §8.9 B+B′): L2 在**池内**重跑回测,
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
    # ★ 2026-09-22（v1.21.29 · (乙)）：**副口径**的剥风格记录（按口径分别落文档 ✓
    #   否则 20 日入选的因子会在文档里写上 5 日的剥风格数字 ✗ —— 那是另一个口径的结论 ✓）
    _strip2_by_expr = {}
    # ★ 副口径入选者（`{expr: 副口径值}`）—— 供 `_save_state` 分口径写文档 ✓
    _hzn2_by_expr = {}
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
                  f"{Rsub_s.shape[0]}期) -> {_P.STYLE_OBS}")
        if _strip_style:
            print(f"  [剥风格] L2 将记录剥 lncap+lnamt 后的 IC/超额/Calmar -> {_P.STRIP_OBS}"
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
    l1, obs_df = _l1_eval(cands, Bsub, Rsub, Usub, args, fail_lib, need_shape,
                           _style_obs, _reuse_v, STYLE_S, R_SHAPE, Usub_s, Rsub_s_n)
    l1 = _l1_filter(l1, Bsub, B, bank, bank_ext, args, _reuse_v, _min_mono, _score_mode)
    if l1 is None:
        return True
    # ---- 结构族配额(QuantaAlpha 冗余检测移植, gen31) ----
    # 数值去重(|corr|>dedup_corr) 只拦"数值近重复"; FSA 冻结只拦"完整串复用"。同族"外层模板
    # 固定、内层微调"的候选(score 各异、公共结构巨大)会继续挤满 L2 名额与下代种子池, 费后全灭 ->
    # 每模板族最多放 fam_quota 条进 L2/种子池(保结构多样性), FSA/下代种子池因此天然跨族。
    # gen51: 族指纹增补"单叶变换"维度(floor_sole_leaf) -> max(<某叶单目变换>, <地板>) 的
    # "同叶不同壳"代理候选归为同族, 由配额拦重复(防 F23 型"leverage 套壳+地板"反复重发现)。
    fam_blocked, l1 = _apply_fam_quota(args, l1)

    # ---- FSA 骨架统计(对齐中金: 抽象因子结构/剥离窗口参数) ----
    # 观察样本 = 本代L1通过者 + 前50候选; 统计对象 = 非叶子结构骨架(剥掉窗口数字)
    # ★★★★ 2026-09-19 修真 BUG（同 v1.21.6/1.21.7 那一类，第三个 ✗ —— 抢读崩溃日志才拿到 traceback ✗）：
    #     File loop_engine.py, line 2679, in run
    #         frozen, nd, r, s = _fsa_stats(args, cands, frozen, fsa, l1, nd, r, s, fsa_frz)
    #     UnboundLocalError: cannot access local variable 's'
    #   ⇒ **等号两边同名**：右边要读的 `s` 此刻还没绑定，左边才刚给它赋值 ✗
    #   ★ 为什么首代才会塌：`s` 唯一的"真"赋值在 `s = pick_parent(rng, seeds, …)`，
    #     而那一句在 `if seeds and r < cut[2]:` 里 ⇒ **首代没有种子（50 池 bank=0）⇒ 走不到** ✗
    #     （另一处 `for v, s in zip(...)` 是**推导式自己的作用域**，绑不到外面的 s ✗）
    #   （本处与前一处的修复合并在 **v1.21.7** 一起发布 ✓）
    #   ★ 已核实这两处 `r`/`s` 都是**死透传**：`_fsa_stats` 内部只把 `s` 当自己的循环变量、
    #     最后原样吐回 ✓；`_save_state` 里的 `s` 也是**局部**（函数内自己 `s = skeleton(nd)`）⇒
    #     传进去的参数**从来没被读过** ✓ ⇒ 给安全初值即可，**语义零变化** ✓
    #   （`r` 不必管：它在 L2163 由 `_critic_review_prev` **无条件**赋值 ✓；只有 `s` 会漏 ✗）
    s = None                           # 首代没有"亲本节点"这个遗留值 ⇒ None（下游不读 ✓）
    frozen, nd, r, s = _fsa_stats(args, cands, frozen, fsa, l1, nd, r, s, fsa_frz)

    # ---- 中金【审查】环节: B角候选级 LLM 精判(硬滤后抽5深判, 与生成侧隔离防自证) ----
    # 硬规则已在上方先滤(IC/稳定/去相关/去重/跨量纲/FSA) -> 剩余候选随机抽 --jury_n 个,
    # 由审查侧 Sub-agent LLM(loop_llm.jury_verdict)判经济含义/过拟合边界/已知族嫌疑,
    # verdict=KILL 者剔除出 L2 费后回测; 无 key/调用失败一律放行不误杀(无人值守铁律)。
    jury_lines, l1, n_jury_kill, n_jury_rev = _jury_deep_review(args, l1, loop_llm, rng)


    ctx['Bsub'] = Bsub
    ctx['Rsub'] = Rsub
    ctx['Usub'] = Usub
    ctx['STYLE_FULL'] = STYLE_FULL
    ctx['l1'] = l1
    ctx['obs_df'] = obs_df
    ctx['fam_blocked'] = fam_blocked
    ctx['jury_lines'] = jury_lines
    ctx['n_jury_kill'] = n_jury_kill
    ctx['n_jury_rev'] = n_jury_rev
    ctx['_min_pool_calmar'] = _min_pool_calmar
    ctx['_min_sharpe'] = _min_sharpe
    ctx['_pool_gate_mode'] = _pool_gate_mode
    ctx['_pool_gate_on'] = _pool_gate_on
    ctx['_pool_gate_or_all'] = _pool_gate_or_all
    ctx['_pool_obs'] = _pool_obs
    ctx['_pools'] = _pools
    ctx['_strip_style'] = _strip_style
    ctx['_dup_ex_corr'] = _dup_ex_corr
    ctx['_ex_by_expr'] = _ex_by_expr
    ctx['_n_dup_ex'] = _n_dup_ex
    ctx['_tag_by_expr'] = _tag_by_expr
    ctx['_strip_by_expr'] = _strip_by_expr
    ctx['_strip2_by_expr'] = _strip2_by_expr
    ctx['_hzn2_by_expr'] = _hzn2_by_expr
    ctx['frozen'] = frozen
    ctx['nd'] = nd
    ctx['r'] = r
    ctx['s'] = s
    return False


def _l2_strip_dual(j, nd, f, dates, cols, close, args, STYLE_FULL, _strip_style, rr):
    """单候选剥风格 + 副口径评估 -> (strip_rec, rr2, strip2, ok2)"""
    strip_rec = None
    rr2, strip2, ok2 = None, None, False
    # ---- 剥风格(2026-09-12, --strip_style; 见 docs/log/2026-09.md §8.13) ----
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
    # =============== ★★★★★ 2026-09-22（v1.21.29 · 用户拍板 (乙)）：**副口径评估** ===============
    #  为什么放这里：正好在「主口径 + 主口径剥风格」之后、「池内」之前 ✓
    #    · 副口径**只做** 主评 + 剥风格 + 分段（不做池内 ✗）——
    #      池内门槛是"池轨道"的概念 ✓，而副口径的价值在**全A 口径下**捞真信号 ✓；
    #      判定上它走 `_ok_q2`（全A 量化口径 ✓），与 `combine_ok` 的 OR 语义天然相容 ✓
    #    · ⚠⚠ **`FWD` 必须在 finally 里复原** ✗✗ —— 它是模块全局，
    #      `evaluate_real` 在**调用时**读它（实测确认 ✓：`fwd_ret=(close.shift(-(1+FWD))…)` 在函数体内 ✓）
    #      ⇒ 一旦中途异常而不复原，**后面所有候选都会按副口径评估** ✗ 且**不报错** ✓
    if args.dual_fwd and rr is not None:
        try:
            # ⚠⚠ **只切 `factor_miner.FWD`，不碰本模块的 `FWD`** ✗ ——
            #   本模块的 `FWD` 只在**候选循环之前**的预计算里用（`[::FWD]` 切片 ✓），
            #   而求值读的是 `factor_miner` 自己的全局 ✓ ⇒ 不需要动它 ✓
            #   ★ 而且**不能**在函数里裸写 `FWD = …` ✗：没有 `global` 声明 ⇒
            #     Python 会当**局部变量** ⇒ 既改不到全局、又会 `UnboundLocalError` ✗✗
            #     （我第一版就是这么写的 ✓ 自查拦下 ✓）
            _FM.set_fwd(int(args.dual_fwd))
            rr2 = evaluate_real(f, close, f"{nd}#h{int(args.dual_fwd)}",
                                cost=args.cost, window=args.window,
                                with_ex=True, with_daily=True)
            if _strip_style and rr2 is not None:
                _fn2 = neutral_rank(f.values.astype('float64'),
                                    [STYLE_FULL['lncap'], STYLE_FULL['lnamt']])
                rr_s2 = evaluate_real(pd.DataFrame(_fn2, index=dates, columns=cols),
                                      close, f"{nd}#h{int(args.dual_fwd)}#strip",
                                      cost=args.cost, window=args.window, with_daily=True)
                if rr_s2 is not None:
                    strip2 = dict(
                        gen=args.gen, expr=str(nd),
                        ic=rr2['ic'], calmar=rr2['calmar'], ann_ex=rr2['ann_ex'],
                        strip_ic=rr_s2['ic'], strip_calmar=rr_s2['calmar'],
                        strip_ann_ex=rr_s2['ann_ex'], strip_sharpe=rr_s2['sharpe'],
                        strip_dd_d=rr_s2.get('dd_d'),
                        strip_calmar_d=rr_s2.get('calmar_d'),
                        strip_sharpe_d=rr_s2.get('sharpe_d'))
        except Exception as e2:
            print(f"  [{j}] 副口径({int(args.dual_fwd)})评估失败(不影响主流程): "
                  f"{type(e2).__name__}: {e2}")
        finally:
            # ★★ 复原主口径：`FWD` 是本轮主口径（5 日 ✓ 由 `--fwd` 同步块设定 ✓）
            #   必须在 finally ⇒ 中途异常也要复原 ✗（否则后续候选全按副口径 ✓ 且静默 ✓）
            _FM.set_fwd(int(FWD))
        # 副口径的判定（**与主口径同一套闸** ✓，但走"全A 量化口径"这条 OR 支路 ✓）
        if rr2 is not None:
            try:
                ok2, _ = pass_filter(rr2, args.min_ic2)
                ok2 = bool(ok2 and rr2['calmar'] > args.min_calmar2
                           and rr2['sharpe'] > args.min_sharpe2)
                if args.seg_n > 1:
                    ok2 = bool(ok2 and seg_verify(rr2.get('ex'),
                                                  args.seg_n, args.seg_need)[0])
                if _strip_style and args.min_strip_calmar > 0 and strip2 is not None:
                    ok2 = bool(ok2 and strip2['strip_calmar'] > args.min_strip_calmar)
            except Exception as e3:
                ok2 = False
                print(f"  [{j}] 副口径判定失败(按未过处理): {type(e3).__name__}: {e3}")

    return strip_rec, rr2, strip2, ok2


def _l2_pool_tags(j, nd, fac, dates, cols, close, args, POOL_M, MCAP, _pools, _lp,
                  rr, strip_rec, strip2, pool_rec, _tag_by_expr, _strip_by_expr, _strip2_by_expr):
    """单候选池内指标 + 池标签/剥风格档派生（就地改 pool_rec / *_by_expr）"""
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
            # ★ 2026-09-22（v1.21.29 · (乙)）：**副口径**的剥风格档 + 记录 ✓
            #   ⚠ 只有**副口径入选**的因子才需要它 ✓（主口径入选者用上面那份 ✓）
            if args.dual_fwd and strip2 is not None:
                try:
                    _sg2_k, _sg2_t = _lp.strip_grade(strip2.get('strip_calmar_d'),
                                                     strip2.get('strip_ann_ex'),
                                                     strip2.get('strip_dd_d'))
                    _strip2_by_expr[str(nd)] = (_sg2_k, _sg2_t,
                                                strip2.get('strip_calmar'),
                                                strip2.get('strip_ann_ex'),
                                                strip2.get('strip_calmar_d'),
                                                strip2.get('strip_dd_d'))
                except Exception as e_s2:
                    print(f"  [{j}] 副口径剥风格档失败(不影响主流程): "
                          f"{type(e_s2).__name__}: {e_s2}")
        except Exception as e_t:
            print(f"  [{j}] 池标签派生失败(不影响主流程): {type(e_t).__name__}: {e_t}")

    return pool_rec


def _run_l2_phase(ctx, args):
    """L2 费后精筛 + 剥风格/池指标/收益流去重 + 落盘 -> 写回 ctx"""
    _min_pool_calmar = ctx['_min_pool_calmar']
    _min_sharpe = ctx['_min_sharpe']
    _pool_gate_mode = ctx['_pool_gate_mode']
    _pool_gate_on = ctx['_pool_gate_on']
    _pool_gate_or_all = ctx['_pool_gate_or_all']
    _pool_obs = ctx['_pool_obs']
    _pools = ctx['_pools']
    cols = ctx['cols']
    dates = ctx['dates']
    l1 = ctx['l1']
    B = ctx['B']
    close = ctx['close']
    STYLE_FULL = ctx['STYLE_FULL']
    _strip_style = ctx['_strip_style']
    fail_lib = ctx['fail_lib']
    bank_ex = ctx['bank_ex']
    bank_ex_ext = ctx['bank_ex_ext']
    _dup_ex_corr = ctx['_dup_ex_corr']
    nd = ctx['nd']
    _ex_by_expr = ctx['_ex_by_expr']
    _tag_by_expr = ctx['_tag_by_expr']
    _strip_by_expr = ctx['_strip_by_expr']
    _strip2_by_expr = ctx['_strip2_by_expr']
    _hzn2_by_expr = ctx['_hzn2_by_expr']

    POOL_M, _lp, _t_l2, top = _run_l2(_min_pool_calmar, _min_sharpe, _pool_gate_mode, _pool_gate_on, _pool_gate_or_all, _pool_obs, _pools, args, cols, dates, l1)
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
        # ★★★★ 2026-09-22（v1.21.29 · (乙) 双口径）：副口径的备用值 —— **必须在 `try` 之前初始化** ✗
        #   （求值中途异常时会跳到 except ⇒ 若不预置就是 `NameError` ✓ 本项目反复踩的坑 ✓）
        rr2, strip2, ok2 = None, None, False
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
            strip_rec, rr2, strip2, ok2 = _l2_strip_dual(j, nd, f, dates, cols, close, args, STYLE_FULL, _strip_style, rr)
            # ---- 池内指标(2026-09-12, --pool_obs; 见 roadmap §8.9 B+B′) ----
            #  口径 = **池内排名**(对齐 standard_test 默认的 --pool_mode=A):
            #    因子池外置 NaN -> cs_rank(逐行只在池内有效值上排名) -> 同一套费后回测。
            #  ⚠ evaluate_real 选股是 `fac.loc[d][U].dropna()` ⇒ 池外 NaN 自动被排除;
            #    且"池等权"基准随之变成**同池等权**(与 standard_test 口径一致, 不是全A等权)。
            pool_rec = _l2_pool_tags(j, nd, fac, dates, cols, close, args, POOL_M, MCAP, _pools, _lp, rr, strip_rec, strip2, pool_rec, _tag_by_expr, _strip_by_expr, _strip2_by_expr)
            del f
            gc.collect()
        except Exception as e:
            print(f"  [{j}] ERR {type(e).__name__}")
            continue
        if rr is None:
            continue
        yr = rr['yr']
        # 统一用 factor_miner.pass_filter 的11项标准(亏损年<-2% <=1, 而非"所有年>0")
        # ★★ 2026-09-22 删掉这里的**函数内 import** ✗✗ —— 病根就是它：
        #   函数内的 `import` 会让 `pass_filter` 在 `run()` 里成为**局部名** ✓
        #   ⇒ 而副口径判定（本函数**更早**处）已经**先用**过它 ✗ ⇒ 抛 `UnboundLocalError`
        #   ⇒ 被 except 吞掉 ⇒ 只打一行「副口径判定失败(按未过处理)」✗ ⇒ **`ok2` 恒为 False** ✗✗
        #   ⇒ 双口径的副口径通道**自 v1.21.29 上线起从未通过一次** ✗（生产一直开着它 ✓）
        #   ⇒ 现在统一取**模块顶部**的 import ✓
        #   ★ 由 `tools/_test_dual_horizon.py` 用 **AST** 钉住两条：
        #     ① 全函数不得有任何 `pass_filter` 的本地绑定 ✗（这才是病根 ✓ 位置无关 ✓）
        #     ② 它必须以**全局名**解析（`run.__code__.co_varnames` 不含 ✓ `co_names` 含 ✓）
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
        # ★★★★★ 2026-09-22（v1.21.29 · (乙)）：**双口径合并 —— 任一通过即入库** ✓
        #   · 顺序：先按主口径（含池门槛 OR 语义 ✓）算出 `ok` ✓，再让副口径做**纯 OR** ✓
        #   · 副口径**不参与池门槛** ✗（池内门槛是池轨道的概念 ✓；副口径的价值在
        #     **全A 口径**下捞真信号 ✓ ⇒ 它只走"全A 量化口径"这条支路 ✓ 语义自洽 ✓）
        #   · ⚠ 记录 `hzn`：文档/日志要按**实际入选的口径**标注 ✗（否则两个口径的数字混在一份文档里 ✓）
        _hzn = int(FWD)
        if args.dual_fwd and ok2 and not ok:
            ok = True
            _hzn = int(args.dual_fwd)
            _hzn2_by_expr[str(nd)] = _hzn
        # ★ 收益流去重(2026-09-13, roadmap §8.34, --dup_ex_corr): 算本候选 vs 历史库收益流的
        #   最大 |相关|。**止血**机制 —— 实测库内 30 个因子的收益流两两相关中位 **0.967**
        #   ⇒ 再攒同类因子等于没攒(合成 Calmar 还低于最好的单因子)。
        #   ⚠ 这里**只记录**(落 archive 的 max_ex_corr 列), 拦入库在下方 bank 追加段做
        #     —— 那里能拿到"本代已入库者"的最新库, 从而同时防"同代内近重复"。
        _mec, _mew = None, None
        _ex = rr.get('ex') if isinstance(rr, dict) else None
        if _dup_ex_corr > 0 and _ex is not None:
            _mec, _mew = ex_max_corr(_ex, _cmp_lib(bank_ex, bank_ex_ext))   # ★ 含外部池库(§1.8)
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
                         passed=ok,
                         # ★★★★★ 2026-09-22（v1.21.29 · (乙)）：副口径列 —— **只在开启时才写** ✗
                         #   ⇒ 关（默认 ✓）时 archive 的表头/内容与改造前**逐字一致** ✓
                         #   （本文件走 `append_csv_schema_safe` ⇒ 加列时会**重写并救回旧行** ✓ 不产生
                         #     混合宽度 ✓ 但仍以"只在需要时才加"为原则 ✓）
                         **(dict(hzn=_hzn,
                                ic2=(rr2['ic'] if rr2 is not None else np.nan),
                                calmar2=(rr2['calmar'] if rr2 is not None else np.nan),
                                sharpe2=(rr2['sharpe'] if rr2 is not None else np.nan),
                                turn2=(rr2.get('turn', np.nan) if rr2 is not None else np.nan),
                                passed2=bool(ok2)) if args.dual_fwd else {})))
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
    _dump_strip_detail(_strip_style, strip_rows)
    # ---- 池内指标落盘(2026-09-12, --pool_obs; **长表**, 独立文件) ----
    #  为什么长表: 池集合由 --pools 决定, 宽表(ic_300/ic_500...)一旦换池集合就会
    #  在追加时表头错位(与 loop_archive.csv 同一个坑)。长表 = (gen,expr,pool) 三键, schema 恒定。
    #  `pool_tag`(300好用/300+500好用/全都好用/只有全A好用) 由**离线**派生(阈值可改后重算)。
    nd, res = _dump_pool_obs(POOL_M, _pools, args, fail_lib, nd, pool_rows, rows, top)


    ctx['POOL_M'] = POOL_M
    ctx['_lp'] = _lp
    ctx['_t_l2'] = _t_l2
    ctx['top'] = top
    ctx['rows'] = rows
    ctx['seg_ok_list'] = seg_ok_list
    ctx['strip_rows'] = strip_rows
    ctx['pool_rows'] = pool_rows
    ctx['res'] = res
    ctx['nd'] = nd
    ctx['_ex_by_expr'] = _ex_by_expr
    ctx['_tag_by_expr'] = _tag_by_expr
    ctx['_strip_by_expr'] = _strip_by_expr
    ctx['_strip2_by_expr'] = _strip2_by_expr
    ctx['_hzn2_by_expr'] = _hzn2_by_expr


def _run_finalize(ctx, args):
    """诊断本代 + B角 LLM 审查 + 保存状态（最后一段，只读 ctx）"""
    fam_blocked = ctx['fam_blocked']
    l1 = ctx['l1']
    pool_rows = ctx['pool_rows']
    res = ctx['res']
    seg_ok_list = ctx['seg_ok_list']
    cfg = ctx['cfg']
    obs_df = ctx['obs_df']
    r = ctx['r']
    jury_lines = ctx['jury_lines']
    llm_hyp = ctx['llm_hyp']
    llm_on = ctx['llm_on']
    n_jury_kill = ctx['n_jury_kill']
    n_jury_rev = ctx['n_jury_rev']
    n_llm_call = ctx['n_llm_call']
    n_llm_hit = ctx['n_llm_hit']
    n_llm_parse = ctx['n_llm_parse']
    _dup_ex_corr = ctx['_dup_ex_corr']
    _ex_by_expr = ctx['_ex_by_expr']
    _n_dup_ex = ctx['_n_dup_ex']
    _strip_by_expr = ctx['_strip_by_expr']
    _tag_by_expr = ctx['_tag_by_expr']
    bank = ctx['bank']
    bank_ex = ctx['bank_ex']
    bank_ex_ext = ctx['bank_ex_ext']
    cands = ctx['cands']
    fail_lib = ctx['fail_lib']
    frozen = ctx['frozen']
    fsa = ctx['fsa']
    n_tested_prev = ctx['n_tested_prev']
    nd = ctx['nd']
    s = ctx['s']
    t0 = ctx['t0']
    top = ctx['top']
    fsa_frz = ctx['fsa_frz']
    _strip2_by_expr = ctx['_strip2_by_expr']
    _hzn2_by_expr = ctx['_hzn2_by_expr']

    # ---- B角: 诊断本代 + 给出下一代策略 + 写日志 ----
    critic, diag, res_c = _critic_diagnose(args, fam_blocked, l1, pool_rows, res, seg_ok_list)
    # ---- 风格暴露诊断聚合(2026-09-11, --style_obs): 落盘已在 L1 求值后完成, 此处只做分组聚合 ----
    #  判读(见 docs/log/2026-09.md §8.3/§8.4): new vs old 两组对比, 若 L2 候选/通过集的
    #  |lntr|、|lnamt| 中位显著上升 -> 确诊"新排序分在低换手/低成交额方向加倍下注"。
    next_cfg, reasons = _agg_style_diag(cfg, critic, diag, l1, obs_df, r, res)
    # ---- 生成侧 LLM 引导留痕(独立引用体小节, 与 ai_review 块同风格) ----
    _log_llm_hint(args, jury_lines, llm_hyp, llm_on, n_jury_kill, n_jury_rev, n_llm_call, n_llm_hit, n_llm_parse)

    # ---- B角 LLM 审查(DeepSeek, --ai_critic auto/on/off, 默认auto=有key即启用) ----
    _v = None  # ★ 死透传（_critic_llm_review 内覆盖参数）；L1 循环 `for _d_,_v in zip` 的兜底赋值已移走
    _v = _critic_llm_review(_v, args, critic, diag, l1, next_cfg, reasons, res_c)

    # ---- 保存状态 ----
    k = None  # ★ 死透传（_save_state 不读 k）；生成循环 `k=str(node)` 的兜底赋值已随 _run_gen 移走
    v = None  # ★ 死透传（_save_state 不读 v）；L2 循环 `v=eval_expr` 的兜底赋值已随 _run_l2_phase 移走
    _save_state(_dup_ex_corr, _ex_by_expr, _n_dup_ex, _strip_by_expr, _tag_by_expr, _v, args, bank, bank_ex, bank_ex_ext, cands, fail_lib, frozen, fsa, k, l1, n_tested_prev, nd, next_cfg, pool_rows, res, s, t0, top, v, fsa_frz,
                _strip2_by_expr, _hzn2_by_expr)



def run(args):
    ctx = _run_prepare(args)
    if _run_gen(ctx, args):
        return
    if _run_l1_phase(ctx, args):
        return
    _run_l2_phase(ctx, args)
    _run_finalize(ctx, args)
    return 0




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
        # ⚠ 同 `_wt`：`base[k] is None` 时 `.get(k, 1.0)` 返回 None ⇒ 乘出来炸（2026-09-17 加固）
        out[k] = _wt(base, k) * (0.3 + 0.7 * n)
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
    # ★★★★★ 2026-09-25 修（用户实测："这 F47 为啥会显示未分类"）—— **一份代码里出现了两个 `Node` 类** ✗✗
    #   病根：引擎直跑时模块名是 `__main__`（类全名 `__main__.Node`），而 `loop_critic` 的
    #     惰性 `import loop_engine as LE` 会把 `loop_engine.py` **再执行一遍**（这次叫 `loop_engine`
    #     模块）⇒ 同一个进程里有**两个** `Node` 类 ✗
    #   实测（读 `loop_state.pkl` 按 pickle 记录的类路径统计）：`bank` 里 439 个 Node 中
    #     **438 个是第二份** ✗；`seeds` / `last_l1` 也各混着 24 个 ✗
    #   ⇒ 后果：所有 `isinstance(x, Node)` 对"第二份"实例**恒为 False** —— 牵连：
    #     · `collect()` → `leaf_parts()` ⇒ 因子库"家族"全落 **「未分类」** ✗
    #       （`docs/loop_archive*.csv` 的 `cat`/`leaf` 列空，全库 392 行）
    #     · **`skeleton()` ⇒ 骨架去重 / FSA 冻结失效** ✗（同族重复因子拦不住）
    #     · `key()`/`size()`（FSA 结构哈希）· `crossover`/`mutate`（子树操作退化成只动顶层）
    #       · `dim_of()`（跨量纲审查）· `clone`
    #   ⇒ 修法（**一行**）：把"自己"注册成 `loop_engine` 模块 ⇒ 之后任何 `import loop_engine`
    #     都拿到**本模块** ⇒ 结构上不可能再出现第二份 ✓
    #   ⚠ 为什么放在**这里**（块内第一条）而不是文件顶部 ✗：
    #     · `tools/_test_fwd_wiring.py` 用 AST 取**第一个** `__main__` 块，并在其中断言
    #       `set_panel_cache` / `set_mem_budget` / `run(_args)` 是**直接语句** ✗
    #       ⇒ 在顶部另起一个 `__main__` 块会把它的"目标块"抢走（实测该守门当场失败 ✗）
    #     · 放在这里也**足够早** ✓：`loop_critic` 是**惰性** import（只在 `run()` 内被调），
    #       而 `run(_args)` 是本块**最后一句** ⇒ 注册必然发生在它之前 ✓
    #   （旧 state 里已混入的 486 个异类，由 `_StateUnpickler` 在读盘时归一 ✓ 见其 docstring）
    sys.modules.setdefault('loop_engine', sys.modules['__main__'])
    ap = argparse.ArgumentParser()
    ap.add_argument('--gen', type=int, default=1)
    ap.add_argument('--n', type=int, default=600)
    ap.add_argument('--gen_only', action='store_true',
                    help='dry-run: 只跑候选生成段验证产量, 不跑L1/L2/不写状态')
    ap.add_argument('--panel_cache', choices=['off', 'use', 'build'], default='off',
                    help='面板只读缓存(2026-09-16, 默认 off = 现状): 把 4.42GB 的面板落成'
                         '【只读 memmap】(engine/_panel_cache/) -> 多个引擎进程共享同一批物理页'
                         '(Windows spawn 下也能省内存), 且免去每次约 14.6s 的 h5 重建。'
                         'off=现场构造(与改造前逐位相同); use=读缓存(缺失/过期**直接报错**, '
                         '不偷偷重建); build=现场构造并落盘后继续(结果与 off 逐位相同)。'
                         '[!] 缓存与池无关, 过期检测 = 来源 h5 的(size,mtime_ns) + 构造函数源码 SHA1')
    # ★ 2026-09-16「每进程私有缓存预算」（默认 = 现状 ⇒ 不传就是旧行为）
    #   并行跑 N 个池时，面板可共享、这三份缓存不能 ⇒ 它们是并行时的内存地板。
    ap.add_argument('--lru_max', type=int, default=400,
                    help='L1 子树缓存(条数)上限, 防 L1 段 OOM(默认 400 = 现状)。'
                         '并行时按内存预算调小(时间换内存: 越小越多子树现场重算)')
    ap.add_argument('--cache2_max', type=int, default=150,
                    help='去相关/去重阶段 cache2(条数)上限(默认 150 = 现状)')
    # ★★★★★ 2026-09-21（用户拍板 (A)：治"宽池工作集"）—— A/B 实测后**收紧默认值** ✓
    #   起因：把 1000 池 L1 的工作集逐项量准（`ai_test/_l1_comp.py` ✓）后发现
    #     **两个缓存（`_LRU` + `VCACHE`）合计 ~4.4 GB = 私有峰值的约一半** ✗
    #     （全量面板 4.2 GB 是 memmap **共享页** ✓ 不算私有；真副本只有 B_sub ≈0.97 ✓）
    #   A/B（同一驱动命令 + `--engine_arg=` 追加 ✓ 只改这两个预算）：
    #     · 旧 2500 / 2000 ⇒ 私有峰值 **8.72 GB** · 工作集 10.60 · 单代 ≈110~120 分钟
    #     · 新 1200 /  800 ⇒ 私有峰值 **7.665 GB**（−1.06 GB / **−12%**）·
    #                        工作集 9.111（−1.49 / −14%）· 单代 ≈ **94 分钟**（**没变慢** ✓）
    #   ★ 为什么**零风险**：两者都是**纯加速缓存** ⇒ 少存只会**重算**，数值/结果完全不变 ✓
    ap.add_argument('--vreuse_cap_mb', type=float, default=800.0,
                    help='跨阶段复用缓存 VCACHE 上限 MB(默认 800; 仅 --reuse_v=1 时生效)')
    # ★★★★★ 2026-09-21（治本）：**字节预算**（条数上限管不住内存 ✗ —— 见 set_mem_budget 注释 ✓）
    # ★ 2026-09-21：默认 2500 → 1200（A/B 实测：私有峰值 −12%、耗时没变差 ✓ 见上条注释）
    ap.add_argument('--lru_mb', type=float, default=1200.0,
                    help='L1 跨批子树缓存**字节**上限 MB(默认 1200; 条数上限 --lru_max 仍作兜底 ✓)')
    ap.add_argument('--cache2_mb', type=float, default=800.0,
                    help='去相关/去重 cache2 **字节**上限 MB(默认 800 ✓)')
    ap.add_argument('--batch_mb', type=float, default=1500.0,
                    help='L1 单批候选的**数组总量**上限 MB(默认 1500 ⇒ 批大小按池宽自适应 ✓)')
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
    # ⚠⚠ argparse 的 help 会走 `help_string % params` 插值 ⇒ **任何字面百分号必须写 `%%`**。
    #   2026-09-14 实录：初版写了裸 `82%` ⇒ `--help` 与 `parse_args` **双双崩溃**
    #   （`ValueError: unsupported format character`）⇒ **引擎完全起不来**。
    #   冒烟测试（`--help`）抓到了它 —— 这就是"每次改动都跑一次 --help"的价值。
    ap.add_argument('--inject_pools', default='',
                    help='★★ 注入**其它池的库**作为对照集（2026-09-14, loop_todo §1.8；默认空=行为不变）。'
                         '逗号分隔池名，如 `--inject_pools=300,500,1000`（跑全A 轨道时用）。'
                         '为什么需要：`--decorr`/`--dup_ex_corr` 的对照集原本只是**本轨道自己的 bank** '
                         '⇒ 跑全A 时**不知道池库挖到了什么** ⇒ 把同一批重挖一遍。'
                         '实测（tools/check_pool_vs_allA.py）：池因子 vs 全A 库(41) 的收益流最大 |相关| '
                         '**中位 0.767**、>0.7 占 **82%%**，而 `--dup_ex_corr=0.90` 只挡得住 18%% '
                         '⇒ 不注入 ≈ **把 82%% 的算力花在重挖上**。'
                         '★ 语义：外部池库只作**对照**（"这些已经挖过了"），'
                         '**不会**写回本轨道的 state / `docs/factor_library*.md` —— 外部池库不算本轨道的产出。')
    # ⚠ argparse help 走 `%` 插值 ⇒ 字面百分号写 `%%`（2026-09-14 踩过，见 `--inject_pools`）
    ap.add_argument('--parent_sel', choices=list(PARENT_SEL_MODES), default='uniform',
                    help='★ 亲本选择策略（2026-09-14, loop_todo §1.3-C；默认 uniform = **行为不变**）：'
                         'uniform=亲本池内均匀随机（**现状**）· best=恒取第 1 名 · '
                         'top_percent_plus_random=**top 30%% 保底 + 余量随机**。'
                         '为什么要有：当前 uniform **丢掉了排名信息** —— L1 里第 1 名和第 30 名'
                         '被选中的概率**完全一样**；我们原来只有"**堵**"的手段'
                         '（`--fam_quota` 配额 / `fam_block_thr` 黑名单 / `--decorr`），'
                         '**没有"疏"**（显式的探索/利用配比）。对齐 QuantaAlpha '
                         '`parent_selection_strategy` 族（`configs/experiment.yaml:83-92`）。'
                         '⚠ 换策略 = **换搜索行为**，跨代对比时勿混用。')
    ap.add_argument('--parent_top_pct', type=float, default=0.30,
                    help='仅 `--parent_sel=top_percent_plus_random` 用：top 段比例'
                         '（默认 0.30，对齐 QuantaAlpha `top_percent_threshold: 0.3`）。'
                         '调大更偏探索（→1.0 退化成 uniform）；建议 0.2~0.5 之间试。')
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
                         '同时要求全A 达标是自相矛盾)。组合标定(tools/combo_calib.py): '
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
    # ★★★★★ 2026-09-21（用户拍板：(C) 双口径挖掘**前置改造**）—— 调仓周期**命令行入口**
    #   背景：`factor_miner.set_fwd()` 早就写好（注释 `1=日频 5=周频 20=月频` ✓）却是**孤儿函数**
    #     —— 全仓零调用 ✗，`FWD` 实际写死 5 ⇒ **引擎侧没有任何口径入口** ✗
    #   ⚠ 语义：**0 = 不改**（沿用引擎默认 5 ⇒ 行为逐位不变 ✓）；非 0 ⇒ 本进程按该口径求值 ✓
    #   ⚠ 与 `--window` **不是一回事** ✗：`--window` 是**样本区间**（full/recent600 ✓），
    #     本参数是**调仓周期** ✓（期数 418 → ~104 ✓）
    ap.add_argument('--fwd', type=int, default=0,
                    help='调仓周期（交易日）；0=沿用引擎默认(5)。★ 双口径挖掘用（20）✓')
    # ★★★★★ 2026-09-22（v1.21.29 · 用户拍板 **(乙) 引擎双评**）—— **副口径**
    #   同一个候选**同时**在 5 日（主口径）与 `--dual_fwd N`（副口径）下评估 ✓
    #   **任一口径达标即入库** ✓，入库文档按**实际入选的口径**标 `horizon` ✓（见 `_save_state` ✓）
    #   ⚠ 默认 0 = **关** ⇒ 不传时行为与改造前**逐位不变** ✓（新增列也只在开启时才写 ✗）
    #   ⚠ `FWD` 是**模块全局** ⇒ 副口径求值必须 **try/finally 复原** ✗（否则污染后续候选 ✓ 且静默 ✓）
    #   ⚠ 成本：每候选 +2 次回测（副口径主评 + 副口径剥风格）⇒ 约 ×1.4（面板/IC 可共用 ✓）
    ap.add_argument('--dual_fwd', type=int, default=0,
                    help='★ 副口径调仓周期（交易日）；0=关（默认 ✓ 行为不变）。'
                         '开启后候选在 5 日与 N 日各评一次，**任一通过即入库** ✓')
    # 副口径的门槛（默认与主口径同档 ✓ —— 实测 20 日分布略高，故也可显式调高 ✓）
    ap.add_argument('--min_calmar2', type=float, default=0.5, help='副口径 Calmar 门槛')
    ap.add_argument('--min_sharpe2', type=float, default=0.5, help='副口径 Sharpe 门槛')
    ap.add_argument('--min_ic2', type=float, default=0.02, help='副口径 |IC| 门槛')
    ap.add_argument('--window', choices=['full', 'recent600'], default='full',
                    help='回测口径: full=2018起九年; recent600=最近600交易日(中金口径)')
    ap.add_argument('--seg_n', type=int, default=3,
                    help='分段独立验证: 费后日超额序列均分成多少个不相交子区间; '
                         '0/1=关闭(默认3: 约3年一段); 样本不足自动放行不误杀')
    ap.add_argument('--seg_need', type=int, default=2,
                    help='分段独立验证: 至少几个子区间累计费后超额>0 才通过 '
                         '(默认2: 3段中≥2段为正, 拦"靠单段行情撑全样本"候选)')
    # ★★★★★ 2026-09-21（用户拍板：(C) 双口径挖掘 **前置改造**）——
    #   把**调仓周期**从命令行接进本模块的全局 `FWD` ✓
    #   ⚠ 必须在 `run()` **之前**同步：`fwd_ret` 的构造（L2183）与 **14 处 `[::FWD]` 切片**都在 run 内 ✓
    #   ⚠ `set_fwd` 返回的是**新值** ⇒ 旧值要先记 ✓
    _args = ap.parse_args()
    if _args.fwd:
        _FWD_OLD = FWD
        _FM.set_fwd(int(_args.fwd))
        FWD = _FM.FWD                # ★ 本模块全局（模块级 if 内赋值 = 全局 ✓）⇒ 14 处切片跟着走 ✓
        print('  ★ 调仓周期口径 = **%d 交易日**（引擎默认 %d）⇒ 期数约 418 → 约 %d ✓'
              % (FWD, _FWD_OLD, max(1, int(418 * _FWD_OLD / float(max(FWD, 1))))), flush=True)
    set_mine_pool(_args.mine_pool)   # ★必须在 run() 之前: 路径后缀 & L1 池掩码都在 run 内部生效
    set_panel_cache(_args.panel_cache)   # ★同上: base_fields() 在 run() 内部首次被调用
    # ★ 2026-09-16：把「私有缓存预算」落到模块全局（默认值与改造前完全相同 ⇒ 逐位不变）
    set_mem_budget(_args.lru_max, _args.cache2_max, _args.vreuse_cap_mb,
                   _args.lru_mb, _args.cache2_mb, _args.batch_mb)
    run(_args)
