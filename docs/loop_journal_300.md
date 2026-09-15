
## 第 1 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 21 | 0.026 | 0.046 | 0.968 | 0.000 | 0.190 | 1.000 | 7 | 0.095 | 21 | 1 | 0.103 | 1.000 | 0.150 | 1.000 | 0.550 | 0.400 | 0.714 |

叶子使用: {'barra_residual_volatility': 4, 'amplitude': 3, 'volume': 3, 'barra_beta': 3, 'overnight': 2, 'ret': 2}

**B角建议(下一代策略)**:
- L2中100%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 配比护栏: 变异/交叉各≥10%且合计50%重归一化, 扰动/引导/随机固定15/20/15(中金规格) -> mix=[0.173, 0.327, 0.15, 0.2, 0.15]

```
mix=[0.173, 0.327, 0.15, 0.2, 0.15]  depth=[3, 4, 4]  min_stab=0.3  decorr=0.75  fsa_th=0.15  bank_skel_max=1
leaf_w={}
```

**LLM 引导(A角 1代)**: 调用3次, 解析通过35条, 引导位使用35条
> 大单与超大单的主动净买入强度相对中小单的背离，以及资金流强度与价格变化的错配，能在未来5日截面收益上产生可持续的正向预测（知情资金吸筹而价格未充分反应）。


**LLM 候选审查(B角 1代)**: 深判 5 个, KILL 2 个(剔除出 L2 费后回测)
- KILL `sub(abs(ts_sum20(barra_size)), ts_mean5(sub(fa_op_yoy, barra_book_to_price)))`
  > 理由: barra_size绝对值与盈利收益率相减，量纲与含义拼凑，无清晰量价机制
- KILL `corr20(ts_delta120(mf_l_buy), mul(mf_l_buy, mktcap))`
  > 理由: 大单买入与市值相乘无经济含义，与自身差分做相关属数学拼凑，冗余难解释


**AI 审查(DeepSeek deepseek-flash, 2s)**:

> (1)病根:信号强度不足且同质化,IC上限仅0.046,叶子扎堆波动率/振幅类,叠加换手与负年约束,导致L2几乎全灭。
> 
> (2)交叉+15%对症但不够,深度加深会进一步稀释IC;变异/交叉合计50%重归一化与固定15/20/15存在配比冲突,实际交叉被压到32.7%,增幅有限。真正该动的是叶子多样性(decorr)与信号强度,而非单纯加深。
> 
> (3)建议mix=[0.25,0.25,0.15,0.2,0.15],depth=[2,3,3],min_stab=0.5,decorr=0.85。理由:降深度保IC,提decorr破波动率扎堆,交叉变异均衡扩源。

## 第 2 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 29 | 0.030 | 0.046 | 0.959 | 0.000 | 0.379 | 1.000 | 9 | 0.138 | 29 | 0 | 0.046 | 1.000 | 0.172 | 0.966 | 0.483 | 0.276 | 0.621 |

叶子使用: {'barra_residual_volatility': 11, 'amplitude': 5, 'mf_l_bqty': 5, 'fa_np_yoy': 4, 'mf_l_sqty': 4, 'mf_m_sell': 3}

**B角建议(下一代策略)**:
- L2中100%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 本代0通过 -> 深度放宽到3~5, 探索更复杂结构
- 配比护栏: 变异/交叉各≥10%且合计50%重归一化, 扰动/引导/随机固定15/20/15(中金规格) -> mix=[0.1, 0.4, 0.15, 0.2, 0.15]

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 5]  min_stab=0.3  decorr=0.75  fsa_th=0.15  bank_skel_max=1
leaf_w={}
```

**LLM 引导(A角 2代)**: 调用3次, 解析通过34条, 引导位使用34条
> 资金流的方向与量级出现跨规模背离（超大单/大单主动净买入持续、中小单反向），且这种背离与价格变化强度不匹配时，未来5日截面收益会向资金流主导方向回归。


**LLM 候选审查(B角 2代)**: 深判 5 个, KILL 0 个(剔除出 L2 费后回测)
> (全部 PASS)


**AI 审查(DeepSeek deepseek-flash, 2s)**:

> (1)病根是信号太弱且同质:IC上限仅0.046、neg_yr几乎全挂,叶子又扎堆amplitude/barra波动,复杂度换不来增量。
> 
> (2)交叉+15%对症(需组合增量),但depth放宽到3~5与min_stab降到0.3互相冲突:弱信号再降稳定门槛只会放大噪声,且0通过不是深度不够而是IC天花板低;扰动/引导固定15/20偏高,在弱信号下浪费预算。
> 
> (3)我建议mix=[0.15,0.35,0.1,0.15,0.25],depth=[2,3,4],min_stab=0.6,decorr=0.85。理由:多留随机与变异拓新,收紧稳定与去相关,先抬IC质量再谈深度。

## 第 3 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 45 | 0.014 | 0.034 | 0.970 | 0.000 | 0.222 | 1.000 | 13 | 0.311 | 30 | 0 | 0.041 | 1.000 | 0.000 | 0.933 | 0.400 | 0.633 | 0.667 |

叶子使用: {'ln_volume': 10, 'true_range': 7, 'barra_residual_volatility': 7, 'mf_m_bqty': 6, 'mf_m_sell': 6, 'mf_m_buy': 6}

**B角建议(下一代策略)**:
- L2中100%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 本代0通过 -> 深度放宽到3~5, 探索更复杂结构
- 配比护栏: 变异/交叉各≥10%且合计50%重归一化, 扰动/引导/随机固定15/20/15(中金规格) -> mix=[0.1, 0.4, 0.15, 0.2, 0.15]

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 5]  min_stab=0.3  decorr=0.75  fsa_th=0.15  bank_skel_max=1
leaf_w={}
```

**LLM 引导(A角 3代)**: 调用3次, 解析通过30条, 引导位使用30条
> 大单与超大单主动资金持续净流入、而中小单反向净流出的结构性失衡，会在未来5日截面收益上形成可延续的超额（聪明钱吸收散户抛压/散户接盘被机构吸筹），且该失衡在超大单方向与价格变化背离时更强。


**LLM 候选审查(B角 3代)**: 深判 5 个, KILL 3 个(剔除出 L2 费后回测)
- KILL `ts_mean20(ts_std150(ts_max20(corr60(mf_m_bqty, mf_m_sell))))`
  > 理由: 多层同源时序算子嵌套冗余，窗口20/60/150无机制依据，经济含义拼凑难解释
- KILL `corr60(cs_scale(cs_scale(corr20(ts_std100(mf_s_sqty), corr60(up_shadow, barra_residual_volatility)))), barra_earnings_yield)`
  > 理由: 多层嵌套corr/cs_scale拼凑，无清晰量价机制，参数冗余似过拟合
- KILL `corr200(fa_np_margin, max(ts_mean200(div(barra_non_linear_size, barra_book_to_price)), div(ts_mean5(hl_ratio), mul(mf_l_sell, fa_np_yoy))))`
  > 理由: 多字段多层嵌套拼凑，经济含义不可解释，属参数海捞针


**AI 审查(DeepSeek deepseek-flash, 2s)**:

> (1)病根:IC量级0.014、L2全灭且neg_yr普遍3~6,是信号本身弱且不稳健,不是深度不够。
> 
> (2)建议基本不对症:加深到3~5只会放大弱信号过拟合;交叉+15%在叶子高度集中于ln_volume/量类时徒增同质后代;min_stab从0.97骤降到0.3与"求稳"目标自相矛盾;decorr=0.75与交叉扩张冲突,会互相抵消。真正该动的是叶子多样性与因子族去重。
> 
> (3)我的取值:mix=[0.25,0.15,0.2,0.25,0.15],depth=[2,3],min_stab=0.85,decorr=0.6。理由:先扩叶子多样性、压同质交叉,再谈深度。

## 第 4 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 34 | 0.010 | 0.032 | 0.972 | 0.000 | 0.118 | 0.971 | 12 | 0.176 | 30 | 1 | 0.069 | 1.000 | 0.138 | 1.000 | 0.448 | 0.828 | 0.800 |

叶子使用: {'overnight': 4, 'mf_s_bqty': 4, 'mf_l_buy': 4, 'barra_momentum': 3, 'intraday': 3, 'fa_lev': 3}

**B角建议(下一代策略)**:
- L2中100%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 配比护栏: 变异/交叉各≥10%且合计50%重归一化, 扰动/引导/随机固定15/20/15(中金规格) -> mix=[0.173, 0.327, 0.15, 0.2, 0.15]

```
mix=[0.173, 0.327, 0.15, 0.2, 0.15]  depth=[3, 4, 4]  min_stab=0.3  decorr=0.75  fsa_th=0.15  bank_skel_max=1
leaf_w={}
```

**LLM 引导(A角 4代)**: 调用3次, 解析通过34条, 引导位使用34条
> 主动资金流内部结构失衡(超大单与中小单方向背离、净买入占比与价格变化不匹配)反映知情交易者与噪音交易者的分歧,该分歧在截面上的短期累积可预测未来5日收益。


**LLM 候选审查(B角 4代)**: 深判 5 个, KILL 2 个(剔除出 L2 费后回测)
- KILL `max(corr100(mf_l_sell, true_range), ts_delta5(down_shadow))`
  > 理由: max拼接相关性与影线变化，量价含义拼凑，无统一经济机制，属数学巧合
- KILL `corr100(true_range, min(ret, barra_comovement))`
  > 理由: 真实波幅与收益/共动取min后相关，经济含义拼凑，属数学巧合


**AI 审查(DeepSeek deepseek-flash, 2s)**:

> (1)病根:IC中位仅0.010、L2几乎全被Calmar与负年数双杀,信号方向弱且不稳定,加深交叉只会放大噪声。
> 
> (2)建议不对症:交叉+15%与深度加深冲突,弱信号下交叉易产近重复高相关子代;扰动/引导/随机固定15/20/15挤占探索,decorr=0.75偏松无法压leaf_conc;min_stab=0.3过低会放行stab不足候选,与"信号弱"矛盾。
> 
> (3)我取mix=[0.30,0.15,0.15,0.20,0.20],depth=[2,3,3],min_stab=0.6,decorr=0.85。理由:先保变异探索与稳定门槛,压交叉防同质,再谈加深。

## 第 5 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 24 | 0.024 | 0.046 | 0.979 | 0.000 | 0.250 | 0.875 | 4 | 0.167 | 24 | 0 | 0.103 | 1.000 | 0.083 | 1.000 | 0.417 | 0.458 | 0.750 |

叶子使用: {'overnight': 6, 'barra_momentum': 4, 'volume': 3, 'fa_op_yoy': 3, 'barra_non_linear_size': 3, 'intraday': 2}

**B角建议(下一代策略)**:
- L2中100%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 本代0通过 -> 深度放宽到3~5, 探索更复杂结构
- 配比护栏: 变异/交叉各≥10%且合计50%重归一化, 扰动/引导/随机固定15/20/15(中金规格) -> mix=[0.1, 0.4, 0.15, 0.2, 0.15]

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 5]  min_stab=0.3  decorr=0.75  fsa_th=0.15  bank_skel_max=1
leaf_w={}
```

**LLM 引导(A角 5代)**: 调用3次, 解析通过31条, 引导位使用31条
> 资金流内部结构失衡（超大单主动净买入相对中小单的背离、且与价格变化不匹配）能在未来5日截面收益上产生反转/延续，而风格暴露的短期偏离与财报景气的加速度会放大这一效应。


**LLM 候选审查(B角 5代)**: 深判 5 个, KILL 2 个(剔除出 L2 费后回测)
- KILL `ts_min100(add(mf_x_bqty, volume))`
  > 理由: 主动买量与成交量原始尺度相加无经济含义，纯数学拼凑，且与成交额老故事同构
- KILL `ts_delta120(ts_mean200(barra_size))`
  > 理由: 仅对市值因子做长窗口平滑再差分，无增量机制，属市值老故事再表达


**AI 审查(DeepSeek deepseek-flash, 2s)**:

> (1)病根在L2信号强度不足且时序同质化：overnight系占4/6且互为近亲，Calmar与neg_yr双杀，非深度不够。
> 
> (2)交叉+15%对症但方向错，同质overnight交叉只会更同质；深度放宽到3~5无效，L1头部已是std/mean类浅结构，加深只增过拟合；扰动/引导/随机固定15/20/15与交叉40合计超100%需重归一，实际交叉被稀释，护栏自相矛盾；min_stab=0.3过松会放行噪声。
> 
> (3)建议mix=[0.25,0.15,0.15,0.25,0.20]，depth=[2,3]，min_stab=0.6，decorr=0.85。理由：提变异与引导、压交叉，靠去相关打破overnight家族垄断，浅深度保稳健。

## 第 5 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 29 | 0.014 | 0.033 | 0.982 | 0.000 | 0.207 | 0.931 | 2 | 0.276 | 29 | 0 | 0.030 | 1.000 | 0.000 | 1.000 | 0.310 | 0.862 | 0.655 |

叶子使用: {'overnight': 6, 'barra_momentum': 4, 'low': 4, 'ln_mktcap': 4, 'mf_s_bqty': 3, 'barra_size': 3}

**B角建议(下一代策略)**:
- L2中100%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 本代0通过 -> 深度放宽到3~5, 探索更复杂结构
- 配比护栏: 变异/交叉各≥10%且合计50%重归一化, 扰动/引导/随机固定15/20/15(中金规格) -> mix=[0.1, 0.4, 0.15, 0.2, 0.15]

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 5]  min_stab=0.3  decorr=0.75  fsa_th=0.15  bank_skel_max=1
leaf_w={}
```

