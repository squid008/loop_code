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

---

## [1.30.0] — 2026-09-28

> 主题：**R1 收官 —— `engine/` 侧 >120 行函数清零**（`build_fa_pit.main` 145→102 · `_save_state` 140→102）
> ＋ **修掉让它们藏了很久的根因**：体检工具只点名 `>150`/`>300` 两档 ⇒ **121~150 一直没人看见** ✗
> ⚠ **引擎行为零改动** ✓（三方证据：`_save_state` 8 用例**逐字节**对拍 · `fa_pit.h5` 80 只股票**逐位**对拍 ·
> 同 seed A/B 8 产物 + stdout 逐字相同 ✓）⇒ 属结构整治 ⇒ SemVer **MINOR** ✓

### 一、为什么要做（`§1.36` 顺带查明的两条**既存** R1 违规）

`build_fa_pit.main()` **145** ✗ · `loop_persist._save_state()` **140** ✗ —— 都是**既存**违规 ✓（非本次引入 ✓）。
★ **真根因不是"没人拆"，而是"没人看见"** ✗：`tools/_audit_codebase.py`【3】只单列 `>300` 与 `150~300`
两档 ⇒ **121~150 这一档**从来没被点名过 ✗✗（R1 写的却是"函数 **≤120** 行" ✓）。

### 二、修根因（体检工具）

`_audit_codebase.py` 现输出 **R1 违规全清单**：凡 **>120 全部点名** ✓，并按
「**评分范围 `engine/`** / 非评分范围（`tools/` `strategies/` 等脚本）」**分组** ✓ ——
避免再把"engine 里的违规"和"脚本里的长 `main`"混为一谈 ✗。本版实测：
**`engine/` = 0 个** ✓（“R1 全达标”）、非评分范围 23 个（供参考 ✓）。

### 三、两条违规的拆法（都是**最小切口** ✓）

| 位置 | 改前 | 改后 | 抽出的 helper |
|---|---|---|---|
| `engine/build_fa_pit.py` | `main()` **145** ✗ | **102** ✓（文件 295 → 326）| `_load_pit_stock`（读 h5 + 解析 quarter/info_date）**67** ✓ |
| `engine/loop_persist.py` | `_save_state()` **140** ✗ | **102** ✓（文件 528 → 579）| `_bank_admit`（入库准入循环）**56** ✓ · `_lib_doc_sync`（分口径落文档）**27** ✓ |

★ `build_fa_pit` 只抽**一段**（49 行）就够 ✓ ⇒ 循环里"选股/填充/落盘"**一字未动** ✓；
★ `_save_state` 里 **「原子写 state」那段绝对没碰** ✓ —— `pickle.dump(dict(...))` 的**键顺序决定字节** ✗，
  动它 A/B 就过不了 ✓；`by_expr`/`n_bank_old` 刻意**留在调用方**（后面还要用 ✓）。
★ **逐字搬运 + 块内零改名**（同 ③ 的铁律 ✓）：形参**刻意取名贴合块内原名**（`bank`/`lib_added` ✓），
  其余用"开头绑回原名"（`_dup_ex_corr, _ex_by_expr, _n_dup_ex = dup_th, ex_by_expr, n_dup_in` ✓）。

### 四、★★ 三道闸门各抓到一个真错（留痕，别再犯 ✗）

| # | 错 | 抓它的闸门 |
|---|---|---|
| 1 | IC 块漏搬 `ics = []` ✗（helper 里 `ics.append` 必 NameError）| `--dump` 人工审阅 |
| 2 | 逐期块残留 `mc_ = None if mcap is None …` ✗（`mc_` 已是形参、`mcap` 不存在）| `--dump` 人工审阅 |
| 3 | `_load_pit_stock` 形参写成 `last_date` 而块里用 `dates[-1]` ✗ | `--dump` 人工审阅 |
| 4 | `_bank_admit` 漏传 `frozen` ✗（块里 `fset = set(frozen)…`）| `tools/_test_undefined_names.py` |
| 5 | `_lib_doc_sync` 形参 `n_bank`/`added` 与块里 `bank`/`lib_added` 不符 ✗ | `--dump` 人工审阅 |

⇒ 结论（已写进各脚本头注 ✓）：**"拼接式手术"必须过两道闸门 —— `--dump` 人工审阅 ＋ `_test_undefined_names`**，
只信"dry-run 报的行数"就 apply 一定会翻车 ✗。

### 五、验证（★ 因为 A/B 一代**覆盖不到**这些分支 ⇒ 必须自己造对拍）

1. ★★ **`_save_state` 逐字节对拍**（`ai_test/_ab_save_state_dual.py` ✓）：旧版(HEAD) vs 新版
   在 **8 个用例**上 ⇒ **state pkl 原始字节 + md + jsonl(`ts` 归一化) + stdout + 异常** 全同 ✓
   （用例：早退 0 通过 · 单入库+池标签+剥风格"纯风格 C" · **双口径分流**（一个副口径一个 5 日 ✓）·
   **收益流去重命中** · **FSA 冻结命中** · **骨架上限命中** · 库内已有同表达式 · 入 2 个+收益流进对照集 ✓）
   —— ⚠ 为什么非造不可：`ab_generation` 的最小规模一代**常"入库 0"** ✗ ⇒ `_save_state` 第一句就早退 ✗✗
   （`if len(res) and res['passed'].any():`），**准入循环与分口径落文档根本不执行** ✗；
2. ★★ **`fa_pit.h5` 逐位对拍**（`ai_test/_ab_fa_pit_dual.py` ✓）：**80 只股票**各跑一遍旧版/新版 ⇒
   产物**逐 key / 逐数组 / float32 原始字节级相同** ✓（2,001,791 字节 ✓）＋ stdout 逐行相同（耗时归一化 ✓）；
3. **同 seed A/B**：`_ab/after3` ←→ 改后 ⇒ **8 产物逐字节 + stdout 逐行相同** ✓；
4. 相关静态守门：`_test_fsa_freeze` **22/22** · `_test_inject_pools` **17/17** · `_test_node_single` ✓ ·
   `_test_library_log` **44/44** · `_test_critic_sensor` ✓ · `_test_action_efficacy` **42/42** ·
   `_test_unbound_return` ✓ · `_test_undefined_names` **0 处** ✓；
5. `tools/release_check.py` ⇒ **55/55 全绿** ✓。

### 六、★ 顺带：给 A/B 工具加**超时预算开关**（否则"别的项目占着机器"时验不完 ✗）

本版跑 A/B 时撞上真实场景：本机同时跑着**别的项目**的重活
（`E:\quant\data_wash\tools\build_multiwindow_panel.py` ✗ —— **不是本项目、没动它** ✓），
一代从 ~190s 变成 >900s ✗ ⇒ `ab_generation.py` 报 **`退出码=-9`**（**是超时、不是行为差异** ✗✗，
极易误判成"改动坏了" ✗）。★ 顺带确认了工具的**自我保护有效** ✓：超时后 `finally` 仍把池轨迹
**逐字节还原** ✓（输出里就有那行 ✓）—— 这正是 `v1.25.0` 建这套隔离的目的 ✓。
⇒ 加**可选**预算（**默认值一字未变** ✓，既有调用方行为不变 ✓）：
`tools/_pool_traj.run_generation(timeout=None)` ⇒ 取 `LOOP_AB_TIMEOUT` 环境变量、再退回 **900** ✓；
`tools/ab_generation.py` 加 `--timeout`（0 = 用默认 ✓）✓。

### 七、顺带清死码（R4）

`loop_critic.pd` ✓ · `gen_f11_daily.pd` ✓ · `augment_panel.glob` ✓ —— 实测三者在本文件出现 **0 次** ✓
（删前确认 ✓，删后编译 + 名字检查 + 守门全过 ✓）。
⚠ **两处工具误报，故意不删** ✗：① `factor_miner.COST_PRESETS` —— 它是**有意转出**的兼容出口 ✓
（注释写着"转出, 勿在此再定义" ✓）；② `engine/_dump_state.py` / `_dump_skel.py` 的 `Node`（或 `E`）——
**pickle 反序列化需要该类在加载方命名空间可见** ✓（脚本里写明了 ✓）。⇒ 已在台账注明，免后人再误删 ✗。

---

## [1.29.0] — 2026-09-28

> 主题：**最后一个大函数拆分 —— `factor_miner.evaluate_real()` 275 → 47 行**（`loop_todo §1.36/§1.37 ③`）
> ⚠ **引擎行为零改动** ✓ —— 因这是**数值路径**，本次用**逐位**证据：**46 次调用**
> （23 用例 × `FWD=5/20`）在 **float64 原始字节级完全相同** ✓ ＋ 同进程重跑 ✓ ＋ **跨进程 `--digest`** ✓
> ＋ 同 seed A/B **8 产物 + stdout 逐字相同** ✓ ⇒ 属结构整治 ⇒ SemVer **MINOR** ✓

### 一、拆法：**原地拆**（不搬模块）＋ **逐字搬运、块内零改名**（★ 与 ①② 不同）

①② 是"搬到新模块 + 闭包变方法"；③ **原地拆**（`factor_miner.py` 只 609 行 ✓ 无 R2 压力 ✓）。
而它是**数值路径**（`calmar`/`sharpe`/`ann_ex`/`dd` 直接进 L2 入库门槛 ✗）⇒ 差 1e-16 就可能翻转
"入库/不入库" ✗✗ ⇒ 唯一安全做法是：

> **每一块逐字搬运、块内一个名字都不改** ✗ —— 只在新函数开头补几行把"原来的局部名"重新绑好
> （`ann_e = res['ann_ex']` / `yrs = len(tr) * FWD / 243` ✓）⇒ **算术顺序、结合、字面量全未动** ✓
> 手术脚本由**内容锚点**定位块（不硬编码行号 ✓），块文本直接从原文件取 ✓。

### 二、落点（`ast` 实测）

| 位置 | 改前 | 改后 |
|---|---|---|
| `evaluate_real` | **275** ✗（R1 线 120）| **47** ✓（只剩编排 ✓）|
| `engine/factor_miner.py` | 609 | **683** ✓ |
| `_er_periods`（逐期主循环 + 3 行几何映射 + `cv`）| 内联 99 行 | **112** ✓ |
| `_er_ic` | 内联 | **27** ✓ |
| `_er_base_res`（期频 + 组合自身指标 + `res` 字面量）| 内联 | **46** ✓ |
| `_er_cw_marks`（市值加权口径）| 内联 | **38** ✓ |
| `_er_daily_marks`（日频 mark-to-market 两段）| 内联 | **50** ✓ |
| 8 条平行累积列表 | — | `_ErAcc`（`NamedTuple`）✓ |

★ `_ErAcc` **故意不用** `loop_l2._L2Acc` 那种"可取属性的可变对象" ✗ ——
可变对象意味着要在 **99 行循环里逐处改名**（`acc.top_r.append(…)` ✗）⇒ **逐位风险上升** ✗
⇒ 宁可用"有名记录 + 8 项返回" ✓（两种选择各自的理由都写进了代码注释 ✓）。

### 三、诚实记账（三条"不是没动" ✗）

1. **两段论述注释搬了家**：原 docstring 的 7（mcap，12 行）/8（with_daily，10 行）两段 essay
   **搬进 `_er_cw_marks` / `_er_daily_marks` 的 docstring** ✓（主 docstring 只留 1~6 号契约 + 指路行 ✓）
   —— 属**文档搬家**（对运行行为零影响 ✓）；
2. **日频两段的守卫合并**：`if with_daily and ex_d_parts:` / `if with_daily and tr_d_parts:`
   ⇒ 调用方一处 `if with_daily and (acc.ex_d or acc.tr_d):` ✓（等价 ✓）；
3. **顺带删一行真死 import**：`factor_miner.py` 的 `import time` ✓ —— 实测 **HEAD 里 `time.` 出现 0 次** ✓
   ⇒ **既存**死码（非本次引入 ✓）。⚠ 另查到 `loop_critic.py` 的 `import pandas as pd` 同为既存死码 ✗
   （`pd.` 在 HEAD 与工作区均出现 **0 次** ✓），**本版未动** ✓（属 ① 的文件，另记台账 ✓）。

### 四、★★ 手术脚本自己犯的两个真错（留痕，别再犯 ✗）

