# 因子库（池 = 500）

> 当前 **4 个入库**
> 本文件由引擎在**每代末尾自动同步**（`--mine_pool=500` 时生效；实现见 `_lib_sync`）。
> ⚠ 与全A 轨道的 `docs/factor_library.md` **互不读写**（池隔离，见 roadmap §8.42）。

> ⚠⚠ **本池 state 曾在 2026-09-13 被误删**（`_cleanup_prerun.py` 重复执行的事故，roadmap §8.26；**state 不可恢复**）⇒ 下列因子中**有 2 个已不在 `state.bank` 里**。
> 它们的**指标与表达式仍完整留档**在 `docs/loop_archive_500.csv`（`passed=True` 行），
> 本文档据「archive 过 L2」+「当时日志的 `入库 N 个新因子`」双证据补录 ⇒ **如实保留，不抹掉**。



> ★ **本池轨迹的池口径（逐代）**：据 `loop_pool_obs_500.csv` 的 pool 列。
>   · gen1~5         `--pools=300,500`   ⚠ **未测 1000**
>   · gen6~11        `--pools=1000,300,500`
> ⚠ 池标签是「**在这些池上**测出来的」⇒ **不同代的标签不能直接比**。
> 典型陷阱：只测 300/500 时，因子会被标成 `csi_all_only`（「只有全A通过 ⇒ 小盘溢价嫌疑、指数增强不可用」）—— **其实只是没测 1000**。

---

## 因子总览

| 编号 | 入库代数 | 家族 | 一句话 | 状态 |
|---|---|---|---|---|

