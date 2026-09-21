# -*- coding: utf-8 -*-
"""因子库：**各池库清单** · **精选池（L3 双闸门）** · **剥风格档** · **池内观测**。

数据源（全部 `docs/`）：
  · `factor_library{,_300,_500,_1000}.md` —— 每池库的「因子总览」表（编号/入库代数/家族/一句话/状态）
  · `factor_pool_selected.md`             —— 精选清单（**双闸门**后，含完整表达式）
  · `loop_strip_style_bank.csv`           —— 剥风格评估口径（`strip_calmar` / `grade`）
  · `loop_pool_obs{,_300,_500,_1000}.csv` —— 池内指标（`ic/calmar/calmar_d/ann_ex/turn/...`）
  · `library_entries.jsonl`                —— ★ 新入库事件日志（**时间/池/代数/编号/公式**，看板「新入库日志」卡）

★ 目标（用户 2026-09-15）：**逐步往「聚宽因子看板」+ PG 数据库靠**
  ⇒ 所以这里已按"**可入库的规整结构**"输出（每行一个因子 + 统一字段名），
    将来接 PG 只需把本模块的 dict 直接 insert ✓
"""
import json
import os
import re

from . import core   # noqa: F401

# 统一字段（面向"因子看板/PG 表"的列）
FACTOR_FIELDS = [
    'code', 'pool', 'gen', 'family', 'summary', 'status',
    'expr', 'calmar', 'stripCalmar', 'grade', 'annEx', 'ic', 'turn',
]

_MD_ROW = re.compile(r'^\|(.+)\|\s*$')
_SEP = re.compile(r'^\|[\s:|-]+\|\s*$')

# ================================================================ 因子明细
# ★★ 2026-09-16 新增（用户之问）：
#   总览表里的"一句话"列是**截断的表达式**（例：`sub(ts_min20(barra_beta), ts_mean60(barra…`），
#   而用户点开一个因子时要看：**完整公式（可复制）· 池标签 · 各项费后指标** ——
#   这些只存在于**明细段**（`### F01 · gen1 入库` 那一段）⇒ 必须解析明细段 ✓
_METRICS_CSV = 'factor_metrics.csv'
# ★★★★★ 2026-09-21（用户："曲线、指标连 20 日一起重算"）—— **20 日口径**的指标表 ✓
#   由 `tools/factor_metrics.py --fwd 20 --out docs/factor_metrics_fwd20.csv` 生成 ✓
#   ⚠ 与 5 日表**列名完全一致**（只是口径不同）⇒ 读法共用 ✓
_METRICS_CSV20 = 'factor_metrics_fwd20.csv'

# ★★★★★ 2026-09-21（用户拍板："标签写法：5、20、双"；"判据：固定 0.624 / 0.701"）
#   —— 列表里的**口径强项标签** ✓
#   判据来源：2026-09-21 全库 62 因子标定（`ai_test/_cmp_gate.py` ✓）：
#     5 日超额 Calmar 中位 **0.624** · 20 日中位 **0.701** ⇒ 各取"中位"作为"该口径下更强"的线 ✓
#   ⚠⚠ 为什么用**固定阈值**而不是"运行时算分位" ✗：
#     分位随库演化**漂移** ⇒ 同一个因子会**无故掉标签/多标签** ✗（用户看到的标签会莫名变化 ✗）
#     固定阈值 = 可复现、可解释、可复核 ✓（与项目既有惯例一致：门槛都写"标定值 + 标定样本" ✓）
#   ⚠ 返回**字符串**（不是数字 ✅ 用户问"纯数字会有 BUG 吗"）：
#     后端给字符串 ⇒ 前端不会做数值比较、也不会拿它当 CSS 类名裸用 ✓（见 `HZN_CLASS` 加前缀 ✓）
_HZN_CAL5 = 0.624
_HZN_CAL20 = 0.701


def _hzn_tag(m5, m20):
    """按超额 Calmar 判"哪个口径下更强" ⇒ `'5'` / `'20'` / `'双'` / `''`（都不突出）✓"""
    a = _num((m5 or {}).get('calmar'))
    b = _num((m20 or {}).get('calmar'))
    if a is None or b is None:
        return ''
    p5, p20 = a >= _HZN_CAL5, b >= _HZN_CAL20
    if p5 and p20:
        return '双'
    if p20:
        return '20'
    if p5:
        return '5'
    return ''


