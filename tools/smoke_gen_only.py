# -*- coding: utf-8 -*-
"""smoke_gen_only.py — 引擎**改动后的快速真机冒烟**（用 `--gen_only`，几秒钟到几十秒）

## 为什么需要它

改引擎时，`py_compile` / 引号检查只能查**语法**，查不出运行期错误；
而一次**真实的一代**要 **50~80 分钟**（`L1` + `L2` 每候选 5 次回测）
⇒ 改完要等一小时才知道有没有 `NameError`，这是**不可接受**的反馈循环。

引擎自带 **`--gen_only`**（`只跑候选生成段验证产量, 不跑 L1/L2 / 不写状态`）
⇒ 正好是为此设计的开关。本脚本把它包一层，做成**可复用、可断言、零副作用**的冒烟：
  ① 跑 `--gen_only`（**不写状态**）
  ② 断言**指定的关键行真的打印了**（`--expect`）
  ③ 断言**无 `Traceback` / `NameError`**
  ④ 断言 **`engine/loop_state*.pkl` 的 SHA256 分毫未动**（万一引擎将来改了 `--gen_only`
     开始写状态，这条会立刻报警 —— 而不是静默污染轨迹）

## 用法

    # 只跑通的冒烟（看有没有崩）
    python tools/smoke_gen_only.py

    # 断言某行必须出现（推荐：新增功能都带一句可审计的打印）
    python tools/smoke_gen_only.py --extra=--parent_sel=top_percent_plus_random \
        --expect="本代亲本策略: parent_sel=top_percent_plus_random" \
        --expect="[亲本] 策略=top_percent_plus_random"

    # 池轨道（会切 state/journal 后缀，仍然不写状态）
    python tools/smoke_gen_only.py --pool=1000 --extra=--inject_pools=300,500

## ⚠ 两个坑（都踩过）

1. **`--llm_jury` 不是这个引擎的参数名** —— 传错会让 argparse 直接退出码 2、
   **一行有用输出都没有**（看起来像"啥都没跑到"）。
2. `--gen` 用一个**远离当前进度**的值（默认 999），避免和真实轨迹的代号混淆。
"""
import argparse
import hashlib
import glob
import os
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
OK = [0, 0]


def chk(cond, msg):
    OK[0] += 1
    if not cond:
        OK[1] += 1
    print('  [{}] {}'.format('OK ' if cond else 'FAIL', msg))


def _sha_map():
    m = {}
    for p in sorted(glob.glob(os.path.join(ROOT, 'engine', 'loop_state*.pkl'))):
        m[os.path.basename(p)] = hashlib.sha256(open(p, 'rb').read()).hexdigest()
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--gen', type=int, default=999, help='代号（默认 999，远离真实进度）')
    ap.add_argument('--n', type=int, default=30, help='候选数（默认 30）')
    ap.add_argument('--pool', default='', help='--mine_pool（如 1000）；默认空=全A')
    ap.add_argument('--extra', default='', help='额外的引擎参数（空格分隔）')
    ap.add_argument('--expect', action='append', default=[],
                    help='必须出现在输出里的字符串（可多次给）')
    ap.add_argument('--timeout', type=int, default=900)
    a = ap.parse_args()

    print('=' * 96)
    print('引擎冒烟（--gen_only：不跑 L1/L2、**不写状态**）')
    print('=' * 96)
    h0 = _sha_map()
    print('  跑前 state: {}'.format(
        ', '.join('{}={}'.format(k, v[:12]) for k, v in h0.items()) or '(无)'))

    cmd = [PY, '-u', 'engine/loop_engine.py', '--gen={}'.format(a.gen),
           '--n={}'.format(a.n), '--gen_only']
    if a.pool:
        cmd.append('--mine_pool={}'.format(a.pool))
    cmd += [x for x in a.extra.split() if x]
    print('  命令: {}\n'.format(' '.join(cmd[1:])))

    env = dict(os.environ, PYTHONIOENCODING='utf-8')
    t0 = time.time()
    try:
        pr = subprocess.run(cmd, cwd=ROOT, capture_output=True, env=env, timeout=a.timeout)
        out = (pr.stdout or b'').decode('utf-8', 'replace')
        err = (pr.stderr or b'').decode('utf-8', 'replace')
        rc = pr.returncode
    except subprocess.TimeoutExpired:
        out, err, rc = '', 'TIMEOUT', -9
    dt = time.time() - t0
    print('  用时 {:.0f}s · 退出码={}\n'.format(dt, rc))

    print('=== 输出里的关键行 ===')
    keys = ('本代参数', '本代亲本策略', '[亲本]', '外部库', '[生成]', 'L1 ', 'Traceback',
            'Error', '保存状态')
    shown = 0
    for l in out.splitlines():
        if any(k in l for k in keys):
            print('  ' + l.strip()[:132])
            shown += 1
            if shown >= 24:
                print('  ...')
                break
    print()

    chk(rc == 0, '退出码 0（实得 {}）'.format(rc))
    chk('Traceback' not in out and 'Traceback' not in err, '无 Traceback')
    chk('NameError' not in out and 'NameError' not in err, '无 NameError')
    for e in a.expect:
        chk(e in out, '断言输出含: {!r}'.format(e[:88]))
    h1 = _sha_map()
    chk(h0 == h1, '★ 全部 loop_state*.pkl **SHA256 未变**'
                  '（`--gen_only` 承诺不写状态；变了 = 冒烟正在污染轨迹，立即查）')

    print('\n' + '=' * 96)
    print('通过 {}/{}'.format(OK[0] - OK[1], OK[0]) + ('' if OK[1] else '  ✓ 全部通过'))
    if OK[1]:
        print('\n--- 输出尾部 40 行（排查用）---')
        for l in (out + '\n' + err).splitlines()[-40:]:
            print('  ' + l[:132])
    return 1 if OK[1] else 0


if __name__ == '__main__':
    sys.exit(main())
