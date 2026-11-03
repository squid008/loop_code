# -*- coding: utf-8 -*-
"""multi_factor_stock.py — 真正的**多因子选股**（不是"买几个因子组合"）。

★ 为什么换做法（2026-11-03，用户指出）：
  上一版是「8 个因子的**多头净值**等权」⇒ 但 53 个多头净值相关性 0.972（都是同一个 β）
  ⇒ 等权只是平均同一个东西，**没有分散** ⇒ 回撤降不下来（-19.5%）✗
  真正的多因子选股是：把多个因子的**横截面分数合成一个综合分**，再选 top 10%
  ⇒ 每只股票同时满足多个条件 ⇒ 才是有效分散 ✓

★ 口径：
  1. 每个因子先做**逐日横截面 rank 百分位**（-0.5 ~ +0.5，天然抗极值、抗量纲）
  2. 等权累加 → 综合分
  3. 每 5 个交易日调仓，买综合分 top 10% 等权
  4. 往返成本 0.004，按实际换手扣
  5. 输出：纯多头（含 β）+ 相对全市场等权的**超额**（= 完美对冲 β 的上限）

⚠ 这一步**不涉及期货**：先看选股本身有没有超额。
  如果超额都不到 5%/年，后面接期货也没意义（这正是用户担心的地方）。

用法：
    python tools/multi_factor_stock.py
    python tools/multi_factor_stock.py --top=0.1 --freq=5 --split=20230101
"""
import argparse
import glob
import io
import os
import sys

import numpy as np
import pandas as pd

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = r"E:\quant\loop_code"
FACS = os.path.join(ROOT, "facs")
PANEL = os.path.join(ROOT, "engine", "panel.h5")
METRICS = os.path.join(ROOT, "docs", "factor_metrics.csv")
LS = os.path.join(ROOT, "data", "ls_curves")


def find_path(name):
    for b in sorted(os.listdir(FACS)):
        p = os.path.join(FACS, b, name, "values.h5")
        if os.path.isfile(p):
            return p
    return None


def read_vals(name):
    import h5py
    p = find_path(name)
    if not p:
        return None
    with h5py.File(p, "r") as f:
        return f["data"][:]


def load_axis():
    with pd.HDFStore(PANEL, "r") as st:
        close = st["close"]
    return close.index.to_numpy(), close.columns.to_numpy(), close.to_numpy(dtype="float32")


def cross_rank(mat):
    """逐行（每日）横截面 rank 百分位，返回 -0.5~+0.5；NaN 保持 NaN。"""
    T, S = mat.shape
    out = np.full((T, S), np.nan, dtype="float32")
    idx = np.arange(S)
    for t in range(T):
        v = mat[t]
        ok = np.isfinite(v)
        n = int(ok.sum())
        if n < 100:
            continue
        o = np.argsort(v[ok])
        r = np.empty(n, dtype="float32")
        r[o] = idx[:n]
        out[t, ok] = r / max(n - 1, 1) - 0.5
    return out


def pick_factors(thr=0.45, cap=15):
    """按样本内 IC 排序 + 多空相关性筛选（用 ls_curves 的相关矩阵，避免同时用未来信息）。"""
    metrics = pd.read_csv(METRICS, encoding="utf-8-sig").drop_duplicates(subset=["name"])
    ls = {}
    for f in sorted(glob.glob(os.path.join(LS, "F[0-9][0-9].json"))):
        try:
            s = pd.read_json(f, typ="series")
        except Exception:                                  # noqa: BLE001
            continue
        s.index = [int(x) for x in s.index]
        ls[os.path.basename(f)[:-5]] = s
    if not ls:
        return [], metrics
    ret = pd.DataFrame(ls).sort_index().ffill().pct_change().dropna(how="all")
    corr = ret.corr()
    m = metrics.set_index("name")
    order = [n for n in m[m.index.isin(corr.columns)].sort_values("ic", ascending=False).index]
    picked = []
    for nm in order:
        if not picked or corr.loc[nm, picked].abs().max() < thr:
            picked.append(nm)
        if len(picked) >= cap:
            break
    return picked, metrics


