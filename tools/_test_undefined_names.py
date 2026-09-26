# -*- coding: utf-8 -*-
"""_test_undefined_names.py — 扫「**用了、却在本作用域链上都没绑定过**」的名字（未定义名）。

## 为什么要它（2026-09-26 两次真事故）
L3 文件级拆分把函数搬进新模块时，**手写的 import 清单漏了名字**：
  ① `loop_stage.py` 用了 `HERE` / `trim_cache_mb` / `ts_mean` 但没 import ✗
  ② `loop_persist.py` 用了 `LIB_ENTRIES` / `time` 但没 import ✗
⇒ `py_compile` 过 ✓、全量回归过 ✓、同 seed 复跑对照也过 ✓ ——
**因为那些代码路径只在特定参数下才走到**（`HERE` 那处只在 `all` 池「外部池注入」时执行，
而对照用的是 `--mine_pool=500` ⇒ **跳过了它** ✗）⇒ **发版后重启挖掘，第一批就 `NameError` 崩** ✗✗
（更隐蔽的第三类：`_l2_pool_tags` 用了**调用方的局部变量** `pool_rows` ——
 「全文件绑过就算」的宽松判据**抓不到**它 ✗ ⇒ 所以本检查器是**作用域感知**的 ✓）

⇒ 教训：**`py_compile` 只查语法、不查名字**；搬函数后必须做一次**作用域感知**的名字解析 ✓
（pyflakes 那类工具干的就是这件事；本机没装 pyflakes ⇒ 这里用 ast 做**最小可用版**）

## 判据
对每个函数/lambda（含嵌套），检查它体内的 `Name`（Load）能否解析到：
  ① 它自己的绑定（形参 / 赋值 / for / with / except / import / 嵌套 def 名 / global+nonlocal 声明）；
  ② **任一外层函数**的绑定（闭包 ✓）；
  ③ 模块级绑定；
  ④ 内置名。
四条都不满足 ⇒ 报「未定义」✓
★ 刻意**宽松**（宁可少报）：把 class 体也当一层作用域、把推导式目标也算进当前作用域 ⇒
  只漏不误报（这几类极少是 bug 源 ✗）。对本项目反复踩的「搬函数漏 import / 用了调用方局部」100% 有效 ✓
"""
import ast
import builtins
import io
import os
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOP = ('engine', 'tools', 'standard')
DUNDER = {'__file__', '__name__', '__doc__', '__package__', '__spec__', '__loader__',
          '__builtins__', '__debug__', '__class__', '__path__', '__all__', '__version__'}
BUILTINS = set(dir(builtins))


def bind_target(node, out):
    """收集赋值目标里的裸名（Name / tuple / list / starred）。"""
    if isinstance(node, ast.Name):
        out.add(node.id)
    elif isinstance(node, (ast.Tuple, ast.List)):
        for e in node.elts:
            bind_target(e, out)
    elif isinstance(node, ast.Starred):
        bind_target(node.value, out)


class Scope:
    def __init__(self, parent):
        self.parent = parent
        self.bound = set()          # 本作用域绑定的名字
        self.loads = []             # [(name, lineno)] 本作用域**直接**载入（不含子作用域）
        self.children = []

    def chain_bound(self):
        """本作用域 + 所有外层作用域的绑定（闭包链）。"""
        s, out = self, set()
        while s is not None:
            out |= s.bound
            s = s.parent
        return out


def _args_of(a):
    return list(a.posonlyargs) + list(a.args) + list(a.kwonlyargs)


