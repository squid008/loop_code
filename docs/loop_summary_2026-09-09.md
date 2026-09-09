# Loop 自动因子挖掘引擎 · 整体复盘（收官版）

> 复盘中金《基于 Loop Engineering 的自动化因子发现引擎》的 GP 式因子自动挖掘工程。
> 运行窗口 **2026-09-08 → 09-09**，手动收官于 **gen22**（gen23 于 09-09 08:25 中断）。
> 本档是全工程复盘入口；逐代诊断与 B 角建议见 `loop_journal.md`，入库因子明细见 `factor_library.md`，
> 逐代技术叙事（Round12~26）见 `factor_roadmap.md`。

---

## 1. 运行概况（收官态 = gen22 完成时 state）

| 项目 | 数值 | 说明 |
|---|---|---|
| 已跑代数 | **gen1~22**（journal 留档 gen4~22 共 19 代） | gen1~3 为原型验证期，未建 journal |
| L1 累计已测候选 | **12133**（state 计数） | 全部经过 L1 批 IC/稳定性粗筛 |
| L2 费后名额累计 | **523**（journal 口径；archive.csv 落 240 行明细） | 每代 25~30 个，跑九年费后回测 |
| 入库因子 | **9**（bank=9，n_pass 累计 9） | gen8×1 / gen10×3 / gen11×4 / gen14×1 |
| 收官态 state | seeds=30 / 冻结骨架 3 / 失败库 1738 骨架 / fsa 2203 骨架 | `engine/loop_state.pkl` |
| 单代耗时（有 log 记录） | 31~70 分钟 | gen13~22；后期 watcher 无人值守 |
| 错误日志 | 全为空（未发生一次代级崩溃） | 每代 `loop*C_err.log` |

engine/ 逐代 log 时间线（gen13 起迁入 `engine/`，此后有完整 log）：

```
gen13 09-08 20:58→21:35 36m | gen14 22:09→23:00 52m | gen15 23:36→09-09 00:46 70m
gen16 02:30→03:39 69m | gen17 03:41→04:29 48m | gen18 04:33→05:20 47m
gen19 05:23→06:05 42m | gen20 06:09→06:54 46m | gen21 06:59→07:38 39m
gen22 07:40→08:11 31m | gen23 08:15→08:25 9m(手动中断)
```

## 2. 逐代质量一览（journal 口径，gen4~22）

| gen | n_l1 | ic_med | known | n_l2 | n_pass | fail_calmar | fail_negyear | 头部叶子 |
|---|---|---|---|---|---|---|---|---|
| 4 | 28 | 0.052 | 0.536 | 25 | 0 | 1.00 | 0.48 | volume/turn_ratio/ln_volume |
| 5 | 41 | 0.058 | 0.488 | 25 | 0 | 1.00 | 0.32 | turn_ratio/volume/turnover |
| 6 | 40 | 0.063 | 0.250 | 25 | 0 | 1.00 | 0.44 | turn_ratio/volume/ret |
| 7 | 45 | 0.066 | 0.400 | 30 | 0 | 1.00 | 0.67 | turn_ratio/volume/ret |
| **8** | 44 | 0.070 | 0.773 | 30 | **1** | 1.00 | 0.86 | turn_ratio/volume/mktcap |
| 9 | 28 | 0.077 | 0.679 | 28 | 0 | 1.00 | 0.96 | turn_ratio/volume/turnover |
| **10** | 29 | 0.073 | 0.690 | 29 | **3** | 1.00 | 0.96 | turn_ratio/volume/turnover |
| **11** | 13 | 0.046 | 0.077 | 13 | **4** | 1.00 | 0.33 | turn_ratio/close/volume |
| 12 | 18 | 0.029 | 0.111 | 18 | 0 | 1.00 | 0.28 | turn_ratio/volume/close |
| 13 | 58 | 0.049 | 0.224 | 30 | 0 | 1.00 | 0.23 | turn_ratio/turnover/ret |
| **14** | 48 | 0.049 | 0.479 | 30 | **1** | 1.00 | 0.31 | turnover/turn_ratio/open |
| 15 | 42 | 0.051 | 0.452 | 30 | 0 | 1.00 | 0.30 | turn_ratio/turnover/ret |
| 16 | 49 | 0.053 | 0.714 | 30 | 0 | 1.00 | 0.17 | turnover/ln_mktcap/vwap |
| 17 | 36 | 0.057 | 0.694 | 30 | 0 | 1.00 | 0.10 | turnover/vwap/turn_ratio |
| 18 | 42 | 0.056 | 0.714 | 30 | 0 | 1.00 | 0.03 | turnover/vwap/turn_ratio |
| 19 | 44 | 0.058 | 0.659 | 30 | 0 | 1.00 | 0.03 | turnover/volume/turn_ratio |
| 20 | 41 | 0.057 | 0.756 | 30 | 0 | 1.00 | 0.03 | turnover/volume/low |
| 21 | 49 | 0.059 | 0.633 | 30 | 0 | 1.00 | 0.00 | turnover/low/volume |
| 22 | 45 | 0.057 | 0.556 | 30 | 0 | **0.967** | 0.00 | volume/turnover/ln_volume |

