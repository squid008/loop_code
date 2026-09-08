# -*- coding: utf-8 -*-
"""
中金 Loop Engineering 自动化因子发现引擎(我方实现)
=====================================================
闭环: 生成 -> L1粗筛(批量IC) -> L2精筛(费后回测+11项过滤) -> L3入库(去重) -> 下一代
参考中金《基于Loop Engineering的自动化因子发现引擎》:
  16939 候选 -> 69 因子(成功率0.41%), Top5等权超额夏普3.14 / 年化超额18.3%

与中金原版的差异(我方改进):
  1. **验证端用费后口径** evaluate_real(): 扣往返成本0.5% + 涨停不可买 + 跌停顺延卖出
     (中金的夏普>0.5 / Calmar>1.0 本就是费后标准, 必须配套费后验证端)
  2. L1 用**批量向量化IC**粗筛(比逐因子 evaluate 快30倍), 否则规模上不去
  3. FSA(频繁子树规避) 用子树哈希计数, 抑制重复表达式

五维演化(中金配比): 变异25% / 交叉25% / 参数扰动15% / 随机探索15% / 语义引导20%

用法:
    python loop_engine.py --gen=1 --n=600        # 第1代 600 个候选
    python loop_engine.py --gen=2 --n=600        # 第2代(读上一代种子池)
"""
import os
import sys
import gc
import json
import time
import random
import pickle
import argparse
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from factor_miner import (load_panel, prepare, get_universe, cs_rank,
                          evaluate_real, START, FWD, COST_PRESETS)

STATE = os.path.join(HERE, 'loop_state.pkl')
ARCHIVE = os.path.join(HERE, 'loop_archive.csv')
JOURNAL = os.path.join(os.path.dirname(HERE), 'docs', 'loop_journal.md')  # B角诊断日志(loop_code/docs)

# 默认搜索策略(B角可动态调整)
DEFAULT_CFG = dict(leaf_w={}, op_bias={}, depth=[2, 3, 4],
                   mix=[0.25, 0.25, 0.15, 0.15, 0.20],      # 变异/交叉/扰动/引导/随机
                   min_stab=0.30, decorr=0.75, fsa_th=0.15)

# ===================== 1. 基础字段 =====================
FIELDS = ['close', 'open', 'high', 'low', 'volume', 'turnover', 'mktcap']
_BASE = None
L1_STOCKS = 2000          # L1 粗筛抽样的股票数(越小越快, 但IC估计误差越大)
L1_ROWS = None
L1_COLS = None
_LRU = {}                 # 跨批次复用子树求值结果(种子演化共享大量子树)
LRU_MAX = 400


def base_fields():
    """返回 {name: (T,S) float32} 基础字段 + 日期/列"""
    global _BASE
    if _BASE is not None:
        return _BASE
    P = load_panel(FIELDS)
    P = prepare(P)
    close = P['close'].astype('float64')
    dates = close.index.values
    cols = list(close.columns)
    B = {
        'close': close.values.astype(np.float32),
        'open': P['open'].reindex(index=dates, columns=cols).values.astype(np.float32),
        'high': P['high'].reindex(index=dates, columns=cols).values.astype(np.float32),
        'low': P['low'].reindex(index=dates, columns=cols).values.astype(np.float32),
        'volume': P['volume'].reindex(index=dates, columns=cols).values.astype(np.float32),
        'turnover': P['turnover'].reindex(index=dates, columns=cols).values.astype(np.float32),
        'mktcap': P['mktcap'].reindex(index=dates, columns=cols).values.astype(np.float32),
    }
    # 衍生
    B['vwap'] = (B['turnover'] / np.maximum(B['volume'], 1e-9)).astype(np.float32)
    B['ret'] = (pd.DataFrame(B['close']).pct_change().values).astype(np.float32)
    B['amt'] = B['turnover']
    B['ln_mktcap'] = np.log(np.maximum(B['mktcap'], 1e-9)).astype(np.float32)
    B['ln_volume'] = np.log(np.maximum(B['volume'], 1e-9)).astype(np.float32)
    B['turn_ratio'] = (B['turnover'] / np.maximum(B['mktcap'], 1e-9)).astype(np.float32)
    # ---- 派生字段(★中金研报: overnight 出现率 85% / amplitude 63%, 是核心信号源) ----
    c, o, h, l = B['close'], B['open'], B['high'], B['low']
    pc = np.vstack([np.full((1, c.shape[1]), np.nan), c[:-1]]).astype(np.float32)  # 昨收
    rng = (h - l).astype(np.float32)
    with np.errstate(invalid='ignore', divide='ignore'):
        B['overnight'] = (o / pc - 1.0).astype(np.float32)          # 隔夜跳空 ★
        B['intraday'] = (c / o - 1.0).astype(np.float32)            # 日内收益
        B['amplitude'] = (rng / pc).astype(np.float32)              # 振幅 ★
        B['up_shadow'] = ((h - np.maximum(o, c)) /
                          np.where(rng > 1e-9, rng, np.nan)).astype(np.float32)
        B['down_shadow'] = ((np.minimum(o, c) - l) /
                            np.where(rng > 1e-9, rng, np.nan)).astype(np.float32)
        B['hl_ratio'] = (h / np.where(l > 1e-9, l, np.nan)).astype(np.float32)
        B['true_range'] = (np.maximum(
            rng, np.maximum(np.abs(h - pc), np.abs(l - pc))) / pc).astype(np.float32)
    del pc, rng
    # ★L1 子面板: 粗筛不需要全样本(瓶颈是内存带宽, 不是计算)。
    #   时间只取 START 之后 + 截面随机抽样 -> 数据量降到 ~1/4, 实测整体提速 3~4 倍。
    #   L1 只是排序用, 抽样误差可接受; L2 精筛仍用全样本。
    global L1_ROWS, L1_COLS
    L1_ROWS = np.where(dates >= START)[0]
    nsub = min(close.shape[1], L1_STOCKS)
    L1_COLS = np.sort(np.random.default_rng(20240917).choice(
        close.shape[1], nsub, replace=False))
    B_sub = {k: v[np.ix_(L1_ROWS, L1_COLS)] for k, v in B.items()}
    _BASE = dict(B=B, B_sub=B_sub, dates=dates, cols=cols, close=close)
    return _BASE


