# -*- coding: utf-8 -*-
"""数据源基础设施：路径常量 · 宽容 pickle · 通用文件读取 · 缓存。

★ 重要设计（2026-09-15 探明）：
  · `engine/loop_state*.pkl` 里有 `loop_engine.Node` 对象 ⇒ 直接 `pickle.load` 会
    `AttributeError: Can't get attribute 'Node'` ✗
  · 但**不需要 import `loop_engine`**（它很重、且可能有副作用）—— 用
    **宽容 Unpickler** 把 `Node` 换成轻量替身，即可拿到顶层键 / `bank` 计数 / `n_tested` / `cfg` ✓
  · ★ 因子**明细**不从 pkl 读，而从 `docs/factor_library*.md` 读（更完整、含编号/家族/表达式）✓
"""
import io
import json
import os
import pickle
import re
import time

from .. import settings

DOCS = settings.DOCS
ENGINE = settings.ENGINE
ROOT = settings.PROJECT_ROOT

# 池定义（与 `engine/loop_pools.py` 的 POOLS 对应）—— 展示名/指数代码
POOLS = [
    {'key': 'all', 'label': '全A', 'index': '', 'color': '#6366f1'},
    {'key': '300', 'label': '沪深300', 'index': '000300.XSHG', 'color': '#0ea5e9'},
    {'key': '500', 'label': '中证500', 'index': '000905.XSHG', 'color': '#10b981'},
    {'key': '1000', 'label': '中证1000', 'index': '000852.XSHG', 'color': '#f59e0b'},
    {'key': '50', 'label': '上证50', 'index': '000016.XSHG', 'color': '#94a3b8'},
]
POOL_KEYS = [p['key'] for p in POOLS]


def pool_label(key):
    for p in POOLS:
        if p['key'] == key:
            return p['label']
    return key


def suffix(pool):
    """池 → 文件名后缀（`all` 无后缀）。"""
    return '' if pool in ('all', '', None) else '_%s' % pool


def docs_path(name):
    return os.path.join(DOCS, name)


# ---------------------------------------------------------------- pickle
class _NodeShim:
    """`loop_engine.Node` 的**宽容替身**：接受任意构造参数，属性缺失返回 None。"""

    __slots__ = ('_a', '_k', '__dict__')

    def __init__(self, *a, **k):
        object.__setattr__(self, '_a', a)
        object.__setattr__(self, '_k', k)

    def __setstate__(self, st):
        if isinstance(st, dict):
            self.__dict__.update(st)

    def __getattr__(self, name):
        if name in ('_a', '_k'):
            raise AttributeError(name)
        return None

    def __repr__(self):
        return 'Node(%s)' % ', '.join(repr(x) for x in getattr(self, '_a', ()))


class _TolerantUnpickler(pickle.Unpickler):
    def find_class(self, module, name):
        if name == 'Node':
            return _NodeShim
        return super().find_class(module, name)


def load_state(pool):
    """读 `engine/loop_state[_<pool>].pkl` ⇒ `{bank_n, n_tested, cfg, ...}`（失败返回 None）。"""
    p = os.path.join(ENGINE, 'loop_state%s.pkl' % suffix(pool))
    if not os.path.exists(p):
        return None
    try:
        with open(p, 'rb') as f:
            st = _TolerantUnpickler(f).load()
    except Exception as e:
        return {'_error': repr(e), '_path': p}
    return {
        'path': p,
        'mtime': os.path.getmtime(p),
        'sizeMB': round(os.path.getsize(p) / 1024 / 1024, 2),
        'bank_n': len(st.get('bank') or []),
        'bank_ex_n': len(st.get('bank_ex') or []),
        'n_tested': st.get('n_tested'),
        'seeds_n': len(st.get('seeds') or []),
        'fsa_n': len(st.get('fsa') or {}),
        'frozen_n': len(st.get('frozen') or []),
        'fail_lib_n': len(st.get('fail_lib') or []),
        'cfg': {k: v for k, v in (st.get('cfg') or {}).items() if not k.startswith('_')},
        'has_last_l1': bool(st.get('last_l1') is not None),
        'has_last_l2': bool(st.get('last_l2') is not None),
    }


# ---------------------------------------------------------------- 文本/CSV
def read_text(path):
    """自动探测编码（utf-8 / gbk）读文本。"""
    if not os.path.exists(path):
        return None
    with open(path, 'rb') as f:
        raw = f.read()
    for enc in ('utf-8-sig', 'utf-8', 'gbk'):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode('utf-8', 'replace')


def read_csv_rows(path, limit=None):
    """极简 CSV 读取（不依赖 pandas，避免大文件开销）⇒ `(header, rows)`。"""
    txt = read_text(path)
    if txt is None:
        return [], []
    import csv
    rows = list(csv.reader(io.StringIO(txt)))
    if not rows:
        return [], []
    head = [c.lstrip('\ufeff') for c in rows[0]]
    body = rows[1:]
    if limit:
        body = body[:limit]
    return head, body


def tail_lines(path, n=12):
    txt = read_text(path)
    if not txt:
        return []
    return txt.splitlines()[-n:]


def mtime_iso(path):
    if not os.path.exists(path):
        return None
    return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(os.path.getmtime(path)))


# ---------------------------------------------------------------- journal 代数
_GEN_RE = re.compile(r'^##\s*第\s*(\d+)\s*代', re.M)


def journal_gens(pool):
    """从 `docs/loop_journal[_<pool>].md` 抽所有「## 第 N 代」⇒ 代数列表（升序）。"""
    p = docs_path('loop_journal%s.md' % suffix(pool))
    txt = read_text(p)
    if not txt:
        return [], p
    gens = sorted(int(g) for g in _GEN_RE.findall(txt))
    return gens, p


def journal_last_gen(pool):
    gens, p = journal_gens(pool)
    return (gens[-1] if gens else None), len(gens), p


# ---------------------------------------------------------------- 缓存
_CACHE = {}


def cached(key, ttl, fn):
    """极简 TTL 缓存（前端轮询友好，避免每次都读 pkl）。"""
    now = time.time()
    hit = _CACHE.get(key)
    if hit and now - hit[0] < ttl:
        return hit[1]
    val = fn()
    _CACHE[key] = (now, val)
    return val
