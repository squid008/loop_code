# -*- coding: utf-8 -*-
"""loop_eval.py — 评估/审查/生成辅助函数（2026-09-26 文件级拆分）

★ 只依赖已拆分模块 + 标准库 + 惰性 import loop_critic/loop_llm/loop_pools，不 import loop_engine。
"""
import re
import time

import numpy as np
import pandas as pd

import factor_miner as _FM
from factor_miner import START

from loop_expr import Node, collect, root_fam, FAM_QUOTA
from loop_gen import _wt, PARENT_SEL_MODES
from loop_ops import UNARY, BINARY
from loop_fields import LEAVES
from loop_metrics import rank_rows, STYLE_KEYS
from loop_pools import pool_mask
from loop_faillib import bad_skels
from loop_persist import _gate_of, _pool_best

import loop_cache as _C
import loop_paths as _P


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


def factor_stability(V, dates=None, start=START, fwd=None):
    """因子稳定性 = 相邻调仓日截面rank的相关性(均值)
    稳定性低 -> 每次调仓Top组大换血 -> 换手高 -> 费后被成本吃光
    这是 L1 必须看、只看IC会漏掉的关键指标

    ★★ 2026-09-21（前置改造）：`fwd` 原来是 `fwd=FWD` —— **默认值在 `def` 那一刻就固化了** ✗
      （Python 的经典坑 ✓）⇒ 就算 `set_fwd(20)` 改了模块全局，这个函数**还是拿 5** ✗
      ⇒ 改成 `fwd=None` + 函数内取**当前**全局 ✓（调用方传值时仍以显式值为准 ✓）
    """
    fwd = _FM.FWD if fwd is None else fwd
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
    Usub = U[np.ix_(_C.L1_ROWS, _C.L1_COLS)]
    if _C.L1_POOL_MASK is not None:
        # ★池内挖掘(§8.19): L1 的 IC = **池内 IC**。这一步是"三池并行"起作用的核心 ——
        #   目标函数里不再有全A 的小盘/低流动性溢价, 风格暴露因子在 L1 就挣不到分。
        Usub = Usub & _C.L1_POOL_MASK
    Rsub = fwd_ret[np.ix_(_C.L1_ROWS, _C.L1_COLS)]
    print(f"L1 子面板 {len(_C.L1_ROWS)}日 x {len(_C.L1_COLS)}股 "
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
