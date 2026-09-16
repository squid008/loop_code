# -*- coding: utf-8 -*-
"""挖掘控制（前端「启动/停止」按钮的后端）—— **2026-09-16 起改为「每池一个独立进程」**。

## ★★★★★ 为什么重构（2026-09-16 用户反馈）
用户：「我点全部停止好像没反应嘛，然后要做成**真正能单独启停某个池**，
      要注意**每个池之间相互不能干扰、搞串了**哈」

**旧实现的问题（串行驱动）**：
`run_tracks.py --pools=300,500,1000,50,all` = **1 个进程串行 for 循环** ⇒
- 实测（2026-09-15 23:38 → 09-16 08:57，**9.3 小时**）：**300 池跑了 24 代**，
  而 **500/1000/50 一代没跑**（时间全被前面的池吃光）✗✗
- "停止某个池"**不可能**（进程不分池）

**新实现（每池独立进程）**：
```
每池一个 run_tracks.py --pools=<单池> --rounds=N --no_global
  300  → PID A      500  → PID B      1000 → PID C      50 → PID D      all → PID E
```
⇒ 任意组合启停 ✓ · 互不干扰 ✓

## ★★★★ 为什么"每池独立"是**安全**的（依据，不是想当然）
1. **引擎输出完全池隔离** —— `loop_engine.set_mine_pool(tag)` 会把 **7 个路径全部按池派生**：
   `STATE`(`loop_state_{pool}.pkl`) · `ARCHIVE`(`loop_archive_{pool}.csv`) · `JOURNAL`(`loop_journal_{pool}.md`) ·
   `LIBRARY`(`factor_library_{pool}.md`) · `STYLE_OBS` · `STRIP_OBS` · `POOL_OBS`
   ⇒ 实测 `docs/` 下每族都是 **5 份**（`all` 无后缀 + `_300`/`_500`/`_1000`/`_50`）✓✓
2. **`--no_global` 挡掉唯一的全局冲突点** —— `run_tracks.py` 一轮结束会跑
   `build_facs.py --only-new` 与 `cross_pool_review.py`（**跨池去重，必须看全所有池**）；
   5 份并行会**重复 5 倍 + 并发写同一份 `factor_library_crosspool.md` / `factor_pool_selected.md`** ✗
   ⇒ 池驱动一律 `--no_global`；全局收尾由**单独一次**调用完成（`run_global()`）✓
3. **`all` 池的「注入对照集」只读**其它池的 bank ⇒ 不冲突 ✓

## ⚠ 内存硬约束（实测 2026-09-16）
机器 **47.9 GB 总 / 27.1 GB 可用**；单引擎约 **6~9 GB** ⇒ **最多并行 ~3 个** ✗
⇒ 所以 `start()` **启动前查可用内存**，不够就**拒绝并说明**（而不是 OOM 崩掉）✓

## ★★ 单池「停止」现在真的只停该池 ✓（按 `--pools=<池>` 识别归属）
"""
import ctypes
import os
import subprocess
import sys
import time

from . import settings
from .sources import core, pools

RUN_TRACKS = os.path.join(settings.PROJECT_ROOT, 'tools', 'run_tracks.py')
LOG_DIR = os.path.join(settings.PROJECT_ROOT, 'ai_test', '_tracks')

ROUNDS_MIN, ROUNDS_MAX = 1, 200
DEFAULT_ROUNDS = 50
GB_PER_ENGINE = 9.0          # ★ 保守估计（实测 6~9 GB，取上限避免 OOM）
MIN_FREE_GB = 3.0            # 低于此值不给启动


class MineError(Exception):
    def __init__(self, msg, code=400):
        super().__init__(msg)
        self.msg = msg
        self.code = code


