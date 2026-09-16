# -*- coding: utf-8 -*-
"""面板只读缓存（文件后备 memmap）—— 跨进程共享同一份物理内存（2026-09-16 新增）。

★ 为什么做它（实测 `ai_test/_measure_engine_cpu.py`）：
  · 面板 `B` = **4.42 GB**（62 字段, 3309x5384 float32），且**构造完成后再也不写**（只读性已逐行核查）；
  · 单引擎只吃 **~1 个核**（等效核 0.99）⇒ 瓶颈是**内存**，不是 CPU；
  · Windows 是 **spawn（无 fork）** ⇒ 每个引擎进程都会**各建一份**面板 ✗
  ⇒ 落成**只读文件映射**：OS 页缓存天然让多进程共享同一批物理页
    ⇒ ① 省内存（N 进程只占 1 份物理页，且是**可回收**的 file cache）
      ② 启动更快（免去每次 ~14.6s 的 h5 重建）。

★ 安全设计（本项目最忌"静默出错"，逐条堵住）：
  1. **只读**：`np.load(..., mmap_mode='r')` ⇒ 任何写操作**立刻抛异常**（fail-loud），
     不会静默污染共享面板；
  2. **过期检测**：manifest 记录来源 h5 的 `(size, mtime_ns)` + **构造函数源码 SHA1**
     ⇒ 数据或构造代码一变 ⇒ **拒绝加载并报错**（绝不"用旧面板算新结果"）；
  3. **形状/类型校验**：加载时逐字段核对 dtype/shape；
  4. **构建必须显式**：只有 `--panel_cache=build` 或 `tools/build_panel_cache.py` 才会写缓存；
     `use` 模式下缓存缺失/过期**直接报错**，不偷偷重建。

★ 缓存**与池无关**：只存全量 `B` + `close` + dates/cols。
  L1 子面板 `B_sub` / `L1_POOL_MASK` 仍由各进程现场派生（与改造前逐字相同）⇒ 语义零变化 ✓
"""
import hashlib
import io
import json
import os
import shutil

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(HERE, '_panel_cache')
MANIFEST = 'manifest.json'
# 面板来源（必须与 `loop_engine._build_panel_fresh()` 读的文件一致）
SRC_FILES = ['panel.h5', 'barra.h5', 'fa_pit.h5']


class CacheError(RuntimeError):
    """缓存缺失/过期/损坏 —— 一律**报错**，绝不静默降级。"""


def _now():
    import datetime
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def src_fingerprint():
    """来源 h5 的 (size, mtime_ns)：比秒级 mtime 更可靠（同一秒内重建也能发现）。"""
    out = {}
    for fn in SRC_FILES:
        try:
            st = os.stat(os.path.join(HERE, fn))
            out[fn] = [int(st.st_size), int(st.st_mtime_ns)]
        except OSError:
            out[fn] = None
    return out


def code_sha1(func):
    """把"构造面板的那段代码"折成短 SHA1 —— 代码一改，缓存自动失效。"""
    import inspect
    src = inspect.getsource(func)
    return hashlib.sha1(src.encode('utf-8')).hexdigest()[:16]


def size_gb(B):
    return sum(int(np.asarray(v).nbytes) for v in B.values()) / 1e9


def _fields_dir(d):
    """字段放在 `fields/` 子目录 —— 避免字段名（如 `close`）与保留文件名（`close.npy`）**撞名**。"""
    return os.path.join(d, 'fields')


def _field_path(d, name):
    return os.path.join(_fields_dir(d), name + '.npy')


def exists(cache_dir=None):
    return os.path.isfile(os.path.join(cache_dir or CACHE_DIR, MANIFEST))


