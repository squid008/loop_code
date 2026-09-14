
## 第 1 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 24 | 0.030 | 0.056 | 0.963 | 0.000 | 0.208 | 1.000 | 11 | 0.042 | 24 | 1 | 0.077 | 1.000 | 0.130 | 0.957 | 0.609 | 0.043 | 0.625 |

叶子使用: {'barra_residual_volatility': 5, 'overnight': 4, 'amplitude': 3, 'close': 3, 'ret': 3, 'volume': 3}

**B角建议(下一代策略)**:
- L2中100%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 配比护栏: 变异/交叉各≥10%且合计50%重归一化, 扰动/引导/随机固定15/20/15(中金规格) -> mix=[0.173, 0.327, 0.15, 0.2, 0.15]

```
mix=[0.173, 0.327, 0.15, 0.2, 0.15]  depth=[3, 4, 4]  min_stab=0.3  decorr=0.75  fsa_th=0.15  bank_skel_max=1
leaf_w={}
```

**LLM 引导(A角 1代)**: 调用3次, 解析通过29条, 引导位使用29条
> 资金流的结构性失衡（大单/超大单主动净买入占比抬升，同时中小单主动净卖出）反映知情资金吸筹，能正向预测未来5日截面收益；当该失衡与价格变化背离（价跌而大单净买占比升）时，反转预测更强。


**LLM 候选审查(B角 1代)**: 深判 5 个, KILL 2 个(剔除出 L2 费后回测)
- KILL `max(log(barra_beta), mul(barra_residual_volatility, mf_l_sqty))`
  > 理由: beta与残差波动率乘平方成交量，量纲与含义拼凑，无清晰量价机制
- KILL `sub(cs_demean(ts_std20(down_shadow)), abs(corr100(mf_l_bqty, amplitude)))`
  > 理由: 两异源量纲项相减无经济含义，窗口20/100拼凑，属数学巧合


**AI 审查(DeepSeek deepseek-flash, 2s)**:

> (1) 病根:信号全是低波动/振幅类同质因子,IC虚高但无收益弹性,Calmar与负年数双杀,不是搜索不足而是方向单一。
> 
> (2) 交叉+15%对症但不够,同质叶子交叉仍产同质;深度加深到4易过拟合、与min_stab=0.3冲突;扰动/引导/随机固定值合理;decorr=0.75偏高会误杀同族有效变体;fsa_th=0.15与bank_skel_max=1偏保守。
> 
> (3) mix=[0.20,0.25,0.15,0.25,0.15],depth=[2,3,3],min_stab=0.5,decorr=0.6。理由:提引导权重换方向、降深度防过拟合、松decorr保同族多样性。

## 第 2 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 25 | 0.034 | 0.056 | 0.960 | 0.000 | 0.520 | 1.000 | 3 | 0.080 | 25 | 0 | 0.048 | 1.000 | 0.280 | 1.000 | 0.480 | 0.080 | 0.360 |

叶子使用: {'barra_residual_volatility': 13, 'amplitude': 5, 'intraday': 3, 'fa_np_margin': 3, 'mf_x_sell': 2, 'barra_beta': 1}

