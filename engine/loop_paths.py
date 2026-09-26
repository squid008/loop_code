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


def set_mine_pool(tag):
    """把引擎切到指定池的**独立轨迹**。

    ① 状态 / 输出文件全部加池后缀 -> 三条轨迹互不读写对方的 bank/archive/journal/library;
    ② L1 子面板列 = 该池**并集**(历史上出现过的全部成分, 保证任一时点的成分都在面板里);
    ③ L1 的 IC 按 **PIT 池掩码**算 -> 目标函数从"全A IC"变成"**池内 IC**"。

    tag='all' 时**完全不动**(向后兼容)。幂等(可从原始路径重复派生)。返回实际生效的 tag。
    """
    if not tag or tag == 'all':
        MINE_POOL = 'all'
        apply_suffix('')
        return 'all'
    import loop_pools as _LP
    if tag not in _LP.POOLS:
        raise SystemExit(f"[--mine_pool] 未知池 '{tag}'; 可选: all / {sorted(_LP.POOLS)}")
    MINE_POOL = tag
    apply_suffix('_' + tag)
    return tag
