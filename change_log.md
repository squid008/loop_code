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

## [0.6.1] — 2026-09-14

> **PATCH** —— 全库日频实测后，**更正 v0.6.0 里的一处过度陈述** + 新增标定工具

### Fixed（文档更正）
- 🔴 **「期频回撤被**系统性**低估 ~3.6pp」用词错了** —— 那是 `F10_1000` 的**极端个案**，
  **不是普遍规律**。全库 50 个因子实测（`tools/calib_daily_threshold.py`）：

  | 口径 | 折算比 `strip_calmar_d / strip_calmar` |
  |---|---|
  | 全部（N=50）| 中位 **0.977** · 四分位 0.913~0.991 |
  | **仅正 calmar（A/B 档，N=31）** | 中位 **0.928** · 四分位 0.891~0.974 · 区间 **0.741~0.992** |

  ⇒ **回撤平均只放大 ~1.08×，不是 1.46×** ✗
  ⇒ **§1.19 的正确结论**：✓ **方向对**（日频更准，值得采用）；✗ **幅度逐因子差异极大**（0.74~0.99）
  ⇒ ★ **日频口径的价值在于「揪出个别高回撤因子」，不是「整体平移」**。

### Added
- `tools/calib_daily_threshold.py` —— 期频 vs 日频对照 + **档位阈值标定**（3 段输出）：
  ① 折算比分布（**只对正 calmar 统计**，因为负超额因子折比 ≈1 无信息量）
  ② 逐因子对照（A/B 档）
  ③ ★★ **阈值敏感度表** ⇒ 让"新阈值定多严"看着数字决定

### Notes（★ 两个新结论）

**① §1.19-③ 的净收益不是「改阈值」，而是「换更准的口径」**

| **日频**阈值 | A 档 | B 档 | 相对"期频 0.30"的保留率 |
|---|---|---|---|
| 0.15 | 21 | 10 | 124% |
| 0.20 | 20 | 11 | 118% |
| **0.25** | **17** | 14 | **100%** ← 与现状**完全相同** |
| 0.30 | 15 | 16 | 88% |

（现状 = **期频** 0.30 ⇒ A 档 **17** 个）
⇒ 因为折算比中位 0.928（不是 0.6~0.7），**日频阈值 0.28~0.30 就与现状等效** ✓

**② ★ 新洞察：A 档判据应加「日频回撤上限」**

有一批因子 **calmar > 0（现行判据判"可用"）但日频回撤高达 −21%~−35%**：
`F03_1000` **−35.3%** · `F11` **−23.1%** · `F40` **−21.2%** · `F04` −17.8% · `F01` −16.3%
⇒ **建议加** `strip_dd_d > -0.20`；对**真中性增强（B 路线）**尤其重要（回撤是产品端硬约束）。
**阈值定多少需用户拍板**（直接决定可用因子数）。

---

## [0.6.0] — 2026-09-14

> 主题：**新增「日频 mark-to-market」风险口径**（治 `loop_todo §1.19`）
> —— 用户拍板「**2 选 ③：重标档位阈值到日频**」
> ⚠ 同时记录用户的两条决策：**§1.18 选 B**（池内判据加 Calmar 下限 + 重算历史标签）·
> **§1.20 铁律**（不要用放宽门槛凑数量）

