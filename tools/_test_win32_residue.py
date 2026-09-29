# -*- coding: utf-8 -*-
"""★ 不变量守门：**Win32 / PowerShell 专有代码只许出现在 `engine/os_compat.py`** ✓。

## 为什么要有它（`loop_todo §1.40.3` · v1.33.0 可移植性平台化收尾）
把 `taskkill` / `Get-CimInstance` / `tasklist` / `wmic` / `GlobalMemoryStatusEx` 收敛到
`engine/os_compat.py` 之后，就有一条**可机器检查**的不变量 ✓：
    全仓库在这条线上应该只剩 `os_compat` 的 **Windows 分支** ✓（Linux 走它的 POSIX 分支 ✓）。
⇒ 以后谁再散落一处，本守门**当场报出来** ✓（比"记得别写"可靠得多 ✓）。
⚠ 这正是本项目一贯的做法：**把纪律变成可执行的守门** ✓（同 `_test_stop_scope` / `_test_engine_mem_budget` ✓）。

## 口径（避免误报 —— 本项目注释里大量"讲道理"时会提到这些词 ✓）
* 只扫 **正式代码**：`engine/` + `tools/` + `dashboard/` ✓
  （`ai_test/` 是**一次性排查脚本** ⇒ 按设计排除 ✓ —— 它们不进正式路径 ✓）
* 逐**命中位置**判断是不是"说明文字"，三条规则 ✓：
  ① 命中落在行内 `#` 注释里 ✓；
  ② 命中落在**含中文的引号串**里 ✓（如 `chk('★ 全程没有调用 taskkill' ✓)` = 断言文案 ✓）；
  ③ 本行含项目标记 `✗`/`✓` ✓ —— 它们**只**出现在注释与文档串里 ✓
     （含多行 docstring 的中间行 ✓，那些行既不在 `#` 后、也不在引号里 ✗ ⇒ 必须靠这条 ✓）。
* 判据是"**代码行**"而不是"字符串出现过" ✓ —— 所以 `os_compat` 自己的 Windows 分支会被列出来 ✓
  （那是**允许**的 ✓），别的文件出现才算违规 ✓。

用法: python tools/_test_win32_residue.py      （<1 秒；只读文件，不碰网络/不写盘 ✓）
"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAT = re.compile(r'Get-CimInstance|powershell|taskkill|tasklist|wmic|GlobalMemoryStatusEx')
SCAN_DIRS = ('engine', 'tools', 'dashboard')
ALLOW = 'engine/os_compat.py'          # ★ 唯一允许出现专有代码的地方（Windows 分支 ✓）
#: ★ 本守门**自己**必然含这些词（① 判据的 `PAT` 模式串 ✓ ② 自证用例 `_toy` ✓ ③ 文件头的说明 ✓）
#: ⇒ 按文件名排除自己 ✓ —— ⚠ 这不是放水 ✗：本文件里**没有一处真的调用**那些接口 ✓
#: （最后一条断言会反过来证明这一点 ✓）。
ALLOW_SELF = 'tools/_test_win32_residue.py'
SKIP_DIRS = ('__pycache__', '.git', 'node_modules', 'history')
FAIL = []


def chk(desc, cond, hint=''):
    print('  %s %s%s' % ('✓' if cond else '✗', desc, ('（%s）' % hint) if hint else ''))
    if not cond:
        FAIL.append(desc)


def is_prose(line, m):
    """这次命中是不是"说明文字"？（判据见文件头 · 按**命中位置**判 ✓，不按整行感觉 ✗）"""
    head = line.split('#')[0]
    if m.start() >= len(head):
        return True
    if ('✗' in line) or ('✓' in line):
        return True
    for q in re.finditer(r'"[^"]*"|\'[^\']*\'', line):
        if q.start() <= m.start() < q.end() and re.search(r'[\u4e00-\u9fff]', q.group(0)):
            return True
    return False


hits = {}
scanned = 0
for d in SCAN_DIRS:
    base = os.path.join(ROOT, d)
    for r, _, fs in os.walk(base):
        if any(x in r for x in SKIP_DIRS):
            continue
        for f in fs:
            if not f.endswith('.py'):
                continue
            p = os.path.join(r, f)
            scanned += 1
            rel = os.path.relpath(p, ROOT).replace(os.sep, '/')
            for i, l in enumerate(io.open(p, encoding='utf-8', errors='replace').read().splitlines(), 1):
                if any(not is_prose(l, m) for m in PAT.finditer(l)):
                    hits.setdefault(rel, []).append((i, l.strip()[:96]))

print('=' * 92)
print('不变量：Win32/PowerShell 专有代码只许出现在 %s（扫 %d 个文件 ✓）' % (ALLOW, scanned))
print('=' * 92)
for rel, v in sorted(hits.items()):
    print('  %-44s %d 处' % (rel, len(v)))
    for i, s in v[:4]:
        print('        L%-5d %s' % (i, s))
print()
chk('%s 仍是唯一含专有代码的文件（实 %d 处 Windows 分支 ✓）'
    % (ALLOW, len(hits.get(ALLOW, []))), len(hits.get(ALLOW, [])) > 0)
extra = {k: v for k, v in hits.items() if k not in (ALLOW, ALLOW_SELF)}
chk('★ 没有别的文件散落专有代码（实 %d 个违规文件 ✓）' % len(extra), not extra,
    '违规: %s' % ', '.join(sorted(extra)) if extra else '')
# 反面自证：判据必须**真的能抓到**（否则"零违规"毫无意义 ✗）
_self = open(__file__, encoding='utf-8').read()
_toy = "subprocess.run(['taskkill', '/PID', '1', '/T', '/F'])"
chk('★ 判据自证：故意喂一行专有代码 ⇒ 必须被判为**违规** ✓',
    any(not is_prose(_toy, m) for m in PAT.finditer(_toy)))
chk('★ 判据自证：注释行 ⇒ 必须被判为**说明文字** ✓',
    all(is_prose('# 这里用 taskkill 讲道理 ✓', m) for m in PAT.finditer('# 这里用 taskkill 讲道理 ✓')))
chk('守门自己不去碰那些词（本文件里只在规则/文案里出现 ✓）', 'subprocess.run' not in _self.split('_toy = ')[0])

print()
print('✗ 失败：%s' % FAIL if FAIL else
      '✓ 全过：专有代码只剩 %s 的 Windows 分支（Linux 走它的 POSIX 分支 ✓）' % ALLOW)
sys.exit(1 if FAIL else 0)
