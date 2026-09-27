# -*- coding: utf-8 -*-
"""loop_stage.py — run() 的阶段函数（2026-09-26 文件级拆分，最后一步）

★ 依赖全部已拆分模块 + 标准库 + 惰性 import loop_critic/loop_llm/loop_pools，不 import loop_engine。
"""
import gc
import os
import random
import time

import numpy as np
import pandas as pd

import factor_miner as _FM
from factor_miner import evaluate_real, cs_rank, pass_filter, get_universe, START

# ★★★★★ 2026-09-26（拆分后**必须还原**这条语义，否则静默改口径 ✗✗）：
#   `FWD` = **本模块的主口径**（默认 5）—— 它同时供 ① 全部 `[::FWD]` 调仓日切片、
#   ② 副口径块的 `finally` **复原**（`_FM.set_fwd(int(FWD))`）。
#   ⚠ **不能**把它换成 `_FM.FWD` ✗：`_FM.set_fwd(20)` 之后 `_FM.FWD` 自己就是 20 ⇒
#     "复原"变成 **no-op** ⇒ 后续候选的**池内指标**全部按 20 日口径算 ✗（实测：
#     池门槛 `+0.254` 而正确值 `+0.192` —— A/B 对拍抓到的 ✓）。
#   ⚠ `--fwd` 由 `loop_engine.py` 的 `main()` **同步两个模块**（见那里的同步块 ✓）。
FWD = _FM.FWD

from loop_expr import (Node, collect, skeleton, root_fam, has_frozen_skel, clone, _fsa_stats)
from loop_ops import UNARY, BINARY, ts_mean
from loop_gen import (DEFAULT_CFG, _clean_cfg, rand_expr, eval_expr, mutate, leaf_parts,
                     crossover, pick_parent, perturb, guided_expr, _build_fam_blacklist)
from loop_dims import review_expr
from loop_faillib import flib_mark
from loop_metrics import (rank_rows, decile_shape, l1_score, style_expo, STYLE_KEYS,
                          neutralize_rows, neutral_rank)
from loop_pools import pool_mask, parse_pools, pool_gate_ok
from loop_eval import (style_features, batch_ic, factor_stability, seg_verify, _run_l1, _run_l2,
                       _critic_review_prev, _load_fail_lib, _rand_explore, _gen_candidates,
                       _apply_fam_quota, _jury_deep_review, _critic_diagnose, _agg_style_diag,
                       _log_llm_hint, _critic_llm_review)
from loop_persist import (_dump_strip_detail, _dump_pool_obs, _save_state, _cmp_lib, ex_max_corr,
                          _gate_of, _pool_best, combine_ok, append_csv_schema_safe,
                          _StateUnpickler)
from loop_data import base_fields
from loop_llm_guide import llm_fetch
from cost_presets import cost_label

import loop_cache as _C
from loop_cache import trim_cache, trim_cache_mb
import loop_paths as _P

HERE = os.path.dirname(os.path.abspath(__file__))   # engine/ 目录（与 loop_engine.py 同目录）


