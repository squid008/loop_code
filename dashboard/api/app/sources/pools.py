# -*- coding: utf-8 -*-
"""池运行状态：**是否在跑**（进程）· **跑多少轮**（journal 代数 + archive 行数）· 库规模（state）。

★ 三路证据交叉，避免单点误判（用户 2026-09-15：「我要能看到**当前几个池子是不是在跑，跑多少轮了**」）：
  ① **进程**：`loop_engine.exe --mine_pool=<池>` / `run_tracks.py`（多池驱动）⇒ 权威"在跑"
  ② **journal 代数**：`docs/loop_journal[_<池>].md` 的「## 第 N 代」块数 ⇒ "跑过多少代"
  ③ **state**：`engine/loop_state[_<池>].pkl` 的 `bank`/`n_tested` ⇒ 库规模与已测候选数
  ④ **archive csv**：`docs/loop_archive[_<池>].csv` 行数 ⇒ L2 候选流水
"""
import json
import os
import re
import subprocess
import sys
import time

from . import core
from .. import settings

PS_PROCS = (
    "Get-CimInstance Win32_Process -Filter \"Name like 'python%'\" | "
    # ★★★ 2026-09-15 修【真 BUG】：原过滤是 `CommandLine -match 'loop_code'`
    #   ⇒ 而实际命令行是 `python.exe tools\run_tracks.py ...` / `... --mine_pool=300`
    #     —— **都不含 `loop_code`**（那只是工作目录，不在命令行里）✗
    #   ⇒ 结果：引擎明明在跑，看板却报 `anyRunning=False`（实测 21:52 复现）✗✗
    #   ⇒ 改为按**脚本名**匹配（这是命令行里真实存在的东西）✓
    "Where-Object { $_.CommandLine -match 'loop_engine|run_tracks|loop_watch' } | "
    "ForEach-Object { [PSCustomObject]@{ pid=$_.ProcessId; "
    "cmd=$_.CommandLine; start=$_.CreationDate.ToString('yyyy-MM-dd HH:mm:ss'); "
    "mem=[math]::Round($_.WorkingSetSize/1MB,0) } } | ConvertTo-Json -Compress -Depth 3"
)

# ★★★★ 2026-09-16 修 BUG H：**必须加"参数边界"断言** `(?<![\w-])`。
#   原写法 `--pools[= ]` 会**误匹配 `--inject_pools=300,500,1000,50`**（它里面也含 `pools=`）✗
#   ⇒ 后果（用户实测）：
#     · `all` 池的引擎命令行含 `--inject_pools=300,500,1000,50`
#       ⇒ 被解析成"这个进程在跑 300/500/1000/50 四个池" ✗✗
#     ⇒ 于是 **`byPool` 里同一个 PID 出现在 4 个池**、**停 300 会误杀 all 的引擎**、
#       **「在跑的池」计数虚高（显示 5 个）** ✗
#   ⇒ 修：要求 `--pools` 前面**不是字母/下划线/横线**（即它是独立参数）✓
#   同理 `--mine_pool` 也加（避免将来出现 `--xxx_mine_pool`）✓
_MINE_POOL_RE = re.compile(r'(?<![\w-])--mine_pool[= ]([A-Za-z0-9,]+)')
_POOLS_RE = re.compile(r'(?<![\w-])--pools[= ]([A-Za-z0-9,]+)')


def list_processes():
    """列出与本项目相关的 python 进程（只读；PowerShell CIM）。"""
    try:
        # ★★★ 2026-09-16：**必须**隐藏窗口 —— 本函数由看板**每 10 秒**调用一次，
        #   若 `powershell` 弹出控制台，就会**一直闪黑窗** ✗（用户要求"后台静默"）
        out = subprocess.run(['powershell', '-NoProfile', '-Command', PS_PROCS],
                             capture_output=True, timeout=25,
                             creationflags=(getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000)
                                            if os.name == 'nt' else 0))
        s = (out.stdout or b'').decode('utf-8', 'replace').strip()
        if not s:
            return []
        rows = json.loads(s)
        return rows if isinstance(rows, list) else [rows]
    except Exception as e:
        return [{'err': repr(e)}]


