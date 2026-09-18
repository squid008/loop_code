
## 第 1 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | gate_min_calmar | gate_min_pool_calmar | fail_calmar | fail_calmar_neg | fail_pool_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 28 | 0.025 | 0.085 | 0.934 | 0.036 | 0.214 | 0.929 | 9 | 0.107 | 10 | 0 | 0.009 | 0.000 | 0.150 | 0.900 | 0.900 | 1.000 | 0.000 | 1.000 | 0.900 | 0.500 | 0.800 |

叶子使用: {'close': 6, 'mf_x_buy': 5, 'mf_x_sell': 5, 'overnight': 4, 'ret': 4, 'mf_l_sell': 4}

**B角建议(下一代策略)**:
- 【r5_calmar_cross】L2中100%因Calmar不足[池口径: 任一池 Calmar > 0.15] -> 交叉+15%, 深度加深
- 【r7_zero_pass】本代0通过 -> 深度放宽到3~5, 探索更复杂结构
- 配比护栏: 变异/交叉各≥10%且合计50%重归一化, 扰动/引导/随机固定15/20/15(中金规格) -> mix=[0.173, 0.327, 0.15, 0.2, 0.15]

```
mix=[0.173, 0.327, 0.15, 0.2, 0.15]  depth=[3, 4, 5]  min_stab=0.3  decorr=0.75  fsa_th=0.15  bank_skel_max=1
leaf_w={}
```

**规则动作留痕**:
- `r5_calmar_cross` L2 多因 Calmar 不足 -> 交叉+15% / 深度加深 —— 施加于第 [2] 代
- `r7_zero_pass` 本代 0 通过 -> 深度放宽到 3~5 —— 施加于第 [2] 代

**LLM 引导(A角 1代)**: 调用3次, 解析通过33条, 引导位使用33条
> 主动资金流的方向与强度在截面上的相对失衡（大单/超大单净买入占比、大小单方向背离、以及资金流强度与价格变化的背离）能预测未来5日截面收益，且该信息在量价与风格暴露之外独立。


**LLM 候选审查(B角 1代)**: 深判 5 个, KILL 1 个(剔除出 L2 费后回测)
- KILL `neg(log(ts_mean100(open)))`
  > 理由: 仅对开盘价取长均值对数再取负，无成交量或价差机制，属价格水平老故事，无增量含义


**AI 审查(DeepSeek deepseek-flash, 2s)**:

> (1) 病根: L1的IC/稳定性已够, 但因子全是低换手慢变量, L2卡在Calmar与负年数, 属"信号有效但收益路径差", 不是深度不够。
> 
> (2) r5_calmar_cross对症但方向错: Calmar差是收益路径/回撤问题, 加深交叉只会更过拟合、更慢, 无效。r7_zero_pass把depth放宽到3~5, 与r5叠加会同时放大复杂度与噪声, 二者互相冲突且都治标不治本。真正该做的是降换手约束、加路径平滑/风控引导, 而非加深度。
> 
> (3) mix=[0.25,0.15,0.15,0.30,0.15] depth=[2,3] min_stab=0.5 decorr=0.6: 减交叉加引导, 控复杂度, 提稳定性门槛。
> 
> 否决: r5_calmar_cross, r7_zero_pass

**⚖️ 规则动作否决（机器读取）**: `r5_calmar_cross`（L2 多因 Calmar 不足 -> 交叉+15% / 深度加深）, `r7_zero_pass`（本代 0 通过 -> 深度放宽到 3~5）

## 第 2 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | gate_min_calmar | gate_min_pool_calmar | fail_calmar | fail_calmar_neg | fail_pool_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 33 | 0.024 | 0.083 | 0.890 | 0.000 | 0.182 | 0.939 | 3 | 0.091 | 10 | 0 | 0.046 | 0.000 | 0.150 | 0.700 | 0.700 | 0.900 | 0.000 | 0.900 | 0.800 | 0.800 | 0.800 |

叶子使用: {'overnight': 6, 'amplitude': 5, 'mf_s_buy': 5, 'mf_l_buy': 4, 'mf_x_sell': 4, 'fa_rev_yoy': 4}