**LLM 引导(A角 5代)**: 调用3次, 解析通过22条, 引导位使用22条
> 主动资金流内部存在稳定的结构性失衡——大单/超大单的主动净买入占比相对中小单持续走强时，代表知情资金在吸筹，该股未来5日截面收益更高；反之中小单净买入占比相对大单走强则预示散户接盘、收益走低。


**LLM 候选审查(B角 5代)**: 深判 5 个, KILL 5 个(剔除出 L2 费后回测)
- KILL `mul(cs_demean(corr100(volume, ln_volume)), max(ts_std150(up_shadow), barra_momentum))`
  > 理由: volume与ln_volume同源自相关，再乘动量与上影线，结构拼凑无清晰量价机制
- KILL `ts_mean100(ts_mean120(ts_delta60(ts_std200(high))))`
  > 理由: 多层同源时序算子嵌套，窗口60/100/120/200无经济含义，纯参数海冗余，难解释
- KILL `corr100(ts_std20(fa_lev), barra_momentum)`
  > 理由: 杠杆波动率与动量相关，含义拼凑且与已知动量/风险因子高度同构，无增量机制
- KILL `corr100(div(corr200(mf_x_buy, mf_l_sqty), mktcap), low)`
  > 理由: 嵌套相关再除以市值，结构冗余且与市值老故事同构，经济含义不清
- KILL `ts_mean120(ts_mean120(ts_delta5(intraday)))`
  > 理由: 双层同源均值嵌套冗余，仅平滑短期日内差分，无明确量价机制，疑参数海捞针


**AI 审查(DeepSeek deepseek-flash, 2s)**:

> (1)病根:IC中位仅0.014且L2全灭于Calmar与负年,信号太弱,加复杂度只会放大噪声而非提纯。
> 
> (2)建议基本不对症:交叉+15%与深度放宽到3~5互相冲突,弱信号下更深结构更易过拟合;min_stab从0.98骤降到0.3会放行大量不稳因子,与decorr=0.75叠加反而稀释有效信号;扰动/引导/随机固定值未针对overnight、barra_momentum叶子过度集中(conc=0.207)做去重,治标不治本。
> 
> (3)建议mix=[0.25,0.15,0.2,0.25,0.15],depth=[2,3],min_stab=0.85,decorr=0.6。理由:弱IC阶段应压交叉、提变异与引导,浅深度保稳定,高stab门槛先筛出可用的弱但稳信号。

## 第 6 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 19 | 0.025 | 0.046 | 0.969 | 0.000 | 0.158 | 1.000 | 8 | 0.211 | 19 | 0 | 0.103 | 1.000 | 0.105 | 1.000 | 0.632 | 0.368 | 0.632 |

叶子使用: {'amplitude': 3, 'barra_momentum': 3, 'barra_size': 2, 'true_range': 2, 'overnight': 2, 'volume': 2}

**B角建议(下一代策略)**:
- L2中100%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 本代0通过 -> 深度放宽到3~5, 探索更复杂结构
- 配比护栏: 变异/交叉各≥10%且合计50%重归一化, 扰动/引导/随机固定15/20/15(中金规格) -> mix=[0.1, 0.4, 0.15, 0.2, 0.15]

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 5]  min_stab=0.3  decorr=0.75  fsa_th=0.15  bank_skel_max=1
leaf_w={}
```

**LLM 引导(A角 6代)**: 调用3次, 解析通过29条, 引导位使用29条
> 主动资金流的方向性失衡在大单与中小单之间出现背离时，反映知情交易者与散户的分歧，这种分歧会在未来5日截面收益上产生可预测的均值回复或延续。


**LLM 候选审查(B角 6代)**: 深判 5 个, KILL 3 个(剔除出 L2 费后回测)
- KILL `add(barra_residual_volatility, barra_non_linear_size)`
  > 理由: 两个Barra风格因子直接相加，无经济机制，纯属拼凑，且与市值/波动率老故事同构
- KILL `ts_delta120(ts_mean200(barra_size))`
  > 理由: 仅对市值做长窗口均值差分，属市值老故事再表达，无增量量价机制
- KILL `corr20(ts_sum20(amplitude), barra_liquidity)`
  > 理由: 振幅求和与流动性做相关，含义拼凑且与流动性老因子同构，无增量机制


**AI 审查(DeepSeek deepseek-flash, 2s)**:

> (1)病根:叶子过度集中在amplitude等少数低IC维度,信号弱且同质,Calmar与负年全线崩,加深结构只会放大噪声。
> 
> (2)交叉+15%对症但方向错:问题不是结构简单,是信号源单一,应加叶子多样性而非深度。depth放宽到3~5有害,复杂结构在弱信号下更易过拟合。min_stab=0.3与L1高stab(0.97)矛盾,会放行不稳因子。decorr=0.75偏低,难破同质。mix中随机15%过高,浪费预算。
> 
> (3)建议mix=[0.15,0.25,0.15,0.35,0.10],depth=[2,3],min_stab=0.6,decorr=0.85。理由:提高引导与变异占比以扩叶子多样性,收紧稳定与去相关门槛,压随机,深度保守防过拟合。

## 第 7 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 18 | 0.030 | 0.046 | 0.953 | 0.000 | 0.389 | 0.944 | 4 | 0.111 | 18 | 0 | 0.046 | 1.000 | 0.056 | 0.944 | 0.611 | 0.167 | 0.500 |

叶子使用: {'amplitude': 7, 'barra_residual_volatility': 4, 'volume': 4, 'mf_m_bqty': 4, 'intraday': 4, 'barra_momentum': 4}

**B角建议(下一代策略)**:
- L2中100%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 本代0通过 -> 深度放宽到3~5, 探索更复杂结构
- 配比护栏: 变异/交叉各≥10%且合计50%重归一化, 扰动/引导/随机固定15/20/15(中金规格) -> mix=[0.1, 0.4, 0.15, 0.2, 0.15]

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 5]  min_stab=0.3  decorr=0.75  fsa_th=0.15  bank_skel_max=1
leaf_w={}
```

**LLM 引导(A角 7代)**: 调用3次, 解析通过41条, 引导位使用41条
> 资金流强度与价格反应背离时，聪明钱的方向信息尚未被价格吸收，未来5日截面收益将向主动净买入占比高（尤其超大单）且价格滞涨的股票倾斜。


**LLM 候选审查(B角 7代)**: 深判 5 个, KILL 3 个(剔除出 L2 费后回测)
- KILL `ts_mean10(ts_mean60(sub(ts_mean200(overnight), ts_mean200(barra_comovement))))`
  > 理由: 嵌套三层同源ts_mean且窗口200/60/10冗余，overnight与barra_comovement相减含义拼凑，无清晰量价机制
- KILL `sub(ts_mean60(turn_ratio), barra_residual_volatility)`
  > 理由: 换手率均值减残差波动率，量纲与含义拼凑，无清晰量价机制，属数学巧合
- KILL `add(neg(log(ts_mean120(ts_mean100(overnight)))), mul(ts_mean20(corr60(down_shadow, down_shadow)), min(corr20(fa_lev, mktcap), sub(barra_liquidity, fa_op_yoy))))`
  > 理由: 结构拼凑：隔夜收益与影线自相关、杠杆市值相关、流动性基本面混搭，无统一经济机制，冗余难解释


**AI 审查(DeepSeek deepseek-flash, 2s)**:

> (1)病根:IC天花板仅0.046且叶子高度挤在amplitude类,信号同质,Calmar与负年双杀,非深度不足。
> 
> (2)建议错配:把Calmar不足归因"信号弱"去加深交叉,方向反了——IC已封顶,加深只会更过拟合,负年7个是主因。交叉40%在18个L1上会近亲繁殖,与decorr=0.75冲突;min_stab从0.95骤降到0.3会放行大量不稳个体,与"提Calmar"目标打架;扰动/引导/随机固定值未针对叶子集中做去重。
> 
> (3)我取mix=[0.2,0.15,0.2,0.25,0.2],depth=[2,3],min_stab=0.6,decorr=0.85。理由:提变异与引导去同质、控深度防过拟合、稳门槛保Calmar。

## 第 8 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 25 | 0.030 | 0.047 | 0.967 | 0.000 | 0.480 | 0.960 | 1 | 0.200 | 25 | 0 | 0.047 | 1.000 | 0.040 | 0.920 | 0.360 | 0.160 | 0.480 |

叶子使用: {'barra_residual_volatility': 12, 'amplitude': 7, 'turn_ratio': 6, 'mf_s_bqty': 4, 'barra_momentum': 4, 'ln_volume': 4}

**B角建议(下一代策略)**:
- 叶子[barra_residual_volatility]占比48%过高 -> 权重压到0.25, 逼引擎换字段
- L2中100%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 本代0通过 -> 深度放宽到3~5, 探索更复杂结构
- 配比护栏: 变异/交叉各≥10%且合计50%重归一化, 扰动/引导/随机固定15/20/15(中金规格) -> mix=[0.1, 0.4, 0.15, 0.2, 0.15]

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 5]  min_stab=0.3  decorr=0.75  fsa_th=0.15  bank_skel_max=1
leaf_w={'barra_residual_volatility': 0.25}
```

**LLM 引导(A角 8代)**: 调用3次, 解析通过24条, 引导位使用24条
> 资金流内部主动买卖方向的错位(超大单与中小单净买入背离、主动买入金额与股数不匹配)会在未来5日截面收益上产生反转/延续,且该错位与价格趋势的背离比单纯资金流强度更稳定。


**LLM 候选审查(B角 8代)**: 深判 5 个, KILL 2 个(剔除出 L2 费后回测)
- KILL `add(barra_residual_volatility, mul(ts_mean20(corr60(down_shadow, down_shadow)), min(corr20(fa_lev, mktcap), sub(barra_liquidity, ts_max100(barra_residual_volatility)))))`
  > 理由: corr(down_shadow,down_shadow)恒为1，结构冗余且含无意义自相关，经济含义拼凑
- KILL `ts_std150(ts_std60(barra_residual_volatility))`
  > 理由: 双层同源ts_std嵌套冗余，仅再表达波动率老故事，无增量机制


**AI 审查(DeepSeek deepseek-flash, 2s)**:

> (1)病根:IC天花板仅0.047且Calmar全负,信号太弱,不是结构不够复杂,而是有效alpha源枯竭。
> 
> (2)叶子压权重对症但会误伤amplitude等次优源;交叉+15%与深度加深对弱信号无效,只会放大过拟合;0通过就放宽深度到5是危险信号,neg_yr=0.92说明是方向/稳定性问题非复杂度;mix固定15/20/15与"交叉≥10%"护栏自洽但变异仅10%偏低,探索不足。
> 
> (3)mix=[0.2,0.3,0.15,0.2,0.15],depth=[2,3,4],min_stab=0.5,decorr=0.8。理由:弱信号期应控复杂度、保稳定、强去相关,而非堆深度。

## 第 9 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 46 | 0.014 | 0.046 | 0.967 | 0.000 | 0.196 | 0.957 | 2 | 0.174 | 30 | 0 | 0.042 | 1.000 | 0.067 | 1.000 | 0.300 | 0.567 | 0.667 |

叶子使用: {'amplitude': 9, 'barra_residual_volatility': 8, 'barra_momentum': 6, 'turn_ratio': 6, 'intraday': 5, 'mf_m_sqty': 4}

**B角建议(下一代策略)**:
- L2中100%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 本代0通过 -> 深度放宽到3~5, 探索更复杂结构
- 配比护栏: 变异/交叉各≥10%且合计50%重归一化, 扰动/引导/随机固定15/20/15(中金规格) -> mix=[0.1, 0.4, 0.15, 0.2, 0.15]

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 5]  min_stab=0.3  decorr=0.75  fsa_th=0.15  bank_skel_max=1
leaf_w={'barra_residual_volatility': 0.25}
```

