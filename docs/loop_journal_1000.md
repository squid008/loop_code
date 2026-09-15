
## 第 1 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 28 | 0.019 | 0.046 | 0.969 | 0.000 | 0.143 | 1.000 | 6 | 0.214 | 28 | 2 | 0.122 | 1.000 | 0.077 | 0.962 | 0.423 | 0.500 | 0.500 |

叶子使用: {'intraday': 4, 'mf_x_bqty': 3, 'mktcap': 3, 'mf_x_sell': 3, 'hl_ratio': 2, 'mf_l_sell': 2}

**B角建议(下一代策略)**:
- L2中100%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 配比护栏: 变异/交叉各≥10%且合计50%重归一化, 扰动/引导/随机固定15/20/15(中金规格) -> mix=[0.173, 0.327, 0.15, 0.2, 0.15]

```
mix=[0.173, 0.327, 0.15, 0.2, 0.15]  depth=[3, 4, 4]  min_stab=0.3  decorr=0.75  fsa_th=0.15  bank_skel_max=1
leaf_w={}
```

**LLM 引导(A角 1代)**: 调用3次, 解析通过36条, 引导位使用36条
> 主动资金流的结构性失衡（大单与超大单净买入强度、以及资金流强度与价格变化的背离）在短期具有截面收益预测力，且该信息在价格与成交额之外独立存在。


**LLM 候选审查(B角 1代)**: 深判 5 个, KILL 3 个(剔除出 L2 费后回测)
- KILL `ts_std150(ts_mean120(ts_rank100(high)))`
  > 理由: 仅对high做多层时序平滑/排名/波动，无成交量价配合，经济含义空洞，属参数海冗余结构
- KILL `corr100(true_range, cs_scale(corr20(hl_ratio, low)))`
  > 理由: 嵌套相关再截面缩放，经济含义拼凑难解释，属参数海捞针冗余结构
- KILL `max(ts_mean150(min(corr20(volume, true_range), mul(fa_ocf_yoy, barra_earnings_yield))), close)`
  > 理由: 量价相关与基本面字段混搭取min/max，经济含义拼凑，纯数学巧合


**AI 审查(DeepSeek deepseek-flash, 2s)**:

> (1)病根:IC天花板太低(中位0.019),信号弱且同质,叶子挤在intraday与资金流,加深搜索只会放大噪声。
> 
> (2)交叉+15%对症但不够,深度加深与min_stab=0.3冲突:弱信号下深树更易过拟合,neg_yr=3~5已示警。扰动/引导/随机固定15/20/15偏保守,引导20%在低IC下易锁死旧方向。decorr=0.75合理,但护栏合计50%重归一化后交叉仅0.327,增幅被稀释,实际效果打折。
> 
> (3)建议mix=[0.25,0.30,0.10,0.15,0.20],depth=[3,3,4],min_stab=0.5,decorr=0.8。理由:提变异与随机以跳出intraday同质,压深度与引导防过拟合,稳住稳定性门槛。

## 第 2 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 27 | 0.022 | 0.046 | 0.983 | 0.000 | 0.222 | 1.000 | 3 | 0.259 | 27 | 1 | 0.125 | 1.000 | 0.000 | 1.000 | 0.462 | 0.423 | 0.519 |

叶子使用: {'barra_beta': 6, 'intraday': 5, 'mf_m_sell': 4, 'ln_mktcap': 4, 'mf_x_bqty': 3, 'vwap': 3}

