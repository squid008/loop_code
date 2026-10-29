# -*- coding: utf-8 -*-
"""portfolio_oos.py — 组合的**只用多头**表现 + **样本外**验证（2026-10-29）。

★ 为什么要做样本外：
  上一轮报的「8 个因子等权 → Calmar 4.47」是**样本内**结果 ——
  那 8 个是**按全样本 Calmar 排序后挑出来的**，天然带选择偏差（挑到了历史最顺的）✗
  唯一能判断“能不能用”的办法：**用前半段选因子，后半段检验** ✓

★ 两种口径：
  · **多头**（long only）：买 top 组，不空 ⇒ **含市场 β**，回撤大但可直接执行
    数据源：`docs/factor_curves/Fxx.json` 的 `nav_t`（已扣成本，2018 起）
  · **多空**（long-short）：top − bottom ⇒ 纯 alpha，但需要融券/期货对冲
    数据源：`data/ls_curves/Fxx.json`（`build_ls_curves.py` 重算，2013 起）

★ 分割：样本内 ≤ 2022-12-31，样本外 ≥ 2023-01-01（约 3.5 年，够看一轮牛熊）

用法：
    python tools/portfolio_oos.py               # 默认 20230101 分割
    python tools/portfolio_oos.py --split=20240101
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
CURVES = os.path.join(ROOT, "docs", "factor_curves")
LS = os.path.join(ROOT, "data", "ls_curves")
METRICS = os.path.join(ROOT, "docs", "factor_metrics.csv")
MIN_N = 100


def load_long():
    """纯多头净值（`nav_t`，已扣成本）→ 日收益。"""
    out = {}
    for f in sorted(glob.glob(os.path.join(CURVES, "F[0-9][0-9].json"))):
        try:
            d = json.load(io.open(f, encoding="utf-8"))
        except Exception:                                  # noqa: BLE001
            continue
        nav, dts = d.get("nav_t"), d.get("d_dates")
        if not nav or not dts or len(nav) != len(dts):
            continue
        s = pd.Series(nav, index=[int(x) for x in dts], dtype="float64").sort_index()
        out[d["name"]] = s.pct_change()
    return pd.DataFrame(out).dropna(how="all").iloc[1:]


def load_ls():
    """多空净值（top10 − bottom10，已扣成本）→ 日收益。"""
    out = {}
    for f in sorted(glob.glob(os.path.join(LS, "F[0-9][0-9].json"))):
        try:
            s = pd.read_json(f, typ="series")
        except Exception:                                  # noqa: BLE001
            continue
        s.index = [int(x) for x in s.index]
        s = pd.Series(s.values, index=s.index, dtype="float64").sort_index()
        out[os.path.basename(f)[:-5]] = s.pct_change()
    return pd.DataFrame(out).dropna(how="all").iloc[1:]


def perf(r):
    """从日收益算年化/Calmar/Sharpe/回撤/负年。"""
    r = pd.Series(r).dropna()
    if len(r) < MIN_N:
        return None
    nav = (1 + r).cumprod()
    yrs = len(r) / 244.0
    ann = float(nav.iloc[-1] ** (1 / yrs) - 1)
    dd = float((nav / nav.cummax() - 1).min())
    vol = float(r.std() * np.sqrt(244))
    sharpe = float(r.mean() / (r.std() + 1e-12) * np.sqrt(244))
    calmar = ann / abs(dd) if dd < 0 else np.nan
    idx = pd.to_datetime(pd.Index(r.index).astype(str), format="%Y%m%d", errors="coerce")
    neg = 0
    if idx.notna().any():
        yr = pd.Series(r.values, index=idx).groupby(lambda i: i.year).apply(lambda x: (1 + x).prod() - 1)
        neg = int((yr < 0).sum())
    return dict(ann=ann, calmar=calmar, sharpe=sharpe, mdd=dd, vol=vol, neg_yr=neg, n=len(r))


def greedy(ret, order, thr):
    """按 `order`（已排好序的因子名）贪婪选与已选相关性 < thr 的。"""
    corr = ret.corr()
    picked = []
    for nm in order:
        if nm not in corr.columns:
            continue
        if not picked or corr.loc[nm, picked].abs().max() < thr:
            picked.append(nm)
    return picked


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="20230101")
    ap.add_argument("--thr", type=float, default=0.5)
    a = ap.parse_args()
    split = int(a.split)

    for kind, loader in (("多头 (long only)", load_long), ("多空 (long-short)", load_ls)):
        ret = loader()
        if ret.empty:
            print("%s：没有数据" % kind)
            continue
        ds = pd.Index(ret.index)
        is_mask = ds < split
        oos_mask = ds >= split

        # ---- 用**样本内** Calmar 排序（不能用全样本，那样就偷看了未来）----
        is_stats = {}
        for c in ret.columns:
            st = perf(ret.loc[is_mask, c])
            if st:
                is_stats[c] = st["calmar"]
        order = [k for k, _ in sorted(is_stats.items(), key=lambda x: -x[1])]
        picked = greedy(ret.loc[is_mask], order, a.thr)
        w = pd.Series(1.0 / len(picked), index=picked)

        print()
        print("=" * 84)
        print("【%s】全样本 %d 因子 · %d 天（%s ~ %s）" % (kind, len(ret.columns),
              len(ret), ret.index[0], ret.index[-1]))
        print("=" * 84)
        print("  样本内（<%d）按 Calmar 选 %d 个：%s" % (split, len(picked), ", ".join(picked)))
        print()
        print("  %-22s %8s %8s %8s %8s %8s %6s" %
              ("口径", "年化", "Calmar", "Sharpe", "最大回撤", "波动", "负年"))

        rows = []
        for tag, mask in (("样本内", is_mask), ("样本外", oos_mask)):
            # 组合（8 个等权）
            st = perf((ret.loc[mask, picked] * w).sum(axis=1))
            if st:
                rows.append(("%s · 组合(%d个)" % (tag, len(picked)), st))
            # 全库等权（对照）
            st2 = perf(ret.loc[mask].mean(axis=1))
            if st2:
                rows.append(("%s · 全库等权" % tag, st2))
            # 单因子（样本内最好的那个）
            if picked:
                st3 = perf(ret.loc[mask, picked[0]])
                if st3:
                    rows.append(("%s · 单因子 %s" % (tag, picked[0]), st3))

        for label, st in rows:
            print("  %-22s %7.2f%% %8.3f %8.2f %8.2f%% %7.2f%% %6d"
                  % (label, 100 * st["ann"], st["calmar"], st["sharpe"],
                     100 * st["mdd"], 100 * st["vol"], st["neg_yr"]))

        # 衰减诊断
        combo_is = next((s for l, s in rows if l.startswith("样本内 · 组合")), None)
        combo_oos = next((s for l, s in rows if l.startswith("样本外 · 组合")), None)
        if combo_is and combo_oos:
            print()
            print("  衰减：Calmar %.3f → %.3f（保留 %.0f%%）· 年化 %.2f%% → %.2f%%"
                  % (combo_is["calmar"], combo_oos["calmar"],
                     100 * combo_oos["calmar"] / combo_is["calmar"] if combo_is["calmar"] else np.nan,
                     100 * combo_is["ann"], 100 * combo_oos["ann"]))


if __name__ == "__main__":
    main()
