
## 第 4 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 28 | 0.052 | 0.067 | 0.912 | 0.000 | 0.429 | 0.929 | 0.536 | 25 | 0 | 0.032 | 1.000 | 0.480 | 0.960 | 0.320 | 0.000 |

叶子使用: {'volume': 12, 'turn_ratio': 10, 'ln_volume': 8, 'turnover': 5, 'ret': 4, 'mktcap': 3}

**B角建议(下一代策略)**:
- 叶子[volume]占比43%过高 -> 权重压到0.25, 逼引擎换字段
- L2中48%因换手过高失败 -> min_stab再+0.10
- L2中100%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 本代0通过 -> 深度放宽到3~5, 探索更复杂结构

```
mix=[0.212, 0.4, 0.15, 0.15, 0.2]  depth=[3, 4, 5]  min_stab=0.4  decorr=0.75
leaf_w={'volume': 0.25}
```

## 第 5 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 41 | 0.058 | 0.071 | 0.914 | 0.000 | 0.634 | 0.902 | 0.488 | 25 | 0 | 0.038 | 1.000 | 0.320 | 1.000 | 0.280 | 0.000 |

叶子使用: {'turn_ratio': 26, 'volume': 25, 'turnover': 10, 'ln_volume': 7, 'ret': 7, 'close': 4}

**B角建议(下一代策略)**:
- 叶子[turn_ratio]占比63%过高 -> 权重压到0.25, 逼引擎换字段
- L2中100%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 本代0通过 -> 深度放宽到3~5, 探索更复杂结构

```
mix=[0.154, 0.45, 0.15, 0.15, 0.2]  depth=[3, 4, 5]  min_stab=0.5  decorr=0.75
leaf_w={'volume': 0.25, 'turn_ratio': 0.25}
```

## 第 6 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 40 | 0.063 | 0.075 | 0.920 | 0.000 | 0.775 | 0.925 | 0.250 | 25 | 0 | 0.030 | 1.000 | 0.440 | 1.000 | 0.240 | 0.000 |

叶子使用: {'turn_ratio': 31, 'volume': 29, 'ret': 13, 'high': 6, 'turnover': 5, 'close': 5}

**B角建议(下一代策略)**:
- 叶子[turn_ratio]占比78%过高 -> 权重压到0.25, 逼引擎换字段
- L2中44%因换手过高失败 -> min_stab再+0.10
- L2中100%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 本代0通过 -> 深度放宽到3~5, 探索更复杂结构

```
mix=[0.111, 0.45, 0.15, 0.15, 0.2]  depth=[3, 4, 5]  min_stab=0.6  decorr=0.75
leaf_w={'volume': 0.25, 'turn_ratio': 0.25}
```

## 第 7 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 45 | 0.066 | 0.079 | 0.905 | 0.000 | 0.911 | 1.000 | 0.400 | 30 | 0 | 0.063 | 1.000 | 0.667 | 0.967 | 0.233 | 0.000 |

叶子使用: {'turn_ratio': 41, 'volume': 36, 'ret': 20, 'mktcap': 11, 'turnover': 7, 'open': 7}

**B角建议(下一代策略)**:
- 叶子[turn_ratio]占比91%过高 -> 权重压到0.25, 逼引擎换字段
- L2中67%因换手过高失败 -> min_stab再+0.10
- L2中100%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 本代0通过 -> 深度放宽到3~5, 探索更复杂结构

```
mix=[0.08, 0.45, 0.15, 0.15, 0.2]  depth=[3, 4, 5]  min_stab=0.75  decorr=0.75
leaf_w={'volume': 0.25, 'turn_ratio': 0.25}
```

## 第 8 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 44 | 0.070 | 0.086 | 0.903 | 0.000 | 0.864 | 0.955 | 0.773 | 30 | 1 | 0.063 | 1.000 | 0.862 | 0.931 | 0.310 | 0.000 |

叶子使用: {'turn_ratio': 38, 'volume': 35, 'mktcap': 26, 'turnover': 11, 'open': 10, 'close': 9}

**B角建议(下一代策略)**:
- 叶子[turn_ratio]占比86%过高 -> 权重压到0.25, 逼引擎换字段
- L2中86%因换手过高失败 -> min_stab再+0.10
- L2中100%因Calmar不足(信号弱) -> 交叉+15%, 深度加深

