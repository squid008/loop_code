# -*- coding: utf-8 -*-
"""combo_calib.py — ①池内有效候选深挖 ②门槛**组合**标定（roadmap §8.26）

为什么必须做"组合"标定（§8.25-④ 的教训）：
  §8.24 逐门标定时每道门单独看都不错，**但 L2 的门是 AND 链** ⇒ 联合保留率 ≈ 各门之**乘积**
  ⇒ 实测把候选杀光（300 池 30→0）。⇒ 必须直接搜"门的组合"。

本脚本回答两件事：
  A. **池内有效的那批候选好不好**（300 有 23/30、500 有 19/30 池内 Calmar>0）——
     它们的池内 Calmar/超额分布、表达式长什么样、是否也过全A 口径。
  B. **门槛组合怎么定**：在 (`min_calmar`, `min_sharpe`, `min_pool_calmar`) × (AND / OR)
     上网格搜索，按「联合精确率 / 召回 / **提升**」排序，为 `--min_sharpe` 与
     `--pool_gate_or_all` 给出**有依据的取值**。

真值 = `strip_calmar > 0`（剥 lncap+lnamt 后仍为正 = 真信号）。
口径：提升 = 保留集真信号占比 ÷ 全集基线占比；**>1 才有筛选力**；**必须看同等保留量**（保留 2 个的提升是假象）。

用法: python tools/combo_calib.py
"""
import io
import os
import sys

import numpy as np
import pandas as pd

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DOCS = os.path.join(ROOT, 'docs')
OUT = os.path.join(HERE, '_combo_calib.md')


def rd(name):
    p = os.path.join(DOCS, name)
    if not os.path.exists(p):
        return None
    try:
        return pd.read_csv(p)
    except Exception:
        return None


def build(pool):
    ar, st, po = (rd(f'loop_archive_{pool}.csv'),
                  rd(f'loop_strip_style_{pool}.csv'),
                  rd(f'loop_pool_obs_{pool}.csv'))
    if ar is None or st is None or po is None:
        return None
    po['pool'] = po['pool'].astype(str)          # ★ CSV 往返会把 '300' 变 int64
    w = ar[['gen', 'expr', 'ic', 'calmar', 'ann_ex', 'sharpe', 'turn', 'neg_yr',
            'passed']].rename(columns={'ic': 'ic_l1', 'calmar': 'cal_all'})
    w = w.merge(st[['expr', 'strip_calmar', 'strip_ann_ex']], on='expr', how='left')
    pw = po.pivot_table(index='expr', columns='pool', values='calmar', aggfunc='first')
    px = po.pivot_table(index='expr', columns='pool', values='ann_ex', aggfunc='first')
    for k in ('300', '500'):
        w[f'cal_{k}'] = w['expr'].map(pw[k]) if k in pw.columns else np.nan
        w[f'ex_{k}'] = w['expr'].map(px[k]) if k in px.columns else np.nan
    w['cal_pool'] = w[f'cal_{pool}']
    w['ex_pool'] = w[f'ex_{pool}']
    w['pool'] = pool
    w['_y'] = (w['strip_calmar'] > 0).fillna(False)   # ★ 显式布尔, NaN->False
    return w


def ev(d, mask, name):
    m = np.isfinite(d['cal_all'].values) & np.isfinite(d['sharpe'].values)
    mask = mask & m
    y = d['_y'].values.astype(bool)
    n = int(m.sum())
    base = y[m].mean() if n else np.nan
    kept = int(mask.sum())
    tp = int((y & mask).sum())
    if not kept or not n:
        return None
    return dict(name=name, n=n, kept=kept, tp=tp, prec=tp / kept,
                rec=tp / max(int(y[m].sum()), 1), lift=(tp / kept) / base if base else np.nan)


