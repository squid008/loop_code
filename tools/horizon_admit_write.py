# -*- coding: utf-8 -*-
"""horizon_admit_write.py — **(丁) 写库**：把 20 日口径选出的因子正式写进因子库 ✓

★ 它干的四件事（**默认 dry-run ✗ 只打印不动手 ✓**）：
  ① **真去重**（补上 C3/甲 都欠的那一条 ✗）：拿**各池 `loop_state*.pkl` 的 `bank_ex`**
     （= 库内全部因子的**每期费后超额序列** ✓）与本批算 `|Spearman 相关|` ✓
     ⇒ `> --dup-ex-corr`（生产值 **0.90** ✓）者**不入库** ✓✓（与引擎 `--dup_ex_corr` 同判据 ✓）
  ② **写文档**：`LE._lib_sync(..., horizon=20)` ✓ —— **复用引擎自己的函数** ✓
     ⇒ 编号规则 / 总览行 / 明细块 / `library_entries.jsonl` 全部与引擎一致 ✓✓
  ③ **写状态**：`loop_state{_pool}.pkl` 的 `bank`（node ✓）+ `bank_ex`（收益流 ✓）追加 ✓
     ⇒ 否则 ① registry 拿不到 node（详情页曲线会空 ✗）② 将来挖掘**不会跟它们去重** ✗
  ④ **刷登记表**：跑 `tools/export_factor_registry.py` ✓

★ 安全设计（**这是写库，必须保守 ✓**）：
  · 默认 **dry-run** ⇒ 只有显式 `--write` 才落盘 ✓
  · 写前**全套备份**（md / jsonl / registry / 各池 pkl）⇒ `ai_test/_admit_bak_<时间戳>/` ✓
  · pkl 用**原子写**（`.tmp` + `os.replace` ✓ 与引擎同一手法 ✓）
  · 幂等：已在 `bank` 里的 expr **跳过** ✓（不重复入库 ✓）
  · 引擎**必须在停** ✗（写 pkl 时若引擎在跑会互相覆盖 ✓ 本工具会先检查 ✓）

用法：
  python tools/horizon_admit_write.py                     # dry-run（推荐先看 ✓）
  python tools/horizon_admit_write.py --write             # 真写（自动备份 ✓）
"""
import argparse
import csv
import io
import json
import os
import pickle
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, 'engine'))
DOCS = os.path.join(ROOT, 'docs')
ENG = os.path.join(ROOT, 'engine')
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:                                                # noqa: BLE001
    pass

POOLS = ('all', '300', '500', '1000', '50')


def _state_path(pool):
    return os.path.join(ENG, 'loop_state.pkl' if pool == 'all'
                        else 'loop_state_%s.pkl' % pool)


def _lock(pool):
    """`_lib_sync` 靠模块全局 `LIBRARY` 决定写哪个 md ⇒ 先切池 ✓"""
    sfx = '' if pool == 'all' else '_' + pool
    return os.path.join(DOCS, 'factor_library%s.md' % sfx), sfx