**B角建议(下一代策略)**:
- 叶子[barra_residual_volatility]占比52%过高 -> 权重压到0.25, 逼引擎换字段
- L2中100%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 本代0通过 -> 深度放宽到3~5, 探索更复杂结构
- 配比护栏: 变异/交叉各≥10%且合计50%重归一化, 扰动/引导/随机固定15/20/15(中金规格) -> mix=[0.1, 0.4, 0.15, 0.2, 0.15]

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 5]  min_stab=0.3  decorr=0.75  fsa_th=0.15  bank_skel_max=1
leaf_w={'barra_residual_volatility': 0.25}
```

**LLM 引导(A角 2代)**: 调用3次, 解析通过16条, 引导位使用16条
> 资金流内部结构失衡（超大单主动净买入占比抬升、且中小单与超大单方向背离）预示未来5日截面收益，其信息在价格/换手之外独立存在。


**LLM 候选审查(B角 2代)**: 深判 5 个, KILL 0 个(剔除出 L2 费后回测)
> (全部 PASS)


**AI 审查(DeepSeek deepseek-flash, 2s)**:

> (1)病根:信号本身太弱且同源——叶子52%挤在barra_residual_volatility,L2全因Calmar/负年不足被毙,不是结构不够复杂,是没找到新alpha源。
> 
> (2)压权重到0.25对症;但"交叉+15%且深度加深到3~5"是错药:同源字段交叉只会放大共线性,加深深度在弱信号下更易过拟合,与min_stab=0.3自相矛盾(降稳定门槛又加复杂度)。扰动/引导/随机固定值属无效护栏,不解决字段同质。decorr=0.75偏松,压不住52%集中。
> 
> (3)我建议mix=[0.25,0.15,0.15,0.25,0.20],depth=[2,3],min_stab=0.6,decorr=0.85。理由:提变异与引导去换字段源,降交叉防同源,收紧稳定与去相关逼出真正独立的新信号。

## 第 3 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 47 | 0.020 | 0.041 | 0.974 | 0.000 | 0.234 | 0.979 | 0 | 0.191 | 30 | 1 | 0.055 | 0.966 | 0.138 | 0.897 | 0.207 | 0.241 | 0.433 |

叶子使用: {'barra_residual_volatility': 11, 'amplitude': 11, 'fa_np_margin': 9, 'ln_volume': 6, 'intraday': 5, 'mf_l_sell': 5}

**B角建议(下一代策略)**:
- L2中97%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 配比护栏: 变异/交叉各≥10%且合计50%重归一化, 扰动/引导/随机固定15/20/15(中金规格) -> mix=[0.1, 0.4, 0.15, 0.2, 0.15]

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 4]  min_stab=0.3  decorr=0.75  fsa_th=0.15  bank_skel_max=1
leaf_w={'barra_residual_volatility': 0.25}
```

**LLM 引导(A角 3代)**: 调用3次, 解析通过28条, 引导位使用28条
> 超大单主动净买入占比相对中小单净买入的持续背离（大单吸筹、小单抛压），叠加日内价格位置偏低（close 相对 true_range 的弱势），预示未来5日截面收益反转向上。


**LLM 候选审查(B角 3代)**: 深判 5 个, KILL 1 个(剔除出 L2 费后回测)
- KILL `ts_std60(log(mul(barra_residual_volatility, corr200(ret, amplitude))))`
  > 理由: 残差波动率与振幅相关性相乘再取波动，多层同源冗余，经济含义拼凑难解释


**AI 审查(DeepSeek deepseek-flash, 2s)**:

> (1)病根:叶子高度同质(barra_residual_volatility+amplitude占近半),L2信号被单一因子族锁死,Calmar弱是表象,多样性枯竭才是根。
> 
> (2)交叉+15%对症但不够:同质叶子交叉只产近亲,无效。深度加深到4会加剧过拟合与turn,与fail_turn=0.138冲突。min_stab=0.3相对当前stab_med=0.974是断崖式放松,会放大量不稳个体,与"稳"目标相悖。decorr=0.75偏保守,难破族内冗余。护栏固定扰动/引导/随机比例,压制了探索弹性。
> 
> (3)建议:mix=[0.15,0.25,0.15,0.25,0.20],depth=[2,3,3],min_stab=0.6,decorr=0.85。理由:提高变异与引导以注入新因子族,降深度防过拟合,抬min_stab守稳定性,加严decorr强制跨族。

## 第 4 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 27 | 0.006 | 0.055 | 0.982 | 0.000 | 0.185 | 0.963 | 15 | 0.111 | 27 | 0 | 0.045 | 1.000 | 0.037 | 0.963 | 0.444 | 0.741 | 0.852 |

叶子使用: {'barra_growth': 5, 'overnight': 4, 'true_range': 3, 'fa_np_margin': 3, 'fa_np_yoy': 3, 'amplitude': 3}

