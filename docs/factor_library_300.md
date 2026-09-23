# 因子库（池 = 300）

> 当前 **5 个入库**（★ 2026-09-23 复核：`state.bank` = 5；快照权威见 `docs/loop_todo.md §0`）
> 本文件由引擎在**每代末尾自动同步**（`--mine_pool=300` 时生效；实现见 `_lib_sync`）。
> ⚠ 与全A 轨道的 `docs/factor_library.md` **互不读写**（池隔离，见 roadmap §8.42）。

> ⚠⚠ **本池 state 曾在 2026-09-13 被误删**（`_cleanup_prerun.py` 重复执行的事故，roadmap §8.26；**state 不可恢复**）⇒ 下列因子中**有 1 个已不在 `state.bank` 里**。
> 它们的**指标与表达式仍完整留档**在 `docs/loop_archive_300.csv`（`passed=True` 行），
> 本文档据「archive 过 L2」+「当时日志的 `入库 N 个新因子`」双证据补录 ⇒ **如实保留，不抹掉**。



> ★ **本池轨迹的池口径（逐代）**：据 `loop_pool_obs_300.csv` 的 pool 列。
>   · gen1~5         `--pools=300,500`   ⚠ **未测 1000**
>   · gen6~11        `--pools=1000,300,500`
> ⚠ 池标签是「**在这些池上**测出来的」⇒ **不同代的标签不能直接比**。
> 典型陷阱：只测 300/500 时，因子会被标成 `csi_all_only`（「只有全A通过 ⇒ 小盘溢价嫌疑、指数增强不可用」）—— **其实只是没测 1000**。

---

## 因子总览

| 编号 | 入库代数 | 家族 | 一句话 | 状态 |
|---|---|---|---|---|

