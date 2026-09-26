# -*- coding: utf-8 -*-
"""loop_cache.py — 运行期可变缓存 + L1/内存预算状态（2026-09-26 文件级拆分）

★ 用法：`import loop_cache as _C`，用 `_C.VCACHE` / `_C._LRU` / `_C.L1_POOL_MASK`（模块引用，运行时取）。
  这些是**运行期可变**的（base_fields / set_mem_budget 改它们），不要值拷贝。
"""
_BASE = None
L1_STOCKS = 2000
L1_ROWS = None
L1_COLS = None
L1_POOL_MASK = None

_LRU = {}
LRU_MAX = 400
CACHE2_MAX = 150
LRU_MB = 1200.0
CACHE2_MB = 800.0
BATCH_MB = 1500.0
VCACHE = {}
_VREUSE_MB = [0.0]
_VREUSE_CAP_MB = 800.0

PANEL_CACHE = 'off'

from loop_persist import _real_mb


def set_panel_cache(mode):
    """切换面板缓存模式：`off`(默认, 现状) / `use`(必须命中) / `build`(构造并落盘)。

    ★ 必须在 `run()` 之前调用（与 `set_mine_pool` 同理）：`base_fields()` 在 run 内首次被调用。
    """
    m = (mode or 'off').strip().lower()
    if m not in ('off', 'use', 'build'):
        raise SystemExit('[--panel_cache] 非法取值 %r（可选: off/use/build）' % (mode,))
    PANEL_CACHE = m
    return PANEL_CACHE


def set_mem_budget(lru_max=400, cache2_max=150, vreuse_cap_mb=800.0,
                   lru_mb=1200.0, cache2_mb=800.0, batch_mb=1500.0):
    """调「**每进程私有缓存**」的上限。

    ★ 为什么需要它：并行跑 N 个池时，**面板**可以靠 `--panel_cache=use` 跨进程共享，
      但 `_LRU` / `cache2` / `VCACHE` 是**每进程私有**的（私有脏写，不能共享）⇒
      它们才是"并行时的内存地板"。要把总占用压到某个数（如 ≤10 GB），
      就得按 N 把这份预算切小 ✓
    ★ 代价：缓存越小 ⇒ 越多的子树要**现场重算** ⇒ 每代变慢（时间换内存）。

    ★★★★★ 2026-09-21 **治本**（用户："走治本的方案A吧"）：**条数上限管不住内存** ✗
      —— 实测（`ai_test/_memprof_1000.py` 外部采样 · 1000 池单代）：
        · `--n=800` 一代里，私有内存 **1 分钟到 4.9 GB、8 分钟到 14.6 GB（工作集 16.6 GB）** ✗
        · 而且是**锯齿式上台阶**（12.5 ↔ 14.8 GB 反复 ✓）⇒ 回不到基线 = **缓存在囤** ✗
        · 根因：`LRU_MAX = 400`、`CACHE2_MAX = 150` 都是**条数** ✗，而单条的体积随**池宽**变：
          1000 池的 L1 子面板 = **2094 日 × 2818 股**（池并集 ✓ 实测日志 ✓）⇒ 单条 ≈ **47 MB** ✗
          ⇒ `400 条 × 47 MB ≈ 18.8 GB` ✗✗（引擎日志里 VCACHE 早就按 MB 算了 ✓，
             只有这两个缓存漏了 ✗）
        · 池越大 ⇒ 单条越大 ⇒ 越容易把机器压到换页（1000 池单代 110~172 分钟 ✗ = 嫌疑根因 ✓）
      ⇒ 修法（**只改"缓存回收"，不动任何数值口径 ✓**）：
        ① `trim_cache_mb()`：按 `arr.nbytes` 累计，超预算从**最旧**开始淘汰 ⇒ **硬上限** ✓
        ② `--lru_mb / --cache2_mb`：字节预算（条数上限**保留作兜底** ✓）
        ③ `--batch_mb`：L1 批大小**按字节自适应** ✗（固定 40 个时，宽池一批就 ≈1.9 GB ✗）
    """
    LRU_MAX = max(20, int(lru_max))
    CACHE2_MAX = max(20, int(cache2_max))
    _VREUSE_CAP_MB = max(0.0, float(vreuse_cap_mb))
    LRU_MB = max(50.0, float(lru_mb))
    CACHE2_MB = max(50.0, float(cache2_mb))
    BATCH_MB = max(100.0, float(batch_mb))
    print('[内存预算] 每进程私有缓存: LRU=%d 条 / ≤%.0f MB · cache2=%d 条 / ≤%.0f MB · '
          'VCACHE≤%.0f MB · L1 单批≤%.0f MB (面板是否共享见 --panel_cache)'
          % (LRU_MAX, LRU_MB, CACHE2_MAX, CACHE2_MB, _VREUSE_CAP_MB, BATCH_MB), flush=True)
    return LRU_MAX, CACHE2_MAX, _VREUSE_CAP_MB


