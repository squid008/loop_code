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




# 默认搜索策略(B角可动态调整)
# ===================== 1. 基础字段 =====================
# ---- 叶子字段单一事实源 = loop_fields.py (引擎A角/B角critic/量纲/写档共用) ----
# 新增字段族只改 loop_fields.py 一处, 勿在本文件硬编码叶子名(防再漂移)。
# 资金流 moneyflow3 原始拆分16列: 金额(×1e4元,量纲A)+量(×100股,量纲V), 净额不预焊由GP自组合;
# BARRA 连续风格11(barra.h5,行业哑不入叶) / 财报PIT as-of比率8(fa_pit.h5,按info_date无未来函数)
from loop_fields import MF16, BARRA_LEAVES, FA_LEAVES, LEAVES, FIELDS
from loop_expr import Node, collect, clone     # ★ L3 拆分：表达式核心类型/遍历单一事实源
from loop_dims import review_expr, dim_of      # ★ L3 拆分：跨量纲审查单一事实源
from loop_expr import _fsa_stats  # ★ 文件级拆分：FSA 骨架统计
from loop_gen import _build_fam_blacklist  # ★ 文件级拆分：结构族黑名单
from loop_data import _build_panel_fresh, _panel_sha1, base_fields  # ★ 文件级拆分
import loop_paths as _P
from loop_paths import set_mine_pool  # ★ 文件级拆分
import loop_cache as _C  # ★ 文件级拆分：路径常量单一事实源（用 _P.STATE 运行时取，勿值拷贝）
from loop_cache import (set_panel_cache, set_mem_budget, trim_cache,
                        trim_cache_mb)  # ★ 文件级拆分：缓存工具 re-export
from loop_stage import (_run_prepare, _run_gen, _run_l1_phase, _run_l2_phase,
                       _run_finalize, _l1_eval, _l1_filter, _l2_strip_dual,
                       _l2_pool_tags)  # ★ 文件级拆分：阶段函数
from loop_eval import (style_features, _jscalar, node_to_dict, node_from_dict,
                      fam_quota_rows, factor_stability, seg_verify, batch_ic,
                      _critic_review_prev, _load_fail_lib, _rand_explore,
                      _gen_candidates, _run_l1, _apply_fam_quota, _jury_deep_review,
                      _run_l2, _critic_diagnose, _agg_style_diag, _log_llm_hint,
                      _critic_llm_review, data_profile, _mix_weights, node_stat_txt,
                      llm_jury, llm_jury_block, llm_journal_block)  # ★ 文件级拆分：评估
from loop_persist import (_StateUnpickler, append_csv_schema_safe, _real_mb,
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
                     crossover, PARENT_SEL_MODES, pick_parent, perturb,
                     guided_expr)  # ★ 文件级拆分：guided_expr 已迁 loop_gen
from loop_ops import (UNARY, BINARY, ts_delay, ts_delta, cs_rank_op,
                     cs_demean_op, cs_scale_op, ts_mean)  # ★ L3 拆分：算子表+le算子
from loop_faillib import flib_mark, fail_lib_cleanup, bad_skels  # ★ L3 拆分：失败模式库
from loop_expr import (norm_op, skeleton, skeleton_freq, subtree_skels,
                        has_frozen_skel, fsa_period, sole_leaf,
                        leaf_proxy_key, root_fam, FSA_FREEZE_SEQ,
                        FSA_COOL_GENS, FAM_CUT, FAM_QUOTA, FAM_BLOCK_THR)

# ★★★ 2026-09-16 新增「面板只读缓存」模式（`--panel_cache`，**默认 off ⇒ 与改造前逐位不变**）
#   实测：面板 B = 4.42 GB 且**构造完成后只读**；而 Windows 是 spawn(无 fork) ⇒
#   每个引擎进程各建一份。落成只读 memmap 后多进程共享同一批物理页（省内存 + 免重建）✓
#   实现见 `engine/panel_cache.py`（含过期检测/只读保护 → 不会静默用旧面板）。


















# ===================== 2. 算子 =====================


# ⚠ 2026-09-15（架构清扫 P0-1）删除 4 个**死代码**：`ts_max_op` / `ts_min_op` /
#   `ts_corr20_op` / `ts_corr60_op` —— 早期实现残留（当时算子表还没统一用
#   `_mx`/`_mn`/`_cr`），经 `tools/_audit_deadcode.py` 实测：**本文件内外均无引用** ✗
#   且与 `UNARY` 里的 `ts_max20`/`ts_min20`/`corr20`/`corr60` 功能重复 ✓