**B角建议(下一代策略)**:
- L2中100%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 配比护栏: 变异/交叉各≥10%且合计50%重归一化, 扰动/引导/随机固定15/20/15(中金规格) -> mix=[0.1, 0.4, 0.15, 0.2, 0.15]

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 4]  min_stab=0.3  decorr=0.75  fsa_th=0.15  bank_skel_max=1
leaf_w={}
```

**LLM 引导(A角 2代)**: 调用3次, 解析通过43条, 引导位使用43条
> 资金流内部结构失衡（大单/超大单主动净买入相对中小单的背离）与量价背离叠加，能预测未来5日截面收益：当超大单持续净买入而中小单净卖出、且价格未同步上行时，后续存在补涨或资金驱动溢价。


**LLM 候选审查(B角 2代)**: 深判 5 个, KILL 2 个(剔除出 L2 费后回测)
- KILL `corr200(corr60(ts_mean60(barra_residual_volatility), ts_rank20(barra_size)), add(mf_x_sqty, ts_std150(mf_s_bqty)))`
  > 理由: 多层嵌套corr叠加异源字段，经济含义拼凑难解释，窗口密集疑参数捞针
- KILL `ts_sum100(corr20(abs(mul(mktcap, fa_gm)), true_range))`
  > 理由: 市值乘毛利率与真实波幅相关，经济含义拼凑，无清晰量价机制，属数学巧合


**AI 审查(DeepSeek deepseek-flash, 2s)**:

> (1)病根:IC信号太弱且同质,叶子挤在barra_beta/intraday,深度不足导致L2全灭于Calmar。
> 
> (2)建议基本对症但两处存疑:交叉+15%合理,但变异压到10%会砍掉探索,与"深度加深"叠加易过拟合;扰动/引导/随机固定中金规格与"合计50%重归一化"自相矛盾,护栏会失效。min_stab=0.3对已0.98的池子形同虚设,decorr=0.75偏松,难破同质。
> 
> (3)我取mix=[0.15,0.30,0.15,0.20,0.20],depth=[3,4,5],min_stab=0.5,decorr=0.6。理由:留足变异与随机探索、加深一层、收紧去相关以破叶子拥挤,比单纯堆交叉更可能救活Calmar。

## 第 3 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 34 | 0.017 | 0.056 | 0.988 | 0.000 | 0.206 | 0.941 | 3 | 0.265 | 30 | 3 | 0.065 | 1.000 | 0.000 | 1.000 | 0.333 | 0.593 | 0.433 |

叶子使用: {'overnight': 7, 'true_range': 6, 'vwap': 5, 'ln_mktcap': 4, 'barra_beta': 4, 'mf_l_sqty': 4}

**B角建议(下一代策略)**:
- L2中100%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 配比护栏: 变异/交叉各≥10%且合计50%重归一化, 扰动/引导/随机固定15/20/15(中金规格) -> mix=[0.1, 0.4, 0.15, 0.2, 0.15]

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 4]  min_stab=0.3  decorr=0.75  fsa_th=0.15  bank_skel_max=1
leaf_w={}
```

**LLM 引导(A角 3代)**: 调用3次, 解析通过34条, 引导位使用34条
> 主动资金流的方向与价格变化出现背离时（价涨但超大单净卖出、或价跌但超大单净买入），未来5日截面收益倾向于反转，且该背离在大单与中小单方向对立时更强。


**LLM 候选审查(B角 3代)**: 深判 5 个, KILL 1 个(剔除出 L2 费后回测)
- KILL `ts_mean60(corr60(ts_delta20(mf_x_bqty), max(abs(mul(mktcap, fa_gm)), ts_mean150(corr20(mf_x_bqty, mf_m_bqty)))))`
  > 理由: 多层嵌套同源corr与量价字段，经济含义拼凑难解释，参数冗余似过拟合


**AI 审查(DeepSeek deepseek-flash, 2s)**:

> (1)病根：L1信号本身太弱且同质，L2只是把弱信号放大成低Calmar，加交叉加深只会复制弱基因。
> 
> (2)交叉+15%对症一半：当前叶子集中在overnight/true_range/vwap，交叉能提多样性，但depth加深到4会加剧过拟合，与min_stab=0.3冲突（低稳定门槛放行噪声）。扰动/引导/随机固定值合理，但变异仅10%偏低，难跳出弱信号盆地。护栏重归一化后交叉0.4偏重，可能挤掉变异探索。
> 
> (3)建议mix=[0.2,0.25,0.15,0.25,0.15]，depth=[2,3,3]，min_stab=0.5，decorr=0.6。理由：提变异与引导、压深度与降相关阈值，先破同质弱信号再谈交叉。

## 第 4 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | gate_min_calmar | gate_min_pool_calmar | fail_calmar | fail_calmar_neg | fail_pool_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 39 | 0.017 | 0.048 | 0.987 | 0.000 | 0.282 | 0.949 | 5 | 0.282 | 30 | 1 | 0.057 | 0.000 | 0.150 | 0.448 | 0.448 | 0.621 | 0.000 | 0.966 | 0.379 | 0.552 | 0.500 |

叶子使用: {'true_range': 11, 'mf_l_sqty': 7, 'barra_beta': 5, 'barra_liquidity': 5, 'mf_x_bqty': 4, 'ln_volume': 4}