**LLM 引导(A角 9代)**: 调用3次, 解析通过38条, 引导位使用38条
> 在残差波动率主导的风格环境下，日内价格位置相对成交均价（vwap）的偏离，叠加隔夜跳空溢价衰减与价量背离，能够刻画短周期资金承接强度与筹码交换效率，从而预测未来5日截面收益。


**LLM 候选审查(B角 9代)**: 深判 5 个, KILL 4 个(剔除出 L2 费后回测)
- KILL `log(mul(ts_mean100(ts_delta120(fa_roe)), ts_mean200(ts_mean200(ln_mktcap))))`
  > 理由: ROE变化乘市值均值，量价无关且窗口冗余，属基本面拼凑，非量价行为
- KILL `ts_delta120(ts_min100(ts_mean100(mf_l_buy)))`
  > 理由: mf_l_buy为资金流字段，嵌套均值最小值再差分，无明确量价机制，属参数堆叠冗余
- KILL `add(ret, corr60(mf_m_sqty, intraday))`
  > 理由: ret与量价相关项直接相加，量纲含义拼凑，无明确经济机制
- KILL `sub(mf_l_bqty, ts_delta5(div(fa_op_yoy, fa_np_yoy)))`
  > 理由: 财务同比比值再差分与主力买量相减，量价与基本面尺度拼凑，无清晰经济机制


**AI 审查(DeepSeek deepseek-flash, 2s)**:

> (1)病根:IC中位仅0.014、L2全灭且neg_yr普遍6-7年,信号方向性弱而非结构不够复杂,加深深度只会放大噪声。
> 
> (2)建议基本不对症:交叉+15%与深度放宽到3~5互相冲突,复杂结构在弱IC下更易过拟合;min_stab=0.3过松,与L1 stab_med=0.967矛盾,会放垃圾进L2;decorr=0.75偏低,叶子已集中amplitude/barra_vol,需提高去相关;扰动/引导/随机固定值合理,可保留。
> 
> (3)取值:mix=[0.15,0.25,0.15,0.25,0.20],depth=[2,3],min_stab=0.7,decorr=0.85。理由:弱IC阶段应控复杂度、提稳定性与去相关,靠引导注入经济含义而非堆结构。

## 第 10 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 29 | 0.020 | 0.051 | 0.971 | 0.000 | 0.310 | 0.966 | 1 | 0.241 | 29 | 1 | 0.050 | 1.000 | 0.036 | 1.000 | 0.286 | 0.607 | 0.793 |

叶子使用: {'barra_momentum': 9, 'turn_ratio': 8, 'amplitude': 6, 'mf_s_bqty': 5, 'barra_residual_volatility': 4, 'ln_volume': 4}

**B角建议(下一代策略)**:
- L2中100%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 配比护栏: 变异/交叉各≥10%且合计50%重归一化, 扰动/引导/随机固定15/20/15(中金规格) -> mix=[0.1, 0.4, 0.15, 0.2, 0.15]

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 4]  min_stab=0.3  decorr=0.75  fsa_th=0.15  bank_skel_max=1
leaf_w={'barra_residual_volatility': 0.25}
```

**LLM 引导(A角 10代)**: 调用3次, 解析通过46条, 引导位使用46条
> 个股特质波动率(barra_residual_volatility)的短期相对长期抬升，叠加主动资金流失衡与日内形态背离，能刻画恐慌抛售/承接不足的截面定价错误，从而预测未来5日截面收益。


**LLM 候选审查(B角 10代)**: 深判 5 个, KILL 2 个(剔除出 L2 费后回测)
- KILL `sub(cs_scale(barra_residual_volatility), max(cs_demean(corr100(mf_s_bqty, ln_volume)), ts_mean60(barra_momentum)))`
  > 理由: 残差波动率减量价相关与动量，字段尺度与含义拼凑，无清晰经济机制，属数学巧合
- KILL `sub(corr100(mf_m_sell, ts_sum100(ts_std100(ts_std20(barra_momentum)))), max(cs_demean(corr100(mf_s_bqty, ln_volume)), ts_mean60(barra_momentum)))`
  > 理由: 多层嵌套同源动量/波动算子，经济含义拼凑难解释，属参数海捞针


**AI 审查(DeepSeek deepseek-flash, 2s)**:

> (1)病根:IC上限仅0.051且L2全灭于Calmar/负年,是信号强度与稳健性双缺,不是搜索广度不足。
> 
> (2)建议部分对症但自相矛盾:交叉+15%对弱信号无效,近亲繁殖只会放大同一弱因子;depth加深到4会加剧过拟合,与min_stab=0.3放宽稳定性直接冲突;decorr=0.75偏低,无法解决leaf_conc=0.31与momentum家族垄断;引导20%合理,应保留。
> 
> (3)我的取值:mix=[0.25,0.15,0.15,0.30,0.15],depth=[2,3,3],min_stab=0.5,decorr=0.85。理由:提高变异与引导、压低交叉和深度,先拓宽低相关骨架再谈组合,避免在弱信号上做无谓交叉。

## 第 11 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 13 | 0.027 | 0.051 | 0.990 | 0.000 | 0.538 | 0.923 | 0 | 0.077 | 13 | 0 | 0.033 | 1.000 | 0.000 | 1.000 | 0.000 | 0.846 | 0.846 |

叶子使用: {'barra_momentum': 7, 'ret': 3, 'mf_x_sell': 2, 'barra_residual_volatility': 2, 'mf_l_buy': 2, 'open': 1}

**B角建议(下一代策略)**:
- 叶子[barra_momentum]占比54%过高 -> 权重压到0.25, 逼引擎换字段
- L2中100%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 本代0通过 -> 深度放宽到3~5, 探索更复杂结构
- 配比护栏: 变异/交叉各≥10%且合计50%重归一化, 扰动/引导/随机固定15/20/15(中金规格) -> mix=[0.1, 0.4, 0.15, 0.2, 0.15]

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 5]  min_stab=0.3  decorr=0.75  fsa_th=0.15  bank_skel_max=1
leaf_w={'barra_residual_volatility': 0.25, 'barra_momentum': 0.25}
```

**LLM 引导(A角 11代)**: 调用3次, 解析通过39条, 引导位使用39条
> 在残差波动率风格暴露高企的股票中，日内价格路径的'量价背离'与'主动资金流失衡'所隐含的短期错误定价更易在5日内修复，即高残差波动+价量背离/资金流背离的交互能预测截面收益反转。


**LLM 候选审查(B角 11代)**: 深判 5 个, KILL 3 个(剔除出 L2 费后回测)
- KILL `ts_std200(ts_std100(corr100(ts_rank60(turn_ratio), mf_m_sell)))`
  > 理由: 换手率与卖单资金相关性的波动率，多层同源嵌套且窗口60/100/200冗余，无清晰增量机制
- KILL `sub(ts_std60(cs_scale(amplitude)), corr200(ts_mean10(mf_x_sell), corr100(mf_l_buy, mktcap)))`
  > 理由: 振幅波动与资金流-市值相关量纲相减，含义拼凑，窗口冗余无经济机制
- KILL `ts_sum20(ts_mean20(corr200(ts_std200(mf_x_sell), mf_m_sell)))`
  > 理由: 多层同源时序算子嵌套冗余，窗口20/200无机制，经济含义拼凑难解释


**AI 审查(DeepSeek deepseek-flash, 2s)**:

> (1)病根:IC天花板太低且全挤在barra_momentum残差上,信号弱导致Calmar全灭,不是结构复杂度不够。
> 
> (2)压权重0.25对症但会误伤唯一有效字段;交叉+15%与深度3~5冲突,弱信号下加深只会放大噪声;min_stab从0.99骤降到0.3自毁稳定性护栏,与decorr0.75矛盾;固定15/20/15挤占交叉空间,重归一化后实际变异被稀释。
> 
> (3)mix=[0.2,0.3,0.15,0.2,0.15],depth=[2,3],min_stab=0.6,decorr=0.6。理由:先保稳定与去相关,靠变异换字段而非加深,弱信号下深度是毒药。

## 第 12 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | gate_min_calmar | gate_min_pool_calmar | fail_calmar | fail_calmar_neg | fail_pool_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 33 | 0.014 | 0.033 | 0.985 | 0.030 | 0.242 | 0.970 | 5 | 0.061 | 30 | 0 | 0.033 | 0.000 | 0.150 | 0.800 | 0.800 | 0.633 | 0.200 | 1.000 | 0.500 | 0.900 | 0.867 |

叶子使用: {'barra_momentum': 8, 'close': 7, 'mf_s_buy': 6, 'mf_l_bqty': 5, 'true_range': 5, 'fa_gm': 5}

**B角建议(下一代策略)**:
- 【r5_calmar_cross】L2中63%因Calmar不足[池口径: 任一池 Calmar > 0.15] -> 交叉+15%, 深度加深
- 【r7_zero_pass】本代0通过 -> 深度放宽到3~5, 探索更复杂结构
- 配比护栏: 变异/交叉各≥10%且合计50%重归一化, 扰动/引导/随机固定15/20/15(中金规格) -> mix=[0.1, 0.4, 0.15, 0.2, 0.15]

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 5]  min_stab=0.3  decorr=0.75  fsa_th=0.15  bank_skel_max=1
leaf_w={'barra_residual_volatility': 0.25, 'barra_momentum': 0.25}
```

**规则动作留痕**:
- `r1_leaf_conc` 叶子过度集中 -> 压低该叶子权重 —— 施加于第 [12] 代
- `r5_calmar_cross` L2 多因 Calmar 不足 -> 交叉+15% / 深度加深 —— 施加于第 [12, 13] 代
- `r7_zero_pass` 本代 0 通过 -> 深度放宽到 3~5 —— 施加于第 [12, 13] 代

**LLM 引导(A角 12代)**: 调用3次, 解析通过35条, 引导位使用35条
> 个股特质波动率与动量在截面上的背离（高特质波动+近期动量衰减的股票）会因风险补偿错配而在未来5日出现截面收益反转，且该效应被资金流大单方向与财报景气度调节。


**LLM 候选审查(B角 12代)**: 深判 5 个, KILL 4 个(剔除出 L2 费后回测)
- KILL `max(mul(corr100(up_shadow, low), barra_liquidity), sub(ts_rsqr20(hl_ratio), ts_skew20(barra_size)))`
  > 理由: 多算子嵌套拼凑，经济含义不清，疑参数海捞针且与流动性/市值同源冗余
- KILL `ts_mean5(ts_sum20(div(corr200(fa_gm, mf_s_buy), mf_s_sqty)))`
  > 理由: corr200后除以同源量字段再双层平滑，经济含义不清且窗口冗余，疑参数拼凑
- KILL `ts_mean20(ts_mean100(ts_mean150(corr20(amplitude, ts_mean150(true_range)))))`
  > 理由: 多层同源均值嵌套冗余，corr后反复平滑无增量机制，参数堆砌难解释
- KILL `add(barra_leverage, ts_mean100(ts_mean10(ts_kurt20(overnight))))`
  > 理由: barra_leverage与隔夜跳空峰度均值相加，量纲与含义拼凑，无清晰量价机制，属数学巧合


**AI 审查(DeepSeek deepseek-flash, 2s)**:

> (1)病根:IC天花板太低(ic_max=0.033)且negyear全灭,不是深度不够,是信号本身没有跨年稳定性。
> 
> (2)r5_calmar_cross:对症但方向反了,Calmar差源于IC弱,加深交叉只会放大噪声;r7_zero_pass:与r5冲突,两者同时放宽深度会让搜索空间爆炸,且0通过的真因是fail_negyear=1.0和fail_ic=0.9,不是复杂度;r1_leaf_conc:leaf_conc=0.242并不高,barra_momentum占8属正常,压权重无效。
> 
> (3)mix=[0.25,0.25,0.15,0.2,0.15],depth=[2,3],min_stab=0.5,decorr=0.7。理由:先保稳定性和低复杂度,把预算还给变异而非交叉。
> 
> (4)否决见下。
> 
> 否决: r5_calmar_cross,r7_zero_pass,r1_leaf_conc

**⚖️ 规则动作否决（机器读取）**: `r5_calmar_cross`（L2 多因 Calmar 不足 -> 交叉+15% / 深度加深）, `r7_zero_pass`（本代 0 通过 -> 深度放宽到 3~5）, `r1_leaf_conc`（叶子过度集中 -> 压低该叶子权重）

## 第 13 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | gate_min_calmar | gate_min_pool_calmar | fail_calmar | fail_calmar_neg | fail_pool_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 33 | 0.014 | 0.033 | 0.993 | 0.000 | 0.333 | 0.909 | 8 | 0.030 | 30 | 0 | 0.021 | 0.000 | 0.150 | 0.767 | 0.767 | 0.500 | 0.000 | 1.000 | 0.333 | 0.967 | 0.767 |

叶子使用: {'barra_momentum': 11, 'mf_s_buy': 9, 'close': 8, 'fa_gm': 6, 'mf_s_sqty': 6, 'barra_liquidity': 6}

**B角建议(下一代策略)**:
- 【拦截】[r7_zero_pass] 已连续 2 代施加 -> 判为饱和（条件恒真=固定偏移），冷却到第 17 代再评估 —— 本代 0 通过 -> 深度放宽到 3~5
- —— 本代共拦截 1 条动作（饱和/LLM 否决），详见上面【拦截】行

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 5]  min_stab=0.3  decorr=0.75  fsa_th=0.15  bank_skel_max=1
leaf_w={'barra_residual_volatility': 0.25, 'barra_momentum': 0.25}
```

