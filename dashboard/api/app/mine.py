# -*- coding: utf-8 -*-
"""挖掘控制（看板「启动/停止」按钮的后端）—— **2026-09-16 v1.3.0：单调度器 + 池轮转**。

## ★★★★★ 用户拍板（原话）
> 「1、走 2； 2、立即停不影响其他池挖掘审查吧？ 3、每轮结束自动收尾。
>  4、有个问题，如果一轮中间我停了一个池子，它是不是就不能收尾了？我觉得应该也要能收尾。
>  启停任意池子都不能影响收尾这个不冲突吧？然后一键全部停掉后，它就自动进入收尾阶段」

## ★★★★ 为什么放弃"每池一进程"（v1.2.0 的做法）—— **内存**
实测（用户质疑"四个池四份内存这不科学"，**他是对的**）：
- 只读大对象 `B`（49 个 float32 字段，3309×5384）≈ **3.25 GB** ⇒ 每进程**各一份** ✗
- 单引擎峰值 ≈ 6 GB ⇒ 5 个池 = **30 GB** > 可用 **27 GB** ⇒ **根本起不来** ✗
- ★ 但每个池只是它的**列子集**（`set_mine_pool`：「L1 子面板列 = 该池并集」）
  ⇒ **同一时刻只跑 1 个引擎** ⇒ 内存 **~6 GB**（省 5 倍）✓
- ★ 且 CPU 仅 6 核/12 线程而单引擎已吃满多核 ⇒ **并行会被互相拖慢 ⇒ 损失≈0** ✓

## 新架构：**1 个调度器 + 池轮转**
```
run_tracks.py --pools=<全部> --rounds=N          ← 1 个调度器进程（不载面板，内存 ~50 MB）
   for r in 1..N:            # 外：轮次
       for pool in 启用池:   # 内：池轮转
           跑 1 代           # spawn 引擎，跑完退出（一代一进程，原架构不变）
       ★ 一轮结束 ⇒ 自动收尾（facs 落地 + 跨池审查 + 精选池）
   ★ 收到 stopAll ⇒ 跳出 ⇒ 自动收尾 ⇒ 退出
```

## 控制面 = **一个 JSON 文件**（`ai_test/_tracks/_control.json`）
前端**只读写它**（+ 必要时杀"当前那一代"的引擎），调度器**每代前重读** ⇒ 启停即时生效 ✓
```json
{ "running": true, "enabled": ["all","300","500","1000","50"], "stopped": ["500"],
  "stopAll": false, "round": 2, "rounds": 50, "curPool": "300", "curGen": 55, "phase": "mine" }
```

## ★★ 用户问题 4 的答案：**停一个池不会让收尾落空** ✓
收尾触发条件是「**没有任何池在跑**」+「**本轮有过真实进展**」，
**不是**"所有池都跑完 N 轮"✗ ⇒ 被停的池只是"不参与轮转"，**绝不阻塞收尾** ✓
（"停某池、其他池继续"时**不收尾**是对的 —— 此时别的池正在写 `docs/`，收尾会撞车 ✓）

## ★★ "立即停"安全（已核实）：池间**文件隔离** + 引擎落盘是**原子 + 代末**
`loop_engine.py:1709` 注释明写 `.tmp` + `os.replace` 是为「**或进程被杀**」这个场景加固的
⇒ 杀掉当前那一代 = 该代作废、旧状态完好、下次重跑 ✓ 且**不影响其他池** ✓
"""
import ctypes
import io
import json
import os
import subprocess
import sys
import time

from . import settings
from .sources import core, pools

RUN_TRACKS = os.path.join(settings.PROJECT_ROOT, 'tools', 'run_tracks.py')
LOGD = os.path.join(settings.PROJECT_ROOT, 'ai_test', '_tracks')
CTL_FILE = os.path.join(LOGD, '_control.json')

ROUNDS_MIN, ROUNDS_MAX = 1, 200
DEFAULT_ROUNDS = 50
GB_PER_ENGINE = 9.0          # 保守（实测 6~9 GB）
MIN_FREE_GB = 3.0


