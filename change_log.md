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

> ⚠ **归档动作（2026-10-20）**：承诺只保留最近 15 个版本，当时已累积 **16** 条 ⇒ 已把最旧的 1 条**整段原文**搬进 `history/change_log_archive.md` ✓。

> ⚠ **归档动作（2026-10-21）**：承诺只保留最近 15 个版本，当时已累积 **16** 条 ⇒ 已把最旧的 1 条**整段原文**搬进 `history/change_log_archive.md` ✓。

> ⚠ **归档动作（2026-10-21 第二次）**：承诺只保留最近 15 个版本，当时已累积 **16** 条 ⇒ 已把最旧的 1 条**整段原文**搬进 `history/change_log_archive.md` ✓。

> ⚠ **归档动作（2026-10-21 第三次）**：承诺只保留最近 15 个版本，当时已累积 **16** 条 ⇒ 已把最旧的 1 条**整段原文**搬进 `history/change_log_archive.md` ✓。

## [1.45.0] — 2026-10-21

> 主题：**参数页完整可用 + 文档同步（里程碑）** ✓

### 一、本版承载

参数页在 **1.44.0** 上线（23 个参数 · `engine/loop_params.py` 单一事实源 ·
覆盖文件 `docs/loop_params.json` · `run_tracks` 启动时按 flag 合并），
**1.44.1** 做了三轮样式与文案打磨。本版把这一串**记为里程碑**，并同步 gen181~190 的逐代诊断。

### 二、参数页用法（一句话）

页面「参数」页签 → 改值 → 保存 → **下次启动挖掘**按新值跑；
「恢复默认」删掉覆盖文件即回到代码里的生产默认。
危险项有红/黄点：**红 = 会直接改变入库严格度**（如 `min_strip_calmar` / `min_calmar2` / 通道B 各阈值）。

### 三、文档同步

`docs/loop_journal.md` 补入 **gen181~190**（10 代）诊断，重点是 `style_gate` 实验的结论：

* 开 `style_gate` 的 10 代（gen181~190）：**0 入库**；过 `calmar2` 的 7 条里 `strip_calmar < 0` 占 **86%**
* 关 `style_gate` 的 16 代（gen165~180）：**4 入库**；过 `calmar2` 的 8 条里 `strip < 0` 占 **37.5%**
  ⇒ 该规则**方向反了**（它拦掉的正是"把风格写明、剥两者后仍能过门槛"的那类），已在生产参数里回退。

### 四、验证

| 项 | 结果 |
|---|---|
| 全量回归 | 见 §五 |

### 五、发版回归

★ **全量回归：60/60 全绿** ✓（**实测 7.2 分钟** ✓；最慢 `_test_e2e_l1l2` 123 s ·
`_test_parallel_runner` 107 s · `_test_daily_dd` 42 s ✓）。
跑前无挖掘在跑 ✓；跑完**未起引擎** ✓、控制文件已复位 ✓。

---

## [1.44.1] — 2026-10-21

> 主题：**参数页的样式与文案打磨**（用户连续三轮反馈：太宽 / 说明被截 / 列不对齐 / 有 AI 味标记）✓

### 一、样式（`styles.css` + `App.tsx`）

* **表格改成 CSS grid 行**（`.prow`）—— 三次迭代后的最终解：
  1. 每个分组是**独立 `<table>`**，auto 布局按内容分列 ⇒ 各组"当前值"列**起点不一致** ✗
  2. 改 `table-layout: fixed` ⇒ 对齐了，但被容器宽度算法推出可视区、说明列被挤走 ✗
  3. **grid 行**：列宽 `140 / 150 / 100 / minmax(180px, 1fr)` · `gap: 14px`
     ⇒ 各分组**绝对对齐** + 说明列**永远占剩余** + 比 table 的 padding 更紧凑 ✓
* 说明列改用 **`.pdesc`**（不限宽、`white-space: normal`、行高 1.5）——
  原 `.sum` 是 `max-width:160px` + 单行省略号，参数说明会被截断 ✗
  （`.sum` 本身不动：因子列表仍用它 ✓）
* 输入框与下拉框统一 **`.pinp { width:100% }`** ⇒ 视觉等宽 ✓

