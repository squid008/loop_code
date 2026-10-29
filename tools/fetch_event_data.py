# -*- coding: utf-8 -*-
"""fetch_event_data.py — 拉「事件类」另类数据（限售解禁 / 股票回购）并落盘。

★ 为什么是这两个（2026-10-29，用户选 A 方案）：
  已验证失败：两融/龙虎榜/大宗 = **行为强度**，与量价同源 ⇒ 25 代 calmar2 最好 0.104 ✗
  拿不到：`report_rc`（券商预测）= **10 次/天** 的试用配额 ⇒ 1 年要 5 天，不可行 ✗
  这两个是 **事件数据**（供给冲击 / 管理层信号），与价格**低相关**，正是 `strip_calmar` 需要的：
    · `share_float`（限售解禁）：学术上解禁前后有负超额
    · `repurchase`（股票回购）：回购公告后有正超额
  ⚠ 且这两个接口**没有配额限制**（实测连调两次都 OK）⇒ 全历史几十分钟拉完 ✓

★ 数据特点（实测 2026-10-29）：
  · `share_float` 单日可达 **6000 行**（每个股东一行，"李磊/贺国旺…"），且区间查询按 **`float_date`** 筛
    ⇒ 存盘前先 `groupby(ts_code, float_date).sum()` 汇总成"该股该解禁日的总解禁比例"
    ⇒ 区间窗口用**半月**（超 6000 会自动降级到按周重拉该窗口）
  · `repurchase` 单日约 28 行，按 `ann_date` 区间查 ⇒ 按年切即可

用法：
    python tools/fetch_event_data.py                    # 拉全历史
    python tools/fetch_event_data.py --start=20180101   # 从某年起
    python tools/fetch_event_data.py --build-only
"""
import argparse
import glob
import io
import json
import os
import sys
import time

import pandas as pd

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = r"E:\quant\loop_code"
CFG = os.path.join(ROOT, "config.local.json")
DATA = os.path.join(ROOT, "data")
PARTS = os.path.join(DATA, "event_parts")
OUT_FLOAT = os.path.join(DATA, "event_share_float.parquet")
OUT_BUY = os.path.join(DATA, "event_repurchase.parquet")

CAP = 6000            # 单次返回上限（撞到就说明被截断）
PAUSE = 1.5           # 这两个接口没有配额，稍作停顿即可


def _pro():
    cfg = json.load(io.open(CFG, encoding="utf-8"))
    tk = (cfg.get("sources") or {}).get("tushare", {}).get("token")
    if not tk:
        raise SystemExit("config.local.json 里没有 sources.tushare.token")
    import tushare as ts
    return ts.pro_api(tk)


def _p(prefix, s, e):
    return os.path.join(PARTS, "%s_%s_%s.parquet" % (prefix, s, e))


def _have(prefix, s, e):
    return os.path.isfile(_p(prefix, s, e))


def _save(prefix, s, e, df):
    os.makedirs(PARTS, exist_ok=True)
    tmp = _p(prefix, s, e) + ".tmp"
    df.to_parquet(tmp, index=False)
    os.replace(tmp, _p(prefix, s, e))


def _half_months(start, end):
    """按**半月**切（1-15 / 16-月末）；`share_float` 一个季度就撞 6000 上限。"""
    import calendar
    y0, m0 = int(start[:4]), int(start[4:6])
    y1, m1 = int(end[:4]), int(end[4:6])
    out, y, m = [], y0, m0
    while (y, m) <= (y1, m1):
        last = calendar.monthrange(y, m)[1]
        for a, b in ((1, 15), (16, last)):
            s = "%04d%02d%02d" % (y, m, a)
            e = "%04d%02d%02d" % (y, m, b)
            if e >= start and s <= end:
                out.append((max(s, start), min(e, end)))
        m += 1
        if m > 12:
            y, m = y + 1, 1
    return out


def _half_month(start, end):
    """把一个窗口再对半切（降级用）。"""
    from datetime import datetime, timedelta
    s0 = datetime.strptime(start, "%Y%m%d")
    e0 = datetime.strptime(end, "%Y%m%d")
    mid = s0 + (e0 - s0) // 2
    return ((start, mid.strftime("%Y%m%d")),
            ((mid + timedelta(days=1)).strftime("%Y%m%d"), end))


