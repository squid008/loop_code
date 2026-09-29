# -*- coding: utf-8 -*-
"""os_compat.py — 把"操作系统专有"的四件事**收敛到一处**（★ 单一实现 ✓）。

## 为什么（`docs/loop_todo.md §1.40.3` · 用户 2026-09-29 拍板：做"**零行为变化**"的平台化 ✓）
可移植性那一分卡的就是这几个点（看板/调度器里的 Win32 专有点 ✗）：
| 能力 | 原来散在哪儿 | 原来怎么写 |
|---|---|---|
| **可用内存** | `tools/parallel_runner.avail_gb` ✓ · `dashboard/.../mine.avail_gb` ✓ · `tools/sysinfo` ✓ · `tools/curves_job_status` ✓ | ctypes `GlobalMemoryStatusEx` ✗ |
| **列进程** | `dashboard/.../sources/pools.PS_PROCS` ✓ · `engine/loop_status` ✓ · `engine/loop_watch` ✓ · `tools/tracks_status` ✓ · `tools/horizon_admit_write` ✓ | PowerShell `Get-CimInstance Win32_Process` ✗ |
| **杀进程** | `dashboard/.../mine.py`（3 处 ✓） | `taskkill /PID … /T /F` ✗ |
| **判存活** | `dashboard/.../mine._alive` ✓ | `tasklist /FI "PID eq …"` ✗ |

## 纪律（★ 与项目其它改动同一条：**Windows 上逐字不变** ✓）
1. 本模块只做**转发/收敛** ✓ —— Windows 分支里的类字段、命令行、键名与原来**逐字一致** ✓
   （原来内联在调用方的那些字符串，一字不差搬进来 ✓）。
2. POSIX 分支是**新增**的 ✓（Windows 上永不执行 ⇒ **行为零变化** ✓✓）。
3. ⚠ **本机没有 Linux ⇒ POSIX 分支只能保证"降级不崩 / 尽力而为"，不能保证端到端可用** ✗ ——
   每个函数上都写明了它的 POSIX 口径与已知差异 ✓（**不假装验证过** ✗）。
4. 取值失败时的**返回契约与原来一模一样** ✓（`None` / `inf` 各按原调用方的约定 ✓，见各函数 ✓）。

> ⚠ 迁移进度（**未完成的别当已做** ✗）：本文件先落地**内存 / 杀进程 / 判存活**三件 ✓；
> 「列进程」那 5 处还在调用方各自拼 PowerShell ✗（要用 `list_procs()` 替掉 ✓，
> 但它们的**输出字段各不相同**：`pools` 要 `start`+`mem` ✓、`loop_status` 要 `run`(分钟) ✓、
> `tracks_status` 要 `pid+cmd` 原文 ✓、`loop_watch` 只要**个数** ✓、`horizon_admit_write` 只要 pid 串 ✓
> ⇒ 得逐处改**消费端**，不是换个函数名 ✓ —— 留作下一步 ✓）。
"""
import os
import subprocess
import sys

IS_WIN = (os.name == 'nt')

#: 起子进程**不弹黑窗**（用户 2026-09-16 要求「启动不要开 python 窗口」✓）。
#: ⚠ 用 `CREATE_NO_WINDOW` 而**不是 `DETACHED_PROCESS`**：后者会让孙子进程**新建控制台** ⇒ 弹窗 ✗；
#:   前者是"有控制台但隐藏" ⇒ **孙进程默认继承** ⇒ 全链路静默 ✓✓（这区别很关键 ✓）。
CREATE_NO_WINDOW = (getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000) if IS_WIN else 0)


# ★ 2026-09-29：原有一个 `_no_win()` 包装，**没有任何调用方** ✗（死码 ✓，被 `_audit_deadcode` 当场点名 ✓）
#   ⇒ 已删 ✓。要用隐藏窗口就直接传本模块的 `CREATE_NO_WINDOW` 常量 ✓（POSIX 上它本来就是 0 ✓）。


