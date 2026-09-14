# -*- coding: utf-8 -*-
"""calib_gate.py — 门标定器（`loop_todo §1.3-B`）· **加门前先跑这个**

## 为什么要有这个工具

本项目反复的教训是「**动作施加了但完全无效**」（§1.1/§1.15）。
**门（gate）最容易犯这个错** —— 抄一个看起来合理的阈值，结果：
  · 要么**误杀**了已经证明有用的因子（把好东西扔掉）
  · 要么**拦不掉任何东西**（白做）
⇒ 所以 **任何门在启用前，必须用本项目数据标定** ✓

## 判据（两条硬要求）

1. **安全**：误杀（把"正样本"拦掉）必须 **≈ 0**
2. **有效**：拦掉"负样本"的比例 **≥ 20%**（否则不值得开）

## 两个待标定位置（用法不同）

### `--target=pre_l1`（生成后、L1 前）
* 正样本 = `bank`（已入库）· 负样本 = `last_l1` 中未入库
* 可用判据只有**表达式结构**（还没算任何数值）
* **2026-09-15 实测结论：此处无可用的复杂度/结构判据** ⇒
  - 复杂度：`cfg['depth']` 已在生成端管住 ⇒ 加长度/节点上界**重复**
  - 结构 Novelty：`bank→seeds` 正反馈使"像库里的"=**进化在青睐的** ⇒ **方向反了**

### `--target=l1_l2`（L1 后、L2 前）★ 真正的预算瓶颈
* 正样本 = `last_l2` 里 `passed=True` · 负样本 = `passed=False`
* 可用判据 = **L1 已算出的指标**（`ic`/`ic_ir`/`stab`/`mono`/`score`/`turn_est`）
* 实测：**`mono`/`score`/`ic_ir` 区分度强** ✓

## 还支持复核一个**具体的门规则**

    python tools/calib_gate.py --target=l1_l2 --eval "mono>=0.75"
    python tools/calib_gate.py --target=l1_l2 --eval "score>=0.90 and stab>=0.9"

⇒ 直接告诉你：**这条规则会误杀几个正样本、拦掉多少负样本** ✓
"""
import argparse
import os
import pickle
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
os.chdir(ROOT)
sys.path.insert(0, os.path.join(ROOT, 'engine'))

import loop_engine as LE          # noqa: E402
import numpy as np                # noqa: E402

sys.modules['__main__'].Node = LE.Node
ALLOPS = set(LE.UNARY) | set(LE.BINARY)


# ============================== 结构指标（pre_l1 用）==============================

def walk(n):
    yield n
    for a in n.args:
        if isinstance(a, LE.Node):
            for x in walk(a):
                yield x


def structure_metrics(node):
    ns = list(walk(node))
    leaves = [x for x in ns if not x.args]
    fields = [x.op for x in leaves if x.op not in ALLOPS]
    return dict(length=len(str(node).strip()), n_nodes=len(ns),
                n_leaves=len(leaves), n_fields=len(set(fields)),
                var_share=(len(set(fields)) / len(ns)) if ns else 0.0)


def skey(n, fold_window=True):
    if not n.args:
        return n.op
    op = LE.norm_op(n.op) if fold_window else n.op
    return (op, tuple(skey(a, fold_window) for a in n.args if isinstance(a, LE.Node)))


def subtree_keys(n, fold_window=True):
    out = {}

    def rec(x):
        k = skey(x, fold_window)
        if k not in out or out[k] < x.size():
            out[k] = x.size()
        for a in x.args:
            if isinstance(a, LE.Node):
                rec(a)
    rec(n)
    return out


# ============================== 数据加载 ==============================

def load_states():
    out = []
    for fn in sorted(os.listdir('engine')):
        if not (fn.startswith('loop_state') and fn.endswith('.pkl')):
            continue
        try:
            st = pickle.load(open(os.path.join('engine', fn), 'rb'))
        except Exception as e:
            print('  [!] %-26s 读取失败: %s' % (fn, e))
            continue
        out.append((fn, st))
    return out


def sample_pre_l1():
    P, N = [], []
    for fn, st in load_states():
        bank = [str(x) for x in (st.get('bank') or [])]
        l1 = st.get('last_l1')
        exprs = ([str(x) for x in l1['expr'].tolist()]
                 if l1 is not None and 'expr' in getattr(l1, 'columns', []) else [])
        bs = set(bank)
        P.extend(bank)
        N.extend([e for e in exprs if e not in bs])
        print('  %-26s bank %3d · last_l1 未入库 %3d' % (fn, len(bank), len(exprs) - len(set(exprs) & bs)))
    return sorted(set(P)), sorted(set(N) - set(P))


