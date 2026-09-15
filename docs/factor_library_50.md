# 因子库（池 = 50）

> 当前 **0 个入库**
> 本文件由引擎在**每代末尾自动同步**（`--mine_pool=50` 时生效；实现见 `_lib_sync`）。
> ⚠ 与全A 轨道的 `docs/factor_library.md` **互不读写**（池隔离，见 roadmap §8.42）。
> ★ 2026-09-15：**本池尚未开采**（`bank=0`；数据文件 `loop_journal_50.md` / `loop_archive_50.csv` / `loop_pool_obs_50.csv` / `loop_strip_style_50.csv` 已就位）。
> 首个因子入库时，引擎会**自动**把条目同步进本表 ✓

---

## 因子总览

| 编号 | 入库代数 | 家族 | 一句话 | 状态 |
|---|---|---|---|---|

## 因子明细

## 相关文件导航

| 文件 | 内容 |
|---|---|
| `docs/factor_library_50.md`（本文件） | 池 **50** 的入库因子（只增不改） |
| `docs/factor_library.md` | 全A 轨道的入库因子 |
| **`docs/factor_library_crosspool.md`** | ★ **跨池派生视图**：各池库里**全A 有效**的因子去重 + 池标签并集修正（`python tools/build_crosspool_view.py` 生成） |
| `docs/loop_journal_50.md` | 池 **50** 的每代诊断 + B角下一代参数 |
| `docs/loop_pool_obs_50.csv` | 池 **50** 候选的**三池池内指标**宽表 |
| `docs/loop_archive_50.csv` | 池 **50** 每代 L2 全量候选流水 |