### 二、文案（`engine/loop_params.py`）

参数说明里去掉机味标记（`**` 加粗、`⇒` 箭头、中文两侧 ASCII 引号），共 4 处。

### 三、守门扩展（`tools/_test_ui_quotes.py`）

* 新增 **`scan_engine_params()`**：参数页的 `label`/`desc` 经 `/api/params` **直接显示给用户**，
  但文件在 `engine/` 下 ⇒ 原来的 `scan_api_strings`（只扫 `dashboard/api`）**扫不到** ✗
  ⇒ 实测漏掉 `**调到 0 = ...**` 被用户直接看到；补上后立刻又抓出 3 处 ✓

### 四、验证

| 项 | 结果 |
|---|---|
| `tsc --noEmit` | 无错误 ✓ |
| `_test_ui_quotes` | **全部干净**（248 条，含新增的参数页文案）✓ |
| 前端接线守门 | 全过 ✓ |
| 全量回归 | 见 §五 |

### 五、发版回归

★ **全量回归：60/60 全绿** ✓（**实测 8.2 分钟** ✓；最慢 `_test_e2e_l1l2` 145 s ·
`_test_parallel_runner` 127 s · `_test_daily_dd` 43 s ✓）。
跑前无挖掘在跑 ✓；跑完**未起引擎** ✓、控制文件已复位 ✓。

---

## [1.44.0] — 2026-10-21

> 主题：**前端「参数」页签**（用户："把所有参数放到前端来…保存之后挖掘就按前端设定来挖"）✓
> 页签位置：**进程** 与 **配置/口径** 之间。

### 一、设计（为什么不能"前端存一套默认值"了事）

参数原先只存在于 `tools/run_tracks.py` 的一个 list 里。若前端另存一套默认值 ⇒ **必然漂移** ✗。
所以做成三层：

| 层 | 位置 | 谁写 |
|---|---|---|
| **元数据 + 生产默认** | `engine/loop_params.py`（**唯一事实源**） | 代码 |
| **覆盖项** | `docs/loop_params.json`（**只含被改过的键**） | 页面保存 |
| **生效** | `run_tracks` 启动时 `merge_extra(load_overrides(), base=_LEGACY_EXTRA)` | 启动时读 |

⇒ 点「恢复默认」即删掉 JSON、完全回到生产默认 ✓；**不会出现两份默认值** ✓

### 二、改动

* **新增 `engine/loop_params.py`**：`PARAM_SPECS`（**23 个参数**的 分组 / 类型 / 默认 /
  范围 / **危险等级** / 说明）、`DEFAULT_EXTRA`、`load_overrides` / `save_overrides`（原子写）/
  `validate`（类型+范围+枚举）/ `merge_extra`（按 flag 替换，不重复追加）
* `tools/run_tracks.py`：原 `extra` list 改名 **`_LEGACY_EXTRA`**（仍是生产默认），
  新增 `extra = merge_extra(load_overrides(), base=_LEGACY_EXTRA)`，启动时打印已应用的覆盖项
* **新增 `dashboard/api/app/sources/params.py`** ＋ `main.py` 三个路由：
  `GET /api/params`（分组清单）· `POST /api/params`（校验 + 保存）· `POST /api/params/reset`
  （engine 模块用 **`importlib` 按路径加载**，避免污染后端 `sys.path`）
* `dashboard/web/src/api.ts`：`ParamItem` / `ParamsDto` + 三个方法
* `dashboard/web/src/App.tsx`：`TabKey` 加 `params`、页签插在「进程」与「配置/口径」之间、
  新增 **`ParamsTab`**（按组表格 + 编辑 + 保存 + 恢复默认 + **危险色标**：红=改入库严格度 / 黄=谨慎）

### 三、验证（实测）

