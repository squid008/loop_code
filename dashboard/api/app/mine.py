# -*- coding: utf-8 -*-
"""挖掘控制（前端「启动/停止」按钮的后端）—— **2026-09-16 新增**。

## ★★★★ 安全设计（这是本模块最重要的部分）
1. **只允许启动一个固定脚本** —— `tools/run_tracks.py`，**不接受任意命令/任意参数** ✗
2. **池名白名单** —— 必须 ∈ `engine/loop_pools.py` 的 `POOLS`（由 `core.POOL_KEYS` 提供）✓
3. **轮数范围校验** —— `1 <= rounds <= 200` ✓
4. ★★★ **防重复启动（最关键）** —— 已有 `run_tracks.py` **或** `loop_engine.py` 在跑 ⇒ **拒绝启动**（HTTP 409）
   为什么：`run_tracks.py` 是**串行驱动**，两个驱动同时跑会**抢同一份 `engine/loop_state*.pkl`**
   ⇒ **因子库/冻结集合会互相覆盖损坏** ✗✗（比崩掉严重得多，因为不可自动恢复）
5. **停止用树杀** `taskkill /PID <驱动PID> /T /F` ⇒ 连带引擎子进程 ✓
6. ★ **子进程脱离父进程**（`DETACHED_PROCESS`）⇒ 后端重启/退出**不会**影响正在跑的挖掘 ✓

## ⚠ 单池语义（必须在 UI 上讲清楚）
`run_tracks.py` 是**串行驱动**（一个进程依次跑多个池）⇒
- **「启动某池」** = 起一个**只跑该池**的驱动（仅当**当前无任何驱动**时才允许）✓
- **「停止某池」** = 只能停**整个驱动**（因为驱动进程不分池）⇒ UI 必须提示"会停掉全部" ✓
"""
import os
import subprocess
import sys
import time

from . import settings
from .sources import core, pools

RUN_TRACKS = os.path.join(settings.PROJECT_ROOT, 'tools', 'run_tracks.py')
LOG_OUT = os.path.join(settings.PROJECT_ROOT, 'ai_test', '_tracks', '_ui_start.log')

ROUNDS_MIN, ROUNDS_MAX = 1, 200
DEFAULT_ROUNDS = 50


class MineError(Exception):
    """带 HTTP 语义的错（`code` 给前端区分）。"""

    def __init__(self, msg, code=400):
        super().__init__(msg)
        self.msg = msg
        self.code = code


def _procs():
    """当前与本项目相关的 python 进程（复用 `pools` 的查询+分类）。"""
    raw = core.cached('procs', 4.0, pools.list_processes)
    return [pools.classify_proc(p) for p in raw if not p.get('err')]


def _drivers(procs=None):
    procs = procs if procs is not None else _procs()
    return [p for p in procs if p.get('kind') == 'driver']


def _engines(procs=None):
    procs = procs if procs is not None else _procs()
    return [p for p in procs if p.get('kind') == 'engine']


def state():
    """给前端：能不能启动 / 现在谁在跑 / 默认参数。"""
    core._CACHE.pop('procs', None)          # 控制类接口一律**实时**查进程
    procs = _procs()
    drv, eng = _drivers(procs), _engines(procs)
    return {
        'canStart': (not drv) and (not eng),
        'drivers': drv,
        'engines': eng,
        'runningPools': sorted({p for e in eng for p in (e.get('pools') or [])}),
        'driverPools': sorted({p for d in drv for p in (d.get('pools') or [])}),
        'defaultRounds': DEFAULT_ROUNDS,
        'roundsRange': [ROUNDS_MIN, ROUNDS_MAX],
        'knownPools': list(core.POOL_KEYS),
        'script': os.path.relpath(RUN_TRACKS, settings.PROJECT_ROOT),
        'note': ('单池「停止」= 停止整个驱动（`run_tracks.py` 为串行驱动，进程不分池）'
                 '；「启动」仅在当前无任何挖掘进程时允许（防止两份驱动抢同一份 state）'),
    }