**规则动作留痕**:
- `r1_leaf_conc` 叶子过度集中 -> 压低该叶子权重 —— 施加于第 [12] 代
- `r5_calmar_cross` L2 多因 Calmar 不足 -> 交叉+15% / 深度加深 —— 施加于第 [12, 13] 代
- `r7_zero_pass` 本代 0 通过 -> 深度放宽到 3~5 —— 施加于第 [12, 13] 代

**LLM 引导(A角 13代)**: 调用3次, 解析通过45条, 引导位使用45条
> 在风格暴露（残差波动率、动量）主导的环境下，个股主动资金流的大小单方向背离与量价跳空结构共同刻画了知情交易者的隐蔽吸筹/派发，这种'资金流-价格-波动'三重错位会在未来5日截面收益上产生修正性回归。


## 第 14 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | gate_min_calmar | gate_min_pool_calmar | fail_calmar | fail_calmar_neg | fail_pool_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 32 | 0.015 | 0.033 | 0.992 | 0.000 | 0.469 | 0.938 | 4 | 0.000 | 30 | 0 | 0.021 | 0.000 | 0.150 | 0.800 | 0.800 | 0.567 | 0.000 | 1.000 | 0.400 | 1.000 | 0.867 |

叶子使用: {'barra_momentum': 15, 'mf_s_buy': 10, 'mf_s_sqty': 8, 'fa_gm': 7, 'close': 5, 'turn_ratio': 4}

**B角建议(下一代策略)**:
- 【r1_leaf_conc】叶子[barra_momentum]占比47%过高 -> 权重压到0.25, 逼引擎换字段
- 【r5_calmar_cross】L2中57%因Calmar不足[池口径: 任一池 Calmar > 0.15] -> 交叉+15%, 深度加深
- 【拦截】[r7_zero_pass] 饱和冷却中（第 17 代自动解禁） —— 本代 0 通过 -> 深度放宽到 3~5
- —— 本代共拦截 1 条动作（饱和/LLM 否决），详见上面【拦截】行
- 配比护栏: 变异/交叉各≥10%且合计50%重归一化, 扰动/引导/随机固定15/20/15(中金规格) -> mix=[0.1, 0.4, 0.15, 0.2, 0.15]

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 4]  min_stab=0.3  decorr=0.75  fsa_th=0.15  bank_skel_max=1
leaf_w={'barra_residual_volatility': 0.25, 'barra_momentum': 0.25}
```

**规则动作留痕**:
- `r1_leaf_conc` 叶子过度集中 -> 压低该叶子权重 —— 施加于第 [12, 15] 代
- `r5_calmar_cross` L2 多因 Calmar 不足 -> 交叉+15% / 深度加深 —— 施加于第 [12, 13, 15] 代
- `r7_zero_pass` 本代 0 通过 -> 深度放宽到 3~5 —— 施加于第 [12, 13] 代

**LLM 引导(A角 14代)**: 调用3次, 解析通过0条, 引导位使用0条
> (本次无机制族假设)


**LLM 候选审查(B角 14代)**: 深判 4 个, KILL 2 个(剔除出 L2 费后回测)
- KILL `sub(corr200(mf_x_buy, corr200(barra_size, ret)), div(corr200(fa_gm, mf_s_buy), mf_s_sqty))`
  > 理由: 多层嵌套corr与div拼凑，经济含义不明，属数学巧合结构
- KILL `min(ts_mean200(mul(min(ts_slope20(turn_ratio), corr200(barra_leverage, mf_m_buy)), min(add(barra_momentum, corr200(mf_x_buy, corr200(barra_size, ret))), corr100(low, mf_s_buy)))), mf_l_sell)`
  > 理由: 多层min/mul/corr嵌套拼凑，无清晰量价机制，参数冗余似过拟合


**AI 审查(DeepSeek deepseek-flash, 2s)**:

> (1) 病根: 0通过不是深度不够, 是IC天花板0.033配Calmar全负, 因子方向性太弱, 加深只会放大噪声。
> 
> (2) r1_leaf_conc对症但0.25过猛, 会连带砍掉唯一IC最高项; r5_calmar_cross误诊, Calmar差源于IC弱非结构不足, 交叉+15%与r7深度放宽叠加, 搜索空间爆炸而信号不变; r7_zero_pass与r5同向加深度, 二者冲突冗余。
> 
> (3) mix=[0.25,0.15,0.2,0.25,0.15], depth=[2,3,3], min_stab=0.5, decorr=0.6; 理由: 收窄深度、提变异与引导、降相关阈值, 逼引擎换字段而非堆结构。
> 
> 否决: r5_calmar_cross,r7_zero_pass

**⚖️ 规则动作否决（机器读取）**: `r5_calmar_cross`（L2 多因 Calmar 不足 -> 交叉+15% / 深度加深）, `r7_zero_pass`（本代 0 通过 -> 深度放宽到 3~5）

## 第 15 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | gate_min_calmar | gate_min_pool_calmar | fail_calmar | fail_calmar_neg | fail_pool_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 29 | 0.014 | 0.033 | 0.996 | 0.000 | 0.414 | 0.897 | 3 | 0.034 | 29 | 0 | 0.005 | 0.000 | 0.150 | 0.862 | 0.862 | 0.483 | 0.000 | 1.000 | 0.345 | 1.000 | 0.931 |

叶子使用: {'barra_momentum': 12, 'close': 7, 'mf_s_buy': 7, 'mf_s_sqty': 6, 'low': 6, 'vwap': 5}

**B角建议(下一代策略)**:
- 【r1_leaf_conc】叶子[barra_momentum]占比41%过高 -> 权重压到0.25, 逼引擎换字段
- 【拦截】[r7_zero_pass] LLM 已【永久】否决，后续各代一律不再施加 —— 本代 0 通过 -> 深度放宽到 3~5
- —— 本代共拦截 1 条动作（饱和/LLM 否决），详见上面【拦截】行

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 4]  min_stab=0.3  decorr=0.75  fsa_th=0.15  bank_skel_max=1
leaf_w={'barra_residual_volatility': 0.25, 'barra_momentum': 0.25}
```

**规则动作留痕**:
- `r1_leaf_conc` 叶子过度集中 -> 压低该叶子权重 —— 施加于第 [12, 15, 16] 代
- `r5_calmar_cross` L2 多因 Calmar 不足 -> 交叉+15% / 深度加深 —— 施加于第 [12, 13, 15] 代（**已永久关闭**）
- `r7_zero_pass` 本代 0 通过 -> 深度放宽到 3~5 —— 施加于第 [12, 13] 代（**已永久关闭**）
- ⛔ **被 LLM 永久否决的动作**（用户要求「让它永久闭嘴」）：`r5_calmar_cross`, `r7_zero_pass`

**LLM 引导(A角 15代)**: 调用3次, 解析通过45条, 引导位使用45条
> 在残余波动率高、动量风格主导的市场环境中，隔夜跳空与日内收益的背离（跳空溢价被日内反转抵消）以及主动资金流与价格变化的量额不匹配，能预测未来5日截面收益的反转/延续。


**LLM 候选审查(B角 15代)**: 深判 5 个, KILL 4 个(剔除出 L2 费后回测)
- KILL `sub(ts_mean200(ts_skew60(ts_mean200(close))), div(corr200(fa_gm, low), mf_s_sqty))`
  > 理由: 多层同源嵌套冗余，fa_gm与mf_s_sqty含义拼凑，无清晰量价机制
- KILL `ts_slope60(ts_mean60(ts_mean60(cs_demean(fa_lev))))`
  > 理由: fa_lev为财务杠杆非量价字段，且三重同源平滑冗余，无增量机制
- KILL `ts_mean20(log(ts_mean200(abs(ts_mean200(barra_residual_volatility)))))`
  > 理由: 三层同源ts_mean嵌套+abs+log，纯平滑冗余无增量机制，窗口200重复属参数堆砌
- KILL `ts_mean120(sub(corr200(ts_sum20(vwap), corr200(close, barra_momentum)), corr200(close, open)))`
  > 理由: 多层嵌套corr与窗口拼凑，无清晰量价机制，属参数海捞针


**AI 审查(DeepSeek deepseek-flash, 2s)**:

> (1)病根:IC天花板0.033、stab虚高0.996却n_pass=0,说明因子全是慢速低换手的barra动量残差,预测力被风格吃掉,过拟合于稳定性而非收益。
> 
> (2)r1_leaf_conc对症但力度不足:压权重到0.25只治叶子,不治"barra_momentum当减项"这一结构性同质;depth放宽3~5与min_stab=0.3方向一致但会稀释,需警惕;r5/r7已关合理,勿复活。
> 
> (3)建议mix=[0.15,0.35,0.15,0.2,0.15],depth=[3,4,5],min_stab=0.2,decorr=0.85:提交叉与去相关,逼出非动量残差结构。
> 
> 否决: 无

## 第 16 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | gate_min_calmar | gate_min_pool_calmar | fail_calmar | fail_calmar_neg | fail_pool_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 19 | 0.017 | 0.033 | 0.997 | 0.000 | 0.474 | 0.947 | 3 | 0.053 | 19 | 0 | -0.019 | 0.000 | 0.150 | 1.000 | 1.000 | 0.632 | 0.000 | 1.000 | 0.368 | 1.000 | 1.000 |

叶子使用: {'barra_momentum': 9, 'vwap': 6, 'close': 4, 'ret': 4, 'open': 3, 'low': 3}

