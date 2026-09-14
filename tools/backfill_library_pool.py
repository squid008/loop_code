# -*- coding: utf-8 -*-
"""backfill_library_pool.py — 补录**各池**已入库但因 bug / 事故而从没写进文档的因子

背景（2026-09-13 ~ 09-14）：
  ① `set_mine_pool` 把 `LIBRARY` 派生成 `docs/factor_library_{pool}.md`，但这三个文件
     **从来没被创建过**；而 `_lib_sync` 开头是
        `if not added_exprs or not os.path.exists(LIBRARY): return`
     ⇒ **静默跳过** ⇒ 池轨道入库的因子**一个都没进文档**。
  ② ★★ 更严重：**`--mine_pool=300/500` 的 state 曾在 2026-09-13 被误删**
     （`_cleanup_prerun.py` 重复执行的事故，roadmap §8.26；**state 不可恢复**）
     ⇒ 那两个池"**曾经入库**"的因子**已不在 `state.bank` 里**：
        · 300：gen1 累计 1 → **gen4 又从"累计 1"重头数**（证明当时是空 state 起跑）⇒ 丢 1 个
        · 500：gen1 累计 1 → gen3 累计 2 ⇒ 事故后 bank 归零 ⇒ **丢 2 个**
        · 1000：事故之后才建的 ⇒ 3 个无损
  ⇒ 所以**不能只用 `state.bank` 当口径**（那会把"曾入库"的因子永久漏掉）。
     **改用双证据**：
       · **archive 的 `passed=True`**（= 过了 L2；`docs/loop_archive_{pool}.csv` 永久留档）
       · **各代日志的 `入库 N 个新因子`**（= 事实上真的进了 bank）—— 两者**逐代核对**
  ⇒ 文档里会**如实标注**该因子现在还在不在 `bank` 里。

用法:
  python tools/backfill_library_pool.py                     # DRY-RUN：先看口径核对表
  python tools/backfill_library_pool.py --apply             # 写盘
  python tools/backfill_library_pool.py --bank-only         # 只补"当前 bank 里"的（旧口径）
  python tools/backfill_library_pool.py --apply --ensure-all # 顺带给每个池建骨架(0 入库也建)
"""
import argparse
import glob
import io
import os
import pickle
import re
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DOCS = os.path.join(ROOT, 'docs')
sys.path.insert(0, os.path.join(ROOT, 'engine'))

LOST_NOTE = (
    '> ⚠⚠ **本池 state 曾在 2026-09-13 被误删**（`_cleanup_prerun.py` 重复执行的事故，'
    'roadmap §8.26；**state 不可恢复**）⇒ 下列因子中**有 {n} 个已不在 `state.bank` 里**。\n'
    '> 它们的**指标与表达式仍完整留档**在 `docs/loop_archive{sfx}.csv`（`passed=True` 行），\n'
    '> 本文档据「archive 过 L2」+「当时日志的 `入库 N 个新因子`」双证据补录 ⇒ **如实保留，不抹掉**。\n'
)


def read_log(path):
    """宽容读日志（utf-8 → gbk）。"""
    if not os.path.exists(path):
        return ''
    try:
        raw = open(path, 'rb').read()
    except Exception:
        return ''
    for enc in ('utf-8', 'gbk', 'cp936'):
        try:
            s = raw.decode(enc)
            if s.count('\ufffd') == 0:
                return s
        except Exception:
            continue
    return raw.decode('utf-8', errors='replace')


def gen_registered_counts(pool):
    """从历史日志里读「每代入库了几个」—— 证据 B。

    日志来源（两处，因为轨迹换过驱动器）：
      · `ai_test/_night/pool{pool}_gen*.log`（旧：night_pipeline）
      · `ai_test/_tracks/pool_{pool}_gen*.log`（新：run_tracks）
    """
    out = {}
    pats = [os.path.join(HERE, '_night', 'pool%s_gen*.log' % pool),
            os.path.join(HERE, '_tracks', 'pool_%s_gen*.log' % pool)]
    for pat in pats:
        for f in glob.glob(pat):
            if '_err' in f:
                continue
            m = re.search(r'gen(\d+)\.log$', f)
            if not m:
                continue
            g = int(m.group(1))
            t = read_log(f)
            k = re.findall(r'入库 (\d+) 个新因子', t)
            if k:
                out[g] = int(k[-1])
    return out