**B角建议(下一代策略)**:
- L2中100%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 本代0通过 -> 深度放宽到3~5, 探索更复杂结构
- 配比护栏: 变异/交叉各≥10%且合计50%重归一化, 扰动/引导/随机固定15/20/15(中金规格) -> mix=[0.173, 0.327, 0.15, 0.2, 0.15]

```
mix=[0.173, 0.327, 0.15, 0.2, 0.15]  depth=[3, 4, 5]  min_stab=0.3  decorr=0.75  fsa_th=0.15  bank_skel_max=1
leaf_w={}
```

**LLM 引导(A角 4代)**: 调用3次, 解析通过38条, 引导位使用38条
> 大单主动资金的方向与价格/成交结构出现背离时，未来5日截面收益更可能向资金流真实方向修正，即‘量价背离+资金流失衡’是独立于旧量价故事的预测源。


**LLM 候选审查(B角 4代)**: 深判 5 个, KILL 3 个(剔除出 L2 费后回测)
- KILL `ts_mean100(corr60(cs_demean(ts_std20(hl_ratio)), add(intraday, abs(up_shadow))))`
  > 理由: 多层同源嵌套冗余，经济含义拼凑难解释，疑参数海捞
- KILL `sub(ts_min100(add(corr100(barra_residual_volatility, barra_growth), sub(barra_growth, barra_size))), div(max(neg(fa_rev_yoy), ts_delta5(barra_momentum)), max(ts_mean200(mf_m_bqty), div(close, ln_mktcap))))`
  > 理由: 多字段多算子拼凑，无清晰量价机制，嵌套冗余疑过拟合
- KILL `add(mul(barra_momentum, barra_liquidity), neg(barra_residual_volatility))`
  > 理由: 三个Barra风格因子相乘相加，无明确量价机制，属数学拼凑，难解释


**AI 审查(DeepSeek deepseek-flash, 2s)**:

> (1)病根:信号IC中位仅0.006、L2全灭于Calmar,本质是因子预测力太弱,而非结构不够复杂。
> 
> (2)交叉+15%与深度放宽到3~5不对症:弱信号下加深只会放大噪声与过拟合,且与min_stab=0.3自相矛盾(稳度门槛骤降会放进大量伪因子)。扰动/引导/随机固定15/20/15占比过高,稀释有效变异。decorr=0.75偏松,难解fam_blocked=15的拥挤。
> 
> (3)建议mix=[0.30,0.15,0.15,0.25,0.15],depth=[2,3],min_stab=0.6,decorr=0.85。理由:先提纯信号质量、控复杂度与相关性,再谈探索。

## 第 5 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 29 | 0.010 | 0.030 | 0.984 | 0.000 | 0.276 | 0.966 | 1 | 0.138 | 29 | 0 | 0.054 | 1.000 | 0.000 | 0.931 | 0.207 | 0.655 | 0.552 |

叶子使用: {'barra_growth': 8, 'overnight': 5, 'true_range': 4, 'fa_np_margin': 4, 'amplitude': 4, 'ln_mktcap': 2}

