"""改动耦合面体检（只读）—— 回答「改一个功能要动几个文件」。

方法：拿项目里**已知的真实改动**（如"加一个算子""加一个关口"）当探针，
数出必须同步修改的文件数；再列出 loop_engine.py 的内部段落，判断可拆分性。

★★ 2026-09-29（v1.34.0）修：本工具**曾经自己在撒谎** ✗ —— 【C】把 `loop_engine.py` 的行数
**写死成 3134**，而它早已是 635 行 ✗（R2 拆分后没跟着改 ✗）。而它又是 §五 打分的"依据"之一 ✓
⇒ 打分基于过期数字 ✗。本次两处根因都堵上：
  ① 行数**现读现算** ✓（不再写死 ✗）；
  ② 【B】的每条"角色声明"都带一个 **必含符号** ⇒ **靠符号自证** ✓，
     缺了就当场打印「⚠ 角色声明已过期」✗（注释/文档会过期，符号不会骗人 ✓）；
  ③ 【A】的探针扫描排除 `history/` · `.codebuddy/`（归档/记忆里全是历史快照 ⇒
     把它们算进去会把"要同步几个文件"虚报到 201 个 ✗，毫无意义 ✓）。
  ④ 新增常驻守门 `tools/_test_audit_selfcheck.py` ✓ ⇒ 以后审计工具再写死数字，发版守门报出来 ✓。
"""
import ast
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
#: ★ 扫描排除：归档 + 记忆 + 缓存（都不是"要同步的源代码" ✓）
SKIP_DIRS = ('__pycache__', '.git', 'node_modules', 'history', '.codebuddy')
PROBE = 'ts_slope20'

print('=' * 100)
print('【A】探针：加 1 个算子，需要同步改动几处？（用真实名字搜全库）')
print('=' * 100)
hits = {}
SELF = os.path.abspath(__file__)          # ★ 排除自己 ✓：本文件里有探针字面量（判据要用 ✓），
#   但"加算子要同步的文件"当然**不包括审计工具自己** ✗ ⇒ 不排就会把结论多算一个 ✗。
for r, ds, fs in os.walk(ROOT):
    ds[:] = [d for d in ds if d not in SKIP_DIRS]
    for f in fs:
        if not f.endswith(('.py', '.md')):
            continue
        p = os.path.join(r, f)
        if os.path.abspath(p) == SELF:
            continue
        try:
            t = io.open(p, encoding='utf-8', errors='replace').read()
        except Exception:
            continue
        c = t.count(PROBE)
        if c:
            hits[os.path.relpath(p, ROOT)] = c
print('  `%s` 出现在 %d 个文件中（已排除 history/ 与 .codebuddy/ ✓）：' % (PROBE, len(hits)))
for p, c in sorted(hits.items()):
    tag = '★ 代码' if p.endswith('.py') else '  文档'
    print('    %s %-52s ×%d' % (tag, p, c))
code_files = [p for p in hits if p.endswith('.py')]
print('  → **同一批算子名要在 %d 个代码文件里重复出现** ⇒ 这就是"副本漂移"的物理来源' % len(code_files))

print()
print('=' * 100)
print('【B】算子相关"事实源"清单（每加一族算子都要同步的地方）')
print('=' * 100)
#: (路径, 角色, 必含符号) —— ★ 必含符号 = **自证锚点** ✓；`None` = 纯记录文件（不要求含算子名 ✓）
spots = [
    ('engine/fastops.py', ' 算子实现（唯一真实现）', PROBE),
    ('engine/ops_registry.py', '算子登记表（UNARY/BINARY/SLOW_OPS）', 'SLOW_OPS'),
    ('engine/loop_critic.py', 'B角稳定性档位（**取用**登记表 ✓）', 'SLOW_OPS'),
    ('engine/loop_llm.py', 'A角 prompt 算子说明', 'BINARY'),
    ('engine/skills/gen_skill.md', '技能文档（算子约定）', 'BINARY'),
    ('tools/_test_ops_sync.py', '算子同步守门（防漂移）', 'UNARY'),
    ('tools/_test_ops_math.py', '算子数值对拍守门', PROBE),
    ('docs/factor_roadmap.md', '算子路线（开发日志）', 'UNARY'),
    ('README.md', '总览（含算子清单）', 'UNARY'),
    ('docs/loop_todo.md', '待办 / 已完成（纯记录 ✓）', None),
    ('change_log.md', '版本变更（纯记录 ✓）', None),
]
print('    %-32s %-34s %s' % ('文件', '角色', '自证锚点'))
stale = []
for p, role, anchor in spots:
    fp = os.path.join(ROOT, p)
    if not os.path.exists(fp):
        print('    %-32s %-34s (文件不存在 ✗)' % (p, role))
        stale.append(p)
        continue
    if anchor is None:
        print('    %-32s %-34s —（纯记录，不锚 ✓）' % (p, role))
        continue
    ok = anchor in io.open(fp, encoding='utf-8', errors='replace').read()
    print('    %-32s %-34s %s %s' % (p, role, anchor, '✓在' if ok else '✗缺'))
    if not ok:
        stale.append(p)
print('  → **加 1 个算子 ≈ 要动 %d 处**（其中 %d 处带锚点自证 ✓）' % (
    len(spots), sum(1 for _, _, a in spots if a)))
if stale:
    print('  ⚠⚠ **上面标 ✗ 的"角色声明"已过期** ✗ —— 文件在、但里面已经没有那个符号了：%s'
          % ', '.join(stale))
    print('     ⇒ 请更新本工具的 `spots`（旧声明会把"要同步的地方"指错 ✗ —— 这正是 3134 那类错误的同族 ✓）')
else:
    print('  ✓ 以上 %d 条角色声明**全部自证通过** ✓（符号都还在老地方 ✓）' % len(spots))

print()
print('=' * 100)
p = os.path.join(ROOT, 'engine', 'loop_engine.py')
ls = io.open(p, encoding='utf-8', errors='replace').read().splitlines()
print('【C】loop_engine.py 内部段落（%d 行 —— 判断可拆分性）' % len(ls))   # ★ 现读现算 ✓（不再写死 ✗）
print('=' * 100)
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
src = io.open(p, encoding='utf-8', errors='replace').read()
tree = ast.parse(src)
top = [((getattr(n, 'end_lineno', n.lineno) - n.lineno + 1), type(n).__name__,
        getattr(n, 'name', '?')) for n in tree.body
       if isinstance(n, (ast.FunctionDef, ast.ClassDef))]
print('  顶层定义 %d 个：' % len(top))
for n, k, name in sorted(top, reverse=True):
    if n >= 25:
        print('    %5d 行  %-10s %s' % (n, k, name))
docs = [n for n, k, name in top if k == 'FunctionDef' and n < 25]
print('    ... 另有 %d 个 <25 行的小函数' % len(docs))
print()
print('（只读体检 ✓；行数/段落均现读现算 ✓）')
sys.exit(1 if stale else 0)
