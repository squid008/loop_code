
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

## 第 23 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 52 | 0.054 | 0.070 | 0.887 | 0.000 | 0.962 | 0.846 | 0.692 | 30 | 2 | 0.067 | 1.000 | 0.000 | 1.000 | 0.179 | 0.000 |

叶子使用: {'intraday': 50, 'turnover': 31, 'volume': 24, 'amplitude': 22, 'up_shadow': 14, 'overnight': 13}

**B角建议(下一代策略)**:
- 叶子[intraday]占比96%过高 -> 权重压到0.25, 逼引擎换字段
- L2中100%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 配比护栏: 变异/交叉各≥10%且合计50%重归一化, 扰动/引导/随机固定15/20/15(中金规格) -> mix=[0.1, 0.4, 0.15, 0.2, 0.15]

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 4]  min_stab=0.75  decorr=0.65  fsa_th=0.15  bank_skel_max=1
leaf_w={'volume': 0.25, 'turn_ratio': 0.25, 'turnover': 0.25, 'intraday': 0.25}
```

**LLM 引导(A角 23代)**: 调用3次, 解析通过36条, 引导位使用36条
> 大单资金流的主动买卖失衡与价格日内动量背离，能捕捉机构行为对短期收益的预测力。


**LLM 候选审查(B角 23代)**: 深判 5 个, KILL 5 个(剔除出 L2 费后回测)
- KILL `ts_mean60(mul(mul(mul(abs(mul(abs(ts_mean10(volume)), intraday)), intraday), ret), intraday))`
  > 理由: 结构冗余，abs与intraday多次相乘无明确量价行为含义，疑似数学拼凑。
- KILL `ts_mean60(mul(mul(mul(abs(mul(div(mul(mul(abs(abs(intraday)), intraday), ret), low), volume)), intraday), intraday), intraday))`
  > 理由: intraday多次自乘与abs嵌套，结构冗余且经济含义不明，疑似数学巧合。
- KILL `mul(turnover, ts_min100(corr100(overnight, ts_std20(ts_sum100(mul(div(amplitude, corr100(up_shadow, ts_std20(ts_sum100(mul(div(amplitude, turnover), intraday))))), intraday))))))`
  > 理由: 多层嵌套同源算子且窗口重复，结构冗余难解释，疑似参数拼凑。
- KILL `ts_mean60(mul(mul(mul(div(hl_ratio, low), intraday), intraday), intraday))`
  > 理由: intraday三次自乘且除以low，结构冗余无明确量价经济含义，疑似数学巧合。
- KILL `ts_mean60(mul(mul(mul(abs(mul(div(mul(turnover, ts_min100(corr100(overnight, ts_std20(turnover)))), down_shadow), intraday)), intraday), intraday), intraday))`
  > 理由: 多层同源intraday自乘冗余，结构拼凑，经济含义模糊，疑似参数搜索产物。


**AI 审查(DeepSeek deepseek-v4-flash, 2s)**:

> (1) 病根是intraday被反复堆叠成同构高相关因子，ic虚高但L2全灭，说明信号是噪声拟合而非真实alpha。
> 
> (2) 压intraday权重对症，但交叉+15%和深度加深会加剧过拟合，与min_stab=0.75矛盾；固定扰动/引导/随机比例限制了探索多样性，可能无效；decorr=0.65偏低，无法拆解同质因子。
> 
> (3) mix=[0.2, 0.2, 0.2, 0.2, 0.2] depth=[2,3,3] min_stab=0.85 decorr=0.8。理由：均衡变异与随机打破intraday垄断，浅层降复杂度，高稳定性与去相关强制换血。

## 第 24 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 64 | 0.054 | 0.070 | 0.889 | 0.000 | 0.797 | 0.734 | 0.797 | 30 | 0 | 0.026 | 1.000 | 0.033 | 1.000 | 0.700 | 0.000 |

叶子使用: {'turnover': 51, 'intraday': 47, 'overnight': 39, 'down_shadow': 28, 'up_shadow': 22, 'amplitude': 22}

**B角建议(下一代策略)**:
- 叶子[turnover]占比80%过高 -> 权重压到0.25, 逼引擎换字段
- L2中100%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 本代0通过 -> 深度放宽到3~5, 探索更复杂结构
- 配比护栏: 变异/交叉各≥10%且合计50%重归一化, 扰动/引导/随机固定15/20/15(中金规格) -> mix=[0.1, 0.4, 0.15, 0.2, 0.15]

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 5]  min_stab=0.75  decorr=0.65  fsa_th=0.15  bank_skel_max=1
leaf_w={'volume': 0.25, 'turn_ratio': 0.25, 'turnover': 0.25, 'intraday': 0.25}
```

**LLM 引导(A角 24代)**: 调用3次, 解析通过31条, 引导位使用31条
> 大单资金流与日内波动结构的背离能捕捉机构行为对短期收益的预测力，即大单净买入占比放大伴随低振幅时预示后续上涨，反之预示下跌。


**LLM 候选审查(B角 24代)**: 深判 5 个, KILL 5 个(剔除出 L2 费后回测)
- KILL `ts_mean60(div(mul(mul(abs(ts_min100(corr100(overnight, ts_std20(ts_sum100(mul(div(amplitude, volume), intraday)))))), intraday), intraday), intraday))`
  > 理由: 结构冗余，多层同源算子嵌套，经济含义模糊，疑似参数拼凑。
- KILL `mul(turnover, ts_min100(corr100(overnight, abs(mf_l_buy))))`
  > 理由: 换手率与隔夜跳空及主力买入相关性相乘，机制拼凑且窗口单一，疑似参数巧合。
- KILL `ts_mean60(mul(div(mul(abs(mul(div(intraday, down_shadow), intraday)), intraday), intraday), intraday))`
  > 理由: 表达式为intraday与down_shadow的冗余乘除嵌套，无明确量价经济含义，疑似数学拼凑。
- KILL `mul(cs_rank(turnover), ts_min100(corr100(up_shadow, ts_std20(ts_sum100(mul(div(intraday, turnover), intraday))))))`
  > 理由: 结构冗余嵌套，含义拼凑，疑似参数搜索产物，无清晰经济逻辑。
- KILL `mul(turnover, ts_min100(corr100(overnight, ts_std20(div(corr100(mf_l_sell, ln_volume), turnover)))))`
  > 理由: 多层嵌套相关与比值，结构复杂难解释，疑似参数拼凑无明确经济含义。


**AI 审查(DeepSeek deepseek-v4-flash, 3s)**:

> (1) 病根：L1高IC因子全是turnover×ts_min100(corr100(overnight,…))同构模板，L2换字段即崩，说明信号来自单一换手率维度而非结构发现。
> 
> (2) 规则B角点评：压turnover权重对症但过猛，0.25会直接砍掉当前唯一有效信号源，可能逼出噪声；交叉+15%和深度放宽到3~5方向对，但深度加深与min_stab=0.75冲突，深结构易不稳；decorr=0.65偏低，无法阻止同模板复制；固定扰动/引导比例无助于打破模板惯性。
> 
> (3) 下代建议：mix=[0.15,0.35,0.25,0.15,0.10]，加大扰动比例以打散corr100(overnight,…)固定组合；depth=[2,3,4]避免过深过拟合；min_stab=0.80维持稳健；decorr=0.80强制叶子与结构去重。理由：扰动是唯一能拆解模板内部嵌套的手段，深度收敛配合高decorr才能逼出真正新信号。

## 第 25 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 63 | 0.061 | 0.074 | 0.886 | 0.000 | 1.000 | 0.794 | 1.000 | 30 | 0 | 0.032 | 1.000 | 0.000 | 1.000 | 0.900 | 0.000 |

叶子使用: {'turnover': 63, 'overnight': 55, 'up_shadow': 44, 'intraday': 39, 'ln_volume': 27, 'volume': 16}

**B角建议(下一代策略)**:
- 叶子[turnover]占比100%过高 -> 权重压到0.25, 逼引擎换字段
- L2中100%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 本代0通过 -> 深度放宽到3~5, 探索更复杂结构
- 配比护栏: 变异/交叉各≥10%且合计50%重归一化, 扰动/引导/随机固定15/20/15(中金规格) -> mix=[0.1, 0.4, 0.15, 0.2, 0.15]

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 5]  min_stab=0.75  decorr=0.65  fsa_th=0.15  bank_skel_max=1
leaf_w={'volume': 0.25, 'turn_ratio': 0.25, 'turnover': 0.25, 'intraday': 0.25}
```

**LLM 引导(A角 25代)**: 调用3次, 解析通过48条, 引导位使用48条
> 日内波动结构在连续放量/缩量切换中形成的短期均值回复效应，以及成交活跃度与日内振幅背离所揭示的流动性溢价衰减，能预测未来5日截面收益。


**LLM 候选审查(B角 25代)**: 深判 5 个, KILL 5 个(剔除出 L2 费后回测)
- KILL `mul(turnover, ts_min100(corr100(overnight, div(corr100(up_shadow, ln_volume), turnover))))`
  > 理由: 多层嵌套相关与比值结构复杂难解，疑似参数拼凑，经济含义不明。
- KILL `mul(turnover, ts_min100(corr100(overnight, abs(ln_volume))))`
  > 理由: turnover与量价相关性相乘，含义拼凑，结构冗余，疑似参数搜索。
- KILL `mul(turnover, ts_min100(corr100(overnight, ts_std20(ts_sum100(ts_min100(corr100(overnight, ts_std20(div(corr100(up_shadow, mul(turnover, ts_min100(corr100(up_shadow, ts_std20(ts_sum100(mul(div(corr100(up_shadow, ts_std20(ts_sum20(mul(div(intraday, turnover), intraday)))), turnover), intraday))))))), turnover)))))))))`
  > 理由: 多层嵌套同源算子且重复corr/ts_std/ts_sum结构，参数堆叠冗余，经济含义模糊，疑似过拟合。
- KILL `mul(turnover, ts_min100(corr100(overnight, abs(corr100(down_shadow, ts_std20(ts_sum100(mul(div(intraday, turnover), intraday))))))))`
  > 理由: 结构冗余嵌套，量价含义牵强，疑似参数拼凑。
- KILL `mul(turnover, ts_min100(corr100(up_shadow, ts_std20(ts_sum20(mul(div(intraday, turnover), amplitude))))))`
  > 理由: turnover与intraday/amplitude多层嵌套，结构冗余且经济含义拼凑，疑似参数过拟合。


**AI 审查(DeepSeek deepseek-v4-flash, 2s)**:

> (1) 病根：所有因子都锁死在turnover×overnight的固定模板上，结构高度同质，IC虽高但纯靠换壳，无新信息注入。
> 
> (2) 规则B角建议：压turnover权重对症，但交叉+15%和深度放宽会加剧模板复用，与压字段目标冲突；固定mix中交叉占40%过高，易生成更多同构变体，而扰动/引导占比偏低，难以打破现有结构惯性。
> 
> (3) 下代mix=[0.15, 0.25, 0.25, 0.2, 0.15]，提升变异与扰动比例，强制引入新叶子组合；depth=[2,3,4]浅层优先，避免在错误模板上过度堆叠；min_stab=0.80，decorr=0.70，提高多样性门槛，逼引擎跳出当前局部最优。

## 第 26 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 63 | 0.061 | 0.075 | 0.886 | 0.000 | 1.000 | 0.778 | 1.000 | 30 | 0 | 0.030 | 1.000 | 0.000 | 1.000 | 0.733 | 0.000 |

叶子使用: {'turnover': 63, 'overnight': 62, 'up_shadow': 46, 'intraday': 27, 'amplitude': 23, 'volume': 12}

**B角建议(下一代策略)**:
- 叶子[turnover]占比100%过高 -> 权重压到0.25, 逼引擎换字段
- L2中100%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 本代0通过 -> 深度放宽到3~5, 探索更复杂结构
- 配比护栏: 变异/交叉各≥10%且合计50%重归一化, 扰动/引导/随机固定15/20/15(中金规格) -> mix=[0.1, 0.4, 0.15, 0.2, 0.15]

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 5]  min_stab=0.75  decorr=0.65  fsa_th=0.15  bank_skel_max=1
leaf_w={'volume': 0.25, 'turn_ratio': 0.25, 'turnover': 0.25, 'intraday': 0.25}
```

**LLM 引导(A角 26代)**: 调用3次, 解析通过32条, 引导位使用32条
> 大单资金流与价格波动背离时，市场情绪反转或延续，可通过资金流强度与日内振幅的交互捕捉未来5日收益。


**LLM 候选审查(B角 26代)**: 深判 5 个, KILL 5 个(剔除出 L2 费后回测)
- KILL `mul(turnover, ts_min100(corr100(overnight, ts_std20(div(corr100(up_shadow, corr100(overnight, ts_min100(corr100(up_shadow, ts_std20(ts_sum20(mul(div(intraday, corr100(overnight, ts_std20(turnover))), intraday))))))), turnover)))))`
  > 理由: 多层嵌套同源算子叠加，结构冗余难解释，疑似参数拼凑无增量机制。
- KILL `mul(turnover, ts_min100(corr100(overnight, ts_std20(div(corr100(up_shadow, div(corr100(up_shadow, fa_lev), turnover)), turnover)))))`
  > 理由: 多层嵌套同源corr/div冗余，经济含义模糊，疑似参数拼凑。
- KILL `mul(turnover, ts_min100(corr100(overnight, ts_std20(div(ts_min100(corr100(overnight, ts_std20(div(corr100(up_shadow, intraday), turnover)))), corr100(overnight, ts_std20(div(corr100(up_shadow, intraday), turnover))))))))`
  > 理由: 嵌套同源算子叠加，结构冗余且经济含义模糊，疑似参数拼凑。
- KILL `mul(turnover, ts_min100(corr100(overnight, ts_std20(ts_sum100(mul(div(amplitude, mul(turnover, ts_std20(ts_sum20(mul(div(amplitude, corr100(down_shadow, ts_std20(ts_sum100(mul(div(overnight, turnover), intraday))))), intraday))))), intraday))))))`
  > 理由: 多层嵌套同源量价算子，结构冗余且经济含义模糊，疑似参数拼凑。
- KILL `mul(turnover, ts_min100(corr100(overnight, ts_std20(ts_std20(div(corr100(up_shadow, fa_gm), turnover))))))`
  > 理由: 多层嵌套同源算子且含ts_min100极值，结构冗余难解释，疑似参数过拟合。


**AI 审查(DeepSeek deepseek-v4-flash, 3s)**:

> (1) 病根：L1因子全部以turnover为根且结构同质化，导致L2样本虽稳定但信号弱、Calmar全负，本质是单一叶子主导下的过拟合浅层复制。
> 
> (2) 规则B角建议：压turnover权重对症但0.25过狠，可能破坏现有微弱信号；交叉+15%与深度加深冲突，因当前结构已冗余，加深只会加剧同质化；放宽深度至5方向正确但需配合强制换叶子，否则无效；mix中交叉0.4过高，会放大现有错误模板。
> 
> (3) 下代建议：mix=[0.15, 0.2, 0.2, 0.3, 0.15]，变异主导以打破turnover垄断；depth=[2,3,4]防过度复杂；min_stab=0.80保底；decorr=0.75强制叶子分散。理由：变异+高decorr才能逼出结构多样性，而非靠交叉复制。

## 第 27 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 65 | 0.066 | 0.081 | 0.882 | 0.000 | 1.000 | 0.877 | 1.000 | 30 | 0 | 0.021 | 1.000 | 0.000 | 1.000 | 0.600 | 0.000 |

叶子使用: {'overnight': 65, 'turnover': 65, 'up_shadow': 46, 'amplitude': 34, 'intraday': 30, 'volume': 17}

**B角建议(下一代策略)**:
- 叶子[overnight]占比100%过高 -> 权重压到0.25, 逼引擎换字段
- L2中100%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 本代0通过 -> 深度放宽到3~5, 探索更复杂结构
- 配比护栏: 变异/交叉各≥10%且合计50%重归一化, 扰动/引导/随机固定15/20/15(中金规格) -> mix=[0.1, 0.4, 0.15, 0.2, 0.15]

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 5]  min_stab=0.75  decorr=0.65  fsa_th=0.15  bank_skel_max=1
leaf_w={'volume': 0.25, 'turn_ratio': 0.25, 'turnover': 0.25, 'intraday': 0.25, 'overnight': 0.25}
```

**LLM 引导(A角 27代)**: 调用3次, 解析通过28条, 引导位使用28条
> 交易活跃度变化与日内振幅结构背离，反映市场微观结构中的流动性冲击与价格发现机制，可预测未来5日截面收益。


**LLM 候选审查(B角 27代)**: 深判 5 个, KILL 5 个(剔除出 L2 费后回测)
- KILL `mul(turnover, ts_min100(corr100(overnight, ts_std20(ts_sum100(mul(div(amplitude, mul(turnover, ts_std20(corr100(overnight, abs(ts_std20(div(div(up_shadow, ln_volume), turnover))))))), intraday))))))`
  > 理由: 多层嵌套同源量价算子，结构冗余复杂，经济含义模糊，疑似参数拼凑。
- KILL `mul(turnover, ts_min100(corr100(overnight, ts_std20(ts_sum20(mul(div(amplitude, corr100(down_shadow, ts_std20(ts_rank60(mul(div(overnight, ts_std20(div(corr100(up_shadow, div(amplitude, turnover)), turnover))), intraday))))), intraday))))))`
  > 理由: 多层嵌套同源算子叠加，窗口参数拼凑，结构冗余难解释，疑似过拟合。
- KILL `mul(turnover, ts_min100(corr100(overnight, ts_std20(ts_sum20(mul(div(barra_liquidity, corr100(down_shadow, ts_std20(ts_sum100(mul(div(overnight, ts_std20(div(corr100(up_shadow, div(amplitude, turnover)), turnover))), intraday))))), intraday))))))`
  > 理由: 多层嵌套同源算子叠加，结构冗余复杂，经济含义模糊，疑似参数拼凑。
- KILL `mul(turnover, ts_min100(corr100(overnight, ts_std20(ts_sum100(mul(div(amplitude, mul(turnover, ts_min100(corr100(overnight, abs(ts_std20(div(div(up_shadow, ln_volume), turnover))))))), fa_np_margin))))))`
  > 理由: 多层嵌套同源量价算子，结构冗余且经济含义模糊，疑似参数拼凑。
- KILL `mul(turnover, ts_min100(corr100(overnight, ts_std20(div(corr100(up_shadow, overnight), turnover)))))`
  > 理由: 多层嵌套同源corr/div/ts_std/min，结构冗余难解释，疑似参数拼凑无明确经济含义。


**AI 审查(DeepSeek deepseek-v4-flash, 3s)**:

> (1) 病根: 所有因子都锚定overnight与turnover, 结构高度同质, 导致IC虚高但L2全因Calmar不足而失败, 是典型过拟合于单一信号源。
> 
> (2) 规则B角建议: 压overnight权重对症, 但0.25仍偏高, 建议压至0.1; 交叉+15%可能加剧同质化, 因交叉对象仍是同源叶子; 深度放宽至5会放大过拟合风险, 与min_stab=0.75偏低冲突, 建议min_stab提至0.80; 固定扰动/引导比例合理, 但随机15%过低, 不足以打破结构锁定。
> 
> (3) 下代建议: mix=[0.15, 0.25, 0.15, 0.25, 0.20], 提高随机与引导比例以强制换源; depth=[2,3,4] 限制复杂度; min_stab=0.80 保稳健; decorr=0.80 强去冗余。理由: 当前首要任务是打破叶子垄断, 而非加深结构。

## 第 28 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 65 | 0.066 | 0.077 | 0.883 | 0.000 | 1.000 | 0.723 | 1.000 | 30 | 0 | -0.004 | 1.000 | 0.000 | 1.000 | 0.800 | 0.000 |

叶子使用: {'overnight': 65, 'turnover': 65, 'up_shadow': 57, 'volume': 34, 'amplitude': 14, 'intraday': 12}

**B角建议(下一代策略)**:
- 叶子[overnight]占比100%过高 -> 权重压到0.25, 逼引擎换字段
- L2中100%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 本代0通过 -> 深度放宽到3~5, 探索更复杂结构
- 配比护栏: 变异/交叉各≥10%且合计50%重归一化, 扰动/引导/随机固定15/20/15(中金规格) -> mix=[0.1, 0.4, 0.15, 0.2, 0.15]

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 5]  min_stab=0.75  decorr=0.65  fsa_th=0.15  bank_skel_max=1
leaf_w={'volume': 0.25, 'turn_ratio': 0.25, 'turnover': 0.25, 'intraday': 0.25, 'overnight': 0.25}
```

**LLM 引导(A角 28代)**: 调用3次, 解析通过46条, 引导位使用46条
> 市场对日内波动结构变化的反应滞后：当日内振幅相对历史收缩而隔夜跳空扩大时，短期动量可能反转，预示未来5日收益的负向调整。


**LLM 候选审查(B角 28代)**: 深判 5 个, KILL 5 个(剔除出 L2 费后回测)
- KILL `mul(turnover, ts_min100(corr100(overnight, ts_std20(ts_mean5(div(corr100(up_shadow, mf_s_sell), turnover))))))`
  > 理由: 多层嵌套同源算子，结构冗余难解释，疑似参数拼凑。
- KILL `mul(turnover, ts_min100(corr100(overnight, ts_std20(corr100(overnight, ts_std20(ts_std20(div(corr100(up_shadow, div(corr100(overnight, ts_std20(ts_std20(div(corr60(up_shadow, volume), turnover)))), turnover)), turnover))))))))`
  > 理由: 多层嵌套同源算子叠加，结构冗余难解释，疑似参数拼凑过拟合。
- KILL `mul(turnover, ts_min100(corr100(overnight, ts_std20(corr100(overnight, ts_std20(ts_min100(corr100(overnight, ts_std20(ts_std20(div(corr100(up_shadow, volume), turnover)))))))))))`
  > 理由: 多层嵌套同源算子叠加，结构冗余难解释，疑似参数拼凑过拟合。
- KILL `mul(turnover, ts_min100(corr100(overnight, ts_std20(ts_sum20(mul(div(amplitude, corr100(down_shadow, ts_std20(ts_sum100(ts_min100(corr100(overnight, ts_std20(ts_std20(div(corr100(up_shadow, abs(turnover)), turnover))))))))), intraday))))))`
  > 理由: 多层嵌套同源算子叠加，窗口参数冗余，结构复杂难解释，疑似过拟合拼凑。
- KILL `mul(turnover, ts_min100(corr100(overnight, neg(div(corr100(up_shadow, volume), ts_min100(corr100(overnight, ts_std20(ts_std20(div(corr100(up_shadow, volume), turnover))))))))))`
  > 理由: 嵌套同源corr/div/ts_min/ts_std冗余，含义拼凑，疑似参数海里捞针。


**AI 审查(DeepSeek deepseek-v4-flash, 3s)**:

> (1) 病根：因子结构高度同质化，全部以turnover×ts_min100(corr100(overnight,…))为骨架，仅内层微调，导致IC饱和且L2全灭。  
> (2) 规则B角：压overnight权重对症，但0.25过猛会破坏现有有效相关；交叉+15%与深度加深冲突，因当前失败源于结构单一而非复杂度不足；放宽min_stab至0.75可能引入低稳因子，decorr=0.65对同质化无解。  
> (3) mix=[0.15,0.3,0.2,0.2,0.15]（加大扰动打破骨架，交叉适度）；depth=[3,4]（防过深）；min_stab=0.80；decorr=0.80（强制去重）。理由：需先破同质再谈深化。

## 第 29 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 63 | 0.068 | 0.078 | 0.881 | 0.000 | 1.000 | 0.698 | 1.000 | 30 | 0 | -0.004 | 1.000 | 0.000 | 1.000 | 0.833 | 0.000 |

叶子使用: {'turnover': 63, 'overnight': 63, 'up_shadow': 53, 'intraday': 20, 'amplitude': 16, 'volume': 8}