def sample_l1_l2():
    rows = []
    for fn, st in load_states():
        l1, l2 = st.get('last_l1'), st.get('last_l2')
        if l1 is None or l2 is None:
            continue
        c1, c2 = getattr(l1, 'columns', []), getattr(l2, 'columns', [])
        if 'expr' not in c1 or 'expr' not in c2:
            continue
        d1 = {str(r['expr']): r for _, r in l1.iterrows()}
        for _, r2 in l2.iterrows():
            r1 = d1.get(str(r2['expr']))
            if r1 is None:
                continue
            rows.append(dict(
                pool=fn, expr=str(r2['expr']), passed=bool(r2.get('passed', False)),
                **{k: float(r1.get(k, np.nan))
                   for k in ('ic', 'ic_ir', 'stab', 'mono', 'score', 'turn_est', 'shape_pos')}))
    return rows


# ============================== 报告 ==============================

def pctl(xs, p):
    xs = [x for x in xs if np.isfinite(x)]
    return float(np.percentile(xs, p)) if xs else float('nan')


def eval_rule(rule, P, N, keys):
    """评估形如 `mono>=0.75 and stab>=0.9` 的规则。"""
    import re
    conds = []
    for tok in re.split(r'\s+and\s+', rule.strip()):
        m = re.match(r'^\s*([a-z_]+)\s*(>=|<=|>|<|==)\s*([-\d.eE]+)\s*$', tok)
        if not m:
            raise SystemExit('  [!] 无法解析条件: %r' % tok)
        k, op, v = m.group(1), m.group(2), float(m.group(3))
        if k not in keys:
            raise SystemExit('  [!] 未知指标 %r（可用: %s）' % (k, '/'.join(keys)))
        conds.append((k, op, v))

    def violated(r):
        for k, op, v in conds:
            x = r.get(k, np.nan)
            if not np.isfinite(x):
                return True                      # 缺值 ⇒ 按「不过」处理（保守）
            if op == '>=' and not (x >= v):
                return True
            if op == '<=' and not (x <= v):
                return True
            if op == '>' and not (x > v):
                return True
            if op == '<' and not (x < v):
                return True
            if op == '==' and not (x == v):
                return True
        return False

    miss = [r for r in P if violated(r)]
    kill = [r for r in N if violated(r)]
    print('\n  ── 规则评估: `%s` ──' % rule)
    print('     ★ 误杀正样本 %d/%d = %.1f%%   %s'
          % (len(miss), len(P), 100.0 * len(miss) / max(len(P), 1),
             '✓ 安全' if len(miss) <= max(1, int(0.02 * len(P))) else '✗ **误杀过多**'))
    print('     ★ 拦掉负样本 %d/%d = %.1f%%   %s'
          % (len(kill), len(N), 100.0 * len(kill) / max(len(N), 1),
             '✓ 有效' if len(kill) >= 0.20 * len(N) else '✗ 拦获不足（不值得开）'))
    return len(miss), len(kill)