def main():
    ds = [x for x in (build('300'), build('500')) if x is not None]
    if not ds:
        print('无池数据')
        return 0
    comb = pd.concat(ds, ignore_index=True)
    L = ["# 池内有效候选深挖 + 门槛**组合**标定（roadmap §8.26）", "",
         "数据：`docs/loop_archive_{300,500}.csv` + `loop_strip_style_*` + `loop_pool_obs_*`"
         "（**含基线 gen1-2 与验收 gen3，共 %d 个 L2 候选**）" % len(comb),
         "真值 = **`strip_calmar > 0`**（剥风格后仍为正）", ""]

    # ---------- A. 池内有效候选深挖 ----------
    L += ["## A. 池内有效候选深挖", ""]
    for pool, d in ((p, x) for p, x in (('300', ds[0]), ('500', ds[1]))):
        good = d[d['cal_pool'] > 0].copy()
        L += [f"### {pool} 池：池内 Calmar > 0 的候选（{len(good)}/{len(d)} = "
              f"{len(good)/len(d):.0%}）", "",
              "| 指标 | 池内 Calmar | 池内超额 | 全A Calmar | 全A 夏普 | 剥风格后 Calmar |",
              "|---|---|---|---|---|---|"]
        for c, lab in (('cal_pool', ''), ('ex_pool', ''),
                       ('cal_all', ''), ('sharpe', ''), ('strip_calmar', '')):
            s = good[c].dropna()
            if len(s):
                L.append(f"| {c} 分位 | 中位 **{s.median():.3f}** | p25 {s.quantile(.25):.3f} | "
                         f"p75 {s.quantile(.75):.3f} | max {s.max():.3f} | min {s.min():.3f} |")
        L.append("")
        # 池内 Calmar top5(去重表达式)
        top = good.nlargest(5, 'cal_pool')
        L += ["**池内最强 Top5（去重）**", "",
              "| 表达式 | 池内Cal | 池内超额 | 全A cal | 夏普 | 剥风格cal |", "|---|---|---|---|---|---|"]
        for _, r in top.iterrows():
            L.append(f"| `{str(r['expr'])[:78]}` | {r['cal_pool']:+.3f} | "
                     f"{r['ex_pool']*100:+.2f}% | {r['cal_all']:+.3f} | {r['sharpe']:+.2f} | "
                     f"{r['strip_calmar']:+.3f} |")
        L += ["", "> ⚠ `池内 Calmar > 0` 是**很低**的门槛（约一半候选都能过）⇒ "
              "真正要看的是**分布的上尾**与「是否同源」（见下）。", ""]

    # 池内有效性 vs 全A 有效性：是否同源？
    L += ["### A2. 池内有效 与 全A 有效，是同一批吗？", "",
          "| 池 | 池内>0 且 全A>0 | 池内>0 但 全A<=0 | 池内<=0 但 全A>0 | 都<=0 |",
          "|---|---|---|---|---|"]
    for p, d in (('300', ds[0]), ('500', ds[1])):
        a = d['cal_pool'] > 0
        b = d['cal_all'] > 0
        m = d['cal_pool'].notna() & d['cal_all'].notna()
        L.append(f"| {p} | {int((a & b & m).sum())} | {int((a & ~b & m).sum())} | "
                 f"{int((~a & b & m).sum())} | {int((~a & ~b & m).sum())} |")
    L += ["",
          "> 若「池内>0 但 全A<=0」占多数 ⇒ **池内有效与全A 有效基本不同源** "
          "⇒ 同时要求两者达标(AND)**必然自相矛盾** ⇒ 应该用 **OR**。", ""]

    # ---------- B. 门槛组合标定 ----------
    L += ["## B. 门槛**组合**标定（核心）", "",
          "网格：`cal_all > c` × `sharpe > s` × `cal_pool >= p`，模式 **AND / OR**。",
          "`OR` 语义 = `(cal_all>c 且 sharpe>s)` **或** `(cal_pool>=p)` —— 对应拟新增的 `--pool_gate_or_all`。", ""]
    grid_c = [0.0]
    grid_s = [-1.0, 0.0, 0.25, 0.5, 0.75]
    grid_p = [0.0, 0.05, 0.10, 0.15, 0.20]
    best = {}
    for mode in ('AND', 'OR'):
        for c in grid_c:
            for s in grid_s:
                for p in grid_p:
                    ca = comb['cal_all'] > c
                    sh = comb['sharpe'] > s
                    pq = comb['cal_pool'] >= p
                    mask = (ca & sh & pq) if mode == 'AND' else ((ca & sh) | pq)
                    r = ev(comb, mask, f"{mode} c>{c} s>{s} pool>={p}")
                    if r:
                        best.setdefault(mode, []).append(r)
    for mode in ('AND', 'OR'):
        rows = sorted(best.get(mode, []), key=lambda r: -r['lift'])
        L += [f"### B.{mode} 模式 —— 按提升排序（只列保留 ≥3 个的）", "",
              "| 组合 | 保留 | 精确率 | 召回 | **提升** |", "|---|---|---|---|---|"]
        shown = 0
        for r in rows:
            if r['kept'] < 3:
                continue
            L.append(f"| `{r['name']}` | {r['kept']}/{r['n']} | {r['prec']:.0%} | "
                     f"{r['rec']:.0%} | **{r['lift']:.2f}×** |")
            shown += 1
            if shown >= 8:
                break
        if not shown:
            L.append("| （无保留≥3 的组合） | | | | |")
        L += [""]

    # 推荐
    L += ["## C. 推荐取值与理由", ""]
    or_rows = [r for r in best.get('OR', []) if r['kept'] >= 5 and np.isfinite(r['lift'])]
    and_rows = [r for r in best.get('AND', []) if r['kept'] >= 5 and np.isfinite(r['lift'])]
    bo = max(or_rows, key=lambda r: r['lift']) if or_rows else None
    ba = max(and_rows, key=lambda r: r['lift']) if and_rows else None
    for lab, r in (('OR 最优(保留≥5)', bo), ('AND 最优(保留≥5)', ba)):
        L.append(f"- **{lab}**：" + (f"`{r['name']}` ⇒ 保留 {r['kept']}/{r['n']}、"
                 f"精确率 {r['prec']:.0%}、召回 {r['rec']:.0%}、提升 **{r['lift']:.2f}×**"
                 if r else '无'))
    L += ["",
          "> **判读**：请选**提升 >1.2 且保留量可观**的那一档作为新门槛；"
          "并把 `min_sharpe` / `min_pool_calmar` 的取值抄进 `docs/loop_todo.md` 的已知事实快照。",
          "> ⚠ 本脚本**没有**复现 `pass_filter` 的 11 项（只用了 `cal_all/sharpe/cal_pool`）"
          "⇒ 是**上限估计**；真实落地值应更宽松一点。", ""]

    txt = '\n'.join(L) + '\n'
    io.open(OUT, 'w', encoding='utf-8').write(txt)
    try:
        print(txt)
    except Exception:
        print(txt.encode('utf-8', 'replace').decode('gbk', 'replace'))
    print(f'已写 {OUT}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
