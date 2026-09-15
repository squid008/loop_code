# -*- coding: utf-8 -*-
"""build_industry.py — 从 BARRA 源数据重建**申万一级行业**面板（roadmap §8.39 续）

背景（2026-09-14 发现）：
  · `engine/barra.h5` **只有 11 个连续风格**，**没有行业** ——
    `engine/build_barra.py` 明确写着「只保留连续风格(入叶, 量纲 R); **行业哑变量不入叶/不入盘**」
    ⇒ 行业是被**故意丢掉**的。
  · 但 `engine/ml_common.py` 的文档与代码**仍假定有 31 个申万一级行业**
    （`industry_names()` / `load()` 里的 `G` 行业编码矩阵）⇒ **它现在是坏的**：
    它的 `BARRA_STYLE` 用的是**不带 `barra_` 前缀**的名字，而 `st.keys()` 返回**带前缀**的
    ⇒ 过滤失效 ⇒ **把 11 个风格当成"行业"返回**；`load()` 的 `G` 也随之变成
    「风格面板 >0.5 的编码」⇒ **静默错误**（多个风格面板互相覆盖）。
  · ⇒ 这直接**卡住了「组合构建的行业中性」**（roadmap §8.39 瓶颈 B）。

好消息：**源数据里有行业** —— `E:\\rq\\others\\barra\\v1\\<code>.h5` 的 `data` 有 **42 列** =
  11 风格 + **31 个申万一级行业**（银行 / 计算机 / 环保 / …）。

本脚本把行业**单独**落成 `engine/industry.h5`（**不动 `barra.h5`，不动任何引擎代码**）：
  · `code`  : (T x S) int16 行业编码 0..30，-1 = 无行业（**与面板同轴**）
  · `names` : 31 个行业名（按编码顺序）
坐标映射**照抄 `build_barra.py`**（`code = 文件名[:-3]`；`index = pd.to_datetime(...).strftime('%Y%m%d').astype(int64)`；
`reindex(index=TARGET_IDX, columns=TARGET_COLS)`），避免自己猜错。

用法: python tools/build_industry.py [--out=engine/industry.h5]
"""
import argparse
import glob
import io
import os
import sys
import time

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ENGINE = os.path.join(ROOT, 'engine')
SRC = r'E:\rq\others\barra\v1'
PANEL = os.path.join(ENGINE, 'panel.h5')

STYLES = ['size', 'non_linear_size', 'momentum', 'liquidity', 'book_to_price',
          'leverage', 'growth', 'earnings_yield', 'beta', 'residual_volatility',
          'comovement']


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(ENGINE, 'industry.h5'))
    ap.add_argument('--limit', type=int, default=0, help='只处理前 N 个文件（调试用）')
    a = ap.parse_args()

    import numpy as np
    import pandas as pd

    t0 = time.time()
    print('=' * 80)
    print('重建申万一级行业面板')
    print('=' * 80)
    if not os.path.isdir(SRC):
        print('源目录不可访问:', SRC)
        return 1
    files = sorted(glob.glob(os.path.join(SRC, '*.h5')))
    if a.limit:
        files = files[:a.limit]
    print('源文件 %d 个   %.0f MB' % (
        len(files), sum(os.path.getsize(f) for f in files) / 1e6))

    with pd.HDFStore(PANEL, 'r') as st:
        _c = st['close']
        TARGET_IDX = np.asarray(_c.index, dtype=np.int64)
        TARGET_COLS = list(_c.columns)
    print('对齐坐标: %d 日 x %d 股' % (len(TARGET_IDX), len(TARGET_COLS)))

    d0 = pd.read_hdf(files[0], key='data')
    IND = [c for c in d0.columns if c not in STYLES]
    print('行业列 %d 个: %s' % (len(IND), ' / '.join(IND[:8]) + ' …'))

    cols = {}
    n_ok = 0
    for i, f in enumerate(files):
        code = os.path.basename(f)[:-3]
        try:
            df = pd.read_hdf(f, key='data')
        except Exception:
            continue
        if df.empty:
            continue
        sub = df.reindex(columns=IND)
        v = sub.values
        with np.errstate(invalid='ignore'):
            mx = np.nanmax(np.where(np.isfinite(v), v, -1.0), axis=1)  # 是否属于任何行业
            am = np.nanargmax(np.where(np.isfinite(v), v, -1.0), axis=1)
        cd = np.where(np.isfinite(mx) & (mx > 0.5), am, -1).astype('int16')
        cols[code] = pd.Series(cd, index=df.index)
        n_ok += 1
        if (i + 1) % 1000 == 0:
            print('  %d/%d  %.0fs' % (i + 1, len(files), time.time() - t0), flush=True)

    print('有效股票 %d   读取耗时 %.0fs' % (n_ok, time.time() - t0))
    D = pd.DataFrame(cols)
    D.index = pd.to_datetime(D.index).strftime('%Y%m%d').astype('int64')
    D = D.sort_index()
    D = D[~D.index.duplicated()]
    D = D.reindex(index=TARGET_IDX, columns=TARGET_COLS).astype('float32')  # 存 float32 兼容
    name_df = pd.DataFrame({'name': IND})
    with pd.HDFStore(a.out, 'w', complib='blosc', complevel=5) as st:
        st['code'] = D
        st['names'] = name_df
    print('已存 %s  (%d 日 x %d 股)' % (a.out, D.shape[0], D.shape[1]))
    fin = D.values
    print('  有效(有行业)占比 %.1f%%' % (100 * np.isfinite(fin).mean()))
    print('  日期覆盖: %s ~ %s' % (int(D.index.min()), int(D.index.max())))
    print('  总耗时 %.0fs' % (time.time() - t0))
    return 0


if __name__ == '__main__':
    sys.exit(main())