**B角建议(下一代策略)**:
- 【r5_calmar_cross】L2中90%因Calmar不足[池口径: 任一池 Calmar > 0.15] -> 交叉+15%, 深度加深
- 【r7_zero_pass】本代0通过 -> 深度放宽到3~5, 探索更复杂结构
- 配比护栏: 变异/交叉各≥10%且合计50%重归一化, 扰动/引导/随机固定15/20/15(中金规格) -> mix=[0.123, 0.377, 0.15, 0.2, 0.15]

```
mix=[0.123, 0.377, 0.15, 0.2, 0.15]  depth=[3, 4, 5]  min_stab=0.3  decorr=0.75  fsa_th=0.15  bank_skel_max=1
leaf_w={}
```

**规则动作留痕**:
- `r5_calmar_cross` L2 多因 Calmar 不足 -> 交叉+15% / 深度加深 —— 施加于第 [2, 3] 代
- `r7_zero_pass` 本代 0 通过 -> 深度放宽到 3~5 —— 施加于第 [2, 3] 代

**LLM 引导(A角 2代)**: 调用3次, 解析通过45条, 引导位使用35条
> 资金流内部结构失衡（大单/超大单主动净买强度与中小单方向背离、量额错配）在截面层面对未来5日收益有正向预测，且该预测在低流动性/低波动股票中更强。


**LLM 候选审查(B角 2代)**: 深判 5 个, KILL 4 个(剔除出 L2 费后回测)
- KILL `div(sub(mf_x_bqty, volume), corr100(mf_m_sell, open))`
  > 理由: 买卖量差与成交量原始尺度相减，再除以价格相关性，量纲混乱、经济含义拼凑，属数学巧合
- KILL `ts_mean20(min(mul(ts_max20(turnover), div(high, fa_lev)), barra_leverage))`
  > 理由: turnover与杠杆/价格尺度混乘取min，无清晰量价机制，属字段拼凑
- KILL `cs_scale(max(fa_roe, add(barra_beta, fa_rev_yoy)))`
  > 理由: 基本面字段与beta取max再横截面标准化，无明确量价机制，属含义拼凑
- KILL `sub(ts_mean200(overnight), ts_mean200(fa_op_yoy))`
  > 理由: 隔夜跳空与营业利润同比增速相减，量价与基本面尺度拼凑，无经济含义


**AI 审查(DeepSeek deepseek-flash, 2s)**:

> (1)病根不在深度或Calmar阈值,而在L1头部全是"均值/低波"类结构,预测方向与收益端脱节,0通过是信号问题不是复杂度问题。
> 
> (2)r5_calmar_cross:误诊。fail_negyear=0.9、fail_lastyr=0.8、fail_ic=0.8,Calmar只是末端症状,加交叉+加深只会放大同质低波族,无效。r7_zero_pass:深度放宽到3~5与min_stab=0.3同时执行自相冲突——深结构本就不稳,再降稳定门槛,只会灌入噪声叶子,且与decorr=0.75的分散目标打架。两者叠加=同族繁殖。
> 
> (3)mix=[0.30,0.15,0.15,0.25,0.15],depth=[2,3],min_stab=0.6,decorr=0.85。理由:先提变异与引导、压交叉,把搜索从低波均值族拉向收益/资金流方向,并抬稳定门槛过滤深噪声。
> 
> 否决: r5_calmar_cross, r7_zero_pass

**⚖️ 规则动作否决（机器读取）**: `r5_calmar_cross`（L2 多因 Calmar 不足 -> 交叉+15% / 深度加深）, `r7_zero_pass`（本代 0 通过 -> 深度放宽到 3~5）

## 第 3 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | gate_min_calmar | gate_min_pool_calmar | fail_calmar | fail_calmar_neg | fail_pool_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 47 | 0.025 | 0.086 | 0.952 | 0.000 | 0.191 | 0.936 | 6 | 0.149 | 10 | 0 | 0.036 | 0.000 | 0.150 | 0.700 | 0.700 | 0.900 | 0.000 | 1.000 | 0.700 | 0.700 | 0.800 |