# ---------------------------------------------------------------- 资源
def avail_gb():
    """可用物理内存（GB）。失败返回 None（⇒ 调用方降级为"不检查"）。"""
    try:
        class MS(ctypes.Structure):
            _fields_ = [('dwLength', ctypes.c_ulong), ('dwMemoryLoad', ctypes.c_ulong),
                        ('ullTotalPhys', ctypes.c_ulonglong), ('ullAvailPhys', ctypes.c_ulonglong),
                        ('ullTotalPageFile', ctypes.c_ulonglong), ('ullAvailPageFile', ctypes.c_ulonglong),
                        ('ullTotalVirtual', ctypes.c_ulonglong), ('ullAvailVirtual', ctypes.c_ulonglong),
                        ('ullAvailExtendedVirtual', ctypes.c_ulonglong)]

        m = MS()
        m.dwLength = ctypes.sizeof(MS)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
        return m.ullAvailPhys / 1024.0 ** 3
    except Exception:
        return None


# ---------------------------------------------------------------- 进程
def _procs(fresh=True):
    if fresh:
        core._CACHE.pop('procs', None)
    raw = core.cached('procs', 3.0, pools.list_processes)
    return [pools.classify_proc(p) for p in raw if not p.get('err')]


def by_pool(procs=None):
    """⇒ `{pool: {'driver': [pid..], 'engine': [pid..]}}`（按 `--pools=`/`--mine_pool=` 归属）。"""
    procs = procs if procs is not None else _procs()
    out = {}
    for p in procs:
        if p['kind'] not in ('driver', 'engine'):
            continue
        for pool in (p.get('pools') or []):
            slot = out.setdefault(pool, {'driver': [], 'engine': []})
            slot[p['kind']].append(p['pid'])
    return out


def state():
    """给前端：每池能否启动/停止 + 资源。"""
    procs = _procs()
    bp = by_pool(procs)
    free = avail_gb()
    running = sorted(bp.keys())
    max_par = (int((free - MIN_FREE_GB) / GB_PER_ENGINE) if free is not None else None)
    return {
        'mode': 'per-pool',                      # ★ 模式标识：每池独立进程
        'knownPools': list(core.POOL_KEYS),
        'runningPools': running,
        'byPool': {k: {'driver': v['driver'], 'engine': v['engine'], 'running': True}
                   for k, v in bp.items()},
        'drivers': [p for p in procs if p['kind'] == 'driver'],
        'engines': [p for p in procs if p['kind'] == 'engine'],
        'anyRunning': bool(running),
        'freeGB': (round(free, 1) if free is not None else None),
        'gbPerEngine': GB_PER_ENGINE,
        # ★ 还能再启动几个（内存视角）
        'canStartMore': (max(0, max_par - len([p for p in procs if p['kind'] == 'driver']))
                         if max_par is not None else None),
        'maxParallel': max_par,
        'defaultRounds': DEFAULT_ROUNDS,
        'roundsRange': [ROUNDS_MIN, ROUNDS_MAX],
        'script': os.path.relpath(RUN_TRACKS, settings.PROJECT_ROOT),
        'note': ('每池一个独立进程（可单独启停、互不干扰）。'
                 '⚠ 单引擎约需 %.0f GB ⇒ 本机可用 %.1f GB，**最多并行约 %s 个**。'
                 '启停某池只影响该池；全局收尾（跨池审查）请用「收尾审查」。'
                 % (GB_PER_ENGINE, (free or 0), max_par)) if free is not None else
                '每池一个独立进程（可单独启停、互不干扰）。',
    }


