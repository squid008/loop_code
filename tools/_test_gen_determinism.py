# -*- coding: utf-8 -*-
"""守门：**同 seed ⇒ 同结果**（"同 seed A/B"·2026-09-27 新增）。

★ 为什么需要：
  本项目有一条铁律 —— 搬函数/重构后必须跑「**名字解析检查 + 同 seed A/B**」
  （v1.23.0 真事故：只跑回归全绿、真实挖掘却每代崩 ✗）。
  其中"名字解析"已有 `_test_undefined_names.py` ✓，**"同 seed A/B"一直没有自动化** ✗。
  重构最阴的破坏方式之一就是**悄悄引入非确定性**：`set` 迭代顺序、`dict` 顺序、
  漏播种的 `random` / `np.random`、`hash()` 随机化（PYTHONHASHSEED）……
  ⇒ 代码不报错、结果却每次不同（对回测是不可接受的 ✗），而且**单跑一遍永远看不出来** ✗

★ 做法（便宜且真）：用 `--gen_only`（**不跑 L1/L2、不写状态** ✓）同 seed 跑**两遍**，
  逐行比对（剔掉耗时/时刻这类必然不同的噪声 ✓）。指纹里含：
  · `生成候选 30/30 个[正常](跨量纲拦5 失败库拦0 FSA拦0 族黑名单拦0 重复拦1, 尝试36)`
    —— 各拦截计数 + **尝试次数**（对 RNG 流极敏感 ✓）
  · 本代参数 / 五维配比 / 亲本策略 / FSA / 随机探索 的全部数值 ✓
  · 上一代 state 的 B角诊断（种子数/失败库/已测候选 …）✓

★ ⚠ 覆盖边界（如实说）：这**不能**证明"候选集合逐字节相同" ✗ ——
  `--gen_only` 只打印**摘要计数**、不打印 30 条表达式；要逐字节比对得上 L1（~25 分钟 ✗）。
  它能抓到的是"随机性/顺序漂移"这一类 ✓，而这正是重构最容易踩的那一类 ✓。

★ 前提：**挖掘必须已停止** —— 两遍之间若真跑完一代，state 变了 ⇒ 计数必然不同 ⇒ **误报** ✗
  （与"挖掘运行时禁跑全量回归"同源 ✓）。
"""
import io
import json
import os
import re
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable
GEN = 9998            # ★ 远离真实进度
N = 30
FAIL = []


def chk(desc, cond, hint=''):
    print('  %s %s' % ('✓' if cond else '✗', desc))
    if not cond:
        FAIL.append(desc + ('（%s）' % hint if hint else ''))


NOISE = re.compile(r'耗时\s*\d+s|已用\s*\d+s|\d{4}-\d{2}-\d{2}|\d{2}:\d{2}:\d{2}')


def _norm(text):
    return [NOISE.sub('<T>', l).strip() for l in text.splitlines() if l.strip()]


def _run():
    cmd = [PY, '-u', 'engine/loop_engine.py', '--gen=%d' % GEN, '--n=%d' % N, '--gen_only',
           '--seed=777', '--llm_guide=off', '--ai_critic=off', '--ai_jury=off']
    env = dict(os.environ, PYTHONIOENCODING='utf-8')
    t0 = time.time()
    pr = subprocess.run(cmd, cwd=ROOT, capture_output=True, env=env, timeout=900)
    out = (pr.stdout or b'').decode('utf-8', 'replace')
    err = (pr.stderr or b'').decode('utf-8', 'replace')
    return pr.returncode, out, err, time.time() - t0


def _mining_busy():
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


def main():
    print('=' * 96)
    print('同 seed A/B 确定性守门（`--gen_only` 跑两遍 · 不写状态）')
    print('=' * 96)

    print('\n【0】前提：挖掘已停止（否则两遍之间 state 会变 ⇒ 误报）')
    busy = _mining_busy()
    chk('挖掘未在跑', not busy, '在跑：%s' % '; '.join(busy))
    if busy:
        print('\n✗ 拒绝执行（没有动任何文件）')
        return 1

    outs = []
    for tag in ('A', 'B'):
        rc, out, err, dt = _run()
        outs.append(_norm(out))
        print('  第 %s 遍: 退出码=%d · 用时 %.0fs · 有效行=%d' % (tag, rc, dt, len(outs[-1])))
        chk('第 %s 遍退出码 0' % tag, rc == 0)
        chk('第 %s 遍无 Traceback' % tag, 'Traceback' not in out and 'Traceback' not in err)
        chk('第 %s 遍无 NameError' % tag, 'NameError' not in out and 'NameError' not in err)
        chk('第 %s 遍有候选生成摘要' % tag, re.search(r'生成候选 \d+/\d+ 个', out) is not None,
            '摘要是本守门的指纹来源，缺了就没得比 ✗')
        io.open(os.path.join(ROOT, 'ai_test', '_det_%s.log' % tag),
                'w', encoding='utf-8').write(out + '\n' + err)

    print('\n【1】逐行比对')
    a, b = outs
    if len(a) != len(b):
        chk('两遍行数相同', False, 'A=%d B=%d' % (len(a), len(b)))
    else:
        chk('两遍行数相同（%d 行）' % len(a), True)
    diff = [(i, x, y) for i, (x, y) in enumerate(zip(a, b)) if x != y]
    chk('★ 同 seed 逐行完全一致（非确定性 = 回测不可复现 ✗）', not diff)
    for i, x, y in diff[:6]:
        print('      #%d\n        A: %s\n        B: %s' % (i, x[:130], y[:130]))

    _cap = [l for l in a if '生成候选' in l]
    print('\n  本次指纹: %s' % (_cap[-1][:150] if _cap else '(未找到摘要行)'))

    print('\n' + '=' * 96)
    if FAIL:
        print('✗ 失败 %d 项：' % len(FAIL))
        for x in FAIL:
            print('   - ' + x)
        return 1
    print('★ 全过 ✓ 同 seed 两遍逐行一致（未见随机性/顺序漂移）✓')
    return 0


if __name__ == '__main__':
    sys.exit(main())
