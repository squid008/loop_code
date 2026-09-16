# -*- coding: utf-8 -*-
"""因子库：**各池库清单** · **精选池（L3 双闸门）** · **剥风格档** · **池内观测**。

数据源（全部 `docs/`）：
  · `factor_library{,_300,_500,_1000}.md` —— 每池库的「因子总览」表（编号/入库代数/家族/一句话/状态）
  · `factor_pool_selected.md`             —— 精选清单（**双闸门**后，含完整表达式）
  · `loop_strip_style_bank.csv`           —— 剥风格评估口径（`strip_calmar` / `grade`）
  · `loop_pool_obs{,_300,_500,_1000}.csv` —— 池内指标（`ic/calmar/calmar_d/ann_ex/turn/...`）

★ 目标（用户 2026-09-15）：**逐步往「聚宽因子看板」+ PG 数据库靠**
  ⇒ 所以这里已按"**可入库的规整结构**"输出（每行一个因子 + 统一字段名），
    将来接 PG 只需把本模块的 dict 直接 insert ✓
"""
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
_SYM = (('★', ''), ('⚠', ''), ('⇒', '，'), ('・', '·'))
# ★★ 2026-09-16（用户要求「所有前端文案提示涉及到引号的地方都改改去掉引号」）：
#   引号**一律去掉**（`「」『』“”‘’`）—— 看板是网页，"书名号式"引号是 AI 味的主要来源之一；
#   `docs/*.md` 本身是**技术文档**（保留原风格，两边各司其职）⇒ **只在这里（后端出口）清洗** ✓
#   ⚠ 之前在**出口处漏了这一步** ⇒ 用户在看板上仍看得到引号（而这函数只管 `**` 与反引号）✗
_QM = (('「', ''), ('」', ''), ('『', ''), ('』', ''),
       ('“', ''), ('”', ''), ('‘', ''), ('’', ''))


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


def _metrics_table():
    """读 `docs/factor_metrics.csv`（`tools/factor_metrics.py` 生成的**统一口径**指标表）。

    ★ 为什么要有这张表：引擎在**入库当期**只把"超额"那几项写进 md 明细行，
      **"组合自身"口径（年化/卡玛/夏普/最大回撤）从来没落盘** ⇒ 明细里查不到。
      该表由 `state.bank`（权威）+ 离线重算生成 ⇒ 顺带回答"**哪些编号还在当前库里**" ✓
    """
    p = core.docs_path(_METRICS_CSV)
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
                                    'rows': len(out)}


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
            'summary': (r[i_sum].strip() if i_sum is not None and len(r) > i_sum else ''),
            'status': (r[i_st].strip() if i_st is not None and len(r) > i_st else ''),
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
    st = core.load_state(pool)
    bank_n = (st or {}).get('bank_n')
    _names = {f['code'] if pool == 'all' else '%s_%s' % (f['code'], pool) for f in factors}
    # ★ 指标表里**属于本池**的条目（按 CSV 的 `pool` 列统计 —— 比按名字匹配更稳：
    #   库里可能有"没进库文档、因而没有 F 编号"的因子，它叫 `X<hash>`，名字对不上但确实属于本池）✓
    _mt_pool = {nm: v for nm, v in mtab.items() if (v.get('pool') or 'all') == pool}
    _measured = sum(1 for nm in _names if nm in mtab)
    # ★★ `inBankKnown` = 「指标表对本池**条数恰好等于当前有效库**」——
    #   只有这时才敢用"不在表里"推断"已移出库"。
    #   ⚠⚠ 否则会**误判**：表还没跑完（或只跑了一部分）时，**所有行都会被标成「历史」** ✗
    #   （2026-09-16 实测：表里只有 2 条全A 记录时，`/api/library/1000` 的 10 行全变「历史」）
    inbank_known = (bool(mt_info.get('found')) and bank_n is not None
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
        f['inBank'] = ((nm in mtab) if inbank_known else None)   # 三态：True/False/None(未知)
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
        'metricsMeasured': len(_mt_pool),
        'inBankKnown': inbank_known,
        'orphans': orphans,
        'caliber': {
            'authoritative': 'stateBank',
            'mdTableRows': len(factors),
            'mdTableMeans': '累计入库编号（该文件声明"只增不改"）',
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


def curves(name, max_pts=700):
    """读 `docs/factor_curves/<name>.json` ⇒ 下采样后的曲线数据（前端直接画）。"""
    rel = os.path.join(CURVE_DIR, '%s.json' % name)
    p = core.docs_path(rel)
    txt = core.read_text(p)
    if not txt:
        return {'found': False, 'name': name, 'path': rel.replace('\\', '/'),
                'hint': '跑一次 python tools/factor_curves.py 生成（离线算，不影响看板性能）'}
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
                 'caliber': st.get('caliber')}
    return {
        'found': True, 'name': d.get('name') or name, 'pool': d.get('pool'),
        'expr': d.get('expr'), 'sign': d.get('sign'), 'gen': d.get('gen'),
        'start': d.get('start'), 'end': d.get('end'), 'n_rebal': d.get('n_rebal'),
        'cost': d.get('cost'), 'window': d.get('window'),
        'caliber': d.get('caliber'), 'path': rel.replace('\\', '/'),
        # ★ 风格相关性画像（2026-09-16）：逐期截面 Spearman 的统计量，量小（几百个数）⇒ 原样透传
        'style': d.get('style'),
        'mtime': core.mtime_iso(p),
        'daily': daily, 'period': period, 'strip': strip,
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
            'grade': (re.sub(r'[`*]', '', r[i_grade]).strip() if i_grade is not None and len(r) > i_grade else ''),
            'stripCalmar': (r[i_sc].strip() if i_sc is not None and len(r) > i_sc else ''),
            'expr': (re.sub(r'[`*]', '', r[i_expr]).strip() if i_expr is not None and len(r) > i_expr else ''),
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
