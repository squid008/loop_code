"""改动耦合面体检（只读）—— 回答「改一个功能要动几个文件」。

方法：拿项目里**已知的真实改动**（如"加一个算子""加一个关口"）当探针，
数出必须同步修改的文件数；再列出 loop_engine.py 的内部段落，判断可拆分性。
"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

print('=' * 100)
print('【A】探针：加 1 个算子，需要同步改动几处？（用真实名字搜全库）')
print('=' * 100)
probe = 'ts_slope20'
hits = {}
for r, ds, fs in os.walk(ROOT):
    ds[:] = [d for d in ds if d not in ('__pycache__', '.git', 'node_modules')]
    for f in fs:
        if not f.endswith(('.py', '.md')):
            continue
        p = os.path.join(r, f)
        try:
            t = io.open(p, encoding='utf-8', errors='replace').read()
        except Exception:
            continue
        c = t.count(probe)
        if c:
            hits[os.path.relpath(p, ROOT)] = c
print('  `%s` 出现在 %d 个文件中：' % (probe, len(hits)))
for p, c in sorted(hits.items()):
    tag = '★ 代码' if p.endswith('.py') else '  文档'
    print('    %s %-52s ×%d' % (tag, p, c))
code_files = [p for p in hits if p.endswith('.py')]
print('  → **同一批算子名要在 %d 个代码文件里重复出现** ⇒ 这就是"副本漂移"的物理来源' % len(code_files))

print()
print('=' * 100)
print('【B】算子相关"事实源"清单（每加一族算子都要同步的地方）')
print('=' * 100)
spots = [
    ('engine/fastops.py', '算子实现（唯一真实现）'),
    ('engine/loop_engine.py', 'UNARY/BINARY 注册表'),
    ('engine/loop_critic.py', 'SLOW_OPS 稳定性档位'),
    ('engine/loop_llm.py', 'A角 prompt 算子说明'),
    ('tools/_test_ops_sync.py', '算子同步测试（防漂移）'),
    ('tools/_test_ops_math.py', '数值对拍测试'),
    ('docs/factor_roadmap.md', '开发日志'),
    ('docs/loop_todo.md', '待办/已完成'),
    ('change_log.md', '版本变更'),
    ('README.md', '版本表'),
]
print('    %-32s %s' % ('文件', '角色'))
for p, role in spots:
    exists = os.path.exists(os.path.join(ROOT, p))
    print('    %-32s %s%s' % (p, role, '' if exists else '  (不存在)'))
print('  → **加 1 个算子 ≈ 要动 %d 处**（其中 %d 处是同一信息的副本）' % (
    len(spots), len(spots) - 1))

print()
print('=' * 100)
print('【C】loop_engine.py 内部段落（3134 行 —— 判断可拆分性）')
print('=' * 100)
p = os.path.join(ROOT, 'engine', 'loop_engine.py')
ls = io.open(p, encoding='utf-8', errors='replace').read().splitlines()
secs = []
for i, l in enumerate(ls, 1):
    m = re.match(r'^(?:#\s*={2,}|#\s*-{2,})\s*(.+)$', l)
    if m and len(m.group(1).strip()) > 3:
        secs.append((i, m.group(1).strip()[:76]))
print('  注释分隔的段落标题共 %d 个（前 34 个）：' % len(secs))
for i, t in secs[:34]:
    print('    L%-5d %s' % (i, t))

print()
print('=' * 100)
print('【D】顶层函数/类的分布（loop_engine.py 里到底装了多少职责）')
print('=' * 100)
import ast
src = io.open(p, encoding='utf-8', errors='replace').read()
tree = ast.parse(src)
top = [(getattr(n, 'end_lineno', n.lineno) - n.lineno + 1, type(n).__name__,
        getattr(n, 'name', '?')) for n in tree.body
       if isinstance(n, (ast.FunctionDef, ast.ClassDef))]
print('  顶层定义 %d 个：' % len(top))
for n, k, name in sorted(top, reverse=True):
    if n >= 25:
        print('    %5d 行  %-10s %s' % (n, k, name))
docs = [n for n, k, name in top if k == 'FunctionDef' and n < 25]
print('    ... 另有 %d 个 <25 行的小函数' % len(docs))
