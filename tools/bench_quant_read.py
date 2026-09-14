# -*- coding: utf-8 -*-
"""bench_quant_read.py — **量化(uint8) vs 原值(float32) 的读取性能实测**（2026-09-14）

## 用户之问
> 「省空间的话读取性能会不会打折扣？」

`docs/software_framework.md` §4.1 测的是**布局**（npy / h5 / parquet）而**不是** float32 vs uint8；
§4.2 只给了**体积**（uint8 截面分位 = 5.1~5.7x）与"保住截面排序语义"这一句定性结论。
⇒ **读取性能必须实测**，不能推断。

## 本脚本测四件事（在**真实落地**的因子上）
  1. 体积
  2. **单日读**（`day`，主导访问模式）
  3. **窗口读**（`window`，如 250 日）
  4. **全量读**（`full`）
  5. ★ **端到端"取调仓日 → 逐行转秩"** —— 这才是 IC / 分层 / 正交诊断**真正**的用法：
     uint8 存的**就是**截面分位 ⇒ **理论上可以跳过转秩** ⇒ 可能**更快**（不是更慢）。

## 用法
    python tools/bench_quant_read.py            # 取 facs/ 里最大的那个因子
    python tools/bench_quant_read.py --name=F25
"""
import argparse
import os
import sys
import tempfile
import time

import numpy as np

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'engine'))


def rank_rows(a):
    """逐行秩（与 orthogonal_diag 同口径）。"""
    out = np.empty(a.shape, dtype=np.float64)
    for i in range(a.shape[0]):
        r = a[i]
        m = np.isfinite(r)
        o = np.full(r.shape, np.nan)
        if m.sum() >= 2:
            v = r[m]
            order = np.argsort(v)
            rk = np.empty(v.size, dtype=np.float64)
            rk[order] = np.arange(1, v.size + 1, dtype=np.float64)
            o[m] = rk
        out[i] = o
    return out


def bench(fs, name, expr, data, dates, cols, reps=7):
    """对同一份数据写 float32 / uint8q 两个 h5，测四类访问。

    ⚠ **必须用独立的临时根**（2026-09-14 实测踩到）：第一版复用 `facs/` 的 `FactorStore`
      ⇒ 把测试条目 **写进了真实因子库**（名如 `F09`，只是 expr 带 `#float32`/`#uint8q` 后缀）
      ⇒ 库里多出 3 个假条目，**得手工清回去**。
      教训与 §8.44 同源：**基准/测试脚本必须与生产数据目录隔离**，别指望"记得删"。
    """
    tmp = tempfile.mkdtemp(prefix='bench_quant_')
    import factor_store as FS
    tfs = FS.FactorStore(root=tmp)
    fs = tfs
    out = {}
    for tag, q in (('float32', None), ('uint8q', 'uint8q')):
        p, _ = fs.write(name, expr + '#' + tag, data, dates, cols,
                        overwrite=True, quantize=q)
        out[tag] = p
    print('  临时根(与 facs/ 隔离): {}'.format(tmp))
    for tag, p in out.items():
        out[tag] = (p, os.path.getsize(p))

    def _t(fn, reps=reps):
        ts = []
        for _ in range(reps):
            t0 = time.perf_counter()
            fn()
            ts.append((time.perf_counter() - t0) * 1000)
        return float(np.median(ts))

    res = {}
    for tag, (p, sz) in out.items():
        with fs.open(name, expr + '#' + tag) as st:
            dd = st._attrs['dates']
            mid = int(dd[len(dd) // 2])
            d0 = int(dd[len(dd) // 2])
            d1 = int(dd[min(len(dd) - 1, len(dd) // 2 + 250)])
            idx = st.on_dates(dd[::5])
            res[tag] = dict(
                sz=sz,
                day=_t(lambda: st.day(mid)),
                win=_t(lambda: st.window(d0, d1)),
                full=_t(lambda: st.full()[:]),
                # ★ 端到端：取调仓日 + 逐行转秩（IC/分层/正交诊断的真实用法）
                e2e=_t(lambda: rank_rows(np.asarray(st._d[idx, :], dtype=np.float64)),
                       reps=3),
                shape=st._d.shape,
            )
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--name', default=None)
    a = ap.parse_args()
    import factor_store as FS
    fs = FS.FactorStore()
    fsd = FS.list_factors()
    if not fsd:
        print('facs/ 为空')
        return 1
    if a.name:
        fsd = [x for x in fsd if x[0] == a.name] or fsd[:1]
    else:
        fsd = sorted(fsd, key=lambda x: os.path.getsize(x[1]))[-1:]
    nm, p, at = fsd[0]
    with fs.open(nm) as st:
        data = np.asarray(st.full()[:], dtype=np.float32)
        dates = st._attrs['dates']
        cols = st._attrs['instruments']
    expr = str(at.get('expr'))
    print('=' * 88)
    print('基准因子: {}  expr={}'.format(nm, expr[:60]))
    print('矩阵: {}  (date x inst)'.format(data.shape))
    print('=' * 88)
    res = bench(fs, nm, expr, data, dates, cols)
    f, u = res['float32'], res['uint8q']
    print()
    print('{:<26s} {:>14s} {:>14s} {:>12s}'.format('项', 'float32', 'uint8q', '倍率'))
    print('-' * 88)
    print('{:<26s} {:>11.1f} MB {:>11.1f} MB {:>11.2f}x'.format(
        '文件大小', f['sz'] / 1e6, u['sz'] / 1e6, f['sz'] / max(u['sz'], 1)))
    for k, lab in (('day', '单日读 (3.5k 股)'), ('win', '窗口读 251 日'),
                   ('full', '全量读'), ('e2e', '★ 取调仓日+转秩(端到端)')):
        print('{:<26s} {:>11.2f} ms {:>11.2f} ms {:>11.2f}x'.format(
            lab, f[k], u[k], f[k] / max(u[k], 1e-9)))
    print('-' * 88)
    sp = f['sz'] / max(u['sz'], 1)
    print('⇒ 省空间 **{:.2f}x**;  端到端耗时比（float32/uint8）= **{:.2f}x**'.format(
        sp, f['e2e'] / max(u['e2e'], 1e-9)))
    print('   ⚠ 注：uint8 存的是**截面分位**，下游若只做(秩相关/分层/多空) ⇒ **可直接用、免转秩**；')
    print('     若要做(中性化/回归/合成) ⇒ 需要原值 ⇒ **uint8 不够**（§4.4：不可逆的信息损失）。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
