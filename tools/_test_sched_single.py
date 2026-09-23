# -*- coding: utf-8 -*-
"""★★★★ 守门：调度器的**单实例闸**（2026-09-23 新增；命名 `_test_*` ⇒ 进全量回归 ✓）。

为什么要有它（**实测事故**，用户拍板要做 ✓）：
  09-23 10:16~10:19 有**两个调度器并起**（看板上重复启动的重叠窗口），它们都盯着**同一个**
  `ai_test/_tracks/_control.json`、各按自己的候选起引擎，而"停止/重启"会杀"当前那一代"的引擎
  ⇒ **互相杀**：`10:19:08 [END] pool=300 gen=185 退出码=1 耗时=2.8min`（500 gen95 同）
  ⇒ **2 代作废**（无脏数据，白跑 ✓，但"谁是权威"被污染 ✗）

本守门钉三件：
  【1】静态：`run_tracks.py` 里有 `acquire_single_instance()`（内核命名互斥量，随进程消亡自动释放 ✓）
        · 闸在 `--rounds>0` 时开 ✓
        · 闸的检查**早于任何 `write_ctl`**（否则第二个实例会先冲掉控制文件再退出 ✗✗）
        · 有 `--force_single=1` 逃生口 ✓
  【2】功能：互斥量语义 —— 抢两次 ⇒ 第二次必失败（同进程也成立 ✓，内核语义）；
        释放后可再抢 ✓
        ★★ 这三小步用**本测试私有的互斥量名**（`…_selftest_<pid>`）—— 因为**真实挖掘调度器
        可能正在跑**，它持有的是**正式名字**那把锁 ✗ 共用会让"抢 ⇒ 成功"假失败（实测踩过 ✓）
  【3·注】"控制文件未被动"那条断言只在**本机没有真调度器**时才判（判据 = 能否抢到正式名字那把锁 ✓）；
        有人在跑时它每代都在写 ctl ⇒ 该断言不适用（打印 note 跳过，**不算失败** ✓）
  【3】端到端：**本进程持有锁**时，真跑 `run_tracks.py --pools=300 --rounds=1 --dry`
        ⇒ 必须以 **rc=3** 退出、且**不碰** `_control.json` ✓（用 --dry ⇒ 万一闸失效也只打印、
        绝不真起引擎 ✓ 安全的负向测试 ✓）
"""
import io
import json
import os
import re
import subprocess
import sys
import time

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

RT = io.open(os.path.join(HERE, 'run_tracks.py'), encoding='utf-8').read()
FAIL = []


def chk(desc, cond, hint=''):
    print('  %s %s' % ('✓' if cond else '✗', desc))
    if not cond:
        FAIL.append(desc + ('（%s）' % hint if hint else ''))


print('[1] 静态：闸存在、位置对、有逃生口')
chk('有 `def acquire_single_instance(`（内核互斥量 ✓）',
    'def acquire_single_instance(' in RT)
chk('用 `CreateMutexW`（**不是** PID 文件 ⇒ 崩溃不留脏锁 ✓）', 'CreateMutexW' in RT)
chk('识别 `ERROR_ALREADY_EXISTS`(183) ⇒ 判定"已有调度器" ✓',
    re.search(r'==\s*183\b', RT) is not None and 'ERROR_ALREADY_EXISTS' in RT)
chk('互斥量名**按 `_tracks` 目录派生**（不同 checkout 互不干扰 ✓）',
    'def sched_mutex_name(' in RT and 'os.path.abspath(LOGD)' in RT)
chk('只在 `--rounds>0` 时开闸（纯收尾 `--rounds=0` 不拦 ✓）',
    re.search(r'if rounds > 0:\n\s+_ok, _why = acquire_single_instance\(\)', RT) is not None)
chk('有 `--force_single=` 解析（人工排障逃生口 ✓）',
    re.search(r"startswith\('--force_single='\)", RT) is not None)
chk('闸失败返回**非零码**（rc=3 ⇒ 看板/人都能看出"没起来" ✓）',
    re.search(r'return 3\b', RT) is not None)
# ★★ 关键顺序：闸必须在**第一次 write_ctl 之前**（否则会先冲掉控制文件 ✗）
_i_guard = RT.find('acquire_single_instance()')
_i_wctl = RT.find('write_ctl(enabled=list(pools), stopped=[])')
chk('★ 闸的检查**早于**第一次 `write_ctl`（不然第二个实例会先改控制文件 ✗✗）',
    _i_guard > 0 and _i_wctl > 0 and _i_guard < _i_wctl,
    'guard@%s write_ctl@%s' % (_i_guard, _i_wctl))

print()
print('[2] 功能：互斥量"抢两次必失败"、释放后可再抢')
try:
    import run_tracks as RTM
    _imp = True
except Exception as e:                                                          # noqa: BLE001
    _imp = False
    print('  ✗ 导入 run_tracks 失败：%r' % (e,))
    FAIL.append('导入 run_tracks 失败：%r' % (e,))

