# -*- coding: utf-8 -*-
"""loop_paths.py — 路径常量单一事实源（2026-09-26 文件级拆分）

★ 为什么单独拆：STATE / ARCHIVE / STYLE_OBS / STRIP_OBS / POOL_OBS / JOURNAL / LIBRARY
  被 loop_engine / loop_persist 等多处使用，且 `set_mine_pool` 会**运行期改**它们（加池后缀）。

★ 用法铁律：使用方必须 `import loop_paths as _P` 然后用 `_P.STATE`（模块引用，运行时取）。
  不要 `from loop_paths import STATE` —— 那是 import 时**值拷贝**，`apply_suffix()` 改不到它
  （同 FWD / LLM_MAX_SIZE 的坑，见 loop_engine 顶部注释）。
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
DOCS = os.path.join(os.path.dirname(HERE), 'docs')

STATE = os.path.join(HERE, 'loop_state.pkl')
ARCHIVE = os.path.join(DOCS, 'loop_archive.csv')
STYLE_OBS = os.path.join(DOCS, 'loop_style_obs.csv')
STRIP_OBS = os.path.join(DOCS, 'loop_strip_style.csv')
POOL_OBS = os.path.join(DOCS, 'loop_pool_obs.csv')
JOURNAL = os.path.join(DOCS, 'loop_journal.md')
LIBRARY = os.path.join(DOCS, 'factor_library.md')
LIB_ENTRIES = os.path.join(DOCS, 'library_entries.jsonl')

MINE_POOL = 'all'   # 当前挖掘池（set_mine_pool 运行期改）

_PATH_KEYS = ('STATE', 'ARCHIVE', 'STYLE_OBS', 'STRIP_OBS', 'POOL_OBS', 'JOURNAL', 'LIBRARY')
_ORIG_PATHS = {}


def apply_suffix(sfx):
    """给 7 个路径常量统一加/去后缀（`set_mine_pool` 切池用）。首次调用快照原始路径，幂等。"""
    if not _ORIG_PATHS:
        for k in _PATH_KEYS:
            _ORIG_PATHS[k] = globals()[k]
    for k in _PATH_KEYS:
        r, e = os.path.splitext(_ORIG_PATHS[k])
        globals()[k] = r + sfx + e