```
mix=[0.058, 0.45, 0.15, 0.15, 0.2]  depth=[3, 4, 4]  min_stab=0.75  decorr=0.75
leaf_w={'volume': 0.25, 'turn_ratio': 0.25}
```

## 第 9 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 28 | 0.077 | 0.085 | 0.862 | 0.000 | 0.857 | 0.964 | 0.679 | 28 | 0 | 0.064 | 1.000 | 0.964 | 0.893 | 0.357 | 0.000 |

叶子使用: {'turn_ratio': 24, 'volume': 19, 'turnover': 13, 'mktcap': 12, 'close': 9, 'ret': 9}

**B角建议(下一代策略)**:
- 叶子[turn_ratio]占比86%过高 -> 权重压到0.25, 逼引擎换字段
- L2中96%因换手过高失败 -> min_stab再+0.10
- L2中100%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 68%候选仍含已知族字段 -> decorr收紧到0.65(0.70≈中金入库IC相关口径)
- 本代0通过 -> 深度放宽到3~5, 探索更复杂结构

```
mix=[0.042, 0.45, 0.15, 0.15, 0.2]  depth=[3, 4, 5]  min_stab=0.75  decorr=0.65
leaf_w={'volume': 0.25, 'turn_ratio': 0.25}
```

## 第 10 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 29 | 0.073 | 0.086 | 0.852 | 0.000 | 0.862 | 1.000 | 0.690 | 29 | 3 | 0.065 | 1.000 | 0.962 | 0.846 | 0.115 | 0.000 |

叶子使用: {'turn_ratio': 25, 'volume': 20, 'turnover': 17, 'ret': 16, 'mktcap': 12, 'close': 7}

**B角建议(下一代策略)**:
- 叶子[turn_ratio]占比86%过高 -> 权重压到0.25, 逼引擎换字段
- L2中96%因换手过高失败 -> min_stab再+0.10
- L2中100%因Calmar不足(信号弱) -> 交叉+15%, 深度加深

```
mix=[0.03, 0.45, 0.15, 0.15, 0.2]  depth=[3, 4, 4]  min_stab=0.75  decorr=0.65
leaf_w={'volume': 0.25, 'turn_ratio': 0.25}
```

## 第 11 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 13 | 0.046 | 0.075 | 0.943 | 0.000 | 0.846 | 1.000 | 0.077 | 13 | 4 | 0.060 | 1.000 | 0.333 | 0.667 | 0.222 | 0.000 |

叶子使用: {'turn_ratio': 11, 'close': 4, 'volume': 4, 'ret': 3, 'open': 3, 'turnover': 1}

**B角建议(下一代策略)**:
- 叶子[turn_ratio]占比85%过高 -> 权重压到0.25, 逼引擎换字段
- L2中100%因Calmar不足(信号弱) -> 交叉+15%, 深度加深

```
mix=[0.022, 0.45, 0.15, 0.15, 0.2]  depth=[3, 4, 4]  min_stab=0.75  decorr=0.65
leaf_w={'volume': 0.25, 'turn_ratio': 0.25}
```

## 第 12 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 18 | 0.029 | 0.075 | 0.895 | 0.000 | 0.833 | 1.000 | 0.111 | 18 | 0 | 0.058 | 1.000 | 0.278 | 0.889 | 0.222 | 0.000 |

叶子使用: {'turn_ratio': 15, 'volume': 6, 'close': 6, 'open': 5, 'ret': 4, 'turnover': 2}

**B角建议(下一代策略)**:
- 叶子[turn_ratio]占比83%过高 -> 权重压到0.25, 逼引擎换字段
- L2中100%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 本代0通过 -> 深度放宽到3~5, 探索更复杂结构

```
mix=[0.016, 0.45, 0.15, 0.15, 0.2]  depth=[3, 4, 5]  min_stab=0.75  decorr=0.65  fsa_th=0.15  bank_skel_max=1
leaf_w={'volume': 0.25, 'turn_ratio': 0.25}
```

## 第 13 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 58 | 0.049 | 0.075 | 0.936 | 0.000 | 0.259 | 1.000 | 0.224 | 30 | 0 | 0.058 | 1.000 | 0.233 | 0.900 | 0.233 | 0.000 |

叶子使用: {'turn_ratio': 15, 'turnover': 8, 'ret': 7, 'open': 6, 'close': 4, 'high': 4}

**B角建议(下一代策略)**:
- L2中100%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 本代0通过 -> 深度放宽到3~5, 探索更复杂结构