**B角建议(下一代策略)**:
- 叶子[turnover]占比100%过高 -> 权重压到0.25, 逼引擎换字段
- L2中100%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 本代0通过 -> 深度放宽到3~5, 探索更复杂结构
- 配比护栏: 变异/交叉各≥10%且合计50%重归一化, 扰动/引导/随机固定15/20/15(中金规格) -> mix=[0.1, 0.4, 0.15, 0.2, 0.15]

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 5]  min_stab=0.75  decorr=0.65  fsa_th=0.15  bank_skel_max=1
leaf_w={'volume': 0.25, 'turn_ratio': 0.25, 'turnover': 0.25, 'intraday': 0.25, 'overnight': 0.25}
```

**LLM 引导(A角 29代)**: 调用3次, 解析通过36条, 引导位使用36条
> 基于日内振幅与成交量的同步扩张或背离，捕捉机构大单入场引发的流动性冲击与价格持续性，同时结合隔夜跳空与日内反转的交互效应，预测未来5日截面收益。


**LLM 候选审查(B角 29代)**: 深判 5 个, KILL 5 个(剔除出 L2 费后回测)
- KILL `mul(turnover, ts_min100(corr100(overnight, ts_min20(ts_std20(div(corr100(up_shadow, div(amplitude, overnight)), turnover))))))`
  > 理由: 多层嵌套同源算子，结构冗余难解释，疑似参数拼凑无明确经济含义。
- KILL `mul(turnover, ts_min100(corr100(overnight, ts_std20(ts_std20(div(ts_min100(corr100(ret, ts_std20(div(corr100(overnight, intraday), turnover)))), turnover))))))`
  > 理由: 多层嵌套同源算子叠加，结构冗余复杂，经济含义模糊，疑似参数海里捞针。
- KILL `mul(turnover, ts_min100(corr100(overnight, ts_std20(div(intraday, div(corr100(up_shadow, intraday), turnover))))))`
  > 理由: 结构嵌套冗余，含义拼凑，疑似参数挖掘，无清晰经济逻辑。
- KILL `mul(turnover, ts_min100(corr100(overnight, ts_std20(ts_std20(div(corr100(ts_std20(ts_std20(div(corr100(up_shadow, div(amplitude, overnight)), turnover))), div(amplitude, overnight)), turnover))))))`
  > 理由: 多层嵌套同源算子且窗口单一，结构冗余难解释，疑似参数拼凑。
- KILL `mul(turnover, ts_min100(corr100(overnight, ts_std20(div(ts_min100(corr100(overnight, turnover)), div(corr100(up_shadow, intraday), turnover))))))`
  > 理由: 多层嵌套同源corr/min/std，结构冗余难解释，疑似参数拼凑无清晰经济含义。


**AI 审查(DeepSeek deepseek-v4-flash, 3s)**:

> (1) 病根：所有L1/L2因子均为turnover×overnight的同一模板嵌套，结构单一且信号被ts_min100过度平滑，导致样本外Calmar全面转负。
> 
> (2) 规则B角建议：压turnover权重对症，但交叉+15%和深度放宽至5可能加剧过拟合，因当前问题不是复杂度不足而是模板固化；固定扰动/引导比例合理，但min_stab=0.75过低，会放行更多同质噪声因子。
> 
> (3) 下代建议：mix=[0.15, 0.25, 0.2, 0.25, 0.15]，提高变异和引导以打破模板，降低交叉防过拟合；depth=[2,3,4]限制深度；min_stab=0.80；decorr=0.70。理由：需强制字段多样性而非结构复杂度。

## 第 30 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 65 | 0.069 | 0.080 | 0.865 | 0.000 | 1.000 | 0.569 | 1.000 | 30 | 0 | -0.004 | 1.000 | 0.000 | 1.000 | 0.700 | 0.000 |

叶子使用: {'overnight': 65, 'turnover': 65, 'up_shadow': 51, 'volume': 12, 'fa_roe': 12, 'intraday': 12}

**B角建议(下一代策略)**:
- 叶子[overnight]占比100%过高 -> 权重压到0.25, 逼引擎换字段
- L2中100%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 本代0通过 -> 深度放宽到3~5, 探索更复杂结构
- 配比护栏: 变异/交叉各≥10%且合计50%重归一化, 扰动/引导/随机固定15/20/15(中金规格) -> mix=[0.1, 0.4, 0.15, 0.2, 0.15]

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 5]  min_stab=0.75  decorr=0.65  fsa_th=0.15  bank_skel_max=1
leaf_w={'volume': 0.25, 'turn_ratio': 0.25, 'turnover': 0.25, 'intraday': 0.25, 'overnight': 0.25}
```

**LLM 引导(A角 30代)**: 调用3次, 解析通过39条, 引导位使用39条
> 日内价格位置与隔夜跳空交互形成的短期惯性/反转结构，以及量价背离在5日截面上的预测能力。


**LLM 候选审查(B角 30代)**: 深判 5 个, KILL 5 个(剔除出 L2 费后回测)
- KILL `mul(turnover, ts_min100(corr100(overnight, ts_std20(div(turnover, div(ts_min100(corr100(overnight, ts_delta20(div(corr100(up_shadow, div(fa_roe, overnight)), turnover)))), turnover))))))`
  > 理由: 多层嵌套同源算子且混入基本面字段，结构冗余难解释，疑似参数拼凑。
- KILL `mul(turnover, ts_min100(corr100(overnight, ts_std20(div(ts_min100(corr100(overnight, overnight)), div(corr100(up_shadow, mf_m_sell), turnover))))))`
  > 理由: 嵌套同源corr/min/div冗余，结构拼凑无清晰量价含义，疑似参数过拟合。
- KILL `mul(turnover, ts_min100(corr100(overnight, ts_std20(ts_std20(div(ts_min100(corr100(overnight, ts_std20(corr20(intraday, turnover)))), turnover))))))`
  > 理由: 多层嵌套同源算子且窗口重复，结构冗余，经济含义模糊，疑似参数拼凑。
- KILL `mul(turnover, ts_min100(corr100(overnight, ts_std20(ts_std20(div(ts_min100(corr100(overnight, ts_std20(div(corr100(overnight, intraday), intraday)))), turnover))))))`
  > 理由: 结构冗余嵌套同源算子，经济含义模糊，疑似参数拼凑。
- KILL `mul(turnover, ts_min100(corr100(overnight, ts_std60(div(corr100(up_shadow, corr100(overnight, ts_min100(barra_momentum))), div(corr100(up_shadow, overnight), turnover))))))`
  > 理由: 多层同源corr嵌套且除以turnover再乘回，结构冗余无清晰经济含义，疑似参数拼凑。


**AI 审查(DeepSeek deepseek-v4-flash, 3s)**:

> (1) 病根: 所有L1与L2共享同一骨架“mul(turnover, ts_min100(corr100(overnight,...)))”, 结构同质化导致IC封顶, 且因子本质是换手率与隔夜收益的静态比值, 缺乏动态信息。
> 
> (2) 规则B角建议: 压overnight权重对症但过猛, 恐致搜索空间突变; 交叉+15%与深度加深会加剧同骨架变异, 无效; 深度放宽至5可能继续堆叠ts_min100, 增加过拟合风险; 整体mix偏保守, 未针对“结构同质化”这一核心。
> 
> (3) 下代建议: mix=[0.25, 0.25, 0.2, 0.2, 0.1], depth=[2,3,4], min_stab=0.8, decorr=0.7。理由: 提高变异与扰动比例以打破骨架锁定, 降低深度避免无意义堆叠, 提高decorr强制结构多样性。

## 第 31 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 27 | 0.058 | 0.079 | 0.879 | 0.000 | 0.815 | 1.000 | 38 | 0.852 | 27 | 1 | 0.053 | 1.000 | 0.500 | 1.000 | 0.577 | 0.000 |

叶子使用: {'turnover': 22, 'overnight': 19, 'up_shadow': 17, 'fa_roe': 9, 'volume': 6, 'intraday': 5}

**B角建议(下一代策略)**:
- 叶子[turnover]占比81%过高 -> 权重压到0.25, 逼引擎换字段
- L2中50%因换手过高失败 -> min_stab再+0.10
- L2中100%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 配比护栏: 变异/交叉各≥10%且合计50%重归一化, 扰动/引导/随机固定15/20/15(中金规格) -> mix=[0.1, 0.4, 0.15, 0.2, 0.15]

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 4]  min_stab=0.75  decorr=0.65  fsa_th=0.15  bank_skel_max=1
leaf_w={'volume': 0.25, 'turn_ratio': 0.25, 'turnover': 0.25, 'intraday': 0.25, 'overnight': 0.25}
```

**LLM 引导(A角 31代)**: 调用3次, 解析通过35条, 引导位使用35条
> 大单资金流向与价格动量背离，结合换手率波动结构，预示短期收益反转。


**LLM 候选审查(B角 31代)**: 深判 5 个, KILL 5 个(剔除出 L2 费后回测)
- KILL `mul(mul(turnover, ts_min100(corr100(overnight, ts_std20(div(log(corr100(overnight, turnover)), ts_delta20(div(corr100(up_shadow, div(fa_roe, turnover)), turnover))))))), ts_min100(corr100(overnight, ts_std20(div(log(corr100(overnight, turnover)), ts_delta20(div(corr100(up_shadow, div(fa_roe, turnover)), turnover)))))))`
  > 理由: 结构冗余嵌套同源corr/div，叠加ts_min/ts_std/ts_delta，参数拼凑无清晰量价机制，疑似过拟合。
- KILL `mul(turnover, cs_rank(corr100(overnight, ts_std20(div(turnover, div(ts_min100(corr100(overnight, ts_std20(div(corr100(up_shadow, abs(turnover)), turnover)))), turnover))))))`
  > 理由: 多层嵌套同源turnover与corr，结构冗余难解释，疑似参数拼凑无增量经济含义。
- KILL `mul(turnover, ts_min100(corr100(overnight, turnover)))`
  > 理由: turnover自乘及与overnight相关，冗余且含义拼凑，疑似换手率老故事。
- KILL `mul(corr100(intraday, ts_mean5(volume)), ts_min100(corr100(overnight, ts_std20(div(turnover, div(ts_min100(corr100(overnight, ts_delta20(div(corr100(up_shadow, div(fa_roe, turnover)), turnover)))), turnover))))))`
  > 理由: 多层嵌套同源corr/div且含财务字段，结构拼凑无清晰量价含义，疑似过拟合。
- KILL `mul(turnover, ts_min100(ts_min100(corr100(overnight, ts_std20(corr100(overnight, ts_std20(div(turnover, div(corr100(up_shadow, turn_ratio), turnover)))))))))`
  > 理由: 嵌套冗余且含义拼凑，窗口重复100，疑似参数过拟合，无清晰经济逻辑。


**AI 审查(DeepSeek deepseek-v4-flash, 3s)**:

> (1) 病根: 因子结构高度同质化, 全部围绕turnover与overnight的嵌套相关, 本质是同一逻辑的重复堆叠, 导致L2集体换手过高且信号衰减。
> 
> (2) 规则B角建议: 压turnover权重对症, 但min_stab+0.10与现有0.85以上候选冲突, 可能误杀; 交叉+15%方向对, 但深度加深会加剧过拟合, 与min_stab上调互相矛盾; 固定变异0.1偏低, 难以突破同质化。
> 
> (3) 下代建议: mix=[0.25, 0.3, 0.15, 0.2, 0.1], 提高变异以引入新叶子组合; depth=[3, 3, 4] 控制复杂度; min_stab=0.70 保留低稳但结构新颖的候选; decorr=0.70 强制去重。理由: 当前核心是结构多样性不足, 而非稳定性或深度问题。

## 第 32 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 27 | 0.058 | 0.072 | 0.885 | 0.000 | 0.815 | 1.000 | 37 | 0.889 | 27 | 0 | 0.053 | 1.000 | 0.370 | 0.963 | 0.630 | 0.000 |

叶子使用: {'turnover': 22, 'up_shadow': 19, 'overnight': 18, 'mf_x_bqty': 8, 'fa_roe': 5, 'turn_ratio': 3}

**B角建议(下一代策略)**:
- 叶子[turnover]占比81%过高 -> 权重压到0.25, 逼引擎换字段
- L2中100%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 本代0通过 -> 深度放宽到3~5, 探索更复杂结构
- 配比护栏: 变异/交叉各≥10%且合计50%重归一化, 扰动/引导/随机固定15/20/15(中金规格) -> mix=[0.1, 0.4, 0.15, 0.2, 0.15]

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 5]  min_stab=0.75  decorr=0.65  fsa_th=0.15  bank_skel_max=1
leaf_w={'volume': 0.25, 'turn_ratio': 0.25, 'turnover': 0.25, 'intraday': 0.25, 'overnight': 0.25}
```

**LLM 引导(A角 32代)**: 调用3次, 解析通过43条, 引导位使用43条
> 中小单与超大单资金流向的持续背离，以及日内振幅与成交活跃度的缩量收敛，预示未来5日截面收益的均值回复。


**LLM 候选审查(B角 32代)**: 深判 5 个, KILL 5 个(剔除出 L2 费后回测)
- KILL `mul(volume, ts_min100(corr100(overnight, ts_std20(div(turnover, div(ts_min100(corr100(overnight, ts_delta20(div(corr100(up_shadow, div(fa_roe, up_shadow)), turnover)))), turnover))))))`
  > 理由: 多层嵌套同源算子叠加，结构冗余难解释，疑似参数拼凑。
- KILL `div(turnover, ts_min100(corr100(overnight, ts_std20(div(turnover, div(corr100(up_shadow, ts_delta20(div(corr100(up_shadow, div(fa_roe, mf_s_buy)), turnover))), turnover))))))`
  > 理由: 多层嵌套同源corr/div/ts_delta，结构拼凑无清晰量价经济含义，疑似过拟合。
- KILL `div(turnover, ts_min100(corr100(overnight, ts_std20(div(turnover, div(corr100(up_shadow, mf_x_bqty), turnover))))))`
  > 理由: 多层嵌套同源换手率与影子价相关，结构冗余且经济含义牵强，疑似参数拼凑。
- KILL `mul(turnover, ts_min100(div(overnight, ts_std200(div(turnover, div(ts_min100(corr100(overnight, ts_delta20(div(corr100(up_shadow, div(fa_roe, mf_s_buy)), turnover)))), turnover))))))`
  > 理由: 多层嵌套同源算子叠加，窗口参数堆砌，结构冗余难解释，疑似参数过拟合。
- KILL `mul(turnover, ts_min100(corr100(div(fa_roe, up_shadow), ts_std20(corr100(overnight, ts_std20(div(turnover, div(corr100(up_shadow, turnover), turnover))))))))`
  > 理由: 结构拼凑财务与量价，嵌套冗余无经济含义，疑似参数过拟合


**AI 审查(DeepSeek deepseek-v4-flash, 3s)**:

> (1) 病根：因子结构高度同质化，全部围绕turnover与overnight的嵌套相关，本质是同一信号的不同包装，导致IC虚高但Calmar全负。
> 
> (2) 规则B角建议点评：压turnover权重对症，但0.25可能过狠，会切断现有有效信号；交叉+15%与深度放宽至5可能加剧过拟合，因为当前失败主因是信号方向错误而非复杂度不足；固定扰动/引导比例缺乏自适应，可能浪费算力在无效空间。
> 
> (3) 下代建议：mix=[0.15, 0.3, 0.2, 0.2, 0.15]，提高变异与引导比例以强制探索新字段组合；depth=[2,3,4]限制深度防过拟合；min_stab=0.80要求更高稳定性；decorr=0.70加强去重。理由：当前需广度突破而非深度挖掘，需用变异和引导跳出turnover陷阱。

## 第 33 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 17 | 0.059 | 0.077 | 0.885 | 0.000 | 0.824 | 0.941 | 47 | 0.882 | 17 | 1 | 0.147 | 1.000 | 0.312 | 1.000 | 0.688 | 0.000 |

叶子使用: {'turnover': 14, 'overnight': 14, 'up_shadow': 11, 'turn_ratio': 5, 'amplitude': 5, 'barra_residual_volatility': 3}

**B角建议(下一代策略)**:
- 叶子[turnover]占比82%过高 -> 权重压到0.25, 逼引擎换字段
- L2中100%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 配比护栏: 变异/交叉各≥10%且合计50%重归一化, 扰动/引导/随机固定15/20/15(中金规格) -> mix=[0.1, 0.4, 0.15, 0.2, 0.15]

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 4]  min_stab=0.75  decorr=0.65  fsa_th=0.15  bank_skel_max=1
leaf_w={'volume': 0.25, 'turn_ratio': 0.25, 'turnover': 0.25, 'intraday': 0.25, 'overnight': 0.25}
```

**LLM 引导(A角 33代)**: 调用3次, 解析通过43条, 引导位使用43条
> 中小单与大单资金流向背离及量价不匹配揭示主力与散户行为差异，结合日内/隔夜收益结构捕捉短期价格修正与动量延续。


**LLM 候选审查(B角 33代)**: 深判 5 个, KILL 5 个(剔除出 L2 费后回测)
- KILL `mul(turnover, ts_std20(corr100(overnight, ts_std20(div(corr100(up_shadow, turnover), div(corr100(overnight, cs_rank(volume)), turnover))))))`
  > 理由: 多层嵌套corr/div/std叠加，结构冗余难解释，疑似参数拼凑无明确量价经济含义。
- KILL `mul(abs(mf_m_buy), ts_min100(corr100(overnight, ts_std20(div(turnover, div(ts_min100(corr100(overnight, ts_delta20(div(corr100(up_shadow, mul(fa_roe, up_shadow)), turnover)))), turnover))))))`
  > 理由: 多层嵌套同源相关与窗口冗余，经济含义模糊，疑似参数拼凑。
- KILL `mul(ts_mean5(turnover), ts_min100(corr100(overnight, amplitude)))`
  > 理由: 换手率均值与隔夜振幅相关性最小值相乘，机制牵强且窗口冗余，疑似参数拼凑。
- KILL `mul(div(ts_min100(turnover), turnover), ts_min100(corr100(overnight, ts_std20(div(turnover, div(corr100(up_shadow, turnover), turnover))))))`
  > 理由: 结构冗余嵌套，经济含义模糊，疑似参数拼凑过拟合。
- KILL `div(ts_min100(corr100(overnight, ts_std20(div(up_shadow, corr100(overnight, ts_std20(corr100(overnight, ts_std20(div(turnover, div(corr100(up_shadow, turn_ratio), turnover)))))))))), turnover)`
  > 理由: 嵌套同源corr/div/ts_std多层冗余，结构拼凑无清晰经济含义，疑似参数过拟合。


**AI 审查(DeepSeek deepseek-v4-flash, 3s)**:

> (1) 病根是L1高IC靠ts_min100/corr100长窗口堆叠，L2却全部Calmar为负，说明信号在样本外时序上失效，纯过拟合。  
> (2) 压turnover权重对症，但0.25过猛，可能把已发现的稳定结构全打散；交叉+15%方向对，但depth加深到4会加剧过拟合，与min_stab=0.75偏低冲突，decorr=0.65也偏松，易放行同质因子。  
> (3) mix=[0.15, 0.3, 0.15, 0.25, 0.15]，depth=[3,3,3]，min_stab=0.85，decorr=0.8。理由：降深度保稳定，提扰动换结构，紧decorr防重复。

## 第 34 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 21 | 0.061 | 0.075 | 0.870 | 0.000 | 0.810 | 1.000 | 42 | 0.905 | 21 | 0 | 0.032 | 1.000 | 0.476 | 1.000 | 0.619 | 0.000 | 0.714 |

叶子使用: {'overnight': 17, 'turnover': 16, 'up_shadow': 13, 'barra_residual_volatility': 10, 'amplitude': 7, 'volume': 4}

**B角建议(下一代策略)**:
- 叶子[overnight]占比81%过高 -> 权重压到0.25, 逼引擎换字段
- L2中48%因换手过高失败 -> min_stab再+0.10
- L2中100%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 本代0通过 -> 深度放宽到3~5, 探索更复杂结构
- 配比护栏: 变异/交叉各≥10%且合计50%重归一化, 扰动/引导/随机固定15/20/15(中金规格) -> mix=[0.1, 0.4, 0.15, 0.2, 0.15]

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 5]  min_stab=0.75  decorr=0.65  fsa_th=0.15  bank_skel_max=1
leaf_w={'volume': 0.25, 'turn_ratio': 0.25, 'turnover': 0.25, 'intraday': 0.25, 'overnight': 0.25}
```

**LLM 引导(A角 34代)**: 调用3次, 解析通过40条, 引导位使用40条
> 市场对隔夜跳空与日内波动的交互反应存在持续性，短期内高振幅伴随跳空扩大的股票可能吸引资金关注，未来5日收益延续；同时资金流大单与中小单背离预示筹码换手压力，未来收益反转。


**LLM 候选审查(B角 34代)**: 深判 5 个, KILL 5 个(剔除出 L2 费后回测)
- KILL `mul(turnover, ts_min100(corr100(div(overnight, up_shadow), ts_std20(corr100(overnight, ts_std20(corr100(overnight, ts_std20(div(corr100(up_shadow, corr100(overnight, ts_min100(overnight))), div(corr100(overnight, ts_mean10(volume)), turnover))))))))))`
  > 理由: 多层嵌套同源corr/ts_std/ts_min叠加，参数堆砌无清晰经济含义，疑似过拟合拼凑。
- KILL `mul(turnover, log(corr100(overnight, div(max(up_shadow, turn_ratio), div(up_shadow, turnover)))))`
  > 理由: 结构拼凑，量价含义混杂，嵌套冗余，疑似参数搜索产物。
- KILL `mul(turnover, ts_min100(corr100(div(barra_liquidity, up_shadow), ts_std20(corr100(overnight, ts_std20(div(turnover, div(ts_min100(corr100(overnight, ts_delta20(div(corr100(up_shadow, div(mf_s_sell, up_shadow)), turnover)))), turnover))))))))`
  > 理由: 多层嵌套同源算子叠加，结构冗余难解释，疑似参数海中捞针。
- KILL `max(barra_residual_volatility, corr20(ln_mktcap, amplitude))`
  > 理由: 市值与振幅相关性无明确量价机制，与残差波动取max拼凑，含义牵强。
- KILL `mul(turnover, ts_min100(corr100(overnight, mf_s_sell)))`
  > 理由: turnover与量价相关因子相乘，结构拼凑，经济含义不明，疑似参数冗余。


**AI 审查(DeepSeek deepseek-v4-flash, 3s)**:

> (1) 病根是过度依赖overnight单一信号源，导致结构趋同、换手过高，而信号本身缺乏增量。
> 
> (2) 压overnight权重对症，但0.25过狠可能引发字段断层；min_stab+0.10与深度放宽互相矛盾，深结构易过拟合反而降稳定；交叉+15%方向对，但未解决换手根源；深度3~5与min_stab=0.75冲突，建议保留浅层。
> 
> (3) mix=[0.15, 0.35, 0.15, 0.2, 0.15]，depth=[2,3,4]，min_stab=0.80，decorr=0.70。理由：适度交叉探索新组合，浅层保稳定，提高去相关强制换叶子。

## 第 35 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 16 | 0.067 | 0.077 | 0.870 | 0.000 | 0.938 | 1.000 | 49 | 1.000 | 16 | 0 | 0.016 | 1.000 | 0.250 | 1.000 | 0.688 | 0.000 | 0.750 |

叶子使用: {'turnover': 15, 'overnight': 15, 'up_shadow': 11, 'barra_residual_volatility': 6, 'ln_volume': 4, 'ln_mktcap': 3}

**B角建议(下一代策略)**:
- 叶子[turnover]占比94%过高 -> 权重压到0.25, 逼引擎换字段
- L2中100%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 本代0通过 -> 深度放宽到3~5, 探索更复杂结构
- 配比护栏: 变异/交叉各≥10%且合计50%重归一化, 扰动/引导/随机固定15/20/15(中金规格) -> mix=[0.1, 0.4, 0.15, 0.2, 0.15]

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 5]  min_stab=0.75  decorr=0.65  fsa_th=0.15  bank_skel_max=1
leaf_w={'volume': 0.25, 'turn_ratio': 0.25, 'turnover': 0.25, 'intraday': 0.25, 'overnight': 0.25}
```

**LLM 引导(A角 35代)**: 调用3次, 解析通过42条, 引导位使用42条
> 日内与隔夜波动结构中的持续性反转，以及量价配合的背离，能够预测未来5日截面收益。


**LLM 候选审查(B角 35代)**: 深判 5 个, KILL 5 个(剔除出 L2 费后回测)
- KILL `mul(div(ts_min100(corr100(overnight, overnight)), turnover), ts_min100(corr100(overnight, ts_std20(div(barra_residual_volatility, div(corr100(up_shadow, barra_size), turnover))))))`
  > 理由: 结构冗余嵌套，overnight自相关及多重同源corr/div叠加，疑似参数拼凑，经济含义模糊。
- KILL `mul(turnover, log(corr100(overnight, div(corr20(amplitude, ln_volume), div(up_shadow, turnover)))))`
  > 理由: 结构拼凑，量价含义混杂，嵌套冗余，疑似参数搜索产物。
- KILL `mul(turnover, ts_min100(max(overnight, div(min(up_shadow, corr100(overnight, ts_std20(div(turnover, div(corr100(up_shadow, barra_residual_volatility), turnover))))), turnover))))`
  > 理由: 多层嵌套同源量价算子，结构冗余难解释，疑似参数拼凑过拟合。
- KILL `mul(turnover, log(corr100(overnight, div(corr100(mf_m_buy, turn_ratio), div(up_shadow, turnover)))))`
  > 理由: 多层嵌套corr/div/log，结构拼凑无明确量价行为，过拟合风险高。
- KILL `mul(add(ts_min100(turnover), turnover), ts_min100(corr100(overnight, ts_std20(div(turnover, div(corr100(up_shadow, volume), turnover))))))`
  > 理由: 结构拼凑，量价含义不明，嵌套冗余，疑似参数过拟合


**AI 审查(DeepSeek deepseek-v4-flash, 3s)**:

> (1) 病根：因子结构高度雷同，全部围绕turnover与overnight的ts_min100/corr100嵌套，IC虽高但L2全灭，说明过拟合于历史噪声而非稳健信号。
> 
> (2) 规则B角建议：压turnover权重对症，但压到0.25过猛，可能直接砍掉唯一有效信号源；交叉+15%与深度放宽至5会加剧结构同质化，与decorr=0.65冲突；固定扰动/引导比例无助于打破当前模板，随机15%不足以引入新字段。
> 
> (3) 下代建议：mix=[0.15, 0.3, 0.2, 0.25, 0.1]，加大扰动与引导以强制换字段；depth=[2,3,4]防过度嵌套；min_stab=0.80提升稳健门槛；decorr=0.75强制结构分化。理由：当前问题不是复杂度不足，而是模板固化，需外力打破。

## 第 36 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 11 | 0.065 | 0.072 | 0.864 | 0.000 | 1.000 | 0.909 | 52 | 1.000 | 11 | 0 | -0.008 | 1.000 | 0.091 | 1.000 | 0.727 | 0.000 | 1.000 |

叶子使用: {'turnover': 11, 'overnight': 11, 'up_shadow': 7, 'barra_residual_volatility': 4, 'mf_m_buy': 3, 'mf_l_buy': 2}

**B角建议(下一代策略)**:
- 叶子[turnover]占比100%过高 -> 权重压到0.25, 逼引擎换字段
- L2中100%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 本代0通过 -> 深度放宽到3~5, 探索更复杂结构
- 配比护栏: 变异/交叉各≥10%且合计50%重归一化, 扰动/引导/随机固定15/20/15(中金规格) -> mix=[0.1, 0.4, 0.15, 0.2, 0.15]

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 5]  min_stab=0.75  decorr=0.65  fsa_th=0.15  bank_skel_max=1
leaf_w={'volume': 0.25, 'turn_ratio': 0.25, 'turnover': 0.25, 'intraday': 0.25, 'overnight': 0.25}
```

**LLM 引导(A角 36代)**: 调用3次, 解析通过38条, 引导位使用38条
> 超大单主动买入金额的短期动量与价格日内波动结构背离时，预示大资金吸筹后价格将上行，而中小单主导的放量滞涨则预示回调。


