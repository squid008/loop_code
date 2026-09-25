# Loop 因子库（入库有效因子）

> 收录 **Loop 引擎**（`engine/loop_engine.py`）逐代挖掘、通过 L1+L2 费后全部门槛并**入库**的因子。
> 入库口径：区间 2018 起、成本单边千一、费后 Calmar>0.5、|IC|>0.02、换手与方向经 L2 校验、与已入库因子去相关 |rank corr|<0.65、骨架不重复。
> 自 gen34 起新增 **分段独立验证**：L2 费后日度超额序列按时间均分 3 个不相交子区间（约 3 年/段），
> 要求 ≥2 段各自累计费后超额 >0 —— 拦"靠单段大行情撑全样本高 t、行情一过即失效"的伪稳健候选
> （防数据窥探/伪衰减）；样本不足以分段时自动放行不误杀。开关：`--seg_n 3 --seg_need 2`。
> 每代挖掘记录（诊断+B角建议）见 `docs/loop_journal.md`；每代 L2 费后明细流水（逐代累积、带 gen/cat/leaf 列，自 gen16 起）见 `docs/loop_archive.csv`；gen16 前旧快照已归 `history/loop_archive.legacy_pre_gen16.csv`。
> **本文件只收录入库因子**，预计每数十轮才 +1 个，文件不会膨胀；round 流水永不并入本文件。
>
> ⚠⚠ **口径警示（2026-09-15 加，源自外部独立审查 §1.24-④）**：**早期代（gen8~gen11）明细块里的「单期换手」可能是旧口径，与当前口径不可比** ✗
> · 实证：`F07`（gen11）本档写「单期换手 **4.9%**」，而外部按当前口径重测是 **11.9%**（**差 2.4 倍**）
> · 根因：`F07` 的明细块写着「费后明细指标：见 gen8 时代历史 journal/日志（**本档建立前未归档**）」⇒ 那条是**旧口径/旧数据** ✓
> · ⇒ ★ **做统计/排序/横向对比时，请排除或单独标注 gen8~gen11 的早期行** ✓
> · ✓ **精选池不受影响** —— 它用的是**新口径**（`docs/loop_strip_style_bank.csv` 的 `calmar/turn`）✓
>
> 当前 **46 个入库**（★ 2026-09-23 复核：all 池 `state.bank` = 45，全A 已跑至 **76** 代；**跨池合计 75**（all 45 · 300 5 · 500 12 · 1000 13 · 50 0），快照权威见 `docs/loop_todo.md §0`）。
> （下面按代次列的 gen8×1 / gen10×3 / … / gen51×1 是 2026-09-10 那次盘点，仅作历史对照 ✓）
> 运行期起：引擎在每代入库（`state.bank` append）时**自动同步追加**新因子条目（gen24 后的入库代次生效），家族/一句话命名随时可人工精炼覆盖。

---

## 因子总览

