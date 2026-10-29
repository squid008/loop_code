# -*- coding: utf-8 -*-
"""build_event_factors.py — 把事件数据聚合成 2 个因子 + 直接算 IC。

★ 因子定义（2026-10-29，用户选 A 方案；先算 IC 再接引擎，避免又白跑几十代）：
  | 因子 | 含义 | 方向 | 学术依据 |
  |---|---|---|---|
  | `float_pressure_60` | **未来 60 日**解禁比例之和（%） | 越大越空 | 解禁前后负超额 |
  | `repurchase_60` | **过去 60 日**回购金额 / 总市值 | 越大越多 | 回购后正超额 |

★ 为什么这两个可能有效（而两融/龙虎榜无效）：
  两融/龙虎榜是**行为强度**，与量价同源 ⇒ 剥风格后 94% 转负；
  解禁是**外生供给事件**、回购是**公司主动信号**，与价格不同源 ✓

用法：
    python tools/build_event_factors.py             # 聚合 + IC + 存 data/event_factors.h5
    python tools/build_event_factors.py --no-save
"""
import argparse
import io
import os
import sys

import numpy as np
import pandas as pd

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = r"E:\quant\loop_code"
DATA = os.path.join(ROOT, "data")
SRC_FLOAT = os.path.join(DATA, "event_share_float.parquet")
SRC_BUY = os.path.join(DATA, "event_repurchase.parquet")
OUT = os.path.join(DATA, "event_factors.h5")
PANEL = os.path.join(ROOT, "engine", "panel.h5")

WIN = 60
MIN_N = 50


def to_panel_col(s):
    s = str(s)
    for a, b in ((".SZ", ".XSHE"), (".SH", ".XSHG"), (".BJ", ".XBSE")):
        if s.endswith(a):
            return s[: -len(a)] + b
    return None


def load_panel():
    with pd.HDFStore(PANEL, "r") as st:
        keys = set(st.keys())
        close = st["close"]
        dates = np.asarray(close.index)
        cols = list(close.columns)
        mktcap = None
        for k in ("mktcap", "/mktcap", "total_mv"):
            if "/" + k.lstrip("/") in keys:
                mktcap = st[k.lstrip("/")].reindex(index=dates, columns=cols).to_numpy(dtype="float32")
                break
        if mktcap is None and "/ln_mktcap" in keys:
            # 市值只有对数形式 ⇒ 还原（回购/市值是比率，取 exp 即可，量级对就够）
            mktcap = np.exp(st["ln_mktcap"].reindex(index=dates, columns=cols).to_numpy(dtype="float32"))
    return dates, cols, close.to_numpy(dtype="float32"), mktcap


def _daily_from_events(df, date_col, val_col, dates, cols):
    """把稀疏事件表展开成 `(T, S)` 日频矩阵：同一 (股票, 交易日) 的多次事件**求和**。"""
    T, S = len(dates), len(cols)
    sidx = {c: i for i, c in enumerate(cols)}
    out = np.zeros((T, S), dtype="float32")
    d = df.copy()
    d["col"] = d["ts_code"].map(to_panel_col)
    d = d[d["col"].notna()].copy()
    d["dt"] = pd.to_numeric(d[date_col], errors="coerce")
    d[val_col] = pd.to_numeric(d[val_col], errors="coerce")
    d = d.dropna(subset=["dt", val_col])

    dates_sorted = np.sort(dates)
    pos = {int(x): i for i, x in enumerate(dates_sorted)}
    n_miss = 0
    for col, dt, v in zip(d["col"], d["dt"].astype("int64"), d[val_col]):
        si = sidx.get(col)
        di = pos.get(int(dt))
        if di is None:
            # 事件日不是交易日（周末/停牌）⇒ 顺延到下一个交易日
            nxt = dates_sorted[dates_sorted >= dt]
            di = pos.get(int(nxt[0])) if len(nxt) else None
        if si is None or di is None:
            n_miss += 1
            continue
        out[di, si] += float(v)
    if n_miss:
        print("    事件日/股票未匹配 %d 条（停牌或已退市，正常）" % n_miss)
    return out


def future_sum(mat, win=WIN):
    """`future_sum[t] = mat[t+1 .. t+win]` 的和（解禁压力要看**未来**）。"""
    T, S = mat.shape
    cs = np.concatenate([np.zeros((1, S), dtype="float64"),
                         np.cumsum(mat.astype("float64"), axis=0)], axis=0)
    idx = np.minimum(np.arange(T) + win + 1, T)
    lo = np.minimum(np.arange(T) + 1, T)
    return (cs[idx] - cs[lo]).astype("float32")


