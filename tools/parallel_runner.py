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
    if rc != 0 or errsz > 0:
        ctl = RT.read_ctl()
        killed = bool(ctl.get('stopAll')) or (t['pool'] in set(ctl.get('stopped') or []))
        # ★ 2026-09-16：把"是不是被用户停的"**带出去**给调用方（用来触发"本轮不再补位"）✓
        t['killed'] = bool(killed)
        RT.log('[!] pool={} 本代非正常结束{} -> **只跳过本池本轮**。人工看 {}'.format(
            t['pool'], '（★ 被用户停止，该代作废下次重跑）' if killed else '（疑似崩溃）',
            os.path.basename(t['errf'])))
        ok = False
    return ok


def _running_brief(running, now):
    return ' | '.join('%s gen%d(%.0fmin)' % (t['pool'], t['gen'], (now - t['t0']) / 60.0)
                      for t in running) or '无'


def run(pools, rounds, n, l2, extra, inject_spec, no_global,
        max_parallel=3, mem_per_engine=3.0, panel_cache='off', dry=False):
    """有界并行跑 `rounds` 轮；返回进程退出码。"""
    plan = []
    for p in pools:
        g0, done = RT.next_gen(p)
        plan.append((p, g0, done))
    RT.log('=' * 76)
    RT.log('★★ 并行模式: 池={} 每池 {} 轮 | 并行上限={} | 每引擎预算={:.1f} GB | '
           '面板缓存={}'.format(pools, rounds, max_parallel, mem_per_engine, panel_cache))
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
            RT.log('## 第 {} / {} 轮   启用池={}   本轮停={}   并行上限={}'.format(
                rnd, rounds, sorted(en), sorted(st) or '无', max_parallel))
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
            deferred = {}                    # 池 -> 顺延那一刻的 stopped 快照（用来认"你重新启用"）
            ran_round = False
            while True:
                ctl = RT.read_ctl()
                if ctl.get('stopAll') and not stopped_by_user:
                    stopped_by_user = True
                    RT.log('[CTL] ★ 收到「全部停止」⇒ 不再补新任务，等在跑的 {} 个自然结束'.format(
                        len(running)))
                if stopped_by_user:
                    for p, _, _ in plan:
                        if p not in launched:
                            deferred[p] = set(RT.read_ctl().get('stopped') or [])
                # ---- 收割已结束的 ----
                for t in list(running):
                    if t['pr'].poll() is not None:
                        if _reap(t):
                            ran_round = True
                            dirty = True
                        if t.get('killed') and len(deferred) == 0 and not stopped_by_user:
                            _st0 = set(RT.read_ctl().get('stopped') or [])
                            for p, _, _ in plan:
                                if p not in launched:
                                    deferred[p] = set(_st0)
                            RT.log('[CTL] ★ 检测到「单独停止」⇒ **本轮不再自动补位**：'
                                   '就保持"停完剩下的 {} 个"在跑；空出来的槽**留给你自己决定**'
                                   '（「启动本池」的那个会**马上**开挖）✓'.format(len(running) - 1))
                        running.remove(t)
                # ---- 动态候选（★ 每次迭代重算）----
                en = set(ctl.get('enabled') or [p for p, _, _ in plan])
                st = set(ctl.get('stopped') or [])
                cand = [(p, g, d) for (p, g, d) in plan
                        if p not in launched and p in en and p not in st
                        and (p not in deferred
                             or (p in deferred[p] and p not in st))]   # ★ 你放回来的 ⇒ 允许马上上
                if not running and not cand:
                    _left = [p for p, _, _ in plan if p not in launched]
                    if _left:
                        RT.log('[CTL] 本轮剩余 {} 个池未启动（{}）⇒ 留到下一轮'
                               '（下一轮按你保留的启用集重新组队）'.format(len(_left), ' '.join(_left)))
                    break
                # ---- 启动（能开几个开几个）----
                while cand and len(running) < max_parallel and not stopped_by_user:
                    p, _g0, _done = cand[0]
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
                    RT.write_ctl(round=rnd, curPool=p, curGen=gen, phase='mine',
                                 active=[{'pool': x['pool'], 'gen': x['gen'], 'pid': x['pr'].pid}
                                         for x in running])
                if running or cand:
                    now = time.time()
                    if now - last_brief > 60:         # 每分钟一条进度（别刷屏）
                        last_brief = now
                        RT.log('[RUN] 第 {} 轮 | 在跑 {} 个: {} | 待启动 {} | 可用 {:.1f} GB'.format(
                            rnd, len(running), _running_brief(running, now), len(cand),
                            avail_gb()))
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