| F01 | gen4 | 资金流、资金流、跳空、振幅 | sub(corr100(mf_x_sell, mf_s_bqty), min(ov… | 已入库(auto) |
| F02 | gen1 | 资金流、资金流 | corr100(cs_scale(mf_x_sell), mf_l_sell) | 已入库(auto) |
| F03 | gen10 | 资金流、资金流 | cs_scale(corr60(mf_l_sell, mf_m_bqty)) | 已入库(auto) |
| F04 | gen129 | 财报、市值 | ts_mean10(ema60(corr200(fa_sell_exp, cs_r… | 已入库(auto) |
| F05 | gen157 | 财报、风格 | corr200(fa_sell_exp, ema60(barra_size)) | 已入库(auto) |
## 因子明细

### F01 · gen4 入库（引擎自动同步，家族命名待人工精炼）
```
sub(corr100(mf_x_sell, mf_s_bqty), min(overnight, hl_ratio))
```
- **符号 `sign`：`-1`**（★ 因子值须乘它才是"越大越好"的方向；不乘 ⇒ 反向选股）
- 家族：资金流、资金流、跳空、振幅（auto）
- 叶子：mf_x_sell、mf_s_bqty、overnight、hl_ratio
- 骨架：`sub(corr(mf_x_sell,mf_s_bqty),min(overnight,hl_ratio))`
- 池标签：**`csi300_all`** —— 全A + **300** 池通过
- 费后指标（full，成本 0.004往返(主用档)）：IC 0.0350 / IC_IR 0.416 / 年化超额 +6.9% / 回撤 -5.0% / Calmar 1.391 / Sharpe 1.273 / 最近年 +9.1% / 单期换手 16.0% / 负年 0

---


### F02 · gen1 入库（引擎自动同步，家族命名待人工精炼）
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


### F03 · gen10 入库（引擎自动同步，家族命名待人工精炼）
```
cs_scale(corr60(mf_l_sell, mf_m_bqty))
```
- **符号 `sign`：`-1`**（★ 因子值须乘它才是"越大越好"的方向；不乘 ⇒ 反向选股）
- 家族：资金流、资金流（auto）
- 叶子：mf_l_sell、mf_m_bqty
- 骨架：`cs_scale(corr(mf_l_sell,mf_m_bqty))`
- 池标签：**`csi300_1000_all`** —— 全A + **300/1000** 池通过
- 费后指标（full，成本 0.004往返(主用档)）：IC 0.0412 / IC_IR 0.451 / 年化超额 +5.0% / 回撤 -7.0% / Calmar 0.713 / Sharpe 0.801 / 最近年 +2.9% / 单期换手 21.8% / 负年 0

---


### F04 · gen129 入库（引擎自动同步，家族命名待人工精炼）
```
ts_mean10(ema60(corr200(fa_sell_exp, cs_rank(ema12(cs_rank(ema12(ema12(mktcap))))))))
```
- 符号 `sign`：**未记录**（缺失时不臆造，见 roadmap §8.45 铁律）
- 家族：财报、市值（auto）
- 叶子：fa_sell_exp、mktcap
- 骨架：`ts_mean(ema60(corr(fa_sell_exp,cs_rank(ema12(cs_rank(ema12(ema12(mktcap))))))))`
- 池标签：**`all3`** —— 全A **且所有池都通过**（真 alpha）
- 剥风格：**`A`** 独立有效（剥风格后**日频** Calmar >= 0.30，且**日频**回撤 > -0.20）（原 Calmar 0.727 → 剥后 0.649；超额 +5.9% → +5.1%；**日频** 剥后 Calmar 0.564，日频回撤 -9.1%）
- 费后指标（full，成本 0.004往返(主用档)）：IC 0.0099 / IC_IR 0.099 / 年化超额 +5.9% / 回撤 -8.2% / Calmar 0.727 / Sharpe 0.899 / 最近年 +14.5% / 单期换手 8.2% / 负年 2

---


### F05 · gen157 入库（引擎自动同步，家族命名待人工精炼）
```
corr200(fa_sell_exp, ema60(barra_size))
```
- **符号 `sign`：`1`**（★ 因子值须乘它才是"越大越好"的方向；不乘 ⇒ 反向选股）
- 家族：财报、风格（auto）
- 叶子：fa_sell_exp、barra_size
- 骨架：`corr(fa_sell_exp,ema60(barra_size))`
- 池标签：**`all3`** —— 全A **且所有池都通过**（真 alpha）
- 剥风格：**`A`** 独立有效（剥风格后**日频** Calmar >= 0.30，且**日频**回撤 > -0.20）（原 Calmar 0.729 → 剥后 0.658；超额 +6.4% → +5.7%；**日频** 剥后 Calmar 0.498，日频回撤 -11.5%）
- 口径：**20 日调仓** ✓（期数 104；成本 0.004往返(主用档)）★ 与 5 日口径的数字**不可直接比** ✗（样本区间/成本相同，只有调仓周期不同 ✓）
- 费后指标（full，成本 0.004往返(主用档)）：IC 0.0312 / IC_IR 0.274 / 年化超额 +6.4% / 回撤 -8.8% / Calmar 0.729 / Sharpe 0.810 / 最近年 +18.2% / 单期换手 33.7% / 负年 1

---


## 相关文件导航

| 文件 | 内容 |
|---|---|
| `docs/factor_library_300.md`（本文件） | 池 **300** 的入库因子（只增不改） |
| `docs/factor_library.md` | 全A 轨道的入库因子 |
| **`docs/factor_library_crosspool.md`** | ★ **跨池派生视图**：各池库里**全A 有效**的因子去重 + 池标签并集修正（本池的因子在这里能看到"全A 视角"） |
| `docs/loop_journal_300.md` | 池 **300** 的每代诊断 + B角下一代参数 |
| `docs/loop_pool_obs_300.csv` | 池 **300** 候选的**三池池内指标**宽表 |
| `docs/loop_archive_300.csv` | 池 **300** 每代 L2 全量候选流水 |
