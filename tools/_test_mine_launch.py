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

★★★★★ 2026-09-23 改：**不再因"真实挖掘在跑"而整体跳过** ✗✗
  原来：`_real_mining()` 检测到调度器/引擎 ⇒ `return 0`（**静默跳过**）——
  设计初衷是对的（本测试要改写 `_control.json`，与调度器每代写同一个文件会互相打架 ✗），
  但**后果很坏**：上一版（v1.21.39 统一槽位口径）发版时线上正在挖 ⇒ 它自跳 ⇒ 它那一节
  **钉死的旧常数**（3.0 GB/引擎 / 可用 5 GB 应拒绝）早已与真实行为不符（应为 4/3/2/1）
  却以"全绿"过关 ✗✗ —— **守门静默失效比没有守门更危险**。
  ⇒ 现在改成**与真实控制文件彻底隔离**：把 `mine.CTL_FILE` / `mine.CTL_LOCK` 指到**临时副本**
    ⇒ 它再也碰不到真实 ctl ⇒ **挖掘在跑也照跑**（不再跳过 ✓），且"还原后逐字节一致"的校验
    仍然成立（只是校验的是临时文件 ✓）。
"""
import hashlib
import io
import json
import os
import shutil
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


def _real_mining():
    """★ 现在**真有挖掘在跑**吗（调度器进程 / 引擎进程）—— 用来决定是否跳过本测试。

    ★★★ 2026-09-17（同一天全量回归被误报**两次**，这次查清了）：
      本测试**直接改写 `_control.json`**（`_set_ctl`，为了把 ctl 摆成确定状态），
      而**真实挖掘调度器每一代都在写同一个文件**（`write_ctl(phase=…, curPool=…, active=…)`）✗
      ⇒ 两边的写交错 ⇒ 断言读到的是**被覆盖后的现场** ⇒ 挂 ✗
      （证据：单独跑本测试**全过**；一进全量就挂，且当时线上确有调度器 + 3 个引擎 ✓
        ⇒ 与 metrics/curves **无关** —— 之前那条"因果"是错的，已更正 ✓）
    ⚠ 判据用**真进程**（`mine.engines()`）而不是只看 ctl 里的 `running` —— 后者可能是脏值（见 v1.17.1 的 `active` 教训）✓
    """
    try:
        if mine.scheduler() or mine.engines():
            return True
    except Exception:                                  # noqa: BLE001
        pass
    try:
        c = mine.ctl()
    except Exception:                                  # noqa: BLE001
        c = {}
    return bool(c.get('running') or (c.get('active') or []))


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
    # ★★★ 2026-09-17：**有人在挖 ⇒ 两边抢同一个 `_control.json` ⇒ 本测试会误报** ✗（回归被它误报过两次）
    # ★★★★★ 2026-09-23：**不再跳过** —— 改成把控制文件**指到临时副本**（见文件头说明）✓
    #   于是"挖掘在跑"只影响"真实 ctl 会变"，而本测试压根不碰它 ✓
    if _real_mining():
        print('  [note] 检测到**真实挖掘在跑** —— 本测试已与真实控制文件隔离（用临时副本），照跑 ✓')
    _tmpd = tempfile.mkdtemp(prefix='_mine_launch_ctl_')
    _real_ctl, _real_lock = mine.CTL_FILE, mine.CTL_LOCK
    if os.path.isfile(_real_ctl):
        try:
            shutil.copy2(_real_ctl, os.path.join(_tmpd, '_control.json'))
        except Exception:
            pass
    mine.CTL_FILE = os.path.join(_tmpd, '_control.json')
    mine.CTL_LOCK = mine.CTL_FILE + '.lock'
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
        # ★★★★★ 2026-09-23 修本节（**它钉的是一批写死的旧常数** ✗）：
        #   v1.21.39「统一槽位口径」把"每引擎按几 GB 算 + 能跑几个 + 护栏"全改由
        #   `tools/parallel_runner.py` 的 `per_engine_gb()/slot_cap()` 决定（**单一事实源** ✓），
        #   而本节还写着旧口径的期望（按 3.0 GB/引擎、且"可用 5 GB 必须拒绝"✗）
        #   ⇒ 改口径后**守门反而报错**：实测 4/3/2/1（按预算 2.0 算，正确 ✓）但期望 3/2/1/REJECT ✗
        #   ⚠ 且它还有一次**静默自跳** —— 真有挖掘在跑时 `_real_mining()` 会让本测试整体跳过
        #     （因为它直接改 `_control.json` ✓），所以上一版的"全绿"**并没覆盖到这一节** ✓
        #   ⇒ 修法：**期望值从单一事实源现算**（`slot_cap` + 护栏同式 `k×每引擎+3.0`），
        #     不再写死常数 —— 以后口径再变，这里自动跟上 ✓（这才是守门该有的样子 ✓）
        import parallel_runner as _PRT
        _per = _PRT.per_engine_gb(2.0, pc)
        for free in (26.0, 12.0, 9.0, 8.9, 5.0, 3.5):
            _set_ctl({'running': False, 'enabled': ['all', '300', '500', '1000', '50'],
                      'stopped': [], 'rounds': 1})
            mine.avail_gb = lambda f=free: f
            _k = _PRT.slot_cap(free, 5, 2.0, pc)                 # ★ 单一事实源：此刻能跑几个 ✓
            _need = _k * _per + 3.0                              # 与 `mine.start` 的护栏同式 ✓
            want = 'REJECT' if free < _need else _k
            try:
                mine.start(['all', '300', '500', '1000', '50'], rounds=1, exec_mode='parallel',
                           panel_cache=pc, mem_per_engine=2.0)
                a = FakeProc.last
                got = [x for x in a if x.startswith('--max_parallel=')]
                got = int(got[0].split('=')[1]) if got else None
            except mine.MineError as e:
                got = 'REJECT' if e.code == 409 else 'ERR:%s' % e.code
            chk('可用 %4.1f GB + 每引擎预算 2.0 GB（实算 %.2f）⇒ %s' % (
                free, _per, ('自动并行 %d' % want) if want != 'REJECT' else '内存护栏拒绝（409）'),
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

        print()
        print('【9】★★★★★ 「启动本池」必须**带上并生效**面板轮数')
        print('     （2026-09-23 用户实测："我单池点启动，面板上轮数我填了 50，怎么轮数上限还是 1 呢？"）')
        print('=' * 96)
        # ★ 真因两处：① 前端/接口不传 rounds ② 调度器把上限启动时拍死（写 ctl 也不生效 ✗）
        #   本节只测**后端这一半**（接线那一半在 `_test_frontend_wiring.py`【9】/ hot-read 在代码注释 ✓）
        mine.scheduler = lambda: []
        mine.avail_gb = lambda: 20.0
        # ① 调度器不在 ⇒ 自动重启时，命令行必须带面板轮数（原来只会沿用 ctl 里的旧值 ✗）
        _set_ctl({'running': False, 'enabled': ['300'], 'stopped': [], 'rounds': 1})
        r = mine.start_pool('500', rounds=7)
        a = FakeProc.last
        chk('★ 重启命令行含 `--rounds=7`（面板填的 7，**不是** ctl 里的 1 ✓）',
            '--rounds=7' in a, str(a[2:]))
        chk('★ 返回体回读 `rounds=7`（面板据此显示"实际生效的上限" ✓）', r.get('rounds') == 7, str(r))
        chk('★ 控制文件 `rounds` 也被写成 7（看板状态区读的就是它 ✓）',
            mine.ctl().get('rounds') == 7, str(mine.ctl().get('rounds')))
        _c = mine.ctl()
        chk('★ 重启时**只启用该池**、且不碰其它池的剔除配置',
            _c.get('enabled') == ['500'] and _c.get('stopped') == [], str(_c))

        # ② 调度器**已在跑** ⇒ 就地更新时也必须写 `rounds`（原来这条分支**从来不写** ✗）
        _set_ctl({'running': True, 'enabled': ['300'], 'stopped': [], 'rounds': 1,
                  'execMode': 'parallel'})
        _real_sched = mine.scheduler
        mine.scheduler = lambda: [{'pid': 1, 'cmd': 'python tools\\run_tracks.py --pools=300',
                                   'pools': None}]
        r2 = mine.start_pool('300', rounds=50)
        chk('★★ 已在跑 ⇒ `rounds` 被就地更新为 50（原来这条分支**完全不写** ✗）',
            mine.ctl().get('rounds') == 50, str(mine.ctl().get('rounds')))
        chk('★★ 返回体 `merged=True`、`restarted=False`、`rounds=50`（语义不变 + 回读新上限 ✓）',
            r2.get('merged') is True and r2.get('restarted') is False and r2.get('rounds') == 50,
            str(r2))
        chk('已在跑时**不动 `enabled` 的其它池**（只并回该池 ✓）',
            mine.ctl().get('enabled') == ['300'], str(mine.ctl().get('enabled')))

        # ③ 不传 rounds ⇒ **沿用 ctl**（老前端 / CLI 打接口时的兼容行为 ✓）
        _set_ctl({'running': True, 'enabled': ['300'], 'stopped': [], 'rounds': 12,
                  'execMode': 'parallel'})
        r3 = mine.start_pool('300')
        chk('不传 `rounds` ⇒ 沿用 ctl 的 12（**旧行为不变** ✓；api.ts 也是"传才发"✓）',
            mine.ctl().get('rounds') == 12 and r3.get('rounds') == 12, str(r3.get('rounds')))
        # ④ 越界拒绝（绝不静默钳位 —— 免得"我填了 0 结果它跑 1 轮"✗）
        for bad in (0, -3, 999):
            try:
                mine.start_pool('300', rounds=bad)
                chk('越界轮数 %s 应被拒绝' % bad, False, '居然通过 ✗')
            except mine.MineError as e:
                chk('越界轮数 %s ⇒ 拒绝（%s）' % (bad, str(e.msg)[:30]), e.code == 400)
        mine.scheduler = _real_sched
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
        print('还原临时 ctl: %s' % ('✓ 逐字节一致' if ok else '✗ 不一致 (%s -> %s)' % (before, after)))
        if not ok:
            FAIL.append('临时 _control.json 还原后不一致')
        # ★ 2026-09-23：把 `mine.CTL_FILE/CTL_LOCK` 还回真实值 + 清掉临时目录（真实 ctl **从未被本测试碰过** ✓）
        mine.CTL_FILE, mine.CTL_LOCK = _real_ctl, _real_lock
        shutil.rmtree(_tmpd, ignore_errors=True)

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
