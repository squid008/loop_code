# -*- coding: utf-8 -*-
"""parallel_runner.py -- 多池轨道的**有界并行**调度器（2026-09-16 新增）。

★ 与 `run_tracks.py`（串行轮转）的关系（**开关切换，旧行为零改动**）：
  · `run_tracks.py --exec_mode=parallel` 会**委托**给本模块；默认仍是 `rotate`（= 现状）✓
  · 本模块**复用** `run_tracks` 的公共件（`log` / `next_gen` / `read_ctl` / `write_ctl` /
    `inject_for` / `do_global_tail` / `read_log` / `NO_WIN` / `LOGD` / `PY`）—— **绝不复制实现**，
    否则两条调度路径必然漂移 ✗
  · 之所以单独成一个模块（而不是塞进 run_tracks）：调度语义不同（轮转 vs 有界并行），
    各自保持可读；`run_tracks.py` 只多一个"分叉 + 透传"的分支 ✓

★ 为什么值得并行（**实测**，`ai_test/_measure_engine_cpu.py`）：
  · 单引擎 **等效核 ≈ 0.99**（只吃 1 个核），本机 6 核/12 线程 ⇒ **CPU 有大把空间**；
  · 真正的约束是**内存**：面板 `B` = **4.42 GB/进程**；
    而 `--panel_cache=use` 把它落成**只读 memmap** ⇒ 多进程共享同一批物理页，
    每进程的**私有**内存只剩 L1 子面板 + 缓存 ⇒ 才放得下 N 个 ✓

★ 语义（与轮转**一致**，只把"同时 1 个"放宽成"同时 N 个"）：
    for r in 1..rounds:
        for pool in 启用池:        # 每池 1 代；★ **队列化**：跑完一个立刻补一个（快池不等慢池）
            跑该池 1 代             # 超出 N 个的进入**排队**
        ★ 一轮全部结束 ⇒ 自动收尾（`--no_global` 可关）
    ★ `stopAll`   ⇒ **不再补新任务**，等在跑的自然结束 ⇒ 收尾退出
    ★ `stopped`   ⇒ 该池**本轮不启动**（不影响其他池）
    ★★ 2026-09-16 新增（用户要求）：「单独停止某个池」⇒ **本轮不再补位** —— 空槽**留给用户自己决定**
       （想加回来点「启动本池」），不会"停一个就自动顶上来一个"✓；只影响**本轮**，
       下一轮按 `enabled - stopped` **重新组队**（被停的池不会自己回来）✓

★ 内存护栏（这套东西存在的意义就是"**别把机器挤爆**"）：
  · `--max_parallel=N`（硬上限，默认 3）
  · `--mem_per_engine=G`（每引擎预算，默认 3.0 GB）
  · 每次启动前查**可用物理内存**，不足 ⇒ **等待并打印原因**（每 15s 重试），而不是硬起
    （本项目出过 OOM/数据事故 ⇒ **宁可慢，不炸**）✓
  · ⚠ 只读 memmap 的页属于**可回收的 file cache**：任务管理器里会看到"已缓存"增长，
    但**别的程序要内存时会被自动回收** ⇒ 不会把机器锁死 ✓
"""
import io
import os
import subprocess
import sys
import time
from datetime import datetime

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import run_tracks as RT          # noqa: E402  ★ 复用公共件（不复制）


def avail_gb():
    """当前**可用物理内存**（GB）；查不到返回 inf（不因"测不出"而卡死）。"""
    try:
        import ctypes

        class MS(ctypes.Structure):
            _fields_ = [('dwLength', ctypes.c_ulong), ('dwMemoryLoad', ctypes.c_ulong),
                        ('ullTotalPhys', ctypes.c_ulonglong),
                        ('ullAvailPhys', ctypes.c_ulonglong),
                        ('ullTotalPageFile', ctypes.c_ulonglong),
                        ('ullAvailPageFile', ctypes.c_ulonglong),
                        ('ullTotalVirtual', ctypes.c_ulonglong),
                        ('ullAvailVirtual', ctypes.c_ulonglong),
                        ('ullAvailExtendedVirtual', ctypes.c_ulonglong)]
        m = MS()
        m.dwLength = ctypes.sizeof(MS)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
        return m.ullAvailPhys / (1024.0 ** 3)
    except Exception:
        return float('inf')


def _cmd_and_paths(pool, gen, n, l2, extra, inject_spec, pools, panel_cache):
    """拼引擎命令行 + 日志路径（与 `run_tracks.py` 的轮转分支**逐字段一致**）。"""
    sfx = '' if pool == 'all' else '_' + pool
    seed = gen * 10 + 7
    cmd = [RT.PY, '-u', 'engine/loop_engine.py', '--gen=%d' % gen, '--n=%d' % n,
           '--l2=%d' % l2, '--seed=%d' % seed] + list(extra)
    _inj = RT.inject_for(pool, pools, inject_spec)
    if _inj:
        cmd.append('--inject_pools=%s' % ','.join(_inj))
    cmd.append('--mine_pool=%s' % pool)          # ★ v1.3.6 BUG G：所有池都显式传（含 all）
    if panel_cache and panel_cache != 'off':     # ★ 默认不传（= 引擎默认 off ⇒ 命令与旧版一致）
        cmd.append('--panel_cache=%s' % panel_cache)
    logf = os.path.join(RT.LOGD, 'pool%s_gen%d.log' % (sfx, gen))
    errf = os.path.join(RT.LOGD, 'pool%s_gen%d_err.log' % (sfx, gen))
    return cmd, logf, errf, seed


