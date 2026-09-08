# -*- coding: utf-8 -*-
"""
B角(审查者 / 启发者) —— 中金 Loop Engineering 双Agent架构的另一半
=====================================================================
A角(loop_engine): 负责"挖" —— 五维演化生成候选
B角(本文件)     : 负责"监督 + 启发" ——
  1) 审查 diagnose(): 对上一代结果做体检
       - 结构多样性(是不是都在原地打转)
       - 叶子/算子使用集中度(是不是被某类字段绑架)
       - 稳定性分布(是不是全是高换手噪声)
       - L2 失败原因分布(弱信号? 换手高? 年度不稳?)
       - 与已知因子的相关性(是不是又绕回已知族)
  2) 启发 suggest(): 根据体检结果输出【下一代搜索策略】
       - 五维配比(变异/交叉/扰动/引导/随机)
       - 叶子权重 / 算子偏好 / 表达式深度
       - 稳定性门槛 / 去相关阈值
  3) 留痕 report(): 生成 markdown 诊断报告(写入 loop_journal.md)

设计原则: **规则透明可解释**(不是黑箱调参), 每条建议都写明触发原因,
         便于人工复核与推翻(人始终是最终B角)。
"""
import os
import hashlib
import numpy as np
import pandas as pd

# 已知有效因子(用于"是否又绕回已知族"的判断)
KNOWN_HINT = ['ln_mktcap', 'ln_volume', 'turnover', 'mktcap', 'amt']

# 长周期算子(稳定性友好) / 短周期算子(换手高)
SLOW_OPS = ['ts_mean20', 'ts_mean10', 'ts_rank60', 'ts_std60', 'ts_max20', 'ts_min20']
FAST_OPS = ['ts_mean5', 'ts_delay1', 'ts_delta5']


def _leaf_of(expr):
    """粗暴提取表达式里出现的叶子字段名"""
    import re
    toks = set(re.findall(r'[A-Za-z_][A-Za-z0-9_]*', expr))
    leaves = ['close', 'open', 'high', 'low', 'volume', 'turnover', 'mktcap',
              'vwap', 'ret', 'turn_ratio', 'ln_mktcap', 'ln_volume']
    return [t for t in toks if t in leaves]


def _ops_of(expr):
    import re
    toks = re.findall(r'[A-Za-z_][A-Za-z0-9_]*', expr)
    ops = ['ts_mean5', 'ts_mean10', 'ts_mean20', 'ts_std20', 'ts_std60', 'ts_max20',
           'ts_min20', 'ts_rank20', 'ts_rank60', 'ts_delay1', 'ts_delta5', 'ts_delta20',
           'ts_sum20', 'cs_rank', 'cs_demean', 'cs_scale', 'corr20', 'corr60',
           'log', 'abs', 'neg', 'sign', 'add', 'sub', 'mul', 'div', 'min', 'max']
    return [t for t in toks if t in ops]


