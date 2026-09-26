# -*- coding: utf-8 -*-
"""loop_data.py — 面板构造（数据准备，2026-09-26 文件级拆分）

★ 只依赖固定常量 HERE（本模块自己派生）+ factor_miner + loop_fields，不 import loop_engine。
  _build_panel_fresh：从 h5 现场构造面板（--panel_cache=build / 测试对拍）
  _panel_sha1：构造代码的 SHA1 指纹（面板缓存靠它感知构造逻辑改动）
"""
import os

import numpy as np
import pandas as pd

from factor_miner import load_panel, prepare, START
import loop_cache as _C
import loop_paths as _P
from loop_fields import FIELDS, MF16, BARRA_LEAVES, FA_LEAVES

HERE = os.path.dirname(os.path.abspath(__file__))


def _build_panel_fresh():
    """从 h5 **现场构造**面板（原 `base_fields()` 的前半段，2026-09-16 为缓存功能**逐字搬运**）。

    ★ 为什么单独抽出来：`--panel_cache=build` 需要"构造一份全新的"来落盘；
      测试也要拿它跟"缓存里读出来的"逐字段对拍（`tools/_test_panel_cache.py`）。
    ★★ **本函数的任何改动都会让面板缓存自动失效**（`panel_cache.code_sha1()` 折了它的源码 SHA1）
      —— 这是刻意的：否则改了构造逻辑却用旧缓存 ⇒ **静默改变结果** ✗
    """
    P = load_panel(FIELDS)
    P = prepare(P)
    close = P['close'].astype('float64')
    dates = close.index.values
    cols = list(close.columns)
    B = {
        'close': close.values.astype(np.float32),
        'open': P['open'].reindex(index=dates, columns=cols).values.astype(np.float32),
        'high': P['high'].reindex(index=dates, columns=cols).values.astype(np.float32),
        'low': P['low'].reindex(index=dates, columns=cols).values.astype(np.float32),
        'volume': P['volume'].reindex(index=dates, columns=cols).values.astype(np.float32),
        'turnover': P['turnover'].reindex(index=dates, columns=cols).values.astype(np.float32),
        'mktcap': P['mktcap'].reindex(index=dates, columns=cols).values.astype(np.float32),
    }
    # ---- 扩展叶子(mf16 随 FIELDS 已入 P; barra/fa 独立 store) ----
    for name in MF16:
        B[name] = P[name].reindex(index=dates, columns=cols).values.astype(np.float32)
    for fn, names in (('barra.h5', BARRA_LEAVES), ('fa_pit.h5', FA_LEAVES)):
        with pd.HDFStore(os.path.join(HERE, fn), 'r') as st:
            for name in names:
                B[name] = st[name].reindex(index=dates, columns=cols).values.astype(np.float32)
    # 衍生
    B['vwap'] = (B['turnover'] / np.maximum(B['volume'], 1e-9)).astype(np.float32)
    B['ret'] = (pd.DataFrame(B['close']).pct_change().values).astype(np.float32)
    B['amt'] = B['turnover']
    B['ln_mktcap'] = np.log(np.maximum(B['mktcap'], 1e-9)).astype(np.float32)
    B['ln_volume'] = np.log(np.maximum(B['volume'], 1e-9)).astype(np.float32)
    B['turn_ratio'] = (B['turnover'] / np.maximum(B['mktcap'], 1e-9)).astype(np.float32)
    # ---- 派生字段(★中金研报: overnight 出现率 85% / amplitude 63%, 是核心信号源) ----
    c, o, h, l = B['close'], B['open'], B['high'], B['low']
    pc = np.vstack([np.full((1, c.shape[1]), np.nan), c[:-1]]).astype(np.float32)  # 昨收
    rng = (h - l).astype(np.float32)
    with np.errstate(invalid='ignore', divide='ignore'):
        B['overnight'] = (o / pc - 1.0).astype(np.float32)          # 隔夜跳空 ★
        B['intraday'] = (c / o - 1.0).astype(np.float32)            # 日内收益
        B['amplitude'] = (rng / pc).astype(np.float32)              # 振幅 ★
        B['up_shadow'] = ((h - np.maximum(o, c)) /
                          np.where(rng > 1e-9, rng, np.nan)).astype(np.float32)
        B['down_shadow'] = ((np.minimum(o, c) - l) /
                            np.where(rng > 1e-9, rng, np.nan)).astype(np.float32)
        B['hl_ratio'] = (h / np.where(l > 1e-9, l, np.nan)).astype(np.float32)
        B['true_range'] = (np.maximum(
            rng, np.maximum(np.abs(h - pc), np.abs(l - pc))) / pc).astype(np.float32)
    del pc, rng
    return B, dates, cols, close


