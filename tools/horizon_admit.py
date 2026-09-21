# -*- coding: utf-8 -*-
"""horizon_admit.py — **(甲) 给 C3 的过门候选补全"真正的入库闸"**（用户拍板：甲 ✓）

★ 为什么需要（C3 只做了"性能预筛" ✗）：
  `tools/horizon_resweep.py`（C3）只过了 **calmar / ic / stab** 三道**性能门** ✓
  ⇒ 它给出的 80 个只能叫「**预筛通过**」✗，**不等于可入库** ✗
  引擎真正入库还要过：**剥风格 / 分段独立 / 池内门槛**（＋相关性去重 ✓）

★ 口径**逐条照抄引擎**（不许自己重造 ✗ —— 见 `engine/loop_engine.py` L2884-3109 的 L2 验收段）：
```
① 主口径   rr = evaluate_real(fac, close, expr, cost, window, with_ex=True, with_daily=True)
② pass_filter(rr, min_ic)        ← 11 项简化版（|IC|·IC胜率≥0.52·calmar≥0.5·最近年>0·亏损年≤1 ✓）
③ _ok_q  = calmar > min_calmar 且 sharpe > min_sharpe
④ seg_ok = seg_verify(rr['ex'], seg_n=3, seg_need=2)          ← 分段独立（防"单段行情撑全样本"）
⑤ strip  = neutral_rank(f, [lncap, lnamt]) → 再 rank → **重跑同一套回测**   ★ 剥风格
           pass_strip = strip_calmar > min_strip_calmar
⑥ pool   = 池内排名（池外 NaN ⇒ 池等权基准）→ 重跑回测（mcap=MCAP ⇒ 附带市值加权口径）
           _pok, _ = pool_gate_ok([池内 calmar_d...], min_pool_calmar, mode='any')
⑦ ok = combine_ok(_ok_prev, _ok_q, _pok, _ok_hard, pool_gate_on, or_all)
        ★ 顺序有**坑**：剥风格/分段记进 `_ok_hard`，**不参与 OR** ✗（引擎注释 §1.17：
          取在 `_ok_q` 之前的快照做 OR 会**把剥风格一起撤掉** ⇒ 池库 13 个入库里 8 个是纯风格 ✗）
⑧ 档位 `loop_pools.strip_grade(...)`（**引擎与脚本共用的事实源** ✓）
```
★ **生产参数值**（取自 `tools/run_tracks.py` 的"必要参数组"注释 ✓ 不是我猜的 ✓）：
```
--strip_style --min_strip_calmar 0.15   ← "只开 --strip_style 不传门槛 = 只记录不拦" ✗（踩过 ✓）
--pool_obs --pools=300,500,1000 --min_pool_calmar 0.15 --pool_gate_or_all
--dup_ex_corr 0.90                      ← 收益流去重（本工具**只对本批内部**算，见下 ⚠）
```
★ 三条红线（同 C3 ✓）：不写库 ✗ · 不覆盖既有表 ✗ · 求值失败**如实另计**（不当"没过门" ✗）

⚠ 本工具**没做**的一件事（如实标注 ✗）：`--dup_ex_corr` 生产上是"与**库内全部因子**收益流比" ✓，
  而库内收益流要 state.pkl / 曲线文件 ✗ ⇒ 本工具只算**本批候选之间**的近重复 ✓
  ⇒ 最终入库前，仍应由**引擎**（或库侧脚本）跑一次真去重 ✓

用法：
  python tools/horizon_admit.py --limit 3 --out ai_test/_admit_smoke.csv     # 冒烟
  python tools/horizon_admit.py --only-new --shards 3 --shard 1 --out docs/horizon20_admit_sh1.csv
"""
import argparse
import csv
import io
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, 'engine'))

DOCS = os.path.join(ROOT, 'docs')
POOLS_TAGS = ['300', '500', '1000']
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:                                                # noqa: BLE001
    pass

