# -*- coding: utf-8 -*-
"""curves_job_status.py — **一行命令查"曲线重算"跑到哪了**（用户要的：过一段时间回来查任务状态）

用户原话：「写个过一段时间查询任务状态的命令」⇒ 就看三件事：
  ① 两段后台任务（`--stage=strip` / `--stage=style+strip2`）各自的进度与是否结束
  ② **数据侧**：61 个曲线文件里，有多少已经是**新口径**（`styCal == 'barra11+industry'`）
     —— 这比看日志更可信（日志可能还在写，文件是最终产物 ✓）
  ③ 进程与资源：还有没有 `factor_curves` 在跑 · 挖矿在不在跑 · 可用内存

用法:  python tools/curves_job_status.py
（退出码：0 = 两段都完成 ✓；1 = 还在跑）
"""
import glob
import io
import json
import os
import re
import subprocess
import sys
import time

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:                                        # noqa: BLE001
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from factor_curves import ALLSTY_CAL                      # noqa: E402  ★ 口径标记单一来源


def _read_any(path):
    """把日志读成 str —— **编码不定**（PowerShell `*>` 默认写 UTF-16LE ✗，python 直接写是本地码页）。

    ⚠ 实测踩到：只按 utf-8 读会把内容变成 NUL 夹杂的乱码 ⇒ 正则永远匹配不上 ⇒ 状态显示"未开始" ✗
      ⇒ 这里依次尝试 utf-16 / utf-8 / gbk，并对残留 NUL 做清理 ✓
    """
    b = open(path, 'rb').read()
    if b[:2] in (b'\xff\xfe', b'\xfe\xff') or b.count(b'\x00') > len(b) // 4:
        return b.decode('utf-16', errors='replace').replace('\x00', '')
    for enc in ('utf-8', 'gbk'):
        try:
            return b.decode(enc)
        except Exception:                                 # noqa: BLE001
            continue
    return b.decode('utf-8', errors='replace')


def _tail(path, pat, n=1):
    """日志尾部的匹配行"""
    if not os.path.exists(path):
        return []
    try:
        t = _read_any(path)
    except Exception:                                     # noqa: BLE001
        return []
    return re.findall(pat, t, re.M)[-n:]


def _procs():
    """在跑的 python 进程（用 wmic 更省事；拿不到就返回空 —— 状态脚本**不该因为查不到进程就挂** ✗）"""
    try:
        out = subprocess.run(['wmic', 'process', 'where', "name like '%python%'",
                              'get', 'ProcessId,CommandLine', '/format:list'],
                             capture_output=True, text=True, timeout=30,
                             errors='replace').stdout
    except Exception:                                     # noqa: BLE001
        return {}
    res = {'curves': 0, 'mine': 0, 'sched': 0}
    cur = ''
    for ln in out.splitlines():
        ln = ln.strip()
        if ln.startswith('CommandLine='):
            cur = ln[12:]
        elif ln.startswith('ProcessId='):
            if 'factor_curves' in cur:
                res['curves'] += 1
            elif 'run_tracks' in cur or 'parallel_runner' in cur:
                res['sched'] += 1
            elif 'loop_engine' in cur:
                res['mine'] += 1
    return res


def _newest(pat):
    """★ 认**最新**那份日志（重跑会换文件名：`_rc_strip.log` / `_rc_strip2.log` / … ✗
    —— 只认死路径会把**上一轮**的进度当成本轮 ✗，实测踩到）"""
    fs = glob.glob(os.path.join(ROOT, 'ai_test', pat))
    return max(fs, key=os.path.getmtime) if fs else ''


def main():
    logs = {'strip': _newest('_rc_strip*.log'), 'style': _newest('_rc_style*.log')}
    print('=' * 78)
    print('曲线重算状态（口径标记 %s）' % ALLSTY_CAL)
    print('=' * 78)
    done = {}
    for tag, p in logs.items():
        prog = _tail(p, r'^\[(\d+/\d+)\]\s+\S+')
        fin = _tail(p, r'^(完成 \d+ 个.*)$')
        done[tag] = bool(fin)
        # ⚠ 必须显示日志**时间戳**：重跑会换文件名（`_rc_style.log` 是上一轮的 ✓），
        #   不看时间就会把"上一轮已完成 59/59"当成本轮进度 ✗（实测踩到）
        mt = time.strftime('%m-%d %H:%M', time.localtime(os.path.getmtime(p))) if p else '—'
        print('  %-6s 进度 %-10s %s   [日志 %s]' % (tag, (prog[0] if prog else '（未开始）'),
                                                   (fin[0] if fin else '⏳ 进行中'), mt))
    files = sorted(glob.glob(os.path.join(ROOT, 'docs', 'factor_curves', '*.json')))
    n_str = n_sty = n_all = 0
    for p in files:
        try:
            d = json.load(io.open(p, encoding='utf-8'))
        except Exception:                                 # noqa: BLE001
            continue
        n_all += 1
        if (d.get('strip') or {}).get('styCal') == ALLSTY_CAL:
            n_str += 1
        if (d.get('style') or {}).get('styCal') == ALLSTY_CAL:
            n_sty += 1
    print('  数据侧 %d 个文件：strip 新口径 %d 个 · style 新口径 %d 个' % (n_all, n_str, n_sty))
    q = _procs()
    print('  进程：曲线重算 %d 个 · 挖矿引擎 %d 个 · 调度器 %d 个' % (q['curves'], q['mine'], q['sched']))
    try:
        import ctypes

        class _MEM(ctypes.Structure):
            _fields_ = [('dwLength', ctypes.c_ulong), ('dwMemoryLoad', ctypes.c_ulong),
                        ('ullTotalPhys', ctypes.c_ulonglong), ('ullAvailPhys', ctypes.c_ulonglong),
                        ('ullTotalPageFile', ctypes.c_ulonglong),
                        ('ullAvailPageFile', ctypes.c_ulonglong),
                        ('ullTotalVirtual', ctypes.c_ulonglong),
                        ('ullAvailVirtual', ctypes.c_ulonglong),
                        ('ullAvailExtendedVirtual', ctypes.c_ulonglong)]
        m = _MEM()
        m.dwLength = ctypes.sizeof(_MEM)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
        print('  内存：可用 %.1f GB / 共 %.1f GB' % (m.ullAvailPhys / 2 ** 30, m.ullTotalPhys / 2 ** 30))
    except Exception:                                     # noqa: BLE001
        pass
    ok = (n_str >= n_all and n_sty >= n_all and n_all > 0 and not q['curves'])
    print('-' * 78)
    print('  %s' % ('★ 两段都跑完了（61 个文件全部是新口径 ✓）' if ok else
                    '⏳ 还在跑 —— 过一会儿再执行一次本命令即可'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