def _launch(pool, gen, n, l2, extra, inject_spec, pools, panel_cache):
    cmd, logf, errf, seed = _cmd_and_paths(pool, gen, n, l2, extra, inject_spec, pools, panel_cache)
    os.makedirs(RT.LOGD, exist_ok=True)
    o = io.open(logf, 'w', encoding='utf-8')
    e = io.open(errf, 'w', encoding='utf-8')
    env = dict(os.environ)
    # ★ 子进程必须显式设 utf-8（否则它按 cp936 写、我们按 utf-8 读 ⇒ 日志乱码、进度解析失效）
    env['PYTHONIOENCODING'] = 'utf-8'
    pr = subprocess.Popen(cmd, cwd=ROOT, stdout=o, stderr=e, env=env,
                          creationflags=RT.NO_WIN)
    RT.log('[START] pool={:<5s} gen={} seed={} pid={} (并行槽 {})'.format(
        pool, gen, seed, pr.pid, os.path.basename(logf)))
    return {'pool': pool, 'gen': gen, 'pr': pr, 'o': o, 'e': e,
            'logf': logf, 'errf': errf, 'cmd': cmd, 't0': time.time()}


# ---------------------------------------------------------------- 退出原因（诊断）
# ★★★★★ 2026-09-21（待办 C 遗留 · 用户："调度器日志里要能看出**为什么**退出"）
#   原状：只有一行 `[END] pool=… gen=… 退出码=… err=…B` +（异常时）一句"疑似崩溃" ✗
#   ⇒ 用户早上来看日志**只能知道崩了、不知道崩在哪** ✗（例如"启动即崩"到底是
#     内存不够 / 权限被挡 / 参数传错 / 数据缺列，全看不出来 ✗）
#   ⇒ 这里把"**退出原因**"拼成一条能读懂的结论：① 退出码语义 ② stderr 关键词 ③ 日志尾部最后一句 ✓
#   并**持久化**（`_engine_exits.log` + 控制文件 `exits` 字段）⇒ 前端以后也能直接显示 ✓
_WIN_RC = {
    3221225477: '访问冲突（0xC0000005）—— 多为 C 扩展/驱动层异常，看 stderr',
    3221225725: '栈溢出（0xC00000FD）—— 递归过深',
    3221225786: '被强制结束（0xC000013A）—— terminate / Ctrl+C 一类',
    3221226505: '快速失败（0xC0000409）—— 运行库检测到致命错误',
    3221225620: '整数除零（0xC0000094）',
    137: '被 SIGKILL —— 多半是内存被杀（OOM）',
    9: '被 SIGKILL —— 多半是内存被杀（OOM）',
    2: '命令行/文件用法错误（argparse）',
    -1: '被信号结束',
}
_ERR_HINTS = (
    ('MemoryError', '内存不足（MemoryError）'),
    ('bad_alloc', '内存不足（bad_alloc）'),
    ('No space left', '磁盘满'),
    ('PermissionError', '权限/占用（PermissionError）—— 常见于杀软或他进程占用同一文件'),
    ('FileNotFoundError', '文件不存在（路径/数据缺）'),
    ('KeyError', '缺列/缺键（数据口径不匹配）'),
    ('ImportError', '依赖导入失败'),
    ('ModuleNotFoundError', '依赖缺失'),
    ('Traceback', 'Python 异常（看 stderr 尾部）'),
)


def _tail_lines(p, n=1, maxlen=110):
    """安全读文件尾 n 行（编码/占用都可能出问题 ⇒ 一律吞掉异常 ✓）。"""
    try:
        if not (p and os.path.exists(p)):
            return []
        with io.open(p, 'r', encoding='utf-8', errors='replace') as f:
            lines = [l.strip() for l in f.read().splitlines() if l.strip()]
        return [l[:maxlen] for l in lines[-n:]]
    except Exception:                                          # noqa: BLE001
        return []


def _exit_reason(rc, errf, logf, killed):
    """把一次异常退出拼成一条可读结论（被用户停的另说 ✓）。"""
    if killed:
        return '被停止（看板/调度器主动停，该代作废、下次重跑）'
    bits = []
    if rc in _WIN_RC:
        bits.append(_WIN_RC[rc])
    elif rc > 1000:
        bits.append('退出码 %d（0x%X，未知 NTSTATUS）' % (rc, rc))
    else:
        bits.append('退出码 %d' % rc)
    etxt = ' '.join(_tail_lines(errf, n=40, maxlen=200))
    for kw, hi in _ERR_HINTS:
        if kw in etxt:
            bits.append(hi)
            break
    last = _tail_lines(errf, n=1) or _tail_lines(logf, n=1)
    if last:
        bits.append('末行: ' + last[0])
    return ' · '.join(bits)


def _log_exit(pool, gen, rc, mins, errsz, killed, why):
    """追加一行到一个**只记退出**的日志（比在 1 MB 调度器日志里翻好找 ✓）。"""
    try:
        os.makedirs(RT.LOGD, exist_ok=True)
        p = os.path.join(RT.LOGD, '_engine_exits.log')
        with io.open(p, 'a', encoding='utf-8') as f:
            f.write('%s  pool=%-5s gen=%-3s rc=%-11s %5.1fmin err=%-7s %s  %s\n'
                    % (time.strftime('%Y-%m-%d %H:%M:%S'), pool, gen, rc, mins, errsz,
                       '被停' if killed else '异常', why))
    except Exception:                                          # noqa: BLE001
        pass


