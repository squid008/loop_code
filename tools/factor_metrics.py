# -*- coding: utf-8 -*-
"""factor_metrics.py — 算齐每个入库因子的**全部费后指标**（含"本身"口径）→ `docs/factor_metrics.csv`

## 为什么要有它（用户 2026-09-16 之问）
看板「因子库」点开一个因子时，用户要看到：
**超额 · 超额卡玛 · 超额夏普 · 超额最大回撤 + 本身的年化 / 卡玛 / 夏普 / 最大回撤 +
最近年 · 单期换手 · 负年**。
而引擎在**入库当期**只把其中一部分写进了 `factor_library*.md` 的明细行（**超额**那几项）；
**"本身"口径（组合自身净值）从来没落盘** ⇒ 明细里查不到 ✗
⇒ 本工具**离线重算**，结果写成**独立派生文件**（**不改任何 md** —— 与项目"派生视图"惯例一致）✓

## 口径（务必与 md 明细行一致，**别混**）
  · `ann_ex / dd / calmar / sharpe`                = **超额**口径（组合腿 − 池内等权基准腿）
  · `ann_top / dd_top / calmar_top / sharpe_top`   = **组合自身**口径（Top10% 等权那一腿）
  · `dd_d / calmar_d / sharpe_d`                   = 同一策略的**日频**打点（回撤不被低估, §1.19）
  · `last_yr` = 最近一年**超额** · `neg_yr` = 年度超额 ≤0 的年数 · `turn` = 单期换手

## 用法
    python tools/factor_metrics.py                    # 全量重算（约 8~12 分钟）
    python tools/factor_metrics.py --only-new         # 只补 CSV 里还没有的（增量）
    python tools/factor_metrics.py --limit=2          # 冒烟
    python tools/factor_metrics.py --panel_cache=use  # 复用只读面板缓存（载入快 16x）

★ 复用 `build_facs.py` 的公共件（`parse_library` / `load_bank_nodes` / `_prep_main` / `_merge_csv` …）
  —— **不复制实现**，避免两处口径漂移 ✓
"""
import argparse
import csv
import io
import os
import sys
import time

import numpy as np

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DOCS = os.path.join(ROOT, 'docs')
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, 'engine'))

COLS = ['name', 'pool',
        # ★★ 2026-09-17（用户："想看历史编号的费后指标/曲线"）：新增 `in_bank` 列（1=在 state.bank，
        #   0=**已移出当前库的历史编号**）。为什么必须是**显式列**而不是"表里有就是在库"：
        #   一旦把历史编号也补进来，"不在表里 = 已移出"这条推断就**失效**了 ✗
        #   （API 原来正是靠"表条数 == 当前库条数"来推的 —— 见 `factors.library()` 的 `inbank_known`）
        'in_bank', 'gen', 'expr', 'sign', 'ic', 'ic_doc', 'ic_ir', 'ic_win',
        # —— 超额口径 ——
        'ann_ex', 'dd', 'calmar', 'sharpe',
        # —— 组合自身口径（2026-09-16 引擎新增字段）——
        'ann_top', 'dd_top', 'calmar_top', 'sharpe_top',
        # —— 日频打点（风险不被低估；⚠ 与上面两组的**配对关系**见 COLS 注释）——
        #   `dd_d/calmar_d/sharpe_d`            = **超额**口径的日频（与 ann_ex/dd/calmar/sharpe 配对）
        #   `dd_top_d/calmar_top_d/sharpe_top_d` = **组合自身**口径的日频（与 ann_top/dd_top/… 配对）
        #   ★ 恒等式：`dd_d <= dd` 与 `dd_top_d <= dd_top`；**不能**拿 `dd_d` 与 `dd_top` 比 ✗
        'dd_d', 'calmar_d', 'sharpe_d',
        'dd_top_d', 'calmar_top_d', 'sharpe_top_d',
        # —— 其他 ——
        'last_yr', 'turn', 'neg_yr', 'n_rebal',
        # ★★ 2026-09-16（用户要求「统一口径要加上**回测区间**，不然不同区间口径不可比」）：
        #   每行记录自己的**回测首/末交易日**（int YYYYMMDD）—— 将来换数据版本/改 START 时，
        #   一眼能看出哪些行是老区间算的 ⇒ 不可比的行不会被误当可比 ✗
        'bt_start', 'bt_end']


