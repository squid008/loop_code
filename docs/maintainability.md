# 易维护性方案与规则（2026-09-25 体检后定稿）

> ★ 本文是**代码易维护性的唯一规则源** —— 改 `engine/` / `tools/` 任何代码前先读这里。
> 现状诊断来自 2026-09-25 全项目体检（工具 `tools/_audit_codebase.py` / `_audit_deadcode.py` /
> `_audit_coupling.py` / `_audit_full.py`，见 `docs/loop_todo.md §2.4`）。
> 定位：**「纪律/测试 A 级、结构 C 级的高质量单体」** —— 纪律与守门很强，唯一短板是**结构没拆**。

---

## 一、规则（★ 必须遵守；每条都可由 `tools/_audit_*.py` 机器检查）

### R1 函数长度
- 新函数 ≤ **120 行**（硬上限 150）。超了按「职责/注释段落」拆纯函数或独立模块。
- 查：`python tools/_audit_codebase.py`（【3】最长函数）。

### R2 文件长度
- 新文件 ≤ **800 行**。
- `engine/loop_engine.py`（现 3917 行）是**唯一允许超标的遗产文件**，但必须**只减不增**：
  每次改它**顺带拆一段出去**，净增必须为 0 ✗。
- 查：`python tools/_audit_codebase.py`（【2】巨型文件）。

### R3 单一事实源
- 任何常量 / 名单 / 门槛 / 口径**只准一处定义**，别处一律 import。
- 查：`python tools/_audit_codebase.py`（【5】同名常量）—— 出现同名常量 = 违规。

### R4 无死代码
- 删功能必须**连实现一起删**。`_audit_deadcode` 报的「彻底无引用」要定期清零。
- ⚠ 两类**合法例外**（不许误删）：
  1. `ops_registry` 的**动态按名引用**（`build_*(..., vars())` / `getattr`）—— 算子实现看着无引用、其实是活的；
  2. **故意保留的反面教材**，注释必须写明「保留仅作反面示例」（例：`factor_miner.cs_zscore`）。
- 查：`python tools/_audit_deadcode.py`（它自己会打印这条局限警告，删前再 grep 一遍名字的字符串引用）。

### R5 单一实现
- 同一算子 / 同一语义只准**一份实现**。
- 新算子只写在 `engine/fastops.py`（实现）+ `engine/ops_registry.py`（清单）；
  **禁止** pandas 老实现与新实现并存（存量老实现见下方台账，逐个清）。

### R6 拆分方式（什么时候拆、怎么拆）
- 文件/函数过大时：按**注释分隔的段落**抽独立模块（一个段落 = 一个模块/一个纯函数）。
- `run()` 这类主循环用 **`ctx` 状态对象**传状态：把可变状态收进一个 dict/对象，子步骤只读写它，
  不再靠十几个闭包变量。
- 拆出去的部分必须能独立 `py_compile` + 有守门覆盖。

### R7 守门
- 每次动 `engine/` / `tools/` **核心逻辑**，配一条 `tools/_test_*.py`：**复现现场（负向）+ 断言新行为**。
- 改完跑全量回归：`python ai_test/_run_all_tests.py`（必须全绿）。

### R8 提交与文档同步
- 改一个功能 = 一个 commit + 一条 `change_log.md` 条目；中文提交走 `-F` 文件 + 编码自检（0 U+FFFD）。
- 任何口径/参数/现状数字改完，**同步 `docs/loop_todo.md`**（唯一事实源是**代码与数据文件**，md 是快照+指针）。

---

## 二、现状违规台账（2026-09-25 体检基线 · ★ 最右列 = 2026-09-26 整治结果）

| 违规 | 位置（09-25 基线） | 量级 | 09-26 整治结果 |
|---|---|---|---|
| 上帝模块 | `loop_engine.py` | **3917 行** / 98 顶层定义 / `run()` **1079 行** | ✅ **已拆**：`loop_engine.py` **619 行**（`run()` 8 行）· 拆出 **12 个**单一职责模块 |
| 次级大函数 | `run_tracks.main` 447 · `parallel_runner.run` 390 · `factor_curves.main` 370 · `combo_constrain.run` 369 · `loop_critic.suggest` 308 · `combo_build.main` 304 | 6 个 >300 行 | ✅ **已拆**：76 / 344 / 42 / 10 / 207 / 40 ⇒ **`>300 行函数 6 → 2`**（余 `parallel_runner.run` 342 · `horizon_admit_write.main` 303）|
| 双实现残留 | `loop_engine.py` 里 `ts_std/ts_sum/ts_rank/ts_corr/ts_delay/ts_delta` 的 pandas 老实现（零调用，被 `fastops` 取代） | 待清 | ✅ **已清**（L1-②：删 6 个死 pandas 算子，−28 行）|
| 死代码 | `factor_miner.py`：`ts_decay/evaluate_dual/fmt_dual/run_round_real/load_lib/save_lib`（旧双口径+旧 lib 读写） | 本轮清 | ✅ **已清**（L1-①）＋ `ml_common.py` + 5 个归档研究脚本 |
| 重复常量 | `strategies/` 下的 all00/all01/all03/all04 四个策略脚本：`MIN_LIST_DAYS/USE_PANIC_LEV/PANIC_DD` 各 ×6 | 研究留档，冻结 | ⚪ **冻结不动**（用户拍板，不抽）|
| 孤儿研究代码 | `strategies/` 14 个 .py / 4022 行，0 生产引用 | 研究留档，不动 | ⚪ 研究留档，不动 |

