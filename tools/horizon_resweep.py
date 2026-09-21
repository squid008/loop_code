# -*- coding: utf-8 -*-
"""horizon_resweep.py — **(C3) 20 日口径「重评筛选」**（用户拍板：(A) → (C)，先做前置改造 + C3 ✓）

★ 它干什么（一句话）：
  把**历史上试过的候选**（`docs/loop_archive*.csv` = 各池每代 L2 的验收流水 ✓）在
  **20 日调仓口径**下**重评一遍**，挑出"在 20 日下真的强"的那批 ⇒ **只出报告，不碰库** ✓

★ 为什么先做 C3（而不是直接上 C1「引擎双评」✗）：
  · C3 **便宜**：20 日下换仓循环 418 → ~104 次 ⇒ 单因子反而**更快** ✓
  · C3 能**先验证**"20 日口径选出来的到底是不是好东西" ✓
    ⇒ 若连重评筛都选不出东西 ⇒ C1 也不会有奇迹 ✓（省一大坨复杂度 ✓）
  · ⚠ C3 **不改挖掘目标函数** ✗：新因子仍是 5 日挖出来的，只是在 20 日下被**重筛**过 ✓
    真要"20 日自己挖"，那是 C1（引擎双评）✓ —— 本工具的输出正是决定要不要上 C1 的依据 ✓

★ 口径三件（必须与原表可分 ✗）：
  · 调仓周期 = `--fwd`（默认 20 ✓）· 样本区间 = `--window`（默认 full ✓）· 往返成本 = `--cost`（0.004 ✓）
  · ★ 评估**在全A 面板**上做（与 `tools/factor_metrics.py` 同口径 ✓）——
    ⚠ 不是"池内"口径 ✗（池内口径只有库文字指标 `factor_metrics.csv` 有 ✓）

★ 三条红线（本工具**全部遵守** ✓）：
  ① **不写库** ✗ —— 不碰 `factor_library*.md` / `factor_registry.json` / `library_entries.jsonl` / state.pkl ✓
  ② **不覆盖**既有 CSV ✗ —— 默认写到**新文件** `docs/horizon20_candidates.csv` ✓
  ③ **不臆造** ✗ —— 求值失败/反解失败的候选**如实记 `.失败原因`**，不当成"没过门" ✓

用法：
  python tools/horizon_resweep.py --limit 5                 # 冒烟（5 个候选）
  python tools/horizon_resweep.py --min-cal5 0.30           # 正式（预筛后再重评）
  python tools/horizon_resweep.py --fwd 20 --min-cal5 0.3 --pools 300,500,1000,all
"""
import argparse
import csv
import glob
import io
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

# 归档里对我们有用的列（C3 只读这些 ✓）
ARC_COLS = ('gen', 'expr', 'ic', 'calmar', 'turn', 'ann_ex', 'n_rebal')
OUT_COLS = ('name', 'pool', 'gen5', 'expr', 'fwd', 'sign',
            'ic5', 'calmar5', 'turn5',
            'ic20', 'calmar20', 'turn20', 'stab20', 'ann_ex20', 'dd20', 'sharpe20',
            'd_calmar', 'pass20', 'fail_reason')


def _f(x):
    try:
        v = float(x)
        return None if v != v else v                      # NaN -> None ✓
    except Exception:                                        # noqa: BLE001
        return None