class MineError(Exception):
    def __init__(self, msg, code=400):
        super().__init__(msg)
        self.msg = msg
        self.code = code


def _now():
    import datetime as _d
    return _d.datetime.now().strftime('%Y-%m-%d %H:%M:%S')


# ---------------------------------------------------------------- 控制文件
CTL_DEFAULT = {'running': False, 'enabled': [], 'stopped': [], 'stopAll': False,
               'rounds': 0, 'round': 0, 'curPool': None, 'curGen': None,
               'phase': 'idle', 'tailAt': None, 'updated': None}


def ctl():
    d = dict(CTL_DEFAULT)
    try:
        with io.open(CTL_FILE, encoding='utf-8') as f:
            d.update(json.load(f) or {})
    except Exception:
        pass
    return d


def _write_ctl(**kw):
    d = ctl()
    d.update(kw)
    d['updated'] = _now()
    try:
        os.makedirs(LOGD, exist_ok=True)
        tmp = CTL_FILE + '.tmp'
        with io.open(tmp, 'w', encoding='utf-8') as f:
            json.dump(d, f, ensure_ascii=False, indent=1)
        os.replace(tmp, CTL_FILE)          # ★ 原子 ⇒ 调度器永远读到完整 JSON ✓
    except Exception as e:
        raise MineError('写控制文件失败: %r' % (e,), 500)
    return d


# ---------------------------------------------------------------- 资源 / 进程
def avail_gb():
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


def _alive(pid):
    try:
        r = subprocess.run(['tasklist', '/FI', 'PID eq %d' % pid, '/NH'],
                           capture_output=True, text=True, encoding='utf-8', errors='replace')
        return str(pid) in (r.stdout or '')
    except Exception:
        return None


def _procs():
    core._CACHE.pop('procs', None)
    raw = core.cached('procs', 2.0, pools.list_processes)
    return [pools.classify_proc(p) for p in raw if not p.get('err')]


def scheduler():
    """★ 找调度器进程：`run_tracks.py` 且**不含 `--no_global`**（旧"每池一进程"模式才带它）。"""
    out = []
    for p in _procs():
        if p['kind'] != 'driver':
            continue
        cmd = p.get('cmd') or ''
        if '--no_global' in cmd:
            continue                      # 旧模式（每池一进程）⇒ 不算调度器
        out.append(p)
    return out


def engines():
    return [p for p in _procs() if p['kind'] == 'engine']


def engine_of(pool):
    """当前正在跑某池的那一代引擎（用于「立即停」只杀它）✓"""
    return [p for p in engines() if pool in (p.get('pools') or [])]


