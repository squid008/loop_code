# -*- coding: utf-8 -*-
"""ops_registry.py — ★★★ 算子表【单一事实源】（2026-09-15, 架构清扫 P0-1）

## 为什么有这个文件（要解决的问题）

加 1 个算子，历史上**要同步改 4 处代码 + 6 处文档**：

```
engine/fastops.py        算子数值实现        ← 保留（唯一真实现）
engine/loop_engine.py    UNARY/BINARY 注册表  ← ★ 本文件接管
engine/loop_critic.py    SLOW_OPS 稳定性档位  ← ★ 本文件接管
engine/loop_llm.py       A角 prompt 算子名单  ← ★ 本文件接管
```

⇒ **同一批算子名被抄了 4 份** ⇒ 改一处必漏其余 ⇒ 这就是 `tools/_test_ops_sync.py`
  当初要建出来"防漂移"的根本原因（它是在**补丁**这个结构问题，而不是根治）。

★★★ **本文件的作用**：算子只在这里**声明一次**，其余全部**派生**：
  · `loop_engine.UNARY/BINARY`  ← `build_unary()/build_binary()`
  · `loop_critic.SLOW_OPS`      ← `SLOW_OPS`
  · `loop_llm` 的 prompt 名单    ← `prompt_unary()/prompt_binary()`
  ⇒ 从此**结构上不可能漂移**（不是靠测试提醒，是根本没得抄）✓

## 绑定方式（三种）

| 写法 | 含义 | 例 |
|---|---|---|
| `('fo', 'ts_mean')` | 调 `fastops.ts_mean(x, w)` | 绝大多数窗口算子 |
| `('le', 'ts_delta')` | 调 `loop_engine` 里的本地函数 | `ts_delay/ts_delta`（pandas 实现）|
| `('fn', func)` | 直接用本文件里的纯函数 | `log/abs/neg/sign/div` |

★ 为什么传 `fastops` / `local_ns` 进来而不是直接 import：
  `loop_engine` 反过来要 import 本模块 ⇒ 本模块若 import `loop_engine` 就**循环依赖** ✗
  ⇒ 用"依赖注入"打破环 ✓（本模块只依赖 numpy）

## ⚠ 一处**有意的顺序变更**（必须记录，不能装作没发生）

旧 `UNARY` dict 的**插入顺序**是历史产物（先加短窗、后补长窗 ⇒ `ts_mean5/10/20` 之后
插了别的族，`ts_mean60/100/...` 才在后面）。本文件改为**自然的族顺序**（与 prompt 一致）。

影响面：`list(UNARY.keys())` 被 `rand_expr`/`mutate`/`_mix_weights` 当作**随机选择池**，
故**同一 RNG 种子会选到不同算子** ⇒ **候选流与旧版不同**（但算子**集合**逐个相同，见测试）。
⇒ 这是**可接受的**（版本升级本来就变了算子集），但**不能声称"零行为变化"** ✗
⇒ 安全网：`tools/_test_ops_registry.py` 断言 **算子集合与重构前逐字相同**（56+10 个）✓
"""
import numpy as np

# ============================================================ 纯函数算子（无窗口）
def _log(x):
    return np.log(np.maximum(x, 1e-9))


def _neg(x):
    return -x


def _div(a, b):
    """★ 除零保护**必须保留**：`b≈0` 处置 NaN（而不是 inf / 0）—— 与原实现逐位一致。"""
    return a / np.where(np.abs(b) > 1e-9, b, np.nan)


# ============================================================ 标志位
SLOW = 1        # 进 `loop_critic.SLOW_OPS`（低换手/稳定档偏好）
FULLWIN = 2     # 满窗语义（前 w-1 期输出 NaN）

