# -*- coding: utf-8 -*-
"""★★ 检查前端**用户可见文本**里是否还有"AI 味"符号（`★` `⇒` `✓` `✗` `**`）。

★ 为什么：用户说「你的所有鼠标提示里面的引号都改改，**看着就是 AI 输出的**」⇒
  `title`（鼠标提示）/ `window.confirm`（确认框）/ `showToast`（提示条）**都是纯文本**，
  满屏 `★ ⇒ ✓` 和 `**加粗**` ⇒ 一眼就是机器写的 ✗
  ⇒ 目标：这些位置只用**自然语言 + 普通标点**（`「」`「，」「。」「；」「：」）✓

**代码注释**（`//` `/*` `{/*`）**不算** —— 用户看不到，保留项目原有风格 ✓
"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
P = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'dashboard', 'web', 'src', 'App.tsx')
# ★★ 2026-09-17：**先剥注释再看**（用状态机，不用正则）——
#   本检查原来是**逐行**判注释的，于是"多行块注释的第二行"会被当成可见文本 ⇒ **误报** ✗
#   （实测踩到：我写的一条 `{/* ... 会被读成"还在库里" ✗ ... */}` 注释就被判成残留）
#   `strip_js` 保留换行 ⇒ 行号仍然对得上，报告不漂 ✓
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _test_ui_quotes import strip_js          # noqa: E402
_raw = io.open(P, encoding='utf-8').read()
RAW_LS = _raw.splitlines()                    # 原样（用于[3]统计注释里的符号）
ls = strip_js(_raw).splitlines()              # 剥注释后（用于[2]判"用户可见"）

SYMS = ['★', '⇒', '✓', '✗', '❗', '**']
COMMENT = re.compile(r'^\s*(//|/\*|\*|\{/\*)')


def in_user_visible(idx):
    """粗判：该行是否属于用户可见文本块。

    策略：从该行向上找最近的"起点"（`window.confirm(` / `title=` / `say(` / `showToast(` /
    `const label =` / `` ` `` 模板串开始），若中途没遇到 `*/` 或 `})` 之类"块结束"就认为是。
    简单起见：向上 12 行内若出现 `confirm(` / `title=` / `say(` / `label =` ⇒ 视为可见区。
    """
    lo = max(0, idx - 12)
    for k in range(idx, lo - 1, -1):
        l = ls[k]
        if COMMENT.match(l):
            # 注释行不"传染"；但若是 JSX 注释块，向下全部不算
            continue
        if any(t in l for t in ('confirm(', 'title=', 'say(', 'showToast(', 'label =', 'setToast(')):
            return True
        # 遇到明显的"块结束"就停
        if re.search(r'(\)\s*return|\}\s*$)', l) and '`' not in l and "'" not in l and '"' not in l:
            break
    return False


print('=' * 100)
print('[1] 所有 `title=` 位置（鼠标提示）')
print('=' * 100)
for k, l in enumerate(ls, 1):
    if re.search(r'\btitle\s*=', l):
        print('  L%-4d %s' % (k, l.strip()[:110]))

print()
print('=' * 100)
print('[2] ★ 用户可见区里残留的 AI 味符号')
print('=' * 100)
bad = []
for k, l in enumerate(ls, 1):
    if COMMENT.match(l):
        continue
    if not in_user_visible(k - 1):
        continue
    hit = [s for s in SYMS if s in l]
    if hit:
        bad.append((k, hit, l.strip()))
for k, hit, l in bad:
    print('  L%-4d %-14s %s' % (k, ','.join(hit), l[:104]))
print('  ⇒ ★ 残留 **%d** 行 %s' % (len(bad), '✓ 干净' if not bad else '✗ 还需清理'))

print()
print('=' * 100)
print('[3] 注释区的符号（**不算问题**，仅统计）')
print('=' * 100)
# ⚠ 统计要基于**原样文本**（`ls` 已剥掉注释 ⇒ 这里会恒为 0，报告就成了假话 ✗）
cnt = sum(1 for l in RAW_LS if COMMENT.match(l) and any(s in l for s in SYMS))
print('  注释行含符号: %d 行（用户看不到，保留项目风格）✓' % cnt)
print()
# ★ 2026-09-16：**改成守门**（原来只报告、不失败 ⇒ 没人会天天手跑它 ⇒ 残留会回来 ✗）
#   退出码 = 有残留就 1 ⇒ 直接进全量回归（文件名也改成 `_test_ai_tone.py`）✓
sys.exit(1 if bad else 0)