def _detail_blocks(txt):
    """解析 `factor_library*.md` 的明细段 ⇒ `{编号: {expr, sign, family, leaves, skeleton,
    poolTag, poolTagNote, strip, metricsDocText}}`。

    ⚠⚠ 2026-09-16 实测踩坑（**静默失配**）：`core.read_text()` 是「**二进制读 + decode**」⇒
      **保留 `\\r\\n`**；而本函数原来用 `\\n` 写正则 ⇒ 在 Windows 检出的文件上
      **代码块（```）这两条正则直接匹配不到** ⇒ `expr`/`skeleton` 全为空，
      而 `poolTag`/`sign` 那几条（不依赖换行）却正常 ⇒ **界面看着"有信息"，公式却是空的** ✗
      ⇒ 所以：**解析 md 前先统一换行**（并且正则写成 `\\r?\\n` 兜底）✓
    """
    txt = str(txt or '').replace('\r\n', '\n').replace('\r', '\n')
    out = {}
    parts = re.split(r'\n###\s+(F\d+)\s*·\s*', txt)
    for k in range(1, len(parts) - 1, 2):
        code, body = parts[k].strip(), parts[k + 1]
        d = {}
        m = re.search(r'```\r?\n([^\r\n]+)', body)
        d['expr'] = m.group(1).strip() if m else ''
        m = re.search(r'符号\s*`?sign`?[^：:]*[：:]\s*`?(-?\d+)', body)
        d['sign'] = m.group(1) if m else ''
        for key, pat in (
                ('family', r'-\s*家族[：:]\s*([^\n]+)'),
                ('leaves', r'-\s*叶子[：:]\s*([^\n]*)'),
                ('skeleton', r'-\s*骨架[：:]\s*`([^`]+)`'),
        ):
            m = re.search(pat, body)
            d[key] = m.group(1).strip() if m else ''
        m = re.search(r'-\s*池标签[：:]\s*([^\n]+)', body)
        if m:
            raw = m.group(1)
            mt = re.search(r'`([^`]+)`', raw)
            d['poolTag'] = mt.group(1) if mt else ''
            d['poolTagNote'] = re.sub(r'^[^—]*—\s*', '', re.sub(r'[`*]', '', raw)).strip()
        else:
            d['poolTag'], d['poolTagNote'] = '', ''
        m = re.search(r'-\s*剥风格[：:]\s*([^\n]+)', body)
        d['strip'] = m.group(1).strip() if m else ''
        # 归档的费后指标行（可能是老口径 ⇒ 只作参考，面板以"统一重算"表为准）
        m = re.search(r'费后指标[^：]*：([^\n]+)', body)
        d['metricsDocText'] = m.group(1).strip() if m else ''
        out[code] = d
    return out


# ⚠ 只处理"**机器味**"的符号：★/⚠（删除）与 ⇒（换成逗号）。
#   **不要动 `——`** —— 它是**规范的中文破折号**，不是 AI 味 ✗（2026-09-16 实测：曾把它换成 `：`
#   反而把「生成 —— 可随时重建」读成「生成 ： 可随时重建」）
# ★ 2026-09-16：把 `✓ ✗ ❗` 也纳入清洗 —— 它们和 `★ ⚠ ⇒` 同类（都是"机味"装饰符号，
#   在正文里没有语义）⇒ 出口一律去掉 ✓（守门 `_test_ui_quotes.py` 就是这么判的，两边对齐）
_SYM = (('★', ''), ('⚠', ''), ('⇒', '，'), ('・', '·'),
        ('✓', ''), ('✗', ''), ('❗', ''),
        # ⚠ `⚠️` 是 `⚠` + **变体选择符 U+FE0F**（emoji 形态）⇒ 只删 U+26A0 会留个"隐形字符" ✗
        ('\ufe0f', ''))
# ★★ 2026-09-16（用户要求「所有前端文案提示涉及到引号的地方都改改去掉引号」）：
#   引号**一律去掉**（`「」『』“”‘’`）—— 看板是网页，"书名号式"引号是 AI 味的主要来源之一；
#   `docs/*.md` 本身是**技术文档**（保留原风格，两边各司其职）⇒ **只在这里（后端出口）清洗** ✓
#   ⚠ 之前在**出口处漏了这一步** ⇒ 用户在看板上仍看得到引号（而这函数只管 `**` 与反引号）✗
_QM = (('「', ''), ('」', ''), ('『', ''), ('』', ''),
       ('“', ''), ('”', ''), ('‘', ''), ('’', ''))


def _plain_style(s):
    """风格画像：**数值原样透传**，只把口径串过一遍出口清洗 ✓（其余字段是纯数字/名字）"""
    if not s:
        return s
    out = dict(s)
    out['caliber'] = _plain(s.get('caliber'))
    return out


def _plain(s):
    """把「给人看」的文本洗成**纯文本**。

    ★★ 2026-09-16（用户反馈「下游使用须知里面也是各种引号处理一下」）：
      `docs/*.md` 是**技术文档**（Markdown 合理），但它**同时被看板展示**，而浏览器
      **不渲染 Markdown** ⇒ `` `sign` `` 会原样显示成带反引号、`**加粗**` 显示成星号 ✗
      ⇒ 在**后端出口处**统一清洗：去 `**` 与反引号、**去所有引号**、把 `★ ⚠ ⇒ ——` 换成人话标点 ✓
    （md 文件本身保持技术风格，不动 —— 两边各司其职）
    """
    s = str(s or '').replace('**', '')
    s = re.sub(r'`([^`]*)`', r'\1', s)
    for a, b in _SYM + _QM:
        s = s.replace(a, b)
    s = re.sub(r'，+', '，', s)
    s = re.sub(r'\s+', ' ', s)
    return s.strip(' ，：')


def _num(x):
    try:
        v = float(str(x).strip())
        return v
    except Exception:
        return None