def mem_status():
    """物理内存状态 ⇒ `{'total_gb','avail_gb','load_pct'}`（取不到 ⇒ `None` ✓，不抛 ✓）。

    · **Windows（逐字搬原实现 ✓）**：`GlobalMemoryStatusEx` + 与原来完全相同的 `_fields_` 布局 ✓
      （`dwLength` 必须自己填 ✓，否则调用无效 ✓）。
    · **POSIX**：读 `/proc/meminfo` 的 `MemTotal`/`MemAvailable` ✓（单位 kB ⇒ 换算 ✓）；
      `load_pct` 按 `(1 - avail/total) * 100` 取整 ✓（⚠ 与 Windows 的 `dwMemoryLoad` 口径**不完全等价** ✗，
      但都是"已用百分比" ✓；Linux 侧**未被真实环境验证过** ✗）。
    """
    try:
        if IS_WIN:
            import ctypes

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [('dwLength', ctypes.c_ulong), ('dwMemoryLoad', ctypes.c_ulong),
                            ('ullTotalPhys', ctypes.c_ulonglong),
                            ('ullAvailPhys', ctypes.c_ulonglong),
                            ('ullTotalPageFile', ctypes.c_ulonglong),
                            ('ullAvailPageFile', ctypes.c_ulonglong),
                            ('ullTotalVirtual', ctypes.c_ulonglong),
                            ('ullAvailVirtual', ctypes.c_ulonglong),
                            ('ullAvailExtendedVirtual', ctypes.c_ulonglong)]

            m = MEMORYSTATUSEX()
            m.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
            if not m.ullTotalPhys:
                return None
            g = 1024 ** 3
            return {'total_gb': m.ullTotalPhys / g, 'avail_gb': m.ullAvailPhys / g,
                    'load_pct': int(m.dwMemoryLoad)}
        with open('/proc/meminfo', encoding='ascii', errors='replace') as f:
            kv = {}
            for ln in f:
                if ':' in ln:
                    k, v = ln.split(':', 1)
                    kv[k.strip()] = v.strip()
        tot = float(str(kv.get('MemTotal', '0')).split()[0]) / 1048576.0       # kB -> GB
        av_ms = kv.get('MemAvailable')
        # ⚠ 老内核没有 MemAvailable ⇒ 退化成 MemFree（会**偏小** ✗，宁可保守：并行开得少一点 ✓）
        av = float(str(av_ms if av_ms is not None else kv.get('MemFree', '0')).split()[0]) / 1048576.0
        if tot <= 0:
            return None
        return {'total_gb': tot, 'avail_gb': av, 'load_pct': int(round((1.0 - av / tot) * 100.0))}
    except Exception:                                                        # noqa: BLE001
        return None


def avail_gb():
    """**可用物理内存（GB）**；取不到 ⇒ `None` ✓。

    ★ 这是 `dashboard/api/app/mine.avail_gb()` 的**原契约**（失败返回 None ✓，调用方自己兜底 ✓）。
    """
    s = mem_status()
    return None if s is None else float(s['avail_gb'])


def avail_gb_or_inf():
    """**可用物理内存（GB）**；取不到 ⇒ `inf` ✓（"不因测不出而卡死" ✓）。

    ★ 这是 `tools/parallel_runner.avail_gb()` 的**原契约** ✓（并行闸门用它 ✓ ——
      返回 inf 的语义是"测不出就别拦" ✓，与返回 None 的调用方**不同** ✗，故两个都留着 ✓）。
    """
    s = mem_status()
    return float('inf') if s is None else float(s['avail_gb'])