**LLM 候选审查(B角 36代)**: 深判 5 个, KILL 5 个(剔除出 L2 费后回测)
- KILL `mul(turnover, ts_min100(corr100(overnight, ts_std20(corr100(overnight, ts_std20(div(turnover, div(corr100(overnight, div(corr100(add(barra_residual_volatility, barra_non_linear_size), turn_ratio), div(up_shadow, amplitude))), turnover))))))))`
  > 理由: 多层嵌套corr/div与barra因子拼凑，结构冗余难解释，疑似参数过拟合。
- KILL `mul(add(ts_mean20(turnover), turnover), ts_min100(corr100(overnight, ts_std20(div(turnover, div(corr100(up_shadow, turnover), turnover))))))`
  > 理由: 结构冗余嵌套，经济含义模糊，疑似参数拼凑，无清晰量价逻辑。
- KILL `mul(div(ts_min100(corr100(overnight, ts_std20(div(corr100(up_shadow, turnover), turnover)))), turnover), ts_min100(mf_m_buy))`
  > 理由: 结构拼凑多源量价，嵌套冗余，窗口参数海捞，经济含义模糊难解释。
- KILL `mul(turnover, ts_std20(corr100(overnight, ts_std20(div(turnover, div(ts_min100(corr100(overnight, ts_delta20(mf_l_buy))), turnover))))))`
  > 理由: 多层嵌套同源算子且窗口参数冗余，结构复杂难解释，疑似参数拼凑。
- KILL `mul(add(cs_rank(turnover), turnover), ts_min100(corr100(overnight, ts_std20(div(turnover, div(corr100(up_shadow, overnight), turnover))))))`
  > 理由: turnover重复嵌套且与自身比率相关，结构冗余拼凑，经济含义模糊。


**AI 审查(DeepSeek deepseek-v4-flash, 3s)**:

> (1) 病根：所有L1候选共享同一核心结构——turnover与overnight的corr嵌套，导致L2全部因信号同质化而Calmar不足，属结构性过拟合而非参数问题。
> 
> (2) 规则B角建议点评：压turnover权重对症但力度不足，因11个叶子全含turnover，0.25仍难破同构；交叉+15%和深度放宽可能加剧同质化，因交叉对象仍是同源结构；min_stab降至0.75风险大，本代stab已0.86仍全败，放宽只会引入更多伪稳定因子。
> 
> (3) 下代建议：mix=[0.35,0.2,0.15,0.2,0.1]，变异为主强制引入新字段组合；depth=[2,3,4]防过度嵌套；min_stab=0.85守住稳定性底线；decorr=0.8强制结构去重。理由：先破同构再谈深度，稳定性是唯一可信指标。

## 第 37 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 10 | 0.066 | 0.072 | 0.876 | 0.000 | 1.000 | 1.000 | 50 | 1.000 | 10 | 0 | 0.005 | 1.000 | 0.000 | 1.000 | 0.900 | 0.000 | 0.900 |

叶子使用: {'overnight': 10, 'turnover': 10, 'up_shadow': 8, 'down_shadow': 4, 'barra_residual_volatility': 3, 'mf_s_sell': 3}

**B角建议(下一代策略)**:
- 叶子[overnight]占比100%过高 -> 权重压到0.25, 逼引擎换字段
- L2中100%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 本代0通过 -> 深度放宽到3~5, 探索更复杂结构
- 配比护栏: 变异/交叉各≥10%且合计50%重归一化, 扰动/引导/随机固定15/20/15(中金规格) -> mix=[0.1, 0.4, 0.15, 0.2, 0.15]

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 5]  min_stab=0.75  decorr=0.65  fsa_th=0.15  bank_skel_max=1
leaf_w={'volume': 0.25, 'turn_ratio': 0.25, 'turnover': 0.25, 'intraday': 0.25, 'overnight': 0.25}
```

**LLM 引导(A角 37代)**: 调用3次, 解析通过37条, 引导位使用37条
> 大单资金主动买卖失衡与日内波动结构交互，预示短期动量延续或反转


**LLM 候选审查(B角 37代)**: 深判 5 个, KILL 5 个(剔除出 L2 费后回测)
- KILL `mul(turnover, ts_min100(max(overnight, div(corr100(up_shadow, corr100(overnight, ts_std100(div(turnover, div(corr100(mul(turnover, ts_min100(corr100(overnight, ts_std20(div(turnover, div(corr100(overnight, volume), turnover)))))), barra_residual_volatility), turnover))))), turnover))))`
  > 理由: 多层嵌套同源算子且参数冗余，结构复杂难解释，疑似参数过拟合。
- KILL `mul(abs(mf_s_sell), ts_min100(corr100(div(sub(up_shadow, barra_residual_volatility), turnover), ts_std20(div(overnight, div(ts_min100(corr100(overnight, ts_delta20(div(corr100(up_shadow, div(mf_s_sell, up_shadow)), turnover)))), turnover))))))`
  > 理由: 多层嵌套同源量价算子，结构冗余难解释，疑似参数拼凑无清晰经济含义。
- KILL `mul(abs(mf_s_sell), ts_min100(corr100(overnight, ts_std60(div(overnight, div(ts_min100(corr100(overnight, ts_delta20(div(corr100(up_shadow, div(mf_s_sell, up_shadow)), turnover)))), turnover))))))`
  > 理由: 结构高度嵌套冗余，含义拼凑，疑似参数海中捞针，无清晰经济逻辑。
- KILL `ts_delay1(add(barra_residual_volatility, mul(turnover, ts_min100(corr100(overnight, ts_std20(div(turnover, div(corr100(corr100(fa_lev, barra_residual_volatility), overnight), turnover))))))))`
  > 理由: 结构嵌套冗余，含义拼凑，疑似参数过拟合，无清晰经济逻辑。
- KILL `mul(turnover, ts_min100(corr100(overnight, mf_s_sell)))`
  > 理由: 换手率与隔夜跳空及主力卖出相关性相乘，机制牵强，疑似参数拼凑。


**AI 审查(DeepSeek deepseek-v4-flash, 3s)**:

> (1) 病根: 因子结构高度同质化, 所有头部候选共享同一核心模板, 仅末端微调, 导致IC饱和但样本外Calmar全面为负, 属于过拟合单一模式而非信号不足。
> 
> (2) 规则B角建议点评: 压overnight权重对症, 但仅压到0.25仍可能残留主导性, 建议压至0.1以下; 交叉+15%和深度加深方向正确, 但深度3~5与当前深度已超20矛盾, 实际是需缩短而非加深; 固定扰动/引导比例可能阻碍跳出局部最优, 建议提高随机占比。
> 
> (3) 下代参数: mix=[0.15, 0.3, 0.2, 0.15, 0.2], depth=[2,3,4], min_stab=0.70, decorr=0.80。理由: 降低深度强制简化结构, 提高随机和扰动打破模板依赖, 提高decorr强制多样性。

## 第 38 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 27 | 0.043 | 0.073 | 0.917 | 0.000 | 0.556 | 1.000 | 37 | 0.519 | 27 | 0 | 0.063 | 1.000 | 0.111 | 0.889 | 0.519 | 0.000 | 0.630 |

叶子使用: {'overnight': 15, 'turnover': 14, 'up_shadow': 8, 'barra_residual_volatility': 5, 'mf_l_buy': 4, 'mf_m_buy': 3}

**B角建议(下一代策略)**:
- 叶子[overnight]占比56%过高 -> 权重压到0.25, 逼引擎换字段
- L2中100%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 本代0通过 -> 深度放宽到3~5, 探索更复杂结构
- 配比护栏: 变异/交叉各≥10%且合计50%重归一化, 扰动/引导/随机固定15/20/15(中金规格) -> mix=[0.1, 0.4, 0.15, 0.2, 0.15]

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 5]  min_stab=0.75  decorr=0.65  fsa_th=0.15  bank_skel_max=1
leaf_w={'volume': 0.25, 'turn_ratio': 0.25, 'turnover': 0.25, 'intraday': 0.25, 'overnight': 0.25}
```

**LLM 引导(A角 38代)**: 调用3次, 解析通过35条, 引导位使用35条
> 日内高低点振幅与短期波动的比值变化反映市场情绪与流动性切换，可用于预测短期收益反转。


**LLM 候选审查(B角 38代)**: 深判 5 个, KILL 4 个(剔除出 L2 费后回测)
- KILL `mul(ts_mean10(mf_m_buy), ts_min100(corr100(overnight, ts_std20(div(turnover, div(ts_min100(corr100(overnight, ts_rank100(mf_l_buy))), turnover))))))`
  > 理由: 结构嵌套冗余，窗口参数拼凑，经济含义模糊，疑似参数过拟合。
- KILL `ts_delay1(add(barra_residual_volatility, mul(turnover, ts_min100(corr100(overnight, div(turnover, div(corr100(up_shadow, mf_m_bqty), turnover)))))))`
  > 理由: 结构嵌套冗余，量价含义拼凑，疑似参数海中捞针，无清晰经济逻辑。
- KILL `ts_mean100(intraday)`
  > 理由: 单字段简单均值无明确量价经济含义，疑似参数拼凑。
- KILL `ts_mean60(intraday)`
  > 理由: 单字段60日均值无明确量价经济含义，疑似冗余平滑。


**AI 审查(DeepSeek deepseek-v4-flash, 3s)**:

> (1) 病根：L1高IC全靠overnight与turnover的深度嵌套自相关，本质是同一信息反复磨皮，L2全灭证明无增量且过拟合。  
> (2) 压overnight权重对症，但0.25仍偏高，建议0.15；交叉+15%与深度放宽会加剧结构冗余，因当前失败主因是信号弱而非复杂度不足；min_stab降至0.75过松，会放行更多伪稳定因子；decorr=0.65对同源叶子约束不足。  
> (3) mix=[0.15,0.25,0.2,0.25,0.15]，depth=[2,3]，min_stab=0.85，decorr=0.8。理由：强制浅层换字段，高稳定性门槛逼出真信号。

## 第 39 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 6 | 0.067 | 0.080 | 0.876 | 0.000 | 1.000 | 1.000 | 57 | 1.000 | 6 | 0 | -0.018 | 1.000 | 0.167 | 1.000 | 0.833 | 0.000 | 1.000 |

叶子使用: {'up_shadow': 6, 'turnover': 6, 'overnight': 6, 'barra_residual_volatility': 2, 'mf_x_bqty': 1, 'high': 1}

**B角建议(下一代策略)**:
- 叶子[up_shadow]占比100%过高 -> 权重压到0.25, 逼引擎换字段

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 5]  min_stab=0.75  decorr=0.65  fsa_th=0.15  bank_skel_max=1
leaf_w={'volume': 0.25, 'turn_ratio': 0.25, 'turnover': 0.25, 'intraday': 0.25, 'overnight': 0.25, 'up_shadow': 0.25}
```

**LLM 引导(A角 39代)**: 调用3次, 解析通过43条, 引导位使用43条
> 日内波动与隔夜跳空的结构性背离，以及量价协动异常，能预测未来5日截面收益；资金流与价格趋势的背离也提供增量信息。


**LLM 候选审查(B角 39代)**: 深判 5 个, KILL 5 个(剔除出 L2 费后回测)
- KILL `mul(turnover, ts_min100(max(overnight, div(corr100(up_shadow, corr100(overnight, ts_std100(div(turnover, ts_std20(div(turnover, div(ts_min100(corr100(overnight, ts_rank100(corr100(overnight, turnover)))), turnover))))))), turnover))))`
  > 理由: 多层同源算子嵌套冗余，经济含义模糊，疑似参数拼凑。
- KILL `mul(turnover, ts_min100(max(ts_min100(corr100(overnight, ts_std20(div(turnover, div(corr100(up_shadow, mf_m_bqty), turnover))))), div(corr100(up_shadow, corr100(overnight, ts_std100(div(turnover, div(corr100(barra_leverage, barra_residual_volatility), turnover))))), barra_leverage))))`
  > 理由: 多层嵌套同源算子拼凑，经济含义模糊，疑似参数过拟合。
- KILL `mul(turnover, ts_min100(corr100(overnight, ts_std20(corr100(overnight, ts_std20(div(turnover, div(corr100(up_shadow, corr100(up_shadow, ts_sum100(mul(turnover, ts_min100(corr100(overnight, mul(turnover, ts_min100(corr100(overnight, ts_std20(corr100(overnight, ts_std20(div(ts_max100(sub(div(barra_residual_volatility, vwap), ts_rank100(barra_earnings_yield))), corr20(corr100(up_shadow, mf_x_bqty), turnover)))))))))))))), turnover))))))))`
  > 理由: 多层同源corr/ts_std嵌套冗余，结构拼凑无清晰量价经济含义，疑似参数过拟合。
- KILL `mul(turnover, ts_min100(ts_min100(corr100(corr100(overnight, ts_std20(div(turnover, div(corr60(up_shadow, mf_m_bqty), turnover)))), mf_s_sell))))`
  > 理由: 多层嵌套同源算子且参数堆叠，经济含义模糊，疑似参数过拟合。
- KILL `mul(ts_max20(mf_m_buy), ts_min100(corr100(overnight, ts_std20(div(turnover, div(ts_min100(corr100(overnight, ts_rank100(ts_max20(mf_m_buy)))), turnover))))))`
  > 理由: 多层嵌套同源算子且窗口参数单一，结构冗余难解释，疑似参数拼凑。


**AI 审查(DeepSeek deepseek-v4-flash, 3s)**:

> (1) 病根：因子结构高度同质化，全部收敛于“turnover×ts_min100(corr100(overnight,…))”单一模板，IC虚高但样本外全灭，本质是过拟合噪声而非有效信号。
> 
> (2) 规则B角建议：压up_shadow权重方向对，但只压到0.25仍不够，因turnover和overnight占比同样100%，需同步压；且未触及核心问题——ts_min100+corr100的深度嵌套组合已固化为骨架，仅换叶子治标不治本。建议直接禁用该模板组合。
> 
> (3) mix=[0.15, 0.5, 0.1, 0.15, 0.1]，提高交叉比例强制重组骨架；depth=[2,3,4]降复杂度；min_stab=0.8；decorr=0.7。理由：必须打破现有模板，用浅层交叉生成新结构。

## 第 40 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 4 | 0.060 | 0.071 | 0.875 | 0.000 | 1.000 | 1.000 | 58 | 1.000 | 4 | 0 | -0.019 | 1.000 | 0.000 | 1.000 | 0.750 | 0.000 | 1.000 |

叶子使用: {'up_shadow': 4, 'overnight': 4, 'turnover': 4, 'barra_liquidity': 2, 'high': 1, 'barra_residual_volatility': 1}

**B角建议(下一代策略)**:
- 叶子[up_shadow]占比100%过高 -> 权重压到0.25, 逼引擎换字段

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 5]  min_stab=0.75  decorr=0.65  fsa_th=0.15  bank_skel_max=1
leaf_w={'volume': 0.25, 'turn_ratio': 0.25, 'turnover': 0.25, 'intraday': 0.25, 'overnight': 0.25, 'up_shadow': 0.25}
```

**LLM 引导(A角 40代)**: 调用3次, 解析通过38条, 引导位使用38条
> 大单资金流向与价格日内形态背离可能预示短期反转，结合换手率与隔夜跳空的波动结构捕捉流动性溢价衰减。


**LLM 候选审查(B角 40代)**: 深判 5 个, KILL 5 个(剔除出 L2 费后回测)
- KILL `ts_delay1(add(barra_residual_volatility, mul(turnover, ts_min100(corr100(overnight, ts_std20(corr100(overnight, ts_std20(div(turnover, div(corr100(up_shadow, corr100(up_shadow, ts_sum100(mul(turnover, ts_min100(corr100(overnight, mul(turnover, ts_min100(corr100(overnight, ts_std20(corr100(overnight, ts_std20(div(turnover, ts_std200(high)))))))))))))), turnover))))))))))`
  > 理由: 多层同源corr/ts_std嵌套冗余，参数堆砌无清晰经济含义，疑似过拟合拼凑。
- KILL `mul(turnover, ts_min100(ts_min100(corr100(overnight, ts_std20(div(turnover, div(corr100(up_shadow, barra_residual_volatility), turnover)))))))`
  > 理由: 结构冗余嵌套，经济含义模糊，疑似参数拼凑。
- KILL `mul(turnover, ts_min100(ts_min100(corr100(overnight, ts_std20(div(turnover, div(corr100(up_shadow, turnover), turnover)))))))`
  > 理由: 多层嵌套同源算子且窗口重复，结构冗余难解释，疑似参数拼凑。
- KILL `add(barra_residual_volatility, mul(turnover, ts_min100(corr100(overnight, ts_std20(corr100(overnight, ts_std20(div(turnover, div(corr100(up_shadow, corr100(up_shadow, ts_sum100(mul(turnover, ts_min100(corr100(overnight, mul(turnover, ts_min100(corr100(overnight, ts_std20(corr100(overnight, ts_std20(div(overnight, up_shadow))))))))))))), turnover)))))))))`
  > 理由: 多层同源corr/ts嵌套冗余，结构拼凑无清晰经济含义，疑似参数过拟合
- KILL `mul(turnover, ts_min100(corr100(overnight, ts_std20(corr100(overnight, ts_std20(div(turnover, div(corr100(up_shadow, corr100(up_shadow, ts_sum100(mul(turnover, ts_min100(corr100(overnight, mul(turnover, ts_min100(corr100(overnight, ts_std100(div(turnover, div(corr100(fa_lev, ts_std20(div(turnover, overnight))), turnover)))))))))))), turnover))))))))`
  > 理由: 多层嵌套同源算子叠加，结构冗余难解释，疑似参数拼凑过拟合。


**AI 审查(DeepSeek deepseek-v4-flash, 2s)**:

> (1) 病根：所有L1因子结构高度同质，均以turnover×ts_min100(corr100(overnight,…))为骨架，仅末端微扰，导致IC虚高但L2全灭，属过拟合同构陷阱。
> 
> (2) 规则B角建议部分对症但不足：压up_shadow权重可促探索，但未触及turnover/overnight主导骨架，且depth=[3,4,5]过浅，无法打破深层同构；decorr=0.65偏低，难以强制结构分化；fsa_th=0.15可能误杀有效变异。
> 
> (3) 下代建议：mix=[0.15, 0.35, 0.2, 0.25, 0.05]，depth=[5,6,7]，min_stab=0.70，decorr=0.85。理由：提高变异与引导比例以暴力拆解同构骨架，加深深度迫使结构重组，降min_stab容忍短期波动以换取多样性，升decorr强制候选间低相关性。

## 第 41 代 (B角诊断)

| n_l1 | fam_blocked | n_l2 |
| --- | --- | --- |
| 0 | 64 | 0 |

**B角建议(下一代策略)**:
- 各项指标正常, 维持当前策略

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 5]  min_stab=0.75  decorr=0.65  fsa_th=0.15  bank_skel_max=1
leaf_w={'volume': 0.25, 'turn_ratio': 0.25, 'turnover': 0.25, 'intraday': 0.25, 'overnight': 0.25, 'up_shadow': 0.25}
```

**LLM 引导(A角 41代)**: 调用3次, 解析通过42条, 引导位使用42条
> 市场在连续多日资金流失衡后，超短期的价格反转与量价背离信号能预测未来5日收益，尤其当大单净流入与价格趋势不一致时。


**LLM 候选审查(B角 41代)**: 深判 5 个, KILL 5 个(剔除出 L2 费后回测)
- KILL `mul(turnover, ts_min100(ts_std20(corr100(overnight, ts_std20(div(turnover, div(corr100(up_shadow, corr100(up_shadow, ts_sum100(mul(turnover, ts_min100(corr100(overnight, mul(turnover, ts_min100(corr100(overnight, ts_std100(corr100(overnight, ts_std20(div(turnover, up_shadow))))))))))))), turnover)))))))`
  > 理由: 结构高度嵌套冗余，同源算子反复叠加，疑似参数海里捞针，经济含义模糊。
- KILL `ts_delay1(add(barra_residual_volatility, mul(turnover, ts_min100(corr100(overnight, ts_std20(corr100(overnight, ts_std20(div(turnover, div(corr100(up_shadow, corr100(up_shadow, ts_sum100(mul(turnover, ts_min100(corr100(up_shadow, corr100(up_shadow, ts_sum100(mul(turnover, ts_min100(corr100(overnight, mul(turnover, ts_min100(corr100(overnight, ts_std20(corr100(overnight, ts_std20(div(turnover, overnight)))))))))))))))))), turnover))))))))))`
  > 理由: 多层同源算子嵌套冗余，参数堆砌无清晰经济含义，疑似过拟合结构。
- KILL `mul(turnover, ts_min100(corr100(overnight, ts_std20(corr100(overnight, ts_std20(div(turnover, div(corr100(up_shadow, corr100(up_shadow, ts_sum100(mul(turnover, ts_min100(corr100(overnight, mul(turnover, ts_min100(corr100(overnight, ts_std100(corr100(overnight, ts_mean200(div(turnover, up_shadow))))))))))))), turnover))))))))`
  > 理由: 多层同源算子嵌套冗余，参数窗口堆叠，经济含义模糊，疑似过拟合拼凑。
- KILL `ts_delay1(add(barra_residual_volatility, mul(turnover, ts_min100(corr100(overnight, ts_std20(corr100(overnight, ts_std20(div(turnover, div(corr100(up_shadow, corr100(up_shadow, ts_sum100(mul(turnover, ts_min100(corr100(up_shadow, corr100(up_shadow, ts_sum100(mul(turnover, ts_min100(corr100(overnight, mul(turnover, ts_min100(corr100(overnight, ts_std20(corr100(overnight, ts_std20(div(turnover, ts_std20(turnover))))))))))))))))))), turnover))))))))))`
  > 理由: 多层嵌套同源算子叠加，结构冗余且经济含义模糊，疑似参数拼凑。
- KILL `mul(turnover, ts_min100(corr100(overnight, ts_std20(corr100(overnight, ts_std20(div(turnover, div(corr100(up_shadow, corr100(up_shadow, ts_sum100(mul(turnover, ts_min100(corr100(overnight, mul(turnover, ts_min100(corr100(overnight, ts_std100(corr100(overnight, ts_std20(div(div(corr100(up_shadow, corr100(overnight, ts_std60(turnover))), turnover), up_shadow))))))))))))), turnover))))))))`
  > 理由: 多层嵌套同源算子叠加，结构冗余复杂，参数窗口密集，疑似参数过拟合拼凑，经济含义模糊。


**AI 审查(DeepSeek deepseek-v4-flash, 3s)**:

> (1) 病根：全家族被阻断且无叶子输出，说明当前因子骨架与数据分布严重失配，搜索已陷入死区。  
> (2) 规则B角“维持策略”完全无效——死区需激进扰动而非保守；mix中变异0.1过低，无法跳出局部；depth上限5过大，在无叶子时浪费算力；decorr0.65对空集无意义。建议冲突：既称正常又无输出，自相矛盾。  
> (3) 下代建议：mix=[0.3,0.2,0.3,0.1,0.1]，depth=[2,3]，min_stab=0.6，decorr=0.5。理由：提高变异与引导比例强制探索新骨架，降低深度与稳定性门槛以快速产生首个有效叶子。

## 第 42 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 35 | 0.039 | 0.066 | 0.950 | 0.000 | 0.171 | 1.000 | 21 | 0.143 | 30 | 0 | 0.046 | 1.000 | 0.233 | 1.000 | 0.500 | 0.000 | 0.500 |

叶子使用: {'barra_residual_volatility': 6, 'ret': 5, 'amplitude': 5, 'intraday': 4, 'true_range': 4, 'mf_x_sqty': 3}

**B角建议(下一代策略)**:
- L2中100%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 本代0通过 -> 深度放宽到3~5, 探索更复杂结构
- 配比护栏: 变异/交叉各≥10%且合计50%重归一化, 扰动/引导/随机固定15/20/15(中金规格) -> mix=[0.1, 0.4, 0.15, 0.2, 0.15]

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 5]  min_stab=0.75  decorr=0.65  fsa_th=0.15  bank_skel_max=1
leaf_w={'volume': 0.25, 'turn_ratio': 0.25, 'turnover': 0.25, 'intraday': 0.25, 'overnight': 0.25, 'up_shadow': 0.25}
```

**LLM 引导(A角 42代)**: 调用3次, 解析通过38条, 引导位使用38条
> 短期日内波动率结构变化与成交量能背离，反映市场情绪切换，能预测未来5日截面收益。


**LLM 候选审查(B角 42代)**: 深判 5 个, KILL 2 个(剔除出 L2 费后回测)
- KILL `ts_std200(cs_demean(ln_mktcap))`
  > 理由: 市值对数横截面去均值后取时序标准差，与市值因子高度同构，无增量机制。
- KILL `add(barra_liquidity, add(ts_delay1(barra_liquidity), fa_ocf_yoy))`
  > 理由: 流动性因子叠加滞后项与基本面增速，含义拼凑且无增量机制。


**AI 审查(DeepSeek deepseek-v4-flash, 3s)**:

> (1) 病根：L1信号虽稳但IC峰值仅0.066，L2全灭源于信号强度不足以穿透Calmar门槛，结构复杂度未转化为收益质量。
> 
> (2) 规则B角建议：交叉+15%方向正确，但深度放宽至5可能加剧过拟合，与min_stab=0.75矛盾；decorr=0.65偏低，无法抑制深度增加带来的冗余；扰动占比20%偏高，会稀释已收敛的稳定结构。
> 
> (3) 下代建议：mix=[0.15, 0.35, 0.1, 0.25, 0.15]，depth=[3,4]，min_stab=0.8，decorr=0.7。理由：提高引导占比强化IC方向，收窄深度保稳定性，提升decorr防同质化。

## 第 43 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 40 | 0.047 | 0.067 | 0.934 | 0.000 | 0.500 | 0.975 | 8 | 0.350 | 30 | 3 | 0.057 | 1.000 | 0.519 | 0.926 | 0.407 | 0.000 | 0.400 |