def backtest(comp, dates, cols, close, freq=5, top=0.1, cost=0.004):
    """按综合分选 top 组等权持有，每 freq 日调仓。返回 (日收益, 调仓次数, 换手列表)。"""
    T, S = comp.shape
    ret = np.zeros(T, dtype="float64")
    prev = None
    reb = list(range(0, T - freq, freq))
    n_tr = 0
    tos = []
    for t in reb:
        v = comp[t]
        px0, px1 = close[t], close[min(t + freq, T - 1)]
        ok = np.isfinite(v) & np.isfinite(px0) & np.isfinite(px1) & (px0 > 0)
        if ok.sum() < 200:
            continue
        n = max(int(ok.sum() * top), 30)
        idx = np.where(ok)[0]
        sel = idx[np.argsort(v[idx])[-n:]]
        fwd = px1[sel] / px0[sel] - 1.0
        # 截断极端值（个别股票 5 日翻倍/腰斩会把等权均值带飞）
        gross = float(np.nanmean(np.clip(fwd, -0.4, 0.4)))
        to = 0.0
        if prev is not None:
            to = len(set(sel.tolist()) ^ set(prev.tolist())) / (2.0 * n)
            tos.append(to)
        prev = sel
        seg = (gross - to * cost) / freq
        ret[t + 1:min(t + freq + 1, T)] = seg
        n_tr += 1
    return pd.Series(ret, index=dates), n_tr, tos