**B角建议(下一代策略)**:
- L2中100%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 本代0通过 -> 深度放宽到3~5, 探索更复杂结构
- 配比护栏: 变异/交叉各≥10%且合计50%重归一化, 扰动/引导/随机固定15/20/15(中金规格) -> mix=[0.1, 0.4, 0.15, 0.2, 0.15]

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 5]  min_stab=0.3  decorr=0.75  fsa_th=0.15  bank_skel_max=1
leaf_w={}
```

**LLM 引导(A角 5代)**: 调用3次, 解析通过39条, 引导位使用39条
> 主动资金流内部结构失衡（超大单与中小单方向背离、净买入强度与价格变化脱钩）刻画了知情交易者与散户的分歧，这种分歧在5日内向价格收敛，可预测截面收益。


**LLM 候选审查(B角 5代)**: 深判 5 个, KILL 4 个(剔除出 L2 费后回测)
- KILL `neg(log(ts_delay1(barra_growth)))`
  > 理由: 仅对barra_growth取对数并延迟1期取负，无价量行为机制，属已知风格因子再表达
- KILL `corr100(ts_std20(ts_sum20(amplitude)), ts_mean20(barra_liquidity))`
  > 理由: 振幅求和后再取波动，与流动性均值做相关，多层同源冗余，经济含义拼凑难解释
- KILL `corr200(sub(corr200(mf_s_bqty, mf_m_buy), ts_std100(amplitude)), fa_np_yoy)`
  > 理由: 多层嵌套corr/sub/ts_std拼凑，含财务字段fa_np_yoy，经济含义不可解释，属参数海捞针
- KILL `ts_sum100(corr100(log(ts_sum20(amplitude)), corr200(min(fa_np_margin, fa_rev_yoy), mf_x_sell)))`
  > 理由: 多层嵌套corr叠加基本面与量价字段，无清晰量价机制，参数冗余似过拟合


**AI 审查(DeepSeek deepseek-flash, 2s)**:

> (1)病根:IC天花板仅0.03、neg_yr高达0.93,是信号本身太弱且时序不稳,不是结构不够复杂。
> 
> (2)交叉+15%与深度3~5对症存疑:弱信号下加深只增过拟合,calmar不会因复杂度改善;min_stab=0.3与stab_med=0.984严重脱节,等于放弃稳定性护栏,与decorr=0.75自相矛盾——既要去相关又要低稳,样本更碎。引导20%在known_ratio仅0.138时近乎空转。
> 
> (3)建议mix=[0.25,0.15,0.2,0.2,0.2],depth=[2,3],min_stab=0.7,decorr=0.6:弱信号期应压深度、保稳定、提变异多样性,而非堆复杂度。

## 第 6 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 26 | 0.028 | 0.056 | 0.941 | 0.000 | 0.231 | 0.923 | 7 | 0.038 | 26 | 0 | 0.043 | 1.000 | 0.115 | 1.000 | 0.577 | 0.077 | 0.654 |

叶子使用: {'barra_residual_volatility': 6, 'amplitude': 6, 'turn_ratio': 5, 'volume': 4, 'ret': 3, 'fa_np_margin': 2}

**B角建议(下一代策略)**:
- L2中100%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 本代0通过 -> 深度放宽到3~5, 探索更复杂结构
- 配比护栏: 变异/交叉各≥10%且合计50%重归一化, 扰动/引导/随机固定15/20/15(中金规格) -> mix=[0.1, 0.4, 0.15, 0.2, 0.15]

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 5]  min_stab=0.3  decorr=0.75  fsa_th=0.15  bank_skel_max=1
leaf_w={}
```

**LLM 引导(A角 6代)**: 调用3次, 解析通过26条, 引导位使用26条
> 大单与超大单主动资金的方向背离、以及资金流强度相对价格变化的错配，隐含知情交易者的吸筹/派发尚未被价格充分反映，可在未来5日截面收益上产生可预测的横截面差异。


**LLM 候选审查(B角 6代)**: 深判 5 个, KILL 2 个(剔除出 L2 费后回测)
- KILL `mul(cs_demean(corr100(mf_m_sqty, mf_l_bqty)), max(ts_std150(up_shadow), barra_momentum))`
  > 理由: 买卖量相关与上影波动、动量相乘，含义拼凑，无清晰量价机制
- KILL `mul(cs_demean(corr100(mf_s_bqty, mf_l_bqty)), max(ts_std150(up_shadow), fa_rev_yoy))`
  > 理由: 大单小单相关性与上影波动、营收增速拼凑相乘，无清晰量价机制，属参数拼凑


**AI 审查(DeepSeek deepseek-flash, 2s)**:

> (1)病根:叶子扎堆amplitude/volatility类同质信号,IC虚高但换手与负年失控,Calmar全灭,是多样性枯竭而非深度不足。
> 
> (2)交叉+15%对症但加深depth到5会放大过拟合,与min_stab=0.3自相矛盾(低稳+深树=噪声);扰动/引导/随机固定值合理;decorr=0.75偏松,难拆amplitude簇;fsa_th=0.15过严会误杀弱信号。
> 
> (3)建议mix=[0.25,0.25,0.15,0.2,0.15],depth=[2,3,4],min_stab=0.6,decorr=0.85。理由:先提变异与去相关破同质,再控深度防过拟合。