---

## 三、执行方案（★ 按风险从低到高，逐项验收，未验收不进下一步）

### L0 文档规则化（零风险 · 2026-09-25 完成）
- 本文 + `docs/loop_todo.md §1.33` 台账 + `§2.4` 指针 ✓

### L1 死代码清理（低风险，机械可验证）
- [x] `factor_miner.py` 删 6 个零引用旧实现（`ts_decay`/`evaluate_dual`/`fmt_dual`/`run_round_real`/`load_lib`/`save_lib`）—— 全量回归 50/50 ✓
- [x] **L1-② 完成（用户拍板选 a）**：删 `loop_engine.py` 6 个死 pandas 老算子
  （`ts_std/ts_sum/ts_rank/ts_corr/ts_max/ts_min`，−28 行）+ 3 个归档研究脚本
  （`history/research/` 下的 round1 / round2 / bench_ops 三个脚本，均 git 追踪、已坏/失效；**已删**）
  ★ 死/活判定以 `ops_registry.py` 唯一事实源为准：`ts_delay`/`ts_delta` 绑 `('le', ...)` → 走本文件
  pandas 版（**活，保留**）；`ts_mean` 被去相关闸门 L2819 直接调用（**活，保留**）；其余 6 个绑
  `('fo', ...)` → 走 fastops ⇒ pandas 版**零引用**（`ts_max/min` 只被死 `ts_rank` 调用）⇒ 删 ✓
- [x] **L1-③ 完成**：删 `ml_common.py`（原在 `engine/` 下；ML验证 & 双重同伴效应的共享数据层，live 代码无人 import）
  + 2 个归档研究脚本（`peer_effect.py`/`verify_neutral.py`）。★ 背景：广发「双重同伴效应」是 2026-09-08
  Round18 已**验证失败**（申万 31 互斥行业下 peer_avg 无 alpha）并放弃的方向，与 A/B 角挖因子无关 ✓
- ⏸ **剩余极小死码（价值≈0，暂不删）**：`loop_pools.pool_masks`（1 行 wrapper）/ `loop_watch.now_s`（1 行）/
  其余都随 ml_common 一起清了 —— 这些留着只占 `_audit_deadcode` 一行噪音，等随模块级改动顺手删
- 验收：`_audit_deadcode.py` 的「彻底无引用」基本清零（registry 例外 + 上面 2 个极小 helper 除外）+ 全量回归绿

> ⚠ **教训（写进 R4 的实例）**：删任何"疑似死码"前，`grep` 要**连 `history/` 归档一起搜** ——
> `_audit_deadcode` 只扫 `engine/tools/standard`，漏掉 `history/research/` 的 import ✗
> （本轮 `LIB` 常量被 `round1.py` import，就是漏搜导致的；好在该脚本本就已坏，不影响生产 ✓）

### L2 重复常量抽取 / 次级大函数拆分（中风险，行为不变）
- [x] `strategies/` 重复常量 → 用户拍板「冻结不动」（研究留档，不抽）✓
- [~] 次级大函数逐段拆纯函数（进行中）：
  - [x] `combo_build.main` **304→40 行**：抽 `_parse_args`/`_load_bank`/`_load_base`/`_eval_factors`/
    `_build_weights`/`_synthesize`/`_emit_report` 7 个纯函数；守门 `tools/_test_combo_build.py` **15/15**；
    顺带删死 import `datetime`
  - [x] `factor_curves.main` **370→42 行**：抽 `_parse_args`/`_setup_output`/`_collect_items`/`_dedup`/
    `_filter_needed`/`_build_context`/`_run_items` + 模块级 `_path`；顺带删死变量 `_pre`
  - [x] `combo_constrain.run` **369→10 行**：抽 `_parse_args`/`_load_and_prep`/`_simulate`/`_report`
  - [x] `run_tracks.main` **433→76 行**：抽 `_parse_args`（191 行）+ `_rotate_schedule`/`_finalize_schedule`
    （轮转主循环 + 退出收尾）
  - [~] `loop_critic.suggest` **308→207 行**（第一步：抽 `_init_sug`/`_apply_rules`/`_finalize_sug`；闭包网 ctx 化留第二步）
  - [x] `parallel_runner.run` **390→~344 行**：抽 `_setup_parallel`/`_cleanup_parallel`（启动段 + 退出清理；
    主循环 307 行的调度状态机保留）
