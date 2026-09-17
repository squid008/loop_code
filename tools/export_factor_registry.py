# -*- coding: utf-8 -*-
"""export_factor_registry.py — 把「各池已入库因子」导出成**机器可读**的 `docs/factor_registry.json`

## 为什么需要它（用户 2026-09-17 之问）

「是不是搞个 json 文件，把各池已入库/丢弃因子的**编号、入库代数、家族、一句话、具体公式**记录在
一个文件里，然后我家里 pull 项目（库是空的）也能自动识别、把因子跑一遍生成 facs 和各种曲线图？」

## 核查结论（现状）

**清单本身早就在 git 里** ✓ —— 各池 `docs/factor_library{_pool}.md`：
  · 「因子总览」表 = `编号 | 入库代数 | 家族 | 一句话 | 状态` ✓
  · 每个因子还有 `### F01 · gen8 入库` 块：**完整公式** + `sign` + 池标签 + 费后指标 + 备注 ✓

**但"pull 回家跑一遍就自动有"不成立** ✗，卡在唯一一个硬缺口：
  `tools/build_facs.py` / `factor_metrics.py` / `factor_curves.py` 全都靠
  **`engine/loop_state{_pool}.pkl` 里的 `bank`**（= **入库 Node 的权威口径**，见 `build_facs.load_bank_nodes`），
  而 `.gitignore` 忽略 `*.pkl` ⇒ **家里 pull 之后一个因子也重建不出来** ✗✗

**⇒ 本工具的定位**：不是"再造一份清单"，而是把**缺的那一环**导出成 git 里的小 JSON ——
  关键是**存 node 结构**（不只是公式文本）：代码注释明确记着，文本重解析走 `parse_expr` 会因
  **`LLM_MAX_SIZE` 尺寸上限静默返回 None**（全A F01 就中过招 ✗）⇒ 只有结构可**精确重建** ✓

## 产出（`docs/factor_registry.json`，几十 KB，进 git）

```json
{"schema": 1, "generatedAt": "...", "counts": {...},
 "factors": [{"pool":"all","no":"F01","gen":8,"family":"换手-量联动波动",
              "oneLiner":"turnover/turn_ratio×volume 双尺度波动","status":"已入库",
              "expr":"add(ts_std20(...))","sign":-1,"poolTag":"csi1000_all",
              "ic":..,"icIr":..,"annEx":..,"dd":..,"calmar":..,"sharpe":..,
              "recentYear":..,"turn":..,"note":"...",
              "node":{"op":"add","args":[...]},        // ★ 可精确重建（不受解析上限影响）
              "alsoIn":["300"]}]}                      // 同一式子在其它池也入库
```

## 谁在用
  · `tools/build_facs.py::load_bank_nodes` ⇒ **JSON ∪ pkl**（JSON 优先；家里没 pkl 也能跑 ✓）
  · 收尾管线 `run_tracks.do_global_tail` ⇒ 每次都重建它（保持与库同步 ✓）
  · `tools/_test_registry.py` ⇒ 守门：JSON 的编号必须**覆盖** md 清单、node 必须能重建出同一表达式 ✓

用法: python tools/export_factor_registry.py [--check]
      `--check`：只校验（不写文件），不一致 ⇒ 退出码 1（给回归测试用）
"""
import argparse
import io
import json
import os
import re
import sys
import time

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DOCS = os.path.join(ROOT, 'docs')
ENG = os.path.join(ROOT, 'engine')
sys.path.insert(0, ENG)
sys.path.insert(0, HERE)

REG = os.path.join(DOCS, 'factor_registry.json')
POOLS = ('all', '300', '500', '1000', '50')


def _md(pool):
    sfx = '' if pool == 'all' else '_' + pool
    p = os.path.join(DOCS, 'factor_library{}.md'.format(sfx))
    return io.open(p, encoding='utf-8').read() if os.path.exists(p) else ''


def parse_overview(pool):
    """「因子总览」表 ⇒ `{编号: {gen, family, oneLiner, status}}`（用户要的四列都在这 ✓）"""
    out = {}
    for ln in _md(pool).splitlines():
        m = re.match(r'^\|\s*(F\d+)\s*\|([^|]*)\|([^|]*)\|([^|]*)\|([^|]*)\|\s*$', ln)
        if not m:
            continue
        no, gen, fam, one, st = (m.group(i).strip() for i in range(1, 6))
        g = re.search(r'gen(\d+)', gen)
        out[no] = dict(gen=int(g.group(1)) if g else None, family=fam,
                       oneLiner=one, status=st)
    return out