```
mix=[0.011, 0.45, 0.15, 0.15, 0.2]  depth=[3, 4, 5]  min_stab=0.75  decorr=0.65  fsa_th=0.15  bank_skel_max=1
leaf_w={'volume': 0.25, 'turn_ratio': 0.25}
```

## 第 14 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 48 | 0.049 | 0.075 | 0.907 | 0.000 | 0.375 | 1.000 | 0.479 | 30 | 1 | 0.088 | 1.000 | 0.310 | 0.828 | 0.483 | 0.000 |

叶子使用: {'turnover': 18, 'turn_ratio': 17, 'open': 10, 'ln_mktcap': 10, 'volume': 8, 'close': 8}

**B角建议(下一代策略)**:
- L2中100%因Calmar不足(信号弱) -> 交叉+15%, 深度加深

```
mix=[0.008, 0.45, 0.15, 0.15, 0.2]  depth=[3, 4, 4]  min_stab=0.75  decorr=0.65  fsa_th=0.15  bank_skel_max=1
leaf_w={'volume': 0.25, 'turn_ratio': 0.25}
```

## 第 15 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 42 | 0.051 | 0.076 | 0.892 | 0.000 | 0.381 | 1.000 | 0.452 | 30 | 0 | 0.050 | 1.000 | 0.300 | 0.900 | 0.667 | 0.000 |

叶子使用: {'turn_ratio': 16, 'turnover': 16, 'ret': 11, 'close': 10, 'ln_mktcap': 10, 'volume': 9}

**B角建议(下一代策略)**:
- L2中100%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 本代0通过 -> 深度放宽到3~5, 探索更复杂结构

```
mix=[0.006, 0.45, 0.15, 0.15, 0.2]  depth=[3, 4, 5]  min_stab=0.75  decorr=0.65  fsa_th=0.15  bank_skel_max=1
leaf_w={'volume': 0.25, 'turn_ratio': 0.25}
```

## 第 16 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 49 | 0.053 | 0.071 | 0.870 | 0.000 | 0.633 | 0.980 | 0.714 | 30 | 0 | 0.052 | 1.000 | 0.167 | 0.967 | 0.500 | 0.000 |

叶子使用: {'turnover': 31, 'ln_mktcap': 11, 'vwap': 7, 'high': 6, 'turn_ratio': 6, 'open': 2}

**B角建议(下一代策略)**:
- 叶子[turnover]占比63%过高 -> 权重压到0.25, 逼引擎换字段
- L2中100%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 本代0通过 -> 深度放宽到3~5, 探索更复杂结构
- 配比护栏: 变异/交叉各≥10%且合计50%重归一化, 扰动/引导/随机固定15/20/15(中金规格) -> mix=[0.1, 0.4, 0.15, 0.2, 0.15]

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 5]  min_stab=0.75  decorr=0.65  fsa_th=0.15  bank_skel_max=1
leaf_w={'volume': 0.25, 'turn_ratio': 0.25, 'turnover': 0.25}
```

**LLM 引导(A角 16代)**: 调用3次, 解析通过43条, 引导位使用43条
> 隔夜与日内收益的波动结构、交易量与换手率的相对变化所反映的短期流动性冲击和价格修正行为，能预测未来5日截面收益。


**LLM 候选审查(B角 16代)**: 深判 5 个, KILL 4 个(剔除出 L2 费后回测)
- KILL `add(ts_sum100(mul(hl_ratio, intraday)), ts_delta120(ts_rank200(ts_mean10(turnover))))`
  > 理由: 混合波动率与换手率不同源信号，结构拼凑且窗口冗余，经济含义模糊。
- KILL `div(turnover, ts_min100(ts_mean60(mul(ln_mktcap, min(intraday, corr100(hl_ratio, intraday))))))`
  > 理由: 结构复杂拼凑，量价含义不明，疑似参数搜索过拟合。
- KILL `sub(add(sub(div(high, vwap), corr60(true_range, volume)), div(abs(amplitude), vwap)), turn_ratio)`
  > 理由: 结构拼凑，量价含义混杂，含换手率老因子，无清晰经济逻辑。
- KILL `ts_mean60(mul(div(turnover, ts_min100(corr100(up_shadow, hl_ratio))), intraday))`
  > 理由: 结构拼凑，量价含义不明，嵌套冗余似参数搜索


**AI 审查(DeepSeek deepseek-v4-flash, 2s)**:

> (1) 病根：信号源过度集中于turnover单一叶子，导致结构同质化，L2全因Calmar不足而失败，缺乏跨字段互补性。
> 
> (2) 规则B角建议：压turnover权重对症，但0.25仍偏高，建议≤0.15；交叉+15%可缓解但深度放宽至5易过拟合，与min_stab=0.75冲突；变异/交叉合计50%重归一化后扰动/引导/随机比例失衡，可能降低探索效率；decorr=0.65对当前高concern不足。
> 
> (3) 下代建议：mix=[0.15,0.35,0.15,0.2,0.15]，depth=[3,4]，min_stab=0.80，decorr=0.75。理由：提高变异比例强制换字段，收紧深度与稳定性以对抗过拟合，提高去相关阈值直接压制leaf_conc。

## 第 17 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 36 | 0.057 | 0.071 | 0.885 | 0.000 | 0.639 | 1.000 | 0.694 | 30 | 0 | 0.055 | 1.000 | 0.100 | 0.900 | 0.333 | 0.000 |

叶子使用: {'turnover': 23, 'vwap': 10, 'turn_ratio': 8, 'high': 5, 'ln_mktcap': 4, 'volume': 3}

**B角建议(下一代策略)**:
- 叶子[turnover]占比64%过高 -> 权重压到0.25, 逼引擎换字段
- L2中100%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 本代0通过 -> 深度放宽到3~5, 探索更复杂结构
- 配比护栏: 变异/交叉各≥10%且合计50%重归一化, 扰动/引导/随机固定15/20/15(中金规格) -> mix=[0.1, 0.4, 0.15, 0.2, 0.15]

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 5]  min_stab=0.75  decorr=0.65  fsa_th=0.15  bank_skel_max=1
leaf_w={'volume': 0.25, 'turn_ratio': 0.25, 'turnover': 0.25}
```

