# -*- coding: utf-8 -*-
"""★★★★★ 守门：**并行槽位口径 = 单一事实源**（2026-09-23 用户拍板："统一口径" ✓）。

为什么要它（用户实测被绊住 ✓）：
    用户之问：_"才 2 个槽位？不是可以最大有 5 个槽位吗？"_ —— 对不上账，因为同一台机器上
    原来有**三套算法 + 一处显示错** ✗：
      · 看板**启动那一刻**：`GB_PER_ENGINE_SHARED`(3.0) / `GB_PER_ENGINE`(9.0) ⇒ 会算出 5 个 ✗
      · 看板**内存护栏**：`max(mem_per_engine, 3.0)` ⇒ 第三个答案 ✗
      · 调度器**运行期**：`(free − 3.0) // --mem_per_engine` —— **连面板惩罚都没有** ✗
      · 看板**显示**：读命令行 `--max_parallel`（启动时的天花板）⇒ 小字写"同时最多 1 个引擎"，
        而真实上限是 2 ✗✗
    ⇒ 现在两边都调 `tools/parallel_runner.py` 的 `per_engine_gb` / `slot_cap` ✓

本守门钉五件：
  【1】静态：单一事实源在位；`mine.py` **不再**有本地口径常数/本地算式 ✗
  【2】功能：★ 核心 —— `_eff_max`（运行期）与 `slot_cap`（启动时同一函数）**答案必须相等** ✓
        ＋ 面板缓存关着时必须把那 4.42 GB 算进去 ✓（运行期原来漏了 ✗）
  【3】接口/前端：`slotCap` / `effMaxParallel` 透传到 DTO，且启动按钮显示**真实值**（不是天花板 ✓）
  【4】文案：口径串不许出现 Markdown `**`（用户可见、会原样显示星号 ✗）
  【5】★★ 回填：`_eff_max` 必须算「**同时最多几个**」（把在跑的按预算加回可用内存 ✓）——
        原来算的是「**还能再开几个**」却拿去和 `len(running)` 比 ✗ ⇒ **空出的槽永远回填不上** ✗✗
        （用户实测 2026-09-23 20:48：_`我停1000池啦，它还在等啊`_ ⇒ 排队中的 50 起不来 ✓）
        ＋ 天花板 = 启动那一刻的容量（不许因"加回去"而悄悄多开 ✗）＋ 内存真紧时照旧不起 ✓
"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

PR = io.open(os.path.join(HERE, 'parallel_runner.py'), encoding='utf-8').read()
MINE = io.open(os.path.join(ROOT, 'dashboard', 'api', 'app', 'mine.py'), encoding='utf-8').read()
APP = io.open(os.path.join(ROOT, 'dashboard', 'web', 'src', 'App.tsx'), encoding='utf-8').read()
API = io.open(os.path.join(ROOT, 'dashboard', 'web', 'src', 'api.ts'), encoding='utf-8').read()

FAIL = []


def chk(desc, cond, hint=''):
    print('  %s %s' % ('✓' if cond else '✗', desc))
    if not cond:
        FAIL.append(desc + ('（%s）' % hint if hint else ''))


print('[1] 静态：单一事实源在位，看板不再自己算 ✗')
chk('parallel_runner 有 `per_engine_gb`（一个引擎按多少 GB 算 ✓）', 'def per_engine_gb(' in PR)
chk('parallel_runner 有 `slot_cap`（能同时跑几个 ✓）', 'def slot_cap(' in PR)
chk('有面板常数 `PANEL_GB`（面板缓存关着时要加它 ✓）',
    re.search(r'^PANEL_GB\s*=\s*[\d.]+', PR, re.M) is not None)
chk('★ `mine.py` **不再**有本地口径常数（`GB_PER_ENGINE*` 一律绝迹 ✗）',
    re.search(r'^\s*GB_PER_ENGINE', MINE, re.M) is None)
chk('★ `mine.py` 启动上限走单一事实源（`_PR().slot_cap(` ✓）',
    '_PR().slot_cap(' in MINE)
chk('★ `mine.py` 内存护栏也走它（`_PR().per_engine_gb(` ✓）',
    '_PR().per_engine_gb(' in MINE)
chk('★ `mine.py` 不再有本地 `// _eff` 之类算式（口径只在 parallel_runner ✓）',
    re.search(r'//\s*_eff\b', MINE) is None)
chk('运行期闸门也统一（`per_engine_gb(mem_per_engine, panel_cache)` 出现在启动循环里 ✓）',
    'per_engine_gb(mem_per_engine, panel_cache)' in PR)

print()
print('[2] 功能：★ 运行期与启动时**同一个答案**（这条是本次改动的核心 ✓）')
try:
    import parallel_runner as PRM
    _ok = True
except Exception as e:                                                         # noqa: BLE001
    _ok = False
    print('  ✗ 导入 parallel_runner 失败：%r' % (e,))
    FAIL.append('导入 parallel_runner 失败：%r' % (e,))

if _ok:
    EN = {'1000', '300', '500'}
    _real_avail = PRM.avail_gb

    def _with_free(v):
        PRM.avail_gb = (lambda: v)

    try:
        # ---- ① 面板共享 + 7.0 GB 预算（就是用户当时的现场：可用 18.6 GB ⇒ 应得 2 ✓）
        _with_free(18.6)
        _a = PRM._eff_max(9, True, EN, set(), 7.0, 'use')
        _b = PRM.slot_cap(18.6, 3, 7.0, 'use')
        chk('① 运行期 `_eff_max` == 启动时 `slot_cap`（18.6 GB / 7.0 / 共享 ⇒ 2 ✓）',
            _a == _b == 2, 'eff_max=%r slot_cap=%r' % (_a, _b))

        # ---- ② 面板缓存关着 ⇒ 每引擎要 7.0 + 4.42 = 11.42 GB ⇒ 只能 1 个（运行期原来漏算 ✗）
        _c = PRM.slot_cap(18.6, 3, 7.0, 'off')
        _d = PRM._eff_max(9, True, EN, set(), 7.0, 'off')
        chk('② 面板缓存关着 ⇒ 槽位变 1（把面板 4.42 GB 算进去 ✓；两边一致 ✓）',
            _c == _d == 1, 'slot_cap=%r eff_max=%r' % (_c, _d))
        chk('②b `per_engine_gb` 确实加了面板那一份 ✓',
            abs(PRM.per_engine_gb(7.0, 'off') - (7.0 + PRM.PANEL_GB)) < 1e-9
            and abs(PRM.per_engine_gb(7.0, 'use') - 7.0) < 1e-9)

        # ---- ③ 非 auto ⇒ 一动不动用命令行上限（旧语义保住 ✓）
        chk('③ 非 auto 时 `_eff_max` 原样返回 `--max_parallel` ✓',
            PRM._eff_max(9, False, EN, set(), 7.0, 'use') == 9)

        # ---- ④ 夹到"可跑池数"与"至少 1"（不会 > 池数、也不会 0 ✓）
        _with_free(9999)
        chk('④ 内存再多也不会超过池数（3 池 ⇒ 最多 3 ✓）',
            PRM._eff_max(9, True, EN, set(), 7.0, 'use') == 3)
        _with_free(1.0)
        chk('④b 内存再紧也至少 1 个（不返回 0 ✓）', PRM.slot_cap(1.0, 3, 7.0, 'use') == 1)
        chk('④c 被单独停掉的池不占槽位（只按 runnable 算 ✓）',
            PRM._eff_max(9, True, EN, {'300', '500'}, 7.0, 'use') == 1)
        chk('④d 测不出内存 ⇒ 保守给 min(池数, 3) ✓', PRM.slot_cap(None, 5, 7.0, 'use') == 3)
    finally:
        PRM.avail_gb = _real_avail

print()
print('[3] 接口与前端：显示**真实值**（不再是命令行天花板 ✗）')
chk('mine.py 透传 `slotCap` ✓', "'slotCap': _slot_cap" in MINE)
chk('mine.py 透传 `effMaxParallel`（运行期写回的上限 ✓）', "'effMaxParallel':" in MINE)
chk('mine.py 的 `gbPerEngine` 来自单一事实源 ✓', "'gbPerEngine': round(_per_gb, 2)" in MINE)
chk('api.ts DTO 有 `slotCap` / `effMaxParallel` / `runnableCount` ✓',
    'slotCap?: number | null' in API and 'effMaxParallel?: number | null' in API
    and 'runnableCount?: number' in API)
chk('★ 启动按钮的 tooltip 显示真实槽位（`effMaxParallel ?? mine.slotCap` ✓）',
    'mine.effMaxParallel ?? mine.slotCap' in APP)
chk('「配置/口径」页有「并行槽位口径」一格 ✓',
    '并行槽位口径' in APP and 'MetaPanel({ m, mine }' in APP)

print()
print('[4] 文案：口径串不许 Markdown `**`（用户可见 ⇒ 会原样显示星号 ✗）')
# 只看 JSX 文本节点里的那几串（注释里允许 ✓）
for _s in re.findall(r'>([^<>{}]*槽位[^<>{}]*)<', APP):
    chk('JSX 文本「%s…」无 `**` ✓' % _s.strip()[:26], '**' not in _s)

print()
print('[5] ★ 回填：空出一个槽要能**立刻顶上**（2026-09-24 修"排队池永远等不到"✗✗）')
#   病根：`_eff_max` 拿 `slot_cap(avail_gb(), …)`（= "**还能再开几个**" ✗，因为 `avail_gb()`
#   已经扣掉了在跑的引擎占的内存）去和 `len(running)`（= **同时在跑几个**）比 ✗ ⇒ 张冠李戴。
#   用户现场（09-23 20:48）：_`我停1000池啦，它还在等啊`_ ——
#     启动 24.3 GB / 5 池 ⇒ 上限 4；停掉 all+1000 后：**在跑 2**（300/500）、可用 **17.3 GB**、
#     排队的还有 **50**（启用剩 3 个）⇒ 旧实现 `slot_cap(17.3, 3, 5.0) = 2` ✗ ⇒ `2 < 2` 假 ⇒ 50 起不来 ✗
if _ok:
    _real_avail5 = PRM.avail_gb
    try:
        # ★ 让实现**只可能**用入参（`avail_gb()` 返回 4.0 —— 若谁又去读实时内存，答案立刻错 ✗）
        PRM.avail_gb = (lambda: 4.0)
        _old_formula = PRM.slot_cap(17.3, 3, 5.0, 'use')
        _now = PRM._eff_max(4, True, {'300', '500', '50'}, {'all', '1000'}, 5.0, 'use',
                            running=2, free_gb=17.3, free0_gb=24.3)
        chk('★ 现场复现：在跑 2 / 可用 17.3 / 启动时 24.3 ⇒ 上限 **3**（> 在跑数 ⇒ 50 能顶上 ✓）',
            _old_formula == 2 and _now == 3,
            '旧口径（"还能开几个"✗）算出 %r = 在跑数 ⇒ 永远回填不上；新实现 %r'
            % (_old_formula, _now))
        chk('★ 入参优先（`free_gb` 给了就用它，不许偷读实时内存 ✗）',
            _now == 3, '若读的是 `avail_gb()=4.0` ⇒ 会算成 2 ✗')
        # 天花板：在跑 4（可用已被吃掉大半）⇒ 仍是启动那一刻的 4，**不许悄悄多开** ✗
        _cap4 = PRM._eff_max(4, True, {'all', '300', '500', '1000', '50'}, set(), 5.0, 'use',
                             running=4, free_gb=11.1, free0_gb=24.3)
        chk('★ 天花板 = 启动那一刻的容量（在跑 4 / 启动时 24.3 ⇒ 仍是 **4**，不多开 ✗）',
            _cap4 == 4, '得到 %r' % (_cap4,))
        # 内存真的紧 ⇒ 照旧不起（可用 3.2 GB ≈ 只剩系统余量）
        _tight = PRM._eff_max(4, True, {'all', '300', '500', '1000', '50'}, set(), 5.0, 'use',
                              running=4, free_gb=3.2, free0_gb=24.3)
        chk('★ 内存真的紧 ⇒ 上限 = 在跑数（`4 < 4` 假 ⇒ 不起新引擎 ✓ 宁慢不炸 ✓）',
            _tight == 4, '得到 %r' % (_tight,))
        # 旧调用（不传在跑数 / 不传启动时内存）⇒ **结果一字不变** ✓（守门【2】那批仍照旧 ✓）
        _compat = PRM._eff_max(9, True, {'1000', '300', '500'}, set(), 7.0, 'use',
                               free_gb=18.6)
        chk('★ 旧调用（不给 `running` / `free0_gb`）结果不变（18.6/7.0/共享 ⇒ 2 ✓）',
            _compat == 2 == PRM.slot_cap(18.6, 3, 7.0, 'use'), '得到 %r' % (_compat,))
    finally:
        PRM.avail_gb = _real_avail5
    chk('★ `run()` 真的把"在跑数 + 启动时内存"传给了 `_eff_max`（否则本版白修 ✗）',
        'running=len(running), free0_gb=_free0' in PR)
    chk('★ 启动那一刻的可用内存被记下来（`_free0 = avail_gb()` ✓）', '_free0 = avail_gb()' in PR)
    chk('★ 旧的"张冠李戴"算式已绝迹（`slot_cap(free, runnable, …)` 不再直接喂 `avail_gb()` ✗）',
        'slot_cap(free, runnable, mem_per_engine, panel_cache)' not in PR)

print()
if FAIL:
    print('✗ 槽位口径守门失败 %d 项：' % len(FAIL))
    for f in FAIL:
        print('   [FAIL] %s' % f)
    sys.exit(1)
print('✓ 槽位口径：全过（启动/护栏/运行期/回填/显示五路同一个公式 ✓）')
sys.exit(0)
