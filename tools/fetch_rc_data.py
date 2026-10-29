# -*- coding: utf-8 -*-
"""fetch_rc_data.py — 拉 tushare `report_rc`（券商盈利预测）并落盘。

★ 为什么用这个数据（2026-10-29，用户批准）：
  之前试的替代数据（两融/龙虎榜/大宗）是**行为数据**，与量价高度同源 ⇒ 实测 25 代
  `calmar2` 最好只 0.104（门槛 0.701）✗
  而 `report_rc` 是**信息数据**（分析师预期/评级/目标价），与价格**低相关** —— 正是
  `strip_calmar`（剥掉 lncap+lnamt 后仍要有超额）需要的东西 ✓

★ 接口限制（实测，必须遵守）：
  · **1 次/分钟**（`抱歉，您访问接口(report_rc)频率超限(1次/分钟)`）
  · **单次 5000 行**（超了会被**静默截断**）
    ⚠ 2026-10-29 实测：**按月拉也会超**（2023-08 一次就撞到 5000）⇒ 必须**按旬**切
    （每月 1-10 / 11-20 / 21-月末 三段，每段约 2000~3000 行 ✓）

★ 落盘：按旬分片 `engine/rc_parts/rc_YYYYMMDD_YYYYMMDD.parquet`（原子写）
  ⇒ 断了只丢当前那一旬（和 `fetch_alt_data.py` 同款教训：那次"最后才写盘"白跑 66 分钟）
  ⚠ 用 **Parquet** 而不是 HDF5：`rating`/`quarter` 是 mixed object 列，
    PyTables 直接报 `map directly to c-types [inferred_type->mixed]` ✗（2026-10-29 实测）

用法：
    python tools/fetch_rc_data.py --start=20230801 --end=20260819     # 近 3 年
    python tools/fetch_rc_data.py --start=20170101                    # 从 17 年
    python tools/fetch_rc_data.py                                     # 全历史
    python tools/fetch_rc_data.py --build-only                        # 只合并分片
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
# ★ 2026-10-29（用户：数据不要放 engine 里，搞个 data 目录）
DATA = os.path.join(ROOT, "data")          # 所有「拉取类」数据统一放这里（与代码分离）
PARTS = os.path.join(DATA, "rc_parts")
OUT = os.path.join(DATA, "rc_data.parquet")

# 只留需要的列（原始明细，聚合阶段再算因子）
KEEP = ["ts_code", "name", "report_date", "quarter", "eps", "np", "pe", "roe",
        "rating", "max_price", "min_price", "tp", "org_name", "report_type"]
# ★ 2026-10-29 实测校准：`report_rc` 有**两层**配额
#   ① 1 次/分钟（瞬时）② **10 次/小时**（总量，更严）
#   ⇒ 间隔取 370 秒（6 分 10 秒）正好卡住 10 次/小时，留一点余量 ✓
#   ⚠ 一开始按 61 秒设，跑到第 3 个窗口就开始连续 FAIL（浪费配额还丢数据）
SLEEP = 370.0
RETRY = 3             # 每轮试 3 次（避开 1 次/分钟的瞬时限流）
MAX_WAIT = 4 * 3600   # 单个窗口最多等 4 小时（配额耗尽时；等不到就跳过，下次重跑补）


def _token():
    cfg = json.load(io.open(CFG, encoding="utf-8"))
    tk = (cfg.get("sources") or {}).get("tushare", {}).get("token")
    if not tk:
        raise SystemExit("config.local.json 里没有 sources.tushare.token")
    return tk


def _pro():
    import tushare as ts
    return ts.pro_api(_token())


def _part(s, e):
    return os.path.join(PARTS, "rc_%s_%s.parquet" % (s, e))


def _have(s, e):
    return os.path.isfile(_part(s, e))


def _save(s, e, df):
    """原子写：.tmp -> replace（中途被杀不会留下半个文件）。"""
    os.makedirs(PARTS, exist_ok=True)
    tmp = _part(s, e) + ".tmp"
    df.to_parquet(tmp, index=False)
    os.replace(tmp, _part(s, e))


def _windows(start, end):
    """按 **7 天滚动窗口**切（实测校准，2026-10-29）：

    | 窗口 | 行数 | 结果 |
    |---|---|---|
    | 1 个月 | ≥5000 | 被截断 ✗ |
    | 10 天（旬） | **5000** | 正好撞上限 ✗ |
    | **7 天** | ~3500 | 留 30% 余量 ✓ |

    每天约 500 行（研报很密）⇒ 7 天是「不撞上限」与「次数可控」的平衡点。
    """
    from datetime import datetime, timedelta
    s0 = datetime.strptime(start, "%Y%m%d")
    e0 = datetime.strptime(end, "%Y%m%d")
    out, cur = [], s0
    while cur <= e0:
        nxt = min(cur + timedelta(days=6), e0)
        out.append((cur.strftime("%Y%m%d"), nxt.strftime("%Y%m%d")))
        cur = nxt + timedelta(days=1)
    return out


def fetch(pro, windows, force=False):
    todo = [(s, e) for (s, e) in windows if force or not _have(s, e)]
    done = len(windows) - len(todo)
    print("旬窗口 %d 个，已有分片 %d，待拉 %d（每条约 %.0f 秒 ⇒ 约 %.0f 分钟）"
          % (len(windows), done, len(todo), SLEEP, len(todo) * SLEEP / 60), flush=True)
    if not todo:
        return

    for i, (s, e) in enumerate(todo, 1):
        t0 = time.time()
        f = _part(s, e)
        if os.path.isfile(f + ".tmp"):
            os.remove(f + ".tmp")
        df = None
        waited = 0
        # ★ 2026-10-29：**配额耗尽时要"等"，不能"跳过"**。
        #   原实现 3 次失败就 continue ⇒ 53 个窗口全部空转失败（实测第 1 个窗口连败 3 次，
        #   每个窗口还要空跑 18 分钟）✗
        #   现在：重试 RETRY 次仍失败 ⇒ 长等 30 分钟再试同一窗口（最多等 MAX_WAIT 小时）。
        while df is None:
            for attempt in range(1, RETRY + 1):
                try:
                    df = pro.report_rc(start_date=s, end_date=e)
                    break
                except Exception as exc:                  # noqa: BLE001
                    print("  [%d/%d] %s~%s FAIL(第%d次) %s"
                          % (i, len(todo), s, e, attempt, str(exc)[:60]), flush=True)
                    if attempt < RETRY:
                        time.sleep(SLEEP)
            if df is None:
                if waited >= MAX_WAIT:
                    print("  [配额] %s~%s 已等 %.1f 小时仍失败 ⇒ 跳过（下次重跑会补）"
                          % (s, e, waited / 3600), flush=True)
                    break
                print("  [配额] %s~%s 重试 %d 次失败 ⇒ 等 30 分钟再试（累计 %.1f 小时）"
                      % (s, e, RETRY, waited / 3600), flush=True)
                time.sleep(1800)
                waited += 1800
        if df is None:
            continue

        if df is None or not len(df):
            print("  [%d/%d] %s~%s 空（写空分片，避免反复重试）" % (i, len(todo), s, e),
                  flush=True)
            _save(s, e, pd.DataFrame(columns=KEEP))
            time.sleep(SLEEP)
            continue

        if len(df) >= 5000:
            # ⚠ 单次硬上限 5000 ⇒ 这一旬被截断，数据不完整，**不写分片**（下次再切细）
            print("  [%d/%d] %s~%s ★ 行数 %d >= 5000（被截断，跳过不写）"
                  % (i, len(todo), s, e, len(df)), flush=True)
            time.sleep(SLEEP)
            continue

        cols = [c for c in KEEP if c in df.columns]
        _save(s, e, df[cols].copy())
        print("  [%d/%d] %s~%s OK %d 行  %.0fs"
              % (i, len(todo), s, e, len(df), time.time() - t0), flush=True)
        time.sleep(SLEEP)


def build():
    """合并所有分片成一张明细表（按 report_date 排序），供聚合阶段用。"""
    fs = sorted(glob.glob(os.path.join(PARTS, "rc_*.parquet")))
    if not fs:
        print("没有分片可合并")
        return None
    frames = []
    for f in fs:
        try:
            d = pd.read_parquet(f)
            if len(d):
                frames.append(d)
        except Exception as e:                            # noqa: BLE001
            print("  分片读失败 %s: %s" % (os.path.basename(f), type(e).__name__))
    if not frames:
        print("所有分片都是空的")
        return None
    all_df = pd.concat(frames, ignore_index=True)
    all_df = all_df.drop_duplicates(subset=["ts_code", "report_date", "quarter", "org_name"])
    all_df = all_df.sort_values(["report_date", "ts_code"]).reset_index(drop=True)
    all_df.to_parquet(OUT, index=False)
    print("合并完成：%d 行 × %d 列 -> %s" % (len(all_df), len(all_df.columns), OUT))
    print("日期范围：%s ~ %s" % (all_df.report_date.min(), all_df.report_date.max()))
    print("覆盖股票数：%d" % all_df.ts_code.nunique())
    return all_df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="20130104")
    ap.add_argument("--end", default=None)
    ap.add_argument("--force", action="store_true", help="重拉已有分片")
    ap.add_argument("--build-only", action="store_true")
    a = ap.parse_args()

    if not a.build_only:
        pro = _pro()
        end = a.end or "20260819"
        fetch(pro, _windows(a.start, end), force=a.force)
    build()


if __name__ == "__main__":
    main()