| 项 | 结果 |
|---|---|
| 守门 `tools/_test_loop_params.py`（**新增**） | **11/11**：`PARAM_SPECS.default` 与 `DEFAULT_EXTRA` 一致 · 合并逐字 · 只替换不重复 · 越界/未知键被拒 · 危险项都有说明 · 读写往返 ✓ |
| `tsc --noEmit`（前端类型） | **无错误** ✓ |
| 前端接线守门 | **全过** ✓ |
| 端到端（重启后端 + 真调接口） | 保存 `{min_strip_calmar:0.2, n:700}` → `docs/loop_params.json` 落盘 · `run_tracks --dry` 打印「已应用覆盖」且引擎参数变 `--min_strip_calmar=0.2 … --n=700` · `reset` 删文件 ✓ |
| `py_compile` / 未定义名 | OK / **0 处**（186 文件）✓ |
| 全量回归 | 见 §四 |

### 四、发版回归

* **首轮 59/60** ✗ —— `_test_ui_quotes` 抓到参数页 `note` 里的 `**` 标记
  （用户可见文案禁 Markdown / 引号）⇒ 去掉后**单独重跑通过** ✓（248 条文案全干净）。
* **第 2 轮：60/60 全绿** ✓（**实测 7.0 分钟**；本轮新增 `_test_loop_params.py` ⇒ 59 → **60** 项）。
  跑前无挖掘在跑 ✓；跑完**未起引擎** ✓、控制文件已复位 ✓。

---

## [1.43.0] — 2026-10-20

> 主题：**生成端拦截「纯风格组合」**（用户拍板 A 方案）✓
> 起因：gen171/172 有 3 条候选过了 `calmar2 >= 0.701`，但 `strip_calmar` 分别
> **−0.072 / −0.167 / −0.055** ⇒ 全被剥风格门槛拦下，**白耗 L2**（每条 ≈56 s）。

### 一、规则（`loop_expr.is_style_combo`）

* (a) `barra_*` 叶子**占比 ≥ 0.5** ⇒ 拦（如 `sub(barra_non_linear_size, barra_beta)`）
* (b) 根往下 **2 层内**的 `div`，其**分子子树**含 `barra_*` ⇒ 拦
  （如 `div(div(barra_liquidity, ema26(low)), mf_s_sqty)`、`div(ts_std20(barra_beta), …)`）
* ⚠ **只拦分子侧** ⇒ 不误杀 F50 `div(fa_ocf_ta, div(mf_l_buy, barra_liquidity))`
  （它剥掉 11 个 Barra + 行业后 Calmar 仍 **+0.387** ✓）

### 二、改动

* `engine/loop_expr.py`：新增 `leaves()` / `style_leaf_ratio()` / `is_style_combo()`
  （⚠ 首版 `leaves` 只认 `str` 叶子 ⇒ 漏掉 `Node(op=名, args=[])` 形态 ⇒ 比例恒 0；已修正）
* `engine/loop_stage.py`：`_gen_guard` 增 `style` 分支；生成摘要打印「风格组合拦 N」
* `engine/loop_engine.py`：新增 `--style_gate`（**默认 0 = 关**，行为不变）
* `tools/run_tracks.py`：生产 extra 加 `--style_gate=1`

### 三、验证

| 项 | 结果 |
|---|---|
| 单元（`ai_test/_test_style_gate.py`） | **8/8**：4 个真实坏样本全拦 · F50 不误杀 · 无风格叶子不拦 ✓ |
| 生成段实测（`--gen_only --n=60 --style_gate=1`） | 生成 **60/60**，**风格组合拦 52**（129 次尝试 ≈40%）· `loop_state.pkl` 未改写 ✓ |
| `py_compile` / 未定义名 | OK / **0 处**（185 文件）✓ |
| R1 审计 | 无新增（`_run_gen` 中途到 **124** 行，注释上移后回到 **119**）✓ |
| 前端接线守门 | **全过** ✓ |
| 冒烟（带 `--style_gate=1`） | **4/4**（rc=0 · 无 Traceback/NameError · 全部 state SHA256 未变）✓ |
| 全量回归 | 见 §四 |

### 四、发版回归

★ **全量回归：59/59 全绿** ✓（**实测 7.3 分钟** ✓；最慢 `_test_e2e_l1l2` 118 s ·
`_test_parallel_runner` 112 s · `_test_daily_dd` 40 s ✓）。
跑前无挖掘在跑 ✓；跑完**未起引擎** ✓、控制文件已复位 ✓。

---

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

