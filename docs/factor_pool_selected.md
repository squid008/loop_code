# 精选因子池（L3）

> **派生视图**，由 `python tools/cross_pool_review.py` 生成 —— 可随时重建。
> 与 `docs/factor_library_crosspool.md`（**忠实镜像**各池库）**定位不同**：
> 本文件是**过了双闸门的精选清单**，供下游（组合/回测/看板）直接使用。

## 双闸门（用户 2026-09-14 拍板）

1. **剥风格档**：只有 `A 独立有效`（剥掉 lncap+lnamt 后 Calmar ≥ 0.30）才准入。
   ⚠ 库内实测约 **44% 是"纯风格"**（剥完转负）⇒ 这一刀砍掉近一半。
2. **正交去重**：准入集合内两两算 **因子值截面秩相关**，`≥ 0.70` 连边 ⇒ 
   **连通分量内只留"剥风格 Calmar 最高"的一个**（同族留最强，不丢信息）。

> ★ 为什么闸门放在这一层、而**不在入库**：如果入库就拦，`bank` 不增长 ⇒
> `--decorr`/`--dup_ex_corr` 的对照集变弱 ⇒ 引擎更容易重复挖 ⇒ 又被拦 ⇒ **死循环**。
> ⇒ **`bank` 照旧长（它是对照集，越大去重力越强）**，另设本精选层。

## 精选清单（7 个）

> ★ **表达式是完整的**（不截断）—— 本文件可直接给下游用，不必回各池库翻。
> 需要**可复制的全文** / `sign` / h5 路径 → 见下方「[精选因子明细](#精选因子明细可直接复制使用)」。

| # | 因子 | 剥风格档 | 剥Calmar | 剥超额 | 原Calmar | 表达式（完整） |
|---|---|---|---|---|---|---|
| 1 | `F07` | **A** | **1.228** | +5.3% | 0.820 | `ts_std100(mul(cs_demean(hl_ratio), ts_mean5(cs_demean(turn_ratio))))` |
| 2 | `F35` | **A** | **0.604** | +2.6% | 1.077 | `mul(ts_max20(max(max(barra_residual_volatility, div(barra_residual_volatility, barra_liquidity)), ts_rank60(cs_scale(ts_std100(barra_residual_volatility))))), corr100(true_range, mf_m_buy))` |
| 3 | `F25` | **A** | **0.551** | +3.9% | 1.295 | `max(ts_mean150(corr100(ts_rank100(cs_rank(barra_leverage)), ts_min20(cs_rank(barra_leverage)))), barra_residual_volatility)` |
| 4 | `F07_1000` | **A** | **0.519** | +6.3% | 0.506 | `ts_mean200(mul(add(sub(overnight, barra_beta), ts_mean60(barra_residual_volatility)), ts_max20(ts_mean60(barra_size))))` |
| 5 | `F33` | **A** | **0.400** | +3.9% | 0.847 | `ts_delta120(add(ts_max20(ts_max100(barra_non_linear_size)), div(cs_rank(barra_beta), ts_std150(mf_x_bqty))))` |
| 6 | `F21` | **A** | **0.351** | +2.2% | 0.868 | `max(add(barra_residual_volatility, barra_leverage), max(ts_min20(cs_rank(div(fa_ocf_yoy, fa_gm))), barra_residual_volatility))` |
| 7 | `F05_500` | **A** | **0.349** | +2.3% | 0.802 | `corr100(mul(mf_m_sqty, ts_std60(mf_x_buy)), mf_m_sqty)` |

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

### 2. `F35`

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

### 3. `F25`

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

### 4. `F07_1000`

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

### 5. `F33`

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

### 6. `F21`

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

### 7. `F05_500`

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
