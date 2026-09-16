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
if FAIL:
    print('★★ 接线检查失败 %d 项：' % len(FAIL))
    for f in FAIL:
        print('   ✗ %s' % f)
    sys.exit(1)
print('★★ 接线检查全部通过 ✓')
