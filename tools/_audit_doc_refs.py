# -*- coding: utf-8 -*-
"""_audit_doc_refs.py — 【只读】扫**所有文档**里引用的**仓库内路径**，检查它是否还存在。

## 为什么（2026-09-15 实录）
用户：「`loop_todo.md` 是不是又要清理了？看看里面有没有错的？有没有要归档的？把各个文档再查一轮」
⇒ 实测立刻抓到：`loop_todo.md §0`（一屏速览）停在 09-13 · `§4.2`（现役参数）缺 4 个生产参数 ·
  `§4.6`（自称"新会话最需要的一页"）列了 **~18 个 `ai_test/*` 工具，而 `ai_test/` 已被整体归档** ✗✗

## 判据
扫 `docs/**/*.md` + 根 `*.md` 里的**反引号内**或行内的**仓库相对路径**（含 `/`、以已知顶层目录开头、
或形如 `xxx.py`），检查 `os.path.exists` ⇒ 不存在就报 ✓
★ 排除：`docs/history`→`history` 已迁移（同样判存在性即可）· 外部绝对路径（`E:\\rq` 等另外报）
"""
import io
import os
import re
import sys
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ROOT = r'D:\loop_code'
TOPDIRS = ('engine', 'tools', 'standard', 'docs', 'history', 'ai_test', 'research',
           'strategies', 'facs', 'scripts')

# 收集文档
docs = []
for d, pat in ((os.path.join(ROOT, 'docs'), r'\.md$'), (ROOT, r'\.md$')):
    if d == ROOT:
        for f in sorted(os.listdir(d)):
            if f.endswith('.md'):
                docs.append(os.path.join(d, f))
    else:
        for r, ds, fs in os.walk(d):
            ds[:] = [x for x in ds if x not in ('__pycache__',)]
            for f in sorted(fs):
                if f.endswith('.md'):
                    docs.append(os.path.join(r, f))
docs = sorted(set(docs))

# ★★★ 路径模式（2026-09-15 修订：**只认带目录前缀的**）----
#   ⚠ 初版把**裸文件名**（如 `values_q.h5`）也当路径 ⇒ **系统性误报** ✗
#     实例：`loop_todo:351` 写"不能用 `values_q.h5` 做中性化" —— 那是**泛指名字**，
#     而实体在 `facs/<2位hex>/<name>/values_q.h5`（实测 57 份）⇒ 不是路径引用 ✗
#   ⇒ **裸文件名一律不判**（除非它前面有目录）✓
PATHRE = re.compile(
    r'(?:`)((?:' + '|'.join(TOPDIRS) + r')/[\w/.\-]+\.(?:py|md|csv|json|txt|ps1|h5|pkl))(?::\d+)?(?:`)'
    r'|(?<![`\w/])((?:' + '|'.join(TOPDIRS) + r')/[\w/.\-]+\.(?:py|md|csv|json|txt|ps1))')

missing = defaultdict(list)   # path -> [(doc, line)]
found = 0
for p in docs:
    rel_doc = os.path.relpath(p, ROOT).replace('\\', '/')
    t = io.open(p, encoding='utf-8', errors='replace').read()
    for i, l in enumerate(t.splitlines(), 1):
        for m in PATHRE.finditer(l):
            cand = m.group(1) or m.group(2)
            if not cand or '*' in cand:
                continue
            cand = cand.split(':')[0].lstrip('./')
            full = os.path.join(ROOT, cand.replace('/', os.sep))
            if os.path.exists(full):
                found += 1
            else:
                missing[cand].append((rel_doc, i))

print('=' * 100)
print('【文档路径引用检查】%d 个文档；命中 %d 处存在 ✓；**%d 处不存在** ✗'
      % (len(docs), found, len(missing)))
print('=' * 100)

