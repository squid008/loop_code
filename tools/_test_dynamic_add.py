# -*- coding: utf-8 -*-
"""★★★ 回归：**调度器已在跑时，中途「启动本池」必须马上并行跑起来**（`_test_*` ⇒ 进全量回归）。

为什么必须有它（同一个坑咬了两次）：
  · v1.10.1 用户报「停止一个池再启动，怎么没马上开挖？」  ⇒ 加了"动态队列"
  · v1.12.0 用户报「点了一个启动、再点一个池子，怎么是**加入轮转**而不是并行？」 ⇒ 又两个真因：
      ① 候选池来自**启动时的 `--pools` 快照** ⇒ 后加的池**永远不会**跑（连下一轮都不跑）✗
      ② 并行上限在**启动那一刻按 `len(pools)` 算死**（只启 1 个池 ⇒ `--max_parallel=1`）
         ⇒ 后加的池只能**排队**（哪怕内存富余）✗
    ★ 教训：上一版的"动态队列"只在**重启路径**（调度器已退出）测过 ⇒ **测试盲区**。
      本测试专门覆盖"**已有调度器在跑时加池**"这条真实路径 ✓

判据（都不靠"每 60s 一条"的进度日志 —— 那东西时机不可控，上一版就栽在这）：
  A 新池能在**同一个调度器**里起引擎（`[START] pool=<新池>` 出现在同一个日志里）
  B 控制文件里的**实时有效上限**放宽到 2（auto 模式由调度器写回）
  C **真并行**：控制文件 `active` 里**同时**出现过 2 个引擎（= 两个池在同时跑）

全程 `--gen_only --no_global`（**不写 state/journal**），并**快照/还原 `_control.json`（逐字节校验）** ✓
"""
import hashlib
import io
import os
import re
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ROOT = r'D:\loop_code'
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import run_tracks as RT          # noqa: E402

PY = sys.executable
RT_PY = os.path.join(ROOT, 'tools', 'run_tracks.py')
LOG = os.path.join(ROOT, 'ai_test', '_dyn_add_test.log')
CTL = RT.CTL_FILE
FAIL = []


def chk(desc, cond, hint=''):
    print('  %s %s' % ('✓' if cond else '✗', desc))
    if not cond:
        FAIL.append(desc + ('（%s）' % hint if hint else ''))


def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest() if os.path.isfile(p) else None


def rlog():
    try:
        with io.open(LOG, encoding='utf-8', errors='replace') as f:
            return f.read()
    except OSError:
        return ''


def main():
    raw_before = open(CTL, 'rb').read() if os.path.isfile(CTL) else None
    before = sha(CTL)
    if os.path.isfile(LOG):
        os.remove(LOG)
    RT.write_ctl(running=False, enabled=['300'], stopped=[], execMode='parallel',
                 panelCache='use', rounds=1, round=0, curPool=None, curGen=None, phase='idle')
    cmd = [PY, '-u', RT_PY, '--pools=300', '--rounds=1', '--n=400',
           '--exec_mode=parallel', '--max_parallel=1', '--mem_per_engine=2.0',
           '--auto_parallel=1', '--panel_cache=use', '--no_global',
           '--engine_arg=--gen_only']
    print('  命令: %s' % ' '.join(cmd[2:]), flush=True)
    o = open(LOG, 'wb')
    pr = subprocess.Popen(cmd, cwd=ROOT, stdout=o, stderr=subprocess.STDOUT,
                          creationflags=RT.NO_WIN)
    try:
        t0 = time.time()
        while time.time() - t0 < 120 and '[START] pool=300' not in rlog():
            time.sleep(2)
        chk('A0 首个池（300）已启动', '[START] pool=300' in rlog())
        # ★ 模拟「启动本池：500」= 只改控制文件，**不重启调度器**（这与看板完全同一条路）
        for _ in range(8):
            RT.write_ctl(enabled=['300', '500'])
            time.sleep(1.5)
            if {'300', '500'} <= set(RT.read_ctl().get('enabled') or []):
                break
        chk('A1 控制文件已写入 enabled=[300,500]',
            {'300', '500'} <= set(RT.read_ctl().get('enabled') or []))
        t1 = time.time()
        while time.time() - t1 < 120 and '[START] pool=500' not in rlog():
            time.sleep(2)
        chk('A2 ★★ 新池 500 在**同一个调度器**里跑起来了（用户报的那个 bug）',
            '[START] pool=500' in rlog(), rlog()[-300:])
        # B 实时上限（auto ⇒ 调度器写回控制文件）
        cap, act2, n2 = None, False, 0
        t2 = time.time()
        while time.time() - t2 < 40:
            c = RT.read_ctl()
            cap = c.get('maxParallel')
            n = len(c.get('active') or [])
            n2 = max(n2, n)
            if n >= 2:
                act2 = True
            if cap == 2 and act2:
                break
            time.sleep(2)
        chk('B ★ 有效上限**动态放宽到 2**（不是启动时算死的 1）', cap == 2, '实测 %s' % cap)
        chk('C ★★ **真并行**：`active` 里同时出现过 2 个引擎（两个池在同时跑）',
            act2, '同时最多 %d 个' % n2)
    finally:
        try:
            subprocess.run(['taskkill', '/PID', str(pr.pid), '/T', '/F'],
                           capture_output=True, creationflags=RT.NO_WIN)
        except Exception:
            pass
        time.sleep(2)
        o.close()
        if raw_before is not None:
            with open(CTL, 'wb') as f:
                f.write(raw_before)
        after = sha(CTL)
        print('  [ctl] 还原 _control.json: %s' % ('✓ 逐字节一致' if after == before
                                            else '✗ 不一致'))
        if after != before:
            FAIL.append('_control.json 还原后不一致')
    print()
    if FAIL:
        print('★★ 运行期加池测试失败 %d 项：' % len(FAIL))
        for x in FAIL:
            print('   ✗ %s' % x)
        return 1
    print('★★ 运行期加池（=「启动本池」）**马上并行跑起来** ✓')
    return 0


if __name__ == '__main__':
    sys.exit(main())