def diagnose(l1, l2, gen, verbose=True):
    """l1: L1候选DataFrame(需含 expr/ic/ic_ir/stab/sign);
       l2: L2精筛结果DataFrame(需含 expr/ann_ex/calmar/sharpe/turn/neg_yr/last_yr/passed) 或 None
    """
    d = {}
    d['gen'] = gen
    d['n_l1'] = 0 if l1 is None or not len(l1) else len(l1)
    if d['n_l1']:
        d['ic_med'] = float(l1['ic'].median())
        d['ic_max'] = float(l1['ic'].max())
        d['stab_med'] = float(l1['stab'].median())
        d['stab_lt50'] = float((l1['stab'] < 0.5).mean())
        # 叶子集中度
        lc = {}
        for e in l1['expr']:
            for lf in set(_leaf_of(e)):
                lc[lf] = lc.get(lf, 0) + 1
        d['leaf_top'] = max(lc.items(), key=lambda x: x[1]) if lc else ('-', 0)
        d['leaf_conc'] = d['leaf_top'][1] / max(d['n_l1'], 1)
        d['leaf_hist'] = dict(sorted(lc.items(), key=lambda x: -x[1])[:6])
        # 结构多样性: 表达式骨架(去掉叶子名)去重率
        sk = []
        for e in l1['expr']:
            s = e
            for lf in ['close', 'open', 'high', 'low', 'volume', 'turnover',
                       'mktcap', 'vwap', 'ret', 'turn_ratio', 'ln_mktcap', 'ln_volume']:
                s = s.replace(lf, 'X')
            sk.append(hashlib.md5(s.encode()).hexdigest()[:8])
        d['struct_div'] = len(set(sk)) / max(len(sk), 1)
        # 已知族占比
        d['known_ratio'] = float(np.mean([any(k in e for k in KNOWN_HINT)
                                          for e in l1['expr']])) if d['n_l1'] else 0.0
    d['n_l2'] = 0 if l2 is None or not len(l2) else len(l2)
    if d['n_l2']:
        d['n_pass'] = int(l2['passed'].sum())
        d['ex_max'] = float(l2['ann_ex'].max())
        # 失败原因分布
        fail = l2[~l2['passed']]
        if len(fail):
            d['fail_calmar'] = float((fail['calmar'] <= 0.5).mean())
            d['fail_turn'] = float((fail['turn'] > 0.30).mean())
            d['fail_negyear'] = float((fail['neg_yr'] > 1).mean())
            d['fail_lastyr'] = float((fail['last_yr'] <= 0).mean())
            d['fail_ic'] = float((fail['ic'] < 0.02).mean())
        else:
            for k in ['fail_calmar', 'fail_turn', 'fail_negyear', 'fail_lastyr', 'fail_ic']:
                d[k] = 0.0
    if verbose:
        print("\n" + "=" * 74)
        print(f"[B角诊断] 第 {gen} 代")
        print("=" * 74)
        for k, v in d.items():
            if isinstance(v, float):
                print(f"  {k:14s} {v:7.3f}")
            else:
                print(f"  {k:14s} {v}")
    return d


