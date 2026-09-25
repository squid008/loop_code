# -*- coding: utf-8 -*-
"""loop_dims.py — 跨量纲审查（中金审查规则之一，2026-09-26 L3 拆分）

量纲族: P=价格元 / R=比率与收益率(无量纲) / V=股数 / A=成交额元 / M=市值元 /
        L=对数标尺(ln) / Z=截面标准化(cs_rank/cs_demean/cs_scale) / C=复合(mul/div)

★ 本模块是「纯静态审查」，只依赖 `loop_expr`（Node/collect）+ `loop_fields`（叶子族），
  **不 import loop_engine**（避免循环依赖）✓
"""
from loop_fields import MF16, BARRA_LEAVES, FA_LEAVES
from loop_expr import Node, collect

_FIELD_DIM = {
    'close': 'P', 'open': 'P', 'high': 'P', 'low': 'P', 'vwap': 'P',
    'ret': 'R', 'overnight': 'R', 'intraday': 'R', 'amplitude': 'R',
    'up_shadow': 'R', 'down_shadow': 'R', 'hl_ratio': 'R', 'true_range': 'R',
    'turn_ratio': 'R', 'volume': 'V', 'ln_volume': 'L', 'ln_mktcap': 'L',
    'turnover': 'A', 'mktcap': 'M',
    # 资金流金额列(×1e4 元, 与 turnover 同量纲 A) / 量列(×100 股, 与 volume 同 V)
    **{k: 'A' for k in MF16 if k.endswith(('_buy', '_sell'))},
    **{k: 'V' for k in MF16 if k.endswith(('_bqty', '_sqty'))},
    # BARRA 风格(Z化后相对值) / 财报 PIT 比率 -> R
    **{k: 'R' for k in BARRA_LEAVES},
    **{k: 'R' for k in FA_LEAVES},
}


def dim_of(node):
    """表达式(树)的'主导量纲'; 用于 add/sub/min/max 的同量纲审查"""
    if not node.args:
        return _FIELD_DIM.get(node.op, 'X')
    op = node.op
    if op in ('cs_rank', 'cs_demean', 'cs_scale'):
        return 'Z'
    if op == 'log':
        return 'L'
    if op.startswith('corr'):
        return 'R'
    if op in ('mul', 'div'):
        return 'C'
    if op in ('add', 'sub', 'min', 'max'):
        a, b = dim_of(node.args[0]), dim_of(node.args[1])
        if a == 'Z' or b == 'Z' or a == 'C' or b == 'C':
            return 'C'
        return a if a == b else 'X'
    if isinstance(node.args[0], Node):
        return dim_of(node.args[0])
    return 'X'


def review_expr(node):
    """静态审查(中金'审查规则'之一'跨量纲运算拒绝'): None=通过, str=拒绝原因。
    不同量纲的原始尺度直接 add/sub/min/max 无金融意义(如 close+volume), 纯浪费
    回测预算 -> 生成端拦截。mul/div/corr 放行(金融常见), cs_* 后(Z)可任意组合。
    顺带毙 div(x,x)/sub(x,x) 常数退化。"""
    for x in collect(node):
        if not x.args:
            continue
        if x.op in ('add', 'sub', 'min', 'max'):
            da, db = dim_of(x.args[0]), dim_of(x.args[1])
            if da not in ('Z', 'C') and db not in ('Z', 'C') and da != db:
                return f"跨量纲{x.op}({da} vs {db}): {x}"
        if x.op in ('sub', 'div') and str(x.args[0]) == str(x.args[1]):
            return f"{x.op}(x,x) 退化为常数: {x}"
    return None
