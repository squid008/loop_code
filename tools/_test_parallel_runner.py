# -*- coding: utf-8 -*-
"""★★★ 并行调度器 回归测试（2026-09-16 新增；命名 `_test_*` ⇒ 进全量回归）。

为什么要有它：
  ① 并行是**新调度路径**，一旦它把 `--mine_pool`/`--panel_cache` 传错，或忘了 `CREATE_NO_WINDOW`，
     会表现为"归属认不出 / 弹黑窗"这类**看着能跑但功能错**的问题（本项目反复踩过）✗
  ② 更要紧的是**别污染轨迹** —— 测试跑的是真引擎，必须用 `--gen_only`
     （不跑 L1/L2、不写状态）并断言 `loop_state*.pkl` / `loop_journal*.md` **SHA256 未变** ✓

【A】静态断言（毫秒级）
【B】端到端（真跑一次 `--exec_mode=parallel`，用 `--gen_only`；约 1 分钟）
     · 两个池**同时**在跑（driver 日志里 2 个 [START] 早于第 1 个 [END]）= 并行真的生效
     · 退出码 0 · 无 Traceback · state/journal 未被改动
     · `_control.json` 测试前**备份、测试后还原**（它是用户配置，不该被测试改掉）
"""
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PY = sys.executable
RT_PY = os.path.join(HERE, 'run_tracks.py')
PR_PY = os.path.join(HERE, 'parallel_runner.py')
ENG = os.path.join(ROOT, 'engine')
DOCS = os.path.join(ROOT, 'docs')
LOGD = os.path.join(ROOT, 'ai_test', '_tracks')
CTL = os.path.join(LOGD, '_control.json')
FAIL = []


def chk(desc, cond, hint=''):
    print('  %s %s' % ('[OK]' if cond else '[FAIL]', desc))
    if not cond:
        FAIL.append(desc + ('（%s）' % hint if hint else ''))


def sha(p):
    if not os.path.exists(p):
        return 'absent'
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()[:12]


def snapshot():
    out = {}
    for d, pat in ((ENG, 'loop_state'), (DOCS, 'loop_journal')):
        for fn in sorted(os.listdir(d)):
            if fn.startswith(pat) and (fn.endswith('.pkl') or fn.endswith('.md')):
                out[os.path.join(d, fn)] = sha(os.path.join(d, fn))
    return out


