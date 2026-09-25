# -*- coding: utf-8 -*-
"""loop_gen.py — 表达式生成 / 亲本选择策略（2026-09-26 L3 Step 2b-3b）

承载：DEFAULT_CFG（中金五策略配比）+ 随机生成 / 变异 / 交叉 / 扰动 / 亲本选择。

★ 依赖：loop_expr（Node/collect）+ loop_ops（UNARY/BINARY）+ loop_fields（叶子族）
  —— 不 import loop_engine（无循环依赖）✓
"""
import numpy as np

from loop_expr import Node, collect
from loop_ops import UNARY, BINARY
from loop_fields import LEAVES, MF16, BARRA_LEAVES, FA_LEAVES


# 中金五策略配比: 变异25 / 交叉25 / 扰动15 / 随机探索15 / LLM机制引导20
# 本表键序=变异/交叉/扰动/引导/随机 -> mix=[0.25,0.25,0.15,0.20,0.15] 即引导20随机15
DEFAULT_CFG = dict(leaf_w={}, op_bias={}, depth=[2, 3, 4],
                   mix=[0.25, 0.25, 0.15, 0.20, 0.15],
                   min_stab=0.30, decorr=0.75, fsa_th=0.15)


def _wt(d, k):
    """取权重：**存在且非 None** 才用它，否则回退 1.0（均匀）✓

    ★★ 2026-09-17（修引擎秒崩的加固层）：`dict.get(k, 1.0)` **只在键不存在时**给默认值 ——
      若键存在但值是 `None`，它照样返回 `None` ⇒ `rng.choices(weights=[None,...])` 直接抛异常 ✗
      （实测根因在 `loop_critic._set_param`，已单独修；这里是**第二道防线**：
       任何来源的 None（旧 state / 人工编辑 / 未来的新代码）都不该让整个池停摆一整晚）
       ⚠ 用 `is None` 判断而不是 `or` —— **0 权重是有意义的**（= 永不抽这个叶子），不能被当成 None ✓
    """
    v = (d or {}).get(k)
    return 1.0 if v is None else v


def _clean_cfg(cfg):
    """把 cfg 里 `leaf_w`/`op_bias` 的 **None 值剔除**（= 回到"该键不存在" ⇒ 均匀权重）✓

    ★★ 2026-09-17（"引擎秒崩"的**自愈**层）：v1.17.1 之前 `loop_critic._set_param` 会把棘轮
      回退的 `old=None` 当真值写进 cfg ⇒ 这些脏值**如果已被存进 state 就会一直崩下去** ✗
      ⇒ 读 state 时先洗一遍（配合 `_wt` 的第二道防线，双保险）✓
    """
    if not isinstance(cfg, dict):
        return dict(DEFAULT_CFG)
    out = dict(cfg)
    for k in ('leaf_w', 'op_bias'):
        d = out.get(k)
        if isinstance(d, dict):
            out[k] = {a: b for a, b in d.items() if b is not None}
    return out


def pick_leaf(rng, cfg):
    w = [_wt(cfg.get('leaf_w'), l) for l in LEAVES]
    return rng.choices(LEAVES, weights=w, k=1)[0]


def pick_op(rng, cfg, pool):
    w = [_wt(cfg.get('op_bias'), o) for o in pool]
    return rng.choices(pool, weights=w, k=1)[0]


def rand_expr(rng, depth=3, cfg=None):
    cfg = cfg or DEFAULT_CFG
    if depth <= 0 or rng.random() < 0.25:
        return Node(pick_leaf(rng, cfg), [])
    r = rng.random()
    if r < 0.45:
        return Node(pick_op(rng, cfg, list(UNARY.keys())),
                    [rand_expr(rng, depth - 1, cfg)])
    return Node(pick_op(rng, cfg, list(BINARY.keys())),
                [rand_expr(rng, depth - 1, cfg), rand_expr(rng, depth - 1, cfg)])


def eval_expr(node, B, cache=None):
    if cache is not None and node.key() in cache:
        return cache[node.key()]
    if not node.args:
        v = B[node.op]
    elif len(node.args) == 1:
        v = UNARY[node.op](eval_expr(node.args[0], B, cache))
    else:
        a = eval_expr(node.args[0], B, cache)
        b = eval_expr(node.args[1], B, cache)
        v = BINARY[node.op](a, b)
    v = np.asarray(v, dtype=np.float32)
    if cache is not None:
        cache[node.key()] = v
    return v


def mutate(node, rng):
    """随机替换一个子树"""
    nodes = collect(node)
    tgt = rng.choice(nodes)
    tgt.op = rng.choice(list(UNARY.keys())) if len(tgt.args) == 1 else \
        (rng.choice(list(BINARY.keys())) if len(tgt.args) == 2
         else rng.choice(LEAVES))
    return node


# ---- 叶子字段族(写档用: loop_archive.csv 的 cat/leaf 列, 保证人读可筛) ----
LEAF_CAT = {
    'close': '价格', 'open': '价格', 'high': '价格', 'low': '价格', 'vwap': '价格',
    'ret': '收益率', 'overnight': '跳空', 'intraday': '日内收益',
    'amplitude': '振幅', 'hl_ratio': '振幅', 'true_range': '振幅',
    'up_shadow': '影线', 'down_shadow': '影线',
    'volume': '量', 'ln_volume': '量',
    'turnover': '成交额', 'turn_ratio': '换手率',
    'mktcap': '市值', 'ln_mktcap': '市值',
    # 扩展: 资金流 / 风格 / 财报
    **{k: '资金流' for k in MF16},
    **{k: '风格' for k in BARRA_LEAVES},
    **{k: '财报' for k in FA_LEAVES},
}