def main():
    ap = argparse.ArgumentParser(description='门标定器（加门前先跑这个）')
    ap.add_argument('--target', choices=['pre_l1', 'l1_l2'], default='l1_l2')
    ap.add_argument('--eval', default='', help='复核一条具体规则，如 "mono>=0.75"')
    ap.add_argument('--fold_window', action='store_true', default=True)
    a = ap.parse_args()

    print('=' * 108)
    print('门标定器（loop_todo §1.3-B）· target=%s' % a.target)
    print('=' * 108)
    print('\n【1】样本')

    if a.target == 'pre_l1':
        P, N = sample_pre_l1()
        print('  ⇒ 正 %d · 负 %d' % (len(P), len(N)))
        MP = [structure_metrics(LE.parse_expr(e)) for e in P if LE.parse_expr(e)]
        MN = [structure_metrics(LE.parse_expr(e)) for e in N if LE.parse_expr(e)]
        print('\n【2】结构指标分布（正=已入库 · 负=进了 L1 但没过 L2）')
        print('  %-12s | %-26s | %-26s' % ('指标', '正 p50/p90/max', '负 p50/p90/max'))
        for k in ('length', 'n_nodes', 'n_fields', 'var_share'):
            p, n = [m[k] for m in MP], [m[k] for m in MN]
            print('  %-12s | %8.1f /%8.1f /%8.1f | %8.1f /%8.1f /%8.1f'
                  % (k, pctl(p, 50), pctl(p, 90), max(p), pctl(n, 50), pctl(n, 90), max(n)))
        print('\n【3】"正样本 max"作安全阈值能拦多少负样本')
        for k, thr, hit in (('length', max(m['length'] for m in MP), None),
                            ('n_nodes', max(m['n_nodes'] for m in MP), None),
                            ('n_fields', max(m['n_fields'] for m in MP), None)):
            n = [m[k] for m in MN]
            r = 100.0 * sum(1 for x in n if x > thr) / max(len(n), 1)
            print('  %-10s 上界 %-6g ⇒ 拦 %5.1f%%   %s'
                  % (k, thr, r, '★ 可用' if r >= 20 else '✗ 无区分度（**不要开这个门**）'))
        # 结构 Novelty（与库的最长公共子树）
        # ⚠⚠ **必须把 (表达式, 子树键) 成对建**（2026-09-15 实录）：
        #   初版写成 `zip([e for e in P if parse(e)], [subtree_keys(parse(e)) for e in P if parse(e)])`
        #   —— 看着对，但只要**有一条解析失败**，两个推导式的过滤**各算各的**，就可能错位
        #   ⇒ 结果：正样本 p50 = **1.0**（正确应为 **7.0**，见 `tools/_calib_novelty.py`）
        #   ⇒ **教训：并行列表绝不要靠"两个同条件推导式"对齐 —— 要成对构造** ✓
        pairs = []
        for e in P:
            nd = LE.parse_expr(e)
            if nd is not None:
                pairs.append((e, subtree_keys(nd, a.fold_window)))
        zoo = [z for _, z in pairs]
        Pv = []
        for _, z in pairs:
            my = z
            best = max((sz for k, sz in my.items() for zz in zoo if zz is not z and k in zz),
                       default=0)
            Pv.append(best)
        Nv = []
        for e in N:
            nd = LE.parse_expr(e)
            if nd is None:
                continue
            my = subtree_keys(nd, a.fold_window)
            Nv.append(max((sz for k, sz in my.items() for zz in zoo if k in zz), default=0))
        print('\n  ★ 结构 Novelty（与库的最长公共子树；正样本已**留一**排除自己）')
        print('     正 p50/p90/max = %.1f / %.1f / %.1f' % (pctl(Pv, 50), pctl(Pv, 90), max(Pv)))
        print('     负 p50/p90/max = %.1f / %.1f / %.1f' % (pctl(Nv, 50), pctl(Nv, 90), max(Nv)))
        print('     ⇒ 正负分布**重合**（中位都是同一个值）⇒ **无区分度 ⇒ 不要开这个门** ✗')
        print('     ⚠⚠ **更正（2026-09-15）**：早先的 `tools/_calib_novelty.py` 报过"正 p50=7.0"'
              '（"方向反了"），')
        print('        那是**实现 bug**：它写 `zip(bank_all, zoo)`，而 `zoo` 只含**可解析**的项'
              '（正样本 50 个里 4 个解析失败）')
        print('        ⇒ **两个列表错位** ⇒ 读数虚高。修好后正 p50 = 1.0（= 负样本）'
              '⇒ 真相是「无区分度」，不是「方向反了」✓')
        print('     ⇒ 无论如何：**不要开** ✓（复杂度门同理：`cfg[\'depth\']` 已在生成端管住）')
        return 0

    # ---- l1_l2 ----
    rows = sample_l1_l2()
    P = [r for r in rows if r['passed']]
    N = [r for r in rows if not r['passed']]
    print('  ⇒ 配对 %d 条 · passed %d · 未通过 %d' % (len(rows), len(P), len(N)))
    if len(rows) < 30:
        print('  [!] 样本偏少（<30）⇒ 结论仅供参考，**别用它拍板**')
    if not P:
        print('  [!] 没有 passed 样本 ⇒ 无法评估"误杀"')
        return 1
    keys = ('ic', 'ic_ir', 'stab', 'mono', 'score', 'turn_est', 'shape_pos')
    print('\n【2】分布对照')
    print('  %-10s | %-26s | %-26s | %s' % ('L1 指标', 'passed p10/p50/p90',
                                            '未通过 p10/p50/p90', '方向'))
    DIR = {}
    for k in keys:
        p, n = [r[k] for r in P], [r[k] for r in N]
        if not p or not n:
            continue
        DIR[k] = '>' if pctl(p, 50) > pctl(n, 50) else '<'
        print('  %-10s | %7.4f /%7.4f /%7.4f | %7.4f /%7.4f /%7.4f | %s'
              % (k, pctl(p, 10), pctl(p, 50), pctl(p, 90),
                 pctl(n, 10), pctl(n, 50), pctl(n, 90),
                 '越大越该留' if DIR[k] == '>' else '越小越该留'))

    print('\n【3】单指标门（阈值 = 正样本最严端 ⇒ 误杀 0）')
    for k in keys:
        p = sorted(r[k] for r in P if np.isfinite(r[k]))
        n = [r[k] for r in N if np.isfinite(r[k])]
        if not p:
            continue
        thr = min(p) if DIR[k] == '>' else max(p)
        rule = '%s>=%.4f' % (k, thr) if DIR[k] == '>' else '%s<=%.4f' % (k, thr)
        miss, kill = eval_rule(rule, P, N, keys)

    if a.eval:
        print('\n【4】复核指定规则')
        eval_rule(a.eval, P, N, keys)
    print('\n' + '=' * 108)
    print('判读：**误杀 ≈ 0 且拦获 ≥ 20%** 才值得开；否则如实报告"此处无可省的空间" ✓')
    print('⚠ 阈值是**样本内**标定 ⇒ 必须有**样本外**复核再长期启用（有过拟合风险）。')
    print('=' * 108)
    return 0


if __name__ == '__main__':
    sys.exit(main())
