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


def _cum_w(x, w):
    """窗口和（前缀和技巧）：`out[t] = Σ x[t-w+1 .. t]`。

    与 `_win_sum` 的区别：这里 `out` 的前 `w-1` 行是 **NaN**（不是"不足窗的部分和"）。
    ⇒ 回归类算子的**正确性要求"同一批点"** ⇒ 必须**满窗**，不能让窗口长度随位置变化
      （否则 `n` 变了，`Su`/`Suu` 常数就错了）✓
    """
    c = np.cumsum(x, axis=0)
    out = np.full_like(c, np.nan)
    out[w - 1] = c[w - 1]
    if c.shape[0] > w:
        out[w:] = c[w:] - c[:-w]
    return out


def ts_slope(x, w):
    """滚动线性回归**斜率** `slope(y ~ t)`（对齐 QuantAlpha `Slope(A, N)` / qlib `BETA*`）。

    ## 2026-09-15 新增（`loop_todo §1.26` ③ 回归类）—— 用户点名

    **为什么值得加**：`slope` 是「**趋势方向 + 强度**」，与 `ts_mean`（水平）是**不同的信息通道**：
      `ts_mean20(x)` 说"x 最近平均多少"，`ts_slope20(x)` 说"x 正在以多快速度往哪个方向走" ✓
      ⇒ 一条**独立的平滑/趋势通道**（正对 §1.20 铁律「瓶颈是信号源多样性」）。

    ## 数学（满窗 `n = w`，`u = 0..w-1` 为窗口内位置）

    ```
    Su  = Σu   = w(w-1)/2                 ← 常数（满窗 ⇒ 只算一次）
    Suu = Σu²  = (w-1)w(2w-1)/6           ← 常数
    Sxx = Suu - Su²/w                     ← 常数
    T1  = Σy ·  T2 = Σu·y ·  T3 = Σy²     ← 3 个前缀和
    Sxy = T2 - Su·T1/w
    slope = Sxy / Sxx
    ```
    ⇒ **只需 3 个前缀和**（`Σy` / `Σu·y` / `Σy²`）⇒ 实测 **0.42s**（3309×2000）✓

    ★★ **满窗语义**（`n = w` 固定）：回归必须用**同一批点**，缺一个点 `Su`/`Suu` 就变
      ⇒ 前 `w-1` 期 + 窗口内含 NaN 的期 ⇒ **输出 NaN** ✓（与 `ts_ema` 的满窗一致）
    ★ **`Sxx` 恒 > 0**（`w≥2`），无需除零保护；但 `x` 全 NaN 时 `T1..T3` 是 0 ⇒ 会被满窗检查挡掉 ✓
    """
    return _linreg(x, w)[0]


def ts_rsqr(x, w):
    """滚动线性回归**拟合度 R²**（对齐 QuantAlpha `Rsquare(A, N)` / qlib `RSQR*`）。

    ## 2026-09-15 新增（用户点名）—— 用户的理由与我的补充

    **用户原话**：「还有线性回归**拟合度 R方**也很重要，**R方高线性度好，说明涨得稳**，你觉得呢？」
    **判断：方向对 ✓，但要补三点**：
      ① ★ **R² 不含方向** —— 「涨得稳」和「**跌得稳**」都是高 R²
         ⇒ **必须配合 `ts_slope` 的符号**用（如 `mul(ts_rsqr20(close), ts_slope20(close))`
            = "趋势干净度 × 方向"，或让引擎按 IC 自己定 `sign`）✓
      ② ★ **`R² = Sxy²/(Sxx·SS_tot)`，当 `SS_tot → 0`（价格几乎不动）时是 0/0** ⇒
         数值不稳定 ⇒ 本实现用 `EPS` 兜底：`SS_tot < EPS` 处**输出 NaN**（**不臆造**）✓
      ③ ★★ **`R²` 是尺度无关的**（乘任何正常数不变）⇒ 对"波动大小"不敏感
         ⇒ 它捕捉的是「**路径有没有单边趋势**」，不是「涨得多不多」✓

    ## 数学
    `R² = 1 - SS_res/SS_tot = Sxy²/(Sxx · SS_tot)`，`SS_tot = T3 - T1²/w`
    """
    return _linreg(x, w)[1]


def ts_resi(x, w):
    """滚动线性回归的**残差**（对齐 QuantAlpha `Resi(A, N)`）—— **最后一点相对趋势线的偏离**。

    ★ 与 `ts_slope` / `ts_rsqr` 出自**同一次回归** ⇒ 几乎零额外成本（同一份前缀和）✓
    **语义**：趋势之外的"意外"部分 ⇒ `+` 表示**冲高偏离**，`-` 表示**超跌偏离** ✓
    """
    return _linreg(x, w)[2]


