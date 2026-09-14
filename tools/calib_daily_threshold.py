# -*- coding: utf-8 -*-
"""calib_daily_threshold.py — 期频 vs 日频口径对照 + **档位阈值标定**（loop_todo §1.19 ③）

## 干什么

用户已拍板「**重标档位阈值到日频**」。本工具给出拍板所需的**全部数字**：

1. **期频 vs 日频对照**（逐因子）：`strip_calmar`（期）vs `strip_calmar_d`（日）
2. **折算比分布**（日/期）：分位数 —— 回答"日频到底打了多少折"
3. ★★ **阈值敏感度表**：日频阈值取 X ⇒ A 档剩几个 / 降到 B 几个 / 掉到 C 几个
   ⇒ 让用户**看着数字选阈值**，而不是拍脑袋

## 为什么"负超额因子"的折算比接近 1（不是 bug）

`calmar = ann_ex / |dd|`。对**负超额**因子，回撤主要来自**持续下行**（而非持有期内的波动）
⇒ 期频打点已经能抓到 ⇒ `dd_d ≈ dd` ⇒ 折算比 ≈ 1 ✓
⇒ **真正有信息量的是 A/B 档（正超额）** —— 那里才有"持有期内回撤被漏掉"的问题。

## 用法

    python tools/calib_daily_threshold.py                    # 全库
    python tools/calib_daily_threshold.py --pool=1000        # 只看某池
    python tools/calib_daily_threshold.py --sens=0.20,0.25,0.30 --min-ann=0
"""
import argparse
import csv
import io
import os
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DOCS = os.path.join(ROOT, 'docs')


def fnum(x):
    try:
        v = float(x)
        return v if v == v else None      # NaN -> None
    except (TypeError, ValueError):
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pool', default='')
    ap.add_argument('--sens', default='0.15,0.20,0.25,0.30',
                    help='要试的**日频** A 档阈值（逗号分隔）')
    ap.add_argument('--min-ann', type=float, default=0.0,
                    help='额外要求剥风格后年化超额 > 此值（对齐 strip_grade 的 C 判据）')
    a = ap.parse_args()

    p = os.path.join(DOCS, 'loop_strip_style_bank.csv')
    rows = list(csv.DictReader(io.open(p, encoding='utf-8-sig', newline='')))
    if a.pool:
        rows = [r for r in rows if r['pool'] == a.pool]

    has_d = [r for r in rows if fnum(r.get('strip_calmar_d')) is not None]
    print('=' * 100)
    print('期频 vs 日频 口径对照{}{}'.format(
        '（pool={}）'.format(a.pool) if a.pool else '', ''))
    print('=' * 100)
    print('  总 {} 条；有日频值的 {} 条（缺的是"已剔除/未重算"的历史行）'.format(
        len(rows), len(has_d)))

    # ---- [1] 折算比分布（只看**正** strip_calmar，因为负值折算比≈1 无信息量）----
    print('\n[1] 折算比 = strip_calmar_d / strip_calmar')
    for tag, sub in (('全部有日频值', has_d),
                     ('仅正 strip_calmar（A/B 档，**有信息量**）',
                      [r for r in has_d if (fnum(r['strip_calmar']) or 0) > 0])):
        rt = [fnum(r['strip_calmar_d']) / fnum(r['strip_calmar'])
              for r in sub if fnum(r['strip_calmar']) not in (None, 0)]
        if not rt:
            print('  {}: （无样本）'.format(tag))
            continue
        rt.sort()
        q = lambda x: rt[min(len(rt) - 1, int(x * len(rt)))]
        print('  {}（N={}）: 中位 {:.3f}  四分位 {:.3f}~{:.3f}  区间 {:.3f}~{:.3f}'.format(
            tag, len(rt), q(0.5), q(0.25), q(0.75), rt[0], rt[-1]))

    # ---- [2] 逐因子对照（只列 A/B 档，C 档折算比无意义）----
    print('\n[2] 逐因子对照（仅 A/B 档 = 剥风格后**仍正**的，共 {} 个）'.format(
        sum(1 for r in has_d if (fnum(r['strip_calmar']) or 0) > 0)))
    print('  {:<12s} {:>10s} {:>10s} {:>8s} {:>10s} {:>10s} {:>8s}'.format(
        'name', '期calmar', '日calmar', '折比', '期dd', '日dd', '放大'))
    for r in sorted([x for x in has_d if (fnum(x['strip_calmar']) or 0) > 0],
                    key=lambda x: -(fnum(x['strip_calmar_d']) or -9)):
        sc, sd = fnum(r['strip_calmar']), fnum(r['strip_calmar_d'])
        dd, ddd = fnum(r['dd_d']), None
        _ddp = fnum(r.get('strip_dd_d'))
        ratio = (sd / sc) if sc else float('nan')
        print('  {:<12s} {:>10.3f} {:>10.3f} {:>8.2f} {:>10s} {:>10s} {:>8s}'.format(
            r['name'], sc, sd, ratio, '-', ('%.3f' % _ddp) if _ddp is not None else '-',
            '-'))

    # ---- [3] ★★ 阈值敏感度表 ----
    print('\n[3] ★★ 日频 A 档阈值敏感度（对齐 strip_grade：C = 年化超额<=0 或 calmar<=0）')
    print('     目的：让"新阈值定多严"这件事**看着数字决定**，不是拍脑袋')
    pos = [r for r in has_d if (fnum(r['strip_ann_ex']) or -9) > a.min_ann
           and (fnum(r['strip_calmar_d']) or -9) > 0]
    print('  （前置：剥风格后**年化超额 > {}** 且 **日频 calmar > 0** ⇒ 候选 {} 个）'.format(
        a.min_ann, len(pos)))
    print()
    print('  {:>10s} {:>8s} {:>8s} {:>10s}'.format('日频阈值', 'A 档', 'B 档', 'A 相对期频0.30 的保留率'))
    base = sum(1 for r in pos if (fnum(r['strip_calmar']) or -9) >= 0.30)
    for th in [float(x) for x in a.sens.split(',') if x.strip()]:
        nA = sum(1 for r in pos if (fnum(r['strip_calmar_d']) or -9) >= th)
        nB = len(pos) - nA
        print('  {:>10.2f} {:>8d} {:>8d} {:>10s}'.format(
            th, nA, nB, ('{:.0%}'.format(nA / base) if base else '-')))
    print('\n  参考：**期频**阈值 0.30 下 A 档 = {} 个（现状口径）'.format(base))
    print('  ⇒ 若日频折算比约 0.6~0.7，则"同等严格度"的新阈值 ≈ **{:.2f}**'.format(
        0.30 * 0.65))
    return 0


if __name__ == '__main__':
    sys.exit(main())
