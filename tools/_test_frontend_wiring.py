# -*- coding: utf-8 -*-
"""★★★ 前端「接线」回归检查（静态，不改运行状态）—— 防「处理函数写了却没接上」。

★ 为什么需要（2026-09-16 血泪）：
  我在 `v1.3.9` 写了 `doStartPool()`（走 `/api/mine/start_pool`，**只动该池**），
  但池卡片上接的仍是 `doStart([p.key])`（走 `/api/mine/start`，**会把 enabled 整体改写**）
  ⇒ 用户点「启动本池(全A)」⇒ **其余 4 个池全被移出轮转** ✗✗
  ★ 而当时的"端到端测试"是**直接打 API** ⇒ **完全没覆盖到前端接线** ✗

⇒ 本脚本做**静态接线断言**：
  ① 关键按钮必须接到**语义正确**的处理函数上；
  ② 处理函数必须**真的被引用**（否则就是"写了没接"的死代码）✗；
  ③ 页面用到的 `api.mine*` 必须在 `api.ts` 里有定义（防拼错 endpoint）。
"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
APP = r'D:\loop_code\dashboard\web\src\App.tsx'
API = r'D:\loop_code\dashboard\web\src\api.ts'

src = io.open(APP, encoding='utf-8').read()
FAIL = []


def chk(desc, cond, hint=''):
    print('  %s %s' % ('✓' if cond else '✗', desc))
    if not cond:
        FAIL.append(desc + ('（%s）' % hint if hint else ''))


print('【1】池卡片按钮的接线（★ 语义必须正确）')
# 池卡片的 onStart 必须走"**只动该池**"的接口 ⇒ doStartPool（而非 doStart）
chk('池卡片 onStart 接的是 doStartPool（只动该池）',
    re.search(r'onStart=\{\(\)\s*=>\s*doStartPool\(', src) is not None,
    '若接成 doStart([...]) ⇒ 会把 enabled 整体改写 ⇒ 其它池被移出轮转 ✗')
chk('池卡片 onStart **没有**误接成 doStart([',
    re.search(r'onStart=\{\(\)\s*=>\s*doStart\(', src) is None,
    '这就是 2026-09-16 的 bug 本体')
chk('池卡片 onStop 接的是 doStop(池)',
    re.search(r'onStop=\{\(\)\s*=>\s*doStop\(', src) is not None)

print()
print('【2】顶栏按钮的接线')
chk('「一键启动全部」接的是 doStart([])',
    re.search(r'doStart\(\[\]\)', src) is not None)
chk('「全部停止」接的是 doStop() 无参（= 全部停）',
    re.search(r'doStop\(\)\}', src) is not None)

print()
print('【3】处理函数必须**真的被引用**（防"写了没接"的死代码）')
for fn in ('doStart', 'doStop', 'doStartPool'):
    uses = list(re.finditer(r'\b%s\(' % fn, src))
    defined = re.search(r'const %s = useCallback' % fn, src) is not None
    n_call = len(uses) - (1 if defined else 0)
    chk('%-12s 已定义且被引用（引用 %d 次）' % (fn, n_call), defined and n_call >= 1,
        '定义了却没接线 ⇒ 功能点了会走旧路径 ✗')

print()
print('【4】接口常量名拼写（防止调到不存在的 endpoint）')
api = io.open(API, encoding='utf-8').read()
for name, path in (('mineState', '/mine/state'), ('mineStart', '/mine/start'),
                   ('mineStop', '/mine/stop'), ('mineStartPool', '/mine/start_pool')):
    ok = ('%s:' % name) in api and ("'%s'" % path) in api
    chk('api.%-13s -> %s' % (name, path), ok)
used = set(re.findall(r'api\.(mine\w+)', src))
known = set(re.findall(r'^\s*(mine\w+):', api, re.M))
unknown = sorted(used - known)
chk('页面里用到的 api.mine* 都已定义%s' % ('：缺 ' + ','.join(unknown) if unknown else ''),
    not unknown)

print()
print('【5】★ 因子曲线：图例必须能**点选显隐**（2026-09-16 用户要求「所有的图，点图例要能显隐曲线」）')
chk('图例是**按钮**而非纯文本（可点）',
    re.search(r'className=\{`ch-lgbtn\$\{off\[i\] \? \' off\' : \'\'\}`\}', src) is not None,
    '图例若仍是 <span> ⇒ 点了没反应 ✗')
chk('图例按钮绑定了 onClick 切换隐藏态',
    re.search(r'onClick=\{\(\) => setOff\(o => \(\{ \.\.\.o, \[i\]: !o\[i\] \}\)\)\}', src) is not None,
    '这是"能显隐"的本体')
chk('隐藏的曲线**退出 Y 轴取值范围**（否则坐标轴仍被撑住 ⇒ 藏了也白藏）',
    re.search(r'vis\.forEach\(x => x\.s\.data\.forEach', src) is not None,
    'Y 轴取值必须基于 vis 而不是 series ✗')
chk('换因子时**重置**显隐状态（否则换到别的因子会莫名少几条线）',
    re.search(r'useEffect\(\(\) => \{ setOff\(\{\}\) \}, \[sig\]\)', src) is not None)
chk('全部隐藏时有提示 + 图例仍可点回来',
    '（曲线已全部隐藏' in src)
# ⚠ 别写成 "`'/curves/`" —— api.ts 里是**模板字符串**（反引号），不是单引号 ✗（2026-09-16 自己踩到）
chk('曲线接口 api.curves -> /curves/ 已定义且被页面调用',
    ('curves:' in api and '/curves/' in api and 'api.curves(' in src))

print()
print('【6】★ 风格相关性画像：横向条形图 + 图例显隐 + 数据来源（2026-09-16 用户要求）')
chk('风格画像走**同一个 /curves 接口**的 style 字段（不另开接口）',
    'StyleProfileDto' in api and "'style': d.get('style')" in io.open(
        r'D:\loop_code\dashboard\api\app\sources\factors.py', encoding='utf-8').read(),
    '另开接口要多一次请求、多一份缓存 ✗')
chk('横向条形图组件已实现', 'function BarChart' in src)
chk('条形图图例同样**可点显隐**（与折线图同约定）',
    'ch-lgbtn' in src and re.search(r'点击隐藏 / 显示「原始」这一根', src) is not None)
chk('风格图固定值域 ±1 ⇒ **跨因子可比**', 'domain={1}' in src,
    '自适应值域会让"0.05 看着和 0.5 一样长" ✗')
chk('行业条用自适应值域（相关性本身很小，固定 ±1 会看不见）',
    re.search(r'<BarChart rows=\{indRows\} />', src) is not None)
chk('统计表含 IR / t / 胜率 / 自相关（不是只给一个相关系数）',
    all(k in src for k in ('|均值|', '>IR<', '>t<', '胜率', '自相关')))
# ★ 2026-09-16 实测教训：相关序列 ac1≈0.93~0.97 ⇒ 朴素 t=IR·√T 会被放大数倍 ⇒ 必须显示**校正后**的 t
chk('表里同时有 **校正 t 与朴素 t**，且用 tAdj', '>t朴素<' in src and 'tAdj' in src)
chk('未生成时给可执行提示（不是空白）', '--stage=style+strip2' in src)
chk('新增两个剥法（剥流通市值 / 剥总市值+限售）已接进图例',
    all(k in src for k in ('floatcap', 'caplimit')))

print()
print('【7】★ 调度模式 / 面板共享：UI 控件必须接到位（2026-09-16 用户之问「前端还没把并行切换加上」）')
MINE = r'D:\loop_code\dashboard\api\app\mine.py'
minepy = io.open(MINE, encoding='utf-8').read()
chk('模式分段控件存在（轮转 / 并行）',
    "setExecMode('parallel')" in src and "setExecMode('rotate')" in src)
# ⚠ 断言里的字面量**别带引号** —— TSX 里是 `mine?.parallelRange`（不带引号），带引号就永远不匹配 ✗
chk('并行数 / 每引擎预算 只在 parallel 时出现',
    'parallelRange' in src and 'memPerEngine' in src and "execMode === 'parallel'" in src)
chk('面板共享复选框存在（勾选 ⇒ panel_cache=use）', "panelCache ? 'use' : 'off'" in src)
chk('doStart 把模式参数**真的**发给接口', 'api.mineStart(pools, rounds, {' in src)
chk('api.mineStart 支持 opts 透传（含 execMode/panelCache）',
    'opts?' in api and 'execMode?: string' in api and 'panelCache?: string' in api)
chk('状态区显示**实际**在跑的模式（不是 UI 上选的那个）',
    'mine.execMode === ' in src and "'execMode': _mode" in minepy,
    '必须**以真实进程命令行为准** —— UI 选择 ≠ 实际运行 ✗')
chk('mine.py：**非默认才追加开关**（默认命令行逐字不变）',
    "if exec_mode != 'rotate':" in minepy and "if panel_cache != 'off':" in minepy)
chk('mine.py：启动参数不可热改 ⇒ 409 拒绝（不静默 no-op）',
    '不能热改' in minepy and 'e.code == 409' in open(r'D:\loop_code\tools\_test_mine_launch.py',
                                                  encoding='utf-8').read())
chk('mine.py：内存护栏**分档**（面板共享后按 GB_PER_ENGINE_SHARED 算）',
    'GB_PER_ENGINE_SHARED' in minepy)
chk('启动参数回归测试在册（假 Popen + 快照还原 ctl）',
    os.path.isfile(r'D:\loop_code\tools\_test_mine_launch.py')
    and '_control.json' in open(r'D:\loop_code\tools\_test_mine_launch.py', encoding='utf-8').read())

print()
if FAIL:
    print('★★ 接线检查失败 %d 项：' % len(FAIL))
    for f in FAIL:
        print('   ✗ %s' % f)
    sys.exit(1)
print('★★ 接线检查全部通过 ✓')
