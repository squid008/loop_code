# -*- coding: utf-8 -*-
"""build_ls_curves.py — 用 `facs/*/values.h5` 重算因子的**多空（long-short）净值**。

★ 为什么必须重算（2026-10-29）：
  `docs/factor_curves/Fxx.json` 里的 `nav_t` 是**纯多头组合净值**（跟着大盘，绝对相关 0.972、
  回撤 -36%）⇒ 拿它做组合优化，只是在平均同一个 β，**降不了风险** ✗
  真正的因子收益 = **top 组 减 bottom 组**（多空对冲，剥离市场）⇒ 才能：
    · 公平比较因子强弱（不被 β 稀释）
    · 做有意义的组合（残差互不相关才叫分散）

★ 口径（对齐 `factor_metrics.csv`，先用 F40 校验）：
  · 每 **5 个交易日**调仓（`n_rebal=418` ↔ 2018-2026 约 2090 日）
  · top 10% 等权做多 / bottom 10% 等权做空（按 `sign` 决定方向）
  · 往返成本 **0.004**，按实际换手率扣
  · 输出：多空净值 + Calmar / Sharpe / 回撤 / 年化

用法：
    python tools/build_ls_curves.py --only=F40        # 先校验口径
    python tools/build_ls_curves.py                   # 全量 53 个
    python tools/build_ls_curves.py --top=0.2         # 改分组比例
"""
import argparse
import glob
import io
import json
import os
import sys

import numpy as np
import pandas as pd

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = r"E:\quant\loop_code"
FACS = os.path.join(ROOT, "facs")
PANEL = os.path.join(ROOT, "engine", "panel.h5")
OUT = os.path.join(ROOT, "data", "ls_curves")


def load_close():
    with pd.HDFStore(PANEL, "r") as st:
        close = st["close"]
    return close.index.to_numpy(), close.columns.to_numpy(), close.to_numpy(dtype="float32")


def read_values(path):
    import h5py
    with h5py.File(path, "r") as f:
        ds = f["data"]
        arr = ds[:]
        at = {k: (v.decode("utf-8") if isinstance(v, bytes) else v)
              for k, v in ds.attrs.items()}
    return arr, at


def ls_nav(vals, dates, cols, close, sign=1, freq=5, top=0.1, cost=0.004):
    """多空净值：每 freq 日调仓，top 组多头 / bottom 组空头。

    `vals` 是 `(T, S)` 因子值（与 dates/cols 对齐）；NaN 视为不可交易。
    返回 (净值 Series, 统计 dict)。
    """
    T, S = vals.shape
    reb = list(range(0, T - freq, freq))
    if not reb:
        return None, {}

    ret = np.full(T, np.nan, dtype="float64")     # 日频多空收益
    prev_long = prev_short = None
    for i, t in enumerate(reb):
        v = vals[t]
        px_t, px_t1 = close[t], close[min(t + freq, T - 1)]
        ok = np.isfinite(v) & np.isfinite(px_t) & np.isfinite(px_t1) & (px_t > 0)
        if ok.sum() < 100:
            continue
        n = int(ok.sum() * top)
        if n < 10:
            continue
        idx = np.where(ok)[0]
        # ⚠⚠ **不要再乘 `sign`**（2026-10-29 实测踩坑）：
        #   `facs/*/values.h5` 的 `data` **已经按 sign 归一化**（值大 ⇒ 预期收益高），
        #   `sign` 只是当时写入时记下的方向；再乘一次就把所有因子翻反 ——
        #   F40 会从 +24%（freq=5，扣成本后）变成 **-24%**，和指标表的 +1.35 完全对不上 ✗
        order = idx[np.argsort(v[idx])]
        longs, shorts = order[-n:], order[:n]

        fwd = px_t1 / px_t - 1.0
        r = float(np.nanmean(fwd[longs]) - np.nanmean(fwd[shorts]))

        # 成本：按与上期持仓的重叠度算换手（新进/新出的比例）
        to = 0.0
        if prev_long is not None:
            to = (len(set(longs.tolist()) ^ set(prev_long.tolist())) / (2.0 * n)
                  + len(set(shorts.tolist()) ^ set(prev_short.tolist())) / (2.0 * n)) / 2.0
        prev_long, prev_short = longs, shorts

        # ⚠⚠ 成本只能扣**一次**（每期一次往返），再按 freq 天均摊。
        #   2026-10-29 首版写成 `r/freq - to*cost` ⇒ 等于**每天**扣一次成本 ⇒
        #   5 天扣 2%、418 期扣掉 167% ⇒ F40 算出来 -32%/年（指标表 +1.35）✗
        seg_total = r - to * cost
        ret[t + 1:min(t + freq + 1, T)] = seg_total / freq

    r = pd.Series(ret, index=dates).dropna()
    if len(r) < 60:
        return None, {}
    nav = (1 + r).cumprod()
    yrs = len(r) / 244.0
    ann = float(nav.iloc[-1] ** (1 / yrs) - 1) if yrs > 0 else np.nan
    dd = float((nav / nav.cummax() - 1).min())
    sharpe = float(r.mean() / (r.std() + 1e-12) * np.sqrt(244))
    calmar = ann / abs(dd) if dd < 0 else np.nan
    return nav, dict(ann=ann, calmar=calmar, sharpe=sharpe, mdd=dd, n=len(r))