def load_candidates(archives, pools, min_cal5, min_ic5, limit):
    """读各池归档 ⇒ 按 expr 去重（保留 5 日 calmar 最好的那条 ✓）⇒ 预筛 ✓"""
    rows, seen = [], {}
    for p in archives:
        base = os.path.basename(p)
        # 池 = 文件名后缀（`loop_archive_1000.csv` ⇒ '1000'；`loop_archive.csv` ⇒ 'all' ✓）
        pool = base[len('loop_archive'):-len('.csv')].lstrip('_') or 'all'
        if pools and pool not in pools:
            continue
        try:
            rd = list(csv.DictReader(io.open(p, encoding='utf-8-sig', newline='')))
        except Exception as e:                                   # noqa: BLE001
            print('  [!] 读归档失败 {}: {}'.format(base, e))
            continue
        for r in rd:
            ex = (r.get('expr') or '').strip()
            if not ex:
                continue
            c = _f(r.get('calmar'))
            key = ex
            old = seen.get(key)
            if old is None or (c is not None and (old['calmar5'] is None or c > old['calmar5'])):
                seen[key] = dict(name='', pool=pool, gen5=r.get('gen'),
                                 expr=ex, calmar5=c, ic5=_f(r.get('ic')), turn5=_f(r.get('turn')))
    cand = list(seen.values())
    n_all = len(cand)
    if min_cal5 is not None:
        cand = [c for c in cand if c['calmar5'] is not None and c['calmar5'] >= min_cal5]
    if min_ic5 is not None:
        cand = [c for c in cand if c['ic5'] is not None and abs(c['ic5']) >= min_ic5]
    cand.sort(key=lambda c: -(c['calmar5'] or -9e9))
    if limit:
        cand = cand[:limit]
    return cand, n_all


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--fwd', type=int, default=20, help='目标调仓周期（默认 20 ✓）')
    ap.add_argument('--window', choices=['full', 'recent600'], default='full')
    ap.add_argument('--cost', type=float, default=0.004)
    ap.add_argument('--archives', default='', help='归档（逗号分隔）；空=docs/loop_archive*.csv 全要 ✓')
    ap.add_argument('--pools', default='', help='只看这些池的归档（如 300,500,1000,all）；空=全部 ✓')
    ap.add_argument('--min-cal5', type=float, default=None, help='预筛：5 日归档 calmar 下限（省时间 ✓）')
    ap.add_argument('--min-ic5', type=float, default=None, help='预筛：|5 日 ic| 下限')
    ap.add_argument('--limit', type=int, default=0, help='只算前 N 个（冒烟用 ✓）')
    # ★ 20 日**标定门槛**（默认取 2026-09-21 全库标定：calmar 中位 0.701 ✓；IC/stab 沿用引擎默认 ✓）
    ap.add_argument('--gate-calmar', type=float, default=0.701,
                    help='20 日口径的卡玛门槛（默认 0.701 = 2026-09-21 全库标定中位 ✓）')
    ap.add_argument('--gate-ic', type=float, default=0.02, help='|IC| 门槛（默认同引擎 0.02 ✓）')
    ap.add_argument('--gate-stab', type=float, default=0.30, help='稳定性门槛（默认同引擎 0.30 ✓）')
    ap.add_argument('--panel_cache', default='use', choices=['off', 'use', 'build'])
    # ★ 分片并行：单因子 15~50s ✗ ⇒ 用 `--shard i/N` 起 N 个进程各算一片（**不引入 multiprocessing** ✓
    #   简单可靠 ✓；每个进程私有 ~2~3 GB ⇒ 按可用内存决定 N ✓，跑完各自出一份 CSV 再合 ✓）
    ap.add_argument('--shard', type=int, default=1, help='第几片（1..N）；默认 1=不分片 ✓')
    ap.add_argument('--shards', type=int, default=1, help='总分片数 N（>1 时按 i::N 切候选 ✓）')
    ap.add_argument('--out', default=os.path.join(DOCS, 'horizon20_candidates.csv'))
    a = ap.parse_args()

    arcs = ([x.strip() for x in a.archives.split(',') if x.strip()] if a.archives
            else sorted(glob.glob(os.path.join(DOCS, 'loop_archive*.csv'))))
    pools = set(x.strip() for x in a.pools.split(',') if x.strip()) if a.pools else None
    cand, n_all = load_candidates(arcs, pools, a.min_cal5, a.min_ic5, a.limit)
    n_cand_all = len(cand)
    if a.shards > 1:
        # ⚠ 分片必须在**预筛与排序之后**切 ✓（否则各片的候选集不同 ⇒ 无法合 ✓）
        cand = cand[(a.shard - 1)::a.shards]

    import numpy as np
    import pandas as pd
    import build_facs as BF
    import factor_miner as FM
    from factor_miner import evaluate_real, cs_rank
    import loop_engine as LE

    BF._prep_main()                      # ★ 与 factor_metrics.py 同一套准备（路径/环境 ✓）
    LE.set_panel_cache(a.panel_cache)
    _old_fwd = FM.FWD
    FM.set_fwd(int(a.fwd))
    LE.FWD = FM.FWD                              # ★ 引擎切片 + factor_stability 都跟着走 ✓

    print('=' * 100)
    print('(C3) 20 日口径重评筛选 → {}'.format(os.path.relpath(a.out, ROOT)))
    print('  口径：调仓周期 FWD={} · 样本区间={} · 往返成本={}（评估在**全A 面板** ✓）'
          .format(FM.FWD, a.window, a.cost))
    print('  候选：本片 {} / 预筛后 {} 个（归档去重后 {}）{}{}'.format(
        len(cand), n_cand_all, n_all,
        '  预筛 min_cal5={}'.format(a.min_cal5) if a.min_cal5 is not None else '',
        '  分片 {}/{}'.format(a.shard, a.shards) if a.shards > 1 else ''))
    print('=' * 100)
    if not cand:
        print('  ⇒ 无候选，退出')
        return 0

    t0 = time.time()
    bf = LE.base_fields()
    B, dates, cols, close = bf['B'], bf['dates'], bf['cols'], bf['close']
    print('  面板载入 {:.0f}s（{} 日 × {} 股）'.format(time.time() - t0, len(dates), len(cols)))

    rows = []
    for i, c in enumerate(cand, 1):
        expr = c['expr']
        nm = 'H%02d' % i                                     # ⚠ 只在本报告里编号 ✗ 不进库 ✓
        rec = dict(name=nm, pool=c['pool'], gen5=c['gen5'], expr=expr, fwd=FM.FWD,
                   ic5=c['ic5'], calmar5=c['calmar5'], turn5=c['turn5'],
                   ic20=None, calmar20=None, turn20=None, stab20=None,
                   ann_ex20=None, dd20=None, sharpe20=None, d_calmar=None,
                   sign=1, pass20=0, fail_reason='')
        t1 = time.time()
        try:
            _cap = LE.LLM_MAX_SIZE                       # ⚠ 必须临时放开 ⇒ 否则超限**静默返回 None** ✗
            LE.LLM_MAX_SIZE = 10 ** 9
            try:
                nd = LE.parse_expr(expr)
            finally:
                LE.LLM_MAX_SIZE = _cap
            if nd is None:
                rec['fail_reason'] = '表达式反解失败(不臆造)'
                rows.append(rec)
                print('  [{:<5s}] 反解失败 -> 跳过'.format(nm))
                continue
            v = LE.eval_expr(nd, B, {})
            fac = cs_rank(pd.DataFrame(v, index=dates, columns=cols).astype('float64'))
            rr = evaluate_real(fac, close, expr, cost=a.cost, window=a.window,
                               with_daily=True, with_ex=True)
            # ★★ 2026-09-21（**冒烟当场抓到** ✗）：**必须做符号对齐** ——
            #   归档里存的是**带符号**的 IC（"越大越好"方向 ✓），而 `expr` 文本**不带符号** ✗
            #   ⇒ 直接按 expr 求值会得到**反方向**（IC 变负 ✓ Calmar 变负 ✗）
            #   ⇒ 与 `tools/factor_metrics.py` **同一判据**：拿归档 5 日 IC 定方向，反了就整体取负重评 ✓
            #   ⚠ 两个口径必须用**同一取向** ✗（因子定义不随持有期变 ✓；变的只是表现 ✓）
            #     所以这里用 **5 日归档 IC** 定向、20 日沿用同一取向 ✓（不是隐瞒符号翻转 ✓）
            if rr is not None and c['ic5'] not in (None, 0) \
                    and np.sign(rr['ic']) != np.sign(c['ic5']):
                rec['sign'] = -1
                rr = (evaluate_real(-fac, close, expr, cost=a.cost, window=a.window,
                                    with_daily=True, with_ex=True) or rr)
            if rr is None:
                rec['fail_reason'] = '回测返回 None'
                rows.append(rec)
                continue
            st = LE.factor_stability(np.asarray(v), dates=dates, start=FM.START)
            rec.update(ic20=rr['ic'], calmar20=rr['calmar'], turn20=rr.get('turn'),
                       stab20=st, ann_ex20=rr['ann_ex'], dd20=rr['dd'], sharpe20=rr['sharpe'])
            if c['calmar5'] is not None and rr['calmar'] is not None:
                rec['d_calmar'] = rr['calmar'] - c['calmar5']
            _ok, _why = [], []
            if rec['calmar20'] is None or rec['calmar20'] < a.gate_calmar:
                _ok.append(0); _why.append('cal {}'.format(
                    '—' if rec['calmar20'] is None else '{:.3f}'.format(rec['calmar20'])))
            if rec['ic20'] is None or abs(rec['ic20']) < a.gate_ic:
                _ok.append(0); _why.append('ic {}'.format(
                    '—' if rec['ic20'] is None else '{:.4f}'.format(rec['ic20'])))
            if rec['stab20'] is None or rec['stab20'] < a.gate_stab:
                _ok.append(0); _why.append('stab {}'.format(
                    '—' if rec['stab20'] is None else '{:.2f}'.format(rec['stab20'])))
            rec['pass20'] = 1 if all(_ok) else 0
            rec['fail_reason'] = '' if rec['pass20'] else ('未过 ' + ' · '.join(_why))
            print('  [{:<5s}] {:>4.0f}s  20日 Cal {:>6} / IC {:>8} / stab {:>5}'
                  '  vs 5日 Cal {:>6}  Δ {:+6.2f}%  {}'.format(
                      nm, time.time() - t1,
                      '{:.3f}'.format(rec['calmar20']) if rec['calmar20'] is not None else '—',
                      '{:.4f}'.format(rec['ic20']) if rec['ic20'] is not None else '—',
                      '{:.2f}'.format(rec['stab20']) if rec['stab20'] is not None else '—',
                      '{:.3f}'.format(c['calmar5']) if c['calmar5'] is not None else '—',
                      (rec['d_calmar'] or 0) * 100,
                      '★过门 ✓' if rec['pass20'] else rec['fail_reason']))
        except Exception as e:                                   # noqa: BLE001
            rec['fail_reason'] = '求值/回测异常 {}: {}'.format(type(e).__name__, str(e)[:60])
            print('  [{:<5s}] 异常 -> {}'.format(nm, rec['fail_reason']))
        rows.append(rec)

    # ---- 写报告（**新文件** ✓ 不动任何既有 CSV ✓）----
    if rows:
        with io.open(a.out, 'w', encoding='utf-8-sig', newline='') as f:
            w = csv.DictWriter(f, fieldnames=list(OUT_COLS))
            w.writeheader()
            for r in rows:
                w.writerow(dict((k, ('' if r.get(k) is None else r.get(k))) for k in OUT_COLS))
    ok = [r for r in rows if r['pass20']]
    fail = [r for r in rows if not r['pass20']]
    print('\n' + '=' * 100)
    print('  ⇒ 报告 = {}（{} 行 ✓ 只出报告、**不碰库** ✓）'.format(
        os.path.relpath(a.out, ROOT), len(rows)))
    print('  ★ 过 20 日门 = {} / {}'.format(len(ok), len(rows)))
    if ok:
        print('  ★ 过门榜（按 20 日 Calmar 降序）：')
        for r in sorted(ok, key=lambda x: -(x['calmar20'] or -9))[:10]:
            print('      {:<6s} 池 {:<5s} 20日Cal {:>6.3f}  5日Cal {:>6.3f}  Δ {:>+6.2f}%  {}'
                  .format(r['name'], r['pool'], r['calmar20'] or 0, r['calmar5'] or 0,
                          (r['d_calmar'] or 0) * 100, r['expr'][:44]))
    _noreason = sum(1 for r in fail if r['fail_reason'].startswith(('求值', '表达式', '回测')))
    if _noreason:
        print('  ⚠ 其中 {} 个是**求值失败**（不是"没过门" ✗ —— 如实分开记 ✓）'.format(_noreason))
    print('  用时 {:.0f}s'.format(time.time() - t0))
    print('=' * 100)

    FM.set_fwd(_old_fwd)                             # 复原（本进程专用 ✓）
    LE.FWD = FM.FWD
    return 0


if __name__ == '__main__':
    sys.exit(main())
