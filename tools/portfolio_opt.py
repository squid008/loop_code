# -*- coding: utf-8 -*-
"""portfolio_opt.py — 因子库的相关性筛选 + 组合优化（2026-10-29，用户选 C 方案）。

★ 为什么做这个（背景）：
  挖掘侧已经 112 代只出 4 个因子（gen165 后），最近 90 代 **0 入库**；
  三次换信号源（两融/龙虎榜/大宗 → 券商预测 → 解禁/回购）全部证伪或数据不足。
  而库里**已有 53 个因子从没组合过** —— 与其继续挖，不如先把已有的用起来。

★ 数据（都已存在，不需要重算）：
  · `docs/factor_curves/Fxx.json` —— 每因子的**净值曲线**
    `nav_t` = **含成本**日频净值（首日 1 - 0.004）、`nav_m` = 不含成本、`d_dates` 日频日期
  · `docs/factor_metrics.csv` —— 每因子指标（ic / calmar / sharpe / turn / neg_yr …）

★ 做法：
  ① 对齐所有因子的公共日频净值 → 日收益矩阵
  ② 相关矩阵（日收益 Pearson）
  ③ **贪婪筛选**：按 Calmar 从高到低，只保留与已选因子相关性 < 阈值的
  ④ 三种加权：等权 / 逆波动率（风险平价近似）/ IC 加权
  ⑤ 回测组合：Calmar / Sharpe / 最大回撤 / 负年 / 年化

用法：
    python tools/portfolio_opt.py                  # 默认阈值 0.7
    python tools/portfolio_opt.py --corr 0.5       # 更严格
    python tools/portfolio_opt.py --pool=500       # 用某池的曲线
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
METRICS = os.path.join(ROOT, "docs", "factor_metrics.csv")


def load_curves(pool="all", ls=False):
    """读净值曲线。

    * `ls=False`：读 `docs/factor_curves/Fxx.json` 的 `nav_t` —— **纯多头**净值（含市场 β）
    * `ls=True` ：读 `data/ls_curves/Fxx.json` —— **多空**净值（`build_ls_curves.py` 重算，
                  top10% 多 − bottom10% 空，已扣成本）⇒ **纯 alpha**，组合优化该用它 ✓
    """
    if ls:
        pat = os.path.join(ROOT, "data", "ls_curves", "F[0-9][0-9].json")
        out = {}
        for f in sorted(glob.glob(pat)):
            try:
                s = pd.read_json(f, typ="series")
            except Exception:                              # noqa: BLE001
                continue
            s.index = [int(x) for x in s.index]
            out[os.path.basename(f)[:-5]] = pd.Series(s.values, index=s.index, dtype="float64")
        return out

    pat = os.path.join(CURVES, "F[0-9][0-9].json" if pool == "all"
                       else "F[0-9][0-9]_%s.json" % pool)
    out = {}
    for f in sorted(glob.glob(pat)):
        try:
            d = json.load(io.open(f, encoding="utf-8"))
        except Exception:                                  # noqa: BLE001
            continue
        nav = d.get("nav_t")
        dts = d.get("d_dates")
        if not nav or not dts or len(nav) != len(dts):
            continue
        out[d["name"]] = pd.Series(nav, index=[int(x) for x in dts], dtype="float64")
    return out


def to_returns(curves):
    """净值 → 日收益（原始 / 超额），并按日期对齐。

    ★★★ 2026-10-29 实测发现（这一步很关键）：
      53 个因子的**原始**日收益相关性中位 **0.972**、最大 0.999 ——
      因为它们都是**纯多组合**（多空对冲后的净值才叫因子收益，这里是多头组合净值）
      ⇒ 相关性几乎全来自**共同的市场 β**，不是因子本身同质 ✗
      ⇒ 算"谁和谁像"必须用**超额收益**（减去当日截面均值，近似中性化）✓
    回测仍用**原始收益**（组合要能真赚钱）；相关性/筛选才用超额。
    """
    nav = pd.DataFrame(curves).sort_index()
    nav = nav.loc[:, nav.notna().sum() > 100]          # 扔掉几乎全空的列
    nav = nav.ffill()
    ret = nav.pct_change().iloc[1:].dropna(how="all")
    ret_ex = ret.sub(ret.mean(axis=1), axis=0)         # 去市场 β
    return nav, ret, ret_ex


def perf(nav_like, label=""):
    """从净值序列算 Calmar / Sharpe / 回撤 / 年化 / 负年。

    ⚠ 传进来的必须是**带日期索引的 Series**（`nav_c`），不能是 `.values`
      —— 否则年度分组拿不到年份（2026-10-29 因此崩过一次）
    """
    s = pd.Series(nav_like).astype("float64").dropna()
    if len(s) < 60:
        return None
    r = s.pct_change().dropna()
    yrs = len(r) / 244.0
    ann = (s.iloc[-1] / s.iloc[0]) ** (1 / yrs) - 1 if yrs > 0 else np.nan
    dd = float((s / s.cummax() - 1).min())
    vol = float(r.std() * np.sqrt(244))
    sharpe = float(r.mean() / (r.std() + 1e-12) * np.sqrt(244))
    calmar = float(ann / abs(dd)) if dd < 0 else np.nan
    idx = pd.to_datetime(pd.Index(s.index[1:]).astype(str), format="%Y%m%d", errors="coerce")
    neg_yr = 0
    if idx.notna().any():
        yr = pd.Series(r.values, index=idx).groupby(lambda i: i.year).apply(
            lambda x: (1 + x).prod() - 1)
        neg_yr = int((yr < 0).sum())
    return dict(label=label, ann=ann, calmar=calmar, sharpe=sharpe, mdd=dd,
                vol=vol, neg_yr=neg_yr, years=yrs)


def greedy_pick(ret, metrics, thr=0.7):
    """按 Calmar 降序贪婪选「与已选相关性 < thr」的因子。"""
    order = metrics[metrics.name.isin(ret.columns)].sort_values("calmar", ascending=False)
    corr = ret.corr()
    picked = []
    for nm in order["name"].tolist():
        if not picked:
            picked.append(nm)
            continue
        c = corr.loc[nm, picked].abs().max()
        if c < thr:
            picked.append(nm)
    return picked, corr


def weights(kind, ret, cols, metrics):
    sub = ret[cols]
    if kind == "equal":
        w = pd.Series(1.0 / len(cols), index=cols)
    elif kind == "invvol":
        v = sub.std().replace(0, np.nan)
        w = (1 / v) / (1 / v).sum()
    elif kind == "ic":
        m = metrics.set_index("name").reindex(cols)["ic"].abs().fillna(0)
        w = m / m.sum() if m.sum() > 0 else pd.Series(1.0 / len(cols), index=cols)
    else:
        w = pd.Series(1.0 / len(cols), index=cols)
    return w


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corr", type=float, default=0.7, help="相关性上限（贪婪筛选）")
    ap.add_argument("--pool", default="all")
    ap.add_argument("--ls", action="store_true",
                    help="用 data/ls_curves 的**多空净值**（纯 alpha，做组合应该用这个）")
    a = ap.parse_args()

    print("=" * 82)
    print("【1】加载净值曲线（%s）" % ("多空 / 纯 alpha" if a.ls else "纯多头 / 含 β"))
    print("=" * 82)
    curves = load_curves(a.pool, ls=a.ls)
    if not curves:
        raise SystemExit("没找到曲线（docs/factor_curves/）")
    nav, ret, ret_ex = to_returns(curves)
    if a.ls:
        ret_ex = ret          # 多空净值本身就是 alpha ⇒ 不需要再去 β
    print("  因子 %d 个 · 公共日频 %d 天（%s ~ %s）"
          % (len(curves), len(ret), ret.index[0], ret.index[-1]))

    metrics = pd.read_csv(METRICS, encoding="utf-8-sig")
    if a.pool != "all" and "pool" in metrics.columns:
        metrics = metrics[metrics["pool"].astype(str) == a.pool]
    metrics = metrics.drop_duplicates(subset=["name"])

    print()
    print("=" * 82)
    print("【2】单因子 Top 10（按 Calmar）")
    print("=" * 82)
    top = metrics[metrics.name.isin(ret.columns)].sort_values("calmar", ascending=False).head(10)
    for _, r in top.iterrows():
        print("  %-5s Calmar %6.3f  Sharpe %5.2f  IC %+.4f  换手 %4.1f%%  负年 %d"
              % (r["name"], r["calmar"], r["sharpe"], r["ic"], 100 * r["turn"], r["neg_yr"]))

    print()
    print("=" * 82)
    print("【3】相关性筛选（阈值 |ρ| < %.2f）" % a.corr)
    print("=" * 82)
    picked, corr = greedy_pick(ret_ex, metrics, a.corr)   # 用**超额**算相关（去市场 β）
    print("  选出 %d / %d 个：%s" % (len(picked), len(ret.columns), ", ".join(picked)))

    tri = corr.where(np.triu(np.ones(corr.shape), 1).astype(bool)).stack()
    print("  全体相关性：中位 %.3f   P90 %.3f   最大 %.3f"
          % (tri.median(), tri.quantile(.9), tri.max()))
    if len(picked) > 1:
        sub = corr.loc[picked, picked]
        tri2 = sub.where(np.triu(np.ones(sub.shape), 1).astype(bool)).stack()
        print("  筛选后    ：中位 %.3f   P90 %.3f   最大 %.3f"
              % (tri2.median(), tri2.quantile(.9), tri2.max()))

    print()
    print("=" * 82)
    print("【4】组合回测")
    print("=" * 82)
    if a.ls:
        print("  口径：**多空净值**（top10% 多 − bottom10% 空，已扣成本）⇒ 本身就是 alpha，")
        print("        直接加权组合即可，不需要再除基准 ✓")
    else:
        print("  ⚠ 口径说明（踩过两次坑）：")
        print("    ① 直接用 `nav_t` ⇒ 被市场 β 主导（F40 算出来 Calmar 0.49，指标表是 1.35）✗")
        print("    ② 用「减截面均值」的日收益加权 ⇒ **等权组合恒为 0**（数学必然）✗")
        print("    ③ 正确做法：先算组合的**绝对净值**，再除以**全市场等权基准净值** ✓")
    rows = []

    bench = (1 + ret.mean(axis=1).fillna(0)).cumprod()      # 全市场等权基准

    def _excess_nav(cols, w):
        nv = (1 + (ret[cols] * w).sum(axis=1)).cumprod()
        if a.ls:
            return nv                                       # 多空净值已是 alpha
        return nv / bench.reindex(nv.index).ffill()

    all_cols = list(ret.columns)
    best = metrics[metrics.name.isin(ret.columns)].sort_values("calmar", ascending=False).iloc[0]
    bm = best["name"]
    st = perf(_excess_nav([bm], pd.Series([1.0], index=[bm])), "单因子 %s(超额)" % bm)
    if st:
        rows.append(st)

    for kind in ("equal", "invvol", "ic"):
        w = weights(kind, ret, all_cols, metrics)
        st = perf(_excess_nav(all_cols, w), "全库(%s)" % kind)
        if st:
            rows.append(st)

    for thr in (0.7, 0.5, 0.3):
        pk, _ = greedy_pick(ret_ex, metrics, thr)
        if len(pk) < 2:
            continue
        for kind in ("equal", "ic", "invvol"):
            w = weights(kind, ret, pk, metrics)
            st = perf(_excess_nav(pk, w), "ρ<%.1f %d个(%s)" % (thr, len(pk), kind))
            if st:
                rows.append(st)

    print()
    print("  %-24s %8s %8s %8s %8s %8s %6s" %
          ("组合（超额）", "年化", "Calmar", "Sharpe", "最大回撤", "波动", "负年"))
    for r in sorted(rows, key=lambda x: -x["calmar"]):
        print("  %-24s %7.2f%% %8.3f %8.2f %8.2f%% %7.2f%% %6d"
              % (r["label"], 100 * r["ann"], r["calmar"], r["sharpe"],
                 100 * r["mdd"], 100 * r["vol"], r["neg_yr"]))

    print()
    print("校验：单因子那条的 Calmar 应接近 factor_metrics.csv 里的值（同口径）；")
    print("判据：超额组合的 Calmar 高于最好的单因子，才算分散真的换来收益/回撤改善")


if __name__ == "__main__":
    main()