- 验收：每拆一个配守门 + 全量回归绿 + 行为逐字不变（必要时 diff 产物）

### L3 上帝模块拆分（高风险，分多步，进行中）
- [x] **Step 1：抽 `Node` + `collect` 到 `engine/loop_expr.py`**（表达式核心类型/遍历单一事实源）
  —— 顺带根治「两份 Node」问题（Node 独立后天然单类）；82 个 `import loop_engine as LE` 全部透明 ✓
- [x] Step 2：抽失败模式库 / 跨量纲 / 亲本选择 / LLM 引导 等段落（**全部完成**）：
  - [x] **Step 2a**：抽跨量纲审查 `dim_of`/`review_expr`/`_FIELD_DIM` 到 `engine/loop_dims.py`
  - [x] **Step 2b-1**：抽骨架/结构族（`norm_op`/`skeleton`/`root_fam`/`sole_leaf`/`leaf_proxy_key` + FSA/FAM 常量）到 `loop_expr.py`
  - [x] **Step 2b-2**：抽失败模式库（`flib_mark`/`fail_lib_cleanup`/`bad_skels`）到 `loop_faillib.py`
  - [x] **Step 2b-3a**：抽 le 算子 + 算子表接线（`UNARY`/`BINARY` 派生）到 `loop_ops.py`（打破「要用算子表就得 import 整个 engine」的环）
  - [x] **Step 2b-3b**：抽亲本选择 + `DEFAULT_CFG`（`pick_leaf`/`rand_expr`/`mutate`/`pick_parent`…）到 `loop_gen.py`
  - [x] **Step 2b-3c**：抽 LLM 引导（`tokenize_expr`/`parse_expr`/`llm_fetch`）到 `loop_llm_guide.py`
    ★ `LLM_MAX_SIZE` 留 loop_engine（运行期可改，避免「值拷贝」漏掉 tools 的临时放开）
- [x] **Step 3：`run()` ctx 化，拆 5 个子步骤（全部完成，2026-09-26 用户在场配实盘对照）**：
  - [x] **Step 3a**：抽准备阶段（初始化+数据+载入 state+审查/黑名单/失败库/随机探索）到 `_run_prepare(args)` 返回 ctx
  - [x] **Step 3b**：抽生成阶段（B角五维配比+LLM引导+守卫链+gen_only）到 `_run_gen(ctx, args)`
  - [x] **Step 3c**：抽 L1 阶段（批量 IC+形状/去相关/去重/族配额/FSA/jury）到 `_run_l1_phase(ctx, args)`
  - [x] **Step 3d**：抽 L2 阶段（费后精筛+剥风格/池指标/收益流去重+落盘）到 `_run_l2_phase(ctx, args)`
  - [x] **Step 3e**：抽保存/诊断阶段到 `_run_finalize(ctx, args)`，run() 收敛为 **10 行纯编排**（原 1079 行）
  - ★ 顺带修 2 个既有 bug（`loop_llm` 未绑定 / `_agg_style_diag` 死透传 `_k`）+ 4 个死透传兜底（`k/v/_v/f`）
- 验收：每步守门 + 全量回归 + **与实盘挖掘结果对照**（同一代 seed 复跑，产出必须一致）

> ✅ **Step 3 完成（2026-09-26 用户在场）**：用户在场配了「同 seed=777 复跑 + state 逐字段对照」。
>  全程 5 步每步 `py_compile` + 同 seed 复跑 + `_cmp_state` 逐字段比对（bank/seeds/cfg/fail_lib/fsa/
>  last_l1/last_l2 全 OK），最终全量回归 **51/51**。`run()` 由 **1079 行 → 10 行**纯编排。
>  ★ 对照方法：改前先跑一次记录 baseline state（MD5），改后恢复 state 备份同 seed 复跑，unpickle 逐字段比对
>  （Node 对象用 `str(node)` 值比对，`==` 是身份比较会假阳性）。