## 第 7 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 30 | 0.030 | 0.056 | 0.941 | 0.000 | 0.367 | 0.933 | 3 | 0.033 | 30 | 0 | 0.038 | 1.000 | 0.133 | 1.000 | 0.467 | 0.033 | 0.467 |

叶子使用: {'barra_residual_volatility': 11, 'turn_ratio': 8, 'amplitude': 6, 'barra_growth': 3, 'fa_np_margin': 2, 'intraday': 2}

**B角建议(下一代策略)**:
- L2中100%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 本代0通过 -> 深度放宽到3~5, 探索更复杂结构
- 配比护栏: 变异/交叉各≥10%且合计50%重归一化, 扰动/引导/随机固定15/20/15(中金规格) -> mix=[0.1, 0.4, 0.15, 0.2, 0.15]

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 5]  min_stab=0.3  decorr=0.75  fsa_th=0.15  bank_skel_max=1
leaf_w={}
```

**LLM 引导(A角 7代)**: 调用3次, 解析通过34条, 引导位使用34条
> 主动资金流的方向性失衡(尤其中小单与超大单的背离、以及资金净额与价格变化的错配)在截面内具有短期定价修正效应,能预测未来5日收益。


**LLM 候选审查(B角 7代)**: 深判 5 个, KILL 2 个(剔除出 L2 费后回测)
- KILL `log(ts_mean5(ts_std150(max(fa_np_margin, fa_np_margin))))`
  > 理由: max自比较冗余，log(波动率)无明确量价含义，属数学拼凑
- KILL `ts_max20(ts_max20(amplitude))`
  > 理由: 嵌套同源ts_max冗余，等价单层20日振幅极值，无增量机制，属参数堆砌


**AI 审查(DeepSeek deepseek-flash, 2s)**:

> (1)病根:叶子被amplitude/barra_residual_volatility垄断(占比超六成),信号同源导致L2全灭,是多样性枯竭而非深度不足。
> 
> (2)交叉+15%对症但深度放宽到3~5是误判:0通过源于因子同质,加深只会放大过拟合与turn;min_stab=0.3与L1高stab(0.94)矛盾,等于放弃稳定性筛选;decorr=0.75偏松,难破同源;扰动/引导/随机固定值合理。
> 
> (3)建议mix=[0.2,0.25,0.15,0.2,0.2],depth=[2,3],min_stab=0.7,decorr=0.9。理由:提变异与随机以打散amplitude家族,收紧stab与decorr逼出正交新叶。

## 第 8 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 19 | 0.035 | 0.042 | 0.975 | 0.000 | 0.684 | 1.000 | 0 | 0.053 | 19 | 0 | 0.063 | 1.000 | 0.105 | 1.000 | 0.474 | 0.105 | 0.474 |

叶子使用: {'barra_residual_volatility': 13, 'turn_ratio': 4, 'fa_np_margin': 3, 'barra_growth': 3, 'barra_liquidity': 2, 'amplitude': 1}

**B角建议(下一代策略)**:
- 叶子[barra_residual_volatility]占比68%过高 -> 权重压到0.25, 逼引擎换字段
- L2中100%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 本代0通过 -> 深度放宽到3~5, 探索更复杂结构
- 配比护栏: 变异/交叉各≥10%且合计50%重归一化, 扰动/引导/随机固定15/20/15(中金规格) -> mix=[0.1, 0.4, 0.15, 0.2, 0.15]

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 5]  min_stab=0.3  decorr=0.75  fsa_th=0.15  bank_skel_max=1
leaf_w={'barra_residual_volatility': 0.25}
```

**LLM 引导(A角 8代)**: 调用3次, 解析通过33条, 引导位使用33条
> 资金流强度与价格变化方向发生背离时（主动大单净买入占比高但价格未同步上涨、或中小单与超大单方向相反），未来5日截面收益更高，反映知情资金吸筹与散户抛压的错位。


