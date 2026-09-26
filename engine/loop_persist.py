# -*- coding: utf-8 -*-
"""loop_persist.py — 落盘/工具纯函数（2026-09-26 文件级拆分）

★ 只放**零依赖**的纯函数（不 import loop_engine，无循环依赖）。
  append_csv_schema_safe：CSV 加列时重写并救回旧行（§8.30 治本）
  _real_mb：估缓存值真实钉住的内存（含 numpy 视图底座）
"""
import io
import os
import sys
import csv

import numpy as np


def append_csv_schema_safe(path, df=None, new_cols=None):
    """**Schema-aware** 追加写 CSV；发现 schema 变化就重写整文件（旧行对齐到新 schema）。

    为什么必须这样（2026-09-13 实录, roadmap §8.30）：
      原先各处的写法是 `_need_h = 文件不存在或为空` + `to_csv(mode='a', header=_need_h)`，
      即**默认 schema 永远不变**。而 2026-09-13 我给 `--pool_obs` 加了 5 列
      （ann_ex_cw/calmar_cw/dd_cw/sharpe_cw/tilt）⇒ 文件变成「**表头 10 列 + 旧行 10 列 +
      新行 15 列**」⇒ `pd.read_csv` 直接报
        `ParserError: Expected 10 fields in line 222, saw 15`
      ⇒ **所有下游报告全崩**，而且崩在**离线脚本**里，引擎自己毫无察觉（静默数据损坏）。
      ★ 本项目其实早就知道这个坑（见 `STYLE_OBS`/`STRIP_OBS` 的注释「追加模式下加列会让历史行
        错位」），解法一直是"**另开一个文件**"。那次我改的正是**已有文件** ⇒ 违反了这条规则。
      ⇒ 根治：写入端**必须与当前 schema 对账**；不一致就重写（这些文件只有几百~几万行，成本可忽略）。
        并且**尽量救回已有数据** —— 混合宽度时按行宽判断该行属于旧头还是新 schema。

    df=None 时 = **只修复**（用 new_cols 对账现有文件）。
    返回 (状态字符串, 修复/写入的行数)。
    """
    import csv
    if new_cols is None:
        new_cols = list(df.columns) if df is not None else None
    if not new_cols:
        return ('skip: 无列信息', 0)

    if (not os.path.exists(path)) or os.path.getsize(path) == 0:
        if df is None:
            return ('absent', 0)
        df.to_csv(path, index=False, header=True, encoding='utf-8-sig')
        return ('created', len(df))

    with io.open(path, encoding='utf-8-sig', newline='') as fh:
        rr = [r for r in csv.reader(fh) if r]
    if not rr:
        if df is None:
            return ('empty', 0)
        df.to_csv(path, index=False, header=True, encoding='utf-8-sig')
        return ('created', len(df))
    hdr, body = rr[0], rr[1:]

    if hdr == list(new_cols):                       # schema 一致 -> 直接追加
        if df is None:
            return ('ok(无需修复)', 0)
        df.to_csv(path, index=False, mode='a', header=False, encoding='utf-8-sig')
        return ('appended', len(df))

    # ---- schema 变了(或文件已混合宽度) -> 重写 ----
    # 救数据: 行宽 == 旧表头列数 -> 按旧头对齐; 行宽 == 新 schema 列数 -> 按新 schema 对齐
    rows, dropped = [], 0
    for parts in body:
        if len(parts) == len(hdr):
            d = dict(zip(hdr, parts))
        elif len(parts) == len(new_cols):
            d = dict(zip(new_cols, parts))
        else:
            dropped += 1
            continue
        rows.append({c: d.get(c, '') for c in new_cols})
    old = pd.DataFrame(rows, columns=list(new_cols))
    out = pd.concat([old, df], ignore_index=True) if df is not None else old
    out.to_csv(path, index=False, header=True, encoding='utf-8-sig')
    msg = (f'rewritten(旧{len(old)}行{"+新" + str(len(df)) + "行" if df is not None else ""}'
           f'{"，丢弃" + str(dropped) + "行无法识别" if dropped else ""})')
    return (msg, len(out))


def _real_mb(obj, seen=None, depth=0):
    """估一个缓存值**真实钉住**的内存（MB）—— ★ 关键：把 numpy **视图的底座**算进来 ✗

    ★★★★★ 2026-09-21（治本第二刀 · 真事故驱动）：
      上一版 `trim_cache_mb` 只数 `getattr(v, 'nbytes')` ✗ —— 而 numpy **视图**的 `nbytes`
      是**视图自己**的大小，它却让**整个底座数组活着**（`arr.base` 不被释放 ✗）
      而引擎缓存里存的恰恰大量是"子面板的切片/移位视图" ✓
      （`eval_expr` 把**叶子字段**与 `[::FWD]` / `x[1:]` 一类结果**直接入缓存** ✓ 见 L1229-1239）
      ⇒ **账实不符**：账上 ≤ 2.5 GB，实测 `_LRU.clear()` 一执行就掉 **3.57 GB** ✗
        （gen36 实测：L1 阶段工作集 7.25 → 11.08 GB **单调爬升**，L1 一结束立刻回落 7.51 ✓
           —— 掉的那一块正好是 `_LRU.clear()`（L2589）执行的那一瞬 ✓ 这就是定位证据 ✓）
      ⇒ 结论：**"按字节裁"还不够，必须按"真实钉住的字节"裁** ✗✓

    做法（全部只读属性，不遍历数组 ⇒ 便宜 ✓）：
      ① ndarray：沿 `.base` 链走到**根**，按根的 `nbytes` 计 ✓
      ② 同一个根**只算一次**（`seen` 由调用方共用 ⇒ 多份视图共享的底座不重复计 ✓）
      ③ pandas ⇒ 走 `.values` ✓ ④ dict/list/tuple ⇒ 递归（限深 3）✓ ⑤ 其它 ⇒ `sys.getsizeof` ✓
    """
    if obj is None:
        return 0.0
    if seen is None:
        seen = set()
    try:
        if isinstance(obj, np.ndarray):
            root = obj
            for _ in range(8):                               # 限深，防异常链 ✓
                b = getattr(root, 'base', None)
                if isinstance(b, np.ndarray):
                    root = b
                else:
                    break
            k = id(root)
            if k in seen:
                return 0.0                                   # 同一底座只算一次 ✓
            seen.add(k)
            return float(getattr(root, 'nbytes', 0) or 0) / 1048576.0
        if depth >= 3:
            return 0.0
        if isinstance(obj, dict):
            return sum(_real_mb(v, seen, depth + 1) for v in obj.values())
        if isinstance(obj, (list, tuple, set)):
            return sum(_real_mb(v, seen, depth + 1) for v in obj)
        _vs = getattr(obj, 'values', None)                   # pandas Series/DataFrame ✓
        if _vs is not None and hasattr(_vs, 'nbytes'):
            return _real_mb(np.asarray(_vs), seen, depth + 1)
        return float(sys.getsizeof(obj)) / 1048576.0
    except Exception:                                        # noqa: BLE001
        return 0.0                                           # 估不出来也不能影响主流程 ✓