**LLM 引导(A角 17代)**: 调用3次, 解析通过40条, 引导位使用40条
> 流动性断层与成交活跃度突变后，资金惯性在5日内延续，可通过换手率与成交额偏离度捕捉


**LLM 候选审查(B角 17代)**: 深判 5 个, KILL 5 个(剔除出 L2 费后回测)
- KILL `div(turnover, ts_min100(corr100(up_shadow, ts_std20(ts_sum100(mul(low, intraday))))))`
  > 理由: 结构拼凑，量价含义不明，窗口冗余似参数搜索。
- KILL `ts_mean60(mul(div(turnover, ts_min100(sub(div(high, vwap), corr60(true_range, intraday)))), intraday))`
  > 理由: 结构拼凑，量价含义混杂，窗口参数冗余，疑似过拟合。
- KILL `div(turnover, ts_min100(corr100(up_shadow, ts_std20(ts_sum100(mul(corr60(div(mktcap, true_range), intraday), intraday))))))`
  > 理由: 结构嵌套冗余，窗口参数堆叠，经济含义模糊，疑似参数搜索产物。
- KILL `div(turnover, ts_min100(corr100(up_shadow, ts_std20(ts_rank200(ts_mean10(vwap))))))`
  > 理由: 换手率除以阴影与VWAP复杂相关最小值，结构拼凑且窗口冗余，经济含义不明。
- KILL `mul(corr200(high, mul(mktcap, mul(open, ln_mktcap))), ts_sum100(mul(ts_std20(amplitude), intraday)))`
  > 理由: 市值与对数市值相乘再与开盘价相关，结构拼凑无明确量价含义，疑似参数冗余。


**AI 审查(DeepSeek deepseek-v4-flash, 2s)**:

> (1) 病根：所有L1因子均以intraday为核心且ts_mean60同构，信号单一且弱，导致L2叠加后Calmar普遍不足，无一通过。
> 
> (2) 规则B角点评：压turnover权重对症，但0.25仍偏高，且未限制intraday这一真正垄断叶子；交叉+15%和深度放宽可增加结构多样性，但深度3~5可能加剧过拟合，与min_stab=0.75偏低冲突；decorr=0.65对同质化因子约束不足。
> 
> (3) 下代建议：mix=[0.15, 0.35, 0.15, 0.2, 0.15]（提高变异探索新叶子），depth=[2,3,4]（控制复杂度），min_stab=0.80（保稳定性），decorr=0.75（强制去同质）。理由：先打破intraday垄断，再谈深度。

