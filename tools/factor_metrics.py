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


def refresh_in_bank(old_rows, items, pools):
    """★ 2026-09-23 新增（纯函数 ⇒ 可单测 ✓ 见 `tools/_test_metrics_rows.py`）：
    把旧行的 `in_bank` **与当前权威库（`state.bank`）对齐**，返回**需要写回的行**。

    为什么（**看板会说谎**，实测 ✓）：
      `in_bank` 原来**只在"该行被重算那一刻"才更新** ⇒ 行一旦不再被重算，值就长期停住 ✗。
      实测：`F01_500` / `F01_1000` 明明在库（`state.bank` ✓），而 5 日表里那两行写着
      `in_bank=0` / **空** ✗ ⇒ 看板「因子库」的**三态徽标**把它们显示成「**已移出**」✗
      —— 前端读的就是这一列（`dashboard/api/app/sources/factors.py::_inb` ✓）。
      （这正是用户 2026-09-23 之问"是不是 5 日 20 日都审查了？"顺带查出来的第 2 处不一致 ✓）

    ⚠ 只刷新**本进程跑的那几个池**（`--pools=500` 时**不许**把别的池的行改成 0 ✗）
    """
    # ⚠ 本模块**只在 `main()` 里** `import build_facs as BF`（保持"顶层不加载重依赖" ✓）
    #   ⇒ 这个纯函数里必须**自己延迟 import**，否则被单测直接调用会 `NameError: BF` ✗（实测踩过 ✓）
    import build_facs as _BF
    bank = {_BF._name_of(it) for it in items if it.get('in_bank', 1) == 1}
    want_pools = {str(x).strip() for x in (pools or [])}
    out = []
    for r in old_rows:
        if (r.get('pool') or 'all') not in want_pools:
            continue
        want = '1' if r.get('name') in bank else '0'
        if str(r.get('in_bank') or '').strip() != want:
            r['in_bank'] = want
            out.append(r)
    return out