def _metrics_table(csv_name=None):
    """读 `docs/factor_metrics.csv`（`tools/factor_metrics.py` 生成的**统一口径**指标表）。

    ★ 为什么要有这张表：引擎在**入库当期**只把"超额"那几项写进 md 明细行，
      **"组合自身"口径（年化/卡玛/夏普/最大回撤）从来没落盘** ⇒ 明细里查不到。
      该表由 `state.bank`（权威）+ 离线重算生成 ⇒ 顺带回答"**哪些编号还在当前库里**" ✓

    ★ 2026-09-21：加 `csv_name` 参数 ⇒ **同一套读法**读 20 日口径表 ✓
      （两张表列名一致 ✓，只有口径不同 ✓ ⇒ 不复制实现、不两处漂移 ✓）
    """
    p = core.docs_path(csv_name or _METRICS_CSV)
    head, rows = core.read_csv_rows(p)
    if not head:
        return {}, None, {'found': False}
    out = {}
    for r in rows:
        d = dict(zip(head, r))
        nm = (d.get('name') or '').strip()
        if not nm:
            continue
        d['_num'] = {k: _num(v) for k, v in d.items()}
        out[nm] = d
    return out, core.mtime_iso(p), {'found': True, 'path': os.path.relpath(p, core.ROOT),
                                    'rows': len(out),
                                    # ★★ 2026-09-17（用户："想看历史编号的费后指标"）：
                                    #   新格式的 CSV 带 **`in_bank` 列**（1=当前库 / 0=已移出的历史编号）
                                    #   ⇒ 可以**直接读**"在不在库"，不再需要"表条数 == 库条数"那条脆弱推断 ✓
                                    'inBankCol': ('in_bank' in [str(x).strip() for x in head])}


def _md_table(lines, header_hint, max_rows=400):
    """从 markdown 行里找表头命中 `header_hint`（任一关键词）的表格 ⇒ `(header, rows)`。

    ★ 2026-09-15 修：原写成 `any(header_hint in c ...)` ⇒ `header_hint` 是 **list**
      ⇒ `TypeError: 'in <string>' requires string as left operand, not list` ✗
      ⇒ 改为逐关键词匹配 ✓
    """
    hints = [header_hint] if isinstance(header_hint, str) else list(header_hint)
    out = []
    head = None
    ncol = 0
    for l in lines:
        s = l.strip()
        if not s:                          # ★ 空行【跳过】——
            continue                       #   ⚠ 原实现遇空行就 `break`，而 `factor_library_1000.md`
                                           #   的表头(L18-19)与数据(L21)之间**正好有一个空行** ⇒ rows=0 ✗
        if not s.startswith('|'):
            if head:                       # 非空且非表格行 ⇒ 才算表格结束
                break
            continue
        if _SEP.match(s):
            continue
        cells = [c.strip() for c in s.strip('|').split('|')]
        if head is None:
            if any(h in c for h in hints for c in cells):
                head = cells
                ncol = len(cells)
            continue
        if len(cells) != ncol:             # ★ 列数不符（通常是后面另一张表）⇒ 结束
            if cells and cells[0] and cells[0] not in ('编号',):
                break
            continue
        out.append(cells)
        if len(out) >= max_rows:
            break
    return head or [], out


def library_entries(limit=50):
    """★ 2026-09-17（用户："我发现又入库了一个新因子，但**找不到什么时候入库的、入的哪个库**"
    ⇒ 要求池状态区加一张"新入库日志"卡片）：

    数据源 = `docs/library_entries.jsonl`（**append-only**，进 git ⇒ 换机器也看得到）：
      · 引擎入库那一刻写（`ts` = **真实时间**，`source='engine'` ✓）
      · 历史条目由 `tools/backfill_library_entries.py` **回填**（时间取自该代引擎日志 mtime，
        `tsSource` 标明是推算的 ✓ —— 推算必须标注来路，不许冒充记录时间 ✗）
    返回**最近 `limit` 条**，并补齐成"库清单里那种因子对象"（`detail`/`metrics`/`inBank`）
    ⇒ 看板可**复用同一个详情弹层** ✓
    """
    p = core.docs_path('library_entries.jsonl')
    txt = core.read_text(p)
    evs = []
    for ln in txt.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            evs.append(json.loads(ln))
        except Exception:
            continue                       # 坏行跳过（不让一行脏数据毁掉整张卡 ✓）
    n_all = len(evs)
    tail = evs[-limit:] if limit and limit > 0 else evs
    libs = {}

    def _lib(pool):
        if pool not in libs:
            libs[pool] = {f['code']: f for f in (library(pool).get('factors') or [])}
        return libs[pool]

    # ★★★ 2026-09-17（用户："新入库日志把那个**已入库、已移出的状态**也加上吧，加在 F06 文字旁边？"）：
    #   三态口径必须与「因子库」页签**完全同源**（同一个 `inBank`）—— 否则同一条编号在两处
    #   会出现两种说法（本项目最忌"一份数据两套口径"）✗
    #   判据优先级：
    #     ① 指标表 CSV 的 `in_bank` 列 —— `--include_history` 之后**连历史编号都写着** ⇒ 覆盖最全 ✓
    #     ② 退回该池库文档那一行带来的 `inBank`（表是老格式 / 这条从没测过指标时）✓
    #     ③ 都拿不到 ⇒ **None** —— "不知道"和"已移出"是两回事，**绝不猜** ✗
    #        （用户看到的「状态未知」= 老实承认判不了，不是"已入库"也不是"已移出" ✓）
    mtab, _mt_mtime, mt_info = _metrics_table()
    _has_ib = bool(mt_info.get('inBankCol'))

    def _inb_of(pool, code, f):
        if not code:
            return None
        nm = code if pool == 'all' else '%s_%s' % (code, pool)
        v = mtab.get(nm)
        if _has_ib and isinstance(v, dict):
            s = str(v.get('in_bank', '')).strip().lower()
            if s in ('0', 'false'):
                return False               # 表里明写"已移出当前库"✓
            if s in ('1', 'true'):
                return True
        if isinstance(f, dict) and f.get('inBank') is not None:
            return bool(f['inBank'])
        return None

    out = []
    for e in reversed(tail):               # ★ 倒序：最新的在最上面 ✓
        pool = e.get('pool') or 'all'
        f = _lib(pool).get(e.get('code')) or {}
        row = dict(e)
        for k in ('detail', 'metrics', 'status'):
            if k in f and k not in row:
                row[k] = f[k]
        # ★ 每条都**显式**给三态（True 在库 / False 已移出 / None 判不了），交给前端原样显示 ✓
        row['inBank'] = _inb_of(pool, e.get('code'), f)
        # 库清单里的 `summary`（一句话，出口已清洗 ✓）优先；事件里的是入库时的原始值 ✓
        row['summary'] = f.get('summary') or _plain(e.get('oneLiner') or '')
        row['family'] = f.get('family') or _plain(e.get('family') or '')
        row['expr'] = f.get('expr') or e.get('expr') or ''
        row['inLibrary'] = bool(f)          # 这条编号今天还在库文档里吗（≠ 在有效库，见 inBank ✓）
        out.append(row)
    return {'count': n_all, 'limit': limit, 'entries': out,
            # ⚠ 这段会**原样显示在看板上**（鼠标提示）⇒ 一律自然语言 + 普通标点 ✓
            #   （不许 `**` / 反引号 / 引号 —— 有 `_test_ui_quotes` 与 `_test_ai_tone` 两道守门 ✗）
            'note': ('时间取自引擎入库那一刻（source=engine）；历史条目另有 tsSource 说明是推算'
                     '（该代引擎日志的写入时间，或该池库文档最后修改时间）')}


