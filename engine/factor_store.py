# -*- coding: utf-8 -*-
"""factor_store.py — 因子值落地存储（`FactorStore` 抽象，实现 `docs/software_framework.md` §4.3）

## 为什么是现在（2026-09-14）
架构文档 §4.3 早已定稿落地格式，但标注 **"M6 未落地"**。用户 2026-09-14 确认：
「`facs` 文件夹可以加，因子值是用 h5 存吧？……数据库用 PGSQL、存储用 h5」⇒ 现在落地。

## 格式（**严格按 §4.3**，那节是实测定稿，不要凭直觉改）
```
facs/                          # 根目录（可配置；文档里写的是 factor_lib/factors/）
  a3/                          # ast_hash 前 2 位分桶（防单目录 30 万文件退化）
    F23/
      values.h5                # dataset 'data' = float32 (n_date, n_inst)
                               #   连续、无 chunk、不压缩
                               # attrs: expr/ast_hash/dates/instruments/freq/unit/
                               #        version/source/created_at/sign/leaf_set/cat
```
**实测定稿的三条（§4.1，别改）**：
  1. 轴序必须 **`(date, inst)`** —— `(inst,date)` 在 HDF5 里单日读要 **151.5ms vs 0.4ms**（500x）。
  2. **连续、不 chunk、不压缩** = HDF5 家族综合最优（单日 0.4ms / 全量 18ms）。
     ⚠ chunk 是**零和**的：优化单日读必然牺牲全量读。
  3. 真正省空间的杠杆是**量化**（uint8 截面分位 5.5x），**不是压缩**（真实因子只 1.2~2.3x）。
     本模块默认 `float32`（保精度）；要省空间用 `dtype='uint8q'`（截面分位）。

**❌ 明确不要做的（§4.4）**：别抄 qlib 的 `.bin`（每股票每字段一文件 ⇒ 横截面读开 5000 文件）；
别用 Parquet（体积 1.25~2.2x、读慢 4~30x，其三件法宝在此场景全失效）；
别把 5 档桶号当存储（丢组内排序 ⇒ 无法重算 IC，**不可逆**）。

## 五个接口（§4.3 指定）
`day(d)` / `window(d0,d1)` / `inst(code)` / `full()` / `meta()` —— 格式被接口挡住，
将来换 parquet 只加一个类。

## ⚠ 已知限制
- `inst(code)`（单股全史）在 `(date,inst)` 下**慢**（33ms~1s）。看板若要画"某股票因子走势"，
  建 `(inst,date)` 副本或缓存，**别为它牺牲主访问模式**（§4.3 末）。
"""
import hashlib
import json
import os
import time

import h5py
import numpy as np

ROOT_DEFAULT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'facs')
VERSION = 1


def ast_hash(expr):
    """表达式指纹（前 2 位用于分桶）。用 `str(node)` 的 md5，**可复现**。"""
    return hashlib.md5(str(expr).encode('utf-8')).hexdigest()


def _bucket(ah):
    return ah[:2]


