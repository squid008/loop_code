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
import re
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
ARCHIVE = os.path.join(os.path.dirname(HERE), 'docs', 'loop_archive.csv')
JOURNAL = os.path.join(os.path.dirname(HERE), 'docs', 'loop_journal.md')  # B角诊断日志(loop_code/docs)
LIBRARY = os.path.join(os.path.dirname(HERE), 'docs', 'factor_library.md')  # 入库因子文档(代末自动同步新增)

# 默认搜索策略(B角可动态调整)
# 中金五策略配比: 变异25 / 交叉25 / 扰动15 / 随机探索15 / LLM机制引导20
# 本表键序=变异/交叉/扰动/引导/随机 -> mix=[0.25,0.25,0.15,0.20,0.15] 即引导20随机15
DEFAULT_CFG = dict(leaf_w={}, op_bias={}, depth=[2, 3, 4],
                   mix=[0.25, 0.25, 0.15, 0.20, 0.15],
                   min_stab=0.30, decorr=0.75, fsa_th=0.15)

# ===================== 1. 基础字段 =====================
# ---- 叶子字段单一事实源 = loop_fields.py (引擎A角/B角critic/量纲/写档共用) ----
# 新增字段族只改 loop_fields.py 一处, 勿在本文件硬编码叶子名(防再漂移)。
# 资金流 moneyflow3 原始拆分16列: 金额(×1e4元,量纲A)+量(×100股,量纲V), 净额不预焊由GP自组合;
# BARRA 连续风格11(barra.h5,行业哑不入叶) / 财报PIT as-of比率8(fa_pit.h5,按info_date无未来函数)
from loop_fields import MF16, BARRA_LEAVES, FA_LEAVES, LEAVES, FIELDS

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
    # ---- 扩展叶子(mf16 随 FIELDS 已入 P; barra/fa 独立 store) ----
    for name in MF16:
        B[name] = P[name].reindex(index=dates, columns=cols).values.astype(np.float32)
    for fn, names in (('barra.h5', BARRA_LEAVES), ('fa_pit.h5', FA_LEAVES)):
        with pd.HDFStore(os.path.join(HERE, fn), 'r') as st:
            for name in names:
                B[name] = st[name].reindex(index=dates, columns=cols).values.astype(np.float32)
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

# ★LEAVES 完整叶子池已由顶部 `from loop_fields import LEAVES` 提供
#   (基础7 + 派生12 + MF16资金流 + BARRA11风格 + FA8财报 = 54), 勿在此重复硬编码(防漂移)

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


# ---- 结构族聚类(QuantaAlpha 冗余检测移植): 拦"外层模板固定、内层微调"的同构霸榜族 ----
FAM_CUT = 3          # 模板指纹展开算子层数(cut 层以下折叠)
FAM_QUOTA = 2        # L1 同模板族候选进 L2/种子池上限


def root_fam(node, cut=FAM_CUT):
    """模板族指纹: 叶子统一'X'(身份无关) + 窗口剥除 + 距根cut层以下折叠'#'。
    mul(turnover,ts_min100(corr100(overnight, <任意深>))) 成员 -> 同一指纹, 判同族。"""
    def rec(nd, d):
        if not nd.args:
            return 'X'
        if d >= cut:
            return '#'
        return norm_op(nd.op) + '(' + ','.join(
            rec(a, d + 1) if isinstance(a, Node) else 'X' for a in nd.args) + ')'
    return rec(node, 0)


def fam_quota_rows(rows, quota=FAM_QUOTA):
    """score 降序的 L1 行上做模板族配额: 同族至多保留 quota 条(保跨族多样), 返回过滤后行集"""
    cnt, keep, n_block = {}, [], 0
    for _, r in rows.iterrows():
        f = root_fam(r['node'])
        c = cnt.get(f, 0)
        if c >= quota:
            n_block += 1
            continue
        cnt[f] = c + 1
        keep.append(r)
    import pandas as _pd
    return _pd.DataFrame(keep), len(cnt), n_block