叶子使用: {'overnight': 9, 'amplitude': 9, 'fa_rev_yoy': 7, 'mf_m_sqty': 6, 'mf_l_buy': 6, 'turnover': 6}

**B角建议(下一代策略)**:
- 【拦截】[r5_calmar_cross] LLM 已【永久】否决，后续各代一律不再施加 —— L2 多因 Calmar 不足 -> 交叉+15% / 深度加深
- 【拦截】[r7_zero_pass] LLM 已【永久】否决，后续各代一律不再施加 —— 本代 0 通过 -> 深度放宽到 3~5
- —— 本代共拦截 2 条动作（饱和/LLM 否决），详见上面【拦截】行

```
mix=[0.123, 0.377, 0.15, 0.2, 0.15]  depth=[3, 4, 5]  min_stab=0.3  decorr=0.75  fsa_th=0.15  bank_skel_max=1
leaf_w={}
```

**规则动作留痕**:
- `r5_calmar_cross` L2 多因 Calmar 不足 -> 交叉+15% / 深度加深 —— 施加于第 [2, 3] 代（**已永久关闭**）
- `r7_zero_pass` 本代 0 通过 -> 深度放宽到 3~5 —— 施加于第 [2, 3] 代（**已永久关闭**）
- ⛔ **被 LLM 永久否决的动作**（用户要求「让它永久闭嘴」）：`r5_calmar_cross`, `r7_zero_pass`

**LLM 引导(A角 3代)**: 调用2次, 解析通过24条, 引导位使用20条
> 主动资金流失衡（大单/超大单净买入强度）与价格短期变化发生背离时，未来5日截面收益更高，即资金流强度未被价格充分反映的个股存在补涨。


**LLM 候选审查(B角 3代)**: 深判 5 个, KILL 4 个(剔除出 L2 费后回测)
- KILL `div(turnover, barra_leverage)`
  > 理由: 换手率除以杠杆，量纲与含义拼凑，无明确量价机制，属数学巧合
- KILL `sub(ts_mean150(overnight), fa_np_margin)`
  > 理由: 净利润率与隔夜跳空均值相减，量纲与含义拼凑，无对应量价行为
- KILL `corr60(corr100(ts_mean10(mf_l_sqty), amplitude), corr200(ts_mean120(mf_l_buy), corr200(mf_x_sell, mf_l_bqty)))`
  > 理由: 多层嵌套corr拼凑，窗口密集无经济机制，疑似参数海捞针
- KILL `mul(abs(fa_np_margin), add(barra_beta, barra_size))`
  > 理由: 净利润率绝对值乘beta与size，量纲拼凑无明确量价机制，属数学巧合


**AI 审查(DeepSeek deepseek-flash, 2s)**:

> (1)病根:IC尚可但L2全军覆没,neg_yr与lastyr双杀,说明因子是"高稳定低收益"的横截面噪声,而非可交易信号。
> 
> (2)两条建议均属"拦截"而非"新增",不冲突;但r5/r7已永久关闭,再提无意义。真正该做的是放宽depth与降min_stab,而非继续加约束。当前建议未触及neg_yr病根,基本无效。
> 
> (3)mix=[0.15,0.30,0.15,0.25,0.15],depth=[2,3,4],min_stab=0.2,decorr=0.6。理由:提高引导与扰动权重、降深度与稳定门槛,逼出短周期收益型因子,缓解neg_yr。
> 
> 否决: 无

## 第 4 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | gate_min_calmar | gate_min_pool_calmar | fail_calmar | fail_calmar_neg | fail_pool_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill | st_l2_lncap | st_l2_lnamt | st_l2_lntr | st_l2_lnpx | st_l1_lncap | st_l1_lnamt | st_l1_lntr | st_l1_lnpx |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 16 | 0.031 | 0.085 | 0.999 | 0.000 | 0.438 | 1.000 | 0 | 0.125 | 16 | 0 | 0.033 | 0.000 | 0.150 | 0.875 | 0.875 | 0.938 | 0.000 | 1.000 | 0.688 | 0.688 | 0.812 | 0.196 | 0.232 | 0.168 | 0.288 | 0.196 | 0.232 | 0.168 | 0.288 |

