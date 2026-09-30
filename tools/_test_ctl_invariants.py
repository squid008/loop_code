# -*- coding: utf-8 -*-
"""★ 守门：控制文件的「启用/停用」语义 + 那两处 2026-09-30 的修复，**不许被改回去** ✗。

## 事故（用户 2026-09-30：「我刚才起了两次才把全A池开起来…第一次停在待启动」）
日志实录（`ai_test/_tracks/_driver.log`）：
```
21:06:51 ## 第 1 / 50 轮  启用池=['all']  本轮停=['1000','300','500','all']   ← 自相矛盾 ✗
21:06:51 [CTL] 本轮剩余 1 个池未启动（all）⇒ 留到下一轮      ← 每轮都这句
 …（第 2~50 轮全在同一秒内走完 ✗）⇒ ★ 轮数上限 50 已跑满 ⇒ 退出
```
**根因两处**（都已在 v1.35.0 修 ✓）：
1. `mine.start_pool()` 冷启动**先起调度器** ✓、**之后**才补写"把该池从 `stopped` 摘掉" ✗
   ⇒ 新调度器**第一轮**读到 `enabled=[pool]` ∧ `stopped` 含 pool（自相矛盾 ✗）。
2. 而"没候选池"的旧路径是 `break` 出本轮 ✗，`rnd` 照样 +1 ⇒ 轮次被**瞬间烧光** ✗✗
   ⇒ 会话在**同一秒**内报废；用户界面却因那次补写**已落地**而显示"待启动" ✗
   ⇒ **界面说在等、调度器其实已经死了** ✗（这就是"起两次才好"的全部真相 ✓）。

## 本守门查四件
1. **纯函数口径** ✓：`run_tracks.runnable_pools` / `all_pools_paused`（调度器与看板共用 ✓）——
   特别是**事故当场的那个输入**必须被判为"全被停用" ⇒ 调度器**去等**、而不是烧轮次 ✓；
2. **静态断言**：`parallel_runner` 的"全被停用 ⇒ 等待"分支必须在 `rnd += 1` **之前** ✓
   （顺序被改回去就复发 ✗✗）；
3. **静态断言**：`mine.start_pool()` 的冷启动把修正后的 `stopped` **并进 `start()` 同一次写入** ✓，
   且**不再**有"起进程之后再补写 `stopped`"的旧形态 ✗；
4. **接线**：后端 `state()` 报 `pausedAll` ✓ + 前端类型声明它 ✓（否则界面的如实提示会静默消失 ✗）。

用法: python tools/_test_ctl_invariants.py    （<2 秒；只读源码 + 纯函数，不动控制文件 ✓）
"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
sys.path.insert(0, os.path.join(ROOT, 'engine'))
FAIL = []


def chk(desc, cond, hint=''):
    print('  %s %s%s' % ('✓' if cond else '✗', desc, ('（%s）' % hint) if hint else ''))
    if not cond:
        FAIL.append(desc)


def src(rel):
    return io.open(os.path.join(ROOT, rel), encoding='utf-8').read()


print('=' * 96)
print('① 纯函数口径：`runnable_pools` / `all_pools_paused`（调度器与看板必须同一口径 ✓）')
print('=' * 96)
import run_tracks as RT                                                        # noqa: E402

chk('事故当场的输入（enabled=[all]，stopped=[1000,300,500,all]）⇒ **全被停用 = True** ✓',
    RT.all_pools_paused(['all'], ['1000', '300', '500', 'all']) is True)
chk('还有别的池能跑（enabled=[all,300]，stopped=[all]）⇒ False ✓（该照常轮转 ✓）',
    RT.all_pools_paused(['all', '300'], ['all']) is False)
chk('`stopped` 为空 ⇒ False ✓（正常情况不许误判成"等一等" ✗）',
    RT.all_pools_paused(['all'], []) is False)
chk('`enabled` 为空 ⇒ False ✓（那是"启用池为空 ⇒ 结束轮转"的另一支 ✓，不该在这里等 ✗）',
    RT.all_pools_paused([], ['all']) is False)
chk('`stopped` 含**无关池** ⇒ False ✓（只有"全被停用"才算 ✓）',
    RT.all_pools_paused(['all'], ['300', '500']) is False)
chk('`runnable_pools` = enabled - stopped ✓',
    RT.runnable_pools(['all', '300', '500'], ['300']) == ['500', 'all'])

print()
print('=' * 96)
print('② 静态：调度器"全被停用 ⇒ 等待"的分支必须在 `rnd += 1` **之前** ✓（顺序即修复本身 ✓）')
print('=' * 96)
pr = src('tools/parallel_runner.py')
_i_pause = pr.find('all_pools_paused')
_i_pause_write = pr.find('RT.write_ctl(pausedAll=')
_i_rnd = pr.find('rnd += 1')
chk('[并行] `all_pools_paused` 出现在调度器里 ✓（实 %s）' % ('有' if _i_pause > 0 else '**没有** ✗'),
    _i_pause > 0)
chk('[并行] ★ 它出现在 `rnd += 1` **之前** ✓（顺序反了就会把轮次烧光 ✗✗）',
    _i_pause > 0 and _i_rnd > 0 and _i_pause < _i_rnd,
    'pause@%d vs rnd@%d' % (_i_pause, _i_rnd))
chk('[并行] 等待处**写了 `pausedAll`** ✓（否则看板只能瞎猜 ✗）', _i_pause_write > 0)
chk('[并行] 等待间隔是个常数（`_PAUSE_WAIT_S` ✓，可调、可读 ✓）', '_PAUSE_WAIT_S' in pr)
chk('[并行] ★ 恢复时**清掉** `pausedAll` ✓（否则界面会一直说"在等" ✗）',
    pr.count('RT.write_ctl(pausedAll=') >= 2)
# ★★ 轮转路径必须**同款** ✓ —— 2026-09-30 实测第一版就栽在这里：
#   我只改了并行 ✗，而实测脚本用 `--from_ctl=1` 走的是**轮转** ⇒ 3 轮在同一秒烧光 ✗✗
#   （"两条路行为不一致"正是本项目最忌 ✗）⇒ 从此**两条路都要断言** ✓。
_rt = src('tools/run_tracks.py')
_i_rot = _rt.find('def _rotate_schedule(')
_rot = _rt[_i_rot:_i_rot + 8000] if _i_rot > 0 else ''
_i_pause_rt = _rot.find('all_pools_paused')
_i_rnd_rt = _rot.find('rnd += 1')
chk('[轮转] ★ 同款判据：`all_pools_paused` 也在 `rnd += 1` **之前** ✓',
    _i_rot > 0 and _i_pause_rt > 0 and _i_rnd_rt > 0 and _i_pause_rt < _i_rnd_rt,
    'pause@%d vs rnd@%d' % (_i_pause_rt, _i_rnd_rt))
chk('[轮转] 同款：写 `pausedAll` ✓ + 恢复时清掉 ✓',
    _rot.count('write_ctl(pausedAll=') >= 2)
chk('[轮转] 同款：等待间隔用同一个常数名 ✓（便于统一调 ✓）', '_PAUSE_WAIT_S' in _rot)

print()
print('=' * 96)
print('③ 静态：`mine.start_pool()` 冷启动必须**同一次写入**带上修正后的 `stopped` ✓')
print('=' * 96)
mi = src('dashboard/api/app/mine.py')
_m = mi.find('def start_pool(')
_seg = mi[_m:_m + 3000]
chk('★ 冷启动的 `start(...)` 调用**带 `stopped=`** ✓（不带 ⇒ 第一轮就矛盾 ✗）',
    bool(re.search(r'start\(en, rounds, reset_stopped=False, stopped=st\)', _seg)))
chk('★ **不再**有"起进程之后再补写 `stopped`"的旧形态 ✗（那就是事故现场 ✓）',
    not re.search(r'r = start\([^\n]*\)\s*\n\s*_write_ctl\(stopped=st', _seg))
chk('`start()` 形参里有 `stopped=None` ✓', re.search(
    r'def start\([^)]*stopped=None\)', mi, re.S) is not None)
chk('显式 `stopped` **优先于** `reset_stopped` ✓（两处分支都要有 ✓）',
    mi.count("kw['stopped'] = list(stopped)") == 2)
chk('⚠ 但**没有**把"单独停"改成"也剔除 enabled" ✗（那会推翻 2026-09-16 的 BUG A 修复 ✓）',
    'def stop(' in mi and '不动 `enabled`' in mi)

print()
print('=' * 96)
print('④ 接线：后端报 `pausedAll` ✓ + 前端类型声明 ✓（否则如实提示会静默消失 ✗）')
print('=' * 96)
chk('`mine.state()` 返回 `pausedAll` ✓', "'pausedAll':" in mi)
chk('前端 `api.ts` 声明 `pausedAll` ✓', 'pausedAll?: string[]' in src('dashboard/web/src/api.ts'))
tsx = src('dashboard/web/src/App.tsx')
chk('前端**读了** `pausedAll` ✓', 'pausedAll' in tsx)
chk('★ 前端不再把"调度器没在跑"说成「待启动」✗（旧文案会让人白等 ✓）',
    "'待启动'" not in tsx and '已配置 · 未启动' in tsx)

print()
print('✗ 失败：%s' % FAIL if FAIL else
      '✓ 全过：口径单一 ✓ · 等待分支在烧轮次之前 ✓ · 冷启动同一次写入 ✓ · 接线在位 ✓')
sys.exit(1 if FAIL else 0)
