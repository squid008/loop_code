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
      `tools/qa_loop_pools.py` **逐日对拍**防漂移（与 `cost_presets.py`/`loop_fields.py`
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


def tool_pools():
    """★ 离线工具（`build_facs` / `factor_metrics` / `factor_curves`）的**默认池清单** —— 单一来源。

    ⚠⚠ 为什么必须有这个函数（2026-09-18 实测到的**真实缺口**）：
      那三个工具**各自硬编码**了 `'all,300,500,1000'` ✗ ⇒ **漏了「50」池** ✗
      而**调度器自己**跑的是 `--pools=all,300,500,1000,50` ✓（见 `mine.py`）
      ⇒ 后果：**若 50 池有因子入库，收尾不会给它生成 facs / 指标表 / 曲线（含剥全部）** ✗✗
        （当前 50 池 `bank=0` ⇒ 还没暴露，但这是埋着的坑）
      ⇒ 现在统一从 `POOLS`（本文件 = 池定义的唯一来源）派生 ⇒ **以后再加池也不会漏** ✓
    ★ 顺序：`all` 在前（全A 先算），其余按 `POOLS` 的声明序 ✓
    """
    return ','.join(['all'] + list(POOLS))


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
TAG_CAL_MIN = 0.30        # 全A通过 = 费后超额 > 0 且 Calmar >= 此值（**日频**口径，§1.19）
# ★★★ 新增（2026-09-14，loop_todo §1.18 用户拍板 B）：**池内 Calmar 下限**
#   修的是一个**判据不对称**（`engine/loop_engine.py` 的 `_okp` vs `_oka`）：
#     全A：`ann_ex > 0` **且** `calmar >= TAG_CAL_MIN(0.30)`   ← 严
#     池内：**只要** `ann_ex > 0`                              ← 松（**完全不卡 Calmar**）
#   ⇒ 于是 `derive_tag` 的 `all3`（"全A 且**所有池都通过** = 真 alpha"）实际只要求"池内超额>0"
#   ⇒ **实测 `F10_1000`**：300 池 calmar **0.0589**、500 池 **0.0233**（都 < `--min_pool_calmar=0.15`）
#     却被标成 **`all3`** ⇒ 而日频复核 300 池**回撤 −41%**、500 池超额仅 +0.41% ⇒ **大中盘段无效**
#   ⇒ 下游按 `all3` 筛"真 alpha"会**误选**。
#   取值 = 与 `--min_pool_calmar` 对齐（0.15）—— 让"标签判据"和"入库门槛"用同一个尺子。
TAG_POOL_FLOOR_CAL = 0.15

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
#   实测（`python tools/check_strip_style_pool.py`）：**池库 7/14 = 50%、全A 库已测的 6/11 = 55%
#   是"纯风格因子"** —— 全A 口径 Calmar 看着漂亮（甚至 1.19/1.39），**剥掉市值/成交额后转负**。
#   例：`corr100(mf_s_bqty, mf_x_sell)` 原 1.193 → 剥 **−0.075**。
# ★ 根因是**入库判定漏了一道关**（`--strip_style` 开了记录却没传 `--min_strip_calmar`，
#   后者默认 -1 = 只记录不拦），已修（`tools/run_tracks.py` 加 `--min_strip_calmar=0.15`）。
# ★ 这一档**并列**于 `derive_tag`（**不改** `ok_all`），because：
#   ① 历史标签语义突变会让 journal/文档前后不可比；
#   ② 剥风格结果可能缺失（未开 `--strip_style`）⇒ 需要一个 **'D 未测'** 的诚实档位。
# ★★ 口径（2026-09-14, loop_todo §1.19 ③，用户拍板）：**本组阈值一律是「日频」口径**
#   为什么：期频 `nav=(1+ex).cumprod()` 只在**每换仓期末**打点 ⇒ 漏掉持有期内回撤
#   ⇒ 实测折算比（日/期）中位 **0.928**（A/B 档 31 个），区间 0.741~0.992 ⇒ 回撤普遍被低估。
#   ⇒ 阈值沿用 0.30（因为折比接近 0.93 ⇒ "同等严格度"的新阈值 ≈ 0.28，取 0.30 略严更稳）。
TAG_STRIP_CAL_MIN = 0.30     # 「独立有效」档（**日频**），与 TAG_CAL_MIN 对齐（口径一致）
# ★★ 新增（2026-09-14，用户拍板 ②）：**日频回撤上限** —— 光看 Calmar 不够。
#   实测有一批因子 `calmar > 0`（旧判据判"可用"）但**日频回撤 −21%~−35%**：
#     `F03_1000` 期0.064/**日dd −35.3%** · `F11` 0.042/**−23.1%** · `F40` 0.001/**−21.2%`
#   ⇒ 对**真中性增强**（产品端回撤是硬约束）尤其致命 ⇒ 回撤超限**不给 A**（降到 B）。
#   ⚠ 只降档、不判 C —— "回撤大"不等于"是纯风格"，两者是不同的病。
TAG_STRIP_DD_MIN = -0.20

