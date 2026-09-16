# -*- coding: utf-8 -*-
"""★★★ 看板「调度模式 / 面板共享」启动参数 回归测试（2026-09-16 新增；`_test_*` ⇒ 进全量回归）。

为什么必须有它：
  用户之问「前端还没把并行切换加上是吧？」的答案曾是"**能力全在 CLI（v1.4.0），缺看板这一层**"。
  现在补齐了 ⇒ 必须钉住三件事，否则会**静默退化**：
  ① **默认行为一行不改**：不传模式参数时，发给 `run_tracks.py` 的命令必须与改造前**逐字一致** ✗
  ② 选了模式/面板共享 ⇒ 必须**真的**出现在命令行里（不是只写进 UI 状态）✗
  ③ **启动参数不能热改** + 内存护栏按模式算（否则"以为切了模式其实没切"/OOM）✗

⚠ 本测试**不起真进程**（用假 `Popen` 只抓命令行），并**快照/还原** `_control.json`（逐字节校验）
  —— 按项目铁律："凡临时改写文件再还原的工具，必须还原后校验" ✓
"""
import hashlib
import io
import json
import os
import sys
import types

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ROOT = r'D:\loop_code'
sys.path.insert(0, os.path.join(ROOT, 'dashboard', 'api'))
sys.path.insert(0, os.path.join(ROOT, 'tools'))

import app.mine as mine          # noqa: E402

FAIL = []


def chk(desc, cond, hint=''):
    print('  %s %s' % ('✓' if cond else '✗', desc))
    if not cond:
        FAIL.append(desc + ('（%s）' % hint if hint else ''))


class FakeProc:
    last = None

    def __init__(self, args, **kw):
        FakeProc.last = list(args)
        self.pid = 999999
        self.returncode = 0


