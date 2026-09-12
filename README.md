# loop_code — Loop 式因子自动挖掘引擎

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
- `standard/` — **统一检验 / 分析工具**（均为独立可跑的绝对路径脚本）
  - `standard_test.py` 因子检验模板：一次跑齐「引擎指标复现校验 + 全A宽池频率扫描 + 沪深300/中证500 成分内 + 风格归因 + 分段独立验证」，含 `--pool_mode=A|B|S`、`--cost-name`；成本口径取自 `engine/cost_presets.py`
  - `style_paired_analysis.py` 排序分**配对**风格暴露比较（old / new / new+mono / new_n）→ 写 `docs/loop_style_paired.md`
  - `qa_style_obs.py` 风格观测链路自检（18 项：向量化 vs 朴素对拍、退化安全、20 日滚动轴、`--help` 冒烟）
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
- **gen51 起新增两道抗冗余闸门**（治 gen50 同代近重复 F20~F23）：`--dedup_corr`（默认 0.85，同代 L1 TopN 两两 |rank corr| 超阈即丢弃后者）+ `--fam_sole`（默认开，族指纹并入"单叶变换"维度把"同叶不同壳"的叶子代理候选归同族）。标定/验证见 `ai_test/calib_gates.py` / `verify_gates.py`，冒烟 `ai_test/qa_fam_smoke.py`。
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

**已建版本**

| tag | 提交 | 内容 |
|---|---|---|
| **v0.1** | `4ebf734` | 成本档单一事实源 + L1 指标层（`loop_metrics.py`）+ `--min_mono` / `--score_mode`（默认关闭）+ `software_framework.md`；**引擎行为不变** |
| **v0.0** | `e582921` | 代码基线（改造之前）：gen51 双闸门版 |