def leaf_parts(node):
    """按出现顺序提取去重叶子字段; 返回 (字段顿号串, 分类顿号串)"""
    cats, names = [], []
    for x in collect(node):
        if not x.args and x.op not in names:
            names.append(x.op)
            cats.append(LEAF_CAT.get(x.op, x.op))
    return '、'.join(names), '、'.join(cats)


def crossover(n1, n2, rng):
    a = rng.choice(collect(n1))
    b = rng.choice(collect(n2))
    a.op, a.args = b.op, b.args
    return n1


# ===================== 亲本选择策略（2026-09-14, loop_todo §1.3-C）=====================
# ★ 为什么值得抄（roadmap §8.21-⑥ #5）：我们原来只有「**堵**」的手段
#   （`--fam_quota` 配额、`fam_block_thr` 黑名单、`--decorr` 去相关），**没有「疏」** ——
#   即**没有显式的"探索/利用配比"**。而当前亲本抽取是 `rng.choice(seeds)`（**全池均匀随机**）
#   ⇒ ★★ **L1 里第 1 名和第 30 名被选中的概率完全一样，排名信息一点没用上**。
#   QuantaAlpha 的 `parent_selection_strategy` 族（`configs/experiment.yaml:83-92`）
#   补的正是这一层：`best`(纯利用) / `random`(纯探索) / `weighted` / `weighted_inverse` /
#   **`top_percent_plus_random`(top30% 保底 + 余量随机)**。
PARENT_SEL_MODES = ('uniform', 'best', 'top_percent_plus_random')


def pick_parent(rng, seeds, mode='uniform', thr=0.30):
    """从亲本池里挑**一个**亲本。

    :param seeds: 亲本池 —— ★ **必须按 score 降序**（引擎里由
        `l1.sort_values('score', ascending=False)`(L1859) -> `l1.head(30)['node']` 保证，
        且 state 存取都保留顺序）。
    :param mode:  `uniform`（默认 = 现状，行为不变）/ `best` / `top_percent_plus_random`
    :param thr:   仅 `top_percent_plus_random` 用；top 段比例（对齐 QuantaAlpha 的
        `top_percent_threshold: 0.3`）

    **`top_percent_plus_random` 的实现依据**（照抄语义，不照抄代码形状）：
    QuantaAlpha `pipeline/evolution/crossover.py:423-437` 是**批量选名额**：
    ```python
    top_n = max(1, int(len(candidates) * top_percent_threshold))   # top 30%
    top_candidates  = sorted_candidates[:top_n]
    rest_candidates = sorted_candidates[top_n:]
    still_needed = num_needed - len(top_candidates)
    ... "从 rest 里随机补齐" ...
    ```
    ⇒ 它的语义是「**一批名额里 ~30% 给 top 段、其余随机**」。
    我们这里是**逐个抽亲本**，等价实现 = **以 `thr` 的概率取 top 段、否则从全池随机**。

    ★★ 一个**容易写错的关键细节**：「否则」必须是**从全池随机**，**不能**是"只从 rest 随机"：
    ```python
    # ✗ 错的写法（退化成 uniform，功能白做）：
    #     return rng.choice(seeds[:n_top] if rng.random() < thr else seeds[n_top:])
    #   n=30, n_top=9 时 P(某个 top)=0.3/9=0.0333, P(某个 rest)=0.7/21=0.0333 ⇒ **完全相同** ✗
    # ✓ 正确（全池）：P(某个 top)=0.3/9 + 0.7/30=0.0567, P(某个 rest)=0.7/30=0.0233
    #   ⇒ top 段权重是 rest 的 **2.43×** ✓ 这才有"利用"的意思。
    ```
    （QuantaAlpha 的 `rest_candidates` 只是"**补剩余名额**"用的来源，不是唯一来源 ✓）

    ★ **诚实说明一处口子差异**：QuantaAlpha 的 `candidates` 是**全部轨迹**；我们的 `seeds`
      已经是 `l1.head(30)`（**已截断到 L1 前 30**）⇒ 我们的 `top 30%` 是
      **"种子池内的前 30%"**（30 个里的 9 个），**两级截断 = 更偏利用**。
      想更偏探索就调大 `--parent_top_pct`（→1.0 即退化成 `uniform`）。
    """
    if not seeds:
        return None
    if mode == 'best':
        return seeds[0]
    if mode == 'top_percent_plus_random':
        n_top = max(1, int(len(seeds) * float(thr)))
        if len(seeds) <= n_top or rng.random() < float(thr):
            return rng.choice(seeds[:n_top])
        return rng.choice(seeds)          # ★ 全池（含 top 段）—— 见上面「容易写错」那段
    return rng.choice(seeds)              # uniform：默认 = 现状，行为不变


def perturb(node, rng):
    """参数扰动: 换一个同族算子(如 ts_mean20 -> ts_mean60)"""
    nodes = collect(node)
    tgt = rng.choice(nodes)
    if tgt.op.startswith('ts_') and any(c.isdigit() for c in tgt.op):
        fam = ''.join(c for c in tgt.op if not c.isdigit())
        alt = [k for k in list(UNARY.keys()) + list(BINARY.keys())
               if k.startswith(fam)]
        if alt:
            tgt.op = rng.choice(alt)
    return node



