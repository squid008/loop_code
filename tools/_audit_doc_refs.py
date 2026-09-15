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
HISTORICAL = ('change_log.md', 'docs/log/2026-09.md', 'docs/log/todo_done.md')
by_doc = defaultdict(list)
for cand, refs in missing.items():
    for doc, ln in refs:
        by_doc[doc].append((cand, ln))

act = {d: v for d, v in by_doc.items() if d not in HISTORICAL}
his = {d: v for d, v in by_doc.items() if d in HISTORICAL}
print('\n  ★ **活跃文档**（必须修）: %d 处，分 %d 个文档' % (sum(len(v) for v in act.values()), len(act)))
print('  ○ 历史记录（**有意不改**）: %d 处，分 %d 个文档' % (sum(len(v) for v in his.values()), len(his)))

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
