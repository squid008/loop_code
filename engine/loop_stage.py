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
            vs = v[np.ix_(_C.L1_ROWS, _C.L1_COLS)]
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
            v0 = _C.VCACHE.get(r['expr']) if _reuse_v else None
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
            trim_cache(cache2, _C.CACHE2_MAX)             # 去相关缓存容量控制(防OOM)
            trim_cache_mb(cache2, _C.CACHE2_MB)           # ★ 治本: 字节上限 ✓
        print(f"去相关(|corr|<={args.decorr} vs {len(Kr)}个已知因子) 后剩 "
              f"{len(keep_rows)} 个 (原 {len(l1)})")
        print(f"  [计时] 去相关 用时 {time.time() - _t_dec:.0f}s "
              f"(复用 L1 值 {n_hit}/{len(l1)} 个, 缓存 {_C._VREUSE_MB[0]:.0f}MB)", flush=True)
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
        vc = _C.VCACHE.get(r['expr']) if _reuse_v else None
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
        trim_cache(cache2, _C.CACHE2_MAX)                 # 去重缓存容量控制(防OOM)
        trim_cache_mb(cache2, _C.CACHE2_MB)               # ★ 治本: 字节上限 ✓
    print(f"\nL1 通过 {len(l1)} 个, 取Top{TOPN}近重复去重(|corr|>{args.dedup_corr:g})"
          f"拦 {n_dup} -> 剩 {len(dedup)} 个")
    print(f"  [计时] 近重复去重 用时 {time.time() - _t_dd:.0f}s "
          f"(复用 L1 值 {n_hit2}/{TOPN} 个)", flush=True)
    _C.VCACHE.clear()                                      # 去相关/去重用完即释放(防与 L2 叠加占内存)
    _C._VREUSE_MB[0] = 0.0
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
    #   ⇒ 取"子面板里任一字段"的真实 dtype/形状算单条 MB，再把批大小压到 `_C.BATCH_MB` 以内 ✓
    try:
        _k0 = next(iter(Bsub))
        _a0 = np.asarray(Bsub[_k0])
        _per_mb = float(_a0.size) * float(_a0.dtype.itemsize) / 1048576.0
        if _per_mb > 0:
            _cap = int(max(4, _C.BATCH_MB / _per_mb))
            if BATCH > _cap:
                print('  [内存预算] L1 批 %d → %d（单条 %.1f MB × 批 ≤ %.0f MB ✓ 治本: 宽池不再一批吃 2 GB ✗）'
                      % (BATCH, _cap, _per_mb, _C.BATCH_MB), flush=True)
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
                v = eval_expr(nd, Bsub, _C._LRU)         # 子面板 + 全局LRU(跨批复用)
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
            #   原来只在"**每批结束**"裁一次（下面 `trim_cache(_C._LRU, _C.LRU_MAX)` ✓）
            #   ⇒ 一批之内 `_C._LRU` 能一路涨到第一个峰值（实测第一批就顶到 8.9 GB ✗，
            #     改之前更是 12.5~14.8 GB 反复 ✗）⇒ 每 8 个候选就裁一次 ✓
            #   代价：`trim_cache_mb` 只是把 `nbytes` 加起来（O(条数) ✓）⇒ 可忽略 ✓
            if i and (i % 8) == 0:
                trim_cache_mb(_C._LRU, _C.LRU_MB)
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
                if _C._VREUSE_MB[0] >= _C._VREUSE_CAP_MB:
                    break
                if _d_['ic'] > args.min_ic and _d_['stab'] > args.min_stab:
                    _arr = np.ascontiguousarray(_v[::FWD])
                    _C.VCACHE[_d_['expr']] = _arr
                    _C._VREUSE_MB[0] += _arr.nbytes / 1e6
        n_eval += len(vals)
        del vals, IC
        gc.collect()
        trim_cache(_C._LRU, _C.LRU_MAX)                      # LRU 容量控制(防OOM)
        trim_cache_mb(_C._LRU, _C.LRU_MB)                    # ★ 治本: 字节上限(池越宽单条越大 ✗)
    print(f"L1 求值完成 {n_eval} 个, 用时 {time.time()-t_l1:.0f}s "
          f"({(time.time()-t_l1)/max(n_eval,1):.2f}s/候选)")
    _C._LRU.clear()                                       # L1 结束: 释放跨批子树缓存
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
    _C.VCACHE.clear()
    _C._VREUSE_MB[0] = 0.0
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
                FEAT_S[_k] = _sf[_k][np.ix_(_C.L1_ROWS, _C.L1_COLS)][::FWD]    # 原始值(供中性化)
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