def t_ctl_lock():
    """★ 真跑一遍跨进程锁（**在临时路径上**，绝不碰真控制文件 —— 用户可能正在挖 ✗）"""
    print('\n===== 控制文件写锁（真跑；用临时 lock 路径）=====')
    import run_tracks as RT
    old = RT.CTL_LOCK
    tmpd = tempfile.gettempdir()
    RT.CTL_LOCK = os.path.join(tmpd, '_lck_probe.lock')
    try:
        for p in (RT.CTL_LOCK,):
            if os.path.exists(p):
                os.remove(p)
        # 手工"占锁" 0.5s ⇒ 期间调 `_with_ctl_lock` 必须**等**（证明它真走锁，而不是直接写）
        # (a) 别的进程"占锁 0.5s 后放开" ⇒ 本次调用**必须等**，放开后立刻拿到并执行 ✓
        import threading

        def _holder():
            _fd = os.open(RT.CTL_LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(_fd)
            time.sleep(0.5)
            os.unlink(RT.CTL_LOCK)

        _th = threading.Thread(target=_holder)
        _th.start()
        time.sleep(0.1)
        _seen = []
        t0 = time.time()
        RT._with_ctl_lock(lambda: _seen.append(True))
        dt = time.time() - t0
        _th.join()
        chk('拿不到锁时**会等待**（实测等 %.2fs）—— 否则等于没锁 ✗' % dt, dt >= 0.3)
        chk('锁里的函数**真的被执行**了（不是"拿到锁就返回"）', _seen == [True])
        chk('执行完**释放锁**（lock 文件被清掉）', not os.path.exists(RT.CTL_LOCK))
        # (b) 锁**一直被占着**（持有者崩掉那种）⇒ 超时后**照样写**（不卡死调度器/接口）✓
        _fd = os.open(RT.CTL_LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(_fd)
        _seen = []
        t0 = time.time()
        RT._with_ctl_lock(lambda: _seen.append(True))
        dt = time.time() - t0
        chk('★ 锁一直被占 ⇒ 超时后**照样执行**（实测 %.1fs），绝不卡死 ✗' % dt,
            _seen == [True] and dt < 8.0)
        os.unlink(RT.CTL_LOCK)
        # (c) 陈旧锁（>15s 的残留）必须被自动清理，否则一次崩溃就永久卡住所有写
        open(RT.CTL_LOCK, 'w').write('stale')
        _old_t = time.time() - 60
        os.utime(RT.CTL_LOCK, (_old_t, _old_t))
        t0 = time.time()
        _seen = []
        RT._with_ctl_lock(lambda: _seen.append(True))
        chk('★ **陈旧锁**（>15s 残留）会被清掉后立刻拿到（不是干等超时）',
            _seen == [True] and time.time() - t0 < 1.0)
    finally:
        RT.CTL_LOCK = old
        try:
            if os.path.exists(os.path.join(tmpd, '_lck_probe.lock')):
                os.remove(os.path.join(tmpd, '_lck_probe.lock'))
        except OSError:
            pass


def main():
    rt = io.open(RT_PY, encoding='utf-8').read()
    pr = io.open(PR_PY, encoding='utf-8').read()

    print('=' * 88)
    print('【A】静态断言')
    print('=' * 88)
    chk('A1 run_tracks 默认仍是 rotate（**旧行为一行不改**）',
        re.search(r"exec_mode = 'rotate'", rt) is not None)
    chk('A2 run_tracks 有 parallel 分叉（委托给独立模块，不塞逻辑）',
        re.search(r"if exec_mode == 'parallel':", rt) is not None
        and re.search(r'_PR\.run\(', rt) is not None)
    chk('A3 parallel_runner **复用** run_tracks（而不是复制实现）',
        re.search(r'^import run_tracks as RT', pr, re.M) is not None)
    chk('A4 parallel_runner 未重复定义公共件（防两套实现漂移）',
        not re.search(r'^def (log|next_gen|do_global_tail|read_ctl|write_ctl|inject_for)\(',
                      pr, re.M),
        '这些必须来自 run_tracks')
    chk('A5 引擎命令行带 --mine_pool（否则看板认不出归属）',
        "'--mine_pool=%s' % pool" in pr or '--mine_pool=' in pr)
    chk('A6 子进程不弹黑窗（带 NO_WIN）',
        'creationflags=RT.NO_WIN' in pr)
    chk('A7 子进程设 utf-8（否则日志乱码、进度解析失效）',
        "PYTHONIOENCODING'] = 'utf-8'" in pr)
    chk('A8 有内存护栏（启动前查可用内存）',
        'avail_gb' in pr and 'mem_per_engine' in pr)
    chk('A9 面板缓存只在非 off 时才追加到命令行（默认命令与旧版一致）',
        "if panel_cache and panel_cache != 'off':" in pr)
    chk('A10 run_tracks 支持 --engine_arg=（追加，避免 --extra 整体替换的陷阱）',
        re.search(r"a\.startswith\('--engine_arg='\)", rt) is not None)
    # ★★ 2026-09-16 v1.10.1/v1.12.0（用户："停止一个池然后重新启动，怎么没马上开挖？" +
    #   "点了一个启动、再点一个池子启动，怎么是加入轮转而不是并行？"）
    chk('A11 ★★ 动态候选来自**当前启用集**（不是启动时 `--pools` 快照）',
        re.search(r'cand = \[p for p in en', pr) is not None and 'p not in launched' in pr,
        '用 `plan` ⇒ 后来加的池**永远不会**跑（连下一轮都不跑）✗ —— 用户实测到的点')
    chk('A12 ★ 顺延池「被重新启用 ⇒ 允许马上上」（既不自顶、又能手动加）',
        'deferred[p]' in pr and 'p in deferred[p] and p not in st' in pr)
    chk('A13 ★ 「启动本池」马上生效：真正启动才记 `launched`',
        'launched.add(p)' in pr and 'RT.next_gen(p)' in pr)
    chk('A14 ★★ `--auto_parallel`：上限按"当前启用池数 + 可用内存"**动态重算**',
        '_eff_max(' in pr and 'auto_parallel' in pr,
        '启动时按 len(pools) 算死 ⇒ 1 个池启动后加的池只能排队 ✗（用户实测到的点）')
    chk('A15 ★ auto 时把**有效上限**写回控制文件（看板显示的是真话，不是启动时的旧值）',
        "'maxParallel': eff_max" in pr)
    # ★★ 2026-09-17（用户实测："只有 300 池是绿点在跑，但显示有 2 个池在挖" + "几个池蓝点像轮转"）
    chk('A16 ★★ 收割后**立刻重写 `active`**（否则控制文件残留**已死引擎**的 pid ⇒ 看板撒谎）',
        'RT.write_ctl(active=[' in pr,
        '原来只在"启动新引擎"时写 active ⇒ 引擎崩了/被杀后列表永远是旧的 ✗')
    chk('A17 ★★ 崩溃**结构化写进控制文件**（各池 `crashes`）⇒ 前端卡片能提示"启动即崩"',
        'write_ctl(crashes=' in pr and 'crashes=_cr' in pr,
        '只写日志 ⇒ 池子每代秒崩、卡片照旧"并行中"蓝点 ⇒ 用户白等一整晚 ✗（这次实测踩到）')
    chk('A18 ★★ 控制文件写操作**加跨进程锁**（read-modify-write 并发会丢更新）',
        'def _with_ctl_lock(' in rt and '_with_ctl_lock(_do)' in rt,
        '实录：调度器写的 `active` 被后端"停止池"写回的旧快照吞掉 ⇒ 残留已死 pid ✗（锁在 run_tracks）')
    chk('A19 ★★ 崩了的池**本轮就重试**（不干等下一轮，但有次数上限防刷屏）',
        'MAX_CRASH_RETRY' in pr and 'launched.discard' in pr,
        '原来崩掉也记 `launched` ⇒ 要等下一轮（可能半小时）才再试 ✗')
    # ★★★★ 2026-09-17：`--pools` 与 ctl 谁说话（本文件 B4/B5/B6 当场抓到的真副作用）
    chk('A20 ★★ 命令行直跑时以 **`--pools` 为准**（播种 enabled、清残留 stopped）',
        re.search(r"if not from_ctl:\s*\n\s*write_ctl\(enabled=list\(pools\), stopped=\[\]\)", rt)
        is not None,
        'v1.12.0 后候选池全看 ctl ⇒ `--pools` 被无视、还继承上次的 stopped ⇒ 只起 1 个池 ✗')
    chk('A22 ★★ `_test_mine_launch` 也加了**有人在挖就跳过**（否则与真调度器抢 `_control.json` ⇒ 全量误报 ✗）',
        '_real_mining()' in io.open(os.path.join(ROOT, 'tools', '_test_mine_launch.py'),
                                    encoding='utf-8').read(),
        '同一天全量被它误报两次；单独跑全过 ⇒ 真因是并发写同一个控制文件 ✗（不是 metrics/curves）')
    chk('A21 ★★ 看板启动带 `--from_ctl=1`（在 ctl 里写好意图 ⇒ 调度器尊重它）',
        '--from_ctl=1' in io.open(os.path.join(ROOT, 'dashboard', 'api', 'app', 'mine.py'),
                                  encoding='utf-8-sig').read())

    # ★★ 锁测试**必须放在这里**（在 `--quick` / "有人在挖就跳过"两个 early-return **之前**）——
    #    否则用户正在挖的时候这条永远不跑（本次就是在挖的时候发现 A18 挂了才知道 ✗）
    t_ctl_lock()
    print()
    print('=' * 88)
    print('【B】端到端：--exec_mode=parallel 真跑一次（`--gen_only`，不写状态）')
    print('=' * 88)
    if '--quick' in sys.argv[1:]:
        print('  [SKIP] --quick')
        return _report()
    # ★★ 2026-09-17（实测踩到）：**真有人在挖时必须跳过** ——
    #   本测试会**快照/还原 `_control.json`**，而线上调度器读写的**就是同一个文件** ⇒
    #   ① 会误报失败（B4/B6 "[START] 数=1"：ctl 被线上调度器改掉/抢走）
    #   ② ⚠ **更危险**：结束时还原快照 会把用户刚改的状态（enabled/stopped）**改回去** ✗
    #   ⚠ 别用 `try: ctl = RT.read_ctl() except: {}` —— 本文件**没有导入 run_tracks**（它只读源码文本），
    #     `NameError` 会被 `except` 吞掉 ⇒ 判定恒为"没人跑" ⇒ 跳过失效 ✗（实测踩到）
    try:
        _c0 = json.load(io.open(CTL, encoding='utf-8'))
    except Exception:
        _c0 = {}
    if _c0.get('running') or (_c0.get('active') or []):
        print('  [SKIP] 检测到**正在运行的调度器/引擎**（%s）⇒ 本测试会动 `_control.json`，'
              '为避免干扰与误报，直接跳过 ✓'
              % ('running=true' if _c0.get('running')
                 else 'active=%d 个引擎在跑' % len(_c0.get('active') or [])))
        return _report()
    before = snapshot()
    # ★ driver 日志是**跨次累积**的（里面有历史 [START]/[END]）⇒ 必须先记下"本次开始前的行数"，
    #   只分析**本次新增**的片段（否则会把历史串行记录当成本次的 → 断言必然误判 ✗）
    dl_path = os.path.join(LOGD, '_driver.log')
    n0 = (len(io.open(dl_path, encoding='utf-8', errors='replace').read().splitlines())
          if os.path.exists(dl_path) else 0)
    ctl_bak = None
    if os.path.exists(CTL):
        ctl_bak = CTL + '.testbak'
        shutil.copy2(CTL, ctl_bak)
    log_key = '并行模式'
    try:
        cmd = [PY, '-u', RT_PY, '--pools=300,500', '--rounds=1', '--n=30',
               '--exec_mode=parallel', '--max_parallel=2', '--mem_per_engine=2.0',
               '--panel_cache=use', '--no_global', '--engine_arg=--gen_only']
        print('  命令: %s' % ' '.join(cmd[1:]), flush=True)
        t0 = time.time()
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                           encoding='utf-8', errors='replace', timeout=1200)
        dt = time.time() - t0
        out = (r.stdout or '') + (r.stderr or '')
        chk('B1 退出码 0（实得 %s）' % r.returncode, r.returncode == 0,
            (r.stderr or '')[-300:])
        chk('B2 无 Traceback', 'Traceback' not in out)
        chk('B3 日志里确认进入了并行模式', log_key in out)
        # 并行证据：**本次新增**的片段里，[START] 数量 == 池数，且第 2 个 [START] 早于第 1 个 [END]
        dl = io.open(dl_path, encoding='utf-8', errors='replace').read().splitlines()[n0:]
        seg = [ln for ln in dl if ('[START]' in ln or '[END]' in ln)]
        starts = [i for i, ln in enumerate(seg) if '[START]' in ln]
        ends = [i for i, ln in enumerate(seg) if '[END]' in ln]
        chk('B4 两个池都启动了（本次 [START] 数=%d）' % len(starts), len(starts) == 2)
        chk('B5 ★ **真的并行**：第 2 个 [START] 早于第 1 个 [END]（本次片段）',
            len(starts) == 2 and len(ends) >= 1 and starts[1] < ends[0],
            '若成立说明是"有界并行"而不是串行轮转；本次 seg=%d 行' % len(seg))
        chk('B6 两个池都正常结束（本次 [END] 数=%d, 均退出码=0）' % len(ends),
            len(ends) == 2 and len([1 for ln in seg if '[END]' in ln and '退出码=0' in ln]) == 2)
        after = snapshot()
        bad = [k for k in set(list(before) + list(after)) if before.get(k) != after.get(k)]
        chk('B7 ★ state/journal **SHA256 未变**（%d 个文件；gen_only 承诺不写状态）'
            % len(before), not bad, '; '.join(os.path.basename(x) for x in bad[:5]))
        print('  用时 %.0fs' % dt)
    finally:
        if ctl_bak and os.path.exists(ctl_bak):
            shutil.move(ctl_bak, CTL)        # ★ 还原用户的控制文件（enabled/stopped 是**用户配置**）
            print('  [ctl] 已还原测试前的 _control.json ✓')
    t_ctl_lock()
    return _report()


def _report():
    print()
    if FAIL:
        print('★★ 并行调度器测试失败 %d 项：' % len(FAIL))
        for f in FAIL:
            print('   [FAIL] %s' % f)
        return 1
    print('★★ 并行调度器测试全部通过')
    return 0


if __name__ == '__main__':
    sys.exit(main())
