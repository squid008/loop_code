# 精选因子池（L3）

> **派生视图**，由 `python tools/cross_pool_review.py` 生成 —— 可随时重建。
> 与 `docs/factor_library_crosspool.md`（**忠实镜像**各池库）**定位不同**：
> 本文件是**过了双闸门的精选清单**，供下游（组合/回测/看板）直接使用。

## 下游使用须知（先读这段再用）

1. **必须乘 `sign`**（见「精选因子明细」）：引擎求值时对 `sign<0` 的因子**取负**；不乘，方向就反了，组合会反向选股。
2. **本表的「剥风格」是评估口径，不是 `facs/` 里的值** —— `facs/<xx>/<name>/values.h5` 存的是**原始因子值**（没有做过中性化）。
   - 剥风格的定义：**把因子对 `lncap`（市值）+ `lnamt`（成交额）做截面秩中性化，再重跑回测**（引擎 `loop_engine.py` 的 `--strip_style`）。
   - 所以：**要做到本表的绩效，下游必须自己实现这一步**（取残差后再排序）；直接用原始值，绩效与风险回撤都对不上（例如 `F33`：未剥日频回撤约 −19%，剥后只有 −10%）。
   - **不能用 `values_q.h5`（uint8 快查副本）做这件事** —— 它丢了原始值（只留截面秩），只能做秩类运算，做不了中性化/回归。
3. **本表不含「池内（300/500/1000）」结论**：这些因子**基本没在池内测过**（`--pool_obs` 是 2026-09-12 才加的，而它们更早入库），池内表现需要另测。
   （已知的外部实测结论：它们在 **300 内全员失效**、500 内只有 `F07` 勉强可用，**不要直接搬进成分内**。）

## 双闸门（用户 2026-09-14 拍板）

1. **剥风格档**：只有「A 独立有效」的因子才能进 —— 也就是「把 `lncap`（市值）+ `lnamt`（成交额）剥掉之后，Calmar 仍然 ≥ 0.30」。
   库内实测约 **44% 是纯风格**（剥完就转负），这一刀砍掉近一半。
2. **正交去重**：把入池的因子两两比「因子值截面秩相关」，**≥ 0.70 的算同一类**，每组只留剥风格 Calmar 最高的一个（像的只留最好的，不像的全都留下）。

> 为什么闸门放在这一层、而不是放在**入库**：如果入库就拦，`bank` 就不增长了，
> 而 `--decorr` / `--dup_ex_corr` 正是拿 `bank` 当对照集的，对照集变弱，引擎更容易重复挖，又被拦，就成了死循环。
> 所以：**`bank` 照旧增长（它是对照集，越大去重越强）**，另设本精选层。

## 精选清单（8 个）