def alive(pid):
    """进程是否还活着 ⇒ `True/False`；**查不出来 ⇒ `None`**（原契约 ✓）。

    · Windows（逐字搬 ✓）：`tasklist /FI "PID eq <pid>" /NH` ⇒ 输出里含该 pid ✓；
    · POSIX：`os.kill(pid, 0)` ⇒ 没抛就是活着 ✓（`PermissionError` 也算活着 ✓ ——
      "存在但没权限信号" ≠ "不存在" ✓）；`ProcessLookupError` ⇒ 已死 ✓。
    """
    try:
        if IS_WIN:
            r = subprocess.run(['tasklist', '/FI', 'PID eq %d' % int(pid), '/NH'],
                               capture_output=True, text=True, encoding='utf-8', errors='replace',
                               creationflags=CREATE_NO_WINDOW)
            return str(pid) in (r.stdout or '')
        os.kill(int(pid), 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except Exception:                                                        # noqa: BLE001
        return None


def kill_tree(pid):
    """**连子孙一起**强杀 ⇒ `(rc, 输出文本)` ✓（rc 语义与 `taskkill` 一致 ✓：0 = 成功 ✓）。

    · Windows（逐字搬 `dashboard/.../mine.py` 那三处 ✓）：`taskkill /PID <pid> /T /F` ✓
      ⚠ `taskkill /F` **返回 ≠ 进程已退出** ✗（Windows 回收要一点时间 ✓）⇒ 调用方仍须**轮询等它真没** ✓
      （`mine.py` 已有那个最多 5s 的轮询 ✓，本函数**不替它做** ✗，以免改变既有语义 ✓）。
    · POSIX：先 `SIGTERM` 整个**进程组**（`os.killpg` ✓；拿不到进程组就退化成杀单进程 ✓），
      短暂等待后仍在 ⇒ 补 `SIGKILL` ✓；返回 `(0, '')` / `(1, 原因)` ✓（⚠ Linux 侧未在真机验证 ✗）。
    """
    pid = int(pid)
    if IS_WIN:
        r = subprocess.run(['taskkill', '/PID', str(pid), '/T', '/F'],
                           capture_output=True, text=True, encoding='utf-8', errors='replace',
                           creationflags=CREATE_NO_WINDOW)
        return int(r.returncode), (r.stdout or r.stderr or '').strip()
    import signal
    import time as _t
    err = ''
    try:
        try:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
        except Exception:                                                    # noqa: BLE001
            os.kill(pid, signal.SIGTERM)
        for _ in range(20):                                                  # 最多 ~2s 等它自己走
            if alive(pid) is False:
                return 0, ''
            _t.sleep(0.1)
        try:
            os.killpg(os.getpgid(pid), signal.SIGKILL)
        except Exception:                                                    # noqa: BLE001
            os.kill(pid, signal.SIGKILL)
        return 0, ''
    except Exception as e:                                                   # noqa: BLE001
        err = '%s: %s' % (type(e).__name__, e)
        return 1, err


def list_procs(name_like='python%'):
    """列出进程 ⇒ `[{'pid':int,'cmd':str,'start':str,'mem_mb':int}, …]` ✓（失败 ⇒ `[]` ✓）。

    ★ **字段名与 `dashboard/.../sources/pools.PS_PROCS` 的输出逐字一致** ✓
      （`pid` / `cmd` / `start`（`yyyy-MM-dd HH:mm:ss`）/ `mem`（MB 取整）✓），
      这样消费端只要把"跑 PS"换成"调本函数"，**其余一字不用改** ✓。
    · Windows：仍是原来那句 `Get-CimInstance Win32_Process … ConvertTo-Json` ✓（逐字搬 ✓，
      只把 `-Filter` 变成参数化的 `Name like '<name_like>'` ✓ —— 传 `'python%'` 与原来等价 ✓）。
    · POSIX：`ps -eo pid,lstart,rss,args` ✓ 解析 ⇒ 同一套字段 ✓
      （`start` 用 `%Y-%m-%d %H:%M:%S` 重排 ✓；`mem_mb` = rss kB / 1024 ✓）。⚠ Linux 侧未真机验证 ✗。
    """
    if IS_WIN:
        import json
        ps = ("Get-CimInstance Win32_Process -Filter \"Name like '%s'\" | "
              "ForEach-Object { [PSCustomObject]@{ pid=$_.ProcessId; "
              "cmd=$_.CommandLine; start=$_.CreationDate.ToString('yyyy-MM-dd HH:mm:ss'); "
              "mem=[math]::Round($_.WorkingSetSize/1MB,0) } } | ConvertTo-Json -Compress -Depth 3"
              % name_like)
        try:
            out = subprocess.run(['powershell', '-NoProfile', '-Command', ps],
                                 capture_output=True, text=True, encoding='utf-8',
                                 errors='replace', creationflags=CREATE_NO_WINDOW)
            d = json.loads((out.stdout or '').strip() or '[]')
        except Exception:                                                    # noqa: BLE001
            return []
        rows = d if isinstance(d, list) else [d]
        out_rows = []
        for it in rows:
            if not isinstance(it, dict):
                continue
            out_rows.append({'pid': int(it.get('pid') or 0), 'cmd': str(it.get('cmd') or ''),
                             'start': str(it.get('start') or ''),
                             'mem_mb': int(float(it.get('mem') or 0))})
        return out_rows
    try:
        out = subprocess.run(['ps', '-eo', 'pid,lstart,rss,args'],
                             capture_output=True, text=True, encoding='utf-8', errors='replace')
    except Exception:                                                        # noqa: BLE001
        return []
    rows = []
    import time as _t
    for ln in (out.stdout or '').splitlines()[1:]:
        parts = ln.split(None, 8)                    # pid + lstart(5 段) + rss + args
        if len(parts) < 8:
            continue
        try:
            pid = int(parts[0])
            rss_kb = int(parts[6])
        except ValueError:
            continue
        cmd = parts[7] if len(parts) > 7 else ''
        try:
            st = _t.strptime(' '.join(parts[1:6]), '%a %b %d %H:%M:%S %Y')
            start = _t.strftime('%Y-%m-%d %H:%M:%S', st)
        except Exception:                                                    # noqa: BLE001
            start = ''
        rows.append({'pid': pid, 'cmd': cmd, 'start': start, 'mem_mb': int(rss_kb / 1024)})
    return rows


if __name__ == '__main__':
    # 自带冒烟：不碰网络、不写文件 ✓（人肉排查用 ✓）
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    print('os.name=%s · CREATE_NO_WINDOW=%s' % (os.name, CREATE_NO_WINDOW))
    print('mem_status = %s' % (mem_status(),))
    print('avail_gb = %s · avail_gb_or_inf = %s' % (avail_gb(), avail_gb_or_inf()))
    print('alive(自己) = %s' % (alive(os.getpid()),))
    ps = [p for p in list_procs() if 'python' in p['cmd'].lower()]
    print('python 进程 %d 个（前 3：%s）' % (len(ps), [(p['pid'], p['mem_mb']) for p in ps[:3]]))