def fetch_share_float(pro, start, end):
    wins = _half_months(start, end)
    todo = [(s, e) for s, e in wins if not _have("float", s, e)]
    print("[share_float] 窗口 %d，待拉 %d（无配额限制）" % (len(wins), len(todo)), flush=True)
    for i, (s, e) in enumerate(todo, 1):
        try:
            df = pro.share_float(start_date=s, end_date=e)
        except Exception as exc:                          # noqa: BLE001
            print("  [%d/%d] %s~%s FAIL %s" % (i, len(todo), s, e, str(exc)[:60]), flush=True)
            time.sleep(PAUSE)
            continue
        if df is None or not len(df):
            _save("float", s, e, pd.DataFrame(columns=["ts_code", "float_date", "float_ratio"]))
            continue
        if len(df) >= CAP:
            # 撞上限 ⇒ 数据不完整 ⇒ 对半切重拉
            print("  [%d/%d] %s~%s 行数 %d 撞上限 ⇒ 改按周切"
                  % (i, len(todo), s, e, len(df)), flush=True)
            for (s2, e2) in _half_month(s, e):
                try:
                    d2 = pro.share_float(start_date=s2, end_date=e2)
                    if d2 is not None and len(d2):
                        _agg_save_float(s2, e2, d2)
                    time.sleep(PAUSE)
                except Exception as exc:                  # noqa: BLE001
                    print("    %s~%s FAIL %s" % (s2, e2, str(exc)[:50]), flush=True)
            continue
        _agg_save_float(s, e, df)
        print("  [%d/%d] %s~%s OK %d 行" % (i, len(todo), s, e, len(df)), flush=True)
        time.sleep(PAUSE)


def _agg_save_float(s, e, df):
    """同一 (股票, 解禁日) 的多个股东**汇总**成一行（`float_ratio` 求和）。"""
    d = df[["ts_code", "float_date", "float_ratio"]].copy()
    d["float_ratio"] = pd.to_numeric(d["float_ratio"], errors="coerce")
    g = d.groupby(["ts_code", "float_date"], as_index=False)["float_ratio"].sum()
    _save("float", s, e, g)


def fetch_repurchase(pro, start, end):
    y0, y1 = int(start[:4]), int(end[:4])
    for y in range(y0, y1 + 1):
        s, e = "%d0101" % y, "%d1231" % y
        if _have("buy", s, e):
            continue
        try:
            df = pro.repurchase(start_date=s, end_date=e)
        except Exception as exc:                          # noqa: BLE001
            print("  [repurchase] %d FAIL %s" % (y, str(exc)[:60]), flush=True)
            time.sleep(PAUSE)
            continue
        if df is None or not len(df):
            _save("buy", s, e, pd.DataFrame(columns=["ts_code", "ann_date", "amount", "vol"]))
            continue
        cols = [c for c in ("ts_code", "ann_date", "end_date", "proc", "exp_date",
                            "vol", "amount") if c in df.columns]
        _save("buy", s, e, df[cols].copy())
        print("  [repurchase] %d OK %d 行" % (y, len(df)), flush=True)
        time.sleep(PAUSE)


def build():
    for prefix, out in (("float", OUT_FLOAT), ("buy", OUT_BUY)):
        fs = sorted(glob.glob(os.path.join(PARTS, "%s_*.parquet" % prefix)))
        if not fs:
            print("  %s 无分片" % prefix)
            continue
        frames = []
        for f in fs:
            try:
                d = pd.read_parquet(f)
                if len(d):
                    frames.append(d)
            except Exception:                             # noqa: BLE001
                pass
        if not frames:
            continue
        all_df = pd.concat(frames, ignore_index=True).drop_duplicates()
        all_df.to_parquet(out, index=False)
        key = "float_date" if prefix == "float" else "ann_date"
        print("  %s: %d 行 -> %s（%s %s~%s）"
              % (prefix, len(all_df), out,
                 key, all_df[key].min() if key in all_df else "?", all_df[key].max() if key in all_df else "?"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="20130104")
    ap.add_argument("--end", default="20260819")
    ap.add_argument("--build-only", action="store_true")
    a = ap.parse_args()
    if not a.build_only:
        pro = _pro()
        fetch_share_float(pro, a.start, a.end)
        fetch_repurchase(pro, a.start, a.end)
    print()
    print("合并：")
    build()


if __name__ == "__main__":
    main()
