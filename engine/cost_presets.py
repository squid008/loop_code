# -*- coding: utf-8 -*-
"""交易成本档位 —— 单一事实源（2026-09-11 建立）
=====================================================================
本模块是全库**唯一**的成本定义处。`factor_miner` / `loop_engine` / `standard_test`
一律 import 此处，**禁止各自硬编码**。

> 为什么建它：2026-09-11 查证发现三处并存（`0.005` / `0.004` / `0.007`），
> 且标签自相矛盾（help 写"往返成本, 默认单边千1.5"、日志打 `bp/边`、
> `factor_library.md` 写"成本 4bp/边"），连读文档的人都被误导过三次。
> 详见 `docs/software_framework.md` §3.0.1。

【语义】所有档位都是「**往返**成本」，且被扣在「**单向换手率**」上：

    ex_t = gross_t - (1 - keep_t) * cost        # keep = 与上期持仓(可买过滤后)的重合比例

因此与单向换手配套的正确成本 = 卖出(佣金 + 滑点 + 印花税) + 买入(佣金 + 滑点)。

【构成对照】

    实盘(滑点千1.5) 0.0046 = 佣金万三×2 0.0006 + 滑点千1.5×2 0.0030 + 卖出印花税千1 0.0010
    实盘(滑点千2)   0.0056 = 同上，滑点千2×2 0.0040
    主用档          0.0040 = 有意取「实盘略宽松一丢丢 + 整数」；≈实盘 0.87x（**不是漏算滑点**）
    压力档          0.0070 = 佣金千1.5×2 + 滑点千1.5×2 + 卖出印花税千1（最后压测用）

【印花税时变】2023-08-28 起由千一减半为万五；全样本统一用千一偏保守（暂未做时变）。
【标签约定】只写「<数字>往返(<档名>)」，**禁止**再出现 `bp/边` / `单边` 之类混用表述。
"""

COST_PRESETS = {
    # ---- 真实档（含滑点；滑点单边千1.5~千2 是常态）----
    '实盘(滑点千1.5)': 0.0046,
    '实盘(滑点千2)': 0.0056,
    # ---- 引擎主用档：实盘略宽松取整（用户有意设计，非漏算）----
    '主用档': 0.004,
    # ---- 压力测试档：standard_test 默认，回答"成本再高 1.5x 还活着吗" ----
    '压力档': 0.007,
    # ---- 历史档位（不含滑点；保留原名以免破坏既有 CLI / 归档口径）----
    '单边千二': 0.005,
    '单边千1.5': 0.004,
    '单边千一': 0.003,
}

DEFAULT_COST = COST_PRESETS['主用档']         # loop_engine --cost 默认
STRESS_COST = COST_PRESETS['压力档']          # standard_test --cost 默认
LIVE_COST = COST_PRESETS['实盘(滑点千1.5)']    # 实盘参考
COST_RT = COST_PRESETS['单边千二']            # 兼容 factor_miner.evaluate_real 的默认参数名


def resolve_cost(name_or_value):
    """档名 -> 数值；已是数值（或数字串）则原样返回。
    便于 CLI 同时支持 `--cost=0.004` 与 `--cost-name=压力档`。"""
    if isinstance(name_or_value, str):
        k = name_or_value.strip()
        if k in COST_PRESETS:
            return COST_PRESETS[k]
        return float(k)                       # 允许 "--cost-name=0.0046"
    return float(name_or_value)


def cost_label(v):
    """数值 -> 可读标签（日志/报告/文档统一用它，避免再写 bp/边）。"""
    try:
        fv = float(v)
    except (TypeError, ValueError):
        return str(v)
    for k, vv in COST_PRESETS.items():
        if abs(vv - fv) < 1e-12:
            return f'{fv:g}往返({k})'
    return f'{fv:g}往返'