### Added
- `engine/factor_miner.evaluate_real(..., **with_daily=False**)` —— 新增**日频 mark-to-market**
  风险指标 `dd_d` / `calmar_d` / `sharpe_d`（`with_ex=True` 时另给 `ex_d` 日度超额序列）。
  **默认 False ⇒ 返回结构与行为完全不变**（老调用方零影响）。

  **为什么需要**（§1.19）：现状 `nav=(1+ex).cumprod()` 而 `ex` 是**每换仓期**一条
  ⇒ 净值**只在期末打点** ⇒ **漏掉持有期内的日内回撤** ⇒ 回撤**系统性低估 ~3.6pp**、Calmar **高估 ~1.4×**。

  ★★★ **实现要点（两个坑，都写进 docstring 了）**：
  1. **不要用 `set_fwd(1)` 得日频** —— 那会变成「**每天调仓**」（换手 ×5、成本 ×5）= **另一个策略** ✗
     正确做法：**保持 `FWD` 调仓，在持有期内逐日 mark**（复用同一个 `keep_top`/`keep_all` 持仓，
     **不重新选股**）⇒ 每因子只多 **~4 秒** ✓
  2. **必须把每期的日超额「锚定」到期频值** —— 即等比缩放使 `prod(1+seg) == 1+ex_e`。
     否则两条净值路径**不是子采样关系**（逐日算术和 ≠ 期收益的复利）⇒ `dd` 不可比、
     `calmar_d ≠ ann_ex/|dd_d|` ✗
     **锚定后**：期频净值 = 日频净值在每个期末的取值 ⇒ **`dd_d <= dd_e` 严格成立**（数学恒等式）
     ⇒ 可被单元测试**钉死** ✓

- `tools/_test_daily_dd.py` —— **15 项**回归测试。核心是三条**不变量**（不是"和某个数字对得上"）：
  · `dd_d <= dd_e`（子采样只能看到更少的极值）✓
  · `calmar_d == ann_ex/|dd_d|` 严格成立（只有回撤换了口径）✓
  · **逐点抽查 418/418 个期频点与日频曲线重合**（锚定的直接验证）✓
  另含"默认 `with_daily` 不产生任何新键 / `dd` 逐位相同"的行为兼容性检查 ✓

- `tools/build_facs.py` 新增**日频列**：`dd_d` / `calmar_d` / `strip_dd_d` / `strip_calmar_d` /
  `strip_sharpe_d`（`docs/loop_strip_style_bank.csv` 列定义同步更新）。
  ⚠ 加列**不会**让历史行错位（`_merge_csv` 用 `DictWriter` 按 key 写 + `setdefault` 补空；
  §8.30 那个坑只发生在"裸行写入"的场景）。

### Notes（与外部独立审查的对拍）

| 指标 | 引擎（期频）| 引擎（日频）| 外部审查（日频）|
|---|---|---|---|
| `F10_1000` dd | −7.77% | **−10.26%** | −11.42% |
| `F10_1000` calmar | 0.8911 | **0.6748** | 0.627 |
| `F10_1000` sharpe | 1.0592 | 1.1190 | 1.139 |

⇒ **方向与量级完全一致**（回撤放大 **1.32×**、Calmar 高估 ~1.3×），但 dd 有 **~1.16pp** 差异
⇒ 差异应来自**基准腿口径 / 停牌处理**的细节（外部用 `standard_test.py`，参数与 `evaluate_real` 未必全同）
⇒ **不影响结论**（"期频系统性低估回撤"成立）✓ 但**报告时要注明口径**。

### Notes（待办，已拍板）

- **§1.18 选 B**：`loop_engine.py` 的 `_okp` 加 Calmar 下限 + `loop_pools.TAG_POOL_FLOOR_CAL`
  + **重算历史标签**（数据都在 `loop_pool_obs_*.csv` ⇒ 离线 re-derive，不必重跑引擎）
- **§1.19 选 ③**：本版已产出日频列 ⇒ **下一步按日频分布重标** `TAG_STRIP_CAL_MIN` / `TAG_CAL_MIN`
- **§1.20 铁律**：**不要用放宽门槛凑因子数量**（瓶颈是**信号源多样性**，不是条数）

---

## [0.5.5] — 2026-09-14

> **PATCH / 纯文档** —— 外部独立审查触发，落两条**口径层面的结构性问题**（待拍板）+ 重跑结果

### Notes（★ 外部 AI 独立审查 `F10_1000` 的结果：7 项指标 8/8 全部复现 ✓）