# ============================================================ ★ 单目算子声明（唯一处）
# 格式：(算子名前缀, 窗口列表 或 None, 绑定, prompt 分组)
#   None 窗口 ⇒ 算子名 = 前缀本身（如 `log` / `cs_rank`）
UNARY_SPECS = [
    # ---- core：核心窗口族（prompt 第 1 组）----
    ('ts_mean',  [5, 10, 20, 60, 100, 120, 150, 200], ('fo', 'ts_mean'),  'core'),
    ('ts_std',   [20, 60, 100, 150, 200],              ('fo', 'ts_std'),   'core'),
    ('ts_max',   [20, 100],                            ('fo', 'ts_max'),   'core'),
    ('ts_min',   [20, 100],                            ('fo', 'ts_min'),   'core'),
    ('ts_rank',  [20, 60, 100, 200],                   ('fo', 'ts_rank'),  'core'),
    # ★ ts_delay/ts_delta 用 pandas 实现（不是 fastops）—— 保持原样，勿改语义
    ('ts_delay', [1],                                  ('le', 'ts_delay'), 'core'),
    ('ts_delta', [5, 20, 60, 120],                     ('le', 'ts_delta'), 'core'),
    ('ts_sum',   [20, 100],                            ('fo', 'ts_sum'),   'core'),
    # 无窗口的通用变换（紧跟 core 名单，与 prompt 一致）
    ('log',      None,                                 ('fn', _log),       'core'),
    ('abs',      None,                                 ('fn', np.abs),     'core'),
    ('neg',      None,                                 ('fn', _neg),       'core'),
    ('sign',     None,                                 ('fn', np.sign),    'core'),
    ('cs_rank',  None,                                 ('le', 'cs_rank_op'),   'core'),
    ('cs_demean', None,                                ('le', 'cs_demean_op'), 'core'),
    ('cs_scale', None,                                 ('le', 'cs_scale_op'),  'core'),
    # ---- ema：指数均线族（2026-09-15 §1.25）----
    #   ★ 12/26 是 MACD 标准参数 ⇒ `sub(ema12(x), ema26(x))` 即 MACD（不必单加 MACD 算子）
    ('ema',      [5, 12, 20, 26, 60],                  ('fo', 'ts_ema'),   'ema'),
    # ---- reg：回归三件套（2026-09-15 §1.26，用户点名 slope + R²）----
    #   ⚠ 满窗语义（回归要求"同一批点"）· 窗口 5/10/20/60（等比 2×/2×/3×）
    ('ts_slope', [5, 10, 20, 60],                      ('fo', 'ts_slope'), 'reg'),
    ('ts_rsqr',  [5, 10, 20, 60],                      ('fo', 'ts_rsqr'),  'reg'),
    ('ts_resi',  [5, 10, 20, 60],                      ('fo', 'ts_resi'),  'reg'),
    # ---- moment：高阶矩（分布形状）----
    #   ⚠ 只给 20/60：高阶矩需足够样本，5 点的偏度 ≈ 噪声 ⇒ 短窗无意义
    ('ts_skew',  [20, 60],                             ('fo', 'ts_skew'),  'moment'),
    ('ts_kurt',  [20, 60],                             ('fo', 'ts_kurt'),  'moment'),
]

# ============================================================ ★ 双目算子声明（唯一处）
# 格式：(算子名前缀, 窗口列表 或 None, 绑定, prompt 分组)
BINARY_SPECS = [
    ('add',  None,           ('fn', np.add),         'binary'),
    ('sub',  None,           ('fn', np.subtract),    'binary'),   # 中金: sub 出现率 94%
    ('mul',  None,           ('fn', np.multiply),    'binary'),
    ('div',  None,           ('fn', _div),           'binary'),
    ('corr', [20, 60, 100, 200], ('fo', 'ts_corr'),  'binary'),
    ('min',  None,           ('fn', np.minimum),     'binary'),
    ('max',  None,           ('fn', np.maximum),     'binary'),
]

# ============================================================ ★ 稳定性档位（唯一处）
# 长周期算子 ⇒ 天然低换手/高稳定 ⇒ B角"诊断→决策"时优先加权它们。
# ★ 这是**子集偏好**（不是全量副本）：只列"想偏好的那一小撮"。
# ★ 为什么不含 `ts_rank20`/`ts_delta*`：它们日频跳变大 ⇒ 换手高，与这一档目的相反。
SLOW_OPS = [
    'ts_mean20', 'ts_mean10', 'ts_rank60', 'ts_std60', 'ts_max20', 'ts_min20',
    'ema60', 'ts_slope60', 'ts_rsqr60',
]


