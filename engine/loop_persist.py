# -*- coding: utf-8 -*-
"""loop_persist.py — 落盘 / 工具 / 库文档同步（2026-09-26 文件级拆分）

★ **不 import loop_engine** ⇒ 无循环依赖（只依赖 loop_expr/loop_gen/loop_faillib/loop_paths/cost_presets）。
  落盘：`append_csv_schema_safe`（CSV 加列重写并救回旧行 §8.30）· `_dump_strip_detail` ·
        `_dump_pool_obs` · `_save_state`（代末原子写）· `_StateUnpickler`（读旧 state 时把 `Node` 归一）
  库文档：`_mk_library_skeleton` · `_tag_desc` · `append_library_entries` · `_lib_sync`
  收益流：`_cmp_lib` · `ex_max_corr` · `_pool_best` · `combine_ok` · `_gate_of`
  工具：`_real_mb`（估缓存真实钉住的内存，含 numpy 视图底座）
"""
import csv
import io
import json
import os
import pickle
import re
import sys
import time

import numpy as np
import pandas as pd

from loop_expr import Node

import loop_paths as _P
from loop_faillib import flib_mark, fail_lib_cleanup
from loop_expr import skeleton, skeleton_freq
from loop_gen import DEFAULT_CFG
from cost_presets import cost_label


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


def _dump_strip_detail(_strip_style, strip_rows):
    """P0-2 纯提取自 `run()`（逐字搬运，语义不变）。

    原段落: 剥风格明细落盘(2026-09-12, --strip_style; 独立文件, 不进 archive 表头)
    """
    if _strip_style and strip_rows:
        try:
            _sd = pd.DataFrame(strip_rows)
            # ★ schema-aware 追加(2026-09-13, §8.30): 加列时会**重写并救回旧行**, 不再产生混合宽度
            _st, _sn = append_csv_schema_safe(_P.STRIP_OBS, _sd)
            _n_pos = int((_sd['strip_ann_ex'] > 0).sum())
            print(f"已存 {_P.STRIP_OBS} ({_st}, 本代 {len(_sd)} 条 L2 候选; "
                  f"剥风格后超额仍为正 {_n_pos}/{len(_sd)})")
        except Exception as e:
            print(f"  [剥风格] 落盘失败(不影响主流程): {type(e).__name__}: {e}")


def _dump_pool_obs(POOL_M, _pools, args, fail_lib, nd, pool_rows, rows, top):
    """P0-2 纯提取自 `run()`（逐字搬运，语义不变）。

    原段落: 池内指标落盘(2026-09-12, --pool_obs; **长表**, 独立文件)
    """
    if POOL_M and pool_rows:
        try:
            _pdd = pd.DataFrame(pool_rows)
            # ★ schema-aware 追加(2026-09-13, §8.30): 见 append_csv_schema_safe 的 docstring
            _pst, _psn = append_csv_schema_safe(_P.POOL_OBS, _pdd)
            if 'rewritten' in _pst:
                print(f"  [池指标] schema 变化 -> 已重写 {os.path.basename(_P.POOL_OBS)}: {_pst}")
            _n_cand = len(_pdd) // max(len(_pools), 1)
            _msg = ', '.join(
                f"{t}: 超额>0 {int((_pdd.loc[_pdd['pool'] == t, 'ann_ex'] > 0).sum())}"
                f"/{int((_pdd['pool'] == t).sum())}" for t in _pools)
            print(f"已存 {_P.POOL_OBS} (追加, 本代 {len(_pdd)} 行 = {_n_cand} 候选 x "
                  f"{len(_pools)} 池; 池内超额>0 -> {_msg})")
        except Exception as e:
            print(f"  [池指标] 落盘失败(不影响主流程): {type(e).__name__}: {e}")
    res = pd.DataFrame(rows)
    # 失败模式库: L2 费后结果落地成败(中金: 失败表达式写入失败库, 生成阶段排除)
    top_node = {str(r['node']): r['node'] for _, r in top.iterrows()}
    for _, r_ in res.iterrows():
        nd = top_node.get(r_['expr'])
        if nd is not None:
            flib_mark(fail_lib, nd, args.gen, bool(r_['passed']),
                      '' if r_['passed'] else 'l2')
    if len(res):
        # 逐代累积流水(带 gen/cat/leaf 列): 文件缺失/为空时写表头, 其后追加
        # —— 每代 L2 明细永久留档(gen16 前旧快照已归 history/loop_archive.legacy_pre_gen16.csv)
        res.insert(0, 'gen', args.gen)
        # ★ schema-aware 追加(2026-09-13, §8.44): 原先是"只判文件有无/为空"决定写不写表头,
        #   而 §8.34 给本表加了 `max_ex_corr`(第 17 列) ⇒ `loop_archive_300/500.csv` 变成
        #   「16列旧行 + 17列新行」混合宽度 ⇒ `pd.read_csv` 报
        #   `Expected 16 fields in line 165, saw 17`。**同一个坑的第三处**
        #   (前两处: loop_pool_obs_* / loop_strip_style_*, 见 `tools/fix_csv_schema.py`)。
        _ast, _asn = append_csv_schema_safe(_P.ARCHIVE, res)
        if 'rewritten' in _ast:
            print(f"  [流水] schema 变化 -> 已重写 {os.path.basename(_P.ARCHIVE)}: {_ast}")
        print(f"\n已存 {_P.ARCHIVE} ({_ast}, 本代 {len(res)} 条)")
        p = res[res['passed']]
        print(f"L2 通过 {len(p)}/{len(res)} 个")
        if len(p):
            print(p.round(4).to_string(index=False))
    return (nd, res)


