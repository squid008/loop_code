# -*- coding: utf-8 -*-
"""horizon_admit_finalize.py — **(丁) 定稿**：把"可入库"那批的**入库所需全部字段**算全 ✓

★ 与 `horizon_admit.py` 的区别（**不重复造** ✗，各司其职 ✓）：
  · `horizon_admit.py`（判定用 ✓）：对 **53** 个候选跑全闸 ⇒ 输出"**过/不过**" + 拦因 ✓
  · 本工具（**入库用** ✓）：只对**已判定可入库**的那批 ⇒ 补齐 `_lib_sync` 写文档**真正要的字段**：
      `ic / ic_ir / ann_ex / dd / calmar / sharpe / last_yr / turn / neg_yr / cost`（`met` 行 ✓）
      + `cat / leaf`（家族/叶子 ✓）+ `sign`（**下游必读** ✗）+ **逐池**明细（派生池标签 ✓）
      + 剥风格档位元组（写文档 ✓）
  ⚠ 为什么要**重算**而不是复用判定表：判定表列不全 ✗（缺 ic_ir/ann_ex/dd/last_yr/neg_yr ✓），
    而"文档里的数字"必须与"判定时的数字"**同一次评估**产出 ✓（否则两处数字漂移 ✗）

输出（**都不碰库** ✓）：
  · `docs/horizon20_admit_final.csv`  ⇒ 人看 + 留档 ✓
  · `<--json>`（默认 `ai_test/_admit_final.json`）⇒ **写库步骤的输入**（含 node 序列化 ✓）

用法：python tools/horizon_admit_finalize.py            # 11 个 ⇒ 约 12 分钟
"""
import argparse
import csv
import io
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, 'engine'))
DOCS = os.path.join(ROOT, 'docs')
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:                                                # noqa: BLE001
    pass

