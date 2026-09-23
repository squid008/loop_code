# 跨池因子视图（全A 有效因子汇总）

> **派生视图**，由 `python tools/build_crosspool_view.py` 生成 —— **可随时重建**，不占编号、不被引擎改写。

> 为什么需要：`docs/factor_library.md`（全A 轨道）是 **append-only 且编号连续**，其计数由 `_lib_sync` 按 `len(bank)` 重写 ⇒ **手工插入会让文档 ≠ state**；且**同一式子会在多个池被独立发现**（各池 bank/decorr 独立）⇒ 直接合并会重复入场。

> 本视图按 **表达式去重**，把「在哪些池被发现」「在哪些池有效」合并成一行，并用 `loop_pools.derive_tag`（**单一事实源**）重算标签 —— **各来源池测到的结果取并集**（同一个式子在 A 池的轨迹里测了 300/500、在 B 池的轨迹里测了三个池 ⇒ 合并后信息最全），而 `all3` 的分母仍是**引擎配置的池全集**（`--pools` 恒为 `300,500,1000`）—— 即"**三个池都通过**"才算真 alpha。⇒ 解决池库文件自己警告的「不同代标签不能直接比」问题。

## 摘要

| 项 | 值 |
|---|---|
| 参与的池 | 300, 500, 1000 |
| 池入库**条目**合计 | 29 条 |
| **去重后唯一因子** | **27 个** |
| ★ **其中「全A 有效」** | **27 个** |
| 其中已存在于全A 库(`factor_library.md`) | **0 个** |
| 跨池重复（>1 个池入库） | **1 个** |
| 其中「仍在 state.bank」（非仅存于文档） | **20 个** |
| ★ **剥风格判定**：A 独立有效 | **9 个** |
| ★ 剥风格判定：B 弱独立 | **9 个** |
| ★★ **剥风格判定：C 纯风格（应拒）** | **9 个** |

⇒ ⚠⚠ **9 / 27 个池因子是「纯风格」**（剥掉 lncap+lnamt 后超额转负）—— **根因是入库判定漏了一道关**：`tools/run_tracks.py` 传了 `--strip_style`（记录）但**没传** `--min_strip_calmar`（默认 `-1` = **只记录不拦**）⇒ 剥风格结果**从未参与入库判定**；而 `derive_tag` 的 `ok_all` 也是**未剥风格**口径 ⇒ `all3` 号称的"真 alpha"**含风格水分**。

⇒ ★ **27 个「全A 有效」的池因子，一个都不在 `factor_library.md` 里** ⇒ 全A 库确实缺了它们（**用户的判断成立**）。

> ⚠ 但**不要直接 append 进 `factor_library.md`**：它是 append-only + 编号连续，计数由 `_lib_sync` 按 `len(bank)` 重写 ⇒ 手插行会造成**文档 ≠ state**，且下次全A 轨道一跑计数就被覆盖、编号错位。⇒ 用**本视图**提供全A 视角。

## 表A · 全A 有效（**先按"剥风格判定"降序**，再按全A Calmar）

`all3` = 全A **且 300/500/1000 三个池全部通过**；`csi*_all` = 全A + 列出的那些池通过；`csi_all_only` = 仅全A（**须三池都测过才可信**）。「来源池(编号)」= 在哪些池的库里入库 + 各池库里的 F 编号；「仍在bank?」中的 `⚠仅文档` = **曾入库但 state 丢了**（详见 §8.44）。

> ★★ **「风格判定」列是本表最重要的列**（2026-09-14 加）：`A 独立有效`(`剥Calmar≥0.30`) / `B 弱独立`(0~0.30) / **`C 纯风格`**（**剥掉 lncap+lnamt 后超额转负** ⇒ 信息基本全是市值/成交额风格暴露）/ `D 无记录`。

> ★★ **「`sign`」列（2026-09-14 加, §1.23）**：引擎求值时对 `sign<0` 的候选**取负**（让"值越大越好"）。
> 下游拿到 `facs/` 的因子值 h5 **直接排序选股、不乘 `sign`** ⇒ **方向反了、组合反向选股** ✗（精选池实测 7 个里 **6 个 `sign=-1`** ⇒ 中招概率很高）。
> ⚠ 「未记录」= 该因子**没在 `facs/` 落地**，`sign` 无从取得 —— **不臆造**（roadmap §8.45 铁律）。