`ai_test/_cut_eval_real.py` 初版：① IC 块锚点从 `fv_all = …` 起 ⇒ **漏搬 `ics = []`** ✗（helper 里
`ics.append` 必 `NameError` ✗）；② 逐期块里残留一行 `mc_ = None if mcap is None else …` ✗ ——
而 `mc_` 已是**形参**、`mcap` 在 helper 里根本不存在 ⇒ 同样 `NameError` ✗✗。
**抓住它们的两道闸门**：先 `--dump` 出全文**人工审阅** ✓ ＋ 事后 `tools/_test_undefined_names.py`
（作用域感知 ✓，实测 **0 处** ✓）。⇒ 结论写进脚本头注：这类"拼接式手术"**必须**这两道 ✓。

### 五、验证（★ 逐位 + 确定性 = 用户点名的两条）

1. `_test_undefined_names` ⇒ **0 处** ✓（179 文件）· `_test_unbound_return`（含 `factor_miner`）✓；
2. ★★ **逐位差分对拍**（`ai_test/_ab_eval_dual.py`）：**旧版（`HEAD:factor_miner.evaluate_real`）
   vs 新版**在 **23 用例 × FWD=5/20 = 46 次调用**上 **float64 原始字节级完全相同** ✓✓
   （直接比 `ndarray.tobytes()` ⇒ 连 `-0.0`、NaN 负载都比 ✓；**键集合/类型/索引/列、以及键的顺序**也一并比 ✓）。
   用例：真实面板派生因子 ×4（`cs_rank(close)`/`-close`/`ts_mean(turnover,20)`/`-mktcap`）· 确定性噪声 ·
   全常数 · **全 NaN（两边都 `None` ⇒ 期数不足早退 ✓）** · **半 NaN** · `window` full/recent600 ·
   `with_ex`/`with_daily`/两者 · `mcap`（无/**真实市值**/**常数市值**（恒等式：市值加权==等权 ✓））·
   `cost=0.002+cash=0.95` ✓；
3. **同 seed 确定性**：同进程连跑两次逐位相同（前 3 例 ✓）＋ **跨进程两遍 `--digest` 输出一致** ✓
   ＋ 端到端 A/B 本身即**跨进程**产物对照 ✓；
4. **同 seed A/B**：`_ab/after2`（改前）←→ `_ab/after3`（改后）⇒ **8 产物逐字节 + stdout 103 行 0 差异** ✓
   （⚠ 基线用 `after2`：③ 与 ② 之间只差注释搬家 ⇒ 行为同一 ✓）；
5. 相关守门：`_test_excess_caliber`（**静态**查四条式子 ✓ 仍在同文件 ⇒ 仍命中 ✓）· `_test_fwd_wiring` ✓ ·
   `_test_daily_dd`（日频口径 23/23 ✓）· `_test_dual_horizon` ✓；
6. `tools/release_check.py` ⇒ **55/55 全绿** ✓（13.x 分钟）。

**⇒ 收官口径**：`engine` 侧 R1 违规**只剩两条既存**（`build_fa_pit.main` **145** ✗ ·
`loop_persist._save_state` **140** ✗，均非本次引入 ✓，已记 `maintainability.md §五` ✓）；
§1.36 点名的三个大函数（`suggest` 207 · `_lib_sync` 186 · `evaluate_real` 275）**全部达标** ✓。

---

## [1.28.0] — 2026-09-28

> 主题：**库文档簇拆成 `engine/loop_libdoc.py`** —— `loop_persist.py` **796 → 528 行**、
> `_lib_sync()` **186 → 61 行**（`docs/loop_todo.md §1.36/§1.37 ②`）
> ⚠ **引擎行为零改动** ✓ —— 同 seed A/B **8 产物 + stdout 逐字相同** ✓ ＋ **18 用例旧版 vs 新版逐字节差分** ✓
> ⇒ 属"向后兼容的结构整治"（同 v1.25.x / v1.27.0 口径）⇒ SemVer **MINOR** ✓

### 一、为什么要"搬"而不是"就地拆"

`loop_persist._lib_sync()` **186 行** ✗（R1 线 120）；而它所在的 `loop_persist.py` 当时 **796 行**，
离 R2 线（800）**只剩 4 行** ✗✗ ⇒ 就地拆（新增 `def`/docstring/`return` 都要占行）**必然把文件顶过线** ✗
⇒ 把「**库文档**」这一件事整簇搬成**单一职责模块** ✓
（同 `v1.25.x` 拆 `loop_l1`/`loop_l2`、`v1.27.0` 拆 `loop_critic_rules` ✓）。

### 二、落点（`ast` 实测）

| 位置 | 改前 | 改后 |
|---|---|---|
| `engine/loop_persist.py` | **796**（贴线 ✗）| **528** ✓ |
| 新模块 `engine/loop_libdoc.py` | — | **347** 行 ✓ |
| `_lib_sync` | **186** ✗ | **61** ✓ |
| 拆出的两段 | — | `_lib_rows`（渲染总览行/明细块/入库事件 · **113** ✓）· `_lib_insert_md`（md 三处锚点 · **31** ✓）|
| 逐字搬的 3 个 | — | `_tag_desc` **4** · `_mk_library_skeleton` **38** · `append_library_entries` **33** ✓ |

★ **`_lib_rows` 一度 121 行** ✗（超 R1 线 1 行）⇒ 用本项目**已有手法**「上移论述注释」压回 **113** ✓
（`v1.25.x` 的 "comment hoist only" ✓）。⚠ **诚实记账**：**没做到**"token 级逐字相同" ✗ ——
上移时顺手把那段注释写得更清楚（并加了 §1.37 的来历）⇒ 属**注释增量**（对行为零影响 ✓）。

### 三、依赖方向（★ 单向，无环）

`loop_libdoc` 只依赖**叶子模块**（`loop_paths` · `loop_expr.skeleton` · `cost_presets` ·
`loop_pools`（惰性 import ✓））⇒ **不 import `loop_persist` / `loop_engine`** ✓；
`loop_persist` 反向 **只** `from loop_libdoc import _lib_sync`（`_save_state` 的代末双口径同步仍要它 ✓）；
`loop_engine` 顶部 **re-export 那 4 个名字** ✓ —— ⚠ `tools/horizon_admit_write.py` /
`tools/backfill_library_pool.py` 走的是 `LE._lib_sync` / `LE._mk_library_skeleton`，
**删掉那行会让两个工具静默失联** ✗ ⇒ 已在原处写明"不许删" ✗。

### 四、验证（★ 其中第 3 条是"必须直拍"的）

1. `tools/_test_undefined_names.py` ⇒ **0 处** ✓（179 个文件 ✓）；
2. **同 seed A/B**：`_ab/base2`（187 s）←→ `_ab/after2`（192 s）⇒ **8 产物逐字节 + stdout 103 行 0 差异** ✓
   —— ⚠ 但它**证明不了 `_lib_sync` 本身** ✗✗：该函数第一句就是 `if not added_exprs: return`，
   而 `ab_generation` 跑的是**最小规模**（"常常入库 0" ✓）⇒ **主体根本没执行** ✗；
3. ★★ **直拍（本版的关键证据）**：`ai_test/_ab_libdoc_dual.py` ——
   **旧版（`HEAD:loop_persist._lib_sync`）vs 新版（`loop_libdoc` 三段）逐字节差分** ✓：
   沙箱把 `loop_paths.LIBRARY/LIB_ENTRIES/MINE_POOL` 指到临时目录（两边各自的副本 ✓），
   **18 个用例**覆盖 早退（无入库/明细为空）· **骨架自动创建** · 表尾插入 · **刚建骨架无数据行（`elif` 分支）** ·
   **缺「相关文件导航」（`p<0` 分支）** · 池标签有/无 · 剥风格 **4 元组 / 6 元组 / 日频 NaN** ·
   `sign` 有/无/坏值 · 口径有/无（含无期数）· 来源 `engine`/`promote` · **编号 F99→F100 边界** ·
   `jsonl` 幂等 · `jsonl` 坏行 ⇒ **18/18 逐字节相同**（md + jsonl（`ts` 归一化）+ **stdout** + 异常）✓；
4. 相关守门：`_test_library_log` **44/44** ✓ · `_test_admit_write` ✓ · `_test_reports_expr` **34/34** ✓ ·
   `_test_dual_horizon` ✓ · `_test_unbound_return`（**新模块已纳入扫描** ✓）✓ · `_audit_deadcode`（无新死码 ✓）✓；
5. `tools/release_check.py`（全量 **55/55**）⇒ 全绿 ✓。

### 五、守门/工具取源同步（防护一字未减 ✓）＋ 顺手修掉一个真缺陷 ✓

* 三处"按文件路径做静态断言"的取源改到 `loop_libdoc.py` ✓：
  `_test_library_log`（`append_library_entries` 有定义且被调用）· `_test_admit_write`（`def _lib_sync(...source=None)`）·
  `_test_reports_expr`（`sign` 行）✓；
* `tools/_test_unbound_return.py` 的默认文件清单加 `engine/loop_libdoc.py` ✓（R7：搬来的代码必须被扫 ✓）；
* ★ **`tools/_mk_pool_library_skeleton.py` 的 `ENGINE_SRC` 原先写 `loop_engine.py`** ✗ ——
  而 `_mk_library_skeleton` **从来不在** loop_engine 里定义（那边只有 import）⇒ **ast 提取每次都失败、
  静默回退内置 `FALLBACK` 副本** ✗（= 引擎改模板、工具照抄旧副本；**实测两份确实有一处不同** ✗）。
  本次把路径指到真正的家 ✓，并用 `ai_test/_check_skeleton_tpl.py` 证明：
  **旧路径提取失败** ✓ / **新路径与引擎模板逐字相同** ✓（该工具**不覆盖已有文件**（`if os.path.exists: exit 0` ✓）
  ⇒ 只影响"将来新建的池骨架"，风险可控 ✓）。
* `loop_persist.py` 里随簇搬走而**变成死 import** 的 `json` / `re` / `cost_label` 已删 ✓（R4 无死码 ✓）。

**遗留（如实记账 ✗）**：① `factor_miner.evaluate_real()` **275 行** ⇒ 下一版（③，碰数值路径 ⇒
需同 seed 确定性 + **逐位对拍** ✓）；② 顺带查明两条**既存** R1 违规（**不是本版引入** ✗）：
`build_fa_pit.main()` **145** · `loop_persist._save_state()` **140** ⇒ 已记入 `maintainability.md §五` 台账 ✓
（根因：`_audit_codebase`【3】只点名 `>150`/`>300` 两档 ⇒ **121~150 这一档一直没被看见** ✗）。

---

## [1.27.0] — 2026-09-28

> 主题：**既存 R2 违规清零 —— `loop_critic.py` 998 → 774 行、`suggest()` 207 → 30 行**
> （`docs/loop_todo.md §1.37` ①：**先对象化、再把 7 个闭包转方法**，走 B 路「整改」✓）
> ⚠ **引擎行为零改动** ✓ —— A/B 证据：**8 个产物逐字节 + stdout 103 行逐行相同（差异 0）** ✓
> ⇒ 属"向后兼容的结构整治"（同 v1.25.x 口径）⇒ SemVer **MINOR** ✓

### 一、为什么要做（§1.36 查出的**既存**违规，口径要一致）

`loop_critic.py` 改前就 **991 行**、v1.26.0 后又 **998 行** ✗（R2 线 = 800）——
它上一轮审计里已是 **engine 最大文件**，却**从未进过 §五 的扣分项** ✗
（而新文件都按 ≤800 算 ✓）⇒ **口径不一致** ✗。两条路里选了 **B（整改）**：A（承认遗产）给不出理由 ✓。

### 二、★ 关键判断：**不做机械抽块**（这条是 AST 机器算出来的，不是人眼猜 ✓）

`tools/_extract_block.py loop_critic.py suggest 581 752 <名>` 的结论：那 7 个嵌套 `def`
「**块里读了、块外才有**」的名字 **13 个** ——
`_ctx · act · base · cmul · cool · diag · ineff · n_blocked · n_ineff · reasons · s · tgt · veto`；
而「块里赋值、块外还读」的**只有 `n_blocked`**。

⇒ 机械抽成函数 ⇒ 每个子函数要背 **13 个形参** ✗✗ —— 正是 `maintainability.md §七` 警告的
   「**上帝函数换成上帝参数表**」✗（`_run_l2_phase` 试抽 `_l2_judge` 已因此回退过一次 ✓）
⇒ 改用**方法**（`self.xxx`）⇒ **形参 0 个** ✓；`n_blocked` / `n_ineff` 留在对象上**就地自增**
   ⇒ **连回传都不需要** ✓✓（原 `n_blocked = [0]` 的单元素列表只是"闭包改不动外层变量"的变通 ✗ ⇒ 顺手拆掉 ✓）。

### 三、落点（`ast` 实测行数）