叶子使用: {'barra_residual_volatility': 20, 'true_range': 10, 'barra_non_linear_size': 9, 'ln_volume': 7, 'turnover': 7, 'ret': 6}

**B角建议(下一代策略)**:
- 叶子[barra_residual_volatility]占比50%过高 -> 权重压到0.25, 逼引擎换字段
- L2中52%因换手过高失败 -> min_stab再+0.10
- L2中100%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 配比护栏: 变异/交叉各≥10%且合计50%重归一化, 扰动/引导/随机固定15/20/15(中金规格) -> mix=[0.1, 0.4, 0.15, 0.2, 0.15]

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 4]  min_stab=0.75  decorr=0.65  fsa_th=0.15  bank_skel_max=1
leaf_w={'volume': 0.25, 'turn_ratio': 0.25, 'turnover': 0.25, 'intraday': 0.25, 'overnight': 0.25, 'up_shadow': 0.25, 'barra_residual_volatility': 0.25}
```

**LLM 引导(A角 43代)**: 调用3次, 解析通过32条, 引导位使用32条
> 日内振幅与隔夜跳空的背离结构反映知情交易者行为，短期波动放大伴随跳空衰减预示弱势；量额背离捕捉资金分歧后的价格修正。


**LLM 候选审查(B角 43代)**: 深判 5 个, KILL 4 个(剔除出 L2 费后回测)
- KILL `ts_mean60(sub(corr100(turnover, barra_non_linear_size), sub(barra_residual_volatility, true_range)))`
  > 理由: 结构拼凑，量价含义不明，含barra风格因子与波动率混合，疑似参数冗余。
- KILL `mul(ts_std100(add(barra_residual_volatility, barra_earnings_yield)), mf_s_sqty)`
  > 理由: 残差波动与盈利收益率相加后取长窗标准差，再乘资金量，含义拼凑且参数冗余。
- KILL `max(ts_std60(mul(barra_residual_volatility, mf_m_sqty)), div(ts_delay1(mf_x_bqty), corr100(sub(corr20(mf_l_sqty, mf_l_sell), amplitude), close)))`
  > 理由: 结构拼凑量价字段，语义混杂，窗口参数多且无经济逻辑，疑似过拟合。
- KILL `add(corr20(corr100(ret, ts_mean150(barra_earnings_yield)), mf_x_sqty), mul(barra_residual_volatility, mf_m_sqty))`
  > 理由: 多源量价与基本面字段拼凑，嵌套相关结构含义模糊，疑似参数搜索产物。


**AI 审查(DeepSeek deepseek-v4-flash, 3s)**:

> (1) 病根：因子同质化严重，barra_residual_volatility单一叶子贡献50%IC，但L2全因Calmar不足而失败，说明信号虽稳但强度弱，缺乏增量信息。
> 
> (2) 规则B角建议：压叶子权重对症，但min_stab+0.10至0.75与当前stab_med=0.934矛盾，可能过度过滤；交叉+15%可增加结构多样性，但深度加深至[3,4,4]易过拟合，与min_stab提升冲突；mix中交叉0.4过高，会破坏现有高稳定性。
> 
> (3) 下代建议：mix=[0.15,0.25,0.2,0.25,0.15]，提高扰动与引导比例以探索新字段组合；depth=[2,3,3]保持浅层防过拟合；min_stab=0.70放宽以容纳弱信号；decorr=0.75强化去重。理由：当前核心是信息不足而非稳定性差，需广度探索而非深度挖掘。

## 第 44 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 30 | 0.057 | 0.071 | 0.925 | 0.000 | 0.767 | 0.967 | 16 | 0.300 | 30 | 0 | 0.055 | 0.933 | 0.367 | 0.833 | 0.367 | 0.000 | 0.267 |

叶子使用: {'barra_residual_volatility': 23, 'fa_ocf_yoy': 11, 'ln_volume': 9, 'fa_gm': 6, 'mf_s_bqty': 4, 'mf_m_sqty': 4}

**B角建议(下一代策略)**:
- 叶子[barra_residual_volatility]占比77%过高 -> 权重压到0.25, 逼引擎换字段
- L2中93%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 本代0通过 -> 深度放宽到3~5, 探索更复杂结构
- 配比护栏: 变异/交叉各≥10%且合计50%重归一化, 扰动/引导/随机固定15/20/15(中金规格) -> mix=[0.1, 0.4, 0.15, 0.2, 0.15]

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 5]  min_stab=0.75  decorr=0.65  fsa_th=0.15  bank_skel_max=1
leaf_w={'volume': 0.25, 'turn_ratio': 0.25, 'turnover': 0.25, 'intraday': 0.25, 'overnight': 0.25, 'up_shadow': 0.25, 'barra_residual_volatility': 0.25}
```

**LLM 引导(A角 44代)**: 调用3次, 解析通过27条, 引导位使用27条
> 日内波动率与隔夜跳空的背离结构可能反映信息交易者的行为差异，进而预测未来5日截面收益。


**LLM 候选审查(B角 44代)**: 深判 5 个, KILL 4 个(剔除出 L2 费后回测)
- KILL `ts_rank200(log(sub(barra_residual_volatility, fa_ocf_yoy)))`
  > 理由: 残差波动与现金流增速跨域相减，含义拼凑无经济逻辑。
- KILL `add(ts_mean100(corr100(corr100(fa_ocf_yoy, fa_gm), barra_residual_volatility)), ts_max20(barra_residual_volatility))`
  > 理由: 财务指标与波动率跨域拼接，语义牵强，结构冗余似参数搜索
- KILL `sub(mul(barra_residual_volatility, mf_m_sqty), fa_ocf_yoy)`
  > 理由: 量价残差波动与基本面增速跨域相减，含义拼凑无经济逻辑。
- KILL `corr60(mf_x_sell, min(mf_m_sell, add(div(ts_std20(hl_ratio), hl_ratio), true_range)))`
  > 理由: 结构拼凑，量价含义不明，嵌套冗余似参数搜索


**AI 审查(DeepSeek deepseek-v4-flash, 3s)**:

> (1) 病根：L1高IC全靠barra_residual_volatility单叶堆叠，L2却因信号弱、换手高、负年多而全军覆没，说明因子本质是低波动代理，非增量alpha。
> 
> (2) 规则B角建议：压叶权重对症但0.25仍偏高，建议≤0.15；交叉+15%与深度放宽至5会加剧过拟合，因当前结构已复杂且stab高，应优先降换手而非加复杂度；min_stab=0.75过低，会放行不稳定结构；decorr=0.65对单叶集中约束不足。
> 
> (3) 下代mix=[0.15,0.25,0.2,0.25,0.15]，depth=[2,3,4]，min_stab=0.85，decorr=0.5。理由：提高扰动与引导比例以强制换字段，降低深度与decorr阈值以强制去相关，同时维持高稳定性门槛。

## 第 45 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 23 | 0.065 | 0.072 | 0.934 | 0.000 | 1.000 | 0.957 | 36 | 0.174 | 23 | 3 | 0.050 | 0.950 | 0.250 | 0.950 | 0.400 | 0.000 | 0.217 |

叶子使用: {'barra_residual_volatility': 23, 'fa_ocf_yoy': 8, 'fa_gm': 8, 'amplitude': 5, 'ln_volume': 4, 'mf_l_buy': 3}

**B角建议(下一代策略)**:
- 叶子[barra_residual_volatility]占比100%过高 -> 权重压到0.25, 逼引擎换字段
- L2中95%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 配比护栏: 变异/交叉各≥10%且合计50%重归一化, 扰动/引导/随机固定15/20/15(中金规格) -> mix=[0.1, 0.4, 0.15, 0.2, 0.15]

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 4]  min_stab=0.75  decorr=0.65  fsa_th=0.15  bank_skel_max=1
leaf_w={'volume': 0.25, 'turn_ratio': 0.25, 'turnover': 0.25, 'intraday': 0.25, 'overnight': 0.25, 'up_shadow': 0.25, 'barra_residual_volatility': 0.25}
```

**LLM 引导(A角 45代)**: 调用3次, 解析通过41条, 引导位使用41条
> 日内波动与隔夜跳空的交互结构预示短期收益，尤其是高波动环境下的跳空回补或延续效应。


**LLM 候选审查(B角 45代)**: 深判 5 个, KILL 4 个(剔除出 L2 费后回测)
- KILL `add(ts_std100(corr100(corr100(fa_ocf_yoy, fa_gm), log(ts_mean60(ts_mean100(corr100(corr100(fa_ocf_yoy, fa_gm), barra_residual_volatility)))))), barra_residual_volatility)`
  > 理由: 财务字段嵌套相关再取对数，与量价无关，纯数学拼凑无经济含义
- KILL `add(ts_mean100(corr100(corr100(fa_ocf_yoy, fa_gm), barra_residual_volatility)), max(ret, barra_residual_volatility))`
  > 理由: 财务字段与波动率相关再叠加收益/波动率取大，含义拼凑无清晰量价机制
- KILL `div(log(sub(barra_residual_volatility, fa_lev)), ts_std20(ts_std20(mf_m_sell)))`
  > 理由: 残差波动减杠杆后取对数，再除以卖量双标准差，量纲与含义拼凑，无清晰量价机制
- KILL `max(corr100(fa_ocf_yoy, fa_gm), barra_residual_volatility)`
  > 理由: 财务字段相关性与波动率取max，含义拼凑无清晰量价机制，属数学巧合


**AI 审查(DeepSeek deepseek-v4-flash, 2s)**:

> (1)病根:barra_residual_volatility被当万能叶子,23条L1全含它,信号同源导致L2集体Calmar塌方。
> 
> (2)压权重到0.25对症但会误伤已高stab的头部;交叉+15%与深度加深同向叠加,易放大同源结构,无效;扰动/引导/随机固定15/20/15与"交叉≥10%合计50%"重归一化冲突,执行会漂移;min_stab=0.75过松,放行噪声。
> 
> (3)我取mix=[0.15,0.25,0.2,0.2,0.2],depth=[3,4,5],min_stab=0.85,decorr=0.75。理由:降交叉、提扰动与引导以破叶子垄断,抬decorr强制换字段,深度分层而非齐加。

## 第 46 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 50 | 0.049 | 0.065 | 0.917 | 0.000 | 0.860 | 0.960 | 9 | 0.200 | 30 | 0 | 0.046 | 0.967 | 0.167 | 0.800 | 0.533 | 0.000 | 0.267 |

叶子使用: {'barra_residual_volatility': 43, 'fa_ocf_yoy': 24, 'ln_volume': 10, 'mf_m_bqty': 9, 'mf_l_buy': 8, 'mf_x_bqty': 8}

**B角建议(下一代策略)**:
- 叶子[barra_residual_volatility]占比86%过高 -> 权重压到0.25, 逼引擎换字段
- L2中97%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 本代0通过 -> 深度放宽到3~5, 探索更复杂结构
- 配比护栏: 变异/交叉各≥10%且合计50%重归一化, 扰动/引导/随机固定15/20/15(中金规格) -> mix=[0.1, 0.4, 0.15, 0.2, 0.15]

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 5]  min_stab=0.75  decorr=0.65  fsa_th=0.15  bank_skel_max=1
leaf_w={'volume': 0.25, 'turn_ratio': 0.25, 'turnover': 0.25, 'intraday': 0.25, 'overnight': 0.25, 'up_shadow': 0.25, 'barra_residual_volatility': 0.25}
```

**LLM 引导(A角 46代)**: 调用3次, 解析通过37条, 引导位使用37条
> 资金流与价格的背离：当主动买卖盘强度与当日价格方向相反时（大单净买入但价格下跌，或大单净卖出但价格上涨），未来5日截面收益更可能向上，反映隐性吸筹/派发未完成。


**LLM 候选审查(B角 46代)**: 深判 5 个, KILL 4 个(剔除出 L2 费后回测)
- KILL `max(corr100(corr100(fa_ocf_yoy, barra_residual_volatility), barra_residual_volatility), barra_residual_volatility)`
  > 理由: 嵌套corr与max拼凑，无清晰量价经济含义，属数学巧合冗余结构
- KILL `max(corr100(ts_std20(mf_m_sell), barra_residual_volatility), barra_residual_volatility)`
  > 理由: 卖出额波动与残差波动率取相关再取max，含义拼凑，无清晰量价机制，疑似参数巧合
- KILL `add(ts_mean100(corr100(ts_std200(corr200(ln_volume, mf_s_bqty)), add(barra_residual_volatility, fa_ocf_yoy))), max(ret, barra_residual_volatility))`
  > 理由: 多层嵌套同源相关/波动算子，窗口100/200冗余，经济含义拼凑难解释，过拟合嫌疑
- KILL `div(log(add(barra_residual_volatility, fa_ocf_yoy)), abs(barra_residual_volatility))`
  > 理由: 残差波动率与现金流增速量纲无关，log内加正数再除自身，纯数学拼凑无经济含义


**AI 审查(DeepSeek deepseek-v4-flash, 2s)**:

> (1)病根:IC已到顶(0.065)但叶子86%挤在barra_residual_volatility,信号同质化,叠加换手/负年/Calmar三重不达标,是"高相关弱信号"而非结构不足。
> 
> (2)压权重到0.25对症;但"交叉+15%且深度加深"与"0通过"冲突——问题在L2质量不在复杂度,加深只会放大过拟合,无效。扰动/引导/随机固定15/20/15与"交叉≥10%合计50%"重归一化后实际比例被稀释,护栏形同虚设。decorr=0.65偏松,压不住同质叶子。
> 
> (3)建议mix=[0.15,0.25,0.15,0.25,0.20],depth=[2,3,4],min_stab=0.80,decorr=0.80。理由:提引导与随机换字段、降深度防过拟合、收紧decorr与stab直击同质病根。

## 第 47 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 22 | 0.057 | 0.067 | 0.940 | 0.000 | 1.000 | 0.955 | 37 | 0.227 | 22 | 0 | 0.070 | 0.909 | 0.091 | 0.636 | 0.500 | 0.000 | 0.136 |

叶子使用: {'barra_residual_volatility': 22, 'fa_ocf_yoy': 10, 'close': 7, 'fa_gm': 6, 'barra_leverage': 5, 'ln_volume': 5}

**B角建议(下一代策略)**:
- 叶子[barra_residual_volatility]占比100%过高 -> 权重压到0.25, 逼引擎换字段
- L2中91%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 本代0通过 -> 深度放宽到3~5, 探索更复杂结构
- 配比护栏: 变异/交叉各≥10%且合计50%重归一化, 扰动/引导/随机固定15/20/15(中金规格) -> mix=[0.1, 0.4, 0.15, 0.2, 0.15]

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 5]  min_stab=0.75  decorr=0.65  fsa_th=0.15  bank_skel_max=1
leaf_w={'volume': 0.25, 'turn_ratio': 0.25, 'turnover': 0.25, 'intraday': 0.25, 'overnight': 0.25, 'up_shadow': 0.25, 'barra_residual_volatility': 0.25}
```

**LLM 引导(A角 47代)**: 调用3次, 解析通过40条, 引导位使用40条
> 日内价格路径的'量价匹配质量'决定短期截面收益：当日内涨幅由低换手/低成交额推动(缩量上行)时，后续5日更易延续，而放量滞涨(高换手但日内涨幅弱、上影长)则反转下行，即用日内形态与换手/量能的背离刻画资金真实介入强度。


**LLM 候选审查(B角 47代)**: 深判 5 个, KILL 5 个(剔除出 L2 费后回测)
- KILL `log(log(sub(barra_residual_volatility, div(add(fa_np_margin, fa_ocf_yoy), mf_l_buy))))`
  > 理由: 残差波动率与财务/资金字段相减相除，量纲与含义拼凑，纯数学巧合
- KILL `max(ts_min20(cs_rank(div(fa_ocf_yoy, mf_l_buy))), barra_residual_volatility)`
  > 理由: 经营现金流增速与主动买入额相除属跨域拼凑，无清晰量价机制，且与残差波动取max冗余难解释
- KILL `max(corr100(corr100(add(ts_std100(corr100(corr100(close, fa_gm), barra_residual_volatility)), barra_residual_volatility), fa_gm), barra_residual_volatility), barra_residual_volatility)`
  > 理由: 多层同源corr/max嵌套冗余，无清晰量价机制，属参数海捞针
- KILL `add(ts_mean100(corr100(corr100(fa_ocf_yoy, ts_std20(corr100(corr100(add(ts_std100(corr100(corr100(close, fa_gm), barra_residual_volatility)), barra_residual_volatility), fa_gm), barra_residual_volatility))), barra_residual_volatility)), max(ret, barra_residual_volatility))`
  > 理由: 多层嵌套corr/ts_std堆叠，经济含义拼凑难解释，参数冗余似过拟合
- KILL `max(ts_min100(fa_ocf_yoy), barra_residual_volatility)`
  > 理由: 基本面现金流增速与残差波动率取max，量价与财务拼凑，无清晰经济机制


**AI 审查(DeepSeek deepseek-v4-flash, 1s)**:

> (1)病根:叶子被barra_residual_volatility垄断(占比100%),信号同源、结构同质,导致L2集体Calmar不足而非多样性问题。
> 
> (2)建议点评:压权重到0.25对症,但交叉+15%与深度加深会加剧同源重组,无效;深度放宽到3~5对Calmar弱无直接帮助,反而放大过拟合;mix中交叉0.4偏高、引导0.2偏低,与"换字段"目标冲突;min_stab=0.75过松,会放行不稳定叶子。
> 
> (3)我的取值:mix=[0.15,0.25,0.15,0.3,0.15],depth=[2,3],min_stab=0.85,decorr=0.75。理由:提高引导与去相关、压低交叉和深度,才能真正逼引擎跳出barra_residual_volatility同源簇。

## 第 48 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 26 | 0.052 | 0.067 | 0.934 | 0.000 | 1.000 | 0.962 | 30 | 0.231 | 26 | 0 | 0.054 | 0.923 | 0.077 | 0.769 | 0.654 | 0.000 | 0.154 |

叶子使用: {'barra_residual_volatility': 26, 'fa_ocf_yoy': 17, 'ln_volume': 6, 'barra_leverage': 5, 'close': 4, 'fa_gm': 4}

**B角建议(下一代策略)**:
- 叶子[barra_residual_volatility]占比100%过高 -> 权重压到0.25, 逼引擎换字段
- L2中92%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 本代0通过 -> 深度放宽到3~5, 探索更复杂结构
- 配比护栏: 变异/交叉各≥10%且合计50%重归一化, 扰动/引导/随机固定15/20/15(中金规格) -> mix=[0.1, 0.4, 0.15, 0.2, 0.15]

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 5]  min_stab=0.75  decorr=0.65  fsa_th=0.15  bank_skel_max=1
leaf_w={'volume': 0.25, 'turn_ratio': 0.25, 'turnover': 0.25, 'intraday': 0.25, 'overnight': 0.25, 'up_shadow': 0.25, 'barra_residual_volatility': 0.25}
```

**LLM 引导(A角 48代)**: 调用3次, 解析通过43条, 引导位使用43条
> 主力资金(大单/超大单)主动净买入的短期加速度与中小单方向背离，叠加日内价格位置与隔夜跳空的错配，能捕捉信息未完全定价的5日截面收益。


**LLM 候选审查(B角 48代)**: 深判 5 个, KILL 5 个(剔除出 L2 费后回测)
- KILL `max(corr100(ts_std20(div(ln_volume, barra_residual_volatility)), barra_residual_volatility), barra_residual_volatility)`
  > 理由: ln_volume与残差波动率量纲相除无经济含义，嵌套corr/max冗余，属数学拼凑
- KILL `add(barra_residual_volatility, add(min(barra_residual_volatility, fa_ocf_yoy), barra_leverage))`
  > 理由: 残差波动率与杠杆同源风险叠加，再混入现金流增速，含义拼凑且冗余，无清晰量价机制
- KILL `max(corr100(fa_ocf_yoy, max(fa_ocf_yoy, barra_residual_volatility)), barra_residual_volatility)`
  > 理由: 财务字段与波动率取max后相关，含义拼凑无清晰量价机制，属数学巧合
- KILL `add(barra_residual_volatility, min(barra_residual_volatility, barra_leverage))`
  > 理由: barra残差波动与杠杆取min再相加，属同源风险因子冗余拼凑，无增量量价机制
- KILL `max(corr100(corr100(min(ts_std100(corr100(corr100(barra_earnings_yield, fa_gm), barra_residual_volatility)), barra_residual_volatility), fa_gm), barra_residual_volatility), barra_residual_volatility)`
  > 理由: 多层同源corr/极值嵌套无经济含义，纯参数堆砌，过拟合


**AI 审查(DeepSeek deepseek-v4-flash, 1s)**:

> (1)病根:叶子被barra_residual_volatility单点垄断(占比100%),所有L1只是它的单调变换,同质化导致L2无独立alpha,neg_yr普遍≥1。
> 
> (2)压权重0.25对症;但交叉+15%且深度加到3~5会放大同质结构,无效甚至恶化;Calmar不足是信号弱非复杂度不足,加深治标不治本;mix护栏把变异压到0.1,反而削弱跳出单点的能力,与"逼换字段"目标冲突;扰动/引导固定值合理。
> 
> (3)我建议mix=[0.25,0.25,0.15,0.2,0.15],depth=[2,3,4],min_stab=0.8,decorr=0.75。理由:提高变异与去相关才能真正打破单字段垄断,深度不宜过深以免过拟合弱信号。

## 第 49 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 34 | 0.051 | 0.064 | 0.935 | 0.000 | 1.000 | 0.941 | 22 | 0.176 | 30 | 0 | 0.070 | 0.867 | 0.033 | 0.800 | 0.633 | 0.000 | 0.067 |

叶子使用: {'barra_residual_volatility': 34, 'fa_ocf_yoy': 23, 'barra_leverage': 17, 'fa_gm': 8, 'close': 7, 'ln_volume': 5}

**B角建议(下一代策略)**:
- 叶子[barra_residual_volatility]占比100%过高 -> 权重压到0.25, 逼引擎换字段
- L2中87%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 本代0通过 -> 深度放宽到3~5, 探索更复杂结构
- 配比护栏: 变异/交叉各≥10%且合计50%重归一化, 扰动/引导/随机固定15/20/15(中金规格) -> mix=[0.1, 0.4, 0.15, 0.2, 0.15]

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 5]  min_stab=0.75  decorr=0.65  fsa_th=0.15  bank_skel_max=1
leaf_w={'volume': 0.25, 'turn_ratio': 0.25, 'turnover': 0.25, 'intraday': 0.25, 'overnight': 0.25, 'up_shadow': 0.25, 'barra_residual_volatility': 0.25}
```

**LLM 引导(A角 49代)**: 调用3次, 解析通过43条, 引导位使用43条
> 在波动率高企的个股中，日内涨幅相对开盘跳空的强弱（即日内承接力）以及主动资金净流入与价格变动的背离，能预测未来5日截面收益：高波动股若日内强势承接且资金真实净买入，短期继续上行；若价格上行但资金净流出则反转。


**LLM 候选审查(B角 49代)**: 深判 5 个, KILL 5 个(剔除出 L2 费后回测)
- KILL `max(corr100(fa_ocf_yoy, max(ts_rank200(fa_ocf_yoy), barra_residual_volatility)), barra_residual_volatility)`
  > 理由: 基本面字段与波动率拼凑，嵌套max/corr无经济机制，属参数海捞针
- KILL `add(ts_mean100(corr100(barra_residual_volatility, min(overnight, fa_ocf_yoy))), max(barra_leverage, barra_residual_volatility))`
  > 理由: 波动率与杠杆/现金流同比拼凑，min/max无经济含义，属数学巧合
- KILL `max(max(barra_leverage, barra_residual_volatility), cs_rank(div(fa_ocf_yoy, ts_min20(ts_std200(barra_leverage)))))`
  > 理由: 杠杆与残差波动取max无经济含义，再叠多层同源算子，属参数拼凑冗余
- KILL `add(ts_mean100(corr100(barra_residual_volatility, min(barra_residual_volatility, fa_ocf_yoy))), max(max(corr100(fa_ocf_yoy, close), barra_residual_volatility), ts_min20(abs(corr200(ln_volume, barra_beta)))))`
  > 理由: 多字段多窗口嵌套拼凑，无清晰量价机制，参数海捞针，冗余难解释
- KILL `max(max(barra_leverage, cs_scale(cs_rank(div(fa_ocf_yoy, ts_min20(ts_std200(barra_leverage)))))), barra_residual_volatility)`
  > 理由: 杠杆与残差波动取max拼凑，嵌套窗口无经济机制，属参数海捞针


**AI 审查(DeepSeek deepseek-v4-flash, 2s)**:

> (1)病根:叶子被barra_residual_volatility单一垄断(占比100%),L1全是它的max/ts包装,信号同质,IC天花板锁死,故L2全灭。
> 
> (2)压权重0.25对症;但"交叉+15%且深度3~5"与"叶子垄断"冲突——深度加深只会放大同一字段的复杂包装,无效。min_stab降到0.75会放行不稳结构,与decorr=0.65去冗余方向相反,可能互相抵消。扰动/引导/随机固定值合理,但交叉0.4过高,易在贫瘠叶子上近亲繁殖。
> 
> (3)建议mix=[0.25,0.2,0.15,0.25,0.15],depth=[2,3],min_stab=0.85,decorr=0.55。理由:先靠变异+引导换字段破垄断,浅深度防过拟合,高stab保质量。

## 第 50 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 36 | 0.050 | 0.059 | 0.939 | 0.000 | 1.000 | 0.944 | 17 | 0.056 | 30 | 4 | 0.070 | 0.846 | 0.000 | 0.769 | 0.538 | 0.000 | 0.000 |

叶子使用: {'barra_residual_volatility': 36, 'barra_leverage': 25, 'fa_ocf_yoy': 23, 'fa_gm': 13, 'close': 6, 'ln_volume': 2}

**B角建议(下一代策略)**:
- 叶子[barra_residual_volatility]占比100%过高 -> 权重压到0.25, 逼引擎换字段
- L2中85%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 配比护栏: 变异/交叉各≥10%且合计50%重归一化, 扰动/引导/随机固定15/20/15(中金规格) -> mix=[0.1, 0.4, 0.15, 0.2, 0.15]

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 4]  min_stab=0.75  decorr=0.65  fsa_th=0.15  bank_skel_max=1
leaf_w={'volume': 0.25, 'turn_ratio': 0.25, 'turnover': 0.25, 'intraday': 0.25, 'overnight': 0.25, 'up_shadow': 0.25, 'barra_residual_volatility': 0.25}
```