def _cmp_lib(bank_ex, bank_ex_ext):
    """对照集 = **外部池库** + 自己的库（2026-09-14, `loop_todo §1.8`）。

    :param bank_ex:     自己的收益流库（`loop_state*.pkl` ⇒ **会被持久化**）
    :param bank_ex_ext: 从**其它池** state 注入的对照集（**只读，绝不持久化**）
    :return: 供 `ex_max_corr` 用的对照视图（浅拷贝，value 是同一个对象 ⇒ 开销可忽略）

    ★★ 为什么要分开存而不是直接并进 `bank_ex`：
      本循环会往 `bank_ex[expr] = _ex` 写（入库即进对照集），而 state 只保存 `bank_ex`
      ⇒ 若把外部池的 47 条并进去，它们会被**当成"全A 自己入库的因子"写进 `loop_state.pkl`
      和 `docs/factor_library.md`** ⇒ **污染因子库** ✗（库里会凭空多出一批不是它挖的因子）
    ★ 语义：外部池库只能"**告诉我这些已经挖过了**"，不能"算我的产出"。
    """
    if not bank_ex_ext:
        return bank_ex
    d = dict(bank_ex_ext)
    d.update(bank_ex)          # 自己的优先（同 expr 时以自己为准）
    return d


def ex_max_corr(ex_new, bank_ex, min_overlap=30):
    """新因子的**费后超额序列** vs 库内全部收益流的**最大 |Spearman 相关|**。

    为什么用"收益流"而不是"表达式/因子值"做去重（2026-09-13, roadmap §8.33 实测）：
      · 库内 30 个入库因子的**组合收益序列两两相关中位 0.967**（max 0.994）——
        **它们是同一块钱的不同写法**；等权合成的 Calmar(0.978) 还**低于**最好的单因子(1.146)
        ⇒ 合成无效 ⇒ 库里其实只有"一个因子"。
      · 同时结构层面**极其多样**（`tools/analyze_diversity.py`：全A 1439 条候选里
        结构骨架 1181 个唯一、Top5 仅占 1.9%）⇒ **表达式去重挡不住"同一块钱"**。
      ⇒ ⇒ 所以"重复"必须**按收益流判**：换叶子/换窗口/换外壳赚同一块钱的，应当归为同族。

    返回 (max|corr|, 命中的库内表达式)；无从判定返回 (None, None)。
    口径: 只取两条序列**共同日期**上的有限值对；重叠期数 < min_overlap 则跳过(不当成重复)。
    """
    if ex_new is None or not bank_ex:
        return None, None
    try:
        en = pd.Series(ex_new).astype('float64')
    except Exception:
        return None, None
    if len(en) < min_overlap:
        return None, None
    best, who = 0.0, None
    for k, ex_old in bank_ex.items():
        try:
            eo = pd.Series(ex_old).astype('float64')
            a, b = en.align(eo, join='inner')
            m = np.isfinite(a.values) & np.isfinite(b.values)
            if int(m.sum()) < min_overlap:
                continue
            # 用两个"新建的 Series"(默认 RangeIndex)对齐后算 Spearman, 避免索引不一致
            c = abs(float(pd.Series(a.values[m]).corr(pd.Series(b.values[m]),
                                                      method='spearman')))
            if np.isfinite(c) and c > best:
                best, who = c, k
        except Exception:
            continue
    return (best if who is not None else None), who


def _tag_desc(tag):
    """池标签的中文含义（转发到单一事实源 loop_pools.tag_desc）。"""
    import loop_pools as _lp
    return _lp.tag_desc(tag)


def _gate_of(args):
    """从命令行参数提取**实际生效的判定门槛**（供 `loop_critic.diagnose` 对账）。

    ★★★ 为什么必须有这个函数（2026-09-14，`docs/loop_todo.md` §1.1 问题②）：

      `loop_critic.py:94` 曾写死 `fail_calmar = (fail['calmar'] <= 0.5).mean()` ——
      **硬编码 0.5 且取全A 口径**；而**池内模式**的判定用的是**池口径**
      （`任一池 Calmar > --min_pool_calmar`）⇒ **传感器测的不是真正卡住候选的那道门**
      ⇒ 实测 `1000 gen1` 报 `fail_calmar=1.000`，而同代**确有 2 个候选 Calmar 0.661/0.561 入库**
      （指标自相矛盾），且 **96/96 代**都触发规则5 ⇒ `depth` 被**永久**推到 `[3,4,4]`。

    **单一事实源纪律**：门槛**只从 `args` 读一次**（本函数），引擎自己那份 `_pool_gate_on`
    也由同一逻辑推出 ⇒ 两侧不会再漂移。改门槛相关的 flag 时，**只改这里**。
    """
    _mpc = float(getattr(args, 'min_pool_calmar', -1.0) or -1.0)
    return dict(min_calmar=float(getattr(args, 'min_calmar', 0.0)),
                min_sharpe=float(getattr(args, 'min_sharpe', 0.5)),
                min_pool_calmar=_mpc,
                pool_gate_on=(_mpc >= 0),          # 默认 -1 = 关; >=0 启用(0 是合法阈值)
                pool_mode=getattr(args, 'pool_gate_mode', 'any') or 'any',
                or_all=bool(getattr(args, 'pool_gate_or_all', False)))


def _pool_best(pool_rows):
    """把 `pool_rows`（逐候选 × 逐池的长表）压成 `{expr: 该候选**最好**的池 calmar}`。

    这是 `loop_critic.diagnose` 的**池口径传感器**输入。
    ★ 为什么取 **max**：池门槛的默认语义是 `any`（**任一池**达标即达标），
      而诊断要回答的是"**离最近的那条通道差多远**" ⇒ max 正确。
      （`all` 语义下 max 不足以判定，但那属于"判定"的职责，不是"诊断"的 ——
       诊断只需指出**有没有一条通道够得着**。）
    ⚠ 缺数据时返回 `{}`（而不是臆造 0）⇒ `diagnose` 会**不产出** `fail_pool_calmar`
      （与 strip / 池门槛 / LLM 同一条"缺失即不臆造"的铁律）。
    """
    out = {}
    for r in (pool_rows or []):
        try:
            e = str(r['expr'])
            c = float(r['calmar'])
        except Exception:
            continue
        if not np.isfinite(c):
            continue
        if e not in out or c > out[e]:
            out[e] = c
    return out