OUT_COLS = ('name', 'pool', 'gen', 'expr', 'sign', 'cat', 'leaf',
            'ic', 'ic_ir', 'ic_win', 'ann_ex', 'dd', 'calmar', 'calmar_d',
            'sharpe', 'last_yr', 'turn', 'n_rebal', 'neg_yr', 'cost', 'stab',
            'strip_grade', 'strip_calmar', 'strip_calmar_d', 'strip_ann_ex', 'strip_dd_d',
            'strip_txt', 'pool_tag', 'pool_detail')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', default=os.path.join(DOCS, 'horizon20_admit.csv'))
    ap.add_argument('--fwd', type=int, default=20)
    ap.add_argument('--window', choices=['full', 'recent600'], default='full')
    ap.add_argument('--cost', type=float, default=0.004)
    ap.add_argument('--pools', default='300,500,1000')
    ap.add_argument('--panel_cache', default='use', choices=['off', 'use', 'build'])
    ap.add_argument('--out', default=os.path.join(DOCS, 'horizon20_admit_final.csv'))
    ap.add_argument('--json', default=os.path.join(ROOT, 'ai_test', '_admit_final.json'))
    a = ap.parse_args()

    # ★★ 2026-09-21 **修 sign 来源** ✗：判定表的 `sign` 列曾漏赋值（已修 ✓），但更稳的做法是
    #   **以 C3 榜为准** ✓ —— 那里是"用哪个取向求值"的**权威定义**（`horizon_resweep.py` 定的 ✓）。
    #   ⚠ 取不到就**报错跳过**，绝不默认 1 ✗ —— 实测代价：`sign=-1` 的因子会被**反向求值**，
    #     指标全部镜像（H117 判定 0.752 → 定稿 -0.238 ✗），而且**不报错** ✓ 正是本项目最忌那类坑 ✓
    c3 = {}
    _c3p = os.path.join(DOCS, 'horizon20_candidates.csv')
    if os.path.exists(_c3p):
        for r in csv.DictReader(io.open(_c3p, encoding='utf-8-sig', newline='')):
            if r.get('expr'):
                c3[r['expr'].strip()] = (int(r.get('sign') or 1), r.get('gen5') or '')
    cand, nosign = [], []
    for r in csv.DictReader(io.open(a.src, encoding='utf-8-sig', newline='')):
        if (r.get('admit') or '') != '1':
            continue
        e = (r.get('expr') or '').strip()
        sg = c3.get(e, (None, None))[0]
        if sg is None:
            nosign.append(r.get('name'))
            continue
        cand.append(dict(name=r['name'], pool=r.get('pool') or 'all', expr=e, sign=sg,
                         gen=(c3.get(e, (None, ''))[1] or r.get('gen5') or '')))
    if nosign:
        print('  ✗ **{} 个候选在 C3 榜上查不到 sign** ⇒ 跳过（不臆造取向 ✓）：{}'
              .format(len(nosign), ', '.join(nosign[:8])))
    print('=' * 100)
    print('(丁) 入库定稿：{} 个（来源 {} 的 admit=1 ✓）'.format(
        len(cand), os.path.relpath(a.src, ROOT)))
    print('=' * 100)
    if not cand:
        return 0

    import numpy as np
    import pandas as pd
    import build_facs as BF
    import factor_miner as FM
    import loop_engine as LE
    import loop_pools as LP
    from factor_miner import evaluate_real, cs_rank

    BF._prep_main()
    LE.set_panel_cache(a.panel_cache)
    _old = FM.FWD
    FM.set_fwd(int(a.fwd))
    LE.FWD = FM.FWD

    t0 = time.time()
    bf = LE.base_fields()
    B, dates, cols, close = bf['B'], bf['dates'], bf['cols'], bf['close']
    MCAP = np.where(B['mktcap'] > 0, B['mktcap'].astype('float64'), np.nan) \
        if 'mktcap' in B else None
    _sf = LE.style_features(B)
    STYLE_FULL = {k: _sf[k] for k in ('lncap', 'lnamt')}
    del _sf
    POOL_M = {}
    for tg in [t.strip() for t in a.pools.split(',') if t.strip()]:
        try:
            POOL_M[tg] = LP.pool_mask(tg, dates, cols)
        except Exception as e:                                   # noqa: BLE001
            print('  [!] 池 {} 掩码失败：{}'.format(tg, e))
    print('  面板 + 风格面 + {} 个池掩码：{:.0f}s'.format(len(POOL_M), time.time() - t0))

    rows, payload = [], []
    for i, c in enumerate(cand, 1):
        t1 = time.time()
        try:
            _cap = LE.LLM_MAX_SIZE
            LE.LLM_MAX_SIZE = 10 ** 9
            try:
                nd = LE.parse_expr(c['expr'])
            finally:
                LE.LLM_MAX_SIZE = _cap
            if nd is None:
                print('  [{:<5s}] 反解失败 -> 跳过 ✗'.format(c['name']))
                continue
            v = LE.eval_expr(nd, B, {})
            if c['sign'] < 0:
                v = -v
            f = cs_rank(pd.DataFrame(v, index=dates, columns=cols).astype('float64'))
            rr = evaluate_real(f, close, c['expr'], cost=a.cost, window=a.window,
                               with_ex=True, with_daily=True)
            if rr is None:
                print('  [{:<5s}] 回测 None -> 跳过 ✗'.format(c['name']))
                continue
            st = LE.factor_stability(np.asarray(v), dates=dates, start=FM.START)
            yr = rr.get('yr') or {}
            neg_yr = sum(1 for x in yr.values() if x <= 0)
            leaf_s, cat_s = LE.leaf_parts(nd)
            # 剥风格（与引擎同法 ✓）
            _fn = LE.neutral_rank(f.values.astype('float64'),
                                  [STYLE_FULL['lncap'], STYLE_FULL['lnamt']])
            rr_s = evaluate_real(pd.DataFrame(_fn, index=dates, columns=cols), close,
                                 c['expr'] + '#strip', cost=a.cost, window=a.window,
                                 with_daily=True)
            sg_k = sg_t = None
            if rr_s is not None:
                sg_k, sg_t = LP.strip_grade(rr_s.get('calmar_d'), rr_s['ann_ex'],
                                            rr_s.get('dd_d'))
            # 逐池（供 derive_tag ✓）
            okp, detail = {}, []
            for tg, _M in POOL_M.items():
                _vp = np.where(_M, f.values, np.nan)
                _fp = cs_rank(pd.DataFrame(_vp, index=dates, columns=cols))
                _rp = evaluate_real(_fp, close, '{}#pool{}'.format(c['expr'], tg),
                                    cost=a.cost, window=a.window, mcap=MCAP, with_daily=True)
                if _rp is None:
                    continue
                _cd = _rp.get('calmar_d')
                _cd = _cd if (_cd is not None and np.isfinite(_cd)) else _rp.get('calmar')
                okp[tg] = bool(np.isfinite(_rp['ann_ex']) and _rp['ann_ex'] > LP.TAG_POOL_FLOOR
                               and _cd is not None and np.isfinite(_cd)
                               and _cd >= LP.TAG_POOL_FLOOR_CAL)
                detail.append(dict(pool=tg, ann_ex=float(_rp['ann_ex']),
                                   calmar=float(_cd) if _cd is not None else None,
                                   ann_ex_cw=float(_rp.get('ann_ex_cw')) if _rp.get('ann_ex_cw') is not None
                                   and np.isfinite(_rp.get('ann_ex_cw')) else None))
            _cd0 = rr.get('calmar_d')
            _cd0 = _cd0 if (_cd0 is not None and np.isfinite(_cd0)) else rr['calmar']
            oka = bool(np.isfinite(rr['ann_ex']) and rr['ann_ex'] > 0
                       and _cd0 is not None and np.isfinite(_cd0) and _cd0 >= LP.TAG_CAL_MIN)
            tag = LP.derive_tag(oka, okp, sorted(POOL_M.keys()))
            rec = dict(name=c['name'], pool=c['pool'], gen=c['gen'], expr=c['expr'],
                       sign=c['sign'], cat=cat_s, leaf=leaf_s,
                       ic=rr['ic'], ic_ir=rr['ic_ir'], ic_win=rr['ic_win'],
                       ann_ex=rr['ann_ex'], dd=rr['dd'], calmar=rr['calmar'],
                       calmar_d=rr.get('calmar_d'), sharpe=rr['sharpe'],
                       last_yr=rr['last_yr'], turn=rr.get('turn'), n_rebal=rr.get('n_rebal'),
                       neg_yr=neg_yr, cost=a.cost, stab=st,
                       strip_grade=sg_k, strip_txt=sg_t,
                       strip_calmar=(rr_s['calmar'] if rr_s else None),
                       strip_calmar_d=(rr_s.get('calmar_d') if rr_s else None),
                       strip_ann_ex=(rr_s['ann_ex'] if rr_s else None),
                       strip_dd_d=(rr_s.get('dd_d') if rr_s else None),
                       pool_tag=tag, pool_detail=json.dumps(detail, ensure_ascii=False))
            rows.append(rec)
            payload.append(dict(name=c['name'], pool=c['pool'], gen=c['gen'], expr=c['expr'],
                                sign=c['sign'], cat=cat_s, leaf=leaf_s, pool_tag=tag,
                                strip_grade=sg_k, strip_txt=sg_t,
                                node=LE.node_to_dict(nd),
                                res=dict((k, (None if rec[k] is None else
                                              (float(rec[k]) if isinstance(rec[k], (int, float, np.floating))
                                               else rec[k])))
                                         for k in ('ic', 'ic_ir', 'ann_ex', 'dd', 'calmar',
                                                   'sharpe', 'last_yr', 'turn', 'neg_yr', 'cost',
                                                   'cat', 'leaf', 'expr'))))
            print('  [{:<5s}] {:>4.0f}s  Cal {:>6} / 剥后 {:>6}({}) / 池标签 {} / 负年 {}'
                  .format(c['name'], time.time() - t1,
                          '{:.3f}'.format(rr['calmar']) if rr['calmar'] is not None else '—',
                          '{:.3f}'.format(rr_s['calmar'])
                          if (rr_s and rr_s['calmar'] is not None) else '—',
                          sg_k or '?', tag, neg_yr))
        except Exception as e:                                   # noqa: BLE001
            print('  [{:<5s}] 异常 {}: {}'.format(c['name'], type(e).__name__, str(e)[:70]))

    if rows:
        with io.open(a.out, 'w', encoding='utf-8-sig', newline='') as fh:
            w = csv.DictWriter(fh, fieldnames=list(OUT_COLS))
            w.writeheader()
            for r in rows:
                w.writerow(dict((k, ('' if r.get(k) is None else r.get(k))) for k in OUT_COLS))
        with io.open(a.json, 'w', encoding='utf-8') as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=1)
    print('\n  ⇒ {}\n  ⇒ {}（写库步骤的输入 ✓）\n  用时 {:.0f}s'.format(
        os.path.relpath(a.out, ROOT), os.path.relpath(a.json, ROOT), time.time() - t0))
    FM.set_fwd(_old)
    LE.FWD = FM.FWD
    return 0


if __name__ == '__main__':
    sys.exit(main())