**B角建议(下一代策略)**:
- 【r5_calmar_cross】L2中62%因Calmar不足[池口径: 任一池 Calmar > 0.15] -> 交叉+15%, 深度加深
- 配比护栏: 变异/交叉各≥10%且合计50%重归一化, 扰动/引导/随机固定15/20/15(中金规格) -> mix=[0.1, 0.4, 0.15, 0.2, 0.15]

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 4]  min_stab=0.3  decorr=0.75  fsa_th=0.15  bank_skel_max=1
leaf_w={}
```

**规则动作留痕**:
- `r5_calmar_cross` L2 多因 Calmar 不足 -> 交叉+15% / 深度加深 —— 施加于第 [4, 5] 代

**LLM 引导(A角 4代)**: 调用3次, 解析通过31条, 引导位使用31条
> 资金流内部结构失衡比总量更能预测未来5日截面收益：超大单主动净买入相对中小单的强弱分化（大资金知情交易痕迹）在短期被低估，随后5日截面收益向上修复。


**LLM 候选审查(B角 4代)**: 深判 5 个, KILL 2 个(剔除出 L2 费后回测)
- KILL `corr100(cs_demean(ts_delta5(ts_mean100(mf_l_sqty))), mf_x_sell)`
  > 理由: mf_l_sqty与mf_x_sell含义拼凑，多层同源时序算子冗余，经济机制不明
- KILL `ts_mean200(max(abs(mul(mktcap, fa_gm)), ts_mean150(corr20(corr20(overnight, true_range), mf_m_bqty))))`
  > 理由: 市值乘毛利率与量价相关嵌套拼凑，无清晰经济机制，参数冗余疑过拟合


**AI 审查(DeepSeek deepseek-flash, 3s)**:

> (1)病根:IC量级够但L2全卡在neg_yr与Calmar,即信号是"高stab低赔率"的波动率/流动性类同质叶子,缺收益弹性。
> 
> (2)r5_calmar_cross对症但药量错:交叉+15%只增组合复杂度,不解决neg_yr=3~5的赔率缺失;与min_stab=0.3、decorr=0.75冲突——放宽稳定度会灌入更多同族叶子,decorr又强压,等于自锁。护栏固定扰动/引导/随机反而挤掉变异探索。
> 
> (3)我建议mix=[0.25,0.2,0.15,0.2,0.2],depth=[3,4,3],min_stab=0.5,decorr=0.6:先保变异多样性、适度松decorr,让收益型算子进场。
> 
> 否决: r5_calmar_cross

**⚖️ 规则动作否决（机器读取）**: `r5_calmar_cross`（L2 多因 Calmar 不足 -> 交叉+15% / 深度加深）

## 第 5 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | gate_min_calmar | gate_min_pool_calmar | fail_calmar | fail_calmar_neg | fail_pool_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 33 | 0.018 | 0.038 | 0.989 | 0.000 | 0.242 | 0.879 | 2 | 0.333 | 30 | 3 | 0.070 | 0.000 | 0.150 | 0.370 | 0.370 | 0.556 | 0.000 | 1.000 | 0.444 | 0.519 | 0.433 |

叶子使用: {'mf_l_sqty': 8, 'true_range': 7, 'ln_volume': 7, 'overnight': 5, 'mf_x_bqty': 5, 'barra_beta': 4}

**B角建议(下一代策略)**:
- 【拦截】[r5_calmar_cross] 已连续 2 代施加 -> 判为饱和（条件恒真=固定偏移），冷却到第 9 代再评估 —— L2 多因 Calmar 不足 -> 交叉+15% / 深度加深
- —— 本代共拦截 1 条动作（饱和/LLM 否决），详见上面【拦截】行

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 4]  min_stab=0.3  decorr=0.75  fsa_th=0.15  bank_skel_max=1
leaf_w={}
```

**规则动作留痕**:
- `r5_calmar_cross` L2 多因 Calmar 不足 -> 交叉+15% / 深度加深 —— 施加于第 [4, 5] 代

**LLM 引导(A角 5代)**: 调用3次, 解析通过34条, 引导位使用34条
> 大单主动资金的方向与价格短期变化背离时，未来5日截面收益倾向于修复——即当价格已涨但超大单净买入占比未同步放大（或价格跌而大单逆势吸筹）时，后续存在超额收益。


**LLM 候选审查(B角 5代)**: 深判 5 个, KILL 1 个(剔除出 L2 费后回测)
- KILL `ts_std100(ts_delay1(ts_std100(ts_delay1(ln_volume))))`
  > 理由: 仅对成交量取对数后做延迟与滚动标准差，属波动率老故事，无增量机制且嵌套冗余


**AI 审查(DeepSeek deepseek-flash, 1s)**:

> (1)病根:IC量级尚可但L2全军覆没,neg_yr与fail_ic双高,说明因子在时间维度上不稳定、且与已知因子同质,不是搜索强度不够。
> (2)r5_calmar_cross已连续两代施加且被引擎判饱和,继续交叉+加深只会放大过拟合,对neg_yr=1.0无解;它与min_stab=0.3、decorr=0.75的收紧方向互相冲突,属无效动作。
> (3)mix=[0.15,0.25,0.2,0.25,0.15],depth=[3,3,4],min_stab=0.5,decorr=0.85:降交叉、提扰动与引导、抬稳定性门槛并强去相关,直击neg_yr与同质化。
> 否决: r5_calmar_cross