def perf(nav):
    s = pd.Series(nav).dropna()
    if len(s) < 100:
        return None
    r = s.pct_change().dropna()
    yrs = len(r) / 244.0
    ann = float(s.iloc[-1] ** (1 / yrs) - 1)
    dd = float((s / s.cummax() - 1).min())
    sharpe = float(r.mean() / (r.std() + 1e-12) * np.sqrt(244))
    return dict(ann=ann, calmar=ann / abs(dd) if dd < 0 else np.nan,
                sharpe=sharpe, mdd=dd, n=len(r))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=float, default=0.1)
    ap.add_argument("--freq", type=int, default=5)
    ap.add_argument("--split", type=int, default=20230101)
    ap.add_argument("--thr", type=float, default=0.45)
    # ★ 2013-2015 因子值全 NaN（库里因子的回测起点是 2018，values 从 2016 才逐日补齐）
    #   ⇒ 那几年组合根本没交易、收益恒为 0，却要拿去和基准比 ⇒ 超额被算成 -32%~-75% ✗
    ap.add_argument("--start", type=int, default=20160101, help="跳过因子值缺失的早期年份")
    a = ap.parse_args()

    picked, metrics = pick_factors(a.thr)
    if not picked:
        raise SystemExit("没选出因子")
    print("按 IC 排序 + 多空相关性 <%.2f 选出 %d 个：%s"
          % (a.thr, len(picked), ", ".join(picked)))

    dates, cols, close = load_axis()
    print("面板 %d 日 × %d 股（%d ~ %d）" % (len(dates), len(cols), dates[0], dates[-1]))

    print("\n合成中（逐因子：读 values.h5 → 逐日横截面 rank → 累加）...")
    comp = np.zeros((len(dates), len(cols)), dtype="float32")
    used = 0
    for nm in picked:
        v = read_vals(nm)
        if v is None or v.shape != comp.shape:
            print("  %-5s 跳过（形状 %s）" % (nm, None if v is None else v.shape))
            continue
        comp += cross_rank(v)
        used += 1
        print("  %-5s ✓（累计 %d 个）" % (nm, used), flush=True)
    if not used:
        raise SystemExit("没有可用因子")
    comp /= used
    print("综合分完成（%d 个因子等权）" % used)

    r, n_tr, tos = backtest(comp, dates, cols, close, a.freq, a.top, 0.004)
    nav = (1 + r).cumprod()

    # ★★ 基准改用**真实指数**（2026-11-03）：
    #   之前两次都错在这一步 ——
    #   ① 全市场 close 等权：2013-2014 大量未上市，`nanmean` 成分天天变 ⇒ 基准失真 ✗
    #   ② 因子 nav_t 等权：index 一个是 np.int64 一个是 python int，
    #      `intersection` 得空集 ⇒ 超额整段退化成净值（打印出来和纯多头一模一样）✗
    #   ⇒ 直接读 `data/idx_csi500.parquet` / `idx_csi1000.parquet`（tushare `index_daily` 拉的）✓
    #   ⚠ 策略买的是 top 10%（约 538 只，偏中小盘）⇒ **csi1000 更接近它的 β**
    def _idx_nav(nm):
        p = os.path.join(ROOT, "data", "idx_%s.parquet" % nm)
        if not os.path.isfile(p):
            return None
        d = pd.read_parquet(p)
        s = pd.Series(d["close"].values,
                      index=pd.Index(d["trade_date"].astype("int64").values))
        return s.sort_index()

    bench_nav = _idx_nav("csi1000")
    excess = nav
    excess500 = None
    if bench_nav is not None:
        nav2 = pd.Series(nav.values, index=pd.Index(np.asarray(nav.index).astype("int64")))
        ben2 = pd.Series(bench_nav.values, index=pd.Index(
            np.asarray(bench_nav.index).astype("int64")))
        common = nav2.index.intersection(ben2.index)
        if len(common) >= 200:
            excess = nav2.loc[common] / ben2.loc[common]
            excess = excess / excess.iloc[0]
            b5 = _idx_nav("csi500")
            if b5 is not None:
                b5 = pd.Series(b5.values, index=pd.Index(np.asarray(b5.index).astype("int64")))
                c5 = nav2.index.intersection(b5.index)
                if len(c5) >= 200:
                    excess500 = nav2.loc[c5] / b5.loc[c5]
                    excess500 = excess500 / excess500.iloc[0]
        else:
            print("  ⚠ 指数与净值无公共区间（%d / %d）⇒ 超额按净值代替"
                  % (len(ben2), len(nav2)))
    else:
        print("  ⚠ 没找到 data/idx_csi1000.parquet ⇒ 请先拉指数")

    print("\n调仓 %d 次，每次持 %d 只（top %.0f%%）"
          % (n_tr, int(len(cols) * a.top), 100 * a.top))
    if tos:
        print("换手率：中位 %.1f%%（每期），年化成本 ≈ %.1f%%"
              % (100 * np.median(tos), 100 * np.median(tos) * 0.004 * 244 / a.freq))
    print()
    print("  %-28s %8s %8s %8s %8s" % ("口径", "年化", "Calmar", "Sharpe", "最大回撤"))
    for tag, mask in (("样本内", lambda i: np.array([(x >= a.start) and (x < a.split) for x in i])),
                      ("样本外", lambda i: np.array([x >= a.split for x in i]))):
        for nm, series in (("纯多头(含β)", nav), ("超额(vs中证1000)", excess)):
            s = series[mask(series.index)]
            if len(s) < 100:
                print("  %-28s 样本不足（%d 天）" % (tag + " · " + nm, len(s)))
                continue
            st = perf(s / s.iloc[0])
            if st:
                print("  %-28s %7.2f%% %8.3f %8.2f %7.2f%%"
                      % (tag + " · " + nm, 100 * st["ann"], st["calmar"],
                         st["sharpe"], 100 * st["mdd"]))
        if excess500 is not None:
            s = excess500[mask(excess500.index)]
            if len(s) >= 100:
                st = perf(s / s.iloc[0])
                if st:
                    print("  %-28s %7.2f%% %8.3f %8.2f %7.2f%%"
                          % (tag + " · 超额(vs中证500)", 100 * st["ann"], st["calmar"],
                             st["sharpe"], 100 * st["mdd"]))

    # ---- 按年分解（解释样本内/外反差）----
    print()
    print("  按年收益（纯多头）:")
    idx = pd.to_datetime(pd.Index(nav.index).astype(str), format="%Y%m%d", errors="coerce")
    yrs = pd.Series(nav.values, index=idx).groupby(lambda i: i.year).apply(
        lambda x: x.iloc[-1] / x.iloc[0] - 1)
    mkt_y = pd.Series(bench_nav.values, index=pd.to_datetime(
        pd.Index(bench_nav.index).astype(str), format="%Y%m%d", errors="coerce")
    ).groupby(lambda i: i.year).apply(lambda x: x.iloc[-1] / x.iloc[0] - 1)
    for y in yrs.index:
        if y < a.start // 10000:
            continue          # 因子值缺失的早期年份不展示（组合恒 0，超额是假的）
        ex = (yrs[y] - mkt_y.get(y, np.nan)) if y in mkt_y.index else np.nan
        print("    %d  组合 %+7.2f%%   中证1000 %+7.2f%%   超额 %+7.2f%%"
              % (y, 100 * yrs[y], 100 * mkt_y.get(y, np.nan), 100 * ex))

    print()
    print("判据：样本外「超额」年化 > 5% 才值得接期货对冲；否则这条路没意义")


if __name__ == "__main__":
    main()
