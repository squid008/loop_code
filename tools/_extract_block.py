# -*- coding: utf-8 -*-
"""通用「按行号抽块成子函数」工具（S3b 用 ✓）—— **两个方向都由 AST 机器算**，不靠人眼 ✗。

★ 为什么通用化：`_l1_calib` 那次我**手挑**回传值 ⇒ 漏了 `FEAT_S`/`STYLE_S` ✗、又漏了块外定义的
  `_min_mono` 等 4 个 ✗ ⇒ 真实一代崩两次（都被极小跑/A/B 抓住 ✓）。本工具把这两件事都机器化：

  · **参数**（EXT_IN）= 块里**读**到、但块里**没赋值**、且**函数内块之前已绑定或就是参数/模块级**的名字
    ⇒ 必须当形参传进去 ✓（否则就是 `NameError` ✗ —— 上一轮正是这个）
  · **回传**（RET） = 块里**赋值/自增**过、且块**之后**仍被读的名字 ⇒ 由调用方接收 ✓
    （漏一个 ⇒ 调用方拿到旧值/未定义 ✗ —— 更早一轮正是这个）
  · 模块级名字（import / 常量）**不进参数**（子函数直接可见 ✓）

★ 不变量：**块内文本原样搬运**（0 改写 ✓）；逐行重建（无行号位移 ✗ —— v1 脚本就栽在这 ✓）

用法：
    python ai_test/_extract2.py <file> <func> <A> <B> <newfunc> [--apply]
    # A/B = 要抽走的行号区间（1-based，含两端 ✓）；新函数插在原函数**结束之后** ✓
"""
import ast
import builtins
import io
import os
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
args = [a for a in sys.argv[1:] if not a.startswith('-')]
APPLY = '--apply' in sys.argv
FNAME, FN = args[0], args[1]
P = os.path.join(ROOT, 'engine', FNAME)

src = io.open(P, encoding='utf-8').read()
lines = src.splitlines(keepends=True)
tree = ast.parse(src)
fn = next(x for x in tree.body if isinstance(x, ast.FunctionDef) and x.name == FN)

if '--list' in sys.argv:
    # ★ 抽块的硬前提：块自身必须与函数体**同缩进**（工具是原样搬运 ✓、不重排缩进 ✗）
    #   ⇒ 先列出**顶层语句**的行号区间，照着挑 ✓（嵌套循环体在 8 空格 ⇒ 抽不了 ✗）
    print('%s :: %s  L%d–L%d（%d 行）· 顶层语句：'
          % (FNAME, FN, fn.lineno, fn.end_lineno, fn.end_lineno - fn.lineno + 1))
    for st in fn.body:
        if isinstance(st, ast.Expr) and isinstance(st.value, ast.Constant):
            continue
        print('  L%-4d–%-4d  %4d 行   %s'
              % (st.lineno, st.end_lineno, st.end_lineno - st.lineno + 1,
                 ast.unparse(st).splitlines()[0][:66]))
    sys.exit(0)

if '--rename-in-fn' in sys.argv:
    # ★ B 方案第 ③ 步用：把函数体里对「口径局部变量」的**裸名**用法换成 `cal.x` / `acc.y` ✓
    #   ① 改写位置**全部来自 AST 的 Name 节点** ⇒ 字符串/注释里的同名词绝不会被误改 ✓✓
    #   ② 只改**这个函数体**里的出现 ⇒ 别的函数不受影响 ✓
    #   ③ 必须先删掉那 24 行 `x = ctx['y']`（否则 Store 目标也会被改 ✗）
    spec = sys.argv[sys.argv.index('--rename-in-fn') + 1]
    REN = dict(kv.split('=', 1) for kv in spec.split(','))
    _lines0 = src.splitlines(keepends=True)
    hits, cnt, _bad = [], {}, []
    for st in fn.body:
        for nn in ast.walk(st):
            if isinstance(nn, ast.Name) and nn.id in REN:
                # ⚠ R0 铁律①：`col_offset` 是 **UTF-8 字节偏移**、不是字符偏移 ✗
                #   本仓库满屏中文注释（每字 3 字节 ✓）⇒ 直接拿去切 str 会**静默切歪** ✓
                #   （实测把 `{n_pool_nogate}` 改成了 `{n_poolacc.n_pool_nogate` ✗）
                _l0 = _lines0[nn.lineno - 1]
                _c0 = len(_l0.encode('utf-8')[:nn.col_offset].decode('utf-8', 'replace'))
                if _l0[_c0:_c0 + len(nn.id)] != nn.id:   # ⚠ R0 铁律②：逐处断言 ✓
                    _bad.append((nn.lineno, nn.col_offset, nn.id))
                    continue
                hits.append((nn.lineno, _c0, len(nn.id), REN[nn.id], nn.id))
                cnt[nn.id] = cnt.get(nn.id, 0) + 1
    if _bad:                                             # ⇒ 宁可中止，绝不留半个改写 ✗
        print('  ✗ %d 处定位对不上（字节/字符偏移 ✗）⇒ 中止、**未写盘** ✓：%s' % (len(_bad), _bad[:5]))
        sys.exit(3)
    print('%s :: %s  L%d–L%d · 待改 %d 处：%s'
          % (FNAME, FN, fn.lineno, fn.end_lineno, len(hits), cnt or '无 ✓'))
    new_src = src
    for ln, col, width, rep, old in sorted(hits, key=lambda h: (-h[0], -h[1])):
        _p = new_src.splitlines(keepends=True)
        _p[ln - 1] = _p[ln - 1][:col] + rep + _p[ln - 1][col + width:]
        new_src = ''.join(_p)
    _nl = new_src.splitlines()
    for h in sorted(hits, key=lambda h: (h[0], h[1]))[:5]:
        print('    L%-4d %s' % (h[0], _nl[h[0] - 1].strip()[:100]))
    if APPLY:
        io.open(P + '.bak2', 'w', encoding='utf-8').write(src)
        io.open(P, 'w', encoding='utf-8').write(new_src)
        ast.parse(new_src)                                    # 改完必须仍是合法 Python ✓
        print('  ✓ 已写盘（.bak2 ✓）· AST 复核通过 ✓')
    else:
        print('  （dry-run；--apply 才写 ✓）')
    sys.exit(0)

