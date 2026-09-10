# -*- coding: utf-8 -*-
"""
audit_f11.py —— 复现 F11 引擎评测 + BUG①(涨停买入剔除不一致)/②(卖出顺延)敏感性
只读验证: 不修改 factor_miner / loop_engine 任何代码。
用法: cd D:\\loop_code\\engine && D:\\miniconda3\\envs\\rqdata\\python.exe audit_f11.py
"""
import os
import sys

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import factor_miner as fm

COST = 0.004  # 用户档(单边千1.5)

# ---------------- 构建 F11 ----------------
P = fm.load_panel()
P = fm.prepare(P)
cl = P["close"].astype("float64")
o, h, l = P["open"].astype("float64"), P["high"].astype("float64"), P["low"].astype("float64")
lo = l.where(l > 1e-9)
intraday = cl / o - 1.0
hl_ratio = h / lo
fac = (hl_ratio / l) * intraday * intraday * P["ret"]
fac = fm.ts_mean(fac, 60)          # rolling(60, min_periods=30).mean()
print("fac 覆盖 %.1f%%" % (100 * float(np.isfinite(fac.values).mean())))

# ---------------- 变体对照 ----------------
def audit(fac, close, mode):
    """mode: 'orig' / 'nodelay' / 'noban' / 'both' """
    TR = fm.get_tradability()
    idx = close.index[close.index >= fm.START]
    fac = fac.reindex(index=idx, columns=close.columns)
    col_of = {c: j for j, c in enumerate(close.columns)}
    dates_all = close.index.values
    pos_of = {d: i for i, d in enumerate(dates_all)}
    cv = TR["close"]
    U = fm.get_universe().reindex(index=idx, columns=close.columns).fillna(False)
    buyable = TR["buyable"]
    next_sell = TR["next_sell"]
    fwd_ret = (close.shift(-(1 + fm.FWD)) / close.shift(-1) - 1).reindex(index=idx)
    ar = np.arange(len(close.columns))
    ics, top_r, mkt_r, turns = [], [], [], []
    prev_top = None
    for d in idx[::fm.FWD][:-1]:
        u = U.loc[d]
        f = fac.loc[d][u].dropna()
        if len(f) < fm.N_GRP * 10:
            continue
        nxt = idx[idx > d]
        if len(nxt) <= fm.FWD:
            continue
        d1, d2 = nxt[0], nxt[fm.FWD]
        i1, i2 = pos_of[d1], pos_of[d2]
        # IC (原始口径, 与引擎一致)
        uu, ff, rr = u.values, fac.loc[d].values, fwd_ret.loc[d].values
        m = np.isfinite(ff) & np.isfinite(rr) & uu
        if m.sum() >= 50:
            ics.append(spearmanr(ff[m], rr[m])[0])
        grp = pd.qcut(f.rank(method="first"), fm.N_GRP, labels=False)
        top = list(f.index[grp == fm.N_GRP - 1])
        j_top = np.array([col_of[s] for s in top])
        j_all = np.array([col_of[s] for s in f.index])
        ok_buy = buyable[i1]
        if mode in ("orig", "nodelay"):
            keep_top = j_top[ok_buy[j_top]]
            keep_all = j_all[ok_buy[j_all]]
        else:  # noban/both: 不剔涨停, 都能买
            keep_top = j_top
            keep_all = j_all
        if len(keep_top) < 10 or len(keep_all) < fm.N_GRP * 5:
            continue
        if mode in ("orig", "noban"):
            si = next_sell[i2]
        else:  # nodelay/both: 固定 FWD 日收盘卖出(账面)
            si = np.full(len(ar), i2, dtype=np.int32)
        sell_px = cv[si, ar]
        r_all = sell_px / cv[i1] - 1.0
        rt = np.nanmean(r_all[keep_top])
        rm = np.nanmean(r_all[keep_all])
        if not (np.isfinite(rt) and np.isfinite(rm)):
            continue
        keep = (len(set(top) & prev_top) / max(len(prev_top), 1)) if prev_top else 0.0
        turn = 1.0 - keep
        top_r.append(rt - turn * COST)
        mkt_r.append(rm)
        turns.append(turn)
        prev_top = set(top)
    if len(top_r) < 30:
        return None
    tr, mr = pd.Series(top_r, index=idx[::fm.FWD][:len(top_r)]), pd.Series(mkt_r, index=idx[::fm.FWD][:len(top_r)])
    ex = tr - mr
    nav_e = (1 + ex).cumprod()
    yrs = len(tr) * fm.FWD / 243
    ann_e = nav_e.iloc[-1] ** (1 / yrs) - 1
    dd_e = (nav_e / nav_e.cummax() - 1).min()
    out = {
        "ic": float(np.mean(ics)), "ann_ex": ann_e, "dd": dd_e,
        "calmar": ann_e / abs(dd_e), "sharpe": float(ex.mean() / ex.std() * np.sqrt(243 / fm.FWD)),
        "turn": float(np.mean(turns)), "n": len(tr), "top_ann": float((1 + tr).cumprod().iloc[-1] ** (1 / yrs) - 1),
        "mkt_ann": float((1 + mr).cumprod().iloc[-1] ** (1 / yrs) - 1),
    }
    yr = {}
    for y, g in ex.groupby(tr.index // 10000):
        yr[int(y)] = float((1 + g).prod() - 1)
    out["yr"] = yr
    return out


def show(tag, r):
    if r is None:
        print("%-14s N/A" % tag)
        return
    y = r["yr"]
    neg = sum(1 for v in y.values() if v < 0)
    print("%-14s IC=%.4f 超额年化=%+6.2f%% 回撤=%6.2f%% Calmar=%.3f Sharpe=%.3f "
          "换手=%.1f%% 负年=%d 最近年=%+5.2f%% (top年化%+.2f/池年化%+.2f, n=%d)"
          % (tag, r["ic"], r["ann_ex"] * 100, r["dd"] * 100, r["calmar"], r["sharpe"],
             r["turn"] * 100, neg, y[max(y)] * 100, r["top_ann"] * 100,
             r["mkt_ann"] * 100, r["n"]))


def load_member(path, dates, cols):
    """成分历史 -> (日期x股票 bool)。成分 obid 格式 '600519.XSHG'，panel 列同格式则直接用。"""
    m = np.zeros((len(dates), len(cols)), dtype=bool)
    cset = set(cols)
    items = []
    with h5py.File(path, "r") as f:
        cd = [x.decode() if isinstance(x, bytes) else str(x)
              for x in f["change_dates"][:]]
        for d in cd:
            mem = set(x.decode() if isinstance(x, bytes) else str(x)
                      for x in f["components"][d][:])
            items.append((int(d.replace("-", "")), mem & cset))
    items.sort()
    cur = np.zeros(len(cols), dtype=bool)
    c2j = {c: i for i, c in enumerate(cols)}
    idx = 0
    for t, d in enumerate(dates):
        while idx < len(items) and items[idx][0] <= d:
            cur[:] = False
            for c in items[idx][1]:
                j = c2j.get(c)
                if j is not None:
                    cur[j] = True
            idx += 1
        m[t] = cur
    return m

def audit_idx(fac, close, member, tag, pct=None, nfix=None):
    """成分内 F11(-fac) 选股(比例或固定只数), 周频; member 已按 close.index 对齐。"""
    TR = fm.get_tradability()
    idx = close.index[close.index >= fm.START]
    gi = np.searchsorted(close.index.values, idx)
    mm = member[gi]
    fac = fac.reindex(index=idx, columns=close.columns)
    col_of = {c: j for j, c in enumerate(close.columns)}
    pos_of = {d: i for i, d in enumerate(close.index.values)}
    cv = TR["close"]
    buyable, next_sell = TR["buyable"], TR["next_sell"]
    ar = np.arange(len(close.columns))
    top_r, mkt_r, turns = [], [], []
    prev = None
    for t in range(0, len(idx) - fm.FWD, fm.FWD):
        d = idx[t]
        mi = mm[t]
        if mi.sum() < 20:
            continue
        f = fac.loc[d].values
        u = mi & np.isfinite(f)
        if u.sum() < 20:
            continue
        d1, d2 = idx[t + 1], idx[t + fm.FWD]
        i1, i2 = pos_of[d1], pos_of[d2]
        js = np.flatnonzero(u)
        fv = f[js]
        k = nfix or max(5, int(len(js) * (pct or 0.10)))
        sel = js[np.argsort(-fv)[:k]]
        keep = sel[buyable[i1, sel]]
        if len(keep) < 5:
            continue
        si = next_sell[i2]
        r_all = cv[si, ar] / cv[i1] - 1.0
        rt = np.nanmean(r_all[keep])
        rm = np.nanmean(r_all[js])
        if not (np.isfinite(rt) and np.isfinite(rm)):
            continue
        prev_s = set(keep)
        turn = 1.0 - (len(prev_s & prev) / max(len(prev), 1)) if prev is not None else 1.0
        top_r.append(rt - turn * COST)
        mkt_r.append(rm)
        turns.append(turn)
        prev = prev_s
    tr = pd.Series(top_r)
    mr = pd.Series(mkt_r)
    ex = tr - mr
    ne = (1 + ex).cumprod()
    yrs = len(tr) * fm.FWD / 243
    ann_e = ne.iloc[-1] ** (1 / yrs) - 1
    dd = (ne / ne.cummax() - 1).min()
    print("%-16s 超额年化=%+6.2f%% 回撤=%6.2f%% Calmar=%.3f 换手=%.1f%% n=%d"
          % (tag, ann_e * 100, dd * 100, ann_e / abs(dd), float(np.mean(turns)) * 100,
             len(tr)))


import h5py
print("\n===== F11(-取反) 全市场 vs 成分内增强(2018起, 费后) =====")
cl_i = cl.index.values
cases = (("沪深300内Top10%", r"E:\rq\constituents\index\000300.XSHG.h5", 0.10, None),
         ("中证500内Top10%", r"E:\rq\constituents\index\000905.XSHG.h5", 0.10, None),
         ("沪深300内Top30只", r"E:\rq\constituents\index\000300.XSHG.h5", None, 30),
         ("中证500内Top50只", r"E:\rq\constituents\index\000905.XSHG.h5", None, 50))
for nm, path, pct, nfix in cases:
    mem = load_member(path, cl_i, list(cl.columns))
    print("\n--", nm)
    audit_idx(-fac, cl, mem, nm, pct=pct, nfix=nfix)

print("\n===== F11 复现与 BUG 敏感性 =====")
for tag, mode, f in (("原样(复现)", "orig", fac),
                     ("取反(-fac)", "orig", -fac),
                     ("卖不延时不剔涨", "nodelay", -fac),
                     ("买不剔涨停", "noban", -fac),
                     ("两者都改", "both", -fac)):
    r = audit(f, cl, mode)
    show(tag, r)
    if tag == "取反(-fac)":
        show("参考(引擎F11)", dict(ic=0.0588, ann_ex=0.064, dd=-0.121, calmar=0.528,
                                   sharpe=0.790, turn=0.249, yr={0: 0, 1: 1, 2: -0.03},
                                   top_ann=0, mkt_ann=0, n=0))