def suggest(diag, cur=None):
    """根据诊断输出下一代搜索策略(规则透明, 每条带触发原因)"""
    cur = cur or {}
    s = dict(leaf_w=dict(cur.get('leaf_w', {})),
             op_bias=dict(cur.get('op_bias', {})),
             depth=list(cur.get('depth', [2, 3, 4])),
             mix=list(cur.get('mix', [0.25, 0.25, 0.15, 0.15, 0.20])),
             min_stab=cur.get('min_stab', 0.30),
             decorr=cur.get('decorr', 0.75),
             fsa_th=cur.get('fsa_th', 0.15),
             bank_skel_max=cur.get('bank_skel_max', 1))
    reasons = []

    # 1) 叶子过度集中 -> 压低该叶子
    if diag.get('leaf_conc', 0) > 0.40:
        top = diag['leaf_top'][0]
        s['leaf_w'][top] = 0.25
        reasons.append(f"叶子[{top}]占比{diag['leaf_conc']:.0%}过高 -> 权重压到0.25, 逼引擎换字段")
    # 2) 稳定性差 -> 抬高门槛 + 偏好长周期算子
    if diag.get('stab_med', 1) < 0.60 or diag.get('stab_lt50', 0) > 0.40:
        s['min_stab'] = min(0.60, s['min_stab'] + 0.15)
        for o in SLOW_OPS:
            s['op_bias'][o] = 1.8
        for o in FAST_OPS:
            s['op_bias'][o] = 0.4
        reasons.append(f"稳定性中位{diag.get('stab_med',0):.2f}(低) -> min_stab提到{s['min_stab']:.2f}, "
                       f"偏好长周期算子")
    # 3) 结构多样性低 -> 提高随机探索
    if diag.get('struct_div', 1) < 0.35:
        m = s['mix']
        s['mix'] = [m[0] * 0.8, m[1] * 0.8, m[2] * 0.8, m[3] * 0.8, min(0.45, m[4] + 0.20)]
        reasons.append(f"结构多样性{diag.get('struct_div',0):.2f}(同质化) -> 随机探索配比提到"
                       f"{s['mix'][4]:.0%}")
    # 4) L2 主要因换手失败 -> 再抬稳定性
    if diag.get('fail_turn', 0) > 0.40:
        s['min_stab'] = min(0.75, s['min_stab'] + 0.10)
        reasons.append(f"L2中{diag['fail_turn']:.0%}因换手过高失败 -> min_stab再+0.10")
    # 5) L2 主要因Calmar不足(信号弱) -> 加强交叉(把已有信号组合起来)
    if diag.get('fail_calmar', 0) > 0.55 and diag.get('n_l2', 0) >= 8:
        m = s['mix']
        s['mix'] = [m[0] * 0.85, min(0.45, m[1] + 0.15), m[2], m[3], m[4]]
        s['depth'] = [3, 4, 4]
        reasons.append(f"L2中{diag['fail_calmar']:.0%}因Calmar不足(信号弱) -> 交叉+15%, 深度加深")
    # 6) 又绕回已知族 -> 收紧去相关阈值(对象=人工基准+历代入库bank, 对齐中金"入库IC<0.70")
    #    ⚠ 原实现 known_ratio 高时放宽到0.85是反的: 已知族候选占满L1却无法入库,
    #    应把更像已知者的拦在L2外, 逼搜索离开已知族; 放宽只会放更多同族进L2.
    if diag.get('known_ratio', 0) > 0.60:
        floor = 0.65 if diag.get('n_pass', 0) == 0 else 0.70
        if s['decorr'] > floor:
            s['decorr'] = max(floor, s['decorr'] - 0.05)
            reasons.append(f"{diag['known_ratio']:.0%}候选仍含已知族字段 -> decorr收紧到"
                           f"{s['decorr']:.2f}(0.70≈中金入库IC相关口径)")
    # 7) 连续无产出 -> 换方向: 提高深度 + 提高随机
    if diag.get('n_pass', 0) == 0 and diag.get('n_l2', 0) >= 10:
        s['depth'] = [3, 4, 5]
        reasons.append("本代0通过 -> 深度放宽到3~5, 探索更复杂结构")
    if not reasons:
        reasons.append("各项指标正常, 维持当前策略")
    return s, reasons


def report(diag, sug, reasons, path):
    """诊断报告 markdown, 追加写入"""
    lines = []
    lines.append(f"\n## 第 {diag['gen']} 代 (B角诊断)\n")
    lines.append("| 指标 | 值 |")
    lines.append("|---|---|")
    for k in ['n_l1', 'ic_med', 'ic_max', 'stab_med', 'stab_lt50',
              'leaf_conc', 'struct_div', 'known_ratio',
              'n_l2', 'n_pass', 'ex_max',
              'fail_calmar', 'fail_turn', 'fail_negyear', 'fail_lastyr', 'fail_ic']:
        if k in diag:
            v = diag[k]
            lines.append(f"| {k} | {v:.3f} |" if isinstance(v, float) else f"| {k} | {v} |")
    if 'leaf_hist' in diag:
        lines.append(f"\n叶子使用: {diag['leaf_hist']}")
    lines.append("\n**B角建议(下一代策略)**:")
    for r in reasons:
        lines.append(f"- {r}")
    lines.append(f"\n```\nmix={[round(x,3) for x in sug['mix']]}  "
                 f"depth={sug['depth']}  min_stab={sug['min_stab']}  "
                 f"decorr={sug['decorr']}  fsa_th={sug.get('fsa_th',0.15)}  "
                 f"bank_skel_max={sug.get('bank_skel_max',1)}\nleaf_w={sug['leaf_w']}\n```")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'a', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')