| 位置 | 改前 | 改后 |
|---|---|---|
| `engine/loop_critic.py` | **998** ✗ | **774** ✓（R2 线 800 ✓）|
| `loop_critic.suggest()` | **207** ✗（R1 线 120）| **30** ✓ |
| 新文件 `engine/loop_critic_rules.py` | — | **312** ✓ |
| 7 个方法（7 个闭包 ⇒ 方法） | — | `_set` **8** · `_ineff_muted` **4** · `_begin` **3** · `_mark` **20** · `_rollback` **34** · `_guard` **43** · `_settle` **54** ✓（**与 §1.37 预估逐数吻合** ✓）|
| `_SugState.__init__`（原 `_init_sug` **并入** ✓）| 30 行模块级函数 | **43** ✓ |
| `_fmt` / `_fmt_l1` / `_fmt_l2` | 闭包 + 2 个模块级 | 一并搬入（**4 / 14 / 18** ✓）|
| **留在原文件** | — | `_apply_rules`（7 条规则表 · **67** ✓）+ `_finalize_sug`（出口 mix 护栏 · **28** ✓）|

★ **两处按实情修正了原方案**（不假装照抄 ✓）：
1. **`_init_sug` 也并进了对象** —— 状态布局的**唯一知情人**就是对象本身 ✓，否则构造时还得再抄 6 行
   "从 `s` 取别名"（重复 ✗）；代价是新模块 312 行（原估 ≈220），仍远在 800 线内 ✓。
2. **`n_blocked`/`n_ineff` 由 `[0]` 单元素列表改为对象整数** ✓（理由见 §二）。

### 四、依赖方向（★ 单向，不成环）

`loop_critic_rules` 顶部 `from loop_critic import …`（**复用**其常量与纯函数 ⇒ **R5 未复制第二份** ✓）；
`loop_critic` **只在函数内** import 它（`suggest` / `report` / `ai_review` 三处）⇒ 到那一刻
`loop_critic` 已完全初始化 ⇒ **不成环** ✓（与 `_op_names` 惰性 import `loop_engine` 同一条理由 ✓）。
模块头注写明「**不许**把它提到 `loop_critic` 的模块级」✗。

### 五、验证（R7 铁律：名字解析 + 同 seed A/B，缺一不可 ✓）

1. `tools/_test_undefined_names.py` ⇒ **0 处** ✓；
2. **A/B 逐字节**：改前 `_ab/base`（219 s ✓）←→ 改后 `_ab/after37`（186 s ✓），
   同 `--pool=50 --gen=9999 --seed=777` + 生产同款 flag ⇒
   **8 个产物逐字节相同**（journal 归一化后逐行相同 ✓）+ **stdout 103 vs 103 行、差异 0** ✓；
3. 相关守门：`_test_critic_sensor`（饱和/否决/永久闭嘴）✓ · `_test_action_efficacy` **42/42** ✓ ·
   `_test_unbound_return`（**新模块已纳入扫描** ✓）✓ · `_test_ops_sync` 28/28 ✓ ·
   `_test_ops_registry` 17/17 ✓ · `_test_critic_firstgen` ✓；
4. `tools/release_check.py`（版本一致 → 未定义名 → 全量 55 条守门）⇒ **全绿** ✓。

**守门同步（防护内容一字未减 ✓）**：`_test_action_efficacy` 的两处静态取源改为
「`loop_critic.py` + `loop_critic_rules.py` **拼接**」✓（动作区正则仍命中原文件里的 `_apply_rules` ✓、
`_set` 计数 10 ✓、"无直接 `s[...]` 赋值" ✓）；`_test_unbound_return` 的默认文件清单加新模块 ✓。

**遗留（如实记账 ✗）**：`engine` 侧仍有 `factor_miner.evaluate_real()` **275 行**、
`loop_persist._lib_sync()` **186 行** ⇒ 即 `loop_todo §1.36` 顺带记的那两笔（**②③ 待办** ✓）。

---

## [1.26.0] — 2026-09-28

> 主题：**给挖掘留"时间线"** —— journal 与 stdout 加**秒级时间**、耗时改**人类可读**、
> `_engine_exits.log` 补上**成功代**记录（用户之问："这些 journal 记录后面要不要把北京时间加进去？"✓）
> ⚠ 引擎**数值行为零改动** ✓（A/B 逐字节 ✓）；改动属**向后兼容的新日志字段** ⇒ SemVer **MINOR** ✓

### 一、为什么要做（用户实测驱动的三个痛点）

1. **journal 里没有时间** ✗ ⇒ 要定位"某一代何时跑的"**只能靠文件 mtime 反推** ✓（用户问"50 池怎么还没挖完"、
   我排查"300 才挖两代吗"时，都是这么硬推的 ✓）；
2. **`_engine_exits.log` 只记非零退出** ✗✗ ⇒ 翻它**只会看到"被停/异常"**，成功完成的代**一行都不写** ✗
   —— 我 2026-09-28 就据此**误判过**"300 才挖两代"（实际已到第 194 代 ✓）；
3. **`耗时 7142s` 不好读** ✗ ⇒ 用户要求改成 `1h59m2s` ✓。

### 二、做了什么（四步 · 每一步都有独立验证 ✓）

| 步 | 内容 | 落点 |
|---|---|---|
| **1** | A/B 比对器**先容忍**新格式 ✓：① `noise` 正则覆盖 `1h59m2s` 复合耗时（放最前，否则短的咬碎长的 ✗）；② **把归一化提到产物比对之前**，并让 **journal 等文本产物也逐行归一化** ✓（原先只有 stdout 做 ⇒ journal 一加时间戳就**每次误报** ✗✗） | `tools/ab_generation.py` |
| **2 (C)** | stdout 新增一行：`时间: … +08:00 · 开工 … · 完工 … · 耗时 1h59m2s` ✓；`保存状态:` 的耗时改用人类可读 ✓ | `engine/loop_persist.py` |
| **3 (A)** | journal 代标题下新增**同格式时间行** ✓ | `engine/loop_critic.py` |
| **4 (B)** | `_engine_exits.log` **三类都留痕**：成功 / 被停 / 异常 ✓（`_log_exit` 加 `tag` ✓）；成功行 = `… 成功  入库 N 个  耗时 1h59m2s` ✓ | `tools/parallel_runner.py` |

**语义定死**（避免歧义 ✓）：`开工` = 进程启动（**开始挖** ✓）；`完工` = 收尾写完（**诊断 + LLM/AI 审查 + 落盘全部完成** ✓）
⇒ 三者**同源**（同一个 `t0` ✓）⇒ 恒有 `完工 − 开工 == 耗时` ✓。
⚠ **journal 只写"诊断落档时刻"** ✗ —— 那一刻 `完工` **还不可知**（AI 审查在其后 ✓）⇒ **不编造** ✓（宁缺勿假 ✓）；
`开工/完工/耗时` 由 stdout 的 `时间:` 行与 `_engine_exits.log` 的成功行给出 ✓。
⚠ **时区用 `%z` 实测** ✓，**不硬编码 `+08:00`** ✗（本机在北京时即 `+0800` ✓；换机器**不会撒谎** ✓）。

### 三、R5/R2 的账（做完才敢说 ✓）

- **R5 单一实现** ✓：把 `fmt_dur()` / `stamp()` 抽进**新增 `engine/loop_log.py`**（**45 行** ✓）——
  先前"工具端自己再写一份格式化"的做法**被否掉** ✗（那是第二份实现 ✗）；
  `tools/parallel_runner.py` 改为**照抄引擎打印的字符串** ✓（不重建 ✓）。
- **R2 文件长度** ✓：改完一度把 `loop_persist.py` 顶到 **816 行** ✗（线 = 800）⇒ 抽出后 **796 行** ✓ 回线内 ✓。
  ⚠ **如实记账**：`engine/loop_critic.py` 现 **998 行** ✗ —— 它**本来就是 991 行**（上一轮审计里 engine 最大文件 ✓），
  本次净增 **+7** ✗ ⇒ 这是**既存**的 R2 违规 ✓，本次**未拆** ✗（不硬塞进本改动 ✓），列入台账待办 ✓。

### 验证

- **A/B ①（基线 = 改动前 ✓）**：7/8 产物**逐字节相同** ✓；`journal` 与 `stdout` 的差异**只有"多一行"** ✓
  （纯插入：A 的第 3001 行 == B 的第 3003 行 ✓）⇒ **数值行为零改动** ✓；并**反证基线确实跑的是旧代码** ✓（A 侧无 `时间:` 行 ✓）
- **A/B ②（抽取 `loop_log.py` 前后 ✓）**：**8/8 全绿** ✓ —— 7 个逐字节相同 ✓ ＋ journal `✓ 归一化后逐行相同` ✓
  ＋ stdout `✓ 逐行相同（101 vs 101，差异 0 行）` ✓ ⇒ **抽取是纯重构** ✓，且第 1 步的归一化**运行时成立** ✓
- **守门**：`_test_undefined_names` —— 期间**抓到过我漏 `import time`**（1 处 ✗）⇒ 修后 **0 处** ✓（扫 177 文件 ✓）
- **全量 `release_check.py`**：改动落地时 **55/55** ✓（13.3 分钟 ✓，含 `_test_e2e_l1l2` **192 s** ✓＝真跑一代 L1+L2 ✓
  ⇒ 证明新增的 stdout/journal 行**没撞坏端到端** ✓；`_test_parallel_runner` **185 s** ✓ 覆盖 B 所在文件 ✓）
- ⚠ **尚未拿到**：B 的**运行时首行**要等**下一代跑完**才会出现在 `_engine_exits.log` ✓（本条**如实标注** ✗，不当作已验证 ✓）

---

## [1.25.3] — 2026-09-27

> 主题：**R1/R2 整治收官** —— 「先对象化、再抽块」，六个超标函数全部达标，`loop_stage.py` 一拆为三
> ⚠ **引擎行为零改动**（每个提交都有 A/B 逐字节证据 ✓）；用户拍板走「**先对象化再拆**」而非「机械抽块」✓

### 一、为什么不是"直接抽块"

机械抽 `_run_l2_phase` 的候选循环会得到「**67 行调用方 + 一个 30 形参的子函数**」✗ ——
正是 `docs/maintainability.md` 自己警告的**「上帝函数换成上帝参数表」** ⚠。那 30 个形参的来源是
函数开头 **24 行 `x = ctx['y']`** ✓。⇒ 用户选 **B：先把口径对象化，再抽块** ✓。

### 二、做了两件事

**① 对象化（`_L2In` / `_L2Acc`，提交 `28e4429`）**

| 对象 | 语义 | 内容 |
|---|---|---|
| `_L2In`（`frozen=True` ✓） | L2 阶段**只读**口径 | 23 项；`frozen` ⇒ 手误写它**立刻抛错** ✓（这是它存在的理由之一 ✓）|
| `_L2Acc`（可变 ✓） | 本代**累积结果** | `rows / seg_ok_list / strip_rows / pool_rows / n_pool_nogate / nd` ✓ |

- **名字对应只有一个来源** ✓：模块级 `_L2IN_MAP`（键 = 旧局部名 = 当时的 ctx 键 ✓，逐字来自源码 ✓）
  ⇒ `_L2In.of(ctx)` **不猜**同名键 ✗，缺键立刻 `KeyError` ✓
- ⚠ `nd` 会被 `_dump_pool_obs` **重绑** ⇒ 必须放**可变**侧 ✗（塞进 `frozen` 会直接抛错 ✓）
- 24 行解包 → `cal = _L2In.of(ctx)` ＋ `acc = _L2Acc(nd=ctx['nd'])`（2 行 ✓）；5 行累加器初始化收进字段默认值 ✓
- **78 处裸名改名**（29 个名字 ✓）⇒ 块内写入全变成**属性写入**（`acc.rows.append(...)` ✓）

**② 抽块（提交 `1348814` / `a182ebe` / `32e84a8`）**

| 函数 | 原 | 现 | 抽出的子函数 |
|---|---|---|---|
| `_run_l1_phase` | 197 | **62** ✓ | `_l1_calib` ✓ |
| `_l1_eval` | 174 | **55** ✓ | `_l1_batches`（111 行 ✓）|
| `_run_l2_phase` | 251 | **41** ✓ | `_l2_candidates`（119 行 ✓）|

★ 抽块的**形参与回传都由 AST 机器算** ✓（不人眼挑 ✗）：形参 = 块里读到、块外才有 ✓；
回传 = 块里赋值、块外还读 ✓；**条件赋值**（只在嵌套分支里绑 ⇒ 可能一次都没执行 ✗）⇒ 子函数内先置 `None` ✓。
对象化之后这项工作**天然归零**：写入全是属性写入 ⇒ `_l2_candidates` 回传只剩 `acc`、再无"条件赋值" ✗✓。