def classify_proc(p):
    """给进程打标签：driver（run_tracks）/ engine（单池）/ watcher（loop_watch）/ other。"""
    cmd = (p.get('cmd') or '').replace('/', '\\')
    base = os.path.basename(cmd.split('"')[1] if cmd.startswith('"') else
                            (cmd.split(' ')[0] if ' ' in cmd else cmd)).lower()
    if 'run_tracks' in cmd:
        kind = 'driver'
    elif 'loop_engine' in cmd:
        kind = 'engine'
    elif 'loop_watch' in cmd:
        kind = 'watcher'
    else:
        kind = 'other'

    # ★★★★★ 2026-09-16 修 BUG（用户实测："停了全A还显示在跑 5 池"）：
    #   **归属必须按 `kind` 分开解析 —— 引擎【只认 `--mine_pool`，绝不 fallback 到 `--pools`】** ✗
    #
    #   为什么（**这是真凶**）：`run_tracks.py` 给引擎透传的固定参数组 `extra` 里
    #   **硬编码了 `--pools=300,500,1000`**（配合 `--pool_obs`，"额外算这几个池的指标"，
    #   用于给因子打池内标签）—— ★ 它**不代表"这个引擎在跑那几个池"** ✗
    #   而原实现"先找 `--mine_pool`，没有就退到 `--pools`" ⇒
    #     · `all` 池的引擎**当时没传 `--mine_pool`**（BUG G，已在 `run_tracks.py` 修）
    #       ⇒ 退到 `--pools=300,500,1000` ⇒ **被当成"在跑 300/500/1000"** ✗✗
    #     · 于是：`stop('all')` 找不到它的引擎 ⇒ **杀不掉，用户以为操作无效** ✗
    #             `byPool` 里同一个 PID 出现在 3 个池 ⇒ **「在跑的池」虚高** ✗
    #   ⇒ 修：**driver 用 `--pools=`（它确实用）；engine/watcher 只用 `--mine_pool=`** ✓
    #     （配合 BUG G 的修复：所有池的引擎都会带 `--mine_pool` ✓）
    pools = []
    if kind == 'driver':
        m2 = _POOLS_RE.search(cmd)
        if m2:
            pools = [x for x in m2.group(1).split(',') if x]
    else:
        m = _MINE_POOL_RE.search(cmd)
        if m:
            pools = [x for x in m.group(1).split(',') if x]
    return {'pid': p.get('pid'), 'kind': kind, 'script': base,
            'pools': pools, 'start': p.get('start'), 'memMB': p.get('mem'),
            'cmd': (p.get('cmd') or '')[:400]}


def pool_status(pool, procs):
    """单池的完整状态。"""
    st = core.load_state(pool)
    gens, jpath = core.journal_gens(pool)
    apath = core.docs_path('loop_archive%s.csv' % core.suffix(pool))
    head, rows = core.read_csv_rows(apath)
    passed = 0
    if 'passed' in head:
        i = head.index('passed')
        passed = sum(1 for r in rows if len(r) > i and str(r[i]).strip().lower() in ('1', 'true', 'yes'))
    gen_col = head.index('gen') if 'gen' in head else None

    # ★★★★★ 2026-09-16 修 BUG J（用户报："我点了停止全A池，怎么顶上在跑的池还是 5/5"）：
    #   **"在跑的池" 必须只认「该池真的有 engine 在跑」** ✓
    #
    #   原实现有两处错 ✗：
    #     ① `not pr['pools']` 兜底 ⇒ "解析不到池 ⇒ 就当它跑遍所有池"
    #        ⇒ 旧引擎（命令行没 `--mine_pool`）会让**5 个池全部显示在跑** ✗
    #     ② `driver`（调度器）也算 ⇒ 它的命令行是 `--pools=all,300,500,1000,50`
    #        ⇒ **5 个池全部命中** ✗ —— 但它只是"**管这 5 个池**"，**不代表此刻都在跑** ✗
    #   ⇒ 修：**只按 engine 的 `--mine_pool` 归属**（归属由 v1.3.6 保证准确）✓
    #     · 调度器"正在跑哪个池"由控制文件 `curPool` 表达 ⇒ 那是 `mine.py` 的职责 ✓
    running_by = []
    for pr in procs:
        if pr.get('err'):
            continue
        if pr['kind'] == 'engine' and pool in (pr.get('pools') or []):
            running_by.append(pr['pid'])

    return {
        'key': pool,
        'label': core.pool_label(pool),
        'running': bool(running_by),
        'runningPids': running_by,
        'state': st,
        'librarySize': (st or {}).get('bank_n'),
        'tested': (st or {}).get('n_tested'),
        'journal': {
            'gens': len(gens),
            'maxGen': max(gens) if gens else None,
            'path': os.path.relpath(jpath, settings.PROJECT_ROOT) if os.path.exists(jpath) else None,
            'mtime': core.mtime_iso(jpath),
        },
        'archive': {
            'rows': len(rows),
            'passed': passed,
            'maxGen': (max(int(r[gen_col]) for r in rows
                            if len(r) > gen_col and str(r[gen_col]).strip().isdigit())
                       if gen_col is not None and rows else None),
            'path': os.path.relpath(apath, settings.PROJECT_ROOT) if os.path.exists(apath) else None,
        },
    }


def snapshot():
    """全量快照：进程 + 各池状态 + 汇总。"""
    procs_raw = core.cached('procs', 4.0, list_processes)
    procs = [classify_proc(p) for p in procs_raw if not p.get('err')]
    err = procs_raw[0].get('err') if (procs_raw and procs_raw[0].get('err')) else None
    pools = [pool_status(k, procs) for k in core.POOL_KEYS]
    return {
        'generatedAt': time.strftime('%Y-%m-%d %H:%M:%S'),
        'anyRunning': any(p['running'] for p in pools),
        'processes': procs,
        'processError': err,
        'pools': pools,
        'summary': {
            'poolCount': len(pools),
            'runningPoolCount': sum(1 for p in pools if p['running']),
            'totalLibrary': sum((p['librarySize'] or 0) for p in pools),
            'totalTested': sum((p['tested'] or 0) for p in pools),
            'totalArchiveRows': sum(p['archive']['rows'] for p in pools),
        },
    }