# ★★★ 以下是本函数**函数体内**的设计说明（S3a 只搬位置、一字未改 ✓）
#   规则：连续 ≥3 行的论述块上移；贴行注释留在代码旁（保局部性 ✓）
    # ★ 收益流库(2026-09-13, roadmap §8.34): {表达式: 每期费后超额 Series} —— 收益流去重的对照集。
    #   缺它的旧 state 也能跑(只与"本次运行新入库的"比), 但要立即见效请先跑
    #   `tools/backfill_bank_ex.py` 补齐历史。
    # ★★ 外部池库对照集（2026-09-14, `loop_todo §1.8`）—— **只读，绝不写回 state / 因子库**。
    #   为什么需要：`--decorr`/`--dup_ex_corr` 的对照集原本只是"**本轨道自己的 bank**"
    #   ⇒ 跑全A 时它不知道池库挖到了什么 ⇒ 把同一批重挖一遍（实测收益流 |相关| 中位 0.767、>0.7 占 82%）。
    #   ★ 与 `bank`/`bank_ex` 的区别：那两个是**本轨道的产出**（会持久化 + 进 `docs/factor_library*.md`）；
    #     这两个只是"**告诉我这些已经挖过了**"的对照来源。
    # ★ n_tested 的基准必须在**写盘之前**取好(2026-09-12 修 —— 这是一个崩在整代末尾的隐蔽 bug):
    #   原写法 `n_tested=st.get('n_tested',0)+len(cands) if os.path.exists(_P.STATE) else len(cands)`
    #   的三元条件是在 `with open(_P.STATE,'wb')` **之后**求值的 —— 而那一步已经把文件创建出来了
    #   ⇒ 条件**恒为 True**; 全新轨迹(无既有 state)时 `st` 从未绑定 ⇒ UnboundLocalError
    #   ⇒ 崩在**整代最后一行**(30 分钟计算白做, 且 state 被 0 字节覆盖)。
    #   实录: `--mine_pool=300` 首次全新轨迹即崩(loop_state_300.pkl 被创建为 0 字节)。
    # ★ 上一代的「池口径」传感器数据（2026-09-14, §1.1 修法②）：代首要**重审上一代**，
    #   而池结果不在 `last_l2` 里（那是全A 口径的表）⇒ 必须随 state 一起存。
    #   ⚠ 无 state 时必须能保持为 None（否则 `st` 未绑定 -> UnboundLocalError，
    #     这正是 §8.23 那个"崩在整代最后一行"的同类坑）。
            # ★★★★★ 2026-09-25：走**归一** Unpickler —— 把历史上误存的 `loop_engine.Node`
            #   也还原成本模块的 `Node`（详见**文件末尾** `__main__` 块的注册处 / `_StateUnpickler`）✓
            #   ⚠ 不加这一句：`bank`/`seeds`/`last_l1` 里的那批"第二份"Node 会让
            #     `skeleton`/`collect`/`key` 全部失效（骨架去重与 FSA 对它们形同虚设）✗
        # ★★★ 外部池库注入对照集（2026-09-14, `loop_todo §1.8`）----
        #   问题：`--decorr` / `--dup_ex_corr` 的对照集是**各自轨道自己的 bank**
        #   ⇒ 跑全A 时它**根本不知道池库挖到了什么** ⇒ 会把同一批重挖一遍。
        #   实测（`tools/check_pool_vs_allA.py`）：池因子 vs 全A 库(41) 的收益流最大 |相关|
        #   **中位 0.767**，>0.7 占 **82%**，而 `--dup_ex_corr=0.90` 只挡得住 18%
        #   ⇒ **不做注入 ≈ 把 82% 的算力花在重挖上**。
        #   ★ 语义：外部池库只能"**告诉我这些已经挖过了**"，**不能算我的产出**
        #     ⇒ 单独存 `bank_ext`/`bank_ex_ext`，**绝不写回自己的 state / 因子库** ✓
    # ---- 结构族黑名单(QuantaAlpha 正交思想, gen31): 上代 L1 霸榜模板族 ----
    # 上代同模板族(叶子身份无关指纹)占比 >= FAM_BLOCK_THR -> 本代生成端禁产(硬闸换血);
    # top2 模板文本另注入 A角 LLM 提示词(软约束)。根治"同族霸榜 -> 0 通过"空转。
    # ---- 随机探索: 数据驱动特征分布引导(中金"随机探索15%=数据驱动分布, 防局部最优") ----
    # 证据分布 = 历代入库因子 + 上一代 L1 通过候选 的叶子/算子族频率;
    # 随机位按该分布抽样(探索有苗头方向的新组合), 无证据时退化为 cfg 权重(均匀)。
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
    bank_ex = {}
    bank_ext, bank_ex_ext = [], {}
    _inject_tags = [x.strip() for x in
                    str(getattr(args, 'inject_pools', '') or '').split(',') if x.strip()]
    frozen = []                # FSA冻结骨架列表(中金: 超15%被禁止复用)
    # ★ 2026-09-17：冻结**记账**（{骨架: {'cnt': 第几次, 'left': 剩余代数, 'cool': 冷却计数}}）
    #   —— 有它才能做"2→4→8 代封顶 + 冷却期遗忘"；`frozen` 仍是骨架字符串列表（口径不变 ✓）
    fsa_frz = {}
    fail_lib = {}              # 失败模式库(骨架级成败滚动统计, 中金: 生成阶段排除)
    cfg = dict(DEFAULT_CFG)
    n_tested_prev = 0
    _prev_pool_map = None
    if os.path.exists(_P.STATE):
        with open(_P.STATE, 'rb') as f:
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
    f = None  # ★ 死透传：_build_fam_blacklist 内覆盖 f；避免「等号两边同名（右边先读）」的静态隐患
    block_fams, f, fam_black_txt, nd = _build_fam_blacklist(args, cfg, critic, f, frozen, prev_l1, seeds)

    # ---- 失败模式库: 载入后按滚动窗口算出本代应排除的'坏骨架' ----
    bad = _load_fail_lib(args, cfg, fail_lib)

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