### 三、验证协议（本轮真正的资产 ✓）

每次抽块都跑同一条链，**三次全部 8/8 逐字节** ✓：

```
① .bak 跑基线（改动前 ✓）→ ② 换新版跑一次 → ③ ab_generation.py --diff：8 个产物逐字节 + stdout 逐行
④ 极小跑（--n=8 --l2=1，~110 s ✓）当快闸门  ⑤ release_check.py 全量（55 条 ✓）
```

**这条链抓到达 6 个「编译/静态检查全过、真跑一代才炸」的缺陷** ✗，全部在**写盘前或提交前**拦下 ✓：

| # | 缺陷 | 谁抓住的 |
|---|---|---|
| 1 | 条件赋值名 `k` 被无条件 `return`（可能从未绑定 ✗） | 极小跑 `NameError` ✓ |
| 2 | `n_eval += 1`（先读后写 ✗）既没当形参又要回传 | 工具的 dry-run ✓ |
| 3 | 删 24 行后下方位移方向写反 ✗ | 脚本的 `assert`（**写盘前**退出 ✓）|
| 4 | 类算好了却**忘了插** ✗ | 极小跑 `NameError` ✓ |
| 5 | ★ **`col_offset` 是 UTF-8 字节偏移、不是字符偏移** ✗ —— 行里含中文时按字符切片切歪 ✓ | 逐处断言「切出来必须正是原名字」✓ |
| 6 | 守门 `_test_dual_horizon` 的坐标过期（引用点搬走了 ✗） | 全量闸门 54/55 ✓ |

⚠ **坑 5 值得写进规则**（本仓库满屏中文注释 ✓）：任何"按 AST 列号切字符串"的脚本**必须**先做
字节→字符转换 ✓，且**每处切完都要断言取到的正是原名字** ✓。

### 四、守门坐标随重构更新（`c7fc1da`）

`_test_dual_horizon` 的 ③④ 断言要求「`pass_filter` 在持有 L2 循环的函数里以**全局名**取」✓。
循环搬进 `_l2_candidates` 后坐标过期 ✗ ⇒ 断言改看**新家**（`sys.modules['loop_l2']` ✓ ——
`loop_engine` 只**转发** `_run_l2_phase` ✓、没导出新函数 ✗）。
⚠ **保护一点没减** ✗：仍是「不许函数内绑定」✓ ＋「必须以全局名取（`co_names`）」✓，且 ③ 从"一个函数"扩成"**两个都查**" ✓。

### 五、八维评分（`docs/maintainability.md`）

| 维度 | 09-27 前 | **09-27** | 依据 |
|---|---|---|---|
| 可读性 | 8 | **9** | ★ §五 明列的扣分项**只有两条** ⇒ 两条全清 ✓：**R1 六函数 41/62/55/115/120/119 全 ≤120** ✓ |
| 可维护性 | 8 | **9** | ★ **R2 达标**：`loop_stage.py` **1332 → 437 行** ✓（同族 `loop_l1.py` 588 ✓ / `loop_l2.py` 510 ✓，均 ≤800 ✓）|
| **综合** | **8.0** | **8.25** | 66 / 8 = 8.25 |

> ⚠ **未动**（不是忘了 ✗）：**性能 6**（一次优化都没做 ✗，重构期硬约束是"行为不变"⇒不许顺手改数值路径 ✗）；
> **可移植性 7**（看板仍 Windows 专有 ✗）；功能性 8（行为逐字不变 ✓ 是本次硬约束 ✓）；
> 测试/工程纪律/文档 9 ✓（v1.24.0 已挣到 ✓）。

### 验证

- **A/B 逐字节 3 次全过** ✓：`_l1_calib`（`base2↔s3d`）· 对象化（`b0↔b3`）· 抽块（`b6↔b5`、`b5↔b7`）
  —— 每个都是 **8 个产物逐字节相同 + stdout 逐行相同** ✓
- **极小跑**：`rc=0` · 无 `Traceback`/`NameError` · 产物真落盘 · **还原后与跑前逐字节一致** ✓
- **`release_check.py`**：**54/55** ⇒ 唯一失败是 §四 的坐标过期 ✓ ⇒ 修复后**单独复验全过** ✓
  （与重构直接相关的守门全绿 ✓：`_test_e2e_l1l2` 179 s ✓ · `_test_parallel_runner` 153 s ✓ ·
  `_test_unbound_return` ✓ · `_test_undefined_names` ✓ · `_test_style_neut` ✓）
- ⚠ **冷缓存辨析** ✓：同一条最小链路实测 **500 s vs 110 s** ✗ ⇒ 逐字节相同、且热缓存重跑 110 s ✓
  ⇒ **是面板缓存冷热，不是代码变慢** ✓（以后比耗时必须连跑两次 ✓）

---

## [1.25.2] — 2026-09-27

> 主题：**函数级拆分 S2 —— L1 组搬出 `loop_stage.py`** ⇒ ★ **R2 达标**（`loop_stage.py` 1349 → **399 行** ✓）
> ⚠ 引擎行为逐字未变（A/B 实证 ✓）；★ **本版 A/B 抓到一个真缺陷** ✓（见下）

* **搬迁**：`_run_l1_phase` / `_l1_eval` / `_l1_filter`（**510 行**）→ 新文件 **`engine/loop_l1.py`**（538 行 ✓）
  ⇒ `loop_stage.py` **909 → 399 行** ✓ · `loop_l2.py` 467 ✓ · `loop_l1.py` 538 ✓ ⇒ **三个文件全 ≤800** ✓
  （`_audit_codebase.py`：巨型文件 0 ✓）
* ★★ **A/B 抓到一个真缺陷（它上一次的自我价值证明 ✓）**：
  `FWD → _S.FWD` 的替换**越界到了 f-string 的字面文本** ✗ ——
  `print(f"...子面板[::FWD] ...")` 里的 `[::FWD]` 是**要打印出来的字**（不是变量 ✓），被改成了 `[::_S.FWD]` ✗
  ⇒ 8 个产物**逐字节相同** ✓ 但 **stdout 多出 1 行差异** ✗ ⇒ 被 A/B 精确指出 ✓
  ⇒ 修：(a) 那处字面文本还原 ✓；(b) 替换**只作用于搬过来的正文**、不碰生成的文件头 ✓；
    (c) **注释行**里的误改也还原（`loop_l1` 5 处 + `loop_l2` 6 处 ✓，代码里的切片 `[::_S.FWD]` 保留 ✓）
  ⚠ **教训（写进 §七 7.5）**：**文本替换必须区分"代码引用"与"注释 / 字符串字面文本"** ✗
* **同步点命中**（§七 7.4 预告；这次是 2 个守门 ✗）：
  `loop_engine` 的 import ✓ ·
  `_test_engine_mem_budget.py`（它的 pattern **全是 L1 的** ⇒ 改看 `loop_l1.py` ✓）·
  `_test_inject_pools.py`（改成按"**阶段层三份拼起来**"搜 ⇒ 对今后搬迁也稳 ✓；它原读 `loop_stage.py` 找 `--decorr` 对照集 ✗）·
  `_test_dual_horizon.py`（AST 检查覆盖三个文件 ✓）
* **验证**：`_test_undefined_names` **0 处** ✓ · 受影响守门 **7/7** ✓ ·
  ★★ **同 seed A/B**：`base2` ←→ `s2b` ⇒ **8 个产物逐字节相同 + stdout 逐行相同（0 差异）** ✓✓
  （**修复前**那一次 stdout 有 1 行差异、被抓住 ✓；轨迹还原逐字节校验 ✓）
* **R1 仍差**：6 个函数 >120 行（`_run_l2_phase` 251 · `_run_l1_phase` 197 · `_l1_eval` 174 ·
  `_run_prepare` 151 · `_run_gen` 135 · `_l1_filter` 133）⇒ **S3** ✓

> ⚠ 一处**如实记账**：新增的 `tools/_pool_traj.py` 带了一个 `HERE`/`ROOT` 常量 ✗ ⇒
> `_audit_codebase` 的 `ROOT`/`HERE` 出现次数 +1（96 个**同名常量**的组数未变 ✓）。
> 这是全项目通用写法（`ROOT` 本就 ×110 ✓），非新增违规种类 ✓，故不动 ✓。

---

## [1.25.1] — 2026-09-27

> 主题：**函数级拆分 S1 —— L2 组搬出 `loop_stage.py`**（可读性/可维护性 → 9 的第 1 步）
> ⚠ **引擎行为逐字未变**（下述 A/B 实证 ✓）

* **搬迁**：`_run_l2_phase` / `_l2_strip_dual` / `_l2_pool_tags`（**436 行**）→ 新文件 **`engine/loop_l2.py`** ✓
  ⇒ `loop_stage.py` **1349 → 909 行**（R2 还差一步：L1 组待搬 ⇒ 目标 ≤800 ✓）
* **怎么搬的**（避免手抄改行为 ✗）：脚本 `ai_test/_split_l2.py` 按 **AST 行范围**切片、**原文搬运** ✓，
  只做两件可控的事：① 按"用了哪些名字"**挑 import**（23 → 12 条 ✓ 不留死 import）
  ② `FWD` → **`_S.FWD`**（★ `FWD` 是主口径快照，**仍只准在 `loop_stage.py` 定义一处** ✓；
     `loop_l2.py` 用 `import loop_stage as _S` **运行时读** ✓ —— **禁止**值拷贝 ✗）
  ★ 写盘前有护栏：**任何模块级名字没被覆盖 ⇒ 拒绝写盘** ✓（本次报告"无 ✓"）
* **同步点**（`maintainability.md §七 7.4` 预告的三个 ✓，本次命中 1 个守门）：
  `loop_engine.py` 的 import 行改成 `from loop_l2 import (...)` ✓（**仍在 loop_engine 层 re-export**，
  因为多个守门按 `loop_engine._run_l2_phase.__code__` 做断言 ✓）；
  `tools/_test_dual_horizon.py` 的 L2 pattern 改看 `loop_l2.py` ✓，并**新增两条防退化断言**：
  ① `loop_l2.py` **不许自己再定义 `FWD`** ✗ ② 必须**运行时读** `_S.FWD` ✓

### ★★ 验证（本项目的铁律：名字解析 + 同 seed A/B，两条都跑 ✓）

* `_test_undefined_names.py` **0 处** ✓ · `py_compile` ✓
* 受影响守门 **7/7 全过**：`_test_dual_horizon` · `_test_fsa_freeze` · `_test_node_single` ·
  `_test_inject_pools` · `_test_engine_mem_budget` · `_test_undefined_names` · `_test_version_sync` ✓
* ★★ **同 seed A/B（`tools/ab_generation.py`）**：改前 `_ab/base2` ←→ 搬运后 `_ab/s1`
  ⇒ **8 个产物逐字节相同 + stdout 逐行相同（0 差异）** ✓✓
  （`state` 走逐字段比 ✓；对照工具此前已自证可信 ✓）
* 轨迹已还原并**逐字节校验** ✓（池 50 未被污染 ✓）

> **下一步（S2）**：同法搬 L1 组（`_run_l1_phase`/`_l1_eval`/`_l1_filter`，504 行）→ `engine/loop_l1.py`
> ⇒ `loop_stage.py` ≈ 405 行（R2 达标 ✓）；随后 S3 = 按注释段落把那 6 个函数切到 ≤120 行（R1 ✓）。

---

## [1.25.0] — 2026-09-27

> 主题：**把「同 seed A/B」落成一条命令**（并**自证可信**）· 端到端守门去重 · **函数级整治方案定稿**
> —— 为「可读性 / 可维护性 → 9」做前置：先把**验证手段**建好，再动 `loop_stage.py`（v1.23.0 的教训 ✓）
> ⚠ **引擎行为零改动**（本次只加工具/文档 + 守门重构 ✓；`git status` 可证 `engine/` 一字未动 ✓）

### 一、新增 `tools/ab_generation.py` + `tools/_pool_traj.py`：**同 seed A/B 一条命令** ✓

`docs/maintainability.md` R7 早写明「**搬函数/拆模块后必须跑「名字解析检查 + 同 seed A/B」**」✗，
但"名字解析"有常驻守门、"**A/B 一直靠人手跑**" ✗ —— 而 **v1.23.0 就是漏了 A/B 才发版即崩** ✗（用户白等一晚）。