**⚖️ 规则动作否决（机器读取）**: `r5_calmar_cross`（L2 多因 Calmar 不足 -> 交叉+15% / 深度加深）

## 第 6 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | gate_min_calmar | gate_min_pool_calmar | fail_calmar | fail_calmar_neg | fail_pool_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 30 | 0.018 | 0.041 | 0.989 | 0.000 | 0.367 | 0.933 | 5 | 0.400 | 30 | 3 | 0.057 | 0.000 | 0.150 | 0.296 | 0.296 | 0.481 | 0.000 | 0.963 | 0.296 | 0.593 | 0.400 |

叶子使用: {'true_range': 11, 'barra_residual_volatility': 6, 'mktcap': 5, 'barra_beta': 5, 'overnight': 5, 'ln_volume': 5}

**B角建议(下一代策略)**:
- 各项指标正常, 维持当前策略

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 4]  min_stab=0.3  decorr=0.75  fsa_th=0.15  bank_skel_max=1
leaf_w={}
```

**规则动作留痕**:
- `r5_calmar_cross` L2 多因 Calmar 不足 -> 交叉+15% / 深度加深 —— 施加于第 [4, 5] 代（**已永久关闭**）
- ⛔ **被 LLM 永久否决的动作**（用户要求「让它永久闭嘴」）：`r5_calmar_cross`

**LLM 引导(A角 6代)**: 调用3次, 解析通过23条, 引导位使用23条
> 在超大单主动资金持续净流入的同时若中小单反向净卖出（散户与主力方向背离），则该股未来5日截面收益更高，因为主力吸筹被散户抛压掩盖，属于被低估的资金流结构信号。


**LLM 候选审查(B角 6代)**: 深判 5 个, KILL 3 个(剔除出 L2 费后回测)
- KILL `ts_mean200(mul(corr20(overnight, true_range), ts_max20(ts_mean60(barra_size))))`
  > 理由: 多层嵌套同源时序算子，窗口20/60/200冗余，经济含义拼凑难解释，过拟合嫌疑
- KILL `ts_mean60(ts_std100(ts_delay1(ln_volume)))`
  > 理由: 仅对成交量对数做延迟、波动、平滑，属成交额老故事再表达，无增量机制
- KILL `ts_mean200(sign(ts_delta5(ts_std150(barra_residual_volatility))))`
  > 理由: 多层同源时序算子嵌套，窗口150/200冗余，仅表残差波动率变化方向，无增量机制


**AI 审查(DeepSeek deepseek-flash, 2s)**:

> (1) 病根: 因子全挤在barra_residual_volatility/true_range等少数叶子上, 同质化严重, L2负年数5/5、calmar全废, 是"高IC低可用"的过拟合假象。
> 
> (2) 规则B角"维持当前策略"不对症: 诊断已明确fail_negyear=0.963、seg_kill=0.4、leaf_conc偏高, 属结构性失效, 维持等于放任同质化。下代表格把min_stab从0.3、decorr=0.75其实方向对, 但与"维持"矛盾——既然维持, 为何改表? 二者冲突。
> 
> (3) 建议: mix=[0.25,0.25,0.15,0.2,0.15] 提高变异/交叉以打散叶子; depth=[2,3,4] 降深度抗过拟合; min_stab=0.5 提门槛; decorr=0.85 强制去同质。
> 
> 否决: 无

## 第 7 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | gate_min_calmar | gate_min_pool_calmar | fail_calmar | fail_calmar_neg | fail_pool_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 19 | 0.020 | 0.050 | 0.987 | 0.000 | 0.368 | 0.947 | 22 | 0.316 | 19 | 1 | 0.069 | 0.000 | 0.150 | 0.389 | 0.389 | 0.556 | 0.167 | 0.889 | 0.444 | 0.444 | 0.316 |

叶子使用: {'barra_residual_volatility': 7, 'overnight': 5, 'turn_ratio': 5, 'barra_size': 5, 'barra_beta': 4, 'mktcap': 2}

**B角建议(下一代策略)**:
- 【拦截】[r5_calmar_cross] LLM 已【永久】否决，后续各代一律不再施加 —— L2 多因 Calmar 不足 -> 交叉+15% / 深度加深
- —— 本代共拦截 1 条动作（饱和/LLM 否决），详见上面【拦截】行

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 4]  min_stab=0.3  decorr=0.75  fsa_th=0.15  bank_skel_max=1
leaf_w={}
```

**规则动作留痕**:
- `r5_calmar_cross` L2 多因 Calmar 不足 -> 交叉+15% / 深度加深 —— 施加于第 [4, 5] 代（**已永久关闭**）
- ⛔ **被 LLM 永久否决的动作**（用户要求「让它永久闭嘴」）：`r5_calmar_cross`

