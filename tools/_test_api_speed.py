# -*- coding: utf-8 -*-
"""★ 守门：看板接口**不许被"每次都真扫进程"拖慢** ✓ ＋ 超时错误**必须说人话** ✓。

## 事故（用户 2026-09-30 报错截图）
界面弹红条：**「signal is aborted without reason」** ✗。两条根因（都已修 ✓）：

1. **前端**：`api.ts` 的 `ctl.abort()` **不带原因** ✗ ⇒ 浏览器抛出的原始文案就是那句
   （`abort()` 无 reason 时的标准文案 ✓）⇒ **把实现细节当错误弹给用户** ✗✗（完全看不懂 ✓）。
2. **后端**：`mine._procs()` 每次都先 `core._CACHE.pop('procs', None)` ✗ ⇒
   **每次轮询都真起一次 PowerShell 扫进程** ⇒ `/api/mine/state` 实测 **1.3 秒/次** ✗
   （前端每几秒轮询一次 ✓）⇒ 机器一忙就顶到前端 40 秒超时 ⇒ 被自己的定时器取消 ⇒ 弹那条红字 ✗。

## 本守门查四件
1. **行为** ✓：`mine._procs()` 第二次调用**必须命中缓存**（≪ 第一次 ✓），
   而 `_procs(fresh=True)` **必须真的重扫** ✓（启停路径靠它 ✓）；
2. **静态**：`fresh=True` 只许出现在**启停/闸门**路径 ✓ —— **只读展示**（`state()`）不许用 ✗
   （那是本次性能问题的现场 ✓）；
3. **静态**：`main.py` 有**慢请求日志**（≥2 秒记一行 ✓）⇒ 下次再出现能直接指名 ✓；
4. **静态**：前端 `abort()` **必须带原因** ✓，且超时被翻译成**人话**（`ApiError.kind === 'timeout'` ✓）。
"""
import io
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'dashboard', 'api'))
sys.path.insert(0, os.path.join(ROOT, 'engine'))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
FAIL = []


def chk(desc, cond, hint=''):
    print('  %s %s%s' % ('✓' if cond else '✗', desc, ('（%s）' % hint) if hint else ''))
    if not cond:
        FAIL.append(desc)


def src(rel):
    return io.open(os.path.join(ROOT, rel), encoding='utf-8').read()


print('=' * 96)
print('① 行为：`_procs()` 命中缓存 ✓ ／ `_procs(fresh=True)` 真重扫 ✓')
print('=' * 96)
try:
    from app import mine                                                        # noqa: E402
    mine._procs(fresh=True)                    # 先热身一次（确保进程查询本身可用 ✓）
    t0 = time.time()
    n_cold = len(mine._procs(fresh=True))      # 强制真扫 ✓
    t_cold = time.time() - t0
    t0 = time.time()
    n_cached = len(mine._procs())              # 立刻再读 ⇒ 必须命中缓存 ✓
    t_cached = time.time() - t0
    t0 = time.time()
    n_fresh = len(mine._procs(fresh=True))     # 强制真扫 ⇒ 又要花时间 ✓
    t_fresh = time.time() - t0
    print('  冷扫 %.3fs（%d 个进程）· 缓存读 %.4fs（%d 个）· 再次强制扫 %.3fs（%d 个）'
          % (t_cold, n_cold, t_cached, n_cached, t_fresh, n_fresh))
    chk('★ 第二次（默认）**命中缓存** ⇒ 比冷扫快一个量级 ✓',
        t_cached < max(t_cold, 0.05) / 3.0, '缓存 %.4fs vs 冷扫 %.3fs' % (t_cached, t_cold))
    chk('★ `fresh=True` **确实重扫**（不是也吃缓存 ⇒ 启停路径才准 ✓）',
        t_fresh > t_cached, 'fresh %.3fs vs 缓存 %.4fs' % (t_fresh, t_cached))
    chk('两种方式**结果一致** ✓（缓存不许改变内容 ✗）', n_cached == n_fresh == n_cold)
except Exception as e:                                                          # noqa: BLE001
    chk('能 import `app.mine` 并调用 `_procs()` ✓', False, repr(e)[:160])