独立审查确认**引擎自报值可信**，但指出两个问题 —— **我复核后两条都成立**：

🔴 **新增 `loop_todo §1.18`：`all3` 标签的判据比入库门槛松得多**
```python
engine/loop_engine.py:2001-2006
_okp = {q['pool']: (ann_ex > TAG_POOL_FLOOR)}      # = 0.0  ← 池内**只要超额>0**
_oka = (ann_ex > 0 and calmar >= TAG_CAL_MIN)      # = 0.30 ← 全A **要卡 calmar**
```
**判据不对称** ⇒ `derive_tag` 的 `all3`（"全A 且所有池都通过 = **真 alpha**"）
实际只要求"池内超额 > 0"，**完全不卡 Calmar** ✗

实测 `F10_1000`：300 池 calmar **0.0589**、500 池 **0.0233**（**均 < `--min_pool_calmar=0.15`**，
入库门槛判**不通过**），但标签判据判通过 ⇒ **库文档标成 `all3`**；
而独立审查的日频复核：300 池**日频回撤 −41.28%**、日频 Calmar 0.06、500 池超额仅 +0.41%
⇒ **大中盘段无效** ⇒ 下游按 `all3` 筛"真 alpha"会**误选**。

🔴 **新增 `loop_todo §1.19`：引擎侧风险指标是「期频打点」口径**
`factor_miner.py: FWD=5`（**无人调用 `set_fwd`** ⇒ 全局周频）+ `nav=(1+ex).cumprod()`
只在**每期期末**打点 ⇒ **回撤系统性低估 ~3.6pp、Calmar 高估 ~1.4×**。
实测折算比（F10）：期频 0.891 → 日频 **0.627**；剥后 0.587 → **0.366** ⇒ **日频 ≈ 0.6~0.7 × 期频**。
**影响面**（系统性）：L2 `calmar/dd` · `loop_strip_style_bank.csv` · `loop_pool_obs_*.csv` ·
journal `fail_calmar` **全是期频** ⇒ 档位阈值 `TAG_STRIP_CAL_MIN=0.30` 与池门槛 `0.15` **都偏松**。
⇒ ★★ **挖掘侧（期频）与组合侧（`combo_constrain` 逐日净值 = 日频）Calmar 不可直接比** ——
这**解释了 §1.4 里"挖掘侧 0.5~0.9 vs 组合侧 S0 2.515"的量级差异**。
**日频能力已现成**（`standard/standard_test.py --freq=1`）⇒ **不必改引擎**。

### Notes（重跑 1000 池 gen7/8/9 完成）

- **gen7** 56.1min 入库 1 · **gen8** 64.6min +0 · **gen9** 55.9min +0 ⇒ **bank 3 → 4**
- ★★ **收尾① 从 23.7 min 降到 2 秒** —— **`--only-new` 终于生效（提速 ~700×）**
  （上次没生效：那个 `run_tracks.py` 进程的内存里是改动前的代码）
- ★★ **§1.17 端到端验证通过**：`gen>=7` 入库的 1 个（`F10_1000`）**是 A 档**，**C 档零新增**
  ⇒ 对比修复前 8 代出 6 个 C 档（60%）· 修复后 **0%** ✓
- 全库 56 因子：**A17 B14 C25** · L3 精选 **7 个**
- ⚠ **产出率极低**（3 代只出 1 个）⇒ 印证 §1.4 的警告「B 真中性路线要 20~50 个因子，按此速度差很远」；
  且**候选数持续萎缩**（L2 `30 → 19 → 15`，冻结骨架 4 个、失败库 384 条）

---

## [0.5.4] — 2026-09-14

> **PATCH**（新增工具，不改引擎行为）—— 补上 §1.17 验证清单第 ④ 条：**防回归断言**

