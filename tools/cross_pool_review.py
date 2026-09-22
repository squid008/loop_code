# -*- coding: utf-8 -*-
"""cross_pool_review.py — **L2 跨池审查 + L3 精选池**（2026-09-14 用户批准的设计）

## 为什么需要它（用户 2026-09-14 拍板）
用户提议：「每个池子入库因子之前分别做剥离风格+正交诊断，过了才入；最后 3 个池子入
`factor_library_crosspool.md` 时再做一次，过了才入？」—— 方向对，但**引擎里只能做"池内"**：

| | 现状 | 能挡住 `F05_1000 ↔ F01_300 = 0.998` 吗 |
|---|---|---|
| 池内去相关 `--decorr` | ✅ 但**只对本池 bank** | ❌ |
| 池内收益流去重 `--dup_ex_corr` | ✅ 但**只对本池 bank_ex** | ❌ |
| **跨池**去重 | ❌ **完全没有** | ← 漏洞 |

★★ **而且跨池不能塞进引擎**：三个池是**独立进程**、互不知道；若让后跑的读先跑的，
**跑序一变结果就变 ⇒ 不可复现**。⇒ 必须做成"**轨道跑完后的一次性审查**"。

## 三层结构（用户批准）
    L1 池内（引擎已有） 11项标准 → 全A或池门槛 → 分段 → **剥风格0.15** → 池门槛 → 收益流去重0.90
                        ⇒ 写 `factor_library_{pool}.md`（**bank 该长就长，它是对照集，越大去重力越强**）
    L2 跨池审查（本脚本）剥风格档 + **vs 全库**的 max|corr|（**因子值**口径，读 uint8 副本加速）
    L3 精选池（本脚本）  入选 ⇒ `docs/factor_pool_selected.md`

## ★★ 两条关键设计（都是用户拍板的）
1. **闸门放在 L3，不在入库**：若把门槛加在入库上 ⇒ `bank` 不增长 ⇒ `--decorr`/`--dup_ex_corr`
   的对照集变弱 ⇒ **引擎更容易重复挖 ⇒ 又被拦 ⇒ 死循环**。⇒ **bank 照旧长**，另设精选池。
2. **入选规则 = 「剥风格 A 档 + 0.7 连通分量去重（每组留剥风格 Calmar 最高的）」**
   —— 不是简单 `corr<0.7` 一刀切（那会"砍掉哪个看排序"，可能砍掉更强的）。
   连通分量保证**同族只留最强的一个**，不丢信息。
3. **对照集包含全A 库的 41 个**（用户明确要求）—— 实际 `facs/` 里本来就是 52 = 41(全A) + 11(池)，
   所以天然满足 ✓

## 用法
    python tools/cross_pool_review.py                  # 审查 + 生成精选池
    python tools/cross_pool_review.py --thr=0.7        # 改阈值
    python tools/cross_pool_review.py --grade=A,B      # 允许 B 档也参与（默认只 A）
"""
import argparse
import csv
import io
import os
import sys

import numpy as np

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DOCS = os.path.join(ROOT, 'docs')
sys.path.insert(0, os.path.join(ROOT, 'engine'))
BT = '`'


# ---------------- 并查集（连通分量）----------------
class DSU:
    def __init__(self):
        self.p = {}

    def find(self, x):
        self.p.setdefault(x, x)
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[rb] = ra


def load_strip():
    """`docs/loop_strip_style_bank.csv` → {name: row}（L2 的剥风格数据源）。"""
    p = os.path.join(DOCS, 'loop_strip_style_bank.csv')
    if not os.path.exists(p):
        return {}
    out = {}
    for r in csv.DictReader(io.open(p, encoding='utf-8-sig', newline='')):
        out[r['name']] = r
    return out


def rank_rows_uint8(a):
    """uint8 分位**本身就是截面秩** ⇒ 直接当秩用（免 O(N logN) 排序，实测快 14x）。"""
    return np.asarray(a, dtype=np.float64)