**LLM 引导(A角 7代)**: 调用3次, 解析通过37条, 引导位使用37条
> 资金流强度与价格变动的背离(主动净买入放大但价格未跟涨、或价格上行而超大单净卖出)反映知情交易者与散户的博弈错位,未来5日截面收益将向资金流方向修正;叠加财报景气动量与风格暴露的错配可增强预测。


**LLM 候选审查(B角 7代)**: 深判 5 个, KILL 4 个(剔除出 L2 费后回测)
- KILL `ts_std150(ts_mean5(ln_volume))`
  > 理由: 仅对成交量均值取长窗标准差，属换手/成交额老故事，无增量机制
- KILL `corr60(abs(barra_beta), high)`
  > 理由: barra_beta与high跨域相关无明确量价机制，属数学拼凑，难解释
- KILL `ts_min20(mul(add(sub(overnight, barra_beta), ts_mean60(barra_residual_volatility)), ts_max20(ts_mean60(mktcap))))`
  > 理由: 隔夜收益与beta/残差波动/市值尺度混算，经济含义拼凑，属数学巧合
- KILL `ts_std150(div(corr60(ln_mktcap, true_range), ts_mean150(barra_beta)))`
  > 理由: 市值与真实波幅相关性再除以beta均值，多层嵌套冗余，经济含义拼凑难解释


**AI 审查(DeepSeek deepseek-flash, 2s)**:

> (1)病根:IC够但L2几乎全灭,neg_yr=0.889、fail_lastyr=0.444,即因子是"近端过拟合的短命信号",而非稳健alpha。
> 
> (2)规则B建议本身无新动作,只复述永久关闭r5_calmar_cross,对症但零信息量;真正该管的是neg_yr与lastyr,建议未触及,等于空转。mix里交叉0.4偏高、引导0.2偏低,与"需换骨架"矛盾。
> 
> (3)我取mix=[0.15,0.25,0.15,0.3,0.15],depth=[3,4,5],min_stab=0.5,decorr=0.7:提引导压交叉,加深换结构,抬stab门槛逼出跨年稳健因子。
> 
> 否决: 无

## 第 8 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | gate_min_calmar | gate_min_pool_calmar | fail_calmar | fail_calmar_neg | fail_pool_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 22 | 0.011 | 0.037 | 0.994 | 0.000 | 0.364 | 1.000 | 5 | 0.591 | 22 | 0 | 0.093 | 0.000 | 0.150 | 0.409 | 0.409 | 0.455 | 0.000 | 0.864 | 0.182 | 0.636 | 0.273 |

叶子使用: {'overnight': 8, 'barra_beta': 8, 'barra_residual_volatility': 7, 'turn_ratio': 6, 'mktcap': 5, 'ln_volume': 5}