### Added
- `tools/pool_grade_summary.py` — **各池入库因子的剥风格档位汇总 + 防回归告警**。
  **动机**：§1.17 那个 bug 能潜伏一天多，唯一原因是**没人在看"入库因子的档位分布"**
  （要人工偶然跑 `build_facs.py` 才碰得到）⇒ 做成**随时可跑的一行命令**。
  - `--since-gen=N` —— 只看第 N 代及以后入库的（**验证修复**用）
  - `--warn-c=0.30` —— C 档占比超阈即报 `[!]` 并**返回退出码 1**（便于将来接进收尾做硬断言）
  - 保留**历史记录**（不隐藏已剔除的 C 档）—— 审计需要看到"曾经混进来过"

### ★★ 端到端验证通过（§1.17 修复的实证）

**只数 `gen>=7`（即修复后）入库的**：

```
## pool=1000   （1 个）
  [A]   F10_1000     原Calmar=0.89107  剥后Calmar=0.5867438   cs_demean(mul(add(turn_ratio, ts_mean60(barr
  档位: A×1   ⇒ C 档占比 **0%**
  [OK] C 档占比未超阈（0% ≤ 30%）
```

对比：**全部 10 个（含修复前的 6 个 C 档，历史保留）** ⇒ `A×2, B×2, C×6` ⇒ **C 占比 60%** `[!]`

⇒ **修复前 8 代出 6 个 C 档（60%）· 修复后第 7 代出 A 档（0%）** ✓✓

★ 附带收获：`F10_1000` 的**剥后 Calmar = 0.587**，是 1000 池目前**剥风格后最好的因子**
（超过 `F07_1000` 的 0.519），原口径 Calmar 0.891、IC +0.0469。

---

## [0.5.3] — 2026-09-14

> 主题：**修 `--pool_gate_or_all` 静默绕过两道硬门槛的 bug**（`loop_todo §1.17`）
> + 用户拍板**产品定位 = B. 真中性增强**（`loop_todo §1.4`）

### Fixed
- 🔴 **`--pool_gate_or_all` 的快照点取错 ⇒ 「剥风格门槛」与「分段独立验证」被静默绕过**
  （`engine/loop_engine.py`）。原实现：
  ```python
  _ok_prev = ok                 # 快照取在 _ok_q **之前**
  ok = ok and _ok_q
  ok = ok and seg_ok            # 分段独立验证
  ok = ok and strip_ok          # 剥风格门槛
  ...
  elif _pool_gate_or_all:
      ok = _ok_prev and (_ok_q or _pok)   # ★ 用旧快照**整个重建** ⇒ seg/strip 一起被撤掉
  ```
  注释本意是「只撤掉 `_ok_q`」（否则 OR 退化成 AND），但快照取早了。
  ⇒ **`--pool_gate_or_all` 一旦开启（§8.26，2026-09-13 起），这两道硬门槛完全失效且无告警**。
  **实测后果**：池后缀 13 个入库因子里 **C 档（纯风格）8 个 = 62%，`strip_calmar` 全为负**，
  本该被 `--min_strip_calmar=0.15` 全部拦下 ⇒ 也是 `§1.9`「库约一半是纯风格」的真因。
  **修法**：把判定组合提取为**纯函数** `loop_engine.combine_ok(ok_base, ok_q, ok_pool, ok_hard,
  pool_gate_on, or_all)` —— **OR 只作用于「全A 口径 vs 池内口径」这个二选一**；
  `seg_ok` / `strip_ok` 另存进 `_ok_hard`，**最后统一 AND 回来，不参与 OR**。

### Added
- `tools/_test_ok_gate.py` — **22 项**真值表回归测试。核心用例：
  `ok_q=False, ok_pool=True, ok_hard=False`（池内达标但剥风格失败）⇒ **必须不通过**
  （旧实现给"通过" ⇒ 直接复现漏拦）；并含**新旧公式同输入对比**，证明本次修复确实改变行为。
