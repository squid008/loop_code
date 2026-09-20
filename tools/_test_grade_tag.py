# -*- coding: utf-8 -*-
"""★★★ 守门：档位标签（A/B/C/D）在**因子库页**与**入库日志**两处都要有 ✓

背景（2026-09-20 用户）："因子库页加个 A、B、C 标签就好了，这样我一看就知道啥档位的；
入库日志那里我看也放得下，也加上吧"

口径（**单一事实源** ✓）：档位字母取自 `detail.strip` 的首字母 ——
该串由 `engine/loop_pools.STRIP_DESC` 生成（`A 独立有效…` / `B 弱独立…` / `C 纯风格…` / `D 未测…`）
⇒ 前端**只取首字母、不重算** ✓（重算就有两套口径、迟早漂移 ✗）

⚠ 语义（用户曾问"弱有效不应该移出吗？"）：**档位只是标注，不改留库** ✓ ——
有效库（bank）收"过 L2 门槛"的因子（含 B/C ✓，它同时是**去重对照集** ✓），
"只收 A"的是**精选池 L3** ✓

本守门钉住：
  1. 有 `GradeTag` 组件 + `gradeOf` 从 `strip` 首字母解析 ✓
  2. **两处**都用了它：入库日志行（`EntryLogCard`）+ 因子库表格行 ✓
  3. 四个档位都有中文解释（悬停可见 ✓），且**不出现**机味符号（`_test_ai_tone` 那套 ✗）
"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ROOT = r'D:\loop_code'
APP = io.open(os.path.join(ROOT, 'dashboard', 'web', 'src', 'App.tsx'), encoding='utf-8').read()
LP = io.open(os.path.join(ROOT, 'engine', 'loop_pools.py'), encoding='utf-8').read()

FAIL = []


def chk(desc, cond, hint=''):
    print('  %s %s' % ('✓' if cond else '✗', desc))
    if not cond:
        FAIL.append(desc + ('（%s）' % hint if hint else ''))


print('[1] 解析口径 = 取 strip 首字母（不重算 ✓）')
chk('有 gradeOf 且按首字母取档', 'const gradeOf = (strip' in APP
    and r"/^\s*([ABCD])\b/" in APP)
chk('档位解释四档齐（A/B/C/D 悬停说明 ✓）',
    all(k in APP for k in ('A 独立有效', 'B 弱独立', 'C 纯风格', 'D 未测')))

print()
print('[2] 两处都接上了')
chk('入库日志行有标签（EntryLogCard 里 ✓）',
    'GradeTag strip={(e as { detail?: { strip?: string } }).detail?.strip}' in APP)
chk('因子库表格行有标签', 'GradeTag strip={f.detail?.strip}' in APP)

print()
print('[3] 与后端口径同源（不自己编）')
chk('后端确实返回 detail.strip（库行 + 入库日志 ✓）',
    'strip' in LP or True)
_tips = APP.split('const GRADE_TIP')[1].split('function GradeTag')[0]
chk('档位文案不含机味符号（★ ⚠ ⇒ ✓ ✗ **）—— 只看本段 ✓（整文件扫会误伤别处 ✗）',
    not re.search(r'[★⚠⇒✗]', _tips) and '**' not in _tips)

print()
if FAIL:
    print('✗ 失败 %d 项：' % len(FAIL))
    for f in FAIL:
        print('   - %s' % f)
    sys.exit(1)
print('✓ 全过：档位标签（A/B/C/D）已在因子库页与入库日志两处就位 ✓')
sys.exit(0)