* `tools/_pool_traj.py` —— 池轨迹的**快照/还原/真跑一代**（单一实现 ✓，供守门与 A/B 共用 ✓）。
  隔离只能靠备份还原 ✗：引擎产物路径是 `__file__` 派生、**无参数/环境变量出口** ✓
* `tools/ab_generation.py` —— `--out <dir>` 跑一代存产物；`--diff A B` 逐文件对照
  （`state` 走**逐字段**比、CSV/md 走逐字节、stdout 剔耗时后逐行 ✓）

★★ **自证可信（关键）**：用**未改动的代码**跑两遍再对照 ⇒
**8 个产物逐字节相同 + stdout 逐行相同（0 差异）** ✓✓ —— 这样"改后出现差异"才一定是**真差异** ✓
> 自检当场抓出并修掉工具自己的两个坑（否则会**假报差异** ✗）：
> ① `Node` **没有 `__eq__`** ⇒ `==` 退化成身份比较，把内容相同的种子判成不同 ✗（改为按表达式文本比 ✓）；
> ② 诊断行 `leaf_hist {...}` 的**字典键序**随 `PYTHONHASHSEED` 变 ✗（内容相同）⇒ 固定 `PYTHONHASHSEED=0` ✓
>   （⚠ 只影响那条诊断行的**键序**，对数值无影响；生产没设它，本工具只是把它变成可控实验 ✓）

### 二、端到端守门改用共用库（去重复实现 · R5）

`tools/_test_e2e_l1l2.py` 原来的备份/还原/起引擎是**自己一份** ✗ ⇒ 与 `ab_generation` 撞车 ✗
⇒ 现统一走 `_pool_traj` ✓，重跑 **20/20 全过** ✓（里程碑 / 产物 / 隔离 / 还原逐字节一致 ✓）

### 三、`docs/maintainability.md §七`：函数级整治方案定稿（**可执行**）

* 侦察（`ai_test/_ls_inventory.py`）：`loop_stage.py` = **1349 行 / 9 函数 / 69 个 ctx 键**，
  6 个函数超 R1（251/197/174/151/135/133 ✓）
* ★ **关键判断：不需要新造 dataclass 配置对象** ✓ —— 先前"20 个口径参数没法传"的结论**不成立** ✗：
  **`ctx` 就是状态对象**、**`args` 就是口径对象**（本来就是属性读 ✓）；
  "参数爆炸"**只在 4 个子函数签名上**（`_l2_pool_tags` **18** / `_l1_eval` **13** / …）——
  它们把 **ctx 里的东西拆开传**了 ✗ ⇒ 改传 `(ctx, args, 少量)` ✓
* ★★ 列出**三个必须同步的点**（漏一个就静默崩 ✗）：`loop_engine` 的 import 行 ·
  **`_LS.FWD = _FM.FWD` 同步**（`FWD` 是主口径快照，拆文件后仍须**单处定义 + 运行时读** ✓）·
  **3 个直接读 `loop_stage.py` 的静态守门**（`_test_inject_pools` / `_test_fsa_freeze` / `_test_dual_horizon` ✓）
* 验收协议：每步 `_test_undefined_names` + **A/B 逐字节** + `release_check`（55 条 · ~11 分钟 ✓）

### 验证

* `tools/_test_e2e_l1l2.py` 重跑 **20/20** ✓ · A/B 工具自证 **8/8 产物逐字节 + stdout 0 差异** ✓
* `git status` 证明 **`engine/` 未改动** ✓ ⇒ 已存基线 `ai_test/_ab/base2` 即"改前"参照 ✓
* 全量回归与 tag 前的 `release_check` 见下一条提交（拆分执行时同步 ✓）

---

## [1.24.0] — 2026-09-27

> 主题：**把「发版前检查」从文档纪律落成一条命令** · **补上项目最大的测试空白（真跑 L1/L2）** · **change_log 归档**
> —— 用户指令："把除了功能性以外所有的项目都提升到 9 分"（先做前三项：可测试性 / 工程纪律 / 文档）
> ⚠ **引擎行为零改动**（本次只加测试/工具/文档 ✓）

### 一、补上最大的测试空白：**真跑一代的完整 L1 + L2**（可测试性 8 → 9）

**问题有多严重**（v1.23.0 真事故的根因）：本项目此前**没有任何测试跑过 L1/L2** ✗ ——
存活的"真起引擎"测试（`smoke_gen_only.py` / `_test_parallel_runner.py` / `_test_dynamic_add.py`）
**一律用 `--gen_only`，而它恰好跳过 L1+L2** ✗✗（`_test_ghost_args.py` 自己都写明了这点）。
⇒ v1.23.0 拆分后 `loop_stage.py` 少了 4 个 import（`HERE` / `trim_cache_mb` / `ts_mean` / `_P.LIB_ENTRIES`），
**全部测试照样全绿**，而真实挖掘**每代秒崩** ✗ ⇒ 用户白等一整晚。

**新增 `tools/_test_e2e_l1l2.py`**（20 项断言 · 实测 **184 s**）：
- **生产同款 flag**：`--strip_style --style_obs --pool_obs --min_pool_calmar --pool_gate_or_all --dual_fwd=20 --min_calmar2=0.701`
  —— 那 4 个 `NameError` 就住在这几条路上 ✓
- **规模压到最小**：`--mine_pool=50`（最小池）· `--n=12` · `--l2=2` ⇒ 全链路 ~3 分钟（不是 50~80 分钟 ✓）
- **隔离靠备份/还原**：引擎产物路径是 `__file__` 派生的、**没有参数/环境变量出口** ✗
  （`loop_paths.set_mine_pool` 只接受真实池名 ✓）⇒ 备份 8 个文件 → 跑 → 断言 → **还原并逐字节校验** ✓
- **断言**：里程碑齐全（候选生成 → L1 分批 → L1 结果 → L2 精筛 → L2 结论 → 诊断写 journal → 代末落盘）
  · 无 `Traceback`/`NameError` · state/archive/journal **真的被更新** · **别的池分毫未动**（防"写错池"）✓
- **安全前提做成硬检查**：挖掘在跑 ⇒ **直接失败退出**（不静默跳过，否则发版可能不经它 ✗）

### 二、"同 seed A/B"终于自动化了（可测试性）

**新增 `tools/_test_gen_determinism.py`**（14 项断言 · 2 × 27 s）：
本项目铁律"搬函数后必须跑『名字解析检查 + 同 seed A/B』"里，**"名字解析"早有守门、"A/B"一直靠人手跑** ✗。
⇒ 用 `--gen_only`（不跑 L1/L2、不写状态 ✓）同 seed 跑**两遍**、剔掉耗时/时刻后**逐行比对** ✓。
指纹含各拦截计数与 **`尝试36`**（对 RNG 流极敏感 ✓）、本代参数/五维配比/亲本策略、上一代 state 的诊断数值 ✓。
实测：**0 差异行** ✓（生成确实可复现 ✓）。
> ⚠ 覆盖边界（如实说）：`--gen_only` 只打印**摘要计数**、不打印 30 条表达式 ⇒
> 这**不能**证明"候选集合逐字节相同" ✗（那要 L1，~25 分钟 ✗）；
> 它能抓的是**随机性/顺序漂移**（漏播种的 `random`、`set` 迭代顺序、`hash` 随机化 …）—— 正是重构最易踩的那类 ✓

### 三、发版纪律落成**一条命令 + 一个退出码**（工程纪律 8 → 9）

**新增 `tools/release_check.py`**（发版前**唯一入口**）：
```
① 版本一致性（VERSION / README / change_log / package.json / settings …）
② 未定义名（拆分/搬函数最容易漏的那类 NameError）
③ 全部守门（tools/_test_*.py 串行跑，逐个落日志 ai_test/_release_logs/）
④ 汇总：通过 x/y · 失败清单 · 最慢 3 个 · 总耗时 · 非零退出
```
★ 为什么需要：此前"发版纪律"**只写在文档里** ✗（`change_log` v1.21.16 那条"全量回归必须先跑完全绿"），
而回归入口 `ai_test/_run_all_tests.py` 自己就是个**临时脚本**、还在"可随时删"的目录里 ✗
⇒ "发版前该跑什么"**依赖人记得** ✗（v1.23.0 的教训正是"记得跑的不够、该自动的没自动" ✗）。
★ 硬前提：**挖掘在跑 ⇒ 拒绝执行**（两个 heavy 守门一个真写轨迹、一个依赖 state 稳定 ✓
  且既有守门会写控制文件 ✓ 与"挖掘运行时禁跑全量回归"同源 ✓）。
★ 支持 `--list` / `--only <子串>` ✓

### 四、`change_log.md` 归档（文档 6 → 9）

本文件曾 **549 KB / 7683 行 / 154 个版本** ⇒ 查最近改动得先翻过一年份历史 ✗（"文档"扣分的就是这条 ✓）。
⇒ 主文件**只保留最近 15 个版本**（**549 KB → 71 KB，‑87%** ✓），其余 **139 个版本**整段搬到
**新增 [`change_log_archive.md`](change_log_archive.md)**（478 KB）。
★ **原文一字未改** + 切分器与校验：版本数 **15 + 139 = 154** ✓ 无重复 ✓ 无丢字 ✓（只多出前言/指针/归档头 277 字符 ✓）。

### 五、八维评分更新（`docs/maintainability.md`）

| 维度 | 09-26 | **09-27** | 变化依据 |
|---|---|---|---|
| 可测试性 | 8 | **9** | 补上"完整 L1/L2 端到端"（§一 ✓）+ "同 seed A/B"自动化（§二 ✓）；守门 52 → **55 条** |
| 工程纪律 | 8 | **9** | 发版前检查落成 `release_check.py`（一条命令 + 退出码 + 挖掘护栏 ✓，§三 ✓） |
| 文档 | 6 | **9** | change_log 归档（549 KB → 71 KB ✓，§四 ✓） |
| **综合** | **7.4** | **8.0** | 64 / 8 = 8.0 |

> ⚠ 未动的三项（**不是忘了** ✗）：**功能性 8**（行为逐字不变 ✓ 是本次的硬约束）；
> **性能 6**（**一次性能优化都没做** —— 重构期明令"不许动数值路径"，要做须用户明确授权"允许改实现、但结果逐位不变"✗）；
> **可移植性 7**（看板仍是 Windows 专有：`taskkill` / `ctypes` Win32 内存 API / `CREATE_NO_WINDOW` ✗）；
> **可读性 8 / 可维护性 8**（`loop_stage.py` 仍 1332 行、2 个函数 >300 ⇒ **违反本项目自己的 R1/R2** ✗，
> 再拆的前提是先把 ~20 个口径参数收进一个 dataclass，否则只是"上帝函数换上帝参数表" ✗）。

### 验证

- ★ **`tools/release_check.py` 全量：55/55 全过 ✓（总耗时 10.0 分钟）** ——
  含新增两个守门：`_test_e2e_l1l2.py` **186 s** ✓ · `_test_gen_determinism.py` **57 s** ✓
  （最慢三名：e2e 186s · `_test_parallel_runner` 152s · `_test_daily_dd` 61s ✓）
- 单独实跑：e2e **20/20** ✓ · 确定性 **14/14**（0 差异行 ✓）· crash 徽标 **14/14** ✓
- change_log 切分校验：154 → 15 + 139 ✓ 无重复 ✓ 无丢字 ✓
- 引擎行为：**零改动**（本次未碰 `engine/` ✓）

---

## [1.23.2] — 2026-09-26

> 主题：**修「停止之后，池卡片仍挂着『启动即崩』红字徽标」** —— 用户实测驱动，纯看板侧修复

### 现象（用户实测）

> "我全部停止了，然后看到俩池子现在都是启动即崩的状态，这跟以前好像不一样？
>  以前应该是回到已停止的状态才对吧~"

### 真因（**不是文案 bug，也不是本次拆分引入的回归** ✓）

前端**本来就**会把状态文案显示成「已停止」✓（`App.tsx`：`configured ? '待启动' : (stopped ? '已停止' : '空闲')`）；
用户看到的是**多出来的红色徽标**「启动即崩 ×1」✗。

徽标的语义是「**此刻**启动即崩」（见 `tools/parallel_runner.py` 2026-09-20 的设计说明 ✓），
但它**只有一个撤销触发点：跑通一代（`rc==0` 且 stderr 为空）** ✗ ——
而「**被用户停掉**」的退出码是 `rc=1` ⇒ 走 `if rc != 0` 分支、`killed=True`
⇒ **既不写徽标、也不撤徽标** ✗✗ ⇒ 一次真崩留下的徽标会**一直挂着** ✓

**实测时间线**（`ai_test/_tracks/_engine_exits.log`）：