- `tools/prune_style_only.py` — 从某个池的 state 剔除**纯风格（C 档）**因子。
  为什么必须剔：`--dup_ex_corr`/`--decorr` 的对照集是**各自轨道的 bank** ⇒ 这些因子会**挡住新因子**
  （自我封锁）；且合成/组合会**自动带上**它们，污染 S2（真中性）口径。
  安全设计沿用 `cleanup_repo.py` 风格：**默认 DRY-RUN** + **先备份** + **原子写** + **只按判据删**
  （对不上的 expr **一律保留**，宁可留不误删）。**只改 state**；`docs/factor_library_*.md` 与 `facs/`
  保留历史记录（可追溯"这些因子确实被挖出来过，只是当时门槛没生效"）。

### Changed
- **1000 池 state：`bank` 9 → 3**（剔除 6 个纯风格因子）。保留的 3 个正是"剥风格后仍有效"的：
  `F01_1000`(B) · `F03_1000`(B) · `F07_1000`(A)。
  备份 `ai_test/_state_prune_1000_20260914_163627.pkl`（可人工恢复）。
- `docs/loop_todo.md §1.4` 记录用户拍板：**产品走「B. 真中性增强」**（市值+行业中性，S2 口径）；
  §1.2 / §1.8 的**两条错误结论已更正**（见下）。

### Removed
- 3 个兼容垫片 `ai_test/{run_tracks,build_facs,cross_pool_review}.py`（**轨道已结束**）。
  ★ **实测有效**：本次收尾①② 都走的是 `ai_test/` 路径，没有垫片就会直接失败 ✓

### Notes
- **两条被更正的结论**（都是此前写错的，已在 `loop_todo` 与 `MEMORY.md` 标注）：
  ① 「组合侧支持 1000 ≫ 500 ≫ 300」**不成立** —— `combo_constrain.py --pool=X` **只改选股范围
     （成分股掩码），不改因子集**（`--fac` 默认是全A 41 因子的合成）⇒ 那是"同一组合换选股范围"，
     **不是"各池自己的因子在自己池里的表现"**。正确数字：全A **2.515/+14.46%** > 1000 内 1.192 > 500 内 0.522 > 300 内 0.046。
  ② 「1000 池效率是全A 的 3.6 倍」**不成立** —— 那是未剥风格口径；按「剥风格后仍有效」重算为
     全A 0.33、1000 0.60、500 0.18、**300 = 0** ⇒ **差距缩到 1.8 倍**。
- **本次收尾① 未用上 v0.5.0 的 `--only-new` 提速**（花了 23.7 min）：
  那个 `run_tracks.py` 进程 13:26 启动，**内存里是改动前的代码** ⇒ 仍走全量。下次跑轨道即生效。

---

## [0.5.2] — 2026-09-14

> 主题：**建 `tools/`，把生产管线从 `ai_test/` 迁出并纳入 git**（治 `loop_todo §1.16`）
> 动机：`ai_test/` 被 `.gitignore` 整个忽略，但收尾管线住在里面
> ⇒ **`git checkout v0.x` 回退代码时整条收尾管线会消失**（回退点不完整）。

### Added
- **`tools/`（新目录，纳入 git）— 23 个生产管线/工具脚本**。判据（三层，不靠"被任何文档提到"）：
  | 层 | 判据 | 例 |
  |---|---|---|
  | **A** | 被 `engine/`、`standard/` 的 **.py 代码**引用 | `build_crosspool_view.py` · `add_quant_copy.py` · `bench_quant_read.py` · `backfill_bank_ex.py` · `analyze_diversity.py` · `scan_non_gbk.py` · `qa_loop_pools.py` · `check_strip_style_pool.py` · `probe_models.py` · `l1_shape_calib.py` |
  | **B** | **收尾/轨道管线成员** | `run_tracks.py` · `build_facs.py` · `cross_pool_review.py` · `critic_sensor_report.py` · `fix_csv_schema.py` · `backfill_library_pool.py` · `tracks_status.py` · `journal_view.py` |
  | **C** | 被 `README` 引用 / 回归测试 / 常用质检 | `calib_gates.py` · `_test_critic_sensor.py` · `_test_build_facs_merge.py` · `_check_quotes.py` · `_doc_outline.py` |
  > ⚠ **不要**按"被任何文档提到"扫 —— 那样会得到 **106 个**（含 `round5_fund.py` / `verify_*.py` 等
  > **roadmap 历史叙事里的"当时用过的一次性脚本"**）。判据必须是「**被代码引用 或 属当前管线**」。
