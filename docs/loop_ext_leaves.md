# Loop 引擎「扩叶子池」方案与落地记录（v3 定稿）

日期：2026-09-09 · 状态：**已全部落地并通过验证**（v1=净额 2 列方案 → 用户评审否决；
v2=资金流原始列入叶 + BARRA/财报PIT 设计；v3=mf16+barra11+fa8 共 54 叶集成进引擎，
单一事实源重构，2026-09-09 16:4x 完成）。

---

## 0. 背景与主矛盾

gen22 收官复盘结论（`docs/loop_summary_2026-09-09.md`）：叶子池纯量价 21 字段 + 五年 FWD
短持有框架决定了候选的**增量信息上限**（头部叶子被 turnover/volume/intraday 轮流垄断，
L1 高 IC 全是已知族机械组合 → L2 全灭于 Calmar）。扩数据源 → 三类新数据叶子 → 自 gen23 重启。

## 1. 落地叶子池（54 = 基础 7 + 派生 12 + 新增 35）

| 族 | 数量 | 叶子 | 源 / 口径 | 量纲 | 覆盖(非NaN) |
|---|---|---|---|---|---|
| 基础量价 | 7 | close open high low volume turnover mktcap | panel.h5 | P/P/P/P/V/A/M | 全期 |
| 派生 | 12 | vwap ret turn_ratio ln_mktcap ln_volume overnight intraday amplitude up_shadow down_shadow hl_ratio true_range | engine 预计算 | P/R/… | 全期 |
| 资金流 MF16 | 16 | mf_{s,m,l,x}_{buy,sell} ×8(金额) + mf_{s,m,l,x}_{bqty,sqty} ×8(量) | moneyflow3 原始拆分×1e4 元/×100 股 → panel.h5 | 金额 A / 量 V | 71.4%（2013 起）|
| BARRA 风格 | 11 | barra_{size,non_linear_size,momentum,liquidity,book_to_price,leverage,growth,earnings_yield,beta,residual_volatility,comovement} | E:\rq barra.h5 → barra.h5 | R（截面已标准化）| 56.9%（2017 起）|
| 财报 PIT | 8 | fa_{np_yoy,rev_yoy,op_yoy,ocf_yoy} + fa_{gm,np_margin,roe,lev} | E:\rq\finance\pit\*.h5 as-of(info_date) → fa_pit.h5 | R | 73–83%（2013 起）|

设计铁律：**净额/净占比/市值可比占比一律不预焊**（结果应由 GP 自组合）；原始金额列不入叶
（非截面可加元）；财报只入 R 量纲比值（YTD→TTM、银行 NaN、修订按 info_date as-of 版本链，
不回溯修正，全部无未来函数）。

## 2. 代码架构（单一事实源，防再次漂移）

- **`engine/loop_fields.py`**（新建）= 叶子字段唯一定义处：`FIELDS_BASE/LEAVES_DERIVED/MF16/
  BARRA_KEYS/BARRA_LEAVES/FA_LEAVES/LEAVES/FIELDS`。**新增字段族只改这一处 + gen_skill.md。**
- 四处已对齐（历史坑：B角与 LLM 内置底稿各自硬编码旧 12 字段，叶子扩展后认不出新族）：
  * `loop_engine.py`：常量区与 LEAVES 直接 `from loop_fields import …`；
  * `loop_critic.py`：`_leaf_of`/`struct_div` 改用 `LEAVES`（诊断/结构去重自动覆盖新族）；
  * `loop_llm.py`：内置 `_GEN_SYSTEM_FALLBACK` 白名单与机制引导同步；
  * `engine/skills/gen_skill.md`：外置 Skill 白名单按族给全 + 新信号族引导（资金流失衡/
    风格轮动/财报景气，可跨族组合）。
- 数据产物与构建（幂等，重建顺序 build_panel → build_mf_leaves → build_barra → build_fa_pit）：
  * `engine/build_mf_leaves.py` → panel.h5 追加 mf_*16 列，**移除旧净额 4 列**
    (mf_net/mf_xl/mf_net_r/mf_xl_r)，勾稽校验 Σ买≈Σ卖；
  * `engine/build_barra.py` → barra.h5（key 带 `barra_` 前缀）；
  * `engine/build_fa_pit.py` → fa_pit.h5（按 info_date 传播版本链 + q vs q-4 同比）。
  * h5 key = 叶子名（barra_/fa_ 前缀），与 loop_fields 单一对应。

## 3. 关键坑与修复

1. **barra.h5 key 漏前缀**：build_barra 曾只对 print 加 `barra_`、存盘 key 是无前缀裸名 →
   `base_fields()` 读 `st['barra_size']` KeyError；已改 `st['barra_'+c]` 并重建（73s）。
2. **PIT 无未来函数**：只有 `info_date`(无 ann_date)；同 quarter 多版本行 → t 日取
   `info_date≤t` 的最新版本（searchsorted right + 逐季度传播），修订不回填历史。
3. **单位/口径**：moneyflow 金额=万元×1e4、量=手×100；财报 YTD→TTM(同比 q vs q-4)；
   银行股 gm/ocf 类=NaN(设计如此，不填)。

## 4. 验证（临时脚本 `ai_test/chk_engine_new_leaves.py` / `chk_dryrun_leaves.py`，可删）

| 项 | 结果 |
|---|---|
| 54 叶在 `_FIELD_DIM`/`LEAF_CAT` 全覆盖 | OK |
| `base_fields()` 全量加载 shape 一致 (3309, 5384) | 54 叶全过 |
| 覆盖 | mf 71.4% / barra 56.9%(2017 起) / fa 73–83% |
| critic 识别 mf_/barra_/fa_ 叶 | OK |
| 隔离干跑：11 个手工含新叶表达式 parse+eval+L1 IC | 11/11，有效日 100% |
| 随机生成 80 候选含新叶比例 | 59/80（≈65%，与 35/54 一致，无旧字段偏向）|

正式通路：2026-09-09 起自 **gen23** 重启（延续收官 state，n=800/l2=30，见 §5）。

## 5. 后续可选（首版未做）

- 三期：技术指标（EMA/MACD/RSI 等预计算列）与分钟频聚合；
- GP depth∈[2,3,4] 组合不出深度≥5 净额结构 → 若三代内 mf 候选仍偏少，加 guided 程序化族
  (mf_net/mf_share 等) 或显式占比列（市值可比后补开关）。
