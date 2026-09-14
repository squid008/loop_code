# -*- coding: utf-8 -*-
"""analyze_diversity.py -- 诊断「生成端多样性」瓶颈到底在哪一层（零成本, 只读归档 CSV）

为什么（2026-09-13 决定下一步路线）：
  实测生成端 `重复拦 3526/尝试 4694 = 75%` = **完全相同的表达式**反复被抽到
  => 生成器的有效采样空间很小。而生成端**已经**有很激进的去重机器
     (FAM_QUOTA=2 / FSA 冻结 / bank_skel_max=1 / fsa_th) => **不是"去重太松"**。
  决定路线需要在两种病因中选一个, 它们**代价差一个数量级**：
    · **A 叶子层**：只反复用少数几个叶子字段（成交额/换手/市值）
       => 便宜解法: 给生成端加**叶子多样性约束**（强制用欠采样的叶子）~1-2h
    · **B 结构层**：叶子已均匀, 但**组合方式**反复（同模板换窗口/换叶子）
       => 贵解法: §8.21-⑥ #5 **语义单元 + 方向维度 + 跨方向优先交叉**（数天）
  本脚本用 `docs/loop_archive*.csv` 的 `cat`（算子族）/`leaf`（叶子字段）/`expr`（表达式）列
  给出**集中度**指标来区分 A/B。

用法: python tools/analyze_diversity.py
"""
import io
import os
import re
import sys
from collections import Counter

import numpy as np
import pandas as pd

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DOCS = os.path.join(ROOT, 'docs')


def hhi(counter, n_total):
    """Herfindahl 指数(0~1)：越大越集中。1/n 类数 = 完全均匀。"""
    if not n_total:
        return float('nan')
    return sum((v / n_total) ** 2 for v in counter.values())


def topk_share(counter, n_total, k=5):
    if not n_total:
        return float('nan')
    return sum(v for _, v in counter.most_common(k)) / n_total


def skel(expr):
    """把数字参数抹掉 -> 结构骨架（粗粒度, 用于看"同模板换窗口"）。"""
    return re.sub(r'\d+', 'N', str(expr))


def main():
    files = []
    for f in sorted(os.listdir(DOCS)):
        if f.startswith('loop_archive') and f.endswith('.csv'):
            files.append(os.path.join(DOCS, f))
    if not files:
        print('没找到 docs/loop_archive*.csv')
        return 1
    print('=' * 78)
    for p in files:
        try:
            d = pd.read_csv(p)
        except Exception as ex:
            print(os.path.basename(p), '读失败', type(ex).__name__, ex)
            continue
        n = len(d)
        print('### {}   ({})'.format(os.path.basename(p), n))
        if n == 0:
            print()
            continue
        # gen 分布（防"多代混合"误读）
        if 'gen' in d.columns:
            g = Counter(d['gen'].dropna().astype(int))
            print('  gen 分布:', dict(sorted(g.items())))
        for col in ('cat', 'leaf'):
            if col not in d.columns:
                continue
            c = Counter(str(x) for x in d[col].dropna())
            uniq = len(c)
            print('  {:5s}: 唯一值 {:4d} ; HHI {:.3f} ; Top5 占比 {:.1%}'.format(
                col, uniq, hhi(c, n), topk_share(c, n)))
            print('         Top8: ' + ', '.join(
                '{}={}'.format(k[:26], v) for k, v in c.most_common(8)))
        # 结构骨架集中度
        s = Counter(skel(x) for x in d['expr'].dropna())
        tot = sum(s.values())
        print('  结构骨架: 唯一 {:4d} ; HHI {:.3f} ; Top5 占比 {:.1%}'.format(
            len(s), hhi(s, tot), topk_share(s, tot, 5)))
        print('         Top5 骨架:')
        for k, v in s.most_common(5):
            print('           x{:<3d} {}'.format(v, k[:112]))
        print()
    print('=' * 78)
    print('判读：')
    print('  · 若 cat/leaf 的 HHI 高(>0.2) 且 Top5 占比高(>0.6) => **A 叶子层**病因')
    print('    => 便宜的"叶子多样性约束"可能就够（~1-2h）')
    print('  · 若 cat/leaf 较均匀但**结构骨架** HHI 高/Top5 占比高 => **B 结构层**病因')
    print('    => 必须上 §8.21-⑥ #5（语义单元 + 方向 + 跨方向优先交叉，数天）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