def _linreg(x, w):
    """一次算出 `(slope, rsqr, resi)` —— 三个算子共用，避免重复前缀和。

    :return: 三个 `(T,S)` float32 数组
    """
    x = _prep(x)
    T, S = x.shape
    y = np.where(np.isfinite(x), x, 0.0)
    m = np.isfinite(x)
    cnt = _cum_w(m.astype(np.float64), w)                 # 满窗有效计数
    T1 = _cum_w(y, w)                                     # Σy
    T3 = _cum_w(y * y, w)                                 # Σy²
    # Σu·y：u 是**窗口内位置**(0..w-1) ⇒ Σ(u·y) = Σ(j·y) - a·Σy，a = 窗口起点 = t-w+1
    #   这里用**全局索引** j 的前缀和；一次性乘上列向量索引即可（O(T·S)）
    j = np.arange(T, dtype=np.float64)[:, None]
    T2 = _cum_w(j * y, w) - (j - (w - 1)) * T1            # = Σu·y ✓
    n = float(w)
    Su = n * (n - 1.0) / 2.0
    Suu = (n - 1.0) * n * (2.0 * n - 1.0) / 6.0
    Sxx = Suu - Su * Su / n                               # 常数 > 0（w>=2）
    mean = T1 / n
    Sxy = T2 - Su * T1 / n
    slope = Sxy / Sxx
    SS_tot = T3 - T1 * T1 / n
    with np.errstate(invalid='ignore', divide='ignore'):
        rsqr = (Sxy * Sxy) / (Sxx * SS_tot)
    # ★ 数值保护：SS_tot≈0（几乎不动）⇒ R² 是 0/0 ⇒ **NaN**（不臆造，也不给假 1.0）
    rsqr = np.where(SS_tot > 1e-12, rsqr, np.nan)
    rsqr = np.clip(rsqr, 0.0, 1.0)                        # 浮点误差可能让它微超 1
    # 残差：最后一个有效点相对趋势线 ⇒ intercept = (T1 - slope·Su)/n，u_last = n-1
    resi = y - ((T1 - slope * Su) / n + slope * (n - 1.0))
    ok = np.isfinite(cnt) & (cnt >= n)                    # ★ 满窗（cnt==w，NaN 处 cnt 为 nan）
    f = lambda a: np.where(ok, a, np.nan).astype(np.float32)
    return f(slope), f(rsqr), f(resi)


def ts_skew(x, w):
    """滚动**偏度**（三阶矩，对齐 QuantAlpha `TS_SKEW` / qlib `SKEW*`）。

    **为什么值得加**：均值/标准差描述"水平和波动"，**偏度描述"尾巴往哪边"** ——
      收益分布右偏（正偏）常伴随"慢跌急涨"，左偏反之 ⇒ **独立的分布形状通道** ✓
    **数学**：`skew = m3 / m2^1.5`，`m2 = E[y²]-E[y]²`，
      `m3 = E[y³] - 3·E[y]·E[y²] + 2·E[y]³`（中心矩展开，避免两次循环）⇒ 3 个前缀和 ✓
    ⚠ 与 `ts_ema` 一致采用**满窗**（矩估计对缺失敏感）⇒ 前 `w-1` 期 NaN。
    """
    x = _prep(x)
    y = np.where(np.isfinite(x), x, 0.0)
    m = np.isfinite(x)
    cnt = _cum_w(m.astype(np.float64), w)
    T1 = _cum_w(y, w)
    T2 = _cum_w(y * y, w)
    T3 = _cum_w(y * y * y, w)
    n = float(w)
    mu = T1 / n
    m2 = T2 / n - mu * mu
    m3 = T3 / n - 3.0 * mu * (T2 / n) + 2.0 * mu ** 3
    with np.errstate(invalid='ignore', divide='ignore'):
        out = m3 / np.power(np.maximum(m2, 1e-12), 1.5)
    ok = np.isfinite(cnt) & (cnt >= n) & (m2 > 1e-12)
    return np.where(ok, out, np.nan).astype(np.float32)