**B角建议(下一代策略)**:
- 【拦截】[r1_leaf_conc] 已连续 2 代施加 -> 判为饱和（条件恒真=固定偏移），冷却到第 20 代再评估 —— 叶子过度集中 -> 压低该叶子权重
- 【拦截】[r5_calmar_cross] LLM 已【永久】否决，后续各代一律不再施加 —— L2 多因 Calmar 不足 -> 交叉+15% / 深度加深
- 【拦截】[r7_zero_pass] LLM 已【永久】否决，后续各代一律不再施加 —— 本代 0 通过 -> 深度放宽到 3~5
- —— 本代共拦截 3 条动作（饱和/LLM 否决），详见上面【拦截】行

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 4]  min_stab=0.3  decorr=0.75  fsa_th=0.15  bank_skel_max=1
leaf_w={'barra_residual_volatility': 0.25, 'barra_momentum': 0.25}
```

**规则动作留痕**:
- `r1_leaf_conc` 叶子过度集中 -> 压低该叶子权重 —— 施加于第 [12, 15, 16] 代
- `r5_calmar_cross` L2 多因 Calmar 不足 -> 交叉+15% / 深度加深 —— 施加于第 [12, 13, 15] 代（**已永久关闭**）
- `r7_zero_pass` 本代 0 通过 -> 深度放宽到 3~5 —— 施加于第 [12, 13] 代（**已永久关闭**）
- ⛔ **被 LLM 永久否决的动作**（用户要求「让它永久闭嘴」）：`r5_calmar_cross`, `r7_zero_pass`

**LLM 引导(A角 16代)**: 调用3次, 解析通过46条, 引导位使用46条
> 在风格层面，当市场对高波动/高动量的拥挤暴露短期急速抬升而长期中枢未跟上时，未来5日该类风格会因拥挤回吐而跑输，故用波动与动量风格暴露的短长窗差及其与残余风险/流动性的背离来预测截面收益。


**LLM 候选审查(B角 16代)**: 深判 5 个, KILL 5 个(剔除出 L2 费后回测)
- KILL `sub(corr200(log(mf_x_sell), high), div(corr200(fa_gm, corr100(vwap, barra_size)), mf_s_sqty))`
  > 理由: 多字段多层嵌套拼凑，经济含义不清，窗口冗余，疑似参数海捞针
- KILL `sub(ts_mean200(corr60(abs(corr60(high, barra_momentum)), barra_momentum)), div(corr200(fa_ocf_yoy, mf_m_sell), mf_s_sqty))`
  > 理由: 多层嵌套corr与量价财务字段拼凑，无清晰经济机制，属参数海捞针
- KILL `corr200(close, corr200(close, low))`
  > 理由: close与low嵌套自相关，无明确量价经济含义，属数学巧合结构
- KILL `ts_mean5(ts_mean120(add(corr200(ts_sum20(vwap), corr200(close, barra_momentum)), barra_momentum)))`
  > 理由: 多层嵌套corr/ts_mean叠加barra_momentum，窗口冗余无清晰量价机制，疑似参数海捞针
- KILL `ts_mean60(ts_mean60(ts_mean60(ts_mean200(ret))))`
  > 理由: 多层同源ts_mean嵌套冗余，仅平滑收益，无增量量价机制，属参数堆叠


**AI 审查(DeepSeek deepseek-flash, 2s)**:

> (1) 病根:IC天花板仅0.033且L2全灭于calmar/负年,因子在barra_momentum上过度同质,是"信号太薄+换手无效"而非深度不够。
> 
> (2) r1_leaf_conc已饱和,继续压权重只会更同质,冷却正确;r5_calmar_cross、r7_zero_pass永久否决合理,但下代表格仍把depth放宽到4、mix交叉0.4,与"信号薄"病根错配,交叉放大同质噪声,可能无效甚至恶化。min_stab=0.3过松,会放进不稳叶子。
> 
> (3) mix=[0.15,0.25,0.2,0.25,0.15] depth=[2,3,3] min_stab=0.6 decorr=0.85:降交叉、提引导与扰动、收紧稳定性与去相关,逼出新正交信号而非加深同质树。
> 
> (4) 停掉已饱和且加剧同质的叶子压制。
> 
> 否决: r1_leaf_conc

**⚖️ 规则动作否决（机器读取）**: `r1_leaf_conc`（叶子过度集中 -> 压低该叶子权重）

## 第 17 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | gate_min_calmar | gate_min_pool_calmar | fail_calmar | fail_calmar_neg | fail_pool_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 20 | 0.017 | 0.040 | 0.996 | 0.000 | 0.550 | 0.950 | 7 | 0.100 | 20 | 0 | -0.012 | 0.000 | 0.150 | 1.000 | 1.000 | 0.300 | 0.000 | 1.000 | 0.350 | 0.950 | 1.000 |

叶子使用: {'barra_momentum': 11, 'open': 5, 'close': 4, 'low': 4, 'mf_m_buy': 3, 'fa_lev': 3}

**B角建议(下一代策略)**:
- 【拦截】[r1_leaf_conc] LLM 已【永久】否决，后续各代一律不再施加 —— 叶子过度集中 -> 压低该叶子权重
- 【拦截】[r7_zero_pass] LLM 已【永久】否决，后续各代一律不再施加 —— 本代 0 通过 -> 深度放宽到 3~5
- —— 本代共拦截 2 条动作（饱和/LLM 否决），详见上面【拦截】行

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 4]  min_stab=0.3  decorr=0.75  fsa_th=0.15  bank_skel_max=1
leaf_w={'barra_residual_volatility': 0.25, 'barra_momentum': 0.25}
```

**规则动作留痕**:
- `r1_leaf_conc` 叶子过度集中 -> 压低该叶子权重 —— 施加于第 [12, 15, 16] 代（**已永久关闭**）
- `r5_calmar_cross` L2 多因 Calmar 不足 -> 交叉+15% / 深度加深 —— 施加于第 [12, 13, 15] 代（**已永久关闭**）
- `r7_zero_pass` 本代 0 通过 -> 深度放宽到 3~5 —— 施加于第 [12, 13] 代（**已永久关闭**）
- ⛔ **被 LLM 永久否决的动作**（用户要求「让它永久闭嘴」）：`r5_calmar_cross`, `r7_zero_pass`, `r1_leaf_conc`

**LLM 引导(A角 17代)**: 调用3次, 解析通过34条, 引导位使用34条
> 在残余波动率高、动量风格主导的市场环境中，大单资金主动净买入的持续性（而非瞬时强度）与价格漂移形成共振，即资金流强度对价格变化的边际确认（量额匹配度）能预测未来5日截面收益，且该效应在中小单方向背离时反转。


**LLM 候选审查(B角 17代)**: 深判 5 个, KILL 4 个(剔除出 L2 费后回测)
- KILL `corr200(vwap, add(close, open))`
  > 理由: vwap与close+open同源价格相加，相关性无经济含义，纯数学巧合
- KILL `ts_mean60(ts_mean200(ts_mean200(corr60(abs(corr200(mf_l_bqty, low)), barra_momentum))))`
  > 理由: 多层同源corr/ts_mean嵌套冗余，经济含义拼凑难解释，过拟合边界模糊
- KILL `ema60(corr200(abs(log(turn_ratio)), ts_delta5(corr200(mf_s_buy, barra_momentum))))`
  > 理由: 多层嵌套corr/ema同源冗余，经济含义拼凑难解释，属参数海捞针
- KILL `ts_mean120(cs_rank(ts_mean200(corr60(abs(corr200(mf_l_bqty, low)), barra_momentum))))`
  > 理由: 多层嵌套corr/abs/rank同源冗余，无清晰量价机制，疑参数海捞针


**AI 审查(DeepSeek deepseek-flash, 2s)**:

> (1)病根:IC天花板太低(0.04)且L2全军覆没,因子在barra_momentum上过度同质,量价信息被风格吃掉,不是深度或稳定性问题。
> 
> (2)两条建议均已被永久否决,本轮无实际动作,故无对症可言;真正该做的是降barra_momentum暴露、提高decorr,而非放宽depth。depth放宽到3~5只会加剧同质搜索,与decorr目标冲突。
> 
> (3)建议mix=[0.15,0.3,0.15,0.25,0.15],depth=[2,3,3],min_stab=0.5,decorr=0.85;理由:当前stab已0.996,瓶颈在IC与去相关,应压深度、提去相关与引导权重。
> 
> 否决: 无

## 第 18 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | gate_min_calmar | gate_min_pool_calmar | fail_calmar | fail_calmar_neg | fail_pool_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 19 | 0.020 | 0.048 | 0.997 | 0.000 | 0.526 | 0.895 | 14 | 0.000 | 19 | 0 | 0.008 | 0.000 | 0.150 | 0.947 | 0.947 | 0.421 | 0.000 | 1.000 | 0.263 | 0.947 | 0.947 |

叶子使用: {'open': 10, 'barra_momentum': 9, 'close': 8, 'low': 5, 'fa_lev': 4, 'mf_m_buy': 3}

**B角建议(下一代策略)**:
- 【拦截】[r1_leaf_conc] LLM 已【永久】否决，后续各代一律不再施加 —— 叶子过度集中 -> 压低该叶子权重
- 【拦截】[r7_zero_pass] LLM 已【永久】否决，后续各代一律不再施加 —— 本代 0 通过 -> 深度放宽到 3~5
- —— 本代共拦截 2 条动作（饱和/LLM 否决），详见上面【拦截】行

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 4]  min_stab=0.3  decorr=0.75  fsa_th=0.15  bank_skel_max=1
leaf_w={'barra_residual_volatility': 0.25, 'barra_momentum': 0.25}
```

**规则动作留痕**:
- `r1_leaf_conc` 叶子过度集中 -> 压低该叶子权重 —— 施加于第 [12, 15, 16] 代（**已永久关闭**）
- `r5_calmar_cross` L2 多因 Calmar 不足 -> 交叉+15% / 深度加深 —— 施加于第 [12, 13, 15] 代（**已永久关闭**）
- `r7_zero_pass` 本代 0 通过 -> 深度放宽到 3~5 —— 施加于第 [12, 13] 代（**已永久关闭**）
- ⛔ **被 LLM 永久否决的动作**（用户要求「让它永久闭嘴」）：`r5_calmar_cross`, `r7_zero_pass`, `r1_leaf_conc`

**LLM 引导(A角 18代)**: 调用3次, 解析通过47条, 引导位使用47条
> 风格暴露的短长窗动量差(残波/动量/流动性/规模等 Barra 暴露在短窗相对长窗的抬升)刻画了拥挤度迁移与风格轮动，能预测未来5日截面收益，且与量价/资金流微观结构背离交互后信号更强。


**LLM 候选审查(B角 18代)**: 深判 5 个, KILL 4 个(剔除出 L2 费后回测)
- KILL `ts_slope5(ts_mean60(ts_mean200(sub(corr200(ts_sum20(mf_l_sqty), ts_mean200(fa_lev)), barra_momentum))))`
  > 理由: 多层同源时序嵌套+窗口参数海，经济含义拼凑难解释，过拟合嫌疑
- KILL `ts_mean5(ts_mean120(sub(corr200(ts_sum20(mf_l_sqty), ts_mean200(fa_lev)), barra_momentum)))`
  > 理由: 多层嵌套同源时序算子，窗口参数冗余，经济含义拼凑难解释，过拟合嫌疑高
- KILL `ts_mean20(corr200(corr100(ln_volume, barra_size), turn_ratio))`
  > 理由: 多层嵌套corr叠加同源量价字段，窗口100/200冗余，本质仍是量价换手老故事，难解释
- KILL `ts_slope5(ts_mean60(ts_mean200(barra_momentum)))`
  > 理由: 对动量做200/60/5多层同源平滑再取斜率，纯冗余嵌套，无增量经济含义


**AI 审查(DeepSeek deepseek-flash, 2s)**:

> (1) 病根:IC天花板仅0.048而neg_yr普遍5~7、calmar全负,说明因子方向/结构错配,不是深度或稳定性不足,放宽depth只会放大过拟合。
> 
> (2) r1_leaf_conc、r7_zero_pass已被永久否决,本轮建议里又出现这两条,属重复无效;且"深度放宽到3~5"与min_stab=0.3、decorr=0.75自相冲突——深度一放,稳定性与去相关必然被稀释,反而推高seg_kill。建议本身对症性弱。
> 
> (3) mix=[0.15,0.35,0.2,0.2,0.1],depth=[2,3,3],min_stab=0.6,decorr=0.6:先压深度保稳定、提引导比例换方向,而非放深度。
> 
> 否决: 无

## 第 19 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | gate_min_calmar | gate_min_pool_calmar | fail_calmar | fail_calmar_neg | fail_pool_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 21 | 0.019 | 0.048 | 0.997 | 0.000 | 0.476 | 0.952 | 10 | 0.000 | 21 | 0 | 0.009 | 0.000 | 0.150 | 0.857 | 0.857 | 0.286 | 0.000 | 1.000 | 0.333 | 0.905 | 0.857 |

叶子使用: {'low': 10, 'barra_momentum': 10, 'open': 8, 'close': 5, 'mf_l_buy': 4, 'mf_m_buy': 4}

**B角建议(下一代策略)**:
- 【拦截】[r1_leaf_conc] LLM 已【永久】否决，后续各代一律不再施加 —— 叶子过度集中 -> 压低该叶子权重
- 【拦截】[r7_zero_pass] LLM 已【永久】否决，后续各代一律不再施加 —— 本代 0 通过 -> 深度放宽到 3~5
- —— 本代共拦截 2 条动作（饱和/LLM 否决），详见上面【拦截】行

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 4]  min_stab=0.3  decorr=0.75  fsa_th=0.15  bank_skel_max=1
leaf_w={'barra_residual_volatility': 0.25, 'barra_momentum': 0.25}
```

**规则动作留痕**:
- `r1_leaf_conc` 叶子过度集中 -> 压低该叶子权重 —— 施加于第 [12, 15, 16] 代（**已永久关闭**）
- `r5_calmar_cross` L2 多因 Calmar 不足 -> 交叉+15% / 深度加深 —— 施加于第 [12, 13, 15] 代（**已永久关闭**）
- `r7_zero_pass` 本代 0 通过 -> 深度放宽到 3~5 —— 施加于第 [12, 13] 代（**已永久关闭**）
- ⛔ **被 LLM 永久否决的动作**（用户要求「让它永久闭嘴」）：`r5_calmar_cross`, `r7_zero_pass`, `r1_leaf_conc`

**LLM 引导(A角 19代)**: 调用3次, 解析通过39条, 引导位使用39条
> 在残余波动与动量风格暴露主导的截面里，短期超大单主动净买入占比相对中小单的抬升，叠加隔夜跳空与日内振幅的背离，能刻画知情资金的吸筹节奏，从而预测未来5日截面收益。