- [x] **Step 4：文件级拆分（文件 ≤800 达成，2026-09-26）**：
  - [x] 路径常量 + `MINE_POOL` → `loop_paths.py`（`apply_suffix` 单一事实源）
  - [x] 缓存 + L1 状态 → `loop_cache.py`（`_C.VCACHE`/`_C._LRU` 等，模块引用）
  - [x] 面板构造 → `loop_data.py`；落盘 → `loop_persist.py`；评估/审查 → `loop_eval.py`
  - [x] 库文档/收益流/保存（`_lib_sync`/`_save_state` 等 10 个）→ `loop_persist.py`
  - [x] 9 个阶段函数 → `loop_stage.py`
  - ✅ **`loop_engine.py` 3917 → 619 行**（只剩 `run()` 8 行编排 + import + argparse + main）
  - ★ 值拷贝陷阱全部规避（`_P.STATE`/`_P.MINE_POOL`/`_C.VCACHE`/`_FM.FWD` 都走运行时取）

> ⚠ **诚实的剩余（2026-09-26）**：`loop_stage.py` 现为 **1332 行**（9 个阶段函数），其中 6 个仍超 R1
>  `_run_l2_phase`(247)/`_run_l1_phase`(196)/`_l1_eval`(173)/`_run_prepare`(150)/`_run_gen`(134)/`_l1_filter`(132)。
>  这些是「深度耦合的单候选处理 + 20 个口径参数」，之前试拆 `_l2_judge` 已确认参数爆炸（13 参数）回退。
>  ⇒ 文件级已达标，函数级若要继续硬啃，需接受「参数多/ctx 样板」的代价，收益递减，建议就此收口。

---

## 四、维护节奏

- **每次体检**（`python tools/_audit_full.py` + `_audit_codebase.py` + `_audit_deadcode.py`）对照本文台账；
- 违规项**只减不增**；新增违规 = 当次改动不合格，回退重写。

---

## 五、重打分（八维 · 2026-09-26 发版时重评 · v1.23.0）

> 口径 = 八项**简单平均**（与 2026-09-15 基线同口径，便于逐项对比）。
> 体检工具：`tools/_audit_codebase.py` / `_audit_deadcode.py` / `_audit_coupling.py`。

| 维度 | 09-15 | **09-26** | 依据（实测） |
|---|---|---|---|
| 功能性 | 8 | **8** | 行为**逐字不变**（A/B：回拆分前同参数跑 ⇒ 逐字相同 ✓）⇒ 功能未增减 |
| 可测试性 | 8 | **8** | 守门 **52 条**（＋新增作用域感知的名字检查）＋ A/B 对照法；⚠ **仍不覆盖完整 L1/L2**（v1.23.0 事故证明 ✗，见 §六）|
| 工程纪律 | 9 | **8** | 一功能一提交 + 中文提交编码自检（0 U+FFFD）+ 台账同步；⚠ **v1.23.0 验收不完整 ⇒ 发版即崩**（已补 A/B 与守门 ✓）|
| 性能 | 6 | **6** | **未做性能优化**（重构要求行为不变 ⇒ 不敢顺手改数值路径）|
| 可读性 | 6 | **8** | God function 消失 · `run()` **8 行** · 模块单一职责；⚠ 扣分见下 |
| 可移植性 | 5 | **7** | 路径全 `__file__` 派生 + `loop_paths` 路径常量单一来源 |
| 文档 | 5 | **6** | 本文规则 + 台账 + README 版本表同步；`change_log.md`（522 KB）仍偏流水 |
| 可维护性 | 4 | **8** | **3917 → 619 行** · 12 个单一事实源模块 · 依赖严格单向 · R1~R8 落地 |
| **综合** | **6.4** | **7.4** | 59 / 8 = 7.375 |

> ★★ **评分口径说明（诚实）**：上面是 **`v1.23.1`（已修 v1.23.0 拆分事故）** 的状态。
> v1.23.0 那次 **「Step 4 只用 `py_compile` + 全量回归验收、漏了同 seed A/B」⇒ 发版后第一批就崩** ✗ ——
> 这正是「可测试性」「工程纪律」**没能给到 9** 的原因（扣分依据见 §六 ✓）；
> 事故已修并补上守门与 A/B 规则 ✓，故综合从基线 **6.4 → 7.4**（结构短板确实已补齐 ✓）。

### 硬指标对照（`_audit_codebase.py` 实测）