def combine_ok(ok_base, ok_q, ok_pool, ok_hard, pool_gate_on, or_all):
    """L2 入库判定的组合逻辑 —— **单一事实源**（2026-09-14 从内联代码提取，见 loop_todo §1.17）

    :param ok_base: `factor_miner.pass_filter` 的结果（11 项基础标准）
    :param ok_q:    「全A 量化口径」= `calmar>min_calmar 且 sharpe>min_sharpe`（+分段，见调用点）
    :param ok_pool: 「池内量化口径」= 任一/全部池 `calmar > min_pool_calmar`；**`None` = 无从判定**
    :param ok_hard: **硬门槛**（剥风格 + 分段独立验证）—— 与"选哪个口径"**无关**，必须**无条件**生效
    :param pool_gate_on: `--min_pool_calmar >= 0`
    :param or_all:       `--pool_gate_or_all`

    ★★★ 为什么必须把 `ok_hard` 独立出来（本次修的 bug）：

    原实现（L2015-2024）：
    ```python
    _ok_prev = ok                     # 快照取在 _ok_q **之前**
    ok = ok and _ok_q
    ...
    ok = ok and seg_ok                # 分段独立验证
    ok = ok and strip_ok              # 剥风格门槛
    ...
    elif _pool_gate_or_all:
        ok = _ok_prev and (_ok_q or _pok)      # ★ 用旧快照**整个重建**
    ```
    注释本意是「**只撤掉 `_ok_q`**」（否则 OR 退化成 AND），但 `_ok_prev` 取在 `_ok_q` 之前
    ⇒ 它**同时撤掉了后面才 AND 进去的 `seg_ok` 与 `strip_ok`**。

    **实测后果**：`--pool_gate_or_all` 一旦开启（§8.26，2026-09-13 起），池轨道的
    「剥风格门槛」与「分段独立验证」**完全失效且无告警** —— 池后缀 13 个入库因子里
    **8 个是「纯风格」（C 档，`strip_calmar` 全为负）**，本该被 `--min_strip_calmar=0.15` 全部拦下。

    ⇒ **OR 只该作用于「全A 口径 **vs** 池内口径」这个二选一**；
      剥风格 / 分段验证是**因子本身的品质关**，与选哪个口径无关 ⇒ 记进 `ok_hard`，
      在池门槛段**之后**统一 AND 回来，**不参与 OR**。

    ⚠ `ok_pool is None`（未开 `--pool_obs` / 计算失败）⇒ **放行不误杀**（与 strip/LLM 同一铁律），
      但调用点要计数并在代末上报，否则门槛静默失效而无人察觉。
    """
    if not pool_gate_on or ok_pool is None:
        ok = bool(ok_base and ok_q)
    elif or_all:
        ok = bool(ok_base and (ok_q or ok_pool))
    else:
        ok = bool(ok_base and ok_q and ok_pool)
    return bool(ok and ok_hard)          # ★ 硬门槛最后统一 AND，**不参与 OR**


def _mk_library_skeleton(fname):
    """为某个池创建 `factor_library_{pool}.md` 的最小骨架（2026-09-13, roadmap §8.44）。

    为什么必须自动建：per-pool 路径由 `set_mine_pool` 派生，但这三个文件**从未被创建**
    ⇒ `_lib_sync` 原先遇到不存在就 `return`，把失败**完全吞掉** ⇒ 池轨道入库的因子
    **一个都没进文档**（实测 1000 池 2 代 3 个因子、300 池 1 个因子全丢）。

    ⚠ 骨架**必须含三个锚点**，否则 `_lib_sync` 的插入逻辑不成立（会再次静默出错）：
      ① `> 当前 **N 个入库**`  —— 供其 `re.sub` 更新计数
      ② `## 因子明细`          —— 明细小节插在它之前
      ③ `## 相关文件导航`      —— 明细插在它之前
    """
    tag = 'all'
    m = re.search(r'factor_library_(.+)\.md$', fname)
    if m:
        tag = m.group(1)
    sfx = '' if tag == 'all' else '_' + tag
    txt = (
        '# 因子库（池 = {t}）\n\n'
        '> 当前 **0 个入库**\n'
        '> 本文件由引擎在**每代末尾自动同步**（`--mine_pool={t}` 时生效；实现见 `_lib_sync`）。\n'
        '> ⚠ 与全A 轨道的 `docs/factor_library.md` **互不读写**（池隔离，见 roadmap §8.42）。\n\n'
        '---\n\n'
        '## 因子总览\n\n'
        '| 编号 | 入库代数 | 家族 | 一句话 | 状态 |\n'
        '|---|---|---|---|---|\n\n'
        '## 因子明细\n\n'
        '## 相关文件导航\n\n'
        '| 文件 | 内容 |\n|---|---|\n'
        '| `docs/factor_library{s}.md`（本文件） | 池 **{t}** 的入库因子（只增不改） |\n'
        '| `docs/factor_library.md` | 全A 轨道的入库因子 |\n'
        '| **`docs/factor_library_crosspool.md`** | ★ **跨池派生视图**：各池库里**全A 有效**的因子'
        '去重 + 池标签并集修正（`python tools/build_crosspool_view.py` 生成） |\n'
        '| `docs/loop_journal{s}.md` | 池 **{t}** 的每代诊断 + B角下一代参数 |\n'
        '| `docs/loop_pool_obs{s}.csv` | 池 **{t}** 候选的**三池池内指标**宽表 |\n'
        '| `docs/loop_archive{s}.csv` | 池 **{t}** 每代 L2 全量候选流水 |\n'
    ).format(t=tag, s=sfx)
    io.open(_P.LIBRARY, 'w', encoding='utf-8').write(txt)