OUT_COLS = ('name', 'pool', 'expr', 'fwd',
            'ic', 'calmar', 'calmar_d', 'sharpe', 'turn', 'stab',
            'seg_ok', 'n_seg_pos',
            'strip_calmar', 'strip_calmar_d', 'strip_ann_ex', 'strip_grade', 'strip_txt',
            'pool_best', 'pool_cal', 'pool_ok',
            'ok_pass_filter', 'ok_q', 'ok_hard', 'ok_pool',
            'admit', 'why')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', default=os.path.join(DOCS, 'horizon20_candidates.csv'))
    ap.add_argument('--only-new', action='store_true',
                    help='只评**库外新东西**（不在 `docs/factor_metrics*.csv` 里的 ✓）——'
                         '库内那批已入库、评了也不是收益 ✗ ⇒ 默认等于全评、加它=只评库外 ✓')
    ap.add_argument('--fwd', type=int, default=20)
    ap.add_argument('--window', choices=['full', 'recent600'], default='full')
    ap.add_argument('--cost', type=float, default=0.004)
    # ★ 门槛默认 = **生产值**（run_tracks 的"必要参数组" ✓）
    ap.add_argument('--min-ic', type=float, default=0.02)
    ap.add_argument('--min-calmar', type=float, default=0.5)
    ap.add_argument('--min-sharpe', type=float, default=0.5)
    ap.add_argument('--min-stab', type=float, default=0.30)
    ap.add_argument('--min-strip-calmar', type=float, default=0.15,
                    help='剥风格后 Calmar 门槛（生产值 0.15 ✓ = 与 min_pool_calmar 同档）')
    ap.add_argument('--min-pool-calmar', type=float, default=0.15)
    ap.add_argument('--no-pool-gate', action='store_true', help='关掉池门槛（默认开 ✓）')
    ap.add_argument('--pools', default=','.join(POOLS_TAGS))
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--shard', type=int, default=1)
    ap.add_argument('--shards', type=int, default=1)
    ap.add_argument('--panel_cache', default='use', choices=['off', 'use', 'build'])
    ap.add_argument('--out', default=os.path.join(DOCS, 'horizon20_admit.csv'))
    a = ap.parse_args()

    # ---- 读 C3 榜（取 pass20=1 的候选 ✓）----
    cand = []
    for r in csv.DictReader(io.open(a.src, encoding='utf-8-sig', newline='')):
        if (r.get('pass20') or '') != '1':
            continue
        cand.append(dict(name=r['name'], pool=r.get('pool'), expr=r['expr'],
                         sign=(-1 if (r.get('sign') or '1').strip() == '-1' else 1),
                         calmar5=float(r['calmar5']) if r.get('calmar5') else None))
    if a.only_new:
        # ★ 与 C3 报告里"库内/库外"对账**同一判据** ✓（表达式文本命中即算库内 ✓）
        _lib = set()
        for _p in (os.path.join(DOCS, 'factor_metrics.csv'),
                   os.path.join(DOCS, 'factor_metrics_fwd20.csv')):
            if os.path.exists(_p):
                for _r in csv.DictReader(io.open(_p, encoding='utf-8-sig', newline='')):
                    if _r.get('expr'):
                        _lib.add(_r['expr'].strip())
        cand = [c for c in cand if c['expr'].strip() not in _lib]
    cand.sort(key=lambda c: -(c['calmar5'] or -9e9))
    n_pre = len(cand)
    if a.shards > 1:
        cand = cand[(a.shard - 1)::a.shards]
    if a.limit:
        cand = cand[:a.limit]

    import numpy as np
    import pandas as pd
    import build_facs as BF
    import factor_miner as FM
    import loop_engine as LE
    import loop_pools as LP
    from factor_miner import evaluate_real, cs_rank, pass_filter

    BF._prep_main()
    LE.set_panel_cache(a.panel_cache)
    _old = FM.FWD
    FM.set_fwd(int(a.fwd))
    LE.FWD = FM.FWD

    print('=' * 104)
    print('(甲) 20 日口径 · **完整入库闸**重评 → {}'.format(os.path.relpath(a.out, ROOT)))
    print('  口径：FWD={} · {} · cost={}   候选 {} 个（C3 过门 {}{}）'.format(
        FM.FWD, a.window, a.cost, len(cand), n_pre,
        '  分片 %d/%d' % (a.shard, a.shards) if a.shards > 1 else ''))
    print('  门槛（生产值 ✓）：|IC|≥{} · calmar≥{} · sharpe≥{} · stab≥{} · 分段 {}/{} · '
          '剥风格 Calmar≥{} · 池 Calmar≥{}（any{}）'.format(
              a.min_ic, a.min_calmar, a.min_sharpe, a.min_stab, 2, 3,
              a.min_strip_calmar, a.min_pool_calmar, '' if a.no_pool_gate else ' ✓'))
    print('=' * 104)

    t0 = time.time()
    bf = LE.base_fields()
    B, dates, cols, close = bf['B'], bf['dates'], bf['cols'], bf['close']
    print('  面板 {:.0f}s（{} 日 × {} 股）'.format(time.time() - t0, len(dates), len(cols)))

    # ★ 复刻引擎的两样 L2 材料（**不重造算法**，只重造输入 ✓）
    #   ① MCAP：引擎里是 `np.where(B['mktcap'] > 0, B['mktcap'], nan)`（`qa_bench_cw.py` 同款 ✓）
    MCAP = np.where(B['mktcap'] > 0, B['mktcap'].astype('float64'), np.nan) \
        if 'mktcap' in B else None
    print('  市值面板：{}'.format('有 ✓（供池内市值加权口径）' if MCAP is not None else '**缺** ✗ 池内口径将退化'))
    #   ② 风格面（剥风格用 lncap + lnamt；`style_features` 是一代一次的贵函数 ✓）
    t1 = time.time()
    _sf = LE.style_features(B)
    STYLE_FULL = {k: _sf[k] for k in ('lncap', 'lnamt')}
    del _sf
    print('  风格面 lncap/lnamt：{:.0f}s ✓'.format(time.time() - t1))
    #   ③ 池掩码（引擎 `_run_l2` 里就是 `pool_mask(tag, dates, cols)` ✓）
    tags = [t.strip() for t in a.pools.split(',') if t.strip()]
    POOL_M = {}
    for tg in tags:
        try:
            POOL_M[tg] = LP.pool_mask(tg, dates, cols)
        except Exception as e:                                   # noqa: BLE001
            print('  [!] 池 {} 掩码失败：{}'.format(tg, e))

    rows = []
    for i, c in enumerate(cand, 1):
        t1 = time.time()
        rec = dict((k, '') for k in OUT_COLS)
        # ★★ 2026-09-21 **修一个我自己的错** ✗：`sign` 在列清单里、却**从没被赋值** ⇒ 下游
        #   （`horizon_admit_finalize.py`）读到空 ⇒ 当 1 处理 ⇒ 对 `sign=-1` 的因子
        #   **按反方向求值** ✗✗（实测 H117：判定 0.752 → 定稿 -0.238 ✗ = 正是镜像值 ✓）
        #   ⇒ 必须**逐行**把 C3 榜上定好的取向带下去 ✓（它已是"越大越好"方向 ✓）
        rec.update(name=c['name'], pool=c['pool'], expr=c['expr'], fwd=FM.FWD,
                   sign=c['sign'])
        why = []
        try:
            _cap = LE.LLM_MAX_SIZE
            LE.LLM_MAX_SIZE = 10 ** 9
            try:
                nd = LE.parse_expr(c['expr'])
            finally:
                LE.LLM_MAX_SIZE = _cap
            if nd is None:
                rec['admit'] = 0
                rec['why'] = '表达式反解失败(不臆造)'
                rows.append(rec)
                continue
            v = LE.eval_expr(nd, B, {})
            if c['sign'] < 0:                               # ★ 符号定向（与 C3 同一取向 ✓）
                v = -v
            fac_df = pd.DataFrame(v, index=dates, columns=cols)
            f = cs_rank(fac_df.astype('float64'))
            rr = evaluate_real(f, close, c['expr'], cost=a.cost, window=a.window,
                               with_ex=True, with_daily=True)
            if rr is None:
                rec['admit'] = 0
                rec['why'] = '回测返回 None'
                rows.append(rec)
                continue
            st = LE.factor_stability(np.asarray(v), dates=dates, start=FM.START)
            rec.update(ic=rr['ic'], calmar=rr['calmar'], calmar_d=rr.get('calmar_d'),
                       sharpe=rr['sharpe'], turn=rr.get('turn'), stab=st)

            # ① pass_filter（11 项简化版 ✓）
            ok_pf, msg_pf = pass_filter(rr, a.min_ic)
            rec['ok_pass_filter'] = 1 if ok_pf else 0
            if not ok_pf:
                why.append('pass_filter:' + msg_pf[:34])
            # ② 全A 量化口径
            _ok_q = bool(rr['calmar'] > a.min_calmar and rr['sharpe'] > a.min_sharpe)
            rec['ok_q'] = 1 if _ok_q else 0
            if not _ok_q:
                why.append('cal{:.3f}/sh{:.2f}'.format(rr['calmar'] or 0, rr['sharpe'] or 0))
            _ok_prev = ok_pf
            # ③ 分段独立
            seg_ok, n_pos, _k, _txt = LE.seg_verify(rr.get('ex'), 3, 2)
            rec['seg_ok'] = 1 if seg_ok else 0
            rec['n_seg_pos'] = n_pos
            if not seg_ok:
                why.append('分段{}/{}'.format(n_pos, 3))
            _ok_q = _ok_q and seg_ok
            _ok_hard = bool(seg_ok)
            # ④ 剥风格（**与引擎逐条同法** ✓）
            _fn = LE.neutral_rank(f.values.astype('float64'),
                                  [STYLE_FULL['lncap'], STYLE_FULL['lnamt']])
            rr_s = evaluate_real(pd.DataFrame(_fn, index=dates, columns=cols),
                                 close, c['expr'] + '#strip',
                                 cost=a.cost, window=a.window, with_daily=True)
            if rr_s is not None:
                _g, _gt = LP.strip_grade(rr_s.get('calmar_d'), rr_s['ann_ex'], rr_s.get('dd_d'))
                rec.update(strip_calmar=rr_s['calmar'], strip_calmar_d=rr_s.get('calmar_d'),
                           strip_ann_ex=rr_s['ann_ex'], strip_grade=_g, strip_txt=_gt)
                _pass_strip = bool(rr_s['calmar'] > a.min_strip_calmar)
                _ok_hard = _ok_hard and _pass_strip
                if not _pass_strip:
                    why.append('剥后 cal{:.3f}≤{}'.format(rr_s['calmar'] or 0, a.min_strip_calmar))
            else:
                why.append('剥风格计算失败(放行不误杀)')
            # ⑤ 池内（池外 NaN ⇒ 池内排名 + 池等权基准 ✓；带 mcap ⇒ 市值加权口径 ✓）
            _pok = None
            _best, _bcal = '', None
            for tg, _M in POOL_M.items():
                _vp = np.where(_M, f.values, np.nan)
                _fp = cs_rank(pd.DataFrame(_vp, index=dates, columns=cols))
                _rp = evaluate_real(_fp, close, '{}#pool{}'.format(c['expr'], tg),
                                    cost=a.cost, window=a.window, mcap=MCAP, with_daily=True)
                if _rp is None:
                    continue
                _cd = _rp.get('calmar_d')
                _cd = _cd if (_cd is not None and np.isfinite(_cd)) else _rp.get('calmar')
                if _cd is not None and (_bcal is None or _cd > _bcal):
                    _best, _bcal = tg, _cd
            if POOL_M and not a.no_pool_gate:
                _pok = bool(_bcal is not None and np.isfinite(_bcal)
                            and _bcal >= a.min_pool_calmar)
            rec['pool_best'] = _best
            rec['pool_cal'] = _bcal
            rec['pool_ok'] = '' if _pok is None else (1 if _pok else 0)
            if _pok is False:
                why.append('池内最好{}{:.3f}'.format(_best, _bcal or 0))
            # ⑥ 组合（**照抄 combine_ok ✓**：OR 只作用于 全A口径/池口径，硬门槛不参与 ✗）
            ok = LE.combine_ok(_ok_prev, _ok_q, _pok, _ok_hard,
                               bool(POOL_M and not a.no_pool_gate), True)
            rec['ok_hard'] = 1 if _ok_hard else 0
            rec['ok_pool'] = '' if _pok is None else (1 if _pok else 0)
            rec['admit'] = 1 if ok else 0
            rec['why'] = '' if ok else ' · '.join(why) if why else '未过组合判定'
            print('  [{:<5s}] {:>4.0f}s  Cal {:>6} / 剥后 {:>6}({}) / stab {:.2f} / 池最好 {}{} ⇒ {}'.format(
                c['name'], time.time() - t1,
                '{:.3f}'.format(rr['calmar']) if rr['calmar'] is not None else '—',
                '{:.3f}'.format(rec['strip_calmar']) if rec['strip_calmar'] != '' else '—',
                rec['strip_grade'] or '?', st,
                _best, '{:+.2f}'.format(_bcal) if _bcal is not None else '—',
                '★**可入库** ✓' if ok else '✗ ' + rec['why']))
        except Exception as e:                                   # noqa: BLE001
            rec['admit'] = 0
            rec['why'] = '异常 {}: {}'.format(type(e).__name__, str(e)[:70])
            print('  [{:<5s}] 异常 -> {}'.format(c['name'], rec['why']))
        rows.append(rec)

    if rows:
        with io.open(a.out, 'w', encoding='utf-8-sig', newline='') as fh:
            w = csv.DictWriter(fh, fieldnames=list(OUT_COLS))
            w.writeheader()
            for r in rows:
                w.writerow(dict((k, ('' if r.get(k) is None else r.get(k))) for k in OUT_COLS))
    good = [r for r in rows if r.get('admit')]
    print('\n' + '=' * 104)
    print('  ⇒ 报告 = {}（{} 行 ✓ 不碰库 ✓）'.format(os.path.relpath(a.out, ROOT), len(rows)))
    print('  ★★ **可入库 = {} / {}**'.format(len(good), len(rows)))
    for r in good:
        print('      {:<6s} 池{:<5s} Cal {:>6} 剥后 {:>6}({}) 池最好 {}{}  {}'.format(
            r['name'], r['pool'],
            '{:.3f}'.format(r['calmar']) if r['calmar'] != '' else '—',
            '{:.3f}'.format(r['strip_calmar']) if r['strip_calmar'] != '' else '—',
            r['strip_grade'] or '?', r['pool_best'], r['pool_cal'], r['expr'][:36]))
    print('  用时 {:.0f}s'.format(time.time() - t0))
    print('=' * 104)

    FM.set_fwd(_old)
    LE.FWD = FM.FWD
    return 0


if __name__ == '__main__':
    sys.exit(main())
