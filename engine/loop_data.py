# -*- coding: utf-8 -*-
"""loop_data.py — 面板构造（数据准备，2026-09-26 文件级拆分）

★ 只依赖固定常量 HERE（本模块自己派生）+ factor_miner + loop_fields，不 import loop_engine。
  _build_panel_fresh：从 h5 现场构造面板（--panel_cache=build / 测试对拍）
  _panel_sha1：构造代码的 SHA1 指纹（面板缓存靠它感知构造逻辑改动）
"""
import os

import numpy as np
import pandas as pd

from factor_miner import load_panel, prepare
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