# ★LEAVES 完整叶子池已由顶部 `from loop_fields import LEAVES` 提供
#   (基础7 + 派生12 + MF16资金流 + BARRA11风格 + FA8财报 = 54), 勿在此重复硬编码(防漂移)

# ===================== 3. 表达式 =====================






















# ★★★★ 2026-09-17（用户："我发现又入库了一个新因子，但**找不到什么时候入库的、入的哪个库**"
#   ⇒ 要求看板池状态区加一张"新入库日志"卡片）：
#   入库事件日志（**append-only JSONL**，进 git ⇒ 换机器也看得到）——
#   · 一行 = 一次入库：时间 / 池 / 代数 / 编号 / 公式 / 家族 / 一句话
#   · 由**引擎入库那一刻**写（真实时间 ✓）；历史条目由
#     `tools/backfill_library_entries.py` **回填**（时间取自该代引擎日志的 mtime，
#     并标 `tsSource` —— 推算出来的时间**必须标明来路**，不许冒充"记录时间" ✗）








# ===================== 4. L1 批量 IC =====================








# rank_rows 已移至 loop_metrics.py（单一事实源, 2026-09-11）; 顶部 import 引入,
# 故本模块内 `rank_rows(...)` 与外部的 `loop_engine.rank_rows` 接口保持不变。








# ===================== 5. 主循环 =====================




















































def run(args):
    ctx = _run_prepare(args)
    if _run_gen(ctx, args):
        return
    if _run_l1_phase(ctx, args):
        return
    _run_l2_phase(ctx, args)
    _run_finalize(ctx, args)
    return 0






















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
    #     **两个缓存（`_C._LRU` + `_C.VCACHE`）合计 ~4.4 GB = 私有峰值的约一半** ✗
    #     （全量面板 4.2 GB 是 memmap **共享页** ✓ 不算私有；真副本只有 B_sub ≈0.97 ✓）
    #   A/B（同一驱动命令 + `--engine_arg=` 追加 ✓ 只改这两个预算）：
    #     · 旧 2500 / 2000 ⇒ 私有峰值 **8.72 GB** · 工作集 10.60 · 单代 ≈110~120 分钟
    #     · 新 1200 /  800 ⇒ 私有峰值 **7.665 GB**（−1.06 GB / **−12%**）·
    #                        工作集 9.111（−1.49 / −14%）· 单代 ≈ **94 分钟**（**没变慢** ✓）
    #   ★ 为什么**零风险**：两者都是**纯加速缓存** ⇒ 少存只会**重算**，数值/结果完全不变 ✓
    ap.add_argument('--vreuse_cap_mb', type=float, default=800.0,
                    help='跨阶段复用缓存 _C.VCACHE 上限 MB(默认 800; 仅 --reuse_v=1 时生效)')
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
        # ★ 2026-09-26（拆分后补）：`loop_stage` 里**也有一份主口径 `FWD`**（供 `[::FWD]` 切片 +
        #   副口径块的 `finally` 复原 ✓）⇒ 必须**一起同步**，否则 `--fwd` 只改本模块、
        #   阶段函数仍用旧值 ⇒ 切片与复原口径不一致 ✗
        import loop_stage as _LS
        _LS.FWD = _FM.FWD
        print('  ★ 调仓周期口径 = **%d 交易日**（引擎默认 %d）⇒ 期数约 418 → 约 %d ✓'
              % (FWD, _FWD_OLD, max(1, int(418 * _FWD_OLD / float(max(FWD, 1))))), flush=True)
    set_mine_pool(_args.mine_pool)   # ★必须在 run() 之前: 路径后缀 & L1 池掩码都在 run 内部生效
    set_panel_cache(_args.panel_cache)   # ★同上: base_fields() 在 run() 内部首次被调用
    # ★ 2026-09-16：把「私有缓存预算」落到模块全局（默认值与改造前完全相同 ⇒ 逐位不变）
    set_mem_budget(_args.lru_max, _args.cache2_max, _args.vreuse_cap_mb,
                   _args.lru_mb, _args.cache2_mb, _args.batch_mb)
    run(_args)
