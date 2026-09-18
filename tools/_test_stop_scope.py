# -*- coding: utf-8 -*-
"""★★★★ 「只停这一个池」**绝不误杀其它池** 回归测试（2026-09-19 新增；`_test_*` ⇒ 进全量回归）。

## 为什么必须有它（真事故，用户原话）
> 「我刚才停了一个上证50池，然后它报错说没有全部停掉…**我本来就想要跑 3 个池，那 3 个池我不想停呀**」

实录（09-19 00:36）：
- 50 池 gen7 于 **00:33 正常跑完**（`rc=0`）⇒ 但控制文件里的 `curPool` **仍留着 `'50'`** ✗
  （`parallel_runner` 每起一个引擎写一次 `curPool`，并行时=最后起的那个，**跑完不清零** ✗）
- 用户 00:36 点「停止 50」⇒ 旧实现那句 `if c.get('curPool') == pool:` **兜底命中** ✗
  ⇒ 把**正在跑的 300 / 500 / 1000 三个引擎全杀了** ✗✗
  （调度器日志：`00:36:29-30` 三个同时 `rc=1`，还被记成"疑似崩溃"✗）
- 且残留检查用**同一个陈旧条件** ⇒ 接口 `ok=False` ⇒ 前端红字「**有进程没停掉**」
- 用户随后看到"过一会儿就没了" = ①调度器**立刻重试**了那 3 个池（旧 pid 消失 ⇒ 检查才通过 ✓）
  ②错误 toast 12s 自动消失 ✓

⇒ 两条契约（本测试钉死）：
  ① **归属只能看"逐池"证据**：命令行 `--mine_pool=` **或** 调度器 `active` 表的 `{pool,pid}`
     —— **不许**再看 `curPool`（陈旧标记 ✗）  → 见 `mine.pool_engines()`
  ② **残留检查必须"等进程真的消失"**（`taskkill /F` 返回 ≠ 已退出 ✗）
     —— 否则误报「有进程没停掉」假警报 ✗

⚠ 本测试**不起真进程、不碰真实文件**：`ctl` / `_write_ctl` / `engines` / `subprocess` / `time.sleep`
   全部**打桩替换** ⇒ 线上正在挖掘时跑它**零干扰** ✓（与 `_test_mine_launch` 的快照/还原不同，
   这里干脆一次都不写文件 ✓）
"""
import io
import os
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ROOT = r'D:\loop_code'
sys.path.insert(0, os.path.join(ROOT, 'dashboard', 'api'))

import app.mine as mine          # noqa: E402

FAIL = []
KILLS = []


def chk(desc, cond, hint=''):
    print('  %s %s' % ('✓' if cond else '✗', desc))
    if not cond:
        FAIL.append(desc + ('（%s）' % hint if hint else ''))


class FakeCP:
    returncode = 0
    stdout = 'SUCCESS: 已终止'
    stderr = ''


LIVE = []            # ★ 假的"活引擎"列表：被 kill 后**真的移除** ⇒ 模拟进程消失 ✓


class FakeSubprocess:
    """替掉 `mine.subprocess` —— 只记录"杀了谁"，绝不真杀 ✓

    ⚠ `survive=True` 时**不移除**（模拟进程赖着不走 ⇒ 用来看残留检查会不会如实报 ✗）
    """

    survive = False

    @staticmethod
    def run(args, **kw):
        KILLS.append(list(args))
        if not FakeSubprocess.survive:
            pid = int(args[2])                                 # ['taskkill','/PID','111','/T','/F']
            LIVE[:] = [e for e in LIVE if e['pid'] != pid]      # 进程真的没了 ✓
        return FakeCP()


class FakeTime:
    """替掉 `mine.time.sleep` —— 只数"等了几轮"（不真睡，测试跑得快 ✓）"""

    def __init__(self):
        self.n = 0

    def sleep(self, s):                                       # noqa: D401
        self.n += 1


def setup(engines, active, cur_pool='50', enabled=None, survive=False):
    """把 `mine` 的四个外部依赖全换成假的（**不写任何文件** ✓）"""
    KILLS.clear()
    LIVE[:] = list(engines)
    FakeSubprocess.survive = survive
    ft = FakeTime()
    mine.engines = lambda: list(LIVE)                          # ← 看的是"此刻还活着"的 ✓
    mine.ctl = lambda: {'enabled': enabled or ['1000', '300', '50', '500'],
                        'stopped': [], 'curPool': cur_pool,
                        'active': list(active), 'running': True, 'stopAll': False}
    mine._write_ctl = lambda **kw: kw                          # ★ 绝不写真实 _control.json ✓
    mine.subprocess = FakeSubprocess
    mine.time = ft
    return ft


