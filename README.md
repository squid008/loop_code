# loop_code — Loop 式因子自动挖掘引擎

> **当前版本 `v0.6.0`**（2026-09-14）— 池化挖掘闭环 + B角「诊断→决策」链条修复 + 收尾提速 + 管线迁入 `tools/` + **修 `--pool_gate_or_all` 静默绕过硬门槛**
> · 变更全文见 **[`change_log.md`](change_log.md)** · 研发档案见 `docs/factor_roadmap.md`
> · 版本历史与回退见下方「[版本与回退](#版本与回退2026-09-11-起)」

从 `D:\rqalpha_demo` 整理迁移（2026-09-08），原目录保留备份。机器外部数据依赖：米筐 bundle `E:\rq`（本地数据盘）。

## 目录结构
- `engine/` — **Loop 挖掘引擎（可独立运行，相互引用均用相对自身路径）**
  - `loop_engine.py` 主引擎（五维演化 + 跨量纲审查 + 失败模式库 + FSA 冻结 + 结构族/叶子代理闸门 + 同代近重复去重 + 两级筛选 + 费后验证）
  - `loop_critic.py` B角诊断（每代自动写 gen 建议进 journal）+ `loop_llm.py` LLM 双子（A角语义引导 / B角候选审查 / 代末 AI 审查）
  - `loop_watch.py` 常驻接力进程（每 5min 轮询，空闲自动启下一代，支持无人值守多代跑）
  - `loop_status.py` 进度/进程/档案查询
  - `loop_fields.py` **叶子字段单一事实源**（基础7+派生12+资金流16+BARRA11+财报8=54；新增字段族只改这一处）
  - `factor_miner.py` 因子挖掘基础框架（panel 加载/预筛选/两段式验证）
  - `fastops.py` L1 向量化快速算子
  - `build_mf_leaves.py` / `build_barra.py` / `build_fa_pit.py` 扩展数据源叶子构建（资金流16列入 panel / barra.h5 / fa_pit.h5，幂等可重建）
  - `panel.h5` / `universe.h5` / `barra.h5` / `fa_pit.h5` L1 筛选用数据（由 `build_*.py` 从 E:\rq 重建）
  - `loop_state.pkl` 引擎滚动状态（运行中会变）
  - `_check_*.py` 机制自检（dry-run 零误杀验证）
- `tools/` — **生产管线与工具（纳入 git）**。2026-09-14（v0.5.2）从 `ai_test/` 迁出：
  - `run_tracks.py` 多池轨道驱动（生产唯一入口）· `build_facs.py` 收尾① 因子值落地（`--only-new` 增量）
  - `cross_pool_review.py` 收尾② L2 跨池审查 + L3 精选池 · `critic_sensor_report.py` B角 传感器审计
  - `fix_csv_schema.py` / `backfill_library_pool.py` / `tracks_status.py` / `journal_view.py`（journal 倒序查看）
  - `build_crosspool_view.py` / `add_quant_copy.py` / `backfill_bank_ex.py` 等（被 `engine/` 代码引用的脚本）
  - `_test_critic_sensor.py`（32 项）· `_test_build_facs_merge.py`（11 项）回归测试 · `_check_quotes.py` 质检
  - ⚠ **为什么迁**：`ai_test/` 长期被 `.gitignore` 整个忽略，但收尾管线住在里面
    ⇒ `git checkout v0.x` 回退代码时**整条管线会消失**（回退点不完整）。
- `ai_test/` — **草稿区 + 运行产物（按 `.gitignore` 忽略，可随时删）**：一次性诊断/探索脚本、
  日志（`_tracks/`）、中间产物（`*.csv`/`*.pkl`/`*.md` 报告）。
  - ⚠ 仅留 3 个**兼容垫片**（`run_tracks.py` / `build_facs.py` / `cross_pool_review.py` → 转发到 `tools/`），
    为「迁移时正在跑的轨道」保留；**轨道结束后可 `git rm`**。
- `standard/` — **统一检验 / 分析工具**（均为独立可跑的绝对路径脚本）
  - `standard_test.py` 因子检验模板：一次跑齐「引擎指标复现校验 + 全A宽池频率扫描 + 沪深300/中证500 成分内 + 风格归因 + 分段独立验证」，含 `--pool_mode=A|B|S`、`--cost-name`；成本口径取自 `engine/cost_presets.py`
  - `style_paired_analysis.py` 排序分**配对**风格暴露比较（old / new / new+mono / new_n）→ 写 `docs/loop_style_paired.md`
  - `qa_style_obs.py` 风格观测链路自检（18 项：向量化 vs 朴素对拍、退化安全、20 日滚动轴、`--help` 冒烟）
  - `prof_evalreal.py` 单点耗时剖析（cProfile + 合成因子跑真实 panel）→ 定位相位瓶颈，不用"总时长减法"猜
- `docs/` — 结论文档/档案：`factor_roadmap.md`（**研发档案主入口**：Round 叙事 + 附录A Loop gen1~22 整体复盘 + 附录B 扩叶落地）/ `factor_library.md`（**Loop 入库因子**，引擎代末自动同步新增）/ `loop_journal.md`（B角代际诊断）/ `loop_archive.csv`（Loop 每代 L2 明细流水，逐代累积）/ `history/`（**归档区**：factor_miner Round1~7 旧档案 factor_archive.md/.csv，已停更）
- `strategies/` — 定稿 rqalpha 回测策略：`all01/`（all00/01/03 + factor_snapshot 数据）、`all04/`（barra 落地 + g6 数据）、`vol/`、`big_small/`，共享 `bt_utils.py`
- `research/` — 早期挖掘轮次 `round*.py` 与专题研究脚本（方法留档；运行需与 `engine` 同目录或放回原 `ai_test` 全套依赖）

## 运行
```powershell
# 引擎一代（后台）：参数与三道闸详见 loop_engine.py argparse
cd D:\loop_code\engine
D:\miniconda3\envs\rqdata\python.exe loop_engine.py --gen=13 --n=800 --l2=30 --seed=123
#   LLM 双子开关（均默认 auto，可 on/off 强开/强关；无 key 或调用失败自动回退纯规则，不影响无人值守）：
#     --llm_guide  A角生成引导：候选引导位由 loop_llm 解析语义候选，失败/无 key 回退本地 13 机制族
#     --ai_jury    B角候选审查：L1 硬滤后随机抽 --jury_n(默认5) 精判，KILL 剔除出 L2
#     --ai_critic  代末 AI 审查：点评本代诊断+规则建议，全文写进 docs/loop_journal.md“AI 审查(DeepSeek)”小节
#   key=桌面 1.txt 或环境变量 DEEPSEEK_API_KEY

# 无人值守多代接力（可选）：启动 watcher 后每 5min 轮询，空闲且该代无 err 自动启下一代
#   停止条件：任一代 err 非空即停下等人工（铁律）；代数达 loop_watch.py 上限（默认 50）自动结束。
#   防多实例/防重复代已内置；引擎在跑时 watcher 只等待不动作，可随时手动启动。
cd D:\loop_code\engine
Start-Process "D:\miniconda3\envs\rqdata\python.exe" -ArgumentList '-u','loop_watch.py' -WorkingDirectory 'D:\loop_code\engine' -WindowStyle Hidden

# 进度查询（脚本在 engine/ 下且按自身路径定位：带全路径即可，从任意目录运行都行）
D:\miniconda3\envs\rqdata\python.exe D:\loop_code\engine\loop_status.py

# 无人值守期间人工查看（代号 N 换成当前代，如 loop23C.*）：
Get-Content D:\loop_code\engine\loop_watcher.log -Tail 20   # watcher 接力事件: [START]/[OK]/[RUN]/[SKIP]/[STOP]/[DONE]
Get-Content D:\loop_code\engine\loop23C.log -Tail 20        # 当前代引擎进度（阶段字样见 loop_status.py）
Get-Content D:\loop_code\engine\loop23C_err.log             # 当前代错误日志（空=正常）
Get-Content D:\loop_code\docs\loop_journal.md -Tail 30      # B角每代诊断 + AI 审查落档

# 定稿策略回测（示例）
cd D:\loop_code\strategies\all04
D:\miniconda3\envs\rqdata\python.exe all04.py
```

## 说明
- 引擎所有文件读写都相对 `engine/` 定位，`loop_code` 可整体搬移；唯一外部依赖是 `E:\rq` 数据盘。
- `loop_state.pkl` 为滚动态：**gen23 起 watcher 无人值守接力，已跑至 gen70 达标收官（2026-09-11）**，入库因子 **30**（F01~F30）。整体复盘见 `docs/factor_roadmap.md` 附录 A/B + Round27；入库因子明细见 `docs/factor_library.md`；逐代诊断见 `docs/loop_journal.md`。跨系统（存储/数据库/对齐）决策见 `docs/software_framework.md`。
- **gen51 起新增两道抗冗余闸门**（治 gen50 同代近重复 F20~F23）：`--dedup_corr`（默认 0.85，同代 L1 TopN 两两 |rank corr| 超阈即丢弃后者）+ `--fam_sole`（默认开，族指纹并入"单叶变换"维度把"同叶不同壳"的叶子代理候选归同族）。标定/验证见 `tools/calib_gates.py` / `verify_gates.py`，冒烟 `ai_test/qa_fam_smoke.py`。
- 数据文件（*.h5/*.pkl）体积大且可由 `build_*.py` 重建，git 入库时按 `.gitignore` 排除。

## 版本与回退（2026-09-11 起）

**约定：每个"版本" = 一次 commit + 一个 annotated tag**（版本名 `v<major>.<minor>` 递增）。
tag 说明固定记录四项，便于回退时判断影响面：

| 项 | 说明 |
|---|---|
| **引擎行为** | 是否改变挖掘结果（阈值/排序分/生成端改动 = **变**；纯工具/文档 = 不变） |
| **已完成代** | 该版下的代数与入库范围（如 gen70 / F01~F30） |
| **关键变更** | 3~5 条要点 |
| **回退方式** | `git checkout <tag>` |

⚠ **引擎滚动状态不在 git 内**：`engine/loop_state.pkl`（bank / 种子 / 冻结 / 失败库）与
`docs/loop_archive.csv` 均按 `.gitignore` 排除。**回退代码 ≠ 回退库状态**——若要连状态一起回退，
需另行备份 `loop_state.pkl`。

```powershell
git --no-pager tag -l -n20                 # 列出所有版本及说明
git --no-pager show v0.1 --stat            # 看某版改了什么
git checkout v0.0                          # 回退到基线（再 git checkout main 回来）
git tag -a v0.2 -F <说明文件>               # 建新版（说明按上表四项写）
```

**已建版本**（**完整变更台账见根目录 [`change_log.md`](change_log.md)**；下表只列"该版一句话 + 回退影响面"）

> ⚠ **表格约定**：**最新一行的"提交"列写 `tag 自身`** —— 这不是偷懒：
> **一个文件无法记录"包含它自己的那次提交"的哈希**（哈希由内容算出，先有内容才有哈希，自指无解）。
> 要用它时 `git show v0.5.1` 即可（tag 直接指向该提交）。历史行才有具体哈希。

| tag | 日期 | 提交 | 一句话内容 |
|---|---|---|---|
| **v0.6.0** | 2026-09-14 | `tag 自身` | **新增「日频 mark-to-market」风险口径**（`evaluate_real(with_daily=True)` ⇒ `dd_d`/`calmar_d`/`sharpe_d`，默认关闭不改变行为）—— 治 §1.19「期频打点导致回撤系统性低估 ~3.6pp」。★ 两个坑写进 docstring：**不能用 `set_fwd(1)`（那是"每天调仓"的另一策略）**、**必须把日超额锚定到期频值**（否则两条净值路径不可比）⇒ `dd_d <= dd_e` **严格成立**。`tools/_test_daily_dd.py` **15 项**（含逐点抽查 418/418 期频点重合）· `build_facs` 落日频列 |
| **v0.5.5** | 2026-09-14 | `b5d975b` | **PATCH / 纯文档**：外部独立审查触发 —— 落 **§1.18**（`all3` 标签判据比入库门槛松：池内只卡"超额>0"、不卡 Calmar ⇒ 误标"真 alpha"）+ **§1.19**（引擎侧风险指标是**期频打点**口径 ⇒ 回撤低估 ~3.6pp、Calmar 高估 ~1.4×；**挖掘侧与组合侧不可直接比**）+ 重跑 gen7/8/9 结果（**收尾 23.7min→2s** ✓ · C 档零新增 ✓）|
| **v0.5.4** | 2026-09-14 | `e89980f` | **PATCH**：`tools/pool_grade_summary.py`（各池档位汇总 + **防回归告警**，`--since-gen` / `--warn-c`，超阈返回码 1）· ★ **§1.17 端到端验证通过**：修复后 gen7 入库 `F10_1000` = **A 档**（C 占比 **0%**），而修复前 8 代出 6 个 C 档（60%）|
| **v0.5.3** | 2026-09-14 | `d8a70c3` | 🔴 **修 `--pool_gate_or_all` 静默绕过「剥风格门槛 + 分段验证」**（`combine_ok()` 纯函数 + `_ok_hard`；`tools/_test_ok_gate.py` 22 项）· `tools/prune_style_only.py`（1000 池 bank 9→3）· 删 3 个垫片 · **产品定位拍板 B. 真中性增强** |
| **v0.5.2** | 2026-09-14 | `b80c93f` | **建 `tools/` 纳入 git**（23 个管线/工具脚本从 `ai_test/` 迁出 ⇒ **回退点完整**）+ 114 处引用更新 + 3 个兼容垫片（**轨道结束后可删**）+ 修 `HERE` 产物路径分裂 + 修 gitignore 误放开 101 个归档文件 |
| **v0.5.1** | 2026-09-14 | `bcea0aa` | **纯文档**：README 版本表修正 v0.5.0 的提交号 + `loop_todo §1.15`（规则1 固定动作且连压 13 代无效 ⇒ 缺"动作有效性"追踪）+ `§1.16`（`ai_test/` 未纳入 git ⇒ **回退点不完整**） |
| **v0.5.0** | 2026-09-14 | `3da89fe` | 池化挖掘闭环（中证1000 池 + 池门槛 OR 语义 + 收益流去重）+ **B角「诊断→决策」链条修复**（门槛对账 / 动作饱和 / **LLM 否决权 + 永久闭嘴**）+ 收尾提速 **23min→4.1s**（`build_facs --only-new`）+ 跨池审查/L3 精选池 + `facs/` 因子值仓（含 `values_q.h5` 快查副本）+ `change_log.md` |
| **v0.4** | 2026-09-12 | `6c60c7f` | 三池并行挖掘 `--mine_pool` + 入库剥风格/池内判据（`--strip_style`/`--pool_obs`）+ `loop_pools.py`（PIT 成分单一事实源）+ **修"整代末尾 `UnboundLocalError`"事故** |
| **v0.3** | 2026-09-12 | `41dbb9d` | `new_n` 判定 ✅ + `--reuse_v` 提速 35% + `--shape_neutral` |
| **v0.2.1** | 2026-09-12 | `3fb5f28` | `shape_pos_n`（风格中性后的第二套形状量，默认仅观测） |
| **v0.2** | 2026-09-12 | `641fe33` | 风格暴露观测 `--style_obs` + 批1 排序分配对实测 |
| **v0.1** | 2026-09-11 | `6ed6b00` | 成本档单一事实源 + L1 指标层（`loop_metrics.py`）+ `--min_mono` / `--score_mode`（默认关闭）+ `software_framework.md`；**引擎行为不变** |
| **v0.0** | `e582921` | 代码基线（改造之前）：gen51 双闸门版 |