class FactorStore:
    """一个因子 = 一个 `values.h5`。写一次、只读多次。"""

    def __init__(self, root=None, name=None, readonly=True):
        self.root = root or ROOT_DEFAULT
        # name 可以是 F 编号（'F23'）或任意可读名；内部仍按 ast_hash 分桶
        self.name = name
        self._f = None
        self._d = None
        self._attrs = None
        self.readonly = readonly

    # ---------- 路径 ----------
    def path_of(self, name, expr=None):
        """定位某个因子的 h5。有 expr 时用 ast_hash 分桶；否则退回根目录下的 name/。"""
        if expr:
            ah = ast_hash(expr)
            return os.path.join(self.root, _bucket(ah), name, 'values.h5'), ah
        # 只知道名字：全库搜（读路径用；写路径必须给 expr）
        for b in sorted(os.listdir(self.root)) if os.path.isdir(self.root) else []:
            p = os.path.join(self.root, b, name, 'values.h5')
            if os.path.exists(p):
                return p, None
        return os.path.join(self.root, '00', name, 'values.h5'), None

    # ---------- 写 ----------
    def write(self, name, expr, data, dates, instruments,
              freq=5, unit='raw', source='genN', sign=1, leaf_set=None,
              cat=None, quantize=None, overwrite=True):
        """落地一个因子值矩阵。

        :param data: (n_date, n_inst) float，**轴序必须是 (date, inst)**（见模块 docstring 第 1 条）
        :param dates: 长度 = data.shape[0]
        :param instruments: 长度 = data.shape[1]
        :param quantize: `None`=float32 原值；`'uint8q'`=截面分位(256 级，体积 ~1/5，保截面排序)
        """
        d = np.asarray(data, dtype=np.float32)
        if d.ndim != 2:
            raise ValueError('data 必须是 2 维 (date, inst)，实得 {}'.format(d.shape))
        if d.shape[0] != len(dates) or d.shape[1] != len(instruments):
            raise ValueError('data {} 与 dates({})/instruments({}) 不匹配'.format(
                d.shape, len(dates), len(instruments)))
        p, ah = self.path_of(name, expr)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        if os.path.exists(p) and not overwrite:
            return p, ah
        store = d
        if quantize == 'uint8q':
            store = _to_uint8q(d)
        # ⚠ 连续 + 不 chunk + 不压缩 = §4.1 实测定稿（单日读 0.4ms / 全量 18ms）
        _tmp = p + '.tmp'
        with h5py.File(_tmp, 'w') as f:
            f.create_dataset('data', data=store, compression=None, chunks=None)
            ds = f['data']
            ds.attrs['expr'] = np.bytes_(str(expr).encode('utf-8'))
            ds.attrs['ast_hash'] = np.bytes_(ah.encode('utf-8'))
            ds.attrs['dates'] = np.asarray(dates)
            ds.attrs['instruments'] = np.asarray([str(x) for x in instruments],
                                                 dtype=object).astype('S')
            ds.attrs['freq'] = int(freq)
            ds.attrs['unit'] = str(unit)
            ds.attrs['version'] = VERSION
            ds.attrs['source'] = str(source)
            ds.attrs['created_at'] = np.bytes_(
                time.strftime('%Y-%m-%d %H:%M:%S').encode('utf-8'))
            ds.attrs['sign'] = int(sign)
            ds.attrs['leaf_set'] = np.bytes_(
                json.dumps(list(leaf_set or []), ensure_ascii=False).encode('utf-8'))
            ds.attrs['cat'] = np.bytes_(str(cat or '').encode('utf-8'))
            ds.attrs['quantized'] = (quantize or 'none')
        os.replace(_tmp, p)      # 原子替换（与 loop_state 同规矩：不留半成品）
        return p, ah

    # ---------- 读 ----------
    def open(self, name, expr=None, quant=False):
        """打开因子。`quant=True` 时**优先读 `values_q.h5`**（uint8 截面分位快查副本）。

        ★★ 为什么双写（2026-09-14 用户批准；`ai_test/bench_quant_read.py` 实测）：
          uint8 副本 **省 3.99x 空间**，且**秩类用法快 14.4x**（`读+免转秩` 146.8→10.2ms）
          —— 因为它存的**就是截面分位**，IC(Spearman)/十档分层/多空/**正交诊断**
          都**不需要再排序**，省掉的正是 `rank_rows` 的 O(N·logN)。
        ⚠ **代价**：uint8 丢原始值 ⇒ **只能做秩类**；中性化/回归/剥风格/因子合成
          **需要原值** ⇒ 必须读 `values.h5`（`quant=False`，默认）。
        """
        if quant:
            pq, _ = self.path_of(name, expr)
            pq = os.path.join(os.path.dirname(pq), 'values_q.h5')
            if os.path.exists(pq):
                self._f = h5py.File(pq, 'r')
                self._d = self._f['data']
                self._attrs = {k: _dec(v) for k, v in self._d.attrs.items()}
                self._attrs['_path'] = pq
                self._attrs['_quant'] = True
                return self
            # 没有副本 -> 静默回落? **不**（§8.44 铁律：静默兜底=排查噩梦）⇒ 明确告知
            raise FileNotFoundError(
                '{} 没有 values_q.h5 快查副本（用 `python ai_test/add_quant_copy.py` 生成）'.format(pq))
        p, _ = self.path_of(name, expr)
        if not os.path.exists(p):
            raise FileNotFoundError(p)
        self._f = h5py.File(p, 'r')
        self._d = self._f['data']
        self._attrs = {k: _dec(v) for k, v in self._d.attrs.items()}
        self._attrs['_path'] = p
        self._attrs['_quant'] = False
        return self

    # ---------- 量化副本 ----------
    def write_quant_copy(self, name, expr=None, overwrite=True):
        """由 `values.h5` 生成/刷新 `values_q.h5`（uint8 截面分位）。**不需要重算因子**。"""
        p, ah = self.path_of(name, expr)
        if not os.path.exists(p):
            raise FileNotFoundError(p)
        pq = os.path.join(os.path.dirname(p), 'values_q.h5')
        if os.path.exists(pq) and not overwrite:
            return pq
        with h5py.File(p, 'r') as f:
            d = f['data'][:]
            at = {k: _dec(v) for k, v in f['data'].attrs.items()}
        q = _to_uint8q(np.asarray(d, dtype=np.float32))
        _tmp = pq + '.tmp'
        with h5py.File(_tmp, 'w') as f:
            f.create_dataset('data', data=q, compression=None, chunks=None)
            ds = f['data']
            for k, v in at.items():
                try:
                    if k == 'quantized':
                        ds.attrs[k] = 'uint8q'
                    elif isinstance(v, str):
                        ds.attrs[k] = np.bytes_(v.encode('utf-8'))
                    else:
                        ds.attrs[k] = v
                except Exception:
                    pass
            ds.attrs['source_float'] = np.bytes_(os.path.basename(p).encode('utf-8'))
        os.replace(_tmp, pq)
        return pq

    def close(self):
        if self._f is not None:
            self._f.close()
            self._f = self._d = self._attrs = None

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()

    def meta(self):
        """接口 5：元数据（attrs 全量）。"""
        return dict(self._attrs or {})

    def _idx(self, dates=None):
        dd = self._attrs['dates']
        return {int(d): i for i, d in enumerate(dd)} if dates is None else None

    def day(self, d):
        """接口 1：某日的截面（一维 (n_inst,)）。**这是主导访问模式**（0.4ms）。"""
        i = self._idx()[int(d)]
        return self._d[i, :]

    def window(self, d0, d1):
        """接口 2：一段日期 × 全市场。"""
        ix = self._idx()
        a, b = ix[int(d0)], ix[int(d1)]
        return self._d[a:b + 1, :]

    def inst(self, code):
        """接口 3：单股全史。⚠ 在 (date,inst) 轴序下**慢**（§4.3 末），别当主访问。"""
        cols = list(self._attrs['instruments'])
        j = cols.index(str(code))
        return self._d[:, j]

    def full(self):
        """接口 4：全量（(n_date, n_inst)）。"""
        return self._d[:, :]

    # ---------- 派生：日频超额序列所需的**调仓日**视图 ----------
    def on_dates(self, date_list, freq=5):
        """按给定日期取行（用于与回测的调仓日对齐）。"""
        ix = self._idx()
        rows = [ix[int(d)] for d in date_list if int(d) in ix]
        return np.asarray(rows, dtype=np.int64)