def append_library_entries(evs, quiet=False):
    """把**本次入库**的事件追加进 `docs/library_entries.jsonl`（幂等：同 (pool, code) 只留一条）。

    ⚠ 契约与 `_lib_sync` 一致：**任何失败只告警，绝不影响入库主流程** ✓（但**必须吼**）
    """
    if not evs:
        return 0
    try:
        old = []
        if os.path.exists(_P.LIB_ENTRIES):
            with io.open(_P.LIB_ENTRIES, encoding='utf-8') as f:
                for ln in f:
                    ln = ln.strip()
                    if not ln:
                        continue
                    try:
                        old.append(json.loads(ln))
                    except Exception:
                        continue          # 坏行跳过（不让一行脏数据毁掉整个日志 ✓）
        seen = {(x.get('pool'), x.get('code')) for x in old}
        add = [e for e in evs if (e.get('pool'), e.get('code')) not in seen]
        if not add:
            return 0
        os.makedirs(os.path.dirname(_P.LIB_ENTRIES), exist_ok=True)
        with io.open(_P.LIB_ENTRIES, 'a', encoding='utf-8') as f:
            for e in add:
                f.write(json.dumps(e, ensure_ascii=False) + '\n')
        if not quiet:
            print('  [入库日志] +%d 条 -> %s' % (len(add), os.path.basename(_P.LIB_ENTRIES)))
        return len(add)
    except Exception as e:                # noqa: BLE001
        print('  [入库日志] [!] 写入失败（不影响入库）: %s: %s' % (type(e).__name__, e))
        return 0


