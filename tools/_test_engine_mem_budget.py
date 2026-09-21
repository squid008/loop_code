# -*- coding: utf-8 -*-
"""★★★★★ 引擎「私有缓存**字节预算**」守门（2026-09-21 新增 · 真实事故驱动）

★ 为什么需要（用户："走治本的方案A吧"）：
  1000 池单代被外部采样抓到 **私有内存 8 分钟到 14.6 GB**（工作集 16.6 GB）✗，
  而且**锯齿式上台阶、回不到基线** ⇒ 是缓存在囤 ✗。
  根因：`LRU_MAX=400` / `CACHE2_MAX=150` 只限**条数** ✗，而单条体积随**池宽**变
  （1000 池 L1 子面板 = 2094 日 × 2818 股 ⇒ 单条 ≈ 47 MB ⇒ 400 条 ≈ 18.8 GB ✗✗）
  ⇒ 三池并行把 47.9 GB 的机器压到只剩 1.7 GB ⇒ 换页 ⇒ 单代 110~172 分钟 ✗

⇒ 本守门钉住四件事（**只测"缓存回收"，不碰任何数值口径** ✓）：
  ① `trim_cache_mb()` 存在，且**真的按字节**裁（动态：造 10 个 10 MB 数组 ⇒ 裁到 25 MB 内 ✓）
  ② 三处裁剪点都**同时**调用了（`_LRU` 一次 + `cache2` 两次 ✓）—— 少一处就白改 ✗
  ③ 启动参数有 `--lru_mb / --cache2_mb / --batch_mb`，且**传进了** `set_mem_budget()` ✓
  ④ L1 批大小有**按字节自适应**（宽池不许一批就吃 2 GB ✗）
  ⑤ ★★ **第二刀（2026-09-21）**："按字节"必须按**真实钉住的**字节 ✗ ——
     numpy **视图**的 `nbytes` 是视图自己的大小，却让**整个底座**活着 ✗
     而引擎缓存里存的恰恰大量是"子面板的切片/移位视图" ✓ ⇒ 账实不符 ⇒ 预算失效 ✗
     （gen36 实测：L1 期间工作集 7.25 → 11.08 GB 单调爬、L1 一结束立刻回落 ✓）
     ⇒ 本守门新增**视图用例**：100MB 底座 / 20MB 视图在 50MB 预算下**必须被裁掉** ✓
       ＋ 同一底座的多份视图**不许重复计** ✓ ＋ 嵌套容器也要能估到 ✓
"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ROOT = r'd:\loop_code'
ENG = os.path.join(ROOT, 'engine', 'loop_engine.py')
FAIL = []


def chk(desc, cond, hint=''):
    print('  %s %s' % ('✓' if cond else '✗', desc))
    if not cond:
        FAIL.append(desc + ('（%s）' % hint if hint else ''))


src = io.open(ENG, encoding='utf-8').read()

print('【1】`trim_cache_mb()` 真的按字节裁（动态验证）')
try:
    sys.path.insert(0, os.path.join(ROOT, 'engine'))
    import numpy as np
    import loop_engine as LE
    chk('loop_engine.trim_cache_mb 存在', hasattr(LE, 'trim_cache_mb'))
    if hasattr(LE, 'trim_cache_mb'):
        cache = {}
        for i in range(10):                                  # 10 个 10 MB 的块 = 100 MB ✓
            cache['k%02d' % i] = np.zeros(2621440, dtype='float32')
        left = LE.trim_cache_mb(cache, 25.0)                 # 预算 25 MB ⇒ 只该剩 ≤ 25 MB ✓
        chk('10×10MB 在 25MB 预算下被裁到 ≤25MB（实剩 %.0f MB / %d 个）' % (left, len(cache)),
            left <= 25.0 + 1e-6, '按条数裁是裁不动的 ✗')
        chk('裁掉的是**最旧**的（保留尾部 ⇒ dict 插入序 ✓）',
            ('k00' not in cache) and (cache and 'k09' in cache))
        big = {'a': np.zeros(2621440, dtype='float32')}
        chk('预算内不动手（1 个 10MB ≤ 50MB ⇒ 原样 ✓）',
            abs(LE.trim_cache_mb(big, 50.0) - 10.0) < 0.5 and 'a' in big)

        # ★★★★★ 2026-09-21（治本**第二刀** · 视图漏算）★ 这是本次真事故的**回归测试** ✓
        #   真因：缓存里存的是**子面板的切片/移位视图** ⇒ 只数视图自己的 `nbytes`
        #   ⇒ 账上远小于实占 ⇒ 预算**形同虚设** ✗
        #   （gen36 实测：L1 期间工作集 7.25 → 11.08 GB **单调爬**，L1 一结束立刻回落 7.51 ✓
        #     —— 掉的那一块正好是 `_LRU.clear()` 执行的一瞬 ⇒ 定位证据 ✓）
        _base = np.zeros(26214400, dtype='float32')          # 100 MB 底座
        _view = _base[::5]                                   # 20 MB 视图（底座仍 100 MB ✓）
        c2 = {'v': _view}
        got = LE.trim_cache_mb(c2, 50.0)
        chk('视图按**底座**计（100MB 底座 / 20MB 视图 ⇒ 50MB 预算下必须裁掉，实剩 %d 个）' % len(c2),
            len(c2) == 0 and got <= 50.0 + 1e-6,
            '只数视图自己的 nbytes ⇒ 账面 20MB 以为"没超" ⇒ 不裁 ✗（这就是内存爬升的根因 ✓）')
        c3 = {'a': _base, 'b': _view, 'c': _base[::3]}       # 同一底座的三份引用/视图 ✓
        got3 = LE.trim_cache_mb(c3, 150.0)
        chk('同一底座的多份视图**不重复计**（总计 100MB ⇒ 150MB 预算内原样保留，实 %.0f MB / %d 个）'
            % (got3, len(c3)), len(c3) == 3 and got3 <= 150.0 + 1e-6,
            '重复计会把 100MB 算成 300MB ⇒ 误裁 ✗')
        _nested = {'x': (_view, {'y': _base})}               # 嵌套容器里也要能算到 ✓
        chk('嵌套 dict/tuple 里的数组也能算到（应 ≈100MB）',
            LE.trim_cache_mb(_nested, 1000.0) > 90.0)
except Exception as e:                                        # noqa: BLE001
    chk('能 import loop_engine 并调用 trim_cache_mb', False,
        '%s: %s' % (type(e).__name__, str(e)[:110]))

print('\n【2】三处裁剪点都接上了（少一处就白改 ✗）')
# ★ 只数**行首的调用**（`^\s*trim_cache_mb\(`）⇒ 注释/文档串里的提及不算 ✗（自测时踩过 ✓）
# ★ 2026-09-21 补第二步后：应该是 **4 处** —— `_LRU` 批末×1 + **`_LRU` 批内（每 8 个候选）×1**
#   + `cache2` 去相关×1 + `cache2` 去重×1 ✓（少任何一处都会让内存重新上台阶 ✗）
n_call = len(re.findall(r'^[ \t]+trim_cache_mb\(', src, re.M))
chk('trim_cache_mb 被**调用** 4 次（_LRU 批末+批内 · cache2 去相关+去重，实 %d）' % n_call, n_call == 4)
chk('_LRU 在**批内**也有一次（防"一批之内一路上台阶"✗）',
    re.search(r"if i and \(i % 8\) == 0:\s*\n\s*trim_cache_mb\(_LRU, LRU_MB\)", src) is not None,
    '实测：只靠批末裁剪，第一批就会顶到 8.9 GB ✗')
chk('_LRU 裁剪处同时调了字节版',
    re.search(r'trim_cache\(_LRU, LRU_MAX\)[^\n]*\n[^\n]*trim_cache_mb\(_LRU, LRU_MB\)', src) is not None)
_n2 = len(re.findall(r'trim_cache\(cache2, CACHE2_MAX\)[^\n]*\n[^\n]*trim_cache_mb\(cache2, CACHE2_MB\)', src))
chk('两处 cache2 裁剪（去相关 + 去重）都接了字节版（实 %d 处）' % _n2, _n2 == 2,
    '两处 cache2 都要接 ✓')

print('\n【3】启动参数与预算落地')
for a in ('--lru_mb', '--cache2_mb', '--batch_mb'):
    chk('%s 存在' % a, a in src)
chk('set_mem_budget 接收三个 MB 参数',
    re.search(r'def set_mem_budget\([^)]*lru_mb[^)]*cache2_mb[^)]*batch_mb', src, re.S) is not None)
chk('main 里把三个 MB 参数传进了 set_mem_budget',
    re.search(r'set_mem_budget\(_args\.lru_max, _args\.cache2_max, _args\.vreuse_cap_mb,\s*\n?\s*'
              r'_args\.lru_mb, _args\.cache2_mb, _args\.batch_mb\)', src) is not None)
chk('全局 LRU_MB / CACHE2_MB / BATCH_MB 有定义', all(
    re.search(r'^%s\s*=' % k, src, re.M) for k in ('LRU_MB', 'CACHE2_MB', 'BATCH_MB')))

print('\n【4】L1 批大小按字节自适应（宽池不许一批 2 GB ✗）')
chk('有 BATCH_MB / 单条 MB 的自适应代码',
    ('_per_mb' in src) and re.search(r'BATCH_MB\s*/\s*_per_mb', src) is not None)
chk('自适应在 BATCH = args.batch 之后生效',
    re.search(r'BATCH = args\.batch[\s\S]{0,1200}?BATCH = _cap', src) is not None)

print('\n' + ('★ 全过 ✓ 引擎私有缓存已是"字节预算"（内存有硬上限 ✓）' if not FAIL
             else '✗ 有 %d 项没过：\n  - %s' % (len(FAIL), '\n  - '.join(FAIL))))
sys.exit(1 if FAIL else 0)