**B角建议(下一代策略)**:
- 【r7_zero_pass】本代0通过 -> 深度放宽到3~5, 探索更复杂结构

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 5]  min_stab=0.3  decorr=0.75  fsa_th=0.15  bank_skel_max=1
leaf_w={}
```

**规则动作留痕**:
- `r5_calmar_cross` L2 多因 Calmar 不足 -> 交叉+15% / 深度加深 —— 施加于第 [4, 5] 代（**已永久关闭**）
- `r7_zero_pass` 本代 0 通过 -> 深度放宽到 3~5 —— 施加于第 [9] 代
- ⛔ **被 LLM 永久否决的动作**（用户要求「让它永久闭嘴」）：`r5_calmar_cross`

**LLM 引导(A角 8代)**: 调用3次, 解析通过43条, 引导位使用43条
> 大单主动资金净流入强度相对中小单方向的背离，叠加日内价格位置偏低，能捕捉知情交易者吸筹后的未来5日截面超额收益。


**LLM 候选审查(B角 8代)**: 深判 5 个, KILL 5 个(剔除出 L2 费后回测)
- KILL `ts_std20(div(ts_delta120(mul(turn_ratio, close)), fa_op_yoy))`
  > 理由: 换手率乘收盘价再除以同比增速，量纲与含义拼凑，无清晰量价机制，属数学巧合
- KILL `corr200(ts_mean150(ts_mean60(low)), corr200(overnight, hl_ratio))`
  > 理由: 多层同源均值嵌套corr，窗口60/150/200冗余，经济含义拼凑难解释，过拟合嫌疑
- KILL `ts_mean150(ts_rank200(corr20(ts_rank60(ts_mean200(corr100(barra_size, min(turn_ratio, amplitude)))), barra_book_to_price)))`
  > 理由: 多层嵌套同源时序算子+窗口堆砌，经济含义拼凑难解释，过拟合嫌疑重
- KILL `ts_sum100(mul(add(sub(overnight, barra_beta), ts_mean60(barra_residual_volatility)), ts_max20(ts_mean60(mktcap))))`
  > 理由: 隔夜收益与beta/波动率/市值量纲混加相乘，无经济含义，属数学拼凑
- KILL `ts_mean200(mul(add(turn_ratio, ts_mean60(barra_residual_volatility)), ts_max20(ts_mean60(barra_size))))`
  > 理由: 换手率叠加波动率残差再乘市值均值，属已知换手/市值老故事拼凑，无增量机制


**AI 审查(DeepSeek deepseek-flash, 2s)**:

> (1) 病根不在深度不够,而在因子全是overnight/barra_beta/residual_vol的同一族堆叠,IC天花板0.037、neg_yr高达0.864,是信号同质+样本外失效,不是结构太浅。
> 
> (2) r7_zero_pass不对症:0通过源于fail_negyear=0.864与fail_ic=0.636,放宽depth只会放大同族过拟合,且与decorr=0.75、min_stab=0.3互斥——低门槛放行弱因子,decorr又难满足,徒增算力。真正该做的是打散叶子族、强制换源。
> 
> (3) mix=[0.15,0.3,0.2,0.25,0.1] depth=[2,3] min_stab=0.6 decorr=0.5:压深度、提稳定性门槛、加引导换族,先解决同质与负年。
> 
> 否决: r7_zero_pass

**⚖️ 规则动作否决（机器读取）**: `r7_zero_pass`（本代 0 通过 -> 深度放宽到 3~5）

## 第 9 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | gate_min_calmar | gate_min_pool_calmar | fail_calmar | fail_calmar_neg | fail_pool_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 15 | 0.011 | 0.037 | 0.994 | 0.000 | 0.600 | 1.000 | 0 | 0.733 | 15 | 0 | 0.093 | 0.000 | 0.150 | 0.333 | 0.333 | 0.333 | 0.000 | 0.800 | 0.067 | 0.667 | 0.400 |

叶子使用: {'barra_beta': 9, 'overnight': 9, 'barra_residual_volatility': 7, 'mktcap': 6, 'ln_mktcap': 3, 'turn_ratio': 2}

**B角建议(下一代策略)**:
- 【r1_leaf_conc】叶子[barra_beta]占比60%过高 -> 权重压到0.25, 逼引擎换字段
- 【r6_known_ratio】73%候选仍含已知族字段 -> decorr收紧到0.70(0.70≈中金入库IC相关口径)
- 【r7_zero_pass】本代0通过 -> 深度放宽到3~5, 探索更复杂结构

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 5]  min_stab=0.3  decorr=0.7  fsa_th=0.15  bank_skel_max=1
leaf_w={'barra_beta': 0.25}
```

**规则动作留痕**:
- `r1_leaf_conc` 叶子过度集中 -> 压低该叶子权重 —— 施加于第 [10] 代
- `r5_calmar_cross` L2 多因 Calmar 不足 -> 交叉+15% / 深度加深 —— 施加于第 [4, 5] 代（**已永久关闭**）
- `r6_known_ratio` 候选仍绕已知族 -> decorr 收紧 —— 施加于第 [10] 代
- `r7_zero_pass` 本代 0 通过 -> 深度放宽到 3~5 —— 施加于第 [9, 10] 代
- ⛔ **被 LLM 永久否决的动作**（用户要求「让它永久闭嘴」）：`r5_calmar_cross`

**LLM 引导(A角 9代)**: 调用3次, 解析通过32条, 引导位使用32条
> 主动资金流的方向性失衡（尤其超大单净买入占比与中小单方向背离）在短期具有持续性，能预测未来5日截面收益，且该信息与价格动量、换手率等传统量价维度正交。


**LLM 候选审查(B角 9代)**: 深判 5 个, KILL 5 个(剔除出 L2 费后回测)
- KILL `ts_mean120(ts_rank200(ts_mean5(ts_delta5(ts_mean60(ts_std100(ts_delay1(ln_volume)))))))`
  > 理由: 多层同源均值/排名嵌套，仅换手量老故事，冗余难解释，过拟合嫌疑
- KILL `sub(max(fa_np_margin, div(ts_mean150(ts_rank200(ts_mean5(ts_delta5(ts_mean60(ts_std100(ts_delay1(ln_volume))))))), barra_comovement)), ts_sum100(corr20(turnover, ln_volume)))`
  > 理由: 多层同源量价算子嵌套冗余，窗口参数堆砌，经济含义不可解释，属参数海捞针
