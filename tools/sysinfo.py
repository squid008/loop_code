# -*- coding: utf-8 -*-
"""`sysinfo.py` — 看机器资源（内存 / CPU），用于判断"能几个引擎并行"。

★ 为什么需要：引擎单进程实测约 **6~9 GB**（载入面板 3309×5384）。
  「每池一进程」= 5 个引擎并行 ⇒ 需要 ~30~45 GB
  ⇒ ★ 启动前必须确认内存够，否则会**互相挤爆（OOM）** ✗
"""
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

print('=' * 90)
print('[1] 内存 / CPU')
print('=' * 90)
try:
    import ctypes

    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [('dwLength', ctypes.c_ulong), ('dwMemoryLoad', ctypes.c_ulong),
                    ('ullTotalPhys', ctypes.c_ulonglong), ('ullAvailPhys', ctypes.c_ulonglong),
                    ('ullTotalPageFile', ctypes.c_ulonglong), ('ullAvailPageFile', ctypes.c_ulonglong),
                    ('ullTotalVirtual', ctypes.c_ulonglong), ('ullAvailVirtual', ctypes.c_ulonglong),
                    ('ullAvailExtendedVirtual', ctypes.c_ulonglong)]

    m = MEMORYSTATUSEX()
    m.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    G = 1024 ** 3
    print('  物理内存: 总 %.1f GB / 可用 %.1f GB / 占用 %d%%'
          % (m.ullTotalPhys / G, m.ullAvailPhys / G, m.dwMemoryLoad))
    print('  ⇒ 单引擎约需 6~9 GB ⇒ 可用内存最多支持约 **%d** 个引擎并行'
          % max(int(m.ullAvailPhys / G / 9), 0))
except Exception as e:
    print('  ✗ %r' % (e,))

try:
    out = subprocess.run(['wmic', 'cpu', 'get', 'NumberOfCores,NumberOfLogicalProcessors', '/format:list'],
                         capture_output=True, text=True, encoding='utf-8', errors='replace')
    for l in (out.stdout or '').splitlines():
        if l.strip():
            print('  CPU %s' % l.strip())
except Exception as e:
    print('  CPU ✗ %r' % (e,))

print()
print('=' * 90)
print('[2] 当前 python 进程内存 top 8')
print('=' * 90)
try:
    out = subprocess.run(['powershell', '-NoProfile', '-Command',
                          "Get-Process python -ErrorAction SilentlyContinue | "
                          "Sort-Object -Descending WorkingSet64 | Select-Object -First 8 | "
                          "ForEach-Object { '{0,7}  {1,9:N0} MB' -f $_.Id, ($_.WorkingSet64/1MB) }"],
                         capture_output=True, text=True, encoding='utf-8', errors='replace')
    print(out.stdout.strip() or '  (无 python 进程)')
except Exception as e:
    print('  ✗ %r' % (e,))
