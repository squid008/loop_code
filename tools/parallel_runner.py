# -*- coding: utf-8 -*-
"""parallel_runner.py -- 多池轨道的**有界并行**调度器（2026-09-16 新增）。

★ 与 `run_tracks.py`（串行轮转）的关系（**开关切换，旧行为零改动**）：
  · `run_tracks.py --exec_mode=parallel` 会**委托**给本模块；默认仍是 `rotate`（= 现状）✓
  · 本模块**复用** `run_tracks` 的公共件（`log` / `next_gen` / `read_ctl` / `write_ctl` /
    `inject_for` / `do_global_tail` / `read_log` / `NO_WIN` / `LOGD` / `PY`）—— **绝不复制实现**，
    否则两条调度路径必然漂移 ✗
  · 之所以单独成一个模块（而不是塞进 run_tracks）：调度语义不同（轮转 vs 有界并行），
    各自保持可读；`run_tracks.py` 只多一个"分叉 + 透传"的分支 ✓

★ 为什么值得并行（**实测**，`ai_test/_measure_engine_cpu.py`）：
  · 单引擎 **等效核 ≈ 0.99**（只吃 1 个核），本机 6 核/12 线程 ⇒ **CPU 有大把空间**；
  · 真正的约束是**内存**：面板 `B` = **4.42 GB/进程**；
    而 `--panel_cache=use` 把它落成**只读 memmap** ⇒ 多进程共享同一批物理页，
    每进程的**私有**内存只剩 L1 子面板 + 缓存 ⇒ 才放得下 N 个 ✓

★ 语义（与轮转**一致**，只把"同时 1 个"放宽成"同时 N 个"）：
    for r in 1..rounds:
        for pool in 启用池:        # 每池 1 代；★ **队列化**：跑完一个立刻补一个（快池不等慢池）
            跑该池 1 代             # 超出 N 个的进入**排队**
        ★ 一轮全部结束 ⇒ 自动收尾（`--no_global` 可关）
    ★ `stopAll`   ⇒ **不再补新任务**，等在跑的自然结束 ⇒ 收尾退出
    ★ `stopped`   ⇒ 该池**本轮不启动**（不影响其他池）
    ★★ 2026-09-16 新增（用户要求）：「单独停止某个池」⇒ **本轮不再补位** —— 空槽**留给用户自己决定**
       （想加回来点「启动本池」），不会"停一个就自动顶上来一个"✓；只影响**本轮**，
       下一轮按 `enabled - stopped` **重新组队**（被停的池不会自己回来）✓

★ 内存护栏（这套东西存在的意义就是"**别把机器挤爆**"）：
  · `--max_parallel=N`（硬上限，默认 3）
  · `--mem_per_engine=G`（每引擎预算，默认 3.0 GB）
  · 每次启动前查**可用物理内存**，不足 ⇒ **等待并打印原因**（每 15s 重试），而不是硬起
    （本项目出过 OOM/数据事故 ⇒ **宁可慢，不炸**）✓
  · ⚠ 只读 memmap 的页属于**可回收的 file cache**：任务管理器里会看到"已缓存"增长，
    但**别的程序要内存时会被自动回收** ⇒ 不会把机器锁死 ✓
"""
import io
import os
import subprocess
import sys
import time
from datetime import datetime

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import run_tracks as RT          # noqa: E402  ★ 复用公共件（不复制）


def avail_gb():
    """当前**可用物理内存**（GB）；查不到返回 inf（不因"测不出"而卡死）。"""
    try:
        import ctypes

        class MS(ctypes.Structure):
            _fields_ = [('dwLength', ctypes.c_ulong), ('dwMemoryLoad', ctypes.c_ulong),
                        ('ullTotalPhys', ctypes.c_ulonglong),
                        ('ullAvailPhys', ctypes.c_ulonglong),
                        ('ullTotalPageFile', ctypes.c_ulonglong),
                        ('ullAvailPageFile', ctypes.c_ulonglong),
                        ('ullTotalVirtual', ctypes.c_ulonglong),
                        ('ullAvailVirtual', ctypes.c_ulonglong),
                        ('ullAvailExtendedVirtual', ctypes.c_ulonglong)]
        m = MS()
        m.dwLength = ctypes.sizeof(MS)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
        return m.ullAvailPhys / (1024.0 ** 3)
    except Exception:
        return float('inf')