def walk_scoped(node, sc):
    """遍历 node，把绑定/载入记到 sc；遇到函数/类/推导式就建子作用域。"""
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        sc.bound.add(node.name)
        for d in node.decorator_list:
            walk_scoped(d, sc)
        for d in node.args.defaults:
            walk_scoped(d, sc)
        for d in (node.args.kw_defaults or []):
            if d is not None:
                walk_scoped(d, sc)
        fn = Scope(sc)
        sc.children.append(fn)
        for a in _args_of(node.args) + [node.args.vararg, node.args.kwarg]:
            if a is not None:
                fn.bound.add(a.arg)
        for st in node.body:
            walk_scoped(st, fn)
        return
    if isinstance(node, ast.Lambda):
        for d in node.args.defaults:
            walk_scoped(d, sc)
        fn = Scope(sc)
        sc.children.append(fn)
        for a in _args_of(node.args) + [node.args.vararg, node.args.kwarg]:
            if a is not None:
                fn.bound.add(a.arg)
        walk_scoped(node.body, fn)
        return
    if isinstance(node, ast.ClassDef):
        sc.bound.add(node.name)
        for d in node.decorator_list:
            walk_scoped(d, sc)
        for b in node.bases:
            walk_scoped(b, sc)
        cls = Scope(sc)
        sc.children.append(cls)
        for st in node.body:
            walk_scoped(st, cls)
        return
    if isinstance(node, (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)):
        comp = Scope(sc)
        sc.children.append(comp)
        for g in node.generators:
            walk_scoped(g.iter, comp)
            bind_target(g.target, comp.bound)
            for i in g.ifs:
                walk_scoped(i, comp)
        if isinstance(node, ast.DictComp):
            walk_scoped(node.key, comp)
            walk_scoped(node.value, comp)
        else:
            walk_scoped(node.elt, comp)
        return
    # ---- 普通节点：先记绑定，再递归子节点 ----
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        for a in node.names:
            sc.bound.add((a.asname or a.name).split('.')[0])
        return
    if isinstance(node, ast.Assign):
        for t in node.targets:
            bind_target(t, sc.bound)
            walk_scoped(t, sc)
        walk_scoped(node.value, sc)
        return
    if isinstance(node, (ast.AnnAssign, ast.AugAssign)):
        bind_target(node.target, sc.bound)
        walk_scoped(node.target, sc)
        if node.value is not None:
            walk_scoped(node.value, sc)
        return
    if isinstance(node, (ast.For, ast.AsyncFor)):
        bind_target(node.target, sc.bound)
        walk_scoped(node.target, sc)
        walk_scoped(node.iter, sc)
        for st in node.body + node.orelse:
            walk_scoped(st, sc)
        return
    if isinstance(node, ast.withitem):
        walk_scoped(node.context_expr, sc)
        if node.optional_vars is not None:
            bind_target(node.optional_vars, sc.bound)
            walk_scoped(node.optional_vars, sc)
        return
    if isinstance(node, ast.ExceptHandler):
        if node.name:
            sc.bound.add(node.name)
        if node.type is not None:
            walk_scoped(node.type, sc)
        for st in node.body:
            walk_scoped(st, sc)
        return
    if isinstance(node, (ast.Global, ast.Nonlocal)):
        sc.bound.update(node.names)
        return
    if isinstance(node, ast.Name):
        if isinstance(node.ctx, ast.Load):
            sc.loads.append((node.id, node.lineno))
        else:
            sc.bound.add(node.id)
        return
    # 其余节点：递归所有直接子节点
    for child in ast.iter_child_nodes(node):
        walk_scoped(child, sc)


def check(path):
    rel = os.path.relpath(path, ROOT).replace('\\', '/')
    try:
        tree = ast.parse(io.open(path, encoding='utf-8', errors='replace').read())
    except SyntaxError as e:
        return ['  [语法错误] %s :: %s' % (rel, e)]
    root = Scope(None)
    for st in tree.body:
        walk_scoped(st, root)
    miss = {}
    stack = [root]
    while stack:
        sc = stack.pop()
        stack.extend(sc.children)
        if sc.parent is None:
            allowed = root.bound                      # 模块级：只看模块绑定
        else:
            allowed = sc.chain_bound()                # 函数级：闭包链上的绑定
        for name, ln in sc.loads:
            if name in allowed or name in BUILTINS or name in DUNDER:
                continue
            miss.setdefault(name, ln)
    if not miss:
        return []
    out = ['  [未定义] %s' % rel]
    for name, ln in sorted(miss.items(), key=lambda kv: kv[1]):
        out.append('      L%-5d %s' % (ln, name))
    return out


def main():
    files = []
    for top in TOP:
        d = os.path.join(ROOT, top)
        for r, ds, fs in os.walk(d):
            ds[:] = [x for x in ds if x != '__pycache__']
            for f in sorted(fs):
                if f.endswith('.py'):
                    files.append(os.path.join(r, f))
    bad = 0
    for p in sorted(files):
        lines = check(p)
        if lines:
            bad += len(lines) - 1
            print('\n'.join(lines))
    print('\n  扫描 %d 个文件；**未定义名 %d 处**' % (len(files), bad))
    if bad:
        print('  ⇒ 基本是「搬函数时漏 import」或「用了调用方的局部变量」'
              '⇒ 补 import / 改模块引用（`_P.X` / `_C.X`）/ 把变量改成参数或返回值 ✓')
        sys.exit(1)
    print('  ✓ 无「用了但作用域链上没绑定」的名字')
    sys.exit(0)


if __name__ == '__main__':
    main()