def load_bank_ex():
    """把**各池** state 的 `bank_ex` 合起来 ⇒ 库内全部因子的收益流（去重对照集 ✓）"""
    out, src = {}, {}
    for p in POOLS:
        sp = _state_path(p)
        if not os.path.exists(sp):
            continue
        try:
            with open(sp, 'rb') as f:
                st = pickle.load(f)
        except Exception as e:                                   # noqa: BLE001
            print('  [!] %s 读失败：%s' % (os.path.basename(sp), e))
            continue
        be = st.get('bank_ex') or {}
        if isinstance(be, dict):
            for k, v in be.items():
                if k not in out:
                    out[k] = v
                    src[k] = p
    return out, src


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', default=os.path.join(DOCS, 'horizon20_admit_final.csv'))
    ap.add_argument('--json', default=os.path.join(ROOT, 'ai_test', '_admit_final.json'))
    ap.add_argument('--fwd', type=int, default=20)
    ap.add_argument('--cost', type=float, default=0.004)
    ap.add_argument('--dup-ex-corr', type=float, default=0.90,
                    help='收益流去重阈值（生产值 0.90 ✓）：与库内任一因子 |corr| 超过它 ⇒ 不入库')
    ap.add_argument('--min-overlap', type=int, default=30)
    ap.add_argument('--panel_cache', default='use', choices=['off', 'use', 'build'])
    ap.add_argument('--write', action='store_true', help='★ 真正落盘（默认只预演 ✗）')
    ap.add_argument('--pkl-only', action='store_true',
                    help='★ 只补 pkl（bank + bank_ex），**不动 md/jsonl** ✗ —— 用于止损：'
                         '文档已写对、但 pkl 少写了时的**幂等修复** ✓（已在 bank 里的会跳过 ✓）')
    a = ap.parse_args()

    # ---- 0) 安全：引擎必须在停 ----
    running = []
    try:
        import subprocess
        r = subprocess.run(['powershell', '-NoProfile', '-Command',
                            "(Get-CimInstance Win32_Process -Filter \"Name like 'python%'\" | "
                            "Where-Object { $_.CommandLine -match 'loop_engine|run_tracks' }).ProcessId"],
                           capture_output=True, text=True, timeout=30)
        running = [x for x in (r.stdout or '').split() if x.strip()]
    except Exception:                                            # noqa: BLE001
        pass
    if running and a.write:
        print('  ✗ **有引擎在跑**（pid %s）⇒ 写 pkl 会互相覆盖 ⇒ 先停引擎再写' % ','.join(running))
        return 2

    # ---- 1) 读定稿 ----
    rows = list(csv.DictReader(io.open(a.src, encoding='utf-8-sig', newline='')))
    payload = json.load(io.open(a.json, encoding='utf-8')) if os.path.exists(a.json) else []
    by_expr = {p['expr']: p for p in payload}
    rows = [r for r in rows if r.get('expr')]
    print('=' * 108)
    print('(丁) 写库 %s —— 候选 %d 个（来源 %s）' % (
        '**真写**' if a.write else '**预演(dry-run)**', len(rows), os.path.relpath(a.src, ROOT)))
    print('=' * 108)
    if not rows:
        return 0

    import numpy as np
    import build_facs as BF
    import factor_miner as FM
    import loop_engine as LE
    from factor_miner import evaluate_real, cs_rank

    BF._prep_main()
    LE.set_panel_cache(a.panel_cache)
    _old = FM.FWD
    FM.set_fwd(int(a.fwd))
    LE.FWD = FM.FWD

    bf = LE.base_fields()
    B, dates, cols, close = bf['B'], bf['dates'], bf['cols'], bf['close']

    # ---- 2) 库内收益流（去重对照集 ✓）----
    lib_ex, lib_src = load_bank_ex()
    print('  库内收益流对照集：%d 条（来自各池 state 的 bank_ex ✓）' % len(lib_ex))

    # ---- 3) 逐个：重算收益流 + 真去重 ----
    keep, blocked = [], []
    for i, r in enumerate(rows, 1):
        expr = r['expr']
        if (r.get('sign') or '') == '':
            print('  [{:<5s}] ✗ **sign 缺失** ⇒ 跳过（不臆造取向 ✗ 取反=镜像值会静默错 ✓）'.format(r['name']))
            blocked.append((r, 'sign 缺失（不臆造）'))
            continue
        sign = int(r.get('sign'))
        t1 = time.time()
        try:
            _cap = LE.LLM_MAX_SIZE
            LE.LLM_MAX_SIZE = 10 ** 9
            try:
                nd = LE.parse_expr(expr)
            finally:
                LE.LLM_MAX_SIZE = _cap
            if nd is None:
                blocked.append((r, '表达式反解失败(不臆造)'))
                continue
            v = LE.eval_expr(nd, B, {})
            if sign < 0:
                v = -v
            f = cs_rank(__import__('pandas').DataFrame(v, index=dates, columns=cols).astype('float64'))
            rr = evaluate_real(f, close, expr, cost=a.cost, window='full', with_ex=True)
            ex = rr.get('ex') if rr else None
            mec, mew = (None, None)
            if ex is not None and lib_ex:
                mec, mew = LE.ex_max_corr(ex, lib_ex, min_overlap=a.min_overlap)
            if mec is not None and mec > a.dup_ex_corr:
                blocked.append((r, '收益流重复 |corr|=%.3f > %.2f（与 %s）'
                                % (mec, a.dup_ex_corr, str(mew)[:54])))
                print('  [{:<5s}] {:>3.0f}s  ✗ **重复** |corr|={:.3f}（对方 {}）'.format(
                    r['name'], time.time() - t1, mec, str(mew)[:50]))
                continue
            rec = dict(r)
            rec['_ex'] = ex
            rec['_mec'] = mec
            rec['_mw'] = mew
            keep.append(rec)
            print('  [{:<5s}] {:>3.0f}s  ✓ 可写  与库最大 |corr| {}'.format(
                r['name'], time.time() - t1,
                ('{:.3f}'.format(mec)) if mec is not None else '—（无可比）'))
        except Exception as e:                                   # noqa: BLE001
            blocked.append((r, '异常 {}: {}'.format(type(e).__name__, str(e)[:60])))
            print('  [{:<5s}] 异常 {}: {}'.format(r['name'], type(e).__name__, str(e)[:60]))

    print('\n  ⇒ 通过去重 %d 个 · 被拦 %d 个' % (len(keep), len(blocked)))
    for r, why in blocked:
        print('      {:<6s} ✗ {}'.format(r['name'], why))

    # ---- 4) 分组预览（池 × 代数）----
    groups = {}
    for r in keep:
        groups.setdefault((r.get('pool') or 'all', str(r.get('gen') or '0')), []).append(r)
    print('\n  === 将写入（按 池 × 代数 分组 ✓ 编号由 `_lib_sync` 从各池 md 现有最大 F+1 起 ✓）===')
    # ⚠ 预览必须**模拟编号递增** ✗：`_lib_sync` 每次调用都重读 md ⇒ 会自然递增 ✓；
    #   若预览按"当前文件"算，多个组会显示**同一个号** ⇒ 看着像撞号（其实不会 ✓）⇒ 现在模拟 ✓
    import re
    cursor = {}
    for (pool, gen), rs in sorted(groups.items()):
        md, sfx = _lock(pool)
        if pool not in cursor:
            nos = [int(x) for x in re.findall(r'\bF(\d{2})\b', io.open(md, encoding='utf-8').read())] \
                if os.path.exists(md) else []
            cursor[pool] = (max(nos) + 1) if nos else 1
        n0 = cursor[pool]
        print('  池 %-5s gen%-4s ⇒ %-24s 新编号 F%02d..F%02d（%d 个）'
              % (pool, gen, os.path.basename(md), n0, n0 + len(rs) - 1, len(rs)))
        for k, r in enumerate(rs):
            print('        F%02d  %s（剥后 %s%s · 池标签 %s · 与库最大|corr| %s）'
                  % (n0 + k, r['name'], r.get('strip_calmar'), r.get('strip_grade'),
                     r.get('pool_tag'), ('%.3f' % r['_mec']) if r.get('_mec') is not None else '—'))
        cursor[pool] = n0 + len(rs)

    if not a.write:
        print('\n  ⚠ **预演结束，未改动任何文件** ✓（要真写请加 `--write` ✓）')
        FM.set_fwd(_old)
        LE.FWD = FM.FWD
        return 0

    # ---- 5) 备份 ----
    ts = time.strftime('%Y%m%d_%H%M%S')
    bak = os.path.join(ROOT, 'ai_test', '_admit_bak_%s' % ts)
    os.makedirs(bak, exist_ok=True)
    for p in POOLS:
        sp = _state_path(p)
        if os.path.exists(sp):
            shutil.copy2(sp, os.path.join(bak, os.path.basename(sp)))
    for fn in os.listdir(DOCS):
        if fn.startswith('factor_library') or fn in ('library_entries.jsonl', 'factor_registry.json'):
            shutil.copy2(os.path.join(DOCS, fn), os.path.join(bak, fn))
    print('\n  [备份] ⇒ %s（%d 个文件 ✓）' % (os.path.relpath(bak, ROOT), len(os.listdir(bak))))

    import pandas as pd
    # ---- 6) 写 md + jsonl（**复用引擎的 `_lib_sync`** ✓）+ 收集要写 pkl 的 node ----
    pkl_add = {}
    for (pool, gen), rs in sorted(groups.items()):
        LE.set_mine_pool(pool)
        exprs, expr2nd, tags, strips = [], {}, {}, {}
        res_rows = []
        bank_len = 0
        # ★ `--pkl-only`：跳过"写文档"这一步（md/jsonl 已写对 ⇒ 重写会**重复** ✗）
        _skip_doc = bool(a.pkl_only)
        sp = _state_path(pool)
        if os.path.exists(sp):
            try:
                with open(sp, 'rb') as fh:
                    bank_len = len(pickle.load(fh).get('bank') or [])
            except Exception:                                    # noqa: BLE001
                bank_len = 0
        for r in rs:
            e = r['expr']
            p_ = by_expr.get(e) or {}
            nd = LE.node_from_dict(p_['node']) if p_.get('node') else None
            exprs.append(e)
            if nd is not None:
                expr2nd[e] = nd
            tags[e] = r.get('pool_tag')
            strips[e] = (r.get('strip_grade'), r.get('strip_txt'),
                         float(r.get('strip_calmar') or 0),
                         float(r.get('strip_ann_ex') or 0),
                         (float(r['strip_calmar_d']) if r.get('strip_calmar_d') not in (None, '') else None),
                         (float(r['strip_dd_d']) if r.get('strip_dd_d') not in (None, '') else None))
            res_rows.append(dict(expr=e, cat=r.get('cat') or '', leaf=r.get('leaf') or '',
                                 ic=float(r.get('ic') or 0), ic_ir=float(r.get('ic_ir') or 0),
                                 ann_ex=float(r.get('ann_ex') or 0), dd=float(r.get('dd') or 0),
                                 calmar=float(r.get('calmar') or 0),
                                 sharpe=float(r.get('sharpe') or 0),
                                 last_yr=float(r.get('last_yr') or 0),
                                 turn=float(r.get('turn') or 0),
                                 neg_yr=int(float(r.get('neg_yr') or 0)),
                                 n_rebal=float(r.get('n_rebal') or 0),
                                 # ⚠ 必须**逐行**取 sign ✗ —— 曾误用上一循环的残留变量 ⇒
                                 #   会把所有行都写成最后一个候选的符号 ✗（文档里的 sign 是
                                 #   下游用它的第一件事 ⇒ 写错 = 反向选股 ✓ 已修 ✓）
                                 cost=a.cost, sign=int(r.get('sign') or 1)))
        res = pd.DataFrame(res_rows)
        # ⚠ `n_total` 必须是**该池最终总数** ✗ —— `_lib_sync` 会重写头部那句「> 当前 **N 个入库**」，
        #   若按"每组各自的总数"传 ⇒ 最后写的那个值只反映**最后一组** ⇒ 计数错了而不报错 ✓
        _pool_add_total = sum(len(v) for (p_, _g), v in groups.items() if p_ == pool)
        if not _skip_doc:
            LE._lib_sync(int(gen) if str(gen).strip() else 0, res, bank_len + _pool_add_total,
                         exprs, expr2nd, pool_tags=tags, strip_grades=strips,
                         horizon=int(a.fwd))
        # ★★ 2026-09-21 **修一个我自己的错** ✗：这里原来是**赋值** ⇒ 每个 (池,代) 组都
        #   **覆盖**上一条 ⇒ 实测每池只进 pkl **1 个** ✗（应为 1000 池 2 / 500 池 4 / all 4 ✓）
        #   典型症状：md 与 jsonl 都对 ✓、pkl 悄悄少 ✗（下游 registry 拿不到 node ✗、
        #   将来挖矿也不会跟它们去重 ✗）⇒ 必须**累积** ✓
        _acc = pkl_add.setdefault(pool, {'nodes': [], 'ex': {}})
        _acc['nodes'].extend([expr2nd[e] for e in exprs if e in expr2nd])
        for r in rs:
            if r.get('_ex') is not None:
                _acc['ex'][r['expr']] = r['_ex']

    # ---- 7) 写 pkl（原子 ✓）：bank + bank_ex ----
    for pool, d in pkl_add.items():
        sp = _state_path(pool)
        if not os.path.exists(sp):
            print('  [pkl] 池 %s 无 state ⇒ 跳过（文档已写 ✓）' % pool)
            continue
        with open(sp, 'rb') as f:
            st = pickle.load(f)
        bank = st.get('bank') or []
        be = st.get('bank_ex') or {}
        have = set(str(x) for x in bank)
        n_add = 0
        for nd in d['nodes']:
            if str(nd) in have:
                continue
            bank.append(nd)
            have.add(str(nd))
            n_add += 1
        n_ex = 0
        for k, v in (d['ex'] or {}).items():
            if k not in be:
                be[k] = v
                n_ex += 1
        st['bank'], st['bank_ex'] = bank, be
        tmp = sp + '.tmp'
        with open(tmp, 'wb') as f:
            pickle.dump(st, f)
        os.replace(tmp, sp)
        print('  [pkl] %s ⇒ bank +%d（共 %d）· bank_ex +%d（共 %d）✓'
              % (os.path.basename(sp), n_add, len(bank), n_ex, len(be)))

    # ---- 8) 刷登记表 ----
    print('\n  ⇒ 下一步（本工具**不自动跑**，避免连锁 ✗）：')
    print('      python tools/export_factor_registry.py')
    print('      python tools/factor_curves.py --only-new              # 补 5 日曲线')
    print('      python tools/factor_curves.py --fwd=20 --only-new '
          '--out_dir=factor_curves_fwd20   # 补 20 日曲线')
    FM.set_fwd(_old)
    LE.FWD = FM.FWD
    return 0


if __name__ == '__main__':
    sys.exit(main())