def _cmd_and_paths(pool, gen, n, l2, extra, inject_spec, pools, panel_cache):
    """拼引擎命令行 + 日志路径（与 `run_tracks.py` 的轮转分支**逐字段一致**）。"""
    sfx = '' if pool == 'all' else '_' + pool
    seed = gen * 10 + 7
    cmd = [RT.PY, '-u', 'engine/loop_engine.py', '--gen=%d' % gen, '--n=%d' % n,
           '--l2=%d' % l2, '--seed=%d' % seed] + list(extra)
    _inj = RT.inject_for(pool, pools, inject_spec)
    if _inj:
        cmd.append('--inject_pools=%s' % ','.join(_inj))
    cmd.append('--mine_pool=%s' % pool)          # ★ v1.3.6 BUG G：所有池都显式传（含 all）
    if panel_cache and panel_cache != 'off':     # ★ 默认不传（= 引擎默认 off ⇒ 命令与旧版一致）
        cmd.append('--panel_cache=%s' % panel_cache)
    logf = os.path.join(RT.LOGD, 'pool%s_gen%d.log' % (sfx, gen))
    errf = os.path.join(RT.LOGD, 'pool%s_gen%d_err.log' % (sfx, gen))
    return cmd, logf, errf, seed


def _launch(pool, gen, n, l2, extra, inject_spec, pools, panel_cache):
    cmd, logf, errf, seed = _cmd_and_paths(pool, gen, n, l2, extra, inject_spec, pools, panel_cache)
    os.makedirs(RT.LOGD, exist_ok=True)
    o = io.open(logf, 'w', encoding='utf-8')
    e = io.open(errf, 'w', encoding='utf-8')
    env = dict(os.environ)
    # ★ 子进程必须显式设 utf-8（否则它按 cp936 写、我们按 utf-8 读 ⇒ 日志乱码、进度解析失效）
    env['PYTHONIOENCODING'] = 'utf-8'
    pr = subprocess.Popen(cmd, cwd=ROOT, stdout=o, stderr=e, env=env,
                          creationflags=RT.NO_WIN)
    RT.log('[START] pool={:<5s} gen={} seed={} pid={} (并行槽 {})'.format(
        pool, gen, seed, pr.pid, os.path.basename(logf)))
    return {'pool': pool, 'gen': gen, 'pr': pr, 'o': o, 'e': e,
            'logf': logf, 'errf': errf, 'cmd': cmd, 't0': time.time()}