**LLM 候选审查(B角 8代)**: 深判 5 个, KILL 5 个(剔除出 L2 费后回测)
- KILL `ts_std150(max(barra_growth, barra_residual_volatility))`
  > 理由: 对两个Barra风格暴露取max再滚动标准差，无明确量价行为含义，属数学拼凑
- KILL `sub(neg(turn_ratio), ts_max100(ts_std20(barra_liquidity)))`
  > 理由: 换手率与流动性同源冗余，负号加双层窗口属参数拼凑，无增量机制
- KILL `cs_scale(sub(barra_residual_volatility, barra_growth))`
  > 理由: 两Barra风格因子原始尺度相减，无经济机制，纯数学拼凑
- KILL `ts_max20(ts_std20(ts_std150(max(fa_np_margin, intraday))))`
  > 理由: max拼凑两异源字段无经济含义，嵌套同源ts_std冗余，窗口20/150似参数捞针
- KILL `sub(barra_residual_volatility, ts_std150(turn_ratio))`
  > 理由: 残差波动率减换手率波动，量纲与含义拼凑，无明确量价机制，属数学巧合


**AI 审查(DeepSeek deepseek-flash, 2s)**:

> (1)病根:叶子被barra_residual_volatility单一字段垄断(68%),同源信号堆叠导致L2全线Calmar不足、负年频发,不是深度不够。
> 
> (2)压权重到0.25对症;但"交叉+15%且深度加深到3~5"与"信号弱"矛盾——弱信号加复杂度只会放大过拟合,无效。min_stab=0.3过低,与stab_med=0.975的稳定优势自毁,冲突。decorr=0.75合理。
> 
> (3)建议mix=[0.15,0.25,0.15,0.25,0.20],depth=[2,3],min_stab=0.6,decorr=0.8。理由:先解字段垄断与过拟合,再谈结构深度,引导权重上调逼换字段。

## 第 9 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 31 | 0.029 | 0.042 | 0.982 | 0.000 | 0.677 | 1.000 | 4 | 0.129 | 30 | 1 | 0.060 | 0.966 | 0.069 | 0.966 | 0.241 | 0.172 | 0.267 |

叶子使用: {'barra_residual_volatility': 21, 'fa_np_margin': 12, 'turn_ratio': 6, 'barra_growth': 4, 'ln_volume': 4, 'barra_book_to_price': 3}