A, B, NEWFN = int(args[2]), int(args[3]), args[4]
print('%s :: %s  L%d–L%d（%d 行）· 抽 L%d–L%d -> %s()'
      % (FNAME, FN, fn.lineno, fn.end_lineno, fn.end_lineno - fn.lineno + 1, A, B, NEWFN))

# 模块级绑定（import / 常量 / def / class）—— 子函数直接可见 ⇒ 不当参数 ✓
_mod = set(dir(builtins))
for st in tree.body:
    if isinstance(st, (ast.Import, ast.ImportFrom)):
        for al in st.names:
            _mod.add((al.asname or al.name).split('.')[0])
    elif isinstance(st, ast.Assign):
        for t in st.targets:
            for nn in ast.walk(t):
                if isinstance(nn, ast.Name):
                    _mod.add(nn.id)
    elif isinstance(st, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        _mod.add(st.name)

_fnargs = {a.arg for a in fn.args.args} | {a.arg for a in fn.args.kwonlyargs}
_before, _blk, _after = set(_fnargs), [], []
for st in fn.body:
    if isinstance(st, ast.Expr) and isinstance(st.value, ast.Constant):
        continue
    if st.lineno >= A and getattr(st, 'end_lineno', st.lineno) <= B:
        _blk.append(st)
    elif getattr(st, 'end_lineno', st.lineno) < A:
        for nn in ast.walk(st):
            if isinstance(nn, ast.Name) and isinstance(nn.ctx, ast.Store):
                _before.add(nn.id)
    else:
        _after.append(st)


def _assigned(stmts):
    """★ 区分「**纯赋值**（Assign ⇒ 块内自给自足 ✓）」与「**自增/增量**（AugAssign ⇒ **先读后写** ✗）」：
    `n_eval += 1` 若被当成"块内定义" ⇒ 既不当形参、又要回传 ⇒ 子函数里必然 `NameError` ✗
    （这正是 dry-run 暴露出来的漏洞 ✓）"""
    plain, aug = set(), set()
    for st in stmts:
        for nn in ast.walk(st):
            if not isinstance(nn, ast.Name):
                continue
            if isinstance(nn.ctx, ast.Store):
                if isinstance(getattr(nn, 'parent_aug', None), ast.AugAssign):
                    continue
                plain.add(nn.id)
        for nn in ast.walk(st):
            if isinstance(nn, ast.AugAssign):
                for t in ast.walk(nn.target):
                    if isinstance(t, ast.Name):
                        aug.add(t.id)
                        plain.discard(t.id)
    return plain, aug


def _read(stmts):
    out = set()
    for st in stmts:
        for nn in ast.walk(st):
            if isinstance(nn, ast.Name) and isinstance(nn.ctx, ast.Load):
                out.add(nn.id)
    return out


def _cond_bound(stmts, names):
    """★ 找出「**条件赋值**」的 RET 名 —— 赋值只出现在**块内嵌套复合语句**里 ⇒ 可能一次都没执行 ✗
    ⇒ 子函数无条件 `return x` 会在没走到那条分支的调用上 `NameError` ✗
    （实测：`_l1_eval` 首抽时 `return k, n_eval, nd` 真崩 —— `k` 只在嵌套分支里绑 ✓）

    ⇒ 对策：这些名字在**子函数体开头先置 `None`** ✓（原函数里它们的作用域覆盖整个函数 ✓）。
    ⚠ 与「自增」型（`x += 1` ⇒ 已当形参传入 ✓）**互斥**：那种绝不能置 `None` ✗（`None + 1` 会 TypeError ✗）。
    """
    cond = set()

    def walk(ss, nested):
        for st in ss:
            for nn in ast.walk(st):
                if isinstance(nn, ast.Name) and isinstance(nn.ctx, ast.Store) and nested:
                    cond.add(nn.id)
            for fld in ('body', 'orelse', 'finalbody'):
                sub = getattr(st, fld, None)
                if isinstance(sub, list) and sub and isinstance(sub[0], ast.stmt):
                    walk(sub, True)
            for h in (getattr(st, 'handlers', None) or []):
                walk(h.body, True)

    walk(stmts, False)
    return cond & set(names)


_blk_plain, _blk_aug = _assigned(_blk)
_p0, _a0 = _assigned([st for st in fn.body if getattr(st, 'end_lineno', st.lineno) < A])
_before |= (_p0 | _a0)
# ★ 形参 = （块里**读到** ∪ **自增**的）−（块里**纯赋值**的）∩ 块前已绑定 − 模块级 ✓
EXT = sorted(((_read(_blk) | _blk_aug) - _blk_plain) & _before - _mod)
# ★ 回传 = （块里**纯赋值** ∪ **自增**）∩ 块后仍被读 − 模块级 ✓
RET = sorted(((_blk_plain | _blk_aug) & _read(_after)) - _mod)
_blk_as = _blk_plain | _blk_aug
print('  块内语句 %d 条 · 赋值 %d 个（纯 %d / 自增 %d）· 读 %d 个'
      % (len(_blk), len(_blk_as), len(_blk_plain), len(_blk_aug), len(_read(_blk))))
print('  ★ 必须当形参传（块读了、块外才有）: %s' % (EXT or '无 ✓'))
print('  ★ 必须回传（块里赋值、块外还读）  : %s' % (RET or '无 ✓'))
if not _blk:
    print('✗ 没圈到语句（检查行号）')
    sys.exit(2)

block = ''.join(lines[A - 1:B])
# ★ 条件赋值名：RET 里**不在** EXT（形参）里的那些，若赋值只在嵌套复合语句里 ⇒ 先置 None ✓
COND = sorted(_cond_bound(_blk, [r for r in RET if r not in EXT]))
print('  ★ 条件赋值（子函数内先置 None）: %s' % (COND or '无 ✓'))
_init = ''.join('    %s = None   # ★ 条件赋值：块内只在嵌套分支里绑 ⇒ 先占位（原函数里作用域覆盖全函数 ✓）\n' % c
                for c in COND)
helper = ('def %s(%s):\n'
          '    """S3b-3（2026-09-27）：从 `%s` **原样搬出**（R1：函数 ≤120 行 ✗）。\n\n'
          '    ★ 形参与回传**都由 AST 机器算** ✓（不人眼挑 ✗）：\n'
          '      形参 = 块里读到、块外才有：`%s`\n'
          '      回传 = 块里赋值、块外还读：`%s`\n'
          '      条件赋值（先置 None）：`%s`\n'
          '    """\n' % (NEWFN, ', '.join(EXT), FN, ', '.join(EXT) or '无', ', '.join(RET) or '无',
                     ', '.join(COND) or '无')
          + _init + block + ('    return ' + ', '.join(RET) + '\n' if RET else ''))

_call = '    %s%s\n' % (('%s = ' % ', '.join(RET)) if RET else '', '%s(%s)' % (NEWFN, ', '.join(EXT)))
out = []
for i, l in enumerate(lines, 1):
    if i == A:
        out.append('    # ★ S3b-3：本块已抽成 `%s(...)` ✓（形参/回传由 AST 机器算 ✓）\n' % NEWFN)
        out.append(_call)
    if A <= i <= B:
        continue
    out.append(l)
    if i == fn.end_lineno:
        out.append('\n\n' + helper)
new = ''.join(out)
nf = next(x for x in ast.parse(new).body if isinstance(x, ast.FunctionDef) and x.name == FN)
nh = next(x for x in ast.parse(new).body if isinstance(x, ast.FunctionDef) and x.name == NEWFN)
print('  新 %s = %d 行（原 %d）· 新函数 %s = %d 行'
      % (FN, nf.end_lineno - nf.lineno + 1, fn.end_lineno - fn.lineno + 1,
         NEWFN, nh.end_lineno - nh.lineno + 1))
if APPLY:
    io.open(P + '.bak', 'w', encoding='utf-8').write(src)
    io.open(P, 'w', encoding='utf-8').write(new)
    print('  ✓ 已写盘（.bak ✓）')
else:
    print('  （dry-run；--apply 才写 ✓）')