> ⚠ **为什么必须看这一列**：池轨道的**入库判定没有经过剥风格这道关** —— `tools/run_tracks.py` 传了 `--strip_style`（记录）但**没传** `--min_strip_calmar`（默认 `-1` = **只记录不拦**）⇒ 池库里混进了纯风格因子（**几个见上表「C 纯风格」一行**）。⇒ **只看"全A Calmar"排序会被误导**（实测最高的两个剥完都是负的）。

| # | 表达式 | **`sign`** | 风格判定 | 全A超额 | Calmar | **剥风格超额** | **剥风格Calmar** | 池标签(重算) | 来源池(编号) | 换手 | 负年 | 仍在bank? |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | `cs_demean(mul(add(turn_ratio, ts_mean60(barra_residual_volatility)), ts_max20(ts_mean60(barra_size))))` | **`+1`** | **A 独立有效** | **+6.9%** | **0.891** | +5.6% | **0.587** | **csi_all_only** | 1000(F10) | +8.0% | 1 | ✓ |
| 2 | `corr100(mul(mf_m_sqty, ts_std60(mf_x_buy)), mf_m_sqty)` | **`-1`** | **A 独立有效** | **+4.0%** | **0.802** | +2.3% | **0.349** | **csi_all_only** | 500(F05) | +18.7% | 2 | ✓ |
| 3 | `ts_mean10(ema60(corr200(fa_sell_exp, cs_rank(ema12(cs_rank(ema12(ema12(mktcap))))))))` | 未记录 | **A 独立有效** | **+5.9%** | **0.727** | +5.1% | **0.649** | **csi_all_only** | 300(F04) | +8.2% | 2 | ✓ |
| 4 | `ts_mean120(max(fa_np_margin, barra_residual_volatility))` | **`-1`** | **A 独立有效** | **+5.4%** | **0.712** | +2.5% | **0.315** | **csi_all_only** | 500(F12) | +6.1% | 1 | ✓ |
| 5 | `max(fa_np_margin, ts_max100(barra_residual_volatility))` | **`-1`** | **A 独立有效** | **+4.7%** | **0.577** | +4.3% | **0.667** | **csi_all_only** | 500(F04) | +6.8% | 1 | ✓ |
| 6 | `ts_mean200(ema20(ts_rank200(overnight)))` | 未记录 | **A 独立有效** | **+3.1%** | **0.521** | +3.9% | **0.567** | **csi_all_only** | 500(F08) | +9.0% | 0 | ✓ |
| 7 | `ts_mean200(mul(add(sub(overnight, barra_beta), ts_mean60(barra_residual_volatility)), ts_max20(ts_mean60(barra_size))))` | **`+1`** | **A 独立有效** | **+7.0%** | **0.506** | +6.3% | **0.519** | **csi_all_only** | 1000(F07) | +4.9% | 2 | ✓ |
| 8 | `ts_mean150(corr100(barra_momentum, ema20(fa_sell_exp)))` | **`+1`** | **A 独立有效** | **+3.7%** | **0.408** | +3.2% | **0.304** | **csi_all_only** | 500(F09) | +7.8% | 2 | ✓ |
| 9 | `max(fa_np_margin, barra_residual_volatility)` | **`-1`** | **A 独立有效** | **+6.3%** | **0.369** | +3.4% | **0.304** | **csi_all_only** | 500(F11) | +13.1% | 2 | ✓ |
| 10 | `sub(ts_min20(barra_beta), ts_mean60(barra_non_linear_size))` | **`+1`** | B 弱独立 | **+12.5%** | **0.763** | +2.2% | **0.064** | **csi_all_only** | 1000(F03) | +9.8% | 1 | ✓ |
| 11 | `corr100(cs_scale(mf_x_sell), mf_l_sell)` | **`-1`** | B 弱独立 | **+7.7%** | **0.661** | +1.7% | **0.180** | **csi_all_only** | 300(F02) · 500(F01) · 1000(F01) | +15.2% | 0 | ✓ |
| 12 | `ts_mean150(mul(barra_residual_volatility, amplitude))` | 未记录 | B 弱独立 | **+4.5%** | **0.563** | +1.9% | **0.171** | **csi_all_only** | 500(F02) | +5.4% | 1 | ⚠仅文档 |
| 13 | `ts_mean200(mul(sub(barra_residual_volatility, cs_rank(ts_delay1(mul(sub(barra_residual_volatility, ts_std100(ts_delay1(corr200(fa_rev_yoy, intraday)))), mul(barra_earnings_yield, barra_book_to_price))))), turn_ratio))` | 未记录 | B 弱独立 | **+3.8%** | **0.513** | +2.5% | **0.258** | **csi_all_only** | 500(F06) | +4.5% | 2 | ✓ |
| 14 | `ts_mean150(corr100(barra_momentum, ts_mean5(fa_gm)))` | 未记录 | B 弱独立 | **+4.3%** | **0.502** | +2.7% | **0.241** | **csi_all_only** | 500(F07) | +7.7% | 1 | ✓ |
| 15 | `sub(ts_mean100(overnight), ts_mean120(intraday))` | **`+1`** | B 弱独立 | **+4.8%** | **0.493** | +1.1% | **0.067** | **csi_all_only** | 1000(F12) | +18.8% | 2 | ✓ |
| 16 | `sub(ts_mean120(overnight), ts_mean120(intraday))` | **`+1`** | B 弱独立 | **+4.8%** | **0.472** | +1.3% | **0.086** | **csi_all_only** | 1000(F11) | +18.5% | 2 | ✓ |
| 17 | `ts_mean150(corr100(barra_momentum, ema20(fa_gm)))` | **`+1`** | B 弱独立 | **+3.9%** | **0.460** | +2.9% | **0.287** | **csi_all_only** | 500(F10) | +7.8% | 2 | ✓ |
| 18 | `corr200(fa_sell_exp, ema60(barra_size))` | **`+1`** | B 弱独立 | **+4.2%** | **0.412** | +3.1% | **0.227** | **csi_all_only** | 300(F05) | +11.0% | 2 | ✓ |
| 19 | `sub(corr100(mf_x_sell, mf_s_bqty), min(overnight, hl_ratio))` | **`-1`** | ❌ **C 纯风格** | **+6.9%** | **1.391** | -3.4% | **-0.082** | **csi_all_only** | 300(F01) | +16.0% | 0 | ✓ |
| 20 | `corr100(mf_s_bqty, mf_x_sell)` | **`-1`** | ❌ **C 纯风格** | **+6.5%** | **1.193** | -3.2% | **-0.075** | **csi_all_only** | 1000(F05) | +15.4% | 0 | ⚠仅文档 |
| 21 | `cs_scale(corr60(mf_l_sell, mf_m_bqty))` | **`-1`** | ❌ **C 纯风格** | **+5.0%** | **0.713** | -3.6% | **-0.087** | **csi_all_only** | 300(F03) | +21.8% | 0 | ✓ |
| 22 | `ts_mean60(corr60(ts_delta5(ts_mean100(mf_x_bqty)), true_range))` | **`-1`** | ❌ **C 纯风格** | **+3.6%** | **0.600** | -0.6% | **-0.050** | **csi_all_only** | 1000(F09) | +12.0% | 0 | ⚠仅文档 |
| 23 | `ts_sum100(corr20(mul(mktcap, fa_gm), true_range))` | **`-1`** | ❌ **C 纯风格** | **+4.8%** | **0.565** | -1.2% | **-0.062** | **csi_all_only** | 1000(F06) | +12.7% | 0 | ⚠仅文档 |
| 24 | `sub(ts_mean60(overnight), ts_mean60(barra_non_linear_size))` | **`+1`** | ❌ **C 纯风格** | **+12.2%** | **0.561** | -5.7% | **-0.102** | **csi_all_only** | 1000(F02) | +6.2% | 1 | ⚠仅文档 |
| 25 | `ts_mean60(corr60(turn_ratio, ts_delta5(ts_mean100(mf_l_sqty))))` | **`-1`** | ❌ **C 纯风格** | **+3.4%** | **0.560** | -1.0% | **-0.054** | **csi_all_only** | 1000(F08) | +12.0% | 3 | ⚠仅文档 |
| 26 | `ts_mean200(mul(ts_max20(max(fa_np_margin, barra_residual_volatility)), volume))` | **`-1`** | ❌ **C 纯风格** | **+6.0%** | **0.559** | -2.3% | **-0.087** | **csi_all_only** | 500(F03) | +6.3% | 1 | ✓ |
| 27 | `ts_sum100(corr20(mktcap, true_range))` | **`-1`** | ❌ **C 纯风格** | **+5.4%** | **0.520** | -0.8% | **-0.042** | **csi_all_only** | 1000(F04) | +12.0% | 0 | ⚠仅文档 |