STRIP_DESC = {
    'A': '独立有效（剥风格后**日频** Calmar >= {:.2f}，且**日频**回撤 > {:.2f}）'.format(
        TAG_STRIP_CAL_MIN, TAG_STRIP_DD_MIN),
    'B': '弱独立（剥风格后日频 Calmar 在 0~{:.2f}，或回撤劣于 {:.2f}）'.format(
        TAG_STRIP_CAL_MIN, TAG_STRIP_DD_MIN),
    'C': '**纯风格**（剥掉 lncap+lnamt 后超额/Calmar 转负）⇒ 指数增强不可用',
    'D': '未测（该代没开 `--strip_style`）',
}


def strip_grade(calmar, ann_ex, dd_d=None):
    """剥风格分档（**单一事实源**；引擎、`tools/build_facs.py`、`tools/check_strip_style_pool.py`、
    `tools/build_crosspool_view.py` 全部 import 本函数，避免多处各写一套漂移）。

    :param calmar: 剥风格后的 Calmar
    :param ann_ex: 剥风格后的年化超额
    :param dd_d:   剥风格后的**日频回撤**（可选）。
                   `None` ⇒ **不启用**回撤判据（向后兼容：老调用方行为不变）
    ⚠⚠ **`calmar` / `ann_ex` 必须传「日频」口径**（2026-09-14 起，§1.19 ③ 用户拍板）——
       期频口径漏掉持有期内回撤、回撤被系统性低估（实测折比中位 0.928）。
       参数名不带 `strip_` 前缀正是为了提醒："**传什么口径由调用方负责**"。

    返回 (档位, 说明)：
      **A 独立有效** `calmar >= TAG_STRIP_CAL_MIN` **且**（若给了 `dd_d`）`dd_d > TAG_STRIP_DD_MIN`
      **B 弱独立**   `0 < calmar < TAG_STRIP_CAL_MIN`，**或**日频回撤劣于 `TAG_STRIP_DD_MIN`
      **C 纯风格**   `ann_ex <= 0` 或 `calmar <= 0` ⇒ **剥完就没了/变负**
      **D 未测**     取不到剥风格数据（**宁可标"未测"，绝不臆断**）

    ⚠ 判 `C` 用**两个条件或**：超额转负是最直接的证据；Calmar<=0 是必要补充
      （避免"超额微正但风险调整后为负"漏判）。
    ⚠ **回撤超限只降到 B、不降到 C** —— "回撤大"与"是纯风格"是两种不同的病，混在一起会误导。
    """
    if calmar is None or ann_ex is None:
        return 'D', STRIP_DESC['D']
    try:
        sc, sa = float(calmar), float(ann_ex)
    except (TypeError, ValueError):
        return 'D', STRIP_DESC['D']
    if not (np.isfinite(sc) and np.isfinite(sa)):
        return 'D', STRIP_DESC['D']
    if sa <= 0 or sc <= 0:
        return 'C', STRIP_DESC['C']
    if sc >= TAG_STRIP_CAL_MIN:
        # ★ 回撤上限（2026-09-14 用户拍板 ②）：给了 dd_d 才判定
        if dd_d is not None:
            try:
                _ddd = float(dd_d)
            except (TypeError, ValueError):
                _ddd = None
            if _ddd is not None and np.isfinite(_ddd) and _ddd <= TAG_STRIP_DD_MIN:
                return 'B', STRIP_DESC['B']      # 仅降档，不判 C
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