def library(pool):
    """单池因子库清单（读 `factor_library[_<池>].md`）。"""
    p = core.docs_path('factor_library%s.md' % core.suffix(pool))
    txt = core.read_text(p)
    if not txt:
        return {'pool': pool, 'label': core.pool_label(pool), 'found': False, 'factors': []}
    lines = txt.splitlines()
    m = re.search(r'当前\s*\**\s*(\d+)\s*个入库', txt)
    head, rows = _md_table(lines, ['编号'])

    def gi(name):
        for i, c in enumerate(head):
            if name and name in c:
                return i
        return None

    i_code, i_gen = gi('编号'), gi('入库代数')
    i_fam, i_sum, i_st = gi('家族'), gi('一句话'), gi('状态')
    factors = []
    for r in rows:
        if i_code is None or len(r) <= i_code:
            continue
        code = r[i_code].strip()
        if not code or code in ('编号',):
            continue
        factors.append({
            'code': code,
            'pool': pool,
            'gen': (r[i_gen].strip() if i_gen is not None and len(r) > i_gen else ''),
            'family': (r[i_fam].strip() if i_fam is not None and len(r) > i_fam else ''),
            # ★ 2026-09-16：md 单元格**原样渲染在看板上** ⇒ 出口清洗（`**` / `★ ⚠ ⇒ ✓ ✗` / 引号）✓
            'summary': _plain(r[i_sum].strip() if i_sum is not None and len(r) > i_sum else ''),
            'status': _plain(r[i_st].strip() if i_st is not None and len(r) > i_st else ''),
            'expr': '',
        })
    # ★★★ 口径对照（2026-09-15 发现「**三个数字都不一样**」，用户最在意的"两处打架"）：
    #   · `mdTableRows`  = 本 md 的「因子总览」表行数 ⇒ **累计入库编号**（该文件自己写着"**只增不改**"）
    #   · `mdDeclared`   = md 里「当前 N 个入库」⇒ 引擎同步时的**快照，可能落后**
    #   · `stateBank`    = `engine/loop_state[_<池>].pkl` 的 `bank` 长度 ⇒ ★ **当前有效库（权威）**
    #   实测（2026-09-15）: 300 → 3 / 2 / 2 · 500 → 5 / 3 / 3 · 1000 → 10 / 4 / 5
    #   ⇒ ★ 前端展示**以 `stateBank` 为准**，并把另两个作为"口径说明"一并给出 ✓
    # ★★ 2026-09-16：把**明细段**（完整公式/池标签/符号/骨架）与**统一口径指标表**接到每个因子上
    det = _detail_blocks(txt)
    mtab, mt_mtime, mt_info = _metrics_table()
    # ★★★★★ 2026-09-21（用户："曲线、指标连 20 日一起重算"）⇒ **同时读 20 日口径表** ✓
    #   （两张表列名一致 ✓ 只有口径不同 ⇒ 共用同一个读法 ✓）
    mtab20, mt20_mtime, mt20_info = _metrics_table(_METRICS_CSV20)
    st = core.load_state(pool)
    bank_n = (st or {}).get('bank_n')
    _names = {f['code'] if pool == 'all' else '%s_%s' % (f['code'], pool) for f in factors}
    # ★ 指标表里**属于本池**的条目（按 CSV 的 `pool` 列统计 —— 比按名字匹配更稳：
    #   库里可能有"没进库文档、因而没有 F 编号"的因子，它叫 `X<hash>`，名字对不上但确实属于本池）✓
    _mt_pool = {nm: v for nm, v in mtab.items() if (v.get('pool') or 'all') == pool}
    # ★★ 2026-09-17：CSV 现在**显式带 `in_bank` 列** ⇒ 优先读它（老格式没有 ⇒ 回退旧推断）✓
    _has_ib = bool(mt_info.get('inBankCol'))

    def _inb(nm):
        if _has_ib:
            return str((mtab.get(nm) or {}).get('in_bank', '')).strip() not in ('0', 'false', 'False')
        return nm in mtab
    _measured = sum(1 for nm in _names if _inb(nm))          # = 本池**在库且已测**的条数
    _nhist = sum(1 for nm, v in _mt_pool.items() if _has_ib and not _inb(nm))
    # ★★ `inBankKnown` = 敢不敢判"在不在库"：
    #   · **新格式**（有 `in_bank` 列）⇒ 表里直接写着 ⇒ 一定敢 ✓（这正是加这一列的原因）
    #   · **老格式** ⇒ 只能靠"表对本池**条数恰好等于当前有效库**"来推；
    #     ⚠⚠ 否则会**误判**：表没跑完时**所有行都会被标成「历史」** ✗
    #     （2026-09-16 实测：表里只有 2 条全A 记录时，`/api/library/1000` 的 10 行全变「历史」）
    inbank_known = (bool(mt_info.get('found')) and _has_ib) or \
        (bool(mt_info.get('found')) and not _has_ib and bank_n is not None
         and len(_mt_pool) == bank_n)
    # ★★ 「**在库里、但库文档没有编号**」的因子（2026-09-16 实证：1000 池有 1 个，gen11 入库）
    #   ⇒ 成因 = §8.44 那个 `_lib_sync` 静默跳过的 bug 期间留下的缺口 ⇒ **如实展示，不隐藏** ✓
    orphans = [{'name': nm, 'expr': (v.get('expr') or ''),
                'ann_ex': (v.get('_num') or {}).get('ann_ex'),
                'metrics': (v.get('_num') or {})}
               for nm, v in sorted(_mt_pool.items()) if nm not in _names]
    for f in factors:
        code = f['code']
        nm = code if pool == 'all' else '%s_%s' % (code, pool)
        d = det.get(code) or {}
        f['expr'] = d.get('expr') or f['expr']          # ★ 完整公式（总览列是被截断的）
        f['detail'] = {k: d.get(k, '') for k in
                       ('sign', 'family', 'leaves', 'skeleton', 'poolTag')}
        for k in ('poolTagNote', 'strip', 'metricsDocText'):     # 散文类 ⇒ 出口处清洗
            f['detail'][k] = _plain(d.get(k, ''))
        f['metrics'] = (mtab.get(nm) or {}).get('_num') or {}
        # ★★★★★ 2026-09-21（用户拍板："标签写法：5、20、双"·"判据：固定 0.624 / 0.701"·
        #   "曲线、指标连 20 日一起重算"）—— 三项一起接上 ✓
        #   ① `metrics20` ⇒ 详情页「口径切换」切到 20 日时**整块指标**换它 ✓（前端不用自己算 ✓）
        #   ② `cal20/ic20/turn20` ⇒ 列表**不展开也能直接用** ✓（免得前端去翻 metrics20 ✓）
        #   ③ `hzn` ⇒ 列表的口径标签（'5' / '20' / '双' / '' ✓ 规则见 `_hzn_tag` ✓）
        _m20 = (mtab20.get(nm) or {}).get('_num') or {}
        f['metrics20'] = _m20
        f['cal20'] = _m20.get('calmar')
        f['ic20'] = _m20.get('ic')
        f['turn20'] = _m20.get('turn')
        f['hzn'] = _hzn_tag(f['metrics'], _m20)
        # ★★★ 2026-09-17（用户："中证500 F06 的方向 sign 为啥是 —？其他因子要么 1 要么 -1，是不是有问题？"）：
        #   不是标签贴错，也**不是 bug**：那条因子的 md 明细段里写的**就是**
        #   「符号 sign：**未记录**（缺失时不臆造，见 roadmap §8.45 铁律）」⇒ 解析出来是空 ⇒ 前端显示 — ✗
        #   （当年引擎确实没拿到该方向 ⇒ md 这样写是**诚实**的 ✓）
        #   但**指标表里有真值**：`factor_metrics` 的 sign 是「重算 IC 与库记录 IC 对齐」求出来的 ✓
        #   语义完全一致（都表示"因子值须乘它才是越大越好"✓）⇒ 空的时候**退回指标表**，
        #   并用 `signFrom` 标出来路 —— **绝不冒充成"库文档记录"** ✗
        if not f['detail'].get('sign'):
            _sg = (f['metrics'] or {}).get('sign')
            if _sg is not None:
                try:
                    f['detail']['sign'] = str(int(_sg))
                    f['detail']['signFrom'] = '重算指标表'
                except (TypeError, ValueError):
                    pass
        # 三态：True 在库 / False 已移出 / None 未知（表不完整或没跑）✓
        f['inBank'] = (_inb(nm) if (inbank_known and nm in mtab) else
                       (False if inbank_known else None))
    return {
        'pool': pool, 'label': core.pool_label(pool), 'found': True,
        'declaredCount': int(m.group(1)) if m else None,   # md 声明（可能落后）
        'count': len(factors),                             # 表格行数（累计，只增不改）
        'stateBank': (st or {}).get('bank_n'),             # ★ 权威：当前有效库
        'stateTested': (st or {}).get('n_tested'),
        'stateFrozen': (st or {}).get('frozen_n'),
        'metricsFound': mt_info.get('found'),
        'metricsInfo': mt_info,
        'metricsMtime': mt_mtime,
        # ★ 2026-09-21：20 日口径表的**元信息**（前端要判"跑没跑过 20 日" ✓）
        'metrics20Info': mt20_info,
        'metrics20Mtime': mt20_mtime,
        # `metricsMeasured` = **本池在库且已测**的条数（与 `stateBank` 比才说明"表跑完了没"）✓
        #   ⚠ 不能再用 `len(_mt_pool)` —— 表里加进历史编号后条数会**大于**库大小 ⇒ 误报"没跑完" ✗
        'metricsMeasured': _measured,
        # ★ 顺带告诉前端：表里还有多少个**已移出的历史编号**也有指标（它们只有 `--include_history` 才算）✓
        'metricsHistory': _nhist,
        'inBankKnown': inbank_known,
        'orphans': orphans,
        'caliber': {
            'authoritative': 'stateBank',
            'mdTableRows': len(factors),
            'mdTableMeans': '累计入库编号（该文件自己声明只增不改）',
            'mdDeclared': int(m.group(1)) if m else None,
            'mdDeclaredMeans': '引擎同步快照，可能落后于 state',
            'stateBank': (st or {}).get('bank_n'),
            'stateBankMeans': '当前有效库（引擎实际在用的对照集）',
        },
        'path': os.path.relpath(p, core.ROOT),
        'mtime': core.mtime_iso(p),
        'factors': factors,
    }