## 跨池重复（同一式子被多个池独立入库）

⚠ 各池 bank / decorr 相互独立 ⇒ 池轨道**不会跨池去重**。这些因子在多池入库，说明信号**跨域稳健**；但也提示**合成时不要重复计入**。

| 表达式 | 来源池 | 各池写入时标签 | **重算标签** |
|---|---|---|---|
| `corr100(cs_scale(mf_x_sell), mf_l_sell)` | 300/500/1000 | 300=csi_all_only · 500=csi_all_only · 1000=csi1000_all | **csi_all_only** |

## 池标签修正对照（并集重算）

池库文件自带警告：**不同代测的池不同 ⇒ 标签不能直接比**。典型陷阱：只测 300/500 时被标 `csi_all_only`（"小盘溢价嫌疑"），**其实只是没测 1000**。

| 表达式 | 来源池 | 写入时标签（测哪些池就写哪个） | **重算标签** | 含义 |
|---|---|---|---|---|
| `cs_demean(mul(add(turn_ratio, ts_mean60(barra_residual_volatility)), ts_max20(ts_mean60(barra_size))))` | 1000 | 1000=all3 | **csi_all_only** | 仅全A 通过（**注意**：仅当所有池都测过时才可信） |
| `corr100(mul(mf_m_sqty, ts_std60(mf_x_buy)), mf_m_sqty)` | 500 | 500=csi500_1000_all | **csi_all_only** | 仅全A 通过（**注意**：仅当所有池都测过时才可信） |
| `ts_mean10(ema60(corr200(fa_sell_exp, cs_rank(ema12(cs_rank(ema12(ema12(mktcap))))))))` | 300 | 300=all3 | **csi_all_only** | 仅全A 通过（**注意**：仅当所有池都测过时才可信） |
| `ts_mean120(max(fa_np_margin, barra_residual_volatility))` | 500 | 500=csi1000_500_all | **csi_all_only** | 仅全A 通过（**注意**：仅当所有池都测过时才可信） |
| `max(fa_np_margin, ts_max100(barra_residual_volatility))` | 500 | 500=csi500_1000_all | **csi_all_only** | 仅全A 通过（**注意**：仅当所有池都测过时才可信） |
| `ts_mean200(ema20(ts_rank200(overnight)))` | 500 | 500=csi500_1000_all | **csi_all_only** | 仅全A 通过（**注意**：仅当所有池都测过时才可信） |
| `ts_mean200(mul(add(sub(overnight, barra_beta), ts_mean60(barra_residual_volatility)), ts_max20(ts_mean60(barra_size))))` | 1000 | 1000=csi500_1000_all | **csi_all_only** | 仅全A 通过（**注意**：仅当所有池都测过时才可信） |
| `ts_mean150(corr100(barra_momentum, ema20(fa_sell_exp)))` | 500 | 500=all3 | **csi_all_only** | 仅全A 通过（**注意**：仅当所有池都测过时才可信） |
| `max(fa_np_margin, barra_residual_volatility)` | 500 | 500=csi1000_all | **csi_all_only** | 仅全A 通过（**注意**：仅当所有池都测过时才可信） |
| `sub(ts_min20(barra_beta), ts_mean60(barra_non_linear_size))` | 1000 | 1000=all3 | **csi_all_only** | 仅全A 通过（**注意**：仅当所有池都测过时才可信） |
| `corr100(cs_scale(mf_x_sell), mf_l_sell)` | 300/500/1000 | 300=csi_all_only · 500=csi_all_only · 1000=csi1000_all | **csi_all_only** | 仅全A 通过（**注意**：仅当所有池都测过时才可信） |
| `ts_mean150(mul(barra_residual_volatility, amplitude))` | 500 | 500=csi300_500_all | **csi_all_only** | 仅全A 通过（**注意**：仅当所有池都测过时才可信） |
| `ts_mean200(mul(sub(barra_residual_volatility, cs_rank(ts_delay1(mul(sub(barra_residual_volatility, ts_std100(ts_delay1(corr200(fa_rev_yoy, intraday)))), mul(barra_earnings_yield, barra_book_to_price))))), turn_ratio))` | 500 | 500=csi500_1000_all | **csi_all_only** | 仅全A 通过（**注意**：仅当所有池都测过时才可信） |
| `ts_mean150(corr100(barra_momentum, ts_mean5(fa_gm)))` | 500 | 500=all3 | **csi_all_only** | 仅全A 通过（**注意**：仅当所有池都测过时才可信） |
| `sub(ts_mean100(overnight), ts_mean120(intraday))` | 1000 | 1000=csi1000_all | **csi_all_only** | 仅全A 通过（**注意**：仅当所有池都测过时才可信） |
| `sub(ts_mean120(overnight), ts_mean120(intraday))` | 1000 | 1000=csi1000_all | **csi_all_only** | 仅全A 通过（**注意**：仅当所有池都测过时才可信） |
| `ts_mean150(corr100(barra_momentum, ema20(fa_gm)))` | 500 | 500=csi1000_500_all | **csi_all_only** | 仅全A 通过（**注意**：仅当所有池都测过时才可信） |
| `corr200(fa_sell_exp, ema60(barra_size))` | 300 | 300=all3 | **csi_all_only** | 仅全A 通过（**注意**：仅当所有池都测过时才可信） |
| `sub(corr100(mf_x_sell, mf_s_bqty), min(overnight, hl_ratio))` | 300 | 300=csi300_all | **csi_all_only** | 仅全A 通过（**注意**：仅当所有池都测过时才可信） |
| `corr100(mf_s_bqty, mf_x_sell)` | 1000 | 1000=csi300_1000_all | **csi_all_only** | 仅全A 通过（**注意**：仅当所有池都测过时才可信） |
| `cs_scale(corr60(mf_l_sell, mf_m_bqty))` | 300 | 300=csi300_1000_all | **csi_all_only** | 仅全A 通过（**注意**：仅当所有池都测过时才可信） |
| `ts_mean60(corr60(ts_delta5(ts_mean100(mf_x_bqty)), true_range))` | 1000 | 1000=csi500_1000_all | **csi_all_only** | 仅全A 通过（**注意**：仅当所有池都测过时才可信） |
| `ts_sum100(corr20(mul(mktcap, fa_gm), true_range))` | 1000 | 1000=csi1000_all | **csi_all_only** | 仅全A 通过（**注意**：仅当所有池都测过时才可信） |
| `sub(ts_mean60(overnight), ts_mean60(barra_non_linear_size))` | 1000 | 1000=csi1000_all | **csi_all_only** | 仅全A 通过（**注意**：仅当所有池都测过时才可信） |
| `ts_mean60(corr60(turn_ratio, ts_delta5(ts_mean100(mf_l_sqty))))` | 1000 | 1000=csi500_1000_all | **csi_all_only** | 仅全A 通过（**注意**：仅当所有池都测过时才可信） |
| `ts_mean200(mul(ts_max20(max(fa_np_margin, barra_residual_volatility)), volume))` | 500 | 500=csi500_1000_all | **csi_all_only** | 仅全A 通过（**注意**：仅当所有池都测过时才可信） |
| `ts_sum100(corr20(mktcap, true_range))` | 1000 | 1000=csi1000_all | **csi_all_only** | 仅全A 通过（**注意**：仅当所有池都测过时才可信） |

---

## 相关文件导航

| 文件 | 内容 |
|---|---|
| `docs/factor_library_crosspool.md`（本文件） | **跨池派生视图**（去重 + 并集重算标签） |
| `docs/factor_library.md` | 全A 轨道的入库因子（append-only，编号连续） |
| `docs/factor_library_300.md` | 池 **300** 的入库因子（append-only，池隔离） |
| `docs/factor_library_500.md` | 池 **500** 的入库因子（append-only，池隔离） |
| `docs/factor_library_1000.md` | 池 **1000** 的入库因子（append-only，池隔离） |
| `docs/loop_pool_obs_{pool}.csv` | 各池候选的**池内指标**（本视图的数据源） |
| `docs/loop_archive_{pool}.csv` | 各池每代 L2 流水（全A 口径指标来源） |