叶子使用: {'overnight': 7, 'turnover': 2, 'barra_leverage': 1, 'fa_lev': 1, 'open': 1, 'fa_pb': 1}

**B角建议(下一代策略)**:
- 【r1_leaf_conc】叶子[overnight]占比44%过高 -> 权重压到0.25, 逼引擎换字段
- 【拦截】[r5_calmar_cross] LLM 已【永久】否决，后续各代一律不再施加 —— L2 多因 Calmar 不足 -> 交叉+15% / 深度加深
- 【拦截】[r7_zero_pass] LLM 已【永久】否决，后续各代一律不再施加 —— 本代 0 通过 -> 深度放宽到 3~5
- —— 本代共拦截 2 条动作（饱和/LLM 否决），详见上面【拦截】行

```
mix=[0.123, 0.377, 0.15, 0.2, 0.15]  depth=[3, 4, 5]  min_stab=0.3  decorr=0.75  fsa_th=0.15  bank_skel_max=1
leaf_w={'overnight': 0.25}
```

**规则动作留痕**:
- `r1_leaf_conc` 叶子过度集中 -> 压低该叶子权重 —— 施加于第 [5] 代
- `r5_calmar_cross` L2 多因 Calmar 不足 -> 交叉+15% / 深度加深 —— 施加于第 [2, 3] 代（**已永久关闭**）
- `r7_zero_pass` 本代 0 通过 -> 深度放宽到 3~5 —— 施加于第 [2, 3] 代（**已永久关闭**）
- ⛔ **被 LLM 永久否决的动作**（用户要求「让它永久闭嘴」）：`r5_calmar_cross`, `r7_zero_pass`

**LLM 引导(A角 4代)**: 调用3次, 解析通过39条, 引导位使用39条
> 在资金流与量价的高频错配中，超大单主动净买入占比的短期加速若未被价格同步反映，则未来5日截面收益向上；相反中小单推动而超大单缺席的上涨属于脆弱流动性溢价，未来收益向下。


**LLM 候选审查(B角 4代)**: 深判 5 个, KILL 4 个(剔除出 L2 费后回测)
- KILL `sub(ts_std200(sub(down_shadow, fa_np_margin)), ts_mean120(fa_np_margin))`
  > 理由: 下影线与净利润率原始尺度相减无经济含义，属字段拼凑，数学巧合
- KILL `ts_mean150(ts_min20(ts_sum20(corr200(mf_m_bqty, mf_s_sell))))`
  > 理由: 多层同源窗口嵌套冗余，经济含义不清，疑似参数海捞针
- KILL `sub(ts_mean150(barra_beta), ts_mean150(ts_delta120(corr200(mf_m_bqty, mf_s_sell))))`
  > 理由: 多层嵌套窗口120/150/200无经济含义，买卖量相关与beta相减属拼凑，过拟合嫌疑
- KILL `ts_mean60(ts_mean20(ts_mean200(corr200(mf_l_buy, mf_x_sell))))`
  > 理由: 多层同源均值嵌套冗余，corr买卖单含义不明，参数海捞针，难解释


**AI 审查(DeepSeek deepseek-flash, 2s)**:

> (1) 病根:叶子被overnight类字段垄断(占比44%),L1的IC全是同一风险源的自相关,导致L2全线负Calmar、neg_yr普遍5~7。
> 
> (2) r1_leaf_conc对症但力度不够,压权重到0.25仍留7个overnight叶子,应直接禁用或限1个;r5_calmar_cross、r7_zero_pass已被永久否决,此处只是复述拦截,无新动作,不冲突。真正缺的是"换字段"而非"加深/交叉"——depth放宽到3~5只会让同源信号更过拟合。
> 
> (3) mix=[0.15,0.30,0.20,0.20,0.15],depth=[2,3],min_stab=0.5,decorr=0.85。理由:降深度、提去相关与稳定性门槛,优先切断overnight同源,而非靠变异量堆数量。
> 
> 否决: r1_leaf_conc