def all_libraries():
    return [library(k) for k in core.POOL_KEYS]


# ================================================================ 因子曲线
# ★★ 2026-09-16（用户要求：指标下面加曲线图）：
#   曲线**离线**由 `tools/factor_curves.py` 预算好（现算一次 = 一次完整回测 ≈ 10s ⇒ 点一下卡十秒 ✗），
#   这里只**读文件 + 下采样**（保两端等步长）⇒ 响应体小、前端画得快 ✓
CURVE_DIR = 'factor_curves'
# ★★★★★ 2026-09-21（用户："曲线、指标连 20 日一起重算"）：**换口径 = 换目录** ✓
#   20 日曲线由 `tools/factor_curves.py --fwd=20 --out_dir=factor_curves_fwd20` 预算 ✓
#   （⚠ 约定：目录名 = 基础名 + `_fwd<N>`；`fwd=5` 用基础目录 ✓ 即老数据零改动 ✓）
def _curve_dir(fwd=5):
    f = int(fwd or 5)
    return CURVE_DIR if f == 5 else '%s_fwd%d' % (CURVE_DIR, f)


def _down(seq, k):
    """等步长抽点（**保两端**）⇒ 返回 `(新序列, 索引表)`；长度 ≤ k 时原样返回。"""
    n = len(seq or [])
    if n == 0:
        return [], []
    if n <= k:
        return list(seq), list(range(n))
    idx = sorted({int(round(i * (n - 1) / float(k - 1))) for i in range(k)})
    out = []
    for i in idx:
        v = seq[i]
        out.append(round(float(v), 6) if isinstance(v, (int, float)) and v is not None else None)
    return out, idx