def _reap(t):
    """收一个已结束的任务：打印摘要 + 同样的 GUARD + 判定是否算"本轮真实进展"。"""
    try:
        t['o'].close()
        t['e'].close()
    except Exception:
        pass
    rc = t['pr'].returncode
    mins = (time.time() - t['t0']) / 60.0
    errsz = os.path.getsize(t['errf']) if os.path.exists(t['errf']) else 0
    RT.log('[END]   pool={} gen={} 退出码={} 耗时={:.1f}min err={}B'.format(
        t['pool'], t['gen'], rc, mins, errsz))
    ok = True
    try:
        txt = RT.read_log(t['logf'])
        import re
        for pat in (r'入库 \d+ 个新因子[^\n]*', r'L2 通过 \d+/\d+ 个[^\n]*',
                    r'保存状态: [^\n]*'):
            mm = re.findall(pat, txt)
            if mm:
                RT.log('        ' + mm[-1][:150])
        # ★ 与轮转调度器同款守卫：**直接核验命令里有没有"池内判定"那组 flag**
        #   （不用 `fail_calmar` 之类的间接量 —— 那类传感器曾失真导致必然误报）
        _need = ['--pool_obs', '--min_pool_calmar', '--pool_gate_or_all']
        _miss = [f for f in _need if not any(x.startswith(f) for x in t['cmd'])]
        if _miss:
            RT.log('        [!][GUARD] 本池**漏传**池内判定的必要参数: {}'.format(', '.join(_miss)))
        if re.search(r'入库 0 个新因子', txt):
            RT.log('        [note] 本代入库 0（连续多代如此先看 fail_* 分布再下结论）')
    except Exception:
        pass
    t['crashed'] = False
    if rc != 0 or errsz > 0:
        ctl = RT.read_ctl()
        killed = bool(ctl.get('stopAll')) or (t['pool'] in set(ctl.get('stopped') or []))
        # ★ 2026-09-16：把"是不是被用户停的"**带出去**给调用方（用来触发"本轮不再补位"）✓
        t['killed'] = bool(killed)
        # ★ 2026-09-17：**崩溃**（不是被用户停的）⇒ 调用方**本轮就重试**（不必等下一轮）✓
        t['crashed'] = not killed
        RT.log('[!] pool={} 本代非正常结束{} -> **只跳过本池本轮**。人工看 {}'.format(
            t['pool'], '（★ 被用户停止，该代作废下次重跑）' if killed else '（疑似崩溃）',
            os.path.basename(t['errf'])))
        ok = False
        if not killed:
            # ★★★★ 2026-09-17（用户实测："几个池子显示蓝点、只有 300 是绿点，像轮转"）：
            #   **崩溃必须在看板上看得见**！以前只写在日志里 ⇒ 池子每代秒崩、卡片却照旧显示
            #   "并行中"（蓝点），用户完全无从发现 ✗✗（这次就是被这个坑耽误了一整晚）
            #   ⇒ 把各池最近几次"启动即崩"的代数**结构化写进控制文件**，前端在卡片上红字提示 ✓
            try:
                _cr = {k: list(v)[-3:] for k, v in (ctl.get('crashes') or {}).items()}
                _g = list(_cr.get(t['pool']) or [])
                if t['gen'] not in _g:
                    _g.append(t['gen'])
                _cr[t['pool']] = _g[-3:]                      # 只留最近 3 次，别让文件长草
                RT.write_ctl(crashes=_cr)
            except Exception as _e:                           # 记不上也不能影响调度 ✓
                RT.log('        [warn] 崩溃计数写控制文件失败: {!r}'.format(_e))
    return ok


MAX_CRASH_RETRY = 2    # ★ 某池"启动即崩"时**本轮**最多重试几次（2026-09-17；防必崩时无限刷屏）

MIN_FREE_GB = 3.0      # 系统余量（与看板 `mine.MIN_FREE_GB` 同一口径：留 3 GB 不碰）


