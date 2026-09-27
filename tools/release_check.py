# -*- coding: utf-8 -*-
"""release_check.py — **发版前的唯一入口**（一条命令跑完全部闸门）。

## 为什么要有它（2026-09-27 新增）

此前"发版纪律"**只写在文档里** ✗：`change_log.md` 的 v1.21.16 条目写着
"全量回归必须先单独跑完、全绿，再提交/tag/push" —— 但**没有任何脚本保证它被执行** ✗。
回归入口 `ai_test/_run_all_tests.py` 还在 `ai_test/`（一个**约定可随时删**的目录 ✓）
且**自己就是临时脚本** ✗ ⇒ "发版前该跑什么"这件事**依赖人记得** ✗
（v1.23.0 的教训正是"记得跑的不够、该自动的没自动"）。

⇒ 本脚本把纪律落成**一条命令 + 一个退出码**：

    ① **版本一致性**（`VERSION` / `README` / `change_log` / `package.json` / settings …）
    ② **未定义名**（拆分/搬函数最容易漏的那类 `NameError`）
    ③ **全部守门**（`tools/_test_*.py` 串行跑，逐个落日志）
    ④ **汇总**：通过 x/y · 失败清单 · 最慢 3 个 · 总耗时 · 非零退出

## 前提（硬检查，不满足直接拒绝）

**挖掘必须已停止** ✗ —— 两个 heavy 守门（`_test_e2e_l1l2` / `_test_gen_determinism`）
一个会**真写池的轨迹**、一个依赖 **state 在两次运行之间不变**；
且既有的 `_test_dynamic_add` 会写控制文件（与"挖掘运行时禁跑全量回归"同一来源 ✓）。

## 用法

    python tools/release_check.py              # 跑全部
    python tools/release_check.py --list       # 只列会跑哪些
    python tools/release_check.py --only e2e   # 只跑名字含 e2e 的（调试用）

⚠ 定位原则（别把"快"和"全"混了）：本脚本**不代替**人工读 change_log / 写 README 版本表 ✓，
  它只管"机器能判的那部分" ✓。
"""
import argparse
import glob
import io
import json
import os
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable
LOGD = os.path.join(ROOT, 'ai_test', '_release_logs')
TOOLS = os.path.join(ROOT, 'tools')

# ★ 先跑这两个：最便宜、且失败原因最"致命"（版本写错 / 名字没绑）⇒ 早失败早止损 ✓
FAST = [('版本一致性', '_test_version_sync.py'),
        ('未定义名', '_test_undefined_names.py')]


def _mining_busy():
    """挖掘是否在跑（控制文件 + 真进程，两路来源 ✓）"""
    why = []
    try:
        with io.open(os.path.join(ROOT, 'ai_test', '_tracks', '_control.json'),
                     encoding='utf-8') as f:
            c = json.load(f) or {}
        if c.get('running'):
            why.append('控制文件 running=true')
        if c.get('active'):
            why.append('控制文件 active=%r' % (c.get('active'),))
    except Exception:
        pass
    try:
        sys.path.insert(0, os.path.join(ROOT, 'dashboard', 'api'))
        from app import mine as _M                                     # noqa: N812
        _e = _M.engines()
        if _e:
            why.append('真进程里有 %d 个引擎' % len(_e))
    except Exception:
        pass
    return why