**⚖️ 规则动作否决（机器读取）**: `r1_leaf_conc`（叶子过度集中 -> 压低该叶子权重）

## 第 5 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | gate_min_calmar | gate_min_pool_calmar | fail_calmar | fail_calmar_neg | fail_pool_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill | st_l2_lncap | st_l2_lnamt | st_l2_lntr | st_l2_lnpx | st_l1_lncap | st_l1_lnamt | st_l1_lntr | st_l1_lnpx |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2 | 0.019 | 0.021 | 1.000 | 0.000 | 0.500 | 1.000 | 3 | 0.000 | 2 | 0 | -0.060 | 0.000 | 0.150 | 1.000 | 1.000 | 1.000 | 0.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0.152 | 0.028 | 0.257 | 0.223 | 0.152 | 0.028 | 0.257 | 0.223 |

叶子使用: {'fa_lev': 1, 'fa_asset_turn': 1}

**B角建议(下一代策略)**:
- 【r1_leaf_conc】叶子[fa_lev]占比50%过高 -> 权重压到0.25, 逼引擎换字段

```
mix=[0.123, 0.377, 0.15, 0.2, 0.15]  depth=[3, 4, 5]  min_stab=0.3  decorr=0.75  fsa_th=0.15  bank_skel_max=1
leaf_w={'overnight': 0.25, 'fa_lev': 0.25}
```

**规则动作留痕**:
- `r1_leaf_conc` 叶子过度集中 -> 压低该叶子权重 —— 施加于第 [5, 6] 代
- `r5_calmar_cross` L2 多因 Calmar 不足 -> 交叉+15% / 深度加深 —— 施加于第 [2, 3] 代（**已永久关闭**）
- `r7_zero_pass` 本代 0 通过 -> 深度放宽到 3~5 —— 施加于第 [2, 3] 代（**已永久关闭**）
- ⛔ **被 LLM 永久否决的动作**（用户要求「让它永久闭嘴」）：`r5_calmar_cross`, `r7_zero_pass`

**LLM 引导(A角 5代)**: 调用3次, 解析通过43条, 引导位使用43条
> 日内主动资金流强度（大单/超大单净买入占比）相对价格涨幅的背离，预示未来5日截面收益的反转：放量滞涨或缩量急拉的个股资金效率低，未来跑输；反之资金效率高者跑赢。


**LLM 候选审查(B角 5代)**: 深判 5 个, KILL 5 个(剔除出 L2 费后回测)
- KILL `neg(ts_mean200(ts_mean100(ts_mean200(ts_mean150(open)))))`
  > 理由: 多层同源ts_mean嵌套仅平滑开盘价，无经济含义，纯参数冗余堆叠
- KILL `ts_mean150(ts_mean5(div(ts_mean150(open), mktcap)))`
  > 理由: 开盘价均值除以市值，仅再表达市值老故事，无增量量价机制，且双层同源均值冗余。
- KILL `ts_mean200(ts_mean5(cs_scale(ts_mean200(ts_mean150(fa_roe)))))`
  > 理由: 纯ROE多层平滑无价量机制，窗口150/200冗余，属参数海里捞针
- KILL `neg(log(ts_mean200(log(ts_mean120(fa_lev)))))`
  > 理由: fa_lev为财务杠杆字段，非量价行为，双层对数长窗口均值无经济含义，属数学拼凑
- KILL `ts_mean60(ts_mean200(fa_pb))`
  > 理由: 仅对pb做双重均线平滑，无价量行为机制，属冗余嵌套，无增量信息


**AI 审查(DeepSeek deepseek-flash, 2s)**:

