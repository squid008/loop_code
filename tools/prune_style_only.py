# -*- coding: utf-8 -*-
"""prune_style_only.py — 从某个池的 state 里剔除「纯风格」因子（`strip_grade == 'C'`）

## 为什么要做（`docs/loop_todo.md` §1.17）

`--pool_gate_or_all` 的快照点取错，导致 **`--min_strip_calmar` 从 2026-09-13 起完全失效**
⇒ 池轨道已经入库了一批**剥掉 `lncap+lnamt` 后超额转负**的因子（纯风格）。
实测：池后缀 13 个入库因子里 **8 个是 C 档**（`strip_calmar` 全为负）。

**为什么必须剔除**（而不是留着）：
1. `--dup_ex_corr` / `--decorr` 的对照集是**各自轨道的 bank** ⇒ 这些 C 档因子会**挡住新因子**
   （"你已经有一个很像的了"）⇒ 继续跑等于**自我封锁**；
2. 合成 / 组合（`combo_build` / `combo_constrain`）会**自动带上**它们 ⇒ 污染 S2（真中性）口径；
3. 用户已拍板产品走 **B. 真中性增强** ⇒ C 档因子**不可用**。

**不做什么**：**不动** `docs/factor_library_{pool}.md` 与 `facs/` —— 那是**历史记录**，
保留可追溯（"这些因子确实被挖出来过，只是当时门槛没生效"）。本工具只改 **state 的 bank/bank_ex**。

## 安全措施（沿用 `cleanup_repo.py` 的四条铁律风格）

① **默认 DRY-RUN**：不加 `--apply` 一个字节都不动；
② **先备份**：`ai_test/_state_prune_{pool}_{ts}.pkl`（可人工恢复）；
③ **原子写**：`tmp + os.replace`（防半成品 state，见 roadmap §8.23 事故）；
④ **只按判据删**：判据 = `loop_strip_style_bank.csv` 的 `grade == 'C'`（**不猜**）；
   映射靠 `expr`（`ai_test/_facs_built.csv`），**对不上的 expr 一律保留**（宁可留，不误删）。

## 用法

    python tools/prune_style_only.py --pool=1000                    # DRY-RUN（看计划）
    python tools/prune_style_only.py --pool=1000 --apply            # 执行（只剔 C 档 = 纯风格）
    python tools/prune_style_only.py --pool=1000 --drop-grades=BC   # 更严：B 档也剔

档位定义（`loop_pools.strip_grade`，**单一事实源**）：
  **A** 剥风格后仍强 · **B** 剥风格后仍正但弱 · **C** 剥风格后**转负 = 纯风格**（指数增强不可用）
"""
import argparse
import csv
import io
import os
import pickle
import shutil
import sys
import time

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ENG = os.path.join(ROOT, 'engine')
AIT = os.path.join(ROOT, 'ai_test')
DOCS = os.path.join(ROOT, 'docs')
sys.path.insert(0, ENG)


def _prep_main():
    """pkl 是引擎以 `__main__` 身份存的 ⇒ 注入引擎的类，否则 `Can't get attribute 'Node'`。"""
    import loop_engine as LE
    for n in dir(LE):
        if n[:1].isupper() and isinstance(getattr(LE, n), type):
            setattr(sys.modules['__main__'], n, getattr(LE, n))
    return LE