> ★ **表达式是完整的**（不截断）—— 本文件可直接给下游用，不必回各池库翻。
> 需要**可复制的全文** / `sign` / h5 路径 → 见下方「[精选因子明细](#精选因子明细可直接复制使用)」。

| # | 因子 | 剥风格档 | 剥Calmar | 剥超额 | 原Calmar | 表达式（完整） |
|---|---|---|---|---|---|---|
| 1 | `F07` | **A** | **1.228** | +5.3% | 0.820 | `ts_std100(mul(cs_demean(hl_ratio), ts_mean5(cs_demean(turn_ratio))))` |
| 2 | `F04_300` | **A** | **0.649** | +5.1% | 0.727 | `ts_mean10(ema60(corr200(fa_sell_exp, cs_rank(ema12(cs_rank(ema12(ema12(mktcap))))))))` |
| 3 | `F35` | **A** | **0.604** | +2.6% | 1.077 | `mul(ts_max20(max(max(barra_residual_volatility, div(barra_residual_volatility, barra_liquidity)), ts_rank60(cs_scale(ts_std100(barra_residual_volatility))))), corr100(true_range, mf_m_buy))` |
| 4 | `F25` | **A** | **0.551** | +3.9% | 1.295 | `max(ts_mean150(corr100(ts_rank100(cs_rank(barra_leverage)), ts_min20(cs_rank(barra_leverage)))), barra_residual_volatility)` |
| 5 | `F07_1000` | **A** | **0.519** | +6.3% | 0.506 | `ts_mean200(mul(add(sub(overnight, barra_beta), ts_mean60(barra_residual_volatility)), ts_max20(ts_mean60(barra_size))))` |
| 6 | `F33` | **A** | **0.400** | +3.9% | 0.847 | `ts_delta120(add(ts_max20(ts_max100(barra_non_linear_size)), div(cs_rank(barra_beta), ts_std150(mf_x_bqty))))` |
| 7 | `F21` | **A** | **0.351** | +2.2% | 0.868 | `max(add(barra_residual_volatility, barra_leverage), max(ts_min20(cs_rank(div(fa_ocf_yoy, fa_gm))), barra_residual_volatility))` |
| 8 | `F05_500` | **A** | **0.349** | +2.3% | 0.802 | `corr100(mul(mf_m_sqty, ts_std60(mf_x_buy)), mf_m_sqty)` |

---

## 精选因子明细（可直接复制使用）

> 每个精选因子一节：**完整表达式** + **`sign`** + **因子值 h5 路径** + 各项指标。
> ⚠ **`sign` 必须用**：因子值要乘 `sign` 才是"越大越好"的方向（引擎求值时就是这个约定；不乘 ⇒ **方向反了**，组合会反向选股）。

### 1. `F07`

**完整表达式**
```
ts_std100(mul(cs_demean(hl_ratio), ts_mean5(cs_demean(turn_ratio))))
```

| 项 | 值 |
|---|---|
| **`sign`（方向，必须乘）** | **-1** |
| 因子值 h5 | `facs/4f/F07/values.h5` |
| 快查副本（uint8，截面秩） | `facs/4f/F07/values_q.h5` |
| 形状 | 3309 日 × 5384 股 |
| 来源 | `lib:all:genNone` |
| 建于 | 2026-09-14 20:44:26 |
| 剥风格判定 | **A 独立有效**（剥掉 lncap+lnamt 后 Calmar 1.228 ≥ 0.30）|
| 剥风格后 Calmar / 超额 | **1.228** / +5.3% |
| 原（未剥）Calmar / 超额 / IC | 0.820 / +6.0% / 0.052 |

### 2. `F04_300`

**完整表达式**
```
ts_mean10(ema60(corr200(fa_sell_exp, cs_rank(ema12(cs_rank(ema12(ema12(mktcap))))))))
```

| 项 | 值 |
|---|---|
| **`sign`（方向，必须乘）** | **1** |
| 因子值 h5 | `facs/11/F04_300/values.h5` |
| 快查副本（uint8，截面秩） | `facs/11/F04_300/values_q.h5` |
| 形状 | 3309 日 × 5384 股 |
| 来源 | `lib:300:genNone` |
| 建于 | 2026-09-20 09:37:45 |
| 剥风格判定 | **A 独立有效**（剥掉 lncap+lnamt 后 Calmar 0.649 ≥ 0.30）|
| 剥风格后 Calmar / 超额 | **0.649** / +5.1% |
| 原（未剥）Calmar / 超额 / IC | 0.727 / +5.9% / 0.010 |

### 3. `F35`

**完整表达式**
```
mul(ts_max20(max(max(barra_residual_volatility, div(barra_residual_volatility, barra_liquidity)), ts_rank60(cs_scale(ts_std100(barra_residual_volatility))))), corr100(true_range, mf_m_buy))
```

| 项 | 值 |
|---|---|
| **`sign`（方向，必须乘）** | **-1** |
| 因子值 h5 | `facs/8e/F35/values.h5` |
| 快查副本（uint8，截面秩） | `facs/8e/F35/values_q.h5` |
| 形状 | 3309 日 × 5384 股 |
| 来源 | `lib:all:genNone` |
| 建于 | 2026-09-14 20:57:40 |
| 剥风格判定 | **A 独立有效**（剥掉 lncap+lnamt 后 Calmar 0.604 ≥ 0.30）|
| 剥风格后 Calmar / 超额 | **0.604** / +2.6% |
| 原（未剥）Calmar / 超额 / IC | 1.077 / +4.6% / 0.037 |

### 4. `F25`

**完整表达式**
```
max(ts_mean150(corr100(ts_rank100(cs_rank(barra_leverage)), ts_min20(cs_rank(barra_leverage)))), barra_residual_volatility)
```

| 项 | 值 |
|---|---|
| **`sign`（方向，必须乘）** | **-1** |
| 因子值 h5 | `facs/d4/F25/values.h5` |
| 快查副本（uint8，截面秩） | `facs/d4/F25/values_q.h5` |
| 形状 | 3309 日 × 5384 股 |
| 来源 | `lib:all:genNone` |
| 建于 | 2026-09-14 20:53:31 |
| 剥风格判定 | **A 独立有效**（剥掉 lncap+lnamt 后 Calmar 0.551 ≥ 0.30）|
| 剥风格后 Calmar / 超额 | **0.551** / +3.9% |
| 原（未剥）Calmar / 超额 / IC | 1.295 / +5.6% / 0.055 |

### 5. `F07_1000`

**完整表达式**
```
ts_mean200(mul(add(sub(overnight, barra_beta), ts_mean60(barra_residual_volatility)), ts_max20(ts_mean60(barra_size))))
```

| 项 | 值 |
|---|---|
| **`sign`（方向，必须乘）** | **1** |
| 因子值 h5 | `facs/20/F07_1000/values.h5` |
| 快查副本（uint8，截面秩） | `facs/20/F07_1000/values_q.h5` |
| 形状 | 3309 日 × 5384 股 |
| 来源 | `lib:1000:genNone` |
| 建于 | 2026-09-14 21:02:55 |
| 剥风格判定 | **A 独立有效**（剥掉 lncap+lnamt 后 Calmar 0.519 ≥ 0.30）|
| 剥风格后 Calmar / 超额 | **0.519** / +6.3% |
| 原（未剥）Calmar / 超额 / IC | 0.506 / +7.0% / 0.017 |

### 6. `F33`

**完整表达式**
```
ts_delta120(add(ts_max20(ts_max100(barra_non_linear_size)), div(cs_rank(barra_beta), ts_std150(mf_x_bqty))))
```

| 项 | 值 |
|---|---|
| **`sign`（方向，必须乘）** | **-1** |
| 因子值 h5 | `facs/93/F33/values.h5` |
| 快查副本（uint8，截面秩） | `facs/93/F33/values_q.h5` |
| 形状 | 3309 日 × 5384 股 |
| 来源 | `lib:all:genNone` |
| 建于 | 2026-09-14 20:56:41 |
| 剥风格判定 | **A 独立有效**（剥掉 lncap+lnamt 后 Calmar 0.400 ≥ 0.30）|
| 剥风格后 Calmar / 超额 | **0.400** / +3.9% |
| 原（未剥）Calmar / 超额 / IC | 0.847 / +11.3% / 0.027 |

### 7. `F21`

**完整表达式**
```
max(add(barra_residual_volatility, barra_leverage), max(ts_min20(cs_rank(div(fa_ocf_yoy, fa_gm))), barra_residual_volatility))
```

| 项 | 值 |
|---|---|
| **`sign`（方向，必须乘）** | **-1** |
| 因子值 h5 | `facs/0a/F21/values.h5` |
| 快查副本（uint8，截面秩） | `facs/0a/F21/values_q.h5` |
| 形状 | 3309 日 × 5384 股 |
| 来源 | `lib:all:genNone` |
| 建于 | 2026-09-14 20:51:29 |
| 剥风格判定 | **A 独立有效**（剥掉 lncap+lnamt 后 Calmar 0.351 ≥ 0.30）|
| 剥风格后 Calmar / 超额 | **0.351** / +2.2% |
| 原（未剥）Calmar / 超额 / IC | 0.868 / +5.5% / 0.053 |

### 8. `F05_500`

**完整表达式**
```
corr100(mul(mf_m_sqty, ts_std60(mf_x_buy)), mf_m_sqty)
```

| 项 | 值 |
|---|---|
| **`sign`（方向，必须乘）** | **-1** |
| 因子值 h5 | `facs/dc/F05_500/values.h5` |
| 快查副本（uint8，截面秩） | `facs/dc/F05_500/values_q.h5` |
| 形状 | 3309 日 × 5384 股 |
| 来源 | `lib:500:genNone` |
| 建于 | 2026-09-14 21:01:53 |
| 剥风格判定 | **A 独立有效**（剥掉 lncap+lnamt 后 Calmar 0.349 ≥ 0.30）|
| 剥风格后 Calmar / 超额 | **0.349** / +2.3% |
| 原（未剥）Calmar / 超额 / IC | 0.802 / +4.0% / 0.009 |

---

## ⚠ 被淘汰（同族重复，**留痕可查**）

淘汰**不是删除** —— 它们仍在各池库里（`factor_library_{pool}.md`），只是不进精选池。
★ 留痕是硬要求（§8.44 教训：**被拦的必须查得到**）。

| 被淘汰 | 与谁相关 ≥0.70 | 保留者 | 保留者剥Calmar | 被淘汰者剥Calmar |
|---|---|---|---|---|
| `F04_500` | （同组） | `F07` | **1.228** | 0.667 |
| `F05` | 0.887 | `F07` | **1.228** | 0.623 |
| `F08` | 0.899 | `F07` | **1.228** | 0.651 |
| `F10_1000` | 0.719 | `F07` | **1.228** | 0.587 |
| `F17` | （同组） | `F07` | **1.228** | 0.543 |
| `F18` | （同组） | `F07` | **1.228** | 0.423 |
| `F28` | （同组） | `F25` | **0.551** | 0.314 |
| `F30` | （同组） | `F25` | **0.551** | 0.311 |
| `F31` | 0.724 | `F25` | **0.551** | 0.415 |
| `F34` | （同组） | `F25` | **0.551** | 0.330 |

---

## 相关文件导航

| 文件 | 内容 |
|---|---|
| `docs/factor_pool_selected.md`（本文件） | ★ **精选池**（A 档 + 正交去重后的推荐清单）|
| `docs/factor_library_crosspool.md` | 跨池**镜像视图**（忠实反映各池库，不去重）|
| `docs/loop_strip_style_bank.csv` | 52 个因子的 `原 vs 剥风格` 实测（本文件的闸门依据）|
| `facs/` | 因子值 h5（float32 权威 + uint8 快查副本）|