def parse_detail(pool):
    """每个因子块 ⇒ `{编号: {expr, sign, poolTag, note, 指标…}}`（`### F01 · gen8 入库` 开头）"""
    out = {}
    t = _md(pool)
    parts = re.split(r'\n### (F\d+) · ', t)
    for k in range(1, len(parts) - 1, 2):
        no, body = parts[k], parts[k + 1]
        d = {}
        m = re.search(r'```\n([^\n]+)', body)
        if m:
            d['expr'] = m.group(1).strip()
        m = re.search(r'sign`：`([+\-]?\d+)`', body)
        if m:
            d['sign'] = int(m.group(1))
        m = re.search(r'池标签：\*\*`([^`]+)`\*\*', body)
        if m:
            d['poolTag'] = m.group(1)
        m = re.search(r'^-\s*家族[^：]*：(.+)$', body, re.M)
        if m:
            d['family'] = m.group(1).strip()
        m = re.search(r'^-\s*备注：(.+)$', body, re.M)
        if m:
            d['note'] = m.group(1).strip()
        # 费后指标行（口径同 `build_facs.parse_library`，**复用它的正则**避免两处漂移）
        m = re.search(r'费后指标[^：]*：IC ([\d.]+) / IC_IR ([\d.]+) / 年化超额 ([+\-\d.]+)% / '
                      r'回撤 ([+\-\d.]+)% / Calmar ([\d.]+) / Sharpe ([+\-\d.]+) / '
                      r'最近年 ([+\-\d.]+)% / 单期换手 ([\d.]+)%', body)
        if m:
            v = [float(m.group(i)) for i in range(1, 9)]
            d.update(ic=v[0], icIr=v[1], annEx=v[2] / 100, dd=v[3] / 100,
                     calmar=v[4], sharpe=v[5], recentYear=v[6] / 100, turn=v[7] / 100)
        if d.get('expr'):
            out[no] = d
    return out


# node 序列化由 `loop_engine.node_to_dict / node_from_dict` 提供（**单一事实源** ✓，
# 免得本文件与 build_facs / 测试各写一份、将来漂移 ✗）


def _load_bank_nodes(pool):
    """从 pkl 读入库 Node（**只在本机有 pkl 时可用**；家里没有 ⇒ 空 ✓）。"""
    import pickle
    import build_facs as BF                      # 复用它的 `_prep_main`（pkl 是 `__main__` 身份存的）
    BF._prep_main()
    sfx = '' if pool == 'all' else '_' + pool
    p = os.path.join(ENG, 'loop_state{}.pkl'.format(sfx))
    if not os.path.exists(p):
        return {}
    try:
        st = pickle.load(open(p, 'rb'))
    except Exception as e:
        print('  [!] 读 {} 失败: {}: {}'.format(os.path.basename(p), type(e).__name__, e))
        return {}
    return {str(x): x for x in (st.get('bank', []) or [])}