# ---------------------------------------------------------------- 状态
def state():
    c = ctl()
    free = avail_gb()
    sched = scheduler()
    engs = engines()
    running_now = bool(sched) and (bool(c.get('running')) or bool(engs))
    known = list(core.POOL_KEYS)
    en = [p for p in (c.get('enabled') or known) if p in known] or known
    st = [p for p in (c.get('stopped') or []) if p in known]
    by_pool = {}
    for k in known:
        by_pool[k] = {
            'enabled': k in en,
            'stopped': k in st,
            'mining': bool(c.get('curPool') == k and engs),
            'engine': [p['pid'] for p in engs if k in (p.get('pools') or [])],
        }
    phase = c.get('phase') or 'idle'
    if not running_now and phase in ('mine',):
        phase = 'idle'                    # 调度器已死但文件没更新 ⇒ 兜底
    label = {'idle': '空闲', 'mine': '挖掘中', 'tail': '收尾审查中'}.get(phase, phase)
    cur = c.get('curPool')
    return {
        'mode': 'scheduler',              # ★ 模式标识：单调度器 + 池轮转
        'phase': phase,
        'phaseLabel': label,
        'running': running_now,
        'stopAll': bool(c.get('stopAll')),
        'schedulerPids': [p['pid'] for p in sched],
        'scheduler': [{'pid': p['pid'], 'cmd': p['cmd'][:300],
                       'memMB': p.get('memMB')} for p in sched],
        'engines': [{'pid': p['pid'], 'pools': p.get('pools'), 'memMB': p.get('memMB')} for p in engs],
        'curPool': cur, 'curGen': c.get('curGen'),
        'round': c.get('round'), 'rounds': c.get('rounds'),
        'roundText': (('第 %s 轮' % c.get('round')) if c.get('round') else None),
        'curText': (('%s · gen %s' % (cur, c.get('curGen'))) if cur else None),
        'tailAt': c.get('tailAt'),
        'updated': c.get('updated'),
        'knownPools': known,
        'enabled': en,
        'stopped': st,
        'byPool': by_pool,
        'runningPools': [k for k in known if by_pool[k]['mining']],
        'freeGB': (round(free, 1) if free is not None else None),
        'gbPerEngine': GB_PER_ENGINE,
        'memNote': ('★ 单调度器 + 池轮转 ⇒ **同一时刻只有 1 个引擎**（约 %.0f GB），'
                    '不再"每池一份内存"✗；可用 %.1f GB ✓' % (GB_PER_ENGINE, free or 0))
                   if free is not None else '',
        'defaultRounds': DEFAULT_ROUNDS,
        'roundsRange': [ROUNDS_MIN, ROUNDS_MAX],
        'script': os.path.relpath(RUN_TRACKS, settings.PROJECT_ROOT),
        'note': ('1 个调度器按轮转跑各池（每轮每池 1 代）⇒ 内存只 1 份、'
                 '★ **每轮结束自动收尾**；单独停某池只影响该池；'
                 '「一键全部停止」⇒ 自动进入收尾阶段后退出 ✓'),
    }


# ---------------------------------------------------------------- 启动
def start(pool_list, rounds=DEFAULT_ROUNDS, no_global=False):
    """启动（或调整）轮转调度器。**已在跑 ⇒ 只更新启用集合/轮数**，不重复起进程 ✓"""
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
    if no_global:
        raise MineError('v1.3.0 起为"单调度器轮转"，不再需要 `--no_global` '
                        '（收尾由调度器自动承担）⇒ 请勿指定 ✗', 400)

    sched = scheduler()
    if sched:
        # ★ 已在跑 ⇒ 只更新控制文件（启用集合、轮数、清掉 stopAll/stopped）
        _write_ctl(enabled=pool_list, stopped=[], stopAll=False, rounds=rounds, running=True)
        return {'ok': True, 'started': [], 'reused': True,
                'schedulerPids': [p['pid'] for p in sched],
                'enabled': pool_list, 'rounds': rounds,
                'note': ('调度器已在运行（PID %s）⇒ 已**就地更新**：启用池=%s、轮数=%d、'
                         '并清除「停止」标记 ✓（未重复起进程）'
                         % ([p['pid'] for p in sched], pool_list, rounds))}

    free = avail_gb()
    if free is not None and free < GB_PER_ENGINE + MIN_FREE_GB:
        raise MineError('内存不足：可用 %.1f GB，单引擎约需 %.0f GB（留 %.0f GB 余量）✗'
                        % (free, GB_PER_ENGINE, MIN_FREE_GB), 409)

    os.makedirs(LOGD, exist_ok=True)
    _write_ctl(running=True, enabled=pool_list, stopped=[], stopAll=False, rounds=rounds,
               round=0, curPool=None, curGen=None, phase='mine', tailAt=None)
    env = dict(os.environ)
    env['PYTHONIOENCODING'] = 'utf-8'
    flags = (getattr(subprocess, 'DETACHED_PROCESS', 0)
             | getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0)) if os.name == 'nt' else 0
    args = [sys.executable, RUN_TRACKS, '--pools=%s' % ','.join(pool_list),
            '--rounds=%d' % rounds]
    log = os.path.join(LOGD, '_ui_scheduler.log')
    proc = subprocess.Popen(args, cwd=settings.PROJECT_ROOT, env=env, stdout=open(log, 'ab'),
                            stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                            creationflags=flags, close_fds=True)
    time.sleep(3)
    return {'ok': True, 'started': [{'pool': ','.join(pool_list), 'pid': proc.pid,
                                     'alive': _alive(proc.pid), 'cmd': ' '.join(args[1:]),
                                     'log': os.path.relpath(log, settings.PROJECT_ROOT)}],
            'enabled': pool_list, 'rounds': rounds, 'freeGB': (round(free, 1) if free is not None else None),
            'note': ('已启动**轮转调度器**（PID %d）：启用池=%s、每池 %d 轮 ⇒ '
                     '同一时刻只 1 个引擎（内存 1 份）✓ **每轮结束自动收尾** ✓'
                     % (proc.pid, pool_list, rounds))}