**LLM 候选审查(B角 19代)**: 深判 5 个, KILL 5 个(剔除出 L2 费后回测)
- KILL `ts_mean5(ts_mean120(sub(corr200(corr200(open, ts_min20(barra_momentum)), corr200(close, barra_momentum)), barra_momentum)))`
  > 理由: 多层同源corr嵌套与barra动量反复相减，无清晰量价机制，参数冗余似过拟合
- KILL `corr200(log(turn_ratio), corr200(mf_m_buy, open))`
  > 理由: 嵌套相关无清晰量价机制，且与换手率老故事同源，冗余难解释
- KILL `ts_mean5(ts_sum20(barra_momentum))`
  > 理由: 对动量因子做20日求和再5日均值，纯线性平滑无增量机制，冗余同源算子
- KILL `ts_mean5(ts_mean120(sub(corr200(corr200(open, ts_mean60(barra_residual_volatility)), corr200(close, barra_momentum)), barra_momentum)))`
  > 理由: 多层同源corr嵌套+窗口堆叠，经济含义拼凑难解释，过拟合冗余
- KILL `ts_mean200(corr100(overnight, corr20(ema12(fa_sell_exp), corr100(fa_lev, mf_l_bqty))))`
  > 理由: 多层嵌套corr无清晰量价机制，窗口堆叠似参数捞针，属数学拼凑


**AI 审查(DeepSeek deepseek-flash, 2s)**:

> (1)病根:IC天花板被barra_momentum单因子绑架,所有头部候选都是"某量价减barra_momentum",同质化到无增量信息,而L2回测calmar全负、neg_yr高达5~8,说明信号方向或持有期错配,不是深度不够。
> 
> (2)规则B角两条建议均已被永久否决,本轮实际未施加任何动作,故无对症可言;真正该做的是打破barra_momentum的减法垄断,而非放宽depth或压叶子权重——后者只会让同质候选更多。
> 
> (3)建议 mix=[0.15,0.3,0.2,0.25,0.1] depth=[2,3,4] min_stab=0.5 decorr=0.85:提高引导与扰动占比以强制引入非momentum骨架,收紧decorr压制同质,min_stab上调过滤伪稳定。
> 
> (4)本代无实际动作可停,但永久关闭项已生效,无需再动。
> 
> 否决: 无

## 第 20 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | gate_min_calmar | gate_min_pool_calmar | fail_calmar | fail_calmar_neg | fail_pool_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 24 | 0.019 | 0.048 | 0.997 | 0.000 | 0.667 | 0.958 | 15 | 0.042 | 24 | 0 | 0.046 | 0.000 | 0.150 | 0.917 | 0.917 | 0.333 | 0.000 | 1.000 | 0.250 | 0.958 | 0.875 |

叶子使用: {'open': 16, 'close': 10, 'barra_momentum': 10, 'low': 8, 'mf_l_bqty': 5, 'barra_leverage': 4}

**B角建议(下一代策略)**:
- 【拦截】[r1_leaf_conc] LLM 已【永久】否决，后续各代一律不再施加 —— 叶子过度集中 -> 压低该叶子权重
- 【拦截】[r7_zero_pass] LLM 已【永久】否决，后续各代一律不再施加 —— 本代 0 通过 -> 深度放宽到 3~5
- —— 本代共拦截 2 条动作（饱和/LLM 否决），详见上面【拦截】行

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 4]  min_stab=0.3  decorr=0.75  fsa_th=0.15  bank_skel_max=1
leaf_w={'barra_residual_volatility': 0.25, 'barra_momentum': 0.25}
```

**规则动作留痕**:
- `r1_leaf_conc` 叶子过度集中 -> 压低该叶子权重 —— 施加于第 [12, 15, 16] 代（**已永久关闭**）
- `r5_calmar_cross` L2 多因 Calmar 不足 -> 交叉+15% / 深度加深 —— 施加于第 [12, 13, 15] 代（**已永久关闭**）
- `r7_zero_pass` 本代 0 通过 -> 深度放宽到 3~5 —— 施加于第 [12, 13] 代（**已永久关闭**）
- ⛔ **被 LLM 永久否决的动作**（用户要求「让它永久闭嘴」）：`r5_calmar_cross`, `r7_zero_pass`, `r1_leaf_conc`

**LLM 引导(A角 20代)**: 调用3次, 解析通过43条, 引导位使用43条
> 在残差波动与动量风格暴露被市场过度定价后，资金流内部大单与中小单的方向背离会通过流动性补偿机制预测未来5日截面收益：当超大单主动净买入占比抬升而中小单同步净卖出（或量额不匹配）时，知情交易者吸收流动性，未来5日该股跑赢截面。


**LLM 候选审查(B角 20代)**: 深判 5 个, KILL 4 个(剔除出 L2 费后回测)
- KILL `cs_rank(ts_mean200(corr60(abs(corr200(ts_mean200(ts_min20(barra_momentum)), low)), barra_momentum)))`
  > 理由: 多层嵌套corr/ts_mean同源冗余，窗口200/60/20堆叠无经济机制，纯参数海捞针
- KILL `ts_mean120(corr200(close, corr200(close, corr200(high, open))))`
  > 理由: 三层同源corr嵌套无经济含义，纯数学巧合，参数冗余过拟合
- KILL `ema60(ts_std20(ts_mean150(ts_mean200(mf_x_buy))))`
  > 理由: 多层同源均值嵌套(150/200)冗余，无明确量价机制，疑参数海捞针
- KILL `ts_mean120(sub(corr200(barra_momentum, open), barra_momentum))`
  > 理由: barra动量与开盘价相关再减动量，量纲与含义拼凑，无清晰量价机制，属数学巧合


**AI 审查(DeepSeek deepseek-flash, 2s)**:

> (1)病根:IC天花板极低(med 0.019)且L2全军覆没,负年数5~7、calmar全负,说明因子方向性弱且被barra_momentum单一暴露绑架,不是深度不够。
> 
> (2)规则B角两条建议均已被永久否决,等于本轮无有效动作;r7_zero_pass若真放宽depth到3~5,只会加剧过拟合与负年,与min_stab=0.3的松绑叠加更危险;r1_leaf_conc压权重方向对但已被关,无法执行,故两条都属无效。
> 
> (3)建议mix=[0.15,0.35,0.15,0.2,0.15],depth=[3,4,4],min_stab=0.5,decorr=0.85:提高稳定门槛与去相关,逼引擎跳出momentum单一暴露,而非靠加深。
> 
> (4)本代未施加任何动作,无可停项。
> 
> 否决: 无

## 第 21 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | gate_min_calmar | gate_min_pool_calmar | fail_calmar | fail_calmar_neg | fail_pool_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 19 | 0.026 | 0.035 | 0.996 | 0.000 | 0.526 | 0.895 | 17 | 0.053 | 19 | 0 | 0.046 | 0.000 | 0.150 | 0.895 | 0.895 | 0.421 | 0.000 | 1.000 | 0.263 | 1.000 | 0.842 |

叶子使用: {'barra_momentum': 10, 'open': 9, 'close': 9, 'mf_l_bqty': 6, 'barra_leverage': 5, 'low': 3}

**B角建议(下一代策略)**:
- 【拦截】[r1_leaf_conc] LLM 已【永久】否决，后续各代一律不再施加 —— 叶子过度集中 -> 压低该叶子权重
- 【拦截】[r7_zero_pass] LLM 已【永久】否决，后续各代一律不再施加 —— 本代 0 通过 -> 深度放宽到 3~5
- —— 本代共拦截 2 条动作（饱和/LLM 否决），详见上面【拦截】行

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 4]  min_stab=0.3  decorr=0.75  fsa_th=0.15  bank_skel_max=1
leaf_w={'barra_residual_volatility': 0.25, 'barra_momentum': 0.25}
```

**规则动作留痕**:
- `r1_leaf_conc` 叶子过度集中 -> 压低该叶子权重 —— 施加于第 [12, 15, 16] 代（**已永久关闭**）
- `r5_calmar_cross` L2 多因 Calmar 不足 -> 交叉+15% / 深度加深 —— 施加于第 [12, 13, 15] 代（**已永久关闭**）
- `r7_zero_pass` 本代 0 通过 -> 深度放宽到 3~5 —— 施加于第 [12, 13] 代（**已永久关闭**）
- ⛔ **被 LLM 永久否决的动作**（用户要求「让它永久闭嘴」）：`r5_calmar_cross`, `r7_zero_pass`, `r1_leaf_conc`

**LLM 引导(A角 21代)**: 调用3次, 解析通过44条, 引导位使用44条
> 风格暴露的短期动量与长期均值之间的背离（尤其是残差波动率与动量的短长窗错位）能预测未来5日截面收益，因为风格轮动时短窗风格暴露的极端偏离往往在随后数日出现均值回复。


**LLM 候选审查(B角 21代)**: 深判 5 个, KILL 4 个(剔除出 L2 费后回测)
- KILL `ema60(corr200(abs(log(mf_l_bqty)), ts_delta5(corr200(mf_s_buy, low))))`
  > 理由: 多层嵌套corr/ema/ts_delta拼凑，无清晰量价机制，参数冗余似过拟合
- KILL `ts_mean20(ts_mean120(ts_mean200(corr60(abs(corr200(mf_l_bqty, close)), barra_momentum))))`
  > 理由: 三层同源ts_mean嵌套+双corr，窗口堆叠无经济机制，属参数冗余过拟合
- KILL `ema60(corr200(abs(log(mf_l_bqty)), ts_delta5(corr200(open, low))))`
  > 理由: 多层嵌套corr/ema/ts_delta拼凑，无清晰量价机制，参数冗余似过拟合
- KILL `ts_mean120(sub(corr200(cs_rank(ts_mean200(corr60(abs(corr200(ts_mean200(ts_min20(barra_momentum)), low)), barra_momentum))), corr200(open, ts_mean60(close))), barra_momentum))`
  > 理由: 18节点多层嵌套同源corr/ts_mean，窗口20-200堆砌，无清晰量价机制，属参数海捞针


**AI 审查(DeepSeek deepseek-flash, 2s)**:

> (1)病根:IC天花板0.035、negyear全灭、seg_kill 0.842,信号是"高稳低效"的伪因子,靠barra_momentum兜底刷稳定度,没有真实横截面预测力。
> 
> (2)两条建议全被永久否决,等于本轮无有效干预;r7_zero_pass放宽depth到3~5是错药——0通过不是深度不够,是信号本身无效,放宽只会加剧过拟合与negyear。r1_leaf_conc压权重也治标不治本,叶子集中是结果不是原因。
> 
> (3)建议mix=[0.15,0.3,0.2,0.2,0.15],depth=[3,4,4],min_stab=0.5,decorr=0.6。理由:提高引导与扰动占比逼出非barra结构,抬min_stab筛掉伪稳,降decorr强制去同质。
> 
> 否决: 无

## 第 22 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | gate_min_calmar | gate_min_pool_calmar | fail_calmar | fail_calmar_neg | fail_pool_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 15 | 0.028 | 0.034 | 0.996 | 0.000 | 0.667 | 1.000 | 11 | 0.133 | 15 | 0 | 0.044 | 0.000 | 0.150 | 0.933 | 0.933 | 0.400 | 0.000 | 1.000 | 0.267 | 1.000 | 0.933 |

叶子使用: {'open': 10, 'barra_momentum': 9, 'mf_l_bqty': 4, 'close': 4, 'vwap': 4, 'high': 3}