def curves(name, max_pts=700, fwd=5):
    """读 `docs/factor_curves[_fwd<N>]/<name>.json` ⇒ 下采样后的曲线数据（前端直接画）。

    ★★★★★ 2026-09-21（用户："曲线、指标连 20 日一起重算"）—— 加 `fwd`（调仓周期口径）✓
      ⇒ 详情页可在 **5 日 / 20 日** 之间切，切完**所有曲线**（净值/剥风格/动态暴露）都换 ✓
      ⚠ `fwd=5` = 老路径（基础目录 ✓ 零改动）；其它口径 = `_fwd<N>` 目录 ✓
    """
    _f = int(fwd or 5)
    rel = os.path.join(_curve_dir(_f), '%s.json' % name)
    p = core.docs_path(rel)
    txt = core.read_text(p)
    if not txt:
        return {'found': False, 'name': name, 'fwd': _f, 'path': rel.replace('\\', '/'),
                'hint': '跑一次 python tools/factor_curves.py %s 生成（离线算，不影响看板性能）'
                        % ('' if _f == 5 else '--fwd=%d --out_dir=%s' % (_f, _curve_dir(_f)))}
    try:
        import json as _json
        d = _json.loads(txt)
    except Exception as e:
        return {'found': False, 'name': name, 'err': repr(e)}

    def _nums(seq):
        return [None if v is None else float(v) for v in (seq or [])]

    d_dates, _ = _down(d.get('d_dates') or [], max_pts)
    # ★ 净值曲线用**对数感**更好的方式？—— 不：直接给净值，前端按需切换线性/对数
    daily = {
        'dates': d_dates,
        'navT': _down(_nums(d.get('nav_t')), max_pts)[0],
        'navM': _down(_nums(d.get('nav_m')), max_pts)[0],
        'navE': _down(_nums(d.get('nav_e')), max_pts)[0],
        'ddE': _down(_nums(d.get('dd_e')), max_pts)[0],
        'ddT': _down(_nums(d.get('dd_t')), max_pts)[0],
    }
    r_dates, _ = _down(d.get('r_dates') or [], max_pts)
    period = {
        'dates': r_dates,
        'ic': _down(_nums(d.get('ic')), max_pts)[0],
        'rankIc': _down(_nums(d.get('rank_ic')), max_pts)[0],
        'decile': [_down(_nums(x), max_pts)[0] for x in (d.get('decile') or [])],
        'ls': _down(_nums(d.get('ls')), max_pts)[0],
        'turn': _down(_nums(d.get('turn_series')), max_pts)[0],
    }
    st = d.get('strip') or None
    strip = None
    if st:
        sd, _ = _down(st.get('dates') or [], max_pts)
        strip = {'dates': sd,
                 'navs': {k: _down(_nums(v), max_pts)[0] for k, v in (st.get('navs') or {}).items()},
                 'calmars': st.get('calmars') or {},
                 # ★ 口径串会**原样显示在看板上** ⇒ 出口处同样清洗 ✓
                 'caliber': _plain(st.get('caliber'))}
    # ★★★★★ 2026-09-20（用户："图出来了，但是风格暴露的时序图怎么没有呢？"）
    #   ⇒ **真因就在这个函数** ✗：它把响应拼成**固定白名单** ⇒ 文件里明明有 `expo`（418 期 · 11 风格 ✓）
    #     却**没被透传** ⇒ 前端 `c.expo` 永远是 undefined ⇒ 那张图自然不出现 ✗
    #   （⚠ 与我早先的判断不同：**不是数据、不是打包、不是前端渲染** ✓ —— 是这一层过滤 ✓）
    ex = d.get('expo') or None
    expo = None
    if ex:
        ed, _ = _down(ex.get('dates') or [], max_pts)
        expo = {'dates': ed,
                'styles': list(ex.get('styles') or []),
                'series': {k: _down(_nums(v), max_pts)[0]
                           for k, v in (ex.get('series') or {}).items()},
                # ★ 中性线 = 0（Barra 原生值口径 ✓）；口径串照出口规矩清洗 ✓
                'neutral': float(ex.get('neutral') or 0.0),
                'caliber': _plain(ex.get('caliber'))}
    return {
        'found': True, 'name': d.get('name') or name, 'pool': d.get('pool'),
        # ★ 2026-09-21：把**生效的口径**回给前端 ✓（否则前端不知道自己看的是 5 日还是 20 日 ✗）
        'fwd': _f,
        'expr': d.get('expr'), 'sign': d.get('sign'), 'gen': d.get('gen'),
        'start': d.get('start'), 'end': d.get('end'), 'n_rebal': d.get('n_rebal'),
        'cost': d.get('cost'), 'window': d.get('window'),
        # ★★ 2026-09-16（用户："t 用 **AR(1) 有效样本量**校正…这还有引号啊"）：
        #   这个口径串是**离线 JSON 里生成**的、被前端**原样渲染** ⇒ 必须在出口清洗
        #   （离线数据可能是老版本生成的 ⇒ 不能只改生成端，出口这层必须有 ✓）
        'caliber': _plain(d.get('caliber')), 'path': rel.replace('\\', '/'),
        # ★ 风格相关性画像（2026-09-16）：数值原样透传，但**口径串要清洗** ✓
        'style': _plain_style(d.get('style')),
        'mtime': core.mtime_iso(p),
        'daily': daily, 'period': period, 'strip': strip, 'expo': expo,
    }