# ---------------------------------------------------------------- 停止
def stop(pool=None, **kw):
    """停止：`pool=None` ⇒ **全部停**（调度器随后自动收尾并退出）；指定池 ⇒ **只停该池** ✓"""
    if pool and pool not in core.POOL_KEYS:
        raise MineError('未知池名: %s' % pool)

    if pool:
        # ★ 单独停：**只写 `stopped`**（绝不动 `enabled`）+ **杀该池当前那一代引擎** ✓
        #   ⚠ 2026-09-16 修 BUG A：原实现把 `enabled` 也剔除并重写 ⇒
        #     ① 丢失"用户本来想跑哪些池" ② 若只启 1 个池 ⇒ `enabled=[]` ⇒ **调度器直接退出** ✗
        c = ctl()
        st = sorted(set(list(c.get('stopped') or []) + [pool]))
        _write_ctl(stopped=st)
        killed = []
        for p in engine_of(pool):
            r = subprocess.run(['taskkill', '/PID', str(p['pid']), '/T', '/F'],
                               capture_output=True, text=True, encoding='utf-8', errors='replace')
            killed.append({'pid': p['pid'], 'kind': 'engine', 'pools': p.get('pools'),
                           'rc': r.returncode, 'out': (r.stdout or r.stderr or '').strip()[:160]})
        time.sleep(1)
        left = engine_of(pool)
        en = [x for x in (c.get('enabled') or core.POOL_KEYS) if x != pool]
        return {'ok': not left, 'scope': 'pool:%s' % pool, 'killed': killed,
                'stillRunning': [{'pid': p['pid'], 'kind': 'engine', 'pools': p.get('pools')} for p in left],
                'note': ('已单独停止池 **%s**：① 从轮转中移除 ② 杀掉它当前那一代（该代作废、'
                         'state 是原子写 ⇒ 不会坏数据）⇒ **其他池不受影响** ✓'
                         '%s' % (pool, '；⚠ 它本来是最后一个启用的池 ⇒ 调度器已无池可跑、'
                                       '将自行退出（若还想要它，点「启动本池」会自动重启调度器）'
                                       '✓' if not en else ''))}

    # ★ 全部停：标记 stopAll + 杀所有引擎 ⇒ **确保收尾一定发生** ✓
    #   ⚠ 2026-09-16 修 BUG C/D：
    #     · C：`stopAll` 写完**必须清掉**，否则会残留并**阻塞下次启动** ✗
    #     · D：若调度器**已不在**（例如它刚跑完最后一个池自己退了）⇒ 没人读 `stopAll`
    #          ⇒ "一键全部停 ⇒ 自动收尾"就**落空**了 ✗ ⇒ **后端兜底直接触发收尾** ✓
    _write_ctl(stopAll=True, stopped=[])
    killed = []
    for p in engines():
        r = subprocess.run(['taskkill', '/PID', str(p['pid']), '/T', '/F'],
                           capture_output=True, text=True, encoding='utf-8', errors='replace')
        killed.append({'pid': p['pid'], 'kind': 'engine', 'pools': p.get('pools'),
                       'rc': r.returncode, 'out': (r.stdout or r.stderr or '').strip()[:160]})
        time.sleep(0.4)

    sched = scheduler()
    tail = None
    if sched:
        # ★ 调度器在 ⇒ 它读到 `stopAll` 会**自己收尾后退出** ✓（清标记由它负责）
        note = ('已请求**全部停止**：当前代已杀（作废、下次重跑）⇒ 调度器将**自动收尾**'
                '（facs 落地 + 跨池审查 + 精选池）随后退出 ✓ ⚠ 收尾期间请勿再启动（会撞车）')
    else:
        # ★ 调度器不在 ⇒ 后端**兜底**触发一次收尾（否则用户的"全部停 ⇒ 自动收尾"落空）✓
        _write_ctl(stopAll=False, running=False, phase='idle', curPool=None, curGen=None)
        try:
            tail = run_global()
            note = ('已停止（无调度器在跑）⇒ **兜底触发了一次收尾审查**（PID %s）✓ '
                    '收尾完成后刷新即可看到最新精选池' % tail.get('pid'))
        except MineError as e:
            note = '已停止。收尾未触发：%s' % e.msg
    return {'ok': True, 'scope': 'all', 'killed': killed, 'stillRunning': [],
            'tail': tail, 'note': note}


