# -*- coding: utf-8 -*-
"""loop_l1.py — 阶段函数（2026-09-27 函数级拆分 S2（L1 组） · **从 loop_stage.py 逐字搬出**）

★ 为什么拆：`loop_stage.py` 曾 **1349 行**（违 R2「新文件 ≤800 行」✗，见
  `docs/maintainability.md §七`）⇒ 按阶段拆成 ≤800 行的多个文件 ✓
★ `FWD` 是**主口径快照**（副口径切换期间 `_FM.FWD` 会短暂是副值 ✗）⇒
  别名**只准在 `loop_stage.py` 定义一处** ✓，本模块**运行时读** `_S.FWD` ✓
  （**禁止** `from loop_stage import FWD` —— 那是 import 时值拷贝，`--fwd` 改不到 ✗）
"""
import loop_stage as _S
import gc
import os
import time
import numpy as np
import pandas as pd
from loop_expr import (Node, collect, skeleton, root_fam, has_frozen_skel, clone, _fsa_stats)
from loop_ops import UNARY, BINARY, ts_mean
from loop_gen import (DEFAULT_CFG, _clean_cfg, rand_expr, eval_expr, mutate, leaf_parts,
                     crossover, pick_parent, perturb, guided_expr, _build_fam_blacklist)
from loop_faillib import flib_mark
from loop_metrics import (rank_rows, decile_shape, l1_score, style_expo, STYLE_KEYS,
                          neutralize_rows, neutral_rank)
from loop_pools import pool_mask, parse_pools, pool_gate_ok
from loop_eval import (style_features, batch_ic, factor_stability, seg_verify, _run_l1, _run_l2,
                       _critic_review_prev, _load_fail_lib, _rand_explore, _gen_candidates,
                       _apply_fam_quota, _jury_deep_review, _critic_diagnose, _agg_style_diag,
                       _log_llm_hint, _critic_llm_review)
import loop_cache as _C
from loop_cache import trim_cache, trim_cache_mb
import loop_paths as _P


# ★★★ S3a（2026-09-27）：以下五段是**从本函数体内上移**的设计说明（**只挪位置、一字未改** ✓）——
#   动因：R1「函数 ≤120 行」把**注释**也算进长度 ✗，而本项目风格是"函数体内写大段论述" ✗
#   ⇒ 把**成段的**论述移到 `def` 上方（与 `combine_ok` / `pool_engines` 同写法 ✓）；
#     **贴行注释留在代码旁**（解释紧邻那一行的不动 ✓，例如 `_reuse_v` / `trim_cache_mb` 那几处 ✓）
#
# ---- ① 形状门槛标定（gen52+, 批1 P0; `--min_mono` 默认 0=关闭 ⇒ 默认零行为变化）----
# 标定(1150 条历史 L2 候选): L2 通过者 mono 中位 0.964 / 最小 0.770; 判死者中位 0.867。
# 故 `mono >= 0.75` 可拦下 ~27% 判死候选且对 19 个入库因子**零误杀**。
#
# ---- ② 去相关的意义 ----
# ★去相关: 与【已入库已知因子】相关性过高的丢弃, 强迫引擎探索新方向
#   (中金的"IC相关性<0.70"; 否则引擎会反复重新发现 ln_mktcap / amt_log)
#
# ---- ③ 去相关的对比对象 ----
# 对比对象 = 人工基准 + 【历代入库因子(state.bank)】 —— 对齐中金
# "与已入库因子IC相关<0.70"的结果闸门: 不是固定两个基准, 库扩大后
# 与新入库因子相似的候选会被拦在L2外(不靠禁叶子字段)
#
# ---- ④ `--score_mode=new` 的标定依据 ----
# 依据: 标定 1150 条历史 L2 候选, 与 L2 Calmar 的相关性 old +0.167 -> new +0.668;
#       ic_ir 本身与 L2 负相关(-0.317), 乘进去在稀释 stab 的正信号(stab 单独 +0.546)。
#       IC 仍由 `ic > min_ic` 当准入门槛, 只是不再当排序驱动。
#
# ---- ⑤ 近重复去重阈值（`--dedup_corr` 默认 0.85）的标定 ----
# gen51: 阈值 0.99 -> args.dedup_corr(默认0.85)。0.99 过松: 实测同代 F20~F23 两两
# |corr| 0.93/0.88 全数放行(4 个近重复因子同代入库)。标定: 全库 23 因子在此口径下
# 仅这两对>0.85(其余<=0.744) -> 0.85 既能拦下两对、又不误杀历史入库因子。
def _l1_filter(l1, Bsub, B, bank, bank_ext, args, _reuse_v, _min_mono, _score_mode):
    """L1 过滤：ic/stab 门槛 + 形状门槛 + 去相关 + 评分 + 近重复去重 -> 返回 l1（空则 None）"""
    cache2 = {}
    if not len(l1):
        print("L1 无候选通过, 退出")
        return None
    l1 = l1[(l1['ic'] > args.min_ic) & (l1['stab'] > args.min_stab)]
    if _min_mono > 0 and 'mono' in l1.columns:
        n_pre_mono = len(l1)
        l1 = l1[np.isfinite(l1['mono']) & (l1['mono'] >= _min_mono)]
        print(f"  [形状门槛] 十档单调性 mono>={_min_mono:g} 后剩 {len(l1)} 个 "
              f"(原 {n_pre_mono}, 拦 {n_pre_mono - len(l1)})")
        if not len(l1):
            print("L1 形状门槛后无候选, 退出")
            return None
    if args.decorr > 0:
        _t_dec = time.time()
        KNOWN = {
            'ln_mktcap': np.log(np.maximum(B['mktcap'], 1e-9)),
            'amt_log': -np.log(ts_mean(B['turnover'], 20) + 1.0),
        }
        # 用子面板算相关性(快); 已知因子也取对应子面板
        Kr = {}
        for k, v in KNOWN.items():
            vs = v[np.ix_(_C.L1_ROWS, _C.L1_COLS)]
            Kr[k] = rank_rows(vs[::_S.FWD])
        # ★ 2026-09-14（§1.8）：对照集 = 自己的 bank **+ 外部池库**（`bank_ext`，只读注入）
        #   不注入的话，跑全A 时这一层"看不见池库" ⇒ 重挖。
        for bi, bnd in enumerate(bank + bank_ext):
            try:
                vb = eval_expr(bnd, Bsub, cache2)
                Kr[f'bank{bi}'] = rank_rows(vb[::_S.FWD])
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
                v0 = v0[::_S.FWD]
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
        l1['score'] = l1_score(l1['stab'], l1['ic_ir'],
                               l1['shape_pos'] if 'shape_pos' in l1.columns else None, 'new')
    else:
        l1['score'] = l1['ic_ir'].abs() * (0.25 + 0.75 * l1['stab'].clip(0, 1))
    l1 = l1.sort_values('score', ascending=False)
    # 数值近重复去重(只对 TopN 做, 用采样指纹加速, 否则 O(n^2) 跑不动)
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
            v = rank_rows(v[::_S.FWD])[samp]
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
                rs = rank_rows(v[::_S.FWD])
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
                    _arr = np.ascontiguousarray(_v[::_S.FWD])
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
    Rsub_s, Usub_s = Rsub[::_S.FWD], Usub[::_S.FWD]
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
                FEAT_S[_k] = _sf[_k][np.ix_(_C.L1_ROWS, _C.L1_COLS)][::_S.FWD]    # 原始值(供中性化)
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
