# 因子库（池 = 1000）

> 当前 **6 个入库**
> 本文件由引擎在**每代末尾自动同步**（`--mine_pool=1000` 时生效；实现见 `_lib_sync`）。
> ⚠ 与全A 轨道的 `docs/factor_library.md` **互不读写**（池隔离，见 roadmap §8.42）。



> ★ **本池轨迹的池口径（逐代）**：据 `loop_pool_obs_1000.csv` 的 pool 列。
>   · gen1~3         `--pools=1000,300,500`
> ⚠ 池标签是「**在这些池上**测出来的」⇒ **不同代的标签不能直接比**。
> 典型陷阱：只测 300/500 时，因子会被标成 `csi_all_only`（「只有全A通过 ⇒ 小盘溢价嫌疑、指数增强不可用」）—— **其实只是没测 1000**。

---

## 因子总览

| 编号 | 入库代数 | 家族 | 一句话 | 状态 |
|---|---|---|---|---|

| F01 | gen1 | 资金流、资金流 | corr100(cs_scale(mf_x_sell), mf_l_sell) | 已入库(auto) |
| F02 | gen1 | 跳空、风格 | sub(ts_mean60(overnight), ts_mean60(barra… | 已入库(auto) |
| F03 | gen2 | 风格、风格 | sub(ts_min20(barra_beta), ts_mean60(barra… | 已入库(auto) |
| F04 | gen3 | 市值、振幅 | ts_sum100(corr20(mktcap, true_range)) | 已入库(auto) |
| F05 | gen3 | 资金流、资金流 | corr100(mf_s_bqty, mf_x_sell) | 已入库(auto) |
| F06 | gen3 | 市值、财报、振幅 | ts_sum100(corr20(mul(mktcap, fa_gm), true… | 已入库(auto) |
## 因子明细

### F01 · gen1 入库（引擎自动同步，家族命名待人工精炼）
```
corr100(cs_scale(mf_x_sell), mf_l_sell)
```
- 家族：资金流、资金流（auto）
- 叶子：mf_x_sell、mf_l_sell
- 骨架：`corr(cs_scale(mf_x_sell),mf_l_sell)`
- 池标签：**`csi1000_all`** —— 全A + **1000** 池通过
- 费后指标（full，成本 0.004往返(主用档)）：IC 0.0455 / IC_IR 0.410 / 年化超额 +7.7% / 回撤 -11.7% / Calmar 0.661 / Sharpe 1.066 / 最近年 +0.0% / 单期换手 15.2% / 负年 0

### F02 · gen1 入库（引擎自动同步，家族命名待人工精炼）
```
sub(ts_mean60(overnight), ts_mean60(barra_non_linear_size))
```
- 家族：跳空、风格（auto）
- 叶子：overnight、barra_non_linear_size
- 骨架：`sub(ts_mean(overnight),ts_mean(barra_non_linear_size))`
- 池标签：**`csi1000_all`** —— 全A + **1000** 池通过
- 费后指标（full，成本 0.004往返(主用档)）：IC 0.0233 / IC_IR 0.201 / 年化超额 +12.2% / 回撤 -21.7% / Calmar 0.561 / Sharpe 1.054 / 最近年 +4.4% / 单期换手 6.2% / 负年 1

---


### F03 · gen2 入库（引擎自动同步，家族命名待人工精炼）
```
sub(ts_min20(barra_beta), ts_mean60(barra_non_linear_size))
```
- 家族：风格、风格（auto）
- 叶子：barra_beta、barra_non_linear_size
- 骨架：`sub(ts_min(barra_beta),ts_mean(barra_non_linear_size))`
- 池标签：**`all3`** —— 全A **且所有池都通过**（真 alpha）
- 费后指标（full，成本 0.004往返(主用档)）：IC 0.0193 / IC_IR 0.112 / 年化超额 +12.5% / 回撤 -16.4% / Calmar 0.763 / Sharpe 1.162 / 最近年 +8.3% / 单期换手 9.8% / 负年 1

---


### F04 · gen3 入库（引擎自动同步，家族命名待人工精炼）
```
ts_sum100(corr20(mktcap, true_range))
```
- 家族：市值、振幅（auto）
- 叶子：mktcap、true_range
- 骨架：`ts_sum(corr(mktcap,true_range))`
- 池标签：**`csi1000_all`** —— 全A + **1000** 池通过
- 费后指标（full，成本 0.004往返(主用档)）：IC 0.0394 / IC_IR 0.410 / 年化超额 +5.4% / 回撤 -10.3% / Calmar 0.520 / Sharpe 0.800 / 最近年 +0.5% / 单期换手 12.0% / 负年 0

### F05 · gen3 入库（引擎自动同步，家族命名待人工精炼）
```
corr100(mf_s_bqty, mf_x_sell)
```
- 家族：资金流、资金流（auto）
- 叶子：mf_s_bqty、mf_x_sell
- 骨架：`corr(mf_s_bqty,mf_x_sell)`
- 池标签：**`csi300_1000_all`** —— 全A + **300/1000** 池通过
- 费后指标（full，成本 0.004往返(主用档)）：IC 0.0346 / IC_IR 0.414 / 年化超额 +6.5% / 回撤 -5.5% / Calmar 1.193 / Sharpe 1.231 / 最近年 +7.4% / 单期换手 15.4% / 负年 0

### F06 · gen3 入库（引擎自动同步，家族命名待人工精炼）
```
ts_sum100(corr20(mul(mktcap, fa_gm), true_range))
```
- 家族：市值、财报、振幅（auto）
- 叶子：mktcap、fa_gm、true_range
- 骨架：`ts_sum(corr(mul(mktcap,fa_gm),true_range))`
- 池标签：**`csi1000_all`** —— 全A + **1000** 池通过
- 费后指标（full，成本 0.004往返(主用档)）：IC 0.0361 / IC_IR 0.412 / 年化超额 +4.8% / 回撤 -8.5% / Calmar 0.565 / Sharpe 0.842 / 最近年 +0.3% / 单期换手 12.7% / 负年 0

---


## 相关文件导航

| 文件 | 内容 |
|---|---|
| `docs/factor_library_1000.md`（本文件） | 池 **1000** 的入库因子（只增不改） |
| `docs/factor_library.md` | 全A 轨道的入库因子 |
| **`docs/factor_library_crosspool.md`** | ★ **跨池派生视图**：各池库里**全A 有效**的因子去重 + 池标签并集修正（本池的因子在这里能看到"全A 视角"） |
| `docs/loop_journal_1000.md` | 池 **1000** 的每代诊断 + B角下一代参数 |
| `docs/loop_pool_obs_1000.csv` | 池 **1000** 候选的**三池池内指标**宽表 |
| `docs/loop_archive_1000.csv` | 池 **1000** 每代 L2 全量候选流水 |
