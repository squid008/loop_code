# -*- coding: utf-8 -*-
"""版本一致性守门测试 —— **防止"版本号打架"**（2026-09-15, v1.0.0 起）。

## 为什么要它（真实事故）
版本号此前散落三处，实测**三处打架** ✗：
| 位置 | 值 | 差距 |
|---|---|---|
| git tag 最新（真实） | `v0.21.1` | — |
| `change_log.md` 最新条目 | `0.20.2` | ⚠ 落后 9 版 |
| `README.md` 顶部声明 | `v0.20.0` | ⚠ 落后 11 版（且与自身版本表格矛盾）|

## 架构（与"端口只改一处"同思路）
```
VERSION                      ← ★ 唯一来源（仓库根）
  ├── README.md              ← 顶部"当前版本"必须等于它
  ├── change_log.md          ← 最新 `## [x.y.z]` 条目必须等于它
  ├── dashboard/api/app/settings.py   ← **读**它（不许硬编码）
  └── dashboard/web/package.json      ← version 字段必须等于它
本测试 = 守门：任一处不一致 ⇒ 非零退出 ✓
"""
import io
import json
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAILS = []
WARNS = []


def read(p):
    fp = os.path.join(R, p)
    return io.open(fp, encoding='utf-8', errors='replace').read() if os.path.exists(fp) else None


# ---------------------------------------------------------------- 1. VERSION
vp = os.path.join(R, 'VERSION')
if not os.path.exists(vp):
    FAILS.append('缺根 `VERSION` 文件（★ 版本唯一来源）')
    VER = None
else:
    # ⚠ `utf-8-sig` 容忍 BOM（负向验证时 `Set-Content -Encoding UTF8` 会加 BOM ⇒
    #   当时报出 `'\ufeff9.9.9'` —— 说明本检查连 BOM 都能抓到 ✓ 但读取应主动容忍）
    VER = io.open(vp, encoding='utf-8-sig').read().strip().lstrip('\ufeff')
    if not re.fullmatch(r'\d+\.\d+\.\d+', VER):
        FAILS.append('`VERSION` 内容不是 `x.y.z` 格式: %r（是否混入 BOM/空行？）' % VER)
print('  [1] VERSION = %s' % VER)

# ---------------------------------------------------------------- 2. README
rd = read('README.md')
if rd is None:
    FAILS.append('缺 README.md')
else:
    m = re.search(r'当前版本\s*`?v?(\d+\.\d+\.\d+)', rd)
    if not m:
        FAILS.append('README.md 里找不到「当前版本 vX.Y.Z」')
    elif VER and m.group(1) != VER:
        FAILS.append('README 当前版本 %s ≠ VERSION %s' % (m.group(1), VER))
    else:
        print('  [2] README 当前版本 = %s ✓' % m.group(1))

# ---------------------------------------------------------------- 3. change_log
cl = read('change_log.md')
if cl is None:
    FAILS.append('缺 change_log.md')
else:
    vs = re.findall(r'^##\s*\[(\d+\.\d+\.\d+)\]', cl, re.M)
    if not vs:
        FAILS.append('change_log.md 里找不到 `## [x.y.z]` 条目')
    elif VER and vs[0] != VER:
        FAILS.append('change_log 最新条目 %s ≠ VERSION %s' % (vs[0], VER))
    else:
        print('  [3] change_log 最新条目 = %s ✓' % vs[0])

# ---------------------------------------------------------------- 4. 后端读 VERSION（不许硬编码）
st = read('dashboard/api/app/settings.py')
if st is None:
    FAILS.append('缺 dashboard/api/app/settings.py')
else:
    if 'VERSION' not in st or "'VERSION'" not in st.replace('"', "'"):
        FAILS.append('settings.py 未从 `VERSION` 文件读版本')
    # 检查 main.py 不许硬编码版本字面量
    mn = read('dashboard/api/app/main.py') or ''
    bad = re.findall(r"version\s*=\s*'(\d+\.\d+\.\d+)'|'version':\s*'(\d+\.\d+\.\d+)'", mn)
    if bad:
        FAILS.append('main.py 硬编码了版本字面量: %s（应读 settings.VERSION）' % (bad,))
    else:
        print('  [4] 后端从 VERSION 读、无硬编码 ✓')

# ---------------------------------------------- 4b. ★ 版本必须**动态读**（2026-09-19）
#   实测事故（用户："页面我刷新怎么还是 1.19.3 版本？"）：
#     `VERSION = _read_version()` 是**模块级常量** ⇒ 只在**服务启动时读一次**、
#     之后冻结在进程内存里 ✗ ⇒ 改了 `VERSION` 之后**刷新页面永远不变**，非得重启 API ✗
#     （那个 API 进程 09-17 12:22 启动 ⇒ 页面卡在 1.19.3，而 VERSION 早已到 1.21.x ✗）
#   ⇒ 契约：`/api/meta` 必须走 `settings.current_version()`（每次调用重读）✓
st2 = read('dashboard/api/app/settings.py') or ''
mn2 = read('dashboard/api/app/main.py') or ''
if 'def current_version' not in st2:
    FAILS.append('settings.py 缺 `current_version()` —— 版本会**冻结在进程启动时** ✗'
                 '（用户实测：改版本后刷新页面不变 ✗）')
elif 'settings.current_version()' not in mn2:
    FAILS.append('/api/meta 未使用 `settings.current_version()` ⇒ 刷新页面看不到最新版本 ✗')
else:
    print('  [4b] /api/meta 动态读 VERSION（改版本后刷新即生效）✓')

# ---------------------------------------------------------------- 5. 前端 package.json
pj = read('dashboard/web/package.json')
if pj is None:
    FAILS.append('缺 dashboard/web/package.json')
else:
    v = json.loads(pj).get('version')
    if VER and v != VER:
        FAILS.append('web/package.json version %s ≠ VERSION %s' % (v, VER))
    else:
        print('  [5] web/package.json version = %s ✓' % v)

# ---------------------------------------------------------------- 6. git tag（仅警告：打 tag 在提交之后）
try:
    r = subprocess.run(['git', 'tag', '--sort=-v:refname'], cwd=R, capture_output=True,
                       text=True, encoding='utf-8', errors='replace', timeout=15)
    tags = [t for t in (r.stdout or '').splitlines() if t.strip()]
    top = tags[0].lstrip('v') if tags else None
    if top and VER and top != VER:
        WARNS.append('git tag 最新 %s ≠ VERSION %s（⚠ 若正要发新版，属正常：tag 在 commit 之后打）'
                     % (tags[0], VER))
    else:
        print('  [6] git tag 最新 = %s ✓' % (tags[0] if tags else '(无)'))
except Exception as e:
    WARNS.append('git tag 查询失败: %r' % (e,))

# ---------------------------------------------------------------- 汇总
print()
for w in WARNS:
    print('  ⚠ %s' % w)
if FAILS:
    print()
    print('  ✗ 版本不一致 %d 处：' % len(FAILS))
    for f in FAILS:
        print('     - %s' % f)
    print()
    print('  ⇒ 改法：只改根 `VERSION`，然后把 README/change_log/package.json 同步到同一个值 ✓')
    sys.exit(1)
print('  ✓ 版本一致性检查通过（单一来源: VERSION）')
sys.exit(0)