| 指标 | 09-15 基线 | **09-26** |
|---|---|---|
| `>1500 行巨型文件` | **1**（`loop_engine.py` 3917）| **0** ✓ |
| `>300 行函数` | **6** | **2**（`parallel_runner.run` 342 · `horizon_admit_write.main` 303）|
| 最长函数 | `run()` **1079** 行 | `parallel_runner.run()` **342** 行 |
| `engine/` 总行数 | — | **10833**（47 文件；最大 `loop_stage.py` 1332）|
| `loop_engine.py` | **3917** 行 / 98 顶层定义 | **619** 行 / 1 个函数（`run()` 8 行）|

### ⚠ 诚实的剩余（扣分项 · 不假装满分）

这两条正是上表「可读性 8」「可维护性 8」没给到 9 的原因：

1. **`loop_stage.py` = 1332 行 ⇒ 违 R2**（R2 明写「新文件 ≤ 800 行」；`loop_engine.py` 那条「唯一允许超标的遗产文件」不适用于新文件 ✗）；
2. **其中 6 个函数仍超 R1**（≤120）：`_run_l2_phase` **248** · `_run_l1_phase` **197** · `_l1_eval` **173** ·
   `_run_prepare` **150** · `_run_gen` **134** · `_l1_filter` **132**。

**为什么停在这里**：这 6 个都是「**深度耦合的单候选处理 + 20 个口径参数**」——
抽**纯函数**会参数爆炸（试拆 `_l2_judge` 已确认要 **13 个参数 + 11 个 ctx 解包** ⇒ **已回退并在提交信息里留痕**）；
抽 **ctx 子函数**则样板爆炸（~22 行解包/回存换 ~130 行正文）。**收益为负**，故本轮**主动收口** ✓

> ⇒ **结论**：**文件级已达标**（`loop_engine.py` ≤800 ✓，巨型文件归零 ✓），
> **函数级在 `loop_stage.py` 内收益递减**，若要继续硬啃需先想清「用什么替代 20 个口径参数」（如 dataclass/配置对象），
> 否则只是把「上帝函数」换成「上帝参数表」✗

---

## 六、★ 拆分后的守门补强（2026-09-26 · v1.23.1，**因为 v1.23.0 真的崩了**）

### 事故（诚实记账 · §1.33 的 Step 4 验收不完整）

`v1.23.0`（文件级拆分）**只用 `py_compile` + 全量回归验收，漏了 Step 1~3 一直在做的
「同 seed 复跑 + `state` 逐字段对照」** ✗ ⇒ 发版 + 重启挖掘后**第一批就崩**：

| 崩法 | 真因 |
|---|---|
| `all` 池 `NameError: HERE` | 搬函数时**漏 import**（`loop_stage.py` 用 `HERE` 但没定义）|
| `NameError: trim_cache_mb` / `ts_mean` / `re` / `LIB_ENTRIES` | 同上（4 处）|
| **L2 每个候选**都被 `except` 吞成一行 `ERR NameError` ⇒ **一个都入不了库** ✗✗ | `_l2_pool_tags` 用了**调用方 `_run_l2_phase` 的局部 `pool_rows`** ✗ |
| **池内指标静默改口径**（池门槛 `+0.254` vs 正解 `+0.192`）| 把 `FWD` 一律替换成 `_FM.FWD` ✗ ⇒ 副口径 `finally` 的"复原"变 **no-op** ✗✗ |

**为什么全量回归没拦住**：回归**不覆盖完整 L1/L2**（`_test_parallel_runner` 用 `--gen_only` 跳过），
而那 4 个名字**只在特定参数/特定池下才走到** —— `HERE` 那行只在 `all` 池「外部池注入」时执行，
而对照命令是 `--mine_pool=500` ⇒ **正好跳过** ✗

### 补强（两条，都已落地）

1. ★ **新增常驻守门 `tools/_test_undefined_names.py`（作用域感知）** ——
   扫「用了、却在本**作用域链**上都没绑定」的名字；
   ★ 关键：**必须作用域感知** —— 宽松版（"全文件绑过就算"）**抓不到「用了调用方的局部」** ✗（`pool_rows` 正是这类 ✓）
2. ★★ **改写 Step 4 的验收标准：文件级拆分必须配「同 seed 复跑 + `state` 逐字段对照」A/B** ——
   本次补做（`git checkout 1129380` 回拆分前、同参数跑）：**池内指标与汇总数字逐字相同** ✓（见 `change_log.md [1.23.1]`）

> ⇒ **规则增量（写进 R7 的实例）**：**`py_compile` 只查语法、不查名字**；
> **搬函数 = 必须跑 `_test_undefined_names.py` + 同 seed A/B**，缺一不可 ✗
