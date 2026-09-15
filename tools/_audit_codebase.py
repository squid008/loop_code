"""代码库体检（软件工程视角）—— 只读，不改任何东西。

用途：回答「项目是否架构混乱/零碎 ⇒ 是否该清扫」时，用**真实数字**而不是感觉。
输出：① 文件规模分布 ② 巨型文件/函数清单 ③ 重复代码 ④ 耦合与契约 ⑤ 各维度评分依据
"""
import io
import os
import re
import sys
import ast
import hashlib
from collections import defaultdict, Counter

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIRS = ('engine', 'tools', 'research', 'standard', 'strategies')


def py_files(d):
    out = []
    for r, _, fs in os.walk(os.path.join(ROOT, d)):
        if '__pycache__' in r:
            continue
        out += [os.path.join(r, f) for f in fs if f.endswith('.py')]
    return out


def line_count(p):
    try:
        return len(io.open(p, encoding='utf-8', errors='replace').read().splitlines())
    except Exception:
        return 0


print('=' * 100)
print('【1】文件规模分布')
print('=' * 100)
allf = []
for d in DIRS:
    fs = py_files(d)
    tot = sum(line_count(f) for f in fs)
    big = [(line_count(f), f) for f in fs]
    big.sort(reverse=True)
    print('  %-12s %3d 个文件  %7d 行   最大: %s' % (
        d, len(fs), tot, ', '.join('%s(%d行)' % (os.path.basename(f), n) for n, f in big[:3])))
    allf += [(n, f, d) for n, f in big]
print('  ' + '-' * 96)
print('  合计 %d 个文件  %d 行' % (len(allf), sum(n for n, _, _ in allf)))

print()
print('=' * 100)
print('【2】★ 巨型文件（>1500 行 —— 单次编辑无法整体装进上下文）')
print('=' * 100)
huge = [(n, f) for n, f, _ in allf if n > 1500]
for n, f in sorted(huge, reverse=True):
    print('  %6d 行  %-42s %8.1f KB' % (n, os.path.relpath(f, ROOT), os.path.getsize(f) / 1024))
print('  → 巨型文件 %d 个，占全部代码 %d 行的 %.1f%%' % (
    len(huge), sum(n for n, _ in huge), 100.0 * sum(n for n, _ in huge) / max(sum(n for n, _, _ in allf), 1)))

print()
print('=' * 100)
print('【3】★ 最长函数 / 最深层级（影响"改一处、稳一处"）')
print('=' * 100)
funcs = []
for n, f, _ in allf:
    try:
        tree = ast.parse(io.open(f, encoding='utf-8', errors='replace').read())
    except Exception:
        continue
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            end = getattr(node, 'end_lineno', node.lineno)
            funcs.append((end - node.lineno + 1, os.path.relpath(f, ROOT), node.name, node.lineno))
funcs.sort(reverse=True)
print('  函数总数 %d' % len(funcs))
print('  最长的 15 个：')
for n, f, name, ln in funcs[:15]:
    flag = '  ★★ 超长' if n > 300 else ('  ★' if n > 150 else '')
    print('    %5d 行  %-40s %s()  L%d%s' % (n, f, name, ln, flag))
over300 = [x for x in funcs if x[0] > 300]
over150 = [x for x in funcs if 150 < x[0] <= 300]
print('  → 超 300 行函数 %d 个；150~300 行 %d 个' % (len(over300), len(over150)))

print()
print('=' * 100)
print('【4】★ 重复代码（AST 规范化后的重复子树 —— "副本漂移"的温床）')
print('=' * 100)


def norm_func(src, node):
    try:
        seg = ast.get_source_segment(src, node)
    except Exception:
        return None
    if not seg:
        return None
    # 去掉注释/空行/字符串字面量内容（只保留结构），便于发现"逻辑重复"
    lines = []
    for l in seg.splitlines():
        l = l.split('#')[0].rstrip()
        if not l.strip():
            continue
        l = re.sub(r'(["\']).*?\1', 'S', l)
        l = re.sub(r'\s+', '', l)
        lines.append(l)
    body = '\n'.join(lines)
    return body if len(lines) >= 8 else None


duphash = defaultdict(list)
for n, f, _ in allf:
    try:
        src = io.open(f, encoding='utf-8', errors='replace').read()
        tree = ast.parse(src)
    except Exception:
        continue
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            b = norm_func(src, node)
            if b:
                duphash[hashlib.md5(b.encode()).hexdigest()].append(
                    (os.path.relpath(f, ROOT), node.name, node.lineno))
dupgroups = [(v[0][1], len(v), v) for v in duphash.values() if len(v) > 1]
dupgroups.sort(key=lambda x: -x[1])
print('  重复函数体（≥8 行、规范化后完全相同）共 %d 组：' % len(dupgroups))
for name, cnt, v in dupgroups[:12]:
    print('    ×%d  %s' % (cnt, name))
    for f, fn, ln in v[:6]:
        print('           %-42s %s() L%d' % (f, fn, ln))
    if len(v) > 6:
        print('           ... 另 %d 处' % (len(v) - 6))

print()
print('=' * 100)
print('【5】★ 跨文件"隐式契约"（同一个名字在多个文件各自定义 —— 改一处必漏）')
print('=' * 100)
const_defs = defaultdict(list)
for n, f, _ in allf:
    try:
        tree = ast.parse(io.open(f, encoding='utf-8', errors='replace').read())
    except Exception:
        continue
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id.isupper():
                    const_defs[t.id].append((os.path.relpath(f, ROOT), node.lineno))
multi = {k: v for k, v in const_defs.items() if len(v) > 1}
print('  同名全大写常量在多个文件**各自定义**的共 %d 个：' % len(multi))
for k in sorted(multi, key=lambda x: -len(multi[x]))[:15]:
    print('    %-28s ×%d  %s' % (k, len(multi[k]),
                                 ', '.join('%s:L%d' % (f, l) for f, l in multi[k][:4])))

print()
print('=' * 100)
print('【6】★ 巨型内联字符串（prompt/模板 —— 编辑器锚点极易撞车）')
print('=' * 100)
for n, f, _ in allf:
    try:
        src = io.open(f, encoding='utf-8', errors='replace').read()
        tree = ast.parse(src)
    except Exception:
        continue
    st = [(getattr(x, 'end_lineno', x.lineno) - x.lineno + 1, x.lineno)
          for x in ast.walk(tree)
          if isinstance(x, ast.Constant) and isinstance(x.value, str) and len(x.value) > 4000]
    for ln_cnt, ln in sorted(st, reverse=True)[:3]:
        print('    %-42s 字符串 %5d 行  @L%d' % (os.path.relpath(f, ROOT), ln_cnt, ln))

print()
print('=' * 100)
print('【7】文档规模（开发日志 vs 有效文档）')
print('=' * 100)
for f in ('README.md', 'change_log.md', 'docs/factor_roadmap.md', 'docs/loop_todo.md'):
    p = os.path.join(ROOT, f)
    if os.path.exists(p):
        print('    %-28s %7d 行  %8.1f KB' % (f, line_count(p), os.path.getsize(p) / 1024))
for p in sorted(os.listdir(os.path.join(ROOT, 'docs'))):
    if p.endswith('.md') and p.startswith('loop_journal'):
        fp = os.path.join(ROOT, 'docs', p)
        print('    %-28s %7d 行  %8.1f KB' % ('docs/' + p, line_count(fp), os.path.getsize(fp) / 1024))