if _imp:
    # ★★★★★ 2026-09-23（自己踩的坑）：互斥量语义那三小步必须用**本测试私有的名字** ✗
    #   原因：**真实挖掘调度器可能正在跑**（它就持有那个正式名字 ✓）⇒ 若共用同一个名字：
    #     · 第一步"抢 ⇒ 成功"会**假失败**（人家替你持着 ✗）
    #     · 第三步"释放后再抢"也会**假失败**（同理 ✗）
    #   —— 而本测试**没有任何理由**去碰真实调度器那把锁 ⇒ 私有名字更干净、也照样验证内核语义 ✓
    _TNAME = 'Local\\loop_code_sched_selftest_%d' % os.getpid()
    if RTM._MUTEX_HANDLE is not None:              # 保险：先把自己那份放掉
        RTM._MUTEX_HANDLE = None
    ok1, why1 = RTM.acquire_single_instance(_TNAME)
    chk('第一次抢 ⇒ 成功（why=%s）' % why1, ok1 is True, '得到 %r/%r' % (ok1, why1))
    ok2, why2 = RTM.acquire_single_instance(_TNAME)
    chk('★ 第二次抢（同名，同进程也算"已存在"）⇒ **必须失败**（why=exists）',
        ok2 is False and why2 == 'exists', '得到 %r/%r' % (ok2, why2))
    # 放掉我们自己那份 ⇒ 再抢必须成功（说明"进程退出即解锁"这条语义成立 ✓）
    _h = RTM._MUTEX_HANDLE
    RTM._MUTEX_HANDLE = None
    if _h:
        try:
            import ctypes
            ctypes.WinDLL('kernel32').CloseHandle(_h)
        except Exception:
            pass
    ok3, why3 = RTM.acquire_single_instance(_TNAME)
    chk('★ 释放后（=进程退出语义）⇒ 再抢成功（无脏锁 ✓）',
        ok3 is True, '得到 %r/%r' % (ok3, why3))
    if RTM._MUTEX_HANDLE is not None:               # 用完就放（别把私名锁带出本节 ✓）
        try:
            import ctypes
            ctypes.WinDLL('kernel32').CloseHandle(RTM._MUTEX_HANDLE)
        except Exception:
            pass
        RTM._MUTEX_HANDLE = None

    print()
    print('[3] 端到端：本进程持锁 ⇒ 真跑一个调度器必须 rc=3')
    CTL = os.path.join(ROOT, 'ai_test', '_tracks', '_control.json')
    # ★ "控制文件一个字节都没动"这条断言只在本机**没有真调度器**时才可判（否则人家每代都在写它 ✗）
    #   ⇒ 判据 = 能不能抢到**正式名字**那把锁：抢到 ⇒ 无调度器（测完立刻放掉 ✓）；抢不到 ⇒ 有人在跑 ✓
    _okr, _whyr = RTM.acquire_single_instance()
    _solo = bool(_okr)
    if _okr and RTM._MUTEX_HANDLE is not None:
        try:
            import ctypes
            ctypes.WinDLL('kernel32').CloseHandle(RTM._MUTEX_HANDLE)
        except Exception:
            pass
        RTM._MUTEX_HANDLE = None
    if not _solo:
        print('  [note] 检测到**真实调度器在跑**（正式互斥量已被占用）⇒ 跳过"控制文件未被动"那条断言 ✓')
    _before = None
    if os.path.exists(CTL):
        try:
            _before = json.load(io.open(CTL, encoding='utf-8'))
        except Exception:
            _before = None
    # ★ 自己持锁（受测的其实是"闸会拦住"，用正式名字 ✓）⇒ 真跑一个调度器（`--dry` ⇒ 绝不起引擎 ✓）
    RTM.acquire_single_instance()
    _env = dict(os.environ)
    _env['PYTHONIOENCODING'] = 'utf-8'
    r = subprocess.run([sys.executable, '-u', 'tools/run_tracks.py',
                        '--pools=300', '--rounds=1', '--dry'],
                       cwd=ROOT, capture_output=True, text=True, encoding='utf-8',
                       errors='replace', env=_env, timeout=300,
                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    out = (r.stdout or '') + (r.stderr or '')
    chk('★ 退出码 = 3（明确"没起来"，不是静默并跑 ✗）', r.returncode == 3,
        'rc=%r 尾巴=%s' % (r.returncode, out.strip().splitlines()[-1:] ))
    chk('★ 日志里说清了原因（"已有一个调度器在跑"）', '已有一个调度器在跑' in out,
        out.strip()[-160:])
    _after = None
    if os.path.exists(CTL):
        try:
            _after = json.load(io.open(CTL, encoding='utf-8'))
        except Exception:
            _after = None
    if _solo:
        chk('★★ 控制文件**一个字节都没动**（闸在 write_ctl 之前 ✓）',
            _before == _after,
            'before=%s after=%s' % (str(_before)[:120], str(_after)[:120]))
    else:
        print('      （控制文件此刻由真实调度器在写 ⇒ 该断言本次不适用 ✓）')
    # 把锁还给"后面还要用它的进程"（本测试进程马上就退出了 ✓ 显式放掉更干净）
    _h2 = RTM._MUTEX_HANDLE
    RTM._MUTEX_HANDLE = None
    if _h2:
        try:
            import ctypes
            ctypes.WinDLL('kernel32').CloseHandle(_h2)
        except Exception:
            pass

print()
if FAIL:
    print('✗ 失败 %d 项：' % len(FAIL))
    for x in FAIL:
        print('   - %s' % x)
    sys.exit(1)
print('✓ 全部通过：单实例闸（静态 + 互斥量语义 + 端到端 rc=3/不碰控制文件）')
time.sleep(0)