def _to_uint8q(d):
    """转 uint8 截面分位（256 级）。§4.2：体积 5.1~5.7x，且**保住截面排序语义**（IC/分组近乎无损）。"""
    out = np.full(d.shape, 255, dtype=np.uint8)
    for i in range(d.shape[0]):
        row = d[i]
        m = np.isfinite(row)
        n = int(m.sum())
        if n < 2:
            continue
        r = np.argsort(np.argsort(row[m]))
        out[i, m] = np.minimum((r * 256 // n), 255).astype(np.uint8)
    return out


def _dec(v):
    if isinstance(v, bytes):
        return v.decode('utf-8', 'replace')
    if isinstance(v, np.ndarray):
        if v.dtype.kind == 'S':
            return [x.decode('utf-8', 'replace') for x in v]
        return v.tolist()
    if isinstance(v, np.generic):
        return v.item()
    return v


def list_factors(root=None):
    """列出库内全部因子：[(F编号, path, attrs)]。"""
    root = root or ROOT_DEFAULT
    out = []
    if not os.path.isdir(root):
        return out
    for b in sorted(os.listdir(root)):
        bd = os.path.join(root, b)
        if not os.path.isdir(bd):
            continue
        for nm in sorted(os.listdir(bd)):
            p = os.path.join(bd, nm, 'values.h5')
            if not os.path.exists(p):
                continue
            try:
                with h5py.File(p, 'r') as f:
                    at = {k: _dec(v) for k, v in f['data'].attrs.items()}
                    at['shape'] = f['data'].shape
            except Exception as e:
                at = {'_err': '{}: {}'.format(type(e).__name__, e)}
            out.append((nm, p, at))
    return out


if __name__ == '__main__':
    import sys
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
    fs = list_factors()
    print('facs 根目录: {}'.format(ROOT_DEFAULT))
    print('因子数: {}'.format(len(fs)))
    for nm, p, at in fs[:20]:
        print('  {}  shape={} expr={}'.format(nm, at.get('shape'), str(at.get('expr'))[:60]))