def save(B, dates, cols, close_values, code_sha1, cache_dir=None, quiet=False):
    """把面板落成只读缓存（先写 `.tmp`、manifest 最后写，再整体换名）。返回缓存目录。"""
    dst = cache_dir or CACHE_DIR
    tmp = dst + '.tmp'
    if os.path.isdir(tmp):
        shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp, exist_ok=True)
    os.makedirs(_fields_dir(tmp), exist_ok=True)
    for k, v in B.items():
        np.save(_field_path(tmp, k), np.ascontiguousarray(np.asarray(v)))
    np.save(os.path.join(tmp, 'close.npy'), np.ascontiguousarray(np.asarray(close_values)))
    np.save(os.path.join(tmp, 'dates.npy'), np.ascontiguousarray(np.asarray(dates)))
    with io.open(os.path.join(tmp, 'cols.json'), 'w', encoding='utf-8') as f:
        json.dump([str(c) for c in cols], f)
    man = {
        'version': 1,
        'code_sha1': code_sha1,
        'src': src_fingerprint(),
        'fields': {k: {'dtype': str(np.asarray(v).dtype),
                       'shape': list(np.asarray(v).shape)} for k, v in B.items()},
        'dates': {'dtype': str(np.asarray(dates).dtype)},
        'close': {'dtype': str(np.asarray(close_values).dtype),
                  'shape': list(np.asarray(close_values).shape)},
        'created': _now(),
        'total_gb': round(size_gb(B) + np.asarray(close_values).nbytes / 1e9, 3),
    }
    with io.open(os.path.join(tmp, MANIFEST), 'w', encoding='utf-8') as f:
        json.dump(man, f, ensure_ascii=False, indent=1, sort_keys=True)
    if os.path.isdir(dst):                      # Windows 不能覆盖非空目录 ⇒ 先删旧的
        shutil.rmtree(dst, ignore_errors=True)
    os.replace(tmp, dst)
    if not quiet:
        print('[面板缓存] 已构建: %d 字段 + close, 共 %.2f GB -> %s'
              % (len(B), man['total_gb'], dst), flush=True)
    return dst


def load(code_sha1, cache_dir=None):
    """加载只读缓存。

    返回 `(B, dates, cols, close_values, manifest)`；`B` 的每个数组都是**只读 memmap**。
    缓存缺失 / 代码变了 / 来源数据变了 / 字段对不上 ⇒ 抛 `CacheError`（附**可执行**的修复提示）。
    """
    d = cache_dir or CACHE_DIR
    mf = os.path.join(d, MANIFEST)
    if not os.path.isfile(mf):
        raise CacheError('面板缓存不存在: %s\n  修复: python tools/build_panel_cache.py' % mf)
    with io.open(mf, encoding='utf-8') as f:
        man = json.load(f)
    if man.get('code_sha1') != code_sha1:
        raise CacheError(
            '面板缓存与当前**构造代码**不匹配（缓存=%s 当前=%s）\n'
            '  => 说明 base_fields 的构造代码改过；用旧缓存会静默改变结果\n'
            '  修复: python tools/build_panel_cache.py'
            % (man.get('code_sha1'), code_sha1))
    cur, old = src_fingerprint(), (man.get('src') or {})
    if old != cur:
        diff = [k for k in sorted(set(list(cur) + list(old))) if old.get(k) != cur.get(k)]
        raise CacheError(
            '面板缓存的**来源数据**已变化: %s\n'
            '  => 必须重建，否则结果对不上最新数据（%s）\n'
            '  修复: python tools/build_panel_cache.py' % (', '.join(diff), ', '.join(SRC_FILES)))
    B = {}
    for k, meta in sorted((man.get('fields') or {}).items()):
        p = _field_path(d, k)
        if not os.path.isfile(p):
            raise CacheError('面板缓存缺字段文件: %s\n  修复: python tools/build_panel_cache.py' % p)
        arr = np.load(p, mmap_mode='r')
        if list(arr.shape) != list(meta.get('shape') or []) or str(arr.dtype) != meta.get('dtype'):
            raise CacheError('字段 %s 形状/类型与 manifest 不符（%s%s vs %s%s）\n'
                             '  修复: python tools/build_panel_cache.py'
                             % (k, arr.shape, arr.dtype, meta.get('shape'), meta.get('dtype')))
        B[k] = arr
    cv = np.load(os.path.join(d, 'close.npy'), mmap_mode='r')
    if list(cv.shape) != list((man.get('close') or {}).get('shape') or []):
        raise CacheError('close 形状与 manifest 不符\n  修复: python tools/build_panel_cache.py')
    dates = np.load(os.path.join(d, 'dates.npy'), mmap_mode='r')
    with io.open(os.path.join(d, 'cols.json'), encoding='utf-8') as f:
        cols = json.load(f)
    return B, dates, cols, cv, man


def status(code_sha1, cache_dir=None):
    """人类可读的缓存状态（给 `--check` / 看板/运维用）。返回 (ok: bool, 说明: str)。"""
    d = cache_dir or CACHE_DIR
    if not exists(d):
        return False, '缓存不存在: %s' % d
    try:
        _B, _dt, _c, _cv, man = load(code_sha1, d)
    except CacheError as e:
        return False, str(e)
    return True, ('有效: %d 字段 / %.2f GB / 构建于 %s / code=%s'
                  % (len(man['fields']), man.get('total_gb', 0), man.get('created'),
                     man.get('code_sha1')))