# ★★★ 关键分类：**历史记录改不得** —— 它们记录"当时用了什么"，路径失效是正常的 ✓
#
# ★★★★★ 2026-09-23（用户："检查各种 md、对项目做个体检"）本轮**补全**了两处漏判：
#   ① `docs/loop_journal*.md` 也是**逐代日志**（与 change_log 同性：记录"当时跑了什么" ✓）——
#      原来不在 HISTORICAL 里 ⇒ 它那 4 处失效引用被算成"必须修" ✗（会误导人改日志 ✗）
#   ② **行级引文**：README「版本与回退」表、`loop_todo.md` 的台账/待办里，会出现
#      "\`旧路径\` → 新名" 这种**引用当时的名字**的句子 ⇒ 改了**反而错** ✗（而按文档分类盖不住 ✗）
#      ⇒ 加一张**显式行级名单** `ALLOW_LINES`（附理由 ✓）：命中即算"有意不改" ✓
#   ⇒ 从此本工具的"活跃文档（必须修）"应当为 **0**；不为 0 就是真问题 ✓
HISTORICAL = ('change_log.md', 'docs/log/2026-09.md', 'docs/log/todo_done.md',
              'docs/loop_journal.md', 'docs/loop_journal_300.md', 'docs/loop_journal_500.md',
              'docs/loop_journal_1000.md', 'docs/loop_journal_50.md')
# ★★ 白名单按 **(文档, 引用串)** 做键 —— **不按行号** ✗
#   为什么（v1.21.44 → v1.21.45，**当天就踩到** ✓）：第一版用行号做键 ✗，而我在同一批里往这些文档
#   **加了说明文字**（行号整体下移 ✗）⇒ 白名单**全部失配**、那 6 处引文"复活"成"必须修" ✗✗
#   ⇒ 教训：**行号是位置、不是身份**；对这种"同一句话的引用"必须按内容/key 匹配 ✓
ALLOW_REFS = {
    ('README.md', 'tools/_chk_ai_tone.py'):
        '版本表引文（v1.3.2 那行描述"当时改了什么"，旧脚本名是原文 ✓）',
    ('README.md', 'tools/calib_gates.py'):
        '版本表引文（v0.20.4 复盘，引的是当时的名字；现名 `calib_dedup_leaf.py` ✓）',
    ('docs/loop_todo.md', 'ai_test/calib_gates.py'):
        '待办条目引文（它说的就是"文档里仍写旧路径"，属**被记录的对象** ✓）',
    ('docs/loop_todo.md', 'tools/calib_gates.py'):
        '台账引文（记录"`tools/calib_gates.py` → `calib_dedup_leaf.py`"这次改名 ✓）',
    ('docs/factor_roadmap.md', 'docs/loop_ext_leaves.md'):
        '原文自己写着"（2026-09-09 并入本档案）"⇒ 保留出处 ✓',
}
by_doc = defaultdict(list)
n_allow = 0
for cand, refs in missing.items():
    for doc, ln in refs:
        if (doc, cand) in ALLOW_REFS:
            n_allow += 1
            continue
        by_doc[doc].append((cand, ln))

act = {d: v for d, v in by_doc.items() if d not in HISTORICAL}
his = {d: v for d, v in by_doc.items() if d in HISTORICAL}
print('\n  ★ **活跃文档**（必须修）: %d 处，分 %d 个文档' % (sum(len(v) for v in act.values()), len(act)))
print('  ○ 历史记录（**有意不改**）: %d 处，分 %d 个文档' % (sum(len(v) for v in his.values()), len(his)))
if n_allow:
    # ★ 显式报出来（**明示**而不是"悄悄放过" ✓ —— 白名单要让人看得见，才不会被滥用 ✓）
    print('  ○ 行级引文（白名单，**有意保留**）: %d 处 —— 都是"记录当时叫什么名"的句子 ✓' % n_allow)
    for (d0, c0), why in sorted(ALLOW_REFS.items()):
        print('      %-26s %-34s %s' % (d0, c0, why))

for doc in sorted(act, key=lambda x: -len(act[x])):
    print('\n  ===== %s（%d 处）=====' % (doc, len(act[doc])))
    # 按路径前缀分组，压缩输出
    pref = defaultdict(list)
    for cand, ln in act[doc]:
        pref[cand.split('/')[0]].append((cand, ln))
    for top in sorted(pref, key=lambda x: -len(pref[x])):
        items = sorted(pref[top])
        print('    [%s/] %d 处：' % (top, len(items)))
        for cand, ln in items[:14]:
            print('        L%-5d %s' % (ln, cand[:74]))
        if len(items) > 14:
            print('        ...（另 %d 处）' % (len(items) - 14))
