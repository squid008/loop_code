# -*- coding: utf-8 -*-
"""★★★ 看板「调度模式 / 面板共享」启动参数 回归测试（2026-09-16 新增；`_test_*` ⇒ 进全量回归）。

为什么必须有它：
  用户之问「前端还没把并行切换加上是吧？」的答案曾是"**能力全在 CLI（v1.4.0），缺看板这一层**"。
  现在补齐了 ⇒ 必须钉住三件事，否则会**静默退化**：
  ① **默认行为一行不改**：不传模式参数、且控制文件里也没有"上次设置"时 ⇒ 命令行与改造前**逐字一致** ✗
  ② 选了模式/面板共享 ⇒ 必须**真的**出现在命令行里（不是只写进 UI 状态）✗
  ③ **启动参数不能热改** + 内存护栏 + **并行数自动算** + **面板缓存不可用自动降级**（2026-09-16 加强）

⚠ 本测试**不起真进程**（用假 `Popen` 只抓命令行），并**快照/还原** `_control.json`（逐字节校验）
  —— 按项目铁律："凡临时改写文件再还原的工具，必须还原后校验" ✓
  ★ 每个小节**先把 ctl 摆成确定状态**再断言（否则"沿用上次设置"的语义会让用例互相污染✗ —— 实测踩过）
"""
import hashlib
import io
import json
import os
import sys
import tempfile
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
    return hashlib.sha256(open(p, 'rb').read()).hexdigest() if os.path.isfile(p) else None


def _set_ctl(d):
    """**直接**写控制文件到确定状态（`mine._write_ctl` 是合并式，删不掉键 ⇒ 这里整份覆盖）。"""
    os.makedirs(os.path.dirname(mine.CTL_FILE), exist_ok=True)
    with io.open(mine.CTL_FILE, 'w', encoding='utf-8') as f:
        json.dump(d, f, ensure_ascii=False, indent=1)


