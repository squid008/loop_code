# -*- coding: utf-8 -*-
"""loop_cache.py — 运行期可变缓存 + L1/内存预算状态（2026-09-26 文件级拆分）

★ 用法：`import loop_cache as _C`，用 `_C.VCACHE` / `_C._LRU` / `_C.L1_POOL_MASK`（模块引用，运行时取）。
  这些是**运行期可变**的（base_fields / set_mem_budget 改它们），不要值拷贝。
"""
_BASE = None
L1_STOCKS = 2000
L1_ROWS = None
L1_COLS = None
L1_POOL_MASK = None

_LRU = {}
LRU_MAX = 400
CACHE2_MAX = 150
LRU_MB = 1200.0
CACHE2_MB = 800.0
BATCH_MB = 1500.0
VCACHE = {}
_VREUSE_MB = [0.0]
_VREUSE_CAP_MB = 800.0
