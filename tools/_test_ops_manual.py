# -*- coding: utf-8 -*-
"""★★★ 守门：**算子手册**必须覆盖全部算子与字段 + 前端按钮/弹窗/接口都在位 ✓

为什么需要（2026-09-19，用户之问）：
  用户看公式 `ts_std100(mul(cs_demean(hl_ratio), ts_mean5(cs_demean(turn_ratio))))` 时
  不知道 `cs_demean` 什么意思 ⇒ 首页加「算子手册」按钮 + 带滚动条的弹窗 ✓
  ⇒ 这里钉住三件事，防"加了算子却忘了写中文"或"按钮/接口没接上" ✗：
    ① 手册的算子名单**派生自** `engine/ops_registry.py`（唯一事实源）；
       每个**前缀**都必须有中文（`OPS_ZH`）⇒ 以后加算子时会**当场 FAIL** ✓
    ② 每个**字段**（`loop_fields.LEAVES`）都必须有中文（`FIELDS_ZH`）✓
    ③ 手册文案**不许有引号/机味符号**（它会被看板直接渲染 ✓）+ 接口与前端接线在位 ✓
"""
import ast
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'dashboard', 'api'))
sys.path.insert(0, os.path.join(ROOT, 'engine'))

FAIL = []


def chk(desc, cond, hint=''):
    print('  %s %s' % ('✓' if cond else '✗', desc))
    if not cond:
        FAIL.append(desc + ('（%s）' % hint if hint else ''))


from app.sources import ops as OM      # noqa: E402

print('[1] 算子前缀中文覆盖（名单派生自 ops_registry，唯一事实源 ✓）')
prefixes = []
for _p, _w, _b, _g in OM.OPS.UNARY_SPECS:
    prefixes.append(_p)
for _p, _w, _b, _g in OM.OPS.BINARY_SPECS:
    prefixes.append(_p)
missing = [p for p in prefixes if p not in OM.OPS_ZH]
chk('共 %d 个算子前缀，全部有中文说明' % len(prefixes), not missing,
    '缺：%s' % ', '.join(missing))
chk('中文说明不是占位（每条都非空 ✓）',
    all((OM.OPS_ZH[p][0] or '').strip() and (OM.OPS_ZH[p][1] or '').strip()
        for p in prefixes if p in OM.OPS_ZH))

print()
print('[2] 字段中文覆盖（loop_fields.LEAVES）')
leaves = list(OM.LF.LEAVES)
miss_f = [f for f in leaves if f not in OM.FIELDS_ZH]
chk('共 %d 个字段，全部有中文说明' % len(leaves), not miss_f,
    '缺：%s' % ', '.join(miss_f))

print()
print('[3] 手册内容与文案纪律')
m = OM.manual()
chk('接口返回算子 %d 个 / 字段 %d 个（都 > 0 ✓）' % (len(m['ops']), len(m['fields'])),
    len(m['ops']) > 0 and len(m['fields']) > 0)
chk('算子名带窗口展开（如 ts_std100 ✓）', any(o['name'] == 'ts_std100' for o in m['ops']))
chk('二元算子写法示例是 a / b 两参 ✓',
    any(o['sig'] == 'mul(a, b)' for o in m['ops'] if o['name'] == 'mul'))
chk('给了通用规则说明（%d 条 ✓）' % len(m['notes']), len(m['notes']) >= 3)
_bad = '「」『』“”‘’★✓✗⇒'
_q = [s for s in [o['zh'] + o['tip'] for o in m['ops']] + [f['zh'] + f['tip'] for f in m['fields']]
      + [n['k'] + n['v'] for n in m['notes']] if any(c in s for c in _bad)]
chk('手册文案没有引号与机味符号（%d 条）' % (
    len(m['ops']) + len(m['fields']) + len(m['notes'])), not _q, '例：%s' % (_q[:2],))

print()
print('[4] 接口与前端接线')
_MAIN = io.open(os.path.join(ROOT, 'dashboard', 'api', 'app', 'main.py'), encoding='utf-8').read()
chk('后端有 /api/ops 路由', "/api/ops" in _MAIN and 'def ops_manual' in _MAIN)
chk('/api/ops 登记进 endpoints 清单', re.search(r"'/api/ops',", _MAIN) is not None)
_API = io.open(os.path.join(ROOT, 'dashboard', 'web', 'src', 'api.ts'), encoding='utf-8').read()
chk('api.ts 定义了 ops 接口', re.search(r"ops:\s*\(\)\s*=>\s*get<OpsDto>\('/ops'\)", _API) is not None)
chk('api.ts 有 OpsDto 类型', 'interface OpsDto' in _API)
_APP = io.open(os.path.join(ROOT, 'dashboard', 'web', 'src', 'App.tsx'), encoding='utf-8').read()
chk('首页有算子手册按钮', '算子手册' in _APP and 'setOpsOpen(true)' in _APP)
chk('打开了就会取数（api.ops ✓）', 'api.ops()' in _APP)
chk('弹窗用了滚动容器（modal-body ✓）', 'className="modal-body"' in _APP)
_CSS = io.open(os.path.join(ROOT, 'dashboard', 'web', 'src', 'styles.css'), encoding='utf-8').read()
chk('弹窗内容区是纵向滚动（overflow-y: auto ✓）',
    re.search(r'\.modal-body\s*\{[^}]*overflow-y:\s*auto', _CSS) is not None)
chk('弹窗内容区不出横向滚动条（overflow-x: hidden ✓）',
    re.search(r'\.modal-body\s*\{[^}]*overflow-x:\s*hidden', _CSS) is not None)

print()
if FAIL:
    print('✗ 失败 %d 项：' % len(FAIL))
    for f in FAIL:
        print('   - %s' % f)
    sys.exit(1)
print('✓ 全过：算子手册覆盖全部算子与字段，接口与前端接线在位')
sys.exit(0)