> 列：`known`=已知族占比；`fail_calmar/negyear`=L2 失败原因占比；头部叶子=该代 L1 上榜候选中占比前三字段。
> 注：gen16~22 为 LLM 双子 + 配比护栏 + watcher 无人值守的 7 代，**全部 err 为空、代代有 A角引导/B角 jury/代末 AI 审查记录**（见 §5）。

## 3. 阶段复盘

### 阶段 A：gen1~7 引擎建成与首次验证（Round12~19）
- gen1~3 原型（`ai_test/`）：五维演化 + 两级筛选(向量化 IC → `evaluate_real` 费后) + `--decorr` 去相关。gen2 独立重现了已知族 `ln_mktcap/amt_log`（费后 +9.74%/Calmar 0.88，与人工实测完全吻合），**证明引擎有效性**；gen3 加 decorr 后 0 通过，正确表述修正为"尚未挖出已知族以外新因子"。
- gen4~7：加 B 角（`loop_critic.py`，Round14）后连续 0 通过，但 B 角给出核心洞察——**IC 全过线 + fail_calmar≈100% + 有亏损年 → 问题不是信号强度，是年度稳定性**。

### 阶段 B：gen8~11 破零与"同族膨胀"教训（Round19/24）
- gen8 首次破零（F01，turn_ratio/量稳定族）。随后 decorr 升级为对 **state.bank 历代入库因子** 去相关，known_ratio 0.77→0.077。
- gen10×3 / gen11×4 集中入库，但 F02/F05~F08 全是 `ts_std(hl_ratio×turn_ratio)` 的**窗口变体**——decorr 拦得住"截面排序近亲"，拦不住"同骨架换窗口"。
- **教训**：去相关是"结果闸门"，同族高分永远霸榜 → 落地 FSA 骨架冻结（同骨架 ≤1）+ 收紧 decorr，此后不再收同类变体（factor_library F09 起为不同结构）。

### 阶段 C：gen12~15 三道闸落地 + 生成断崖修复（Round25/26）
- gen12 首次真实一代验证 FSA/失败库/跨量纲审查，0 通过；**暴露生成断崖**：54/800（重复去重无计数 + 五维分支阈值 bug：`r<cut[0]+cut[1]+cut[2]` 恒 >1 → 100% 走 seed 分支打转）。
- 修复（gen13 前）：分支改 `r<cut[2]/cut[3]`、去重 list→set 计数、上限放宽 + 纯随机兜底。gen13/15 恢复 **800/800 产量**。
- gen14（22:09~23:00）**F09 入库**：深度 5、混入 mktcap/close/open 的换手×量×价格结构，费后 Calmar 0.914/Sharpe 1.256/负年 0 —— 破连续 0 通过，也是最后一个入库因子。

### 阶段 D：gen16~22 LLM 双子 + 无人值守（09-09 凌晨）
- 对齐中金的 A角 LLM 语义引导（13 机制族，占用 20% 生成位）+ B角 LLM 候选审查（jury 抽 5 精判，KILL 剔除出 L2）+ 代末 AI 审查落档，首次真实一代验证即连续工作 7 代。
- IDE automation 接力因一次 run 超时进入日级退避而弃用 → 常驻 watcher（`loop_watch.py`，5min 轮询）03:41 起自动接力 gen17→22 共 6 代零事故。
- 挖掘产出：连续 0 通过 8 代（gen15~22）。机械链路与 AI 链路全部健康（§5/§6），不构成故障；处于严苛口径下的正常低产期。

## 4. 入库因子（9 个，详见 factor_library.md）

| 家族 | 因子 | 说明 |
|---|---|---|
| 换手-量联动波动 | F01(gen8) / F03、F04(gen10) | turnover/turn_ratio/volume 波动组合（amt_log 远亲） |
| hl_ratio×turn_ratio 稳定 | F02(gen10) + F05~F08(gen11) | **同骨架 4 个窗口变体** → 触发 FSA 冻结的关键案例 |
| 换手×量×价格 深度交叉 | F09(gen14) | 唯一非纯量/换手族结构；深度 5，混入 mktcap/close/open |

- 入库分布与 `n_pass` 累计一致：9 个入库 = gen8×1 / gen10×3 / gen11×4 / gen14×1。
- 除 F09 外，8/9 属于"换手/成交量"流动维度（含小成交额族的统计近亲）——即引擎在已知维度的稳健复现强，向新维度突围尚未成功。

## 5. LLM 双子链路验证结论（gen16~22，7 代真实运行）

| 组件 | 规格 | 7 代实测 |
|---|---|---|
| A角 语义引导 | 每次 3 次调用、每次解析一批机制族表达式，填引导位 | 38~45 条/代全部解析通过并投入使用 |
| B角 候选审查 | L2 前抽 5 个精判，KILL 即剔除 | 深判 5 / KILL 4~5 个（多为同源嵌套冗余、sign(x²)、min(x,x) 等，理由可读、模式稳定） |
| 代末 AI 审查 | 深链 v4-flash，点评规则 B 角建议并给下代建议 | 2~3s/次，代代落档 journal |

