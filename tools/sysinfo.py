# -*- coding: utf-8 -*-
"""`sysinfo.py` — 看机器资源（内存 / CPU），用于判断"能几个引擎并行"。

★ 为什么需要：引擎单进程实测约 **6~9 GB**（载入面板 3309×5384）。
  「每池一进程」= 5 个引擎并行 ⇒ 需要 ~30~45 GB
  ⇒ ★ 启动前必须确认内存够，否则会**互相挤爆（OOM）** ✗
"""
import os
import sys            # ★ 2026-09-29：subprocess 随 wmic/PowerShell 一起下岗（死码 ✗）

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

print('=' * 90)
print('[1] 内存 / CPU')
print('=' * 90)
# ★ 2026-09-29（`loop_todo §1.40.3` 可移植性平台化）：内存查询搬进 `engine/os_compat.py` ✓
#   （Win32 的 ctypes 逐字搬过去了 ✓；这里不再有 Win32 代码 ✓；契约：取不到 ⇒ None ✓）
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'engine'))
import os_compat as OC                                                       # noqa: E402
_s = OC.mem_status()
if _s is None:
    print('  ✗ 取不到内存信息（os_compat.mem_status() 返回 None ✓）')
else:
    G = 1024 ** 3
    print('  物理内存: 总 %.1f GB / 可用 %.1f GB / 占用 %d%%'
          % (_s['total_gb'], _s['avail_gb'], _s['load_pct']))
    print('  ⇒ 单引擎约需 6~9 GB ⇒ 可用内存最多支持约 **%d** 个引擎并行'
          % max(int(_s['avail_gb'] / 9), 0))

# ★ 2026-09-29（§1.40.3 可移植性平台化）：改用 `os.cpu_count()` ✓
#   （原为 `wmic cpu get NumberOfCores,NumberOfLogicalProcessors` ✗ —— wmic 是 Win32 专有，
#    且在新版 Windows 上**已被移除** ✗）
#   ⚠ 如实记账：这**只报逻辑核** ✗（物理核要 wmic / psutil —— 本工具不再依赖它们 ✓，
#     想看物理核请用别的工具 ✓）。
print('  CPU 逻辑核数：%s' % (os.cpu_count() if os.cpu_count() else '?'))

print()
print('=' * 90)
print('[2] 当前 python 进程内存 top 8')
print('=' * 90)
# ★ 2026-09-29（§1.40.3）：列进程也走 `os_compat.list_procs()` ✓
#   （Windows 仍是同一句 PowerShell ✓，POSIX 换成 `ps` ✓；字段名与原来一致 ✓）
_rows = [p for p in OC.list_procs() if 'python' in (p['cmd'] or '').lower()]
_rows.sort(key=lambda p: -p['mem_mb'])
if _rows:
    for p in _rows[:8]:
        print('%7d  %9s MB' % (p['pid'], format(p['mem_mb'], ',')))
else:
    print('  (无 python 进程)')
