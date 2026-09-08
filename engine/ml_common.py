# -*- coding: utf-8 -*-
"""ML验证 & 双重同伴效应 的共享数据层
======================================
- panel.h5  : 前复权 OHLCV + 市值 + 成交额(ai_test 因子挖掘统一口径)
- barra.h5  : 10个BARRA风格 + 31张申万一级行业指示面板(date x stock, 0/1)
- universe.h5: 可交易池(bool 宽表)

load() 返回全部对齐后的数据(日期=行业表覆盖范围, 列=panel∩行业∩universe 求交)。
"""
import os
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
PANEL = os.path.join(HERE, 'panel.h5')
BARRA = os.path.join(HERE, 'barra.h5')
UNIVERSE = os.path.join(HERE, 'universe.h5')
BARRA_STYLE = {'beta', 'book_to_price', 'comovement', 'earnings_yield', 'growth',
               'leverage', 'liquidity', 'momentum', 'non_linear_size',
               'residual_volatility', 'size'}
_cache = {}


def industry_names():
    with pd.HDFStore(BARRA, 'r') as st:
        keys = [k.strip('/') for k in st.keys()]
    return sorted(k for k in keys if k not in BARRA_STYLE)


def load(need=None):
    """返回:
      dates: np.ndarray[int], cols: np.ndarray[str]
      P: DataFrame dict: close/open/high/low/volume/turnover/mktcap (float64, 全有限性由调用方判断)
      U: bool DataFrame (可交易池)
      G: int16 (T,S) 行业编码 0..30, -1=无行业;  GNAMES: list[str]
      (T=行业表日期∩panel日期, S=列交集)
    """
    if _cache:
        return _cache
    with pd.HDFStore(PANEL, 'r') as st:
        P = {k: st[k].astype('float64') for k in
             ['close', 'open', 'high', 'low', 'volume', 'turnover', 'mktcap']}
    with pd.HDFStore(UNIVERSE, 'r') as st:
        U = st['universe']
    keys = industry_names()
    with pd.HDFStore(BARRA, 'r') as st:
        ind_tabs = {k: st[k] for k in keys}

    close = P['close']
    # 对齐轴: 行业表日期 ∩ 行情日期; 列: 行情∩行业∩universe
    dates = close.index.intersection(list(ind_tabs.values())[0].index).values
    cols = close.columns.intersection(ind_tabs[keys[0]].columns)
    cols = cols.intersection(U.columns).values
    P = {k: v.reindex(index=dates, columns=cols) for k, v in P.items()}
    U = U.reindex(index=dates, columns=cols).fillna(False)
    # 行业编码矩阵 G (T,S) int16
    T, S = len(dates), len(cols)
    G = np.full((T, S), -1, dtype=np.int16)
    for i, k in enumerate(keys):
        v = (ind_tabs[k].reindex(index=dates, columns=cols).values > 0.5)
        G[v] = i
    _cache.update(dict(dates=dates, cols=cols, P=P, U=U, G=G, GNAMES=keys))
    return _cache


def fwd_ret(P_close, fwd=5):
    """T+1 买入、持 fwd 日卖出的前瞻收益(与 factor_miner 口径一致):
    fwd_ret_t = close_{t+1+fwd} / close_{t+1} - 1
    """
    return P_close.shift(-(1 + fwd)) / P_close.shift(-1) - 1.0


def neutralize_day(Y, G_t, lnmc_t, valid):
    """单截面中性化: Y(n,k) 对 X=[1, ln_mktcap, 行业哑变量(31)] OLS 取残差。
    Y/lnmc_t/G_t 已按 valid 过滤好(长度 n)。返回残差 (n,k)。
    """
    n = Y.shape[0]
    X = np.ones((n, 1 + 1 + 31), dtype=np.float64)
    X[:, 1] = lnmc_t
    if n:
        X[np.arange(n), 2 + G_t] = 1.0
    coef, *_ = np.linalg.lstsq(X, Y, rcond=None)
    resid = Y - X @ coef
    return resid


def neutralize_panel(F, G, lnmc, valid):
    """整面板按日中性化: F/T 为 (T,S,k) 或 dict of (T,S)。
    返回与输入同构的残差面板。"""
    T = G.shape[0]
    if isinstance(F, dict):
        keys = list(F.keys())
        A = np.stack([F[k].values for k in keys], axis=2)   # (T,S,k)
        R = neutralize_panel(A, G, lnmc, valid)
        return {k: pd.DataFrame(R[:, :, i], index=F[k].index,
                                columns=F[k].columns) for i, k in enumerate(keys)}
    # F: (T,S,k)
    Tk = F.shape[2] if F.ndim == 3 else 1
    FF = F[:, :, None] if F.ndim == 2 else F
    out = np.full_like(FF, np.nan, dtype=np.float64)
    ln = lnmc.values if hasattr(lnmc, 'values') else lnmc
    V = valid.values if hasattr(valid, 'values') else valid
    Gv = G
    for t in range(T):
        m = V[t] & np.isfinite(ln[t])
        g = Gv[t][m]
        m2 = g >= 0
        if m2.sum() < 50 or not m2.any():
            continue
        idx = np.where(m)[0][m2]
        yy = FF[t][idx]                                # (nk, k)
        ff = np.isfinite(yy)
        if not ff.any():
            continue
        # 逐特征: 各自 finite 的行做中性化
        res = np.full_like(yy, np.nan)
        for kk in range(yy.shape[1]):
            mm = ff[:, kk]
            if mm.sum() < 50:
                continue
            Yk = yy[mm, kk]
            X = np.ones((mm.sum(), 1 + 1 + 31))
            X[:, 1] = ln[t][idx][mm]
            gg = g[mm]
            X[np.arange(len(gg)), 2 + gg] = 1.0
            coef, *_ = np.linalg.lstsq(X, Yk, rcond=None)
            res[mm, kk] = Yk - X @ coef
        out[t][idx] = res
    if F.ndim == 2:
        out = out[:, :, 0]
    return out


def cross_rank(df):
    """逐行(截面) rank 0~1"""
    return df.rank(axis=1, pct=True)