def start_pool(pool):
    """★ 单独**启动/恢复**某池 —— 调度器在 ⇒ 就地恢复；不在 ⇒ **自动重启调度器** ✓

    ⚠ 2026-09-16 修 BUG B：原实现"调度器不在就 409 报错" ⇒
      用户"停掉最后一个启用的池"后（调度器随之退出）**再也点不动** ✗
      ⇒ 改为：自动重启调度器（启用集合 = 现有启用 ∪ {该池}）✓
    """
    if pool not in core.POOL_KEYS:
        raise MineError('未知池名: %s' % pool)
    c = ctl()
    st = [p for p in (c.get('stopped') or []) if p != pool]
    en = sorted(set(list(c.get('enabled') or core.POOL_KEYS) + [pool]))
    if scheduler():
        _write_ctl(stopped=st, enabled=en, stopAll=False)
        return {'ok': True, 'pool': pool, 'enabled': en, 'stopped': st, 'restarted': False,
                'note': '已把池 **%s** 重新加入轮转（下一轮就会轮到它）✓' % pool}
    # ★ 调度器不在 ⇒ 自动重启（轮数沿用上次，默认 50）
    r = start(en, int(c.get('rounds') or DEFAULT_ROUNDS))
    _write_ctl(stopped=st)
    return {'ok': True, 'pool': pool, 'enabled': en, 'stopped': st, 'restarted': True,
            'started': r.get('started'), 'note':
            ('调度器原本不在运行 ⇒ 已**自动重启**（启用池=%s，来源：上次的启用集合 + %s）✓'
             % (en, pool))}


# ---------------------------------------------------------------- 全局收尾（保留，前端已隐藏按钮）
def run_global():
    """跑**一次性全局收尾**（`--rounds=0`）。⚠ 要求当前无任何挖掘在跑。"""
    c = ctl()
    if scheduler() or engines() or (c.get('running') and (c.get('phase') == 'mine')):
        raise MineError('仍有挖掘在跑 ⇒ 拒绝收尾（收尾必须"无人写"）✗ 请先全部停止', 409)
    args = [sys.executable, RUN_TRACKS, '--pools=%s' % ','.join(core.POOL_KEYS), '--rounds=0']
    os.makedirs(LOGD, exist_ok=True)
    env = dict(os.environ)
    env['PYTHONIOENCODING'] = 'utf-8'
    flags = (getattr(subprocess, 'DETACHED_PROCESS', 0)
             | getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0)) if os.name == 'nt' else 0
    log = os.path.join(LOGD, '_ui_global.log')
    proc = subprocess.Popen(args, cwd=settings.PROJECT_ROOT, env=env, stdout=open(log, 'ab'),
                            stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                            creationflags=flags, close_fds=True)
    _write_ctl(phase='tail', tailAt=_now())
    time.sleep(2)
    return {'ok': True, 'pid': proc.pid, 'alive': _alive(proc.pid),
            'log': os.path.relpath(log, settings.PROJECT_ROOT),
            'note': '全局收尾已启动（facs 落地 + 跨池审查 + 精选池）✓'}
