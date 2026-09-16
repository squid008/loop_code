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
import re
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
GB_PER_ENGINE_SHARED = 3.0   # ★ 面板共享后的每引擎私有内存（面板不再各建一份；实测 3 并行 ≈ 8.1 GB）
MIN_FREE_GB = 3.0

# ★★★ 2026-09-16（用户之问「前端还没把并行切换加上是吧？」）：把 `run_tracks.py` **v1.4.0 就有的**
#   调度模式开关与面板共享**暴露到看板**（能力全在 CLI，缺的只是这一层）。
#   ★ 默认：**模式仍是 `rotate`**（不加参数时命令行与改造前一致）✓
#     ⚠ **面板共享**自 2026-09-16 起**默认开**（用户要求「一直默认勾、去掉勾选框」）——
#       理由：无副作用（结果逐位相同 · 载入 28.6s→1.8s · 内存更低）；缓存失效时**自动降级为 off** ✓
EXEC_MODES = ('rotate', 'parallel')
PANEL_CACHES = ('off', 'use', 'build')
PARALLEL_RANGE = (1, 6)
MEM_DEFAULT = 3.0            # 每引擎内存预算 GB（仅 parallel 用）
PANEL_CACHE_DIR = os.path.join(settings.PROJECT_ROOT, 'engine', '_panel_cache')


def panel_cache_info():
    """读面板缓存 manifest（**纯文件系统**，不需要引擎进程）⇒ 给看板显示"共享面板就绪没有"。

    ⚠ 只校验**来源数据指纹**（size+mtime_ns）；**构造代码指纹**要引擎才算
      ⇒ 这里不冒充"完全有效"，真校验由引擎在 `--panel_cache=use` 时自己做强校验（过期即报错）✓
    """
    p = os.path.join(PANEL_CACHE_DIR, 'manifest.json')
    if not os.path.isfile(p):
        return {'exists': False,
                'hint': '未构建，请跑 python tools/build_panel_cache.py（约 1~2 分钟，与池无关、所有池共用）'}
    try:
        with io.open(p, encoding='utf-8') as f:
            man = json.load(f)
        bad = []
        for fn, fp in (man.get('src') or {}).items():
            try:
                st = os.stat(os.path.join(settings.PROJECT_ROOT, 'engine', fn))
                cur = [int(st.st_size), int(st.st_mtime_ns)]
            except OSError:
                cur = None
            if fp != cur:
                bad.append(fn)
        return {'exists': True, 'gb': man.get('total_gb'), 'builtAt': man.get('created'),
                'fields': len(man.get('fields') or {}), 'sourceOk': not bad, 'staleSources': bad,
                'codeSha': man.get('code_sha1'),
                'hint': ('数据指纹已变（%s），缓存已过期，要重建否则引擎会拒绝加载'
                         % ', '.join(bad)) if bad else
                        '数据指纹一致（构造代码指纹由引擎在启动时校验）'}
    except Exception as e:
        return {'exists': False, 'err': repr(e)}


def _flag(cmd, name, cast=str, default=None):
    """从命令行里取 `--name=value`（**以真实进程的命令行为准** —— 那才是"现在到底怎么跑的"）。"""
    m = re.search(r'--%s=(\S+)' % re.escape(name), cmd or '')
    if not m:
        return default
    try:
        return cast(m.group(1))
    except Exception:
        return default