def _run_test(name, timeout=1500):
    path = os.path.join(TOOLS, name)
    if not os.path.isfile(path):
        return {'name': name, 'rc': -404, 'dt': 0.0, 'tail': '(文件不存在)'}
    t0 = time.time()
    try:
        pr = subprocess.run([PY, '-u', os.path.relpath(path, ROOT)], cwd=ROOT,
                            capture_output=True, timeout=timeout,
                            env=dict(os.environ, PYTHONIOENCODING='utf-8'))
        out = (pr.stdout or b'').decode('utf-8', 'replace')
        err = (pr.stderr or b'').decode('utf-8', 'replace')
        rc = pr.returncode
    except subprocess.TimeoutExpired:
        out, err, rc = '', 'TIMEOUT(%ds)' % timeout, -9
    dt = time.time() - t0
    logf = os.path.join(LOGD, name.replace('.py', '') + '.log')
    try:
        os.makedirs(LOGD, exist_ok=True)
        io.open(logf, 'w', encoding='utf-8').write(out + '\n--- stderr ---\n' + err)
    except OSError:
        pass
    tail = ''
    for l in (out or '').splitlines()[::-1]:
        if l.strip():
            tail = l.strip()
            break
    if rc != 0 and not tail:
        tail = (err or '').strip().splitlines()[-1] if (err or '').strip() else ''
    return {'name': name, 'rc': rc, 'dt': dt, 'tail': tail[:130]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--list', action='store_true', help='只列出会跑哪些')
    ap.add_argument('--only', default='', help='只跑名字含该子串的')
    a = ap.parse_args()

    tests = sorted(os.path.basename(p)
                   for p in glob.glob(os.path.join(TOOLS, '_test_*.py')))
    if a.only:
        tests = [t for t in tests if a.only in t]
    if a.list:
        print('会跑 %d 个：' % (len(FAST) - 1 + len(tests)))
        for tag, f in FAST:
            print('  [先跑] %-34s (%s)' % (f, tag))
        for t in tests:
            print('  %s' % t)
        return 0

    print('=' * 96)
    print('发版前检查（release_check）—— %s' % time.strftime('%Y-%m-%d %H:%M:%S'))
    print('=' * 96)
    print('  版本单一来源: %s' % io.open(os.path.join(ROOT, 'VERSION'),
                                        encoding='utf-8').read().strip())

    print('\n【0】前提检查：挖掘必须已停止')
    busy = _mining_busy()
    if busy:
        print('  ✗ 挖掘正在跑（%s）' % '; '.join(busy))
        print('  ⇒ 拒绝执行：heavy 守门会真写池轨迹 / 依赖 state 稳定，\n'
              '     且既有守门会写控制文件 ⇒ 先"全部停止"再发版 ✓')
        return 2
    print('  ✓ 挖掘未在跑')

    print('\n【1】先跑快而致命的两个闸门')
    for tag, f in FAST:
        r = _run_test(f)
        print('  %s %-34s rc=%-3d %5.1fs  %s'
              % ('✓' if r['rc'] == 0 else '✗', r['name'], r['rc'], r['dt'], r['tail']))
        if r['rc'] != 0:
            print('\n✗ 快闸门就挂了 ⇒ 先在 %s 里看详情'
                  % os.path.relpath(os.path.join(LOGD, f.replace('.py', '.log')), ROOT))
            return 1

    print('\n【2】全部守门（%d 个，串行；日志在 %s）' % (len(tests), os.path.relpath(LOGD, ROOT)))
    res, t00 = [], time.time()
    for i, t in enumerate(tests, 1):
        r = _run_test(t)
        res.append(r)
        print('  [%2d/%2d] %s %-36s rc=%-3d %6.1fs  %s'
              % (i, len(tests), '✓' if r['rc'] == 0 else '✗', r['name'],
                 r['rc'], r['dt'], r['tail']), flush=True)

    bad = [r for r in res if r['rc'] != 0]
    slow = sorted(res, key=lambda r: -r['dt'])[:3]
    print('\n' + '=' * 96)
    print('通过 %d/%d（总耗时 %.1f 分钟）' % (len(res) - len(bad), len(res),
                                             (time.time() - t00) / 60.0))
    print('最慢: ' + ' · '.join('%s %.0fs' % (r['name'], r['dt']) for r in slow))
    if bad:
        print('\n✗ 失败 %d 个：' % len(bad))
        for r in bad:
            print('   - %-36s rc=%-3d %s' % (r['name'], r['rc'], r['tail']))
            print('     详情: %s' % os.path.relpath(
                os.path.join(LOGD, r['name'].replace('.py', '.log')), ROOT))
        return 1
    print('\n★ 全部通过 ✓ 可以提交 / 打 tag（记得同步 README 版本表与 change_log ✓）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
