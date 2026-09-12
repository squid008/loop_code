# -*- coding: utf-8 -*-
"""obs_analysis.py — 观测跑后的联合分析（剥风格 x 池内 x 全A）

数据源（引擎的观测产物，均 gitignore）：
    docs/loop_archive.csv      全A 口径（L2 明细）
    docs/loop_strip_style.csv  剥风格明细（--strip_style）
    docs/loop_pool_obs.csv     池内明细，长表（--pool_obs）

回答四个问题（都是**定门槛前必须先看的分布**）：
  1. 剥风格后还剩多少？衰减多少？（定 `--min_strip_calmar`）
  2. 池内通过率多高？（定池门槛）
  3. ★ **全A 越强，池内是否越差？**（相关/分档）—— 若是，说明"全A Calmar 排序在筛风格暴露强度"
  4. 新入库因子的 `pool_tag` 是什么？

用法：
    python standard/obs_analysis.py            # 全部代
    python standard/obs_analysis.py --gen=71   # 指定代
"""
import io
import os
import sys

import numpy as np
import pandas as pd

try:
    sys.stdout.reconfigure(errors='replace')
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ARCHIVE = os.path.join(ROOT, 'docs', 'loop_archive.csv')
STRIP = os.path.join(ROOT, 'docs', 'loop_strip_style.csv')
POOL = os.path.join(ROOT, 'docs', 'loop_pool_obs.csv')
OUT = os.path.join(HERE, 'obs_analysis_report.md')

GENS = None
for a in sys.argv[1:]:
    if a.startswith('--gen='):
        GENS = [int(x) for x in a[6:].split(',')]


def _rd(path):
    if not os.path.exists(path):
        return None
    d = pd.read_csv(path)
    if 'pool' in d.columns:
        d['pool'] = d['pool'].astype(str)      # ★ CSV 往返后变 int64, 必须统一成字符串
    if GENS is not None and 'gen' in d.columns:
        d = d[d['gen'].isin(GENS)]
    return d