def _eff_max(max_parallel, auto_parallel, en, st, mem_per_engine):
    """★ **有效并行上限**（2026-09-16 用户实测「加的池只排队、不并行」后新增）。

    `--auto_parallel=1`（看板默认）⇒ **每次迭代重算**：
        `min(可跑池数, floor((可用内存 - 余量) / 每引擎预算))`，至少 1
      ⇒ "能开几个开几个、快爆就少开"（用户要的语义）✓ ；池子加进来 ⇒ 上限**自动跟着长** ✓
    非 auto ⇒ 直接用 `--max_parallel`（显式指定，一动不动）✓

    ⚠ 它只决定"**要不要起新引擎**"；**已经在跑的绝不因上限变小而被杀**（宁慢不炸）✓
    """
    if not auto_parallel:
        return max_parallel
    runnable = len([p for p in en if p not in st])
    free = avail_gb()
    if free is None:
        return max(1, min(runnable, max_parallel))
    cap = int(max(1, (free - MIN_FREE_GB) // max(mem_per_engine, 0.5)))
    return max(1, min(runnable, cap))


def _running_brief(running, now):
    return ' | '.join('%s gen%d(%.0fmin)' % (t['pool'], t['gen'], (now - t['t0']) / 60.0)
                      for t in running) or '无'


def run(pools, rounds, n, l2, extra, inject_spec, no_global,
        max_parallel=3, mem_per_engine=3.0, panel_cache='off', dry=False,
        auto_parallel=False):
    """有界并行跑 `rounds` 轮；返回进程退出码。"""
    plan = []
    for p in pools:
        g0, done = RT.next_gen(p)
        plan.append((p, g0, done))
    RT.log('=' * 76)
    RT.log('★★ 并行模式: 池={} 每池 {} 轮 | 并行上限={}{} | 每引擎预算={:.1f} GB | '
           '面板缓存={}'.format(pools, rounds, max_parallel,
                            '（**自动**：按可用内存与启用池数动态定）' if auto_parallel else '',
                            mem_per_engine, panel_cache))
    if auto_parallel:
        RT.log('   ★ 上限会自动放宽：**你随时点「启动本池」加池，只要有内存就会立刻并行开起来** ✓'
               '（加池不需要重启调度器）')
    RT.log('   可用内存 {:.1f} GB'.format(avail_gb()))
    if panel_cache == 'off':
        RT.log('   [!] 面板缓存关着：每个引擎会**各建一份 4.42 GB 面板** ⇒ '
               '并行 N 个 = N 份 ⇒ 建议加 --panel_cache=use（先跑 tools/build_panel_cache.py）')
    RT.log('=' * 76)
    if dry:
        RT.log('（--dry：只列计划，不执行）')
        return 0

    RT.write_ctl(running=True, round=0, rounds=rounds, phase='mine',
                 enabled=[p for p, _, _ in plan] or list(pools), curPool=None, curGen=None)
    dirty = False
    stopped_by_user = False
    running = []
    last_brief = 0.0
    try:
        for rnd in range(1, rounds + 1):
            ctl = RT.read_ctl()
            if ctl.get('stopAll'):
                RT.log('[CTL] ★ 收到「全部停止」⇒ 结束轮转（随后自动收尾）')
                stopped_by_user = True
                break
            en = set(ctl.get('enabled') or [p for p, _, _ in plan])
            st = set(ctl.get('stopped') or [])
            if not en:
                RT.log('[CTL] 启用池为空 ⇒ 无池可跑，结束轮转')
                break
            RT.log('')
            RT.log('#' * 76)
            RT.log('## 第 {} / {} 轮   启用池={}   本轮停={}   并行上限={}{}'.format(
                rnd, rounds, sorted(en), sorted(st) or '无',
                _eff_max(max_parallel, auto_parallel, en, st, mem_per_engine),
                '(自动)' if auto_parallel else ''))
            RT.log('#' * 76)
            # ---- ★★ 本轮状态：**动态队列**（不是"轮初拍死的列表"）----
            #   ★ 2026-09-16 二次修订（用户实测："我停止一个池然后重新启动，怎么没马上开挖？"）：
            #     并行运行中「启动本池」必须**马上生效** ⇒ 每轮迭代**重新算候选**：
            #     本轮还没启动过、现在仍在启用集、且没被停的池，都能立刻上 ✓
            #   ★★ 同时保住上一版要求（"我停一个池，别自动把闲置池顶上来"）：
            #     `deferred` 记录"本轮不自动补位"的池，并记下**顺延那一刻的 stopped 快照**；
            #     ★ 只有"**你在 stopped 里、之后又被「启动本池」放回来**"的池才允许马上上
            #       ⇒ 既不会自动顶上来，又让你手动加的那个立刻开挖 ✓✓
            launched = set()                 # 本轮已启动
            retries = {}                     # ★ 池 -> 本轮"崩溃重试"已用次数（见 `MAX_CRASH_RETRY`）
            deferred = {}                    # 池 -> 顺延那一刻的 stopped 快照（用来认"你重新启用"）
            ran_round = False
            while True:
                ctl = RT.read_ctl()
                if ctl.get('stopAll') and not stopped_by_user:
                    stopped_by_user = True
                    RT.log('[CTL] ★ 收到「全部停止」⇒ 不再补新任务，等在跑的 {} 个自然结束'.format(
                        len(running)))
                # ★ 启用集/剔除集**每轮迭代重读**（用户随时可能加/停池）—— 放在最前面，下面都要用
                en = set(ctl.get('enabled') or [p for p, _, _ in plan])
                st = set(ctl.get('stopped') or [])
                # ★★★ 有效并行上限：`--auto_parallel` 时**每次都按"当前启用池数 + 可用内存"重算**
                #   2026-09-16 用户实测：「点一个启动、再点一个池子，怎么是加入轮转而不是并行？」
                #   ⇒ 真因之二：并行数是**启动那一刻按 `len(pools)` 算死的**（1 个池 ⇒ `--max_parallel=1`）
                #     ⇒ 后来加的池**永远只能排队**（哪怕内存富余）✗ ⇒ 现在 auto 模式下**动态放宽** ✓
                eff_max = _eff_max(max_parallel, auto_parallel, en, st, mem_per_engine)
                if stopped_by_user:
                    for p in en:
                        if p not in launched:
                            deferred[p] = set(st)
                # ---- 收割已结束的 ----
                for t in list(running):
                    if t['pr'].poll() is not None:
                        if _reap(t):
                            ran_round = True
                            dirty = True
                        if t.get('killed') and len(deferred) == 0 and not stopped_by_user:
                            _st0 = set(RT.read_ctl().get('stopped') or [])
                            for p in en:
                                if p not in launched:
                                    deferred[p] = set(_st0)
                            RT.log('[CTL] ★ 检测到「单独停止」⇒ **本轮不再自动补位**：'
                                   '就保持"停完剩下的 {} 个"在跑；空出来的槽**留给你自己决定**'
                                   '（「启动本池」的那个会**马上**开挖）✓'.format(len(running) - 1))
                        running.remove(t)
                        # ★★★★ 2026-09-17 修（用户实测："只有 300 池是绿点在跑，但显示有 2 个池在挖"）：
                        #   收割后**立刻按当前在跑集合重写 `active`** —— 否则控制文件里会残留
                        #   **已死引擎**的 `{pool, gen, pid}`（原来只在"启动新引擎"时才写它）✗
                        #   ⇒ 看板/鼠标提示会拿旧列表撒谎（后端另有一道"按活进程核对"，双保险）✓
                        RT.write_ctl(active=[{'pool': x['pool'], 'gen': x['gen'], 'pid': x['pr'].pid}
                                             for x in running])
                        # ★★ 2026-09-17：**崩了的池本轮就重试**（用户在"蓝点"上白等过一整晚）——
                        #   原来崩掉也记 `launched` ⇒ 该池要等到**下一轮**（可能半小时后）才再试 ✗
                        #   ⇒ 现在按 `MAX_CRASH_RETRY` 次重试（防"必崩"时无限重启刷屏）✓
                        if t.get('crashed'):
                            _n = retries.get(t['pool'], 0)
                            if _n < MAX_CRASH_RETRY:
                                retries[t['pool']] = _n + 1
                                launched.discard(t['pool'])
                                RT.log('[CTL] ★ pool={} 本代崩溃 ⇒ **本轮立刻重试**（第 {}/{} 次）'
                                       '；若一直崩，看它的 *_err.log（别再干等下一轮）✗'.format(
                                           t['pool'], _n + 1, MAX_CRASH_RETRY))
                            else:
                                RT.log('[CTL] pool={} 本轮已崩 {} 次 ⇒ 不再重试（留到下一轮）；'
                                       '**先看 *_err.log 的 traceback** ✗'.format(
                                           t['pool'], MAX_CRASH_RETRY))
                # ---- 动态候选（★ 每次迭代重算）----
                # ★★★ 候选来自**当前启用集**，不是启动时的 `--pools` 快照！
                #   2026-09-16 用户实测「点了一个启动、再点一个池子启动，怎么是加入轮转而不是并行？」
                #   ⇒ 真因：`plan` 是**启动时 `--pools=300` 拍死的** ⇒ 后来加的池**既不在候选、也不在队列**
                #     ⇒ **永远不会**在这个调度器里跑（连下一轮都不会）✗✗（我上一版只在"重启路径"测过，
                #     漏了"已有调度器在跑时加池"，测试盲区）
                #   ⇒ 现在：候选 = `en - stopped - 本轮已启动`（顺序按 `enabled` 列表，稳定）✓
                cand = [p for p in en
                        if p not in launched and p not in st
                        and (p not in deferred
                             or (p in deferred[p] and p not in st))]   # ★ 你放回来的 ⇒ 允许马上上
                if not running and not cand:
                    _left = [p for p in en if p not in launched]
                    if _left:
                        RT.log('[CTL] 本轮剩余 {} 个池未启动（{}）⇒ 留到下一轮'
                               '（下一轮按你保留的启用集重新组队）'.format(len(_left), ' '.join(_left)))
                    break
                # ---- 启动（能开几个开几个；上限 = `eff_max`）----
                while cand and len(running) < eff_max and not stopped_by_user:
                    p = cand[0]
                    ctl = RT.read_ctl()
                    if ctl.get('stopAll'):
                        stopped_by_user = True
                        break
                    en2 = set(ctl.get('enabled') or [p2 for p2, _, _ in plan])
                    st2 = set(ctl.get('stopped') or [])
                    if p not in en2 or p in st2:
                        RT.log('[SKIP] pool={:<5s} {} ⇒ 本轮跳过（不影响其他池）'.format(
                            p, '不在启用集合' if p not in en2 else '已被单独停止'))
                        deferred.setdefault(p, set(st2))     # ★ 不占坑：之后你放回来仍能马上上 ✓
                        cand.pop(0)
                        continue
                    free = avail_gb()
                    if free < mem_per_engine:
                        RT.log('[MEM] 可用 {:.1f} GB < 每引擎预算 {:.1f} GB ⇒ 等 15s 再试'
                               '（宁慢不炸；内存是这台机器的真瓶颈）'.format(free, mem_per_engine))
                        time.sleep(15)
                        continue
                    cand.pop(0)
                    launched.add(p)                      # ★ 真正启动才记"本轮已启动"
                    gen, done = RT.next_gen(p)           # ★ 每代现取（journal 是唯一事实源）
                    t = _launch(p, gen, n, l2, extra, inject_spec, pools, panel_cache)
                    t['done'] = done
                    running.append(t)
                    # ★ auto 模式下把**当前有效上限**写进控制文件 ⇒ 看板显示的是"真话"（不是启动时的旧值）✓
                    _kw = {} if not auto_parallel else {'maxParallel': eff_max}
                    RT.write_ctl(round=rnd, curPool=p, curGen=gen, phase='mine',
                                 active=[{'pool': x['pool'], 'gen': x['gen'], 'pid': x['pr'].pid}
                                         for x in running], **_kw)
                if running or cand:
                    now = time.time()
                    if now - last_brief > 60:         # 每分钟一条进度（别刷屏）
                        last_brief = now
                        RT.log('[RUN] 第 {} 轮 | 在跑 {} 个: {} | 待启动 {} | 上限 {}{} | 可用 {:.1f} GB'.format(
                            rnd, len(running), _running_brief(running, now), len(cand), eff_max,
                            '(自动)' if auto_parallel else '', avail_gb()))
                    time.sleep(5)
            # ---- 一轮结束 ⇒ 自动收尾（**必须等本轮全部跑完**：跨池审查要求"无人在写 docs/"）----
            #   ⚠ 走到这里保证"没有在跑的、也没有待启动的"（上面 `break` 的条件）⇒ 不必再判 queue ✓
            if ran_round and not no_global:
                RT.do_global_tail('第 {} / {} 轮结束（并行模式）'.format(rnd, rounds))
                dirty = False
            if stopped_by_user:
                break
    finally:
        # ★ 调度器退出前：把还在跑的子进程**收干净**（否则它们会变成无主进程继续吃内存）
        for t in running:
            try:
                if t['pr'].poll() is None:
                    t['pr'].terminate()
            except Exception:
                pass
        for t in running:
            try:
                t['pr'].wait(timeout=30)
            except Exception:
                pass
            try:
                t['o'].close()
                t['e'].close()
            except Exception:
                pass
        if stopped_by_user and dirty and not no_global:
            RT.do_global_tail('★ 全部停止后（并行模式）')
            dirty = False
        RT.write_ctl(running=False, phase='idle', curPool=None, curGen=None,
                     stopAll=False, tailAt=None, active=[])
        RT.log('  [CTL] 调度器退出（已复位控制文件）✓')
    RT.log('===== 全部轨道结束（并行模式）=====')
    return 0