## 第 18 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 42 | 0.056 | 0.071 | 0.894 | 0.000 | 0.690 | 1.000 | 0.714 | 30 | 0 | 0.055 | 1.000 | 0.033 | 0.933 | 0.367 | 0.000 |

叶子使用: {'turnover': 29, 'vwap': 6, 'turn_ratio': 5, 'volume': 5, 'ln_mktcap': 4, 'high': 3}

**B角建议(下一代策略)**:
- 叶子[turnover]占比69%过高 -> 权重压到0.25, 逼引擎换字段
- L2中100%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 本代0通过 -> 深度放宽到3~5, 探索更复杂结构
- 配比护栏: 变异/交叉各≥10%且合计50%重归一化, 扰动/引导/随机固定15/20/15(中金规格) -> mix=[0.1, 0.4, 0.15, 0.2, 0.15]

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 5]  min_stab=0.75  decorr=0.65  fsa_th=0.15  bank_skel_max=1
leaf_w={'volume': 0.25, 'turn_ratio': 0.25, 'turnover': 0.25}
```

**LLM 引导(A角 18代)**: 调用3次, 解析通过45条, 引导位使用45条
> 流动性边际收缩与日内波动结构突变预示未来5日截面收益分化


**LLM 候选审查(B角 18代)**: 深判 5 个, KILL 4 个(剔除出 L2 费后回测)
- KILL `ts_mean60(mul(amplitude, min(intraday, cs_rank(ts_min100(corr100(up_shadow, ts_std20(cs_rank(open))))))))`
  > 理由: 结构复杂嵌套，多算子叠加同源量价字段，经济含义模糊，疑似过拟合拼凑。
- KILL `div(turnover, ts_min100(corr100(up_shadow, div(turnover, ts_min100(mul(turnover, intraday))))))`
  > 理由: turnover自除冗余，嵌套无经济含义，疑似参数拼凑。
- KILL `div(turnover, ts_min100(corr100(up_shadow, ts_std20(ts_rank200(ts_mean60(mul(div(vwap, ts_min100(overnight)), intraday)))))))`
  > 理由: 多层嵌套窗口叠加，结构冗余难解释，疑似参数海中捞针
- KILL `div(turnover, ts_min100(corr100(intraday, ts_std20(sign(mul(intraday, intraday))))))`
  > 理由: 结构拼凑，日内收益平方符号与换手率比值无明确经济含义，疑似过拟合。


**AI 审查(DeepSeek deepseek-v4-flash, 3s)**:

> (1) 病根: 信号源单一且弱, 全代围绕intraday/amplitude做均值化, 无增量信息, 导致Calmar全线不达标。
> 
> (2) 规则B角点评: 压turnover权重对症, 但0.25过猛易破坏现有微弱信号; 交叉+15%与深度放宽方向正确, 但深度3~5在弱信号下易过拟合; 变异仅10%偏低, 无法有效跳出intraday陷阱; decorr=0.65偏高, 会过度惩罚同源结构, 反而限制探索。
> 
> (3) 建议: mix=[0.15, 0.35, 0.15, 0.20, 0.15], depth=[3,4], min_stab=0.70, decorr=0.55。理由: 提高变异比例以强制换字段, 降低稳定与去相关门槛以容忍弱信号下的结构多样性。

## 第 19 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 44 | 0.058 | 0.071 | 0.901 | 0.000 | 0.614 | 1.000 | 0.659 | 30 | 0 | 0.062 | 1.000 | 0.033 | 0.933 | 0.500 | 0.000 |

叶子使用: {'turnover': 27, 'volume': 9, 'turn_ratio': 7, 'ln_mktcap': 4, 'high': 3, 'low': 2}

**B角建议(下一代策略)**:
- 叶子[turnover]占比61%过高 -> 权重压到0.25, 逼引擎换字段
- L2中100%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 本代0通过 -> 深度放宽到3~5, 探索更复杂结构
- 配比护栏: 变异/交叉各≥10%且合计50%重归一化, 扰动/引导/随机固定15/20/15(中金规格) -> mix=[0.1, 0.4, 0.15, 0.2, 0.15]

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 5]  min_stab=0.75  decorr=0.65  fsa_th=0.15  bank_skel_max=1
leaf_w={'volume': 0.25, 'turn_ratio': 0.25, 'turnover': 0.25}
```

**LLM 引导(A角 19代)**: 调用3次, 解析通过40条, 引导位使用40条
> 高频换手与日内波动结构交互形成的流动性溢价衰减，预测未来5日截面收益方向反转


