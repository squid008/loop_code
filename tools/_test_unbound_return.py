# -*- coding: utf-8 -*-
"""★★★★ 静态守门：「**可能未绑定的局部变量**」（`UnboundLocalError` 隐患）——2026-09-19 新增

## 为什么必须有它（同一天连崩三次，同一个源头 ✗）
v0.17.0 `41705f4`「P0-2 拆 run() 1291→921 行（17 个函数）」把内联代码抽成函数时
**加了 return / 加了参数**，于是原本"潜伏没人读"的变量立刻变成引擎**起来即崩** ✗：
```
_critic_review_prev  : return (cfg, critic, diag, r, reasons)          ⇒ UnboundLocalError: diag ← v1.21.6 ✓
_build_fam_blacklist : return (block_fams, f, fam_black_txt, nd)       ⇒ UnboundLocalError: nd   ← v1.21.7 ✓
run()                : frozen, nd, r, s = _fsa_stats(…, nd, r, s, …)   ⇒ UnboundLocalError: s    ← v1.21.8 ✓
```
⇒ 一个一个等它崩出来不是办法 ⇒ **按类钉死** ✓

## 判据（"一定绑定"的三口径）
1. 函数体最外层直接语句绑定（`x = …` / `for x in …`）✓
2. `with` 体 / `try` 体 —— **必执行**（出异常就直接离开函数，走不到后面 ✗）⇒ 透明递归 ✓
3. 完整 `if/else`（含 elif 链）**两支都绑定**同一名字 ⇒ 也算 ✓
- 以上都要求**行号更早** ✗（否则"当前这条语句自己"会自证安全 ⇒ 漏报 ✗，实测踩过三次 ✓）
- ★ **推导式是独立作用域** ⇒ 内部 Store/Load 一律不算函数局部 ✗（否则
  `[(-v if s<0 else v) for v, s in zip(...)]` 的 `s` 会被误当函数级赋值 ⇒ 漏报 ✗）
- 规则 A：`return` 带出可能未绑定的局部 ✗
- 规则 B：**等号两边同名**（含**元组解包** `a, b = f(…, a, b)` ✗ —— 真凶形态 ✓）
- 少量**已登记豁免**（见 `ALLOW`：人工核过"确实安全"、静态证明不了的写法 ✓）

★ **自带自检**：每次运行都会拿内置的"必崩样本/必不报样本"验自己一遍 ✓
  （防"守着守着失灵" ✗ —— 2026-09-19 实测这套规则漏报过三次，全都是自检抓出来的 ✓）

⚠ 纯静态、不跑引擎、不写文件、不连网 ⇒ **线上挖掘时可安全跑** ✓
"""
import ast
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = [a for a in sys.argv[1:] if not a.startswith('--')] or [
    'engine/loop_engine.py', 'engine/loop_critic.py', 'engine/factor_miner.py']
COMPOUND = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try, ast.With, ast.AsyncWith, ast.Match)
COMPREH = (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)

# ---- 已登记豁免（人工核过"确实安全"，静态证明不了 ✓）----
ALLOW = {
    ('engine/loop_engine.py', 'run', 'f'):
        '`f` = 面板对象，在 run() 前段就绑好；此处只是 _build_fam_blacklist 的透传 ✓',
    ('engine/loop_engine.py', 'run', '_v'):
        '`_v` 在 L1 求值循环里赋值；该循环在本代有候选时必然至少跑一次 ✓（若将来允许 0 候选，需重看 ✗）',
}
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# ================================================================ 分析核心
def comp_ids(fn):
    out = set()
    for cn in ast.walk(fn):
        if isinstance(cn, COMPREH):
            for x in ast.walk(cn):
                out.add(id(x))
    return out


def bind_names(node, out, skip):
    for e in ast.walk(node):
        if id(e) in skip:
            continue
        if isinstance(e, ast.Name) and isinstance(e.ctx, ast.Store):
            out.add(e.id)


def branch_names(body, skip):
    """一个分支块里**一定**绑定的名字（保守取并 ✓）"""
    out = set()
    for st in body:
        if isinstance(st, ast.Assign):
            for t in st.targets:
                bind_names(t, out, skip)
        elif isinstance(st, (ast.AnnAssign, ast.AugAssign)):
            bind_names(st, out, skip)
        elif isinstance(st, (ast.For, ast.AsyncFor)):
            bind_names(st.target, out, skip)
        elif isinstance(st, (ast.With, ast.AsyncWith, ast.Try)):
            for it in getattr(st, 'items', []) or []:
                if it.optional_vars is not None:
                    bind_names(it.optional_vars, out, skip)
            out |= branch_names(getattr(st, 'body', []), skip)
            for h in getattr(st, 'handlers', []) or []:
                out |= branch_names(h.body, skip)
        elif isinstance(st, ast.If) and st.orelse:
            out |= (branch_names(st.body, skip) & branch_names(st.orelse, skip))
    return out


def walk_sure(stmts, out, skip, lines):
    for st in stmts:
        if isinstance(st, (ast.With, ast.AsyncWith)):
            walk_sure(st.body, out, skip, lines)      # with 体：必执行 ⇒ 透明 ✓
            continue
        if isinstance(st, ast.Try):
            walk_sure(st.body, out, skip, lines)      # try 体：异常即离开函数 ⇒ 透明 ✓
            continue
        for nm in branch_names([st], skip):
            out.add(nm)
            lines.setdefault(nm, st.lineno)           # ★ 最早的外层绑定行 ✓
    return out


