# -*- coding: utf-8 -*-
"""build_rc_factors.py — 把 `data/rc_data.parquet`（券商研报明细）聚合成 4 个因子 + 直接算 IC。

★ 为什么先算 IC 而不是直接接引擎（2026-10-29，用户选 A 方案）：
  接引擎要改 5 个文件 + 发版 + 跑几代（每代 ~50 分钟）。而 **IC 是上游指标**：
  IC 不行 ⇒ Calmar 必然不行。所以先用 20 分钟算 IC，避免又白跑几十代
  （前面两融/龙虎榜就是这样白跑了 30 代才发现 `calmar2` 最好只有 0.104）。

★ 4 个因子（都与价格低相关，正是 `strip_calmar` 需要的东西）：
  | 因子 | 含义 | 学术支撑 |
  |---|---|---|
  | `rc_eps_rev60` | 近 60 天 EPS 预测的**上调幅度** | earnings revision（分析师修正）是公认强因子 |
  | `rc_rating` | 近 60 天评级均值（买入=1 … 卖出=-1） | 评级变动有短期动量 |
  | `rc_cov60` | 近 60 天研报条数 | 关注度 / 信息环境 |
  | `rc_target_gap` | 目标价中值 / 收盘 - 1 | 估值空间 |

用法：
    python tools/build_rc_factors.py            # 聚合 + 算 IC + 存 data/rc_factors.h5
    python tools/build_rc_factors.py --no-save  # 只算 IC，不落盘
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
SRC = os.path.join(DATA, "rc_data.parquet")
OUT = os.path.join(DATA, "rc_factors.h5")
PANEL = os.path.join(ROOT, "engine", "panel.h5")

WIN = 60          # 滚动窗口（交易日）
MIN_N = 50        # 算 IC 时每日最少股票数

# 评级 → 分数（未知评级会告警并跳过，不臆造）
# ★ 2026-10-29 实测补全：数据里混着**英文评级**（BUY / OVERWEIGHT）和"谨慎推荐"
RATING_MAP = {
    "买入": 1.0, "强烈推荐": 1.0, "强推": 1.0, "推荐": 0.75, "强烈推荐-A": 1.0,
    "增持": 0.75, "优于大市": 0.75, "跑赢行业": 0.75,
    "中性": 0.0, "持有": 0.0, "同步大市": 0.0, "观望": 0.0, "中性评级": 0.0,
    "审慎增持": 0.25, "谨慎推荐": 0.25, "谨慎增持": 0.25,
    "减持": -0.5, "弱于大市": -0.5, "跑输行业": -0.5,
    "卖出": -1.0, "回避": -1.0,
    # 英文（同一批数据里混用）
    "BUY": 1.0, "STRONG BUY": 1.0, "OVERWEIGHT": 0.75, "OUTPERFORM": 0.75,
    "HOLD": 0.0, "NEUTRAL": 0.0, "UNDERWEIGHT": -0.5, "UNDERPERFORM": -0.5,
    "SELL": -1.0,
}


def to_panel_col(s):
    """`000001.SZ` → `000001.XSHE`（与 panel.h5 的列名对齐）。"""
    s = str(s)
    for a, b in ((".SZ", ".XSHE"), (".SH", ".XSHG"), (".BJ", ".XBSE")):
        if s.endswith(a):
            return s[: -len(a)] + b
    return None


def load_axis():
    """从 panel.h5 读坐标轴与收盘价（因子矩阵必须与它逐格对齐）。"""
    with pd.HDFStore(PANEL, "r") as st:
        close = st["close"]
        dates = np.asarray(close.index)
        cols = list(close.columns)
    return dates, cols, close


def load_rc():
    if not os.path.isfile(SRC):
        raise SystemExit("找不到 %s —— 先用 tools/fetch_rc_data.py 拉数据" % SRC)
    df = pd.read_parquet(SRC)
    df["col"] = df["ts_code"].map(to_panel_col)
    df = df[df["col"].notna()].copy()
    df["dt"] = pd.to_numeric(df["report_date"], errors="coerce")
    df = df[df["dt"].notna()].copy()
    df["dt"] = df["dt"].astype("int64")
    df["eps"] = pd.to_numeric(df["eps"], errors="coerce")
    df["tp"] = pd.to_numeric(df["tp"], errors="coerce")
    df["min_price"] = pd.to_numeric(df["min_price"], errors="coerce")
    # ★ 目标价 = `min_price`（2026-10-29 实测校准，别被字段名骗了）：
    #   `tp` 看着像 target price，实际是**净利润预测**（中位 85500 万，与 `np` 同量级）；
    #   真正的目标价是 `min_price`（中位 28.97 元）；`max_price` 非空率仅 **0.2%** ⇒ 弃用。
    #   ⚠ 用错字段会让 `rc_target_gap` 均值变成 **+34898**（应为 -1~1），一眼能看出是单位错配
    df["target"] = df["min_price"]
    df["score"] = df["rating"].map(RATING_MAP)
    unk = df[df["score"].isna()]["rating"].dropna().value_counts()
    if len(unk):
        print("  未识别评级（跳过，不臆造）：%s" % dict(list(unk.items())[:8]))
    print("  研报明细 %d 行 · %d 只股票 · %d ~ %d"
          % (len(df), df["col"].nunique(), df["dt"].min(), df["dt"].max()))
    return df


def _rolling_mean(mat, win=WIN):
    """按行（时间）滚动均值，忽略 NaN。"""
    df = pd.DataFrame(mat)
    return df.rolling(win, min_periods=1).mean().to_numpy(dtype="float32")


def build(df, dates, cols):
    """生成 4 个 `(T, S)` 因子矩阵，并与面板坐标轴严格对齐。"""
    T, S = len(dates), len(cols)
    sidx = {c: i for i, c in enumerate(cols)}
    didx = {int(d): i for i, d in enumerate(dates)}

    dates_sorted = np.sort(dates)
    dpos = {int(d): i for i, d in enumerate(dates_sorted)}

    # 每个 (股票, 日期) 先算"当日截面值"，再做 60 日滚动
    per_day = {}
    for kind in ("eps_rev", "rating", "cov", "gap"):
        per_day[kind] = np.full((T, S), np.nan, dtype="float32")

    # ---- 1) 每日 研报数 / 评级均值 / 目标价中值 ----
    g = df.dropna(subset=["score"]).groupby(["dt", "col"])["score"].mean()
    cnt = df.groupby(["dt", "col"]).size()
    tgt = df.dropna(subset=["target"]).groupby(["dt", "col"])["target"].median()

    def _put(series, kind):
        mat = per_day[kind]
        for (dt, col), v in series.items():
            di = dpos.get(int(dt))
            si = sidx.get(col)
            if di is not None and si is not None:
                mat[di, si] = v
        return mat

    _put(cnt, "cov")
    _put(g, "rating")
    _put(tgt, "gap")

    # ---- 2) EPS 修正：按 (股票, quarter) 追踪 60 日内的变化 ----
    eps_df = df.dropna(subset=["eps"]).sort_values(["dt"])
    eps_mat = per_day["eps_rev"]
    for (col, quarter), sub in eps_df.groupby(["col", "quarter"]):
        si = sidx.get(col)
        if si is None:
            continue
        sub = sub.drop_duplicates(subset=["dt"], keep="last")
        base_dt, base_eps = None, None
        for dt, eps in zip(sub["dt"].tolist(), sub["eps"].tolist()):
            di = dpos.get(int(dt))
            if di is None:
                continue
            if base_eps is not None and abs(base_eps) > 1e-9:
                rev = (eps - base_eps) / abs(base_eps)
                if np.isfinite(rev):
                    prev = eps_mat[di, si]
                    eps_mat[di, si] = rev if not np.isfinite(prev) else (prev + rev) / 2
            # 60 天后更换基准
            base_dt, base_eps = dt, eps

    # ---- 3) 60 日滚动（因子当日无研报 ⇒ 用窗口内历史值）----
    out = {}
    out["rc_cov60"] = _rolling_mean(per_day["cov"])
    out["rc_rating"] = _rolling_mean(per_day["rating"])
    out["rc_eps_rev60"] = _rolling_mean(per_day["eps_rev"])

    # 目标价空间 = 滚动目标价 / 当日收盘 - 1
    close = None
    with pd.HDFStore(PANEL, "r") as st:
        c = st["close"]
        close = c.reindex(index=dates, columns=cols).to_numpy(dtype="float32")
    tgt_roll = _rolling_mean(per_day["gap"])
    with np.errstate(divide="ignore", invalid="ignore"):
        out["rc_target_gap"] = tgt_roll / close - 1.0
    out["rc_target_gap"][~np.isfinite(out["rc_target_gap"])] = np.nan
    return out


def fwd_ret(close, h=5):
    """未来 h 日收益（与引擎的调仓口径同量级，仅用于 IC）。"""
    c = pd.DataFrame(close)
    r = c.shift(-h) / c - 1.0
    return r.to_numpy(dtype="float32")


def calc_ic(fac, ret, min_n=MIN_N):
    """逐日横截面 Spearman IC ⇒ 均值 / IC_IR / 正比例 / 覆盖率。"""
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
                pos=float((a > 0).mean()), ic_std=float(a.std()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-save", action="store_true")
    a = ap.parse_args()

    print("=" * 78)
    print("【1】读数据")
    print("=" * 78)
    dates, cols, close = load_axis()
    df = load_rc()
    print("  面板 %d 日 × %d 股（%d ~ %d）" % (len(dates), len(cols), dates[0], dates[-1]))

    print()
    print("=" * 78)
    print("【2】聚合成因子")
    print("=" * 78)
    facs = build(df, dates, cols)
    for nm, m in facs.items():
        cov = np.isfinite(m).mean()
        print("  %-16s 覆盖率 %5.1f%%  均值 %+.4f" % (nm, 100 * cov, np.nanmean(m)))

    print()
    print("=" * 78)
    print("【3】IC（5 日未来收益，逐日横截面 Spearman）")
    print("=" * 78)
    r5 = fwd_ret(close, 5)
    rows = []
    for nm, m in facs.items():
        st = calc_ic(m, r5)
        if st:
            rows.append((nm, st))
            print("  %-16s IC %+.4f  IC_IR %+.3f  正比例 %.0f%%  （%d 日，min_n=%d）"
                  % (nm, st["ic"], st["ic_ir"], 100 * st["pos"], st["n"], MIN_N))
        else:
            print("  %-16s 有效交易日不足（覆盖率太低或数据太短）" % nm)

    print()
    print("判据：|IC| > 0.02 且 IC_IR > 0.2 才算有信息量；"
          "两融/龙虎榜当时最好的一条 calmar2 只 0.104 ⇒ 已证明无效")

    if not a.no_save:
        with pd.HDFStore(OUT, "w") as st:
            for nm, m in facs.items():
                st[nm] = pd.DataFrame(m, index=dates, columns=cols)
        print("\n已存 -> %s" % OUT)


if __name__ == "__main__":
    main()