def _lib_sync(gen, res, n_total, added_exprs, expr2nd, pool_tags=None, strip_grades=None,
              horizon=None, source=None):
    """本代新入库因子自动同步追加进 docs/factor_library.md(只增不改历史, 家族命名留待人工精炼)。
    幂等: 编号取文本现有最大 F{nn}+1; 任何失败仅告警, 绝不影响入库主流程。
    added_exprs: 本代真正 append 进 bank 的 expr 列表; expr2nd: {str(node): node}(模块已有 Node/skeleton)。
    pool_tags  : ★ 2026-09-13 新增 {expr: pool_tag} —— 用户要"一眼看出这个因子是全A+哪个池好用、
                 还是只有全A好用"。规则来自 `loop_pools.derive_tag`（单一事实源），
                 与 `standard/pool_tags.py` 派生出的 `docs/pool_tags.csv` **同一套口径**。
                 没跑到 `--pool_obs` 时字典为空 -> 该行写"未测(--pool_obs 未开)"，**不写未知标签**。
    horizon    : ★ 2026-09-21 新增（**默认 None = 5 日口径 = 行为与改造前完全一致** ✓）。
                非 None（如 20）时：① 明细块加一行「口径」✓ ② `library_entries.jsonl` 的
                事件带 `horizon` 字段 ✓。
                ⚠ 为什么加：**双口径**下"同一个表达式在两个口径下表现不同" ⇒ 入库文档必须写明
                  按哪个口径验的 ✗，否则半年后无法分辨（与 `factor_metrics.py` 抬头打口径同理 ✓）。
                ⚠ 为什么**不加表格列**：总览表头固定 5 列、文件 append-only ⇒ 加列会让历史行错位 ✗
                  （与池标签/剥风格/sign 同一处理 ✓ 只写明细块 ✓）。"""
    import re
    import io
    # ★★★ 2026-09-15 修（P0-2 重构时被"名字封闭性检查"照出来的**潜伏 bug**）：
    #   本函数用了 `_lp.TAG_STRIP_DD_MIN`，但 `_lp` **没有可解析来源** ——
    #     · `_tag_desc` 里的 `import loop_pools as _lp` 是**它的局部**，与本函数无关 ✗
    #     · 模块级也没有 `_lp`（`dir(loop_engine)` 已确认）✗
    #   ⇒ 一旦 `strip_grades` 带日频回撤（即 `--strip_style` 开过）⇒ **`NameError`** ✗
    #   ★★ 而本函数 docstring 写着"任何失败仅告警, 绝不影响入库主流程" ⇒ 被 try 吞掉
    #     ⇒ **静默失败**：因子库文档不更新，且不报错（正是本项目反复踩的那类坑）✗✗
    #   ⇒ 补上 import（最小修法，零行为变化）✓
    import loop_pools as _lp
    try:
        if not added_exprs:
            return
        if not os.path.exists(_P.LIBRARY):
            # ★★ 不再静默跳过（2026-09-13 实录, roadmap §8.44）：
            #   per-pool 的 _P.LIBRARY 路径是 `set_mine_pool` 派生的（`factor_library_{pool}.md`），
            #   而这三个文件**从来没被创建过** ⇒ 原先的 `return` 把失败**完全吞掉**
            #   （不报错、不告警、不留痕）⇒ 实测 `--mine_pool=1000` 连跑 2 代入库 **3 个因子**，
            #   文档**一个都没写**；300 池入库的那 1 个也从没写进 `factor_library_300.md`。
            #   ⚠ 这与今天修的 `--pool_obs` 是**同一类坑**：新功能只做了一半（路径派生了、
            #     文件没人建），而且**失败无声**。⇒ 修法：**自动创建骨架 + 明确打印**。
            _mk_library_skeleton(os.path.basename(_P.LIBRARY))
            print(f"  [文档] {os.path.basename(_P.LIBRARY)} 不存在 -> **已自动创建骨架**"
                  f"（首次同步；此前该池的入库因子从未写进文档）")
        rows = {str(r['expr']): r for _, r in res.iterrows()} if len(res) else {}
        txt = io.open(_P.LIBRARY, encoding='utf-8').read()
        nos = [int(x) for x in re.findall(r'\bF(\d{2})\b', txt)]
        no = (max(nos) + 1) if nos else 1
        tbl_rows, det_rows = [], []
        evs = []                     # ★ 入库事件（写 md 的同时落到 `library_entries.jsonl` ✓）
        for expr in added_exprs:
            r = rows.get(expr)
            if r is None:
                continue
            nd = expr2nd.get(expr)
            cat_s = str(r['cat']); leaf_s = str(r['leaf'])
            fam = (cat_s[:20] + '…') if len(cat_s) > 20 else (cat_s or '未分类')
            short = expr if len(expr) <= 44 else expr[:41] + '…'
            met = ('IC %.4f / IC_IR %.3f / 年化超额 %+.1f%% / 回撤 %.1f%% / '
                   'Calmar %.3f / Sharpe %.3f / 最近年 %+.1f%% / 单期换手 %.1f%% / 负年 %d'
                   % (r['ic'], r['ic_ir'], r['ann_ex'] * 100, r['dd'] * 100,
                      r['calmar'], r['sharpe'], r['last_yr'] * 100, r['turn'] * 100,
                      int(r['neg_yr'])))
            skel = skeleton(nd) if nd is not None else '?'
            _tg = (pool_tags or {}).get(expr)
            _tg_line = ('- 池标签：**`%s`** —— %s\n' % (_tg, _tag_desc(_tg))
                        if _tg else '- 池标签：未测（本代未开 `--pool_obs`）\n')
            # ★★★ 符号 `sign`（2026-09-14, loop_todo §1.23）—— **下游用它的第一件事**。
            #   为什么必须写进文档：引擎求值时对 `sign<0` 的候选**取负**（让"值越大越好"）；
            #   下游拿到因子值 h5 **直接排序选股、不乘 `sign`** ⇒ **方向反了、组合反向选股** ✗
            #   实测：精选池 7 个里 **6 个 `sign=-1`** ⇒ 中招概率很高，且**错了不报错**。
            # ⚠ 只写进**明细块**，**不加表格列** —— 本文件 append-only、总览表头只写一次，
            #   加列会让历史行全部错位（与 §8.30 的 CSV 同一个坑，见上面 `tbl_rows` 处的注释）。
            _sg_val = r.get('sign') if hasattr(r, 'get') else None
            try:
                _sg_n = int(round(float(_sg_val)))
            except Exception:
                _sg_n = None
            _sg_line2 = ('- **符号 `sign`：`%d`**（★ 因子值须乘它才是"越大越好"的方向；'
                         '不乘 ⇒ 反向选股）\n' % _sg_n if _sg_n is not None
                         else '- 符号 `sign`：**未记录**（缺失时不臆造，见 roadmap §8.45 铁律）\n')
            # ★ 剥风格档（2026-09-14, §1.9）：**并列**于池标签，不替代它。
            #   为什么要写进文档：实测约一半入库因子是"纯风格"（全A 口径漂亮、剥掉
            #   lncap+lnamt 后转负），而**下游拿到文档就该一眼看出**，不能靠回头翻 CSV。
            _sg = (strip_grades or {}).get(expr)
            if _sg:
                _sg_k, _sg_txt = _sg[0], _sg[1]
                #  ★ 2026-09-14（§1.19）：判据已改**日频** ⇒ 文档里同时给日频（可缺）
                _scd, _sddd = (_sg[4] if len(_sg) > 4 else None,
                               _sg[5] if len(_sg) > 5 else None)
                _ddtxt = ''
                if _scd is not None and np.isfinite(_scd):
                    _ddtxt = '；**日频** 剥后 Calmar %.3f' % _scd
                    if _sddd is not None and np.isfinite(_sddd):
                        _ddtxt += '，日频回撤 %.1f%%' % (_sddd * 100)
                        if _sddd <= _lp.TAG_STRIP_DD_MIN:
                            _ddtxt += ' ⚠（劣于上限 %.2f ⇒ 只给 B）' % _lp.TAG_STRIP_DD_MIN
                _sg_line = ('- 剥风格：**`%s`** %s'
                            '（原 Calmar %.3f → 剥后 %.3f；超额 %+.1f%% → %+.1f%%%s）\n'
                            % (_sg_k, _sg_txt, r['calmar'], _sg[2],
                               r['ann_ex'] * 100, _sg[3] * 100, _ddtxt))
            else:
                _sg_line = ('- 剥风格：**未测**（本代未开 `--strip_style`）'
                            '⇒ ⚠ **不可断言它是独立 alpha**（见 roadmap §8.45 / loop_todo §1.9）\n')
            # ⚠ **不加表格列**（2026-09-13 实录）：总览表头是**固定 5 列**
            #   `| 编号 | 入库代数 | 家族 | 一句话 | 状态 |`，而本文件是 append-only、
            #   表头只写一次 ⇒ 加列会让**历史行全部错位**（与 §8.30 的 CSV 同一个坑）。
            #   ⇒ 池标签只写进**明细块**（用户正是看那里）。
            tbl_rows.append('| F%02d | gen%d | %s | %s | 已入库(auto) |'
                            % (no, gen, fam, short))
            # ★ 2026-09-21（双口径）：**口径行** —— 只写明细块 ✗（总览表头固定 5 列、文件
            #   append-only ⇒ 加列会让历史行错位 ✓ 与池标签/剥风格/sign 同一处理 ✓）
            # ★ 2026-09-22（(丁) 受控入库）：**来源**要如实标 ✗ —— 默认 `engine`（引擎自己跑的 ✓，
            #   行为与改造前**逐位不变** ✓）；`tools/horizon_admit_write.py` 传 `promote` ⇒
            #   ① 事件里 `source/tsSource` 写 `promote` ✓（不能冒充引擎 ✗ —— 看板"新入库日志"
            #      与将来的审计都要能分辨"哪些是自动挖的、哪些是事后受控补的" ✓）
            #   ② 明细块加一行「来源」✓（标题行**不动** ✗ —— `BF.parse_library` 按
            #      `### F\d+ · ` 切分正文 ✓，改标题会牵动解析 ✓）
            _src = source or 'engine'
            _src_line = ('- 来源：**受控入库**（`tools/horizon_admit_write.py`，非引擎自动 ✓）'
                         '★ 入库依据与生产线不同 ✗ ⇒ 该条**未经过引擎当代 L1/L2 全链**\n'
                         if _src != 'engine' else '')
            _hz_line = ''
            if horizon:
                _nr = r.get('n_rebal') if hasattr(r, 'get') else None
                _hz_line = ('- 口径：**%d 日调仓** ✓（%s成本 %s）'
                            '★ 与 5 日口径的数字**不可直接比** ✗'
                            '（样本区间/成本相同，只有调仓周期不同 ✓）\n'
                            % (int(horizon),
                               ('期数 %s；' % (int(_nr) if _nr is not None and np.isfinite(_nr)
                                              else '—')) if _nr is not None else '',
                               cost_label(r['cost'])))
            det_rows.append(
                '\n### F%02d · gen%d 入库（引擎自动同步，家族命名待人工精炼）\n'
                '```\n%s\n```\n'
                '%s- 家族：%s（auto）\n- 叶子：%s\n- 骨架：`%s`\n'
                '%s%s%s%s'
                '- 费后指标（full，成本 %s）：%s\n'
                % (no, gen, expr, _sg_line2, fam, leaf_s, skel, _tg_line, _sg_line, _hz_line,
                   _src_line, cost_label(r['cost']), met))
            _ev = dict(ts=time.strftime('%Y-%m-%d %H:%M:%S'), tsSource=_src,
                       source=_src, pool=_P.MINE_POOL, gen=int(gen),
                       code='F%02d' % no, expr=expr, family=fam, oneLiner=short,
                       ic=(float(r['ic']) if np.isfinite(r['ic']) else None),
                       annEx=(float(r['ann_ex']) if np.isfinite(r['ann_ex']) else None))
            if horizon:
                # ★ 双口径：事件里标明**按哪个口径验的** ✓（默认 5 日 ⇒ 不带该字段 ⇒ 历史不变 ✓）
                _ev['horizon'] = int(horizon)
            evs.append(_ev)
            no += 1
        if not det_rows:
            return
        add_tbl = '\n'.join(tbl_rows)
        add_det = ''.join(det_rows)
        # 1) 头部计数行(自动同步计数)
        txt = re.sub(r'> 当前 \*\*\d+ 个入库\*\*', '> 当前 **%d 个入库**' % n_total,
                     txt, count=1)
        # 2) 总览表格末尾(## 因子明细 前最后一个 '| F' 数据行)后插入新行
        j = txt.find('\n## 因子明细')
        i = txt.rfind('\n| F', 0, j) if j > 0 else -1
        if i >= 0:
            k = txt.find('\n', i + 2)
            if k >= 0:
                txt = txt[:k] + '\n' + add_tbl + txt[k:]
        elif j > 0:
            # ★ 该池文档还没有任何数据行(刚建的骨架) -> 表行插在 '## 因子明细' 之前
            #   否则 `rfind('\n| F')` 返回 -1, 总览表**永远不会有数据行**(静默)。
            #   ⚠ 这里要**补两个换行**：`txt[j:]` 只带一个 `\n`，少一个空白行会让
            #     `## 因子明细` 被 markdown 当成表格的一部分（渲染错乱）。
            txt = txt[:j] + '\n' + add_tbl + '\n\n' + txt[j + 1:]
        # 3) 明细小节插在 '## 相关文件导航' 前(原 --- 分节保留, 新条目自带分隔)
        nav = '\n## 相关文件导航'
        p = txt.find(nav)
        if p < 0:
            txt = txt.rstrip('\n') + add_det + '\n'
        else:
            txt = txt[:p] + add_det + '\n---\n\n' + txt[p:]
        io.open(_P.LIBRARY, 'w', encoding='utf-8').write(txt)
        # ★ 同步落一份**结构化入库事件**（看板"新入库日志"卡片读它 ✓；失败只告警、不影响入库 ✓）
        append_library_entries(evs)
        # ⚠ 打印**真实文件名**（2026-09-13）：原先硬编码写 `factor_library.md`，
        #   池轨道跑时也在报 `factor_library.md`，**指到了别的文件** ⇒ 排查时误导。
        print(f"  [文档] {os.path.basename(_P.LIBRARY)} 已自动追加 {len(det_rows)} 条新入库 "
              f"(F{nos and max(nos)+1 or 1}~F{no-1}, 累计 {n_total})")
    except Exception as e:
        # ⚠ 失败路径也要报**真实文件名**（2026-09-14 修）：成功路径早已改成 basename，
        #   失败路径却还硬编码 `factor_library.md` ⇒ 池轨道出错时会**指错文件**（§8.44 的孪生坑）。
        print(f"  [文档] {os.path.basename(_P.LIBRARY)} 自动同步失败(不影响入库): "
              f"{type(e).__name__}: {e}")