def _apply_inbank_refresh(out_path, items, pools):
    """把 `out_path` 里**该池**的旧行 `in_bank` 与权威库对齐、**就地合并写回**；返回改了几行 ✓

    ⚠ 复用 `BF._merge_csv`（**按 `name` 合并** ⇒ 只覆盖改过的那几行，其余原样 ✓ 零副作用 ✓）
    """
    if not os.path.exists(out_path):
        return 0
    import build_facs as _BF
    try:
        old = [r for r in csv.DictReader(io.open(out_path, encoding='utf-8-sig', newline=''))]
    except Exception:                                                           # noqa: BLE001
        return 0
    fix = refresh_in_bank(old, items, [x.strip() for x in str(pools or '').split(',')
                                       if x.strip()])
    if not fix:
        return 0
    _BF._merge_csv(out_path, fix, COLS)
    return len(fix)


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
    # ★ 2026-09-21（用户："咱们是不是要做个 20 日调仓的口径？这样一些财务低频因子
    #   才有用武之地、才能被选出来？"）—— 先做**事后重评**实测，再决定要不要建双口径 ✓
    #   ⚠ 修 bug：原来这里是 `--window type=int default=5` ✗ —— `evaluate_real(window=...)`
    #     要的是 `'full'`/`'recent600'` **字符串**（见其 docstring 第 5 条 ✓）⇒ 传 int 5
    #     会落到 else 分支 = full ⇒ **行为上无害、语义上误导** ✗ ⇒ 改 `choices` + `default='full'`
    #     （**行为完全不变**：默认仍等价于原来的 full ✓）
    ap.add_argument('--window', choices=['full', 'recent600'], default='full',
                    help='样本区间：full=START(2018) 起全口径（默认）· recent600=最近 600 交易日')
    # ★★ `--fwd`：调仓周期（交易日）。**引擎里 FWD 写死 5** 且**没有命令行入口** ✗
    #   （`factor_miner.set_fwd()` 早就写好了、却是个**孤儿函数**（全仓零调用 ✗）⇒ 这里接上 ✓）
    #   ⚠⚠ 这只是**评估口径**变了 ⇒ **不改库、不改既有数字、不覆盖原表** ✓
    #      （务必配 `--out` 写到另一个文件 ✓，否则会把 5 日口径的表冲掉 ✗）
    ap.add_argument('--fwd', type=int, default=0,
                    help='调仓周期（交易日）；0=引擎默认(5) ⇒ 行为完全不变。'
                         '★ 对照口径用（如 --fwd=20）；只影响本进程的评估 ✓')
    ap.add_argument('--panel_cache', default='off', choices=['off', 'use', 'build'])
    ap.add_argument('--out', default=os.path.join(DOCS, 'factor_metrics.csv'))
    ap.add_argument('--ic_tol', type=float, default=0.002,
                    help='IC 自检容差：与**库文档/归档**里记录的 IC 差超过它就报警 '
                         '(口径没对齐时必须吼出来，否则落地的是错的数；'
                         '换口径对照时必然超差 ⇒ 可传大值静音 ✓)')
    a = ap.parse_args()

    import pandas as pd
    import build_facs as BF
    LE = BF._prep_main()
    LE.set_panel_cache(a.panel_cache)
    from factor_miner import evaluate_real, cs_rank
    import factor_miner as _FM
    if a.fwd:
        _old = _FM.FWD                       # ⚠ set_fwd 返回的是**新值**，旧值要先记 ✓
        _FM.set_fwd(int(a.fwd))
        print('  ★ 调仓周期口径 = **{} 交易日**（引擎默认 {}）—— 仅本进程有效 ✓'
              '  只重算、不动库 ✓'.format(_FM.FWD, _old))
        if abs(int(a.fwd) - int(_old)) >= 2:
            print('  ⚠ 换口径后：IC/卡玛/换手**都与原表不可直接比**；'
                  '期数会从 ~418 变成 ~{} ✓'.format(int(len(pd.date_range(
                      '2018-01-01', '2026-09-18', freq='B')) / int(a.fwd))))

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
    # ★★ 2026-09-23：去重（同式子**算一次**）+ **别名表**（同式子的每个编号**都要写一行** ✓）
    #   这里原来"**先按 `expr` 去重、再按名字查 CSV**" ✗ ⇒ 同式子的别名编号
    #   （实测 `corr100(cs_scale(mf_x_sell), mf_l_sell)` = 300:F02 / 500:F01 / 1000:F01 ✓）
    #   只剩池序最靠前那个（`F02_300`）⇒ `F01_500` / `F01_1000` **永远进不了待算队列** ✗
    #   ⇒ 20 日指标表缺这两行、看板口径标签在这两个因子上一直显示"缺" ✗
    #     （而 5 日表里那两行是**老版本**留下的 ⇒ 两表看上去"一个有一个没有" ✓）—— 详见 `plan_rows` ✓
    uniq, alias = BF.plan_rows(items)
    for it in uniq:
        it['ic_ref'] = it['ic_arc'] if it['ic_arc'] is not None else it['ic_lib']
        for _x in (alias.get(it['expr']) or []):     # ★ 别名各自带**自己池**的库记录（IC 对账用 ✓）
            _x['ic_ref'] = _x['ic_arc'] if _x['ic_arc'] is not None else _x['ic_lib']

    # ---- 增量：跳过 CSV 里已有名字（★ 有一处不同：**任一别名缺行 ⇒ 这条式子仍要算** ✓）----
    done = set()
    if a.only_new and os.path.exists(a.out):
        for r in csv.DictReader(io.open(a.out, encoding='utf-8-sig', newline='')):
            done.add(r.get('name'))
    if done:
        uniq = [it for it in uniq
                if any(BF._name_of(_x) not in done
                       for _x in (alias.get(it['expr']) or [it]))]
    if a.limit:
        uniq = uniq[:a.limit]
    print('=' * 96)
    print('因子费后指标补算 → {}'.format(os.path.relpath(a.out, ROOT)))
    print('  待算 {} 个（bank 内去重后）{}'.format(
        len(uniq), '  [增量 --only-new]' if a.only_new else ''))
    # ★ 2026-09-21：把**口径三件**打进抬头 ✓ —— 否则换口径算出来的表会与原表**看着一样**，
    #   半年后没人知道哪张是 5 日、哪张是 20 日 ✗
    print('  口径：调仓周期 FWD={} 交易日 · 样本区间={} · 往返成本={}'.format(
        _FM.FWD, a.window, a.cost))
    print('=' * 96)
    # ---- ★★ 2026-09-23：`in_bank` 徽标刷新（**必须在"无待算就退出"之前** ✓）----
    #   为什么：它原来只在"该行被重算"时才更新 ⇒ 一旦没有新因子要算，就**永远不会被修** ✗
    #   （实测：`F01_500`/`F01_1000` 在库、表里却写着 0/空 ⇒ 看板显示「已移出」✗）
    _nfix = _apply_inbank_refresh(a.out, items, a.pools)
    if _nfix:
        print('  ★ 顺带刷新 {} 行的 `in_bank`（对齐当前权威库 state.bank ✓）'.format(_nfix))
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
        # ★★ 2026-09-23：**同式子的每个编号各写一行**（别名扇出 ✓）
        #   `_als[0]` 就是本条（池序最靠前那个，用它做的计算），其余是**同式子的别名编号** ✓
        _als = alias.get(expr) or [it]
        for _x in _als:
            rows.append(dict(
                name=BF._name_of(_x), pool=_x['pool'], in_bank=_x.get('in_bank', 1),
                gen=_x['gen'], expr=expr, sign=sign,
                ic=rr['ic'], ic_doc=_x['ic_ref'], ic_ir=rr['ic_ir'], ic_win=rr['ic_win'],
                ann_ex=rr['ann_ex'], dd=rr['dd'], calmar=rr['calmar'], sharpe=rr['sharpe'],
                ann_top=rr.get('ann_top'), dd_top=rr.get('dd_top'),
                calmar_top=rr.get('calmar_top'), sharpe_top=rr.get('sharpe_top'),
                dd_d=rr.get('dd_d'), calmar_d=rr.get('calmar_d'), sharpe_d=rr.get('sharpe_d'),
                dd_top_d=rr.get('dd_top_d'), calmar_top_d=rr.get('calmar_top_d'),
                sharpe_top_d=rr.get('sharpe_top_d'),
                last_yr=rr.get('last_yr'), turn=rr.get('turn'),
                neg_yr=sum(1 for x in yr.values() if x <= 0), n_rebal=rr.get('n_rebal'),
                bt_start=int(rr['ex'].index[0]), bt_end=int(rr['ex'].index[-1])))
        _show = nm + (' +%d 别名(%s)' % (len(_als) - 1,
                                         ','.join(BF._name_of(_x) for _x in _als[1:]))
                      if len(_als) > 1 else '')
        print('  [{:<10s}] {:.0f}s  超额 {:+6.2f}%/Cal {:.3f}/夏普 {:.2f}  自身 {:+6.2f}%/Cal {:.3f}'
              '  日频Cal {}  最近年 {:+.1f}% 换手 {:.1f}% 负年 {}'.format(
                  _show[:10], time.time() - t1, rr['ann_ex'] * 100, rr['calmar'] or 0, rr['sharpe'],
                  (rr.get('ann_top') or 0) * 100, rr.get('calmar_top') or 0,
                  ('{:.3f}'.format(rr['calmar_d']) if rr.get('calmar_d') is not None else '—'),
                  (rr.get('last_yr') or 0) * 100, (rr.get('turn') or 0) * 100,
                  rows[-1]['neg_yr'])
              + '  区间 %d~%d' % (rows[-1]['bt_start'], rows[-1]['bt_end'])
              + (('  ← ' + _show) if len(_als) > 1 else ''))

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