def load_maps():
    """返回 (expr -> name, name -> grade)。缺文件就报错停下（**不静默用空表**）。"""
    e2n, n2g = {}, {}
    p1 = os.path.join(AIT, '_facs_built.csv')
    p2 = os.path.join(DOCS, 'loop_strip_style_bank.csv')
    for p in (p1, p2):
        if not os.path.exists(p):
            raise SystemExit('缺少前置文件: {}（先跑 tools/build_facs.py）'.format(p))
    for r in csv.DictReader(io.open(p1, encoding='utf-8-sig', newline='')):
        if r.get('expr'):
            e2n[r['expr']] = r.get('name') or '?'
    for r in csv.DictReader(io.open(p2, encoding='utf-8-sig', newline='')):
        n2g[r['name']] = r.get('grade') or '?'
    return e2n, n2g


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pool', default='1000')
    ap.add_argument('--drop-grades', default='C',
                    help="要剔除的档位（默认 'C' = 纯风格）。⚠ 别写 'BC' —— 那会把 B 档也剔掉")
    ap.add_argument('--apply', action='store_true', help='真正执行（默认 DRY-RUN）')
    a = ap.parse_args()

    _prep_main()
    sfx = '' if a.pool == 'all' else '_' + a.pool
    sp = os.path.join(ENG, 'loop_state{}.pkl'.format(sfx))
    if not os.path.exists(sp):
        raise SystemExit('state 不存在: {}'.format(sp))

    bad_grades = set(a.drop_grades)
    e2n, n2g = load_maps()

    st = pickle.load(open(sp, 'rb'))
    bank = list(st.get('bank') or [])
    bank_ex = st.get('bank_ex') or {}

    print('=' * 92)
    print('剔除「纯风格」因子   pool={}   state={}   （{}）'.format(
        a.pool, os.path.basename(sp), '**APPLY**' if a.apply else 'DRY-RUN'))
    print('=' * 92)
    print('  判据: 剥风格档位 ∈ {} 即剔除（来源 docs/loop_strip_style_bank.csv）'.format(
        sorted(bad_grades)))
    print('  state 现状: bank={}  bank_ex={}  其它键={}'.format(
        len(bank), len(bank_ex),
        sorted(k for k in st.keys() if k not in ('bank', 'bank_ex'))[:8]))
    print()

    keep, drop = [], []
    for nd in bank:
        s = str(nd)
        nm = e2n.get(s)
        gd = n2g.get(nm, '?') if nm else '?'
        (drop if gd in bad_grades else keep).append((nm or '?', gd, s))

    print('  --- 剔除 {} 个 ---'.format(len(drop)))
    for nm, gd, s in drop:
        print('    [{}] {:<12s} {}'.format(gd, nm, s[:66]))
    print('  --- 保留 {} 个 ---'.format(len(keep)))
    for nm, gd, s in keep:
        print('    [{}] {:<12s} {}'.format(gd, nm, s[:66]))

    if not drop:
        print('\n  ⇒ 没有需要剔除的，无需改动。')
        return 0

    drop_expr = {s for _, _, s in drop}
    n_bex_drop = sum(1 for k in bank_ex if k in drop_expr)
    print('\n  bank_ex 中将被移除 {} 条（按 expr 匹配）'.format(n_bex_drop))

    if not a.apply:
        print('\n（DRY-RUN。确认无误后加 --apply 执行）')
        return 0

    # ---- 备份（时间戳，不覆盖历史备份）----
    ts = time.strftime('%Y%m%d_%H%M%S')
    bak = os.path.join(AIT, '_state_prune_{}_{}.pkl'.format(a.pool, ts))
    shutil.copy2(sp, bak)
    print('\n  备份 -> {}'.format(os.path.relpath(bak, ROOT)))

    # ---- 改 state（原子写）----
    st['bank'] = [nd for nd in bank if str(nd) not in drop_expr]
    st['bank_ex'] = {k: v for k, v in bank_ex.items() if k not in drop_expr}
    st['_prune_note'] = ('2026-09-14 prune_style_only: 剔除 {} 个纯风格因子（§1.17 门槛失效产物）'
                         '；备份 {}'.format(len(drop), os.path.basename(bak)))
    tmp = sp + '.tmp'
    with open(tmp, 'wb') as f:
        pickle.dump(st, f, protocol=pickle.HIGHEST_PROTOCOL)
    os.replace(tmp, sp)
    print('  已写 {}（原子写）: bank {} -> {} · bank_ex {} -> {}'.format(
        os.path.basename(sp), len(bank), len(st['bank']), len(bank_ex), len(st['bank_ex'])))
    print('\n  ⚠ 提醒: 本操作**只改 state**；`docs/factor_library_{}.md` 与 `facs/` 保留历史记录。'
          .format(a.pool))
    return 0


if __name__ == '__main__':
    sys.exit(main())