def ensure_scope_note(pool, obs_path, lib):
    """在池文档头部写明「**本池轨迹的池口径**」—— 独立步骤，与是否补录无关。

    ★★ 为什么必须写（2026-09-14 发现的一个真缺陷）：
      池标签由 `loop_pools.derive_tag(ok_all, ok_by_pool, pools)` 派生 ⇒
      **它是"当时测了哪些池"的函数**。而引擎 `--pools` 的默认值是 `300,500`
      （`parse_pools(getattr(args,'pools','300,500'))`），**早期批次没显式传 1000**
      ⇒ 那些行**根本就没测 1000**。
      实测同一个式子 `corr100(cs_scale(mf_x_sell), mf_l_sell)`：
        · `1000` 池 gen1（**三池都测**）⇒ 标签 **`csi1000_all`** —— 全A + 1000 池通过
        · ` 500` 池 gen1（**只测 300/500**）⇒ 标签 **`csi_all_only`** —— 字面是
          「只有全A通过 ⇒ 小盘/流动性溢价嫌疑，指数增强不可用」，**其实只是没测 1000** ⇒ **会冤枉因子**
      ⇒ 所以**每条池轨迹文档都必须写清测过的池集合**，否则标签**不能跨批次直接比**。
    """
    import pandas as pd
    if not os.path.exists(lib) or not os.path.exists(obs_path):
        return
    try:
        o = pd.read_csv(obs_path)
        if not len(o) or 'pool' not in o.columns or 'gen' not in o.columns:
            return
        o['pool'] = o['pool'].astype(str)
        o['gen'] = o['gen'].astype(int)
    except Exception:
        return
    txt = io.open(lib, encoding='utf-8').read()
    # ★ 幂等：**先删掉旧的标注块再插新的**（而不是"已存在就跳过"）——
    #   否则标注逻辑改进后（本次就改了粒度：文件级并集 → 逐代）旧文本会永久占位。
    txt = re.sub(r'>\s*★\s*\*\*本池轨迹的池口径[\s\S]*?(?=\n---\n|\n## |\Z)',
                 '', txt, count=1)
    # ★ 逐代统计（**关键**：`loop_pool_obs_*.csv` 是累积文件，
    #   文件级并集会把"早期只测两池"的历史掩盖掉）
    union = sorted(o['pool'].unique())
    per_gen = {}
    for g, sub in o.groupby('gen'):
        per_gen[int(g)] = sorted(sub['pool'].unique())
    # 把"池集合相同的连续代"合并成区间，便于阅读
    rows, prev, start = [], None, None
    for g in sorted(per_gen):
        if per_gen[g] != prev:
            if prev is not None:
                rows.append((start, last, prev))
            prev, start = per_gen[g], g
        last = g
    rows.append((start, last, prev))
    lines = []
    for g0, g1, ps in rows:
        tag = 'gen%d' % g0 if g0 == g1 else 'gen%d~%d' % (g0, g1)
        miss = [x for x in union if x not in ps]
        lines.append('>   · %-14s `--pools=%s`%s'
                     % (tag, ','.join(ps),
                        '   ⚠ **未测 %s**' % '/'.join(miss) if miss else ''))
    head = ('> ★ **本池轨迹的池口径（逐代）**：据 `loop_pool_obs%s.csv` 的 pool 列。\n'
            % ('' if pool == 'all' else '_' + pool))
    foot = ('> ⚠ 池标签是「**在这些池上**测出来的」⇒ **不同代的标签不能直接比**。\n'
            '> 典型陷阱：只测 300/500 时，因子会被标成 `csi_all_only`（「只有全A通过 ⇒ '
            '小盘溢价嫌疑、指数增强不可用」）—— **其实只是没测 1000**。\n')
    line = head + '\n'.join(lines) + '\n' + foot
    anchor = '\n---\n\n## 因子总览'
    txt = (txt.replace(anchor, '\n' + line + anchor, 1) if anchor in txt
           else line + '\n' + txt)
    io.open(lib, 'w', encoding='utf-8').write(txt)
    print('    [标注] 已写明**逐代**池口径: %s'
          % '; '.join('%s=%s' % ('gen%d' % g, ','.join(p)) for g, p in sorted(per_gen.items())))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pools', default='300,500,1000')
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--bank-only', action='store_true',
                    help='只用 state.bank 当口径（旧行为；会漏掉"曾入库但 state 丢了"的）')
    ap.add_argument('--ensure-all', action='store_true',
                    help='给每个池建骨架（0 入库也建），避免"文件缺失 = 含义不明"')
    a = ap.parse_args()

    import numpy as np
    import pandas as pd
    import loop_engine as LE
    import loop_pools as LP

    # ⚠ state pkl 是引擎**以 `__main__` 身份运行**时 pickle 的 ⇒ 先把引擎的类注入 `__main__`
    #   否则 unpickle 会报 `Can't get attribute 'Node' on <module '__main__'>`。
    for _n in dir(LE):
        if _n[:1].isupper() and isinstance(getattr(LE, _n), type):
            setattr(sys.modules['__main__'], _n, getattr(LE, _n))

    def bank_exprs():
        if not os.path.exists(LE.STATE):
            return set()
        try:
            st = pickle.load(open(LE.STATE, 'rb'))
            return {str(x) for x in (st.get('bank', []) or [])}
        except Exception as e:
            print('    [!] 读 state 失败(%s) -> 退回空集' % type(e).__name__)
            return set()

    pools = [x.strip() for x in a.pools.split(',') if x.strip()]
    print('=' * 84)
    print('模式:', 'APPLY(写盘)' if a.apply else 'DRY-RUN(只报告)')
    print('口径:', '**仅当前 bank**（旧；会漏"曾入库"）' if a.bank_only
          else '**archive 过 L2 + 日志入库数**（双证据，含"曾入库但 state 丢了"）')
    print('=' * 84)

    total = 0
    for pool in pools:
        LE.set_mine_pool(pool)
        arch, obs = LE.ARCHIVE, LE.POOL_OBS
        print('\n--- pool=%s ---' % pool)
        lib = LE.LIBRARY
        print('    文档: %s  (%s)' % (
            os.path.relpath(lib, ROOT), '已存在' if os.path.exists(lib) else '**不存在**'))
        # ★ 独立步骤：不管有没有东西补录，都保证文档头部写明「本池轨迹的池口径」
        #   （它的正确性不依赖本次是否补录；见 ensure_scope_note 的 docstring）
        ensure_scope_note(pool, obs, lib)
        if not os.path.exists(arch):
            print('    档案不存在 -> 跳过')
            continue
        d = pd.read_csv(arch)
        if 'passed' not in d.columns:
            print('    档案无 passed 列 -> 跳过')
            continue
        passed = d[d['passed'].astype(str).str.lower().isin(('true', '1'))].copy()
        passed['expr'] = passed['expr'].astype(str)
        bk = bank_exprs()
        reg = gen_registered_counts(pool)          # 证据 B: 每代入库数

        # ---- 口径核对表（**让人一眼看出每代过 L2 几个、日志说入库几个**）----
        print('    口径核对（每代）:')
        print('      %-6s %-12s %-12s %s' % ('代', '过L2数', '日志入库数', '当前在 bank?'))
        keep_rows = []
        for g, sub in passed.groupby('gen'):
            g = int(g)
            n_reg = reg.get(g, None)
            inb = sum(1 for e in sub['expr'] if e in bk)
            print('      %-6d %-12d %-12s %d/%d' % (
                g, len(sub), ('%d' % n_reg) if n_reg is not None else '(无日志)',
                inb, len(sub)))
            if a.bank_only:
                keep_rows.append(sub[sub['expr'].isin(bk)])
            else:
                # 双证据：过 L2 **且** 该代日志确认有入库（个数不足时按指标取前 N）
                if n_reg is None or n_reg <= 0:
                    print('        -> 该代日志无"入库>0"记录 ⇒ 不补录（可能被 FSA/收益流去重拦下）')
                    continue
                if n_reg < len(sub):
                    sub = sub.sort_values('calmar', ascending=False).head(n_reg)
                    print('        -> 该代入库 %d 个 < 过 L2 %d 个 ⇒ 按 Calmar 取前 %d（口径为上界）'
                          % (n_reg, len(passed[passed['gen'] == g]), n_reg))
                keep_rows.append(sub)
        q = (pd.concat(keep_rows, ignore_index=True) if keep_rows else pd.DataFrame())
        # ★ 去重：文档里**已经有**的表达式不再写（否则重跑一次就重复一条）
        if len(q) and os.path.exists(lib):
            _txt = io.open(lib, encoding='utf-8').read()
            _dup = [e for e in q['expr'] if e in _txt]
            if _dup:
                print('    已有 %d 个在文档中 -> 跳过（防重复）' % len(_dup))
                q = q[~q['expr'].isin(_dup)].reset_index(drop=True)
        n_lost = int(len(q) - q['expr'].isin(bk).sum()) if len(q) else 0
        if not len(q):
            print('    无可补录因子（均已入档）')
            if a.apply and a.ensure_all and not os.path.exists(lib):
                LE._mk_library_skeleton(os.path.basename(lib))
                print('    [ensure-all] 已建骨架（0 入库）->', os.path.relpath(lib, ROOT))
            continue
        print('    待补录 %d 个（其中 **%d 个已不在 bank**：state 丢失的）' % (len(q), n_lost))
        for _, r in q.iterrows():
            mark = '  ' if str(r['expr']) in bk else '★丢'
            print('      %s gen%-2d %s' % (mark, int(r['gen']), str(r['expr'])[:84]))
        if not a.apply:
            continue

        o = pd.read_csv(obs) if os.path.exists(obs) else pd.DataFrame()
        if not os.path.exists(lib):
            LE._mk_library_skeleton(os.path.basename(lib))
            print('    [建骨架]', os.path.relpath(lib, ROOT))
        n_before = 0
        for g, sub in q.groupby('gen'):
            res = sub.copy()
            by_expr = {}
            for e in res['expr']:
                try:
                    by_expr[e] = LE.parse_expr(e)
                except Exception:
                    pass
            tags = {}
            for _, r in res.iterrows():
                e = str(r['expr'])
                s2 = (o[o['expr'].astype(str) == e]
                      if ('expr' in getattr(o, 'columns', [])) else pd.DataFrame())
                if len(s2) and 'pool' in s2.columns:
                    okp = {str(p): bool(np.isfinite(v) and v > LP.TAG_POOL_FLOOR)
                           for p, v in zip(s2['pool'], s2['ann_ex'])}
                else:
                    okp = {}
                oka = bool(np.isfinite(r['ann_ex']) and r['ann_ex'] > 0
                           and np.isfinite(r['calmar']) and r['calmar'] >= LP.TAG_CAL_MIN)
                tags[e] = LP.derive_tag(oka, okp, ['300', '500', '1000'])
            n_before += len(res)
            LE._lib_sync(int(g), res, n_before, list(res['expr']), by_expr, pool_tags=tags)
            total += len(res)
        # ---- state 丢失的如实标注（**不抹掉历史**）----
        if n_lost:
            txt = io.open(lib, encoding='utf-8').read()
            note = LOST_NOTE.format(n=n_lost,
                                    sfx='' if pool == 'all' else '_' + pool)
            anchor = '\n---\n\n## 因子总览'
            if anchor in txt:
                txt = txt.replace(anchor, '\n' + note + anchor, 1)
            else:
                txt = note + '\n' + txt
            io.open(lib, 'w', encoding='utf-8').write(txt)
            print('    [标注] 已在文档头部写明「%d 个已不在 bank」' % n_lost)

    print()
    if a.apply:
        print('完成：共补录 %d 条' % total)
    else:
        print('（DRY-RUN；确认后加 --apply 写盘）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