def _save_state(_dup_ex_corr, _ex_by_expr, _n_dup_ex, _strip_by_expr, _tag_by_expr, _v, args, bank, bank_ex, bank_ex_ext, cands, fail_lib, frozen, fsa, k, l1, n_tested_prev, nd, next_cfg, pool_rows, res, s, t0, top, v, fsa_frz,
                _strip2_by_expr=None, _hzn2_by_expr=None):
    """P0-2 纯提取自 `run()`（逐字搬运，语义不变）。

    原段落: 保存状态
    """
    new_seeds = list(l1.head(30)['node'])
    if len(res) and res['passed'].any():
        new_seeds = list(l1.head(20)['node'])
    # 入库因子库 bank: 本代通过者入列(node级去重), 供下代 decorr 对比
    # 对齐中金: ①冻结骨架禁入 ②同结构参数变体上限有限(bank_skel_max) 防窗口变体堆叠
    if len(res) and res['passed'].any():
        by_expr = {str(r['node']): r['node'] for _, r in top.iterrows()}
        skel_cnt = skeleton_freq(bank)
        fset = set(frozen) if args.fsa_th > 0 else set()
        n_bank_old = len(bank)
        lib_added = []
        for expr in res.loc[res['passed'], 'expr'].tolist():
            nd = by_expr.get(expr)
            if nd is None or any(str(x) == expr for x in bank):
                continue
            s = skeleton(nd)
            if s in fset:
                print(f"  [FSA] 通过但不入库: 骨架已冻结 -> {s}")
                continue
            if skel_cnt.get(s, 0) >= args.bank_skel_max:
                print(f"  [FSA] 通过但不入库: 骨架 {s} 已有 {skel_cnt.get(s,0)} "
                      f"个(上限{args.bank_skel_max})")
                continue
            # ★ 收益流去重(2026-09-13, roadmap §8.34, --dup_ex_corr): **止血**闸门。
            #   bank_ex 会在本循环里随入库增长 ⇒ 同时防"与历史库重复"与"同代内近重复"。
            #   ⚠ 拿不到收益流(旧 state / 回测失败)则**放行不误杀**(与本项目其它闸门同一铁律)。
            _ex_i = _ex_by_expr.get(expr)
            if _dup_ex_corr > 0 and _ex_i is not None:
                _mc2, _mw2 = ex_max_corr(_ex_i, _cmp_lib(bank_ex, bank_ex_ext))   # ★ 含外部池库(§1.8)
                if _mc2 is not None and _mc2 > _dup_ex_corr:
                    _n_dup_ex += 1
                    print(f"  [收益流去重] 不入库: 与库内收益流相关 {_mc2:.3f} > "
                          f"{_dup_ex_corr:.2f}（对方 {str(_mw2)[:66]}）")
                    continue
            bank.append(nd)
            skel_cnt[s] = skel_cnt.get(s, 0) + 1
            lib_added.append(expr)
            if _ex_i is not None:
                bank_ex[expr] = _ex_i          # 入库 -> 其收益流进对照集
        if _n_dup_ex:
            print(f"  [收益流去重] 本代拦下 {_n_dup_ex} 个「与库内赚同一块钱」的因子"
                  f"(阈值 |corr|>{_dup_ex_corr:.2f})")
        if len(bank) > n_bank_old:
            print(f"  入库 {len(bank)-n_bank_old} 个新因子, 累计 {len(bank)} 个")
            # 入库文档自动同步(factor_library.md): 只增不改, 失败不影响入库
            # ★ 带池标签(§8.42): 入库条目里写明"适用哪个池"
            # ★★★★★ 2026-09-22（v1.21.29 · (乙)）：**按口径分别落文档** ✓
            #   为什么必须分：`_lib_sync` 会写「口径：N 日调仓」+ 用**对应口径**的剥风格数字 ✓
            #   ⇒ 混在一起就会把 5 日的剥风格结论写给 20 日入选的因子 ✗
            #   ⚠ 两次调用都**重读 md** ⇒ 编号自动递增 ✓ 不会撞号 ✓（`_lib_sync` 的既有行为 ✓）
            _added_2 = [e for e in lib_added if e in _hzn2_by_expr]
            _added_5 = [e for e in lib_added if e not in _hzn2_by_expr]
            if _added_5:
                _lib_sync(args.gen, res, len(bank), _added_5, by_expr,
                          pool_tags=_tag_by_expr, strip_grades=_strip_by_expr)
            if _added_2:
                print(f"  [双口径] 其中 {len(_added_2)} 个是**副口径({int(args.dual_fwd)} 日)"
                      f"入选** ✓ ⇒ 文档按该口径标注 ✓（与 5 日口径的数字不可直接比 ✗）")
                _lib_sync(args.gen, res, len(bank), _added_2, by_expr,
                          pool_tags=_tag_by_expr, strip_grades=_strip2_by_expr,
                          horizon=int(args.dual_fwd))
            # ★ 剥风格档汇总（2026-09-14, §1.9）：**"纯风格"必须吼出来** —— 它是"全A 口径漂亮
            #   但剥掉 lncap+lnamt 后转负"的因子，入库后**指数增强不可用**，不吼会被忽略。
            if _strip_by_expr:
                _sc_cnt = {}
                for _e in lib_added:
                    _v = _strip_by_expr.get(_e)
                    if _v:
                        _sc_cnt[_v[0]] = _sc_cnt.get(_v[0], 0) + 1
                if _sc_cnt:
                    print("  [剥风格档] 本代入库因子: " + ", ".join(
                        "{}x{}".format(k, v) for k, v in sorted(_sc_cnt.items())))
                _n_c = sum(v for k, v in _sc_cnt.items() if k == 'C')
                if _n_c:
                    print("  [!][剥风格档] **{} 个是「纯风格」**（剥掉 lncap+lnamt 后超额/Calmar 转负）"
                          "⇒ 指数增强不可用 ⇒ 检查 `--min_strip_calmar` 是否已设".format(_n_c))
            if _tag_by_expr:
                _tg_cnt = {}
                for _e in lib_added:
                    _t = _tag_by_expr.get(_e)
                    if _t:
                        _tg_cnt[_t] = _tg_cnt.get(_t, 0) + 1
                if _tg_cnt:
                    print("  [池标签] 本代入库因子: " + ", ".join(
                        "{}x{}".format(k, v) for k, v in sorted(_tg_cnt.items())))
    for k, v in DEFAULT_CFG.items():
        next_cfg.setdefault(k, v)      # critic.suggest 重建dict可能丢键 -> 兜底补齐
    next_cfg.setdefault('bank_skel_max', args.bank_skel_max)
    fail_lib = fail_lib_cleanup(fail_lib, args.gen)
    # ★ 原子写(2026-09-12 加固): 先写 .tmp 再 os.replace 原子替换。
    #   原因: 原 `open(_P.STATE,'wb')` 会**立刻把旧 state 截断成 0 字节**, 一旦 dump 中途异常
    #   (或进程被杀), 就得到一个 0 字节坏状态 —— 而 journal 已写了"第 N 代完成"
    #   ⇒ 下次续跑会拿坏状态接代数, 静默错乱。实录见 roadmap §8.23。
    _tmp = _P.STATE + '.tmp'
    with open(_tmp, 'wb') as f:
        pickle.dump(dict(seeds=new_seeds[:60], fsa=fsa,
                         # ★ 入库库**全量保存**(2026-09-12 去掉 `bank[-30:]` 上限, 用户选定):
                         #  截断会丢掉最老的入库因子 -> ①--decorr 不再对照它们 ->
                         #  引擎可能重新发现旧因子("打转"的隐藏成因); ②引擎 bank 与
                         #  docs/factor_library.md(append-only) 数量不一致(实录 30 vs 32)。
                         #  代价: --decorr 每候选要跟整库逐个比, 成本 O(len(bank)) ->
                         #  若库显著增长, 见去相关段的计时输出(实测 30 库/432 候选 = 276s)。
                         bank=bank,
                         # ★ 收益流库(§8.34): {表达式: 每期费后超额 Series}。
                         #   体积很小(每条 ~400 期 float64 ≈ 3KB; 100 个因子 ≈ 0.3MB)。
                         bank_ex=bank_ex,
                         frozen=frozen,
                         # ★ 2026-09-17：冻结**记账**（次数/剩余代数/冷却计数）—— 有它才能跨代做
                         #   "2→4→8 代封顶 + 冷却期遗忘"；缺它则每次重启都当"第 1 次冻结"（偏松 ✗）
                         fsa_frz=fsa_frz,
                         fail_lib=fail_lib,
                         n_tested=n_tested_prev + len(cands),
                         last_l1=l1, last_l2=res if len(res) else None,
                        # ★ 池口径传感器（2026-09-14, §1.1 修法②）: {expr: 最好的池 calmar}。
                        #   代首"重审上一代"时必须用它才能算出**池口径**失败率 ——
                        #   `last_l2` 只有全A 口径，回答不了"离池门槛差多远"。
                        #   体积很小（每代候选数个小 float），可忽略。
                        last_pool_map=_pool_best(pool_rows),
                         cfg=next_cfg), f)
    os.replace(_tmp, _P.STATE)        # 原子替换: 要么全新状态, 要么保持旧状态, 不会出现半成品
    # ⚠ 日志口径: 打印的必须是**实际持久化**的数量(此前截断时打内存值 -> 与落盘不一致)
    print(f"\n保存状态: 种子 {len(new_seeds[:60])} 个, 入库因子 {len(bank)} 个(全量), "
          f"收益流库 {len(bank_ex)} 条, 冻结骨架 {len(frozen)} 个, 失败库 {len(fail_lib)} 条, "
          # ★ 2026-09-17：把冻结**记账**也报出来（用户要"日志留痕"）⇒ 一眼看出谁冻着、剩几代 ✓
          f"冻结记账 {len(fsa_frz)} 条"
          + ('（' + ', '.join('%s:剩%d代/第%d次' % (k[:28], v.get('left', 0), v.get('cnt', 0))
                              for k, v in sorted(fsa_frz.items(),
                                                 key=lambda kv: -kv[1].get('left', 0))[:3]) + '）'
             if fsa_frz else '') + ', '
          f"耗时 {time.time()-t0:.0f}s")


