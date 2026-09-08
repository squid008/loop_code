
## 第 4 代 (B角诊断)

| 指标 | 值 |
|---|---|
| n_l1 | 28 |
| ic_med | 0.052 |
| ic_max | 0.067 |
| stab_med | 0.912 |
| stab_lt50 | 0.000 |
| leaf_conc | 0.429 |
| struct_div | 0.929 |
| known_ratio | 0.536 |
| n_l2 | 25 |
| n_pass | 0 |
| ex_max | 0.032 |
| fail_calmar | 1.000 |
| fail_turn | 0.480 |
| fail_negyear | 0.960 |
| fail_lastyr | 0.320 |
| fail_ic | 0.000 |

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

| 指标 | 值 |
|---|---|
| n_l1 | 41 |
| ic_med | 0.058 |
| ic_max | 0.071 |
| stab_med | 0.914 |
| stab_lt50 | 0.000 |
| leaf_conc | 0.634 |
| struct_div | 0.902 |
| known_ratio | 0.488 |
| n_l2 | 25 |
| n_pass | 0 |
| ex_max | 0.038 |
| fail_calmar | 1.000 |
| fail_turn | 0.320 |
| fail_negyear | 1.000 |
| fail_lastyr | 0.280 |
| fail_ic | 0.000 |

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

| 指标 | 值 |
|---|---|
| n_l1 | 40 |
| ic_med | 0.063 |
| ic_max | 0.075 |
| stab_med | 0.920 |
| stab_lt50 | 0.000 |
| leaf_conc | 0.775 |
| struct_div | 0.925 |
| known_ratio | 0.250 |
| n_l2 | 25 |
| n_pass | 0 |
| ex_max | 0.030 |
| fail_calmar | 1.000 |
| fail_turn | 0.440 |
| fail_negyear | 1.000 |
| fail_lastyr | 0.240 |
| fail_ic | 0.000 |

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

| 指标 | 值 |
|---|---|
| n_l1 | 45 |
| ic_med | 0.066 |
| ic_max | 0.079 |
| stab_med | 0.905 |
| stab_lt50 | 0.000 |
| leaf_conc | 0.911 |
| struct_div | 1.000 |
| known_ratio | 0.400 |
| n_l2 | 30 |
| n_pass | 0 |
| ex_max | 0.063 |
| fail_calmar | 1.000 |
| fail_turn | 0.667 |
| fail_negyear | 0.967 |
| fail_lastyr | 0.233 |
| fail_ic | 0.000 |

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

| 指标 | 值 |
|---|---|
| n_l1 | 44 |
| ic_med | 0.070 |
| ic_max | 0.086 |
| stab_med | 0.903 |
| stab_lt50 | 0.000 |
| leaf_conc | 0.864 |
| struct_div | 0.955 |
| known_ratio | 0.773 |
| n_l2 | 30 |
| n_pass | 1 |
| ex_max | 0.063 |
| fail_calmar | 1.000 |
| fail_turn | 0.862 |
| fail_negyear | 0.931 |
| fail_lastyr | 0.310 |
| fail_ic | 0.000 |

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

| 指标 | 值 |
|---|---|
| n_l1 | 28 |
| ic_med | 0.077 |
| ic_max | 0.085 |
| stab_med | 0.862 |
| stab_lt50 | 0.000 |
| leaf_conc | 0.857 |
| struct_div | 0.964 |
| known_ratio | 0.679 |
| n_l2 | 28 |
| n_pass | 0 |
| ex_max | 0.064 |
| fail_calmar | 1.000 |
| fail_turn | 0.964 |
| fail_negyear | 0.893 |
| fail_lastyr | 0.357 |
| fail_ic | 0.000 |

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

| 指标 | 值 |
|---|---|
| n_l1 | 29 |
| ic_med | 0.073 |
| ic_max | 0.086 |
| stab_med | 0.852 |
| stab_lt50 | 0.000 |
| leaf_conc | 0.862 |
| struct_div | 1.000 |
| known_ratio | 0.690 |
| n_l2 | 29 |
| n_pass | 3 |
| ex_max | 0.065 |
| fail_calmar | 1.000 |
| fail_turn | 0.962 |
| fail_negyear | 0.846 |
| fail_lastyr | 0.115 |
| fail_ic | 0.000 |

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

| 指标 | 值 |
|---|---|
| n_l1 | 13 |
| ic_med | 0.046 |
| ic_max | 0.075 |
| stab_med | 0.943 |
| stab_lt50 | 0.000 |
| leaf_conc | 0.846 |
| struct_div | 1.000 |
| known_ratio | 0.077 |
| n_l2 | 13 |
| n_pass | 4 |
| ex_max | 0.060 |
| fail_calmar | 1.000 |
| fail_turn | 0.333 |
| fail_negyear | 0.667 |
| fail_lastyr | 0.222 |
| fail_ic | 0.000 |

叶子使用: {'turn_ratio': 11, 'close': 4, 'volume': 4, 'ret': 3, 'open': 3, 'turnover': 1}

**B角建议(下一代策略)**:
- 叶子[turn_ratio]占比85%过高 -> 权重压到0.25, 逼引擎换字段
- L2中100%因Calmar不足(信号弱) -> 交叉+15%, 深度加深

```
mix=[0.022, 0.45, 0.15, 0.15, 0.2]  depth=[3, 4, 4]  min_stab=0.75  decorr=0.65
leaf_w={'volume': 0.25, 'turn_ratio': 0.25}
```

## 第 12 代 (B角诊断)

| 指标 | 值 |
|---|---|
| n_l1 | 18 |
| ic_med | 0.029 |
| ic_max | 0.075 |
| stab_med | 0.895 |
| stab_lt50 | 0.000 |
| leaf_conc | 0.833 |
| struct_div | 1.000 |
| known_ratio | 0.111 |
| n_l2 | 18 |
| n_pass | 0 |
| ex_max | 0.058 |
| fail_calmar | 1.000 |
| fail_turn | 0.278 |
| fail_negyear | 0.889 |
| fail_lastyr | 0.222 |
| fail_ic | 0.000 |

叶子使用: {'turn_ratio': 15, 'volume': 6, 'close': 6, 'open': 5, 'ret': 4, 'turnover': 2}

**B角建议(下一代策略)**:
- 叶子[turn_ratio]占比83%过高 -> 权重压到0.25, 逼引擎换字段
- L2中100%因Calmar不足(信号弱) -> 交叉+15%, 深度加深
- 本代0通过 -> 深度放宽到3~5, 探索更复杂结构

```
mix=[0.016, 0.45, 0.15, 0.15, 0.2]  depth=[3, 4, 5]  min_stab=0.75  decorr=0.65  fsa_th=0.15  bank_skel_max=1
leaf_w={'volume': 0.25, 'turn_ratio': 0.25}
```