# ---------------------------------------------------------------- 启动
def start(pool_list, rounds=DEFAULT_ROUNDS, no_global=True):
    """**为每个池各起一个独立驱动进程**。已在跑的池会被跳过（不重复启动）。"""
    rounds = int(rounds)
    if not (ROUNDS_MIN <= rounds <= ROUNDS_MAX):
        raise MineError('轮数必须在 %d~%d 之间（收到 %s）' % (ROUNDS_MIN, ROUNDS_MAX, rounds))

    pool_list = [str(x).strip() for x in (pool_list or []) if str(x).strip()]
    if not pool_list:
        pool_list = list(core.POOL_KEYS)
    bad = [p for p in pool_list if p not in core.POOL_KEYS]
    if bad:
        raise MineError('未知池名: %s（可选 %s）' % (bad, list(core.POOL_KEYS)))
    if not os.path.exists(RUN_TRACKS):
        raise MineError('找不到 %s' % os.path.relpath(RUN_TRACKS, settings.PROJECT_ROOT), 500)

    procs = _procs()
    bp = by_pool(procs)
    todo = [p for p in pool_list if p not in bp]          # ★ 跳过已在跑的池
    skipped = [{'pool': p, 'why': '已在跑', 'pids': bp[p]['driver'] + bp[p]['engine']}
               for p in pool_list if p in bp]

    # ★ 内存检查（只算"要新起的"个数）
    free = avail_gb()
    n_new = len(todo)
    if free is not None and n_new > 0:
        need = n_new * GB_PER_ENGINE
        if free - need < MIN_FREE_GB:
            raise MineError(
                '内存不足：可用 %.1f GB，新起 %d 个引擎约需 %.0f GB（留 %.0f GB 余量）'
                '⇒ 请减少同时启动的池数（本机最多并行约 %d 个）✗'
                % (free, n_new, need, MIN_FREE_GB, max(int((free - MIN_FREE_GB) / GB_PER_ENGINE), 0)), 409)
    if not todo:
        return {'ok': True, 'started': [], 'skipped': skipped,
                'note': '所有指定池都已在跑 ⇒ 未重复启动 ✓'}

    os.makedirs(LOG_DIR, exist_ok=True)
    env = dict(os.environ)
    env['PYTHONIOENCODING'] = 'utf-8'
    flags = 0
    if os.name == 'nt':
        flags = getattr(subprocess, 'DETACHED_PROCESS', 0) | getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0)

    started = []
    for p in todo:
        args = [sys.executable, RUN_TRACKS, '--pools=%s' % p, '--rounds=%d' % rounds]
        if no_global:
            args.append('--no_global')
        log = os.path.join(LOG_DIR, '_ui_start_%s.log' % p)
        fout = open(log, 'ab')
        proc = subprocess.Popen(args, cwd=settings.PROJECT_ROOT, env=env, stdout=fout,
                                stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                creationflags=flags, close_fds=True)
        started.append({'pool': p, 'pid': proc.pid, 'log': os.path.relpath(log, settings.PROJECT_ROOT),
                        'cmd': ' '.join(args[1:])})
    time.sleep(3)
    for s in started:
        s['alive'] = _alive(s['pid'])
    return {
        'ok': True,
        'started': started,
        'skipped': skipped,
        'noGlobal': no_global,
        'freeGB': (round(free, 1) if free is not None else None),
        'note': ('已为 %d 个池各起一个独立进程（互不干扰）%s。'
                 '真实进度见 `ai_test/_tracks/_driver.log` 与 `pool_<池>_gen<N>.log`；'
                 '全局收尾（跨池审查）需另点「收尾审查」✓'
                 % (len(started), '；跳过的已在跑：%s' % [s['pool'] for s in skipped] if skipped else '')),
    }


def _alive(pid):
    try:
        r = subprocess.run(['tasklist', '/FI', 'PID eq %d' % pid, '/NH'],
                           capture_output=True, text=True, encoding='utf-8', errors='replace')
        return str(pid) in (r.stdout or '')
    except Exception:
        return None