> (1)病根:两个L1全是深度嵌套的ts_mean平滑,信号被磨平,IC≈0.02且calmar为负,叶子集中只是表象,真病是因子无预测力却硬撑结构。
> 
> (2)r1_leaf_conc对症但力度错:压权重到0.25只会逼引擎换字段,不解决嵌套过深;且与depth=[3,4,5]冲突——深度上限仍允许5层,换汤不换药。decorr=0.75偏高会误杀同族弱信号,min_stab=0.3过松,stab已全1.0,形同虚设。
> 
> (3)建议:mix=[0.35,0.25,0.15,0.15,0.10] 提高变异与随机以跳出平滑陷阱;depth=[2,3,4] 砍掉5层;min_stab=0.6 收紧;decorr=0.5 放宽避免误杀。
> 
> (4)否决见下。
> 
> 否决: r1_leaf_conc

**⚖️ 规则动作否决（机器读取）**: `r1_leaf_conc`（叶子过度集中 -> 压低该叶子权重）

## 第 6 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | gate_min_calmar | gate_min_pool_calmar | fail_calmar | fail_calmar_neg | fail_pool_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill | st_l2_lncap | st_l2_lnamt | st_l2_lntr | st_l2_lnpx | st_l1_lncap | st_l1_lnamt | st_l1_lntr | st_l1_lnpx |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 12 | 0.052 | 0.085 | 0.999 | 0.000 | 0.167 | 1.000 | 2 | 0.083 | 12 | 0 | 0.003 | 0.000 | 0.150 | 0.917 | 0.917 | 1.000 | 0.000 | 1.000 | 0.833 | 0.833 | 1.000 | 0.209 | 0.144 | 0.251 | 0.229 | 0.209 | 0.144 | 0.251 | 0.229 |

叶子使用: {'fa_asset_turn': 2, 'mf_s_sell': 2, 'barra_beta': 2, 'fa_lev': 1, 'high': 1, 'overnight': 1}

**B角建议(下一代策略)**:
- 【拦截】[r5_calmar_cross] LLM 已【永久】否决，后续各代一律不再施加 —— L2 多因 Calmar 不足 -> 交叉+15% / 深度加深
- 【拦截】[r7_zero_pass] LLM 已【永久】否决，后续各代一律不再施加 —— 本代 0 通过 -> 深度放宽到 3~5
- —— 本代共拦截 2 条动作（饱和/LLM 否决），详见上面【拦截】行

```
mix=[0.123, 0.377, 0.15, 0.2, 0.15]  depth=[3, 4, 5]  min_stab=0.3  decorr=0.75  fsa_th=0.15  bank_skel_max=1
leaf_w={}
```

**规则动作留痕**:
- `r1_leaf_conc` 叶子过度集中 -> 压低该叶子权重 —— 施加于第 [5, 6] 代（**已永久关闭**）
- `r5_calmar_cross` L2 多因 Calmar 不足 -> 交叉+15% / 深度加深 —— 施加于第 [2, 3] 代（**已永久关闭**）
- `r7_zero_pass` 本代 0 通过 -> 深度放宽到 3~5 —— 施加于第 [2, 3] 代（**已永久关闭**）
- ⛔ **被 LLM 永久否决的动作**（用户要求「让它永久闭嘴」）：`r5_calmar_cross`, `r7_zero_pass`, `r1_leaf_conc`

**LLM 引导(A角 6代)**: 调用3次, 解析通过31条, 引导位使用31条
> 个股日内主动资金流的短期相对强度(短窗净主动买入占比相对长窗基准的偏离)刻画了知情交易者的持续吸筹行为,该行为在截面上的延续性可预测未来5日收益。


**LLM 候选审查(B角 6代)**: 深判 5 个, KILL 3 个(剔除出 L2 费后回测)
- KILL `ts_mean100(ema5(ema60(mf_s_bqty)))`
  > 理由: mf_s_bqty为主动卖量，ema5/ema60/ts_mean100三层同源平滑冗余，无增量机制，属参数海捞针
- KILL `neg(log(ts_mean200(fa_pb)))`
  > 理由: 仅对市净率取长周期均值再取负，属估值类老故事，非量价行为，无增量机制
- KILL `sub(ts_mean120(overnight), ts_mean120(barra_leverage))`
  > 理由: 隔夜收益减杠杆因子，量纲与含义拼凑，无明确量价机制，属数学巧合


