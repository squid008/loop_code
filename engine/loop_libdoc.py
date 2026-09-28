# -*- coding: utf-8 -*-
"""loop_libdoc.py — **因子库文档 + 入库事件日志**（2026-09-28 从 `loop_persist.py` 拆出 · `loop_todo §1.36/§1.37 ②`）
========================================================================================================
## 为什么拆（两条硬指标同时逼出来的 ✓）

1. `_lib_sync()` 改前 **186 行** ✗ —— 违 R1（函数 ≤120 行，见 `docs/maintainability.md`）；
2. `loop_persist.py` 改前 **796 行**，离 R2 线（文件 ≤800）**只剩 4 行** ✗✗
   ⇒ **在位内拆 `_lib_sync` 必然把文件顶过 800 线** ✗（拆出来的函数名/文档/返回都要占行 ✓）
   ⇒ 只能把「库文档」这一簇**整体搬成单一职责模块** ✓（与 `v1.25.x` 拆 `loop_l1/loop_l2`、
     `v1.27.0` 拆 `loop_critic_rules` 同一套路 ✓）。

## 职责（4 个名字，都是"库文档"这一件事 ✓）

· `_mk_library_skeleton`（建骨架，**必须含三个锚点** ✓）· `_tag_desc`（池标签中文含义，转发 `loop_pools` ✓）
· `append_library_entries`（追加 `docs/library_entries.jsonl` —— 看板"新入库日志"卡片读它 ✓）
· `_lib_sync`（本代入库因子同步进 `factor_library*.md` + 落事件 ✓，拆成 `_lib_rows`/`_lib_insert_md` ✓）

## 依赖方向（★ 单向：谁都不反向依赖本模块）

只依赖**叶子模块**：`loop_paths`（`_P.LIBRARY`/`_P.LIB_ENTRIES`/`_P.MINE_POOL` 一律**运行时取** ✓）·
`loop_expr.skeleton` · `cost_presets.cost_label` · `loop_pools.tag_desc/TAG_STRIP_DD_MIN`（惰性 import ✓）
⇒ **不 import `loop_persist`、不 import `loop_engine`** ✓ ⇒ 无环 ✓（与 `loop_persist` 同一条纪律 ✓）。

## ⚠ 两个"不许动"（动了就静默坏事 ✗）

1. **`loop_engine` 顶部必须继续 re-export 这 4 个名字** ✗ —— `tools/horizon_admit_write.py`
   与 `tools/backfill_library_pool.py` 走的是 `LE._lib_sync` / `LE._mk_library_skeleton` ✓，
   删掉那行 import 会让两个工具**静默失联**（AttributeError 是好的，静默跳过才可怕 ✗）。
2. **三个 md 锚点**（`> 当前 **N 个入库**` / `## 因子明细` / `## 相关文件导航`）与
   **总览表固定 5 列** ✗ —— 本文件 append-only ⇒ 加列会让**历史行全部错位**（§8.30 同一个坑 ✓）。
   ⇒ 新信息（池标签 / 剥风格 / `sign` / 口径 / 来源）**一律只写明细块** ✓。
"""
import io
import json
import os
import re
import time

import numpy as np

import loop_paths as _P
from loop_expr import skeleton
from cost_presets import cost_label


def _tag_desc(tag):
    """池标签的中文含义（转发到单一事实源 loop_pools.tag_desc）。"""
    import loop_pools as _lp
    return _lp.tag_desc(tag)


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