def main():
    ap = argparse.ArgumentParser()
    # ★★ 2026-09-18：默认池从 `loop_pools.POOLS` **派生**（原来硬编码 ⇒ 漏了 50 池 ✗）
    import loop_pools as _LP
    ap.add_argument('--pools', default=_LP.tool_pools())
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--only-new', action='store_true',
                    help='只补 `factor_metrics.csv` 里还没有的因子（增量；已算的跳过）')
    ap.add_argument('--include_history', action='store_true',
                    help='★ 也补**已移出当前库的历史编号**（从库文档取公式反向解析；'
                         '默认只算 state.bank = 当前有效库）')
    ap.add_argument('--cost', type=float, default=0.004, help='往返成本（默认 0.004 = 引擎主用档）')
    ap.add_argument('--window', type=int, default=5)
    ap.add_argument('--panel_cache', default='off', choices=['off', 'use', 'build'])
    ap.add_argument('--out', default=os.path.join(DOCS, 'factor_metrics.csv'))
    ap.add_argument('--ic_tol', type=float, default=0.002,
                    help='IC 自检容差：与**库文档/归档**里记录的 IC 差超过它就报警 '
                         '(口径没对齐时必须吼出来，否则落地的是错的数)')
    a = ap.parse_args()

    import pandas as pd
    import build_facs as BF
    LE = BF._prep_main()
    LE.set_panel_cache(a.panel_cache)
    from factor_miner import evaluate_real, cs_rank

    # ---- 收集：**以 state.bank 为权威**（真正在库里的因子），文档提供 F 编号/IC 参照 ----
    #   ★ 2026-09-17：`--include_history` 时**额外**补"库文档里有、bank 里没有"的编号（= 已移出）
    items = []
    n_hist = 0
    for p in [x.strip() for x in a.pools.split(',') if x.strip()]:
        nodes = BF.load_bank_nodes(p)
        if not nodes:
            print('  [{}] state 不存在或无 bank -> 跳过'.format(p))
            continue
        ics = BF.load_archive_ic(p)
        lib_rows = BF.parse_library(p)
        lib = {r['expr']: r for r in lib_rows}
        for expr, nd in nodes.items():
            L = lib.get(expr) or {}
            items.append(dict(pool=p, no=L.get('no') or BF._fallback_name(expr), expr=expr,
                              node=nd, in_bank=1, ic_lib=L.get('ic'), ic_arc=ics.get(expr),
                              ae_lib=L.get('ann_ex'), gen=L.get('gen') or ''))
        if not a.include_history:
            continue
        for r in lib_rows:
            if r['expr'] in nodes:
                continue                      # 在库里 ⇒ 上面已经加过（避免重复）
            items.append(dict(pool=p, no=r.get('no') or BF._fallback_name(r['expr']),
                              expr=r['expr'], node=None, in_bank=0,
                              ic_lib=r.get('ic'), ic_arc=ics.get(r['expr']),
                              ae_lib=r.get('ann_ex'), gen=r.get('gen') or ''))
            n_hist += 1
    if a.include_history:
        print('  ★ --include_history：额外补 **{} 个已移出当前库的历史编号**'.format(n_hist))
    seen, uniq = {}, []
    for it in items:
        if it['expr'] in seen:
            seen[it['expr']]['also'] = (seen[it['expr']].get('also') or []) + [it['pool']]
            continue
        seen[it['expr']] = it
        uniq.append(it)
    for it in uniq:
        it['ic_ref'] = it['ic_arc'] if it['ic_arc'] is not None else it['ic_lib']

    # ---- 增量：跳过 CSV 里已有名字 ----
    done = set()
    if a.only_new and os.path.exists(a.out):
        for r in csv.DictReader(io.open(a.out, encoding='utf-8-sig', newline='')):
            done.add(r.get('name'))
    uniq = [it for it in uniq if BF._name_of(it) not in done]
    if a.limit:
        uniq = uniq[:a.limit]
    print('=' * 96)
    print('因子费后指标补算 → {}'.format(os.path.relpath(a.out, ROOT)))
    print('  待算 {} 个（bank 内去重后）{}'.format(
        len(uniq), '  [增量 --only-new]' if a.only_new else ''))
    print('=' * 96)
    if not uniq:
        print('  ⇒ 无待算因子，退出')
        return 0

    t0 = time.time()
    bf = LE.base_fields()
    B, dates, cols, close = bf['B'], bf['dates'], bf['cols'], bf['close']
    print('面板载入完成: {} 日 x {} 股, {:.0f}s'.format(len(dates), len(cols), time.time() - t0))

    rows, warn = [], []
    for i, it in enumerate(uniq, 1):
        nm, expr, nd = BF._name_of(it), it['expr'], it['node']
        t1 = time.time()
        if nd is None:
            # ★ 历史编号：库里没有 Node ⇒ 从库文档的表达式文本**反向解析**
            #   ⚠⚠ 必须**临时放开** `LLM_MAX_SIZE`：`parse_expr` 有一道节点数上限，超限时
            #      **静默返回 None**（`load_bank_nodes` 的注释里就记着这个坑：全A F01 曾因超限返回 None ✗）
            _cap = LE.LLM_MAX_SIZE
            LE.LLM_MAX_SIZE = 10 ** 9
            try:
                nd = LE.parse_expr(expr)
            finally:
                LE.LLM_MAX_SIZE = _cap
            if nd is None:
                print('  [{}] **表达式反解失败**（跳过，不臆造）：{}'.format(nm, expr[:70]))
                continue
        try:
            v = LE.eval_expr(nd, B, {})
            fac = cs_rank(pd.DataFrame(v, index=dates, columns=cols).astype('float64'))
            # ★ `with_ex=True` ⇒ 额外拿到期频序列 `ex`（用于记录**回测区间** 首/末交易日）
            rr = evaluate_real(fac, close, expr, cost=a.cost, window=a.window,
                               with_daily=True, with_ex=True)
        except Exception as e:
            print('  [{}] **求值/回测失败** {}: {}'.format(nm, type(e).__name__, e))
            continue
        if rr is None:
            print('  [{}] 回测返回 None -> 跳过'.format(nm))
            continue
        # ★ 符号对齐（与 build_facs 同一判据）：库里记的是**带符号** IC，而 node 不带符号
        sign = 1
        ref = it['ic_ref'] if it['ic_ref'] not in (None, 0) else it['ae_lib']
        if ref not in (None, 0) and np.sign(rr['ic']) != np.sign(ref):
            sign = -1
            rr = (evaluate_real(-fac, close, expr, cost=a.cost, window=a.window,
                                with_daily=True, with_ex=True) or rr)
        elif ref in (None, 0):
            warn.append(nm)
        yr = rr.get('yr') or {}
        rows.append(dict(
            name=nm, pool=it['pool'], in_bank=it.get('in_bank', 1),
            gen=it['gen'], expr=expr, sign=sign,
            ic=rr['ic'], ic_doc=it['ic_ref'], ic_ir=rr['ic_ir'], ic_win=rr['ic_win'],
            ann_ex=rr['ann_ex'], dd=rr['dd'], calmar=rr['calmar'], sharpe=rr['sharpe'],
            ann_top=rr.get('ann_top'), dd_top=rr.get('dd_top'),
            calmar_top=rr.get('calmar_top'), sharpe_top=rr.get('sharpe_top'),
            dd_d=rr.get('dd_d'), calmar_d=rr.get('calmar_d'), sharpe_d=rr.get('sharpe_d'),
            dd_top_d=rr.get('dd_top_d'), calmar_top_d=rr.get('calmar_top_d'),
            sharpe_top_d=rr.get('sharpe_top_d'),
            last_yr=rr.get('last_yr'), turn=rr.get('turn'),
            neg_yr=sum(1 for x in yr.values() if x <= 0), n_rebal=rr.get('n_rebal'),
            bt_start=int(rr['ex'].index[0]), bt_end=int(rr['ex'].index[-1])))
        print('  [{:<10s}] {:.0f}s  超额 {:+6.2f}%/Cal {:.3f}/夏普 {:.2f}  自身 {:+6.2f}%/Cal {:.3f}'
              '  日频Cal {}  最近年 {:+.1f}% 换手 {:.1f}% 负年 {}'.format(
                  nm, time.time() - t1, rr['ann_ex'] * 100, rr['calmar'] or 0, rr['sharpe'],
                  (rr.get('ann_top') or 0) * 100, rr.get('calmar_top') or 0,
                  ('{:.3f}'.format(rr['calmar_d']) if rr.get('calmar_d') is not None else '—'),
                  (rr.get('last_yr') or 0) * 100, (rr.get('turn') or 0) * 100,
                  rows[-1]['neg_yr'])
              + '  区间 %d~%d' % (rows[-1]['bt_start'], rows[-1]['bt_end']))

    if rows:
        n = BF._merge_csv(a.out, rows, COLS)
        print('\n⇒ {}（合并后共 {} 条；**独立派生文件，不改任何 md**）'.format(
            os.path.relpath(a.out, ROOT), n))
    # ---- ★ 自检：与库文档/归档里记录的 IC 对账（口径没对齐时必须吼出来）----
    diff = [(r['name'], r['ic_doc'], r['ic']) for r in rows
            if r['ic_doc'] not in (None, '') and
            abs(float(r['ic']) - float(r['ic_doc'])) > a.ic_tol]
    if diff:
        print('\n[!] **{} 个因子的 IC 与归档记录不符**（> {}）—— 口径可能不同，'
              '看板以本文件为准（统一口径），但需人工复核：'.format(len(diff), a.ic_tol))
        for nm, e, g in diff[:12]:
            print('    {:<12s} 归档 {:.4f} vs 重算 {:.4f}  (差 {:+.4f})'.format(
                nm, float(e), float(g), float(g) - float(e)))
    if warn:
        print('\n[!] {} 个因子**无 IC 记录**（老条目）⇒ 符号按 node 原样（未对账）：{}'.format(
            len(warn), ', '.join(warn[:10])))
    print('完成，用时 {:.0f}s'.format(time.time() - t0))
    return 0


if __name__ == '__main__':
    sys.exit(main())