- **3 个兼容垫片** `ai_test/{run_tracks,build_facs,cross_pool_review}.py` —— 转发到 `tools/`（`runpy.run_path`）。
  存在的唯一原因：**迁移时轨道正在跑**（`run_tracks.py` 用硬编码 `ai_test/build_facs.py` 调收尾①②）。
  **轨道结束后可 `git rm`。**

### Changed
- **114 处引用** `ai_test/xxx.py` → `tools/xxx.py`：`engine/*.py`(17) · `tools/*.py`(自引用) ·
  `README.md` · `docs/loop_todo.md`(37) · `docs/factor_library*.md` · `docs/factor_pool_selected.md`。
  **不改**：`docs/factor_roadmap.md`（**历史档案** —— 改写历史路径 = 篡改档案，改为顶部加**导航注记**）·
  `docs/history/**`（归档只读）· `docs/loop_journal*.md`（运行日志是既成事实，不可回改）。
- `.gitignore`：`ai_test/` → **`ai_test/*` + 3 个 `!` 例外** + 补 `docs/history/**/ai_test/`。
- `tools/run_tracks.py` 收尾①②改调 `tools/build_facs.py` / `tools/cross_pool_review.py`
  （**新跑的用新路径**；垫片只服务正在跑的那一次）。
- `.codebuddy/`、`ai_test/` 的定位在 README「目录结构」里改写清楚（工具入 git、产物继续忽略）。

### Fixed
- ★★ **`HERE` 产物路径会被劈成两半**：`run_tracks.py` 的 `_tracks`、`critic_sensor_report.py` 读的 `_tracks`、
  `build_facs.py` 的 `_facs_built.csv` —— 若沿用 `HERE`，迁走后新进程会写 `tools/_tracks/`，
  而**正在跑的进程仍在写 `ai_test/_tracks/`** ⇒ 日志/清单分裂。
  **修法**：显式 `os.path.join(ROOT, 'ai_test', ...)`（**代码进 tools/，产物仍留 ai_test/**）。
- ★ **gitignore 回归（我引入的）**：原 `ai_test/`（**无斜杠 ⇒ 匹配任意层级**）改成 `ai_test/*`
  （**带斜杠 ⇒ 锚定仓库根**）后，**误放开** `docs/history/**/ai_test/` 下 **101 个归档文件**
  （`001311` 下 88 · `001515` 下 13）⇒ 补 `docs/history/**/ai_test/`。
- ★ **垫片不能写 stderr**：初版往 stderr 写提示 ⇒ PowerShell 报 `NativeCommandError`，
  且收尾段会检查子进程 stderr 非空并记 `[stderr]` ⇒ 改 **stdout**。

### Notes
- **迁移脚本**（可复跑，带 `--dry-run`）：`ai_test/_migrate_to_tools.py` / `_fix_refs_tools.py` / `_scan_refs.py`
  （留在草稿区不入 git —— 一次性任务，但保留以便复核与回滚）。
- 验证：26 个文件编译通过 · 引号检查全绿 · 两处垫片转发实测（退出码 0）· 回归测试 11/11 + 32/32 ·
  `git status` 仅显示 `tools/` + 3 垫片 · **引擎全程未受影响**（迁移前后 PID 3460/2540 均在跑 1000 池 gen4）。

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