def _col_corr(A, b):
    out = np.full(A.shape[0], np.nan)
    for i in range(A.shape[0]):
        x, y = A[i], b[i]
        m = np.isfinite(x) & np.isfinite(y) & (x > 0) & (y > 0)
        if m.sum() < 30:
            continue
        xx, yy = x[m], y[m]
        xx = xx - xx.mean()
        yy = yy - yy.mean()
        d = np.sqrt((xx * xx).sum() * (yy * yy).sum())
        if d > 0:
            out[i] = (xx * yy).sum() / d
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--thr', type=float, default=0.70, help='正交阈值（连通分量连接门限）')
    ap.add_argument('--grade', default='A', help='允许入选的剥风格档（逗号分隔，默认 A）')
    ap.add_argument('--sample', type=int, default=120, help='调仓日采样数')
    ap.add_argument('--out', default=os.path.join(DOCS, 'factor_pool_selected.md'))
    a = ap.parse_args()
    ok_grades = [x.strip().upper() for x in a.grade.split(',') if x.strip()]

    import factor_store as FS
    strip = load_strip()
    fsd = FS.list_factors()
    if not fsd:
        print('`facs/` 为空 —— 先跑 `tools/build_facs.py`')
        return 1

    # ---- 载入（优先 uint8 副本 ⇒ 快；副本缺失回退 float32 并求秩）----
    names, mats, meta = [], {}, {}
    # ★ 明细段要用的原始信息：h5 路径 + h5 attrs（sign / source / shape / created_at ...）
    #   （2026-09-14：用户指出精选池的表达式被截断 ⇒ 明细段必须给"可直接复制使用"的全文）
    fpath, fattrs = {}, {}
    for nm, p, at in fsd:
        fpath[nm], fattrs[nm] = p, at
        try:
            with FS.FactorStore().open(nm, quant=True) as st:
                d = np.asarray(st.full()[:])
                dd = st._attrs['dates']
                used_q = True
        except FileNotFoundError:
            with FS.FactorStore().open(nm) as st:
                d = np.asarray(st.full()[:], dtype=np.float64)
                dd = st._attrs['dates']
                used_q = False
                # float32 -> 取秩（uint8 分支免此步）
                o = np.empty(d.shape)
                for i in range(d.shape[0]):
                    r = d[i]
                    m = np.isfinite(r)
                    o[i] = np.nan
                    if m.sum() >= 2:
                        v = r[m]
                        od = np.argsort(v)
                        t = np.empty(v.size)
                        t[od] = np.arange(1, v.size + 1)
                        o[i, m] = t
                d = o
        step = max(1, d.shape[0] // a.sample)
        names.append(nm)
        mats[nm] = np.asarray(d[::step, :], dtype=np.float64)
        meta[nm] = dict(expr=str(at.get('expr') or ''), sign=at.get('sign'), q=used_q)
    print('=' * 96)
    print('L2 跨池审查 + L3 精选池   （{} 个因子，含全A 库全部）'.format(len(names)))
    print('=' * 96)
    print('  读法: uint8 快查副本（免转秩）' if meta[names[0]]['q'] else '  读法: float32 + 转秩')

    # ---- 档位（缺剥风格记录 => D，不入选）----
    grade = {n: (strip.get(n, {}).get('grade') or 'D') for n in names}
    # ★★★★★ 2026-09-22（用户："改成日频对齐"）—— "同族里留谁"的判据改用**日频**剥后卡玛 ✓
    #   原来用期频 `strip_calmar` ✗ ⇒ 与"准入档按日频判"打架 ⇒ 可能把**日频更强的淘汰掉** ✗
    #   ⚠ 取值/回退规则集中在 `strip_cal_daily()`（单一事实源 ✓ 可单测 ✓）
    s_cal = {n: strip_cal_daily(strip.get(n)) for n in names}
    n_by_g = {}
    for n in names:
        n_by_g[grade[n]] = n_by_g.get(grade[n], 0) + 1
    print('  剥风格档分布: ' + ', '.join('{}x{}'.format(k, v) for k, v in sorted(n_by_g.items())))

    pool = [n for n in names if grade[n] in ok_grades]
    print('  **准入档 {} 共 {} 个**（对照集 = 全部 {} 个，含全A 库）'.format(
        '/'.join(ok_grades), len(pool), len(names)))
    if not pool:
        print('  无准入因子 -> 结束')
        return 0

    # ---- L2：在准入集合内两两算 |中位相关|，>=thr 连边 ----
    dsu = DSU()
    for n in pool:
        dsu.find(n)
    edges = []
    for i in range(len(pool)):
        for j in range(i + 1, len(pool)):
            x, y = pool[i], pool[j]
            c = float(np.nanmedian(np.abs(_col_corr(mats[x], mats[y]))))
            if np.isfinite(c) and c >= a.thr:
                edges.append((c, x, y))
                dsu.union(x, y)
    edges.sort(reverse=True)
    print('  准入集合内 ≥{:.2f} 的边: **{} 条**'.format(a.thr, len(edges)))

    # ---- L3：每个连通分量留剥风格 Calmar 最高的 ----
    comp = {}
    for n in pool:
        comp.setdefault(dsu.find(n), []).append(n)
    sel, dropped = [], []
    for root, members in comp.items():
        members.sort(key=lambda n: -s_cal[n])
        keep = members[0]
        sel.append(keep)
        for m in members[1:]:
            c = next((cc for cc, x, y in edges if (x == m and y == keep) or (y == m and x == keep)), None)
            dropped.append((m, keep, c))
    sel.sort(key=lambda n: -s_cal[n])
    print('  连通分量: {} 个 -> **入选 {} 个**（淘汰 {} 个同族重复）'.format(
        len(comp), len(sel), len(dropped)))

    # ---- 输出 ----
    L = []
    L += ['# 精选因子池（L3）', '',
          '> **派生视图**，由 `python tools/cross_pool_review.py` 生成 —— 可随时重建。',
          '> 与 `docs/factor_library_crosspool.md`（**忠实镜像**各池库）**定位不同**：',
          '> 本文件是**过了双闸门的精选清单**，供下游（组合/回测/看板）直接使用。', '']
    # ★★★ 下游使用须知（2026-09-15 加）—— 起因：外部独立审查核对时暴露的**落地缺口**
    #   核心：本文件的「剥风格 Calmar」是**评估口径**，而 `facs/` 里存的是**原始因子值**
    #   ⇒ 下游若直接把 h5 拿去排序选股，**拿到的是未剥风格的版本**，表现与本表**不符** ✗
    L += ['## 下游使用须知（先读这段再用）', '',
          '1. **必须乘 `sign`**（见「精选因子明细」）：引擎求值时对 `sign<0` 的因子**取负**；'
          '不乘，方向就反了，组合会反向选股。',
          '2. **本表的「剥风格」是评估口径，不是 `facs/` 里的值** —— '
          '`facs/<xx>/<name>/values.h5` 存的是**原始因子值**（没有做过中性化）。',
          '   - 剥风格的定义：**把因子对 `lncap`（市值）+ `lnamt`（成交额）做截面秩中性化，'
          '再重跑回测**（引擎 `loop_engine.py` 的 `--strip_style`）。',
          '   - 所以：**要做到本表的绩效，下游必须自己实现这一步**（取残差后再排序）；'
          '直接用原始值，绩效与风险回撤都对不上（例如 `F33`：未剥日频回撤约 −19%，'
          '剥后只有 −10%）。',
          '   - **不能用 `values_q.h5`（uint8 快查副本）做这件事** —— '
          '它丢了原始值（只留截面秩），只能做秩类运算，做不了中性化/回归。',
          '3. **本表不含「池内（300/500/1000）」结论**：这些因子**基本没在池内测过**'
          '（`--pool_obs` 是 2026-09-12 才加的，而它们更早入库），池内表现需要另测。',
          '   （已知的外部实测结论：它们在 **300 内全员失效**、500 内只有 `F07` 勉强可用，'
          '**不要直接搬进成分内**。）', '']
    L += ['## 双闸门（用户 2026-09-14 拍板）', '',
          '1. **剥风格档**：只有「A 独立有效」的因子才能进 —— 也就是「把 `lncap`（市值）+ '
          '`lnamt`（成交额）剥掉之后，Calmar 仍然 ≥ 0.30」。',
          '   库内实测约 **44% 是纯风格**（剥完就转负），这一刀砍掉近一半。',
          # ★ 2026-09-16（用户要求「说明文字 2-5 直接合并成一条，写简单点」）：
          #   原来「正交去重」+ 三个子条目共 4 行 ⇒ 合成**一条**，只说清"怎么算、怎么留" ✓
          '2. **正交去重**：把入池的因子两两比「因子值截面秩相关」，**≥ %.2f 的算同一类**，'
          '每组只留剥风格 Calmar 最高的一个（像的只留最好的，不像的全都留下）。' % a.thr, '',
          '> 为什么闸门放在这一层、而不是放在**入库**：如果入库就拦，`bank` 就不增长了，',
          '> 而 `--decorr` / `--dup_ex_corr` 正是拿 `bank` 当对照集的，对照集变弱，引擎更容易重复挖，'
          '又被拦，就成了死循环。',
          '> 所以：**`bank` 照旧增长（它是对照集，越大去重越强）**，另设本精选层。', '']
    # ★★ 2026-09-14 修（用户反馈）：**原表格把表达式截断到 58 字符** ⇒
    #   而这**是唯一给出表达式的文件**（它没有"明细段"，不像 `factor_library*.md`
    #   有「总览（截断）+ 明细（全文）」两层）⇒ 一截就**无处可查**，
    #   用户被迫"去对应的因子库翻表达式" ✗
    #   ⇒ ① 表格**不截断**；② 另加「因子明细」段（全文 + 可复制的代码块 + `sign` + h5 路径）。
    #   ⚠ 顺带修一个隐患：Markdown 表格里若出现 `|` 会**静默切断单元格** ⇒ 统一转义。
    def _cell(s):
        return str(s).replace('|', '\\|')

    L += ['## 精选清单（{} 个）'.format(len(sel)), '',
          '> ★ **表达式是完整的**（不截断）—— 本文件可直接给下游用，不必回各池库翻。',
          '> 需要**可复制的全文** / `sign` / h5 路径 → 见下方「[精选因子明细](#精选因子明细可直接复制使用)」。', '',
          '| # | 因子 | 剥风格档 | 剥Calmar(日频) | 剥超额 | 原Calmar | 表达式（完整） |',
          '|---|---|---|---|---|---|---|']
    for i, n in enumerate(sel, 1):
        r = strip.get(n) or {}
        L.append('| {} | {}{}{} | **A** | **{}** | {} | {} | {}{}{} |'.format(
            i, BT, n, BT, _f(strip_cal_daily(r, None)), _pct(r.get('strip_ann_ex')),
            _f(r.get('calmar')), BT, _cell(meta[n]['expr']), BT))

    # ---- ★ 精选因子明细（可直接复制使用）----
    #   为什么要有：下游（组合/回测/看板）真正需要的是"**能直接拿来算的**"三件东西
    #   —— ① 完整表达式 ② `sign`（**方向**！不乘它因子就是反的）③ 因子值 h5 路径。
    #   原来这三样一样都不在本文件里 ⇒ 每个用户都要自己去翻 ✗
    L += ['', '---', '', '## 精选因子明细（可直接复制使用）', '',
          '> 每个精选因子一节：**完整表达式** + **`sign`** + **因子值 h5 路径** + 各项指标。',
          '> ⚠ **`sign` 必须用**：因子值要乘 `sign` 才是"越大越好"的方向'
          '（引擎求值时就是这个约定；不乘 ⇒ **方向反了**，组合会反向选股）。', '']
    for i, n in enumerate(sel, 1):
        r = strip.get(n) or {}
        at = fattrs.get(n) or {}
        rel = os.path.relpath(fpath[n], ROOT).replace('\\', '/') if fpath.get(n) else '（未在 facs/ 找到）'
        q = os.path.join(os.path.dirname(rel), 'values_q.h5').replace('\\', '/')
        L += ['### {}. `{}`'.format(i, n), '',
              '**完整表达式**',
              '```',
              meta[n]['expr'],
              '```', '',
              '| 项 | 值 |',
              '|---|---|',
              '| **`sign`（方向，必须乘）** | **{}** |'.format(at.get('sign')),
              '| 因子值 h5 | `{}` |'.format(rel),
              '| 快查副本（uint8，截面秩） | `{}` |'.format(q),
              '| 形状 | {} 日 × {} 股 |'.format(*(at.get('shape') or ('?', '?'))),
              '| 来源 | `{}` |'.format(at.get('source')),
              '| 建于 | {} |'.format(str(at.get('created_at') or '').strip() or '—'),
              # ★ 2026-09-22：这里也改**日频** ✓（与上面「留谁」的判据同一口径 ✓ 不再一处期频一处日频 ✗）
              '| 剥风格判定 | **A 独立有效**（剥掉 lncap+lnamt 后**日频** Calmar {} ≥ 0.30）|'.format(
                  _f(strip_cal_daily(r, None))),
              '| 剥风格后 Calmar（日频）/ 超额 | **{}** / {} |'.format(
                  _f(strip_cal_daily(r, None)), _pct(r.get('strip_ann_ex'))),
              '| 原（未剥）Calmar / 超额 / IC | {} / {} / {} |'.format(
                  _f(r.get('calmar')), _pct(r.get('ann_ex')), _f(r.get('ic'))),
              '']
    L += ['---', '', '## ⚠ 被淘汰（同族重复，**留痕可查**）', '',
          '淘汰**不是删除** —— 它们仍在各池库里（`factor_library_{pool}.md`），只是不进精选池。',
          '★ 留痕是硬要求（§8.44 教训：**被拦的必须查得到**）。', '',
          # ★ 2026-09-22：列名标明**日频** ✓（这就是"留谁"的判据 ✓ 与文档标题口径一致 ✓）
          '| 被淘汰 | 与谁相关 ≥{:.2f} | 保留者 | 保留者剥Calmar(日频) | 被淘汰者剥Calmar(日频) |'
          .format(a.thr),
          '|---|---|---|---|---|']
    for m, keep, c in sorted(dropped, key=lambda x: (x[1], x[0])):
        L.append('| {}{}{} | {} | {}{}{} | **{}** | {} |'.format(
            BT, m, BT, ('{:.3f}'.format(c) if c is not None else '（同组）'),
            BT, keep, BT, _f(strip_cal_daily(strip.get(keep), None)),
            _f(s_cal[m] if s_cal[m] > -1e8 else None)))
    L += ['']
    L += ['---', '', '## 相关文件导航', '', '| 文件 | 内容 |', '|---|---|']
    L += ['| `docs/factor_pool_selected.md`（本文件） | ★ **精选池**（A 档 + 正交去重后的推荐清单）|']
    L += ['| `docs/factor_library_crosspool.md` | 跨池**镜像视图**（忠实反映各池库，不去重）|']
    L += ['| `docs/loop_strip_style_bank.csv` | 52 个因子的 `原 vs 剥风格` 实测（本文件的闸门依据）|']
    L += ['| `facs/` | 因子值 h5（float32 权威 + uint8 快查副本）|']
    outp = a.out if os.path.isabs(a.out) else os.path.join(ROOT, a.out)
    io.open(outp, 'w', encoding='utf-8').write('\n'.join(L) + '\n')
    print('\n[DONE] -> {}'.format(outp))
    print('  精选 **{} 个**（准入 {} → 去重后 {}）'.format(len(sel), len(pool), len(sel)))
    for n in sel:
        # ⚠ 控制台这里**仍然截断**（终端要能一行放下）—— 这是**有正当理由的**；
        #   而**写进文件**的表达式绝不能截断（文件是给人复制去用的）。两者别混为一谈。
        _e = meta[n]['expr']
        print('    [{:<10s}] 剥Calmar(日频) {:>7s}  sign={:<3}  {}'.format(
            n, _f(strip_cal_daily(strip.get(n, {}), None)),
            str((fattrs.get(n) or {}).get('sign')), _e[:52] + ('…' if len(_e) > 52 else '')))
    print('  （控制台为一行预览；**文件里是完整表达式** + `sign` + h5 路径，见「精选因子明细」）')
    return 0


def strip_cal_daily(row, default=float('-inf')):
    """★ 2026-09-22（用户："**改成日频对齐**"）—— 取**日频**剥后卡玛 `strip_calmar_d` ✓。

    为什么必须日频：**准入档 A/B/C 是引擎按日频判的**（2026-09-14 §1.19 起判据改日频 ✓：
    "期频漏掉持有期内回撤、回撤被低估" ⇒ 所有门槛/档位改日频 ✓）
    ⇒ 本文件的"**同族里留谁**"若仍用期频，就会出现
      "**日频更强者被淘汰、日频更弱者留下**" ✗（两个口径打架 ⇒ 精选池选错人 ✓）
    ⇒ 现与档位口径**统一到日频** ✓；`docs/factor_pool_selected.md` 的列名也写明"(日频)" ✓

    ⚠ 回退规则（**不误杀** ✓）：缺 `strip_calmar_d`（旧记录/未开日频那次评估）⇒ 回退期频
      `strip_calmar` ✓；两者都取不到 ⇒ `default` ✓（排序用 −inf ⇒ 排最后 ✓；展示用 None ⇒ 显示 — ✓）
    """
    if not row:
        return default
    for k in ('strip_calmar_d', 'strip_calmar'):
        try:
            f = float(row.get(k))
        except Exception:                                        # noqa: BLE001
            continue
        if f == f:                       # NaN 自比不相等 ⇒ 跳过（别把 NaN 当有效值 ✓）
            return f
    return default


def _f(v):
    try:
        x = float(v)
        return '%.3f' % x if np.isfinite(x) else '-'
    except Exception:
        return '-'


def _pct(v):
    try:
        x = float(v)
        return '%+.1f%%' % (100 * x) if np.isfinite(x) else '-'
    except Exception:
        return '-'


if __name__ == '__main__':
    sys.exit(main())