class _StateUnpickler(pickle.Unpickler):
    """★★★★★ 2026-09-25：读 state 时把**历史上误存的** `loop_engine.Node` 一并归一成本类 ✓

    背景（完整说明见**文件末尾** `__main__` 块里那行注册）：引擎直跑时曾并存**两个 `Node` 类**
    （`__main__.Node` 与 `loop_engine.Node`）⇒ 旧 state 的 `bank` / `seeds` / `last_l1`
    里混着两份类 ✗

    ⚠ 为什么必须归一：`isinstance(x, Node)` 是**类身份**判定 ⇒ 对第二份实例恒为 False ✗
      ⇒ `collect` / `leaf_parts` / **`skeleton`（骨架去重 / FSA 冻结）** / `key` / `size` /
      `crossover` / `mutate` / `dim_of` **全部对那批因子失效** ✗✗
      （实测：`bank` 439 个 Node 里 **438 个**是第二份 ⇒ 去重与 FSA 一直没对它们生效 ✗）

    修法：**只认类名** —— 不管 pickle 里记的是 `__main__.Node` 还是 `loop_engine.Node`，
      一律还原成**本模块**的 `Node` ✓（结构逐字一致，差的只是类身份 ✓）
    """

    def find_class(self, module, name):
        if name == 'Node':
            return Node
        return super().find_class(module, name)