print()
print('=' * 96)
print('② 静态：`fresh=True` 只许出现在**启停/闸门**路径 ✓，只读展示不许用 ✗')
print('=' * 96)
mi = src('dashboard/api/app/mine.py')
_i_state = mi.find('def state(')
_state_seg = mi[_i_state:_i_state + 6000] if _i_state > 0 else ''
chk('★ `state()`（看板轮询的主接口）**不用** `fresh=True` ✓',
    _i_state > 0 and 'fresh=True' not in _state_seg)
_hits = [i for i, l in enumerate(mi.splitlines(), 1) if 'fresh=True' in l and not l.strip().startswith(('*', '#'))]
chk('`fresh=True` 的调用点是**有意义的少数几处**（启停/等待/闸门 ✓）',
    3 <= len(_hits) <= 12, '实 %d 处：%s' % (len(_hits), _hits))
chk('启停路径确实用上了（`scheduler(fresh=True)` ✓ / `pool_engines(…, fresh=True)` ✓）',
    'scheduler(fresh=True)' in mi and 'pool_engines(pool, c, fresh=True)' in mi
    and 'pool_engines(pool, fresh=True)' in mi)
chk('`_procs(fresh=False)` 的默认值没被改掉 ✓（否则缓存失效 ✗）',
    re.search(r'def _procs\(fresh=False\):', mi) is not None)

print()
print('=' * 96)
print('③ 静态：后端有**慢请求日志**（下次再"看不懂的红条"能直接指名 ✓）')
print('=' * 96)
mn = src('dashboard/api/app/main.py')
chk('`main.py` 注册了慢请求中间件 ✓', '_log_slow_request' in mn and "@app.middleware('http')" in mn)
chk('阈值是 2 秒 ✓（`_SLOW_S = 2.0`）', re.search(r'_SLOW_S\s*=\s*2\.0', mn) is not None)
chk('写到固定位置 ✓（`_api_slow.log`，便于排障）', '_api_slow.log' in mn)
chk('★ 它**不许影响请求** ✓（异常全吞 ✓）',
    # ⚠ 行尾可能有 `# noqa` 注释 ✗（我第一版正则没留它 ⇒ 假失败 ✓）
    re.search(r'except Exception:[^\n]*\n\s*pass', mn) is not None)

print()
print('=' * 96)
print('④ 静态：前端 `abort()` **必须带原因** ✓ ＋ 超时**必须说人话** ✓')
print('=' * 96)
ap = src('dashboard/web/src/api.ts')
# ⚠ 必须**剔掉注释**再判 ✗ —— 说明文字里会**引用**旧写法 `ctl.abort()`（我第一版就被自己绊倒 ✓）
ap_code = '\n'.join(l for l in ap.splitlines()
                    if not l.strip().startswith(('//', '*', '/*')))
chk('★ 没有"不带原因"的 `abort()` ✗（那正是那句怪文案的来源 ✓）',
    re.search(r'\.abort\(\)', ap_code) is None,
    '' if re.search(r'\.abort\(\)', ap_code) is None else '还残留无参 abort() ✗')
chk('所有 `abort(` 都带了参数 ✓',
    all(')' in ap[m.start():m.start() + 90] and ')' != ap[m.start() + 1]
        for m in re.finditer(r'\.abort\(', ap)))
chk('定义了 `ApiError` 且带 `kind` ✓（超时可被区分 ✓）',
    'class ApiError' in ap and "kind: 'timeout' | 'http' | 'network'" in ap)
chk('★ 超时文案是**人话** ✓（含"请求超时"✓，且说明"动作通常已生效"✓）',
    '请求超时' in ap and '动作' in ap)
chk('`DOMException` 用了 `TimeoutError` 名字 ✓（便于判定 ✓）',
    "new DOMException(" in ap and "'TimeoutError'" in ap)

print()
print('✗ 失败：%s' % FAIL if FAIL else
      '✓ 全过：轮询走缓存 ✓ · 启停仍真查 ✓ · 慢请求有日志 ✓ · 超时说人话 ✓')
sys.exit(1 if FAIL else 0)