def find_files(only=None):
    out = []
    for b in sorted(os.listdir(FACS)):
        d = os.path.join(FACS, b)
        if not os.path.isdir(d):
            continue
        for nm in sorted(os.listdir(d)):
            p = os.path.join(d, nm, "values.h5")
            if os.path.isfile(p) and (only is None or nm == only):
                out.append((nm, p))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=None)
    ap.add_argument("--top", type=float, default=0.1)
    ap.add_argument("--freq", type=int, default=5)
    ap.add_argument("--cost", type=float, default=0.004)
    a = ap.parse_args()

    dates, cols, close = load_close()
    files = find_files(a.only)
    print("因子值文件 %d 个；面板 %d 日 × %d 股" % (len(files), len(dates), len(cols)))
    os.makedirs(OUT, exist_ok=True)

    metrics = pd.read_csv(os.path.join(ROOT, "docs", "factor_metrics.csv"),
                          encoding="utf-8-sig").drop_duplicates(subset=["name"])
    ref = metrics.set_index("name")

    rows = []
    for nm, p in files:
        vals, at = read_values(p)
        if vals.shape != (len(dates), len(cols)):
            print("  %-5s 形状不符 %s ⇒ 跳过" % (nm, vals.shape))
            continue
        sign = int(at.get("sign", 1) or 1)
        nav, st = ls_nav(vals, dates, cols, close, sign=sign, freq=a.freq,
                         top=a.top, cost=a.cost)
        if nav is None:
            print("  %-5s 有效样本不足 ⇒ 跳过" % nm)
            continue
        nav.to_json(os.path.join(OUT, "%s.json" % nm))
        r = ref.loc[nm] if nm in ref.index else None
        rows.append((nm, st, (r["calmar"] if r is not None else np.nan)))

    print()
    print("  %-6s %8s %8s %8s %10s %10s" %
          ("因子", "多空年化", "多空Calmar", "Sharpe", "指标表Calmar", "差"))
    for nm, st, mc in sorted(rows, key=lambda x: -x[1]["calmar"])[:20]:
        print("  %-6s %7.2f%% %8.3f %8.2f %10.3f %10.3f"
              % (nm, 100 * st["ann"], st["calmar"], st["sharpe"], mc,
                 st["calmar"] - mc if np.isfinite(mc) else np.nan))

    n_ok = sum(1 for _, st, _ in rows if np.isfinite(st["calmar"]))
    med = np.nanmedian([st["calmar"] for _, st, _ in rows]) if rows else np.nan
    print("\n完成 %d 个（多空 Calmar 中位 %.3f）-> %s" % (n_ok, med, OUT))
    print("校验：多空 Calmar 应与指标表的 Calmar 同量级（指标表是超额口径）")


if __name__ == "__main__":
    main()