def trim_cache(cache, cap):
    """子树缓存容量控制: 条目超过 cap 时淘汰最早插入的键(dict 保插入序)。
    子树缓存只是加速(命中失败会重算), 淘汰不影响正确性。"""
    if cache is not None and len(cache) > cap:
        for k in list(cache.keys())[:len(cache) - cap]:
            cache.pop(k, None)


def _cache_real_mb(cache):
    """整个缓存的**真实**占用 MB（共用一份 `seen` ⇒ 多份视图共享的底座只计一次 ✓）。"""
    seen = set()
    return sum(_real_mb(v, seen) for v in cache.values())


def trim_cache_mb(cache, max_mb):
    """★★★★★ 2026-09-21（治本）：按**真实字节**裁缓存 ⇒ 内存有**硬上限** ✓

    ★ 为什么必须按字节（实测见 `set_mem_budget` 的注释 ✓）：
      `trim_cache` 只管"条数"✗，而单条大小随**池宽**变化 ——
      1000 池的 L1 子面板是 2094 日 × 2818 股 ⇒ 单条 ≈ **47 MB** ✗
      ⇒ 400 条 ≈ **18.8 GB** ✗（实测这一代的私有内存峰值 14.6 GB ✓ 工作集 16.6 GB ✓）
      ⇒ 三个池并行就把 47.9 GB 的机器压到只剩 1.7 GB ⇒ 换页 ⇒ 单代 110~172 分钟 ✗
    ★★ 第二刀（2026-09-21）：**"按字节"还不够 —— 要按"真实钉住的字节"** ✗
      见 `_real_mb`：只数视图自己的 nbytes ⇒ 账实不符 ⇒ 预算**形同虚设** ✗
    ★ 淘汰策略：dict 保插入序 ⇒ 从**最旧**开始丢 ✓（缓存只是加速、丢了会重算 ⇒ 不影响正确性 ✓）
    ★ 返回：裁完之后的**真实**总 MB（便于日志/守门核验 ✓）
    """
    if cache is None:
        return 0.0
    try:
        tot = _cache_real_mb(cache)
        if tot <= max_mb:
            return tot
        n0 = len(cache)
        for k in list(cache.keys()):
            if tot <= max_mb:
                break
            cache.pop(k, None)
            # ⚠ 必须**重算**而不是"减掉刚才那份" ✗ —— 底座可能被**多份视图共享** ✓
            #   （减掉就会重复扣，把预算算成"早就达标"⇒ 又会提前停手 ✗）
            tot = _cache_real_mb(cache)
        if n0 > len(cache):
            print('  [内存预算] 缓存裁至 %.0f MB（丢最旧 %d 个 ✓ 口径=**含视图底座**的真实占用 ✓）'
                  % (tot, n0 - len(cache)), flush=True)
        return max(tot, 0.0)
    except Exception:                                        # noqa: BLE001
        return 0.0                                           # 裁不动也不能影响主流程 ✓