def past_sum(mat, win=WIN):
    df = pd.DataFrame(mat.astype("float64"))
    return df.rolling(win, min_periods=1).sum().to_numpy(dtype="float32")


def fwd_ret(close, h):
    c = pd.DataFrame(close)
    return (c.shift(-h) / c - 1.0).to_numpy(dtype="float32")


def calc_ic(fac, ret, min_n=MIN_N):
    ics = []
    for t in range(len(fac) - 1):
        f, r = fac[t], ret[t]
        m = np.isfinite(f) & np.isfinite(r)
        if m.sum() < min_n:
            continue
        fr = pd.Series(f[m]).rank()
        rr = pd.Series(r[m]).rank()
        if fr.std() < 1e-12 or rr.std() < 1e-12:
            continue
        ics.append(float(np.corrcoef(fr, rr)[0, 1]))
    if not ics:
        return None
    a = np.asarray(ics)
    return dict(n=len(a), ic=float(a.mean()), ic_ir=float(a.mean() / (a.std() + 1e-12)),
                pos=float((a > 0).mean()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-save", action="store_true")
    a = ap.parse_args()

    print("=" * 78)
    print("【1】读数据")
    print("=" * 78)
    dates, cols, close, mktcap = load_panel()
    print("  面板 %d 日 × %d 股（%d ~ %d）" % (len(dates), len(cols), dates[0], dates[-1]))
    print("  市值字段: %s" % ("有" if mktcap is not None else "缺失（回购因子改用成交额代理）"))

    facs = {}

    # ---- 因子 1：未来 60 日解禁压力 ----
    if os.path.isfile(SRC_FLOAT):
        f = pd.read_parquet(SRC_FLOAT)
        print("  解禁记录 %d 行 · %d 只股票" % (len(f), f.ts_code.nunique()))
        daily = _daily_from_events(f, "float_date", "float_ratio", dates, cols)
        facs["float_pressure_60"] = future_sum(daily)
    else:
        print("  解禁数据缺失（先跑 tools/fetch_event_data.py）")

    # ---- 因子 2：近 60 日回购金额 / 市值 ----
    if os.path.isfile(SRC_BUY):
        b = pd.read_parquet(SRC_BUY)
        print("  回购记录 %d 行 · %d 只股票" % (len(b), b.ts_code.nunique()))
        daily_b = _daily_from_events(b, "ann_date", "amount", dates, cols)
        num = past_sum(daily_b)
        if mktcap is not None:
            with np.errstate(divide="ignore", invalid="ignore"):
                facs["repurchase_60"] = num / mktcap
            facs["repurchase_60"][~np.isfinite(facs["repurchase_60"])] = np.nan
        else:
            facs["repurchase_60"] = num
    else:
        print("  回购数据缺失")

    print()
    print("=" * 78)
    print("【2】因子概况")
    print("=" * 78)
    for nm, m in facs.items():
        fin = np.isfinite(m) & (m != 0)
        print("  %-20s 非零覆盖 %5.1f%%  中位 %.4g  P95 %.4g"
              % (nm, 100 * fin.mean(),
                 float(np.nanmedian(m[fin])) if fin.any() else float("nan"),
                 float(np.nanpercentile(m[fin], 95)) if fin.any() else float("nan")))

    print()
    print("=" * 78)
    print("【3】IC（逐日横截面 Spearman）")
    print("=" * 78)
    for h in (5, 20):
        r = fwd_ret(close, h)
        for nm, m in facs.items():
            st = calc_ic(m, r)
            if st:
                print("  %-20s %2d日 IC %+.4f  IC_IR %+.3f  正比例 %.0f%%" %
                      (nm, h, st["ic"], st["ic_ir"], 100 * st["pos"]))
            else:
                print("  %-20s %2d日 有效样本不足" % (nm, h))

    print()
    print("判据：|IC| > 0.02 且 IC_IR > 0.2 才值得接引擎")

    if not a.no_save and facs:
        with pd.HDFStore(OUT, "w") as st:
            for nm, m in facs.items():
                st[nm] = pd.DataFrame(m, index=dates, columns=cols)
        print("\n已存 -> %s" % OUT)


if __name__ == "__main__":
    main()
