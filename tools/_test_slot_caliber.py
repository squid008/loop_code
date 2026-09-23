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

本守门钉四件：
  【1】静态：单一事实源在位；`mine.py` **不再**有本地口径常数/本地算式 ✗
  【2】功能：★ 核心 —— `_eff_max`（运行期）与 `slot_cap`（启动时同一函数）**答案必须相等** ✓
        ＋ 面板缓存关着时必须把那 4.42 GB 算进去 ✓（运行期原来漏了 ✗）
  【3】接口/前端：`slotCap` / `effMaxParallel` 透传到 DTO，且启动按钮显示**真实值**（不是天花板 ✓）
  【4】文案：口径串不许出现 Markdown `**`（用户可见、会原样显示星号 ✗）
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
if FAIL:
    print('✗ 槽位口径守门失败 %d 项：' % len(FAIL))
    for f in FAIL:
        print('   [FAIL] %s' % f)
    sys.exit(1)
print('✓ 槽位口径：全过（启动/护栏/运行期/显示四路同一个公式 ✓）')
sys.exit(0)