def _lib_sync(gen, res, n_total, added_exprs, expr2nd):
    """本代新入库因子自动同步追加进 docs/factor_library.md(只增不改历史, 家族命名留待人工精炼)。
    幂等: 编号取文本现有最大 F{nn}+1; 任何失败仅告警, 绝不影响入库主流程。
    added_exprs: 本代真正 append 进 bank 的 expr 列表; expr2nd: {str(node): node}(模块已有 Node/skeleton)。"""
    import re
    import io
    try:
        if not added_exprs or not os.path.exists(LIBRARY):
            return
        rows = {str(r['expr']): r for _, r in res.iterrows()} if len(res) else {}
        txt = io.open(LIBRARY, encoding='utf-8').read()
        nos = [int(x) for x in re.findall(r'\bF(\d{2})\b', txt)]
        no = (max(nos) + 1) if nos else 1
        tbl_rows, det_rows = [], []
        for expr in added_exprs:
            r = rows.get(expr)
            if r is None:
                continue
            nd = expr2nd.get(expr)
            cat_s = str(r['cat']); leaf_s = str(r['leaf'])
            fam = (cat_s[:20] + '…') if len(cat_s) > 20 else (cat_s or '未分类')
            short = expr if len(expr) <= 44 else expr[:41] + '…'
            met = ('IC %.4f / IC_IR %.3f / 年化超额 %+.1f%% / 回撤 %.1f%% / '
                   'Calmar %.3f / Sharpe %.3f / 最近年 %+.1f%% / 单期换手 %.1f%% / 负年 %d'
                   % (r['ic'], r['ic_ir'], r['ann_ex'] * 100, r['dd'] * 100,
                      r['calmar'], r['sharpe'], r['last_yr'] * 100, r['turn'] * 100,
                      int(r['neg_yr'])))
            skel = skeleton(nd) if nd is not None else '?'
            tbl_rows.append('| F%02d | gen%d | %s | %s | 已入库(auto) |'
                            % (no, gen, fam, short))
            det_rows.append(
                '\n### F%02d · gen%d 入库（引擎自动同步，家族命名待人工精炼）\n'
                '```\n%s\n```\n'
                '- 家族：%s（auto）\n- 叶子：%s\n- 骨架：`%s`\n'
                '- 费后指标（full，成本 %.0fbp/边）：%s\n'
                % (no, gen, expr, fam, leaf_s, skel, r['cost'] * 1000, met))
            no += 1
        if not det_rows:
            return
        add_tbl = '\n'.join(tbl_rows)
        add_det = ''.join(det_rows)
        # 1) 头部计数行(自动同步计数)
        txt = re.sub(r'> 当前 \*\*\d+ 个入库\*\*', '> 当前 **%d 个入库**' % n_total,
                     txt, count=1)
        # 2) 总览表格末尾(## 因子明细 前最后一个 '| F' 数据行)后插入新行
        j = txt.find('\n## 因子明细')
        i = txt.rfind('\n| F', 0, j) if j > 0 else -1
        if i >= 0:
            k = txt.find('\n', i + 2)
            if k >= 0:
                txt = txt[:k] + '\n' + add_tbl + txt[k:]
        # 3) 明细小节插在 '## 相关文件导航' 前(原 --- 分节保留, 新条目自带分隔)
        nav = '\n## 相关文件导航'
        p = txt.find(nav)
        if p < 0:
            txt = txt.rstrip('\n') + add_det + '\n'
        else:
            txt = txt[:p] + add_det + '\n---\n\n' + txt[p:]
        io.open(LIBRARY, 'w', encoding='utf-8').write(txt)
        print(f"  [文档] factor_library.md 已自动追加 {len(det_rows)} 条新入库 "
              f"(F{nos and max(nos)+1 or 1}~F{no-1}, 累计 {n_total})")
    except Exception as e:
        print(f"  [文档] factor_library.md 自动同步失败(不影响入库): "
              f"{type(e).__name__}: {e}")