**AI 审查(DeepSeek deepseek-flash, 2s)**:

> (1)病根:IC尚可但L2全线负Calmar、neg_yr高达3~7,因子只有截面区分度、没有时序赚钱能力,叠加known_ratio仅0.083说明在重复挖已知无效骨架。
> 
> (2)两条建议都是"拦截"而非新动作,等于本代零干预;r5/r7已被永久否决,再列一遍只是复述,不产生新信息。真正该动的是L2的neg_yr与lastyr,而建议完全没碰,属对症错位。
> 
> (3)mix=[0.15,0.35,0.15,0.2,0.15],depth=[2,3,4],min_stab=0.5,decorr=0.6:压低深度与随机、抬高引导,逼出时序稳健而非再堆IC。
> 
> 否决: 无

## 第 7 代 (B角诊断)

| n_l1 | fam_blocked | n_l2 |
| --- | --- | --- |
| 0 | 0 | 0 |

**B角建议(下一代策略)**:
- 各项指标正常, 维持当前策略

```
mix=[0.123, 0.377, 0.15, 0.2, 0.15]  depth=[3, 4, 5]  min_stab=0.3  decorr=0.75  fsa_th=0.15  bank_skel_max=1
leaf_w={}
```

**规则动作留痕**:
- `r1_leaf_conc` 叶子过度集中 -> 压低该叶子权重 —— 施加于第 [5, 6] 代（**已永久关闭**）
- `r5_calmar_cross` L2 多因 Calmar 不足 -> 交叉+15% / 深度加深 —— 施加于第 [2, 3] 代（**已永久关闭**）
- `r7_zero_pass` 本代 0 通过 -> 深度放宽到 3~5 —— 施加于第 [2, 3] 代（**已永久关闭**）
- ⛔ **被 LLM 永久否决的动作**（用户要求「让它永久闭嘴」）：`r5_calmar_cross`, `r7_zero_pass`, `r1_leaf_conc`

**LLM 引导(A角 7代)**: 调用3次, 解析通过32条, 引导位使用32条
> 资金流内部结构失衡（超大单主动净买入相对中小单的背离，且该失衡与价格变化方向不一致时）能在未来5日截面收益上产生反转式预测力，即'聪明钱吸筹但价格未跟涨'的股票后续跑赢。


**LLM 候选审查(B角 7代)**: 深判 4 个, KILL 4 个(剔除出 L2 费后回测)
- KILL `neg(ts_mean200(neg(ts_mean200(ema60(fa_asset_turn)))))`
  > 理由: 双重取负+双层200日均值冗余嵌套，仅平滑资产周转率，无增量量价机制，属参数堆砌
- KILL `neg(ts_mean200(ema60(ts_mean150(high))))`
  > 理由: 仅对high做多层长窗平滑取负，无成交量价配合，属参数冗余的纯价格趋势，无增量机制
- KILL `ts_mean200(ts_mean150(min(fa_lev, fa_lev)))`
  > 理由: min自比较冗余，双层同源均值无经济含义，纯参数堆砌
- KILL `ts_min20(ts_mean60(ts_mean200(barra_leverage)))`
  > 理由: 纯杠杆字段多层同源均值嵌套，无价量行为含义，参数冗余似过拟合


**AI 审查(DeepSeek deepseek-flash, 2s)**:

> (1) 病根: n_l1=n_l2=0 且叶子使用 None, 说明本轮根本没产出候选, 不是"指标正常", 而是采样/筛选链路整段空转。
> 
> (2) 规则B角"维持当前策略"完全不对症: 零候选下维持等于再空跑一代, 且与已永久关闭三项规则叠加, 搜索空间被压得更窄, 无任何新增探索补偿。
> 
> (3) 下代建议: mix=[0.35,0.25,0.15,0.15,0.10] 提高变异与随机以打破空转; depth=[3,4] 降深度减组合爆炸; min_stab=0.15 放宽门槛先让候选落地; decorr=0.6 松绑相关性约束。
> 
> 否决: 无