# ★★★ 2026-09-16：起子进程**一律不弹黑窗**（用户要求「启动不要开 python 窗口，审查之类的都后台静默」）。
#   ⚠ 为什么用 `CREATE_NO_WINDOW` 而**不是 `DETACHED_PROCESS`**（这个区别很关键）：
#     · `DETACHED_PROCESS` ⇒ 子进程**没有控制台** ⇒ 它再 spawn 孙子进程时，
#       Windows 会**给孙子新建一个控制台窗口** ⇒ **弹黑窗** ✗（这正是"每代/收尾都弹窗"的来源）
#     · `CREATE_NO_WINDOW` ⇒ 子进程**有控制台但隐藏** ⇒ **孙进程默认继承它** ⇒ 全链路静默 ✓✓
#   ⇒ 所以「隐藏控制台」比「去掉控制台」更能"传染"到整条进程链 ✓
_NO_WIN = (getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000)
           | getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0)) if os.name == 'nt' else 0


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
                           capture_output=True, text=True, encoding='utf-8', errors='replace',
                           creationflags=_NO_WIN)
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
        # ★★★★ 2026-09-16 修 BUG I：`mining` 必须**以"真的有它的引擎在跑"为准**，
        #   不能只看调度器的 `curPool` —— 否则会出现
        #   `{stopped: True, mining: True, engine: []}` 这种**自相矛盾**的状态
        #   ⇒ 前端「启动本池」「停止本池」**两个按钮同时可点** ✗（用户实测）
        #   （根因在 `classify_proc` 把 `all` 的引擎归属丢了 —— 已在 `pools.py` 修）
        _eng = [p['pid'] for p in engs if k in (p.get('pools') or [])]
        by_pool[k] = {
            'enabled': k in en,
            'stopped': k in st,
            'mining': bool(_eng),                    # ★ 有引擎 = 正在跑 ✓
            'engine': _eng,
        }
    phase = c.get('phase') or 'idle'
    if not running_now and phase in ('mine',):
        phase = 'idle'                    # 调度器已死但文件没更新 ⇒ 兜底
    # ★★ 2026-09-16（用户实测："我把池都停了，它还显示挖掘中，但 0/5 在跑"）：
    #   调度器**还活着**但**没有任何引擎在跑**、且**没有池可跑**（启用池全在 stopped 里）⇒
    #   这不是"挖掘中"，是**空转待命**（并行模式下它要等各个引擎退出、再复位控制文件）
    #   ⇒ 明确标成「待命」，别让状态说谎 ✗（另：**收尾审查**只在"本轮有进展"时才跑，
    #     5 个引擎全被中途杀掉 ⇒ `dirty=False` ⇒ **不会**收尾 ✓ 见 `_ui_scheduler.log`）
    if phase == 'mine' and sched and not engs:
        _runnable = [p for p in en if p not in st]
        if not _runnable:
            phase = 'idle'
    label = {'idle': '空闲', 'mine': '挖掘中', 'tail': '收尾审查中'}.get(phase, phase)
    cur = c.get('curPool')
    # ---- ★★★ 调度模式 / 内存设置：**以真实进程命令行为准**（"现在到底怎么跑的"只有它有发言权）----
    _cmd = ((sched[0].get('cmd') if sched else (engs[0].get('cmd') if engs else '')) or '')
    _mode = _flag(_cmd, 'exec_mode', str, c.get('execMode') or 'parallel')
    _mp = _flag(_cmd, 'max_parallel', int, c.get('maxParallel') or 3)
    _mpe = _flag(_cmd, 'mem_per_engine', float, c.get('memPerEngine') or MEM_DEFAULT)
    _pc = _flag(_cmd, 'panel_cache', str, c.get('panelCache') or 'off')
    # ★ 并行上限是不是"自动"的（看板没显式指定 ⇒ 调度器按内存动态重算）⇒ 界面上要标注清楚 ✓
    _auto = str(_flag(_cmd, 'auto_parallel', str, c.get('autoParallel') or '') or ''
                ).strip().lower() in ('1', 'true', 'yes', 'on')
    _pcinfo = panel_cache_info()
    if free is None:
        _mnote = ''
    elif _mode == 'parallel':
        # ★ 2026-09-16（用户要求"文案去掉引号/机味符号"）：这些串**原样显示**在看板上
        #   ⇒ 一律自然语言 + 普通标点（不许 `★ ⚠ ⇒ ✓ ✗ **`）✓ 守门见 `tools/_test_ui_quotes.py`
        _mnote = ('并行模式：同时最多 %d 个引擎%s（跑完一个立刻补一个，其余排队）· 面板共享=%s，%s'
                  '；可用 %.1f GB' % (
                      _mp, '（自动：按可用内存与启用池数动态定，'
                           '你随时点启动本池加池都会立刻开起来）' if _auto else '', _pc,
                      ('4.6 GB 面板只占一份物理页，每进程私有约 %.1f GB' % _mpe)
                      if _pc != 'off' else
                      '面板缓存关着，每个引擎各建一份 4.42 GB 面板（N 份），强烈建议开面板共享',
                      free))
    else:
        _mnote = ('单调度器 + 池轮转：同一时刻只有 1 个引擎（约 %.0f GB）%s；可用 %.1f GB' % (
            GB_PER_ENGINE,
            '；面板共享=on，载入 28.6s→1.8s、内存更低' if _pc != 'off' else '', free))
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
        # ★★★ 调度模式 / 内存设置（2026-09-16）：**以真实进程的命令行为准**（那才是"现在到底怎么跑的"）
        'execMode': _mode, 'maxParallel': _mp, 'memPerEngine': _mpe,         'panelCache': _pc,
        'autoParallel': _auto,
        'panelCacheInfo': _pcinfo,
        'execModes': list(EXEC_MODES),
        'parallelRange': list(PARALLEL_RANGE),
        'memDefault': MEM_DEFAULT,
        'memNote': _mnote,
        'defaultRounds': DEFAULT_ROUNDS,
        'roundsRange': [ROUNDS_MIN, ROUNDS_MAX],
        'script': os.path.relpath(RUN_TRACKS, settings.PROJECT_ROOT),
        'note': ('1 个调度器按轮转跑各池（每轮每池 1 代），内存只 1 份、'
                 '每轮结束自动收尾；单独停某池只影响该池；'
                 '一键全部停止会自动进入收尾阶段后退出'),
    }


