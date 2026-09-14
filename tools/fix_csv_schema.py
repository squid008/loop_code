# -*- coding: utf-8 -*-
"""fix_csv_schema.py -- 修复因「追加加列」而混合宽度的观测 CSV（roadmap §8.30）

背景（2026-09-13）：给 `--pool_obs` 加了 5 列（ann_ex_cw/calmar_cw/dd_cw/sharpe_cw/tilt），
而写入端是"只判有无文件/空"来决定写不写表头 ⇒ 文件变成「表头 10 列 + 旧行 10 列 + 新行 15 列」
⇒ `pd.read_csv` 报 `ParserError: Expected 10 fields in line 222, saw 15`
⇒ 所有下游报告（tilt / night_report / valid_report）全崩。

本脚本用 `loop_engine.append_csv_schema_safe(path, None, new_cols)` 做**只修复**：
把旧行按旧表头对齐、加列后写入的行按新 schema 对齐，缺列补空，整体重写。
**gen5 的 tilt 数据只在这些文件里 ⇒ 必须先备份再修。**

用法: python tools/fix_csv_schema.py [--apply]
      不加 --apply = 只做**体检**(报告列数分布)，不写盘。
"""
import io
import os
import shutil
import sys
import time

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'engine'))
DOCS = os.path.join(ROOT, 'docs')

import csv                                    # noqa: E402

# 新增后的**目标 schema**（顺序必须与 pool_rec 的 dict 顺序一致）
POOL_COLS = ['gen', 'expr', 'pool', 'ic', 'ic_ir', 'calmar', 'ann_ex', 'dd', 'sharpe',
             'turn', 'ann_ex_cw', 'calmar_cw', 'dd_cw', 'sharpe_cw', 'tilt']
# ★ 2026-09-13 追加（roadmap §8.44）：`max_ex_corr`（§8.34 新增的第 17 列）在**追加时也没做
#   schema 对账** ⇒ `loop_archive_300.csv` 16列×164 + 17列×62、`_500.csv` 16列×136 + 17列×75
#   ⇒ `pd.read_csv` 直接报 `Expected 16 fields in line 165, saw 17`。**同一个坑的第三处**。
#   （`loop_archive.csv`(all) 是 16列×1440 —— 它自 §8.34 后没再跑过，所以还没被污染。）
ARCHIVE_COLS = ['gen', 'expr', 'cat', 'leaf', 'window', 'cost', 'ic', 'ic_ir', 'ann_ex', 'dd',
                'calmar', 'sharpe', 'last_yr', 'turn', 'neg_yr', 'max_ex_corr', 'passed']
TARGETS = [('loop_pool_obs.csv', POOL_COLS),
           ('loop_pool_obs_300.csv', POOL_COLS),
           ('loop_pool_obs_500.csv', POOL_COLS),
           ('loop_pool_obs_1000.csv', POOL_COLS),
           ('loop_archive.csv', ARCHIVE_COLS),
           ('loop_archive_300.csv', ARCHIVE_COLS),
           ('loop_archive_500.csv', ARCHIVE_COLS),
           ('loop_archive_1000.csv', ARCHIVE_COLS)]


def width_hist(path):
    """返回 (表头列数, {行宽: 行数})。不依赖 pandas（文件可能已损坏）。"""
    rr = []
    with io.open(path, encoding='utf-8-sig', newline='') as fh:
        for r in csv.reader(fh):
            if r:
                rr.append(r)
    if not rr:
        return 0, {}
    hdr = rr[0]
    h = {}
    for parts in rr[1:]:
        h[len(parts)] = h.get(len(parts), 0) + 1
    return len(hdr), h


def main():
    apply_ = '--apply' in sys.argv[1:]
    import loop_engine as LE

    print('=' * 76)
    print('模式:', 'APPLY(写盘)' if apply_ else 'DRY-RUN(只体检)')
    print('=' * 76)
    for name, cols in TARGETS:
        p = os.path.join(DOCS, name)
        if not os.path.exists(p):
            print(f'  - {name:26s} (不存在)')
            continue
        hdr_n, hist = width_hist(p)
        bad = [k for k in hist if k != hdr_n]
        status = '正常' if not bad else f'**混合宽度** {sorted(hist.items())}'
        print(f'  - {name:26s} 表头 {hdr_n} 列 -> 目标 {len(cols)} 列 ; {status}')
        if bad and apply_:
            st = os.path.join(DOCS, 'history')
            os.makedirs(st, exist_ok=True)
            bak = os.path.join(st, f'{name}.bak_{time.strftime("%Y%m%d_%H%M%S")}')
            shutil.copy2(p, bak)
            msg, n = LE.append_csv_schema_safe(p, None, cols)
            print(f'      备份 -> {os.path.relpath(bak, ROOT)}')
            print(f'      修复 -> {msg} ; 共 {n} 行')
            hdr2, hist2 = width_hist(p)
            print(f'      复核: 表头 {hdr2} 列, 行宽分布 {sorted(hist2.items())}')
    print()
    if not apply_:
        print('（DRY-RUN；确认无误后加 --apply 写盘）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