def _sha(p):
    if not os.path.isfile(p):
        return None
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def main():
    ctl_p = mine.CTL_FILE
    before = _sha(ctl_p)
    raw_before = open(ctl_p, 'rb').read() if os.path.isfile(ctl_p) else None
    old_sub, old_time = mine.subprocess, mine.time
    old_sched, old_avail = mine.scheduler, mine.avail_gb
    old_pcdir = mine.PANEL_CACHE_DIR
    try:
        # ⚠ 假 `subprocess` 必须**继承真模块的所有属性**（STDOUT/DEVNULL/run 都要在）⇒ 只替换 Popen ✓
        _fake_sub = types.SimpleNamespace(
            **{k: getattr(old_sub, k) for k in dir(old_sub) if not k.startswith('_')})
        _fake_sub.Popen = FakeProc
        mine.subprocess = _fake_sub
        _fake_time = types.SimpleNamespace(
            **{k: getattr(old_time, k) for k in dir(old_time) if not k.startswith('_')})
        _fake_time.sleep = lambda *a: None
        mine.time = _fake_time

        print('=' * 96)
        print('【1】默认（不传模式参数）⇒ 命令行必须与改造前**逐字一致**（旧行为一行不改）')
        print('=' * 96)
        mine.scheduler = lambda: []
        mine.avail_gb = lambda: 20.0
        r = mine.start(['all'], rounds=5, reset_stopped=True)
        args = FakeProc.last
        chk('命令 = [python, run_tracks.py, --pools=all, --rounds=5]（无新增开关）',
            args[2:] == ['--pools=all', '--rounds=5'], str(args[2:]))
        chk('返回体里 execMode=rotate / panelCache=off（默认）',
            r.get('execMode') == 'rotate' and r.get('panelCache') == 'off')

        print()
        print('【2】并行 + 面板共享 ⇒ 参数**真的**透传到命令行')
        print('=' * 96)
        r = mine.start(['300', '500'], rounds=2, exec_mode='parallel',
                       max_parallel=3, mem_per_engine=2.5,
                       panel_cache='use' if mine.panel_cache_info().get('exists') else 'off')
        args = FakeProc.last
        chk('含 --exec_mode=parallel', '--exec_mode=parallel' in args, str(args[2:]))
        chk('含 --max_parallel=3', '--max_parallel=3' in args)
        chk('含 --mem_per_engine=2.5', '--mem_per_engine=2.5' in args)
        if mine.panel_cache_info().get('exists'):
            chk('含 --panel_cache=use', '--panel_cache=use' in args)
        chk('返回体回显设置（供 UI 显示"实际在跑什么"）',
            r.get('execMode') == 'parallel' and r.get('maxParallel') == 3)

        print()
        print('【3】只用面板共享（轮转模式）⇒ 只加 --panel_cache，**不加**并行开关')
        print('=' * 96)
        pc = 'use' if (mine.panel_cache_info().get('exists')
                       and mine.panel_cache_info().get('sourceOk')) else None
        if pc:
            mine.start(['all'], rounds=1, exec_mode='rotate', panel_cache='use')
            args = FakeProc.last
            chk('含 --panel_cache=use 且**不含** --exec_mode',
                '--panel_cache=use' in args and not any(x.startswith('--exec_mode') for x in args),
                str(args[2:]))
        else:
            print('  [SKIP] 面板缓存不可用 ⇒ 跳过')

        print()
        print('【4】非法取值必须**报错**（不是静默忽略）')
        print('=' * 96)
        for kw, desc in ((dict(exec_mode='bogus'), 'exec_mode=bogus'),
                         (dict(max_parallel=99), 'max_parallel=99'),
                         (dict(mem_per_engine=0.1), 'mem_per_engine=0.1'),
                         (dict(panel_cache='yes'), 'panel_cache=yes')):
            try:
                mine.start(['all'], rounds=1, **kw)
                chk('拒绝 %s' % desc, False, '居然通过了 ✗')
            except mine.MineError as e:
                chk('拒绝 %s ⇒ %s' % (desc, str(e.msg)[:38]), True)

        print()
        print('【5】★ 已在跑时：改**启动参数**必须 409 拒绝（绝不静默 no-op）')
        print('=' * 96)
        mine.scheduler = lambda: [{'pid': 1, 'cmd': 'python tools\\run_tracks.py --pools=all --rounds=5',
                                   'pools': None}]
        try:
            mine.start(['all'], rounds=5, exec_mode='parallel', max_parallel=3,
                       mem_per_engine=3.0, panel_cache='off')
            chk('改模式被拒', False, '居然允许热改 ✗')
        except mine.MineError as e:
            chk('改模式被拒（%s）' % str(e.msg)[:34], e.code == 409)
        # ⚠ 必须传**与当前一致**的参数（否则会被上面那条守卫正当拒绝 —— 实测踩到过 ✓）
        _c = mine.ctl()
        r = mine.start(['all', '300'], rounds=7, exec_mode=_c.get('execMode') or 'rotate',
                       max_parallel=_c.get('maxParallel') or 3,
                       mem_per_engine=_c.get('memPerEngine') or mine.MEM_DEFAULT,
                       panel_cache=_c.get('panelCache') or 'off')
        chk('参数一致 ⇒ 仍然就地更新（reused=True，轮数改到 7）',
            r.get('reused') is True and r.get('rounds') == 7)

        print()
        print('【6】内存护栏**按模式算**（并行 ×N 与轮转不是一个数）')
        print('=' * 96)
        mine.scheduler = lambda: []
        mine.avail_gb = lambda: 8.0
        try:
            mine.start(['all'], rounds=1, exec_mode='parallel', max_parallel=3,
                       mem_per_engine=3.0, panel_cache='use')
            chk('8 GB 可用 ⇒ 拒绝 3×3.0+3.0=12 GB', False, '护栏没生效 ✗')
        except mine.MineError as e:
            chk('8 GB 可用 ⇒ 拒绝并行 ×3（%s）' % str(e.msg)[:30], e.code == 409)
        try:
            mine.start(['all'], rounds=1, exec_mode='rotate', panel_cache='off')
            chk('8 GB 可用 ⇒ 轮转（关面板）也拒绝（需 9+3=12）', False, '护栏没生效 ✗')
        except mine.MineError as e:
            chk('8 GB 可用 ⇒ 轮转（关面板）也拒绝（需 9+3=12）', e.code == 409)
        # ★ 反面：面板共享=use ⇒ 轮转只需 3+3=6 GB ⇒ **同一个内存下应该放行**
        #   （这正说明「面板共享」不是摆设 —— 它真的能把"起不来"变成"起得来"✓）
        if mine.panel_cache_info().get('exists') and mine.panel_cache_info().get('sourceOk'):
            try:
                mine.start(['all'], rounds=1, exec_mode='rotate', panel_cache='use')
                chk('同一个 8 GB 可用 ⇒ 面板共享后轮转**放行**（3+3=6）✓', True)
            except mine.MineError as e:
                chk('同一个 8 GB 可用 ⇒ 面板共享后应放行', False, str(e.msg)[:40])
        else:
            print('  [SKIP] 面板缓存不可用 ⇒ 跳过"共享后放行"这一项')
    finally:
        mine.subprocess, mine.time = old_sub, old_time
        mine.scheduler, mine.avail_gb = old_sched, old_avail
        mine.PANEL_CACHE_DIR = old_pcdir
        # ★ 还原 `_control.json` 并**逐字节校验**（项目铁律）
        if raw_before is not None:
            with open(ctl_p, 'wb') as f:
                f.write(raw_before)
        after = _sha(ctl_p)
        ok = (after == before)
        print()
        print('还原 _control.json: %s' % ('✓ 逐字节一致' if ok else '✗ 不一致 (%s -> %s)' % (before, after)))
        if not ok:
            FAIL.append('_control.json 还原后不一致')

    print()
    if FAIL:
        print('★★ 启动参数回归失败 %d 项：' % len(FAIL))
        for f in FAIL:
            print('   ✗ %s' % f)
        return 1
    print('★★ 看板启动参数回归全部通过 ✓')
    return 0


if __name__ == '__main__':
    sys.exit(main())
