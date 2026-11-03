# -*- coding: utf-8 -*-
"""hedge_cost.py — 算「**真正可执行**」的策略表现（2026-11-02）。

★ 为什么需要这个（用户质疑，且质疑完全正确）：
  上一轮报的「8 因子多空 → 样本外 Calmar 3.85」在 A 股**拿不到**：
  空头腿是 bottom 10%（恰恰是小盘股）⇒ 融券券源极少、费率 8~10%、个人额度基本没有 ✗
  ⇒ 那是**理论值**，不是可执行值。

★ 三种口径（必须分清）：

  | 口径 | 能不能做 | 说明 |
  |---|---|---|
  | ① 纯多头 | ✓ 能做 | 买 top 组，无对冲 ⇒ 承担全部市场 β，回撤 -34%~-47% |
  | ② 多空（top−bottom） | **✗ 拿不到** | 空头腿需要融券，小盘股借不到 ⇒ **仅作理论上限参考** |
  | ③ **多头 + 股指期货空头** | ✓ **可行** | 买 top 组，用 IC/IF 空头对冲 β ⇒ 拿到「多头超额 + 贴水」 |

  本脚本算的是 ③（唯一可执行的“中性”方案）：
    收益 ≈ 多头超额（已有 `nav_t` ÷ 全市场等权） + 期货贴水收益 − 期货成本

★ 贴水与成本（保守假设，可调）：
  · IC/IM 期货常年**贴水**，对**空头有利**（空头只支付期货涨幅，比现货少涨）
    ⇒ 按年化 **+5%** 计入（2019-2021 深贴水时是 +10~15%，2024 后收窄 ⇒ 取保守值）
  · 期货保证金占用 15%、资金成本 3% ⇒ **0.45%/年**
  · 展期 12 次/年 × 单边 0.02% ⇒ **0.24%/年**
  · 多头交易成本已含在 `nav_t` 里（首日就扣了 0.004）

用法：
    python tools/hedge_cost.py
    python tools/hedge_cost.py --basis=0.08 --cost=0.007   # 改假设
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
SPLIT = 20230101
MIN_N = 100


def load_long():
    """纯多头净值（已扣成本）→ 净值矩阵（不是收益，超额要用净值相除）。"""
    out = {}
    for f in sorted(glob.glob(os.path.join(CURVES, "F[0-9][0-9].json"))):
        try:
            d = json.load(io.open(f, encoding="utf-8"))
        except Exception:                                  # noqa: BLE001
            continue
        nav, dts = d.get("nav_t"), d.get("d_dates")
        if not nav or not dts or len(nav) != len(dts):
            continue
        out[d["name"]] = pd.Series(nav, index=[int(x) for x in dts], dtype="float64")
    return pd.DataFrame(out).sort_index().ffill().dropna(how="all")


def load_ls():
    out = {}
    for f in sorted(glob.glob(os.path.join(LS, "F[0-9][0-9].json"))):
        try:
            s = pd.read_json(f, typ="series")
        except Exception:                                  # noqa: BLE001
            continue
        s.index = [int(x) for x in s.index]
        out[os.path.basename(f)[:-5]] = pd.Series(s.values, index=s.index, dtype="float64")
    return pd.DataFrame(out).sort_index().ffill().dropna(how="all")


def perf(nav, basis=0.0, cost=0.0, mask=None):
    """从**净值**算指标；`basis`/`cost` 是按年化加减的常数（贴水收益 / 期货成本）。"""
    s = pd.Series(nav).dropna()
    if mask is not None:
        s = s[mask(s.index)]
    if len(s) < MIN_N:
        return None
    r = s.pct_change().dropna()
    yrs = len(r) / 244.0
    # 把年化常数摊到每天：贴水对空头=正收益，成本=负
    adj = (basis - cost) / 244.0
    r2 = r + adj
    nv = (1 + r2).cumprod()
    ann = float(nv.iloc[-1] ** (1 / yrs) - 1)
    dd = float((nv / nv.cummax() - 1).min())
    vol = float(r2.std() * np.sqrt(244))
    sharpe = float(r2.mean() / (r2.std() + 1e-12) * np.sqrt(244))
    calmar = ann / abs(dd) if dd < 0 else np.nan
    return dict(ann=ann, calmar=calmar, sharpe=sharpe, mdd=dd, vol=vol, n=len(r2))


def greedy(ret, order, thr):
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
    ap.add_argument("--basis", type=float, default=0.05, help="期货贴水年化收益（保守 5%%）")
    ap.add_argument("--cost", type=float, default=0.007, help="期货保证金+展期成本年化")
    ap.add_argument("--thr", type=float, default=0.5)
    a = ap.parse_args()

    nav_l = load_long()
    nav_s = load_ls()
    metrics = pd.read_csv(METRICS, encoding="utf-8-sig").drop_duplicates(subset=["name"])

    # 基准：全市场等权（近似中证500 的 β）
    ret_l = nav_l.pct_change().dropna(how="all")
    bench_ret = ret_l.mean(axis=1)
    bench = (1 + bench_ret).cumprod()

    print("=" * 88)
    print("可执行性对照（样本外 = %d 起）" % SPLIT)
    print("=" * 88)
    print("  贴水假设 %+.1f%%/年（对空头有利）；期货成本 %.2f%%/年"
          % (100 * a.basis, 100 * a.cost))
    print()

    # ---- 选因子：用样本内多头 Calmar ----
    is_mask = lambda idx: np.array([i < SPLIT for i in idx])
    is_stats = {}
    for c in nav_l.columns:
        st = perf(nav_l[c], mask=is_mask)
        if st:
            is_stats[c] = st["calmar"]
    order = [k for k, _ in sorted(is_stats.items(), key=lambda x: -x[1])]
    picked = greedy(ret_l[lambda idx: idx < SPLIT] if False else ret_l.loc[is_mask(ret_l.index)],
                    order, a.thr)
    if not picked:
        picked = order[:8]
    w = pd.Series(1.0 / len(picked), index=picked)
    print("  样本内选出 %d 个因子：%s" % (len(picked), ", ".join(picked)))
    print()

    # 组合多头净值（等权再平衡 = 日频加权近似）
    port_ret = (ret_l[picked] * w).sum(axis=1)
    port_nav = (1 + port_ret).cumprod()
    # 多头超额净值 = 组合 / 基准
    excess_nav = port_nav / bench.reindex(port_nav.index).ffill()

    rows = []
    for tag, mk in (("样本内", lambda idx: np.array([i < SPLIT for i in idx])),
                    ("样本外", lambda idx: np.array([i >= SPLIT for i in idx]))):
        rows.append((tag + " · ① 纯多头", perf(port_nav, mask=mk)))
        rows.append((tag + " · ③ 多头超额(=完美对冲β)", perf(excess_nav, mask=mk)))
        rows.append((tag + " · ③ + 贴水 − 期货成本", perf(excess_nav, a.basis, a.cost, mask=mk)))

    # ② 多空（理论值，仅参考）
    if not nav_s.empty:
        ls_is = {}
        for c in nav_s.columns:
            st = perf(nav_s[c], mask=is_mask)
            if st:
                ls_is[c] = st["calmar"]
        ls_order = [k for k, _ in sorted(ls_is.items(), key=lambda x: -x[1])]
        ls_ret = nav_s.pct_change().dropna(how="all")
        ls_pick = greedy(ls_ret.loc[is_mask(ls_ret.index)], ls_order, a.thr)
        if ls_pick:
            wl = pd.Series(1.0 / len(ls_pick), index=ls_pick)
            ls_nav = (1 + (ls_ret[ls_pick] * wl).sum(axis=1)).cumprod()
            for tag, mk in (("样本内", lambda idx: np.array([i < SPLIT for i in idx])),
                            ("样本外", lambda idx: np.array([i >= SPLIT for i in idx]))):
                rows.append((tag + " · ② 多空（★拿不到）", perf(ls_nav, mask=mk)))

    print("  %-34s %8s %8s %8s %8s" % ("口径", "年化", "Calmar", "Sharpe", "最大回撤"))
    for label, st in rows:
        if not st:
            continue
        print("  %-34s %7.2f%% %8.3f %8.2f %7.2f%%"
              % (label, 100 * st["ann"], st["calmar"], st["sharpe"], 100 * st["mdd"]))

    print()
    print("读法：① 能买但回撤大；② 理论最好但**空头腿拿不到**；③ 才是能落地的中性方案")


if __name__ == "__main__":
    main()
