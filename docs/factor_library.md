# Loop 因子库（入库有效因子）

> 收录 **Loop 引擎**（`engine/loop_engine.py`）逐代挖掘、通过 L1+L2 费后全部门槛并**入库**的因子。
> 入库口径：区间 2018 起、成本单边千一、费后 Calmar>0.5、|IC|>0.02、换手与方向经 L2 校验、与已入库因子去相关 |rank corr|<0.65、骨架不重复。
> 每代挖掘记录（诊断+B角建议）见 `docs/loop_journal.md`；每代 L2 费后明细流水（逐代累积、带 gen/cat/leaf 列，自 gen16 起）见 `docs/loop_archive.csv`；gen16 前旧快照见 `docs/loop_archive.legacy_pre_gen16.csv`。
> **本文件只收录入库因子**，预计每数十轮才 +1 个，文件不会膨胀；round 流水永不并入本文件。
>
> 当前 **9 个入库**（截至 gen22 收官，2026-09-09；分布 gen8×1 / gen10×3 / gen11×4 / gen14×1；整体复盘见 `loop_summary_2026-09-09.md`）

---

## 因子总览

| 编号 | 入库代数 | 家族 | 一句话 | 状态 |
|---|---|---|---|---|
| F01 | gen8 | 换手-量联动波动 | turnover/turn_ratio×volume 双尺度波动 | 已入库 |
| F02 | gen10 | hl_ratio×换手稳定 族A | std20 × (hl_ratio×turn_ratio 长均) | 已入库 |
| F03 | gen10 | 换手波动叠加 | log(turnover) 波动 + turn_ratio 波动 | 已入库 |
| F04 | gen10 | 换手/量波动组合 | turn_ratio 波动 + log(volume) 波动 | 已入库 |
| F05 | gen11 | hl_ratio×换手稳定 族A | std60×mean5 窗口变体 | 已入库 |
| F06 | gen11 | hl_ratio×换手稳定 族A | std150×mean100 窗口变体 | 已入库 |
| F07 | gen11 | hl_ratio×换手稳定 族A | std100×mean5 窗口变体 | 已入库 |
| F08 | gen11 | hl_ratio×换手稳定 族A | std150×mean5 窗口变体 | 已入库 |
| F09 | gen14 | 换手×量×价格 深度交叉 | 深度5、混入 mktcap/close/open | 已入库 |

> ⚠️ F02/F05~F08 为**同一骨架（hl_ratio×turn_ratio）不同窗口**，gen11 后 bank 一度 5/8 同骨架——
> 正是这触发了 Round24 的 **FSA 骨架冻结**（同骨架 ≤1）与 decorr 收紧，后续不再收同类变体。

---

## 因子明细

### F01 · gen8 入库（第 1 个）
```
add(ts_std20(cs_demean(log(turnover))), ts_std60(cs_rank(cs_demean(add(mul(ret, ts_std20(volume)), log(cs_demean(turn_ratio)))))))
```
- 家族：换手-量联动波动（ret×volume 交互 + 换手双对数）
- 费后明细指标：见 gen8 时代历史 journal/日志（本档建立前未归档）

### F02 · gen10 入库
```
ts_std20(mul(cs_demean(hl_ratio), ts_mean100(cs_demean(turn_ratio))))
```
- 家族 A：hl_ratio×turn_ratio 稳定度（F05~F08 同骨架）
- 备注：decorr 0.70 时代入库

### F03 · gen10 入库
```
add(ts_std60(cs_demean(log(turnover))), add(ts_sum20(cs_demean(ts_std20(cs_demean(log(turn_ratio))))), cs_demean(log(turnover))))
```
- 家族：换手波动叠加（turnover 60 波动 + turn_ratio 短期波动）

### F04 · gen10 入库
```
add(ts_sum20(ts_std20(cs_demean(log(turn_ratio)))), cs_demean(log(ts_mean5(ts_std20(volume)))))
```
- 家族：turn_ratio 波动 + volume 波动组合

### F05 · gen11 入库
```
ts_std60(mul(cs_demean(hl_ratio), ts_mean5(cs_demean(turn_ratio))))
```
- 家族 A 窗口变体（std60 / mean5）

### F06 · gen11 入库
```
ts_std150(mul(cs_demean(hl_ratio), ts_mean100(cs_demean(turn_ratio))))
```
- 家族 A 窗口变体（std150 / mean100）

### F07 · gen11 入库
```
ts_std100(mul(cs_demean(hl_ratio), ts_mean5(cs_demean(turn_ratio))))
```
- 家族 A 窗口变体（std100 / mean5）

### F08 · gen11 入库
```
ts_std150(mul(cs_demean(hl_ratio), ts_mean5(cs_demean(turn_ratio))))
```
- 家族 A 窗口变体（std150 / mean5）
- F05~F08 备注：decorr 0.70 拦不住同骨架换窗口（当时 bank 5/8 同骨架）→ 触发 Round24 FSA 冻结

### F09 · gen14 入库（2026-09-08 23:00）★最新
```
neg(log(ts_mean60(div(add(mul(mul(turn_ratio, ts_mean5(ts_std20(cs_rank(log(turnover))))), ts_std20(add(mul(turn_ratio, ts_mean5(ts_mean20(volume))), mul(turn_ratio, corr20(log(cs_demean(turn_ratio)), mktcap))))), close), ts_std60(cs_rank(open))))))
```
- 家族：换手×量×价格 深度 5 交叉（不再是纯量/换手族窗口变体，混入 mktcap/close/open）
- 费后指标（full，成本 0.004）：IC 0.0484 / IC_IR 0.454 / 年化超额 +8.85% / 回撤 −9.7% /
  **Calmar 0.914 / Sharpe 1.256** / 最近年 +5.1% / 单期换手 15.7% / 负年 0
- 备注：n_pass=1 破连续 0 通过；同代 L2 其余 29 个仍 fail_calmar 100%（信号弱是主矛盾）

---

## 相关文件导航

| 文件 | 内容 |
|---|---|
| `docs/factor_library.md`（本文件） | 只收入库因子（每数十轮 +1，不膨胀） |
| `docs/loop_journal.md` | 每代诊断 + B角下一代参数（引擎自动读写） |
| `engine/loop_archive.csv` | 每代全量候选流水（expr/指标/passed） |
| `engine/loop_state.pkl` | 运行状态：bank/seeds/失败库/FSA（`_dump_state.py` 可看） |
| `docs/factor_archive.md` | **旧 factor_miner 体系** round1~7 挖掘档案（2026-09 前，已停更不并入 Loop） |