def build():
    import build_facs as BF
    import loop_engine as LE
    factors, counts, md_drift = [], {}, []
    for pool in POOLS:
        ov = parse_overview(pool)
        det = parse_detail(pool)
        bank = _load_bank_nodes(pool)            # 可能为空（家里 / 该池无 state）
        n_pool, seen_expr = 0, set()
        for no in sorted(set(list(ov.keys()) + list(det.keys()))):
            d = dict(det.get(no) or {})
            expr = d.get('expr')
            if not expr:
                continue                          # 没有公式 ⇒ 无法重建，跳过（且下面会计数报告）
            o = ov.get(no) or {}
            nd = bank.get(expr)
            rec = {'pool': pool, 'no': no,
                   'gen': o.get('gen', d.get('gen')),
                   'family': o.get('family') or d.get('family'),
                   'oneLiner': o.get('oneLiner'),
                   'status': o.get('status'),
                   'expr': expr,
                   'sign': d.get('sign'), 'poolTag': d.get('poolTag'), 'note': d.get('note')}
            for k in ('ic', 'icIr', 'annEx', 'dd', 'calmar', 'sharpe', 'recentYear', 'turn'):
                if k in d:
                    rec[k] = d[k]
            rec['inBank'] = nd is not None
            rec['node'] = LE.node_to_dict(nd) if nd is not None else None
            factors.append(rec)
            seen_expr.add(expr)
            n_pool += 1
        # ★★★★ 2026-09-17（本导出器的**第一个真发现**）：`state.bank`（**引擎权威口径**）里有、
        #   而**库文档 md 里没有**的入库因子 ⇒ 实测 1000 池就有 1 个（`ts_mean150(corr100(...))`）✗
        #   ⇒ 若清单只信 md，"家里重建"就会**悄悄少算**这个因子 ✗✗ ⇒ 这里**必须**把它收进来：
        #     编号/代数/家族/一句话 都取不到（md 是它们唯一的家）⇒ 如实留空 + 标注"仅 bank"✓
        #     ⚠ 同时把这种漂移**吼出来**（md 该由引擎入库时自动追加，见 md 头部说明 ✓）
        for expr, nd in sorted(bank.items()):
            if expr in seen_expr:
                continue
            factors.append({'pool': pool, 'no': None, 'gen': None, 'family': None,
                            'oneLiner': None, 'status': '仅 bank（库文档 md 未收录）',
                            'expr': expr, 'sign': None, 'poolTag': None, 'note': None,
                            'inBank': True, 'node': LE.node_to_dict(nd), 'nodeFrom': 'pkl',
                            'bankOnly': True})
            md_drift.append((pool, expr))
        counts[pool] = dict(listed=n_pool, overview=len(ov), detail=len(det), bank=len(bank),
                            bank_only=len([1 for f in factors
                                           if f['pool'] == pool and f.get('bankOnly')]))
    # 同一式子跨池入库 ⇒ 记 `alsoIn`（下游去重/合并时不用再猜 ✓）
    by_expr = {}
    for f in factors:
        by_expr.setdefault(f['expr'], []).append(f)
    for expr, fs in by_expr.items():
        if len(fs) > 1:
            for f in fs:
                f['alsoIn'] = sorted(x['pool'] for x in fs if x is not f)
    # ★★ node 补全（**跨池借用**）：某池库里有这条（池标签说明它在该池通过），但 node 记在**别的池**的
    #   bank 里（谁挖的就存谁那儿 ✓）—— 同一式子的 node 必然相同 ⇒ 借用即可，别丢重建成能力 ✗
    #   实测：全A 41 + 池 19 条 ⇒ 有 9 条**只有别的池有 node**（如 300 库里的 F02 来自全A 轨道）
    for expr, fs in by_expr.items():
        donor = next((x for x in fs if x.get('node')), None)
        if donor is None:
            continue
        for f in fs:
            if not f.get('node'):
                f['node'] = donor['node']
                f['inBank'] = True
                f['nodeFrom'] = donor['pool']        # ★ 留痕：这个 node 是**借来的**（可复核 ✓）
    # ★★ node 补全（**由公式文本重建**）：还剩几个是"**已从库中移除**"的历史条目（编号/公式还在 md，
    #   但 Node 已不在任何 pool 的 bank 里 ✗）⇒ 用 `parse_expr(max_size=10**9)` 重建 ✓
    #   为什么可以放开上限：库里留着的公式**都是过了全部门槛的**（尺寸护栏本来是防 LLM 生成超大式子）✓
    #   ⇒ 重建出来照常能算因子值 ⇒ **"pull 回家能不能重建"不再取决于这条有没有被移出库** ✓
    for f in factors:
        if f.get('node') or not f.get('expr'):
            continue
        try:
            nd = LE.parse_expr(f['expr'], max_size=10 ** 9)
        except Exception:
            nd = None
        if nd is not None and str(nd) == f['expr']:
            f['node'] = LE.node_to_dict(nd)
            f['nodeFrom'] = 'expr'                   # ★ 留痕：由公式文本重建 ✓
    out = {'schema': 1,
           'generatedAt': time.strftime('%Y-%m-%d %H:%M:%S'),
           'source': 'docs/factor_library*.md（编号/代数/家族/一句话/公式/指标）+ '
                     'engine/loop_state*.pkl（入库 Node 结构，权威口径）',
           'why': 'pkl 不进 git ⇒ 换机器（家里 pull）时本文件是"重建 facs/指标/曲线"的**唯一入口** ✓',
           'counts': counts,
           'mdDrift': [{'pool': p, 'expr': e} for p, e in md_drift],
           'n_factors': len(factors), 'n_with_node': sum(1 for f in factors if f['node']),
           'factors': factors}
    return out


def compare(cur, old):
    """`--check`：新旧差异（给回归测试用；**只比"编号集合 + node 是否可重建"**，不比时间戳）✓

    :param cur: **本次构建出的 `factors` 列表**（不是整个 dict —— 别传错，实测踩过 ✗）
    :param old: 旧 JSON 的整体 dict（读出来的完整对象）
    """
    problems = []
    # ⚠ key 必须**可排序**：`no` 可能是 `None`（"仅 bank"条目没有编号）⇒ `sorted()` 会炸 ✗（实测踩到）
    #   ⇒ 用 `no or ''` 兜底、并把 `expr` 拼进去（同一池同一条式子唯一定位 ✓）
    key = lambda f: (f['pool'], f.get('no') or '', f.get('expr') or '')      # noqa: E731
    c, o = {key(f): f for f in cur}, {key(f): f for f in (old or {}).get('factors', [])}
    for k in sorted(set(c) - set(o)):
        problems.append('JSON 缺条目 %s/%s' % k)
    for k in sorted(set(o) - set(c)):
        problems.append('JSON 多了条目 %s/%s（md 里已没有）' % k)
    for k in sorted(set(c) & set(o)):
        if c[k]['expr'] != o[k]['expr']:
            problems.append('%s/%s 公式与 md 不一致' % k)
        if o[k].get('node') and not c[k].get('node'):
            problems.append('%s/%s 丢了 node（重建能力退化）' % k)
    return problems


