# -*- coding: utf-8 -*-
"""★★★ 守门：池徽标「**挖掘中 / 审查中 / 并行中**」三分 + 逐池进度显示 ✓

背景（2026-09-19 用户之问）：
  「300/500 一直都是并行中，是在审查呢还是在等 50 池挖完？」
  「池徽标语义是不是加一个审查中？这样跟并行中就能区分开，我就知道它挖完了正在审查，
    然后审查完了就是并行中，然后就是挖掘中」
  「轮次显示逻辑按照我想要的改（不是 1/50 那样，而是每隔几秒滚动显示各池自己的轮次）」

## 三态语义（不许再混 ✗）
  · **挖掘中** = 有它的引擎在跑（后端 `byPool[p].mining` ✓）
  · **审查中** = 它刚挖完、正在做收尾（后端 `byPool[p].reviewing` ✓
    = `tailPool == p`（池内收尾指名它）**或** `phase == 'tail'`（轮末全局收尾）✓）
  · **并行中** = 已参与并行，但此刻既没在挖也没在审（典型：本轮它已跑完，在等其它池 ✓）

## 本守门钉住
  1. 后端 `mine.state()` 必须给出 `reviewing`（逐池）+ `tailPool`（全局）+ `gensRound`（逐池）✓
  2. `do_pool_tail` 必须**写/清** `tailPool`（否则"审查中"根本亮不起来 ✗）
  3. `parallel_runner` 必须写 `gensRound`（否则"各池自己的进度"永远是 0 ✗）
  4. 前端徽标分支必须含 `reviewing ? '审查中'`，且**挖掘中/并行中仍在** ✓
  5. 前端要有逐池明细（相位卡悬停 `poolLines`）+ 卡片上的"本轮已跑"字段 ✓
"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ROOT = r'D:\loop_code'
MINE = io.open(os.path.join(ROOT, 'dashboard', 'api', 'app', 'mine.py'), encoding='utf-8').read()
RT = io.open(os.path.join(ROOT, 'tools', 'run_tracks.py'), encoding='utf-8').read()
PR = io.open(os.path.join(ROOT, 'tools', 'parallel_runner.py'), encoding='utf-8').read()
APP = io.open(os.path.join(ROOT, 'dashboard', 'web', 'src', 'App.tsx'), encoding='utf-8').read()
API = io.open(os.path.join(ROOT, 'dashboard', 'web', 'src', 'api.ts'), encoding='utf-8').read()

FAIL = []


def chk(desc, cond, hint=''):
    print('  %s %s' % ('✓' if cond else '✗', desc))
    if not cond:
        FAIL.append(desc + ('（%s）' % hint if hint else ''))


print('[1] 后端：三态信号齐全')
chk("mine.py 逐池给 reviewing（含 tailPool 与 phase==tail 两路 ✓）",
    "'reviewing': bool(_tail_all or (_tap == k))" in MINE)
chk("mine.py 逐池给 gensRound", "'gensRound': int(_gens.get(k) or 0)" in MINE)
chk("mine.py 顶层给 tailPool", "'tailPool': _tap" in MINE)
chk("mine.py 顶层给 gensRound", "'gensRound': {k: int(v or 0)" in MINE)
chk("mine.py 读了控制文件的 tailPool / phase", "_tap = c.get('tailPool')" in MINE
    and "_tail_all = (c.get('phase') == 'tail')" in MINE)

print()
print('[2] 收尾与调度：写入/清空这两个信号')
chk("do_pool_tail 开始写 tailPool=pool", 'write_ctl(tailPool=pool)' in RT)
chk("do_pool_tail 结束清 tailPool=None", 'write_ctl(tailPool=None)' in RT)
chk("parallel_runner 启动/收割都写 gensRound", PR.count('gensRound=dict(gens)') >= 2)
chk('parallel_runner 启动引擎时把 tailPool 清掉（避免残留的审查中 ✗）',
    'tailPool=None' in PR)

print()
print('[3] 前端：徽标三分 + 逐池进度')
chk("徽标含审查中分支", "reviewing ? '审查中'" in APP)
chk("徽标仍含挖掘中", "'挖掘中'" in APP)
chk("徽标仍含并行中（qword + '中'）", "(qword + '中')" in APP)
chk("挖掘中带上该池自己的 gen（滚动感 ✓）", '挖掘中 · gen' in APP)
chk("审查中给的是浅黄点（与挖掘中的绿点区分 ✓）", "reviewing ? 'var(--amber)'" in APP)
chk("有逐池明细 poolLines（悬停可见 ✓）", 'const poolLines = useMemo' in APP
    and 'poolLines.join' in APP)
chk("相位卡那格改逐池滚动 rollText", 'const rollText = useMemo' in APP
    and 'rollText' in APP and '<small title=' in APP)
chk("卡片有「本轮已跑」字段", '本轮已跑' in APP)
chk("api.ts DTO 补了 reviewing / gensRound / tailPool",
    'reviewing?: boolean' in API and 'gensRound?: number' in API and 'tailPool?: string | null' in API)

print()
if FAIL:
    print('✗ 失败 %d 项：' % len(FAIL))
    for f in FAIL:
        print('   - %s' % f)
    sys.exit(1)
print('✓ 全过：挖掘中 / 审查中 / 并行中 三分到位，逐池进度显示到位')
sys.exit(0)
