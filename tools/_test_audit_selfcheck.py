# -*- coding: utf-8 -*-
"""★ 守门：**审计工具自己不许撒谎** ✓（`docs/maintainability.md §五` 的打分依据是它们 ✓）。

## 为什么（2026-09-29 · v1.34.0 实证）
`tools/_audit_coupling.py` 曾把 `loop_engine.py` 的行数**写死成 3134** ✗，而它早已是 635 行 ✗
（R2 拆分后没跟着改 ✗）—— 该工具是 §五 打分的**依据之一** ⇒ **打分建立在过期数字上** ✗✗。
⇒ 本守门把"工具不许撒谎"变成**可执行**的 ✓（与 `_test_win32_residue` 同一思路 ✓）。

## 它查两件
1. **活动数字** ✗：三个审计工具的**打印/字符串**里不许出现"写死的规模数字"
   （`3134 行` / `920 个` / `71 KB` … ✗ —— 凡不随代码变化自动更新，就一定会过期 ✓）。
   ⚠ 判据刻意留出**合法例外** ✓（避免变成"什么都不能写" ✗）——
   ★ 原则：**政策数字**（阈值/范围/展示上限 ✓）允许写死 ✓；**读数**必须现算 ✓。
     · 阈值/范围：`>1500 行` / `≤800 行` / `~120 行` / `150~300 行` ✓（那是**规则** ✓）；
     · 展示上限：`最长的 15 个` / `前 34 个` ✓（那是**界面选择** ✓）；
     · 格式符：`%d 行` / `%s 行` ✓（**现算现填** ✓，正是我们要的做法 ✓）；
     · 注释与文档串里的**历史陈述**（含 `✗`/`✓` 的项目标记 ✓）不算 ✗。
   ⇒ 而"（**3134 行** —— 判断可拆分性）"这种**读数**照样会被抓 ✓（它前面既不是阈值也不是上限 ✓）。
2. **能跑通** ✓：三个工具都要 **rc=0** ✓ —— `_audit_coupling.py` 本次已改成
   "角色声明（必含符号）自证" ✓，声明过期时会 **rc=1** ✓ ⇒ 这里就能拦住 ✓。

## 自带三条"判据自证" ✓（否则"零违规"可能只是判据写死了 ✗）
用法: python tools/_test_audit_selfcheck.py     （约 3~5 秒；只读 ✓）
"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable
AUDITS = ['tools/_audit_codebase.py', 'tools/_audit_deadcode.py', 'tools/_audit_coupling.py']
FAIL = []


def chk(desc, cond, hint=''):
    print('  %s %s%s' % ('✓' if cond else '✗', desc, ('（%s）' % hint) if hint else ''))
    if not cond:
        FAIL.append(desc)


#: 活动数字（**读数**）：数字 + 单位（行/个/KB/MB）✓
LIVE_NUM = re.compile(r'(\d{2,5})\s*(行|个|KB|MB)')
#: ★ 政策标记（允许写死 ✓）—— 判据看**数字前一小段**里有没有它们 ✓
#: ⚠ 为什么不用 lookbehind ✗：政策词与数字之间隔着空格/"的"（`最长的 15 个` ✓）⇒ 贴不住 ✗
#:   （我第一版就这么写错了 ✗，被自证用例当场抓出来 ✓）
POLICY = '><≤≥~%／/超约前最另限到第'


def has_live_number(line):
    """这一行里有没有"写死的活动数字（读数）"？○ 政策数字例外见文件头 ✓"""
    s = line.strip()
    if s.startswith('#'):
        return False                      # 注释里的历史陈述 ⇒ 不算 ✗
    if ('✗' in line) or ('✓' in line):
        return False                      # 本条目的解释性文案 ✓
    for m in LIVE_NUM.finditer(line):
        before = line[max(0, m.start() - 6):m.start()]      # ★ 数字前一小段 ✓
        if any(c in before for c in POLICY):
            continue                      # 政策数字（阈值/范围/展示上限）✓ 允许写死 ✓
        return True
    return False


print('=' * 96)
print('① 审计工具的打印/字符串里有没有"写死的活动数字"✗（应为 0 处 ✓）')
print('=' * 96)
offenders = []
for f in AUDITS:
    p = os.path.join(ROOT, f)
    for i, l in enumerate(io.open(p, encoding='utf-8', errors='replace').read().splitlines(), 1):
        if has_live_number(l):
            offenders.append('%s:%d' % (f, i))
            print('    ✗ %-34s L%-5d %s' % (f, i, l.strip()[:92]))
if not offenders:
    print('    （无 ✓ —— 行数/规模一律现读现算 ✓）')
chk('★ 三个审计工具里没有写死的活动数字（实 %d 处 ✓）' % len(offenders), not offenders,
    ', '.join(offenders[:6]))

print()
print('=' * 96)
print('② 三个审计工具都要能跑通（rc=0 ✓；`_audit_coupling.py` 角色声明过期时会 rc=1 ✗）')
print('=' * 96)
for f in AUDITS:
    r = subprocess.run([PY, os.path.join(ROOT, f)], capture_output=True, cwd=ROOT)
    out = (r.stdout or b'').decode('utf-8', 'replace')
    n = len(out.splitlines())
    stale = '角色声明' in out and '已过期' in out
    chk('%-32s rc=0（实 rc=%s · %d 行输出%s）'
        % (f, r.returncode, n, ' · ⚠ 角色声明过期 ✗' if stale else ''),
        r.returncode == 0,
        out.strip().splitlines()[-1][:80] if out.strip() else '(无输出 ✗)')

print()
print('=' * 96)
print('③ 判据自证（证明这套判据**有鉴别力** ✓，不是写死的"零违规" ✗）')
print('=' * 96)
chk('★ 喂一行写死数字 ⇒ 必须判为违规 ✓',
    has_live_number("print('【C】loop_engine.py 内部段落（3134 行 —— 判断可拆分性）')"))
chk('★ 喂一行**阈值/范围** ⇒ 必须**不**判违规 ✓（>1500 行 / 150~300 行 是规则，不是读数 ✓）',
    not has_live_number("print('  【2】巨型文件（>1500 行）')") and not has_live_number(
        "print('  → 超 300 行函数 %d 个；150~300 行 %d 个' % (a, b))"))
chk('★ 喂一行**展示上限** ⇒ 必须**不**判违规 ✓（最长的 15 个 / 前 34 个 是界面选择 ✓）',
    not has_live_number("print('  最长的 15 个：')") and not has_live_number(
        "print('  段落标题共 %d 个（前 34 个）' % len(secs))"))
chk('★ 喂一行**格式符** ⇒ 必须**不**判违规 ✓（%d 行 = 现算现填 ✓，正是正确做法 ✓）',
    not has_live_number("print('【C】loop_engine.py 内部段落（%d 行）' % len(ls))"))
chk('★ 喂一行注释 ⇒ 必须**不**判违规 ✓（历史陈述 ✓）',
    not has_live_number('# 2026-09-15 时是 3917 行（历史 ✓）'))

print()
print('✗ 失败：%s' % FAIL if FAIL else
      '✓ 全过：三个审计工具既**不写死活动数字** ✓、又都**跑得通** ✓（评分依据可信 ✓）')
sys.exit(1 if FAIL else 0)