def start(pool_list, rounds=DEFAULT_ROUNDS):
    """启动挖掘。`pool_list` 可为空 ⇒ 用全部池。"""
    rounds = int(rounds)
    if not (ROUNDS_MIN <= rounds <= ROUNDS_MAX):
        raise MineError('轮数必须在 %d~%d 之间（收到 %s）' % (ROUNDS_MIN, ROUNDS_MAX, rounds))

    if not pool_list:
        pool_list = list(core.POOL_KEYS)
    pool_list = [str(x).strip() for x in pool_list if str(x).strip()]
    bad = [p for p in pool_list if p not in core.POOL_KEYS]
    if bad:
        raise MineError('未知池名: %s（可选 %s）' % (bad, list(core.POOL_KEYS)))
    if not pool_list:
        raise MineError('至少要选一个池')

    if not os.path.exists(RUN_TRACKS):
        raise MineError('找不到 %s' % os.path.relpath(RUN_TRACKS, settings.PROJECT_ROOT), 500)

    # ★★★ 防重复（核心安全）
    core._CACHE.pop('procs', None)
    procs = _procs()
    drv, eng = _drivers(procs), _engines(procs)
    if drv or eng:
        who = []
        if drv:
            who.append('驱动 PID %s（池 %s）' % (drv[0]['pid'], '/'.join(drv[0].get('pools') or []) or '?'))
        if eng:
            who.append('引擎 PID %s（池 %s）' % (eng[0]['pid'], '/'.join(eng[0].get('pools') or []) or '?'))
        raise MineError(
            '已有挖掘在跑：%s ⇒ **拒绝启动**（两个驱动会同抢 `engine/loop_state*.pkl`，'
            '会损坏因子库 ✗）。请先「全部停止」。' % '；'.join(who), 409)

    args = [sys.executable, RUN_TRACKS,
            '--pools=%s' % ','.join(pool_list),
            '--rounds=%d' % rounds]
    os.makedirs(os.path.dirname(LOG_OUT), exist_ok=True)
    env = dict(os.environ)
    env['PYTHONIOENCODING'] = 'utf-8'        # ★ 防 Windows GBK 打印崩
    flags = 0
    if os.name == 'nt':
        # ★ 脱离父进程：后端重启/退出不影响挖掘
        flags = getattr(subprocess, 'DETACHED_PROCESS', 0) | getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0)
    fout = open(LOG_OUT, 'ab')
    proc = subprocess.Popen(args, cwd=settings.PROJECT_ROOT, env=env, stdout=fout,
                            stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                            creationflags=flags, close_fds=True)
    time.sleep(3)                            # 稍等，让进程稳定
    alive = proc.poll() is None
    core._CACHE.pop('procs', None)
    return {
        'ok': True,
        'pid': proc.pid,
        'alive': alive,
        'pools': pool_list,
        'rounds': rounds,
        'cmd': ' '.join(args[1:]),
        'log': os.path.relpath(LOG_OUT, settings.PROJECT_ROOT),
        'note': ('已启动。真实日志见 `ai_test/_tracks/_driver.log` 与 `pool_<池>_gen<N>.log`；'
                 '刷新看板即可看到进度。'),
    }


def stop(all_pools=True, pool=None):
    """停止挖掘：树杀驱动（连带引擎）。`all_pools=False` 时仅作提示（串行驱动不分池）。"""
    core._CACHE.pop('procs', None)
    procs = _procs()
    drv, eng = _drivers(procs), _engines(procs)
    killed = []
    # 先杀驱动（树杀会连带其引擎子进程）
    for d in drv:
        r = subprocess.run(['taskkill', '/PID', str(d['pid']), '/T', '/F'],
                           capture_output=True, text=True, encoding='utf-8', errors='replace')
        killed.append({'pid': d['pid'], 'kind': 'driver',
                       'rc': r.returncode, 'out': (r.stdout or r.stderr or '').strip()[:200]})
        time.sleep(1)
    # 再兜底杀残留引擎（孤儿）
    core._CACHE.pop('procs', None)
    for e in _engines(_procs()):
        r = subprocess.run(['taskkill', '/PID', str(e['pid']), '/T', '/F'],
                           capture_output=True, text=True, encoding='utf-8', errors='replace')
        killed.append({'pid': e['pid'], 'kind': 'engine',
                       'rc': r.returncode, 'out': (r.stdout or r.stderr or '').strip()[:200]})
    time.sleep(1)
    core._CACHE.pop('procs', None)
    still = _drivers() + _engines()
    return {
        'ok': not still,
        'killed': killed,
        'stillRunning': [{'pid': p['pid'], 'kind': p['kind']} for p in still],
        'scope': 'all' if all_pools else ('pool:%s' % pool),
        'note': ('串行驱动已被停止（含其引擎子进程）。'
                 '⚠ 正在跑的那一代**未完成**，其 state 不会被写入 ⇒ 下次从该代重跑 ✓'),
    }
