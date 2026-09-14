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


# ===================== 池标签（pool_tag）单一事实源 =====================
# ★ 为什么放在这里（2026-09-13）：原先 `tag_of` 只存在于 `standard/pool_tags.py`，
#   而引擎要在**入库时**把标签写进 `docs/factor_library.md` ⇒ 若各自实现一份，
#   两份规则必然漂移（本项目一贯治理原则：能统一就统一，暂不能统一就必须对拍）。
#   今起**本模块是唯一事实源**，`standard/pool_tags.py` 与引擎都 import 它。
# 判定口径（与 §8.13 的 bank 诊断一致；改阈值只需改这两个常数并重跑派生脚本）：
TAG_POOL_FLOOR = 0.0      # 池内通过 = 该池费后超额 > 此值
TAG_CAL_MIN = 0.30        # 全A通过 = 费后超额 > 0 且 Calmar >= 此值

TAG_DESC = {
    'none': '全不通过',
    'all3': '全A **且所有池都通过**（真 alpha）',
    'csi_all_only': '**只有全A通过** ⇒ 小盘/流动性溢价嫌疑，**指数增强不可用**',
}


def derive_tag(ok_all, ok_by_pool, pools):
    """由「哪些池通过」派生标签（**单一事实源**；原 `standard/pool_tags.py:tag_of`）。

    ok_all     : 全A 是否通过（超额>0 且 Calmar>=TAG_CAL_MIN）
    ok_by_pool : {池: bool}，池内是否通过（该池费后超额 > TAG_POOL_FLOOR）
    pools      : 池顺序（决定标签里池名的排列）
    """
    passed = [p for p in pools if ok_by_pool.get(p)]
    if not passed and not ok_all:
        return 'none'
    if ok_all and len(passed) == len(pools):
        return 'all3'
    if ok_all and not passed:
        return 'csi_all_only'
    if ok_all:
        return 'csi' + '_'.join(passed) + '_all'
    if len(passed) == 1:
        return 'csi{}_only'.format(passed[0])
    return 'csi' + '_'.join(passed)


# ===================== 剥风格分档（单一事实源，2026-09-14）=====================
# ★★★ 为什么单独加这一档（问的是"这个因子的超额，剥掉 lncap+lnamt 之后还剩多少？"）：
#   实测（`python ai_test/check_strip_style_pool.py`）：**池库 7/14 = 50%、全A 库已测的 6/11 = 55%
#   是"纯风格因子"** —— 全A 口径 Calmar 看着漂亮（甚至 1.19/1.39），**剥掉市值/成交额后转负**。
#   例：`corr100(mf_s_bqty, mf_x_sell)` 原 1.193 → 剥 **−0.075**。
# ★ 根因是**入库判定漏了一道关**（`--strip_style` 开了记录却没传 `--min_strip_calmar`，
#   后者默认 -1 = 只记录不拦），已修（`ai_test/run_tracks.py` 加 `--min_strip_calmar=0.15`）。
# ★ 这一档**并列**于 `derive_tag`（**不改** `ok_all`），because：
#   ① 历史标签语义突变会让 journal/文档前后不可比；
#   ② 剥风格结果可能缺失（未开 `--strip_style`）⇒ 需要一个 **'D 未测'** 的诚实档位。
TAG_STRIP_CAL_MIN = 0.30     # 「独立有效」档，与 TAG_CAL_MIN 对齐（口径一致）

STRIP_DESC = {
    'A': '独立有效（剥风格后 Calmar 仍 >= {:.2f}）'.format(TAG_STRIP_CAL_MIN),
    'B': '弱独立（剥风格后 Calmar 在 0~{:.2f}）'.format(TAG_STRIP_CAL_MIN),
    'C': '**纯风格**（剥掉 lncap+lnamt 后超额/Calmar 转负）⇒ 指数增强不可用',
    'D': '未测（该代没开 `--strip_style`）',
}


def strip_grade(strip_calmar, strip_ann_ex):
    """剥风格分档（**单一事实源**；引擎、`ai_test/check_strip_style_pool.py`、
    `ai_test/build_crosspool_view.py` 全部 import 本函数，避免三处各写一套漂移）。

    返回 (档位, 说明)：
      **A 独立有效** `strip_calmar >= TAG_STRIP_CAL_MIN`
      **B 弱独立**   0 < strip_calmar < TAG_STRIP_CAL_MIN
      **C 纯风格**   `strip_ann_ex <= 0` 或 `strip_calmar <= 0` ⇒ **剥完就没了/变负**
      **D 未测**     取不到剥风格数据（**宁可标"未测"，绝不臆断**）

    ⚠ 判 `C` 用**两个条件或**：超额转负是最直接的证据；Calmar<=0 是必要补充
      （避免"超额微正但风险调整后为负"漏判）。
    """
    if strip_calmar is None or strip_ann_ex is None:
        return 'D', STRIP_DESC['D']
    try:
        sc, sa = float(strip_calmar), float(strip_ann_ex)
    except (TypeError, ValueError):
        return 'D', STRIP_DESC['D']
    if not (np.isfinite(sc) and np.isfinite(sa)):
        return 'D', STRIP_DESC['D']
    if sa <= 0 or sc <= 0:
        return 'C', STRIP_DESC['C']
    if sc >= TAG_STRIP_CAL_MIN:
        return 'A', STRIP_DESC['A']
    return 'B', STRIP_DESC['B']


def tag_desc(tag):
    """标签的中文含义（写进文档用）。未登记的组合名给通用说明。"""
    if tag in TAG_DESC:
        return TAG_DESC[tag]
    if tag.startswith('csi') and tag.endswith('_only'):
        return '仅 **{}** 池通过（全A 不通过）'.format(tag[3:-5])
    if tag.endswith('_all'):
        return '全A + **{}** 池通过'.format(tag[3:-4].replace('_', '/'))
    return '多池通过、全A 不通过（**{}**）'.format(tag[3:].replace('_', '/'))

