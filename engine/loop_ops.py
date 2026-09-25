# -*- coding: utf-8 -*-
"""loop_ops.py — 算子表接线 + le 绑定的本地算子（2026-09-26 L3 Step 2b-3a）

★★ 为什么单独拆出来：`UNARY`/`BINARY` 是引擎、亲本选择、LLM 引导三方共用的算子表，
  由 `ops_registry` 派生；但其中有 5 个 `('le', ...)` 绑定的本地算子（pandas 口径）
  以前住在 loop_engine 里 ⇒ 谁想用 UNARY/BINARY 都得 import 整个 loop_engine（循环依赖）。
  拆到本模块后，loop_gen / loop_llm_guide 只需 import 本模块 ✓

依赖注入（与 ops_registry 同模式）：ops_registry 不 import 本模块，由本模块把
  fastops + vars() 传进去 ⇒ 打破环 ✓（`('le', ...)` 按名取 `vars()` 里的本地函数）
"""
import numpy as np
import pandas as pd

from factor_miner import cs_rank
import ops_registry as _OPS
import fastops as _FO


def ts_delay(x, n):
    return pd.DataFrame(x).shift(n).values


def ts_delta(x, n):
    return x - pd.DataFrame(x).shift(n).values


def cs_rank_op(x):
    return cs_rank(pd.DataFrame(x)).values


def cs_demean_op(x):
    df = pd.DataFrame(x)
    return df.sub(df.mean(axis=1), axis=0).values


def cs_scale_op(x):
    r = cs_rank_op(x)
    return (r - 0.5) * 2


UNARY = _OPS.build_unary(_FO, vars())
BINARY = _OPS.build_binary(_FO, vars())
