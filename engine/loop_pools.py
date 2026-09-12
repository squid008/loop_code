# -*- coding: utf-8 -*-
"""池（指数成分股）成员 —— **单一事实源**（2026-09-12，roadmap §8.9 的 B+B′ 步）

背景：用户要求「300、500、全市场都能选，入库时打标签（300好用 / 300+500好用 / 全都好用 /
     只有全A好用），将来做因子库 PG 时按标签筛选」。本模块提供 PIT 成分掩码，供引擎在
     **池内**计算 IC / 回测，从而生成该标签。

口径（**与 `standard_test.py` 的 `load_const` 一致**，PIT）：
    items = [(YYYYMMDD, {成员代码}), ...] 按日期升序
    某交易日 T 的成员 = items[bisect_right(cdates, T) - 1]   ← **当日之前最近一次调整**
    ⇒ 不是"最新快照"，避免未来函数（幸存者偏差）。
    ⚠ 这是**第二份实现**（第一份在 `standard_test.py:load_const`）⇒ 必须用
      `ai_test/qa_loop_pools.py` **逐日对拍**防漂移（与 `cost_presets.py`/`loop_fields.py`
      同一治理思路：能统一就统一，暂不能统一就必须有对拍）。

⚠ 本模块**不 import loop_engine**（避免循环依赖）；只依赖 numpy / h5py。

配置：成分文件路径见 `POOLS`；可用环境变量 `LOOP_POOL_DIR` 覆盖所在目录。
"""
import bisect
import os

import numpy as np

# E:\rq\constituents\index\ —— 聚宽导出，带 change_dates（PIT）
POOL_DIR = os.environ.get('LOOP_POOL_DIR', r'E:\rq\constituents\index')
POOLS = {
    '300': os.path.join(POOL_DIR, '000300.XSHG.h5'),    # 沪深300
    '500': os.path.join(POOL_DIR, '000905.XSHG.h5'),    # 中证500
    '1000': os.path.join(POOL_DIR, '000852.XSHG.h5'),   # 中证1000（数据已备，留待扩池）
    '50': os.path.join(POOL_DIR, '000016.XSHG.h5'),     # 上证50
}

_CACHE = {}          # tag -> (cdates:list[int], members:list[set[str]])


def pool_path(tag):
    """池代码 -> h5 路径；未知池报错（早失败优于静默空池）。"""
    if tag not in POOLS:
        raise KeyError(f"未知池 '{tag}'（可选: {sorted(POOLS)}）")
    return POOLS[tag]


def load_pool(tag):
    """载入 PIT 成分。返回 (cdates, members)：
      cdates  : list[int] 升序，调整日 YYYYMMDD
      members : list[set[str]] 与 cdates 等长，对应调整日**生效后**的成分集合
    结果带缓存（同一个进程内只读一次 h5）。"""
    if tag in _CACHE:
        return _CACHE[tag]
    import h5py
    path = pool_path(tag)
    if not os.path.exists(path):
        raise FileNotFoundError(f"成分文件不存在: {path}（可用 LOOP_POOL_DIR 覆盖目录）")
    items = []
    with h5py.File(path, 'r') as f:
        cd = [x.decode() if isinstance(x, bytes) else str(x) for x in f['change_dates'][:]]
        for d in cd:
            mem = {x.decode() if isinstance(x, bytes) else str(x)
                   for x in f['components'][d][:]}
            items.append((int(d.replace('-', '')), mem))
    items.sort(key=lambda x: x[0])
    _CACHE[tag] = ([x[0] for x in items], [x[1] for x in items])
    return _CACHE[tag]


def pool_union(tag):
    """该池在样本期内**出现过的全部**股票代码集合。
    用途：扩 L1 子面板列（`L1_COLS` = 随机抽样 ∪ 池并集），见 §8.9-⑤ 的"选项 2"。"""
    _, mems = load_pool(tag)
    u = set()
    for m in mems:
        u |= m
    return u


def pool_mask(tag, dates, cols):
    """构建 (T,S) bool PIT 掩码，行 = `dates`（YYYYMMDD 整数或可 int() 化），列 = `cols`。

    落在池内且**在面板里有列**的位置为 True；池外 / 面板无该股票 -> False
    （新股上市前、退市后自然为 False）。`dates` 建议升序（不强制，但升序时可走单调指针）。
    """
    cdates, mems = load_pool(tag)
    col_of = {}
    for j, c in enumerate(cols):
        col_of.setdefault(c, j)          # 重复列名取第一个（面板列名本应唯一）
    T, S = len(dates), len(cols)
    M = np.zeros((T, S), dtype=bool)
    if not cdates:
        return M
    for i, d in enumerate(dates):
        j = bisect.bisect_right(cdates, int(d)) - 1
        if j < 0:
            continue                      # 早于首个调整日 -> 无成分（不用未来数据）
        idx = [col_of[c] for c in mems[j] if c in col_of]
        if idx:
            M[i, np.asarray(idx, dtype=np.int64)] = True
    return M


def pool_masks(tags, dates, cols):
    """一次取多个池的掩码 -> {tag: (T,S) bool}"""
    return {t: pool_mask(t, dates, cols) for t in tags}


def pool_gate_ok(cals, thr, mode='any'):
    """池门槛判定（**纯函数**，便于单测；门槛语义错一格后果很重）。

    参数
      cals : 各池的 Calmar（可含 None/NaN —— 计算失败或该池样本不足）
      thr  : 阈值（引擎里来自 `--min_pool_calmar`；Calmar>0 即"该池有效"）
      mode : 'any' = **至少一个池**达标（方案 C：滤掉"只在全A有效"）
             'all' = **所有池**都达标（更严，要"真 alpha"）
    返回 (ok, val)
      ok  : True/False；**None 表示无从判定**（一个有效值都没有）-> 调用方应放行不误杀
      val : 参与判定的值（any 取 max / all 取 min）；无从判定时为 None
    """
    v = [float(c) for c in cals if c is not None and np.isfinite(c)]
    if not v:
        return None, None
    val = max(v) if mode == 'any' else min(v)
    return bool(val > thr), val


def parse_pools(text):
    """'300,500' -> ['300','500']；去重保序，非法池早失败。"""
    out = []
    for t in str(text).split(','):
        t = t.strip()
        if not t:
            continue
        if t not in POOLS:
            raise KeyError(f"未知池 '{t}'（可选: {sorted(POOLS)}）")
        if t not in out:
            out.append(t)
    return out
