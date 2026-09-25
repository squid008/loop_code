# -*- coding: utf-8 -*-
"""★★★ 守门：`do_pool_tail` 的内存护栏**不许因未定义名而崩** ✓

背景（2026-09-20 用户："`500/F07` 详情页还是没曲线"）：
  查到 `09-20 01:44:22 [!] 池内收尾失败(NameError) -> 继续挖掘` ✗
  真因：`run_tracks.do_pool_tail` 里 `free = avail_gb()` —— 而 **`avail_gb` 在
  `run_tracks.py` 里从未定义/导入** ✗（它住在 `parallel_runner` ✓，本文件到 L702 才 import ✗）
  ⇒ **池内收尾从上线起没成功跑过一次** ✗（每次第一行就崩 ✓，异常被吞成一行温和日志 ✗）

本守门钉住：
  1. `do_pool_tail` 里**不许再出现裸 `avail_gb()`** —— 必须走延迟 import ✓
  2. ★ **功能校验**：`force=False` + **故意给一个不可能满足的 `min_free_gb`**
     ⇒ 必须**优雅返回 False**（打印"跳过"✓）、**绝不抛异常** ✓
     （这条同时验证了"内存护栏这条路真的能走通" ✓ —— 而它正是这次崩掉的那条 ✓）
  3. 调用方（`parallel_runner`）**必须把异常信息也打出来** ✓（只记类型 ⇒ 看不见病根 ✗）
"""
import io
import os
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # ★ 2026-09-25 换机器：原写死 `D:\loop_code` ⇒ 改自身路径派生 ✓
RT = io.open(os.path.join(ROOT, 'tools', 'run_tracks.py'), encoding='utf-8').read()
PR = io.open(os.path.join(ROOT, 'tools', 'parallel_runner.py'), encoding='utf-8').read()

FAIL = []


def chk(desc, cond, hint=''):
    print('  %s %s' % ('✓' if cond else '✗', desc))
    if not cond:
        FAIL.append(desc + ('（%s）' % hint if hint else ''))


print('[1] 静态：内存护栏走延迟 import ✓')
chk('do_pool_tail 里有 `import parallel_runner as _PR`', 'import parallel_runner as _PR' in RT)
chk('调的是 `_PR.avail_gb()`', '_PR.avail_gb()' in RT)
chk('★ 不再有裸 `free = avail_gb()`', 'free = avail_gb()' not in RT)

print()
print('[2] 静态：调用方必须打印异常**信息**（不只类型）')
chk('parallel_runner 打了 str(_e) 与 traceback',
    'type(_e).__name__, str(_e)[:160]' in PR and 'format_exc()' in PR)

print()
print('[3] ★ 功能校验：护栏路径必须**优雅返回 False**（不许抛异常）')
sys.path.insert(0, os.path.join(ROOT, 'tools'))
sys.path.insert(0, os.path.join(ROOT, 'engine'))
try:
    import run_tracks as R
    # 给一个**绝不可能满足**的内存下限 ⇒ 必然走"跳过"分支（不会跑任何工具 ✓ 零副作用 ✓）
    ret = R.do_pool_tail('__nonexistent_pool__', tag='守门自检', min_free_gb=10 ** 9)
    chk('返回 False（优雅跳过 ✓，且没有抛异常）', ret is False, '返回=%r' % (ret,))
except Exception as e:
    chk('护栏路径不抛异常', False, '%s: %s' % (type(e).__name__, e))

print()
if FAIL:
    print('✗ 失败 %d 项：' % len(FAIL))
    for f in FAIL:
        print('   - %s' % f)
    sys.exit(1)
print('✓ 全过：池内收尾的内存护栏能真正走通（不会再 NameError 静默废掉整条收尾 ✗）')
sys.exit(0)
