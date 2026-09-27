# -*- coding: utf-8 -*-
"""loop_l2.py — L2 阶段（2026-09-27 文件级拆分 · **从 loop_stage.py 逐字搬出**）

★ 为什么拆：`loop_stage.py` 曾 **1349 行**（违 R2「新文件 ≤800 行」✗，见
  `docs/maintainability.md §七`）。本次只搬 **L2 组** 3 个函数，**逐字未改** ✓
★ `_S.FWD` 是**主口径快照**（副口径切换期间 `_FM.FWD` 会短暂是副值 ✗）⇒
  别名**只准在 `loop_stage.py` 定义一处** ✓，本模块**运行时读** `_S.FWD` ✓
  （**禁止** `from loop_stage import _S.FWD` —— 那是 import 时值拷贝，`--fwd` 改不到 ✗）
"""
import loop_stage as _S
import gc
import time
import numpy as np
import pandas as pd
import factor_miner as _FM
from factor_miner import evaluate_real, cs_rank, pass_filter, get_universe, START
from loop_gen import (DEFAULT_CFG, _clean_cfg, rand_expr, eval_expr, mutate, leaf_parts,
                     crossover, pick_parent, perturb, guided_expr, _build_fam_blacklist)
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
from cost_presets import cost_label


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
    #    · ⚠⚠ **`_S.FWD` 必须在 finally 里复原** ✗✗ —— 它是模块全局，
    #      `evaluate_real` 在**调用时**读它（实测确认 ✓：`fwd_ret=(close.shift(-(1+_S.FWD))…)` 在函数体内 ✓）
    #      ⇒ 一旦中途异常而不复原，**后面所有候选都会按副口径评估** ✗ 且**不报错** ✓
    if args.dual_fwd and rr is not None:
        try:
            # ⚠⚠ **只切 `factor_miner.FWD`，不碰本模块的 `_S.FWD`** ✗ ——
            #   本模块的 `_S.FWD` 只在**候选循环之前**的预计算里用（`[::_S.FWD]` 切片 ✓），
            #   而求值读的是 `factor_miner` 自己的全局 ✓ ⇒ 不需要动它 ✓
            #   ★ 而且**不能**在函数里裸写 `_S.FWD = …` ✗：没有 `global` 声明 ⇒
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
            # ★★ 复原主口径：`_S.FWD` 是本轮主口径（5 日 ✓ 由 `--fwd` 同步块设定 ✓）
            #   必须在 finally ⇒ 中途异常也要复原 ✗（否则后续候选全按副口径 ✓ 且静默 ✓）
            _FM.set_fwd(int(_S.FWD))
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
        # ⚠ `pool_rows.extend(pool_rec)` **不在这里做** —— 它是**调用方** `_run_l2_phase` 的局部变量 ✗
        #   （2026-09-26 真事故：搬函数时把它留在这儿 ⇒ 每次 L2 都 `NameError: pool_rows` 被
        #    `except` 吞掉 ⇒ **一个候选都入不了库** ✗✗）⇒ 已移到调用方紧接调用之后 ✓
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
            # ★ 池内明细(长表) 落 `pool_rows` —— 原在 `_l2_pool_tags` 里（那是**调用方局部** ✗），
            #   2026-09-26 移回调用方；`POOL_M` 关或 `rr is None` 时 `pool_rec` 本就是空表 ⇒ 逐字等价 ✓
            pool_rows.extend(pool_rec)
            del f
            gc.collect()
        except Exception as e:
            print(f"  [{j}] ERR {type(e).__name__}: {e}")   # ★ 带上消息（原来只有类型，排查时看不到名字 ✗）
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
        _hzn = int(_S.FWD)
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