# ★★★ 以下是本函数**函数体内**的设计说明（S3a 只搬位置、一字未改 ✓）
#   规则：连续 ≥2 行的论述块上移；贴行注释留在代码旁（保局部性 ✓）
    # ---- 生成候选(按B角给的五维配比) ----
    # ★gen13修复: cut为累积上界, 判重/分支原来写成 cut[i] 相加 -> 数值>1恒真,
    # 使 r<cut0+cut1+cut2 永远成立: guided(引导族)与rand(纯随机)从不会被执行,
    # 代代只在seeds内打转 -> 重复爆炸。 现改回 r<cut[2](seed三操作) / r<cut[3](引导) / 否则随机。
    # ---- 生成侧 LLM 引导(A角子代理, 中金"生成预算~20%语义引导"): ----
    # 引导位 r∈[cut2,cut3) 的候选来源 = LLM 解析池; 池空且调用未超限则按需补一次;
    # 无 key/超时/解析失败/超限 -> 回退本地 guided_expr。LLM 候选与规则候选走
    # 同一条守卫链(跨量纲/失败库/FSA/判重), 不产生旁路。
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

    _psel, _ptop, cut, m = _gen_candidates(args, cfg, seeds)
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
        # ★ S3b：守卫链已抽成 `_gen_guard(ctx, args, node, rand_only)` ✓（值全从 ctx 取 ✓）
        node, _skip = _gen_guard(ctx, args, node, rand_only)
        if _skip == 'dim':
            n_skip_dim += 1
            continue
        if _skip == 'bad':
            n_skip_bad += 1
            continue
        if _skip == 'fsa':
            n_skip_fsa += 1
            continue
        if _skip == 'fam':
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
    # ★ 回写 ctx（**原样保留** ✓）——
    #   ⚠ S3b 第一次改时，**我把 `_gen_guard` 插在了这里**（以为函数到此结束 ✗），
    #   于是这 8 行被新函数"吸走"（落到它的 `return` 之后 ⇒ 死代码 ✗）
    #   ⇒ `ctx['cands']` 再没被写 ⇒ 真实一代立刻 `KeyError: 'cands'` ✗✗
    #   ⇒ A/B 第一次跑就报出来 ✓（这正是"真动代码必须跑 A/B"的理由 ✓）
    ctx['cands'] = cands
    ctx['llm_on'] = llm_on
    ctx['llm_pool'] = llm_pool
    ctx['llm_hyp'] = llm_hyp
    ctx['n_llm_call'] = n_llm_call
    ctx['n_llm_parse'] = n_llm_parse
    ctx['n_llm_hit'] = n_llm_hit
    return False


def _gen_guard(ctx, args, node, rand_only):
    """生成阶段的**守卫链**（跨量纲 / 失败库 / FSA / 族黑名单）-> `(node, skip)` ✓

    ★ S3b（2026-09-27）：从 `_run_gen` 的循环体里**原文搬出**（R1：6 个函数超 120 行 ✗）。
      为什么签名只有 4 个参数（而不是 §七 之前担心的"参数爆炸" ✗）：
      **值全在 `ctx` 里**（`rng`/`cfg`/`cfg_r`/`frozen`/`bad`/`block_fams` 都是 ctx 的键 ✓）
      ⇒ 改传 ctx 即可 ✓ —— 当年"13~18 个参数"是因为把 **ctx 里的东西拆开传**了 ✗

    :return: `(node, skip)`；`skip` ∈ {None, 'dim', 'bad', 'fsa', 'fam'} ——
             调用方据此给对应计数器 +1 并 `continue` ✓
             （⚠ FSA 那支会**改 `node`**（重试 2 次随机探索 ✓），故 node 必须回传 ✓）
    """
    frozen = ctx['frozen']
    bad = ctx['bad']
    block_fams = ctx['block_fams']
    rng = ctx['rng']
    cfg = ctx['cfg']
    cfg_r = ctx['cfg_r']
    # 跨量纲审查(中金: 跨量纲运算拒绝): close+volume 之类荒谬组合直接重抽
    if args.dim_review > 0 and review_expr(node):
        return node, 'dim'
    # 失败模式库: 多次全败的坏骨架 -> 生成阶段自动排除(中金)
    if args.fail_rate > 0 and bad and has_frozen_skel(node, bad):
        return node, 'bad'
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
            return node, 'fsa'
    # 结构族黑名单闸(gen31): 命中上代垄断模板族 -> 重抽(rand_only 兜底豁免防死锁)
    if not rand_only and block_fams and root_fam(node) in block_fams:
        return node, 'fam'
    return node, None


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