# ============================================================ 构建
def _resolve(bind, fastops_mod, local_ns):
    kind, ref = bind
    if kind == 'fo':
        return getattr(fastops_mod, ref)
    if kind == 'le':
        return local_ns[ref]
    if kind == 'fn':
        return ref
    raise ValueError('未知绑定类型: %r' % (bind,))


def _build(specs, fastops_mod, local_ns):
    """把声明展开成 `{算子名: 可调用}` —— **保持声明顺序**（见文件头"顺序变更"说明）。"""
    out = {}
    for prefix, wins, bind, _group in specs:
        fn = _resolve(bind, fastops_mod, local_ns)
        for w in (wins if wins else [None]):
            if w is None:
                out[prefix] = (lambda x, _f=fn: _f(x))
            else:
                out['%s%d' % (prefix, w)] = (lambda x, _f=fn, _w=w: _f(x, _w))
    return out


def _build_binary(specs, fastops_mod, local_ns):
    out = {}
    for prefix, wins, bind, _group in specs:
        fn = _resolve(bind, fastops_mod, local_ns)
        for w in (wins if wins else [None]):
            if w is None:
                out[prefix] = (lambda a, b, _f=fn: _f(a, b))
            else:
                out['%s%d' % (prefix, w)] = (lambda a, b, _f=fn, _w=w: _f(a, b, _w))
    return out


def build_unary(fastops_mod, local_ns):
    """★ `loop_engine.UNARY` 由此派生（**不要**再手写算子字典）。"""
    return _build(UNARY_SPECS, fastops_mod, local_ns)


def build_binary(fastops_mod, local_ns):
    """★ `loop_engine.BINARY` 由此派生。"""
    return _build_binary(BINARY_SPECS, fastops_mod, local_ns)


# ============================================================ 名单 / prompt 生成
def _abbrev(prefix, wins):
    """`('ts_mean', [5,10,20])` -> `'ts_mean5/10/20'`；单窗口 -> `'ts_delay1'`。

    ★ 必须与 `tools/_test_ops_sync.py::_expand_abbrev()` 的解析口径**互为逆运算**，
      否则 prompt 覆盖检查会误报（该坑 2026-09-15 已踩过一次）。
    """
    if not wins:
        return prefix
    return '%s%s' % (prefix, '/'.join(str(w) for w in wins))


def unary_groups():
    """分组 -> [名字片段]（按声明顺序，保持 prompt 可读性）。"""
    g = {}
    for prefix, wins, _b, group in UNARY_SPECS:
        g.setdefault(group, []).append(_abbrev(prefix, wins))
    return g


def prompt_unary(group):
    """★ 自动生成 prompt 的算子名单（**语义说明仍手写在 loop_llm**，只自动化机械部分）。"""
    g = unary_groups()
    if group not in g:
        raise KeyError('未知 prompt 分组: %r（可选 %s）' % (group, sorted(g)))
    return ' '.join(g[group])


def prompt_binary():
    g = {}
    for prefix, wins, _b, _group in BINARY_SPECS:
        g.setdefault('list', []).append(_abbrev(prefix, wins))
    return ' '.join(g['list'])


def unary_names(fastops_mod=None, local_ns=None):
    """全部单目算子名（**自包含**：不传参也能列名，供测试/文档用）。

    ★ 不传参时只做**名单**展开，不解析绑定 ⇒ 无依赖、快。
    """
    out = []
    for prefix, wins, _b, _g in UNARY_SPECS:
        for w in (wins if wins else [None]):
            out.append(prefix if w is None else '%s%d' % (prefix, w))
    return out


def binary_names():
    out = []
    for prefix, wins, _b, _g in BINARY_SPECS:
        for w in (wins if wins else [None]):
            out.append(prefix if w is None else '%s%d' % (prefix, w))
    return out