**LLM 引导(A角 50代)**: 调用3次, 解析通过44条, 引导位使用44条
> 资金流主动性失衡与量价背离：当大单/超大单主动净买入占比高但价格未同步上行（或中小单与超大单方向背离）时，未来5日截面收益更高，反映知情资金吸筹而散户抛压被承接。


**LLM 候选审查(B角 50代)**: 深判 5 个, KILL 5 个(剔除出 L2 费后回测)
- KILL `max(add(barra_residual_volatility, barra_leverage), barra_residual_volatility)`
  > 理由: max(a+b,a)恒等于a+b，结构冗余无意义，纯数学巧合，无经济含义
- KILL `max(max(corr100(fa_ocf_yoy, max(ts_min20(cs_rank(div(fa_ocf_yoy, fa_gm))), barra_residual_volatility)), barra_residual_volatility), barra_residual_volatility)`
  > 理由: 财务字段与波动率残差多层max/corr嵌套，无清晰量价机制，属参数拼凑
- KILL `max(ts_min20(max(corr100(fa_ocf_yoy, max(fa_ocf_yoy, barra_residual_volatility)), barra_residual_volatility)), barra_residual_volatility)`
  > 理由: 财务字段与波动率做相关再嵌套max/min，无清晰量价机制，属参数拼凑
- KILL `max(ts_min20(max(barra_leverage, max(max(corr100(fa_ocf_yoy, close), barra_residual_volatility), barra_residual_volatility))), barra_residual_volatility)`
  > 理由: 多源异质字段嵌套max/corr，无清晰量价机制，属参数拼凑冗余结构
- KILL `div(log(add(barra_residual_volatility, max(barra_leverage, add(barra_residual_volatility, barra_leverage)))), close)`
  > 理由: barra风险因子与价格相除取对数，无明确量价行为，属数学拼凑


**AI 审查(DeepSeek deepseek-v4-flash, 2s)**:

> (1) 病根:叶子被barra_residual_volatility垄断(占比100%),所有表达式退化成"套壳波动率",IC虚高但L2无超额,是典型单因子过拟合。
> 
> (2) 建议点评:压叶子权重到0.25对症,但仅压权重不封禁字段,引擎仍会绕回;交叉+15%与深度加深冲突——深度已够,再加深只增复杂度不增信号,Calmar弱是信号问题非搜索空间问题;固定15/20/15与"变异交叉合计50%"自洽,但变异仅10%过低,削弱跳出局部能力。整体方向对,力度错配。
> 
> (3) 我的取值:mix=[0.2,0.35,0.15,0.15,0.15],depth=[3,4,4],min_stab=0.8,decorr=0.7。理由:提变异、降引导、抬去相关与稳定性门槛,逼引擎换字段而非堆深度。


## ★ gen50 收官复盘 + gen51 双闸门（人工节，2026-09-10）

**背景**：watcher 接力至 gen50（`[DONE] gen50 >= 50`，watcher 退出）。gen50 一代入库 4 个
（F20~F23），复盘中判定这 4 个为**近重复因子**：F20↔F23 |corr|=0.932、F21↔F22=0.879。

**证据链**（`ai_test/verify_max_collapse.py`，口径=引擎去重段 `rank_rows(v[::FWD])`）：
- 4 者顶层骨架均为 `max(<内层>, barra_residual_volatility)`。因内层是 `cs_rank(...)`∈[0,1]
  而 resvol 是截面 z-score（中心 0），`max` 约 **1/3 样本直接取到 resvol**（实测坍缩占比
  34.4 / 24.5 / 34.4 / 34.9%）——"地板效应"确凿存在。
- **但地板不是高相关的根因**：线性剔除 resvol 后 F20↔F23 仅 0.932→0.894；两者都未坍缩的
  子样本(n=38万)相关仍 **0.856**；剥离地板只比内层 = **0.789**。
- 真因是**共享主导叶**：F23 内层 `ts_min20(cs_rank(barra_leverage))` 与 barra_leverage 相关
  **0.997**（≡该叶）；F20 内层 0.786。F21/F22 共享 `fa_ocf_yoy`(0.844/0.725) 与骨架
  `ts_min20(cs_rank(...))`。
- **引擎未拦住的原因**：①同代数值去重阈值硬编码 `|corr|>0.99`，放行 0.93/0.88；
  ②`root_fam(cut=3)` 将 4 者判为不同族（`ts_mean` vs `ts_min`、内层 `#` vs `X`）；
  ③`decorr` 只比历史 bank + 基准，**同代之间不互查**。

**gen51 双闸门**（本轮实现，只影响下一代字节码）：
- **闸门1 同代近重复去重**：`|corr|>0.99` → 可配 `--dedup_corr`（默认 **0.85**）。
  标定（当时在 `ai_test/calib_gates.py`；现为 **`tools/calib_dedup_leaf.py`**）：全库 23 因子在此口径下仅上述两对 >0.85（其余 ≤0.744）
  → 0.85 拦下两对、且不误杀任何历史入库因子。
- **闸门2 叶子代理族**：`root_fam` 增补"单叶变换"维度（`--fam_sole` 默认开）。顶层 `max/min`
  的内层若经纯单目算子链化简恰为单一叶子（=叶子代理），族键取 `~<叶名>[|<地板叶>]`
  → "同叶不同壳"的代理候选归同族、按 `fam_quota` 拦重复（防 leverage 套壳+地板反复重发现）。

**验证**：`ai_test/verify_gates.py`（真实 F19~F23 回放）：闸门1 拦 F22(0.879 vs F21)、
F23(0.932 vs F20)，4 近重复 → 2；冒烟 `ai_test/qa_fam_smoke.py` 8 项全过。
**遗留**：F20~F23 已入 bank 不动（保历史可追溯），仅在新档加冗余警示；后续代次由双闸门拦截。

## 第 51 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 26 | 0.046 | 0.063 | 0.933 | 0.000 | 0.423 | 1.000 | 6 | 0.115 | 26 | 1 | 0.148 | 0.960 | 0.120 | 0.840 | 0.400 | 0.000 | 0.385 |

叶子使用: {'barra_residual_volatility': 11, 'barra_leverage': 8, 'fa_ocf_yoy': 5, 'close': 4, 'fa_gm': 3, 'vwap': 3}

**B角建议(下一代策略)**:
- 叶子[barra_residual_volatility]占比42%过高 -> 权重压到0.25, 逼引擎换字段
- L2中96%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 配比护栏: 变异/交叉各≥10%且合计50%重归一化, 扰动/引导/随机固定15/20/15(中金规格) -> mix=[0.1, 0.4, 0.15, 0.2, 0.15]

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 4]  min_stab=0.75  decorr=0.65  fsa_th=0.15  bank_skel_max=1
leaf_w={'volume': 0.25, 'turn_ratio': 0.25, 'turnover': 0.25, 'intraday': 0.25, 'overnight': 0.25, 'up_shadow': 0.25, 'barra_residual_volatility': 0.25}
```

**LLM 引导(A角 51代)**: 调用3次, 解析通过33条, 引导位使用33条
> 日内价格路径的'尾盘承接强度'——即日内收益中由收盘前主动买入推动、且伴随量额放大而非单纯换手抬升的部分——能刻画知情资金在当日信息消化后的真实方向,从而预测未来5日截面收益。


**LLM 候选审查(B角 51代)**: 深判 5 个, KILL 5 个(剔除出 L2 费后回测)
- KILL `max(corr200(fa_np_margin, barra_leverage), barra_residual_volatility)`
  > 理由: barra风格因子与财务利润率拼凑，无清晰量价机制，属数学巧合
- KILL `neg(div(log(max(sign(ts_std20(corr200(ln_volume, ts_std200(barra_leverage)))), barra_residual_volatility)), barra_comovement))`
  > 理由: 多层嵌套同源算子拼凑，无清晰量价经济含义，参数冗余似过拟合
- KILL `max(corr100(fa_ocf_yoy, ts_min20(max(barra_leverage, barra_leverage))), barra_residual_volatility)`
  > 理由: 财务字段与barra风格因子拼凑，ts_min取自身无意义，经济含义不清
- KILL `cs_scale(mul(ts_std200(ln_volume), div(ts_delta120(barra_non_linear_size), ts_sum20(barra_liquidity))))`
  > 理由: 成交量波动率乘规模变化除流动性，三源拼凑无清晰量价机制，窗口冗余疑过拟合
- KILL `mul(add(max(add(barra_residual_volatility, barra_leverage), barra_residual_volatility), barra_leverage), barra_residual_volatility)`
  > 理由: 仅两字段嵌套add/max/mul，无窗口无经济机制，属数学拼凑冗余结构


**AI 审查(DeepSeek deepseek-v4-flash, 2s)**:

> (1)病根:叶子被barra_residual_volatility绑架(42%),L2信号同质化,Calmar普遍不足,不是搜索强度问题而是表达多样性枯竭。
> 
> (2)压权重到0.25对症;交叉+15%与深度加深方向对但会加剧同质(现有L2已全是max+barra结构),可能无效;扰动/引导/随机固定15/20/15与"交叉≥10%合计50%"存在配比冲突,重归一化后实际交叉被稀释,护栏形同虚设。
> 
> (3)建议mix=[0.2,0.3,0.15,0.2,0.15],depth=[3,4,4],min_stab=0.75,decorr=0.7。理由:降交叉、提变异与decorr,先破叶子垄断再谈深度,否则加深只是复制同质结构。

## 第 52 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 19 | 0.056 | 0.063 | 0.928 | 0.000 | 1.000 | 1.000 | 17 | 0.053 | 19 | 1 | 0.069 | 1.000 | 0.167 | 0.778 | 0.500 | 0.000 | 0.263 |

叶子使用: {'barra_residual_volatility': 19, 'barra_leverage': 9, 'fa_ocf_yoy': 9, 'fa_gm': 2, 'barra_comovement': 2, 'hl_ratio': 2}

**B角建议(下一代策略)**:
- 叶子[barra_residual_volatility]占比100%过高 -> 权重压到0.25, 逼引擎换字段
- L2中100%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 配比护栏: 变异/交叉各≥10%且合计50%重归一化, 扰动/引导/随机固定15/20/15(中金规格) -> mix=[0.1, 0.4, 0.15, 0.2, 0.15]

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 4]  min_stab=0.75  decorr=0.65  fsa_th=0.15  bank_skel_max=1
leaf_w={'volume': 0.25, 'turn_ratio': 0.25, 'turnover': 0.25, 'intraday': 0.25, 'overnight': 0.25, 'up_shadow': 0.25, 'barra_residual_volatility': 0.25}
```

**LLM 引导(A角 52代)**: 调用3次, 解析通过28条, 引导位使用28条
> 在换手与成交额活跃的股票里,日内价格路径(振幅/上下影线/隔夜跳空)与残差波动率共同刻画了'交易拥挤度—情绪错配'结构:当短期日内形态相对长期基准发生偏离、且残差波动率被压缩或放大时,未来5日截面收益会出现可预测的反转/延续,而非单纯的量能水平。


**LLM 候选审查(B角 52代)**: 深判 5 个, KILL 5 个(剔除出 L2 费后回测)
- KILL `max(ts_rank100(neg(barra_leverage)), barra_residual_volatility)`
  > 理由: barra风险因子非量价字段，max拼接无经济含义，属数学拼凑
- KILL `max(ts_mean120(cs_rank(div(barra_leverage, max(add(add(barra_residual_volatility, fa_ocf_yoy), barra_leverage), barra_residual_volatility)))), barra_residual_volatility)`
  > 理由: 财务杠杆/现金流与波动率拼凑相除，无清晰量价行为，属数学巧合
- KILL `max(ts_rank100(max(ts_mean120(cs_rank(corr200(barra_leverage, fa_gm))), barra_residual_volatility)), barra_residual_volatility)`
  > 理由: 多窗口嵌套堆叠同源算子，经济含义拼凑难解释，属参数海捞针
- KILL `max(ts_mean150(corr100(cs_rank(barra_leverage), ts_min20(cs_rank(barra_leverage)))), barra_residual_volatility)`
  > 理由: barra风格暴露自相关叠加残差波动，无清晰量价行为，属参数海捞针冗余结构
- KILL `max(ts_mean120(cs_rank(div(barra_leverage, add(add(fa_gm, barra_leverage), barra_residual_volatility)))), barra_residual_volatility)`
  > 理由: 杠杆/毛利/残差波动拼凑比值，无清晰量价机制，属数学巧合


**AI 审查(DeepSeek deepseek-v4-flash, 2s)**:

> (1)病根:叶子被barra_residual_volatility单一支配(19/19),L1的IC全是它撑的,信号同质化,换字段才是真解。
> 
> (2)压权重0.25对症;但交叉+15%与深度加深同时上,易生成同质深树,无效甚至反效;扰动/引导/随机固定15/20/15与"变异/交叉合计50%重归一化"冲突,护栏会吃掉交叉增量;min_stab=0.75偏松,会放水。
> 
> (3)建议mix=[0.15,0.30,0.15,0.25,0.15],depth=[3,3,4],min_stab=0.80,decorr=0.70。理由:降交叉、提引导与去相关,先破同质再谈深度。

## 第 53 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 9 | 0.055 | 0.064 | 0.904 | 0.000 | 1.000 | 1.000 | 17 | 0.111 | 9 | 0 | 0.069 | 0.889 | 0.222 | 0.778 | 0.333 | 0.000 | 0.222 |

叶子使用: {'barra_residual_volatility': 9, 'barra_leverage': 4, 'fa_np_yoy': 3, 'mf_s_buy': 2, 'fa_gm': 2, 'fa_ocf_yoy': 2}

**B角建议(下一代策略)**:
- 叶子[barra_residual_volatility]占比100%过高 -> 权重压到0.25, 逼引擎换字段
- L2中89%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 配比护栏: 变异/交叉各≥10%且合计50%重归一化, 扰动/引导/随机固定15/20/15(中金规格) -> mix=[0.1, 0.4, 0.15, 0.2, 0.15]

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 4]  min_stab=0.75  decorr=0.65  fsa_th=0.15  bank_skel_max=1
leaf_w={'volume': 0.25, 'turn_ratio': 0.25, 'turnover': 0.25, 'intraday': 0.25, 'overnight': 0.25, 'up_shadow': 0.25, 'barra_residual_volatility': 0.25}
```

**LLM 引导(A角 53代)**: 调用3次, 解析通过48条, 引导位使用48条
> 在换手与成交额主导的短周期博弈中，日内振幅相对隔夜跳空的错配（振幅放大而跳空收敛）与上影线相对真实波幅的异常抬升，反映日内抛压未被隔夜定价吸收，这类量价结构失衡会在未来5日截面收益上表现为负向修正，而大单主动净买入占比与中小单方向背离则提供资金流侧的独立确认。


**LLM 候选审查(B角 53代)**: 深判 5 个, KILL 4 个(剔除出 L2 费后回测)
- KILL `max(ts_rank100(max(ts_mean150(ts_min20(corr100(fa_ocf_yoy, vwap))), barra_residual_volatility)), barra_residual_volatility)`
  > 理由: 多层嵌套同源时序算子，窗口20/100/150冗余，经济含义拼凑难解释，过拟合嫌疑
- KILL `max(ts_mean150(corr100(fa_ocf_yoy, cs_rank(fa_rev_yoy))), barra_residual_volatility)`
  > 理由: 财务字段相关叠加残差波动率取大，无清晰量价机制，属拼凑结构
- KILL `neg(div(log(max(sign(ts_std20(corr200(ln_volume, ts_std200(add(fa_gm, ts_mean10(cs_rank(div(barra_leverage, max(add(fa_gm, barra_leverage), barra_residual_volatility))))))))), barra_residual_volatility)), barra_comovement))`
  > 理由: 多层嵌套拼凑，经济含义不可解，属参数海捞针式冗余结构
- KILL `max(cs_scale(max(ts_mean120(cs_rank(div(barra_leverage, max(add(fa_gm, cs_scale(cs_scale(mf_s_bqty))), barra_residual_volatility)))), barra_residual_volatility)), fa_rev_yoy)`
  > 理由: 财务与量价字段混搭嵌套，经济含义拼凑难解释，冗余高


**AI 审查(DeepSeek deepseek-v4-flash, 2s)**:

> (1)病根:叶子被barra_residual_volatility单一字段垄断(占比100%),导致所有L1候选同源、L2信号弱且换手/负年集中,是"字段塌缩"而非搜索不足。
> 
> (2)点评:压权重到0.25对症,但仅压权重不封字段,引擎仍会换壳复用;交叉+15%与深度加深同时上,会放大同源表达式、加剧过拟合,二者部分冲突;扰动/引导/随机固定15/20/15偏保守,引导20%在字段塌缩下易无效;护栏"变异≥10%"与压权重方向一致,可保留。
> 
> (3)下代取值:mix=[0.15,0.30,0.15,0.20,0.20],depth=[3,4,4],min_stab=0.80,decorr=0.75。理由:提高变异与随机以强制换字段,降交叉防同源放大,decorr上调压制barra残差波动率家族。

## 第 54 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 8 | 0.059 | 0.068 | 0.884 | 0.000 | 1.000 | 1.000 | 21 | 0.125 | 8 | 0 | 0.047 | 1.000 | 0.500 | 0.875 | 0.500 | 0.000 | 0.500 |

叶子使用: {'barra_residual_volatility': 8, 'mf_s_buy': 6, 'fa_np_yoy': 6, 'fa_lev': 4, 'barra_leverage': 2, 'fa_ocf_yoy': 2}

**B角建议(下一代策略)**:
- 叶子[barra_residual_volatility]占比100%过高 -> 权重压到0.25, 逼引擎换字段
- L2中50%因换手过高失败 -> min_stab再+0.10
- L2中100%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 配比护栏: 变异/交叉各≥10%且合计50%重归一化, 扰动/引导/随机固定15/20/15(中金规格) -> mix=[0.1, 0.4, 0.15, 0.2, 0.15]

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 4]  min_stab=0.75  decorr=0.65  fsa_th=0.15  bank_skel_max=1
leaf_w={'volume': 0.25, 'turn_ratio': 0.25, 'turnover': 0.25, 'intraday': 0.25, 'overnight': 0.25, 'up_shadow': 0.25, 'barra_residual_volatility': 0.25}
```

**LLM 引导(A角 54代)**: 调用3次, 解析通过36条, 引导位使用36条
> 日内价格路径的'位置-形态'信息（收盘在当日区间的相对位置、上下影线不对称、隔夜与日内收益的背离）在截面内对短期反转/延续有独立于纯换手与成交额的预测力，尤其当这种形态与残差波动率或资金流失衡交互时。


**LLM 候选审查(B角 54代)**: 深判 5 个, KILL 5 个(剔除出 L2 费后回测)
- KILL `div(log(add(add(barra_residual_volatility, fa_op_yoy), add(add(barra_residual_volatility, barra_leverage), max(barra_leverage, barra_leverage)))), close)`
  > 理由: 多字段无意义相加后除价格，纯数学拼凑，无对应量价行为
- KILL `max(max(ts_mean120(cs_rank(div(barra_leverage, max(add(fa_gm, add(barra_residual_volatility, barra_leverage)), barra_residual_volatility)))), barra_residual_volatility), barra_residual_volatility)`
  > 理由: 杠杆/残差波动/毛利拼凑比值，无清晰量价行为，属数学巧合
- KILL `max(ts_mean120(ts_mean120(cs_rank(fa_op_yoy))), barra_residual_volatility)`
  > 理由: 基本面盈利增速与残差波动率取max，量纲含义拼凑，无清晰量价机制
- KILL `div(log(add(add(barra_residual_volatility, barra_leverage), add(add(barra_residual_volatility, barra_leverage), max(barra_leverage, barra_leverage)))), close)`
  > 理由: barra风险因子与价格相除取对数，无明确量价机制，属数学拼凑
- KILL `log(log(add(barra_residual_volatility, max(corr200(fa_np_yoy, ts_mean60(ts_min20(div(fa_ocf_yoy, vwap)))), barra_leverage))))`
  > 理由: 多层嵌套log/max/corr拼凑基本面与量价，无清晰经济机制，属参数海捞针


**AI 审查(DeepSeek deepseek-v4-flash, 2s)**:

> (1)病根：叶子被barra_residual_volatility单一字段垄断，导致L1高IC全是同源换皮，L2一落地就Calmar崩、负年多，属结构性过拟合而非信号不足。
> 
> (2)压权重0.25对症但会误伤头部IC；min_stab+0.10与depth加深、交叉+15%互相打架：深度越深越不稳，稳定门槛反而更难过，等于自锁。交叉提到0.4而变异仅0.1，会加速同源收敛，与decorr目标冲突。扰动/引导/随机固定值合理，可保留。
> 
> (3)建议mix=[0.2,0.3,0.15,0.2,0.15]，depth=[3,3,4]，min_stab=0.70，decorr=0.75。理由：先保多样性、松稳定门槛，让新字段有机会活过L2，再谈加深。

## 第 55 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 3 | 0.060 | 0.069 | 0.852 | 0.000 | 1.000 | 1.000 | 17 | 0.000 | 3 | 0 | 0.031 | 1.000 | 0.667 | 0.667 | 0.667 | 0.000 | 0.667 |

叶子使用: {'barra_residual_volatility': 3, 'fa_np_yoy': 3, 'mf_s_buy': 2, 'barra_leverage': 2, 'fa_ocf_yoy': 2}

**B角建议(下一代策略)**:
- 叶子[barra_residual_volatility]占比100%过高 -> 权重压到0.25, 逼引擎换字段
- L2中67%因换手过高失败 -> min_stab再+0.10

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 4]  min_stab=0.75  decorr=0.65  fsa_th=0.15  bank_skel_max=1
leaf_w={'volume': 0.25, 'turn_ratio': 0.25, 'turnover': 0.25, 'intraday': 0.25, 'overnight': 0.25, 'up_shadow': 0.25, 'barra_residual_volatility': 0.25}
```

**LLM 引导(A角 55代)**: 调用3次, 解析通过30条, 引导位使用30条
> 在换手与波动率给定的条件下，日内价格位置相对隔夜跳空的偏离（跳空未被日内吸收的部分）以及主动资金净买入与价格变化的背离，会在未来5日截面收益上产生反转/延续，且该效应在低流动性、高残差波动股票中更强。


**LLM 候选审查(B角 55代)**: 深判 5 个, KILL 5 个(剔除出 L2 费后回测)
- KILL `max(ts_rank100(mul(mf_s_buy, ts_rank100(corr200(fa_np_yoy, ts_mean60(ts_mean60(ts_min20(corr100(fa_ocf_yoy, barra_leverage)))))))), barra_residual_volatility)`
  > 理由: 多层嵌套同源相关/均值算子，窗口堆砌无经济机制，属参数海捞针
- KILL `max(ts_rank100(cs_rank(mul(mf_s_buy, ts_rank100(corr200(fa_np_yoy, ts_mean60(max(ts_mean120(cs_rank(mf_s_sqty)), barra_residual_volatility))))))), barra_residual_volatility)`
  > 理由: 多层嵌套同源算子冗余，窗口参数堆砌，经济含义拼凑难解释
- KILL `neg(div(log(max(sign(ts_std20(corr200(ln_volume, ts_std200(add(true_range, ts_std150(hl_ratio)))))), barra_residual_volatility)), barra_comovement))`
  > 理由: 多层嵌套同源波动/量算子，窗口20/150/200拼凑，无清晰量价机制，疑似参数海捞
- KILL `max(ts_rank100(max(ts_rank100(cs_rank(mul(mf_s_buy, ts_rank100(corr200(fa_np_yoy, ts_mean60(barra_non_linear_size)))))), barra_residual_volatility)), barra_residual_volatility)`
  > 理由: 多层ts_rank/cs_rank嵌套无清晰量价机制，参数60/100/200冗余，疑过拟合拼凑
- KILL `log(log(add(barra_residual_volatility, max(corr200(fa_np_yoy, ts_mean60(ts_min20(corr100(barra_residual_volatility, barra_leverage)))), barra_leverage))))`
  > 理由: 多层嵌套相关/时序算子拼凑，无清晰量价经济含义，参数冗余似过拟合


**AI 审查(DeepSeek deepseek-v4-flash, 2s)**:

> (1)病根:叶子被barra_residual_volatility单一垄断(占比100%),叠加max/ts_rank100嵌套过深,信号被平滑成低换手但无alpha的残差波动暴露。
> 
> (2)压权重0.25对症,但min_stab+0.10与L2失败主因(换手0.5、neg_yr高)不对症,反而会进一步锁死高稳定低IC的残差叶子,加剧同质;两者叠加会互相抵消换字段效果。fsa_th=0.15与bank_skel_max=1也偏保守,难破垄断。
> 
> (3)建议:mix=[0.15,0.35,0.2,0.2,0.1],depth=[2,3,3],min_stab=0.65,decorr=0.75。理由:降深度去嵌套、提扰动与去相关,才真正逼引擎换叶子并救换手。

## 第 56 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2 | 0.060 | 0.069 | 0.871 | 0.000 | 1.000 | 1.000 | 14 | 0.000 | 2 | 0 | 0.038 | 1.000 | 0.500 | 0.500 | 0.500 | 0.000 | 0.500 |

叶子使用: {'fa_np_yoy': 2, 'barra_residual_volatility': 2, 'barra_leverage': 2, 'mf_s_buy': 1}

**B角建议(下一代策略)**:
- 叶子[fa_np_yoy]占比100%过高 -> 权重压到0.25, 逼引擎换字段
- L2中50%因换手过高失败 -> min_stab再+0.10

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 4]  min_stab=0.75  decorr=0.65  fsa_th=0.15  bank_skel_max=1
leaf_w={'volume': 0.25, 'turn_ratio': 0.25, 'turnover': 0.25, 'intraday': 0.25, 'overnight': 0.25, 'up_shadow': 0.25, 'barra_residual_volatility': 0.25, 'fa_np_yoy': 0.25}
```