# ===================== 2. 算子 =====================
def ts_mean(x, w):
    return pd.DataFrame(x).rolling(w, min_periods=max(2, w // 2)).mean().values


def ts_std(x, w):
    return pd.DataFrame(x).rolling(w, min_periods=max(2, w // 2)).std().values


def ts_sum(x, w):
    return pd.DataFrame(x).rolling(w, min_periods=max(2, w // 2)).sum().values


def ts_max(x, w):
    return pd.DataFrame(x).rolling(w, min_periods=max(2, w // 2)).max().values


def ts_min(x, w):
    return pd.DataFrame(x).rolling(w, min_periods=max(2, w // 2)).min().values


def ts_rank(x, w):
    """过去w日当前值的分位(快)"""
    mn = ts_min(x, w)
    mx = ts_max(x, w)
    return (x - mn) / (mx - mn + 1e-12)


def ts_delay(x, n):
    return pd.DataFrame(x).shift(n).values


def ts_delta(x, n):
    return x - pd.DataFrame(x).shift(n).values


def ts_corr(x, y, w):
    return pd.DataFrame(x).rolling(w, min_periods=max(3, w // 2)).corr(
        pd.DataFrame(y)).values


def ts_max_op(x):
    import fastops
    return fastops.ts_max(x, 20)


def ts_min_op(x):
    import fastops
    return fastops.ts_min(x, 20)


def ts_corr20_op(a, b):
    import fastops
    return fastops.ts_corr(a, b, 20)


def ts_corr60_op(a, b):
    import fastops
    return fastops.ts_corr(a, b, 60)


def cs_rank_op(x):
    return cs_rank(pd.DataFrame(x)).values


def cs_demean_op(x):
    df = pd.DataFrame(x)
    return df.sub(df.mean(axis=1), axis=0).values


def cs_scale_op(x):
    r = cs_rank_op(x)
    return (r - 0.5) * 2


def _m(x, w):
    import fastops
    return fastops.ts_mean(x, w)


def _s(x, w):
    import fastops
    return fastops.ts_std(x, w)


def _r(x, w):
    import fastops
    return fastops.ts_rank(x, w)


def _mx(x, w):
    import fastops
    return fastops.ts_max(x, w)


def _mn(x, w):
    import fastops
    return fastops.ts_min(x, w)


def _sm(x, w):
    import fastops
    return fastops.ts_sum(x, w)


def _cr(a, b, w):
    import fastops
    return fastops.ts_corr(a, b, w)


UNARY = {
    # 短中窗口(原)
    'ts_mean5': lambda x: _m(x, 5),
    'ts_mean10': lambda x: _m(x, 10),
    'ts_mean20': lambda x: _m(x, 20),
    'ts_std20': lambda x: _s(x, 20),
    'ts_std60': lambda x: _s(x, 60),
    'ts_max20': lambda x: _mx(x, 20),
    'ts_min20': lambda x: _mn(x, 20),
    'ts_rank20': lambda x: _r(x, 20),
    'ts_rank60': lambda x: _r(x, 60),
    'ts_delay1': lambda x: ts_delay(x, 1),
    'ts_delta5': lambda x: ts_delta(x, 5),
    'ts_delta20': lambda x: ts_delta(x, 20),
    'ts_sum20': lambda x: _sm(x, 20),
    # ★长窗口(中金: 51-100天52次 / 151-200天23次, 明显中长窗口偏好)
    'ts_mean60': lambda x: _m(x, 60),
    'ts_mean100': lambda x: _m(x, 100),
    'ts_mean120': lambda x: _m(x, 120),
    'ts_mean150': lambda x: _m(x, 150),
    'ts_mean200': lambda x: _m(x, 200),
    'ts_std100': lambda x: _s(x, 100),
    'ts_std150': lambda x: _s(x, 150),
    'ts_std200': lambda x: _s(x, 200),
    'ts_rank100': lambda x: _r(x, 100),
    'ts_rank200': lambda x: _r(x, 200),
    'ts_max100': lambda x: _mx(x, 100),
    'ts_min100': lambda x: _mn(x, 100),
    'ts_delta60': lambda x: ts_delta(x, 60),
    'ts_delta120': lambda x: ts_delta(x, 120),
    'ts_sum100': lambda x: _sm(x, 100),
    'log': lambda x: np.log(np.maximum(x, 1e-9)),
    'abs': np.abs,
    'neg': lambda x: -x,
    'sign': np.sign,
    'cs_rank': cs_rank_op,
    'cs_demean': cs_demean_op,
    'cs_scale': cs_scale_op,
}

BINARY = {
    'add': lambda a, b: a + b,
    'sub': lambda a, b: a - b,            # 中金: sub 出现率 94%(差值/背离结构为主)
    'mul': lambda a, b: a * b,
    'div': lambda a, b: a / np.where(np.abs(b) > 1e-9, b, np.nan),
    'corr20': lambda a, b: _cr(a, b, 20),
    'corr60': lambda a, b: _cr(a, b, 60),
    'corr100': lambda a, b: _cr(a, b, 100),
    'corr200': lambda a, b: _cr(a, b, 200),
    'min': lambda a, b: np.minimum(a, b),
    'max': lambda a, b: np.maximum(a, b),
}

LEAVES = ['close', 'open', 'high', 'low', 'volume', 'turnover', 'mktcap',
          'vwap', 'ret', 'turn_ratio', 'ln_mktcap', 'ln_volume',
          # ★派生字段(中金 overnight 85% / amplitude 63%)
          'overnight', 'intraday', 'amplitude', 'up_shadow', 'down_shadow',
          'hl_ratio', 'true_range']

# ===================== 3. 表达式 =====================
class Node(object):
    __slots__ = ('op', 'args')

    def __init__(self, op, args):
        self.op = op
        self.args = args

    def __str__(self):
        if not self.args:
            return self.op
        return f"{self.op}({', '.join(str(a) for a in self.args)})"

    def key(self):
        """结构哈希(用于FSA), 忽略叶子名差异时可用 op-only"""
        if not self.args:
            return self.op
        return (self.op, tuple(a.key() if isinstance(a, Node) else a
                               for a in self.args))

    def size(self):
        return 1 + sum(a.size() for a in self.args if isinstance(a, Node))


def norm_op(op):
    """算子族归一化: ts_mean20 -> ts_mean / corr60 -> corr (剥窗口数字, 保留算子族)"""
    for p in ('ts_mean', 'ts_std', 'ts_sum', 'ts_max', 'ts_min',
              'ts_rank', 'ts_delay', 'ts_delta', 'corr'):
        if op.startswith(p):
            return p
    return op


def skeleton(node):
    """骨架键 = 算子族名 + 树结构 + 叶子身份(保留叶子名), 完全剥离窗口数字。
    对齐中金 FSA 的'抽象因子结构': ts_std60/ts_std100/ts_std150 视为同一骨架,
    只换窗口的同族候选会被识别为重复骨架, 由冻结/入库上限机制拦下。"""
    if not node.args:
        return node.op
    return norm_op(node.op) + '(' + ','.join(
        skeleton(a) if isinstance(a, Node) else str(a)
        for a in node.args) + ')'


def skeleton_freq(nodes):
    """统计一组表达式的完整骨架频次(用于FSA冻结与库内骨架去重)"""
    c = {}
    for nd in nodes:
        s = skeleton(nd)
        c[s] = c.get(s, 0) + 1
    return c


def subtree_skels(node):
    """候选的全部【非叶子】子树骨架集合(叶子/字段名不算结构, 防'某字段出现>15%'误冻结)"""
    out = set()
    for x in collect(node):
        if x.args:
            out.add(skeleton(x))
    return out


def has_frozen_skel(node, frozen):
    """候选是否含任一已冻结的结构骨架(中金: 冻结骨架禁止复用 -> 生成端丢弃/入库端审查)"""
    return bool(frozen and (subtree_skels(node) & set(frozen)))


# ===================== 跨量纲审查(中金审查规则之一) =====================
# 量纲族: P=价格元 / R=比率与收益率(无量纲) / V=股数 / A=成交额元 / M=市值元 /
#         L=对数标尺(ln) / Z=截面标准化(cs_rank/cs_demean/cs_scale) / C=复合(mul/div)
_FIELD_DIM = {
    'close': 'P', 'open': 'P', 'high': 'P', 'low': 'P', 'vwap': 'P',
    'ret': 'R', 'overnight': 'R', 'intraday': 'R', 'amplitude': 'R',
    'up_shadow': 'R', 'down_shadow': 'R', 'hl_ratio': 'R', 'true_range': 'R',
    'turn_ratio': 'R', 'volume': 'V', 'ln_volume': 'L', 'ln_mktcap': 'L',
    'turnover': 'A', 'mktcap': 'M',
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


# ===================== 失败模式库(中金: 失败表达式写入失败库, 生成阶段自动排除) =====================
# fail_lib = {骨架: dict(try_=参与测试数, ok=通过L1数, fail=失败数, rs={原因:计数}, last=最近代)}
def flib_mark(fail_lib, node, gen, ok, reason=''):
    e = fail_lib.setdefault(skeleton(node),
                            dict(try_=0, ok=0, fail=0, rs={}, last=gen))
    e['try_'] += 1
    e['last'] = gen
    if ok:
        e['ok'] += 1
    else:
        e['fail'] += 1
        e['rs'][reason] = e['rs'].get(reason, 0) + 1


def fail_lib_cleanup(fail_lib, gen, keep_gen=5):
    """滚动: 超过 keep_gen 代未再出现的骨架淘汰, 防库膨胀"""
    return {s: e for s, e in fail_lib.items() if e['last'] >= gen - keep_gen}


def bad_skels(fail_lib, gen, min_fail=3, rate=0.6, keep_gen=5):
    """失败模式 = 骨架试了 min_fail 次以上、从未通过L1、失败率>=rate -> 生成阶段排除"""
    return {s for s, e in fail_lib.items()
            if e['last'] >= gen - keep_gen and e['fail'] >= min_fail
            and e['ok'] == 0 and e['fail'] / max(e['try_'], 1) >= rate}


def pick_leaf(rng, cfg):
    w = [cfg['leaf_w'].get(l, 1.0) for l in LEAVES]
    return rng.choices(LEAVES, weights=w, k=1)[0]


def pick_op(rng, cfg, pool):
    w = [cfg['op_bias'].get(o, 1.0) for o in pool]
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


def collect(node, out=None):
    out = [] if out is None else out
    out.append(node)
    for a in node.args:
        if isinstance(a, Node):
            collect(a, out)
    return out


def crossover(n1, n2, rng):
    a = rng.choice(collect(n1))
    b = rng.choice(collect(n2))
    a.op, a.args = b.op, b.args
    return n1


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


# ===================== 4. L1 批量 IC =====================
def rank_rows(X):
    """逐行排名(0~1), NaN 置 NaN; 用两次 argsort"""
    Xf = np.where(np.isfinite(X), X, np.inf)
    order = np.argsort(np.argsort(Xf, axis=1), axis=1).astype(np.float32)
    n = np.isfinite(X).sum(axis=1, keepdims=True)
    r = order / np.maximum(n - 1, 1)
    r[~np.isfinite(X)] = np.nan
    return r


def factor_stability(V, dates=None, start=START, fwd=FWD):
    """因子稳定性 = 相邻调仓日截面rank的相关性(均值)
    稳定性低 -> 每次调仓Top组大换血 -> 换手高 -> 费后被成本吃光
    这是 L1 必须看、只看IC会漏掉的关键指标
    """
    sub = V[::fwd] if dates is None else V[dates >= start][::fwd]
    R = rank_rows(sub)
    cs = []
    for i in range(len(R) - 1):
        a, b = R[i], R[i + 1]
        m = np.isfinite(a) & np.isfinite(b)
        if m.sum() < 50:
            continue
        sa, sb = a[m].std(), b[m].std()
        if sa > 0 and sb > 0:
            cs.append(np.corrcoef(a[m], b[m])[0, 1])
    return float(np.nanmean(cs)) if cs else np.nan


def batch_ic(Fs, fwd_ret, U, dates=None, start=START):
    """Fs: list of (T,S); 返回 IC均值 / IC_IR / IC矩阵。
    dates=None 时按已切好的(子)面板直接使用。"""
    if dates is None:
        Uv, Rv = U, fwd_ret
        Fs_ = Fs
    else:
        m = (dates >= start)
        Uv, Rv = U[m], fwd_ret[m]
        Fs_ = [F[m] for F in Fs]
    Rr = rank_rows(Rv)
    ics = []
    for F in Fs_:
        Fr = rank_rows(F)
        X = np.where(Uv, Fr, np.nan)
        Y = np.where(Uv, Rr, np.nan)
        cnt = np.isfinite(X) & np.isfinite(Y)
        n = cnt.sum(axis=1)
        X0 = np.where(cnt, X, 0.0)
        Y0 = np.where(cnt, Y, 0.0)
        Xm = X0.sum(axis=1) / np.maximum(n, 1)
        Ym = Y0.sum(axis=1) / np.maximum(n, 1)
        Xz = np.where(cnt, X - Xm[:, None], 0.0)
        Yz = np.where(cnt, Y - Ym[:, None], 0.0)
        num = (Xz * Yz).sum(axis=1)
        d1 = np.sqrt((Xz ** 2).sum(axis=1))
        d2 = np.sqrt((Yz ** 2).sum(axis=1))
        c = np.where((d1 > 0) & (d2 > 0) & (n >= 50), num / (d1 * d2 + 1e-12), np.nan)
        ics.append(c)
    IC = np.array(ics)                       # (n_factors, n_days)
    mu = np.nanmean(IC, axis=1)
    sd = np.nanstd(IC, axis=1)
    ir = mu / np.where(sd > 0, sd, np.nan)
    return mu, ir, IC


# ===================== 5. 主循环 =====================
def run(args):
    t0 = time.time()
    rng = random.Random(args.seed)
    np.random.seed(args.seed)
    base = base_fields()
    B, dates, cols, close = base['B'], base['dates'], base['cols'], base['close']
    T, S = close.shape

    U = get_universe().reindex(index=dates, columns=cols).fillna(False).values
    fwd_ret = (close.shift(-(1 + FWD)) / close.shift(-1) - 1).values

    # 载入上一代: 种子 + B角建议
    seeds, fsa, prev_l1, prev_l2, bank = [], {}, None, None, []
    frozen = []                # FSA冻结骨架列表(中金: 超15%被禁止复用)
    fail_lib = {}              # 失败模式库(骨架级成败滚动统计, 中金: 生成阶段排除)
    cfg = dict(DEFAULT_CFG)
    if os.path.exists(STATE):
        with open(STATE, 'rb') as f:
            st = pickle.load(f)
        seeds = st.get('seeds', [])
        fsa = st.get('fsa', {})
        if not fsa.pop('v2', False):
            fsa = {}      # 旧格式(md5子树哈希键)与骨架口径不兼容 -> 重新累计
        prev_l1 = st.get('last_l1', None)
        prev_l2 = st.get('last_l2', None)
        bank = st.get('bank', [])          # 历代入库因子(node) —— decorr 的对比对象
        frozen = st.get('frozen', [])
        fail_lib = st.get('fail_lib', {})  # 失败模式库
        cfg = st.get('cfg', cfg)
        print(f"载入上一代种子 {len(seeds)} 个, 入库因子 {len(bank)} 个, "
              f"冻结骨架 {len(frozen)} 个, 失败库 {len(fail_lib)} 条, "
              f"已测 {st.get('n_tested', 0)} 个候选")

    # ---- B角: 先审查上一代, 再据此定本代搜索策略 ----
    import loop_critic as critic
    if prev_l1 is not None and len(prev_l1):
        diag = critic.diagnose(prev_l1, prev_l2, args.gen - 1)
        cfg, reasons = critic.suggest(diag, cfg)
        print("\n[B角建议] 本代搜索策略:")
        for r in reasons:
            print("  -", r)
    else:
        print("\n[B角] 首代, 使用默认策略")
    # B角建议落地(命令行显式指定则优先)
    if args.decorr < 0:
        args.decorr = cfg.get('decorr', 0.0)
    if args.fsa_th < 0:
        args.fsa_th = cfg.get('fsa_th', 0.0)   # 0=关闭FSA冻结
    args.min_stab = cfg.get('min_stab', args.min_stab)
    args.bank_skel_max = cfg.get('bank_skel_max', args.bank_skel_max)
    print(f"  本代参数: min_stab={args.min_stab:.2f}  decorr={args.decorr:.2f}  "
          f"fsa_th={args.fsa_th:.2f}  bank同骨架上限={args.bank_skel_max}  "
          f"depth={cfg['depth']}")
    if frozen:
        print(f"  [FSA] 本代生效冻结骨架 {len(frozen)} 个(生成时禁止复用)")

    # ---- 失败模式库: 载入后按滚动窗口算出本代应排除的'坏骨架' ----
    if args.dim_review < 0:
        args.dim_review = 1                      # 跨量纲审查默认开启
    # 命令行显式指定则优先, 否则用 B角cfg(默认开: fail_rate=0.6, min_fail=3)
    if args.fail_rate < 0:
        args.fail_rate = cfg.get('fail_rate', 0.6)
    if args.min_fail <= 0:
        args.min_fail = cfg.get('min_fail', 3)
    bad = bad_skels(fail_lib, args.gen, min_fail=args.min_fail,
                    rate=args.fail_rate) if args.fail_rate > 0 else set()
    if bad:
        print(f"  [失败库] 本代排除坏骨架 {len(bad)} 个"
              f"(失败>={args.min_fail}次 全败率>={args.fail_rate:.0%})")

    # ---- 生成候选(按B角给的五维配比) ----
    # ★gen13修复: cut为累积上界, 判重/分支原来写成 cut[i] 相加 -> 数值>1恒真,
    # 使 r<cut0+cut1+cut2 永远成立: guided(引导族)与rand(纯随机)从不会被执行,
    # 代代只在seeds内打转 -> 重复爆炸。 现改回 r<cut[2](seed三操作) / r<cut[3](引导) / 否则随机。
    m = cfg['mix']
    cut = [m[0], m[0] + m[1], m[0] + m[1] + m[2], m[0] + m[1] + m[2] + m[3]]
    cands, seen = [], set()        # seen: 表达式级判重(原[in list] O(n²) -> O(1))
    n_skip_fsa = n_skip_dim = n_skip_bad = n_skip_dup = 0
    n_tries = dup_streak = 0
    rand_only = False              # 兜底: 连续重复过多/超时 -> 纯随机硬凑产量
    MAX_TRY = args.n * 30
    while len(cands) < args.n and n_tries < MAX_TRY:
        n_tries += 1
        if not rand_only and n_tries > args.n * 12:
            print(f"  [生成] 达{args.n*12}次仍差{args.n-len(cands)}个 -> 转纯随机兜底",
                  flush=True)
            rand_only = True
        if rand_only:
            node = rand_expr(rng, depth=rng.choice(cfg['depth']), cfg=cfg)
        else:
            r = rng.random()
            if seeds and r < cut[2]:
                s = rng.choice(seeds)
                node = clone(s)
                q = rng.random()
                den = max(m[0] + m[1] + m[2], 1e-9)
                if q < m[0] / den:
                    node = mutate(node, rng)
                elif q < (m[0] + m[1]) / den:
                    node = crossover(node, clone(rng.choice(seeds)), rng)
                else:
                    node = perturb(node, rng)
            elif r < cut[3]:
                node = guided_expr(rng, cfg)
            else:
                node = rand_expr(rng, depth=rng.choice(cfg['depth']), cfg=cfg)
        # 跨量纲审查(中金: 跨量纲运算拒绝): close+volume 之类荒谬组合直接重抽
        if args.dim_review > 0 and review_expr(node):
            n_skip_dim += 1
            continue
        # 失败模式库: 多次全败的坏骨架 -> 生成阶段自动排除(中金)
        if args.fail_rate > 0 and bad and has_frozen_skel(node, bad):
            n_skip_bad += 1
            continue
        # FSA: 含已冻结骨架的候选禁止复用(中金"冻结骨架不再生成"); 至多重试2次随机探索
        if args.fsa_th > 0 and frozen and has_frozen_skel(node, frozen):
            for _ in range(2):
                n2 = rand_expr(rng, depth=rng.choice(cfg['depth']), cfg=cfg)
                if args.dim_review > 0 and review_expr(n2):
                    continue
                if not has_frozen_skel(n2, frozen):
                    node = n2
                    break
            else:
                n_skip_fsa += 1
                continue
        k = str(node)
        if k in seen:              # 重复: 计数 + 连续重到阈值切纯随机
            n_skip_dup += 1
            dup_streak += 1
            if dup_streak > 100 and not rand_only:
                print(f"  [生成] 连续{dup_streak}次重复 -> 切纯随机兜底", flush=True)
                rand_only = True
            continue
        dup_streak = 0
        seen.add(k)
        cands.append(node)
    mode = '随机兜底' if rand_only else '正常'
    print(f"生成候选 {len(cands)}/{args.n} 个[{mode}]"
          f"(跨量纲拦{n_skip_dim} 失败库拦{n_skip_bad} FSA拦{n_skip_fsa} "
          f"重复拦{n_skip_dup}, 尝试{n_tries}), 耗时 {time.time()-t0:.0f}s")
    if getattr(args, 'gen_only', False):
        print("[gen_only] 仅验证候选生成产量, 停在此处(不跑L1/L2/不写状态)")
        return

    # ---- L1 批量 IC(★分批处理 + 子面板 + 跨批LRU) ----
    Bsub = base['B_sub']
    Usub = U[np.ix_(L1_ROWS, L1_COLS)]
    Rsub = fwd_ret[np.ix_(L1_ROWS, L1_COLS)]
    print(f"L1 子面板 {len(L1_ROWS)}日 x {len(L1_COLS)}股 "
          f"(全量 {U.shape[0]}x{U.shape[1]}) -> 数据量约 1/{U.size/max(Usub.size,1):.0f}")
    stats = []
    BATCH = args.batch
    n_eval = 0
    t_l1 = time.time()
    for b0 in range(0, len(cands), BATCH):
        print(f"  L1 批 {min(b0 + BATCH, len(cands))}/{len(cands)} 开始 "
              f"(已用 {time.time()-t_l1:.0f}s)", flush=True)
        chunk = cands[b0:b0 + BATCH]
        vals, kidx = [], []
        for i, nd in enumerate(chunk):
            try:
                v = eval_expr(nd, Bsub, _LRU)         # 子面板 + 全局LRU(跨批复用)
            except Exception:
                flib_mark(fail_lib, nd, args.gen, False, 'eval')  # 求值异常
                continue
            if not np.isfinite(v).any():
                flib_mark(fail_lib, nd, args.gen, False, 'nan')
                continue
            if nd.size() < 2 and not nd.args:          # 退化的纯叶子
                continue
            if np.isfinite(v).mean() < 0.30:           # 覆盖率过低
                flib_mark(fail_lib, nd, args.gen, False, 'cov')
                continue
            if not np.isfinite(np.nanstd(v)) or np.nanstd(v) < 1e-10:
                flib_mark(fail_lib, nd, args.gen, False, 'const')
                continue
            vals.append(v)
            kidx.append(b0 + i)
        if not vals:
            gc.collect()
            continue
        mu, ir, IC = batch_ic(vals, Rsub, Usub, None)
        # ★方向对齐: 统一成"因子越大越好"(IC>0); 否则负IC因子取Top组等于做空它
        sign = np.sign(mu)
        vals = [(-v if s < 0 else v) for v, s in zip(vals, sign)]
        mu, ir = np.abs(mu), np.abs(ir)
        stab = [factor_stability(v, None) for v in vals]
        for m_, i_, s_, k_, sg in zip(mu, ir, stab, kidx, sign):
            stats.append(dict(idx=int(k_), node=cands[int(k_)],
                              expr=str(cands[int(k_)]), ic=float(m_),
                              ic_ir=float(i_), stab=float(s_), sign=float(sg)))
        n_eval += len(vals)
        del vals, IC
        gc.collect()
        if len(_LRU) > LRU_MAX:                        # LRU 容量控制(防OOM)
            for k in list(_LRU.keys())[:len(_LRU) - LRU_MAX]:
                _LRU.pop(k, None)
    print(f"L1 求值完成 {n_eval} 个, 用时 {time.time()-t_l1:.0f}s "
          f"({(time.time()-t_l1)/max(n_eval,1):.2f}s/候选)")
    l1 = pd.DataFrame(stats)
    # 失败模式库: IC/稳定性不过线的候选按骨架记失败(过线者待 L2 后记 ok)
    for r_ in stats:
        nd = r_['node']
        if r_['ic'] <= args.min_ic:
            flib_mark(fail_lib, nd, args.gen, False, 'ic')
        elif r_['stab'] <= args.min_stab:
            flib_mark(fail_lib, nd, args.gen, False, 'stab')
    cache2 = {}
    if not len(l1):
        print("L1 无候选通过, 退出")
        return
    l1 = l1[(l1['ic'] > args.min_ic) & (l1['stab'] > args.min_stab)]
    # ★去相关: 与【已入库已知因子】相关性过高的丢弃, 强迫引擎探索新方向
    #   (中金的"IC相关性<0.70"; 否则引擎会反复重新发现 ln_mktcap / amt_log)
    if args.decorr > 0:
        # 对比对象 = 人工基准 + 【历代入库因子(state.bank)】 —— 对齐中金
        # "与已入库因子IC相关<0.70"的结果闸门: 不是固定两个基准, 库扩大后
        # 与新入库因子相似的候选会被拦在L2外(不靠禁叶子字段)
        KNOWN = {
            'ln_mktcap': np.log(np.maximum(B['mktcap'], 1e-9)),
            'amt_log': -np.log(ts_mean(B['turnover'], 20) + 1.0),
        }
        # 用子面板算相关性(快); 已知因子也取对应子面板
        Kr = {}
        for k, v in KNOWN.items():
            vs = v[np.ix_(L1_ROWS, L1_COLS)]
            Kr[k] = rank_rows(vs[::FWD])
        for bi, bnd in enumerate(bank):
            try:
                vb = eval_expr(bnd, Bsub, cache2)
                Kr[f'bank{bi}'] = rank_rows(vb[::FWD])
                del vb
            except Exception:
                pass
        keep_rows = []
        for _, r in l1.iterrows():
            v0 = eval_expr(r['node'], Bsub, cache2)
            if r['sign'] < 0:
                v0 = -v0
            v = rank_rows(v0[::FWD])
            del v0
            mx = 0.0
            for w in Kr.values():
                m = np.isfinite(v) & np.isfinite(w)
                if m.sum() < 100:
                    continue
                c = abs(np.corrcoef(v[m], w[m])[0, 1])
                mx = max(mx, c if np.isfinite(c) else 0.0)
            if mx <= args.decorr:
                keep_rows.append(r)
        print(f"去相关(|corr|<={args.decorr} vs {len(Kr)}个已知因子) 后剩 "
              f"{len(keep_rows)} 个 (原 {len(l1)})")
        if keep_rows:
            l1 = pd.DataFrame(keep_rows)
    # 关键: 不能只按 |IC_IR| 排! 低稳定性(高换手)因子费后必亏
    # L1评分 = |IC_IR| x 稳定性权重; 换手代理 turn_est = 1 - stab
    l1['turn_est'] = 1.0 - l1['stab']
    l1['score'] = l1['ic_ir'].abs() * (0.25 + 0.75 * l1['stab'].clip(0, 1))
    l1 = l1.sort_values('score', ascending=False)
    # 数值等价去重(只对 TopN 做, 用采样指纹加速, 否则 O(n^2) 跑不动)
    TOPN = min(len(l1), args.dedup_n)
    dedup, seen_v = [], []
    samp = slice(None, None, max(1, 418 // args.dedup_days))   # 抽样调仓日
    cache2 = {}
    for _, r in l1.head(TOPN).iterrows():
        v = eval_expr(r['node'], Bsub, cache2)
        if r['sign'] < 0:
            v = -v
        v = rank_rows(v[::FWD])[samp]
        dup = False
        for w in seen_v:
            m = np.isfinite(v) & np.isfinite(w)
            if m.sum() < 100:
                continue
            if abs(np.corrcoef(v[m], w[m])[0, 1]) > 0.99:
                dup = True
                break
        if not dup:
            seen_v.append(v)
            dedup.append(r)
    print(f"\nL1 通过 {len(l1)} 个, 取Top{TOPN}去重后 {len(dedup)} 个")
    l1 = pd.DataFrame(dedup) if dedup else l1.head(TOPN)
    print(l1[['expr', 'ic', 'ic_ir', 'stab']].head(15).round(4).to_string(index=False))

    # ---- FSA 骨架统计(对齐中金: 抽象因子结构/剥离窗口参数) ----
    # 观察样本 = 本代L1通过者 + 前50候选; 统计对象 = 非叶子结构骨架(剥掉窗口数字)
    fsa['v2'] = True
    for nd in list(l1['node']) + [c for c in cands[:50]]:
        for s in subtree_skels(nd):
            fsa[s] = fsa.get(s, 0) + 1
    # 冻结判定(滚动口径, 对齐中金"定期扫描>15%即禁复用"):
    #   ①本代L1候选中覆盖占比 >= fsa_th 的骨架 -> 新冻结
    #   ②上代冻结骨架若本代已完全不再出现 -> 自动解冻(防冻结集永久膨胀、搜索空间缩死)
    if args.fsa_th > 0 and len(l1):
        thr = max(2, int(round(len(l1) * args.fsa_th)))
        cov = {}
        for _, r in l1.iterrows():
            for s in subtree_skels(r['node']):
                cov[s] = cov.get(s, 0) + 1
        old = set(frozen)
        new_frozen = sorted(s for s, c in cov.items() if c >= thr)
        frozen = sorted((old & set(cov)) | set(new_frozen))
        if new_frozen or len(old - set(frozen)):
            print(f"  [FSA] 覆盖>={thr}/{len(l1)}候选({args.fsa_th:.0%}): "
                  f"新冻结{len(new_frozen)} 解冻{len(old - set(frozen))} "
                  f"冻结中{len(frozen)}")
            for s in new_frozen[:6]:
                print(f"     冻结骨架: {s}")

    # ---- L2 费后精筛 ----
    top = l1.head(args.l2)
    print(f"\nL2 费后精筛 {len(top)} 个 ...")
    rows = []
    for j, (_, r) in enumerate(top.iterrows(), 1):
        nd = r['node']
        try:
            v = eval_expr(nd, B, {})
            if r['sign'] < 0:
                v = -v
            fac = pd.DataFrame(v, index=dates, columns=cols)
            f = cs_rank(fac.astype('float64'))
            rr = evaluate_real(f, close, str(nd), cost=args.cost,
                               window=args.window)
            del f
            gc.collect()
        except Exception as e:
            print(f"  [{j}] ERR {type(e).__name__}")
            continue
        if rr is None:
            continue
        yr = rr['yr']
        # 统一用 factor_miner.pass_filter 的11项标准(亏损年<-2% <=1, 而非"所有年>0")
        from factor_miner import pass_filter
        ok, _ = pass_filter(rr, args.min_ic)
        ok = ok and rr['calmar'] > args.min_calmar and rr['sharpe'] > 0.5
        rows.append(dict(expr=str(nd), window=args.window, cost=args.cost,
                         ic=rr['ic'], ic_ir=rr['ic_ir'],
                         ann_ex=rr['ann_ex'], dd=rr['dd'], calmar=rr['calmar'],
                         sharpe=rr['sharpe'], last_yr=rr['last_yr'],
                         turn=rr.get('turn', np.nan),
                         neg_yr=sum(1 for v in yr.values() if v <= 0),
                         passed=ok))
        print(f"  [{j}] IC={rr['ic']:+.4f} 费后超额={rr['ann_ex']*100:+6.2f}% "
              f"Calmar={rr['calmar'] if rr['calmar'] else 0:5.2f} "
              f"夏普={rr['sharpe']:5.2f} 换手={rr.get('turn', np.nan)*100:4.1f}% "
              f"负年{sum(1 for v in yr.values() if v <= 0)} "
              f"[cost={args.cost*1000:.1f}bp/边 win={args.window}] "
              f"{'PASS' if ok else ''}")
    res = pd.DataFrame(rows)
    # 失败模式库: L2 费后结果落地成败(中金: 失败表达式写入失败库, 生成阶段排除)
    top_node = {str(r['node']): r['node'] for _, r in top.iterrows()}
    for _, r_ in res.iterrows():
        nd = top_node.get(r_['expr'])
        if nd is not None:
            flib_mark(fail_lib, nd, args.gen, bool(r_['passed']),
                      '' if r_['passed'] else 'l2')
    if len(res):
        res.to_csv(ARCHIVE, index=False, encoding='utf-8-sig')
        print(f"\n已存 {ARCHIVE}")
        p = res[res['passed']]
        print(f"L2 通过 {len(p)}/{len(res)} 个")
        if len(p):
            print(p.round(4).to_string(index=False))

    # ---- B角: 诊断本代 + 给出下一代策略 + 写日志 ----
    import loop_critic as critic
    diag = critic.diagnose(l1, res if len(res) else None, args.gen)
    next_cfg, reasons = critic.suggest(diag, cfg)
    print("\n[B角建议] 下一代:")
    for r in reasons:
        print("  -", r)
    critic.report(diag, next_cfg, reasons, JOURNAL)
    print(f"诊断已写入 {JOURNAL}")

    # ---- 保存状态 ----
    new_seeds = list(l1.head(30)['node'])
    if len(res) and res['passed'].any():
        new_seeds = list(l1.head(20)['node'])
    # 入库因子库 bank: 本代通过者入列(node级去重), 供下代 decorr 对比
    # 对齐中金: ①冻结骨架禁入 ②同结构参数变体上限有限(bank_skel_max) 防窗口变体堆叠
    if len(res) and res['passed'].any():
        by_expr = {str(r['node']): r['node'] for _, r in top.iterrows()}
        skel_cnt = skeleton_freq(bank)
        fset = set(frozen) if args.fsa_th > 0 else set()
        n_bank_old = len(bank)
        for expr in res.loc[res['passed'], 'expr'].tolist():
            nd = by_expr.get(expr)
            if nd is None or any(str(x) == expr for x in bank):
                continue
            s = skeleton(nd)
            if s in fset:
                print(f"  [FSA] 通过但不入库: 骨架已冻结 -> {s}")
                continue
            if skel_cnt.get(s, 0) >= args.bank_skel_max:
                print(f"  [FSA] 通过但不入库: 骨架 {s} 已有 {skel_cnt.get(s,0)} "
                      f"个(上限{args.bank_skel_max})")
                continue
            bank.append(nd)
            skel_cnt[s] = skel_cnt.get(s, 0) + 1
        if len(bank) > n_bank_old:
            print(f"  入库 {len(bank)-n_bank_old} 个新因子, 累计 {len(bank)} 个")
    for k, v in DEFAULT_CFG.items():
        next_cfg.setdefault(k, v)      # critic.suggest 重建dict可能丢键 -> 兜底补齐
    next_cfg.setdefault('bank_skel_max', args.bank_skel_max)
    fail_lib = fail_lib_cleanup(fail_lib, args.gen)
    with open(STATE, 'wb') as f:
        pickle.dump(dict(seeds=new_seeds[:60], fsa=fsa,
                         bank=bank[-30:],
                         frozen=frozen,
                         fail_lib=fail_lib,
                         n_tested=st.get('n_tested', 0) + len(cands)
                         if os.path.exists(STATE) else len(cands),
                         last_l1=l1, last_l2=res if len(res) else None,
                         cfg=next_cfg), f)
    print(f"\n保存状态: 种子 {len(new_seeds[:60])} 个, 入库因子 {len(bank)} 个, "
          f"冻结骨架 {len(frozen)} 个, 失败库 {len(fail_lib)} 条, "
          f"耗时 {time.time()-t0:.0f}s")


def clone(n):
    return Node(n.op, [clone(a) if isinstance(a, Node) else a for a in n.args])


def guided_expr(rng, cfg=None):
    """语义引导: 按【机制族】生成(中金定义13族, 其核心为跳空溢价/振幅/影线/价格结构)
    中金实证: overnight 85% / amplitude 63%; 核心结构家族
      sub(ma(overnight,N), ...) 与 sub(delta(ma(overnight,N),M), ...)
    """
    cfg = cfg or DEFAULT_CFG
    kind = rng.choice(['gap', 'gap_trend', 'amp', 'shadow', 'price_struct',
                       'mom', 'rev', 'vol', 'liq', 'vpin'])
    N = rng.choice([20, 60, 100, 120, 150, 200])
    M = rng.choice([5, 20, 60])
    if kind == 'gap':                      # 跳空溢价(中金第一大族)
        return Node('ts_mean%d' % N, [Node('overnight', [])])
    if kind == 'gap_trend':                # 跳空趋势背离: sub(ma(overnight,N), ...)
        return Node('sub', [Node('ts_mean%d' % N, [Node('overnight', [])]),
                            Node('ts_mean%d' % N, [Node(pick_leaf(rng, cfg), [])])])
    if kind == 'amp':                      # 振幅
        return Node(rng.choice(['ts_mean%d' % N, 'neg']),
                    [Node('amplitude', [])])
    if kind == 'shadow':                   # 影线支撑(中金 FSA 后被迫转向的方向)
        return Node(rng.choice(['ts_mean%d' % N, 'neg']),
                    [Node(rng.choice(['down_shadow', 'up_shadow']), [])])
    if kind == 'price_struct':             # 价格结构 hl_ratio / true_range
        return Node('ts_mean%d' % N,
                    [Node(rng.choice(['hl_ratio', 'true_range', 'intraday']), [])])
    if kind == 'mom':
        return Node('ts_delta%d' % M, [Node(rng.choice(['close', 'vwap']), [])])
    if kind == 'rev':
        return Node('neg', [Node('ts_delta%d' % M,
                                 [Node(rng.choice(['close', 'vwap']), [])])])
    if kind == 'vol':
        VW = rng.choice([60, 100, 150, 200])          # ts_std 无120窗口
        return Node('neg', [Node('ts_std%d' % VW, [Node('ret', [])])])
    if kind == 'liq':
        return Node('neg', [Node('log', [Node('ts_mean%d' % N,
                                              [Node(pick_leaf(rng, cfg), [])])])])
    return Node('corr%d' % min(N, 100), [Node('volume', []), Node('ret', [])])


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--gen', type=int, default=1)
    ap.add_argument('--n', type=int, default=600)
    ap.add_argument('--gen_only', action='store_true',
                    help='dry-run: 只跑候选生成段验证产量, 不跑L1/L2/不写状态')
    ap.add_argument('--min_ic', type=float, default=0.02)
    ap.add_argument('--min_calmar', type=float, default=0.5)
    ap.add_argument('--min_stab', type=float, default=0.30)
    ap.add_argument('--batch', type=int, default=40,
                    help='L1 每批候选数(控内存: 每个(T,S)面板约71MB)')
    ap.add_argument('--dedup_n', type=int, default=70)
    ap.add_argument('--dedup_days', type=int, default=60)
    ap.add_argument('--decorr', type=float, default=-1,
                    help='与已知因子(ln_mktcap/amt_log)的最大|corr|, 超过则丢弃; '
                         '负数=跟随B角建议, 0=关闭')
    ap.add_argument('--fsa_th', type=float, default=-1,
                    help='FSA骨架冻结阈值: bank中同骨架占比超过该值即冻结该骨架, '
                         '后续候选不再生成/入库(中金>15%冻结); 负数=跟随B角建议, 0=关闭')
    ap.add_argument('--bank_skel_max', type=int, default=1,
                    help='bank中每个骨架允许的最大入库数(同结构参数变体上限, 中金FSA)')
    ap.add_argument('--dim_review', type=float, default=-1,
                    help='跨量纲静态审查(中金审查规则): 拦截价格+成交量等异量纲add/sub; '
                         '负数=开启(默认), 0=关闭')
    ap.add_argument('--fail_rate', type=float, default=-1,
                    help='失败模式库排除阈值: 全败率>=该值且失败>=min_fail的骨架生成时排除; '
                         '负数=跟随B角cfg(默认0.6), 0=关闭')
    ap.add_argument('--min_fail', type=int, default=-1,
                    help='失败模式库最小失败次数(默认3)')
    ap.add_argument('--l2', type=int, default=40)
    ap.add_argument('--seed', type=int, default=42)
    ap.add_argument('--cost', type=float, default=COST_PRESETS['单边千1.5'],
                    help=f'往返成本, 默认单边千1.5=0.004; 档位: {COST_PRESETS}')
    ap.add_argument('--window', choices=['full', 'recent600'], default='full',
                    help='回测口径: full=2018起九年; recent600=最近600交易日(中金口径)')
    run(ap.parse_args())