def _reap(t):
    """收一个已结束的任务：打印摘要 + 同样的 GUARD + 判定是否算"本轮真实进展"。"""
    try:
        t['o'].close()
        t['e'].close()
    except Exception:
        pass
    rc = t['pr'].returncode
    mins = (time.time() - t['t0']) / 60.0
    errsz = os.path.getsize(t['errf']) if os.path.exists(t['errf']) else 0
    RT.log('[END]   pool={} gen={} 退出码={} 耗时={:.1f}min err={}B'.format(
        t['pool'], t['gen'], rc, mins, errsz))
    ok = True
    try:
        txt = RT.read_log(t['logf'])
        import re
        for pat in (r'入库 \d+ 个新因子[^\n]*', r'L2 通过 \d+/\d+ 个[^\n]*',
                    r'保存状态: [^\n]*'):
            mm = re.findall(pat, txt)
            if mm:
                RT.log('        ' + mm[-1][:150])
        # ★ 与轮转调度器同款守卫：**直接核验命令里有没有"池内判定"那组 flag**
        #   （不用 `fail_calmar` 之类的间接量 —— 那类传感器曾失真导致必然误报）
        _need = ['--pool_obs', '--min_pool_calmar', '--pool_gate_or_all']
        _miss = [f for f in _need if not any(x.startswith(f) for x in t['cmd'])]
        if _miss:
            RT.log('        [!][GUARD] 本池**漏传**池内判定的必要参数: {}'.format(', '.join(_miss)))
        # ★ 2026-09-19（第 2 步用）：本代**入库个数** ⇒ 决定要不要立刻补 pool-local 数据 ✓
        _bm = re.findall(r'入库 (\d+) 个新因子', txt)
        t['banked'] = int(_bm[-1]) if _bm else 0
        if re.search(r'入库 0 个新因子', txt):
            RT.log('        [note] 本代入库 0（连续多代如此先看 fail_* 分布再下结论）')
    except Exception:
        pass
    t['crashed'] = False
    if rc != 0 or errsz > 0:
        ctl = RT.read_ctl()
        killed = bool(ctl.get('stopAll')) or (t['pool'] in set(ctl.get('stopped') or []))
        # ★ 2026-09-16：把"是不是被用户停的"**带出去**给调用方（用来触发"本轮不再补位"）✓
        t['killed'] = bool(killed)
        # ★ 2026-09-17：**崩溃**（不是被用户停的）⇒ 调用方**本轮就重试**（不必等下一轮）✓
        t['crashed'] = not killed
        # ★★★★★ 2026-09-21（待办 C 遗留）：把"**为什么退出**"写成一条结论 ✓
        #   三处落地：① 调度器日志一行（人看 ✓）② `_engine_exits.log` 专档（好翻 ✓）
        #            ③ 控制文件 `exits` 字段（结构化，前端以后能直接显示 ✓）
        _why = _exit_reason(rc, t['errf'], t['logf'], killed)
        t['exit_reason'] = _why
        RT.log('[退出原因] pool={} gen={} rc={} :: {}'.format(t['pool'], t['gen'], rc, _why))
        _log_exit(t['pool'], t['gen'], rc, mins, errsz, killed, _why)
        try:
            _ex = dict((RT.read_ctl() or {}).get('exits') or {})
            _ex[t['pool']] = {'gen': t['gen'], 'rc': rc, 'killed': bool(killed),
                              'at': time.strftime('%Y-%m-%d %H:%M:%S'),
                              'reason': _why[:200]}
            RT.write_ctl(exits=_ex)
        except Exception as _e2:                                # noqa: BLE001
            RT.log('        [warn] 退出原因写控制文件失败: {!r}'.format(_e2))
        RT.log('[!] pool={} 本代非正常结束{} -> **只跳过本池本轮**。人工看 {}'.format(
            t['pool'], '（★ 被用户停止，该代作废下次重跑）' if killed else '（疑似崩溃）',
            os.path.basename(t['errf'])))
        ok = False
        if not killed:
            # ★★★★ 2026-09-17（用户实测："几个池子显示蓝点、只有 300 是绿点，像轮转"）：
            #   **崩溃必须在看板上看得见**！以前只写在日志里 ⇒ 池子每代秒崩、卡片却照旧显示
            #   "并行中"（蓝点），用户完全无从发现 ✗✗（这次就是被这个坑耽误了一整晚）
            #   ⇒ 把各池最近几次"启动即崩"的代数**结构化写进控制文件**，前端在卡片上红字提示 ✓
            try:
                _cr = {k: list(v)[-3:] for k, v in (ctl.get('crashes') or {}).items()}
                _g = list(_cr.get(t['pool']) or [])
                if t['gen'] not in _g:
                    _g.append(t['gen'])
                _cr[t['pool']] = _g[-3:]                      # 只留最近 3 次，别让文件长草
                RT.write_ctl(crashes=_cr)
            except Exception as _e:                           # 记不上也不能影响调度 ✓
                RT.log('        [warn] 崩溃计数写控制文件失败: {!r}'.format(_e))
    else:
        # ★★★★★ 2026-09-20（用户："中证500 怎么启动即崩了？"）：**跑通一代就撤掉该池的崩溃标记** ✓
        #   原先这个标记**只追加、从不清除** ✗ ⇒ 早上 10:26 那一次**偶发**崩溃
        #   （`PermissionError [WinError 5]`：写 `loop_state_500.pkl.tmp` 原子替换时被文件锁挡住 ✗
        #    —— Windows 上杀软 / 索引器 / 别处在读该 pkl 的进程抢锁，durable 环境噪声 ✓）
        #   会让 500 的卡片**一直**挂"启动即崩"红字 ✗✗（实际它此后 gen74/75/76 全部 rc=0 ✓）
        #   ⇒ 语义修正：这个徽标表示"**此刻启动即崩**" ⇒ 成功一代即撤 ✓；
        #     真·必崩的池每代都会崩 ⇒ 标记立刻被重新写上 ⇒ 照样看得见 ✓（能力不减 ✗）
        try:
            ctl = RT.read_ctl()
            _cr = {k: list(v)[-3:] for k, v in (ctl.get('crashes') or {}).items()}
            if _cr.pop(t['pool'], None) is not None:
                RT.write_ctl(crashes=_cr)
                RT.log('        [清除] pool={} 跑通一代 ⇒ 撤掉启动即崩标记 ✓'.format(t['pool']))
        except Exception:                                     # 撤不掉也不能影响调度 ✓
            pass
    return ok


MAX_CRASH_RETRY = 2    # ★ 某池"启动即崩"时**本轮**最多重试几次（2026-09-17；防必崩时无限刷屏）

MIN_FREE_GB = 3.0      # 系统余量（留 3 GB 不碰；看板 `mine.MIN_FREE_GB` 同值 ✓）