**LLM 候选审查(B角 19代)**: 深判 5 个, KILL 5 个(剔除出 L2 费后回测)
- KILL `div(turnover, ts_min100(corr100(ts_std20(sign(mul(intraday, intraday))), ts_mean60(ts_std20(hl_ratio)))))`
  > 理由: sign(mul(intraday,intraday))恒为1，结构冗余无增量，且嵌套复杂似参数拼凑。
- KILL `sub(add(sub(div(high, turnover), corr60(true_range, turn_ratio)), neg(log(corr100(mul(amplitude, intraday), intraday)))), turn_ratio)`
  > 理由: 结构拼凑多源量价，含义混杂难解释，疑似参数冗余过拟合。
- KILL `mul(turnover, ts_min100(corr100(up_shadow, ts_std20(ts_sum100(mul(ts_delta120(mul(volume, min(intraday, intraday))), intraday))))))`
  > 理由: 结构冗余拼凑，窗口嵌套无经济含义，疑似参数过拟合。
- KILL `sub(mul(turnover, ts_min100(corr100(up_shadow, ts_std20(ts_sum100(mul(ts_mean60(mul(volume, min(intraday, intraday))), intraday)))))), turn_ratio)`
  > 理由: 结构冗余嵌套，含min(x,x)恒等及多层同源窗口，疑似参数拼凑，经济含义模糊。
- KILL `ts_mean60(mul(amplitude, min(intraday, cs_rank(ts_min100(corr100(up_shadow, ts_std20(ts_sum100(mul(ln_mktcap, true_range)))))))))`
  > 理由: 结构嵌套冗余，窗口参数堆砌，经济含义模糊，疑似参数搜索产物。


**AI 审查(DeepSeek deepseek-v4-flash, 2s)**:

> (1) 病根：信号结构单一，全部依赖振幅与日内波动的组合，缺乏独立信息源，导致IC封顶且无法通过Calmar检验。
> 
> (2) 规则B角点评：压turnover权重对症但力度不足，因头部因子仍以intraday为核心；交叉+15%与深度放宽可能加剧结构同质化，无效；min_stab降至0.75过松，会引入噪声因子，与decorr=0.65冲突。
> 
> (3) 下代建议：mix=[0.15, 0.25, 0.2, 0.25, 0.15]，增加变异与引导探索新叶子组合；depth=[2,3,4]限制深度防过拟合；min_stab=0.85保质量；decorr=0.8强制去重。理由：需打破振幅垄断，引入换手率与市值交互。

## 第 20 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 41 | 0.057 | 0.074 | 0.901 | 0.000 | 0.659 | 0.976 | 0.756 | 30 | 0 | 0.062 | 1.000 | 0.033 | 0.933 | 0.300 | 0.000 |

叶子使用: {'turnover': 27, 'volume': 7, 'low': 6, 'ln_volume': 4, 'turn_ratio': 4, 'high': 2}

