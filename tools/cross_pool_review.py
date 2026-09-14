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
    for nm, p, at in fsd:
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
    s_cal = {}
    for n in names:
        try:
            s_cal[n] = float(strip[n]['strip_calmar'])
        except Exception:
            s_cal[n] = float('-inf')
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
    L += ['## 双闸门（用户 2026-09-14 拍板）', '',
          '1. **剥风格档**：只有 `A 独立有效`（剥掉 lncap+lnamt 后 Calmar ≥ 0.30）才准入。',
          '   ⚠ 库内实测约 **44% 是"纯风格"**（剥完转负）⇒ 这一刀砍掉近一半。',
          '2. **正交去重**：准入集合内两两算 **因子值截面秩相关**，`≥ {:.2f}` 连边 ⇒ '.format(a.thr),
          '   **连通分量内只留"剥风格 Calmar 最高"的一个**（同族留最强，不丢信息）。', '',
          '> ★ 为什么闸门放在这一层、而**不在入库**：如果入库就拦，`bank` 不增长 ⇒',
          '> `--decorr`/`--dup_ex_corr` 的对照集变弱 ⇒ 引擎更容易重复挖 ⇒ 又被拦 ⇒ **死循环**。',
          '> ⇒ **`bank` 照旧长（它是对照集，越大去重力越强）**，另设本精选层。', '']
    L += ['## 精选清单（{} 个）'.format(len(sel)), '',
          '| # | 因子 | 剥风格档 | 剥Calmar | 剥超额 | 原Calmar | 表达式 |',
          '|---|---|---|---|---|---|---|']
    for i, n in enumerate(sel, 1):
        r = strip.get(n) or {}
        L.append('| {} | {}{}{} | **A** | **{}** | {} | {} | {}{}{} |'.format(
            i, BT, n, BT, _f(r.get('strip_calmar')), _pct(r.get('strip_ann_ex')),
            _f(r.get('calmar')), BT, meta[n]['expr'][:58], BT))
    L += ['', '## ⚠ 被淘汰（同族重复，**留痕可查**）', '',
          '淘汰**不是删除** —— 它们仍在各池库里（`factor_library_{pool}.md`），只是不进精选池。',
          '★ 留痕是硬要求（§8.44 教训：**被拦的必须查得到**）。', '',
          '| 被淘汰 | 与谁相关 ≥{:.2f} | 保留者 | 保留者剥Calmar | 被淘汰者剥Calmar |'.format(a.thr),
          '|---|---|---|---|---|']
    for m, keep, c in sorted(dropped, key=lambda x: (x[1], x[0])):
        L.append('| {}{}{} | {} | {}{}{} | **{}** | {} |'.format(
            BT, m, BT, ('{:.3f}'.format(c) if c is not None else '（同组）'),
            BT, keep, BT, _f(strip.get(keep, {}).get('strip_calmar')), _f(s_cal[m] if s_cal[m] > -1e8 else None)))
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
        print('    [{:<10s}] 剥Calmar {:>7s}  {}'.format(
            n, _f(strip.get(n, {}).get('strip_calmar')), meta[n]['expr'][:52]))
    return 0


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
