# Change Log / 变更日志

本文件**事无巨细**地记录每一次改动。格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [语义化版本 SemVer](https://semver.org/lang/zh-CN/)：
**MAJOR**（不兼容改动）· **MINOR**（向后兼容的功能新增）· **PATCH**（向后兼容的修复）。

> **改动 → 版本 → tag 的动作约定**（沿用 README「版本与回退」）：
> 每次改动 = **一次 commit**；每个版本 = **一个 annotated tag**（`git tag -a vX.Y.Z -F <说明>`）。

---

## 本文件与 `docs/factor_roadmap.md` 的分工

两份文档**相似但职责不同**，不要互相替代：

| | **`change_log.md`**（本文件） | **`docs/factor_roadmap.md`** |
|---|---|---|
| **定位** | 变更台账（审计/回退用） | 研发档案 / 开发手册（复盘/传承用） |
| **记什么** | **每一次改动**：新增/变更/修复/移除，含文件名 | **大改动、踩坑、经验、结论、事后纠正** |
| **粒度** | 事无巨细，逐提交 | 只记**值得复盘**的 |
| **小修小改** | ✅ 都写 | ❌ 不写 |
| **写完后** | 不回头改 | **可被后续章节推翻/纠正**（如 §8.35 推翻 §8.33） |
| **失败/负结果** | 只记"改了什么" | **重点记"为什么错、怎么发现的"** |
| **给谁看** | 想知道"这版动了什么、怎么回退"的人 | 想理解"为什么这样设计、踩过哪些坑"的人 |
| **章节号稳定性** | 版本号即索引 | ⚠ **`§8.x` 编号被 451 处引用**（代码注释/文档）⇒ **只增不改、不重编号** |

**实践口径**：一次改动先在 `change_log.md` 落一行；若它**改变了引擎行为 / 推翻了一个结论 / 踩了新坑**，
再在 `roadmap` 里写一节（带证据与复盘）。纯重命名、纯格式、纯脚本搬移 → 只写 changelog。

---

## [Unreleased]

（下一次改动写这里，发布时整段移到新版本号下）

---

## [0.5.1] — 2026-09-14

> **PATCH / 纯文档**（不改引擎行为）—— v0.5.0 提交后的收尾补充。

### Fixed
- `README.md` 的「已建版本」表：v0.5.0 行由 `HEAD` 改为**实际提交号 `3da89fe`**
  （表格是给人查回退用的，写 `HEAD` 等于没有信息）。
- README 版本表新增**表格约定**：最新一行的"提交"列写 `tag 自身`。
  原因：**一个文件无法记录"包含它自己的那次提交"的哈希**（哈希由内容算出，自指无解）
  ⇒ 与其每版都靠"提交后再补一次"制造永无止境的追赶，不如把这个死结写成显式约定。

### Added
- `docs/loop_todo.md §1.15` — **规则1 也在重演「固定动作」，且连压 13 代完全无效**。
  由 `journal_view.py --index` 意外发现：全A 池 **gen61~gen73 连续 13 代**都在压同一个叶子
  `barra_residual_volatility`，而占比始终回到 62%~100% ⇒ **动作施加了但完全无效**。
  ⇒ 缺的能力：**动作有效性追踪**（现在只记"施加次数"，不记"施加后指标变好没"）。
  建议：施加时登记基线指标，冷却解禁时比对，无效则标记并降权。
- `docs/loop_todo.md §1.16` — **`ai_test/` 全目录被 gitignore，但收尾管线已住在里面**。
  `run_tracks.py` / `build_facs.py` / `cross_pool_review.py` / `critic_sensor_report.py` /
  `fix_csv_schema.py` / `backfill_library_pool.py` / `_test_*.py` 都是**生产路径**，
  而 `.gitignore` 仍写着"临时诊断脚本（可随时删）" ⇒ **约定已漂移**。
  ⚠ 后果：`git checkout v0.x` **回退代码时整条收尾管线会消失**（回退点不完整）。
  已在 `v0.5.0` 的 tag 说明里显式标注；修法（建 `tools/` 迁出管线脚本）待拍板。

---

## [0.5.0] — 2026-09-14

> 主题：**池化挖掘闭环 + B角「诊断→决策」链条修复 + 收尾提速**
> 覆盖 `roadmap §8.24 ~ §8.45`。此提交后入库因子：全A 41 · 中证300 2 · 中证500 3 · 中证1000 6。

### Added（新增）

**因子值落地仓（`facs/`）**
- `engine/factor_store.py` — 因子值持久化仓（2026-09-14）。每因子落 `facs/<hash2>/<name>/`：
  `meta.json`（expr/sign/freq/unit/source/IC）+ `values.h5`（原始 float32）。
  **双写 `values_q.h5`**（uint8 截面分位快查副本）：省 3.99× 空间，**秩类用法（IC/分层/多空/正交诊断）快 14.4×**。
  ⚠ 需要原值的用法（中性化/回归/剥风格/合成）**必须读 `values.h5`**。
- `engine/qa_bench_cw.py` / `qa_ex_dedup.py` / `qa_pool_tag.py` — 三个机制自检脚本。

**分池因子库与跨池视图**
- `docs/factor_library_{300,500,1000}.md` — 分池因子库（池隔离，与全A 库互不读写）。
- `docs/factor_library_crosspool.md` — 跨池视图（一个因子在哪些池达标）。
- `docs/factor_pool_selected.md` — **L2 跨池审查 + L3 精选池**（准入档 A → 相关去重后入选）。
- `docs/loop_journal_{300,500,1000}.md` — 分池 journal（`--mine_pool` 池隔离的必然产物）。

**因子值工具链（`ai_test/`，按 `.gitignore` 本地专用）**
- `ai_test/build_facs.py --only-new` / `--force` — **增量落地**（见 Changed）。
- `ai_test/cross_pool_review.py` — L2 跨池 + L3 精选池报告。
- `ai_test/fix_csv_schema.py` — CSV 混合宽度体检（治 §8.30 的"加列导致下游全崩"）。
- `ai_test/backfill_library_pool.py` — 池因子库补录（治"只做插入不做创建"）。

**B角 机制（`engine/loop_critic.py`）**
- **规则动作登记表 `RULE_NAMES`** — 给每条规则动作稳定 ID（`r1_leaf_conc` … `r7_zero_pass`）。
- **动作饱和检测** — 连续 `SAT_N=2` 代施加同一动作 ⇒ 判饱和 ⇒ **冷却 `COOL_N=3` 代**。
- **LLM 否决通道** — `parse_veto()` 解析 LLM 末行的 `否决: <ID列表或 无>`；
  **连续 `LLM_MUTE_N=2` 次否决 ⇒ 写入哨兵 `MUTE` = 永久停用**（用户要求"让它永久闭嘴"）。
- **诊断新传感量** — `fail_calmar_neg`（`calmar<=0`，**真·信号弱，不随配置漂移**）·
  `fail_pool_calmar`（**池口径** = 池内模式的真实卡点）· `gate_min_calmar` / `gate_min_pool_calmar`（门槛回显对账）。

**引擎（`engine/loop_engine.py`）**
- `_gate_of(args)` — **生效门槛单一事实源**（诊断与判定同源，防漂移）。
- `_pool_best(pool_rows)` — 池口径聚合 `{expr: 最好池 calmar}`，并随 state 存 `last_pool_map`。

**回归测试**
- `ai_test/_test_critic_sensor.py` — **32 项**（门槛对账 / 饱和 / 否决 / 永久哨兵 / parse_veto 容错）。
- `ai_test/_test_build_facs_merge.py` — **11 项**（增量合并不得清空已有数据）。

**文档**
- `change_log.md`（本文件，根目录）。
- `docs/loop_todo.md` — **跨会话任务真相源**：待办表 / 判断分支 / 进度日志 / 已知误报。

### Changed（变更）

- **收尾① 落地改增量**：`run_tracks.py` 收尾① → `build_facs.py --only-new`。
  **`build_facs.py` 在载面板之前三档分流**：`full`（值缺 ⇒ 求值+回测+剥风格）/
  `quant_only`（值在、`values_q.h5` 缺 ⇒ **只补副本，不载面板不重算**）/ `skipped`（都在 ⇒ 跳过）。
  ⇒ **无新因子时连面板都不载**。实测收尾①②合计 **23 min → 4.1 s（提速 ~340×）**；缺 3 个副本 ⇒ 5.9 s。
- `loop_critic.diagnose()` 新增 `gate=` / `pool_map=` 参数；`fail_calmar` 改用**生效的** `min_calmar`
  （原**硬编码 0.5 + 全A 口径**）。
- `loop_critic.ai_review()` 返回值 **`str` → `dict`**（`{'status','veto','text'}`）；引擎把 `veto`
  写进 `next_cfg['_veto']`（键 = **目标代** `gen+1`）⇒ 下一代 `suggest()` **真的跳过**被否决的动作。
- `ai_review()` 的 system prompt 新增第 (4) 项要求 + **末行格式约定**，并把「本代实际施加的动作 ID」
  与「已永久关闭的动作」一并喂给 LLM（不给 ID 它无从否决；不给已关闭名单它会年年否决同一件事）。
- `run_tracks.py` 的 **GUARD 判据重写**：原用 `fail_calmar > 0.9`（该量当时恒为 1.000）
  ⇒ 改为**直接核验命令里有没有那组 flag**（`--pool_obs` / `--min_pool_calmar` / `--pool_gate_or_all`）。
- `--pools=300,500,1000` / `--pool_obs` / `--min_pool_calmar` / `--pool_gate_or_all` 的**池门槛 OR 语义**落地（§8.26）：
  多门 AND 会让入库率**联合归零**，改「任一池达标即达标」。
- `--dup_ex_corr` **收益流去重**（§8.34）：按候选与历代入库因子的**收益流**相关，而非表达式/因子值。
- `--min_strip_calmar` **剥风格后超额**入库判据（§8.14）。
- 组合构建约束（`combo_constrain.py` 方向）：对**真实指数** 000300/000905/000852 计算组合 Calmar。

### Fixed（修复）

- **`fail_calmar` 传感器失真**（§1.1 问题①②）：硬编码 0.5 + 全A 口径 ⇒ 池内模式下**测的不是真正卡住候选的那道门**。
  实测 `pool=1000 gen1` 报 `fail_calmar=1.000`，而同代**确有 2 个候选 Calmar 0.661/0.561 入库**（指标自相矛盾）。
- **规则5 退化成固定动作**（§1.1 问题①）：`fail_calmar` 触发条件 **96/96 代 = 100% 成立**
  ⇒ `depth` 被**永久**推到 `[3,4,4]`、`mix` 交叉撞上限 0.4。
- **LLM 审查只写日志、从不参与决策**（§1.1 问题③）：`ai_review()` 返回值**只用于打印**
  ⇒ **85/98 次**独立反驳全部被浪费，且方向与规则**相反**（LLM 每代建议降深度，B角 每代升深度）。
- **GUARD 必然误报**（§1.1 问题④）：判据用了失真的 `fail_calmar` ⇒ 轨道跑完时报了一次
  「全A 门槛在砍全部门」，而**参数其实传全了**。★ 用不可靠的量当报警判据 ⇒ 必然误报，
  "狼来了"会让真警报被忽略（比不报警更糟）。
- **`_lib_sync` 只做插入不做创建**：池因子库文件不存在时**静默**不建 ⇒ 已修（gen4+ 生效）。
- **`bank` 被截断丢失历史**（§8.17/§8.18）：去掉 `bank` 上限 + 补回丢失因子 + 一致性守卫。
- **候选池萎缩**：`300 gen11` 候选数骤降至 **13**（其它代 29~30）—— 冻结骨架 + 失败库累积到 1582 条所致，已记录待观察。

### Deprecated / Removed

- `docs/loop_archive.csv` 等逐代 CSV 继续按 `.gitignore` 排除（运行产物，非 git 跟踪）。
- `docs/history/cleanup_2026091{4}_*` — 2026-09-14 的归档清理清单（保留落档）。

### Notes（本次会话内验证，未入库的证据）

- 端到端验证：50 池（**冒烟专用池**）全新跑 **3 代**，验证门槛对账 / 传感器"活"了
  （`fail_calmar` 0.900→0.700、`fail_pool_calmar` 1.000→0.900）/ LLM 否决生效 / **连续 2 次否决 ⇒ 永久闭嘴**。
  证据：`ai_test/_smoke50_g{1,2,3}.log` + `docs/loop_journal_50.md`。
- 收尾链手跑：`build_facs --only-new` 2.0s + `cross_pool_review` 2.1s ✓
- ⚠ **已知遗留限制**：**参数棘轮（ratchet）—— 新机制只"停手"不"回退"**。`depth` 被推到 `[3,4,5]` 后，
  即使 LLM 永久否决该动作，`depth` **仍停在 `[3,4,5]`**（而 LLM 建议 `[2,3]`）。是否要做"永久闭嘴时回退基线"**待拍板**。

---

## [0.4] — 2026-09-12

> 主题：**三池并行挖掘 + 池内判据 + 整代末尾崩溃修复**（`roadmap §8.19 ~ §8.23`）
> tag：`v0.4`（提交 `6c60c7f`）

### Added
- **`engine/loop_pools.py`** — PIT 指数成分**单一事实源**：`pool_path/load_pool/pool_union/pool_mask/pool_gate_ok`。
  成分数据 `E:\rq\constituents\index\`（000300 / 000905 / 000852 / 000016）。
- **`engine/loop_metrics.py`** — `neutral_rank()`（风格中性化，与 `standard_test` 【6】同口径）。
- **`standard/pool_tags.py` + `standard/obs_analysis.py`** — 池标签宽表（长表→宽表，喂 PG）+ 观测分析。
- **`engine/qa_mine_pool.py`** — `--mine_pool` 校验（路径派生 / 幂等 / 未知池报错 / 参数注册；
  `--heavy` 含 L1 池并集与 PIT 掩码当期成分数，实测 300 池 925 列 / 中位 299 只）。
  另含"全新轨迹保存状态"的复现路径（用一次性池 50 冒烟）。
- **`docs/loop_todo.md`** — 跨会话任务真相源（轮询者纪律 / 占用锁 / 待办表 / 判断分支 / 进度日志）。

### Changed
- **`--mine_pool=all|300|500`** — 全A / 沪深300 / 中证500 **三条完全独立**轨迹。状态与输出全部按池加后缀
  （幂等，从原始路径快照派生）；**L1 子面板列 = 该池并集**；**L1 的 IC 按 PIT 池掩码算 = 池内 IC**
  （这是"池内挖掘"起作用的核心）。
  依据（§8.13）：全A 含微盘 ⇒ 低流动性溢价让风格因子轻松过关（30/30 的 `lnamt`/`lntr` 全负、剥成交额后仅 3/30 为正），池内不存在该溢价。
- **`--strip_style` / `--min_strip_calmar`** — 入库剥风格判据，口径与 `standard_test`【6】逐位一致
  （rank→逐日截面 OLS 残差→rank→重跑回测），落 `loop_strip_style*.csv`。
- **`--pool_obs` / `--pools` / `--min_pool_calmar`** — L2 在指数成分内重跑，逐池指标落 `loop_pool_obs*.csv`（长表），供入库打池标签（§8.15）。
- **`engine/loop_watch.py`** — `--pool=300|500`：journal / 日志名加池后缀（否则三条轨迹**同名碰撞**）、
  启动引擎透传 `--mine_pool`、`is_engine_running/already_running` 按池区分（否则三条 watch 互相误判）。
- **`.gitignore`** — 数据区改**通配**（`--mine_pool` 会产出带池后缀的变体 `loop_archive_300.csv` 等，
  原精确名匹配不到 ⇒ 会变成"未跟踪"甚至被误提交）；新增 `QuantaAlpha-main/`（外部只读参考，不入库）。

### Fixed
- **全新轨迹（首次运行、无既有 state）崩在整代最后一行**的 `UnboundLocalError`（§8.23）。
  根因：`open(STATE,'wb')` 本身会创建文件 ⇒ 其后 `os.path.exists(STATE)` 恒真，
  而 `st` 只在"载入上一代"处绑定。**破坏**：30 分钟计算白做 + 旧 state 被截断成 0 字节。
  **修法**：① `n_tested` 基准提前到载入处取；② 保存改**原子写**（tmp + `os.replace`）根治半成品状态。

### Docs
- `roadmap §8.19~§8.23`：三池并行提案的离线验证（**「剥风格进 L1 排序」被证伪**）、`--mine_pool` 落地、
  QuantaAlpha 精髓清单、目标函数现状核实、事故复盘。

---

## [0.3] — 2026-09-12

> tag：`v0.3`（提交 `41dbb9d`）

### Added / Changed
- **`new_n` 判定落地** — 形状量改用**风格中性后**收益（判定 ✅）。
- **`--reuse_v`** — 提速 **35%**（含相位插桩与对拍验证）。
- **`--shape_neutral`** — 形状量用风格中性收益的开关。

---

## [0.2.1] — 2026-09-12

> tag：`v0.2.1`（提交 `3fb5f28`）

### Added
- **`shape_pos_n`** — 记录"风格中性后"的**第二套**形状量（批2 候选，**默认仅观测**）。

---

## [0.2] — 2026-09-12

> tag：`v0.2`（提交 `641fe33`）

### Added
- **`--style_obs`** — 风格暴露观测（默认关闭）。

### Docs
- 批1 排序分的**配对实测结论**（`standard/style_paired_analysis.py` → `docs/loop_style_paired.md`）。

### Chore
- 风格观测 / 配对分析脚本移入 `standard/` 纳入跟踪；README 目录结构补 `standard/`。

---

## [0.1] — 2026-09-11

> tag：`v0.1`（提交 `6ed6b00`；主体在 `4ebf734`）

### Added
- **`engine/loop_metrics.py`** — L1 指标层。
- **成本档单一事实源**。
- **`--min_mono` / `--score_mode`**（默认关闭）+ `software_framework.md`。

### Docs
- README 新增**「版本与回退」约定**（每版本 = commit + annotated tag，说明记四项）。

---

## [0.0] — 2026-09-10

> tag：`v0.0`（提交 `e582921`）— **代码基线（改造之前）**

### Baseline
- gen51 **双闸门治同代近重复**；watcher 目标 50 → 70。
- 此前无版本号的历史提交（对应 `v0.0` 之前）：
  `a309a14` 工作区首次提交（Loop 引擎：五维演化 / FSA / 失败库 / gen13 修复）·
  `007c9d7` LLM 双子代理落地 + 五维配比运行态护栏 ·
  `dfebf3e` gen1-22 收官 + 双子/接力/复盘，`factor_library` 收在 9 因子 ·
  `cf4e6bc` **扩叶子池 v3**（`mf16` 资金流 + BARRA11 风格 + 财报 PIT8 共 **54 叶**；`loop_fields.py` 单一事实源）·
  `b5b3894` gen23 新叶首代完成 + watcher 无人值守接力 ·
  `6f4939e` 文档归档整理 + 入库自动同步（`_lib_sync`）·
  `ca09bca`/`807aea1`/`ee10ea0` QuantaAlpha 结构族机制（冗余检测 + 正交换血）。

---

<!--
模板（发布时复制）：
## [X.Y.Z] — YYYY-MM-DD
> 主题：一句话
### Added
- 
### Changed
- 
### Fixed
- 
### Removed
- 
-->