**B角建议(下一代策略)**:
- 叶子[turnover]占比66%过高 -> 权重压到0.25, 逼引擎换字段
- L2中100%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 本代0通过 -> 深度放宽到3~5, 探索更复杂结构
- 配比护栏: 变异/交叉各≥10%且合计50%重归一化, 扰动/引导/随机固定15/20/15(中金规格) -> mix=[0.1, 0.4, 0.15, 0.2, 0.15]

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 5]  min_stab=0.75  decorr=0.65  fsa_th=0.15  bank_skel_max=1
leaf_w={'volume': 0.25, 'turn_ratio': 0.25, 'turnover': 0.25}
```

**LLM 引导(A角 20代)**: 调用3次, 解析通过44条, 引导位使用44条
> 市场对日内波动结构（尤其上影与下影的不对称性）的定价存在持续性，且与成交量能交互作用，可预测未来5日截面收益。


**LLM 候选审查(B角 20代)**: 深判 5 个, KILL 5 个(剔除出 L2 费后回测)
- KILL `ts_mean60(mul(div(mul(intraday, mul(amplitude, intraday)), ts_min100(intraday)), intraday))`
  > 理由: intraday自乘嵌套冗余，含义拼凑，疑似参数搜索产物。
- KILL `ts_mean60(mul(amplitude, min(intraday, cs_rank(ts_sum100(mul(ts_mean5(mul(volume, min(intraday, intraday))), intraday))))))`
  > 理由: 多层嵌套同源算子且含min(x,x)冗余，结构复杂难解释，疑似参数拼凑。
- KILL `mul(turnover, ts_min100(corr100(true_range, ts_std20(ts_std20(ts_sum100(mul(intraday, up_shadow)))))))`
  > 理由: 多层同源波动率嵌套叠加换手率，结构冗余且经济含义模糊，疑似参数拼凑。
- KILL `mul(turnover, ts_min100(corr100(ts_min100(intraday), ts_std20(ts_sum100(mul(div(amplitude, ts_min100(intraday)), intraday))))))`
  > 理由: 结构冗余嵌套同源算子，经济含义模糊，疑似参数拼凑
- KILL `mul(turnover, ts_min100(corr100(up_shadow, ts_std20(ts_sum100(mul(ts_mean10(ts_mean60(mul(amplitude, min(intraday, cs_rank(down_shadow))))), intraday))))))`
  > 理由: 多层嵌套窗口与同源影子/振幅算子叠加，结构冗余难解释，疑似参数拼凑。


**AI 审查(DeepSeek deepseek-v4-flash, 2s)**:

> (1) 病根：IC虽高但L2全灭，说明候选因子是“短命高相关”的伪信号，且过度依赖turnover单叶，结构脆弱无增量。
> 
> (2) 规则B角点评：压turnover权重对症，但0.25过狠，恐逼出噪声替代；交叉+15%与深度放宽至5方向对，但深度5易过拟合，且与min_stab=0.75冲突（深树难稳）；decorr=0.65偏低，无法解决leaf_conc=0.659的根因。
> 
> (3) 下代建议：mix=[0.15, 0.35, 0.15, 0.2, 0.15]，depth=[3,4]，min_stab=0.85，decorr=0.8。理由：浅树+高稳定性+强去相关，优先验证“turnover+intraday”组合的普适性，而非盲目加复杂度。

## 第 21 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 49 | 0.059 | 0.072 | 0.897 | 0.000 | 0.449 | 0.959 | 0.633 | 30 | 0 | 0.059 | 1.000 | 0.000 | 0.933 | 0.167 | 0.000 |

叶子使用: {'turnover': 22, 'low': 19, 'volume': 10, 'ln_volume': 7, 'ret': 4, 'ln_mktcap': 3}

**B角建议(下一代策略)**:
- 叶子[turnover]占比45%过高 -> 权重压到0.25, 逼引擎换字段
- L2中100%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 本代0通过 -> 深度放宽到3~5, 探索更复杂结构
- 配比护栏: 变异/交叉各≥10%且合计50%重归一化, 扰动/引导/随机固定15/20/15(中金规格) -> mix=[0.1, 0.4, 0.15, 0.2, 0.15]

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 5]  min_stab=0.75  decorr=0.65  fsa_th=0.15  bank_skel_max=1
leaf_w={'volume': 0.25, 'turn_ratio': 0.25, 'turnover': 0.25}
```

**LLM 引导(A角 21代)**: 调用3次, 解析通过38条, 引导位使用38条
> 市场在日内与隔夜信息不对称中，通过交易量与换手率的边际变化捕捉流动性溢价与信息冲击的衰减，同时利用日内价格形态的极端状态反转预测未来5日收益。


**LLM 候选审查(B角 21代)**: 深判 5 个, KILL 4 个(剔除出 L2 费后回测)
- KILL `ts_mean60(mul(amplitude, min(intraday, cs_rank(ts_min20(corr100(up_shadow, ts_std20(sign(mul(intraday, intraday)))))))))`
  > 理由: 结构拼凑，intraday自乘取符号与振幅影线相关嵌套，经济含义模糊，疑似过拟合。
- KILL `mul(turnover, ts_min100(corr100(up_shadow, ts_std20(corr20(ts_std20(sign(mul(intraday, intraday))), ts_mean10(ts_std20(intraday)))))))`
  > 理由: 结构冗余嵌套同源算子，经济含义模糊，疑似参数拼凑。
- KILL `mul(turnover, ts_min100(corr100(ts_rank20(sign(mul(intraday, intraday))), ts_mean10(ts_std20(intraday)))))`
  > 理由: sign(intraday^2)恒为1，corr退化无信息，纯冗余拼凑。
- KILL `ts_mean60(mul(mul(mul(abs(ln_volume), intraday), intraday), intraday))`
  > 理由: 纯数学拼凑，无明确量价经济含义，冗余立方结构。


