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

    print()
    print('=' * 88)
    print('【B】端到端：--exec_mode=parallel 真跑一次（`--gen_only`，不写状态）')
    print('=' * 88)
    if '--quick' in sys.argv[1:]:
        print('  [SKIP] --quick')
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