**B角建议(下一代策略)**:
- 【拦截】[r1_leaf_conc] LLM 已【永久】否决，后续各代一律不再施加 —— 叶子过度集中 -> 压低该叶子权重
- 【拦截】[r7_zero_pass] LLM 已【永久】否决，后续各代一律不再施加 —— 本代 0 通过 -> 深度放宽到 3~5
- —— 本代共拦截 2 条动作（饱和/LLM 否决），详见上面【拦截】行

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 4]  min_stab=0.3  decorr=0.75  fsa_th=0.15  bank_skel_max=1
leaf_w={'barra_residual_volatility': 0.25, 'barra_momentum': 0.25}
```

**规则动作留痕**:
- `r1_leaf_conc` 叶子过度集中 -> 压低该叶子权重 —— 施加于第 [12, 15, 16] 代（**已永久关闭**）
- `r5_calmar_cross` L2 多因 Calmar 不足 -> 交叉+15% / 深度加深 —— 施加于第 [12, 13, 15] 代（**已永久关闭**）
- `r7_zero_pass` 本代 0 通过 -> 深度放宽到 3~5 —— 施加于第 [12, 13] 代（**已永久关闭**）
- ⛔ **被 LLM 永久否决的动作**（用户要求「让它永久闭嘴」）：`r5_calmar_cross`, `r7_zero_pass`, `r1_leaf_conc`

**LLM 引导(A角 22代)**: 调用3次, 解析通过30条, 引导位使用30条
> 主动资金流内部结构失衡（超大单与中小单方向背离、净买入占比的稳定性）比资金流绝对水平更能预测未来5日截面收益，且该失衡在低残波/高动量风格股中更显著。


**LLM 候选审查(B角 22代)**: 深判 5 个, KILL 5 个(剔除出 L2 费后回测)
- KILL `ts_mean120(sub(corr200(barra_leverage, corr200(open, ts_mean120(ts_mean20(ts_mean150(barra_non_linear_size))))), barra_momentum))`
  > 理由: 多层同源嵌套窗口堆叠，经济含义拼凑难解释，属参数海捞针
- KILL `ts_mean20(corr200(close, corr200(close, corr200(high, corr100(mf_l_buy, vwap)))))`
  > 理由: 多层嵌套corr无经济含义，窗口200/100/20拼凑，属参数海捞针的数学巧合结构
- KILL `ts_mean200(ts_slope20(ts_mean20(ts_mean150(ts_sum20(barra_non_linear_size)))))`
  > 理由: 仅对市值类字段做多层同源平滑求斜率，无价量增量机制，属已知市值族冗余再表达
- KILL `ema60(corr200(abs(mf_x_buy), ts_delta5(corr200(open, mf_l_bqty))))`
  > 理由: 多层嵌套corr/ema/ts_delta，经济含义拼凑难解释，参数冗余似过拟合
- KILL `corr200(close, ts_mean20(corr200(high, low)))`
  > 理由: 嵌套相关无经济含义，纯数学拼凑，窗口冗余难解释


**AI 审查(DeepSeek deepseek-flash, 3s)**:

> (1)病根:因子全被barra_momentum主导、同质化严重,IC天花板0.034却negyear全灭,是"高稳低效"的死循环,不是深度不够。
> 
> (2)规则B角两条建议均已被永久否决,等于没建议。r1_leaf_conc方向对(open占10/15确实过集中)但被LLM封杀;r7_zero_pass放宽depth到3~5是错的——0通过不是深度问题而是信号无效,放宽只会放大过拟合,幸被否决。
> 
> (3)mix=[0.15,0.35,0.15,0.2,0.15] depth=[2,3,3] min_stab=0.5 decorr=0.85。理由:降depth防过拟合、提decorr强制去barra_momentum同质、提min_stab筛掉伪稳定。
> 
> (4)本代未施加任何动作,无可否决。
> 
> 否决: 无

## 第 23 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | gate_min_calmar | gate_min_pool_calmar | fail_calmar | fail_calmar_neg | fail_pool_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 12 | 0.023 | 0.036 | 0.995 | 0.000 | 0.750 | 0.833 | 16 | 0.083 | 12 | 0 | 0.055 | 0.000 | 0.150 | 0.833 | 0.833 | 0.333 | 0.000 | 1.000 | 0.250 | 1.000 | 0.833 |

叶子使用: {'open': 9, 'barra_momentum': 6, 'barra_non_linear_size': 4, 'close': 4, 'high': 3, 'barra_leverage': 2}

**B角建议(下一代策略)**:
- 【拦截】[r1_leaf_conc] LLM 已【永久】否决，后续各代一律不再施加 —— 叶子过度集中 -> 压低该叶子权重
- 【拦截】[r7_zero_pass] LLM 已【永久】否决，后续各代一律不再施加 —— 本代 0 通过 -> 深度放宽到 3~5
- —— 本代共拦截 2 条动作（饱和/LLM 否决），详见上面【拦截】行

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 4]  min_stab=0.3  decorr=0.75  fsa_th=0.15  bank_skel_max=1
leaf_w={'barra_residual_volatility': 0.25, 'barra_momentum': 0.25}
```

**规则动作留痕**:
- `r1_leaf_conc` 叶子过度集中 -> 压低该叶子权重 —— 施加于第 [12, 15, 16] 代（**已永久关闭**）
- `r5_calmar_cross` L2 多因 Calmar 不足 -> 交叉+15% / 深度加深 —— 施加于第 [12, 13, 15] 代（**已永久关闭**）
- `r7_zero_pass` 本代 0 通过 -> 深度放宽到 3~5 —— 施加于第 [12, 13] 代（**已永久关闭**）
- ⛔ **被 LLM 永久否决的动作**（用户要求「让它永久闭嘴」）：`r5_calmar_cross`, `r7_zero_pass`, `r1_leaf_conc`

**LLM 引导(A角 23代)**: 调用3次, 解析通过34条, 引导位使用34条
> 在波动率高企且风格动量拥挤的环境中，资金流失衡（大单主动净买入与中小单方向背离）与价格变化的背离，比单纯量价关系更能预测未来5日截面收益——即'聪明钱逆散户'的资金流结构在风险暴露高的股票中具有更强的截面区分度。


**LLM 候选审查(B角 23代)**: 深判 5 个, KILL 5 个(剔除出 L2 费后回测)
- KILL `ts_mean120(sub(corr200(cs_rank(ts_mean200(corr60(close, ln_mktcap))), corr200(open, ts_mean60(open))), barra_momentum))`
  > 理由: 多层嵌套同源corr与窗口堆叠，经济含义拼凑难解释，过拟合冗余
- KILL `ts_mean120(sub(corr200(barra_leverage, corr200(open, ts_mean200(fa_gm))), barra_momentum))`
  > 理由: 多层嵌套corr与barra因子相减，经济含义拼凑难解释，属参数海捞针冗余结构
- KILL `ts_mean120(sub(corr200(cs_rank(ts_mean200(corr60(close, ln_mktcap))), corr200(open, mf_x_sqty)), barra_momentum))`
  > 理由: 多层嵌套同源corr+窗口60/120/200冗余，经济含义拼凑难解释，过拟合嫌疑
- KILL `corr200(vwap, corr200(vwap, open))`
  > 理由: 嵌套自相关无经济含义，纯数学巧合，窗口单一但结构冗余难解释
- KILL `add(ts_mean120(sub(corr200(barra_leverage, corr200(open, ts_mean120(fa_gm))), barra_momentum)), barra_non_linear_size)`
  > 理由: 多因子嵌套相关再相减，无清晰量价机制，属参数拼凑冗余结构


**AI 审查(DeepSeek deepseek-flash, 2s)**:

> (1) 病根:IC 天花板仅 0.036、fail_ic=1.0 且 neg_yr 普遍 3~7,说明信号方向本身无预测力,而非稳定性或深度不足。
> 
> (2) 两条建议均不对症:r1_leaf_conc 与 r7_zero_pass 已被永久否决,再提无效;且“0通过就放宽 depth”是错的——depth 放宽只会放大无 alpha 的噪声,与 min_stab 收紧方向冲突。真正该动的是因子族与目标(IC/negyear),不是深度。
> 
> (3) mix=[0.15,0.25,0.2,0.25,0.15] depth=[2,3,3] min_stab=0.5 decorr=0.6:降深度防过拟合、提引导与扰动换血、降 decorr 逼出正交新族。
> 
> 否决: 无

## 第 24 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | gate_min_calmar | gate_min_pool_calmar | fail_calmar | fail_calmar_neg | fail_pool_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 15 | 0.021 | 0.031 | 0.996 | 0.000 | 0.800 | 1.000 | 22 | 0.000 | 15 | 0 | -0.001 | 0.000 | 0.150 | 1.000 | 1.000 | 0.133 | 0.000 | 1.000 | 0.133 | 1.000 | 1.000 |

叶子使用: {'open': 12, 'barra_momentum': 11, 'mf_m_buy': 5, 'barra_leverage': 4, 'high': 4, 'low': 4}

**B角建议(下一代策略)**:
- 【拦截】[r1_leaf_conc] LLM 已【永久】否决，后续各代一律不再施加 —— 叶子过度集中 -> 压低该叶子权重
- 【拦截】[r7_zero_pass] LLM 已【永久】否决，后续各代一律不再施加 —— 本代 0 通过 -> 深度放宽到 3~5
- —— 本代共拦截 2 条动作（饱和/LLM 否决），详见上面【拦截】行

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 4]  min_stab=0.3  decorr=0.75  fsa_th=0.15  bank_skel_max=1
leaf_w={'barra_residual_volatility': 0.25, 'barra_momentum': 0.25}
```

**规则动作留痕**:
- `r1_leaf_conc` 叶子过度集中 -> 压低该叶子权重 —— 施加于第 [12, 15, 16] 代（**已永久关闭**）
- `r5_calmar_cross` L2 多因 Calmar 不足 -> 交叉+15% / 深度加深 —— 施加于第 [12, 13, 15] 代（**已永久关闭**）
- `r7_zero_pass` 本代 0 通过 -> 深度放宽到 3~5 —— 施加于第 [12, 13] 代（**已永久关闭**）
- ⛔ **被 LLM 永久否决的动作**（用户要求「让它永久闭嘴」）：`r5_calmar_cross`, `r7_zero_pass`, `r1_leaf_conc`

**LLM 引导(A角 24代)**: 调用3次, 解析通过47条, 引导位使用47条
> 在残余波动率高、动量风格主导的截面里，短期隔夜跳空相对长期跳空基准的偏离（跳空溢价衰减）以及大单主动净买入相对中小单的方向背离，能预测未来5日截面收益：跳空溢价被消化、且大单与散户资金流反向的股票，后续收益更高。


**LLM 候选审查(B角 24代)**: 深判 5 个, KILL 5 个(剔除出 L2 费后回测)
- KILL `corr200(vwap, corr200(cs_scale(corr200(close, open)), add(close, open)))`
  > 理由: 多层嵌套corr与cs_scale拼凑，无清晰量价机制，属数学巧合冗余结构
- KILL `ts_mean200(ts_slope20(ts_mean60(barra_non_linear_size)))`
  > 理由: 仅对市值类字段做多层平滑与斜率，无价量增量机制，属已知市值因子再表达
- KILL `ts_mean120(sub(corr200(cs_rank(ts_mean200(corr60(ts_rank200(corr200(mf_l_bqty, open)), barra_non_linear_size))), add(close, open)), barra_momentum))`
  > 理由: 多层嵌套相关+排序+窗口堆叠，无清晰量价机制，属参数海捞针高冗余
- KILL `corr200(add(close, open), ts_mean20(corr200(high, low)))`
  > 理由: close+open与high-low相关性嵌套，无明确量价经济含义，属数学拼凑
- KILL `ts_mean120(sub(corr60(barra_leverage, corr200(open, ts_mean120(mf_s_buy))), barra_momentum))`
  > 理由: 多层嵌套corr与异源字段相减，经济含义拼凑难解释，窗口冗余疑过拟合


**AI 审查(DeepSeek deepseek-flash, 2s)**:

> (1)病根:IC天花板0.031且L2全负calmar,说明因子只挖到"barra_momentum+open"这一条拥挤共线结构,增量信息为零。
> 
> (2)规则B角两条建议均已被永久否决,等于本轮无有效动作;真正该做的是打断叶子共线(open/barra_momentum占23/30),而非放宽depth——放宽只会加深过拟合,与decorr目标冲突。
> 
> (3)我建议:mix=[0.15,0.25,0.2,0.25,0.15] depth=[2,3,3] min_stab=0.5 decorr=0.9。理由:提高扰动与引导、压低交叉,强制去共线并收紧稳定性门槛。
> 
> (4)本代未施加任何规则动作,无可停项。
> 
> 否决: 无

## 第 25 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | gate_min_calmar | gate_min_pool_calmar | fail_calmar | fail_calmar_neg | fail_pool_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 15 | 0.018 | 0.031 | 0.995 | 0.000 | 0.667 | 0.800 | 22 | 0.000 | 15 | 0 | 0.009 | 0.000 | 0.150 | 0.867 | 0.867 | 0.333 | 0.000 | 1.000 | 0.133 | 0.933 | 0.933 |

叶子使用: {'open': 10, 'barra_momentum': 7, 'barra_leverage': 5, 'vwap': 5, 'close': 3, 'barra_liquidity': 2}

**B角建议(下一代策略)**:
- 【拦截】[r1_leaf_conc] LLM 已【永久】否决，后续各代一律不再施加 —— 叶子过度集中 -> 压低该叶子权重
- 【拦截】[r7_zero_pass] LLM 已【永久】否决，后续各代一律不再施加 —— 本代 0 通过 -> 深度放宽到 3~5
- —— 本代共拦截 2 条动作（饱和/LLM 否决），详见上面【拦截】行

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 4]  min_stab=0.3  decorr=0.75  fsa_th=0.15  bank_skel_max=1
leaf_w={'barra_residual_volatility': 0.25, 'barra_momentum': 0.25}
```