# ---------------------------------------------------------------- 启动
def start(pool_list, rounds=DEFAULT_ROUNDS, reset_stopped=True,
          exec_mode=None, max_parallel=None, mem_per_engine=None, panel_cache=None):
    """启动（或调整）调度器。**已在跑 ⇒ 只更新启用集合/轮数**，不重复起进程 ✓

    :param reset_stopped: ★★★ 2026-09-16 新增（修用户报的"启动一个池，**其它池的剔除全被取消**"）：
        · `True`（默认，**"一键启动全部"用**）⇒ **清空 `stopped`** ✓
          —— 用户的意图是"**让这些池全部参与**"，所以清掉剔除是**对的** ✓
        · `False`（**`start_pool()` 内部重启时用**）⇒ **保留 `stopped`** ✓
          —— 否则"启动 500"会把用户刚停掉的 all/1000 **又拉回来** ✗✗
        ⚠ 原实现**无条件 `stopped=[]`** ⇒ 所以 `start_pool` 里"先 start() 再写 stopped"
          会被 start() 覆盖**一半**，且**清掉了其它池的剔除** ✗
    :param exec_mode / max_parallel / mem_per_engine / panel_cache: ★★★ 2026-09-16 新增
        —— 把 `run_tracks.py`（**v1.4.0 就有**）的「调度模式 + 面板共享」暴露到看板。
        · 传 `None` ⇒ **沿用 `_control.json` 里上次的设置**（`start_pool()` 自动重启走这条 ⇒
          不会把用户选的并行模式**悄悄退回轮转** ✗）；文件里也没有 ⇒ 历史默认 `rotate`/`off` ✓
        · ⚠ **这四个都不能"热改"**（它们是**子进程启动参数**）⇒ 已在跑且与请求不同 ⇒ **409 拒绝**
          并提示"先全部停止"（**绝不静默 no-op** —— 那会让用户以为切了模式其实没切 ✗）
        · 内存护栏按模式算：parallel ⇒ `max_parallel × 每引擎预算`；面板缓存关着时**按整份面板抬价** ✓
    """
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

    # ---- ★ 调度模式参数：校验 + 缺省继承（`None` ⇒ 沿用上次设置）----
    c0 = ctl()
    # ★ 2026-09-16（用户："干脆把轮转/并行按钮都隐藏了，先直接默认并行吧"）：
    #   看板侧**默认 = 并行**（`rotate` 仍保留在 CLI / API 里，随时可切回来）✓
    exec_mode = (exec_mode if exec_mode is not None else c0.get('execMode') or 'parallel')
    panel_cache = (panel_cache if panel_cache is not None else c0.get('panelCache') or 'use')
    exec_mode = str(exec_mode).strip().lower()
    panel_cache = str(panel_cache).strip().lower()
    mem_per_engine = float(mem_per_engine if mem_per_engine is not None
                           else (c0.get('memPerEngine') or MEM_DEFAULT))
    _mp_explicit = max_parallel is not None
    max_parallel = int(max_parallel) if _mp_explicit else 0     # 0 = 待自动算（见下）
    if exec_mode not in EXEC_MODES:
        raise MineError('调度模式只能是 %s（收到 %s）' % (list(EXEC_MODES), exec_mode))
    if panel_cache not in PANEL_CACHES:
        raise MineError('面板缓存只能是 %s（收到 %s）' % (list(PANEL_CACHES), panel_cache))
    if _mp_explicit and not (PARALLEL_RANGE[0] <= max_parallel <= PARALLEL_RANGE[1]):
        raise MineError('并行上限要在 %d~%d 之间（收到 %s）' % (PARALLEL_RANGE[0], PARALLEL_RANGE[1],
                                                          max_parallel))
    if not (0.5 <= mem_per_engine <= 32.0):
        raise MineError('每引擎预算要在 0.5~32 GB 之间（收到 %s）' % mem_per_engine)
    # ---- ★★ 面板共享：**缓存不可用就自动降级为 off**（而不是让启动失败）----
    #   2026-09-16 用户要求：「一直默认勾，没副作用的话干脆不要这个勾选框」⇒ 看板固定发 `use`：
    #     · 缓存**有效** ⇒ 真的共享（载入 28.6s→1.8s、内存更低；结果**逐位相同**，见 _test_panel_cache）
    #     · 缓存**过期/缺失** ⇒ **自动关掉共享**（降到"更慢但一定正确"的路径）+ 在 note 里说清楚 ✓
    #   ⚠ 这是"降级到安全路径"、不是"用旧数据算新结果" ⇒ 不违反"绝不静默污染" ✓（但必须**明确告知**）
    _pcinfo = panel_cache_info()
    _pc_degraded = False
    if panel_cache == 'use' and (not _pcinfo.get('exists') or not _pcinfo.get('sourceOk')):
        _pc_degraded = True
        panel_cache = 'off'

    # ---- ★★ 并行上限：**没传就按可用内存自动算**（用户要求：「一键启动就全部五池启动 +
     #   万一会爆内存就自动少一个池」）----
    #   `K = floor((可用 - 余量) / 每引擎)`，再夹到 `1 ~ 池数` ⇒ **能开几个开几个** ✓
    #   · 面板共享开着 ⇒ 每引擎按 3 GB（共享的那 4.56 GB 只算一份）✓ 关着 ⇒ 按 9 GB（各建一份）
    #   · 还有一道**运行期**护栏在 `parallel_runner`（可用内存 < 预算就**排队等**，宁慢不炸）✓
    free0 = avail_gb()
    _mp_auto = False
    if exec_mode == 'parallel' and not _mp_explicit:
        _eff = GB_PER_ENGINE_SHARED if panel_cache != 'off' else GB_PER_ENGINE
        if free0 is None:
            max_parallel = min(len(pool_list), 3)
        else:
            max_parallel = int(max(1, min(len(pool_list), (free0 - MIN_FREE_GB) // _eff)))
        _mp_auto = True

    sched = scheduler()
    if sched:
        # ★★ 已在跑：**启动参数不能热改** ⇒ 与真实命令行不一致就 409（不静默 no-op）✗
        _cmd = ((sched[0].get('cmd') if sched else '') or '')
        _cur = dict(execMode=_flag(_cmd, 'exec_mode', str, c0.get('execMode') or 'rotate'),
                    maxParallel=_flag(_cmd, 'max_parallel', int, c0.get('maxParallel') or 3),
                    memPerEngine=_flag(_cmd, 'mem_per_engine', float,
                                       c0.get('memPerEngine') or MEM_DEFAULT),
                    panelCache=_flag(_cmd, 'panel_cache', str, c0.get('panelCache') or 'off'))
        _want = dict(execMode=exec_mode, maxParallel=max_parallel,
                     memPerEngine=mem_per_engine, panelCache=panel_cache)
        # ★ 只比"模式类"参数：`execMode` / `panelCache`。
        #   并行数是**每次按内存自动算**的（换个时刻算出来就不一样）⇒ 拿它做"热改"比较会**误报 409** ✗
        _d = [k for k in ('execMode', 'panelCache') if _want[k] != _cur[k]]
        if _d:
            raise MineError(
                '调度器已在运行（当前 %s）；而 %s 是启动参数、不能热改。\n'
                ' 想换：先点全部停止，再用新设置启动'
                % (' '.join('%s=%s' % (k, _cur[k]) for k in _want),
                   ' / '.join('%s=%s' % (k, _want[k]) for k in _d)), 409)
        # 一致 ⇒ 只更新控制文件（启用集合、轮数、清 stopAll；stopped 视 reset_stopped 而定）✓
        kw = dict(enabled=pool_list, stopAll=False, rounds=rounds, running=True,
                  execMode=exec_mode, maxParallel=max_parallel,
                  memPerEngine=mem_per_engine, panelCache=panel_cache)
        if reset_stopped:
            kw['stopped'] = []
        _write_ctl(**kw)
        return {'ok': True, 'started': [], 'reused': True,
                'schedulerPids': [p['pid'] for p in sched],
                'enabled': pool_list, 'rounds': rounds,
                'resetStopped': reset_stopped,
                'execMode': exec_mode, 'maxParallel': max_parallel,
                'memPerEngine': mem_per_engine, 'panelCache': panel_cache,
                'note': ('调度器已在运行（PID %s），已就地更新：启用池=%s、轮数=%d%s（未重复起进程）'
                         % ([p['pid'] for p in sched], pool_list, rounds,
                            '、并清除停止标记' if reset_stopped else '、保留已有的停止标记'))}

    # ---- 内存护栏（**按模式 + 面板共享**算）----
    # ★ 面板共享开着时，4.42 GB 面板**只占一份物理页**，每进程私有只剩 L1 子面板+缓存 ≈ 3 GB
    #   ⇒ 护栏必须分档，否则"面板共享"这个开关**永远解锁不了低内存启动**（白做）✗
    free = free0                      # ★ 复用上面那次读数（同一次启动内一致，别读两次）
    _eff1 = GB_PER_ENGINE if panel_cache == 'off' else GB_PER_ENGINE_SHARED
    if exec_mode == 'parallel':
        _eff = _eff1 if panel_cache == 'off' else max(mem_per_engine, GB_PER_ENGINE_SHARED)
        _need = max_parallel * _eff + MIN_FREE_GB
        _hint = ('（%s，每引擎按 %.1f GB 算）' % (
            '面板缓存关着、每个引擎各建一份 4.42 GB 面板' if panel_cache == 'off'
            else '面板共享=on', _eff))
    else:
        _need = _eff1 + MIN_FREE_GB
        _hint = ('（面板共享=on，按 %.1f GB 算）' % GB_PER_ENGINE_SHARED
                 if panel_cache != 'off' else '')
    if free is not None and free < _need:
        raise MineError('内存不足：可用 %.1f GB，本次需要约 %.1f GB%s'
                        % (free, _need, _hint), 409)

    os.makedirs(LOGD, exist_ok=True)
    kw = dict(running=True, enabled=pool_list, stopAll=False, rounds=rounds,
              round=0, curPool=None, curGen=None, phase='mine', tailAt=None,
              # ★ 记下本次启动参数（`start_pool()` 自动重启时**照抄**，不会退回轮转 ✗）
              execMode=exec_mode, maxParallel=max_parallel,
              memPerEngine=mem_per_engine, panelCache=panel_cache,
              autoParallel=('1' if _mp_auto else ''))
    if reset_stopped:
        kw['stopped'] = []
    _write_ctl(**kw)
    env = dict(os.environ)
    env['PYTHONIOENCODING'] = 'utf-8'
    flags = _NO_WIN
    args = [sys.executable, RUN_TRACKS, '--pools=%s' % ','.join(pool_list),
            '--rounds=%d' % rounds]
    # ★★ 只在**非默认**时追加 ⇒ 默认命令与改造前**逐字一致**（旧行为一行不改 ✓）
    if exec_mode != 'rotate':
        args += ['--exec_mode=%s' % exec_mode, '--max_parallel=%d' % max_parallel,
                 '--mem_per_engine=%.1f' % mem_per_engine]
        # ★★★ 2026-09-16：`_mp_auto`（看板没显式指定并行数）⇒ 让调度器**动态重算上限**
        #   —— 否则并行数在**启动那一刻就按池数算死**，后来点「启动本池」加的池**永远只能排队** ✗
        #   （用户实测："点一个启动，再点一个池子，怎么是加入轮转而不是并行？"）
        if _mp_auto:
            args.append('--auto_parallel=1')
    if panel_cache != 'off':
        args.append('--panel_cache=%s' % panel_cache)
    log = os.path.join(LOGD, '_ui_scheduler.log')
    proc = subprocess.Popen(args, cwd=settings.PROJECT_ROOT, env=env, stdout=open(log, 'ab'),
                            stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                            creationflags=flags, close_fds=True)
    time.sleep(3)
    _extra = []
    if exec_mode == 'parallel' and _mp_auto:
        _extra.append('并行数按可用内存自动定为 %d（可用 %.1f GB / 每引擎按 %.0f GB 估）'
                      % (max_parallel, free or 0,
                         GB_PER_ENGINE_SHARED if panel_cache != 'off' else GB_PER_ENGINE))
    if _pc_degraded:
        _extra.append('面板缓存不可用（%s），本次自动关掉面板共享（载入慢 ~27s、结果不变）'
                      % ((_pcinfo.get('hint') or _pcinfo.get('err') or '未知原因')[:70]))
    return {'ok': True, 'started': [{'pool': ','.join(pool_list), 'pid': proc.pid,
                                     'alive': _alive(proc.pid), 'cmd': ' '.join(args[1:]),
                                     'log': os.path.relpath(log, settings.PROJECT_ROOT)}],
            'enabled': pool_list, 'rounds': rounds, 'resetStopped': reset_stopped,
            'execMode': exec_mode, 'maxParallel': max_parallel,
            'memPerEngine': mem_per_engine, 'panelCache': panel_cache,
            'freeGB': (round(free, 1) if free is not None else None),
            'note': ('已启动%s（PID %d）：启用池=%s、每池 %d 轮，%s每轮结束自动收尾'
                     % ('并行调度器' if exec_mode == 'parallel' else '轮转调度器',
                        proc.pid, pool_list, rounds,
                        ('同时最多 %d 个引擎（其余排队）· 面板共享=%s '
                         % (max_parallel, panel_cache)) if exec_mode == 'parallel'
                        else '同一时刻只 1 个引擎（内存 1 份）· 面板共享=%s ' % panel_cache)
                     + ('；' + '；'.join(_extra) if _extra else ''))}


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
        # ★★★★ 2026-09-16 兜底（用户实测"停止了全A，它还在跑"）：
        #   若控制文件里 **`curPool == pool`**（调度器正在跑它），
        #   那就把**当前这个引擎**也算进来一起杀 —— **不依赖命令行归属解析** ✓
        #   为什么需要：命令行归属可能因历史原因失配（如旧进程没传 `--mine_pool`），
        #   而"调度器正在跑哪个池"是**确定的事实** ⇒ 用它兜底最可靠 ✓
        _targets = list(engine_of(pool))
        if c.get('curPool') == pool:
            _seen = {x['pid'] for x in _targets}
            _targets += [x for x in engines() if x['pid'] not in _seen]
        _was_mining = bool(_targets)          # ★ 它当时是否在跑（以“有无目标进程”为准）✓
        for p in _targets:
            r = subprocess.run(['taskkill', '/PID', str(p['pid']), '/T', '/F'],
                               capture_output=True, text=True, encoding='utf-8', errors='replace',
                               creationflags=_NO_WIN)
            killed.append({'pid': p['pid'], 'kind': 'engine', 'pools': p.get('pools'),
                           'rc': r.returncode, 'out': (r.stdout or r.stderr or '').strip()[:160]})
        time.sleep(1)
        # ★ 残留检查同样要兜底：归属解析不到、但调度器仍指向该池 ⇒ 也算"没杀干净" ✓
        left = list(engine_of(pool))
        if ctl().get('curPool') == pool:
            left += [x for x in engines() if x['pid'] not in {y['pid'] for y in left}]
        en = [x for x in (c.get('enabled') or core.POOL_KEYS) if x != pool]
        # ★ 文案按"它当时是否在跑"区分 —— 没在跑却说"杀掉了当前那一代"会误导 ✗
        _how = ('从轮转中移除，并结束它当前那一代（该代作废，下次重跑；state 是原子写，不会坏数据）'
                if _was_mining else
                '从轮转中移除（它当前没在跑，所以只影响后续轮次）')
        return {'ok': not left, 'scope': 'pool:%s' % pool, 'killed': killed,
                'stillRunning': [{'pid': p['pid'], 'kind': 'engine', 'pools': p.get('pools')} for p in left],
                'note': ('已停止池 %s：%s，其他池不受影响'
                         '%s' % (pool, _how, '；注意它本来是最后一个启用的池，调度器已无池可跑、'
                                              '将自行退出（若还想要它，点启动本池会自动重启调度器）'
                                              if not en else ''))}

    # ★ 全部停：标记 stopAll + 杀所有引擎 ⇒ **确保收尾一定发生** ✓
    #   ⚠ 2026-09-16 修 BUG C/D：
    #     · C：`stopAll` 写完**必须清掉**，否则会残留并**阻塞下次启动** ✗
    #     · D：若调度器**已不在**（例如它刚跑完最后一个池自己退了）⇒ 没人读 `stopAll`
    #          ⇒ "一键全部停 ⇒ 自动收尾"就**落空**了 ✗ ⇒ **后端兜底直接触发收尾** ✓
    # ★★ 只设 `stopAll`，**不动 `stopped`** —— 否则"全部停止 → 再启动"会**丢掉用户的剔除配置** ✗
    #   （"一键启动全部"时若想重置，由 `start(reset_stopped=True)` 显式做 ✓）
    _write_ctl(stopAll=True)
    killed = []
    for p in engines():
        r = subprocess.run(['taskkill', '/PID', str(p['pid']), '/T', '/F'],
                           capture_output=True, text=True, encoding='utf-8', errors='replace',
                           creationflags=_NO_WIN)
        killed.append({'pid': p['pid'], 'kind': 'engine', 'pools': p.get('pools'),
                       'rc': r.returncode, 'out': (r.stdout or r.stderr or '').strip()[:160]})
        time.sleep(0.4)

    sched = scheduler()
    tail = None
    if sched:
        # ★ 调度器在 ⇒ 它读到 `stopAll` 会**自己收尾后退出** ✓（清标记由它负责）
        note = ('已请求全部停止：当前代已杀（作废、下次重跑），调度器将自动收尾'
                '（facs 落地 + 跨池审查 + 精选池）随后退出。收尾期间请勿再启动（会撞车）')
    else:
        # ★ 调度器不在 ⇒ 后端**兜底**触发一次收尾（否则用户的"全部停 ⇒ 自动收尾"落空）✓
        _write_ctl(stopAll=False, running=False, phase='idle', curPool=None, curGen=None)
        try:
            tail = run_global()
            note = ('已停止（无调度器在跑），兜底触发了一次收尾审查（PID %s）'
                    '，收尾完成后刷新即可看到最新精选池' % tail.get('pid'))
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
    # ★★★ 只动**这一个池**：把它从 `stopped` 移除、加入 `enabled`；
    #     ⚠ **绝不碰其它池的 `stopped`**（否则"启动 500"会把刚停的 all/1000 又拉回来 ✗）
    st = [p for p in (c.get('stopped') or []) if p != pool]
    en = sorted(set(list(c.get('enabled') or core.POOL_KEYS) + [pool]))
    if scheduler():
        _write_ctl(stopped=st, enabled=en, stopAll=False)
        return {'ok': True, 'pool': pool, 'enabled': en, 'stopped': st, 'restarted': False,
                # ★ 2026-09-16：并行模式下**运行期动态加入** ⇒ 提示要分模式（别让人以为要等下一轮 ✗）
                'note': ('已把池 %s 加入%s（%s）；其它池的停止状态保持不变'
                         % (pool, '并行' if (c.get('execMode') == 'parallel') else '轮转',
                            '马上会起一个引擎，不用等下一轮' if (c.get('execMode') == 'parallel')
                            else '下一轮就轮到它')),
                'merged': True}
    # ★ 调度器不在 ⇒ 自动重启。⚠ **必须 `reset_stopped=False`** ——
    #   否则 `start()` 默认会 `stopped=[]`，把用户的剔除**全清掉** ✗（用户实测的 BUG）
    # ★★ 2026-09-16（用户："我不一键开启所有池，我挨个池子点启动"）：
    #   调度器不在时**只启动这一个池**（`enabled = [pool]`）—— 原实现拿"控制文件里遗留的 enabled
    #   集合"去重启 ⇒ 点一个池会把上次那一堆**全拉起来** ✗（与"挨个点"的预期相反）
    #   想全部参与 ⇒ 用「一键启动全部」（它走 `start(reset_stopped=True)`）✓
    rounds = int(c.get('rounds') or DEFAULT_ROUNDS)
    en = [pool]
    r = start(en, rounds, reset_stopped=False)
    _write_ctl(stopped=st, enabled=en)      # ★ 重启后把“只移除该池”的 stopped 写回 ✓
    return {'ok': True, 'pool': pool, 'enabled': en, 'stopped': st, 'restarted': True,
            'started': r.get('started'), 'note':
            ('调度器原本不在运行，已自动重启（轮数沿用 %d）：启用池=%s；'
             '池 %s 已加入轮转，其它池的停止状态保持不变' % (rounds, en, pool))}


# ---------------------------------------------------------------- 全局收尾（保留，前端已隐藏按钮）
def run_global():
    """跑**一次性全局收尾**（`--rounds=0`）。⚠ 要求当前无任何挖掘在跑。"""
    c = ctl()
    if scheduler() or engines() or (c.get('running') and (c.get('phase') == 'mine')):
        raise MineError('仍有挖掘在跑，拒绝收尾（收尾要求无人写），请先全部停止', 409)
    args = [sys.executable, RUN_TRACKS, '--pools=%s' % ','.join(core.POOL_KEYS), '--rounds=0']
    os.makedirs(LOGD, exist_ok=True)
    env = dict(os.environ)
    env['PYTHONIOENCODING'] = 'utf-8'
    flags = _NO_WIN
    log = os.path.join(LOGD, '_ui_global.log')
    proc = subprocess.Popen(args, cwd=settings.PROJECT_ROOT, env=env, stdout=open(log, 'ab'),
                            stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                            creationflags=flags, close_fds=True)
    _write_ctl(phase='tail', tailAt=_now())
    time.sleep(2)
    return {'ok': True, 'pid': proc.pid, 'alive': _alive(proc.pid),
            'log': os.path.relpath(log, settings.PROJECT_ROOT),
            'note': '全局收尾已启动（facs 落地 + 跨池审查 + 精选池）'}