# ---------------------------------------------------------------- 停止
def stop(pool=None, **kw):
    """停止：`pool=None` ⇒ 全部；指定池 ⇒ **只停该池**（真独立）✓"""
    if pool and pool not in core.POOL_KEYS:
        raise MineError('未知池名: %s' % pool)

    procs = _procs()
    if pool:
        want = [p for p in procs if p['kind'] in ('driver', 'engine') and pool in (p.get('pools') or [])]
    else:
        want = [p for p in procs if p['kind'] in ('driver', 'engine')]

    killed = []
    # ★ 先杀 driver（树杀 /T 会连带其 engine 子进程）
    for p in sorted(want, key=lambda x: 0 if x['kind'] == 'driver' else 1):
        r = subprocess.run(['taskkill', '/PID', str(p['pid']), '/T', '/F'],
                           capture_output=True, text=True, encoding='utf-8', errors='replace')
        killed.append({'pid': p['pid'], 'kind': p['kind'], 'pools': p.get('pools'),
                       'rc': r.returncode, 'out': (r.stdout or r.stderr or '').strip()[:160]})
        time.sleep(0.5)

    # 兜底：再查一次，残留的（孤儿引擎）也杀
    time.sleep(1)
    left = _procs()
    leftover = ([p for p in left if p['kind'] in ('driver', 'engine') and pool in (p.get('pools') or [])]
                if pool else [p for p in left if p['kind'] in ('driver', 'engine')])
    for p in leftover:
        r = subprocess.run(['taskkill', '/PID', str(p['pid']), '/T', '/F'],
                           capture_output=True, text=True, encoding='utf-8', errors='replace')
        killed.append({'pid': p['pid'], 'kind': p['kind'], 'pools': p.get('pools'),
                       'rc': r.returncode, 'out': (r.stdout or r.stderr or '').strip()[:160]})
    time.sleep(1)
    still = _procs()
    still_run = ([p for p in still if p['kind'] in ('driver', 'engine') and pool in (p.get('pools') or [])]
                 if pool else [p for p in still if p['kind'] in ('driver', 'engine')])
    return {
        'ok': not still_run,
        'scope': ('pool:%s' % pool) if pool else 'all',
        'killed': killed,
        'stillRunning': [{'pid': p['pid'], 'kind': p['kind'], 'pools': p.get('pools')} for p in still_run],
        'note': ('已停止%s。⚠ 正在跑的那一代**未完成**（state 不写入）⇒ 下次从该代重跑 ✓'
                 % ('池 %s' % pool if pool else '全部池')),
    }


# ---------------------------------------------------------------- 全局收尾
def run_global():
    """跑**一次性全局收尾**（facs 落地 + 跨池审查 + 精选池）。

    ⇒ 用 `run_tracks.py --rounds=0`：**不跑任何代数**，直接进收尾 ✓
    ⚠ 要求：**当前无任何池在跑**（否则会与它们抢写 `crosspool.md` / `factor_pool_selected.md`）✗
    """
    procs = _procs()
    running = [p for p in procs if p['kind'] in ('driver', 'engine')]
    if running:
        raise MineError('仍有挖掘在跑（PID %s）⇒ 拒绝收尾：跨池审查必须"看全所有池且无人写" '
                        '⇒ 请先停止所有池 ✗' % [p['pid'] for p in running], 409)
    args = [sys.executable, RUN_TRACKS, '--pools=300', '--rounds=0']
    os.makedirs(LOG_DIR, exist_ok=True)
    env = dict(os.environ)
    env['PYTHONIOENCODING'] = 'utf-8'
    flags = getattr(subprocess, 'DETACHED_PROCESS', 0) | getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0) \
        if os.name == 'nt' else 0
    log = os.path.join(LOG_DIR, '_ui_global.log')
    proc = subprocess.Popen(args, cwd=settings.PROJECT_ROOT, env=env, stdout=open(log, 'ab'),
                            stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                            creationflags=flags, close_fds=True)
    time.sleep(2)
    return {'ok': True, 'pid': proc.pid, 'alive': _alive(proc.pid),
            'log': os.path.relpath(log, settings.PROJECT_ROOT),
            'note': '全局收尾已启动（facs 落地 + 跨池审查 + 精选池）；日志见 `ai_test/_tracks/_ui_global.log` ✓'}
