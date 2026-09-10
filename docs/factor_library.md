# Loop 因子库（入库有效因子）

> 收录 **Loop 引擎**（`engine/loop_engine.py`）逐代挖掘、通过 L1+L2 费后全部门槛并**入库**的因子。
> 入库口径：区间 2018 起、成本单边千一、费后 Calmar>0.5、|IC|>0.02、换手与方向经 L2 校验、与已入库因子去相关 |rank corr|<0.65、骨架不重复。
> 自 gen34 起新增 **分段独立验证**：L2 费后日度超额序列按时间均分 3 个不相交子区间（约 3 年/段），
> 要求 ≥2 段各自累计费后超额 >0 —— 拦"靠单段大行情撑全样本高 t、行情一过即失效"的伪稳健候选
> （防数据窥探/伪衰减）；样本不足以分段时自动放行不误杀。开关：`--seg_n 3 --seg_need 2`。
> 每代挖掘记录（诊断+B角建议）见 `docs/loop_journal.md`；每代 L2 费后明细流水（逐代累积、带 gen/cat/leaf 列，自 gen16 起）见 `docs/loop_archive.csv`；gen16 前旧快照已归 `docs/history/loop_archive.legacy_pre_gen16.csv`。
> **本文件只收录入库因子**，预计每数十轮才 +1 个，文件不会膨胀；round 流水永不并入本文件。
>
> 当前 **23 个入库**（截至 gen50，2026-09-10；gen8×1 / gen10×3 / gen11×4 / gen14×1 / gen23×2 / gen31×1 / gen33×1 / gen43×3 / gen45×3 / gen50×4）。
> 运行期起：引擎在每代入库（`state.bank` append）时**自动同步追加**新因子条目（gen24 后的入库代次生效），家族/一句话命名随时可人工精炼覆盖。

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
| F10 | gen23 | 量价背离·影线强度综合 | corr100(up_shadow,ln_volume)/turnover，融合真实波幅/日内 对数合成 | 已入库 |
| F11 | gen23 | 日内强度密度 | hl_ratio/low × intraday² × ret（ts_mean60） | 已入库 |
| F12 | gen31 | 跳空、影线、财报、成交额 | div(ts_min100(corr100(overnight, ts_std60… | 已入库(auto) |
| F13 | gen33 | 风格、风格 | ts_delay1(add(barra_residual_volatility, … | 已入库(auto) |
| F14 | gen43 | 风格、量 | add(log(barra_non_linear_size), ts_std150… | 已入库(auto) |
| F15 | gen43 | 成交额、风格、风格、振幅 | ts_mean20(ts_mean60(sub(corr100(turnover,… | 已入库(auto) |
| F16 | gen43 | 成交额、风格、风格、振幅 | neg(ts_mean100(ts_mean60(sub(corr100(turn… | 已入库(auto) |
| F17 | gen45 | 财报、财报、风格、振幅 | add(ts_mean100(corr100(corr100(fa_ocf_yoy… | 已入库(auto) |
| F18 | gen45 | 财报、财报、风格、收益率 | add(ts_mean100(corr100(corr100(fa_ocf_yoy… | 已入库(auto) |
| F19 | gen45 | 资金流、量、资金流、风格 | max(ts_min20(cs_rank(div(mf_s_buy, ts_min… | 已入库(auto) |
| F20 | gen50 | 风格、财报、风格 | max(ts_mean120(cs_rank(div(barra_leverage… | 已入库(auto) |
| F21 | gen50 | 风格、风格、财报、财报 | max(add(barra_residual_volatility, barra_… | 已入库(auto) |
| F22 | gen50 | 财报、风格、风格 | max(ts_min20(cs_rank(add(fa_ocf_yoy, barr… | 已入库(auto) |
| F23 | gen50 | 风格、风格 | max(ts_min20(cs_rank(barra_leverage)), ba… | 已入库(auto) |

> ⚠️ F02/F05~F08 为**同一骨架（hl_ratio×turn_ratio）不同窗口**，gen11 后 bank 一度 5/8 同骨架——
> 正是这触发了 Round24 的 **FSA 骨架冻结**（同骨架 ≤1）与 decorr 收紧，后续不再收同类变体。
> F10/F11 为 gen23（8:25 手动中断前 L2 已跑完）入库、收官文档封版于 gen22 未收录；2026-09-09 由引擎状态核对后补录。
>
> ⚠️ **F20~F23（gen50 同代入库 4 个）为近重复因子**：F20↔F23 |corr|=0.932、F21↔F22=0.879，
> 顶层骨架均为 `max(<内层>, barra_residual_volatility)`。复盘确认真因是**共享主导叶**
> （F23 内层 ≡ barra_leverage，相关 0.997；F20 内层 0.786；F21/F22 共享 fa_ocf_yoy）
> 而非"地板效应"（剔除 resvol 后仍 0.894 / 非坍缩子样本 0.856）。此事件直接催生
> **gen51 双闸门**（同代近重复去重 `--dedup_corr` + 叶子代理族 `--fam_sole`），
> 详见 `docs/loop_journal.md` 末节与 `docs/factor_roadmap.md` Round27。**F20~F23 保留入库，
> 但按去重口径应仅 2 个有效**，使用该库时须注意此冗余。

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

### F10 · gen23 入库（2026-09-09 补录，来源 state.bank/archive）
```
sub(add(sub(div(corr100(up_shadow, ln_volume), turnover), corr60(true_range, turn_ratio)), neg(log(corr100(amplitude, intraday)))), ln_volume)
```
- 家族：量价背离·影线强度综合（up_shadow 与 ln_volume 的 100 日相关 ÷ turnover，叠加真实波幅/换手/日内波幅的对数合成）
- 叶子：up_shadow、ln_volume、turnover、true_range、turn_ratio、amplitude、intraday
- 费后指标（full，成本 0.004）：IC 0.0637 / IC_IR 0.577 / 年化超额 +6.7% / 回撤 −10.7% / **Calmar 0.624 / Sharpe 0.989** / 最近年 +1.5% / 单期换手 27.1% / 负年 0
- 备注：gen23（8:25 手动中断前 L2 已跑完）入库，bank 9→10；收官文档封版于 gen22 故未收录，本次核对补录

### F11 · gen23 入库（2026-09-09 补录，来源 state.bank/archive）
```
ts_mean60(mul(div(hl_ratio, low), mul(mul(intraday, ret), intraday)))
```
- 家族：日内强度密度（隔夜区间相对低点 hl_ratio/low × 日内动量² × 收益，60 日均值）
- 叶子：hl_ratio、low、intraday、ret
- 费后指标（full，成本 0.004）：IC 0.0588 / IC_IR 0.569 / 年化超额 +6.4% / 回撤 −12.1% / **Calmar 0.528 / Sharpe 0.790** / 最近年 +2.9% / 单期换手 24.9% / 负年 2
- 备注：同代入库（bank 10→11）；构造明显区别于历史 9 只的"波动/换手稳定"族

---

### F12 · gen31 入库（引擎自动同步，家族命名待人工精炼）
```
div(ts_min100(corr100(overnight, ts_std60(div(corr100(up_shadow, div(fa_roe, turnover)), turnover)))), turnover)
```
- 家族：跳空、影线、财报、成交额（auto）
- 叶子：overnight、up_shadow、fa_roe、turnover
- 骨架：`div(ts_min(corr(overnight,ts_std(div(corr(up_shadow,div(fa_roe,turnover)),turnover)))),turnover)`
- 费后指标（full，成本 4bp/边）：IC 0.0607 / IC_IR 0.586 / 年化超额 +5.3% / 回撤 -9.2% / Calmar 0.576 / Sharpe 0.794 / 最近年 +0.7% / 单期换手 35.7% / 负年 2

---


### F13 · gen33 入库（引擎自动同步，家族命名待人工精炼）
```
ts_delay1(add(barra_residual_volatility, barra_non_linear_size))
```
- 家族：风格、风格（auto）
- 叶子：barra_residual_volatility、barra_non_linear_size
- 骨架：`ts_delay(add(barra_residual_volatility,barra_non_linear_size))`
- 费后指标（full，成本 4bp/边）：IC 0.0743 / IC_IR 0.627 / 年化超额 +14.7% / 回撤 -19.5% / Calmar 0.750 / Sharpe 1.460 / 最近年 +3.7% / 单期换手 12.0% / 负年 1

---


### F14 · gen43 入库（引擎自动同步，家族命名待人工精炼）
```
add(log(barra_non_linear_size), ts_std150(ts_delay1(ts_sum20(ln_volume))))
```
- 家族：风格、量（auto）
- 叶子：barra_non_linear_size、ln_volume
- 骨架：`add(log(barra_non_linear_size),ts_std(ts_delay(ts_sum(ln_volume))))`
- 费后指标（full，成本 4bp/边）：IC 0.0390 / IC_IR 0.446 / 年化超额 +4.8% / 回撤 -9.4% / Calmar 0.507 / Sharpe 0.849 / 最近年 +3.6% / 单期换手 9.5% / 负年 1

### F15 · gen43 入库（引擎自动同步，家族命名待人工精炼）
```
ts_mean20(ts_mean60(sub(corr100(turnover, barra_non_linear_size), sub(barra_residual_volatility, true_range))))
```
- 家族：成交额、风格、风格、振幅（auto）
- 叶子：turnover、barra_non_linear_size、barra_residual_volatility、true_range
- 骨架：`ts_mean(ts_mean(sub(corr(turnover,barra_non_linear_size),sub(barra_residual_volatility,true_range))))`
- 费后指标（full，成本 4bp/边）：IC 0.0430 / IC_IR 0.412 / 年化超额 +5.2% / 回撤 -10.2% / Calmar 0.507 / Sharpe 0.902 / 最近年 +1.7% / 单期换手 8.3% / 负年 2

### F16 · gen43 入库（引擎自动同步，家族命名待人工精炼）
```
neg(ts_mean100(ts_mean60(sub(corr100(turnover, barra_non_linear_size), sub(barra_residual_volatility, true_range)))))
```
- 家族：成交额、风格、风格、振幅（auto）
- 叶子：turnover、barra_non_linear_size、barra_residual_volatility、true_range
- 骨架：`neg(ts_mean(ts_mean(sub(corr(turnover,barra_non_linear_size),sub(barra_residual_volatility,true_range)))))`
- 费后指标（full，成本 4bp/边）：IC 0.0377 / IC_IR 0.382 / 年化超额 +5.7% / 回撤 -8.0% / Calmar 0.720 / Sharpe 1.018 / 最近年 +3.5% / 单期换手 6.2% / 负年 0

---


### F17 · gen45 入库（引擎自动同步，家族命名待人工精炼）
```
add(ts_mean100(corr100(corr100(fa_ocf_yoy, fa_gm), barra_residual_volatility)), max(ts_rank200(ts_max100(amplitude)), barra_residual_volatility))
```
- 家族：财报、财报、风格、振幅（auto）
- 叶子：fa_ocf_yoy、fa_gm、barra_residual_volatility、amplitude
- 骨架：`add(ts_mean(corr(corr(fa_ocf_yoy,fa_gm),barra_residual_volatility)),max(ts_rank(ts_max(amplitude)),barra_residual_volatility))`
- 费后指标（full，成本 4bp/边）：IC 0.0528 / IC_IR 0.641 / 年化超额 +4.1% / 回撤 -4.7% / Calmar 0.874 / Sharpe 0.959 / 最近年 +1.7% / 单期换手 12.9% / 负年 1

### F18 · gen45 入库（引擎自动同步，家族命名待人工精炼）
```
add(ts_mean100(corr100(corr100(fa_ocf_yoy, fa_gm), add(barra_residual_volatility, fa_ocf_yoy))), max(ret, barra_residual_volatility))
```
- 家族：财报、财报、风格、收益率（auto）
- 叶子：fa_ocf_yoy、fa_gm、barra_residual_volatility、ret
- 骨架：`add(ts_mean(corr(corr(fa_ocf_yoy,fa_gm),add(barra_residual_volatility,fa_ocf_yoy))),max(ret,barra_residual_volatility))`
- 费后指标（full，成本 4bp/边）：IC 0.0531 / IC_IR 0.603 / 年化超额 +3.5% / 回撤 -6.2% / Calmar 0.568 / Sharpe 0.959 / 最近年 +6.3% / 单期换手 13.0% / 负年 1

### F19 · gen45 入库（引擎自动同步，家族命名待人工精炼）
```
max(ts_min20(cs_rank(div(mf_s_buy, ts_min20(ts_std200(corr200(ln_volume, mf_s_bqty)))))), barra_residual_volatility)
```
- 家族：资金流、量、资金流、风格（auto）
- 叶子：mf_s_buy、ln_volume、mf_s_bqty、barra_residual_volatility
- 骨架：`max(ts_min(cs_rank(div(mf_s_buy,ts_min(ts_std(corr(ln_volume,mf_s_bqty)))))),barra_residual_volatility)`
- 费后指标（full，成本 4bp/边）：IC 0.0644 / IC_IR 0.576 / 年化超额 +5.0% / 回撤 -7.7% / Calmar 0.643 / Sharpe 0.894 / 最近年 +3.6% / 单期换手 15.4% / 负年 2

---


### F20 · gen50 入库（引擎自动同步，家族命名待人工精炼）
```
max(ts_mean120(cs_rank(div(barra_leverage, fa_gm))), barra_residual_volatility)
```
- 家族：风格、财报、风格（auto）
- 叶子：barra_leverage、fa_gm、barra_residual_volatility
- 骨架：`max(ts_mean(cs_rank(div(barra_leverage,fa_gm))),barra_residual_volatility)`
- 费后指标（full，成本 4bp/边）：IC 0.0562 / IC_IR 0.707 / 年化超额 +6.7% / 回撤 -7.4% / Calmar 0.907 / Sharpe 1.415 / 最近年 +2.7% / 单期换手 10.2% / 负年 1

### F21 · gen50 入库（引擎自动同步，家族命名待人工精炼）
```
max(add(barra_residual_volatility, barra_leverage), max(ts_min20(cs_rank(div(fa_ocf_yoy, fa_gm))), barra_residual_volatility))
```
- 家族：风格、风格、财报、财报（auto）
- 叶子：barra_residual_volatility、barra_leverage、fa_ocf_yoy、fa_gm
- 骨架：`max(add(barra_residual_volatility,barra_leverage),max(ts_min(cs_rank(div(fa_ocf_yoy,fa_gm))),barra_residual_volatility))`
- 费后指标（full，成本 4bp/边）：IC 0.0525 / IC_IR 0.708 / 年化超额 +5.5% / 回撤 -6.4% / Calmar 0.868 / Sharpe 1.310 / 最近年 +0.4% / 单期换手 13.2% / 负年 0

### F22 · gen50 入库（引擎自动同步，家族命名待人工精炼）
```
max(ts_min20(cs_rank(add(fa_ocf_yoy, barra_leverage))), barra_residual_volatility)
```
- 家族：财报、风格、风格（auto）
- 叶子：fa_ocf_yoy、barra_leverage、barra_residual_volatility
- 骨架：`max(ts_min(cs_rank(add(fa_ocf_yoy,barra_leverage))),barra_residual_volatility)`
- 费后指标（full，成本 4bp/边）：IC 0.0527 / IC_IR 0.689 / 年化超额 +4.8% / 回撤 -6.9% / Calmar 0.699 / Sharpe 1.230 / 最近年 +0.8% / 单期换手 13.2% / 负年 0

### F23 · gen50 入库（引擎自动同步，家族命名待人工精炼）
```
max(ts_min20(cs_rank(barra_leverage)), barra_residual_volatility)
```
- 家族：风格、风格（auto）
- 叶子：barra_leverage、barra_residual_volatility
- 骨架：`max(ts_min(cs_rank(barra_leverage)),barra_residual_volatility)`
- 费后指标（full，成本 4bp/边）：IC 0.0535 / IC_IR 0.653 / 年化超额 +4.8% / 回撤 -8.9% / Calmar 0.532 / Sharpe 1.042 / 最近年 +2.9% / 单期换手 10.2% / 负年 1

---


## 相关文件导航

| 文件 | 内容 |
|---|---|
| `docs/factor_library.md`（本文件） | 只收入库因子；引擎代末自动同步新入库，家族命名随时可人工精炼 |
| `docs/loop_journal.md` | 每代诊断 + B角下一代参数（引擎自动读写） |
| `docs/loop_archive.csv` | 每代 L2 全量候选流水（expr/指标/passed，引擎逐代追加） |
| `engine/loop_state.pkl` | 运行状态：bank/seeds/失败库/FSA（`_dump_state.py` 可看） |
| `docs/factor_roadmap.md` | 研发档案（Round 叙事 + Loop 整体复盘/扩叶落地附录，续做入口） |
| `docs/history/` | **归档区**：factor_miner round1~7 档案（`factor_archive.md/.csv`）+ gen16 前 Loop L2 旧快照（`loop_archive.legacy_pre_gen16.csv`），均已停更 |