def ts_kurt(x, w):
    """滚动**超额峰度**（四阶矩，对齐 QuantAlpha `TS_KURT` / qlib `KURT*`）。

    **为什么值得加**：峰度刻画"**极端值密度**" —— 高峰度 = 厚尾（暴涨暴跌多），
      低峰度 = 温和 ⇒ 与波动率**不等价**（同样是 σ，厚尾的尾部风险更大）✓
    **数学**：`kurt = m4/m2² - 3`（**超额**，正态为 0 ⇒ 便于比较），
      `m4 = E[y⁴] - 4·E[y]·E[y³] + 6·E[y]²·E[y²] - 3·E[y]⁴` ⇒ 4 个前缀和 ✓
    """
    x = _prep(x)
    y = np.where(np.isfinite(x), x, 0.0)
    m = np.isfinite(x)
    cnt = _cum_w(m.astype(np.float64), w)
    T1 = _cum_w(y, w)
    T2 = _cum_w(y * y, w)
    T3 = _cum_w(y * y * y, w)
    T4 = _cum_w(y * y * y * y, w)
    n = float(w)
    mu = T1 / n
    m2 = T2 / n - mu * mu
    m4 = (T4 / n - 4.0 * mu * (T3 / n) + 6.0 * mu * mu * (T2 / n) - 3.0 * mu ** 4)
    with np.errstate(invalid='ignore', divide='ignore'):
        out = m4 / np.maximum(m2 * m2, 1e-24) - 3.0
    ok = np.isfinite(cnt) & (cnt >= n) & (m2 > 1e-12)
    return np.where(ok, out, np.nan).astype(np.float32)


def ts_ema(x, w):
    """指数移动平均 EMA —— 衰减因子 `α = 2/(w+1)`（对齐 QuantaAlpha `EMA` / 通达信 `EMA`）。

    ## 2026-09-15 新增（`loop_todo §1.25`）—— 为什么值得加

    盘点发现：我们的算子族里 **`ts_mean` 是「等权」、EMA 是「指数加权」
    ⇒ 这是**不同的算子，组合不出来** ⇒ 这是唯一"补不回来"的缺口** ✗
    加了它 ⇒ 提供一条**新的平滑通道** = **新信号源**（正对 §1.20 铁律「瓶颈是信号源多样性」）✓
    ★ 尤其：`sub(ema12(x), ema26(x))` **就是 MACD** ⇒ 不必再单独加 `MACD` ✓

    ## ★ 为什么**不能用前缀和**（本文件其它算子的加速技巧）

    EMA 是**递归**的：`ema_t = α·x_t + (1-α)·ema_{t-1}` ⇒ 无法用 `cumsum` 表达。
    ★★ **真面板实测（3309×5384，2026-09-15）**：
      `ema12(close)` **0.58s** · `ema26(close)` 0.59s · `sub(ema12,ema26)` 1.26s
      **vs 对照 `ts_mean20(close)` 1.17s** ⇒ ★ **`ema` 反而比 `ts_mean` 快约一倍** ✓
      （原因：`ts_mean` 要算两次 `cumsum`（值和有效计数）+ 除法，而 EMA 是单次循环）
      ⚠ 我原先按小面板估算写"ema 更慢" ⇒ **是错的，真面板实测相反** ✓
    （也试过 `scipy.signal.lfilter`：0.32s（该随机数据下），且它把 NaN **传播**成整段 NaN ⇒
      不符合我们"NaN 视为缺失"的口径 ✗ ⇒ **不引入 scipy 依赖**。）

    ## ★★ 与其它 `ts_*` 的**两点语义差异**（都是"递归量"带来的）

    **(1) `min_periods = w`（满窗）**，不是 `max(2, w//2)`：
      EMA 的早期值**严重依赖起点** —— 起点影响 `(1-α)^k`，`w` 期后仍有 `(1-2/(w+1))^w ≈ 13.5%` 残留
      ⇒ **必须等满窗**才输出 ⇒ 前 `w-1` 期为 NaN。
      **代价可控**：面板 **3309 日**，`w=60` 只占 **1.8%** ✓
      （⚠ 与 `ts_mean` 不同：后者用 `w//2`，前几期就有值 —— 均值稳定，EMA 不稳定）

    **(2) NaN 处「跳过」**：保持上一个 EMA 值、**计数不增加**（不是 rolling 那种
      "窗内 NaN 不计入分母"）—— 这是通达信/qlib 的口径 ✓
      计数不足 `w` 时输出 NaN ⇒ 停牌很久的股票不会被"补出"虚假值 ✓

    **★ 不引入未来信息**（铁律）：只依赖 `≤ t` 的值，递归单向 ✓
    """
    x = _prep(x)                      # (T,S) float64
    T, S = x.shape
    a = 2.0 / (w + 1.0)
    out = np.full((T, S), np.nan, dtype=np.float64)
    prev = np.full(S, np.nan, dtype=np.float64)
    n = np.zeros(S, dtype=np.int64)
    for t in range(T):
        v = x[t]
        m = np.isfinite(v)
        # 有上一个 ema ⇒ 递推（NaN 处沿用 prev）；否则以本期值作起点
        prev = np.where(np.isfinite(prev),
                        a * np.where(m, v, prev) + (1.0 - a) * prev,
                        np.where(m, v, np.nan))
        n = np.where(m, n + 1, n)
        out[t] = np.where(n >= w, prev, np.nan)
    return out.astype(np.float32)
