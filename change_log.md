# Change Log / 变更日志

本文件**事无巨细**地记录每一次改动。格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [语义化版本 SemVer](https://semver.org/lang/zh-CN/)：
**MAJOR**（不兼容改动）· **MINOR**（向后兼容的功能新增）· **PATCH**（向后兼容的修复）。

> ★ **归档约定（2026-09-27 起）**：本文件**只保留最近 15 个版本**，
> 更早的条目整段搬到 [`history/change_log_archive.md`](history/change_log_archive.md)（**原文一字未改** ✓；
> 2026-09-28 从仓库根目录挪进 `history/` ✓ —— 根目录只留活跃文件，历史归 `history/` ✓）。
> 为什么：本文件曾长到 **549 KB / 7683 行 / 154 个版本** ⇒ 查最近改动得先翻过一年份的历史 ✗
> （八维评分里「文档」扣分的正是这一条 ✓）。新增条目照旧写在**最上方** ✓。

> **改动 → 版本 → tag 的动作约定**（沿用 README「版本与回退」）：
> 每次改动 = **一次 commit**；每个版本 = **一个 annotated tag**（`git tag -a vX.Y.Z -F <说明>`）。

---

> ★ **旁注（2026-09-15）**：本文件历史条目里出现的 `docs/history/` 归档区，
> 已于 2026-09-15 整体移到**仓库根 `history/`**（`docs/` 只放活跃文档）。
> 历史条目**有意保留原文**（不改写记录）✓

> ⚠ **归档动作（2026-09-28）**：本文件头部承诺"只保留最近 15 个版本" ✓，而当时已累积 **24 条** ✗（约定只在 v1.24.0 执行过一次 ⇒ 之后每版漂一格 ✗）
> ⇒ 已把最旧的 9 条**整段原文**搬进 `history/change_log_archive.md` ✓（逐字校验 ✓：条目数 旧 = 新 + 搬走、无重复、版本号集合不变 ✓）。

> ⚠ **归档动作（2026-09-29）**：本文件头部承诺"只保留最近 15 个版本" ✓，而当时已累积 **17 条** ✗（约定只在 v1.24.0 执行过一次 ⇒ 之后每版漂一格 ✗）
> ⇒ 已把最旧的 2 条**整段原文**搬进 `history/change_log_archive.md` ✓（逐字校验 ✓：条目数 旧 = 新 + 搬走、无重复、版本号集合不变 ✓）。

> ⚠ **归档动作（2026-09-29）**：本文件头部承诺"只保留最近 15 个版本" ✓，而当时已累积 **16 条** ✗（约定只在 v1.24.0 执行过一次 ⇒ 之后每版漂一格 ✗）
> ⇒ 已把最旧的 1 条**整段原文**搬进 `history/change_log_archive.md` ✓（逐字校验 ✓：条目数 旧 = 新 + 搬走、无重复、版本号集合不变 ✓）。

> ⚠ **归档动作（2026-09-29）**：本文件头部承诺"只保留最近 15 个版本" ✓，而当时已累积 **16 条** ✗（约定只在 v1.24.0 执行过一次 ⇒ 之后每版漂一格 ✗）
> ⇒ 已把最旧的 1 条**整段原文**搬进 `history/change_log_archive.md` ✓（逐字校验 ✓：条目数 旧 = 新 + 搬走、无重复、版本号集合不变 ✓）。

> ⚠ **归档动作（2026-09-29）**：本文件头部承诺"只保留最近 15 个版本" ✓，而当时已累积 **16 条** ✗（约定只在 v1.24.0 执行过一次 ⇒ 之后每版漂一格 ✗）
> ⇒ 已把最旧的 1 条**整段原文**搬进 `history/change_log_archive.md` ✓（逐字校验 ✓：条目数 旧 = 新 + 搬走、无重复、版本号集合不变 ✓）。

> ⚠ **归档动作（2026-09-30）**：本文件头部承诺"只保留最近 15 个版本" ✓，而当时已累积 **16 条** ✗（约定只在 v1.24.0 执行过一次 ⇒ 之后每版漂一格 ✗）
> ⇒ 已把最旧的 1 条**整段原文**搬进 `history/change_log_archive.md` ✓（逐字校验 ✓：条目数 旧 = 新 + 搬走、无重复、版本号集合不变 ✓）。

> ⚠ **归档动作（2026-10-01）**：本文件头部承诺"只保留最近 15 个版本" ✓，而当时已累积 **16 条** ✗（约定只在 v1.24.0 执行过一次 ⇒ 之后每版漂一格 ✗）
> ⇒ 已把最旧的 1 条**整段原文**搬进 `history/change_log_archive.md` ✓（逐字校验 ✓：条目数 旧 = 新 + 搬走、无重复、版本号集合不变 ✓）。

> ⚠ **归档动作（2026-10-01）**：本文件头部承诺"只保留最近 15 个版本" ✓，而当时已累积 **16 条** ✗（约定只在 v1.24.0 执行过一次 ⇒ 之后每版漂一格 ✗）
> ⇒ 已把最旧的 1 条**整段原文**搬进 `history/change_log_archive.md` ✓（逐字校验 ✓：条目数 旧 = 新 + 搬走、无重复、版本号集合不变 ✓）。

---

> ⚠ **归档动作（2026-10-17）**：本文件承诺只保留最近 15 个版本 ✓，当时已累积 **18** 条 ✗
> ⇒ 已把最旧的 3 条（**1.25.1 / 1.25.2 / 1.25.3**）**整段原文**搬进 `history/change_log_archive.md` ✓（逐字校验：版本集合不变、无重复 ✓）。

> ⚠ **归档动作（2026-10-18）**：本文件承诺只保留最近 15 个版本 ✓，当时已累积 **16** 条 ✗
> ⇒ 已把最旧的 1 条（**1.26.0**）**整段原文**搬进 `history/change_log_archive.md` ✓（逐字校验：版本集合不变、无重复 ✓）。

> ⚠ **归档动作（2026-10-18 第二次）**：承诺只保留最近 15 个版本，当时已累积 **16** 条 ⇒ 已把最旧的 1 条**整段原文**搬进 `history/change_log_archive.md` ✓。

> ⚠ **归档动作（2026-10-18 第三次）**：承诺只保留最近 15 个版本，当时已累积 **16** 条 ⇒ 已把最旧的 1 条**整段原文**搬进 `history/change_log_archive.md` ✓。

> ⚠ **归档动作（2026-10-19）**：承诺只保留最近 15 个版本，当时已累积 **16** 条 ⇒ 已把最旧的 1 条**整段原文**搬进 `history/change_log_archive.md` ✓。

> ⚠ **归档动作（2026-10-19 第二次）**：承诺只保留最近 15 个版本，当时已累积 **16** 条 ⇒ 已把最旧的 1 条**整段原文**搬进 `history/change_log_archive.md` ✓。

> ⚠ **归档动作（2026-10-19 第三次）**：承诺只保留最近 15 个版本，当时已累积 **16** 条 ⇒ 已把最旧的 1 条**整段原文**搬进 `history/change_log_archive.md` ✓。

> ⚠ **归档动作（2026-10-19 第四次）**：承诺只保留最近 15 个版本，当时已累积 **16** 条 ⇒ 已把最旧的 1 条**整段原文**搬进 `history/change_log_archive.md` ✓。

> ⚠ **归档动作（2026-10-19 第五次）**：承诺只保留最近 15 个版本，当时已累积 **16** 条 ⇒ 已把最旧的 1 条**整段原文**搬进 `history/change_log_archive.md` ✓。

> ⚠ **归档动作（2026-10-19 第六次）**：承诺只保留最近 15 个版本，当时已累积 **16** 条 ⇒ 已把最旧的 1 条**整段原文**搬进 `history/change_log_archive.md` ✓。

> ⚠ **归档动作（2026-10-19 第七次）**：承诺只保留最近 15 个版本，当时已累积 **16** 条 ⇒ 已把最旧的 1 条**整段原文**搬进 `history/change_log_archive.md` ✓。

## [1.42.0] — 2026-10-19

> 主题：**L1 排序改为 `mono_n`（风格中性十档单调性）主导** ✓
> 起因：用户 _"L1 排序换成 mono_n 主导，跑 2~3 代看通过数"_。

### 一、依据（n=107，gen161-164 的 L2 候选 vs `strip_calmar` Spearman）

| L1 指标 | vs `strip_calmar` | vs `strip_ann_ex` | vs 日频 `strip_calmar_d` |
|---|---|---|---|
| **`mono_n`（中性化十档单调性）** | **+0.764** | **+0.754** | **+0.770** |
| `ic_n`（风格中性 IC） | +0.386 | +0.332 | +0.396 |
| `ic`（原始 IC） | +0.057 | +0.039 | +0.064 |
| `stab`（旧主项） | **−0.210** | −0.200 | −0.222 |

⇒ `mono_n` 是唯一强预测项，且**零额外成本**（`decile_shape` 已在算、每代落盘）。

### 二、改动

* `engine/loop_metrics.py`：`l1_score(..., mono_n=None)` 增 `mode='mono_n'` = `clip(mono_n, 0, 1)`
* `engine/loop_l1.py`：`_make_score` 增 `mono_n` 分支；缺值（未开 `--style_obs`）
  **回退 `new` 并告警**（不静默 ✓）
* `engine/loop_engine.py`：`--score_mode` choices 加 `'mono_n'`
* `tools/run_tracks.py`：生产 extra `--score_mode=new` → **`--score_mode=mono_n`**（含依据与回退注释）
* `engine/loop_l1.py`（顺带）：`_ic_n` 的异常**不再静默** + 首调用一次性诊断
  （v1.38.3 就是被 `except` 吞掉，导致 gen161 的 `ic_n` 整列 NaN 而日志无线索 ✗；
  实测 gen162 起已恢复正常，2180 条有值 ✓）

### 三、验证

| 项 | 结果 |
|---|---|
| 单元（`ai_test/_test_score_mono_n.py`） | **7/7**：mono_n 裁剪 / 全空回退 / 列缺失回退 / `new`·`ic_n` 逐位不变 / argparse / 生产 extra ✓ |
| `py_compile` / 未定义名 | OK / **0 处**（185 文件）✓ |
| R1 审计 | 无新增（`engine/` 仍只剩既存 `build_fa_pit.main()` 150 行）✓ |
| 前端接线守门 | **全过** ✓ |
| 冒烟（带 `--score_mode=mono_n`） | **4/4**（rc=0 · 无 Traceback/NameError · 全部 state SHA256 未变）✓ |
| 全量回归 | 见 §四 |

### 四、发版回归

★ **全量回归：59/59 全绿** ✓（**实测 14.8 分钟** —— 机器偏慢，
`_test_e2e_l1l2` 248 s / `_test_parallel_runner` 207 s / `_test_gen_determinism` 86 s）。
跑前无挖掘在跑 ✓（且全程**只跑这一个任务**，不与补测并行 —— 2026-10-19 曾因
`build_facs`(5 GB) 与回归测试引擎(2×4.5 GB) 并跑把内存压到 2 GB 而被迫中断）；
跑完**未起引擎** ✓、控制文件已复位 ✓。

---

## [1.41.0] — 2026-10-19

> 主题：**20 日口径的剥风格指标** ✓（用户："20 日的还没算完？挖完会自动算吗？"）
> 此前 `strip2` 只在**入库那一刻**算过、且只喂 md 文档，**不落结构化文件** ⇒ 看板切 20 日永远是空 ✗。

### 一、为什么以前一直空

* `engine/loop_l2.py` 的 `strip2`（副口径剥风格）**算了**，但只进 `_strip2_by_expr`（写 md 用），
  没有独立 CSV。
* `tools/build_facs.py` 三处 `window=5` 硬编码 ⇒ 收尾补测**只跑 5 日** ⇒ 汇总表也只有 5 日。

### 二、改动（A 长期自动 + B 立即回填）

**A（引擎侧，以后自动有）**
* `engine/loop_paths.py`：新增 `STRIP_OBS_20 = docs/loop_strip_style_20.csv`，纳入 `_PATH_KEYS`（各池独立 ✓）
* `engine/loop_persist.py`：新增 **`_dump_strip_detail20()`**（schema-safe；先过滤 `None` 行）
* `engine/loop_l2.py`：`_L2Acc` 增 `strip2_rows`；候选循环收集；代末落盘

**B（补测 + 展示）**
* `tools/build_facs.py`：每因子在 5 日剥风格后**再跑一次 `FWD=20`**（复用同一份中性化因子值），
  写 `docs/loop_strip_style_bank_fwd20.csv`
* `dashboard/api/app/sources/factors.py`：新增 `strip_bank_20()` / `_strip_bank_20_map()`
  （mtime 缓存、命中零 IO）与 **`_merge_strip_into()`**（5 日/20 日**共用**，含 `strip_dd` 恒等式兜底）；
  20 日字段并入 `metrics20`
* **前端零改动**（`METRIC_GROUPS` 在 20 日模式本来就读 `metrics20`）

### 三、验证（实测）

| 项 | 结果 |
|---|---|
| `py_compile` / 未定义名 | OK / **0 处**（185 文件）✓ |
| R1 审计 | 无新增（中途 `_l2_candidates` 到 **122** 行，已压回 **120**）✓ |
| 前端接线守门 | **全过** ✓ |
| 单元（`ai_test/_test_strip_rec_of.py`） | 22 字段齐 / 超额口径逐字未变 / 缺字段不抛 ✓ |
| 全量回归 | 见 §四 |
| 20 日回填 | 见 §五 |

### 四、发版回归

★ **全量回归：59/59 全绿** ✓（**实测 13.8 分钟** —— 机器偏慢，
`_test_e2e_l1l2` 232 s / `_test_parallel_runner` 178 s）。
跑前无挖掘在跑 ✓；跑完**未起引擎** ✓、控制文件已复位 ✓。

### 五、20 日回填

（待补测跑完后回填——本次补测会给全库 68 个因子补上 20 日剥风格）

---

## [1.40.2] — 2026-10-19

> 主题：**面板补齐「超额 · 剥风格后」＋ 分组重排** ✓
> （用户："面板里是不是还得加超额口径·剥风格后的各种指标？然后把组合自身口径期频打点和日频打点
> 放在超额口径上面"）—— 纯展示改动，**判定/排序零改动** ✓。

### 一、改动

* `engine/loop_l2.py`：`strip_rec` 补 **`strip_dd`**（超额 · **期频**回撤 —— 此前只存了日频 `dd_d`）
* `tools/build_facs.py`：汇总表加 `strip_dd` 列
* `dashboard/api/app/sources/factors.py`：
  * 并入 `metrics` 的剥风格字段从 7 个扩到 **14 个**
    （补超额四件套 `strip_ann_ex / strip_dd / strip_calmar / strip_sharpe` 与日频三项）
  * **`strip_dd` 缺失时用恒等式派生**：`|dd| = ann_ex / calmar`
    （老汇总表没有这一列 ⇒ **不必重跑 50 分钟补测**就能显示 ✓）
* `dashboard/web/src/App.tsx`：`METRIC_GROUPS` 顺序改为
  **组合自身（期频 / 日频 / 剥风格期频 / 剥风格日频）→ 超额（同四格）→ 其他**
* **`dashboard/api/app/sources/core.py`：修 `cached()` 的 TTL 起点（真 BUG）** ——
  原实现用**扫描开始前**的 `now` 当时间戳 ⇒ 冷扫耗时（实测 2.0s）把 2 秒 TTL 直接吃光
  ⇒ 缓存**刚写完就已过期** ⇒ 前端每 2 秒轮询几乎每次真扫进程（这也是用户长期抱怨
  `/api/status` 常 2 秒+ 的根因）。改为用**写入完成时刻** ⇒ 缓存读从 **1.2s → 0.0000s** ✓

### 二、验证（实测）

| 项 | 结果 |
|---|---|
| 单元（`ai_test/_test_strip_rec_of.py`） | **22 字段齐** · 组合自身取值对 · 超额口径未变 · 缺字段记 None 不抛 ✓ |
| `py_compile` / 未定义名 | OK / **0 处** ✓ |
| R1 审计 | 无新增（`engine/` 仍只剩既存 `build_fa_pit.main()` 150 行）✓ |
| 前端接线守门 | **全过** ✓ |
| 后端实测（重启后 `/api/library/all`） | F48 的 **14 个 `strip_*` 全部可读**；派生 `strip_dd = −6.02%`、真值 `strip_dd_d = −7.78%`（日频更深，符合"逐日 mark"定义 ✓） |
| 全量回归 | 见 §三 |

### 三、发版回归

* **第 1 轮：58/59** ✗ —— 唯一失败 `_test_api_speed.py`（两项：缓存命中加速比、`fresh=True` 重扫）。
  实测数字：冷扫 **5.139s** · 缓存读 **2.8598s** · 强制扫 2.701s ⇒ 缓存读**根本没命中** ✗。
  **根因是 `cached()` 的真 BUG**（见 §一 最后一条），不是本次展示改动。
  ⇒ 改为"写入完成时刻"作 TTL 起点后：缓存读 **1.2s → 0.0000s**、冷扫 2.525s ⇒ 守门**全过** ✓。
* **第 2 轮：59/59 全绿** ✓（**实测 12.9 分钟** —— 机器仍偏慢，
  `_test_e2e_l1l2` 219 s / `_test_parallel_runner` 174 s）。
  跑前无挖掘在跑 ✓；跑完**未起引擎** ✓、控制文件已复位 ✓。

---

## [1.40.1] — 2026-10-19

> 主题：**组合自身口径的剥风格指标** ✓（用户："组合自身口径下面要不要也加上剥风格后的指标？"）
> 纯展示字段 —— **判定/排序零改动** ✓。

### 一、为什么加

现有 `strip_*` 全是**超额**口径（组合 − 池内等权基准）。指数增强最终看的是
**组合自身的绝对收益**；只看超额回答不了"剥掉风格后这个组合自己还能不能赚"。
`evaluate_real` 本来就返回组合自身四件套 ⇒ **零额外回测成本** ✓。

### 二、改动（4 处）

* `engine/loop_l2.py`：新增 **`_strip_rec_of()`**（主/副口径共用）；`strip_rec` 增加 **7 字段**：
  `strip_ann_top / strip_dd_top / strip_calmar_top / strip_sharpe_top`
  ＋ 日频 `strip_dd_top_d / strip_calmar_top_d / strip_sharpe_top_d`
  （原主口径 10 行、副口径 8 行的 dict 构造收敛到同一函数 ⇒ `_l2_candidates` 反而更短 ✓）
* `tools/build_facs.py`：剥风格补测汇总表加这 7 列（`_merge_csv` 按 key 写，旧行自动补空 ✓）
* `dashboard/api/app/sources/factors.py`：`library()` 里把 7 个字段并进 `f['metrics']`
  （新增按 mtime 缓存的 `_strip_bank_map()`；CSV 字符串转 float）
* `dashboard/web/src/App.tsx`：`METRIC_GROUPS` 新增两格 ——
  「组合自身口径 · 剥风格后（剥 lncap+lnamt）· 期频/日频打点」

### 三、验证

| 项 | 结果 |
|---|---|
| 单元（`ai_test/_test_strip_rec_of.py`） | **4/4**：21 字段齐 / 组合自身取值对 / 超额口径逐字未变 / 缺字段记 `None` 不抛 ✓ |
| `py_compile` / 未定义名 | OK / **0 处** ✓ |
| R1 审计 | 无新增（`engine/` 仍只剩既存 `build_fa_pit.main()` 150 行）✓ |
| 冒烟 `smoke_gen_only` | **4/4**（rc=0 · 无 Traceback/NameError · 全部 state SHA256 未变）✓ |
| 全量回归 | 见 §四 |

### 四、发版回归

* **第 1 轮：58/59** ✗ —— 唯一失败 `_test_api_speed.py`
  （"第二次命中缓存应比冷扫快一个量级"）。
  **根因是本次改动的缓存实现**：`_strip_bank_map()` 首版先调 `strip_bank()` 再比对 mtime
  ⇒ 每次仍把整张 `loop_strip_style_bank.csv` 读一遍（表达式很长）⇒ 缓存命中时仍有 IO ✗。
  ⇒ 改为**先用 `os.path.getmtime` 判缓存**（命中直接返回，零 IO），单独重跑**全过** ✓。
* **第 2 轮：59/59 全绿** ✓（**实测 17.4 分钟** —— 本轮机器同时跑着别的重活，
  `_test_e2e_l1l2` 261 s / `_test_parallel_runner` 258 s 均为平时的 2 倍以上）。
  跑前无挖掘在跑 ✓；跑完**未起引擎** ✓、控制文件已复位 ✓。

---

## [1.40.0] — 2026-10-19

> 主题：**新增「剥风格独立通道」（通道 B）** ✓ —— 纯 alpha 型因子的第二条入库路。
> 起因：用户 _"同意改造，把剥风格口径变成独立通道"_（在 `ic_n` 排序实验之后）。

### 一、为什么必须分开（数据）

现有入库是 **AND**：`calmar2 ≥ 0.701`（含风格 beta）∧ `strip_calmar ≥ 0.15`（剥风格 alpha）
∧ `neg_yr ≤ 2` … ⇒ 实际要求"**既有 beta 又有 alpha**"，而实测两类**不可兼得**：

| 代 | 排序 | L2 候选 | `strip_calmar` 中位 | max | >0 条数 | `calmar2` 中位 |
|---|---|---|---|---|---|---|
| gen162 | `new`（stab） | 28 | −0.160 | −0.090 | **0** | 0.397 |
| gen163 | `ic_n` | 30 | −0.139 | **+1.150** | **4** | −0.069 |

gen163 最强的一条 **`ts_std100(ln_volume)`**：`strip_calmar` **1.150** /
`strip_ann_ex` **6.93%** / `strip_sharpe` **1.349** / `strip_dd` −7.78%，
但 `calmar2` 仅 0.204、`neg_yr` 4 ⇒ 被 AND 门槛拒（用户已拿去独立复测）。

### 二、阈值标定（`loop_archive` ⨝ `loop_strip_style`，gen>=100 共 1496 条）

* `strip_calmar` 中位 **−0.167**、99 分位 0.038；
* `>=0.15` 仅 **5** 条 · `>=0.3` **4** 条 · **`>=0.5` 仅 1 条**（正是上面那条）；
* 历史入库者（12 条有剥风格观测）`strip_calmar` 中位 −0.014、max 0.604。
⇒ 取**极严档**：`0.5 / 3% / 0.8`（**不是**"放宽门槛凑数量"）。

### 三、改动

* `engine/loop_l2.py`
  * 新增 **`strip_channel_b_ok(rr, strip_rec, args, mec)`** —— 纯判定，
    **不要求**原始 calmar / 年超额 / neg_yr（只要求剥风格口径自身 + `|ic|` + 相关性）
  * 新增 **`_apply_strip_channel_b(...)`** —— 接线 + 审计打印（从 `_l2_candidates` 抽出，守 R1）
  * 通道 B 在 `_mec`（与库收益流相关性）**之后**判定 ⇒ 与主通道**同一去重口径** ✓
* `engine/loop_engine.py`：新增 5 个参数（`--strip_channel_b` 默认关；阈值默认 0.5/0.03/0.8/0.02）
* `tools/run_tracks.py`：生产 `extra` 启用通道 B（阈值同上）
* ⚠ **不加 `--strip_channel_b` ⇒ 行为完全不变** ✓

### 四、验证

| 项 | 结果 |
|---|---|
| 单元（`ai_test/_test_strip_channel_b.py`） | **11/11**：默认关 / 各阈值边界（含 `=` 不通过）/ 相关性超限 / 缺字段不抛 ✓ |
| `py_compile` / 未定义名 | OK / **0 处** ✓ |
| R1 审计 | 回到 1 个**既存**违规（`build_fa_pit.main()` 150 行）✓；中途 `_l2_candidates` 被顶到 126 行，已抽函数修回 **120** ✓ |
| 冒烟 `smoke_gen_only` | **4/4**（rc=0 · 无 Traceback/NameError · 全部 state SHA256 未变）✓ |
| 全量回归 | 见 §五 |

### 五、发版回归

* **第 1 轮：58/59** ✗ —— 唯一失败 `_test_gen_determinism.py`（同 seed 逐行一致）。
  **根因是守门自身缺陷**，不是本次改动：它构造子进程 env 时**没固定 `PYTHONHASHSEED`**
  （`tools/_pool_traj.py` 早就设了 ✓，本文件漏了），而差异行只是 `leaf_hist` 的
  **dict 键序**（`amplitude`/`true_range` 顺序互换，**内容完全相同**）⇒ 它变成了"测哈希顺序"。
  ⇒ 已给该守门补 `PYTHONHASHSEED='0'`（含注释说明原因），单独重跑**通过** ✓。
* **第 2 轮：59/59 全绿** ✓（**实测 8.1 分钟** ✓；最慢 `_test_parallel_runner` 167 s ·
  `_test_e2e_l1l2` 123 s · `_test_daily_dd` 37 s ✓）。
  跑前无挖掘在跑 ✓；跑完**未起引擎** ✓、控制文件已复位 ✓。

---

## [1.39.1] — 2026-10-19

> 主题：**修 v1.39.0 的 CLI 漏改** ✗ —— `--score_mode=ic_n` 被 argparse 拒绝（引擎 rc=2）。
> 起因：v1.39.0 只改了 `l1_score` / `_make_score`，**漏改 `loop_engine.py` 的
> `choices=['old','new']`** ⇒ 实验启动后**连崩 2 次**（每次 0.1 分钟）、轮次被烧光 ✗。

### 一、根因（调度器日志逐字）

```
pool=all gen=163 rc=2 :: 命令行/文件用法错误（argparse）
  loop_engine.py: error: argument --score_mode: invalid choice: 'ic_n' (choose from 'old', 'new')
```

随后 `[CTL] ★ 本代崩溃 ⇒ 本轮立刻重试（1/2）` → 再崩 → `本轮已崩 2 次 ⇒ 不再重试`
→ `轮数上限 1 已跑满` ⇒ 调度器干净退出（**没有脏数据** ✓，该代作废）。

★ **为什么会漏**：v1.39.0 的验证只覆盖了**函数层**（`l1_score` / `_make_score` 单元）
和**不带该参数的冒烟**（`smoke_gen_only` 默认参数）⇒ **CLI 解析路径从未被执行** ✗。
这是"验收要覆盖实际路径"的又一例（同类教训：v1.23.0 的拆分事故）。

### 二、修法 + 防再犯

* `engine/loop_engine.py`：`choices=['old', 'new', 'ic_n']`（help 补口径与 `--style_obs` 依赖）
* 单元 `ai_test/_test_score_icn.py` 新增 **[6] 静态断言**：源码必须含
  `choices=['old', 'new', 'ic_n']`（漏改即 FAIL）
* 冒烟改为**带 `--extra=--score_mode=ic_n` 真跑**（真正覆盖 argparse 路径 ✓）

### 三、验证

| 项 | 结果 |
|---|---|
| 单元 6 项 | 全过（含新增的 argparse 断言）✓ |
| 冒烟 `smoke_gen_only --extra=--score_mode=ic_n` | **4/4**（rc=0 · 无 Traceback/NameError · 全部 state SHA256 未变）✓ |
| 全量回归 | 见 §四 |

### 四、发版回归

★ **全量回归：59/59 全绿** ✓（**实测 6.7 分钟** ✓；最慢 `_test_e2e_l1l2` 114 s ·
`_test_parallel_runner` 107 s · `_test_daily_dd` 36 s ✓）。
跑前无挖掘在跑 ✓；跑完**未起引擎** ✓、控制文件已复位 ✓。

---

## [1.39.0] — 2026-10-19

> 主题：**新增 `score_mode=ic_n`（按风格中性 IC 排序）** ✓
> —— 这是目前**唯一与剥风格结果同向**的 L1 指标。
> 起因：用户 _"加个排序跑1代"_（在 v1.38.4 修好 `ic_n` 观测之后）。

### 一、依据（gen162 · 720 条观测 · 28 条 L2 候选）

| 指标 | vs `strip_calmar` | vs `strip_ann_ex` |
|---|---|---|
| `ic`（现行排序的准入门槛） | **−0.211** | −0.161 |
| 现行 `new`（`stab` 主导） | −0.157 | −0.241 |
| **`ic_n`（本版新增）** | **+0.197** | **+0.231** |

* `ic_n` 与 `ic` 仅 **0.536** 相关（中位 0.0064 vs 0.0175）⇒ **有独立信息** ✓
* 全候选 **99 条 `ic_n>0.02`（13.8%）**，但现行排序没把它们送进 L2
  （L2 只有 28 条、且 `strip_calmar` **全部为负**）⇒ 有货可选，是"选错了人" ✓

⚠ **诚实标注**：样本仅 **28 条**（标准误 ±0.19）⇒ `+0.197` **还谈不上显著**。
本版是**一次性实验**，判据事先定死：
**L2 里是否出现 `strip_calmar > 0`**。若仍全负 ⇒ 排序彻底走到头，转生成端。

### 二、改动（默认行为不变）

* `engine/loop_metrics.py::l1_score(..., mode='ic_n', ic_n=None)` —— `clip(ic_n, 0, ∞)`
* `engine/loop_l1.py::_make_score(l1, mode)` —— 排序分**单一入口**；
  `ic_n` 缺值（未开 `--style_obs`）时**回退 `new` 并打印告警**（绝不静默 ✗）
* `_l1_filter` 里原 if/else 三行改为调用 `_make_score`（净减 5 行，守 R1 ✓）
* ⚠ **默认仍是 `new`**（由 `run_tracks.extra` 的 `--score_mode=new` 决定）⇒ 不加参数 = 行为不变 ✓

### 三、验证

| 项 | 结果 |
|---|---|
| 单元（`ai_test/_test_score_icn.py`） | ic_n 模式 / 缺值回退+告警 / `new`·`old` **逐位不变** / 负值 clip ✓ |
| `py_compile` / 未定义名 | OK / **0 处**（185 文件）✓ |
| R1 审计 | 无新增（`engine/` 仍只剩既存 `build_fa_pit.main()` 150 行）✓ |
| 冒烟 `smoke_gen_only` | **4/4**（rc=0 · 无 Traceback/NameError · 全部 state SHA256 未变）✓ |
| 全量回归 | 见 §四 |

### 四、发版回归

★ **全量回归：59/59 全绿** ✓（**实测 6.7 分钟** ✓；最慢 `_test_e2e_l1l2` 113 s ·
`_test_parallel_runner` 107 s · `_test_daily_dd` 36 s ✓）。
跑前无挖掘在跑 ✓；跑完**未起引擎** ✓、控制文件已复位 ✓。

---

## [1.38.4] — 2026-10-18

> 主题：**修 v1.38.3 的 `ic_n` 全 NaN** ✗ —— 观测字段的**行对齐 bug**，引擎判定零改动 ✓。
> 起因：v1.38.3 上线后跑 gen161，`loop_style_obs_ret.csv` 的 `ic_n` **716/716 全为空** ✗。

### 一、根因（已用最小用例复现）

`Rsub_s_n` 在 `loop_stage` 里是 **`[::FWD]` 调仓日视图**
（`Rsub_s = Rsub[::FWD]` → 再 `neutralize_rows`），而 `_ic_n()` 首版直接传了**全期** `vals`
⇒ `batch_ic` 内部广播失败：

```
ValueError: operands could not be broadcast together with shapes (24,300) (120,300)
```

⇒ 被 `except` 吞掉 ⇒ 返回 `None` ⇒ 整列 NaN（**不报错、不写日志**，属于最坏的失败形态 ✗）。

### 二、修法

`_ic_n()` 内先抽样：`vs = [v[::_S.FWD] for v in vals]`，再
`batch_ic(vs, Rsub_s_n, Usub_s, None)`。**判定/排序零改动**（仍是纯观测）。

### 三、验证

| 项 | 结果 |
|---|---|
| 最小用例（`ai_test/_test_ic_n.py`） | `_ic_n` 与 `batch_ic([v[::FWD]], …)` **逐位一致**（0.43068699 ✓） |
| 旧形态复现 | 确实抛 `ValueError`（24×300 vs 120×300）✓ |
| `Rsub_s_n=None` | 返回 `None`（不写假值）✓ |
| `py_compile` / 未定义名 | OK / **0 处**（185 文件）✓ |
| 冒烟 `smoke_gen_only` | **4/4**（rc=0 · 无 Traceback/NameError · 全部 state SHA256 未变）✓ |
| 全量回归 | 见 §四 |

### 四、发版回归

★ **全量回归：59/59 全绿** ✓（**实测 8.7 分钟** ✓；最慢 `_test_parallel_runner` 143 s ·
`_test_e2e_l1l2` 139 s · `_test_daily_dd` 51 s ✓）。
跑前无挖掘在跑 ✓；跑完**未起引擎** ✓、控制文件已复位 ✓。

---

## [1.38.3] — 2026-10-18

> 主题：**风格中性 IC（`ic_n`）观测** ✓ —— **引擎判定/排序零改动** ✗。
> 起因：用户 _"不一定要 IC 高……应该是要年化收益高"_，而实测发现**排序/名额这条路已被排除**
> （B 实验 `score_mode=old` + `--l2=60` ⇒ **L2 通过 0/35、入库 0**）；
> 真正的根因在**剥风格门槛**：gen>=100 有 **38 条**候选过了
> `calmar2/ic2/sharpe2/neg_yr/max_ex_corr` **全部**判据，`strip_calmar` **38/38 全为负**
> （中位 −0.161）⇒ 它们赚的全是风格 beta ✓。

### 一、诊断链（本次三代实验的完整证据）

| 实验 | 参数 | 结果 |
|---|---|---|
| A/B/C 连续 | `score_mode=new` 69 代 | 入库 0 |
| v1.38.1/1.38.2 观测 | 真换手 / 纯多头 / 风格中性 | 纯多头费后与 L2 **相关仅 0.1~0.19**；风格中性后 **−0.449** |
| **B 实验** | `score_mode=old`（≈`\|ic_ir\|`）+ `--l2=60` | **L2 通过 0/35 · 入库 0**（74 min） |

生成端**不背锅**（`loop_style_obs` 63,580 条全候选）：叶子覆盖 **63/63**，
资金流占比仅 **44.9% → 54.8% → 49.7%**（gen 三段），是 **L1 选人后**才变成 85%。
⇒ **排序/名额排除、生成端多样性正常、唯一卡点是「剥掉 lncap+lnamt 后无 alpha」** ✓。

### 二、改动（`engine/loop_l1.py`，纯观测）

* 新增 **`_ic_n(vals, Rsub_s_n, Usub_s)`**：在**风格中性残差收益**上再算一版 IC
  （`batch_ic` + `|·|`，与现有 `ic` 同口径）。
  * 原料 `Rsub_s_n` **本来就算好**（给 `shape_pos_n` 用）⇒ **零额外求值成本** ✓
* `_append_stats()` 增加 `ic_n` 字段；`_write_obs_ret()` 观测文件增加 `ic_n` 列（25 列）。
* ⚠ **不改 score / 不改任何门槛** —— 先验证 `ic_n` 与 `strip_calmar` 的相关是否高于原始 `ic`。

### 三、验证

| 项 | 结果 |
|---|---|
| `py_compile` | OK ✓ |
| `_test_undefined_names` | **0 处**（185 文件）✓ |
| R1 审计 | 无新增（`engine/` 仍只剩既存 `build_fa_pit.main()` 150 行）✓ |
| 单元（`ai_test/_test_obs_ret.py`） | 新文件 **25 列**（`ic_n` 在位）· 旧结构自动轮转 · 公式与追加行为全过 ✓ |
| 冒烟 `smoke_gen_only` | **4/4**（rc=0 · 无 Traceback/NameError · 全部 state SHA256 未变）✓ |

### 四、发版回归

★ **全量回归：59/59 全绿** ✓（**实测 8.6 分钟** ✓；最慢 `_test_e2e_l1l2` 141 s ·
`_test_parallel_runner` 128 s · `_test_panel_cache` 48 s ✓）。
跑前无挖掘在跑 ✓；跑完**未起引擎** ✓、控制文件已复位 ✓。

---

## [1.38.2] — 2026-10-18

> 主题：**纯多头费后代理观测（步骤 1）** ✓ —— **引擎判定/排序零改动** ✗。
> 起因：用户 _"不能用多空来当主指标啊…肯定是看纯多头费后指标当主力"_ ✓
> ⇒ v1.38.1 的 `ret_spread_ann`（多空）与 `ann_ex` 相关 0.667，**但主要来自空头腿**：
> `ret_d10`（最差档）vs `ann_ex` **−0.449**，而 `ret_d1`（多头档）只有 **+0.308**
> ⇒ A 股做不了空，多空指标不可用 ⇒ 本版补齐**纯多头**口径的三块原料 ✓。

### 一、实测（gen148~156 · 195 条 · 同批对比）

| 指标 | vs calmar2 | vs ann_ex | 按它排序 Q1→Q4 的 calmar2 |
|---|---|---|---|
| `ret_spread_ann`（多空，**不可交易**） | 0.532 | 0.667 | 0.290 → 0.443 |
| `ret_top_ann`（纯多头费前） | 0.309 | 0.308 | 0.293 → 0.395 |
| `net_ann`（纯多头费后，旧换手代理） | 0.301 | 0.293 | 0.293 → 0.395 |
| `net_sharpe` | 0.229 | 0.327 | 0.293 → 0.394 |
| `ic` | 0.256 | 0.608 | — |

⇒ 纯多头代理可用（Q4 把 calmar2 抬 **+35%**），但明显弱于多空；三个可修的弱点：
① D1 单档样本太小（≈30 只/期）② 未剥风格 ③ `turn_est = 1−stab` **不是换手**
（与 `ann_ex` 甚至 +0.132）⇒ 本版逐个补。

### 二、改动（2 文件，只增不减）

* **`engine/loop_metrics.py::decile_shape`** 新增返回：
  * `top20_ret` / `top20_std`：**Top20%（D1+D2）** 每期平均收益 / 时序标准差
    （≈60 只/期，降顶档噪声）
  * `turn_top`：**D1 名单跨期 Jaccard 重叠率** ⇒ `1 − 平均重叠` = **真换手**
    （⚠ 中间有期被跳过时相邻两期可能跨更长间隔 ⇒ 换手略偏高，docstring 已注明）
* **`engine/loop_l1.py`**：
  * `_append_stats()` 多带 `ret20/std20/turn_top` ＋ 风格中性后的 `ret_d1_n/std_top_n`
    （风格中性收益**零额外成本** —— 复用已有 `shn` 那次 `decile_shape` 调用 ✓）
  * `_write_obs_ret()` 新增 **10 列**：`turn_top, ret20, std20, ret_d1_n, std_top_n,
    ret20_ann, net20_ann, net20_sharpe, net_n_ann, net_n_sharpe`
  * 新增 **`_ensure_obs_schema()`**：**列结构一变就把旧文件轮转成 `<name>.v1.csv`**
    （数据保留）—— 否则 append 会让新旧行列按位置错位 ✗
* 纯多头口径：
  ```
  ret20_ann = ret20 × (252/FWD)
  net20_ann = ret20_ann − cost × 2 × turn_top × (252/FWD)
  net_n_ann = ret_d1_n × (252/FWD) − cost × 2 × turn_top × (252/FWD)   # 风格中性后
  ```

### 三、验证

| 项 | 结果 |
|---|---|
| `py_compile` | OK ✓ |
| `_test_undefined_names` | **0 处**（185 文件）✓ |
| 单元验证（`ai_test/_test_obs_ret.py`） | 轮转 OK（旧 14 列 → `.v1.csv`）· 新文件 **24 列**（10 个新列齐）· `net20_ann` / `net_n_ann` 与手算**逐位一致** · 同结构再写**不轮转、正确追加** ✓ |
| 冒烟 `smoke_gen_only` | **4/4**（rc=0 · 无 Traceback/NameError · 全部 state SHA256 未变）✓ |
| R1 审计 | 无新增（`engine/` 仍只剩**既存** `build_fa_pit.main()` 150 行）✓ |

⚠ **行为变化：无** ✓（新字段不参与 score/门槛，仍是纯观测）。
⚠ **观测文件要等下一次完整一代才有新列**；旧 6,381 行会保留在
`docs/loop_style_obs_ret.v1.csv` ✓（轮转机制自动做）。

### 四、发版回归

★ **全量回归：59/59 全绿** ✓（**实测 8.4 分钟** ✓；最慢 `_test_e2e_l1l2` 144 s ·
`_test_parallel_runner` 133 s · `_test_daily_dd` 44 s ✓）。
跑前 `_control.json` = `running=false / phase=idle`（无挖掘在跑 ✓，符合前提 ✓）；
跑完**未起引擎** ✓、测试轨迹已还原 ✓。

---

## [1.38.1] — 2026-10-17

> 主题：**L1 费后收益代理观测（阶段 1：只落盘、不改判定）** ✓ —— **引擎判定/排序零改动** ✗。
> 起因：用户 _"不一定要 IC 高，因为 IC 高只是代表排序线性度好，应该是要年化收益高或者费后年化收益高"_ ✓
> ⇒ 实测发现 **L1 根本没有"费后收益"这个量**（只有 ic / stab / 十档单调性 / 换手代理）
> ⇒ 本次先把**原料与代理**落到独立观测文件，攒几代后用离线 join 决定排序目标 ✓。

### 一、背景：为什么不是"简单换个排序"

`docs/loop_style_obs.csv`（全候选 L1 指标）⨝ `docs/loop_archive.csv`（L2 结果），
**n = 1683**，Spearman（`ai_test/_corr_obs_join.py` ✓）：

| L1 指标 | vs calmar2 (gen<100) | vs calmar2 (gen>=100) | vs calmar (gen>=100) |
|---|---|---|---|
| **`score_new`（现行 `stab×(0.5+0.5·shape_pos)`）** | **−0.005** | **−0.066** | **−0.160** |
| `score_old`（`\|ic_ir\|×(0.25+0.75·stab)`） | +0.609 | +0.398 | +0.566 |
| `ic` | +0.571 | +0.415 | +0.556 |
| **`stab`（现行主项）** | **−0.380** | **−0.283** | **−0.403** |
| `shape_pos` | +0.206 | +0.102 | +0.054 |

通过组 vs 未通过组中位数：`ic` **0.058 vs 0.020** · `ic_ir` 0.700 vs 0.192 ·
**`stab` 0.919 vs 0.997（通过组反而更低）** · `max_ex_corr` **0.452 vs 0.772**。

⚠ **与 `engine/loop_l1.py` 头部 2026-09 标定注释（stab 单独 +0.546 / ic_ir −0.317）方向相反** ✗
⇒ 该标定已过期（或口径不同），**待阶段 2 用新口径重标后再动排序** ✓（本次不动 ✓）。

★ 结论：IC 与费后年化只是**中等强度**正相关（0.54），不是目标本身；
先把"费后年化/净夏普"的**廉价代理**量化出来，再决定拿什么当排序目标 ✓。

### 二、改动（3 文件，只增不减）

* **`engine/loop_metrics.py::decile_shape`**：返回新增 `std_top` / `std_spread`
  （顶档 / 多空收益的**时序标准差**）；`d1`/`d10` 原本已算、此前只是没返回 ✓
  * ⚠ 口径确认：分档 `floor((1−RS)·n)` ⇒ **D1 = 因子值最高档（多头档）**，不是 d10
    （实现时差点搞反，已在 docstring 写死 ✓）
* **`engine/loop_l1.py`**：
  * `stats` 行新增 `ret_d1 / ret_d10 / std_top / std_spread`（**纯观测**）
  * 新增 **`_write_obs_ret()`** → 写 **`docs/loop_style_obs_ret.csv`**（**独立文件**：
    老 `loop_style_obs.csv` 已 5.5 万行 / 14 列，直接 append 新列会让新旧表头错位 ✗）
  * 把 stats 装配段抽成 **`_append_stats()`** —— 新增字段把 `_l1_batches` 顶到 **125 行**
    （R1 线 120 ✗）⇒ 抽出后回到线内 ✓
* **`engine/loop_paths.py`**：新增 `STYLE_OBS_RET` 并纳入 `_PATH_KEYS`（各池仍独立轨迹 ✓）

### 三、口径（写死，防再搞反）

```
ret_top_ann    = d1 × (252/FWD)                       # 多头（D1）费前年化
ret_spread_ann = (d1 − d10) × (252/FWD)               # 多空费前年化
net_ann        = ret_top_ann − cost × 2 × turn_est × (252/FWD)   # 费后年化代理
net_sharpe     = net_ann / (std_top × √(252/FWD))
turn_est       = 1 − stab                             # 现状换手代理（同源）
```
观测列：`gen, expr, sign, fwd, cost, stab, turn_est, ret_d1, ret_d10, std_top,
ret_top_ann, ret_spread_ann, net_ann, net_sharpe`。

### 四、验证（★ 据实）

| 项 | 结果 |
|---|---|
| `py_compile` 三文件 | OK ✓ |
| `_test_undefined_names` | **0 处**（185 文件）✓ |
| `_test_ops_sync` | **28/28** ✓ |
| 冒烟 `smoke_gen_only`（真跑引擎） | **4/4**：rc=0 · 无 Traceback/NameError · **全部 `loop_state*.pkl` SHA256 未变**（19 s）✓ |
| 公式单元验证（`ai_test/_test_obs_ret.py`） | `ann=50.4`；`net_ann` 与手算**逐位一致**；`d1<0 ⇒ net_ann<0` ✓ |
| 方向验证（不对称噪声） | 只给 D10 加噪声时 `std_top=0.00002` ⇒ 确认对应 **D1** ✓ |
| R1 审计 | `_l1_batches` 回到 ≤120 ✓；`engine/` 评分范围只剩 **1 个既存**违规：`build_fa_pit.main()` **150 行**（v1.30.0 记录是 102 行 ⇒ **漂移，非本次引入** ✗，单独记账）|

⚠ **本版行为变化：无** ✓（不读新字段、不改 score/门槛；`--gen_only` 冒烟已证 state 逐字节不变）。
⚠ **观测文件本版还不会生成** —— `_write_obs_ret` 在 L1 之后才写，必须跑**完整一代**才有第一批数据 ✓。

### 五、发版回归

★ **全量回归：59/59 全绿** ✓（**实测 7.1 分钟** ✓；最慢 `_test_e2e_l1l2` 119 s ·
`_test_parallel_runner` 107 s · `_test_daily_dd` 42 s ✓）。
跑前 `ai_test/_tracks/_control.json` = `running=false / phase=idle`（无挖掘在跑 ✓，
符合 `release_check` 的前提 ✓）；跑完**未起引擎** ✓、控制文件已复位 ✓。

---

## [1.38.0] — 2026-10-14

> 主题：**财报叶子 +2 —— 自由现金流收益率 `fa_fcf_yield` + 现金 ROA `fa_ocf_ta`** ✓
> 起因：用户问 _"咱们的算子里有自由现金流、ROE、ROA这些吗"_ ✓
> 答案：ROE **有**（`fa_roe`，且早已有因子在用）；**自由现金流没有** ✗；**ROA 做过又删** ✗
>   （`fa_roa` 当年因与 `fa_np_margin` 截面相关 +0.867 被判重复）
> ⇒ 用户拍板 _"1、2都做，要避免共线性相关性太高"_ ✓

### 一、口径**先实测后定**（本次最花时间的一步）

新增叶子前先做**逐日截面 rank 相关**体检（与 `tools/calib_dedup_leaf.py` 同口径：
`E.base_fields()['B']` 全样本 → `E.rank_rows(v[::FWD])` → 相关）；共 10 个候选：

| 候选 | 最大\|相关\| | 主导叶子 | 采用 |
|---|---|---|---|
| `cand_fcf_margin` | 0.412 | barra_earnings_yield | ✗（与另两个 FCF 口径 0.90 / 0.94 共线）|
| `cand_fcf_ta` | 0.428 | barra_earnings_yield | ✗（与 `fcf_yield` 0.914 共线）|
| **`cand_fcf_yield`** | **0.485** | barra_earnings_yield | ★ **采用** |
| `cand_ocf_excash` | 0.545 | fa_accrual | ✗（与 `ocf_ta` 0.989 共线）|
| **`cand_ocf_ta`** | **0.553** | fa_accrual | ★ **采用**（现金 ROA）|
| `cand_ocf_yield` | 0.727 | barra_earnings_yield | ✗ |
| `cand_roa_excash` | **0.824** | fa_roe | ✗ |
| `cand_roa_op` | **0.834** | fa_roe | ✗ |
| `cand_roa_np` | **0.844** | fa_roe | ✗ |
| `cand_roa_yoy` | **0.947** | fa_np_yoy | ✗ |

★ **结论：净利润口径的 ROA 在本仓无解** ✗ —— 四个变体（水平 / 营业利润 / 剔除货币资金 / 同比）
全部与 `fa_roe`·`fa_np_margin`·`fa_np_yoy` 共线 **0.82~0.95** ⇒ 连"换分母"都压不下来
（根因：**分子同源** + 分母在截面上高度同步）⇒ 改用**现金流口径**的资产回报率
（`fa_ocf_ta` = 现金 ROA）✓。该结论已固化进 `engine/build_fa_pit.py` 顶部
（新增第 **(c) 类"试过但删掉"**，免得日后重复试 ✗）。

### 二、实现（`engine/build_fa_pit.py` + `engine/loop_fields.py`）

* **`_ttm()`（新增函数）**：资本开支科目 `cash_paid_for_asset` 源里**没有 TTM 版** ✗
  ⇒ 自己按 YTD 滚 4 季：`TTM(q) = YTD(q) + 上年年报 − 上年同期 YTD`（q 为年报时两项相消 ✓ 公式统一 ✓）。
  ⚠ 这是本项目**第一次**在财报侧做 YTD→TTM —— 原有 15 个叶子全部只用 RQ 已算好的 `*TTM` 字段 ✓。
* `fa_fcf_yield` = `(经营现金流TTM − 资本开支TTM) / 日总市值` —— 与 `fa_pb` 同款：**分子按报告期、分母按日** ✓
* `fa_ocf_ta` = `经营现金流TTM / 总资产`（普通 per-report 常量 ✓）
* **`--cand_out PATH`（新增 CLI）**：把候选列另写一份 h5 供体检，**不改正式输出** ✓
  （默认空 ⇒ 正式行为与改造前一致 ✓）；体检脚本 `ai_test/dedup_check.py` ✓
* `loop_fields.FA_LEAVES` **追加在末尾**（顺序即 critic 结构去重的替换优先级 ✓）+2 ⇒ 叶子池 **61 → 63**

### 三、顺带修的两处（都是实测抓到的）

1. **`build_fa_pit.py` 缺 UTF-8 stdout** ✗：输出重定向到文件时编码是 GBK ⇒ 打印 `⇒` 抛
   `UnicodeEncodeError` **直接中断构建**（实测：跑到 4800/5567 崩 ✗）⇒ 补齐（仓库其它脚本都有 ✓）。
2. **注释记账校正**：顶部原写「扩展：8 → **20** 个叶子」「其它 **19** 个」✗ —— 把"试过但删掉"的
   也算进去了 ⇒ 当时真实落地是 **15** 个 ⇒ 已按实际改正 ✓。

### 四、验证（★ 本项目的证据纪律）

| 项 | 结果 |
|---|---|
| **改动独立性**（旧 15 列逐位不变）| ★ **全部 15 列逐位相同** ✓（`(3309,5384) float32`；对拍脚本 `ai_test/fa_pit_ab_check.py`，基准 = 改动前备份）|
| **体检口径 = 落地口径** | ★ `cand_ocf_ta` ≡ `fa_ocf_ta` ⇒ **BITWISE SAME** ✓（无口径漂移 ✓）|
| **覆盖率**（项目判据：近 3 年 ≥30% ✓）| `fa_fcf_yield` 有效 **66.7%** ✓ · `fa_ocf_ta` 有效 **75.1%** ✓ |
| 重建完整性 | 5567 个 pit 文件 → **5384 只股票全部有效、0 只缺科目** ✓（77 s ✓）|
| 守门 | `_test_ops_manual` ✓ 全过 · `_test_ops_sync` **28/28** ✓（叶子数自动跟着变 63 ✓）· `_test_ops_math` **51/51** ✓ · `_test_undefined_names` **0 处**（185 文件）✓ · `_test_reports_expr` **34/34** ✓ · `_test_ops_registry` **17/17** ✓ |
| 手写手册 | `dashboard/api/app/sources/ops.py::FIELDS_ZH` +2 ✓ · `engine/loop_llm.py` 与 `engine/skills/gen_skill.md` 的财报族语义 +2 ✓（★ 守门当场抓到缺失 ✗ ⇒ 补齐后全过 ✓）|

⚠ **本版行为变化（如实记账）**：叶子池 61 → 63 ⇒ **候选生成空间变大**（新叶子会进入生成 / B角诊断 / 去重）
⇒ 属**功能新增**（SemVer **MINOR** ✓）；`engine/loop_state*.pkl` 的 `bank` **不受影响** ✓（叶子只影响生成侧 ✓）。
⚠ **未做** ✗：新叶子**暂无任何因子用到**（库里 18 个财报因子用的仍是旧叶子 ✓）⇒ 下次挖掘才会开始用 ✓。

### 五、部署动作（★ 三步，缺一不可）

1. `fa_pit.h5` **已重建**（**17 列 / 625 MB** ✓）。
2. ★★ **面板只读缓存必须重建** ✗ —— `fa_pit.h5` 一变 ⇒ 缓存**来源指纹失效** ✗
   （实测 `panelCacheInfo`：`sourceOk=false`、`staleSources=["fa_pit.h5"]`、hint 提示"引擎会拒绝加载"）；
   引擎带 `--panel_cache=use` 会**直接报错**，而看板启动路径会**自动降级为 off** ⇒ 每个引擎各建一份
   4.42 GB 面板 ⇒ 内存需求从 ~12 GB 涨到 **23.8 GB** ⇒ 撞内存护栏 ✗（★ 本次**全量回归第一轮**
   就是这样失败的：`_test_mine_launch` 报"内存不足：可用 20.0 GB，本次需要约 23.8 GB"✗）。
   ⇒ 跑 `python tools/build_panel_cache.py`（**实测 33 s** ✓，缓存 **62 → 64 字段 / 4.70 GB** ✓）
   ⇒ 之后 `sourceOk=true`、`staleSources=[]` ✓ 且 `_test_mine_launch` 单独重跑即过 ✓。
3. `dashboard/api/app/sources/ops.py` 改了 ⇒ **看板后端必须重启**（`reload=false` ✗）✓ 已重启
   （`/api/meta` 回读 **1.38.0** ✓；`/api/ops` 回读已含 `fa_fcf_yield` / `fa_ocf_ta` 与中文名 ✓）。

### 六、发版回归（★ 据实记账）

* **第 1 轮**：`release_check` **58/59** ✗ —— 唯一失败 = `_test_mine_launch.py`，
  根因就是上面第 2 条的**缓存失效连带**（面板共享被降级 ⇒ 内存护栏拒绝 ⇒ 守门拿不到期望的
  命令行/返回体）⇒ **不是**本次叶子改动本身的缺陷 ✓。
* **第 2 轮**（缓存重建后）：**59/59 全绿** ✓（**实测 6.7 分钟** ✓；最慢 `_test_e2e_l1l2` 114 s ·
  `_test_parallel_runner` 106 s · `_test_daily_dd` 38 s ✓）。`_test_panel_cache` 本轮 **24.4 s**
  （上轮仅 1.9 s —— 因为上轮缓存处于失效态、走的是降级路径 ✗）✓。
* 跑完**未留脏状态** ✓（`_control.json` = `running=false / active=[]`，引擎与调度器进程 0 ✓）。
* ⚠ **过程记账**：停机时是**直接杀进程** ⇒ `_control.json` 残留 `running=true` ✗ ⇒
  `release_check` 的前提检查**正确地拒绝了两次** ✓（这是设计，不是缺陷 ✓）；后经看板停止接口复位
  （接口回 422，但复位实际生效 ✓）⇒ 之后回归才跑起来 ✓。

---

## [1.37.1] — 2026-10-08

> 主题：**搬盘（`D:\loop_code` → `E:\quant\loop_code`）后的文档/注释校正** ✓ —— **纯文档版 · 代码零改动** ✗。
> 起因：用户 2026-10-08 _"我把项目从D盘挪到E盘了，你读下各种MD，看看还有啥问题没"_ ⇒ 复核后修掉四处问题 ✓（§一~§四）。

### 一、旧项目根（★ 最要紧：README 照抄会失败 ✗）

`README.md` 的「运行」段仍写 `D:\loop_code\...` ✗ ⇒ **13 个文件 / 29 处**全部改为 `E:\quant\loop_code` ✓：

| 文件 | 处数 | 落点 |
|---|---|---|
| `README.md` | 9 | 「运行」段：`cd` ×2 · `Start-Process -WorkingDirectory` · `loop_status` · `Get-Content` ×4 · 策略回测 `cd` |
| `engine/loop_watch.py` | 3 | docstring「运行 / 日志 / 例」 |
| `engine/loop_status.py` · `engine/audit_f11.py` · `engine/gen_f11_daily.py` | 3 | docstring 用法行 |
| `engine/loop_llm.py` | 2 | `api_key()` docstring（改为 `<仓库根>/` ✓）+ `base = ...` 行尾注释（改为「仓库根（派生，不写死盘符）」✓）|
| `strategies/all01/{all00,all03}.py` · `strategies/all04/{all04,all04_barra,all04_f11_idx}.py` | 9 | 头部用法注释 + `UNIV_PATH` 上方说明注释 |
| `docs/factor_roadmap.md` | 3 | 「续跑方法」代码块 |
| `docs/software_framework.md` | 1 | §0 对照表「本库」路径 |

⚠ **有意不改（约 10 处）** ✗：`docs/log/*`·`.codebuddy/memory/*`（**当时实录** ✓）、`change_log.md` 历史条目 ✓，
以及 `standard/qa_style_obs.py`·`standard/standard_test.py`·`tools/calib_dedup_leaf.py`·`tools/l1_shape_calib.py`·
`tools/_test_pool_tail.py`·`tools/_test_sched_kgen.py` 里「★ 原为硬编码 ⇒ 改为从 `__file__` 派生」的**整改注解** ✓
（改了反而丢掉「为什么这么写」的证据 ✗）。另：`D:\miniconda3\envs\rqdata\python.exe` **不用改** ✓（环境确实在 D 盘 ✓）。

### 二、`待办.md`：两处事实错误 ✗ ＋ 一处自相矛盾

1. **环境名写反** ✗：原写「家里 = conda 环境 `rq`；凡出现 `envs\rqdata\python.exe` 的都是**旧路径**」——
   实测 `conda env list` **没有 `rq`** ✓，只有 **`rqdata`**（`D:\miniconda3\envs\rqdata\python.exe`：Python 3.11.15 /
   numpy 1.26.4 / pandas 2.3.3 ✓）⇒ **`envs\rqdata` 才是能跑的那个** ✓ ⇒ §2 与 §3.1 已按实测更正 ✓。
2. **统计低估** ✗：§3.1 原写「项目根 `E:\quant\loop_code`：仅 **1 处**（README）」——
   实测旧根 **13 个文件 / 29 处** ✓ ⇒ 该表按实测重写 ✓。
3. **自相矛盾**：§0 示例 `D:\work\loop_code` 与 §3.1 的 `E:\quant\loop_code` 打架 ⇒ 已统一 ✓；
   §0 的「期望 HEAD = `d0fbecd`」已过期 ⇒ 改注「以 tag `v1.37.x` 为准」✓。

### 三、顺带核实（不是新 bug，记账 ✓）

* `engine/loop_state*.pkl` **6 个全在** ✓（1.7 / 1.9 / 1.1 / 0.5 / 0.45 / 0.39 MB ✓）⇒ `待办.md §4` 最担心的
  「各池 `bank`/规则/参数**静默归零** ✗」**没有发生** ✓；`config.local.json` ✓ · `.deepseek_key` ✓ ·
  数据盘 `E:\rq` ✓ · `_panel_cache` ✓ · `panel|barra|fa_pit|universe|industry.h5` ✓ · 前端 `node_modules` ✓ · 无残留进程 ✓。
* 根目录残留（**未提交**，仅记录）：`_pull_backup_20261008/`（空目录）、`.log`（2026-09-16 的 uvicorn 日志，已被 `*.log` 忽略 ✓）、
  `QuantaAlpha-main/`（外部参考项目，已忽略 ✓）。⚠ **未**擅自删除 ✗。

### 四、验证

* `python tools/_test_version_sync.py` ⇒ **[1]~[6] 全绿** ✓（VERSION / README / change_log / 后端无硬编码 /
  `/api/meta` 动态读 / 前端 `package.json` / 最新 tag 一致 ✓）。
* 本轮**未动任何运行代码** ✓ ⇒ 无行为变更 ⇒ 不适用「同 seed A/B 逐字节」那套 ✓（无行为可对拍 ✓）。
* ★ **全量回归已跑**：`tools/release_check.py` ⇒ **59/59 全绿** ✓（**实测 6.6 分钟** ✓ —— 机器空闲 ⇒ 比历史那次 39.8 min 快得多 ✓；
  最慢三条 `_test_e2e_l1l2` 106 s · `_test_parallel_runner` 96 s · `_test_daily_dd` 39 s ✓）；
  两个快闸门（`_test_version_sync` / `_test_undefined_names`）先过 ✓；跑完**未留脏状态** ✓
  （`ai_test/_tracks/_control.json` 仍是 `running=false / enabled=[1000,300,500] / stopped=[all] / updated 2026-09-24` ✓，无引擎进程残留 ✓）。
  ⚠ **记账**：这一跑发生在**本版提交之前** ✓，而本条目初稿写的是「**未做**」✗ ⇒ 本行是**据实补记** ✓
  （同 v1.36.0 那次的补记做法 ✓）。

---

## [1.37.0] — 2026-10-01

> 主题：**性能 7 → 8**（八维综合 **8.5 → 8.6** ✓）—— 兑现 09-29 那句
> _「让 mining 真跑一代 n=800，读 `[计时] 去相关` 那行即知」_ ✓。
> ⚠ **纯文档版** ✓：**代码零改动** ✗（只更新 `docs/maintainability.md §五` ＋ 三处记账 ✓）。
> 另：**v1.36.0 的最终一轮全量回归已跑完 ⇒ 59/59 全绿** ✓（39.8 分钟 ✓，据实补记 ✓）。

### 一、性能为什么可以 +1（★ 拿"生产实测"补上那一档）

09-29 那次只给 7 ✓，理由是**"省 ≈25 min"是推算** ✗（当时无一代真跑完 ✗，同规模 A/B 只有
5/33 个候选 ⇒ 缓存 100% 命中 ⇒ **测不出** ✗）。而当时就把**补法**写清了 ✓（零成本 ✓）。
**用户 09-30 起跑到 gen205** ✓ ⇒ 实测到手 ✓（**真实生产日志** ✓，非估算 ✗）：

| 阶段 | 旧（gen191~197） | 新（gen198~205） | 实测 |
|---|---|---|---|
| **去相关** | **1321~1838 s**（命中只 239/7xx ⇒ 其余重算 ✗） | **73~81 s**（「批内就地判定 · **0 次重复求值**」✓） | ★ **省 ≈21~29 min/代** ✓ |
| 整代 | **107~127 min** | **68~81 min** | ★ **≈快 35%** ✓ |
| L2 精筛 | 1595~2561 s | 1110~1710 s | ⚠ **归因不清** ✗（候选数/负载不同 ⇒ **不邀功** ✓） |

⇒ **当初的推算被实测证实** ✓（≈25 min ✓）⇒ **性能 7 → 8** ✓。
⚠ **不给 9** ✗：**L1 仍占整代 ≈67%（52 min）且单核** ✗ ⇒ 须做 **L1 多进程并行**
（≈2~4× ✓，**要动引擎架构 + 内存预算** ✗，且**必然改变运行期行为** ⇒ **不适用"逐位不变"** ✗
⇒ **需用户单独授权** ✓）。

### 二、八维表更新（`docs/maintainability.md §五` ✓）

* 新增 **09-29→10-01 追记** ✓（上面那张实测表 ✓ + "为何不给 9" ✓ + "补法零成本"的因果闭环 ✓）；
* 表头改成 **09-27 v1.24.0 ＋ 09-29 v1.34.0 ＋ 10-01 v1.37.0** ✓；
* 性能行 `7` ⇒ **`8`** ✓ ＋ **综合 `8.5` ⇒ `8.6`**（69/8 = 8.625 ≈ 8.6 ✓）。

### 三、验证

* `tools/_test_version_sync.py` ⇒ ✓（VERSION/README/package.json/change_log 四处同步 ✓）；
* `tools/release_check.py` ⇒ ⚠ **本版是纯文档改动** ✓ ⇒ 提交后**照例补跑全量** ✓
  （**上一版 v1.36.0 的 59/59 刚跑完 ✓**，且本版**未动任何代码** ✗ ⇒ 风险为零 ✓）；
* ⚠ **机器背景**（据实记 ✓）：**另一个项目正在跑重活** ✗ ⇒ 机器被压住（`/api/status` 曾撞 40 秒超时 ✗、
  上一轮全量从 ~20 分钟涨到 **39.8 分钟** ✗）⇒ 与项目记忆里"外部重活会把计时类断言打成假阳性"同源 ✓。

---

## [1.36.0] — 2026-10-01

> 主题：**修「signal is aborted without reason」** ✗（用户 2026-09-30 报错截图）＋
> **顺带查明一个更大的问题**：看板后端已连续跑 **4 天**、且 `reload=false` ⇒ **它跑的是旧代码** ✗。
> ⚠ **引擎数值路径零改动** ✓（只动看板后端/前端 ✓）。

### 一、那条红字是什么（两个根因，都已修 ✓）

1. **前端**：`api.ts` 的 `ctl.abort()` **不带原因** ✗ ⇒ 浏览器抛出的原始文案就是
   「**signal is aborted without reason**」✗ ⇒ 界面把**实现细节**当错误弹给用户 ✗✗（完全看不懂 ✓）。
2. **后端**：`mine._procs()` 每次**先 `pop` 掉自己的缓存** ✗ ⇒ 每次轮询都真起一次 PowerShell 扫进程
   ⇒ `/api/mine/state` 实测 **1.3 秒/次** ✗（前端每几秒轮询一次 ✓，超时预算 40 秒 ✓）
   ⇒ 机器一忙就顶到超时 ⇒ 被**前端自己的定时器**取消 ⇒ 弹那条红字 ✓。

★ **那行 `pop` 不是随手写的** ✗：`git log -S` 查到它是 **2026-09-16 v1.2.0**
（"每池一个独立进程 + 修「停止没反应」"）加的 ✓ —— 为**"点停止要立刻看见引擎"** ✓，**正确性优先** ✓
⇒ 本版**没有**删掉这个语义 ✗，而是**按用途分流** ✓（见下 ✓）。

### 二、改了三处（a/b/c）

| # | 位置 | 改动 |
|---|---|---|
| **a** | `dashboard/web/src/api.ts` | ★ `abort()` **带原因** ✓（`new DOMException(…, 'TimeoutError')` ✓）；新增 `ApiError`（带 `kind: 'timeout'｜'http'｜'network'` ✓）⇒ 超时/断连一律**翻译成人话** ✓，并说明"**动作通常已经生效**，刷新即可确认" ✓ |
| **b** | `dashboard/api/app/mine.py` | ★★ `_procs(fresh=False)` **按用途分流** ✓：**只读轮询**走 `core.cached` 的 2 秒缓存 ✓；**启停/等待/闸门**传 `fresh=True` **强制真查** ✓（`_procs`／`scheduler`／`engines`／`engine_of`／`pool_engines` 都加了参数 ✓，8 处调用点全在启停路径 ✓） |
| **c** | `dashboard/api/app/main.py` | ★ **慢请求日志**：凡 ≥**2 秒**的请求记一行（时间/方法/路径/状态/耗时 ✓）到 `ai_test/_tracks/_api_slow.log` ✓ —— 下次再出现**直接指名** ✓，不必再猜 ✗；异常全吞 ✓（**绝不影响请求** ✓） |

### 三、★★ 顺带查明：**看板后端跑的是 4 天前的旧代码** ✗（比那条红字更要紧）

| 事实 | 值 |
|---|---|
| 看板后端进程 | pid **26560** · 启动 **2026-09-27 00:22** ✗（连续跑 4 天）|
| `dashboard/config.json` | `"reload": false` ✗ ⇒ **永不加载新代码** |
| 前端 dev server | pid 18504 · 09-24 起 ✓（Vite **热更新** ✓ ⇒ 前端**是**新的）|

⇒ ⇒ **v1.31.0 ~ v1.35.0 的所有后端改动都没生效** ✗（含 **v1.35.0 那个"起两次才开起来"的修复** ✗、
`pausedAll` ✗、可移植性收尾里的 `mine.py` 改动 ✗）；而**前端是新的** ✗ ⇒ **前后端不一致** ✓
⇒ **必须重启后端** ✓（本版发版后已重启 ✓，见第四节 ✓）。

### 四、验证

1. ★ **新守门** `tools/_test_api_speed.py` ✓（**4 组 13 条全过** ✓，含**实测**）：
   `_procs()` **冷扫 0.678s → 缓存读 0.0000s** ✓（**600+ 倍** ✓）、`fresh=True` **确实重扫** ✓
   （0.56s ✓）、两者**结果一致** ✓；静态断言 `state()` **不许**用 `fresh=True` ✓、
   慢请求日志在位 ✓、前端**无参 `abort()` 清零** ✓。
   ⚠ 本守门第一版**两条断言自己写错** ✗ 并当场暴露 ✓：① `except Exception:` 后面跟着 `# noqa` 注释
   ⇒ 正则没留位置 ✗；② 判"无参 abort"时**匹配到了我自己注释里引用的旧写法** ✗ ⇒ 已改成**先剔注释** ✓。
2. **重启后实测**：`/api/mine/state` 从 **1.3 秒 → 秒级以下** ✓（见下 ✓）。
3. 前端 `npx tsc --noEmit` ⇒ **rc=0** ✓。
4. `tools/release_check.py` ⇒ ⚠ **据实记账**：两轮各查出**两条真失败** ✓，都是**我改了签名（`scheduler/engines/pool_engines` 加 `fresh=`）撞了守门的桩** ✗
   （`_test_mine_launch` 的 `lambda: []` ✗ / `_test_stop_scope` 的 `lambda: list(LIVE)` ✗ ⇒ 桩不收参数 ⇒
   `TypeError: got an unexpected keyword argument 'fresh'` ✗）⇒ **两处桩都已改**（`lambda *a, **k:` ✓，
   **防护内容一字不减** ✓ —— 只让桩收下新参数 ✓），并**各自单独重跑 ⇒ rc=0 全过** ✓
   （`_test_mine_launch`「看板启动参数回归全部通过」✓ / `_test_stop_scope`「全部通过」✓）。
   最终一轮全量：★ **59/59 全绿** ✓✓（**总耗时 39.8 分钟** ✓ —— 比平时慢一倍，因为**另一个项目
   正在跑重活、把机器压住了** ✗；最慢 `_test_parallel_runner` **1051s** ✗（它**真跑一代引擎** ⇒
   慢，不是卡死 ✓）、`_test_ui_quotes` 370s、`_test_panel_cache` 342s ✓）。
   ⚠ 提交当时该轮还在跑（[40/59] 零失败 ✓）⇒ 本行是**事后补记的最终结果** ✓（不愿写"预计会过" ✗）。
5. `tools/_test_undefined_names.py` ⇒ **0 处** ✓（185 文件 ✓）。

**★ 重启记录（本版发布动作之一 ✓）**：后端 pid 26560 → 重启（加载 v1.36.0 ✓）；
前端 dev server 同时重启 ✓（pid 18504 ✓）。⚠ 重启**不影响挖掘** ✓（调度器是独立进程 ✓）。

---