- KILL `ts_mean5(ts_sum100(mul(add(sub(overnight, barra_beta), ts_mean60(barra_residual_volatility)), ts_max20(ts_mean60(mktcap)))))`
  > 理由: 隔夜收益与beta/残差波动/市值跨尺度相乘相加，量纲混乱无经济含义，属数学拼凑
- KILL `sub(max(fa_np_margin, div(close, barra_comovement)), ts_sum100(corr20(turnover, ln_volume)))`
  > 理由: 净利润率与价量协整量纲相减，含义拼凑，无清晰量价机制
- KILL `ts_mean20(ts_mean10(ts_mean60(ts_mean150(ret))))`
  > 理由: 多层同源均值嵌套，仅平滑收益，无增量量价机制，属冗余参数堆叠


**AI 审查(DeepSeek deepseek-flash, 2s)**:

> (1)病根:不是深度不够,是候选全挤在overnight/barra_beta/mktcap同一模板上,IC低且neg_yr普遍4~5,属结构性同质,加深度只会放大过拟合。
> 
> (2)r1_leaf_conc对症但权重压到0.25过猛,会误伤唯一calmar=0.45的turn_ratio组合;r6_known_ratio把decorr收到0.70与r1同时执行会双重封锁字段,导致无米下锅;r7_zero_pass最不对症,0通过源于neg_yr与IC,非深度,放宽到5只会加深同质。
> 
> (3)mix=[0.15,0.35,0.15,0.2,0.15],depth=[2,3],min_stab=0.5,decorr=0.8:先保稳定与去同质,再谈复杂度。
> 
> 否决: r7_zero_pass

**⚖️ 规则动作否决（机器读取）**: `r7_zero_pass`（本代 0 通过 -> 深度放宽到 3~5）

## 第 10 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | gate_min_calmar | gate_min_pool_calmar | fail_calmar | fail_calmar_neg | fail_pool_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 25 | 0.011 | 0.039 | 0.994 | 0.000 | 0.440 | 1.000 | 1 | 0.440 | 25 | 0 | 0.067 | 0.000 | 0.150 | 0.280 | 0.280 | 0.400 | 0.000 | 0.920 | 0.040 | 0.680 | 0.280 |

叶子使用: {'overnight': 11, 'barra_beta': 8, 'hl_ratio': 6, 'barra_residual_volatility': 4, 'mktcap': 4, 'ln_mktcap': 4}

**B角建议(下一代策略)**:
- 【r1_leaf_conc】叶子[overnight]占比44%过高 -> 权重压到0.25, 逼引擎换字段
- 【拦截】[r7_zero_pass] LLM 已【永久】否决，后续各代一律不再施加 —— 本代 0 通过 -> 深度放宽到 3~5
- —— 本代共拦截 1 条动作（饱和/LLM 否决），详见上面【拦截】行

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 5]  min_stab=0.3  decorr=0.65  fsa_th=0.15  bank_skel_max=1
leaf_w={'barra_beta': 0.25, 'overnight': 0.25}
```

**规则动作留痕**:
- `r1_leaf_conc` 叶子过度集中 -> 压低该叶子权重 —— 施加于第 [10, 11] 代
- `r5_calmar_cross` L2 多因 Calmar 不足 -> 交叉+15% / 深度加深 —— 施加于第 [4, 5] 代（**已永久关闭**）
- `r6_known_ratio` 候选仍绕已知族 -> decorr 收紧 —— 施加于第 [10] 代
- `r7_zero_pass` 本代 0 通过 -> 深度放宽到 3~5 —— 施加于第 [9, 10] 代（**已永久关闭**）
- ⛔ **被 LLM 永久否决的动作**（用户要求「让它永久闭嘴」）：`r5_calmar_cross`, `r7_zero_pass`

**LLM 引导(A角 10代)**: 调用3次, 解析通过35条, 引导位使用35条
> 资金流内部结构失衡（大单主动净买入相对中小单的背离、且与价格变化方向不匹配）能捕捉知情交易者的隐蔽吸筹，预测未来5日截面收益。


**LLM 候选审查(B角 10代)**: 深判 5 个, KILL 1 个(剔除出 L2 费后回测)
- KILL `ts_mean20(ts_mean60(ts_mean60(ts_mean150(ret))))`
  > 理由: 多层同源ts_mean嵌套冗余，仅平滑收益无增量机制，参数拼凑过拟合


**AI 审查(DeepSeek deepseek-flash, 1s)**:

> (1) 病根: 0通过不是深度不够, 而是neg_yr=0.92+ic=0.68双杀, 因子全是隔夜/日内均值类同源信号, 缺时序稳定性与收益结构。
> 
> (2) r1_leaf_conc对症但力度过猛, 压到0.25会误伤唯一高stab的overnight族; r6_known_ratio与r1冲突, 一边逼换字段一边收紧去相关, 只会把搜索推向随机噪声; 放宽depth到3~5对neg_yr无解, 属无效动作。
> 
> (3) mix=[0.15,0.35,0.2,0.2,0.1] depth=[2,3,4] min_stab=0.5 decorr=0.5。理由: 先保稳定与去同源, 再谈深度。
> 
> 否决: r6_known_ratio

**⚖️ 规则动作否决（机器读取）**: `r6_known_ratio`（候选仍绕已知族 -> decorr 收紧）

## 第 11 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | gate_min_calmar | gate_min_pool_calmar | fail_calmar | fail_calmar_neg | fail_pool_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 23 | 0.016 | 0.035 | 0.995 | 0.000 | 0.391 | 1.000 | 2 | 0.435 | 23 | 1 | 0.067 | 0.000 | 0.150 | 0.273 | 0.273 | 0.227 | 0.000 | 0.818 | 0.000 | 0.545 | 0.261 |

叶子使用: {'overnight': 9, 'barra_beta': 8, 'mktcap': 5, 'barra_residual_volatility': 5, 'turn_ratio': 5, 'hl_ratio': 4}

**B角建议(下一代策略)**:
- 各项指标正常, 维持当前策略

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 5]  min_stab=0.3  decorr=0.65  fsa_th=0.15  bank_skel_max=1
leaf_w={'barra_beta': 0.25, 'overnight': 0.25}
```