**AI 审查(DeepSeek deepseek-v4-flash, 3s)**:

> (1) 病根：L1高IC全靠ts_mean60平滑intraday与amplitude，本质是日内振幅动量，但L2全因Calmar不足被否，说明信号无持续性收益，纯统计噪音。
> 
> (2) 规则B角建议：压turnover权重对症，但交叉+15%且加深深度会加剧过拟合，与“0通过”矛盾；深度放宽至3~5虽探索结构，但当前min_stab=0.75过低，易选入不稳定因子；mix中变异仅10%过少，扰动固定15%浪费算力，应加大变异探索新叶子组合。
> 
> (3) 下代建议：mix=[0.25, 0.25, 0.15, 0.2, 0.15]，变异与交叉对半开，优先重组现有高IC片段；depth=[2,3,4]防过深；min_stab=0.85提门槛；decorr=0.7强制去重。理由：信号弱需高稳定与低相关，而非盲目加深。

## 第 22 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 45 | 0.057 | 0.069 | 0.889 | 0.000 | 0.422 | 0.978 | 0.556 | 30 | 0 | 0.061 | 0.967 | 0.000 | 0.967 | 0.133 | 0.000 |

叶子使用: {'volume': 19, 'turnover': 13, 'ln_volume': 10, 'low': 10, 'ret': 6, 'mktcap': 3}

**B角建议(下一代策略)**:
- 叶子[volume]占比42%过高 -> 权重压到0.25, 逼引擎换字段
- L2中97%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 本代0通过 -> 深度放宽到3~5, 探索更复杂结构
- 配比护栏: 变异/交叉各≥10%且合计50%重归一化, 扰动/引导/随机固定15/20/15(中金规格) -> mix=[0.1, 0.4, 0.15, 0.2, 0.15]

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 5]  min_stab=0.75  decorr=0.65  fsa_th=0.15  bank_skel_max=1
leaf_w={'volume': 0.25, 'turn_ratio': 0.25, 'turnover': 0.25}
```

**LLM 引导(A角 22代)**: 调用3次, 解析通过45条, 引导位使用45条
> 跳空缺口与成交量能的结构性背离在五日维度上反映聪明钱对隔夜信息定价的持续性溢价衰减


**LLM 候选审查(B角 22代)**: 深判 5 个, KILL 5 个(剔除出 L2 费后回测)
- KILL `ts_mean60(mul(mul(mul(abs(ln_volume), intraday), ret), mul(abs(ln_volume), intraday)))`
  > 理由: 冗余嵌套同源量价乘积，无清晰经济含义，疑似参数拼凑。
- KILL `ts_mean60(mul(div(ln_volume, low), mul(mul(mul(abs(ln_mktcap), intraday), intraday), intraday)))`
  > 理由: 量价字段原始尺度混乘且重复intraday三次，含义拼凑无经济逻辑。
- KILL `ts_mean60(mul(div(mul(ret, intraday), ts_min100(true_range)), intraday))`
  > 理由: intraday在分子分母同时出现可约分，结构冗余且经济含义不明。
- KILL `ts_mean60(mul(mul(mul(abs(mul(abs(mul(div(amplitude, down_shadow), intraday)), intraday)), intraday), ret), intraday))`
  > 理由: 多层同源intraday自乘冗余，含义拼凑，疑似参数过拟合
- KILL `ts_mean60(mul(mul(mul(abs(ln_volume), intraday), ret), mul(abs(mul(div(amplitude, down_shadow), intraday)), intraday)))`
  > 理由: 多重量价字段乘积拼凑，无清晰经济含义，结构冗余似参数搜索


**AI 审查(DeepSeek deepseek-v4-flash, 2s)**:

> (1) 核心病根：L1高IC因子全部依赖intraday与turnover/volume的机械组合，信号伪高但无经济逻辑，导致L2全部Calmar失败。
> 
> (2) 规则B角点评：压volume权重对症但力度不足，因intraday才是主犯；交叉+15%与深度放宽会加剧已有结构同质化，可能无效；min_stab=0.75过低，会放行更多伪信号，与decorr=0.65冲突。
> 
> (3) 下代建议：mix=[0.15,0.3,0.2,0.2,0.15]，depth=[2,3,4]，min_stab=0.85，decorr=0.5。理由：用浅层强制换字段，提高稳定性门槛，降低相关性容忍度以逼出真正异质结构。