# ★★★★★ 2026-09-23（用户："统一口径"）：**槽位口径 = 单一事实源**（本文件这一处）★
#   以前同一台机器上有**三套算法**，答案自然不一样 ✗：
#     · 看板**启动那一刻**：`GB_PER_ENGINE_SHARED`(3.0) 或 `GB_PER_ENGINE`(9.0) ⇒ 会算出 5 个 ✗
#     · 看板**内存护栏**：又是 `max(mem_per_engine, 3.0)` ⇒ 第三个答案 ✗
#     · 调度器**运行期**：`(free − 3.0) // --mem_per_engine`（**连面板惩罚都没有** ✗）
#     · 看板**显示**：读命令行 `--max_parallel`（= 启动时的天花板，不是此刻真能开几个 ✗）
#   实测症状（用户截图）：小字写"同时最多 **1** 个引擎"，而真实上限是 **2** ✗ —— 他就是被这个绊住的 ✓
#   ⇒ 现在两边**都调下面两个纯函数**（`per_engine_gb` / `slot_cap`）✓
#   ⚠ 为什么放在本文件：它本来就是"并行调度"的所在 ✓ 且纯 stdlib（看板后端 import 它零成本 ✓）
PANEL_GB = 4.42        # 面板（只读 memmap）一份的大小；**面板缓存关着**时每个引擎各建一份 ✗


def per_engine_gb(mem_per_engine, panel_cache='use'):
    """★ 单一事实源：**一个引擎该按多少 GB 算** ✓

    = `--mem_per_engine`（每进程**私有**预算；实测私有峰值 ≈ 7.7 GB，见 v1.21.27）
      ＋ 面板缓存**关着**时再加一整份面板（`PANEL_GB`，每个引擎各建一份 ✗）

    ⚠ 运行期原来**漏了这一项** ✗ —— 面板缓存关着时它仍只按 `--mem_per_engine` 判内存，
      而引擎实际要多花 4.42 GB ⇒ 有 OOM 风险 ✓（本版一并修 ✓）
    """
    p = float(mem_per_engine or 0.0)
    if str(panel_cache or '').strip().lower() == 'off':
        p += PANEL_GB
    return p


