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

_MINE_POOL_RE = re.compile(r'--mine_pool[= ]([A-Za-z0-9,]+)')
_POOLS_RE = re.compile(r'--pools[= ]([A-Za-z0-9,]+)')


def list_processes():
    """列出与本项目相关的 python 进程（只读；PowerShell CIM）。"""
    try:
        out = subprocess.run(['powershell', '-NoProfile', '-Command', PS_PROCS],
                             capture_output=True, timeout=25)
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
    pools = []
    m = _MINE_POOL_RE.search(cmd)
    if m:
        pools = [x for x in m.group(1).split(',') if x]
    else:
        m2 = _POOLS_RE.search(cmd)
        if m2:
            pools = [x for x in m2.group(1).split(',') if x]
    if 'run_tracks' in cmd:
        kind = 'driver'
    elif 'loop_engine' in cmd:
        kind = 'engine'
    elif 'loop_watch' in cmd:
        kind = 'watcher'
    else:
        kind = 'other'
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

    # 在跑判定：① 有 engine 进程且池匹配；② driver 在跑的池集合
    running_by = []
    for pr in procs:
        if pr.get('err'):
            continue
        if pr['kind'] == 'engine' and (not pr['pools'] or pool in pr['pools']):
            running_by.append(pr['pid'])
        elif pr['kind'] == 'driver' and (not pr['pools'] or pool in pr['pools']):
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