**LLM 引导(A角 56代)**: 调用3次, 解析通过29条, 引导位使用29条
> 资金流主动买卖的方向失衡在短窗内被价格确认时延续、未被确认时反转，即大单净买入强度与日内收益的匹配度（量额一致性）比单纯净额更能预测未来5日截面收益。


**LLM 候选审查(B角 56代)**: 深判 5 个, KILL 5 个(剔除出 L2 费后回测)
- KILL `log(log(add(barra_residual_volatility, max(corr200(fa_np_yoy, ts_mean60(ts_min20(sub(fa_ocf_yoy, barra_leverage)))), barra_leverage))))`
  > 理由: 财务字段与barra风险因子嵌套相减再取log，无清晰量价行为，属数学拼凑
- KILL `max(ts_rank100(cs_rank(mul(mf_s_buy, ts_rank100(add(barra_residual_volatility, max(corr200(fa_np_yoy, ts_mean60(ts_min20(corr100(mf_x_bqty, barra_leverage)))), barra_leverage)))))), barra_residual_volatility)`
  > 理由: 多层嵌套同源算子，窗口20/60/100/200堆砌，经济含义拼凑难解释，过拟合嫌疑
- KILL `max(ts_rank100(max(ts_rank100(cs_rank(mul(mf_s_buy, ts_rank100(mul(fa_np_yoy, ts_mean60(barra_residual_volatility)))))), barra_residual_volatility)), barra_residual_volatility)`
  > 理由: 多层同源ts_rank/max嵌套冗余，量价与基本面拼凑，经济含义不清，过拟合嫌疑
- KILL `max(ts_rank100(max(ts_rank100(cs_rank(mul(mf_s_buy, ts_rank100(corr200(fa_np_yoy, ts_mean60(barra_residual_volatility)))))), mul(mf_s_buy, ts_rank100(corr200(fa_np_yoy, ts_mean60(barra_residual_volatility)))))), barra_residual_volatility)`
  > 理由: 多层ts_rank/corr嵌套冗余，经济含义拼凑难解释，参数海捞针
- KILL `max(ts_rank100(max(ts_rank100(cs_rank(mul(mf_s_buy, ts_rank100(corr200(fa_np_yoy, ts_mean100(barra_residual_volatility)))))), barra_residual_volatility)), barra_residual_volatility)`
  > 理由: 多层ts_rank/cs_rank嵌套冗余，经济含义拼凑难解释，属参数海捞针


**AI 审查(DeepSeek deepseek-v4-flash, 2s)**:

> (1)病根:叶子集中度1.0、结构多样性1.0却全族被拦14次,说明不是多样性不足,而是有效信号在L2被换手与稳定性双杀,进化在自噬。
> 
> (2)建议一(压fa_np_yoy到0.25)不对症:叶子占比高是结果不是原因,强压会砍掉唯一有IC的字段,应改按族配额而非单字段。建议二(min_stab+0.10)与L2换手失败冲突:换手高是失败主因,提稳定性阈值只会更早淘汰候选,加剧n_pass=0。两条建议方向相反,一条松一条紧,叠加后大概率空转。
> 
> (3)我建议mix=[0.15,0.35,0.2,0.2,0.1],depth=[2,3,4],min_stab=0.70,decorr=0.55。理由:降深度与稳定性门槛先救活L2,再靠交叉与引导补多样性,避免在无候选时继续收紧。

## 第 57 代 (B角诊断)

| n_l1 | fam_blocked | n_l2 |
| --- | --- | --- |
| 0 | 19 | 0 |

**B角建议(下一代策略)**:
- 各项指标正常, 维持当前策略

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 4]  min_stab=0.75  decorr=0.65  fsa_th=0.15  bank_skel_max=1
leaf_w={'volume': 0.25, 'turn_ratio': 0.25, 'turnover': 0.25, 'intraday': 0.25, 'overnight': 0.25, 'up_shadow': 0.25, 'barra_residual_volatility': 0.25, 'fa_np_yoy': 0.25, 'barra_leverage': 0.25}
```

**LLM 引导(A角 57代)**: 调用3次, 解析通过31条, 引导位使用31条
> 资金流方向与价格/换手行为发生背离时（大单主动净买入强而价格未跟上，或中小单承接而超大单撤离），未来5日截面收益更可能向上；同时盈利同比加速度与风格暴露的错配提供独立确认。


**LLM 候选审查(B角 57代)**: 深判 3 个, KILL 3 个(剔除出 L2 费后回测)
- KILL `log(log(add(barra_residual_volatility, max(corr200(fa_np_yoy, ts_mean60(ts_mean200(corr100(barra_residual_volatility, barra_leverage)))), barra_leverage))))`
  > 理由: 多层嵌套corr/ts_mean拼凑，无清晰量价机制，参数冗余似过拟合
- KILL `log(log(add(barra_residual_volatility, max(corr200(fa_np_yoy, ts_mean60(ts_min20(corr100(amplitude, barra_leverage)))), barra_leverage))))`
  > 理由: 多层嵌套corr/ts_min/ts_mean拼凑，无清晰量价机制，参数冗余似过拟合
- KILL `max(ts_rank100(add(barra_residual_volatility, max(corr200(fa_np_yoy, ts_mean60(ts_min20(corr100(barra_residual_volatility, barra_leverage)))), barra_leverage))), barra_residual_volatility)`
  > 理由: 多层嵌套corr/ts_min/ts_mean拼凑，无清晰量价经济含义，参数冗余似过拟合


**AI 审查(DeepSeek deepseek-v4-flash, 2s)**:

> (1)病根:19个家族全被blocked且L1/L2双零产出,说明是准入门槛或去相关约束把整代掐死,而非搜索无效。
> 
> (2)规则B"指标正常维持现状"完全不对症:零产出不是正常,是硬约束过紧。min_stab=0.75配decorr=0.65在无候选时只会继续空转,二者叠加等于双重否决,互相强化锁死。
> 
> (3)我建议mix=[0.2,0.3,0.15,0.2,0.15],depth=[2,3,4],min_stab=0.5,decorr=0.4,fsa_th=0.1,bank_skel_max=2:先放宽稳定与去相关门槛让种子活下来,再谈择优。

## 第 58 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 27 | 0.039 | 0.067 | 0.908 | 0.000 | 0.222 | 0.963 | 13 | 0.148 | 27 | 2 | 0.083 | 1.000 | 0.240 | 1.000 | 0.560 | 0.000 | 0.704 |

叶子使用: {'intraday': 6, 'barra_residual_volatility': 4, 'barra_non_linear_size': 4, 'overnight': 3, 'mf_m_sqty': 3, 'mf_l_sqty': 2}

**B角建议(下一代策略)**:
- L2中100%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 配比护栏: 变异/交叉各≥10%且合计50%重归一化, 扰动/引导/随机固定15/20/15(中金规格) -> mix=[0.1, 0.4, 0.15, 0.2, 0.15]

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 4]  min_stab=0.75  decorr=0.65  fsa_th=0.15  bank_skel_max=1
leaf_w={'volume': 0.25, 'turn_ratio': 0.25, 'turnover': 0.25, 'intraday': 0.25, 'overnight': 0.25, 'up_shadow': 0.25, 'barra_residual_volatility': 0.25, 'fa_np_yoy': 0.25, 'barra_leverage': 0.25}
```

**LLM 引导(A角 58代)**: 调用3次, 解析通过37条, 引导位使用37条
> 在换手与成交额放大的背景下，若日内价格强度（收盘位置/振幅）与隔夜跳空方向出现背离，且这种背离伴随残余波动率抬升，则未来5日截面收益倾向于反转向上——即'高换手+日内弱但隔夜强'的错杀股存在短期修复溢价。


**LLM 候选审查(B角 58代)**: 深判 5 个, KILL 2 个(剔除出 L2 费后回测)
- KILL `mul(sub(ts_delta20(corr60(open, fa_ocf_yoy)), ts_mean150(barra_residual_volatility)), mul(mf_s_bqty, mf_s_bqty))`
  > 理由: 价量基本面混搭，mf_s_bqty平方无经济含义，窗口拼凑似参数海捞针
- KILL `max(cs_demean(mf_s_sqty), ts_std20(ts_mean5(corr100(barra_size, mf_m_sqty))))`
  > 理由: 两分支量纲/含义拼凑，corr100与嵌套窗口冗余，无清晰量价机制


**AI 审查(DeepSeek deepseek-v4-flash, 2s)**:

> (1)病根：IC尚可但L2全军覆没，fail_calmar与fail_negyear双100%，说明信号是"高稳定低收益"的伪alpha，非深度不足。
> 
> (2)交叉+15%对症存疑：病根在收益/换手结构而非搜索空间，加深depth只会放大过拟合，无效。mix重归一化后交叉0.4偏高，与decorr=0.65叠加会挤压变异探索，互相冲突。min_stab=0.75反而放松了本就过稳的约束，方向反了。
> 
> (3)建议：mix=[0.25,0.2,0.15,0.25,0.15]，depth=[2,3,3]，min_stab=0.85，decorr=0.5。理由：提变异与引导、降深度与相关约束，逼出收益弹性而非更稳的弱信号。

## 第 59 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 39 | 0.046 | 0.069 | 0.878 | 0.000 | 0.513 | 0.897 | 9 | 0.103 | 30 | 0 | 0.023 | 1.000 | 0.500 | 0.967 | 0.700 | 0.000 | 0.933 |

叶子使用: {'barra_residual_volatility': 20, 'mf_m_sqty': 9, 'mf_l_sqty': 8, 'barra_non_linear_size': 6, 'barra_liquidity': 6, 'barra_size': 5}

**B角建议(下一代策略)**:
- 叶子[barra_residual_volatility]占比51%过高 -> 权重压到0.25, 逼引擎换字段
- L2中50%因换手过高失败 -> min_stab再+0.10
- L2中100%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 本代0通过 -> 深度放宽到3~5, 探索更复杂结构
- 配比护栏: 变异/交叉各≥10%且合计50%重归一化, 扰动/引导/随机固定15/20/15(中金规格) -> mix=[0.1, 0.4, 0.15, 0.2, 0.15]

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 5]  min_stab=0.75  decorr=0.65  fsa_th=0.15  bank_skel_max=1
leaf_w={'volume': 0.25, 'turn_ratio': 0.25, 'turnover': 0.25, 'intraday': 0.25, 'overnight': 0.25, 'up_shadow': 0.25, 'barra_residual_volatility': 0.25, 'fa_np_yoy': 0.25, 'barra_leverage': 0.25}
```

**LLM 引导(A角 59代)**: 调用3次, 解析通过37条, 引导位使用37条
> 在资金流分层信息未被价格充分定价时，超大单主动净买入占比的短期抬升、以及中小单与超大单的方向背离，能预测未来5日截面收益，且该效应在低换手、低残波环境中更强。


**LLM 候选审查(B角 59代)**: 深判 5 个, KILL 2 个(剔除出 L2 费后回测)
- KILL `ts_delta60(barra_non_linear_size)`
  > 理由: 对市值类因子做60日差分，仅再表达规模老故事，无增量量价机制
- KILL `min(mf_s_buy, div(sub(log(mf_s_bqty), cs_rank(close)), mul(max(turn_ratio, fa_lev), true_range)))`
  > 理由: 多字段量价杠杆波动率拼凑嵌套，无清晰经济机制，属数学巧合


**AI 审查(DeepSeek deepseek-v4-flash, 2s)**:

> (1)病根: 叶子被barra_residual_volatility家族垄断(51%), L1高IC全是同一结构的自相关变体, 信号同质导致L2 Calmar全灭。
> 
> (2)压权重到0.25对症但不够, 需硬性ban该字段或强制跨族配对; min_stab+0.10方向反了, 失败主因是Calmar弱非不稳, 加稳会进一步锁死探索; 交叉+15%与深度3~5合理, 但mix里变异仅0.1偏低, 交叉0.4易在贫瘠池里近亲繁殖; 扰动/引导/随机固定值无冲突但引导0.2在叶子集中时会被同族吸走。
> 
> (3)建议mix=[0.2,0.3,0.15,0.2,0.15], depth=[2,3,4], min_stab=0.70, decorr=0.75。理由: 提变异+降decorr阈值强制换族, 深度不过5避免过拟合弱信号。

## 第 60 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 33 | 0.057 | 0.070 | 0.875 | 0.000 | 0.545 | 0.939 | 12 | 0.061 | 30 | 0 | 0.015 | 1.000 | 0.567 | 1.000 | 0.667 | 0.000 | 0.867 |

叶子使用: {'barra_residual_volatility': 18, 'mf_m_sqty': 12, 'barra_non_linear_size': 11, 'mf_x_bqty': 10, 'mf_s_bqty': 7, 'mf_l_sqty': 6}

**B角建议(下一代策略)**:
- 叶子[barra_residual_volatility]占比55%过高 -> 权重压到0.25, 逼引擎换字段
- L2中57%因换手过高失败 -> min_stab再+0.10
- L2中100%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 本代0通过 -> 深度放宽到3~5, 探索更复杂结构
- 配比护栏: 变异/交叉各≥10%且合计50%重归一化, 扰动/引导/随机固定15/20/15(中金规格) -> mix=[0.1, 0.4, 0.15, 0.2, 0.15]

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 5]  min_stab=0.75  decorr=0.65  fsa_th=0.15  bank_skel_max=1
leaf_w={'volume': 0.25, 'turn_ratio': 0.25, 'turnover': 0.25, 'intraday': 0.25, 'overnight': 0.25, 'up_shadow': 0.25, 'barra_residual_volatility': 0.25, 'fa_np_yoy': 0.25, 'barra_leverage': 0.25}
```

**LLM 引导(A角 60代)**: 调用3次, 解析通过35条, 引导位使用35条
> 在资金流与波动结构交互层面，超大单主动净买入相对中小单的背离、以及资金流强度与价格变化的量额错配，能刻画知情交易者的隐蔽吸筹/派发行为，从而预测未来5日截面收益。


**LLM 候选审查(B角 60代)**: 深判 5 个, KILL 3 个(剔除出 L2 费后回测)
- KILL `sub(barra_residual_volatility, corr20(mul(barra_non_linear_size, mf_m_sqty), ts_sum100(mf_l_sell)))`
  > 理由: 残差波动率减量价相关，字段尺度与含义拼凑，无清晰经济机制
- KILL `sub(barra_residual_volatility, ts_rank60(corr60(ts_rank100(barra_size), corr20(ret, mf_x_sqty))))`
  > 理由: 多层嵌套同源相关与排序，经济含义拼凑难解释，参数冗余疑过拟合
- KILL `sub(barra_residual_volatility, corr20(corr100(barra_non_linear_size, mf_m_sqty), barra_non_linear_size))`
  > 理由: 残差波动率与非线性市值相关量相减，量纲含义拼凑，无清晰量价机制，属数学巧合


**AI 审查(DeepSeek deepseek-v4-flash, 2s)**:

> (1)病根:叶子被barra_residual_volatility绑架,所有L1都是"减波动"同质变体,IC虚高但无独立alpha,L2全灭。
> 
> (2)叶子压权重对症;但min_stab+0.10与depth放宽到3~5自相矛盾,复杂结构稳定性更差,会加剧0通过;交叉+15%在叶子同质下等于近亲繁殖,无效;decorr=0.65偏松,无法拆散同族。
> 
> (3)mix=[0.25,0.2,0.15,0.25,0.15],depth=[2,3],min_stab=0.70,decorr=0.80。理由:先降同质、强去相关、控深度,再谈复杂度。

## 第 61 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 33 | 0.058 | 0.073 | 0.881 | 0.000 | 0.667 | 0.909 | 11 | 0.091 | 30 | 0 | 0.025 | 1.000 | 0.500 | 1.000 | 0.567 | 0.000 | 0.700 |

叶子使用: {'barra_residual_volatility': 22, 'mf_m_sqty': 11, 'barra_liquidity': 10, 'mf_x_bqty': 10, 'barra_non_linear_size': 9, 'amplitude': 7}

**B角建议(下一代策略)**:
- 叶子[barra_residual_volatility]占比67%过高 -> 权重压到0.25, 逼引擎换字段
- L2中50%因换手过高失败 -> min_stab再+0.10
- L2中100%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 本代0通过 -> 深度放宽到3~5, 探索更复杂结构
- 配比护栏: 变异/交叉各≥10%且合计50%重归一化, 扰动/引导/随机固定15/20/15(中金规格) -> mix=[0.1, 0.4, 0.15, 0.2, 0.15]

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 5]  min_stab=0.75  decorr=0.65  fsa_th=0.15  bank_skel_max=1
leaf_w={'volume': 0.25, 'turn_ratio': 0.25, 'turnover': 0.25, 'intraday': 0.25, 'overnight': 0.25, 'up_shadow': 0.25, 'barra_residual_volatility': 0.25, 'fa_np_yoy': 0.25, 'barra_leverage': 0.25}
```

**LLM 引导(A角 61代)**: 调用3次, 解析通过33条, 引导位使用33条
> 在换手率与波动率放大的背景下，日内价格位置相对开盘价的偏移（日内动量）与隔夜跳空的方向背离，能捕捉知情交易者与非知情交易者的博弈，从而预测未来5日截面收益。


**LLM 候选审查(B角 61代)**: 深判 5 个, KILL 3 个(剔除出 L2 费后回测)
- KILL `mul(corr20(mul(barra_non_linear_size, barra_liquidity), barra_non_linear_size), neg(barra_residual_volatility))`
  > 理由: Barra风格暴露相乘再相关，属已知市值/流动性/波动率同源冗余，无增量机制
- KILL `sub(barra_residual_volatility, corr20(mul(neg(ts_rank60(barra_liquidity)), mf_m_sqty), ts_mean200(mf_l_sell)))`
  > 理由: 残差波动率减流动性-资金流相关，量纲与机制拼凑，无清晰量价行为
- KILL `ts_delta20(ts_std200(mul(mf_l_sqty, ts_mean60(barra_liquidity))))`
  > 理由: 多层同源时序算子嵌套，窗口20/60/200无机制解释，经济含义拼凑难辨，过拟合嫌疑


**AI 审查(DeepSeek deepseek-v4-flash, 2s)**:

> (1)病根:叶子被barra_residual_volatility单点垄断(67%),且L2全灭于Calmar/负年,说明信号弱在结构同质而非深度不足。
> 
> (2)压叶子权重对症;min_stab+0.10与depth放宽到3~5自相矛盾,更深结构通常更不稳,会加剧换手与过拟合;交叉+15%对Calmar无效,因同质叶子交叉仍产同族;mix护栏把变异压到10%反而削弱去同质化。
> 
> (3)我建议mix=[0.25,0.30,0.15,0.15,0.15],depth=[2,3],min_stab=0.80,decorr=0.80。理由:提变异+强去相关才能破叶子垄断,深度不升反降以保稳定。

## 第 62 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 32 | 0.056 | 0.069 | 0.909 | 0.000 | 0.906 | 0.875 | 10 | 0.094 | 30 | 0 | 0.039 | 1.000 | 0.433 | 1.000 | 0.567 | 0.000 | 0.600 |

叶子使用: {'barra_residual_volatility': 29, 'amplitude': 12, 'barra_liquidity': 10, 'mf_m_sqty': 9, 'barra_non_linear_size': 8, 'mf_x_bqty': 6}

**B角建议(下一代策略)**:
- 叶子[barra_residual_volatility]占比91%过高 -> 权重压到0.25, 逼引擎换字段
- L2中43%因换手过高失败 -> min_stab再+0.10
- L2中100%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 本代0通过 -> 深度放宽到3~5, 探索更复杂结构
- 配比护栏: 变异/交叉各≥10%且合计50%重归一化, 扰动/引导/随机固定15/20/15(中金规格) -> mix=[0.1, 0.4, 0.15, 0.2, 0.15]

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 5]  min_stab=0.75  decorr=0.65  fsa_th=0.15  bank_skel_max=1
leaf_w={'volume': 0.25, 'turn_ratio': 0.25, 'turnover': 0.25, 'intraday': 0.25, 'overnight': 0.25, 'up_shadow': 0.25, 'barra_residual_volatility': 0.25, 'fa_np_yoy': 0.25, 'barra_leverage': 0.25}
```

**LLM 引导(A角 62代)**: 调用3次, 解析通过40条, 引导位使用40条
> 资金流内部结构失衡（大单与中小单方向背离、量额不匹配）叠加日内形态与波动结构，能捕捉未被价格充分定价的短期截面收益。


**LLM 候选审查(B角 62代)**: 深判 5 个, KILL 3 个(剔除出 L2 费后回测)
- KILL `sub(barra_residual_volatility, corr20(mul(barra_non_linear_size, corr100(mf_x_bqty, mf_s_bqty)), barra_non_linear_size))`
  > 理由: 残差波动率与非线性市值自相关相减，量价含义拼凑，属数学巧合
- KILL `ts_delta20(ts_std200(mul(mf_l_sqty, ts_mean60(corr60(low, corr20(neg(mul(barra_liquidity, neg(barra_residual_volatility))), barra_residual_volatility))))))`
  > 理由: 多层嵌套corr/neg/mul拼凑，无清晰量价机制，参数冗余似过拟合
- KILL `sub(barra_residual_volatility, corr20(mul(neg(ts_rank60(ts_std200(sub(mf_x_bqty, mf_m_bqty)))), amplitude), ts_sum20(mf_l_sell)))`
  > 理由: 多层嵌套同源算子冗余，买卖量差与振幅拼凑，无清晰量价机制，疑似参数海捞针


**AI 审查(DeepSeek deepseek-v4-flash, 2s)**:

> (1)病根:叶子被barra_residual_volatility垄断(91%),L2全是它的残差变体,信号同质且Calmar全灭,是"单因子过拟合"而非探索不足。
> 
> (2)压权重0.25对症;min_stab+0.10错——换手失败是turn高不是stab低,加stab无效且与放宽depth冲突;交叉+15%加深depth方向对但会加剧叶子集中,需配合去相关;mix里交叉0.4已够,扰动/引导固定值偏机械,随机0.15在0通过时是浪费。
> 
> (3)建议mix=[0.15,0.30,0.15,0.25,0.15],depth=[2,3,4],min_stab=0.70,decorr=0.75。理由:降depth防过拟合、提decorr强制换字段、引导权重升以注入先验,比盲目加深更对症。

## 第 63 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 26 | 0.058 | 0.069 | 0.896 | 0.000 | 0.962 | 0.923 | 14 | 0.115 | 26 | 0 | 0.021 | 1.000 | 0.577 | 1.000 | 0.538 | 0.000 | 0.500 |

叶子使用: {'barra_residual_volatility': 25, 'barra_liquidity': 6, 'amplitude': 6, 'mf_m_sqty': 6, 'barra_non_linear_size': 4, 'mf_x_bqty': 4}

**B角建议(下一代策略)**:
- 叶子[barra_residual_volatility]占比96%过高 -> 权重压到0.25, 逼引擎换字段
- L2中58%因换手过高失败 -> min_stab再+0.10
- L2中100%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 本代0通过 -> 深度放宽到3~5, 探索更复杂结构
- 配比护栏: 变异/交叉各≥10%且合计50%重归一化, 扰动/引导/随机固定15/20/15(中金规格) -> mix=[0.1, 0.4, 0.15, 0.2, 0.15]

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 5]  min_stab=0.75  decorr=0.65  fsa_th=0.15  bank_skel_max=1
leaf_w={'volume': 0.25, 'turn_ratio': 0.25, 'turnover': 0.25, 'intraday': 0.25, 'overnight': 0.25, 'up_shadow': 0.25, 'barra_residual_volatility': 0.25, 'fa_np_yoy': 0.25, 'barra_leverage': 0.25}
```

**LLM 引导(A角 63代)**: 调用3次, 解析通过44条, 引导位使用44条
> 日内收益与隔夜跳空的背离（日内被砸而出价未跳低=日内吸收）预示未来五日截面收益反转向上，且该吸收效应在低残波、低杠杆、高盈利增长股中更强。


**LLM 候选审查(B角 63代)**: 深判 5 个, KILL 4 个(剔除出 L2 费后回测)
- KILL `max(barra_residual_volatility, ts_rank60(cs_scale(barra_non_linear_size)))`
  > 理由: max拼接波动率与规模时序排名，两字段异源无经济机制，属含义拼凑
- KILL `sub(sub(barra_residual_volatility, corr100(barra_non_linear_size, fa_roe)), corr100(barra_non_linear_size, fa_roe))`
  > 理由: 残差波动率减两倍同源相关项，结构冗余且经济含义拼凑，难解释
- KILL `max(barra_residual_volatility, ts_rank60(cs_scale(ts_std60(ts_std60(fa_ocf_yoy)))))`
  > 理由: 残差波动率与现金流同比双层波动率拼凑，经济含义不清，属数学巧合
- KILL `max(barra_residual_volatility, ts_rank60(sub(barra_residual_volatility, corr20(mul(barra_non_linear_size, mul(mf_m_sqty, mul(mf_m_sqty, amplitude))), barra_growth))))`
  > 理由: 多层同源barra残差波动嵌套，含成交量平方与振幅拼凑，无清晰量价机制，冗余过拟合


**AI 审查(DeepSeek deepseek-v4-flash, 2s)**:

> (1) 病根:叶子被barra_residual_volatility单点垄断(96%),信号同源导致L2全线Calmar不足,不是深度不够而是多样性枯竭。
> 
> (2) 压权重0.25对症;min_stab+0.10与0通过矛盾,只会更死;交叉+15%且深度3~5,在单叶垄断下只放大同源噪声,无效;扰动/引导/随机固定值合理但被交叉挤压;整体把"缺多样性"误诊为"缺复杂度"。
> 
> (3) mix=[0.25,0.2,0.15,0.25,0.15],depth=[2,3,4],min_stab=0.70,decorr=0.80。理由:先靠变异与引导换字段、降相关,再谈深度。

## 第 64 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 26 | 0.059 | 0.076 | 0.883 | 0.000 | 1.000 | 1.000 | 15 | 0.038 | 26 | 0 | 0.037 | 1.000 | 0.769 | 1.000 | 0.500 | 0.000 | 0.538 |

叶子使用: {'barra_residual_volatility': 26, 'barra_liquidity': 11, 'low': 8, 'amplitude': 7, 'mf_x_bqty': 7, 'barra_non_linear_size': 6}

**B角建议(下一代策略)**:
- 叶子[barra_residual_volatility]占比100%过高 -> 权重压到0.25, 逼引擎换字段
- L2中77%因换手过高失败 -> min_stab再+0.10
- L2中100%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 本代0通过 -> 深度放宽到3~5, 探索更复杂结构
- 配比护栏: 变异/交叉各≥10%且合计50%重归一化, 扰动/引导/随机固定15/20/15(中金规格) -> mix=[0.1, 0.4, 0.15, 0.2, 0.15]

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 5]  min_stab=0.75  decorr=0.65  fsa_th=0.15  bank_skel_max=1
leaf_w={'volume': 0.25, 'turn_ratio': 0.25, 'turnover': 0.25, 'intraday': 0.25, 'overnight': 0.25, 'up_shadow': 0.25, 'barra_residual_volatility': 0.25, 'fa_np_yoy': 0.25, 'barra_leverage': 0.25}
```