关键结论：
1. **全链路可用**：解析 → 引导位使用 → jury → AI 审查落档，7 代无一失败（失败自动放行不阻断无人值守）。
2. **代代 AI 审查共识**（跨 7 代高度一致）：L1 高 IC 因子全部依赖 turnover/volume/intraday 的机械组合，**信号伪高但无增量信息源** → L2 全灭于 Calmar。这与规则 B 角诊断互证，说明卡点是"搜索结构被换手/量维度锁死"，而非参数没调好。
3. **工程坑（已修）**：deepseek v4-flash 是推理模型，默认深度推理会吃光 max_tokens 致 content 恒空 —— 请求体必须固定 `reasoning_effort='none'`；改 API 层时勿丢（勿用 'low'）。

## 6. 无人值守体系

- **automation 弃用原因**：IDE automation「loop-gen50」一次 run 超过 90min 上限 → 调度器进入日级退避（next_run 被排到次日 00:00），外部改库下次触发仍被覆写，**不可用于 50 代级接力**（已置 PAUSED，见 §8）。
- **watcher**（`engine/loop_watch.py`，已提交）：每 5min 查 `loop_engine` 进程；空闲且该代 err 空且代数 < 上限 → 自动启下一代（seed=(N+1)×10+7 / n=800 / l2=30，防重复）。实测 09-09 03:41 → 08:15 连续自动接力 6 代（gen17→22），err 全空。
- 单代 31~70 分钟；含轮询间隙稳定在 ~35~45 min/代（后半夜 CPU 空载时更快）。

## 7. 质量结论（边界与正确表述）

1. **正确表述**：截至收官（gen22，L1 累计 12133 候选），**已稳健复现"小市值/小成交额/换手-量流动"已知维度，但尚未挖出已知族以外的可入库新因子**。不要轻言"挖掘到头"：中金 16939 候选才出 69 因子（0.41%），前 50 轮仅入库 4 个；我方累计 12133 候选、口径还严苛约 3.5 倍（九年+费后 vs 近 600 交易日），连续 8 代 0 通过完全在统计波动内。
2. **主矛盾不是挖掘参数，而是结构**：19 代里 18 代 `fail_calmar≈100%`（信号弱）+ 头部叶子被 turnover/volume/turn_ratio/intraday 轮流垄断（leaf_w 连压 3 代无效 → 已证是 L1 选择压力问题非生成频率问题）。引擎的机制闸门（decorr/FSA/失败库/跨量纲/jury）已全部工作且把重复发现压到很低，但**叶子池（纯量价 21 字段）与五年 FWD 的短持有框架决定了候选的增量信息上限**。
3. **经验资产的价值高于因子**：全流程（生成-审查-验证三端、结果闸门、失败反馈、LLM 双代理、护栏化建议、幂等落档）已跑通并被真实数据反复校验；后续若扩充叶子池（财报 PIT / 分钟频聚合）或改持有多空结构，可直接复用整套基建。

## 8. 遗留资产与续跑指南

**资产清单**
- 因子：`docs/factor_library.md`（9 个入库因子 + 指标）；L2 流水 `docs/loop_archive.csv`（240 行明细）+ `loop_archive.legacy_pre_gen16.csv`
- 逐代诊断：`docs/loop_journal.md`（gen4~22）；全叙事 `docs/factor_roadmap.md`（Round12~26）
- 状态快照：`engine/loop_state.pkl`（收官态：bank 9 / seeds 30 / 失败库 1738 / L1 已测 12133）
- 代码：`engine/loop_engine.py` / `loop_critic.py` / `loop_llm.py` / `loop_watch.py` / `loop_status.py`；每代对话录音 `ai_test/loop_conv/gen*C_conv.md`
- 引擎依赖外部数据盘 `E:\rq`（bundle/panel/universe）

**续跑方法**（若日后要接着挖，从 gen23 起）：
```powershell
# 1) 启动 watcher 自动接力（每 5min 轮询，空闲自动启下一代）
cd D:\loop_code\engine
Start-Process python -ArgumentList '-u','loop_watch.py' -WorkingDirectory 'D:\loop_code\engine' -WindowStyle Hidden
# 2) 查看进度/阶段
D:\miniconda3\envs\rqdata\python.exe D:\loop_code\engine\loop_status.py
```
如需改目标代数：编辑 `loop_watch.py` 中的上限（默认 50）；IDE automation「loop-gen50」已 PAUSED，可手动恢复/删除。
如需重置目标（例如以新叶子池重跑），应新建 state 或先存档现有 `loop_state.pkl`。

---

*本档生成于 2026-09-09，基于 journal/state/log/archive 实读整理；收官后 gen23 已由新叶通路完整跑完
（09-5x~10:2x，err 空，journal 第 23 代已落档），watcher 无人值守自动接力 gen24 跑动中（见 §8/loop_ext_leaves.md）。*