# ===================== 跨量纲审查(中金审查规则之一) =====================
# 量纲族: P=价格元 / R=比率与收益率(无量纲) / V=股数 / A=成交额元 / M=市值元 /
#         L=对数标尺(ln) / Z=截面标准化(cs_rank/cs_demean/cs_scale) / C=复合(mul/div)
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
    # ---- LLM 对话录音: 本代 A角/B角 与 DeepSeek 的全部往返落盘(ai_test, gitignore) ----
    # automation 无人值守, 人看不到实时 LLM 对话; 录音文件供跑代后随时回溯/本窗口转述。
    try:
        import loop_llm as _llm
        _conv_dir = os.path.join(os.path.dirname(HERE), 'ai_test', 'loop_conv')
        _llm.set_conv_path(os.path.join(_conv_dir, 'gen%02dC_conv.md' % args.gen))
        print(f"  LLM 对话录音 -> ai_test/loop_conv/gen{args.gen:02d}C_conv.md", flush=True)
    except Exception as _e:
        print(f"  (LLM 对话录音初始化失败: {_e})", flush=True)
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
    # ---- 结构族黑名单(QuantaAlpha 正交思想, gen31): 上代 L1 霸榜模板族 ----
    # 上代同模板族(叶子身份无关指纹)占比 >= FAM_BLOCK_THR -> 本代生成端禁产(硬闸换血);
    # top2 模板文本另注入 A角 LLM 提示词(软约束)。根治"同族霸榜 -> 0 通过"空转。
    block_fams, fam_black_txt = set(), ''
    if prev_l1 is not None and len(prev_l1):
        fam_cnt = {}
        for nd in list(prev_l1['node'])[:40]:
            f = root_fam(nd)
            fam_cnt[f] = fam_cnt.get(f, 0) + 1
        n_pv = len(prev_l1)
        tops = sorted(fam_cnt.items(), key=lambda x: -x[1])
        if args.fam_block_thr > 0 and tops and tops[0][1] / n_pv >= args.fam_block_thr:
            block_fams = {tops[0][0]}
        fam_black_txt = '；'.join(f'「{f}」({c}/{n_pv}条)' for f, c in tops[:2])
    if block_fams:
        print(f"  [族黑名单] 上代 L1 同模板族占比>={args.fam_block_thr:.0%} -> "
              f"本代生成端禁产该模板族, 强制结构换血")
    # 五维配比护栏(与 critic.suggest 出口同源): 即使旧state cfg 漂移且本轮无规则触发
    # (如无上一代), 本代实际生效 mix 也强制回到中金规格内(变异/交叉≥10%、槽位15/20/15)
    cfg['mix'] = critic.guard_mix(cfg.get('mix'))
    print(f"  五维配比 mix={[round(x, 3) for x in cfg['mix']]} "
          f"(变异/交叉自适应≥{critic.MIX_MIN:.0%}, 扰动/引导/随机=15/20/15)")
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

    # ---- 随机探索: 数据驱动特征分布引导(中金"随机探索15%=数据驱动分布, 防局部最优") ----
    # 证据分布 = 历代入库因子 + 上一代 L1 通过候选 的叶子/算子族频率;
    # 随机位按该分布抽样(探索有苗头方向的新组合), 无证据时退化为 cfg 权重(均匀)。
    ev_nodes = list(bank) + (list(prev_l1['node'])
                             if prev_l1 is not None and len(prev_l1) else [])
    cfg_r = dict(cfg)
    prof = data_profile(ev_nodes)
    if prof:
        cfg_r['leaf_w'] = _mix_weights(cfg.get('leaf_w', {}), prof['leaf'], LEAVES)
        cfg_r['op_bias'] = _mix_weights(cfg.get('op_bias', {}), prof['op'],
                                        list(UNARY.keys()) + list(BINARY.keys()),
                                        family=True)
        print(f"  [随机探索] 数据驱动特征分布: 叶子证据{len(prof['leaf'])}种 / "
              f"算子族{len(prof['op'])}种 -> 随机位按证据加权探索")
    else:
        print("  [随机探索] 无历史证据(首代) -> 随机位退化均匀")

    # ---- 生成候选(按B角给的五维配比) ----
    # ★gen13修复: cut为累积上界, 判重/分支原来写成 cut[i] 相加 -> 数值>1恒真,
    # 使 r<cut0+cut1+cut2 永远成立: guided(引导族)与rand(纯随机)从不会被执行,
    # 代代只在seeds内打转 -> 重复爆炸。 现改回 r<cut[2](seed三操作) / r<cut[3](引导) / 否则随机。
    m = cfg['mix']
    cut = [m[0], m[0] + m[1], m[0] + m[1] + m[2], m[0] + m[1] + m[2] + m[3]]
    # ---- 生成侧 LLM 引导(A角子代理, 中金"生成预算~20%语义引导"): ----
    # 引导位 r∈[cut2,cut3) 的候选来源 = LLM 解析池; 池空且调用未超限则按需补一次;
    # 无 key/超时/解析失败/超限 -> 回退本地 guided_expr。LLM 候选与规则候选走
    # 同一条守卫链(跨量纲/失败库/FSA/判重), 不产生旁路。
    llm_on = (getattr(args, 'llm_guide', 'auto') != 'off')
    llm_pool, llm_hyp = [], ''
    n_llm_call = n_llm_parse = n_llm_hit = 0
    if llm_on:
        import loop_llm
        if not loop_llm.api_key():
            if getattr(args, 'llm_guide', 'auto') == 'on':
                print("  [LLM引导] --llm_guide=on 但未找到 DeepSeek key -> 回退本地引导")
            llm_on = False
        else:
            print("  [LLM引导] 生成侧 A角 LLM 引导已启用(模型="
                  f"{getattr(args, 'llm_model', None) or loop_llm.DEFAULT_MODEL}), "
                  f"上限 {args.llm_max_calls} 次/代, 引导位命中按需补池")
    cands, seen = [], set()        # seen: 表达式级判重(原[in list] O(n²) -> O(1))
    n_skip_fsa = n_skip_dim = n_skip_bad = n_skip_dup = n_skip_fam = 0
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
            node = rand_expr(rng, depth=rng.choice(cfg['depth']), cfg=cfg_r)
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
                # 引导位: LLM(A角)候选优先, 池空则按需补一次; 无 key/失败 -> 本地引导
                if llm_on and not llm_pool and n_llm_call < args.llm_max_calls:
                    n_llm_call += 1
                    _ok, llm_hyp, _ns = llm_fetch(args, cfg, seeds, bank,
                                                  frozen, fail_lib,
                                                  fam_black=fam_black_txt)
                    n_llm_parse += len(_ns)
                    llm_pool = _ns
                if llm_pool:
                    node = llm_pool.pop()
                    n_llm_hit += 1
                else:
                    node = guided_expr(rng, cfg)
            else:
                node = rand_expr(rng, depth=rng.choice(cfg['depth']), cfg=cfg_r)
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
                n2 = rand_expr(rng, depth=rng.choice(cfg['depth']), cfg=cfg_r)
                if args.dim_review > 0 and review_expr(n2):
                    continue
                if not has_frozen_skel(n2, frozen):
                    node = n2
                    break
            else:
                n_skip_fsa += 1
                continue
        # 结构族黑名单闸(gen31): 命中上代垄断模板族 -> 重抽(rand_only 兜底豁免防死锁)
        if not rand_only and block_fams and root_fam(node) in block_fams:
            n_skip_fam += 1
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
          f"族黑名单拦{n_skip_fam} 重复拦{n_skip_dup}, 尝试{n_tries}), "
          f"耗时 {time.time()-t0:.0f}s")
    if llm_on and n_llm_call:
        print(f"  [LLM引导] 调用{n_llm_call}次, 解析通过{n_llm_parse}条, "
              f"引导位出队{n_llm_hit}条"
              + (f" | hyp: {llm_hyp[:110]}" if llm_hyp else ""))
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
    # ---- 结构族配额(QuantaAlpha 冗余检测移植, gen31) ----
    # 数值去重(|corr|>0.99) 只拦"数值等价"; FSA 冻结只拦"完整串复用"。同族"外层模板固定、
    # 内层微调"的候选(score 各异、公共结构巨大)会继续挤满 L2 名额与下代种子池, 费后全灭 ->
    # 每模板族最多放 fam_quota 条进 L2/种子池(保结构多样性), FSA/下代种子池因此天然跨族。
    fam_blocked = 0
    if args.fam_quota > 0 and len(l1):
        n_pre = len(l1)
        l1, nfam, n_blocked = fam_quota_rows(l1, quota=args.fam_quota)
        fam_blocked = n_blocked
        if n_blocked:
            print(f"  [族配额] 模板族 {nfam} 个 -> 结构冗余拦 {n_blocked}/{n_pre} "
                  f"(剩 {len(l1)}, 每族<={args.fam_quota})")

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

    # ---- 中金【审查】环节: B角候选级 LLM 精判(硬滤后抽5深判, 与生成侧隔离防自证) ----
    # 硬规则已在上方先滤(IC/稳定/去相关/去重/跨量纲/FSA) -> 剩余候选随机抽 --jury_n 个,
    # 由审查侧 Sub-agent LLM(loop_llm.jury_verdict)判经济含义/过拟合边界/已知族嫌疑,
    # verdict=KILL 者剔除出 L2 费后回测; 无 key/调用失败一律放行不误杀(无人值守铁律)。
    kills_j, n_jury_rev, n_jury_kill, jury_lines = set(), 0, 0, []
    jury_on = getattr(args, 'ai_jury', 'auto')
    if jury_on != 'off' and len(l1):
        import loop_llm
        if not loop_llm.api_key():
            if jury_on == 'on':
                print("  [LLM审查] --ai_jury=on 但未找到 key -> 跳过(纯硬规则审查)")
        else:
            jmodel = getattr(args, 'ai_jury_model', None) or loop_llm.DEFAULT_MODEL
            kills_j, n_jury_rev, n_jury_kill, jury_lines = \
                llm_jury(args, rng, l1, model=jmodel)
            if kills_j:
                l1 = l1[~l1['expr'].isin(kills_j)]
                print(f"  [LLM审查] KILL {len(kills_j)} 个候选剔除出 L2, "
                      f"剩余 {len(l1)} 个进入费后回测")

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
        leaf_s, cat_s = leaf_parts(nd)
        rows.append(dict(expr=str(nd), cat=cat_s, leaf=leaf_s,
                         window=args.window, cost=args.cost,
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
        # 逐代累积流水(带 gen/cat/leaf 列): 文件缺失/为空时写表头, 其后追加
        # —— 每代 L2 明细永久留档(gen16 前旧快照已归 docs/history/loop_archive.legacy_pre_gen16.csv)
        res.insert(0, 'gen', args.gen)
        need_head = (not os.path.exists(ARCHIVE)) or os.path.getsize(ARCHIVE) == 0
        res.to_csv(ARCHIVE, index=False, mode='a', header=need_head,
                   encoding='utf-8-sig')
        print(f"\n已存 {ARCHIVE} (追加, 本代 {len(res)} 条)")
        p = res[res['passed']]
        print(f"L2 通过 {len(p)}/{len(res)} 个")
        if len(p):
            print(p.round(4).to_string(index=False))

    # ---- B角: 诊断本代 + 给出下一代策略 + 写日志 ----
    import loop_critic as critic
    diag = critic.diagnose(l1, res if len(res) else None, args.gen)
    diag['fam_blocked'] = fam_blocked
    next_cfg, reasons = critic.suggest(diag, cfg)
    print("\n[B角建议] 下一代:")
    for r in reasons:
        print("  -", r)
    critic.report(diag, next_cfg, reasons, JOURNAL)
    print(f"诊断已写入 {JOURNAL}")
    # ---- 生成侧 LLM 引导留痕(独立引用体小节, 与 ai_review 块同风格) ----
    if llm_on and n_llm_call:
        llm_journal_block(args.gen, n_llm_call, n_llm_parse, n_llm_hit,
                          llm_hyp, JOURNAL)
        print(f"LLM 引导小结已写入 {JOURNAL}")
    if n_jury_rev:
        llm_jury_block(args.gen, n_jury_rev, n_jury_kill, jury_lines, JOURNAL)
        print(f"LLM 候选审查小结已写入 {JOURNAL}")

    # ---- B角 LLM 审查(DeepSeek, --ai_critic auto/on/off, 默认auto=有key即启用) ----
    ai = getattr(args, 'ai_critic', 'auto')
    if ai != 'off':
        critic.ai_review(diag, l1, res if len(res) else None, args.gen,
                         JOURNAL, reasons=reasons, sug=next_cfg, force=(ai == 'on'))

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
        lib_added = []
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
            lib_added.append(expr)
        if len(bank) > n_bank_old:
            print(f"  入库 {len(bank)-n_bank_old} 个新因子, 累计 {len(bank)} 个")
            # 入库文档自动同步(factor_library.md): 只增不改, 失败不影响入库
            _lib_sync(args.gen, res, len(bank), lib_added, by_expr)
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
    """语义引导: 按【机制族】生成。中金 LLM 机制引导位定义 13 个机制族,
    核心为跳空溢价/振幅/影线/价格结构(实证 overnight 85% / amplitude 63%)。
    13族 = gap / gap_trend / gap_decay / amp / amp_vol / shadow / price_struct /
           mom / rev / vol / liq / turn_anom / vpin
    (此函数仅在引导位 LLM 候选不足时回退使用, 与 A角 Skill 的族口径同源。)
    """
    cfg = cfg or DEFAULT_CFG
    kind = rng.choice(['gap', 'gap_trend', 'gap_decay', 'amp', 'amp_vol',
                       'shadow', 'price_struct', 'mom', 'rev', 'vol', 'liq',
                       'turn_anom', 'vpin'])
    N = rng.choice([60, 100, 120, 150, 200])   # 长窗口(与中金 51~200 对齐)
    M = rng.choice([5, 20, 60])                # 短窗口
    VW = rng.choice([60, 100, 150, 200])       # ts_std 无120窗口
    leaf = lambda: pick_leaf(rng, cfg)
    if kind == 'gap':                          # 跳空溢价(中金第一大族)
        return Node('ts_mean%d' % N, [Node('overnight', [])])
    if kind == 'gap_trend':                    # 跳空趋势背离: sub(ma(overnight,N), 别字段)
        return Node('sub', [Node('ts_mean%d' % N, [Node('overnight', [])]),
                            Node('ts_mean%d' % N, [Node(leaf(), [])])])
    if kind == 'gap_decay':                    # 隔夜溢价衰减: 短-长均值差
        return Node('sub', [Node('ts_mean%d' % M, [Node('overnight', [])]),
                            Node('ts_mean%d' % N, [Node('overnight', [])])])
    if kind == 'amp':                          # 振幅(中金实证 63%)
        return Node(rng.choice(['ts_mean%d' % N, 'neg']), [Node('amplitude', [])])
    if kind == 'amp_vol':                      # 振幅波动聚集(波动率聚族变体)
        return Node('ts_std%d' % VW, [Node('amplitude', [])])
    if kind == 'shadow':                       # 影线支撑(中金 FSA 后被迫转向的方向)
        return Node(rng.choice(['ts_mean%d' % N, 'neg']),
                    [Node(rng.choice(['down_shadow', 'up_shadow']), [])])
    if kind == 'price_struct':                 # 价格结构 hl_ratio / true_range
        return Node('ts_mean%d' % N,
                    [Node(rng.choice(['hl_ratio', 'true_range', 'intraday']), [])])
    if kind == 'mom':                          # 动量
        return Node('ts_delta%d' % M, [Node(rng.choice(['close', 'vwap']), [])])
    if kind == 'rev':                          # 反转
        return Node('neg', [Node('ts_delta%d' % M,
                                 [Node(rng.choice(['close', 'vwap']), [])])])
    if kind == 'vol':                          # 波动率风险溢价
        return Node('neg', [Node('ts_std%d' % VW, [Node('ret', [])])])
    if kind == 'liq':                          # 流动性
        return Node('neg', [Node('log', [Node('ts_mean%d' % N, [Node(leaf(), [])])])])
    if kind == 'turn_anom':                    # 量能/换手异动: 短-长换手偏离
        return Node('sub', [Node('ts_mean%d' % M, [Node('turn_ratio', [])]),
                            Node('ts_mean%d' % N, [Node('turn_ratio', [])])])
    return Node('corr%d' % min(N, 100), [Node('volume', []), Node('ret', [])])  # vpin


# ===================== 生成侧 LLM 引导(A角子代理, 中金"生成预算20%语义引导") =====================
# loop_llm.GEN_SYSTEM/gen_candidates 已定义 A角 Skill 与调用封装; 此处只补两件事:
#   ① parse_expr: LLM 返回的表达式文本 -> 引擎 Node(严格反向解析, 任一不合规返回 None);
#   ② llm_fetch: 拼本代上下文 -> 调 gen_candidates -> 解析成 Node 池供引导位使用。
# 失败安全: 无 key/超时/JSON坏/语法不合规 -> 一律静默回退本地 guided_expr, 绝不阻塞迭代;
# 解析产物与规则候选走同一条守卫链(跨量纲/失败库/FSA/判重), 口径一致不产生旁路。
LLM_MAX_SIZE = 15         # 解析上限: 超过该节点总数的巨型表达式视为 LLM 失控, 丢弃
_EXPR_TOK = re.compile(r'[A-Za-z_][A-Za-z0-9_]*|[(),]')


def tokenize_expr(text):
    """分词并校验: token 间只允许空白, 出现其它字符(如 + 1 中缀残留)返回 None
    (防止 LLM 输出 'cs_rank(volume) + 1' 时非法尾部被静默吞掉而误收)。"""
    s = str(text)
    toks, pos = [], 0
    for mt in _EXPR_TOK.finditer(s):
        if s[pos:mt.start()].strip():
            return None
        toks.append(mt.group(0))
        pos = mt.end()
    if s[pos:].strip():
        return None
    return toks


def _parse_sexp(toks, i):
    """递归下降单元素: 返回 (Node|None, 下一token下标)"""
    if i >= len(toks):
        return None, i
    name = toks[i]
    i += 1
    if i < len(toks) and toks[i] == '(':
        i += 1
        args = []
        while True:
            nd, i = _parse_sexp(toks, i)
            if nd is None:
                return None, i
            args.append(nd)
            if i < len(toks) and toks[i] == ',':
                i += 1
                continue
            if i < len(toks) and toks[i] == ')':
                return Node(name, args), i + 1
            return None, i
    return Node(name, []), i


def parse_expr(text):
    """LLM 表达式文本 -> Node(与 Node.__str__ 前缀式 op(a, b) 严格对齐)。
    校验: 叶子名∈LEAVES / 函数名∈UNARY∪BINARY / 参数个数匹配 / size≤LLM_MAX_SIZE;
    任一不合规返回 None, 由调用方静默丢弃(不修复不猜测)。"""
    toks = tokenize_expr(text)
    if not toks:
        return None
    nd, i = _parse_sexp(toks, 0)
    if nd is None or i != len(toks):
        return None
    for x in collect(nd):
        if not x.args:
            if x.op not in LEAVES:
                return None
            continue
        if len(x.args) == 1:
            if x.op not in UNARY:
                return None
        elif x.op not in BINARY:          # len(x.args)==2
            return None
    if nd.size() > LLM_MAX_SIZE:
        return None
    return nd


def llm_fetch(args, cfg, seeds, bank, frozen, fail_lib, fam_black=''):
    """A角 LLM 拉一批候选: 拼上下文 -> loop_llm.gen_candidates -> 文本解析回 Node。
    返回 (ok, hyp, nodes); 任何失败 ok=False 且 nodes=[] (内部已打印原因)。"""
    import loop_llm
    diag = (f"第{args.gen}代搜索, 目标候选数{args.n}, 种子池{len(seeds)}个(上一代L1头部)。\n"
            f"当前已知: 入库因子{len(bank)}个(同骨架上限{args.bank_skel_max}), "
            f"冻结骨架{len(frozen)}个(禁止复用), "
            f"失败库{len(fail_lib)}条(多次全败骨架生成端排除)。\n"
            f"本代策略: mix(变异/交叉/扰动/引导/随机)={cfg['mix']}, depth={cfg['depth']}, "
            f"min_stab={cfg.get('min_stab')}, decorr={cfg.get('decorr')}, "
            f"fsa_th={cfg.get('fsa_th')}。\n"
            f"叶子权重: {cfg.get('leaf_w') or '(均匀)'}。")
    hint = ("请避开易重复结构: 纯市值/成交额/换手率的旧故事表达、同骨架只换窗口的参数变体"
            "都算重复; 优先给出有独立金融机制的表达式(跳空溢价/价量背离/波动结构/日内形态/"
            "流动性等), 宁少勿滥。")
    if fam_black:
        hint += ("\n[结构族黑名单] 上一代 L1 通过集被下列外层模板垄断(L1 高分但费后全灭), "
                 "本代请勿再产出同构模板(换内层参数/叶子不算新结构): " + fam_black)
    model = getattr(args, 'llm_model', None) or loop_llm.DEFAULT_MODEL
    ok, d = loop_llm.gen_candidates(diag, hint, n=args.llm_n, model=model)
    if not ok:
        print(f"  [LLM引导] 调用失败({d}) -> 回退本地引导")
        return False, '', []
    nodes = []
    for t in (d.get('exprs') or []):
        nd = parse_expr(t)
        if nd is not None:
            nodes.append(nd)
    print(f"  [LLM引导] 回复 {len(d.get('exprs') or [])} 条, "
          f"语法解析通过 {len(nodes)} 条")
    return True, (d.get('hyp') or '').strip(), nodes


def data_profile(nodes):
    """随机探索的'数据驱动特征分布'(中金): 统计证据候选的叶子字段与(去窗口)算子族频率。
    证据 = 历代入库因子 + 上一代 L1 通过候选;
    返回 {'leaf': {叶: cnt}, 'op': {算子族: cnt}} 或 None(无证据)。"""
    if not nodes:
        return None
    leaf, op = {}, {}
    for nd in nodes:
        try:
            for n in collect(nd):
                if not n.args:
                    leaf[n.op] = leaf.get(n.op, 0) + 1
                else:
                    fam = ''.join(c for c in n.op if not c.isdigit())
                    op[fam] = op.get(fam, 0) + 1
        except Exception:
            continue
    return {'leaf': leaf, 'op': op} if (leaf or op) else None


def _mix_weights(base, freq, universe, family=False):
    """把证据频率(按最大归一化)加权到 universe 每个候选名的抽样权重, 保留既有下限(0.3x)。
    family=True: freq 键为'去窗口算子族', 同族所有具体算子共享该族证据权重。"""
    if not freq:
        return dict(base)
    mx = max(freq.values()) or 1.0
    out = {}
    for k in universe:
        if family:
            n = freq.get(''.join(c for c in k if not c.isdigit()), 0.0) / mx
        else:
            n = freq.get(k, 0.0) / mx
        out[k] = base.get(k, 1.0) * (0.3 + 0.7 * n)
    return out


def node_stat_txt(nd):
    """候选级审查输入的结构统计(中金: 审查侧只给'表达式+结构统计', 不知来源/IC/假设)"""
    nodes = collect(nd)
    leaves = sorted({n.op for n in nodes if not n.args})
    ops = sorted({''.join(c for c in n.op if not c.isdigit()) for n in nodes if n.args})
    wins = sorted({int(x) for n in nodes for x in re.findall(r'\d+', n.op)})
    return (f"叶子字段: {','.join(leaves) or '无'}; 算子族: {','.join(ops) or '无'}; "
            f"节点数: {nd.size()}; 窗口参数: {wins or '无'}")


def llm_jury(args, rng, l1, model=None):
    """中金【审查】环节: L1 硬规则过滤后, 随机抽 --jury_n 个做 Sub-agent LLM 精判
    (与生成侧隔离防自证): verdict=KILL 者剔除出 L2; 调用失败/超时一律放行不误杀。
    返回 (kills:set[str], n_rev:int, n_kill:int, kill_lines:list[str])。"""
    import loop_llm
    kills, kill_lines, n_rev, n_kill = set(), [], 0, 0
    pool = list(l1['node'])
    n = min(max(0, int(getattr(args, 'jury_n', 5))), len(pool))
    if n <= 0:
        return kills, 0, 0, []
    print(f"  [LLM审查] 随机抽 {n} 个候选做 Sub-agent 精判 ...", flush=True)
    for i in rng.sample(range(len(pool)), n):
        nd = pool[i]
        ok, d = loop_llm.jury_verdict(str(nd), node_stat_txt(nd), model=model)
        if not ok:
            print(f"  [LLM审查] 判定失败({d}) -> 放行")
            continue
        n_rev += 1
        if d.get('verdict') == 'KILL':
            n_kill += 1
            kills.add(str(nd))
            reason = (d.get('reason') or '').replace('\n', ' ')
            kill_lines.append(f"- KILL `{nd}`\n  > 理由: {reason}")
            print(f"  [LLM审查] KILL {str(nd)[:72]} | {reason[:40]}")
        else:
            print(f"  [LLM审查] PASS {str(nd)[:72]}")
    return kills, n_rev, n_kill, kill_lines


def llm_jury_block(gen, n_rev, n_kill, kill_lines, path):
    """B角候选级审查小结追加 journal(引用体, 不干扰 _journal_format 的表格处理)"""
    body = [f"\n**LLM 候选审查(B角 {gen}代)**: 深判 {n_rev} 个, "
            f"KILL {n_kill} 个(剔除出 L2 费后回测)"]
    body += kill_lines if kill_lines else ['> (全部 PASS)']
    body.append('')
    with open(path, 'a', encoding='utf-8') as f:
        f.write('\n'.join(body) + '\n')


def llm_journal_block(gen, calls, parsed, used, hyp, path):
    """A角 LLM 引导小结追加 journal(引用体, 不干扰 _journal_format 的表格处理)"""
    body = [f"\n**LLM 引导(A角 {gen}代)**: 调用{calls}次, 解析通过{parsed}条, "
            f"引导位使用{used}条"]
    if hyp:
        body += ['> ' + x for x in hyp.splitlines()]
    else:
        body.append('> (本次无机制族假设)')
    body.append('')
    with open(path, 'a', encoding='utf-8') as f:
        f.write('\n'.join(body) + '\n')


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
    ap.add_argument('--ai_critic', default='auto', choices=['auto', 'on', 'off'],
                    help='B角LLM审查(DeepSeek): auto=找到key(环境变量DEEPSEEK_API_KEY或桌面1.txt)'
                         '即每代末尾自动AI审查并写journal; on=强制(无key仅告警跳过); off=纯规则B角')
    ap.add_argument('--llm_guide', default='auto', choices=['auto', 'on', 'off'],
                    help='A角生成侧LLM引导(中金生成预算~20%语义引导位): '
                         'auto=找到DeepSeek key即启用(引导位候选=LLM表达式); '
                         'on=强制(无key告警后回退本地引导); off=纯本地规则引导')
    ap.add_argument('--llm_n', type=int, default=12,
                    help='每次A角LLM调用请求的表达式条数(建议8~16, loop_llm上限)')
    ap.add_argument('--llm_max_calls', type=int, default=3,
                    help='每代最多A角LLM调用次数(超限回退本地 guided_expr, 防拖慢无人值守)')
    ap.add_argument('--llm_model', default=None,
                    help='A角生成侧模型名(缺省与B角审查同款 loop_llm.DEFAULT_MODEL=deepseek-v4-flash; '
                         '可选 deepseek-v4-pro/deepseek-reasoner 做物理隔离)')
    ap.add_argument('--ai_jury', default='auto', choices=['auto', 'on', 'off'],
                    help='B角候选级LLM审查(中金【审查】环节, L1硬滤后随机抽--jury_n深判, '
                         '与生成侧隔离防自证): KILL者剔除出L2; auto=找到DeepSeek key即启用; '
                         'on=强制(无key告警跳过); off=纯硬规则审查')
    ap.add_argument('--jury_n', type=int, default=5,
                    help='LLM候选精判每代抽样个数(中金随机抽5)')
    ap.add_argument('--ai_jury_model', default=None,
                    help='审查侧模型名(缺省同loop_llm.DEFAULT_MODEL=deepseek-v4-flash; '
                         '可选 deepseek-v4-pro 与生成侧做物理隔离)')
    ap.add_argument('--l2', type=int, default=40)
    ap.add_argument('--fam_quota', type=int, default=FAM_QUOTA,
                    help='结构族配额(QuantaAlpha冗余检测, gen31): L1通过集同模板族'
                         '(外层结构相同仅内层微调)最多保留N条进L2/种子池; 0=关闭')
    ap.add_argument('--fam_block_thr', type=float, default=FAM_BLOCK_THR,
                    help='结构族黑名单: 上代L1同模板族占比>=该值则本代生成端禁产该模板族'
                         '(强制结构换血); 0=关闭')
    ap.add_argument('--seed', type=int, default=42)
    ap.add_argument('--cost', type=float, default=COST_PRESETS['单边千1.5'],
                    help=f'往返成本, 默认单边千1.5=0.004; 档位: {COST_PRESETS}')
    ap.add_argument('--window', choices=['full', 'recent600'], default='full',
                    help='回测口径: full=2018起九年; recent600=最近600交易日(中金口径)')
    run(ap.parse_args())