**LLM 引导(A角 64代)**: 调用3次, 解析通过45条, 引导位使用45条
> 资金流内部方向背离（中小单与超大单主动买卖净额之差）叠加日内价格位置与波动结构，能刻画知情交易者与散户的博弈，从而预测未来5日截面收益。


**LLM 候选审查(B角 64代)**: 深判 5 个, KILL 4 个(剔除出 L2 费后回测)
- KILL `max(barra_residual_volatility, ts_rank60(cs_scale(ts_std200(ts_delta5(ln_volume)))))`
  > 理由: max拼接残差波动率与成交量波动秩，含义拼凑且窗口冗余，无统一经济机制
- KILL `max(sub(barra_residual_volatility, ts_rank200(cs_scale(ts_std200(ts_std60(low))))), ts_rank60(corr60(mf_x_bqty, amplitude)))`
  > 理由: 多层嵌套同源波动算子冗余，含barra残差波动与量价拼凑，经济含义不清，疑似参数海捞针
- KILL `mul(corr60(mf_x_bqty, amplitude), sub(mul(barra_residual_volatility, barra_residual_volatility), corr100(barra_non_linear_size, fa_roe)))`
  > 理由: 多字段多算子拼凑，经济含义不清，疑似参数海捞针与冗余嵌套
- KILL `sub(barra_residual_volatility, corr20(div(barra_non_linear_size, barra_liquidity), barra_non_linear_size))`
  > 理由: barra因子间相减拼凑，无明确量价行为，属数学巧合结构


**AI 审查(DeepSeek deepseek-v4-flash, 1s)**:

> (1)病根:叶子被barra_residual_volatility单一主导(100%),信号同质化导致Calmar全灭,换手与稳定性只是伴生症状。
> 
> (2)点评:压权重到0.25对症,但需配字段白名单否则无效;min_stab+0.10与深度放宽到3~5互相冲突,深树更易过拟合、稳定性更难达标;交叉+15%在叶子同质时只是近亲繁殖,无效;mix重归一化后交叉0.4偏高、变异0.1偏低,探索不足。
> 
> (3)我建议:mix=[0.25,0.25,0.15,0.2,0.15],depth=[2,3,4],min_stab=0.80,decorr=0.75。理由:先提变异与去相关打破叶子垄断,深度收敛防过拟合,稳定门槛不降反升。

## 第 65 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 28 | 0.060 | 0.076 | 0.893 | 0.000 | 1.000 | 1.000 | 9 | 0.036 | 28 | 0 | 0.066 | 0.964 | 0.679 | 1.000 | 0.607 | 0.000 | 0.571 |

叶子使用: {'barra_residual_volatility': 28, 'barra_liquidity': 13, 'barra_non_linear_size': 8, 'low': 7, 'mf_m_sqty': 6, 'mf_s_bqty': 5}

**B角建议(下一代策略)**:
- 叶子[barra_residual_volatility]占比100%过高 -> 权重压到0.25, 逼引擎换字段
- L2中68%因换手过高失败 -> min_stab再+0.10
- L2中96%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 本代0通过 -> 深度放宽到3~5, 探索更复杂结构
- 配比护栏: 变异/交叉各≥10%且合计50%重归一化, 扰动/引导/随机固定15/20/15(中金规格) -> mix=[0.1, 0.4, 0.15, 0.2, 0.15]

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 5]  min_stab=0.75  decorr=0.65  fsa_th=0.15  bank_skel_max=1
leaf_w={'volume': 0.25, 'turn_ratio': 0.25, 'turnover': 0.25, 'intraday': 0.25, 'overnight': 0.25, 'up_shadow': 0.25, 'barra_residual_volatility': 0.25, 'fa_np_yoy': 0.25, 'barra_leverage': 0.25}
```

**LLM 引导(A角 65代)**: 调用3次, 解析通过43条, 引导位使用43条
> 主动资金流的方向性失衡(大单/超大单净买入占比)与价格变化出现背离时，未来5日截面收益向资金流方向修复；同时财报景气加速度与风格暴露的错配提供独立定价线索。


**LLM 候选审查(B角 65代)**: 深判 5 个, KILL 4 个(剔除出 L2 费后回测)
- KILL `max(barra_residual_volatility, ts_rank60(cs_scale(div(barra_non_linear_size, ts_std150(barra_residual_volatility)))))`
  > 理由: 残差波动率与非线性市值相除再标准化，属已知市值/波动率族冗余拼凑，无增量机制
- KILL `max(max(barra_residual_volatility, ts_rank60(barra_liquidity)), ts_rank60(max(barra_residual_volatility, ts_rank60(cs_scale(ts_std200(mf_m_sqty))))))`
  > 理由: 多层max/ts_rank嵌套冗余，残差波动与流动性拼凑，无清晰增量机制
- KILL `max(barra_residual_volatility, ts_rank60(sub(barra_residual_volatility, ts_rank100(cs_scale(ts_std200(ts_std60(barra_liquidity)))))))`
  > 理由: 多层同源波动率/流动性嵌套，窗口60/100/200冗余，经济含义拼凑难解释
- KILL `mul(corr60(mf_m_sqty, cs_demean(div(mf_m_buy, low))), abs(max(barra_residual_volatility, ts_rank60(ts_std200(cs_rank(mf_m_sell))))))`
  > 理由: 多层嵌套同源量价算子，窗口60/200冗余，经济含义拼凑难解释，过拟合嫌疑


**AI 审查(DeepSeek deepseek-v4-flash, 2s)**:

> (1)病根:叶子被barra_residual_volatility单一垄断,信号同质化,IC虚高但Calmar/换手全崩,是过拟合而非因子弱。
> 
> (2)压权重0.25对症;min_stab+0.10与depth放宽到3~5自相矛盾,越复杂越不稳,应反向;交叉+15%且depth加深会放大同质繁殖,无效;扰动/引导/随机固定比例合理;decorr=0.65偏松,难破垄断。
> 
> (3)我建议mix=[0.15,0.25,0.15,0.25,0.20],depth=[2,3],min_stab=0.85,decorr=0.80。理由:先降复杂度、提稳定性与去相关,逼引擎换字段,而非加深结构。

## 第 66 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 27 | 0.060 | 0.076 | 0.884 | 0.000 | 1.000 | 0.963 | 16 | 0.074 | 27 | 0 | 0.066 | 0.963 | 0.741 | 0.926 | 0.481 | 0.000 | 0.593 |

叶子使用: {'barra_residual_volatility': 27, 'barra_liquidity': 13, 'mf_m_sqty': 6, 'barra_non_linear_size': 6, 'low': 6, 'amplitude': 4}

**B角建议(下一代策略)**:
- 叶子[barra_residual_volatility]占比100%过高 -> 权重压到0.25, 逼引擎换字段
- L2中74%因换手过高失败 -> min_stab再+0.10
- L2中96%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 本代0通过 -> 深度放宽到3~5, 探索更复杂结构
- 配比护栏: 变异/交叉各≥10%且合计50%重归一化, 扰动/引导/随机固定15/20/15(中金规格) -> mix=[0.1, 0.4, 0.15, 0.2, 0.15]

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 5]  min_stab=0.75  decorr=0.65  fsa_th=0.15  bank_skel_max=1
leaf_w={'volume': 0.25, 'turn_ratio': 0.25, 'turnover': 0.25, 'intraday': 0.25, 'overnight': 0.25, 'up_shadow': 0.25, 'barra_residual_volatility': 0.25, 'fa_np_yoy': 0.25, 'barra_leverage': 0.25}
```

**LLM 引导(A角 66代)**: 调用3次, 解析通过33条, 引导位使用33条
> 在资金流、财报景气与风格暴露三条新叶子上，真正能预测未来5日截面收益的是'信息到达速度差'：主动资金流相对其自身历史的异常强度、盈利同比的加速度、以及风格动量短长窗背离，三者共同刻画'增量信息尚未被价格完全吸收'的股票，其未来5日截面收益更高。


**LLM 候选审查(B角 66代)**: 深判 5 个, KILL 5 个(剔除出 L2 费后回测)
- KILL `max(max(barra_residual_volatility, ts_rank60(barra_liquidity)), ts_rank60(cs_scale(ts_std200(sub(barra_non_linear_size, barra_liquidity)))))`
  > 理由: 多因子max拼凑，含尺度相减与嵌套同源算子，无清晰量价机制，冗余过拟合
- KILL `max(mul(barra_residual_volatility, barra_residual_volatility), ts_rank60(sub(barra_residual_volatility, abs(barra_residual_volatility))))`
  > 理由: 残差波动率平方与自减绝对值恒为0的ts_rank拼凑，无经济含义，纯数学巧合
- KILL `sub(mul(barra_residual_volatility, barra_residual_volatility), corr200(barra_non_linear_size, cs_scale(ts_mean20(barra_liquidity))))`
  > 理由: 残差波动平方减流动性相关，量纲与含义拼凑，无清晰量价机制
- KILL `max(barra_residual_volatility, div(barra_residual_volatility, barra_liquidity))`
  > 理由: 同源barra字段自除再取max，无窗口无经济机制，属数学拼凑冗余结构
- KILL `sub(max(barra_residual_volatility, ts_rank60(sub(barra_residual_volatility, ts_rank200(cs_scale(ts_std200(ts_std60(ts_rank60(barra_liquidity)))))))), ts_rank60(barra_comovement))`
  > 理由: 多层同源波动率/流动性算子嵌套冗余，窗口60/200拼凑，经济含义难辨，疑似参数海捞


**AI 审查(DeepSeek deepseek-v4-flash, 1s)**:

> (1)病根:叶子被barra_residual_volatility单一霸占,信号同质化,换手与Calmar双杀,0通过是必然。
> 
> (2)压权重0.25对症;min_stab+0.10错,stab_med已0.884且lt50为0,再抬只砍候选不降换手;交叉+15%与深度3~5叠加会加剧过拟合,且与decorr0.65冲突;扰动/引导/随机固定值合理。核心矛盾是换手,非稳定性。
> 
> (3)建议mix=[0.15,0.25,0.2,0.25,0.15],depth=[2,3,4],min_stab=0.80,decorr=0.75。理由:降深度、提引导与去相关,逼叶子换血并压换手,而非堆复杂度。

## 第 67 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 25 | 0.060 | 0.069 | 0.871 | 0.000 | 1.000 | 1.000 | 17 | 0.120 | 25 | 1 | 0.066 | 0.958 | 0.833 | 0.958 | 0.292 | 0.000 | 0.400 |

叶子使用: {'barra_residual_volatility': 25, 'barra_liquidity': 10, 'barra_non_linear_size': 10, 'volume': 6, 'mf_l_sqty': 5, 'mf_s_bqty': 4}

**B角建议(下一代策略)**:
- 叶子[barra_residual_volatility]占比100%过高 -> 权重压到0.25, 逼引擎换字段
- L2中83%因换手过高失败 -> min_stab再+0.10
- L2中96%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 配比护栏: 变异/交叉各≥10%且合计50%重归一化, 扰动/引导/随机固定15/20/15(中金规格) -> mix=[0.1, 0.4, 0.15, 0.2, 0.15]

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 4]  min_stab=0.75  decorr=0.65  fsa_th=0.15  bank_skel_max=1
leaf_w={'volume': 0.25, 'turn_ratio': 0.25, 'turnover': 0.25, 'intraday': 0.25, 'overnight': 0.25, 'up_shadow': 0.25, 'barra_residual_volatility': 0.25, 'fa_np_yoy': 0.25, 'barra_leverage': 0.25}
```

**LLM 引导(A角 67代)**: 调用3次, 解析通过43条, 引导位使用43条
> 资金流内部结构失衡（大单/超大单主动净买入相对中小单的背离）配合日内形态与隔夜跳空的量价背离，能刻画知情交易者的吸筹/派发行为，从而预测未来5日截面收益。


**LLM 候选审查(B角 67代)**: 深判 5 个, KILL 4 个(剔除出 L2 费后回测)
- KILL `max(mul(corr60(mf_l_sell, amplitude), abs(barra_residual_volatility)), cs_scale(barra_non_linear_size))`
  > 理由: 拼凑barra风格因子与资金流，max叠加无经济机制，属参数堆砌
- KILL `sub(max(barra_residual_volatility, ts_rank60(cs_scale(barra_liquidity))), ts_rank200(cs_scale(ts_std200(ts_std60(ts_rank60(cs_scale(ts_std150(barra_residual_volatility))))))))`
  > 理由: 多层同源波动率嵌套+窗口堆叠，无清晰量价机制，冗余过拟合
- KILL `mul(corr60(turnover, amplitude), abs(max(max(mul(corr60(mf_l_sell, amplitude), abs(barra_residual_volatility)), ts_rank60(barra_non_linear_size)), ts_rank60(cs_scale(ts_std200(cs_rank(mf_l_sqty)))))))`
  > 理由: 多层同源算子嵌套拼凑，含市值/成交额老因子，无清晰量价机制，过拟合嫌疑重
- KILL `mul(corr60(turnover, amplitude), abs(max(barra_residual_volatility, ts_rank60(ts_std200(cs_rank(mf_l_sqty))))))`
  > 理由: 成交额与振幅相关乘残差波动，多算子嵌套冗余，经济含义拼凑难解释


**AI 审查(DeepSeek deepseek-v4-flash, 2s)**:

> (1)病根:叶子被barra_residual_volatility单一霸占(占比100%),信号同质化导致L2普遍Calmar弱、换手高,是"伪分散"。
> 
> (2)压权重0.25对症;min_stab再+0.10方向反了,换手高不是稳定性问题,加stab只会更锁死同质叶子;交叉+15%且depth加深与"降换手"目标冲突,深树更易过拟合、换手更高;mix护栏本身自洽,但把交叉抬到0.4会放大同质重组。
> 
> (3)建议mix=[0.25,0.2,0.15,0.25,0.15],depth=[2,3,3],min_stab=0.70,decorr=0.80。理由:提变异、压交叉、降深度、升decorr,才能真正打破单叶子垄断并压换手。

## 第 68 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 17 | 0.055 | 0.069 | 0.885 | 0.000 | 1.000 | 0.941 | 8 | 0.294 | 17 | 0 | 0.108 | 0.941 | 0.529 | 1.000 | 0.353 | 0.000 | 0.294 |

叶子使用: {'barra_residual_volatility': 17, 'barra_liquidity': 11, 'turnover': 5, 'barra_non_linear_size': 5, 'mf_s_buy': 4, 'mf_m_sqty': 3}

**B角建议(下一代策略)**:
- 叶子[barra_residual_volatility]占比100%过高 -> 权重压到0.25, 逼引擎换字段
- L2中53%因换手过高失败 -> min_stab再+0.10
- L2中94%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 本代0通过 -> 深度放宽到3~5, 探索更复杂结构
- 配比护栏: 变异/交叉各≥10%且合计50%重归一化, 扰动/引导/随机固定15/20/15(中金规格) -> mix=[0.1, 0.4, 0.15, 0.2, 0.15]

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 5]  min_stab=0.75  decorr=0.65  fsa_th=0.15  bank_skel_max=1
leaf_w={'volume': 0.25, 'turn_ratio': 0.25, 'turnover': 0.25, 'intraday': 0.25, 'overnight': 0.25, 'up_shadow': 0.25, 'barra_residual_volatility': 0.25, 'fa_np_yoy': 0.25, 'barra_leverage': 0.25}
```

**LLM 引导(A角 68代)**: 调用3次, 解析通过38条, 引导位使用38条
> 隔夜跳空与日内反转的背离结构（跳空高开但日内资金/量能无法延续）是短期截面收益的负向预测源，其与波动率暴露、换手率冲击的交互能进一步放大该反转效应。


**LLM 候选审查(B角 68代)**: 深判 5 个, KILL 5 个(剔除出 L2 费后回测)
- KILL `mul(corr60(turnover, amplitude), abs(max(barra_residual_volatility, ts_rank100(cs_scale(ts_std200(cs_rank(turnover)))))))`
  > 理由: 多层同源换手率嵌套+多窗口拼凑，经济含义不清，冗余过拟合
- KILL `max(max(barra_residual_volatility, ts_min100(barra_non_linear_size)), max(barra_residual_volatility, ts_rank200(cs_scale(ts_std100(cs_rank(mf_s_buy))))))`
  > 理由: barra残差波动与非线性市值拼凑，量价含义不清，属参数海捞针冗余结构
- KILL `sub(mul(barra_residual_volatility, barra_liquidity), corr100(barra_non_linear_size, cs_rank(max(barra_residual_volatility, ts_rank200(cs_scale(ts_std100(cs_rank(mf_s_buy))))))))`
  > 理由: 多层嵌套同源波动/流动性算子，含原始尺度相减，经济含义拼凑难解释，过拟合嫌疑
- KILL `max(max(barra_residual_volatility, div(barra_residual_volatility, barra_liquidity)), ts_rank60(cs_scale(ts_std150(cs_rank(mf_s_buy)))))`
  > 理由: 残差波动率与流动性相除无经济含义，再叠长窗量价rank，属参数拼凑冗余
- KILL `max(abs(max(barra_residual_volatility, max(abs(max(barra_residual_volatility, ts_rank60(cs_scale(ts_std200(cs_rank(turnover)))))), ts_rank60(cs_scale(max(barra_residual_volatility, div(barra_residual_volatility, barra_liquidity))))))), ts_rank60(cs_scale(max(barra_residual_volatility, div(barra_residual_volatility, barra_liquidity)))))`
  > 理由: 多层max/abs嵌套冗余，含barra残差波动与流动性自除，无清晰量价机制，疑似参数拼凑


**AI 审查(DeepSeek deepseek-v4-flash, 3s)**:

> (1)病根:叶子被barra_residual_volatility单一字段垄断(占比100%),信号同质化,叠加过度换手与弱Calmar,导致L2全灭。
> 
> (2)点评:压权重到0.25对症,但仅压权重不够,需硬性字段配额。min_stab+0.10方向反了——stab_med已0.885、stab_lt50=0,再抬只会更空,应降。交叉+15%与深度加深对症弱信号,但depth放宽到5会加剧换手,与fail_turn冲突。mix重归一化后交叉0.4偏高、变异0.1偏低,探索不足。decorr=0.65偏松,难破同质。
> 
> (3)取值:mix=[0.2,0.3,0.15,0.2,0.15],depth=[2,3,4],min_stab=0.80,decorr=0.80。理由:提变异+收紧decorr破字段垄断,控深度压换手,min_stab微降留活口。

## 第 69 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 38 | 0.052 | 0.075 | 0.900 | 0.000 | 0.579 | 0.921 | 5 | 0.211 | 30 | 1 | 0.108 | 0.966 | 0.379 | 0.966 | 0.483 | 0.000 | 0.400 |

叶子使用: {'barra_residual_volatility': 22, 'barra_liquidity': 17, 'barra_non_linear_size': 14, 'turnover': 5, 'intraday': 5, 'mf_s_buy': 3}

**B角建议(下一代策略)**:
- 叶子[barra_residual_volatility]占比58%过高 -> 权重压到0.25, 逼引擎换字段
- L2中97%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 配比护栏: 变异/交叉各≥10%且合计50%重归一化, 扰动/引导/随机固定15/20/15(中金规格) -> mix=[0.1, 0.4, 0.15, 0.2, 0.15]

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 4]  min_stab=0.75  decorr=0.65  fsa_th=0.15  bank_skel_max=1
leaf_w={'volume': 0.25, 'turn_ratio': 0.25, 'turnover': 0.25, 'intraday': 0.25, 'overnight': 0.25, 'up_shadow': 0.25, 'barra_residual_volatility': 0.25, 'fa_np_yoy': 0.25, 'barra_leverage': 0.25}
```

**LLM 引导(A角 69代)**: 调用3次, 解析通过45条, 引导位使用45条
> 本代假设：在流动性与波动暴露被风格化剥离后，真正的截面收益来自‘资金流方向与价格/跳空形态的错位’——即主动大单净买入持续但日内价格未跟上（价量背离）的股票，以及隔夜跳空与日内反转结构不匹配的股票，未来5日截面收益更高；同时盈利景气与杠杆风格的错配提供二次确认。


**LLM 候选审查(B角 69代)**: 深判 5 个, KILL 4 个(剔除出 L2 费后回测)
- KILL `sub(mul(barra_residual_volatility, barra_liquidity), corr100(barra_non_linear_size, cs_rank(ts_mean100(mf_s_buy))))`
  > 理由: 波动率×流动性再减规模与资金流相关，结构拼凑冗余，属已知风格因子重述
- KILL `sub(mul(barra_residual_volatility, barra_liquidity), corr100(barra_non_linear_size, cs_rank(cs_rank(amplitude))))`
  > 理由: barra风险因子与振幅秩相关相乘再减，含义拼凑，无清晰量价机制
- KILL `max(barra_residual_volatility, div(div(barra_non_linear_size, barra_liquidity), barra_liquidity))`
  > 理由: barra因子二次相除拼凑，无明确量价机制，属数学巧合
- KILL `max(max(barra_residual_volatility, ts_rank60(sub(barra_residual_volatility, ts_rank200(cs_scale(ts_std200(barra_liquidity)))))), ts_rank60(ts_std200(volume)))`
  > 理由: 残差波动率与流动性/成交量多层嵌套拼凑，无清晰量价机制，冗余过拟合


**AI 审查(DeepSeek deepseek-v4-flash, 2s)**:

> (1)病根:叶子被barra_residual_volatility垄断58%,信号同质化,IC虚高但Calmar/负年普遍不过,是"单一因子换皮"而非真分散。
> 
> (2)压权重到0.25对症;但交叉+15%与深度加深同时上,会放大同源重组,反致叶子更集中,二者部分冲突。扰动/引导/随机固定15/20/15偏保守,引导20%在已知比仅0.21时易空转。decorr=0.65偏松,难破58%集中。min_stab=0.75会放行stab0.76的弱叶,与去同质目标矛盾。
> 
> (3)建议mix=[0.15,0.30,0.15,0.20,0.20],depth=[3,4,3],min_stab=0.85,decorr=0.75。理由:提变异与随机、降交叉深度以强制换字段,收紧stab与decorr直接压集中度。

## 第 70 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 21 | 0.054 | 0.075 | 0.906 | 0.000 | 1.000 | 0.905 | 8 | 0.238 | 21 | 1 | 0.108 | 0.850 | 0.450 | 0.950 | 0.750 | 0.000 | 0.143 |

叶子使用: {'barra_residual_volatility': 21, 'barra_liquidity': 15, 'barra_non_linear_size': 13, 'turnover': 5, 'mf_s_buy': 1, 'barra_comovement': 1}

**B角建议(下一代策略)**:
- 叶子[barra_residual_volatility]占比100%过高 -> 权重压到0.25, 逼引擎换字段
- L2中45%因换手过高失败 -> min_stab再+0.10
- L2中85%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 配比护栏: 变异/交叉各≥10%且合计50%重归一化, 扰动/引导/随机固定15/20/15(中金规格) -> mix=[0.1, 0.4, 0.15, 0.2, 0.15]

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 4]  min_stab=0.75  decorr=0.65  fsa_th=0.15  bank_skel_max=1
leaf_w={'volume': 0.25, 'turn_ratio': 0.25, 'turnover': 0.25, 'intraday': 0.25, 'overnight': 0.25, 'up_shadow': 0.25, 'barra_residual_volatility': 0.25, 'fa_np_yoy': 0.25, 'barra_leverage': 0.25}
```

**LLM 引导(A角 70代)**: 调用3次, 解析通过45条, 引导位使用45条
> 日内振幅相对换手率的异常放大（振幅未被成交充分解释）反映知情交易者隐蔽吸筹，此类个股未来5日截面收益更高，且该效应在隔夜跳空温和、上影线受抑时更纯净。


**LLM 候选审查(B角 70代)**: 深判 5 个, KILL 5 个(剔除出 L2 费后回测)
- KILL `max(max(barra_residual_volatility, ts_rank60(sub(barra_residual_volatility, ts_rank200(ts_rank60(ts_std200(cs_rank(barra_residual_volatility))))))), ts_rank60(ts_std200(cs_rank(corr100(ts_rank20(fa_ocf_yoy), ts_std60(barra_size))))))`
  > 理由: 多层同源波动率嵌套+窗口堆砌，含尺度相减，经济含义拼凑难解释
- KILL `max(barra_residual_volatility, div(cs_scale(ts_std100(max(barra_residual_volatility, ts_rank60(ts_std200(cs_rank(barra_residual_volatility)))))), barra_liquidity))`
  > 理由: 多层嵌套同源残差波动率自比，窗口60/100/200冗余，经济含义拼凑难解释
- KILL `max(barra_residual_volatility, ts_rank60(ts_std200(div(barra_non_linear_size, barra_liquidity))))`
  > 理由: 非线性市值除流动性再取波动率排名，含义拼凑，与残差波动率取max冗余，难解释
