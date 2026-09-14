# loop_code — Loop 式因子自动挖掘引擎

> **当前版本 `v0.12.0`**（2026-09-15）— 池化挖掘闭环 + B角「诊断→决策」链条修复 + 收尾提速 + 管线迁入 `tools/` + **修 `--pool_gate_or_all` 静默绕过硬门槛**
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
  - `fix_csv_schema.py` / `backfill_library_pool.py` / **`backfill_library_sign.py`**（回填各库明细块的 `sign`）/ `tracks_status.py` / `journal_view.py`（journal 倒序查看）
  - `build_crosspool_view.py` / `add_quant_copy.py` / `backfill_bank_ex.py` 等（被 `engine/` 代码引用的脚本）
  - `_test_critic_sensor.py`（32 项）· `_test_build_facs_merge.py`（11 项）· `_test_inject_pools.py`（17 项）
    · `_test_parent_sel.py`（20 项）· `_test_reports_expr.py`（34 项，**报告表达式必须完整**）
    · `_test_action_efficacy.py`（33 项，**动作有效性 + 参数棘轮**）回归测试 · `_check_quotes.py` 质检
  - ★ **`verify_test_catches.py`** — **负向验证**：把 bug 人为放回源码 → 跑测试 ⇒ **必须 FAIL** → 还原 ⇒ PASS。
    **一个"永远通过"的测试没有价值** —— 必须证明它真的抓得到它要防的 bug（`try/finally` 保证还原）
  - ★ **`smoke_gen_only.py`** — **引擎改动后的几十秒真机冒烟**（用引擎自带的 `--gen_only`：
    「只跑候选生成段、不跑 L1/L2、**不写状态**」）⇒ 断言行真的打印了 + 无 `Traceback`/`NameError`
    + **全部 `loop_state*.pkl` SHA256 未变**。★ 意义：**把"改引擎要等 50 分钟才知道崩没崩"降到 30 秒**
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
| **v0.12.0** | 2026-09-15 | `tag 自身` | **加 `ema` 算子**（`ema5/ema12/ema20/ema26/ema60`，`α=2/(w+1)`）—— 治盘点发现的**唯一真缺**（`ts_mean` 等权 vs EMA 指数加权 ⇒ **组合不出来**）；★ **`sub(ema12,ema26)` 就是 MACD** ⇒ 不必单加 `MACD` · ★★ **顺手抓到一处已存在漂移**：`loop_critic._ops_of()` **硬编码 28 个算子而引擎有 45 个**（**缺 15 个长窗算子 ⇒ 一直被 B角 结构诊断忽视**）⇒ 改成**从引擎派生**（惰性 import 避免循环）+ **`_test_ops_sync.py` 22 项锁住**（含穷尽搜"白名单副本"、prompt 简写展开、`ts_ema` 手算递归/满窗/**无未来信息**）· ★ `min_periods=w` 满窗（EMA 早期值严重依赖起点）· ★★ **性能实测推翻估算**：真面板 `ema12` **0.58s** vs `ts_mean20` **1.17s** ⇒ **ema 反而快一倍** |
| **v0.11.3** | 2026-09-15 | `848021e` | **特征/算子盘点**（对照**本地 `QuantaAlpha-main` 源码**，不凭记忆）—— 结论：**四价一量 ✅ 全有**（`close`/`open`/`high`/`low`/`volume` 是**基础 7 叶子直接可用**）· **MA ✅**（`ts_mean` ×8 档）· **HHV/LLV ✅**（`ts_max`/`ts_min`，但只 2 档窗口）· ★★★ **真正缺的只有「加权均线族」= `EMA`/`MACD`**（`ts_mean` 等权、EMA 指数加权 ⇒ **组合不出来** ✗）—— 而这**正是文档里既定的"三期"项**（非遗漏）· 🟡 **RSI/BOLL/ATR 都能用现有算子组合出来**（`ts_rank` / `ts_mean`±`ts_std` / `ts_mean(true_range)`）· ★ 我们的**优势**：**资金流 16 列 + BARRA 11 + 财报 PIT 8**（QuantaAlpha 都没有）· **建议**：若补**只加 `ema` 一个算子**（加了就能组合出 MACD），并配套复杂度门（否则只扩大搜索空间） |
| **v0.11.2** | 2026-09-15 | `72098be` | ⚠ **更正 v0.11.1 的建议**（用户一问引出：「扩到 11 个**要不要等**每个风格都有 1-2 个因子？」）—— 我的答复：**① 「不用等」**（剥离用的是**风格暴露值**，与库里有没有该风格的因子无关）；**② ★★★★ 但「扩到 11」本身方向错** —— 实测**全库 28/56 = 50% 的因子用 BARRA 叶子构造**（`barra_residual_volatility` 一个被 **22 个**用；精选池 7 个里 5 个含它）⇒ 那 11 个是「**因子的构造原料**」而非「要剥的风格」，**剥它们=把因子掏空** ✗ ⇒ **正确动作 = `2 → 4`（加 `lntr`+`lnpx`），零边际成本**（`style_features` 本来就算这 4 个，剥离代码一行 `if` 过滤掉了后两个）· ★ 由此确立分工原则：**「诊断暴露」要全（15 个都可看）、「剥离清单」只含背景暴露（4 个）** —— **诊断维度 ≠ 中性化维度** |
| **v0.11.1** | 2026-09-15 | `789c3ab` | **核对「外部独立审查」的 7 个精选因子** —— 结论：**他的判断基本正确、引擎值 14/14 复现** ✓（我们 CSV 7/7 完全一致；`sign` 7/7 一致；300 内全员失效与 §1.3-A 交叉验证成立）。★ 但核对暴露**两条重要局限**：① ★★★ **「剥风格」只剥 2 个风格（lncap+lnamt），而暴露是 11 个 BARRA 风格** ⇒ `F07` 号称"最独立"但**仍暴露于换手率 `lntr` −0.51** ⇒ 「A 档」的准确含义只是「剥掉市值+成交额后仍有效」（**已记 roadmap §8.47**，是否扩到 11 个风格**待你拍板**）② **下游落地缺口（已修）**：`facs/` 存的是**原始值**、本表是**评估口径** ⇒ 直接用 h5 **绩效与回撤都对不上** ⇒ 精选池顶部加「**下游使用须知**」（必须乘 `sign` / 必须自己剥风格 / **不能用 `values_q.h5`** / 池内未测）|
| **v0.11.0** | 2026-09-14 | `fab2acb` | **「动作有效性」+「参数棘轮」**（§1.15 + §1.1，**同族一起做**）—— 共同点：**都要给动作加"施加前快照"**。① **有效性**：记目标指标基线，一段闭合后**结算**「施加了到底有没有变好」，无效 ⇒ **冷却翻倍**（3→6→12）⇒ 累计 2 次 **永久停用**（治「全A gen61~73 连压 13 代同一叶子且完全无效」）② **棘轮**：记参数旧值，永久停用时**保守回退**（只回退被证伪动作、**且之后没人再动过**的参数）⇒ 治「`depth` 被推到 `[3,4,5]` 后**再也回不去**」。★ 关键设计：**唯一写入口 `_set()` + 动作上下文**（同代多动作会改同一参数，手写旧值必然漏）+ **静态断言防止将来新增动作静默漏记** · ★★ 踩到并修掉「回退顺序导致**停在半路**」（改为**重试收敛**，不需排序）+ 「部分成功不能整体清账」· 回归 **33 项** + 既有 32 项不破 + **两个负向验证** + 真机冒烟 5/5 |
| **v0.10.0** | 2026-09-14 | `2da02b3` | **`sign`（方向）全链路补齐** —— 引擎侧 `_lib_sync` 给新入库因子写 `sign`（**写明细块、不加表格列**：库文件 append-only，加列会让历史行错位 —— 这个坑 2026-09-13 已踩过）+ **`tools/backfill_library_sign.py`** 回填历史（**59 块 · 58 匹配 + 1 未落地 · 幂等**，缺失写「未记录」**绝不臆造**）+ crosspool 视图表A/表B **加 `sign` 列**。★ 先实测回答「下游有没有按列解析」：**一处都没有**（解析的都是明细段/代码块/前两列内容）· ⚠ 修：回填工具幂等前缀太严会**重复插入**（幸好默认 DRY-RUN 当场救了一次）· 回归 **34 项** + 负向验证 |
| **v0.9.1** | 2026-09-14 | `9d16699` | **修 `factor_pool_selected.md` 的表达式被截断**（`[:58]` ⇒ 最长 **58→189**）—— 根因：该文件**只有表格、没有明细段**（对比 `factor_library*.md` 是「总览截断 + 明细全文」两层）⇒ **截了就无处可查** ✗ · ★ **顺带补上 `sign`（方向，必须乘）与 h5 路径** —— 原来 7 个精选因子里 **6 个 `sign=-1`**，不乘它**组合会反向选股** ✗ · 新增 `tools/_test_reports_expr.py`（27 项，编码"没明细段的文件不许省略"）+ **`tools/verify_test_catches.py`**（**负向验证**：把 bug 放回去看测试是否 FAIL —— 已实测抓得到）|
| **v0.9.0** | 2026-09-14 | `b22cea7` | **第二批 ②：亲本选择策略 `--parent_sel`**（`uniform` 默认=不变 / `best` / **`top_percent_plus_random`**）—— 治「**当前 `rng.choice(seeds)` 把排名信息全丢了**：L1 第 1 名和第 30 名被选中概率完全一样」，补上 QuantaAlpha 的**显式探索/利用配比**（我们原来只有「堵」的手段：`fam_quota`/`fam_block_thr`/`--decorr`，**没有「疏」**）· ★ 头号坑：`top_percent_plus_random` 的「否则」分支**必须从全池随机**（写成"只从 rest 随机"会**正好抵消、退化成 uniform**）⇒ 已用**统计检验**守护（比值 **2.42** vs 理论 2.43）· **新增 `tools/smoke_gen_only.py`**（用 `--gen_only` 做**几十秒的真机冒烟** + 断言 state SHA256 未变 —— 把"改引擎要等 50 分钟才知道有没有 `NameError`"降到 **30 秒**）· ⚠ 效果**尚未 A/B 实测** |
| **v0.8.0** | 2026-09-14 | `b1c6333` | **第二批 ①：给全A 轨道注入池库对照集**（`--inject_pools`，`bank_ext`/`bank_ex_ext` **只读注入**，**绝不写回** state/因子库 —— 否则因子库会凭空多出一批不是它挖的因子）⇒ 治「跑全A 会把池库重挖一遍」（实测收益流 \|相关\| 中位 **0.767**、>0.7 占 **82%**）· ★ **只给 `all` 注入**（池轨道的产出是"有效域标签"，注入全A 库会让它无产出）· `run_tracks.py` 默认自动 + `--inject_pools=none` 可关 · ⚠ 顺带修：**argparse help 里的裸 `%` 会让引擎完全起不来** |
| **v0.7.1** | 2026-09-14 | `499c85a` | **PATCH / 纯文档**：落**第二批改造清单**（`loop_todo §1.21`：`§1.15` 动作有效性 · `§1.1` 参数棘轮 · `§1.8` 池库对照集 · `§1.3-C` 亲本策略）+ 分批理由（一次改 5 处无法归因）|
| **v0.7.0** | 2026-09-14 | `6474965` | **第一批改造（判据与口径族）**：`strip_grade` 改**日频** + 新增 **A 档回撤上限 `dd_d > -0.20`**（回撤超限**只降 B 不判 C**）· 新增 `TAG_POOL_FLOOR_CAL=0.15` **修判据不对称**（原来池内只要超额>0 ⇒ `all3` 名不副实）· L2 三处回测开 `with_daily` · `loop_pool_obs` 加 `pools_scope`（§1.5）· **验证：`F10_1000` 标签 `all3`→`csi1000_only`，与外部审查闭环** |
| **v0.6.1** | 2026-09-14 | `59e9ac4` | **PATCH**：全库 50 因子日频实测后**更正 v0.6.0 的过度陈述** —— 「期频**系统性**低估 3.6pp」是 `F10` 极端个案，**全库折算比中位 0.928**（回撤平均只放大 ~1.08×）⇒ 日频的价值在**揪出个别高回撤因子**（`F03_1000` 日 dd **−35%**、`F11` **−23%**）· 新增 `tools/calib_daily_threshold.py`（**阈值敏感度表**：日频 0.25 ⇒ A 档 17 个 **与现状相同**）|
| **v0.6.0** | 2026-09-14 | `0c06780` | **新增「日频 mark-to-market」风险口径**（`evaluate_real(with_daily=True)` ⇒ `dd_d`/`calmar_d`/`sharpe_d`，默认关闭不改变行为）—— 治 §1.19「期频打点导致回撤系统性低估 ~3.6pp」。★ 两个坑写进 docstring：**不能用 `set_fwd(1)`（那是"每天调仓"的另一策略）**、**必须把日超额锚定到期频值**（否则两条净值路径不可比）⇒ `dd_d <= dd_e` **严格成立**。`tools/_test_daily_dd.py` **15 项**（含逐点抽查 418/418 期频点重合）· `build_facs` 落日频列 |
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