| F01 | gen1 | 资金流、资金流 | corr100(cs_scale(mf_x_sell), mf_l_sell) | 已入库(auto) |
| F02 | gen3 | 风格、振幅 | ts_mean150(mul(barra_residual_volatility,… | 已入库(auto) |
| F03 | gen9 | 财报、风格、量 | ts_mean200(mul(ts_max20(max(fa_np_margin,… | 已入库(auto) |
| F04 | gen10 | 财报、风格 | max(fa_np_margin, ts_max100(barra_residua… | 已入库(auto) |
| F05 | gen10 | 资金流、资金流 | corr100(mul(mf_m_sqty, ts_std60(mf_x_buy)… | 已入库(auto) |
| F06 | gen17 | 风格、财报、日内收益、风格、风格、换手率 | ts_mean200(mul(sub(barra_residual_volatil… | 已入库(auto) |

## 因子明细

### F01 · gen1 入库（引擎自动同步，家族命名待人工精炼）
```
corr100(cs_scale(mf_x_sell), mf_l_sell)
```
- **符号 `sign`：`-1`**（★ 因子值须乘它才是"越大越好"的方向；不乘 ⇒ 反向选股）
- 家族：资金流、资金流（auto）
- 叶子：mf_x_sell、mf_l_sell
- 骨架：`corr(cs_scale(mf_x_sell),mf_l_sell)`
- 池标签：**`csi_all_only`** —— **只有全A通过** ⇒ 小盘/流动性溢价嫌疑，**指数增强不可用**
- 费后指标（full，成本 0.004往返(主用档)）：IC 0.0455 / IC_IR 0.410 / 年化超额 +7.7% / 回撤 -11.7% / Calmar 0.661 / Sharpe 1.066 / 最近年 +0.0% / 单期换手 15.2% / 负年 0

---


### F02 · gen3 入库（引擎自动同步，家族命名待人工精炼）
```
ts_mean150(mul(barra_residual_volatility, amplitude))
```
- 符号 `sign`：**未记录**（该因子未在 `facs/` 落地 ⇒ 待落地后回填）
- 家族：风格、振幅（auto）
- 叶子：barra_residual_volatility、amplitude
- 骨架：`ts_mean(mul(barra_residual_volatility,amplitude))`
- 池标签：**`csi300_500_all`** —— 全A + **300/500** 池通过
- 费后指标（full，成本 0.004往返(主用档)）：IC 0.0453 / IC_IR 0.356 / 年化超额 +4.5% / 回撤 -8.0% / Calmar 0.563 / Sharpe 0.810 / 最近年 +4.3% / 单期换手 5.4% / 负年 1

---


### F03 · gen9 入库（引擎自动同步，家族命名待人工精炼）
```
ts_mean200(mul(ts_max20(max(fa_np_margin, barra_residual_volatility)), volume))
```
- **符号 `sign`：`-1`**（★ 因子值须乘它才是"越大越好"的方向；不乘 ⇒ 反向选股）
- 家族：财报、风格、量（auto）
- 叶子：fa_np_margin、barra_residual_volatility、volume
- 骨架：`ts_mean(mul(ts_max(max(fa_np_margin,barra_residual_volatility)),volume))`
- 池标签：**`csi500_1000_all`** —— 全A + **500/1000** 池通过
- 费后指标（full，成本 0.004往返(主用档)）：IC 0.0415 / IC_IR 0.387 / 年化超额 +6.0% / 回撤 -10.7% / Calmar 0.559 / Sharpe 1.032 / 最近年 +3.7% / 单期换手 6.3% / 负年 1

---


### F04 · gen10 入库（引擎自动同步，家族命名待人工精炼）
```
max(fa_np_margin, ts_max100(barra_residual_volatility))
```
- **符号 `sign`：`-1`**（★ 因子值须乘它才是"越大越好"的方向；不乘 ⇒ 反向选股）
- 家族：财报、风格（auto）
- 叶子：fa_np_margin、barra_residual_volatility
- 骨架：`max(fa_np_margin,ts_max(barra_residual_volatility))`
- 池标签：**`csi500_1000_all`** —— 全A + **500/1000** 池通过
- 费后指标（full，成本 0.004往返(主用档)）：IC 0.0509 / IC_IR 0.395 / 年化超额 +4.7% / 回撤 -8.1% / Calmar 0.577 / Sharpe 0.756 / 最近年 +0.6% / 单期换手 6.8% / 负年 1

### F05 · gen10 入库（引擎自动同步，家族命名待人工精炼）
```
corr100(mul(mf_m_sqty, ts_std60(mf_x_buy)), mf_m_sqty)
```
- **符号 `sign`：`-1`**（★ 因子值须乘它才是"越大越好"的方向；不乘 ⇒ 反向选股）
- 家族：资金流、资金流（auto）
- 叶子：mf_m_sqty、mf_x_buy
- 骨架：`corr(mul(mf_m_sqty,ts_std(mf_x_buy)),mf_m_sqty)`
- 池标签：**`csi500_1000_all`** —— 全A + **500/1000** 池通过
- 费后指标（full，成本 0.004往返(主用档)）：IC 0.0087 / IC_IR 0.184 / 年化超额 +4.0% / 回撤 -5.0% / Calmar 0.802 / Sharpe 0.896 / 最近年 +1.9% / 单期换手 18.7% / 负年 2

---


### F06 · gen17 入库（引擎自动同步，家族命名待人工精炼）
```
ts_mean200(mul(sub(barra_residual_volatility, cs_rank(ts_delay1(mul(sub(barra_residual_volatility, ts_std100(ts_delay1(corr200(fa_rev_yoy, intraday)))), mul(barra_earnings_yield, barra_book_to_price))))), turn_ratio))
```
- 符号 `sign`：**未记录**（缺失时不臆造，见 roadmap §8.45 铁律）
- 家族：风格、财报、日内收益、风格、风格、换手率（auto）
- 叶子：barra_residual_volatility、fa_rev_yoy、intraday、barra_earnings_yield、barra_book_to_price、turn_ratio
- 骨架：`ts_mean(mul(sub(barra_residual_volatility,cs_rank(ts_delay(mul(sub(barra_residual_volatility,ts_std(ts_delay(corr(fa_rev_yoy,intraday)))),mul(barra_earnings_yield,barra_book_to_price))))),turn_ratio))`
- 池标签：**`csi500_1000_all`** —— 全A + **500/1000** 池通过
- 剥风格：**`B`** 弱独立（剥风格后日频 Calmar 在 0~0.30，或回撤劣于 -0.20）（原 Calmar 0.513 → 剥后 0.258；超额 +3.8% → +2.5%；**日频** 剥后 Calmar 0.251，日频回撤 -9.8%）
- 费后指标（full，成本 0.004往返(主用档)）：IC 0.0397 / IC_IR 0.447 / 年化超额 +3.8% / 回撤 -7.4% / Calmar 0.513 / Sharpe 0.743 / 最近年 +5.6% / 单期换手 4.5% / 负年 2

---


## 相关文件导航

| 文件 | 内容 |
|---|---|
| `docs/factor_library_500.md`（本文件） | 池 **500** 的入库因子（只增不改） |
| `docs/factor_library.md` | 全A 轨道的入库因子 |
| **`docs/factor_library_crosspool.md`** | ★ **跨池派生视图**：各池库里**全A 有效**的因子去重 + 池标签并集修正（本池的因子在这里能看到"全A 视角"） |
| `docs/loop_journal_500.md` | 池 **500** 的每代诊断 + B角下一代参数 |
| `docs/loop_pool_obs_500.csv` | 池 **500** 候选的**三池池内指标**宽表 |
| `docs/loop_archive_500.csv` | 池 **500** 每代 L2 全量候选流水 |