def scan(src, rel):
    tree = ast.parse(src)
    parent = {}
    for n in ast.walk(tree):
        for c in ast.iter_child_nodes(n):
            parent[c] = n
    hits = []
    for fn in [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
        skip = comp_ids(fn)
        params = {a.arg for a in (fn.args.args + fn.args.kwonlyargs + fn.args.posonlyargs)}
        for a in (fn.args.vararg, fn.args.kwarg):
            if a:
                params.add(a.arg)
        gl = set()
        for n in ast.walk(fn):
            if isinstance(n, ast.Global):
                gl.update(n.names)
            elif isinstance(n, ast.Nonlocal):
                gl.update(n.names)
        sure_lines = {}
        walk_sure(fn.body, set(), skip, sure_lines)

        def is_sure(nm, line):
            return nm in params or nm in gl or sure_lines.get(nm, 10 ** 9) < line

        stores = [n for n in ast.walk(fn)
                  if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)
                  and n.id not in params and n.id not in gl and id(n) not in skip]
        local_names = {n.id for n in stores}
        safe = {}
        for n in stores:
            cur = parent.get(n)
            while cur is not None and not isinstance(cur, COMPOUND):
                cur = parent.get(cur)
            if cur is not None and getattr(cur, 'end_lineno', None):
                safe.setdefault(n.id, []).append((n.lineno, cur.lineno, cur.end_lineno))

        def safe_at(nm, line):
            return any(sl < line and a <= line <= b for sl, a, b in safe.get(nm, []))

        # 规则 A
        for node in ast.walk(fn):
            if not isinstance(node, ast.Return) or node.value is None:
                continue
            vals = ([e for e in node.value.elts] if isinstance(node.value, (ast.Tuple, ast.List))
                    else [node.value])
            for e in vals:
                if not isinstance(e, ast.Name) or e.id not in local_names \
                        or is_sure(e.id, node.lineno) or safe_at(e.id, node.lineno):
                    continue
                hits.append((rel, fn.name, node.lineno, e.id, 'return 带出未绑定变量'))
        # 规则 B
        for node in ast.walk(fn):
            if not isinstance(node, ast.Assign):
                continue
            tn = set()
            for t in node.targets:
                for e in ast.walk(t):
                    if id(e) not in skip and isinstance(e, ast.Name) \
                            and isinstance(e.ctx, ast.Store):
                        tn.add(e.id)
            if not tn:
                continue
            ld = {e.id for e in ast.walk(node.value)
                  if id(e) not in skip and isinstance(e, ast.Name) and isinstance(e.ctx, ast.Load)}
            for nm in sorted((tn & ld) & local_names):
                if is_sure(nm, node.lineno) or safe_at(nm, node.lineno):
                    continue
                hits.append((rel, fn.name, node.lineno, nm, '等号两边同名（右边先读）'))
    return hits


# ================================================================ 自带自检
_SAMPLE = '''
def must_flag_a(prev, cfg):
    if prev:
        diag = {'a': 1}
        cfg = dict(cfg, x=1)
    return cfg, diag


def must_flag_b(args, seeds):
    if seeds and 0.5 < 0.8:
        s = "parent"
        node = s
    for _i in range(3):
        pass
    s = None if False else s
    frozen, nd, r, s = _fsa(args, r=0.5, s=s)
    return frozen, nd, r, s


def must_not_flag_1(args):
    s = None
    if args:
        s = "parent"
    a, b = _fsa(args, s=s)
    return a, b


def must_not_flag_2(vals):
    v0 = 1.0
    for x in vals:
        v0 = v0 + x
        if v0 > 5:
            v0 = 5.0
    return v0


def must_not_flag_3(vals, sign):
    return [(-v if s < 0 else v) for v, s in zip(vals, sign)]
'''

print('静态守门：局部变量不许"可能未绑定"就被读')
print('  [自检] 内置样本：必须命中 2 处 ✗、必须不误报 3 处 ✓')
_self = scan(_SAMPLE, '<selftest>')
_self_ok = (sum(1 for h in _self if h[1].startswith('must_flag')) == 2
            and not [h for h in _self if h[1].startswith('must_not')])
print('  [自检] %s（命中 %d 处：%s）' % (
    '通过 ✓' if _self_ok else '失败 ✗✗ 规则已失灵！',
    len(_self), ', '.join('%s.%s' % (h[1], h[3]) for h in _self)))

all_hits = list(_self)
for rel in FILES:
    p = os.path.join(ROOT, rel)
    if not os.path.exists(p):
        continue
    print('  扫 %s' % rel)
    all_hits += scan(io.open(p, encoding='utf-8').read(), rel)

real = [h for h in all_hits if not h[0].startswith('<')]
allowed = [h for h in real if (h[0], h[1], h[3]) in ALLOW]
real = [h for h in real if h not in allowed]

if allowed:
    print('  ◻ 已登记豁免 %d 处（人工核过 ✓）：' % len(allowed))
    for rel, fname, ln, nm, _why in allowed:
        print('     - %s:%d %s() `%s` ⇒ %s' % (rel, ln, fname, nm, ALLOW[(rel, fname, nm)]))
if real:
    print('  ✗ 命中 %d 处隐患：' % len(real))
    for rel, fname, ln, nm, why in real:
        print('     - %s:%d  %s()  `%s`  （%s）' % (rel, ln, fname, nm, why))
    print('  ⇒ 修法：在**函数体最外层**先给同形默认值（或把变量绑到确定路径上）✗')
    sys.exit(1)
if not _self_ok:
    sys.exit(1)
print('  ✓ 干净：没有"可能未绑定就被读"的局部变量（自检通过 ✓）')
sys.exit(0)
