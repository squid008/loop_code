
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
