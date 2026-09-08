# -*- coding: utf-8 -*-
"""
高性能时序算子(纯 numpy, cumsum 技巧)
========================================
pandas rolling 对 (3309, 5384) 面板单次约 0.3~0.5s, 一个表达式 5 个节点就要 2~3s,
跑 1 万候选根本不可行。这里用前缀和实现 O(T*S) 的 rolling 统计, 实测提速 5~10 倍。
所有算子: NaN 视为缺失(min_periods 不足则为 NaN), 输出 float32。
"""
import numpy as np

MP_RATIO = 0.5          # min_periods = max(2, w//2)


def _mp(w):
    return max(2, w // 2)


def _prep(x):
    return np.asarray(x, dtype=np.float64)


def _win_sum(c, w):
    """由前缀和 c 得到窗口和: out[t] = c[t] - c[t-w]"""
    T = c.shape[0]
    out = np.empty_like(c)
    out[:w] = c[:w]
    if T > w:
        out[w:] = c[w:] - c[:-w]
    return out


def ts_mean(x, w):
    x = _prep(x)
    m = np.isfinite(x)
    x0 = np.where(m, x, 0.0)
    s = _win_sum(np.cumsum(x0, axis=0), w)
    n = _win_sum(np.cumsum(m.astype(np.float64), axis=0), w)
    mp = _mp(w)
    out = np.where(n >= mp, s / np.maximum(n, 1.0), np.nan)
    return out.astype(np.float32)


def ts_sum(x, w):
    x = _prep(x)
    m = np.isfinite(x)
    x0 = np.where(m, x, 0.0)
    s = _win_sum(np.cumsum(x0, axis=0), w)
    n = _win_sum(np.cumsum(m.astype(np.float64), axis=0), w)
    return np.where(n >= _mp(w), s, np.nan).astype(np.float32)


def ts_std(x, w):
    """var = E[x^2] - E[x]^2 (数值上够用, 已 clip)"""
    x = _prep(x)
    m = np.isfinite(x)
    x0 = np.where(m, x, 0.0)
    s1 = _win_sum(np.cumsum(x0, axis=0), w)
    s2 = _win_sum(np.cumsum(x0 * x0, axis=0), w)
    n = _win_sum(np.cumsum(m.astype(np.float64), axis=0), w)
    mp = _mp(w)
    n = np.maximum(n, 1.0)
    mean = s1 / n
    var = s2 / n - mean * mean
    var = np.maximum(var, 0.0)
    out = np.where(_win_sum(np.cumsum(m.astype(np.float64), axis=0), w) >= mp,
                   np.sqrt(var), np.nan)
    return out.astype(np.float32)


def ts_corr(x, y, w):
    x = _prep(x)
    y = _prep(y)
    m = np.isfinite(x) & np.isfinite(y)
    x0 = np.where(m, x, 0.0)
    y0 = np.where(m, y, 0.0)
    sx = _win_sum(np.cumsum(x0, axis=0), w)
    sy = _win_sum(np.cumsum(y0, axis=0), w)
    sxy = _win_sum(np.cumsum(x0 * y0, axis=0), w)
    sxx = _win_sum(np.cumsum(x0 * x0, axis=0), w)
    syy = _win_sum(np.cumsum(y0 * y0, axis=0), w)
    n = _win_sum(np.cumsum(m.astype(np.float64), axis=0), w)
    mp = max(3, w // 2)
    nn = np.maximum(n, 1.0)
    cov = sxy / nn - (sx / nn) * (sy / nn)
    vx = np.maximum(sxx / nn - (sx / nn) ** 2, 0.0)
    vy = np.maximum(syy / nn - (sy / nn) ** 2, 0.0)
    den = np.sqrt(vx * vy)
    out = np.where((n >= mp) & (den > 1e-12), cov / np.where(den > 1e-12, den, 1.0),
                   np.nan)
    return out.astype(np.float32)


def _sliding(x, w):
    """返回 (T, S, w) 视图(不复制); 前面补 NaN"""
    T, S = x.shape
    pad = np.full((w - 1, S), np.nan)
    xp = np.vstack([pad, x])
    st = np.lib.stride_tricks.as_strided(
        xp, shape=(T, S, w),
        strides=(xp.strides[0], xp.strides[1], xp.strides[0]))
    return st


def _chunked(fn, x, w, chunk=None):
    """分块执行 sliding 类算子: 每块取 [start:j] 段(含前 w-1 天温启动), 只取 [i:j] 结果。
    避免 (T,S,w) 大数组同时落内存(w=200 全样本会到 28GB 访问量)。"""
    T, S = x.shape
    if chunk is None:                                   # 自适应: 单块窗口体积 < 2GB
        chunk = 400
        while (chunk + w - 1) * S * w * x.itemsize > 2e9 and chunk > 60:
            chunk //= 2
    out = np.empty((T, S), dtype=np.float32)
    for i in range(0, T, chunk):
        j = min(i + chunk, T)
        start = max(0, i - w + 1)                       # 温启动起点
        seg = x[start:j]
        r = fn(seg, w)                                  # 输出与 seg 等长(前缀 nan)
        out[i:j] = r[i - start:]                        # 丢弃温启动段
    return out


def ts_max(x, w):
    x = _prep(x)
    if x.shape[0] * x.shape[1] * w > 8e7:            # 大窗口 -> 分块
        return _chunked(_ts_max_full, x, w)
    return _ts_max_full(x, w)


def _ts_max_full(x, w):
    st = _sliding(x, w)
    out = np.nanmax(st, axis=2)
    cnt = np.isfinite(st).sum(axis=2)
    return np.where(cnt >= _mp(w), out, np.nan).astype(np.float32)


def ts_min(x, w):
    x = _prep(x)
    if x.shape[0] * x.shape[1] * w > 8e7:
        return _chunked(_ts_min_full, x, w)
    return _ts_min_full(x, w)


def _ts_min_full(x, w):
    st = _sliding(x, w)
    out = np.nanmin(st, axis=2)
    cnt = np.isfinite(st).sum(axis=2)
    return np.where(cnt >= _mp(w), out, np.nan).astype(np.float32)


def ts_rank(x, w):
    """当前值在过去 w 日窗口中的分位(0~1)"""
    x = _prep(x)
    if x.shape[0] * x.shape[1] * w > 8e7:
        return _chunked(_ts_rank_full, x, w)
    return _ts_rank_full(x, w)


def _ts_rank_full(x, w):
    st = _sliding(x, w)
    cur = x.copy()
    cur[~np.isfinite(cur)] = np.nan
    c = cur[:, :, None]
    valid = np.isfinite(st) & np.isfinite(c)
    less = np.where(valid, (st < c), 0).sum(axis=2).astype(np.float64)
    cnt = np.isfinite(st).sum(axis=2).astype(np.float64)
    out = np.where(cnt >= _mp(w), less / np.maximum(cnt - 1, 1), np.nan)
    return out.astype(np.float32)


def ts_delay(x, n):
    x = np.asarray(x, dtype=np.float32)
    out = np.full_like(x, np.nan)
    if n < x.shape[0]:
        out[n:] = x[:-n]
    return out


def ts_delta(x, n):
    x = np.asarray(x, dtype=np.float32)
    out = np.full_like(x, np.nan)
    if n < x.shape[0]:
        out[n:] = x[n:] - x[:-n]
    return out