| 时刻 | 池 / 代 | rc | 耗时 | 判定 | 效果 |
|---|---|---|---|---|---|
| 22:22:02 | `all` gen81 | 1 | 0.6min | **异常** `NameError: 'HERE'` | **写徽标** ✓ |
| 22:22:42 | `300` gen191 | 1 | 1.3min | **异常** `NameError: 'trim_cache_mb'` | **写徽标** ✓ |
| 23:42:14 | `all` gen81 | 1 | **24.9min** | **被停**（err=0） | **没撤** ✗ |
| 23:46:14 | `300` gen191 | 1 | 0.5min | **被停**（err=0） | **没撤** ✗ |

⇒ 两池其实**早已恢复正常**（`v1.23.1` 那次各跑了 **24.9 分钟、stderr 为空**，
是用户主动停的 ✓）⇒ 徽标是**过期证据** ✓

⚠ **为什么以前没见过**：这个缺口自 2026-09-20 就在 ✗，只是**以前那两池没经历过"真崩"**
（v1.23.0 是第一次）⇒ 没有徽标可残留 ✓ —— 所以用户"感觉不一样"是对的，但不是"停止逻辑变了" ✓

### 修法

`dashboard/api/app/mine.py` 新增 `clear_crashes(pools=None)`，并在**停止**时调用：
- **单池停止** ⇒ `clear_crashes([pool])` ✓（只撤该池，**别的池的徽标不许误撤** ✗）
- **全部停止** ⇒ `clear_crashes()` ✓

★ **语义**：**停止 = 用户的明确动作、该池已回到空闲** ⇒ 徽标"此刻已不成立" ⇒ 一并撤掉 ✓
★ **保护不减弱**：真·必崩的池**下次启动还会崩** ⇒ 一分钟内徽标自动回来 ✓
  （撤的是「过期证据」，**不是关掉报警** ✓ —— 守门里专门钉住这条 ✓）

### 验证

- **新增守门 `tools/_test_crash_badge.py`（14 项全过 ✓）**：
  静态 3 项（接线 + "非被停的异常退出仍写徽标"）＋ **行为 8 项**（导入 `app.mine`、
  换到**临时控制文件**真调 `clear_crashes`：只撤指定池 · 不误撤他池 · 幂等 ·
  「不碰 `exits` / `enabled` / `stopped`」· 原子写 ✓）
- **清掉当前残留**：`_control.json` 的 `crashes` 由 `{all:[81], 300:[191]}` → `{}` ✓
- **重启后端**（`dashboard/api/run.py`，`reload:false` ⇒ 必须重启 ✓）；
  接口复核：`/api/mine/state` 的 `crashes = {}` ✓ ⇒ 卡片恢复干净「已停止」✓

---

## [1.23.1] — 2026-09-26

> 主题：**修 `v1.23.0` 的 4 处 `NameError`（拆分漏 import / 用了调用方局部）
> + 修「副口径复原成 no-op」造成的口径静默污染** —— **纯修复，恢复正常挖掘**

### 真事故（v1.23.0 发版后，重启挖掘第一批就崩）

| 现象 | 真因 |
|---|---|
| `all` 池：`NameError: name 'HERE' is not defined` | `loop_stage.py` 用了 `HERE`（引擎目录）但**没定义/没 import** ✗ |
| `300` 池：`NameError: name 'trim_cache_mb' is not defined` | `loop_stage.py` 用了 `trim_cache_mb` 但**没 import** ✗ |
| **L2 每个候选**都只打一行 `[j] ERR NameError`（被 `except` 吞掉） ⇒ **一个候选都入不了库** ✗✗ | `_l2_pool_tags` 里用了 **调用方 `_run_l2_phase` 的局部变量 `pool_rows`** ✗（同类：`ts_mean` 没 import、`loop_persist` 的 `LIB_ENTRIES` 没改成 `_P.`、`run_tracks._rotate_schedule` 漏了 `panel_cache` 形参） |
| **池内指标静默改口径**（实测池门槛 `+0.254`，正确值 `+0.192`）| 文件级拆分时把 `FWD` **一律替换成 `_FM.FWD`** ✗ ⇒ 副口径块的 `finally: _FM.set_fwd(int(FWD))` 变成 `int(_FM.FWD)` ⇒ `set_fwd(20)` 之后 `_FM.FWD` **自己就是 20** ⇒ **"复原"是 no-op** ✗✗ |

### 为什么没被拦住（★ 诚实记账）

`v1.23.0` 的 **L3 Step 4（文件级拆分）只跑了 `py_compile` + 全量回归**，
**漏掉了 Step 1~3 一直在用的「同 seed 复跑 + `state` 逐字段对照」** ✗。
而全量回归**不覆盖完整 L1/L2 路径**（`_test_parallel_runner` 用 `--gen_only` 跳过 L1/L2），
且那 4 个名字**只在特定参数/特定池下才走到** —— 典型：`HERE` 那行只在 `all` 池
「外部池注入」时执行，而我的对照命令是 `--mine_pool=500` ⇒ **正好跳过了它** ✗。
⇒ **教训**：**`py_compile` 只查语法、不查名字**；搬函数后必须做一次**作用域感知**的名字解析检查 ✓

### 修法

1. `loop_stage.py`：补 `HERE` / `from loop_cache import trim_cache, trim_cache_mb` / `from loop_ops import …, ts_mean`
2. `loop_persist.py`：补 `import re`（`_mk_library_skeleton` 用）+ `LIB_ENTRIES` → `_P.LIB_ENTRIES`
3. `loop_stage.py`：`pool_rows.extend(pool_rec)` **从 `_l2_pool_tags` 移回调用方** `_run_l2_phase`（那里才是它的作用域 ✓）
4. `run_tracks.py`：`_rotate_schedule` 补 `panel_cache` 形参（**轮转模式一起就崩** ✓，生产用并行模式所以没暴露）
5. **`loop_stage.py` 恢复模块级 `FWD`**（`FWD = _FM.FWD`）：
   `[::FWD]` 切片与副口径 `finally` 复原**都回到它** ✓；`loop_engine.main()` 的 `--fwd` 同步块
   **同时同步 `loop_stage.FWD`** ✓（否则 `--fwd` 只改一个模块 ✗）
6. `loop_stage.py` 的 L2 异常打印**补上异常消息**（原来只有 `type(e).__name__` ⇒ 排查时看不到名字 ✗）

### ★ 新增常驻守门 `tools/_test_undefined_names.py`（作用域感知）

扫「**用了、却在本作用域链上都没绑定过**」的名字（自建，因为本机没装 `pyflakes`）：
形参 / 赋值 / `for` / `with` / `except` / import / 嵌套 def 名 / `global`+`nonlocal` 都算绑定，
再沿**闭包链**解析到模块级与内置名 ⇒ 四条都不满足就报 ✓
⚠ 关键：**必须是作用域感知的** —— 第一版用「全文件绑过就算」的宽松判据，
**抓不到「用了调用方的局部变量」**（`pool_rows` 正好被 `_run_l2_phase` 绑过 ✗）。
⇒ 现在扫描 167 个文件、**未定义名 0 处** ✓

### 验证（★ 这次是 **A/B**，不是"看起来对"）

把 `engine/` 用 `git checkout 1129380`（**文件级拆分之前**）恢复，跑**完全相同**的命令
（`--mine_pool=500 --seed=777 --n=20 --l2=3 --strip_style --style_obs --pool_obs
--pools=300,500,1000 --dup_ex_corr=0.90 --min_pool_calmar=0.15 --pool_gate_or_all
--min_strip_calmar=0.15 --dual_fwd=20 --min_calmar2=0.701`）：

| 项 | 拆分前（`1129380`） | 拆分后（本版） |
|---|---|---|
| 候选 [1] 池内指标 | `300:+3.15%/Cal+0.19(市值2.42%/倾斜-0.74%) 500:+1.88%/Cal+0.11 …` | **逐字相同** ✓ |
| 池门槛 | `过(+0.192)` | **`过(+0.192)`** ✓ |
| 种子 / 入库 / 收益流库 / 冻结骨架 / 失败库 / 冻结记账 | 3 / 10 / 10 / 3 / 584 / 17 | **完全相同** ✓ |
| `ERR` / `NameError` | 0 | **0** ✓ |

⇒ 全量回归 **52/52** ✓（含新守门）

### 连带：诚实修订八维评分（7.6 → **7.4**）

`v1.23.0` 这次事故**正好暴露了两个维度的真实缺口** ⇒ 修订（依据与全文见 `docs/maintainability.md §五`）：
- **可测试性 9 → 8**：守门虽到 52 条，但**仍不覆盖完整 L1/L2**（`_test_parallel_runner` 用 `--gen_only` 跳过）✗；
- **工程纪律 9 → 8**：`v1.23.0` **验收不完整**（Step 4 漏了同 seed A/B）⇒ 发版即崩 ✗（现已补规则 ✓）

⇒ 综合 **6.4 → 7.4**（59 / 8 = 7.375）；结构短板（巨型文件/God function）确实已补齐 ⇒ 分数较基线仍显著上升 ✓

---

## [1.23.0] — 2026-09-26

> 主题：**易维护性整治上线（L1 死码清理 → L2 大函数拆分 → L3 上帝模块拆分）**
> —— **纯结构改动，引擎行为逐字不变**（每步都用「同 seed 复跑 + `state` 逐字段对照」守住）

### 背景

2026-09-25 全项目体检结论：**「纪律/测试 A 级、结构 C 级的高质量单体」** —— 八维评分综合 **≈6.4/10**，
短板全在**结构**（单点巨人 `loop_engine.py` 3917 行 · `run()` 单个函数 1079 行 · 加 1 个算子要同步 10 处）。
本次按 `docs/maintainability.md` 的 **R1~R8** 规则分三轮整治（**未验收不进下一步**）。

### L1 死代码清理（净删约 856 行）

- `factor_miner.py` 删 6 个零引用旧实现（`ts_decay` / `evaluate_dual` / `fmt_dual` /
  `run_round_real` / `load_lib` / `save_lib`）
- `loop_engine.py` 删 6 个死 pandas 老算子（`ts_std` / `ts_sum` / `ts_rank` / `ts_corr` / `ts_max` / `ts_min`，−28 行）
  ★ 死/活判定以 `ops_registry.py` 为**唯一事实源**（`ts_delay`/`ts_delta` 绑 `'le'` ⇒ 活；`ts_mean` 被去相关闸门直接调 ⇒ 活）
- 删 `engine/ml_common.py`（共享数据层，live 代码无人 import）+ 5 个归档研究脚本
  ★ **教训**：删任何"疑似死码"前，`grep` 要**连 `history/` 归档一起搜**（`_audit_deadcode` 只扫 `engine/tools/standard`）

### L2 次级大函数拆分（行为不变）

| 函数 | 前 | 后 | 做法 |
|---|---|---|---|
| `run_tracks.main` | 433 | **76** | 抽 `_parse_args`(191) + `_rotate_schedule` / `_finalize_schedule` |
| `factor_curves.main` | 370 | **42** | 抽 7 个纯函数 + 模块级 `_path` |
| `combo_constrain.run` | 369 | **10** | 抽 `_parse_args`/`_load_and_prep`/`_simulate`/`_report` |
| `combo_build.main` | 304 | **40** | 抽 7 个纯函数（顺带删死 import `datetime`）|
| `parallel_runner.run` | 390 | **344** | 抽 `_setup_parallel`/`_cleanup_parallel`（调度状态机保留）|
| `loop_critic.suggest` | 308 | **207** | 抽 `_init_sug`/`_apply_rules`/`_finalize_sug`（闭包网 ctx 化留第二步）|

### L3 上帝模块拆分（★ 本次大头）

- **Step 1**：`Node` + `collect` → `engine/loop_expr.py`（顺带根治「一份代码里并存两个 `Node` 类」，82 个 `import loop_engine as LE` 全透明）
- **Step 2**：拆段落模块 —— `loop_dims`（跨量纲审查）· `loop_faillib`（失败模式库）·
  `loop_ops`（算子表接线）· `loop_gen`（亲本选择/变异/交叉）· `loop_llm_guide`（LLM 引导解析）+ 骨架/结构族并入 `loop_expr`
- **Step 3**：`run()` **ctx 化**拆 5 个子步骤（`_run_prepare` / `_run_gen` / `_run_l1_phase` / `_run_l2_phase` / `_run_finalize`）
  ⇒ **`run()` 1079 → 10 行**纯编排