# ---------------------------------------------------------------- 精选池
def selected():
    """精选池（L3）：`factor_pool_selected.md` 清单 + `loop_strip_style_bank.csv` 的剥风格档。"""
    p = core.docs_path('factor_pool_selected.md')
    txt = core.read_text(p)
    if not txt:
        return {'found': False, 'factors': [], 'gates': [], 'notes': []}
    lines = txt.splitlines()

    # 上方的"须知"要点（> 开头）—— ★ 出口处清洗成纯文本（浏览器不渲染 Markdown）
    notes = [_plain(l.lstrip('> ').strip()) for l in lines[:40]
             if l.strip().startswith('>') and len(l.strip()) > 6][:8]

    # 双闸门说明（★ 连**缩进的子条目**一起收 —— 否则只剩标题、解释全丢 ✗）
    gates = []
    for i, l in enumerate(lines):
        if '双闸门' in l and l.startswith('##'):
            for l2 in lines[i + 1:i + 30]:
                s2 = l2.strip()
                if not s2:
                    continue
                if s2.startswith('##'):                 # 下一节 ⇒ 停
                    break
                m_num = re.match(r'^\d+\.\s*(.+)', s2)
                m_sub = re.match(r'^[-–*]\s+(.+)', s2)
                if m_num:
                    gates.append(_plain(m_num.group(1)))
                elif m_sub and gates:                   # 子条目接着上一条
                    gates.append('· ' + _plain(m_sub.group(1)))

    head, rows = _md_table(lines, ['剥风格档'])
    i_no, i_code = (0 if head and '#' in head[0] else None), None
    for i, c in enumerate(head):
        if '因子' in c:
            i_code = i
    i_grade, i_sc = None, None
    for i, c in enumerate(head):
        if '剥风格档' in c:
            i_grade = i
        elif '剥Calmar' in c or ('Calmar' in c and '原' not in c):
            i_sc = i
    i_expr = None
    for i, c in enumerate(head):
        if '表达式' in c:
            i_expr = i
    factors = []
    for r in rows:
        if i_code is None or len(r) <= i_code:
            continue
        code = re.sub(r'[`*]', '', r[i_code]).strip()
        if not code or code in ('因子',):
            continue
        factors.append({
            'code': code,
            'pool': code.split('_')[1] if '_' in code else 'all',
            'grade': _plain(re.sub(r'[`*]', '', r[i_grade]).strip()
                            if i_grade is not None and len(r) > i_grade else ''),
            # ★★ 2026-09-16（实测残留）：md 里剥风格 Calmar 写成 `**1.228**` ⇒ 原来**原样**返回 ⇒
            #   前端只好自己 `replace(/\*/g,'')` 遮丑 ✗ ⇒ 出口清洗掉 `**` ✓（前端那层留着也无害）
            'stripCalmar': _plain(r[i_sc].strip() if i_sc is not None and len(r) > i_sc else ''),
            'expr': (re.sub(r'[`*]', '', r[i_expr]).strip() if i_expr is not None and len(r) > i_expr else ''),
            # ★★★★★ 2026-09-21（用户："精选池那里还只有 A 标签，没有 5、20、双标签"）——
            #   精选池的 `hzn` / `metrics20` **不在这里自己算** ✗：
            #   下面的联表步会从 `library(pool)` 的行里**照抄** ⇒ 阈值仍然只有一处 ✓
            #   （占位给空值 ⇒ 键恒定存在，前端不用判 undefined ✓）
            'hzn': '', 'metrics20': {},
        })
    # ★★ 2026-09-16（用户要求「**精选池也要加详情按钮**」）：把各池库文档的**明细**（完整公式/池标签/sign/叶子）
    #   与**统一口径指标表**按因子名 join 进精选条目 ⇒ 前端可复用同一个「因子详情」弹层 ✓
    idx = {}
    for pk in core.POOL_KEYS:
        try:
            lb = library(pk)
        except Exception:
            continue
        for f2 in lb.get('factors') or []:
            nm = f2['code'] if pk == 'all' else '%s_%s' % (f2['code'], pk)
            idx[nm] = f2
        for o in lb.get('orphans') or []:          # 库里在、文档无编号的因子也放进来（可查详情）
            idx.setdefault(o['name'], {'code': o['name'], 'pool': pk, 'gen': '',
                                       'family': '', 'summary': '', 'status': '',
                                       'expr': o.get('expr') or '', 'detail': {},
                                       'metrics': o.get('metrics') or {}, 'inBank': True})
    for f in factors:
        f2 = idx.get(f['code']) or {}
        f['expr'] = f2.get('expr') or f['expr']          # ★ 用**完整公式**（精选表里本来就完整，双保险）
        f['detail'] = f2.get('detail') or {}
        f['metrics'] = f2.get('metrics') or {}
        # ★★★★★ 2026-09-21（用户："精选池那里还只有 A 标签，没有 5、20、双标签"）：
        #   这两项**跟着库表走**（`library()` 里算好的 ✓）⇒ 口径判定**只有一处实现** ✓
        #   ＋ `metrics20` 让精选池里点「详情」也能用**口径开关** ✓
        f['metrics20'] = f2.get('metrics20') or {}
        f['hzn'] = f2.get('hzn') or ''
        f['inBank'] = f2.get('inBank')
        f['pool'] = f2.get('pool') or f['pool']
    return {
        'found': True,
        'path': os.path.relpath(p, core.ROOT),
        'mtime': core.mtime_iso(p),
        'count': len(factors),
        'factors': factors,
        'gates': gates,
        'notes': notes,
    }


