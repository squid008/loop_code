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

## 二、现状违规台账（2026-09-25 体检实测）

| 违规 | 位置 | 量级 |
|---|---|---|
| 上帝模块 | `engine/loop_engine.py` | **3917 行** / 98 顶层定义 / 14 段职责 / `run()` **1079 行** |
| 次级大函数 | `run_tracks.main` 447 · `parallel_runner.run` 390 · `factor_curves.main` 370 · `combo_constrain.run` 369 · `loop_critic.suggest` 308 · `combo_build.main` 304 | 6 个 >300 行 |
| 双实现残留 | `loop_engine.py` 里 `ts_std/ts_sum/ts_rank/ts_corr/ts_delay/ts_delta` 的 pandas 老实现（零调用，被 `fastops` 取代） | 待清 |
| 死代码 | `factor_miner.py`：`ts_decay/evaluate_dual/fmt_dual/run_round_real/load_lib/save_lib`（旧双口径+旧 lib 读写） | 本轮清 |
| 重复常量 | `strategies/all00/01/03/04.py`：`MIN_LIST_DAYS/USE_PANIC_LEV/PANIC_DD` 各 ×6 | 研究留档，冻结 |
| 孤儿研究代码 | `strategies/` 14 个 .py / 4022 行，0 生产引用 | 研究留档，不动 |

---

## 三、执行方案（★ 按风险从低到高，逐项验收，未验收不进下一步）

### L0 文档规则化（零风险 · 2026-09-25 完成）
- 本文 + `docs/loop_todo.md §1.33` 台账 + `§2.4` 指针 ✓

### L1 死代码清理（低风险，机械可验证）
- [x] `factor_miner.py` 删 6 个零引用旧实现（`ts_decay`/`evaluate_dual`/`fmt_dual`/`run_round_real`/`load_lib`/`save_lib`）—— 全量回归 50/50 ✓
- [x] **L1-② 完成（用户拍板选 a）**：删 `loop_engine.py` 6 个死 pandas 老算子
  （`ts_std/ts_sum/ts_rank/ts_corr/ts_max/ts_min`，−28 行）+ 3 个归档研究脚本
  （`history/research/round1.py`/`round2.py`/`bench_ops.py`，均 git 追踪、已坏/失效）
  ★ 死/活判定以 `ops_registry.py` 唯一事实源为准：`ts_delay`/`ts_delta` 绑 `('le', ...)` → 走本文件
  pandas 版（**活，保留**）；`ts_mean` 被去相关闸门 L2819 直接调用（**活，保留**）；其余 6 个绑
  `('fo', ...)` → 走 fastops ⇒ pandas 版**零引用**（`ts_max/min` 只被死 `ts_rank` 调用）⇒ 删 ✓
- [x] **L1-③ 完成**：删 `engine/ml_common.py`（ML验证 & 双重同伴效应的共享数据层，live 代码无人 import）
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
  - [ ] `run_tracks.main`（447）· `parallel_runner.run`（390）· `combo_constrain.run`（369）·
    `loop_critic.suggest`（308）
- 验收：每拆一个配守门 + 全量回归绿 + 行为逐字不变（必要时 diff 产物）

### L3 上帝模块拆分（高风险，最后做，分多步）
- [ ] `loop_engine.py` 先按段落抽独立模块（失败库 / 结构族 / 跨量纲 / 亲本选择 / LLM 引导…）
- [ ] `run()` 引入 `ctx` 对象，拆子步骤
- 验收：每步守门 + 全量回归 + **与实盘挖掘结果对照**（同一代 seed 复跑，产出必须一致）

---

## 四、维护节奏

- **每次体检**（`python tools/_audit_full.py` + `_audit_codebase.py` + `_audit_deadcode.py`）对照本文台账；
- 违规项**只减不增**；新增违规 = 当次改动不合格，回退重写。
