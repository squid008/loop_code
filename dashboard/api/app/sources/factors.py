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

from . import core

# 统一字段（面向"因子看板/PG 表"的列）
FACTOR_FIELDS = [
    'code', 'pool', 'gen', 'family', 'summary', 'status',
    'expr', 'calmar', 'stripCalmar', 'grade', 'annEx', 'ic', 'turn',
]

_MD_ROW = re.compile(r'^\|(.+)\|\s*$')
_SEP = re.compile(r'^\|[\s:|-]+\|\s*$')


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
    st = core.load_state(pool)
    return {
        'pool': pool, 'label': core.pool_label(pool), 'found': True,
        'declaredCount': int(m.group(1)) if m else None,   # md 声明（可能落后）
        'count': len(factors),                             # 表格行数（累计，只增不改）
        'stateBank': (st or {}).get('bank_n'),             # ★ 权威：当前有效库
        'stateTested': (st or {}).get('n_tested'),
        'stateFrozen': (st or {}).get('frozen_n'),
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


# ---------------------------------------------------------------- 精选池
def selected():
    """精选池（L3）：`factor_pool_selected.md` 清单 + `loop_strip_style_bank.csv` 的剥风格档。"""
    p = core.docs_path('factor_pool_selected.md')
    txt = core.read_text(p)
    if not txt:
        return {'found': False, 'factors': [], 'gates': [], 'notes': []}
    lines = txt.splitlines()

    # 上方的"须知"要点（> 开头）
    notes = [l.lstrip('> ').strip() for l in lines[:40]
             if l.strip().startswith('>') and len(l.strip()) > 6][:8]

    # 双闸门说明
    gates = []
    for i, l in enumerate(lines):
        if '双闸门' in l and l.startswith('##'):
            for l2 in lines[i + 1:i + 12]:
                if re.match(r'^\d+\.', l2.strip()):
                    gates.append(re.sub(r'^\d+\.\s*', '', l2.strip()))

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