# ---------------------------------------------------------------- 剥风格档（全库）
def strip_bank():
    """`loop_strip_style_bank.csv` ⇒ 每因子剥风格评估（含 grade）。"""
    p = core.docs_path('loop_strip_style_bank.csv')
    head, rows = core.read_csv_rows(p)
    if not head:
        return {'found': False, 'rows': []}
    out = []
    for r in rows:
        d = dict(zip(head, r))
        d['pool'] = d.get('pool') or ('all')
        out.append(d)
    return {'found': True, 'path': os.path.relpath(p, core.ROOT),
            'mtime': core.mtime_iso(p), 'rows': out, 'count': len(out)}


# ---------------------------------------------------------------- 池内观测
def pool_obs(pool, limit=300):
    """`loop_pool_obs[_<池>].csv` ⇒ 最近的池内指标（倒序截断）。"""
    p = core.docs_path('loop_pool_obs%s.csv' % core.suffix(pool))
    head, rows = core.read_csv_rows(p)
    if not head:
        return {'found': False, 'rows': [], 'columns': []}
    rows = rows[-limit:]
    out = [dict(zip(head, r)) for r in rows]
    return {'found': True, 'path': os.path.relpath(p, core.ROOT),
            'mtime': core.mtime_iso(p), 'columns': head,
            'total': len(rows), 'rows': out}


# ---------------------------------------------------------------- 扁平化（面向 PG）
def flatten_for_db():
    """把"各池库"展平成**统一字段**的记录列表 —— 将来可直接 insert 到 PG。"""
    recs = []
    bank = {(r['name']): r for r in strip_bank().get('rows', [])}
    for lib in all_libraries():
        for f in lib['factors']:
            key = f['code'] if f['pool'] == 'all' else '%s_%s' % (f['code'], f['pool'])
            b = bank.get(key) or bank.get(f['code']) or {}
            recs.append({
                'code': f['code'], 'pool': f['pool'], 'gen': f['gen'],
                'family': f['family'], 'summary': f['summary'], 'status': f['status'],
                'expr': b.get('expr', ''), 'calmar': b.get('calmar', ''),
                'stripCalmar': b.get('strip_calmar', ''), 'grade': b.get('grade', ''),
                'annEx': b.get('ann_ex', ''), 'ic': b.get('ic', ''),
                'turn': b.get('turn', ''),
            })
    return recs