# ★ 面板缓存的有效性 = 「构造代码」的指纹（惰性求值：只在真的用缓存时才算）
_PANEL_CODE_SHA1 = None


def _panel_sha1():
    """`_build_panel_fresh` 的源码 SHA1（面板缓存靠它感知"构造逻辑改过了"）。"""
    global _PANEL_CODE_SHA1
    if _PANEL_CODE_SHA1 is None:
        import panel_cache as _pc
        _PANEL_CODE_SHA1 = _pc.code_sha1(_build_panel_fresh)
    return _PANEL_CODE_SHA1


def base_fields():
    """返回 {name: (T,S) float32} 基础字段 + 日期/列"""
    if _C._BASE is not None:
        return _C._BASE
    # ★★★ 2026-09-16「面板只读缓存」（`--panel_cache`，**默认 off ⇒ 与改造前逐位不变**）：
    #   面板 4.42 GB 且构造后只读 ⇒ 落成只读 memmap 后多进程共享同一批物理页（spawn 下也能省内存）。
    #   · `use`   = 必须命中；缺失/过期**直接报错**（绝不偷偷重建，更不会拿旧面板算新结果）
    #   · `build` = 现场构造一份并落盘，随后继续用（结果与 off **逐位相同**）
    #   ⚠ 只有"面板从哪来"变了；`B_sub` / `_C.L1_POOL_MASK` 等派生逻辑**保持逐字不变** ✓
    if _C.PANEL_CACHE == 'off':
        B, dates, cols, close = _build_panel_fresh()
    else:
        import panel_cache as _pc
        if _C.PANEL_CACHE == 'use':
            B, dates, cols, _cv, _man = _pc.load(_panel_sha1())
            # close 只有 0.14 GB，**拷一份**避免"pandas 直接操作只读块"的一类意外
            close = pd.DataFrame(np.array(_cv), index=pd.Index(dates), columns=cols)
            print('[面板缓存] 只读映射命中: %d 字段 / %.2f GB -> %s'
                  % (len(B), _pc.size_gb(B), _pc.CACHE_DIR), flush=True)
        else:
            B, dates, cols, close = _build_panel_fresh()
            _pc.save(B, dates, cols, close.values, _panel_sha1())
    # ★L1 子面板: 粗筛不需要全样本(瓶颈是内存带宽, 不是计算)。
    #   时间只取 START 之后 + 截面随机抽样 -> 数据量降到 ~1/4, 实测整体提速 3~4 倍。
    #   L1 只是排序用, 抽样误差可接受; L2 精筛仍用全样本。
    _C.L1_ROWS = np.where(dates >= START)[0]
    if _P.MINE_POOL != 'all':
        # ★池内挖掘(§8.19): L1 列 = 池**并集**(不随机抽样 —— 必须保证任一时点的成分都在)。
        #   掩码另按 PIT 生效, 故并集稍大不影响口径。
        import loop_pools as _LP
        uni = _LP.pool_union(_P.MINE_POOL)
        _C.L1_COLS = np.array([i for i, c in enumerate(cols) if c in uni], dtype=np.int64)
        if _C.L1_COLS.size == 0:
            raise SystemExit(f"[--mine_pool={_P.MINE_POOL}] 池并集与面板列无交集, 检查股票代码格式")
        _C.L1_POOL_MASK = _LP.pool_mask(_P.MINE_POOL, dates, cols)[np.ix_(_C.L1_ROWS, _C.L1_COLS)]
        print(f"[--mine_pool={_P.MINE_POOL}] L1 子面板列 = 池并集 {_C.L1_COLS.size} 只; "
              f"当期池成分中位 {int(np.median(_C.L1_POOL_MASK.sum(1)))} 只 "
              f"(面板共 {close.shape[1]} 列)")
    else:
        nsub = min(close.shape[1], _C.L1_STOCKS)
        _C.L1_COLS = np.sort(np.random.default_rng(20240917).choice(
            close.shape[1], nsub, replace=False))
        _C.L1_POOL_MASK = None
    B_sub = {k: v[np.ix_(_C.L1_ROWS, _C.L1_COLS)] for k, v in B.items()}
    _C._BASE = dict(B=B, B_sub=B_sub, dates=dates, cols=cols, close=close)
    return _C._BASE