def self_test():
    """★ 负向自检：**证明"重建"这条链真的可用**
      [1] `node_to_json` → `node_from_json` 必须给出**同一表达式**（往返恒等）
      [2] 构造一个**超 `parse_expr` 尺寸上限**的深树 ⇒ 结构往返仍恒等（这正是"不能只存文本"的理由）
    """
    import loop_engine as LE
    fails = []
    # ⚠ 叶子名**必须真的在 `LEAVES` 里**（自检自己写错叶子 ⇒ `parse_expr` 会正确地判 None，
    #   于是自检**误报** ✗ —— 2026-09-17 实测踩到：`mf_ret` 不是叶子）⇒ 从 `LEAVES` 取真名 ✓
    lf = [x for x in LE.LEAVES if x.startswith(('mf_', 'barra_', 'ln'))][:2] or list(LE.LEAVES)[:2]
    nd = LE.Node('add', [LE.Node('ts_std20', [LE.Node(lf[0], [])]),
                         LE.Node('cs_rank', [LE.Node(lf[1], [])])])
    back = LE.node_from_dict(LE.node_to_dict(nd))
    if str(back) != str(nd):
        fails.append('结构往返不等于原表达式 ✗')
    if LE.parse_expr(str(nd), max_size=10 ** 9) is None:
        fails.append('公式文本重建失败（`parse_expr(max_size=…)` 应当能读回 ✓）')
    deep = LE.Node(lf[0], [])
    for _ in range(40):
        deep = LE.Node('cs_rank', [deep])
    deep2 = LE.node_from_dict(LE.node_to_dict(deep))
    if str(deep2) != str(deep) or deep2.size() != deep.size():
        fails.append('深树（超解析上限那种）往返不等 ✗')
    print('  [自检] 结构往返恒等 ✓（含 40 层深树）+ 公式文本可重建 ✓'
          if not fails else '  [自检] ✗ ' + ' / '.join(fails))
    return fails


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true', help='只校验（不写文件），不一致退出码 1')
    a = ap.parse_args()
    print('=' * 96)
    print('导出因子登记表 → %s' % os.path.relpath(REG, ROOT))
    print('=' * 96)
    st = self_test()
    cur = build()
    print('  池计数: ' + ' · '.join(
        '%s: 列表%d/明细%d/bank%d' % (p, v['listed'], v['detail'], v['bank'])
        for p, v in cur['counts'].items()))
    print('  共 %d 条（其中 **有 node 可重建** %d 条）' % (cur['n_factors'], cur['n_with_node']))
    if cur['mdDrift']:
        print('  ⚠⚠ **库文档 md 漏记了 %d 个已入库因子**（引擎 bank 有、md 没有）：' % len(cur['mdDrift']))
        for x in cur['mdDrift'][:5]:
            print('      池 %-5s %s' % (x['pool'], x['expr'][:90]))
        print('      ⇒ 已按「仅 bank」收录（**不会漏算** ✓），但**编号/家族/一句话缺失** ——')
        print('         应查为何引擎入库时没自动追加 md 条目（md 头部写明会自动追加）✗')
    if cur['n_with_node'] < cur['n_factors']:
        miss = [(f['pool'], f['no']) for f in cur['factors'] if not f['node']]
        print('  ⚠ 无 node（多为"已移出库"的历史条目，或本机无该池 state）：%d 个 %s'
              % (len(miss), miss[:6]))
    old = None
    if os.path.exists(REG):
        try:
            old = json.load(io.open(REG, encoding='utf-8'))
        except Exception as e:
            print('  [!] 旧文件读不出来（忽略）: %r' % e)
    problems = compare(cur['factors'], old) if old else []
    if a.check:
        for p in problems:
            print('  ✗ %s' % p)
        print()
        print('★ %s' % ('一致 ✓' if (not problems and not st) else '不一致（见上）✗'))
        return 1 if (problems or st) else 0
    if problems:
        print('  与旧文件的差异（更新理由）：')
        for p in problems[:8]:
            print('    · ' + p)
    tmp = REG + '.tmp'
    io.open(tmp, 'w', encoding='utf-8').write(
        json.dumps(cur, ensure_ascii=False, indent=1))
    os.replace(tmp, REG)
    print('  已写 %s（%.1f KB）✓' % (os.path.relpath(REG, ROOT),
                                     os.path.getsize(REG) / 1024.0))
    print()
    print('★ 换机器重建：`python tools/build_facs.py --only-new` → `tools/factor_metrics.py` →'
          ' `tools/factor_curves.py`（它们都优先读本 JSON ✓）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