- **Step 4**：文件级拆分 ⇒ `loop_paths`（路径常量 + `MINE_POOL`）· `loop_cache`（缓存 + L1 状态）·
  `loop_data`（面板构造）· `loop_persist`（落盘 + 库文档同步）· `loop_eval`（评估/审查/生成辅助）·
  `loop_stage`（9 个阶段函数）⇒ **`loop_engine.py` 3917 → 619 行**（只剩 `run()` 8 行编排 + import + argparse + main）

**成果**：**`>1500 行巨型文件 1 → 0 个`** · **`>300 行函数 6 → 2 个`**；
引擎拆成 **12 个单一事实源模块**，依赖**严格单向（无环）**：
`loop_engine` → `loop_stage` →（`loop_eval`/`loop_persist`/`loop_data`/`loop_cache`/`loop_paths`/`loop_gen`/`loop_dims`/`loop_faillib`/`loop_llm_guide`）→ `loop_expr`/`loop_ops`。

### 验证（★ 每步都做，不是最后补的）

- 每步 `py_compile` + **同 `seed=777` 复跑 + `state` 逐字段对照**
  （`bank` / `seeds` / `cfg` / `fail_lib` / `fsa` / `last_l1` / `last_l2` 全 OK；
  ★ 对照方法：`Node` 用 `str(node)` **值比对** —— `==` 是身份比较会**假阳性**）
- 全量回归 **51/51**（含端到端真跑）；`_audit_deadcode` 的「彻底无引用」除动态注册例外已清零

### 顺带修的既有隐患（只有完整跑 `run()` 才暴露，`--gen_only` 冒烟覆盖不到）

- `loop_llm` 未绑定（`--llm_guide=off` 时崩）· `_agg_style_diag` 死透传 `_k` 未绑定
- 4 个死透传兜底（`k` / `v` / `_v` / `f`）—— ctx 化后它们的兜底赋值点移走了，显式给 `None`
- **3 个「值拷贝陷阱」全部规避**：`_P.STATE` / `_P.MINE_POOL` / `_C.VCACHE` / `_FM.FWD` 一律
  **模块引用运行时取**（`import X as _P` + `_P.X`），**不再 `from X import CONST`**
  （同 `FWD` / `LLM_MAX_SIZE` 踩过的坑：`from` 是 import 时值拷贝，运行期改不到）

### 重打分（八维 · 2026-09-26 发版时重评；口径 = 八项**简单平均**，与 09-15 基线同口径）

| 维度 | 09-15 | **09-26** | 依据 |
|---|---|---|---|
| 功能性 | 8 | **8** | 行为逐字不变，功能未增减 |
| 可测试性 | 8 | **9** | 51 条守门 + 每步 seed 对照法 + 模块可独立 `py_compile`/单测 |
| 工程纪律 | 9 | **9** | 一功能一提交 + 编码自检（0 U+FFFD）+ 台账 |
| 性能 | 6 | **6** | 未做性能优化（重构要求行为不变）|
| 可读性 | 6 | **8** | God function 消失、`run()` 8 行、模块单一职责；⚠ 扣分项见下 |
| 可移植性 | 5 | **7** | 路径全 `__file__` 派生 + `loop_paths` 单一来源 |
| 文档 | 5 | **6** | 规则 + 台账 + README 同步；`change_log` 偏流水 |
| 可维护性 | 4 | **8** | 3917→619 行 · 12 模块 · 依赖单向 · R1~R8 落地；⚠ 扣分项见下 |
| **综合** | **6.4** | **7.6** | 结构短板补齐（8 项简单平均：61/8 = 7.625）|

⚠ **诚实的剩余（扣分项，不假装满分）**：`loop_stage.py` 现为 **1332 行** ——
① **违 R2**（新文件应 ≤800）；② 其中 **6 个函数仍超 R1**（`_run_l2_phase` 248 · `_run_l1_phase` 197 ·
`_l1_eval` 173 · `_run_prepare` 150 · `_run_gen` 134 · `_l1_filter` 132）。
它们是「深度耦合的单候选处理 + 20 个口径参数」，抽纯函数会**参数爆炸**
（试拆 `_l2_judge` 已确认 13 参数 ⇒ **回退**）。
⇒ **`loop_engine.py` 文件级达标（≤800 ✓），函数级收益递减，本轮在此收口** ✓

### 规则落地

- 新增 `docs/maintainability.md`（**R1~R8 唯一规则源** + 违规台账 + 执行方案 L0~L3）

---

## [1.22.4] — 2026-09-25

> 主题：**修「本轮启动过、又被停掉」的池会永久排队（且本轮永不收口）**
> （用户实测："我重新开启（沪深300），它怎么要排队了？"；现场：`enabled:["300","all"] · stopped:[]`、
> 日志 `上限 2(自动·总容量) · 可用 12.5 GB` 却 **`待启动 0`** ⇒ 300 进不了候选 ✗）

### 真因（`tools/parallel_runner.py` 代码坐实）

- 候选池 = `启用 − 已停 − **本轮已启动(launched)**`（原 `L715-718`）；而 `300` 在 19:31 **已启动过一次**
  （`[START] pool=300 gen=191`，20 秒后被用户停掉）⇒ **留在 `launched` 里** ✗
- `launched` 原来**只有**两处 `discard`：① 某池**跑完一代**且 `_again` 成立（继续领下一代）
  ② 某池**崩溃**（`crashed`，按 `MAX_CRASH_RETRY` 重试）—— **"被用户停掉"（`killed`）没有** ✗
- ⇒ 300 **本轮永远回不到候选**；而同轮又**收不了口**：收轮判据 =
  「每个 `pending_pools` 池都完成 ≥ `min_gens_per_round`（默认 **3**）代」，
  而 `pending` 含 300 且其 **0 代** ⇒ `_again` **恒 True** ⇒ `all` 跑完一代就被 `discard` 回去**继续领下一代**
  ⇒ `running` 永不为空 ⇒ `not running and not cand` 的 `break` **永不触发** ⇒
  **本轮不完 ⇒ 轮末全局收尾（跨池审查/精选池/指标表/登记表）也不执行** ✗✗
- 顺带：`19:31:27` 那句日志「空槽留给你自己决定（点「启动本池」的那个会**马上**开挖 ✓）」对
  "**排队中的池**"成立 ✓，对"**本轮已启动过又被停**"的池**不成立** ✗（文案过度承诺）

### 修法

1. **抽纯函数** `candidate_pools(en_list, st, launched, deferred, killed_user)`：
   候选 = 启用 − 已停 − 本轮已启动 − 本轮已放弃；`st`（已单独停）**永远一票否决**（放最前 ✓）；
   `launched` / `deferred` 各带一个"**你放回来就允许马上上**"的逃逸口 ✓
2. `_reap` 被停路径：`killed_user[pool] = 被停那一刻的 stopped 快照`
   ⇒ 池被停后又回到启用集（不在 `st`）⇒ `candidate_pools` 放它**本轮再上** ✓（与 `deferred` 同一条语义）
3. 循环的候选生成：`cand = candidate_pools(_en_list, st, launched, deferred, killed_user)`（不再内联列表推导）

### 守门 / 验证

- 新守门 **`tools/_test_sched_relaunch.py`**：
  【1】复现现场（300 被停后再启用 ⇒ 回到候选）+ 负向（无 `killed_user` ⇒ 仍被 `launched` 挡住 = 旧 bug ✓）
  【2】`st` 一票否决 / `deferred` 逃逸口 / 正常候选（回归不破）【3】静态接线 3 条
- 同步更新 `tools/_test_sched_fair.py`（候选改纯函数后的**有序名单**断言）与
  `tools/_test_parallel_runner.py`（A11 动态候选断言）—— 原断言钉的是旧的内联写法 ✗
- **全量回归 50/50** ✓（含 `_test_parallel_runner` 端到端 `--gen_only` 真跑：`--pools=300,500` 并行、
  无 traceback、state/journal SHA256 **未变** ✓）

### 影响面 / 回退

- **只动调度器的候选/收轮逻辑** ✗ 引擎的挖掘与判定、库/数据**均未改** ✓
- ⚠ **需重启调度器才生效**（`parallel_runner.py` 是调度器进程在用的模块，启动时已加载）
- 回退：`git checkout v1.22.3`（旧行为 = "本轮启动过又被停的池只能等下一轮" ✗）
- 现场确认：用户重启调度器后实测 `300` 只等一会儿内存（槽位 1→2）就开始并行挖 ✓

---

## [1.22.3] — 2026-09-25

> 主题：**详情页加「IC 口径注」＋ 9 个编号的「在库」口径收口**
> （用户："详情页加 IC 口径注" · "9 个编号收口"；前情是"先用全A 的指标吧"与"9 个 CSV 你核对一下"）

### 一、先说清一件事：**三个 IC 数字各有定义**（纠正 2026-09-21 的旧结论 ✗）

**背景**：用户看详情页时觉得"文字指标 / 图上的 `ic` / 图的 `RankIC`"三个数对不上。

**旧结论（2026-09-21，**本次实测否定** ✗）**：原以为"库里指标是引擎**按池**算的、曲线是全A 口径
⇒ 同一页两套口径并排"。

**2026-09-25 逐行读代码 + 当场复算后的事实**：
- `tools/factor_metrics.py` 调 `evaluate_real(...)`，其投资域是 `engine/factor_miner.py:215` 的
  `get_universe()` = **全市场 PIT 可交易** ⇒ **与曲线同一个掩码** ✓
- 且 CSV 的 `ic_doc`（引擎写进库文档明细段的 IC）与重算的 `ic` **15 位完全相同**
  （`F04_300` 两列都是 `0.00987929327746464` ✓）⇒ **文字与图本来就同口径、不存在"按池 vs 全A"** ✗

**真因 = IC 的定义与采样不同**（同一个因子的三个数**都对** ✓）：

| 位置 | 数值（`F04_300` · 5 日） | 定义（代码依据） |
|---|---|---|
| 文字（指标表 / 库文档明细段） | **0.00988** | **逐日 2090 天**截面 `spearmanr` 均值（`factor_miner.py:231-250`；窗口重叠）|
| 图 `ic`（Pearson） | **0.01167** | **换仓日 418 期** Pearson（`factor_curves.py:229` 的 `np.corrcoef`）|
| 图 `rank_ic`（RankIC） | **0.01005** | 同一条引擎 IC 序列，只取换仓日 418（`factor_curves.py:269` 的 `reindex(rb)`）|

**用户拍板**：**"先用全A 的指标"**（统一按全A 口径）⇒ **不重算曲线、不改指标口径** ✓
⇒ 另一件相关事实写清：**非 `all` 池因子的图与文字，投资域都是全市场**（不是该池成分）；
池内口径在 `docs/loop_pool_obs*.csv` 与池标签那边 ✓（与 `--pool_gate_or_all` 语义一致 ✓）

### 二、改法：详情页加「IC 口径注」（`dashboard/web/src/App.tsx`）

- 「费后指标」那块**之前**新增一行 `dt-note`：说清这块的 `ic` = **全日频 Spearman 均值**、
  图的 `ic` = **换仓日 Pearson**、`RankIC` = **换仓日 Spearman**（三个数不同属正常）
  ＋ **全A 之外的池（300/500/1000）指标与曲线投资域是全市场、不是该池成分股** ✓
- IC 图下的 `ch-note` 补一句"本图两条都是换仓日采样"
- 文案遵守用户可见文本铁律（无 Markdown 标记 / 无引号类字符 ✓，过 `_test_ai_tone` + `_test_ui_quotes` ✓）
- **守门**：`tools/_test_frontend_wiring.py` 新增 **【12】3 条**（口径注在位 / 投资域写明 / 图注在位 ✓）

### 三、9 个编号的「在库」口径收口

**症状**：`state.bank` 合计 **67**，而 `docs/factor_metrics*.csv` 的 `in_bank=1` 合计 **76** ⇒ 差 **9**
—— 而**看板「因子库」读的就是这一列**（`factors.py::_inb`）⇒ 这 9 条**显示为在库**（引擎库里其实没有）✗

**逐条判据**（只读脚本 `ai_test/_retired_audit.py`，按 `docs/loop_strip_style*.csv` 的 `strip_calmar`）：

| 池 | 编号 | 剥风格 Calmar | 判读 |
|---|---|---|---|
| `1000` | `F02/F04/F05/F06/F08/F09` | −0.05 ~ −0.10 | **纯风格**（剥后转负）|
| `300` | `F02` | **+0.180** | 过门槛；**同式子在 1000 池 `state.bank` 里** ⇒ 别名 |
| `500` | `F01` | **+0.180** | 同上（同一式子）|
| `500` | `F02` | **+0.171** | 过门槛 ⇒ **原因待查**（**不臆造理由** ✓）|