def main():
    ctl_p = mine.CTL_FILE
    before = _sha(ctl_p)
    raw_before = open(ctl_p, 'rb').read() if os.path.isfile(ctl_p) else None
    old_sub, old_time = mine.subprocess, mine.time
    old_sched, old_avail = mine.scheduler, mine.avail_gb
    old_pcdir = mine.PANEL_CACHE_DIR
    real_pcinfo = mine.panel_cache_info()
    try:
        # ⚠ 假 `subprocess` 必须**继承真模块的所有属性**（STDOUT/DEVNULL/run 都要在）⇒ 只替换 Popen ✓
        _fs = types.SimpleNamespace(**{k: getattr(old_sub, k) for k in dir(old_sub)
                                       if not k.startswith('_')})
        _fs.Popen = FakeProc
        mine.subprocess = _fs
        _ft = types.SimpleNamespace(**{k: getattr(old_time, k) for k in dir(old_time)
                                       if not k.startswith('_')})
        _ft.sleep = lambda *a: None
        mine.time = _ft
        mine.scheduler = lambda: []
        mine.avail_gb = lambda: 20.0

        print('=' * 96)
        print('【1】控制文件**没有**"上次设置" + 不传模式参数 ⇒ **默认并行 + 面板共享**（用户要求）')
        print('=' * 96)
        _set_ctl({'running': False, 'enabled': ['all'], 'stopped': [], 'rounds': 50})
        r = mine.start(['all'], rounds=5, reset_stopped=True)
        a = FakeProc.last[2:]
        # ★ 2026-09-16 用户要求：①「共享默认勾、去掉勾选框」②「干脆把轮转/并行按钮隐藏，默认并行」
        #   ⇒ 看板侧默认 = **并行 + 面板共享**（`rotate` 仍保留在 CLI/API，随时可切回来）✓
        chk('含 --exec_mode=parallel（默认并行，20GB 可用只 1 个池 ⇒ 自动并行 1）',
            '--exec_mode=parallel' in a and '--max_parallel=1' in a, str(a))
        chk('含 --auto_parallel=1（★ 上限**动态重算**：后来加池不用重启调度器）',
            '--auto_parallel=1' in a, str(a))
        chk('含 --panel_cache=use（共享默认开）', '--panel_cache=use' in a, str(a))
        # ★★★★ 2026-09-17（回归测试当场抓到）：看板**必须**带 `--from_ctl=1` ——
        #   它先在 ctl 里写好 enabled/stopped，再让调度器"以 ctl 为准" ✓
        #   否则调度器按"命令行直跑"处理 ⇒ **清掉 stopped**（用户刚停的池被拉回来 ✗✗）
        chk('★ 含 --from_ctl=1（看板启动以**控制文件**为准 ⇒ 动态启停才有效）',
            '--from_ctl=1' in a, str(a))
        chk('返回体 execMode=parallel / panelCache=use',
            r.get('execMode') == 'parallel' and r.get('panelCache') == 'use')

        print()
        print('【2】并行 + 面板共享 ⇒ 参数**真的**透传到命令行')
        print('=' * 96)
        _set_ctl({'running': False, 'enabled': ['300', '500'], 'stopped': [], 'rounds': 50})
        pc = 'use' if (real_pcinfo.get('exists') and real_pcinfo.get('sourceOk')) else 'off'
        r = mine.start(['300', '500'], rounds=2, exec_mode='parallel',
                       max_parallel=3, mem_per_engine=2.5, panel_cache=pc)
        a = FakeProc.last
        chk('含 --exec_mode=parallel', '--exec_mode=parallel' in a, str(a[2:]))
        chk('含 --max_parallel=3（显式传入时按传入值）', '--max_parallel=3' in a)
        # ★★ 2026-09-17（用户实测："只有 300 池是绿点，却显示 2 个池在挖"）：
        #   后端与调度器**都要**给控制文件加同一把跨进程锁（否则 read-modify-write 互相吞字段 ✗）
        chk('后端 `_write_ctl` 走**跨进程锁**（与 tools/run_tracks.py 同款）',
            '_with_ctl_lock(_do)' in io.open(
                r'D:\loop_code\dashboard\api\app\mine.py', encoding='utf-8-sig').read())
        chk('后端 `state()` 把 `active` **按活进程过滤**（文件可能残留已死 pid ⇒ 不许撒谎）',
            "a.get('pid') in {p['pid'] for p in engs}" in io.open(
                r'D:\loop_code\dashboard\api\app\mine.py', encoding='utf-8-sig').read())
        chk('显式指定并行数 ⇒ **不带** --auto_parallel（用户的明确指定不被自动覆盖）',
            '--auto_parallel=1' not in a, str(a))
        chk('含 --mem_per_engine=2.5', '--mem_per_engine=2.5' in a)
        if pc == 'use':
            chk('含 --panel_cache=use', '--panel_cache=use' in a)
        chk('返回体回显设置', r.get('execMode') == 'parallel' and r.get('maxParallel') == 3)

        print()
        print('【3】只用面板共享（轮转模式）⇒ 只加 --panel_cache，**不加**并行开关')
        print('=' * 96)
        _set_ctl({'running': False, 'enabled': ['all'], 'stopped': [], 'rounds': 50})
        if pc == 'use':
            mine.start(['all'], rounds=1, exec_mode='rotate', panel_cache='use')
            a = FakeProc.last
            chk('含 --panel_cache=use 且**不含** --exec_mode',
                '--panel_cache=use' in a and not any(x.startswith('--exec_mode') for x in a),
                str(a[2:]))
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
                chk('拒绝 %s ⇒ %s' % (desc, str(e.msg)[:34]), True)

        print()
        print('【5】★ 已在跑时：改**模式类**启动参数必须 409 拒绝（绝不静默 no-op）')
        print('=' * 96)
        _set_ctl({'running': True, 'enabled': ['all'], 'stopped': [], 'rounds': 5,
                  'execMode': 'rotate', 'panelCache': 'off'})
        mine.scheduler = lambda: [{'pid': 1, 'cmd': 'python tools\\run_tracks.py --pools=all --rounds=5',
                                   'pools': None}]
        try:
            mine.start(['all'], rounds=5, exec_mode='parallel', max_parallel=3,
                       mem_per_engine=3.0, panel_cache='off')
            chk('改模式被拒', False, '居然允许热改 ✗')
        except mine.MineError as e:
            chk('改模式被拒（%s）' % str(e.msg)[:32], e.code == 409)
        # ⚠ 必须传**与当前一致**的模式（否则会被上面那条守卫正当拒绝 —— 实测踩到过 ✓）
        r = mine.start(['all', '300'], rounds=7, exec_mode='rotate', panel_cache='off')
        chk('模式一致 ⇒ 仍然就地更新（reused=True，轮数改到 7）',
            r.get('reused') is True and r.get('rounds') == 7)

        print()
        print('【6】★★ 并行数**自动算**（用户："一键启动就全部五池，万一会爆内存就自动少一个池"）')
        print('=' * 96)
        mine.scheduler = lambda: []
        # ★ 自动并行数 K = clamp(1, min(池数, (可用-3)//每引擎))；停不下来时**内存护栏会拒绝**
        #   （1 个引擎也要 3+3=6 GB ⇒ 可用 <6 时拒绝是对的，别硬上 ✗）
        for free, want in ((26.0, 5), (12.0, 3), (9.0, 2), (8.9, 1), (5.0, 'REJECT'), (3.5, 'REJECT')):
            _set_ctl({'running': False, 'enabled': ['all', '300', '500', '1000', '50'],
                      'stopped': [], 'rounds': 1})
            mine.avail_gb = lambda f=free: f
            try:
                mine.start(['all', '300', '500', '1000', '50'], rounds=1, exec_mode='parallel',
                           panel_cache=pc, mem_per_engine=2.0)
                a = FakeProc.last
                got = [x for x in a if x.startswith('--max_parallel=')]
                got = int(got[0].split('=')[1]) if got else None
            except mine.MineError as e:
                got = 'REJECT' if e.code == 409 else 'ERR:%s' % e.code
            chk('可用 %4.1f GB + 面板共享(3GB/引擎) ⇒ %s' % (
                free, ('自动并行 %d' % want) if want != 'REJECT' else '内存护栏拒绝（409）'),
                got == want, '实测 %s' % got)

        print()
        print('【7】★★★ 「启动本池」：**调度器不在时只启动这一个池**（用户："我挨个池子点启动"）')
        print('=' * 96)
        mine.scheduler = lambda: []
        mine.avail_gb = lambda: 20.0
        _set_ctl({'running': False, 'enabled': ['all', '300', '500'], 'stopped': [], 'rounds': 50,
                  'execMode': 'parallel', 'panelCache': 'use'})
        r = mine.start_pool('500')
        a = FakeProc.last[2:]
        chk('★ 命令行 `--pools=500`（**只有它**，不是"上次遗留的 all,300,500"）',
            '--pools=500' in a, str(a))
        _c = mine.ctl()
        # ⚠ 中文串里**别塞 ASCII 单引号**（会截断字符串 ⇒ SyntaxError；本项目的老坑）⇒ 用「」
        chk('★ 控制文件 enabled 只剩「500」（其余池保持"不参与"）',
            _c.get('enabled') == ['500'], str(_c.get('enabled')))
        chk('返回体 restarted=True', r.get('restarted') is True)

        print()
        print('【8】★★ 面板缓存不可用 ⇒ **自动降级为 off**（不让启动失败），并在 note 里说明')
        print('=' * 96)
        _set_ctl({'running': False, 'enabled': ['all'], 'stopped': [], 'rounds': 1})
        mine.avail_gb = lambda: 20.0
        with tempfile.TemporaryDirectory(prefix='_pc_missing_') as tmp:
            mine.PANEL_CACHE_DIR = tmp                     # 空目录 ⇒ 缓存"缺失"
            try:
                r = mine.start(['all'], rounds=1, exec_mode='rotate', panel_cache='use')
                chk('缓存缺失时**不报错**（降级继续）', r.get('ok') is True)
                chk('返回体 panelCache=off（降级后的真实值）', r.get('panelCache') == 'off')
                chk('命令行里**没有** --panel_cache（没拿失效缓存去跑）',
                    not any(x.startswith('--panel_cache') for x in FakeProc.last), str(FakeProc.last[2:]))
                chk('note 里明确说了"自动关掉面板共享"', '自动关掉' in (r.get('note') or ''))
            except mine.MineError as e:
                chk('缓存缺失时应降级而不是报错', False, str(e.msg)[:50])
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