def main():
    ar, st, po = _rd(ARCHIVE), _rd(STRIP), _rd(POOL)
    if ar is None:
        print(f"缺少 {ARCHIVE}"); return 1
    L = ["# 观测跑联合分析", "",
         f"数据: archive {0 if ar is None else len(ar)} 行 / "
         f"strip {0 if st is None else len(st)} 行 / pool {0 if po is None else len(po)} 行"
         + (f"（限 gen={GENS}）" if GENS else ""), ""]

    # ---------- 1/2. 剥风格 ----------
    if st is not None and len(st):
        L += ["## 1. 剥风格分布（定 `--min_strip_calmar` 的依据）", "",
              "| 统计（中位） | 原版 | 剥风格后 |", "|---|---|---|"]
        for c0, c1, lab in (('ann_ex', 'strip_ann_ex', '费后超额/年'),
                            ('calmar', 'strip_calmar', 'Calmar'), ('ic', 'strip_ic', 'IC')):
            L.append(f"| {lab} | {st[c0].median():+.4f} | {st[c1].median():+.4f} |")
        L += ["", "```",
              f"原版超额>0:      {int((st['ann_ex'] > 0).sum())}/{len(st)}",
              f"剥风格后超额>0:  {int((st['strip_ann_ex'] > 0).sum())}/{len(st)}",
              f"原版 Calmar>=0.3:     {int((st['calmar'] >= 0.3).sum())}/{len(st)}",
              f"剥风格后 Calmar>=0.3: {int((st['strip_calmar'] >= 0.3).sum())}/{len(st)}",
              f"超额衰减(剥-原) 中位: {((st['strip_ann_ex'] - st['ann_ex']) * 100).median():+.2f}%",
              "```", "",
              "> 门槛建议：取一个**不误杀已证明可行者**的值。先看 `strip_calmar` 分布再定；",
              "> 若设 `--min_strip_calmar=0.3`，则本批只留上面那一行的数量。", ""]

    # ---------- 3. 全A vs 池内 ----------
    if po is not None and len(po) and 'expr' in ar.columns:
        m = ar.merge(po, on=['gen', 'expr'], suffixes=('_all', '_p'))
        pools = sorted(po['pool'].unique())
        L += ["## 2. ★ 全A 口径 vs 池内口径（核心诊断）", ""]
        if len(m):
            try:
                from scipy import stats
                L += ["| 池 | 全ACalmar vs 池内超额 | 全A超额 vs 池内超额 | 全A IC vs 池内 IC |",
                      "|---|---|---|---|"]
                for p in pools:
                    s = m[m['pool'] == p]
                    if len(s) < 4:
                        continue
                    r1, p1 = stats.spearmanr(s['calmar_all'], s['ann_ex_p'])
                    r2, p2 = stats.spearmanr(s['ann_ex_all'], s['ann_ex_p'])
                    r3, p3 = stats.spearmanr(s['ic_all'], s['ic_p'])
                    L.append(f"| {p} | {r1:+.3f} (p={p1:.3f}) | {r2:+.3f} (p={p2:.3f}) | "
                             f"{r3:+.3f} (p={p3:.3f}) |")
                L += ["", "> 若「全ACalmar vs 池内超额」为**负**，说明"
                          "**按全A Calmar 排序 = 按风格暴露强度排序**（越强越不在池内生效）。", ""]
            except ImportError:
                L.append("(无 scipy，跳过相关性)")
            # 分档
            L += ["### 按 全A Calmar 分档看池内表现", "",
                  "| 全A Calmar 档 | n | 池内超额中位 | 池内为正 |", "|---|---|---|---|"]
            for p in pools:
                s = m[m['pool'] == p].copy()
                if not len(s):
                    continue
                s['b'] = pd.cut(s['calmar_all'], [-9, -0.1, 0.2, 0.4, 0.6, 9],
                                labels=['<0', '0~0.2', '0.2~0.4', '0.4~0.6', '>0.6'])
                for lab in ['<0', '0~0.2', '0.2~0.4', '0.4~0.6', '>0.6']:
                    sel = s[s['b'] == lab]
                    if not len(sel):
                        continue
                    L.append(f"| {p} / {lab} | {len(sel)} | "
                             f"{sel['ann_ex_p'].median() * 100:+.2f}% | "
                             f"{int((sel['ann_ex_p'] > 0).sum())}/{len(sel)} |")
            L.append("")

        # 通过率
        L += ["### 池内通过率", "", "```"]
        L.append(f"全A 超额>0: {int((ar['ann_ex'] > 0).sum())}/{len(ar)}")
        for p in pools:
            s = po[po['pool'] == p]
            L.append(f"{p} 内超额>0: {int((s['ann_ex'] > 0).sum())}/{len(s)}")
        L.append("```")
        # 新入库因子的标签
        if 'passed' in ar.columns:
            ok = ar[ar['passed'] == 1]
            if len(ok):
                mg = ok.merge(po, on=['gen', 'expr'], suffixes=('_all', '_p'))
                L += ["### 本批入库因子的池内表现", "",
                      "| gen | 全A超额 | 全A Calmar | " +
                      " | ".join(f"{p} 内超额" for p in pools) + " |", "|---" * (3 + len(pools)) + "|"]
                for e, g in mg.groupby('expr'):
                    r0 = g.iloc[0]
                    L.append(f"| {r0['gen']} | {r0['ann_ex_all']*100:+.2f}% | "
                             f"{r0['calmar_all']:.3f} | " +
                             " | ".join(
                                 (f"{g.loc[g['pool'] == p, 'ann_ex_p'].iloc[0]*100:+.2f}%"
                                  if p in set(g['pool']) else "-") for p in pools) + " |")
                L.append("")

    io.open(OUT, 'w', encoding='utf-8').write('\n'.join(L) + '\n')
    print(f"已写 {OUT}")
    print('\n'.join(L))
    return 0


if __name__ == '__main__':
    sys.exit(main())
