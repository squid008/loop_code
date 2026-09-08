
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