| 编号 | 入库代数 | 家族 | 一句话 | 状态 |
|---|---|---|---|---|
| F01 | gen8 | 换手-量联动波动 | turnover/turn_ratio×volume 双尺度波动 | 已入库 |
| F02 | gen10 | hl_ratio×换手稳定 族A | std20 × (hl_ratio×turn_ratio 长均) | 已入库 |
| F03 | gen10 | 换手波动叠加 | log(turnover) 波动 + turn_ratio 波动 | 已入库 ⚠️冗余① |
| F04 | gen10 | 换手/量波动组合 | turn_ratio 波动 + log(volume) 波动 | 已入库 ⚠️冗余① |
| F05 | gen11 | hl_ratio×换手稳定 族A | std60×mean5 窗口变体 | 已入库 ⚠️冗余② |
| F06 | gen11 | hl_ratio×换手稳定 族A | std150×mean100 窗口变体 | 已入库 |
| F07 | gen11 | hl_ratio×换手稳定 族A | std100×mean5 窗口变体 | 已入库 ⚠️冗余② |
| F08 | gen11 | hl_ratio×换手稳定 族A | std150×mean5 窗口变体 | 已入库 ⚠️冗余② |
| F09 | gen14 | 换手×量×价格 深度交叉 | 深度5、混入 mktcap/close/open | 已入库 |
| F10 | gen23 | 量价背离·影线强度综合 | corr100(up_shadow,ln_volume)/turnover，融合真实波幅/日内 对数合成 | 已入库 |
| F11 | gen23 | 日内强度密度 | hl_ratio/low × intraday² × ret（ts_mean60） | 已入库 |
| F12 | gen31 | 跳空、影线、财报、成交额 | div(ts_min100(corr100(overnight, ts_std60… | 已入库(auto) |
| F13 | gen33 | 风格、风格 | ts_delay1(add(barra_residual_volatility, … | 已入库(auto) |
| F14 | gen43 | 风格、量 | add(log(barra_non_linear_size), ts_std150… | 已入库(auto) |
| F15 | gen43 | 成交额、风格、风格、振幅 | ts_mean20(ts_mean60(sub(corr100(turnover,… | 已入库(auto) ⚠️冗余③ |
| F16 | gen43 | 成交额、风格、风格、振幅 | neg(ts_mean100(ts_mean60(sub(corr100(turn… | 已入库(auto) ⚠️冗余③ |
| F17 | gen45 | 财报、财报、风格、振幅 | add(ts_mean100(corr100(corr100(fa_ocf_yoy… | 已入库(auto) |
| F18 | gen45 | 财报、财报、风格、收益率 | add(ts_mean100(corr100(corr100(fa_ocf_yoy… | 已入库(auto) |
| F19 | gen45 | 资金流、量、资金流、风格 | max(ts_min20(cs_rank(div(mf_s_buy, ts_min… | 已入库(auto) |
| F20 | gen50 | 风格、财报、风格 | max(ts_mean120(cs_rank(div(barra_leverage… | 已入库(auto) ⚠️冗余④ |
| F21 | gen50 | 风格、风格、财报、财报 | max(add(barra_residual_volatility, barra_… | 已入库(auto) ⚠️冗余⑤ |
| F22 | gen50 | 财报、风格、风格 | max(ts_min20(cs_rank(add(fa_ocf_yoy, barr… | 已入库(auto) ⚠️冗余⑤ |
| F23 | gen50 | 风格、风格 | max(ts_min20(cs_rank(barra_leverage)), ba… | 已入库(auto) ⚠️冗余④ |
| F24 | gen51 | 风格、财报、资金流、风格、资金流、风格、… | min(sub(barra_non_linear_size, min(div(fa… | 已入库(auto) |
| F25 | gen52 | 风格、风格 | max(ts_mean150(corr100(ts_rank100(cs_rank… | 已入库(auto) |
| F26 | gen58 | 风格 | ts_delta120(barra_non_linear_size) | 已入库(auto) |
| F27 | gen58 | 资金流、振幅 | corr100(mf_m_sqty, hl_ratio) | 已入库(auto) |
| F28 | gen67 | 风格、风格、风格 | max(max(barra_residual_volatility, ts_ran… | 已入库(auto) |
| F29 | gen69 | 风格、风格、风格 | max(max(barra_residual_volatility, corr60… | 已入库(auto) |
| F30 | gen70 | 风格、风格、风格 | sub(mul(barra_residual_volatility, barra_… | 已入库(auto) |
| F31 | gen71 | 风格、风格、风格 | mul(max(barra_residual_volatility, ts_ran… | 已入库(auto) |
| F32 | gen71 | 风格、风格、风格、风格 | add(barra_residual_volatility, div(sub(ba… | 已入库(auto) |
| F33 | gen72 | 风格、风格、资金流 | ts_delta120(add(ts_max20(ts_max100(barra_… | 已入库(auto) |
| F34 | gen72 | 未分类 | div(max(barra_residual_volatility, ts_ran… | 已入库(auto) |
| F35 | gen74 | 振幅、资金流 | mul(ts_max20(max(max(barra_residual_volat… | 已入库(auto) |
| F36 | gen75 | 振幅、资金流 | ts_mean120(corr100(true_range, ts_delta20… | 已入库(auto) |
| F37 | gen75 | 资金流、振幅、资金流 | mul(ts_max20(ts_std200(mf_x_sqty)), corr1… | 已入库(auto) |
| F38 | gen75 | 资金流、资金流 | ts_mean120(corr20(cs_scale(mf_l_sqty), mf… | 已入库(auto) |
| F39 | gen75 | 资金流、资金流 | ts_mean150(corr20(ts_delta5(mf_l_sqty), m… | 已入库(auto) |
| F40 | gen75 | 资金流、资金流 | corr100(mf_l_bqty, mf_l_sell) | 已入库(auto) |
| F41 | gen75 | 振幅、资金流 | neg(corr100(true_range, mf_x_bqty)) | 已入库(auto) |
| F42 | gen0 | 外部基准 · 短周期价量 | neg(mul(cs_rank(ts_rank10(close)), cs_rank(sub(ts_delta10(close), ts_delta5(close))))) | 已移出(外部基准 · 不合格) |
| F43 | gen42 | 跳空、日内收益 | sub(ts_mean100(overnight), ts_mean100(int… | 已入库(auto) |
| F44 | gen68 | 风格、风格 | max(max(barra_residual_volatility, div(ba… | 已入库(auto) |
| F45 | gen71 | 风格、风格、财报 | max(max(barra_residual_volatility, div(ba… | 已入库(auto) |
| F46 | gen74 | 风格、风格 | add(max(barra_residual_volatility, div(ba… | 已入库(auto) |
| F47 | gen78 | 未分类 | ts_mean200(ts_std60(cs_demean(neg(low)))) | 已入库(auto) |

> 标记 `⚠️冗余①~⑤` = 库内近重复组成员（口径与明细见下方「库内冗余对清单」）；**每组按 1 个独立因子计**。

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
>
> ⚠️ **库内冗余对清单（2026-09-10 全库去重体检）**：对 `engine/loop_state.pkl` 的 bank 全 24 个因子实测
> （口径 = 引擎去重段 `rank_rows(v[::FWD])[::6]` 池化 \|corr\|），共 **6 对 ≥0.80**，全为 gen51 双闸门
> 上线前的历史遗留（体检脚本 `history/ai_test_20260915/bank_dup_check2.py`）：
>
> | 冗余组 | 成员 | 两两 \|corr\| | 建议保留 | 备注 |
> |---|---|---|---|---|
> | ① 换手/量波动族 | F03 · F04 | 0.905 | 二者其一 | gen10 同期入库，无历史指标留存 |
> | ② hl_ratio×turn_ratio 族A | F05 · F07 · F08 | 0.821 / 0.864 | 二者其一 | 同骨架仅换窗口（F02/F06 同骨架但 \|corr\|<0.80） |
> | ③ 风格波动族 | F15 · F16 | 0.874 | 二者其一 | F16 = `neg(...)` 与 F15 同内层 → 同一因子正反两向 |
> | ④ max(·,resvol)＋leverage | F20 · F23 | 0.932 | **F20** | gen50；F20 Calmar 0.907/Sharpe 1.415 优于 F23 0.532/1.042 |
> | ⑤ max(·,resvol)＋fa_ocf_yoy | F21 · F22 | 0.879 | **F21** | gen50；F21 Calmar 0.868/Sharpe 1.310 优于 F22 0.699/1.230 |
>
> **使用规则**：每个冗余组按 **1 个独立因子**计（组内任取其一，或等权合成）→ 该库**有效独立因子数 ≈ 18**
> （24 − 6）。未过线但接近：F01↔F04 0.798、F17↔F18 0.744。
> ⚠️ **F24（gen51）不属于任何冗余组**（最相似 F14 仅 0.587）；但 standard_test【6】显示其**剥成交额后
> 超额≈0** → 收益主要来自成交额**风格暴露**，独立性有限（属"风格暴露"问题，非"库内重复"）。
> **防复发**：上表 0.932/0.905/0.879/0.874/0.864 五对若在今天生成会被 `--dedup_corr 0.85` 拦下；
> 0.821 那对同骨架会被 FSA 冻结 / `bank_skel_max=1` 拦。


---

## 因子明细

### F01 · gen8 入库（第 1 个）
```
add(ts_std20(cs_demean(log(turnover))), ts_std60(cs_rank(cs_demean(add(mul(ret, ts_std20(volume)), log(cs_demean(turn_ratio)))))))
```
- **符号 `sign`：`-1`**（★ 因子值须乘它才是"越大越好"的方向；不乘 ⇒ 反向选股）
- 池标签：**`csi1000_all`** —— 全A + **1000** 池通过
  （全A 超额 +3.37% / Calmar +0.302；300 -7.76%；500 -5.50%；1000 +1.44%）
- 家族：换手-量联动波动（ret×volume 交互 + 换手双对数）
- 费后明细指标：见 gen8 时代历史 journal/日志（本档建立前未归档）

### F02 · gen10 入库
```
ts_std20(mul(cs_demean(hl_ratio), ts_mean100(cs_demean(turn_ratio))))
```
- **符号 `sign`：`-1`**（★ 因子值须乘它才是"越大越好"的方向；不乘 ⇒ 反向选股）
- 池标签：**`csi_all_only`** —— **只有全A通过** ⇒ 小盘/流动性溢价嫌疑，**指数增强不可用**
  （全A 超额 +2.19% / Calmar +0.318；300 -5.97%；500 -3.80%；1000 -0.06%）
- 家族 A：hl_ratio×turn_ratio 稳定度（F05~F08 同骨架）
- 备注：decorr 0.70 时代入库

### F03 · gen10 入库
```
add(ts_std60(cs_demean(log(turnover))), add(ts_sum20(cs_demean(ts_std20(cs_demean(log(turn_ratio))))), cs_demean(log(turnover))))
```
- **符号 `sign`：`-1`**（★ 因子值须乘它才是"越大越好"的方向；不乘 ⇒ 反向选股）
- 池标签：**`csi1000_all`** —— 全A + **1000** 池通过
  （全A 超额 +5.18% / Calmar +0.386；300 -4.85%；500 -4.74%；1000 +0.98%）
- 家族：换手波动叠加（turnover 60 波动 + turn_ratio 短期波动）

### F04 · gen10 入库
```
add(ts_sum20(ts_std20(cs_demean(log(turn_ratio)))), cs_demean(log(ts_mean5(ts_std20(volume)))))
```
- **符号 `sign`：`-1`**（★ 因子值须乘它才是"越大越好"的方向；不乘 ⇒ 反向选股）
- 池标签：**`csi1000_all`** —— 全A + **1000** 池通过
  （全A 超额 +4.02% / Calmar +0.484；300 -6.90%；500 -4.50%；1000 +1.23%）
- 家族：turn_ratio 波动 + volume 波动组合

### F05 · gen11 入库
```
ts_std60(mul(cs_demean(hl_ratio), ts_mean5(cs_demean(turn_ratio))))
```
- **符号 `sign`：`-1`**（★ 因子值须乘它才是"越大越好"的方向；不乘 ⇒ 反向选股）
- 池标签：**`csi500_1000_all`** —— 全A + **500/1000** 池通过
  （全A 超额 +4.86% / Calmar +0.589；300 -4.51%；500 +0.08%；1000 +5.86%）
- 家族 A 窗口变体（std60 / mean5）

### F06 · gen11 入库
```
ts_std150(mul(cs_demean(hl_ratio), ts_mean100(cs_demean(turn_ratio))))
```
- **符号 `sign`：`-1`**（★ 因子值须乘它才是"越大越好"的方向；不乘 ⇒ 反向选股）
- 池标签：**`csi500_1000_all`** —— 全A + **500/1000** 池通过
  （全A 超额 +3.62% / Calmar +1.146；300 -0.02%；500 +0.84%；1000 +4.08%）
- 家族 A 窗口变体（std150 / mean100）

### F07 · gen11 入库
```
ts_std100(mul(cs_demean(hl_ratio), ts_mean5(cs_demean(turn_ratio))))
```
- **符号 `sign`：`-1`**（★ 因子值须乘它才是"越大越好"的方向；不乘 ⇒ 反向选股）
- 池标签：**`csi500_1000_all`** —— 全A + **500/1000** 池通过
  （全A 超额 +5.38% / Calmar +0.709；300 -2.65%；500 +3.43%；1000 +6.11%）
- 家族 A 窗口变体（std100 / mean5）

### F08 · gen11 入库
```
ts_std150(mul(cs_demean(hl_ratio), ts_mean5(cs_demean(turn_ratio))))
```
- **符号 `sign`：`-1`**（★ 因子值须乘它才是"越大越好"的方向；不乘 ⇒ 反向选股）
- 池标签：**`csi500_1000_all`** —— 全A + **500/1000** 池通过
  （全A 超额 +3.78% / Calmar +0.506；300 -3.65%；500 +2.24%；1000 +3.13%）
- 家族 A 窗口变体（std150 / mean5）
- F05~F08 备注：decorr 0.70 拦不住同骨架换窗口（当时 bank 5/8 同骨架）→ 触发 Round24 FSA 冻结

### F09 · gen14 入库（2026-09-08 23:00）★最新
```
neg(log(ts_mean60(div(add(mul(mul(turn_ratio, ts_mean5(ts_std20(cs_rank(log(turnover))))), ts_std20(add(mul(turn_ratio, ts_mean5(ts_mean20(volume))), mul(turn_ratio, corr20(log(cs_demean(turn_ratio)), mktcap))))), close), ts_std60(cs_rank(open))))))
```
- **符号 `sign`：`1`**（★ 因子值须乘它才是"越大越好"的方向；不乘 ⇒ 反向选股）
- 池标签：**`csi300_1000_all`** —— 全A + **300/1000** 池通过
  （全A 超额 +8.02% / Calmar +0.806；300 +0.38%；500 -0.10%；1000 +3.38%）
- 家族：换手×量×价格 深度 5 交叉（不再是纯量/换手族窗口变体，混入 mktcap/close/open）
- 费后指标（full，成本 0.004）：IC 0.0484 / IC_IR 0.454 / 年化超额 +8.85% / 回撤 −9.7% /
  **Calmar 0.914 / Sharpe 1.256** / 最近年 +5.1% / 单期换手 15.7% / 负年 0
- 备注：n_pass=1 破连续 0 通过；同代 L2 其余 29 个仍 fail_calmar 100%（信号弱是主矛盾）

### F10 · gen23 入库（2026-09-09 补录，来源 state.bank/archive）
```
sub(add(sub(div(corr100(up_shadow, ln_volume), turnover), corr60(true_range, turn_ratio)), neg(log(corr100(amplitude, intraday)))), ln_volume)
```
- **符号 `sign`：`1`**（★ 因子值须乘它才是"越大越好"的方向；不乘 ⇒ 反向选股）
- 池标签：**`csi_all_only`** —— **只有全A通过** ⇒ 小盘/流动性溢价嫌疑，**指数增强不可用**
  （全A 超额 +5.30% / Calmar +0.459；300 -4.09%；500 -3.03%；1000 -0.57%）
- 家族：量价背离·影线强度综合（up_shadow 与 ln_volume 的 100 日相关 ÷ turnover，叠加真实波幅/换手/日内波幅的对数合成）
- 叶子：up_shadow、ln_volume、turnover、true_range、turn_ratio、amplitude、intraday
- 费后指标（full，成本 0.004）：IC 0.0637 / IC_IR 0.577 / 年化超额 +6.7% / 回撤 −10.7% / **Calmar 0.624 / Sharpe 0.989** / 最近年 +1.5% / 单期换手 27.1% / 负年 0
- 备注：gen23（8:25 手动中断前 L2 已跑完）入库，bank 9→10；收官文档封版于 gen22 故未收录，本次核对补录

### F11 · gen23 入库（2026-09-09 补录，来源 state.bank/archive）
```
ts_mean60(mul(div(hl_ratio, low), mul(mul(intraday, ret), intraday)))
```
- **符号 `sign`：`-1`**（★ 因子值须乘它才是"越大越好"的方向；不乘 ⇒ 反向选股）
- 池标签：**`csi1000_all`** —— 全A + **1000** 池通过
  （全A 超额 +5.11% / Calmar +0.405；300 -3.15%；500 -2.72%；1000 +0.29%）
- 家族：日内强度密度（隔夜区间相对低点 hl_ratio/low × 日内动量² × 收益，60 日均值）
- 叶子：hl_ratio、low、intraday、ret
- 费后指标（full，成本 0.004）：IC 0.0588 / IC_IR 0.569 / 年化超额 +6.4% / 回撤 −12.1% / **Calmar 0.528 / Sharpe 0.790** / 最近年 +2.9% / 单期换手 24.9% / 负年 2
- 备注：同代入库（bank 10→11）；构造明显区别于历史 9 只的"波动/换手稳定"族

---

### F12 · gen31 入库（引擎自动同步，家族命名待人工精炼）
```
div(ts_min100(corr100(overnight, ts_std60(div(corr100(up_shadow, div(fa_roe, turnover)), turnover)))), turnover)
```
- **符号 `sign`：`-1`**（★ 因子值须乘它才是"越大越好"的方向；不乘 ⇒ 反向选股）
- 家族：跳空、影线、财报、成交额（auto）
- 叶子：overnight、up_shadow、fa_roe、turnover
- 骨架：`div(ts_min(corr(overnight,ts_std(div(corr(up_shadow,div(fa_roe,turnover)),turnover)))),turnover)`
- 池标签：**`none`** —— 全不通过
  （全A 超额 +3.49% / Calmar +0.295；300 -8.10%；500 -6.54%；1000 -1.95%）
- 费后指标（full，成本 4bp/边）：IC 0.0607 / IC_IR 0.586 / 年化超额 +5.3% / 回撤 -9.2% / Calmar 0.576 / Sharpe 0.794 / 最近年 +0.7% / 单期换手 35.7% / 负年 2

---


### F13 · gen33 入库（引擎自动同步，家族命名待人工精炼）
```
ts_delay1(add(barra_residual_volatility, barra_non_linear_size))
```
- **符号 `sign`：`-1`**（★ 因子值须乘它才是"越大越好"的方向；不乘 ⇒ 反向选股）
- 家族：风格、风格（auto）
- 叶子：barra_residual_volatility、barra_non_linear_size
- 骨架：`ts_delay(add(barra_residual_volatility,barra_non_linear_size))`
- 池标签：**`csi1000_all`** —— 全A + **1000** 池通过
  （全A 超额 +13.99% / Calmar +0.713；300 -2.61%；500 -2.01%；1000 +5.63%）
- 费后指标（full，成本 4bp/边）：IC 0.0743 / IC_IR 0.627 / 年化超额 +14.7% / 回撤 -19.5% / Calmar 0.750 / Sharpe 1.460 / 最近年 +3.7% / 单期换手 12.0% / 负年 1

---


### F14 · gen43 入库（引擎自动同步，家族命名待人工精炼）
```
add(log(barra_non_linear_size), ts_std150(ts_delay1(ts_sum20(ln_volume))))
```
- **符号 `sign`：`-1`**（★ 因子值须乘它才是"越大越好"的方向；不乘 ⇒ 反向选股）
- 家族：风格、量（auto）
- 叶子：barra_non_linear_size、ln_volume
- 骨架：`add(log(barra_non_linear_size),ts_std(ts_delay(ts_sum(ln_volume))))`
- 池标签：**`csi300_1000_all`** —— 全A + **300/1000** 池通过
  （全A 超额 +4.30% / Calmar +0.439；300 +1.57%；500 -0.18%；1000 +3.40%）
- 费后指标（full，成本 4bp/边）：IC 0.0390 / IC_IR 0.446 / 年化超额 +4.8% / 回撤 -9.4% / Calmar 0.507 / Sharpe 0.849 / 最近年 +3.6% / 单期换手 9.5% / 负年 1

### F15 · gen43 入库（引擎自动同步，家族命名待人工精炼）
```
ts_mean20(ts_mean60(sub(corr100(turnover, barra_non_linear_size), sub(barra_residual_volatility, true_range))))
```
- **符号 `sign`：`1`**（★ 因子值须乘它才是"越大越好"的方向；不乘 ⇒ 反向选股）
- 家族：成交额、风格、风格、振幅（auto）
- 叶子：turnover、barra_non_linear_size、barra_residual_volatility、true_range
- 骨架：`ts_mean(ts_mean(sub(corr(turnover,barra_non_linear_size),sub(barra_residual_volatility,true_range))))`
- 池标签：**`csi1000_all`** —— 全A + **1000** 池通过
  （全A 超额 +4.73% / Calmar +0.455；300 -3.33%；500 -1.67%；1000 +4.31%）
- 费后指标（full，成本 4bp/边）：IC 0.0430 / IC_IR 0.412 / 年化超额 +5.2% / 回撤 -10.2% / Calmar 0.507 / Sharpe 0.902 / 最近年 +1.7% / 单期换手 8.3% / 负年 2

### F16 · gen43 入库（引擎自动同步，家族命名待人工精炼）
```
neg(ts_mean100(ts_mean60(sub(corr100(turnover, barra_non_linear_size), sub(barra_residual_volatility, true_range)))))
```
- **符号 `sign`：`-1`**（★ 因子值须乘它才是"越大越好"的方向；不乘 ⇒ 反向选股）
- 家族：成交额、风格、风格、振幅（auto）
- 叶子：turnover、barra_non_linear_size、barra_residual_volatility、true_range
- 骨架：`neg(ts_mean(ts_mean(sub(corr(turnover,barra_non_linear_size),sub(barra_residual_volatility,true_range)))))`
- 池标签：**`csi500_1000_all`** —— 全A + **500/1000** 池通过
  （全A 超额 +5.43% / Calmar +0.663；300 -1.22%；500 +0.45%；1000 +3.44%）
- 费后指标（full，成本 4bp/边）：IC 0.0377 / IC_IR 0.382 / 年化超额 +5.7% / 回撤 -8.0% / Calmar 0.720 / Sharpe 1.018 / 最近年 +3.5% / 单期换手 6.2% / 负年 0

---


### F17 · gen45 入库（引擎自动同步，家族命名待人工精炼）
```
add(ts_mean100(corr100(corr100(fa_ocf_yoy, fa_gm), barra_residual_volatility)), max(ts_rank200(ts_max100(amplitude)), barra_residual_volatility))
```
- **符号 `sign`：`-1`**（★ 因子值须乘它才是"越大越好"的方向；不乘 ⇒ 反向选股）
- 家族：财报、财报、风格、振幅（auto）
- 叶子：fa_ocf_yoy、fa_gm、barra_residual_volatility、amplitude
- 骨架：`add(ts_mean(corr(corr(fa_ocf_yoy,fa_gm),barra_residual_volatility)),max(ts_rank(ts_max(amplitude)),barra_residual_volatility))`
- 池标签：**`csi300_1000_all`** —— 全A + **300/1000** 池通过
  （全A 超额 +3.46% / Calmar +0.710；300 +1.39%；500 -2.47%；1000 +4.64%）
- 费后指标（full，成本 4bp/边）：IC 0.0528 / IC_IR 0.641 / 年化超额 +4.1% / 回撤 -4.7% / Calmar 0.874 / Sharpe 0.959 / 最近年 +1.7% / 单期换手 12.9% / 负年 1

### F18 · gen45 入库（引擎自动同步，家族命名待人工精炼）
```
add(ts_mean100(corr100(corr100(fa_ocf_yoy, fa_gm), add(barra_residual_volatility, fa_ocf_yoy))), max(ret, barra_residual_volatility))
```
- **符号 `sign`：`-1`**（★ 因子值须乘它才是"越大越好"的方向；不乘 ⇒ 反向选股）
- 家族：财报、财报、风格、收益率（auto）
- 叶子：fa_ocf_yoy、fa_gm、barra_residual_volatility、ret
- 骨架：`add(ts_mean(corr(corr(fa_ocf_yoy,fa_gm),add(barra_residual_volatility,fa_ocf_yoy))),max(ret,barra_residual_volatility))`
- 池标签：**`csi500_1000_all`** —— 全A + **500/1000** 池通过
  （全A 超额 +2.89% / Calmar +0.434；300 -1.89%；500 +1.57%；1000 +2.41%）
- 费后指标（full，成本 4bp/边）：IC 0.0531 / IC_IR 0.603 / 年化超额 +3.5% / 回撤 -6.2% / Calmar 0.568 / Sharpe 0.959 / 最近年 +6.3% / 单期换手 13.0% / 负年 1

### F19 · gen45 入库（引擎自动同步，家族命名待人工精炼）
```
max(ts_min20(cs_rank(div(mf_s_buy, ts_min20(ts_std200(corr200(ln_volume, mf_s_bqty)))))), barra_residual_volatility)
```
- **符号 `sign`：`-1`**（★ 因子值须乘它才是"越大越好"的方向；不乘 ⇒ 反向选股）
- 家族：资金流、量、资金流、风格（auto）
- 叶子：mf_s_buy、ln_volume、mf_s_bqty、barra_residual_volatility
- 骨架：`max(ts_min(cs_rank(div(mf_s_buy,ts_min(ts_std(corr(ln_volume,mf_s_bqty)))))),barra_residual_volatility)`
- 池标签：**`csi1000_all`** —— 全A + **1000** 池通过
  （全A 超额 +4.20% / Calmar +0.509；300 -4.62%；500 -2.32%；1000 +1.06%）
- 费后指标（full，成本 4bp/边）：IC 0.0644 / IC_IR 0.576 / 年化超额 +5.0% / 回撤 -7.7% / Calmar 0.643 / Sharpe 0.894 / 最近年 +3.6% / 单期换手 15.4% / 负年 2

---


### F20 · gen50 入库（引擎自动同步，家族命名待人工精炼）
```
max(ts_mean120(cs_rank(div(barra_leverage, fa_gm))), barra_residual_volatility)
```
- **符号 `sign`：`-1`**（★ 因子值须乘它才是"越大越好"的方向；不乘 ⇒ 反向选股）
- 家族：风格、财报、风格（auto）
- 叶子：barra_leverage、fa_gm、barra_residual_volatility
- 骨架：`max(ts_mean(cs_rank(div(barra_leverage,fa_gm))),barra_residual_volatility)`
- 池标签：**`csi500_1000_all`** —— 全A + **500/1000** 池通过
  （全A 超额 +6.15% / Calmar +0.826；300 -3.24%；500 +0.17%；1000 +3.59%）
- 费后指标（full，成本 4bp/边）：IC 0.0562 / IC_IR 0.707 / 年化超额 +6.7% / 回撤 -7.4% / Calmar 0.907 / Sharpe 1.415 / 最近年 +2.7% / 单期换手 10.2% / 负年 1

### F21 · gen50 入库（引擎自动同步，家族命名待人工精炼）
```
max(add(barra_residual_volatility, barra_leverage), max(ts_min20(cs_rank(div(fa_ocf_yoy, fa_gm))), barra_residual_volatility))
```
- **符号 `sign`：`-1`**（★ 因子值须乘它才是"越大越好"的方向；不乘 ⇒ 反向选股）
- 家族：风格、风格、财报、财报（auto）
- 叶子：barra_residual_volatility、barra_leverage、fa_ocf_yoy、fa_gm
- 骨架：`max(add(barra_residual_volatility,barra_leverage),max(ts_min(cs_rank(div(fa_ocf_yoy,fa_gm))),barra_residual_volatility))`
- 池标签：**`csi500_1000_all`** —— 全A + **500/1000** 池通过
  （全A 超额 +4.85% / Calmar +0.731；300 -5.19%；500 +0.60%；1000 +1.93%）
- 费后指标（full，成本 4bp/边）：IC 0.0525 / IC_IR 0.708 / 年化超额 +5.5% / 回撤 -6.4% / Calmar 0.868 / Sharpe 1.310 / 最近年 +0.4% / 单期换手 13.2% / 负年 0

### F22 · gen50 入库（引擎自动同步，家族命名待人工精炼）
```
max(ts_min20(cs_rank(add(fa_ocf_yoy, barra_leverage))), barra_residual_volatility)
```
- **符号 `sign`：`-1`**（★ 因子值须乘它才是"越大越好"的方向；不乘 ⇒ 反向选股）
- 家族：财报、风格、风格（auto）
- 叶子：fa_ocf_yoy、barra_leverage、barra_residual_volatility
- 骨架：`max(ts_min(cs_rank(add(fa_ocf_yoy,barra_leverage))),barra_residual_volatility)`
- 池标签：**`csi1000_all`** —— 全A + **1000** 池通过
  （全A 超额 +4.15% / Calmar +0.577；300 -3.24%；500 -2.20%；1000 +1.83%）
- 费后指标（full，成本 4bp/边）：IC 0.0527 / IC_IR 0.689 / 年化超额 +4.8% / 回撤 -6.9% / Calmar 0.699 / Sharpe 1.230 / 最近年 +0.8% / 单期换手 13.2% / 负年 0

### F23 · gen50 入库（引擎自动同步，家族命名待人工精炼）
```
max(ts_min20(cs_rank(barra_leverage)), barra_residual_volatility)
```
- **符号 `sign`：`-1`**（★ 因子值须乘它才是"越大越好"的方向；不乘 ⇒ 反向选股）
- 家族：风格、风格（auto）
- 叶子：barra_leverage、barra_residual_volatility
- 骨架：`max(ts_min(cs_rank(barra_leverage)),barra_residual_volatility)`
- 池标签：**`csi500_1000_all`** —— 全A + **500/1000** 池通过
  （全A 超额 +4.23% / Calmar +0.464；300 -2.00%；500 +0.60%；1000 +3.11%）
- 费后指标（full，成本 4bp/边）：IC 0.0535 / IC_IR 0.653 / 年化超额 +4.8% / 回撤 -8.9% / Calmar 0.532 / Sharpe 1.042 / 最近年 +2.9% / 单期换手 10.2% / 负年 1

---


### F24 · gen51 入库（引擎自动同步，家族命名待人工精炼）
```
min(sub(barra_non_linear_size, min(div(fa_ocf_yoy, mf_s_bqty), ts_max100(barra_growth))), min(ts_mean5(corr100(mf_s_sqty, barra_liquidity)), ts_rank100(corr200(mf_m_bqty, barra_momentum))))
```
- **符号 `sign`：`-1`**（★ 因子值须乘它才是"越大越好"的方向；不乘 ⇒ 反向选股）
- 家族：风格、财报、资金流、风格、资金流、风格、…（auto）
- 叶子：barra_non_linear_size、fa_ocf_yoy、mf_s_bqty、barra_growth、mf_s_sqty、barra_liquidity、mf_m_bqty、barra_momentum
- 骨架：`min(sub(barra_non_linear_size,min(div(fa_ocf_yoy,mf_s_bqty),ts_max(barra_growth))),min(ts_mean(corr(mf_s_sqty,barra_liquidity)),ts_rank(corr(mf_m_bqty,barra_momentum))))`
- 池标签：**`csi_all_only`** —— **只有全A通过** ⇒ 小盘/流动性溢价嫌疑，**指数增强不可用**
  （全A 超额 +14.30% / Calmar +0.724；300 -3.67%；500 -4.91%；1000 -0.21%）
- 费后指标（full，成本 4bp/边）：IC 0.0333 / IC_IR 0.371 / 年化超额 +14.8% / 回撤 -19.7% / Calmar 0.751 / Sharpe 1.312 / 最近年 +3.6% / 单期换手 9.3% / 负年 0

---


### F25 · gen52 入库（引擎自动同步，家族命名待人工精炼）
```
max(ts_mean150(corr100(ts_rank100(cs_rank(barra_leverage)), ts_min20(cs_rank(barra_leverage)))), barra_residual_volatility)
```
- **符号 `sign`：`-1`**（★ 因子值须乘它才是"越大越好"的方向；不乘 ⇒ 反向选股）
- 家族：风格、风格（auto）
- 叶子：barra_leverage、barra_residual_volatility
- 骨架：`max(ts_mean(corr(ts_rank(cs_rank(barra_leverage)),ts_min(cs_rank(barra_leverage)))),barra_residual_volatility)`
- 池标签：**`csi500_1000_all`** —— 全A + **500/1000** 池通过
  （全A 超额 +4.94% / Calmar +1.129；300 -2.69%；500 +0.80%；1000 +3.41%）
- 费后指标（full，成本 4bp/边）：IC 0.0548 / IC_IR 0.631 / 年化超额 +5.6% / 回撤 -4.3% / Calmar 1.295 / Sharpe 1.581 / 最近年 +7.0% / 单期换手 12.4% / 负年 1

---


### F26 · gen58 入库（引擎自动同步，家族命名待人工精炼）
```
ts_delta120(barra_non_linear_size)
```
- **符号 `sign`：`-1`**（★ 因子值须乘它才是"越大越好"的方向；不乘 ⇒ 反向选股）
- 家族：风格（auto）
- 叶子：barra_non_linear_size
- 骨架：`ts_delta(barra_non_linear_size)`
- 池标签：**`csi_all_only`** —— **只有全A通过** ⇒ 小盘/流动性溢价嫌疑，**指数增强不可用**
  （全A 超额 +7.14% / Calmar +0.497；300 -2.40%；500 -8.07%；1000 -0.53%）
- 费后指标（full，成本 4bp/边）：IC 0.0394 / IC_IR 0.466 / 年化超额 +8.3% / 回撤 -12.8% / Calmar 0.652 / Sharpe 0.908 / 最近年 +3.0% / 单期换手 22.8% / 负年 1

### F27 · gen58 入库（引擎自动同步，家族命名待人工精炼）
```
corr100(mf_m_sqty, hl_ratio)
```
- **符号 `sign`：`-1`**（★ 因子值须乘它才是"越大越好"的方向；不乘 ⇒ 反向选股）
- 家族：资金流、振幅（auto）
- 叶子：mf_m_sqty、hl_ratio
- 骨架：`corr(mf_m_sqty,hl_ratio)`
- 池标签：**`csi500_1000_all`** —— 全A + **500/1000** 池通过
  （全A 超额 +3.27% / Calmar +0.440；300 -3.15%；500 +1.33%；1000 +0.87%）
- 费后指标（full，成本 4bp/边）：IC 0.0309 / IC_IR 0.407 / 年化超额 +4.2% / 回撤 -6.9% / Calmar 0.618 / Sharpe 0.803 / 最近年 +5.9% / 单期换手 19.1% / 负年 1

---


### F28 · gen67 入库（引擎自动同步，家族命名待人工精炼）
```
max(max(barra_residual_volatility, ts_rank60(cs_scale(ts_std200(barra_residual_volatility)))), sub(barra_non_linear_size, barra_liquidity))
```
- **符号 `sign`：`-1`**（★ 因子值须乘它才是"越大越好"的方向；不乘 ⇒ 反向选股）
- 家族：风格、风格、风格（auto）
- 叶子：barra_residual_volatility、barra_non_linear_size、barra_liquidity
- 骨架：`max(max(barra_residual_volatility,ts_rank(cs_scale(ts_std(barra_residual_volatility)))),sub(barra_non_linear_size,barra_liquidity))`
- 池标签：**`csi1000_all`** —— 全A + **1000** 池通过
  （全A 超额 +4.60% / Calmar +0.459；300 -4.15%；500 -2.35%；1000 +2.69%）
- 费后指标（full，成本 4bp/边）：IC 0.0460 / IC_IR 0.708 / 年化超额 +5.9% / 回撤 -9.9% / Calmar 0.592 / Sharpe 1.344 / 最近年 +2.7% / 单期换手 24.5% / 负年 2

---


### F29 · gen69 入库（引擎自动同步，家族命名待人工精炼）
```
max(max(barra_residual_volatility, corr60(barra_residual_volatility, barra_liquidity)), barra_non_linear_size)
```
- **符号 `sign`：`-1`**（★ 因子值须乘它才是"越大越好"的方向；不乘 ⇒ 反向选股）
- 家族：风格、风格、风格（auto）
- 叶子：barra_residual_volatility、barra_liquidity、barra_non_linear_size
- 骨架：`max(max(barra_residual_volatility,corr(barra_residual_volatility,barra_liquidity)),barra_non_linear_size)`
- 池标签：**`csi1000_all`** —— 全A + **1000** 池通过
  （全A 超额 +3.07% / Calmar +0.384；300 -3.67%；500 -2.31%；1000 +5.49%）
- 费后指标（full，成本 4bp/边）：IC 0.0519 / IC_IR 0.651 / 年化超额 +4.1% / 回撤 -7.8% / Calmar 0.529 / Sharpe 0.807 / 最近年 +6.3% / 单期换手 21.2% / 负年 2

---


### F30 · gen70 入库（引擎自动同步，家族命名待人工精炼）
```
sub(mul(barra_residual_volatility, barra_liquidity), corr100(barra_non_linear_size, abs(max(barra_residual_volatility, barra_liquidity))))
```
- **符号 `sign`：`-1`**（★ 因子值须乘它才是"越大越好"的方向；不乘 ⇒ 反向选股）
- 家族：风格、风格、风格（auto）
- 叶子：barra_residual_volatility、barra_liquidity、barra_non_linear_size
- 骨架：`sub(mul(barra_residual_volatility,barra_liquidity),corr(barra_non_linear_size,abs(max(barra_residual_volatility,barra_liquidity))))`
- 池标签：**`csi1000_all`** —— 全A + **1000** 池通过
  （全A 超额 +4.25% / Calmar +0.426；300 -4.64%；500 -2.87%；1000 +3.96%）
- 费后指标（full，成本 4bp/边）：IC 0.0538 / IC_IR 0.622 / 年化超额 +5.1% / 回撤 -9.7% / Calmar 0.527 / Sharpe 0.984 / 最近年 +0.6% / 单期换手 16.9% / 负年 1

---


### F31 · gen71 入库（引擎自动同步，家族命名待人工精炼）
```
mul(max(barra_residual_volatility, ts_rank60(ts_std200(cs_rank(barra_non_linear_size)))), max(barra_residual_volatility, div(min(barra_non_linear_size, barra_liquidity), barra_liquidity)))
```
- **符号 `sign`：`-1`**（★ 因子值须乘它才是"越大越好"的方向；不乘 ⇒ 反向选股）
- 家族：风格、风格、风格（auto）
- 叶子：barra_residual_volatility、barra_non_linear_size、barra_liquidity
- 骨架：`mul(max(barra_residual_volatility,ts_rank(ts_std(cs_rank(barra_non_linear_size)))),max(barra_residual_volatility,div(min(barra_non_linear_size,barra_liquidity),barra_liquidity)))`
- 池标签：**`csi1000_all`** —— 全A + **1000** 池通过
  （全A 超额 +7.01% / Calmar +0.442；300 -7.41%；500 -3.08%；1000 +1.43%）
- 费后指标（full，成本 0.004往返(主用档)）：IC 0.0583 / IC_IR 0.718 / 年化超额 +8.1% / 回撤 -15.6% / Calmar 0.519 / Sharpe 1.258 / 最近年 +1.2% / 单期换手 20.8% / 负年 1

### F32 · gen71 入库（引擎自动同步，家族命名待人工精炼）
```
add(barra_residual_volatility, div(sub(barra_non_linear_size, barra_comovement), barra_liquidity))
```
- **符号 `sign`：`-1`**（★ 因子值须乘它才是"越大越好"的方向；不乘 ⇒ 反向选股）
- 家族：风格、风格、风格、风格（auto）
- 叶子：barra_residual_volatility、barra_non_linear_size、barra_comovement、barra_liquidity
- 骨架：`add(barra_residual_volatility,div(sub(barra_non_linear_size,barra_comovement),barra_liquidity))`
- 池标签：**`csi1000_all`** —— 全A + **1000** 池通过
  （全A 超额 +6.96% / Calmar +0.725；300 -5.30%；500 -1.96%；1000 +1.79%）
- 费后指标（full，成本 0.004往返(主用档)）：IC 0.0588 / IC_IR 0.700 / 年化超额 +8.0% / 回撤 -9.4% / Calmar 0.851 / Sharpe 1.261 / 最近年 +1.4% / 单期换手 19.9% / 负年 1

---


### F33 · gen72 入库（引擎自动同步，家族命名待人工精炼）
```
ts_delta120(add(ts_max20(ts_max100(barra_non_linear_size)), div(cs_rank(barra_beta), ts_std150(mf_x_bqty))))
```
- **符号 `sign`：`-1`**（★ 因子值须乘它才是"越大越好"的方向；不乘 ⇒ 反向选股）
- 家族：风格、风格、资金流（auto）
- 叶子：barra_non_linear_size、barra_beta、mf_x_bqty
- 骨架：`ts_delta(add(ts_max(ts_max(barra_non_linear_size)),div(cs_rank(barra_beta),ts_std(mf_x_bqty))))`
- 池标签：**`csi300_1000_all`** —— 全A + **300/1000** 池通过
  （全A 超额 +10.73% / Calmar +0.806；300 +0.55%；500 -0.34%；1000 +4.45%）
- 费后指标（full，成本 0.004往返(主用档)）：IC 0.0270 / IC_IR 0.383 / 年化超额 +11.3% / 回撤 -13.3% / Calmar 0.847 / Sharpe 1.266 / 最近年 +1.8% / 单期换手 9.7% / 负年 1

### F34 · gen72 入库（引擎自动同步，家族命名待人工精炼）
```
div(max(barra_residual_volatility, ts_rank60(ts_std200(cs_rank(barra_non_linear_size)))), max(barra_residual_volatility, div(min(barra_non_linear_size, barra_liquidity), barra_liquidity)))
```
- **符号 `sign`：`-1`**（★ 因子值须乘它才是"越大越好"的方向；不乘 ⇒ 反向选股）
- 家族：未分类（auto）
- 叶子：
- 骨架：`div(max(barra_residual_volatility, ts_rank60(ts_std200(cs_rank(barra_non_linear_size)))),max(barra_residual_volatility, div(min(barra_non_linear_size, barra_liquidity), barra_liquidity)))`
- 池标签：**`csi1000_all`** —— 全A + **1000** 池通过
  （全A 超额 +6.93% / Calmar +0.453；300 -8.33%；500 -2.67%；1000 +1.52%）
- 费后指标（full，成本 0.004往返(主用档)）：IC 0.0387 / IC_IR 0.498 / 年化超额 +8.1% / 回撤 -15.0% / Calmar 0.537 / Sharpe 1.332 / 最近年 +2.5% / 单期换手 21.7% / 负年 1

---


### F35 · gen74 入库（引擎自动同步，家族命名待人工精炼）
```
mul(ts_max20(max(max(barra_residual_volatility, div(barra_residual_volatility, barra_liquidity)), ts_rank60(cs_scale(ts_std100(barra_residual_volatility))))), corr100(true_range, mf_m_buy))
```
- **符号 `sign`：`-1`**（★ 因子值须乘它才是"越大越好"的方向；不乘 ⇒ 反向选股）
- 家族：振幅、资金流（auto）
- 叶子：true_range、mf_m_buy
- 骨架：`mul(ts_max(max(max(barra_residual_volatility, div(barra_residual_volatility, barra_liquidity)),ts_rank60(cs_scale(ts_std100(barra_residual_volatility))))),corr(true_range,mf_m_buy))`
- 池标签：**`csi500_1000_all`** —— 全A + **500/1000** 池通过
  （全A 超额 +3.60% / Calmar +0.800；300 -4.72%；500 +1.06%；1000 +1.88%）
- 费后指标（full，成本 0.004往返(主用档)）：IC 0.0368 / IC_IR 0.643 / 年化超额 +4.6% / 回撤 -4.3% / Calmar 1.077 / Sharpe 1.063 / 最近年 +5.0% / 单期换手 20.0% / 负年 0

---


### F36 · gen75 入库（引擎自动同步，家族命名待人工精炼）
```
ts_mean120(corr100(true_range, ts_delta20(mf_l_buy)))
```
- **符号 `sign`：`-1`**（★ 因子值须乘它才是"越大越好"的方向；不乘 ⇒ 反向选股）
- 家族：振幅、资金流（auto）
- 叶子：true_range、mf_l_buy
- 骨架：`ts_mean(corr(true_range,ts_delta(mf_l_buy)))`
- 池标签：**`csi500_1000_all`** —— 全A + **500/1000** 池通过
  （全A 超额 +4.19% / Calmar +0.629；300 -2.33%；500 +1.63%；1000 +3.89%）
- 费后指标（full，成本 0.004往返(主用档)）：IC 0.0217 / IC_IR 0.296 / 年化超额 +4.6% / 回撤 -5.9% / Calmar 0.777 / Sharpe 0.915 / 最近年 +2.7% / 单期换手 8.4% / 负年 2

### F37 · gen75 入库（引擎自动同步，家族命名待人工精炼）
```
mul(ts_max20(ts_std200(mf_x_sqty)), corr100(true_range, mf_m_buy))
```
- **符号 `sign`：`-1`**（★ 因子值须乘它才是"越大越好"的方向；不乘 ⇒ 反向选股）
- 家族：资金流、振幅、资金流（auto）
- 叶子：mf_x_sqty、true_range、mf_m_buy
- 骨架：`mul(ts_max(ts_std(mf_x_sqty)),corr(true_range,mf_m_buy))`
- 池标签：**`csi500_all`** —— 全A + **500** 池通过
  （全A 超额 +5.96% / Calmar +0.622；300 -3.84%；500 +0.52%；1000 -0.64%）
- 费后指标（full，成本 0.004往返(主用档)）：IC 0.0277 / IC_IR 0.242 / 年化超额 +6.3% / 回撤 -9.3% / Calmar 0.684 / Sharpe 0.944 / 最近年 +5.7% / 单期换手 7.5% / 负年 1

### F38 · gen75 入库（引擎自动同步，家族命名待人工精炼）
```
ts_mean120(corr20(cs_scale(mf_l_sqty), mf_s_sqty))
```
- **符号 `sign`：`-1`**（★ 因子值须乘它才是"越大越好"的方向；不乘 ⇒ 反向选股）
- 家族：资金流、资金流（auto）
- 叶子：mf_l_sqty、mf_s_sqty
- 骨架：`ts_mean(corr(cs_scale(mf_l_sqty),mf_s_sqty))`
- 池标签：**`csi300_1000_all`** —— 全A + **300/1000** 池通过
  （全A 超额 +4.86% / Calmar +0.572；300 +0.76%；500 -1.44%；1000 +1.20%）
- 费后指标（full，成本 0.004往返(主用档)）：IC 0.0391 / IC_IR 0.372 / 年化超额 +5.3% / 回撤 -8.4% / Calmar 0.633 / Sharpe 0.846 / 最近年 +5.3% / 单期换手 9.5% / 负年 1

### F39 · gen75 入库（引擎自动同步，家族命名待人工精炼）
```
ts_mean150(corr20(ts_delta5(mf_l_sqty), mf_s_sqty))
```
- **符号 `sign`：`-1`**（★ 因子值须乘它才是"越大越好"的方向；不乘 ⇒ 反向选股）
- 家族：资金流、资金流（auto）
- 叶子：mf_l_sqty、mf_s_sqty
- 骨架：`ts_mean(corr(ts_delta(mf_l_sqty),mf_s_sqty))`
- 池标签：**`csi300_1000_all`** —— 全A + **300/1000** 池通过
  （全A 超额 +3.66% / Calmar +0.437；300 +0.64%；500 -0.63%；1000 +0.33%）
- 费后指标（full，成本 0.004往返(主用档)）：IC 0.0314 / IC_IR 0.354 / 年化超额 +4.2% / 回撤 -8.0% / Calmar 0.524 / Sharpe 0.718 / 最近年 +5.5% / 单期换手 10.3% / 负年 2

### F40 · gen75 入库（引擎自动同步，家族命名待人工精炼）
```
corr100(mf_l_bqty, mf_l_sell)
```
- **符号 `sign`：`-1`**（★ 因子值须乘它才是"越大越好"的方向；不乘 ⇒ 反向选股）
- 家族：资金流、资金流（auto）
- 叶子：mf_l_bqty、mf_l_sell
- 骨架：`corr(mf_l_bqty,mf_l_sell)`
- 池标签：**`all3`** —— 全A **且所有池都通过**（真 alpha）
  （全A 超额 +7.29% / Calmar +1.162；300 +3.10%；500 +0.17%；1000 +4.35%）
- 费后指标（full，成本 0.004往返(主用档)）：IC 0.0423 / IC_IR 0.460 / 年化超额 +8.1% / 回撤 -6.0% / Calmar 1.349 / Sharpe 1.273 / 最近年 +4.3% / 单期换手 15.7% / 负年 1

### F41 · gen75 入库（引擎自动同步，家族命名待人工精炼）
```
neg(corr100(true_range, mf_x_bqty))
```
- **符号 `sign`：`1`**（★ 因子值须乘它才是"越大越好"的方向；不乘 ⇒ 反向选股）
- 家族：振幅、资金流（auto）
- 叶子：true_range、mf_x_bqty
- 骨架：`neg(corr(true_range,mf_x_bqty))`
- 池标签：**`csi1000_all`** —— 全A + **1000** 池通过
  （全A 超额 +5.44% / Calmar +0.464；300 -2.32%；500 -2.27%；1000 +1.03%）
- 费后指标（full，成本 0.004往返(主用档)）：IC 0.0421 / IC_IR 0.460 / 年化超额 +6.2% / 回撤 -11.5% / Calmar 0.544 / Sharpe 0.909 / 最近年 +0.5% / 单期换手 15.5% / 负年 0

---


### F43 · gen42 入库（引擎自动同步，家族命名待人工精炼）
```
sub(ts_mean100(overnight), ts_mean100(intraday))
```
- **符号 `sign`：`1`**（★ 因子值须乘它才是"越大越好"的方向；不乘 ⇒ 反向选股）
- 家族：跳空、日内收益（auto）
- 叶子：overnight、intraday
- 骨架：`sub(ts_mean(overnight),ts_mean(intraday))`
- 池标签：**`csi1000_all`** —— 全A + **1000** 池通过
- 剥风格：**`A`** 独立有效（剥风格后**日频** Calmar >= 0.30，且**日频**回撤 > -0.20）（原 Calmar 0.893 → 剥后 0.483；超额 +6.4% → +4.2%；**日频** 剥后 Calmar 0.380，日频回撤 -11.2%）
- 口径：**20 日调仓** ✓（期数 104；成本 0.004往返(主用档)）★ 与 5 日口径的数字**不可直接比** ✗（样本区间/成本相同，只有调仓周期不同 ✓）
- 费后指标（full，成本 0.004往返(主用档)）：IC 0.0777 / IC_IR 0.764 / 年化超额 +6.4% / 回撤 -7.2% / Calmar 0.893 / Sharpe 1.027 / 最近年 +4.2% / 单期换手 41.2% / 负年 0

---


### F44 · gen68 入库（引擎自动同步，家族命名待人工精炼）
```
max(max(barra_residual_volatility, div(barra_residual_volatility, barra_liquidity)), ts_rank60(cs_scale(ts_std100(barra_residual_volatility))))
```
- **符号 `sign`：`-1`**（★ 因子值须乘它才是"越大越好"的方向；不乘 ⇒ 反向选股）
- 家族：风格、风格（auto）
- 叶子：barra_residual_volatility、barra_liquidity
- 骨架：`max(max(barra_residual_volatility,div(barra_residual_volatility,barra_liquidity)),ts_rank(cs_scale(ts_std(barra_residual_volatility))))`
- 池标签：**`csi1000_all`** —— 全A + **1000** 池通过
- 剥风格：**`B`** 弱独立（剥风格后日频 Calmar 在 0~0.30，或回撤劣于 -0.20）（原 Calmar 1.709 → 剥后 0.301；超额 +4.6% → +1.9%；**日频** 剥后 Calmar 0.255，日频回撤 -7.5%）
- 口径：**20 日调仓** ✓（期数 104；成本 0.004往返(主用档)）★ 与 5 日口径的数字**不可直接比** ✗（样本区间/成本相同，只有调仓周期不同 ✓）
- 费后指标（full，成本 0.004往返(主用档)）：IC 0.0552 / IC_IR 0.884 / 年化超额 +4.6% / 回撤 -2.7% / Calmar 1.709 / Sharpe 1.104 / 最近年 +5.4% / 单期换手 63.0% / 负年 0

---


### F45 · gen71 入库（引擎自动同步，家族命名待人工精炼）
```
max(max(barra_residual_volatility, div(barra_residual_volatility, barra_liquidity)), ts_rank60(cs_scale(ts_std100(max(barra_residual_volatility, ts_rank60(ts_std200(cs_rank(div(fa_np_margin, barra_liquidity)))))))))
```
- **符号 `sign`：`-1`**（★ 因子值须乘它才是"越大越好"的方向；不乘 ⇒ 反向选股）
- 家族：风格、风格、财报（auto）
- 叶子：barra_residual_volatility、barra_liquidity、fa_np_margin
- 骨架：`max(max(barra_residual_volatility,div(barra_residual_volatility,barra_liquidity)),ts_rank(cs_scale(ts_std(max(barra_residual_volatility,ts_rank(ts_std(cs_rank(div(fa_np_margin,barra_liquidity)))))))))`
- 池标签：**`csi1000_all`** —— 全A + **1000** 池通过
- 剥风格：**`A`** 独立有效（剥风格后**日频** Calmar >= 0.30，且**日频**回撤 > -0.20）（原 Calmar 1.066 → 剥后 0.537；超额 +3.1% → +2.0%；**日频** 剥后 Calmar 0.443，日频回撤 -4.5%）
- 口径：**20 日调仓** ✓（期数 104；成本 0.004往返(主用档)）★ 与 5 日口径的数字**不可直接比** ✗（样本区间/成本相同，只有调仓周期不同 ✓）
- 费后指标（full，成本 0.004往返(主用档)）：IC 0.0520 / IC_IR 0.890 / 年化超额 +3.1% / 回撤 -2.9% / Calmar 1.066 / Sharpe 0.944 / 最近年 +2.1% / 单期换手 69.0% / 负年 1

---


### F46 · gen74 入库（引擎自动同步，家族命名待人工精炼）
```
add(max(barra_residual_volatility, div(barra_residual_volatility, barra_liquidity)), ts_rank60(cs_scale(ts_std100(barra_residual_volatility))))
```
- **符号 `sign`：`-1`**（★ 因子值须乘它才是"越大越好"的方向；不乘 ⇒ 反向选股）
- 家族：风格、风格（auto）
- 叶子：barra_residual_volatility、barra_liquidity
- 骨架：`add(max(barra_residual_volatility,div(barra_residual_volatility,barra_liquidity)),ts_rank(cs_scale(ts_std(barra_residual_volatility))))`
- 池标签：**`csi1000_all`** —— 全A + **1000** 池通过
- 剥风格：**`B`** 弱独立（剥风格后日频 Calmar 在 0~0.30，或回撤劣于 -0.20）（原 Calmar 0.770 → 剥后 0.473；超额 +3.7% → +2.2%；**日频** 剥后 Calmar 0.289，日频回撤 -7.7%）
- 口径：**20 日调仓** ✓（期数 104；成本 0.004往返(主用档)）★ 与 5 日口径的数字**不可直接比** ✗（样本区间/成本相同，只有调仓周期不同 ✓）
- 费后指标（full，成本 0.004往返(主用档)）：IC 0.0624 / IC_IR 0.858 / 年化超额 +3.7% / 回撤 -4.7% / Calmar 0.770 / Sharpe 0.712 / 最近年 +3.3% / 单期换手 47.4% / 负年 1

---


### F47 · gen78 入库（引擎自动同步，家族命名待人工精炼）
```
ts_mean200(ts_std60(cs_demean(neg(low))))
```
- 符号 `sign`：**未记录**（缺失时不臆造，见 roadmap §8.45 铁律）
- 家族：未分类（auto）
- 叶子：
- 骨架：`ts_mean(ts_std60(cs_demean(neg(low))))`
- 池标签：**`csi500_1000_all`** —— 全A + **500/1000** 池通过
- 剥风格：**`B`** 弱独立（剥风格后日频 Calmar 在 0~0.30，或回撤劣于 -0.20）（原 Calmar 1.119 → 剥后 0.256；超额 +8.6% → +2.6%；**日频** 剥后 Calmar 0.219，日频回撤 -12.0%）
- 口径：**20 日调仓** ✓（成本 0.004往返(主用档)）★ 与 5 日口径的数字**不可直接比** ✗（样本区间/成本相同，只有调仓周期不同 ✓）
- 费后指标（full，成本 0.004往返(主用档)）：IC 0.0327 / IC_IR 0.246 / 年化超额 +8.6% / 回撤 -7.7% / Calmar 1.119 / Sharpe 1.520 / 最近年 +2.8% / 单期换手 6.6% / 负年 0

---


## 相关文件导航

| 文件 | 内容 |
|---|---|
| `docs/factor_library.md`（本文件） | 只收入库因子；引擎代末自动同步新入库，家族命名随时可人工精炼 |
| **`docs/factor_library_crosspool.md`** | ★ **跨池派生视图**：把 `factor_library_{300,500,1000}.md` 里**全A 有效**的因子**去重合并**（实测 **12 个**，且**个个都不在本文件里** —— 因为它们写进了各自的池库）。附带**池标签并集修正**。由 `python tools/build_crosspool_view.py` 生成 |
| `docs/loop_journal.md` | 每代诊断 + B角下一代参数（引擎自动读写） |
| `docs/loop_archive.csv` | 每代 L2 全量候选流水（expr/指标/passed，引擎逐代追加） |
| `engine/loop_state.pkl` | 运行状态：bank/seeds/失败库/FSA（`_dump_state.py` 可看） |
| `docs/factor_roadmap.md` | 研发档案（Round 叙事 + Loop 整体复盘/扩叶落地附录，续做入口） |
| `history/` | **归档区**：factor_miner round1~7 档案（`factor_archive.md/.csv`）+ gen16 前 Loop L2 旧快照（`loop_archive.legacy_pre_gen16.csv`），均已停更 |

### F42 · gen0 入库 → 已移出（**外部基准**：Alpha191 的 Alpha143 —— ⚠ 公式勘误见下 ✓）

- ⚠ **公式勘误（2026-09-20，用户看研报发现 ✗）**：研报原式是**递归式** ——
  `CLOSE>DELAY(CLOSE,1)?(CLOSE-DELAY(CLOSE,1))/DELAY(CLOSE,1)*SELF:SELF`（`SELF` = **t-1 日的 Alpha143 值** ✓）
  ⇒ 下面这条（原先登记的式子）**不是 Alpha143** ✗，只作历史留档：
  `neg(mul(cs_rank(ts_rank10(close)), cs_rank(sub(ts_delta10(close), ts_delta5(close)))))`
- 真式实测（`ai_test/_alpha143_true.py`：递归 ⇒ 离线手算 ✓，`log` 累加与连乘**排序等价** ✓）：
  20 日 rank-IC 全A **−0.019** · 1000 **−0.021** · 500 **−0.023** · 300 **−0.020**（t −11 ~ −16）
  ⇒ **显著为负 = 短期反转** ⇒ 方向必须**取反**（买低分端 ✓）
- 真式分层（`ai_test/alpha143_true/` ✓）：**中证1000 上第 4 档最好**（20 日年化 +38.6% · 5 日 +43.1%，
  远超其余档 ✓ —— 用户 2026-09-20 预判 _"可能 4 分位是最好的"_ **在 1000 上成立** ✓）；
  500/300 的第 5 档虽最高（+26 ~ +42%）但等权小盘味道重 ⚠ · 全A 各档差异极小 ⇒ **分层非单调** ✓
- **符号 `sign`：`1`**（历史留档：上面那条**勘误式**自带 `neg` ⇒ sign 记为 1 ✓；真式方向**须取反** ✓ 见上 ✓）
- 来源：外部基准因子，用户 2026-09-20 要求"加进全A池让管线全流程测一遍" ✓
- 口径说明：`ts_rank10` / `ts_delta10` 为 2026-09-20 新增的 10 日窗口算子 ✓
  （原式 `delta(delay(close,5),5)` 已化简易证为 `ts_delta10 - ts_delta5` ✓）
- 结论（本管线实测）：超额 **−18.22%/年** · 日频 Calmar **−0.216** · 夏普 −1.62 ·
  单期换手 71.7%（年化约 36 倍）· **负年 9 年** ⇒ **不合格** ✓

```
neg(mul(cs_rank(ts_rank10(close)), cs_rank(sub(ts_delta10(close), ts_delta5(close)))))
```
- 家族：外部基准 · 短周期价量
- 叶子：close
- 骨架：`neg(mul(cs_rank(ts_rank(close)),cs_rank(sub(ts_delta(close),ts_delta(close)))))`
- 口径：`ts_rank10` / `ts_delta10` 是 2026-09-20 新增的 10 日窗口算子 ✓（原本是为上面那条**勘误式**服务 ✗
  —— 但这两个算子**保留** ✓：通用算子，别处用得上 ✓）
  （原式 `delta(delay(close,5),5)` = `ts_delta10 − ts_delta5`，化简易证 ✓）
- 池标签：**`all_only`** —— 只在全A 上测（用户要求：先进全A 跑全流程 ✓）
- 费后指标（full，成本 0.004往返(主用档)）：超额 **-18.2%** / 日频 Calmar **-0.216** /
  夏普 -1.62 / 单期换手 71.7%（年化约 36 倍）/ **负年 9 年** ⇒ **不合格** ✓
- 状态：**已移出**（2026-09-20）—— ① 公式**本身找错了** ✗（见上勘误）② 按原式实测也**不合格** ✓
  ⇒ `in_bank` 置 0 + 退出入库历史名单 ✓（用户原话："测出来不行，再给它移出不就行了"、"搞成已移出吧" ✓）

---
