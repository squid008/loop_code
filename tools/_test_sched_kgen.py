# -*- coding: utf-8 -*-
"""★★★ 守门：调度器「第 1 步 K 代/轮」+「第 2 步 池内即时收尾」在位且**界线正确** ✓

背景（2026-09-19 用户之问）：
  「为什么要等三个池一起挖完才审查？不能一个池挖完就马上审查、然后接着挖？效率不是更高？」
  ⇒ 实测：收尾只 13 秒 ✗ 不是瓶颈；真浪费是**轮屏障**（50 池一代 3-8 分钟，却每轮白等约 30 分钟 ✗）
  ⇒ 两步落地：
    ① `--gens_per_round=K` 每池每轮连跑 K 代（快池少空转 ✓）
    ② `--pool_tail=on` 某池有入库就**立刻**补它的 facs/指标/曲线（挖到就能马上看 ✓）

本守门钉住的关键界线（**这一条最容易写坏** ✗）：
  · 池内收尾只做「**按因子落文件**」的段（facs / 指标 / 曲线）⇒ 多池并发互不相干 ✓
  · 池内收尾**绝不许**包含**全局语义**的两件：`cross_pool_review`（跨池去重）+ 登记表导出
    ⇒ 那两件仍由轮末的 `do_global_tail` 统一做 ✓（否则并发写同一份产出 ⇒ 互相覆盖 ✗✗）
"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ROOT = r'D:\loop_code'
RT = io.open(os.path.join(ROOT, 'tools', 'run_tracks.py'), encoding='utf-8').read()
PR = io.open(os.path.join(ROOT, 'tools', 'parallel_runner.py'), encoding='utf-8').read()
MN = io.open(os.path.join(ROOT, 'dashboard', 'api', 'app', 'mine.py'), encoding='utf-8').read()

FAIL = []


def chk(desc, cond, hint=''):
    print('  %s %s' % ('✓' if cond else '✗', desc))
    if not cond:
        FAIL.append(desc + ('（%s）' % hint if hint else ''))


print('[1] 第 1 步：每池每轮连跑（--gens_per_round；0 = 不限 ✓）')
chk('run_tracks 解析 --gens_per_round=（允许 0 ✓）',
    re.search(r"startswith\('--gens_per_round='\)", RT) is not None
    and 'max(0, min(50,' in RT)
chk('run_tracks 默认 = 0（不限 ✓，用户拍板"500 跑一代、50 该跑七八代"）',
    re.search(r'^\s*gens_per_round\s*=\s*0\s*$', RT, re.M) is not None)
chk('参数透传给 parallel_runner.run', 'gens_per_round=gens_per_round' in RT)
chk('parallel_runner.run 签名带 gens_per_round', 'gens_per_round=1' in PR)
chk('★ 核心：把该池**放回候选**（launched.discard ✓）',
    'gens[_gp] = gens.get(_gp, 0) + 1' in PR and 'launched.discard(_gp)' in PR)
chk('★ 不限模式：别的池还没完成 1 代就继续领（_again = any(... < 1) ✓）',
    'gens.get(x, 0) < 1 for x in _need_r' in PR)

print()
print('[2] 第 2 步：池内即时收尾（--pool_tail，且有互斥锁 ✓）')
chk('run_tracks 解析 --pool_tail=', re.search(r"startswith\('--pool_tail='\)", RT) is not None)
chk('有 do_pool_tail 函数', 'def do_pool_tail(' in RT)
chk('有跨进程收尾互斥锁（tail_lock ✓）', 'class tail_lock' in RT and 'TAIL_LOCK' in RT)
chk('全局收尾也走这把锁（wrapper 调 _global_tail_impl ✓）',
    'with tail_lock():' in RT and 'def _global_tail_impl(' in RT)
chk('池内收尾按池执行（--pools=%s ✓）', "'--pools=%s' % pool" in RT)
chk('有内存护栏（可用内存不足就跳过 ✓）', 'TAIL_MIN_FREE_GB' in RT and '引擎优先' in RT)

print()
print('[2b] ★★ 界线：池内收尾**只做 pool-local**，不许碰全局两件 ✗')
_seg = RT[RT.index('def do_pool_tail('):RT.index('def do_global_tail(')]
chk('池内收尾**不含** cross_pool_review（跨池去重是全局语义 ✗）',
    'cross_pool_review' not in _seg)
chk('池内收尾**不含** export_factor_registry（登记表是全局语义 ✗）',
    'export_factor_registry' not in _seg)
chk('池内收尾**含** facs 落地 / 指标表 / 曲线三段 ✓',
    'build_facs.py' in _seg and 'factor_metrics.py' in _seg and 'factor_curves.py' in _seg)
chk('全局收尾仍做那两件（没被误删 ✓）',
    'cross_pool_review.py' in RT and 'export_factor_registry.py' in RT)

print()
print('[3] 看板启动默认带上这两步（用户点按钮即生效 ✓）')
chk("mine.py 传 --gens_per_round=0（不限）", "'--gens_per_round=0'" in MN)
chk("mine.py 传 --pool_tail=on", "'--pool_tail=on'" in MN)

print()
print('[4] 并行 runner 在「有入库」时才触发池内收尾（平时零开销 ✓）')
chk('只用 t.banked 判断（真入库才跑 ✓）', "if pool_tail and t.get('banked')" in PR)
chk('_reap 解析出入库个数（banked ✓）', "t['banked'] = int(_bm[-1])" in PR)

print()
if FAIL:
    print('✗ 失败 %d 项：' % len(FAIL))
    for f in FAIL:
        print('   - %s' % f)
    sys.exit(1)
print('✓ 全过：K 代/轮 与 池内即时收尾 都已就位，且全局/池内界线正确')
sys.exit(0)