def eng(pid, pool):
    return {'pid': pid, 'pools': [pool], 'kind': 'engine', 'memMB': 100}


E300, E500, E1000 = eng(111, '300'), eng(222, '500'), eng(333, '1000')
ACTIVE3 = [{'pool': '300', 'gen': 68, 'pid': 111},
           {'pool': '500', 'gen': 25, 'pid': 222},
           {'pool': '1000', 'gen': 21, 'pid': 333}]

print('[1] ★ 复现原 BUG 场景：`curPool` 陈旧指向 50，但**在跑的是 300/500/1000**')
print('    ⇒ 停 50 必须「一个都不杀」（旧实现在这里误杀了三个 ✗）')
setup([E300, E500, E1000], ACTIVE3, cur_pool='50')
r = mine.stop(pool='50')
chk('返回 ok=True（不该报"有进程没停掉"）', r.get('ok') is True, 'r=%r' % (r.get('stillRunning'),))
chk('killed 为空（没杀任何引擎）', r.get('killed') == [], 'killed=%r' % (r.get('killed'),))
chk('★ 全程**没有调用 taskkill**', KILLS == [], 'kills=%r' % (KILLS,))
chk('scope = pool:50', r.get('scope') == 'pool:50')
chk('文案仍写"其他池不受影响"', '其他池不受影响' in (r.get('note') or ''))

print()
print('[2] 正常单池停：300 那一代在跑 ⇒ 只杀它一个（111），222/333 不动')
setup([E300, E500, E1000], ACTIVE3, cur_pool='300')
r = mine.stop(pool='300')
pids = [k[2] for k in KILLS]
chk('只杀 111', pids == ['111'], 'killed pids=%r' % (pids,))
chk('ok=True', r.get('ok') is True)
chk('killed 记的就是 111', [x['pid'] for x in r.get('killed') or []] == [111])

print()
print('[3] 命令行归属兜底：`active` 表为空（旧进程没登记）也能认出来')
setup([eng(444, '50')], [], cur_pool=None)
r = mine.stop(pool='50')
chk('按 --mine_pool=50 认出 444 并杀掉', [k[2] for k in KILLS] == ['444'], 'kills=%r' % (KILLS,))
chk('ok=True', r.get('ok') is True)

print()
print('[4] ★ 假警报修复：残留检查必须**轮询等进程消失**（原来 sleep(1) 就判定 ⇒ 误报 ✗）')
ft = setup([E300], [{'pool': '300', 'gen': 68, 'pid': 111}], cur_pool='300', survive=True)
r = mine.stop(pool='300')
chk('进程一直不消失 ⇒ ok=False（如实报告 ✓）', r.get('ok') is False)
chk('stillRunning 里有 111', [x['pid'] for x in r.get('stillRunning') or []] == [111])
chk('★ 轮询了多轮（不是只看一次）', ft.n >= 5, 'sleep 次数=%d' % ft.n)
chk('轮询有上限（最多 20 次，不会卡死）', ft.n <= 20, 'sleep 次数=%d' % ft.n)

print()
print('[5] 静态守门：`stop()` 里**不许再出现** `curPool` 比较（根因 ✗）')
src = io.open(os.path.join(ROOT, 'dashboard', 'api', 'app', 'mine.py'), encoding='utf-8').read()
i = src.index('def stop(')
j = src.index('\ndef ', i + 1)
seg = src[i:j]
chk("无 `curPool` 比较（get('curPool') == 不许再出现）",
    "get('curPool') ==" not in seg and 'get("curPool") ==' not in seg)
chk('用了 pool_engines（逐池归属）', 'pool_engines(pool' in seg)
chk('残留检查是轮询等待（有 for + sleep）', 'for _ in range(' in seg and 'time.sleep(' in seg)

print()
if FAIL:
    print('✗ 失败 %d 项：' % len(FAIL))
    for f in FAIL:
        print('   - %s' % f)
    sys.exit(1)
print('✓ 全部通过：「只停这一个池」不会误杀其它池；残留检查不再误报')
sys.exit(0)