**B角建议(下一代策略)**:
- 叶子[barra_residual_volatility]占比68%过高 -> 权重压到0.25, 逼引擎换字段
- L2中97%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 配比护栏: 变异/交叉各≥10%且合计50%重归一化, 扰动/引导/随机固定15/20/15(中金规格) -> mix=[0.1, 0.4, 0.15, 0.2, 0.15]

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 4]  min_stab=0.3  decorr=0.75  fsa_th=0.15  bank_skel_max=1
leaf_w={'barra_residual_volatility': 0.25}
```

**LLM 引导(A角 9代)**: 调用3次, 解析通过41条, 引导位使用41条
> 在残余波动率主导的风格环境下，个股日内跳空与主动资金流失衡的短长窗背离能预测未来5日截面收益：即隔夜跳空溢价衰减叠加超大单净买入强度与价格变化的背离，反映知情资金吸筹而价格尚未反应。


**LLM 候选审查(B角 9代)**: 深判 5 个, KILL 4 个(剔除出 L2 费后回测)
- KILL `ts_mean120(ts_std20(ts_delta120(ts_std20(ts_delta120(fa_np_margin)))))`
  > 理由: 多层同源ts_delta/ts_std嵌套冗余，无清晰量价经济含义，属参数海捞针
- KILL `ts_max20(log(ts_std60(sub(barra_residual_volatility, barra_growth))))`
  > 理由: 两Barra风格因子相减无经济含义，嵌套ts_std/ts_max属参数拼凑，纯数学巧合
- KILL `ts_mean150(ts_std20(ln_volume))`
  > 理由: 仅对成交量取对数后做波动率再平滑，属换手/成交额老故事，无增量机制
- KILL `log(ts_std60(ts_std150(max(amplitude, barra_residual_volatility))))`
  > 理由: 嵌套同源波动率算子冗余，窗口60/150无机制，属参数海捞针


**AI 审查(DeepSeek deepseek-flash, 2s)**:

> (1)病根:叶子被barra_residual_volatility单一字段垄断(68%),L1全是它的ts_std嵌套自相关变体,同质化导致IC天花板锁死在0.04、L2信号弱Calmar崩。
> 
> (2)压权重到0.25对症,但仅压权重不改ts_std算子族无效,引擎会换字段仍套同一模板。交叉+15%与深度加深方向对,但L1已高度同质,交叉近亲繁殖只会加剧;真正缺的是字段多样性而非组合复杂度。扰动/引导/随机固定值属拍脑袋,与"逼换字段"目标冲突,引导20%若仍指向vol族则白给。护栏重归一化逻辑自洽,无冲突。
> 
> (3)建议mix=[0.15,0.25,0.15,0.25,0.20],depth=[2,3,4],min_stab=0.5,decorr=0.85。理由:提高引导与随机占比强制注入新字段,降交叉避免同质,decorr拉高去相关,min_stab回升保质量。

## 第 10 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 31 | 0.021 | 0.040 | 0.993 | 0.000 | 0.613 | 0.968 | 3 | 0.000 | 30 | 2 | 0.047 | 1.000 | 0.000 | 1.000 | 0.143 | 0.429 | 0.500 |

叶子使用: {'barra_residual_volatility': 19, 'barra_growth': 15, 'turn_ratio': 12, 'fa_np_margin': 9, 'barra_book_to_price': 7, 'volume': 3}

**B角建议(下一代策略)**:
- 叶子[barra_residual_volatility]占比61%过高 -> 权重压到0.25, 逼引擎换字段
- L2中100%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 配比护栏: 变异/交叉各≥10%且合计50%重归一化, 扰动/引导/随机固定15/20/15(中金规格) -> mix=[0.1, 0.4, 0.15, 0.2, 0.15]

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 4]  min_stab=0.3  decorr=0.75  fsa_th=0.15  bank_skel_max=1
leaf_w={'barra_residual_volatility': 0.25}
```

**LLM 引导(A角 10代)**: 调用3次, 解析通过28条, 引导位使用28条
> 在残余波动率风格暴露高的股票中，大单主动买入净额相对中小单净额的失衡（聪明钱与散户资金方向背离）会通过资金流惯性在截面延续，从而预测未来5日收益。


**LLM 候选审查(B角 10代)**: 深判 5 个, KILL 4 个(剔除出 L2 费后回测)
- KILL `ts_mean150(mul(ts_max20(barra_residual_volatility), corr20(volume, barra_book_to_price)))`
  > 理由: 残差波动率与量价相关性相乘再长均，经济含义拼凑，属参数海捞针冗余结构
- KILL `ts_std20(ts_std150(max(mul(ts_max20(sub(barra_residual_volatility, barra_growth)), volume), barra_residual_volatility)))`
  > 理由: barra残差波动率与成长因子相减再乘量、多层嵌套，无清晰量价含义，属参数拼凑
- KILL `max(fa_np_margin, ts_std60(ts_std150(max(fa_np_margin, sub(barra_residual_volatility, barra_growth)))))`
  > 理由: 净利润率与波动率/成长残差混拼，嵌套双层同源std，经济含义不清，疑参数捞针
- KILL `sub(neg(sub(barra_residual_volatility, barra_growth)), ts_max20(sub(ts_sum20(amplitude), barra_growth)))`
  > 理由: barra风格因子与振幅混算，量纲含义拼凑，无清晰量价机制，疑似参数巧合


**AI 审查(DeepSeek deepseek-flash, 2s)**:

> (1) 病根:叶子被barra_residual_volatility垄断(61%),L1高IC全靠单字段时序变形,信号同质、L2无真实alpha,Calmar全灭。
> 
> (2) 建议点评:压权重到0.25对症,但"交叉+15%+加深深度"方向错——同质叶子交叉只会放大barra残差波动族,不解决字段单一;且深度加深会加剧过拟合,与min_stab=0.3放松稳定性自相矛盾(放松稳定性+加深=更易过拟合)。mix把交叉提到0.4而变异仅0.1,探索多样性反而下降,与"逼换字段"目标冲突。decorr=0.75偏低,挡不住同族。
> 
> (3) 我的取值:mix=[0.25,0.25,0.15,0.2,0.15],depth=[2,3,3],min_stab=0.5,decorr=0.85。理由:提高变异与去相关、压低深度,才能真正逼出非barra残差族的新字段。

## 第 11 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 30 | 0.014 | 0.038 | 0.994 | 0.000 | 0.467 | 1.000 | 5 | 0.067 | 30 | 0 | 0.032 | 1.000 | 0.000 | 1.000 | 0.233 | 0.733 | 0.633 |

叶子使用: {'turn_ratio': 14, 'barra_growth': 13, 'fa_np_margin': 10, 'barra_book_to_price': 6, 'intraday': 6, 'barra_residual_volatility': 6}

**B角建议(下一代策略)**:
- 叶子[turn_ratio]占比47%过高 -> 权重压到0.25, 逼引擎换字段
- L2中100%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 本代0通过 -> 深度放宽到3~5, 探索更复杂结构
- 配比护栏: 变异/交叉各≥10%且合计50%重归一化, 扰动/引导/随机固定15/20/15(中金规格) -> mix=[0.1, 0.4, 0.15, 0.2, 0.15]

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 5]  min_stab=0.3  decorr=0.75  fsa_th=0.15  bank_skel_max=1
leaf_w={'barra_residual_volatility': 0.25, 'turn_ratio': 0.25}
```

**LLM 引导(A角 11代)**: 调用3次, 解析通过39条, 引导位使用39条
> 在残差波动率主导的风格暴露下，真实波动结构相对日间振幅的短期扩张与隔夜跳空溢价的背离，能捕捉到波动率错误定价和资金流方向不一致的截面收益机会。


**LLM 候选审查(B角 11代)**: 深判 5 个, KILL 4 个(剔除出 L2 费后回测)
- KILL `ts_mean200(max(fa_np_margin, ts_max100(turn_ratio)))`
  > 理由: fa_np_margin与turn_ratio量纲不同取max无经济含义，纯数学拼凑，且嵌套同源算子冗余
- KILL `ts_std100(max(fa_np_margin, mul(ts_max20(sub(fa_np_margin, barra_growth)), volume)))`
  > 理由: 净利润率与成交量原始尺度相乘、再套多层极值标准差，无清晰量价机制，属参数拼凑
- KILL `ts_mean200(mul(sub(barra_residual_volatility, barra_liquidity), corr20(barra_earnings_yield, barra_book_to_price)))`
  > 理由: Barra风格因子相减相乘拼凑，无清晰量价行为，属数学巧合
- KILL `ts_std100(max(fa_np_margin, mul(ts_max20(sub(corr100(mf_s_buy, cs_rank(ts_delay1(corr200(open, intraday)))), barra_growth)), volume)))`
  > 理由: 多层嵌套同源算子拼凑，无清晰量价机制，参数海捞，疑似过拟合


**AI 审查(DeepSeek deepseek-flash, 2s)**:

> (1)病根:IC天花板仅0.038且L2全灭,信号本身太弱,不是结构不够复杂,是因子缺经济含义、纯噪声堆叠。
> 
> (2)建议点评:压turn_ratio权重对症,但叶子集中是果不是因;交叉+15%与深度放宽到5互相冲突,弱信号下加深只会放大过拟合;min_stab从0.994骤降到0.3自毁护栏,等于放噪声进来;decorr=0.75偏松,与"换字段"目标矛盾;扰动/引导/随机固定中金规格合理,保留。
> 
> (3)我的取值:mix=[0.15,0.25,0.15,0.25,0.20],depth=[2,3],min_stab=0.85,decorr=0.85。理由:弱信号期应缩深度、提稳定门槛、加引导权重去挖经济逻辑,而非靠复杂度和松约束硬凑通过率。