**规则动作留痕**:
- `r1_leaf_conc` 叶子过度集中 -> 压低该叶子权重 —— 施加于第 [12, 15, 16] 代（**已永久关闭**）
- `r5_calmar_cross` L2 多因 Calmar 不足 -> 交叉+15% / 深度加深 —— 施加于第 [12, 13, 15] 代（**已永久关闭**）
- `r7_zero_pass` 本代 0 通过 -> 深度放宽到 3~5 —— 施加于第 [12, 13] 代（**已永久关闭**）
- ⛔ **被 LLM 永久否决的动作**（用户要求「让它永久闭嘴」）：`r5_calmar_cross`, `r7_zero_pass`, `r1_leaf_conc`

**LLM 引导(A角 25代)**: 调用3次, 解析通过47条, 引导位使用47条
> 在残差波动率高企且风格动量拥挤的股票池中，日内主动大单资金净流入相对价格涨幅的背离（大单吸筹但价格滞涨）预示未来5日截面超额收益，因为机构在低波动被忽视的标的中分批建仓而尚未推升价格。


**LLM 候选审查(B角 25代)**: 深判 5 个, KILL 5 个(剔除出 L2 费后回测)
- KILL `ts_mean120(sub(corr200(cs_rank(ts_mean200(ts_slope20(ts_mean60(sub(corr200(barra_leverage, corr200(open, ts_mean120(mf_s_buy))), barra_momentum))))), ts_delay1(barra_leverage)), barra_momentum))`
  > 理由: 多层嵌套corr/ts_mean/slope堆叠，窗口密集，经济含义不可解释，属参数海捞针
- KILL `corr200(add(corr200(ts_std60(mf_m_buy), open), barra_momentum), ts_mean20(corr200(high, open)))`
  > 理由: 多层嵌套corr叠加同源算子，经济含义拼凑难解释，参数冗余似过拟合
- KILL `ts_mean120(sub(corr200(cs_rank(ts_mean200(corr60(ts_rank200(corr200(mf_l_bqty, ts_slope20(ts_mean60(ts_sum20(barra_non_linear_size))))), ts_mean60(ts_sum20(barra_non_linear_size))))), open), barra_momentum))`
  > 理由: 多层嵌套同源corr/ts_mean冗余，含size与open尺度相减，经济含义拼凑难解释
- KILL `ts_mean200(ts_slope20(ts_mean60(sub(corr200(barra_leverage, corr200(open, ts_mean120(mf_s_buy))), barra_momentum))))`
  > 理由: 多层嵌套同源corr/ts_mean，窗口20-200堆叠，经济含义拼凑难解释，过拟合嫌疑
- KILL `ts_mean120(sub(corr200(cs_rank(ts_mean200(corr60(ts_rank200(corr200(mf_l_bqty, ts_slope20(ts_mean60(ts_sum20(barra_non_linear_size))))), barra_non_linear_size))), open), barra_momentum))`
  > 理由: 多层嵌套同源corr/ts_rank冗余，含size/momentum老因子，经济含义拼凑难解释


**AI 审查(DeepSeek deepseek-flash, 2s)**:

> (1)病根:IC天花板极低(0.031)且L2全灭,失败集中在negyear/ic/seg_kill,说明信号是barra_momentum主导的伪相关,换手低但无跨年稳健性。
> 
> (2)两条建议均被永久否决,等于本轮无有效规则介入;r7_zero_pass放宽depth到3~5方向对但已被关,无法执行;r1_leaf_conc关掉后叶子仍集中(open+barra_momentum占17/32),集中病未治。无冲突,但整体空转。
> 
> (3)mix=[0.15,0.35,0.15,0.2,0.15],depth=[3,4,5],min_stab=0.5,decorr=0.8;理由:提高交叉与深度探索、抬min_stab压伪相关、加decorr拆barra_momentum簇。
> 
> 否决: 无

## 第 26 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | gate_min_calmar | gate_min_pool_calmar | fail_calmar | fail_calmar_neg | fail_pool_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 19 | 0.018 | 0.035 | 0.997 | 0.000 | 0.789 | 0.895 | 21 | 0.000 | 19 | 0 | 0.004 | 0.000 | 0.150 | 0.947 | 0.947 | 0.316 | 0.000 | 1.000 | 0.053 | 1.000 | 0.895 |

叶子使用: {'open': 15, 'barra_momentum': 14, 'vwap': 8, 'barra_liquidity': 6, 'barra_leverage': 5, 'mf_m_buy': 4}

**B角建议(下一代策略)**:
- 【拦截】[r1_leaf_conc] LLM 已【永久】否决，后续各代一律不再施加 —— 叶子过度集中 -> 压低该叶子权重
- 【拦截】[r7_zero_pass] LLM 已【永久】否决，后续各代一律不再施加 —— 本代 0 通过 -> 深度放宽到 3~5
- —— 本代共拦截 2 条动作（饱和/LLM 否决），详见上面【拦截】行

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 4]  min_stab=0.3  decorr=0.75  fsa_th=0.15  bank_skel_max=1
leaf_w={'barra_residual_volatility': 0.25, 'barra_momentum': 0.25}
```

**规则动作留痕**:
- `r1_leaf_conc` 叶子过度集中 -> 压低该叶子权重 —— 施加于第 [12, 15, 16] 代（**已永久关闭**）
- `r5_calmar_cross` L2 多因 Calmar 不足 -> 交叉+15% / 深度加深 —— 施加于第 [12, 13, 15] 代（**已永久关闭**）
- `r7_zero_pass` 本代 0 通过 -> 深度放宽到 3~5 —— 施加于第 [12, 13] 代（**已永久关闭**）
- ⛔ **被 LLM 永久否决的动作**（用户要求「让它永久闭嘴」）：`r5_calmar_cross`, `r7_zero_pass`, `r1_leaf_conc`

**LLM 引导(A角 26代)**: 调用3次, 解析通过48条, 引导位使用48条
> 在风格暴露层面，特质波动率与动量的截面交互：高特质波动率且近期动量弱的股票未来5日继续跑输（低波+强动量组合占优），因为投资者对高特质风险股票的过度关注与动量崩塌形成负向共振。


**LLM 候选审查(B角 26代)**: 深判 5 个, KILL 3 个(剔除出 L2 费后回测)
- KILL `ts_mean120(sub(corr200(barra_leverage, corr200(vwap, ts_mean120(barra_liquidity))), barra_momentum))`
  > 理由: 多层嵌套corr与均值叠加，经济含义拼凑难解释，属参数海捞针冗余结构
- KILL `corr200(add(corr200(ts_std60(barra_momentum), open), barra_momentum), ts_mean20(corr200(high, barra_momentum)))`
  > 理由: 多层同源corr嵌套、窗口200/60/20拼凑，无清晰量价机制，属参数海捞针
- KILL `ts_mean200(ts_slope20(ts_mean60(sub(barra_liquidity, barra_momentum))))`
  > 理由: 两Barra因子相减再套三层时序算子，经济含义拼凑且窗口冗余，难解释


**AI 审查(DeepSeek deepseek-flash, 2s)**:

> (1) 病根:IC 高但全是 barra_momentum 的单调变形,neg_yr 普遍5~6、calmar 全负,因子无独立 alpha,只换壳不换芯。
> (2) 两条建议均已被永久否决,本轮无实际动作可评;真正该做的是打断 momentum 依赖,而非放宽 depth。mix 里交叉0.4偏高会继续放大同族重组,与 decorr=0.75 自相矛盾。
> (3) mix=[0.15,0.2,0.2,0.3,0.15] depth=[2,3,4] min_stab=0.5 decorr=0.85;理由:提高扰动与引导、降交叉,强制引入非 momentum 叶子并去同族冗余。
> 否决: 无

## 第 27 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | gate_min_calmar | gate_min_pool_calmar | fail_calmar | fail_calmar_neg | fail_pool_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 21 | 0.019 | 0.035 | 0.998 | 0.000 | 0.857 | 0.905 | 7 | 0.048 | 21 | 0 | 0.016 | 0.000 | 0.150 | 0.857 | 0.857 | 0.333 | 0.000 | 1.000 | 0.095 | 1.000 | 0.762 |

叶子使用: {'open': 18, 'barra_momentum': 17, 'mf_m_buy': 9, 'vwap': 8, 'barra_leverage': 5, 'barra_non_linear_size': 4}

**B角建议(下一代策略)**:
- 【拦截】[r1_leaf_conc] LLM 已【永久】否决，后续各代一律不再施加 —— 叶子过度集中 -> 压低该叶子权重
- 【拦截】[r7_zero_pass] LLM 已【永久】否决，后续各代一律不再施加 —— 本代 0 通过 -> 深度放宽到 3~5
- —— 本代共拦截 2 条动作（饱和/LLM 否决），详见上面【拦截】行

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 4]  min_stab=0.3  decorr=0.75  fsa_th=0.15  bank_skel_max=1
leaf_w={'barra_residual_volatility': 0.25, 'barra_momentum': 0.25}
```

**规则动作留痕**:
- `r1_leaf_conc` 叶子过度集中 -> 压低该叶子权重 —— 施加于第 [12, 15, 16] 代（**已永久关闭**）
- `r5_calmar_cross` L2 多因 Calmar 不足 -> 交叉+15% / 深度加深 —— 施加于第 [12, 13, 15] 代（**已永久关闭**）
- `r7_zero_pass` 本代 0 通过 -> 深度放宽到 3~5 —— 施加于第 [12, 13] 代（**已永久关闭**）
- ⛔ **被 LLM 永久否决的动作**（用户要求「让它永久闭嘴」）：`r5_calmar_cross`, `r7_zero_pass`, `r1_leaf_conc`

**LLM 引导(A角 27代)**: 调用3次, 解析通过33条, 引导位使用33条
> 在残差波动率高且动量风格占优的截面环境下，隔夜跳空溢价与日内主动资金流强度之间存在时变背离：当隔夜跳空相对日内真实波动的短期均值显著高于长期均值、同时大单主动净买入占比确认时，未来5日截面收益更强，即'跳空溢价×资金流确认'的机制在被风格暴露放大后仍能预测收益。


**LLM 候选审查(B角 27代)**: 深判 5 个, KILL 5 个(剔除出 L2 费后回测)
- KILL `ts_mean120(add(corr200(barra_leverage, corr200(barra_leverage, ts_mean120(corr200(mf_m_buy, open)))), barra_momentum))`
  > 理由: 多层同源corr/ts_mean嵌套冗余，经济含义拼凑难解释，过拟合嫌疑
- KILL `ts_mean200(ts_slope20(ts_mean60(sub(corr200(barra_leverage, corr200(barra_leverage, ts_mean120(corr200(mf_m_buy, open)))), barra_momentum))))`
  > 理由: 多层同源corr嵌套+窗口堆叠，经济含义拼凑难解释，过拟合冗余
- KILL `ts_mean120(add(corr200(barra_non_linear_size, low), ts_mean60(sub(corr200(barra_leverage, corr200(barra_leverage, ts_mean120(corr200(mf_m_buy, open)))), barra_momentum))))`
  > 理由: 多层嵌套同源corr/ts_mean冗余，含barra风格与量价拼凑，经济含义不清，疑过拟合
- KILL `ts_mean120(corr200(vwap, corr200(ts_sum20(corr200(close, high)), open)))`
  > 理由: 多层嵌套corr与ts_sum拼凑，无清晰量价机制，窗口200/120/20冗余，疑参数海捞
- KILL `ts_mean20(sub(corr200(corr200(vwap, corr200(low, open)), barra_momentum), barra_momentum))`
  > 理由: 三层corr嵌套无经济含义，窗口200/20拼凑，属数学巧合与冗余结构


**AI 审查(DeepSeek deepseek-flash, 2s)**:

> (1)病根:IC天花板仅0.035且L2全灭,因子被barra_momentum单一腿绑架,负年数普遍6年,是信号而非结构问题。
> 
> (2)两条建议均无效:r1_leaf_conc、r7_zero_pass已被永久否决,再提只是复述;且"深度放宽到3~5"与表格depth=[3,4,4]自相矛盾,放宽深度只会加剧过拟合,不解决neg_yr=6。
> 
> (3)我建议mix=[0.15,0.3,0.2,0.2,0.15],提高扰动与引导以打破momentum依赖;depth=[2,3,3]压低复杂度;min_stab=0.5过滤伪稳定;decorr=0.85强制去momentum相关。
> 
> (4)本代未施加任何规则动作,无可停项。
> 
> 否决: 无