**改法**（脚本 `ai_test/_retire_apply.py`：**默认 DRY-RUN** · 写前**自动备份**（`ai_test/_backups_20260925_retire/`）· `.tmp` + `os.replace` 原子写 ✓）：
1. `docs/factor_library_{300,500,1000}.md`：总览表**状态列** ＋ **明细段体内**各标「已移出」
   ⚠ **两处都要** —— `export_factor_registry.parse_overview` 只跳状态列、`parse_detail` 跳**块体**含
   "已移出"的块，而 `build()` 是 `set(overview) | set(detail)` ⇒ **只改总览列会被明细块带回登记表** ✗
2. `docs/library_entries.jsonl`：删这 9 条（76 → **67**）——
   它是 `build_facs.load_bank_nodes()` 的**并集源**之一，留着就会被 `factor_metrics.refresh_in_bank`
   **每轮刷回 `in_bank=1`** ✗
3. `docs/factor_metrics*.csv`：**不手改**，按顺序重生成 —— `export_factor_registry.py` →
   `factor_metrics.py --only-new`（5 日）→ 同上的 `--fwd 20`（各刷 **6 行**；
   刷新发生在**载面板之前**、随即"无待算"退出 ⇒ **秒级** ✓）
4. `docs/factor_registry.json` 一并重导（顺带带上 v1.22.2 回填后的**真实家族**：
   `未分类` → `价格` / `风格` ✓）

**验证**：

| 项 | 结果 |
|---|---|
| md 两处（总览列 + 明细段）| ✓ 9/9 |
| **不在** `library_entries.jsonl` · **不在** `factor_registry.json` | ✓ 9/9 |
| 5 日 + 20 日 CSV `in_bank` | ✓ 均 **0** |
| **登记表条目 = 5 池 `state.bank` 合计** | **67 = 67** ✓（收口前 CSV 口径是 76 ✗）|
| `ai_test/_retired_audit.py` 各池差集 | ✓ **全部归零**（46 / 4 / 10 / 7）|
| ★ **接口实测**（`ai_test/_api_check.py`，8101 在线）| ✓ 9 条 `inBank=false` ＋ 新状态串；三池 `stateBank` = **4 / 10 / 7** ✓ |

⚠ **取舍（知情）**：这 9 条既不在 JSONL、也不在登记表 ⇒ `load_bank_nodes()` 不再收它们
⇒ 收尾**不再自动**给它们算指标/曲线；要看它们的数得显式带 `--include_history` ✓
（**原有文件不会被删**，仍在 `docs/factor_metrics*.csv` 与 `docs/factor_curves*/` 里 ✓）

### 四、文档同步（`docs/loop_todo.md`）

- `§1.30`：**改写为"三个 IC 数字各有定义"**，并**留痕**记下原结论错在哪 ✗ ＋ 用户拍板"先用全A" ✓
- `§1.31`：**新增**（9 个编号的判据 / 改动 / 收口的坑 / 验证），执行后改为 **✅ 已完成** ✓
- `§0.1 / §0.2 / §0.4 / §0.5`：按实测更新（`all` 池 gen79 在跑 · 各池状态与**口径修正** ·
  **20 日双口径已在生产 `extra`**：`--dual_fwd=20 --min_calmar2=0.701`（2026-09-22 起）✓）
- ⚠ 记一条教训：2026-09-21 的探针（`_expo_repro.py` / `_ic_scope_probe.py`）**已随 `ai_test/` 清理而不在仓库** ✗
  ⇒ 文档改为**只引用可重跑的脚本**（`ai_test/_curves_scope_check.py` ✓）

### 五、影响面 / 回退

- **引擎的挖掘与判定逻辑未改** ✓（本次只动**前端文案**、**库文档状态列**、**入库历史 JSONL**、
  以及**登记表 / 指标表的对账字段**）
- ⚠ `factor_metrics*.csv` / `factor_curves*/` 是**产物**（`.gitignore`）⇒ **回退代码不会回退它们**
- 回退：`git checkout v1.22.2`（md / JSONL 属**数据**，要回退得手工、或从
  `ai_test/_backups_20260925_retire/` 取原件 ✓）
- 验证：**全量回归 49/49** ✓ · `tsc --noEmit` ✓ · `_test_ai_tone` / `_test_ui_quotes` 干净 ✓
- 本版含**前端用户可见改动** ⇒ 刷新 `5273` 即可看到（Vite 源热更，**无需** `npm run build` ✓）

---

## [1.22.2] — 2026-09-25

> 主题：**修「一份代码里并存两个 `Node` 类」**（因子库家族全落「未分类」＋ 骨架去重 / FSA 冻结失效 ✗✗）
> **＋ 修「新入库日志卡点开的详情页，20 日口径按钮被误置灰」**
> （用户实测：_"这 F47 为啥会显示未分类"_ · _"20 日的那个按钮我点不了，提示还未生成"_）

### 一、修「一份代码里并存**两个 `Node` 类**」⇒ 家族全落「未分类」＋ 骨架去重 / FSA 冻结失效 ✗✗

**症状**（用户之问）：新入库的 `F47` 在因子库里显示 **「未分类」** ✗

**真因**：引擎**直跑**时模块名是 `__main__`（`Node` 的类全名 = `__main__.Node` ✗），而
`loop_critic` 的**惰性** `import loop_engine as LE` 会把 `loop_engine.py` **再执行一遍**
（这次模块名是 `loop_engine` ✗）⇒ 同一个进程里出现**两个 `Node` 类** ✗

**实测规模**（读 `loop_state.pkl`，按 pickle 记录的类路径统计）：

- `bank` 里 **439** 个 Node 中 **438 个**是"第二份" ✗
- `seeds` / `last_l1` 也各混着 **24** 个 ✗（合计 **486** 个异类）

**后果**（`isinstance(x, Node)` 对"第二份"实例**恒为 False** ✗）：

| 牵连 | 后果 |
|---|---|
| `collect()` → `leaf_parts()` | 因子库"家族"全落 **「未分类」** ✗（`docs/loop_archive*.csv` 的 `cat`/`leaf` 列空，全库 **392 行**）|
| **`skeleton()`** | **骨架去重 / FSA 冻结失效** ✗（同族重复因子拦不住）|
| `key()` / `size()` | FSA 结构哈希对那批因子失真 ✗ |
| `crossover` / `mutate` | 子树操作退化成"只能动顶层" ✗ |
| `dim_of()` / `clone` | 跨量纲审查、克隆同样失效 ✗ |

**改法（两处）**：

1. **治本（一行）** —— 引擎末尾的 `__main__` 块**第一条**注册自己：

```python
sys.modules.setdefault('loop_engine', sys.modules['__main__'])
```

   ⇒ 之后任何 `import loop_engine` 都拿到**本模块** ⇒ **结构上不可能再有第二份** ✓

   ⚠ **位置有讲究：不能放文件顶部** —— `tools/_test_fwd_wiring.py` 用 AST 取**第一个**
   `__main__` 块，并在其中断言 `set_panel_cache` / `set_mem_budget` / `run(_args)` 是**直接语句**；
   顶部另起一块会抢走它的"目标块"（实测该守门**当场失败** ✗）。放末尾也**足够早** ✓
   （`loop_critic` 是惰性 import，而 `run(_args)` 是该块**最后一句** ⇒ 注册必在它之前 ✓）

2. **治旧（读盘归一）** —— 新增 `_StateUnpickler(pickle.Unpickler)`：`find_class` 把类名 `Node`
   **一律**映射回本模块的类；**主 state** 与**外部池注入**两处读取都改走它 ✓
   ⇒ 旧 state 里已混入的 **486 个异类**在读盘时**自动归一**（无需重算、无需手改 state ✓）

**数据回填**：`docs/loop_archive*.csv` 的 `cat`/`leaf` 补齐 ⇒ 空 `cat` 行 **392 → 0** ✓

| 文件 | 空 `cat`（回填前 → 后）|
|---|---|
| `loop_archive.csv`（全A）| 39 → 0 |
| `loop_archive_1000.csv` | 178 → 0 |
| `loop_archive_300.csv` | 160 → 0 |
| `loop_archive_500.csv` | 15 → 0 |
| `loop_archive_50.csv` | 0（本就齐 ✓）|

⚠ 回填**只补 `cat` / `leaf` 两列**，**指标数值逐字未动** ✓（备份在 `ai_test/_backups_20260925/` ✓）
⚠ `docs/loop_archive*.csv` 在 `.gitignore` 里 ⇒ 回填**不入库**（属产物 ✓）

**文档同步**：`docs/factor_library.md`（**6 处**）＋ `docs/factor_library_1000.md`（**3 处**）
的「未分类」修正为真实家族 / 叶子 ✓（合计 **9 处**）

- `F47`（全A gen78 · `ts_mean200(ts_std60(cs_demean(neg(low))))`）：`未分类` → **`价格` / `low`** ✓
- `F34`（全A）：`未分类` → **`风格`×3**（`barra_residual_volatility` / `barra_non_linear_size` / `barra_liquidity`）✓
- `F10`（1000 池）：`未分类` → **`换手率`、`风格`×2** ✓

（`docs/factor_registry.json` 一并重导 ⇒ 与回填后数据一致，**内容无变化** ✓）

**新守门** `tools/_test_node_single.py`（4 组）：

1. **静态**：注册在位 ✓ · 在**末尾**块里 ✓ · 引擎**只许 1 个** `__main__` 块 ✓ · 注册在 `run(_args)` 之前 ✓
2. **静态**：`_StateUnpickler` 已定义 ✓ · state 的**两处**读取都走它 ✓ · 无残留裸 `pickle.load` ✓
3. **功能**：`bank`＋`seeds` 共 **516** 个 Node **全部**是本模块类（异类 **0**）✓ ·
   `last_l1` 里"取不到叶子"（会落「未分类」）的候选 = **0** ✓
4. **数据**：各池 `loop_archive*.csv` 的 `cat` 空行 = **0**（防再次出现 ✓）

### 二、修「新入库日志卡点开的详情页，20 日按钮被误置灰」

**症状**（用户之问）：_"20 日的那个按钮我点不了，提示还未生成"_ ✗ —— 而数据其实**早就算好了** ✓

**真因**：详情页判 `has20 = (metrics20Info ? … : true) && Object.keys(f.metrics20 ?? {}).length > 0`
⇒ **哪个入口没把 `metrics20` 传给 `FactorDetail`，那一路的 20 日按钮就恒置灰** ✗
实测**三条入口里只有「新入库日志」卡漏了** ✗（「因子库」表 /「精选池」两条都传了 ✓）
—— 后端 `/api/library/entries` 本就照抄了 `metrics20` ✓，是**前端漏传** ＋
`LibraryEntryDto` 类型里也缺字段 ✗

**改法**：

- `dashboard/web/src/api.ts`：`LibraryEntryDto` 补 `hzn?` / `metrics20?` ✓
- `dashboard/web/src/App.tsx`：详情弹层传 `metrics20: entrySel.metrics20` ✓
- 口径仍**只有一处**（后端照抄 `_lib(pool)`）✓ 前端不自己算 ✓

**守门**：`tools/_test_frontend_wiring.py` 新增【11】—— **三条入口**各钉一处 ＋
`LibraryEntryDto` 必须有这两个字段 ＋ 后端 `factors.py` 必须照抄
`'detail', 'metrics', 'metrics20', 'status', 'hzn'` ✓

### 三、工程杂项

- `.gitignore`：加 `*.bak_before_*`（批量改数据时的临时备份**不入库** ✓；备份本身保留、可回滚 ✓）

### 四、验证

| 项 | 结果 |
|---|---|
| `tsc --noEmit`（前端改动）| ✓ 0 错 |
| `_test_node_single.py`（新守门）| ✓ 全过 |
| `_test_fwd_wiring.py`（注册挪位后）| ✓ 全过 |
| 真机冒烟 `ai_test/smoke_gen_only.py` | ✓ **4/4**（`loop_state*.pkl` SHA256 **未变** ✓）|
| **全量回归** `ai_test/_run_all_tests.py` | ✓ **49/49 通过** |

### 五、影响面 / 回退

- **引擎的因子求值逻辑未改** ✓（只加一行注册 ＋ 读 state 走归一 Unpickler ✓）
- ⚠ 本次发版后须**重启调度器**，注册与归一才在新进程生效 ✓
  （旧 state **无需手工处理**：新进程读盘时自动归一 ✓）
- 回退：`git checkout v1.22.1`（数据回填属产物，留着无害 ✓）

---