def slot_cap(free_gb, n_pools, mem_per_engine, panel_cache='use', min_free_gb=MIN_FREE_GB):
    """★ 单一事实源：**能同时跑几个引擎** —— 「启动时」（看板）与「运行期」（调度器）共用 ✓

        槽位 = max(1, min(可跑池数, floor((可用内存 − 余量) / 每引擎预算)))

    `free_gb is None`（测不出内存）⇒ 保守给 `min(池数, 3)` ✓（不因"测不出"而卡死 ✗）
    """
    n = max(1, int(n_pools or 1))
    if free_gb is None:
        return max(1, min(n, 3))
    per = max(per_engine_gb(mem_per_engine, panel_cache), 0.5)   # 防 0/负预算 ⇒ 除零 ✓
    return max(1, min(n, int((float(free_gb) - float(min_free_gb)) // per)))


def _eff_max(max_parallel, auto_parallel, en, st, mem_per_engine, panel_cache='use'):
    """★ **有效并行上限**（2026-09-16 用户实测「加的池只排队、不并行」后新增）。

    `--auto_parallel=1`（看板默认）⇒ **每次迭代重算**：
        `min(可跑池数, floor((可用内存 - 余量) / 每引擎预算))`，至少 1
      ⇒ "能开几个开几个、快爆就少开"（用户要的语义）✓ ；池子加进来 ⇒ 上限**自动跟着长** ✓
    非 auto ⇒ 直接用 `--max_parallel`（显式指定，一动不动）✓

    ⚠ 它只决定"**要不要起新引擎**"；**已经在跑的绝不因上限变小而被杀**（宁慢不炸）✓

    ★★★★★ 2026-09-23（"统一口径"）：算法搬进 `slot_cap()` ⇒ **与看板启动那一刻同一个公式** ✓
       并且**补上了面板惩罚**（`per_engine_gb` ⇒ 面板缓存关着时"每引擎"要算上 4.42 GB ✓）。
    """
    if not auto_parallel:
        return max_parallel
    runnable = len([p for p in en if p not in st])
    free = avail_gb()
    if free is None:
        return max(1, min(runnable, max_parallel))
    return max(1, min(runnable, slot_cap(free, runnable, mem_per_engine, panel_cache)))


def fair_order(cand, gens, last_start, min_gens_per_round, order=()):
    """★★★ 2026-09-23 新增：候选池的**公平排队**（纯函数 ⇒ 可单测 ✓，见 `tools/_test_sched_fair.py`）。

    为什么加（**真 bug**，用户 2026-09-23 实测发现 ✓）：
        用户："1000 池跑了 6 代，500 才跑 1 代？出问题了吧"
      真因不在引擎、不在内存，而在**候选顺序** ✗：
        · 候选原来来自 `en`（**`set`** ⇒ 迭代顺序**任意**，且在同一进程里**固定不变** ✗）
          —— 上一行注释写着"顺序按 `enabled` 列表，稳定"✗，**代码与注释不符** ✗✗
        · 而启动**只取 `cand[0]`** ⇒ 每当一个槽位空出来，**排在前面的那个池每次都抢到** ✗✗
        · 更要命：它**从不看 `gens`** —— 谁欠本轮配额、谁等得久，一律不看 ✗
      实测后果（3 池 + 并行上限 2 ⇒ 必然有池排队）：
        09-22 22:47 → 09-23 08:18（**9.5 小时**）：500 只跑 1 代（gen94 ✓），
        而 300 连跑 **13 代**（gen170→182 ✗✗）；日志实证"**槽位刚空就被抢**"：
        `00:25:07 [END] pool=500` ⇒ `00:25:07 [START] pool=300` ✗
      危害不止"不公平"：**收轮判据 = 每个启用池都完成 ≥ `min_gens_per_round` 代**
        ⇒ 被饿的池永远攒不够 ⇒ `cand` 永不为空 ⇒ **轮末全局收尾**（跨池审查 / 精选池 /
        登记表重导）**一直不执行** ✗✗（正是 v1.21.18 治过的症状，换了个入口复发 ✗）

    排序键（先欠账 → 再 FIFO → 最后"没跑过的先上"）：
        ① `gens[p] >= min_gens_per_round` —— **False（还欠本轮配额）排最前** ✓
           为什么：欠账的池**卡着收轮** ✗；已跑够的池只是"顺带多挖" ✓
        ② `last_start[p]`（本轮**上次启动时刻**；没启动过 = `0.0` ⇒ 最前）—— **谁等得久谁先** ✓
           为什么：这是"**刚跑完就立刻又抢槽位**"的解药 ✓（它的 `last_start` 最新 ⇒ 排最后 ✓）
        ③ `gens[p]` · ④ `order` 里的位置 —— 只为**确定性**（同分时**不看运气** ✓）

    ⚠ **不改变既有语义**（只排序：候选集合一个不增不减 ✓）：
        · "快池照旧一直领活" ✓ —— 慢池**在跑**时它压根不在候选里，立刻领 ✓
        · 只有"**欠账池正在排队等槽位**"时，快池才让位 ✓（这才是用户要的公平 ✓）
    """
    idx = {p: i for i, p in enumerate(order)}
    return sorted(cand, key=lambda p: (gens.get(p, 0) >= min_gens_per_round,
                                       last_start.get(p, 0.0),
                                       gens.get(p, 0),
                                       idx.get(p, 99)))


def _running_brief(running, now):
    return ' | '.join('%s gen%d(%.0fmin)' % (t['pool'], t['gen'], (now - t['t0']) / 60.0)
                      for t in running) or '无'


def run(pools, rounds, n, l2, extra, inject_spec, no_global,
        max_parallel=3, mem_per_engine=3.0, panel_cache='off', dry=False,
        auto_parallel=False, gens_per_round=1, pool_tail=False, min_gens_per_round=3):
    """有界并行跑 `rounds` 轮；返回进程退出码。

    ★★★★ 2026-09-19 新增两个开关（用户："为什么要等三个池一起挖完才审查？不能一个池挖完就
    马上审查、然后接着挖？那样效率不是更高？"）：
      · `gens_per_round=K`（**第 1 步**）—— 每池每轮连跑几代：
        `K>=1` ⇒ 定量的 K 代；**`K=0` ⇒ 不限**（默认 ✓，用户 09-19 拍板："500 跑一代，
        50 应该能跑七八代"）——语义 = 谁跑完谁**接着领下一代**，直到**别的启用池都已完成 1 代**
        才收轮 ✓（于是快池几乎不空转，轮长仍由最慢的池决定 ✓）
     · ★★★★ **2026-09-20（方案 B，用户："最少的都跑 3 代了，按理说应该至少 3 轮了"
       ⇒ "按方案 B 改掉收轮判据"）**：上面这条"1 代"的判据被**证伪** ✗ ——
       它配合下面那句 `or bool(_others)` ⇒ 只要还有别的池在跑，刚跑完的池就立刻重排队
       ⇒ `cand` 永不为空 ⇒ 内层唯一出口 `not running and not cand` 几乎永不成立
       ⇒ **轮永远收不了口** ✗（实测：本轮 4.5 小时、25 代，`round` 仍 = 1 ✗；
       而**轮末全局收尾**因此从不执行 ✗ —— 跨池审查/精选池/指标表/**登记表重导**/
       剥风格/风格画像，实测上次是 09:37，之后 9 小时没跑 ✓）
       ⇒ 新判据 = **每个启用池都完成 `min_gens_per_round` 代（默认 3 ✓，可用
       `--min_gens_per_round=` 调）才收轮** ✓：收口前快池**照旧一直领** ✓（09-19 的
       诉求不丢 ✓），最慢的池攒够 K 代后不再重排队 ⇒ 等它跑完 ⇒ 自然 break ⇒ 收尾 ⇒ round+1 ✓
      · `pool_tail=True`（**第 2 步**）—— 某池本代**真有入库**时，**立刻**为它补 pool-local 数据
        （facs 落地 / 指标表 / 曲线三段 ✓）。为什么可并发：这三段都**按因子落文件**
        （`facs/*.h5`、`docs/factor_curves/*.json`）⇒ 不同池的文件**互不相干** ✓；
        而**聚合文件**（登记表 / 跨池审查 / 精选池）仍留在轮末由 `do_global_tail` 统一做 ✓
        ⇒ 于是"挖到因子 ⇒ 几分钟内就有指标和曲线"，不必等到整轮结束 ✓
    """
    plan = []
    for p in pools:
        g0, done = RT.next_gen(p)
        plan.append((p, g0, done))
    RT.log('=' * 76)
    RT.log('★★ 并行模式: 池={} 每池 {} 轮 | 并行上限={}{} | 每引擎预算={:.1f} GB | '
           '面板缓存={}'.format(pools, rounds, max_parallel,
                            '（**自动**：按可用内存与启用池数动态定）' if auto_parallel else '',
                            mem_per_engine, panel_cache))
    if auto_parallel:
        RT.log('   ★ 上限会自动放宽：**你随时点「启动本池」加池，只要有内存就会立刻并行开起来** ✓'
               '（加池不需要重启调度器）')
    RT.log('   可用内存 {:.1f} GB'.format(avail_gb()))
    if panel_cache == 'off':
        RT.log('   [!] 面板缓存关着：每个引擎会**各建一份 4.42 GB 面板** ⇒ '
               '并行 N 个 = N 份 ⇒ 建议加 --panel_cache=use（先跑 tools/build_panel_cache.py）')
    RT.log('=' * 76)
    if dry:
        RT.log('（--dry：只列计划，不执行）')
        return 0

    RT.write_ctl(running=True, round=0, rounds=rounds, phase='mine',
                 enabled=[p for p, _, _ in plan] or list(pools), curPool=None, curGen=None)
    dirty = False
    stopped_by_user = False
    running = []
    last_brief = 0.0
    try:
        for rnd in range(1, rounds + 1):
            ctl = RT.read_ctl()
            if ctl.get('stopAll'):
                RT.log('[CTL] ★ 收到「全部停止」⇒ 结束轮转（随后自动收尾）')
                stopped_by_user = True
                break
            en = set(ctl.get('enabled') or [p for p, _, _ in plan])
            st = set(ctl.get('stopped') or [])
            if not en:
                RT.log('[CTL] 启用池为空 ⇒ 无池可跑，结束轮转')
                break
            RT.log('')
            RT.log('#' * 76)
            RT.log('## 第 {} / {} 轮   启用池={}   本轮停={}   并行上限={}{}'.format(
                rnd, rounds, sorted(en), sorted(st) or '无',
                _eff_max(max_parallel, auto_parallel, en, st, mem_per_engine, panel_cache),
                '(自动)' if auto_parallel else ''))
            RT.log('#' * 76)
            # ---- ★★ 本轮状态：**动态队列**（不是"轮初拍死的列表"）----
            #   ★ 2026-09-16 二次修订（用户实测："我停止一个池然后重新启动，怎么没马上开挖？"）：
            #     并行运行中「启动本池」必须**马上生效** ⇒ 每轮迭代**重新算候选**：
            #     本轮还没启动过、现在仍在启用集、且没被停的池，都能立刻上 ✓
            #   ★★ 同时保住上一版要求（"我停一个池，别自动把闲置池顶上来"）：
            #     `deferred` 记录"本轮不自动补位"的池，并记下**顺延那一刻的 stopped 快照**；
            #     ★ 只有"**你在 stopped 里、之后又被「启动本池」放回来**"的池才允许马上上
            #       ⇒ 既不会自动顶上来，又让你手动加的那个立刻开挖 ✓✓
            launched = set()                 # 本轮已启动
            gens = {}                        # ★ 2026-09-19（第 1 步）：池 -> 本轮已完成代数（到 K 就收手 ✓）
            last_start = {}                  # ★ 2026-09-23：池 -> 本轮**上次启动时刻**（公平排队用 ✓，见 fair_order）
            retries = {}                     # ★ 池 -> 本轮"崩溃重试"已用次数（见 `MAX_CRASH_RETRY`）
            deferred = {}                    # 池 -> 顺延那一刻的 stopped 快照（用来认"你重新启用"）
            ran_round = False
            while True:
                ctl = RT.read_ctl()
                if ctl.get('stopAll') and not stopped_by_user:
                    stopped_by_user = True
                    RT.log('[CTL] ★ 收到「全部停止」⇒ 不再补新任务，等在跑的 {} 个自然结束'.format(
                        len(running)))
                # ★ 启用集/剔除集**每轮迭代重读**（用户随时可能加/停池）—— 放在最前面，下面都要用
                # ★★★ 2026-09-23：同时留一份**有序**名单 `_en_list`（= 控制文件 `enabled` 的书写顺序 ✓）
                #   —— 原来只有 `en`（**set** ✗）却拿它当候选顺序 ⇒ "谁抢到槽位靠运气" ✗✗
                #   （真 bug；判断与排序见 `fair_order` ✓）
                _en_list = list(ctl.get('enabled') or [p for p, _, _ in plan])
                en = set(_en_list)
                st = set(ctl.get('stopped') or [])
                # ★★★ 有效并行上限：`--auto_parallel` 时**每次都按"当前启用池数 + 可用内存"重算**
                #   2026-09-16 用户实测：「点一个启动、再点一个池子，怎么是加入轮转而不是并行？」
                #   ⇒ 真因之二：并行数是**启动那一刻按 `len(pools)` 算死的**（1 个池 ⇒ `--max_parallel=1`）
                #     ⇒ 后来加的池**永远只能排队**（哪怕内存富余）✗ ⇒ 现在 auto 模式下**动态放宽** ✓
                eff_max = _eff_max(max_parallel, auto_parallel, en, st, mem_per_engine, panel_cache)
                if stopped_by_user:
                    for p in en:
                        if p not in launched:
                            deferred[p] = set(st)
                # ---- 收割已结束的 ----
                for t in list(running):
                    if t['pr'].poll() is not None:
                        if _reap(t):
                            ran_round = True
                            dirty = True
                            # ★★★ 2026-09-19（第 1 步）：本代**成功** ⇒ 记数；再决定要不要接着领下一代 ✓
                            #   · `gens_per_round >= 1`（定量的 K）⇒ 没到 K 代就回候选 ✓
                            #   · `gens_per_round == 0` ⇒ **不限**：只要**别的启用池还没跑完 1 代**，
                            #     就继续领 ✓（实测动机：500 一代 30-43 分钟，而 50 一代 3-8 分钟
                            #     ⇒ 用户说得对——500 跑一代的工夫，50 该能跑七八代 ✗ 而不是干等 ✓）
                            _gp = t['pool']
                            gens[_gp] = gens.get(_gp, 0) + 1
                            if gens_per_round >= 1:
                                _again = gens[_gp] < gens_per_round
                            else:
                                _need_r = [x for x in en if x not in st]
                                # ★★★★★ 2026-09-19（用户拍板："慢池还在跑 ⇒ 快池就继续领活，
                                #   对，就这样"）—— 在原条件上**再加一条**：
                                #   只要**别的启用池此刻还有引擎在跑**（= 轮还没收口 ✓），
                                #   快池就**继续领下一代** ✓
                                #   为什么必须加：原条件只看"有没有池还没跑完第 1 代" ✗ ⇒
                                #   **所有池都≥1 代之后，快池就空转了** ✗
                                #   实录（14:09）：50 刚跑完 gen41 就空着，而 300 的 gen88 还在跑
                                #   ⇒ 并行上限 3 却只用了 1 个槽位 ✗（50 一代 4~6min、300 一代 20~40min
                                #   ⇒ 这段等待本该产出 5~8 代 ✓）
                                #   ⚠ 不改变"轮长由最慢的池决定"（收轮仍要等所有在跑的引擎结束 ✓）
                                _others = [x for x in running
                                           if x.get('pool') != _gp and x.get('pool') not in st]
                                # ★★★★★ 2026-09-20（方案 B ✓ 用户："最少的都跑 3 代了，
                                #   按理说应该至少 3 轮了" ⇒ "按方案 B 改掉收轮判据"）：
                                #   收轮判据 = **每个启用池都完成 >= min_gens_per_round 代**
                                #   （默认 3 ✓）—— 原来那句 `or bool(_others)`（09-19 加 ✓）
                                #   会让"刚跑完的池"在**还有别的池在跑时立刻重排队** ⇒
                                #   `cand` 永不为空 ⇒ 内层唯一出口 `not running and not cand`
                                #   几乎永不成立 ⇒ **轮永远收不了口** ✗ ⇒ **轮末全局收尾
                                #   从不执行** ✗（跨池审查/精选池/指标表/登记表重导/剥风格/
                                #   风格画像；实测上次 09:37，之后 9 小时没跑 ✓）
                                #   效果：收口前快池**照旧一直领** ✓（12 代也行 ✓）；
                                #   最慢的池也攒够 K 代后 ⇒ 不再重排队 ⇒ 等它跑完 ⇒
                                #   `running` 清空 ⇒ break ⇒ 全局收尾 ⇒ round + 1 ✓
                                _again = any(gens.get(x, 0) < min_gens_per_round
                                             for x in _need_r)
                            if _again:
                                launched.discard(_gp)
                            RT.write_ctl(gensRound=dict(gens))      # ★ 看板进度随即刷新 ✓
                            # ★★★ 2026-09-19（第 2 步）：本代**真有入库** ⇒ 立刻补该池的
                            #   pool-local 数据（facs 落地 / 指标表 / 曲线）⇒ 挖到就能马上看 ✓
                            #   ⚠ 只在"有入库"时跑（`--only-new` 增量本来也是几秒 ✓）⇒ 平时零开销 ✓
                            if pool_tail and t.get('banked'):
                                try:
                                    RT.do_pool_tail(_gp, 'gen{} 入库 {} 个'.format(
                                        t['gen'], t['banked']))
                                except Exception as _e:      # noqa: BLE001
                                    # ★★★★ 2026-09-20（教训）：**只记异常类型** ✗ ⇒
                                    #   一个 `NameError` 被吞成一行温和日志 ⇒ 功能全废却浑然不觉 ✗✗
                                    #   ⇒ 必须把**异常信息**也打出来 ✓（traceback 首行足够定位 ✓）
                                    import traceback as _tb
                                    RT.log('      [!] 池内收尾失败({}: {}) -> 继续挖掘'.format(
                                        type(_e).__name__, str(_e)[:160]))
                                    try:                      # ★ 取末行；取不到就算了（别在错误路径再炸 ✗）
                                        _ln = _tb.format_exc().strip().splitlines()[-1]
                                    except Exception:         # noqa: BLE001
                                        _ln = ''
                                    RT.log('      [!] 定位用：' + _ln[:160])
                        if t.get('killed') and len(deferred) == 0 and not stopped_by_user:
                            _st0 = set(RT.read_ctl().get('stopped') or [])
                            for p in en:
                                if p not in launched:
                                    deferred[p] = set(_st0)
                            RT.log('[CTL] ★ 检测到「单独停止」⇒ **本轮不再自动补位**：'
                                   '就保持"停完剩下的 {} 个"在跑；空出来的槽**留给你自己决定**'
                                   '（「启动本池」的那个会**马上**开挖）✓'.format(len(running) - 1))
                        running.remove(t)
                        # ★★★★ 2026-09-17 修（用户实测："只有 300 池是绿点在跑，但显示有 2 个池在挖"）：
                        #   收割后**立刻按当前在跑集合重写 `active`** —— 否则控制文件里会残留
                        #   **已死引擎**的 `{pool, gen, pid}`（原来只在"启动新引擎"时才写它）✗
                        #   ⇒ 看板/鼠标提示会拿旧列表撒谎（后端另有一道"按活进程核对"，双保险）✓
                        RT.write_ctl(active=[{'pool': x['pool'], 'gen': x['gen'], 'pid': x['pr'].pid}
                                             for x in running])
                        # ★★ 2026-09-17：**崩了的池本轮就重试**（用户在"蓝点"上白等过一整晚）——
                        #   原来崩掉也记 `launched` ⇒ 该池要等到**下一轮**（可能半小时后）才再试 ✗
                        #   ⇒ 现在按 `MAX_CRASH_RETRY` 次重试（防"必崩"时无限重启刷屏）✓
                        if t.get('crashed'):
                            _n = retries.get(t['pool'], 0)
                            if _n < MAX_CRASH_RETRY:
                                retries[t['pool']] = _n + 1
                                launched.discard(t['pool'])
                                RT.log('[CTL] ★ pool={} 本代崩溃 ⇒ **本轮立刻重试**（第 {}/{} 次）'
                                       '；若一直崩，看它的 *_err.log（别再干等下一轮）✗'.format(
                                           t['pool'], _n + 1, MAX_CRASH_RETRY))
                            else:
                                RT.log('[CTL] pool={} 本轮已崩 {} 次 ⇒ 不再重试（留到下一轮）；'
                                       '**先看 *_err.log 的 traceback** ✗'.format(
                                           t['pool'], MAX_CRASH_RETRY))
                # ---- 动态候选（★ 每次迭代重算）----
                # ★★★ 候选来自**当前启用集**，不是启动时的 `--pools` 快照！
                #   2026-09-16 用户实测「点了一个启动、再点一个池子启动，怎么是加入轮转而不是并行？」
                #   ⇒ 真因：`plan` 是**启动时 `--pools=300` 拍死的** ⇒ 后来加的池**既不在候选、也不在队列**
                #     ⇒ **永远不会**在这个调度器里跑（连下一轮都不会）✗✗（我上一版只在"重启路径"测过，
                #     漏了"已有调度器在跑时加池"，测试盲区）
                #   ⇒ 现在：候选 = `en - stopped - 本轮已启动`（★ 2026-09-23 起：顺序由 `fair_order` 定 ✓）
                #     ⚠ 曾经这里写"顺序按 `enabled` 列表，稳定"，而代码遍历的是 **`en`（set）** ✗
                #       ⇒ 注释与实现不符 ⇒ 排到前面那个池**每次都抢到空槽** ✗✗（真 bug，见 `fair_order` ✓）
                cand = [p for p in _en_list
                        if p not in launched and p not in st
                        and (p not in deferred
                             or (p in deferred[p] and p not in st))]   # ★ 你放回来的 ⇒ 允许马上上
                # ★★★★★ 2026-09-23（用户："1000 池跑了 6 代，500 才跑 1 代？出问题了吧"）：
                #   **欠账优先 + 谁等得久谁先**（治"槽位刚空就被同一个池抢走" ⇒ 被饿的池攒不够代
                #   ⇒ 收轮永远收不了口 ⇒ 轮末全局收尾不执行 ✗）—— 详见 `fair_order` ✓
                cand = fair_order(cand, gens, last_start, min_gens_per_round, _en_list)
                if not running and not cand:
                    _left = [p for p in _en_list if p not in launched]
                    if _left:
                        RT.log('[CTL] 本轮剩余 {} 个池未启动（{}）⇒ 留到下一轮'
                               '（下一轮按你保留的启用集重新组队）'.format(len(_left), ' '.join(_left)))
                    break
                # ---- 启动（能开几个开几个；上限 = `eff_max`）----
                while cand and len(running) < eff_max and not stopped_by_user:
                    p = cand[0]
                    ctl = RT.read_ctl()
                    if ctl.get('stopAll'):
                        stopped_by_user = True
                        break
                    en2 = set(ctl.get('enabled') or [p2 for p2, _, _ in plan])
                    st2 = set(ctl.get('stopped') or [])
                    if p not in en2 or p in st2:
                        RT.log('[SKIP] pool={:<5s} {} ⇒ 本轮跳过（不影响其他池）'.format(
                            p, '不在启用集合' if p not in en2 else '已被单独停止'))
                        deferred.setdefault(p, set(st2))     # ★ 不占坑：之后你放回来仍能马上上 ✓
                        cand.pop(0)
                        continue
                    free = avail_gb()
                    # ★ 2026-09-23（"统一口径"）：运行期这道闸也按**同一个** `per_engine_gb` 判 ✓
                    #   （原来只比 `mem_per_engine` ⇒ 面板缓存关着时**漏算 4.42 GB** ✗）
                    _need = per_engine_gb(mem_per_engine, panel_cache)
                    if free < _need:
                        RT.log('[MEM] 可用 {:.1f} GB < 每引擎预算 {:.1f} GB{} ⇒ 等 15s 再试'
                               '（宁慢不炸；内存是这台机器的真瓶颈）'.format(
                                   free, _need,
                                   '（含面板一份 {:.2f} GB）'.format(PANEL_GB)
                                   if panel_cache == 'off' else ''))
                        time.sleep(15)
                        continue
                    cand.pop(0)
                    launched.add(p)                      # ★ 真正启动才记"本轮已启动"
                    last_start[p] = time.time()          # ★ 2026-09-23：公平排队用（FIFO ⇒ 刚跑完的排最后 ✓）
                    gen, done = RT.next_gen(p)           # ★ 每代现取（journal 是唯一事实源）
                    t = _launch(p, gen, n, l2, extra, inject_spec, pools, panel_cache)
                    t['done'] = done
                    running.append(t)
                    # ★ auto 模式下把**当前有效上限**写进控制文件 ⇒ 看板显示的是"真话"（不是启动时的旧值）✓
                    # ★★ 2026-09-19：同时写 `gensRound`（**每池本轮已跑几代**）—— 用户要"各池自己的
                    #   轮次/进度"能滚动显示 ✓（不限模式下 50 一轮能跑七八代，这个数就是它的进度 ✓）
                    _kw = {} if not auto_parallel else {'maxParallel': eff_max}
                    RT.write_ctl(round=rnd, curPool=p, curGen=gen, phase='mine',
                                 gensRound=dict(gens), tailPool=None,
                                 active=[{'pool': x['pool'], 'gen': x['gen'], 'pid': x['pr'].pid}
                                         for x in running], **_kw)
                if running or cand:
                    now = time.time()
                    if now - last_brief > 60:         # 每分钟一条进度（别刷屏）
                        last_brief = now
                        RT.log('[RUN] 第 {} 轮 | 在跑 {} 个: {} | 待启动 {} | 上限 {}{} | 可用 {:.1f} GB'.format(
                            rnd, len(running), _running_brief(running, now), len(cand), eff_max,
                            '(自动)' if auto_parallel else '', avail_gb()))
                    time.sleep(5)
            # ---- 一轮结束 ⇒ 自动收尾（**必须等本轮全部跑完**：跨池审查要求"无人在写 docs/"）----
            #   ⚠ 走到这里保证"没有在跑的、也没有待启动的"（上面 `break` 的条件）⇒ 不必再判 queue ✓
            if ran_round and not no_global:
                RT.do_global_tail('第 {} / {} 轮结束（并行模式）'.format(rnd, rounds))
                dirty = False
            if stopped_by_user:
                break
    finally:
        # ★ 调度器退出前：把还在跑的子进程**收干净**（否则它们会变成无主进程继续吃内存）
        for t in running:
            try:
                if t['pr'].poll() is None:
                    t['pr'].terminate()
            except Exception:
                pass
        for t in running:
            try:
                t['pr'].wait(timeout=30)
            except Exception:
                pass
            try:
                t['o'].close()
                t['e'].close()
            except Exception:
                pass
        if stopped_by_user and dirty and not no_global:
            RT.do_global_tail('★ 全部停止后（并行模式）')
            dirty = False
        RT.write_ctl(running=False, phase='idle', curPool=None, curGen=None,
                     stopAll=False, tailAt=None, active=[])
        RT.log('  [CTL] 调度器退出（已复位控制文件）✓')
    RT.log('===== 全部轨道结束（并行模式）=====')
    return 0