**规则动作留痕**:
- `r1_leaf_conc` 叶子过度集中 -> 压低该叶子权重 —— 施加于第 [10, 11] 代
- `r5_calmar_cross` L2 多因 Calmar 不足 -> 交叉+15% / 深度加深 —— 施加于第 [4, 5] 代（**已永久关闭**）
- `r6_known_ratio` 候选仍绕已知族 -> decorr 收紧 —— 施加于第 [10] 代
- `r7_zero_pass` 本代 0 通过 -> 深度放宽到 3~5 —— 施加于第 [9, 10] 代（**已永久关闭**）
- ⛔ **被 LLM 永久否决的动作**（用户要求「让它永久闭嘴」）：`r5_calmar_cross`, `r7_zero_pass`

**LLM 引导(A角 11代)**: 调用3次, 解析通过41条, 引导位使用41条
> 在风格暴露（beta/动量/成长）被市场短期过度定价后，个股的隔夜跳空溢价与主动资金大单净流入方向会发生背离，这种风格暴露-资金流-跳空的错配会在未来5日截面收益上出现均值回复。


**LLM 候选审查(B角 11代)**: 深判 5 个, KILL 4 个(剔除出 L2 费后回测)
- KILL `ts_mean20(ts_mean150(min(turn_ratio, overnight)))`
  > 理由: 换手率与隔夜收益取min再长窗平滑，含义拼凑且与换手率老因子高度同构，无增量机制
- KILL `max(ts_mean5(barra_residual_volatility), ts_mean120(fa_ocf_yoy))`
  > 理由: 量价波动率与财务经营现金流同比跨域取max，无经济机制，属字段拼凑
- KILL `ts_mean150(min(ts_mean120(sub(fa_lev, barra_momentum)), corr200(ts_mean10(ts_mean60(low)), corr200(mf_l_bqty, hl_ratio))))`
  > 理由: 多层嵌套同源均值与相关，窗口密集堆叠，经济含义拼凑难解释，过拟合嫌疑
- KILL `corr200(ts_mean10(ts_mean60(low)), corr200(log(turnover), hl_ratio))`
  > 理由: 多层同源corr/ts_mean嵌套冗余，经济含义拼凑难解释，参数海捞针


**AI 审查(DeepSeek deepseek-flash, 2s)**:

> (1)病根在L2端:neg_yr=5/4/6、fail_negyear=0.818,说明因子方向不稳、跨年符号翻转,而L1的ic_med仅0.016、known_ratio=0.435,信息量本就稀薄。
> (2)规则B角「维持当前策略」不对症:它只看了L1的stab与leaf_conc,完全无视neg_yr与fail_negyear,等于放任病根;且与r6_known_ratio收紧decorr的意图相冲,一边说正常一边收紧,自相矛盾。
> (3)mix=[0.15,0.35,0.15,0.2,0.15],depth=[3,4],min_stab=0.5,decorr=0.7:压depth与min_stab以逼出跨年稳健结构,略提decorr但不过度,给引导留空间。
> 否决: r1_leaf_conc

**⚖️ 规则动作否决（机器读取）**: `r1_leaf_conc`（叶子过度集中 -> 压低该叶子权重）
