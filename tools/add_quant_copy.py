# -*- coding: utf-8 -*-
"""add_quant_copy.py — 给 `facs/` 里每个因子补 **uint8 快查副本** `values_q.h5`（2026-09-14）

## 为什么（用户已批准"双写"）
实测（`tools/bench_quant_read.py`，真实落地因子 3309×5384）：

| 项 | float32 | uint8 | 倍率 |
|---|---|---|---|
| 文件大小 | 71.3 MB | 17.9 MB | **省 3.99x** |
| 单日读 | 0.34 ms | 0.34 ms | 持平 |
| 窗口 251 日 | 1.95 ms | 0.74 ms | 快 2.6x |
| 全量读 | 27.3 ms | 5.9 ms | 快 4.6x |
| 端到端「取调仓日 **+转秩**」 | 137 ms | 142 ms | 持平 |
| ★★ 端到端「取调仓日 **+免转秩**」 | 137 ms | **10.2 ms** | **快 14.4x** |

⇒ **uint8 存的**就是截面分位**** ⇒ IC(Spearman)/十档分层/多空/**正交诊断** 无需再排序 ⇒ 快 14.4x。
⚠ **代价**：uint8 丢原始值 ⇒ 只能做**秩类**；中性化/回归/剥风格/因子合成**需要原值** ⇒ 读 `values.h5`。

## 本脚本的特点：**不需要重算因子**（只读 h5 → 量化 → 写 h5）⇒ 很快
全 52 个预计 **~2 分钟**（vs `build_facs.py` 全量 21 分钟，因为不用载面板/回测）。

## 用法
    python tools/add_quant_copy.py            # 全量补/刷新
    python tools/add_quant_copy.py --limit=3  # 冒烟
"""
import argparse
import os
import sys
import time

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'engine'))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--facs_root', default=None)
    a = ap.parse_args()

    import factor_store as FS
    root = a.facs_root or FS.ROOT_DEFAULT
    fs = FS.FactorStore(root=root)
    items = FS.list_factors(root)
    if a.limit:
        items = items[:a.limit]
    print('=' * 92)
    print('补 uint8 快查副本 → {}  （{} 个）'.format(root, len(items)))
    print('=' * 92)
    t0 = time.time()
    n_new, n_skip, sz_f, sz_q, err = 0, 0, 0, 0, 0
    for i, (nm, p, at) in enumerate(items, 1):
        expr = str(at.get('expr') or '')
        try:
            pq = fs.write_quant_copy(nm, expr, overwrite=True)
        except Exception as e:
            print('  [{}] **失败** {}: {}'.format(nm, type(e).__name__, e))
            err += 1
            continue
        fsz = os.path.getsize(p)
        qsz = os.path.getsize(pq)
        sz_f += fsz
        sz_q += qsz
        print('  [{:<10s}] {:>6.1f}MB -> {:>6.1f}MB ({:.2f}x)'.format(
            nm, fsz / 1e6, qsz / 1e6, fsz / max(qsz, 1)))
    print('-' * 92)
    print('完成 {} 个, 失败 {} 个;  用时 {:.0f}s'.format(len(items) - err, err, time.time() - t0))
    print('float32 合计 **{:.2f} GB** -> uint8 副本合计 **{:.2f} GB**（省 {:.2f}x）'.format(
        sz_f / 1e9, sz_q / 1e9, sz_f / max(sz_q, 1)))
    print('⇒ 总占用 **{:.2f} GB**（双写）。'
          '秩类用法读 `values_q.h5`（快 14x）；需要原值读 `values.h5`。'.format(
              (sz_f + sz_q) / 1e9))
    return 0


if __name__ == '__main__':
    sys.exit(main())