# ★★★ 2026-09-15 修（P0-2 重构时被"名字封闭性检查"照出来的**潜伏 bug**）——
#   为什么 `_lib_rows` 里必须**真的** `import loop_pools as _lp`（⚠ 这段注释是它的说明书 ✓）：
#     · 原先那段用了 `_lp.TAG_STRIP_DD_MIN`，但 `_lp` **没有可解析来源** ——
#       `_tag_desc` 里的 `import loop_pools as _lp` 是**它的局部**，与本段无关 ✗；
#       模块级当时也没有 `_lp`（`dir(loop_engine)` 已确认）✗
#     · ⇒ 一旦 `strip_grades` 带日频回撤（即 `--strip_style` 开过）⇒ **`NameError`** ✗
#     · ★★ 而本簇的契约定的是"任何失败仅告警, 绝不影响入库主流程" ⇒ 该 `NameError` 被 try 吞掉
#       ⇒ **静默失败**：因子库文档不更新，且不报错（正是本项目反复踩的那类坑）✗✗
#     · ⇒ 补上 import（最小修法，零行为变化）✓
#   ★ 2026-09-28（§1.36/§1.37 ②）：本段从 `_lib_sync` 搬进 `_lib_rows` 时，**只把论述注释上移**
#     （token 级逐字相同 ✓）—— 因为 `_lib_rows` 一度 121 行、超 R1 线（120）1 行 ✗；
#     上移注释是本项目**已有的手法**（见 `v1.25.x` 的 "comment hoist only" 提交 ✓）。
def _lib_rows(gen, rows, added_exprs, expr2nd, no, pool_tags, strip_grades, horizon, source):
    """把本代新入库的因子**渲染**成三份产物（**纯渲染**：不读文件、不写文件 ✓）。

    :param rows:   `{expr: 指标行}`（`res` 的逐行字典；只在**有指标**的 expr 上出现 ✓）
    :param no:     本代**首个**可用编号（`F{no:02d}` ✓）
    :return:       `(tbl_rows, det_rows, evs, no)` —— `no` = 用完之后的下一个编号 ✓

    ★ 2026-09-28（`loop_todo §1.36/§1.37 ②`）：从 `_lib_sync` 的 100 行内联循环里**整块搬出** ✓
      —— 正文只改两处：`r = rows.get(expr)` 直接用传入的 `rows` ✓、循环变量 `no` 变参数 ✓。
    """
    import loop_pools as _lp
    tbl_rows, det_rows, evs = [], [], []
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
        #   加列会让历史行全部错位（与 §8.30 的 CSV 同一个坑，见下面 `tbl_rows` 处的注释）。
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
    return tbl_rows, det_rows, evs, no


def _lib_insert_md(txt, add_tbl, add_det, n_total):
    """把新行插进库文档的**三个锚点**处（纯字符串手术：不读文件、不写文件 ✓）。

    ⚠ 单独成函数的理由：这三处判据都很**脆**（表尾最后一条 `| F` / `## 因子明细` 前 /
      `## 相关文件导航` 前），散在 `_lib_sync` 里一旦改错就是"**静默写坏文档**" ✗
      ⇒ 收在一处、连同各自的实录注释一起看 ✓。
    """
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
    return txt


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
                  （与池标签/剥风格/sign 同一处理 ✓ 只写明细块 ✓）。
    ★ 2026-09-28（`loop_todo §1.36/§1.37 ②`）：本函数改前 **186 行** ✗（R1 线 120）
      ⇒ 拆成三段，**本函数只剩编排** ✓：
        · `_lib_rows(...)`      —— 渲染「总览表行 / 明细块 / 入库事件」三份产物（纯渲染 ✓）
        · `_lib_insert_md(...)` —— md 的**三处锚点插入**（纯字符串 ✓）
        · 本函数                —— 读现有编号 → 渲染 → 插锚点 → 落盘 → 事件日志 → 打印 ✓
      ⇒ 行为**逐字不变**：拆出来的两段就是原来那段代码本身，只把"读哪一行指标/编号从几起"
        改成**显式入参**（原来是闭包式地用外层局部变量 ✓）。
    """
    import io
    import re
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
        txt = io.open(_P.LIBRARY, encoding='utf-8').read()
        nos = [int(x) for x in re.findall(r'\bF(\d{2})\b', txt)]
        no = (max(nos) + 1) if nos else 1
        rows = {str(r['expr']): r for _, r in res.iterrows()} if len(res) else {}
        tbl_rows, det_rows, evs, no = _lib_rows(gen, rows, added_exprs, expr2nd, no,
                                                pool_tags, strip_grades, horizon, source)
        if not det_rows:
            return
        txt = _lib_insert_md(txt, '\n'.join(tbl_rows), ''.join(det_rows), n_total)
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