- KILL `max(max(barra_residual_volatility, div(barra_residual_volatility, turnover)), ts_rank60(cs_scale(ts_std100(max(barra_residual_volatility, max(max(barra_residual_volatility, div(barra_residual_volatility, turnover)), ts_rank60(cs_scale(ts_std100(max(barra_residual_volatility, ts_rank60(ts_std200(cs_rank(barra_residual_volatility)))))))))))))`
  > 理由: 残差波动率与换手率多层嵌套自引用，窗口60/100/200堆叠，无清晰经济含义，过拟合冗余
- KILL `max(max(barra_residual_volatility, div(barra_residual_volatility, turnover)), ts_rank60(cs_scale(barra_liquidity)))`
  > 理由: 残差波动率除以换手率再取max，量纲拼凑无经济含义，且与流动性因子同源冗余


**AI 审查(DeepSeek deepseek-v4-flash, 2s)**:

> (1)病根:叶子被barra_residual_volatility单点垄断(占比100%),信号同质化导致L2普遍Calmar弱、换手高,而非稳定性不足。
> 
> (2)压权重到0.25对症;min_stab+0.10无效甚至有害——stab_med已0.906、stab_lt50=0,瓶颈是Calmar不是稳定度,加码只会误杀;交叉+15%与加深depth方向对但会放大同质叶子,需先破垄断;扰动/引导/随机固定15/20/15与"交叉≥10%合计50%"自洽,无冲突。
> 
> (3)mix=[0.25,0.35,0.15,0.15,0.10] depth=[3,4,4] min_stab=0.70 decorr=0.75。理由:提变异与decorr强制换字段破垄断,降min_stab避免误杀,交叉略降防同质放大。

## 第 71 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 21 | 0.057 | 0.075 | 0.885 | 0.000 | 1.000 | 1.000 | 5 | 0.286 | 21 | 2 | 0.104 | 0.895 | 0.368 | 0.947 | 0.632 | 0.000 | 0.190 |

叶子使用: {'barra_residual_volatility': 21, 'barra_liquidity': 14, 'barra_non_linear_size': 12, 'turnover': 6, 'fa_np_margin': 4, 'barra_comovement': 3}

**B角建议(下一代策略)**:
- 叶子[barra_residual_volatility]占比100%过高 -> 权重压到0.25, 逼引擎换字段
- L2中89%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 配比护栏: 变异/交叉各≥10%且合计50%重归一化, 扰动/引导/随机固定15/20/15(中金规格) -> mix=[0.1, 0.4, 0.15, 0.2, 0.15]

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 4]  min_stab=0.75  decorr=0.65  fsa_th=0.15  bank_skel_max=1
leaf_w={'volume': 0.25, 'turn_ratio': 0.25, 'turnover': 0.25, 'intraday': 0.25, 'overnight': 0.25, 'up_shadow': 0.25, 'barra_residual_volatility': 0.25, 'fa_np_yoy': 0.25, 'barra_leverage': 0.25}
```

**LLM 引导(A角 71代)**: 调用3次, 解析通过40条, 引导位使用40条
> 在换手率与日内振幅放大的环境下，隔夜跳空溢价与价量背离所隐含的短期错误定价，会被资金流大单方向与波动结构（残差波动/杠杆暴露）修正，从而预测未来5日截面收益。


**LLM 候选审查(B角 71代)**: 深判 5 个, KILL 5 个(剔除出 L2 费后回测)
- KILL `max(max(barra_residual_volatility, div(barra_residual_volatility, barra_liquidity)), ts_rank60(cs_scale(ts_std100(max(barra_residual_volatility, ts_rank60(ts_std200(cs_rank(barra_liquidity))))))))`
  > 理由: 残差波动率与流动性多层嵌套自引用，窗口60/100/200堆叠，无清晰经济机制，过拟合冗余
- KILL `max(barra_residual_volatility, div(min(barra_non_linear_size, fa_ocf_yoy), barra_liquidity))`
  > 理由: 多字段量纲混杂相除取极值，无明确量价行为，属数学拼凑
- KILL `max(max(barra_residual_volatility, ts_rank60(sub(barra_residual_volatility, ts_rank200(ts_rank60(ts_std200(ts_std100(barra_residual_volatility))))))), ts_rank60(ts_std200(cs_rank(turnover))))`
  > 理由: 多层同源ts_std/ts_rank嵌套冗余，含turnover老故事，参数堆砌难解释
- KILL `max(max(barra_residual_volatility, div(max(barra_residual_volatility, ts_rank60(ts_std200(cs_rank(barra_non_linear_size)))), barra_liquidity)), barra_non_linear_size)`
  > 理由: 纯Barra风格暴露拼凑，嵌套max/div无经济机制，属数学巧合冗余结构
- KILL `max(barra_residual_volatility, div(mul(barra_non_linear_size, barra_comovement), barra_liquidity))`
  > 理由: Barra风险因子拼凑，非线性市值乘联动除流动性再取max，无明确量价机制，属数学巧合


**AI 审查(DeepSeek deepseek-flash, 2s)**:

> (1)病根:叶子被barra_residual_volatility垄断(占比100%),深度同质化导致L1高IC但L2 Calmar/换手全崩,是典型"单因子过拟合+结构塌缩"。
> 
> (2)点评:压权重到0.25对症,但仅压权重不封字段,引擎仍会绕回;交叉+15%与深度加深会加剧同质化,反而恶化Calmar;扰动/引导/随机固定15/20/15与"交叉+15%"叠加后实际交叉被稀释,护栏自相矛盾;min_stab=0.75偏松,会放行低稳样本。
> 
> (3)建议:mix=[0.2,0.25,0.15,0.25,0.15],depth=[2,3,3],min_stab=0.85,decorr=0.75。理由:降深度+提引导+强去相关,才能逼出异质叶子、修复L2弱信号。

## 第 72 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 21 | 0.049 | 0.075 | 0.903 | 0.000 | 0.619 | 1.000 | 18 | 0.143 | 21 | 2 | 0.113 | 1.000 | 0.368 | 0.947 | 0.579 | 0.000 | 0.476 |

叶子使用: {'barra_residual_volatility': 13, 'barra_liquidity': 9, 'barra_non_linear_size': 6, 'mf_x_bqty': 3, 'fa_np_margin': 3, 'turnover': 2}

**B角建议(下一代策略)**:
- 叶子[barra_residual_volatility]占比62%过高 -> 权重压到0.25, 逼引擎换字段
- L2中100%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 配比护栏: 变异/交叉各≥10%且合计50%重归一化, 扰动/引导/随机固定15/20/15(中金规格) -> mix=[0.1, 0.4, 0.15, 0.2, 0.15]

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 4]  min_stab=0.75  decorr=0.65  fsa_th=0.15  bank_skel_max=1
leaf_w={'volume': 0.25, 'turn_ratio': 0.25, 'turnover': 0.25, 'intraday': 0.25, 'overnight': 0.25, 'up_shadow': 0.25, 'barra_residual_volatility': 0.25, 'fa_np_yoy': 0.25, 'barra_leverage': 0.25}
```

**LLM 引导(A角 72代)**: 调用3次, 解析通过42条, 引导位使用42条
> 在换手活跃的日内博弈中，主动资金流的方向与强度若与价格短期变动形成背离（大单净买入占优但价格滞涨、或中小单抛压而超大单承接），这种量额不匹配的微观结构失衡会在未来5日截面收益上正向修复，且该修复在低残差波动、高景气（盈利同比为正）的股票中更显著。


**LLM 候选审查(B角 72代)**: 深判 5 个, KILL 4 个(剔除出 L2 费后回测)
- KILL `ts_rank200(ts_std20(ts_std60(mf_x_bqty)))`
  > 理由: mf_x_bqty含义不明，三层嵌套同源ts_std+ts_rank纯数学堆叠，无清晰量价机制，疑似参数海捞针
- KILL `sub(ts_mean5(ts_delta120(barra_liquidity)), ts_std60(corr200(mf_s_bqty, mf_x_buy)))`
  > 理由: 流动性长期变化减资金流相关性波动，两分量异源拼凑，经济含义不清，窗口冗余
- KILL `mul(max(barra_residual_volatility, ts_rank60(ts_std200(max(barra_residual_volatility, corr100(barra_non_linear_size, abs(max(barra_residual_volatility, barra_residual_volatility))))))), abs(turnover))`
  > 理由: 残差波动率与成交额原始尺度相乘，含义拼凑且嵌套冗余，无清晰量价机制
- KILL `max(min(corr200(low, mf_l_buy), div(mf_m_bqty, fa_ocf_yoy)), add(fa_lev, corr20(hl_ratio, vwap)))`
  > 理由: 多字段跨族嵌套拼凑，无统一量价机制，属参数海捞针


**AI 审查(DeepSeek deepseek-flash, 2s)**:

> (1)病根在叶子塌缩：barra_residual_volatility占62%，L1头部几乎全是它的自嵌套，IC高但同源，L2全灭于Calmar弱。
> 
> (2)压权重到0.25对症；交叉+15%方向对但mix里交叉已0.4，再加会挤掉变异，且扰动/引导/随机固定值使护栏形同虚设；depth加深到4对负年数无效反增过拟合；decorr=0.65偏松，压不住同源。
> 
> (3)建议mix=[0.25,0.30,0.15,0.15,0.15]，depth=[3,3,4]，min_stab=0.80，decorr=0.80。理由：先破叶子垄断、收紧去相关，再谈深度。

## 第 73 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 33 | 0.049 | 0.075 | 0.882 | 0.000 | 1.000 | 1.000 | 1 | 0.364 | 30 | 0 | 0.034 | 1.000 | 0.367 | 0.967 | 0.633 | 0.000 | 0.633 |

叶子使用: {'barra_residual_volatility': 33, 'barra_liquidity': 23, 'barra_non_linear_size': 12, 'mf_l_sqty': 11, 'true_range': 11, 'mf_l_bqty': 8}

**B角建议(下一代策略)**:
- 叶子[barra_residual_volatility]占比100%过高 -> 权重压到0.25, 逼引擎换字段
- L2中100%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 本代0通过 -> 深度放宽到3~5, 探索更复杂结构
- 配比护栏: 变异/交叉各≥10%且合计50%重归一化, 扰动/引导/随机固定15/20/15(中金规格) -> mix=[0.1, 0.4, 0.15, 0.2, 0.15]

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 5]  min_stab=0.75  decorr=0.65  fsa_th=0.15  bank_skel_max=1
leaf_w={'volume': 0.25, 'turn_ratio': 0.25, 'turnover': 0.25, 'intraday': 0.25, 'overnight': 0.25, 'up_shadow': 0.25, 'barra_residual_volatility': 0.25, 'fa_np_yoy': 0.25, 'barra_leverage': 0.25}
```

**LLM 引导(A角 73代)**: 调用3次, 解析通过45条, 引导位使用45条
> 在换手与日内波动放大的环境下，隔夜跳空方向与日内真实承接方向出现背离时，未来5日截面收益由‘资金承接强度’主导：即隔夜高开但日内主动买盘未能同步放大（或隔夜低开但日内主动卖盘衰竭）的股票，短期存在跳空回补/反转溢价；同时该溢价受个股残差波动与杠杆风格调节。


**LLM 候选审查(B角 73代)**: 深判 5 个, KILL 5 个(剔除出 L2 费后回测)
- KILL `div(mul(cs_rank(barra_residual_volatility), ts_max20(mf_l_sqty)), corr100(sub(mf_m_bqty, mf_l_bqty), ln_volume))`
  > 理由: 分子量价尺度相除、分母相关量纲混乱，经济含义拼凑，属数学巧合
- KILL `div(mul(div(barra_residual_volatility, ts_rank60(sub(barra_residual_volatility, sub(max(barra_residual_volatility, div(fa_np_margin, barra_liquidity)), barra_liquidity)))), ts_max20(mf_l_sqty)), corr100(sub(mf_m_bqty, mf_l_bqty), ln_volume))`
  > 理由: 多层嵌套拼凑残差波动与买卖量，含对数成交量，经济含义混乱难解释，过拟合嫌疑
- KILL `add(max(barra_residual_volatility, ts_rank60(sub(barra_residual_volatility, ts_rank200(ts_rank60(ts_std200(ts_std100(barra_residual_volatility))))))), ts_rank60(ts_std200(cs_rank(mf_x_bqty))))`
  > 理由: 多层同源波动率嵌套+量字段拼凑，无清晰经济含义，冗余过拟合
- KILL `div(mul(mul(true_range, barra_residual_volatility), ts_max20(corr20(max(barra_residual_volatility, ts_rank60(ts_std200(cs_rank(barra_non_linear_size)))), max(barra_residual_volatility, div(min(barra_non_linear_size, barra_liquidity), barra_liquidity))))), corr100(sub(mf_m_bqty, mf_l_bqty), ln_volume))`
  > 理由: 多层嵌套同源波动/流动性算子拼凑，含除零风险，经济含义不可解释，属参数海捞针
- KILL `div(mul(mul(true_range, barra_residual_volatility), ts_max20(mul(mul(true_range, barra_residual_volatility), ts_max20(mf_l_sqty)))), corr100(sub(mf_m_bqty, mf_l_bqty), ln_volume))`
  > 理由: 多层同源波动/量算子嵌套冗余，分母量价相关含义拼凑，难解释易过拟合


**AI 审查(DeepSeek deepseek-flash, 2s)**:

> (1)病根:叶子被barra_residual_volatility垄断(占比100%),信号同源导致L2全灭,不是深度不够而是多样性枯竭。
> 
> (2)压权重到0.25对症;交叉+15%方向对但幅度不足;深度放宽到3~5无效且有害——L1已有复杂嵌套,病在字段不在结构;扰动/引导/随机固定15/20/15与"交叉+15%"冲突,重归一化后交叉实际被稀释;min_stab=0.75偏松,会放行stab=0.76的弱苗。
> 
> (3)建议:mix=[0.15,0.35,0.15,0.2,0.15],depth=[2,3,4],min_stab=0.85,decorr=0.75。理由:先保稳定与去相关,把探索预算从"加深"转向"换字段",交叉略降避免同源重组。

## 第 74 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 42 | 0.025 | 0.057 | 0.938 | 0.000 | 0.286 | 1.000 | 0 | 0.214 | 30 | 1 | 0.098 | 0.931 | 0.069 | 0.897 | 0.621 | 0.310 | 0.367 |

叶子使用: {'barra_residual_volatility': 12, 'barra_liquidity': 11, 'mf_l_sqty': 10, 'mf_m_buy': 9, 'true_range': 8, 'ln_volume': 6}

**B角建议(下一代策略)**:
- L2中93%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 配比护栏: 变异/交叉各≥10%且合计50%重归一化, 扰动/引导/随机固定15/20/15(中金规格) -> mix=[0.1, 0.4, 0.15, 0.2, 0.15]

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 4]  min_stab=0.75  decorr=0.65  fsa_th=0.15  bank_skel_max=1
leaf_w={'volume': 0.25, 'turn_ratio': 0.25, 'turnover': 0.25, 'intraday': 0.25, 'overnight': 0.25, 'up_shadow': 0.25, 'barra_residual_volatility': 0.25, 'fa_np_yoy': 0.25, 'barra_leverage': 0.25}
```

**LLM 引导(A角 74代)**: 调用3次, 解析通过46条, 引导位使用46条
> 资金流内部结构性失衡（超大单与中小单方向背离、主动净买入占比与价格变化不匹配）比总量资金流更能预测未来5日截面收益，因为知情资金往往通过大单定向吸筹而散户小单反向交易，这种背离在量价上尚未被价格充分反映。


**LLM 候选审查(B角 74代)**: 深判 5 个, KILL 3 个(剔除出 L2 费后回测)
- KILL `sub(ts_mean150(sub(ts_mean150(overnight), min(max(barra_residual_volatility, div(barra_residual_volatility, barra_liquidity)), ts_rank60(cs_scale(ts_std100(barra_residual_volatility)))))), sub(max(barra_residual_volatility, div(sub(max(barra_residual_volatility, div(fa_np_margin, barra_liquidity)), barra_liquidity), barra_liquidity)), corr100(barra_non_linear_size, abs(max(barra_residual_volatility, corr100(barra_non_linear_size, abs(max(barra_residual_volatility, barra_residual_volatility))))))))`
  > 理由: 嵌套冗余、参数拼凑，无清晰量价含义，属数学巧合
- KILL `neg(mul(min(max(barra_residual_volatility, div(barra_residual_volatility, barra_liquidity)), ts_rank60(cs_scale(ts_std100(ts_std100(barra_residual_volatility))))), cs_rank(mul(ts_max20(min(max(barra_residual_volatility, div(barra_residual_volatility, barra_liquidity)), ts_rank60(cs_scale(ts_std100(ts_std100(barra_residual_volatility)))))), corr100(true_range, mf_m_buy)))))`
  > 理由: 残差波动率与流动性相除再嵌套多层同源算子，含义拼凑冗余，难解释
- KILL `corr60(low, ts_rank100(ts_delay1(barra_momentum)))`
  > 理由: 低点与动量排名做相关，经济含义拼凑，且经延迟排名嵌套冗余，属参数海捞针


**AI 审查(DeepSeek deepseek-flash, 2s)**:

> (1)病根:叶子被barra_residual_volatility等少数变量垄断,表达式过度嵌套同源,IC虚高但L2 Calmar/负年普遍不达标,是"同质过拟合"而非信号不足。
> 
> (2)交叉+15%对症但不够:同源叶子交叉仍产同质后代,需先强制换叶。深度加深有害,当前已是ts_rank套ts_std套ts_mean的深链,再深只会更过拟合、更脆。扰动/引导/随机固定值合理。护栏"变异≥10%"与"交叉40%"叠加会挤压探索,且与"深度加深"目标冲突。
> 
> (3)我建议mix=[0.25,0.25,0.15,0.2,0.15],depth=[2,3,3],min_stab=0.8,decorr=0.75。理由:提变异、降深度、抬去相关,先破叶子垄断再谈交叉。

## 第 75 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | fail_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 26 | 0.025 | 0.043 | 0.991 | 0.000 | 0.346 | 0.885 | 2 | 0.346 | 26 | 6 | 0.100 | 1.000 | 0.000 | 0.850 | 0.400 | 0.450 | 0.038 |

叶子使用: {'mf_l_sqty': 9, 'ln_volume': 7, 'true_range': 5, 'mf_s_bqty': 4, 'amplitude': 4, 'mf_l_bqty': 4}

**B角建议(下一代策略)**:
- L2中100%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 配比护栏: 变异/交叉各≥10%且合计50%重归一化, 扰动/引导/随机固定15/20/15(中金规格) -> mix=[0.1, 0.4, 0.15, 0.2, 0.15]

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 4]  min_stab=0.75  decorr=0.65  fsa_th=0.15  bank_skel_max=1
leaf_w={'volume': 0.25, 'turn_ratio': 0.25, 'turnover': 0.25, 'intraday': 0.25, 'overnight': 0.25, 'up_shadow': 0.25, 'barra_residual_volatility': 0.25, 'fa_np_yoy': 0.25, 'barra_leverage': 0.25}
```

**LLM 引导(A角 75代)**: 调用3次, 解析通过43条, 引导位使用43条
> 在换手与波动结构给定的前提下，日内形态（上影线/振幅）与隔夜跳空的背离，叠加主动资金流失衡，能刻画‘日内被压制的抛压/承接’这一微观机制，从而预测未来5日截面收益。


**LLM 候选审查(B角 75代)**: 深判 5 个, KILL 4 个(剔除出 L2 费后回测)
- KILL `ts_max100(ts_std200(corr200(mf_l_sqty, fa_roe)))`
  > 理由: ROE与成交量相关性再取波动极值，经济含义拼凑，窗口嵌套冗余，疑参数海捞
- KILL `ts_mean150(corr20(cs_scale(div(neg(ts_std200(mf_x_sqty)), ts_mean20(corr100(ln_volume, mf_l_sqty)))), mf_s_sqty))`
  > 理由: 多层嵌套同源量价算子，窗口参数冗余，经济含义拼凑难解释，过拟合嫌疑
- KILL `mul(ts_max20(max(max(barra_residual_volatility, div(barra_residual_volatility, barra_liquidity)), ts_rank60(cs_scale(ts_std100(barra_residual_volatility))))), div(neg(ts_std200(mf_x_sqty)), ts_mean20(corr100(ln_volume, mf_l_sqty))))`
  > 理由: 多层嵌套同源波动率算子冗余，含成交量原始尺度相减，经济含义拼凑难解释
- KILL `ts_mean10(sub(fa_rev_yoy, ts_max100(barra_non_linear_size)))`
  > 理由: 营收增速与市值非线性项相减，量纲与含义拼凑，无清晰量价机制，属数学巧合


**AI 审查(DeepSeek deepseek-flash, 2s)**:

> (1)病根:IC天花板0.043、叶子高度集中在少数量价字段,信号弱且同质,L2全卡Calmar只是表征。
> 
> (2)交叉+15%对症但过头:同源叶子交叉难出增量,反易放大共线性;深度加深会加剧过拟合与negyear(已0.85)。护栏把交叉提到0.4、变异压到0.1,与"需新信息"矛盾;扰动/引导/随机固定值属拍脑袋,无诊断支撑。min_stab=0.75偏松,会放噪声。
> 
> (3)mix=[0.25,0.2,0.15,0.25,0.15],depth=[2,3,3],min_stab=0.9,decorr=0.5。理由:提变异与引导换新字段、压交叉与深度控过拟合,decorr收紧保多样。

## 第 76 代 (B角诊断)

| n_l1 | ic_med | ic_max | stab_med | stab_lt50 | leaf_conc | struct_div | fam_blocked | known_ratio | n_l2 | n_pass | ex_max | gate_min_calmar | gate_min_pool_calmar | fail_calmar | fail_calmar_neg | fail_pool_calmar | fail_turn | fail_negyear | fail_lastyr | fail_ic | seg_kill | st_l2_lncap | st_l2_lnamt | st_l2_lntr | st_l2_lnpx | st_l1_lncap | st_l1_lnamt | st_l1_lntr | st_l1_lnpx |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 8 | 0.021 | 0.029 | 0.994 | 0.000 | 0.375 | 1.000 | 20 | 0.125 | 8 | 0 | 0.057 | 0.000 | 0.150 | 0.000 | 0.000 | 0.875 | 0.000 | 1.000 | 0.625 | 0.375 | 0.125 | 0.259 | 0.274 | 0.130 | 0.213 | 0.259 | 0.274 | 0.130 | 0.213 |

叶子使用: {'mf_l_sell': 3, 'low': 2, 'mf_x_bqty': 2, 'mf_s_bqty': 2, 'barra_non_linear_size': 1, 'fa_rev_yoy': 1}

**B角建议(下一代策略)**:
- 【r5_calmar_cross】L2中88%因Calmar不足[池口径: 任一池 Calmar > 0.15] -> 交叉+15%, 深度加深
- 配比护栏: 变异/交叉各≥10%且合计50%重归一化, 扰动/引导/随机固定15/20/15(中金规格) -> mix=[0.1, 0.4, 0.15, 0.2, 0.15]

```
mix=[0.1, 0.4, 0.15, 0.2, 0.15]  depth=[3, 4, 4]  min_stab=0.75  decorr=0.65  fsa_th=0.15  bank_skel_max=1
leaf_w={'volume': 0.25, 'turn_ratio': 0.25, 'turnover': 0.25, 'intraday': 0.25, 'overnight': 0.25, 'up_shadow': 0.25, 'barra_residual_volatility': 0.25, 'fa_np_yoy': 0.25, 'barra_leverage': 0.25}
```

**规则动作留痕**:
- `r5_calmar_cross` L2 多因 Calmar 不足 -> 交叉+15% / 深度加深 —— 施加于第 [77] 代

**LLM 引导(A角 76代)**: 调用3次, 解析通过48条, 引导位使用48条
> 在隔夜跳空与日内收益之间，短期相对长期的跳空溢价衰减/反转，配合资金流失衡与风格暴露的背离，能预测未来5日截面收益。


**LLM 候选审查(B角 76代)**: 深判 5 个, KILL 4 个(剔除出 L2 费后回测)
- KILL `ts_rank200(ts_mean60(corr60(mf_l_buy, mf_l_sell)))`
  > 理由: mf_l_buy与mf_l_sell同源资金流字段相减再相关，含义拼凑且嵌套冗余，无清晰量价机制
- KILL `corr200(volume, mf_x_bqty)`
  > 理由: mf_x_bqty含义不明，与volume做200日相关无清晰量价机制，疑似拼凑
- KILL `ema26(ts_std60(cs_demean(neg(low))))`
  > 理由: 对负低价做截面去均值再时序波动，经济含义不明，纯数学拼凑
- KILL `ts_min100(sub(div(ts_delta60(corr100(neg(low), barra_leverage)), ts_min100(corr60(amplitude, mf_l_sqty))), corr200(ts_mean5(cs_rank(ln_mktcap)), ts_delta120(mf_l_bqty))))`
  > 理由: 多层嵌套同源相关算子，窗口参数堆砌，经济含义拼凑难解释，过拟合嫌疑


**AI 审查(DeepSeek deepseek-flash, 2s)**:

> (1)病根:IC天花板太低(中位0.021、最大0.029),L2全军覆没于负年份(100%)与近一年失效(62.5%),是信号本身弱且不稳,不是Calmar门槛问题。
> 
> (2)r5_calmar_cross不对症:Calmar低是弱IC的结果而非原因,加交叉+加深只会放大过拟合;且mix交叉0.4挤压变异到0.1,探索多样性下降,与"深度加深"叠加更易过拟合。护栏本身自洽,但方向错。
> 
> (3)建议 mix=[0.25,0.2,0.15,0.25,0.15],depth=[2,3,3],min_stab=0.85,decorr=0.7:先保探索与去相关,压深度防过拟合,提稳定性门槛筛真信号。
> 
> 否决: r5_calmar_cross

**⚖️ 规则动作否决（机器读取）**: `r5_calmar_cross`（L2 多因 Calmar 不足 -> 交叉+15% / 深度加深）
