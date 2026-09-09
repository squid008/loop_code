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

# 叶子字段全集与引擎A角共用单一事实源 loop_fields.py(新增字段族只改那一处)
# 历史坑: 本文件曾硬编码旧12字段, 引擎叶子池扩展后 B角诊断漏认新族 -> 漂移
from loop_fields import LEAVES

# 已知有效因子(用于"是否又绕回已知族"的判断)
KNOWN_HINT = ['ln_mktcap', 'ln_volume', 'turnover', 'mktcap', 'amt']

# 长周期算子(稳定性友好) / 短周期算子(换手高)
SLOW_OPS = ['ts_mean20', 'ts_mean10', 'ts_rank60', 'ts_std60', 'ts_max20', 'ts_min20']
FAST_OPS = ['ts_mean5', 'ts_delay1', 'ts_delta5']


def _leaf_of(expr):
    """粗暴提取表达式里出现的叶子字段名(全集=loop_fields.LEAVES, 与引擎生成池同步)"""
    import re
    toks = set(re.findall(r'[A-Za-z_][A-Za-z0-9_]*', expr))
    return [t for t in toks if t in LEAVES]


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
            for lf in LEAVES:   # 叶子全集(含资金流/风格/财报扩展), 顺序=LEAVES 定义序
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


# ---- 五维配比护栏(对齐中金固定规格) ----
# mix 键序=变异/交叉/扰动/引导/随机; 中金研报固定配比:
#   变异25 / 交叉25 / 参数扰动15 / 随机探索15 / LLM机制引导20
#   -> 代码 mix=[0.25, 0.25, 0.15, 0.20, 0.15] (键2扰动15/键3引导20/键4随机15)
# B角自适应只落在 变异/交叉 两槽(合计50%), 各自保底 MIX_MIN 后重归一化 -> 恒和为1。
MIX_MIN = 0.10


def guard_mix(mix):
    """五维配比护栏: 修复运行态漂移/旧state槽位错位, 防变异归零与交叉翻倍过头。
    - 固定槽(中金规格): 扰动15% / LLM机制引导20% / 随机探索15%
    - 自适应槽: 变异+交叉合计=50%, 按原比例缩放且各≥MIX_MIN(单槽上限=50%-MIX_MIN)
    例: 旧state [0.006, 0.45, 0.15, 0.15, 0.2] -> [0.10, 0.40, 0.15, 0.20, 0.15]
    """
    m = [float(x) for x in (mix or [])]
    if len(m) != 5 or any(not np.isfinite(x) for x in m):
        m = [0.25, 0.25, 0.15, 0.20, 0.15]
    a, b = max(m[0], 0.0), max(m[1], 0.0)
    if a + b < 1e-9:
        a = b = 0.25
    a, b = a / (a + b) * 0.50, b / (a + b) * 0.50
    if a < MIX_MIN:
        a, b = MIX_MIN, 0.50 - MIX_MIN
    elif b < MIX_MIN:
        a, b = 0.50 - MIX_MIN, MIX_MIN
    return [round(a, 6), round(b, 6), 0.15, 0.20, 0.15]


def suggest(diag, cur=None):
    """根据诊断输出下一代搜索策略(规则透明, 每条带触发原因)"""
    cur = cur or {}
    s = dict(leaf_w=dict(cur.get('leaf_w', {})),
             op_bias=dict(cur.get('op_bias', {})),
             depth=list(cur.get('depth', [2, 3, 4])),
             mix=list(cur.get('mix', [0.25, 0.25, 0.15, 0.20, 0.15])),
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
    # 3) 结构多样性低 -> 加强探索(随机槽固定15%走数据驱动加权, 故提变异逼换新信号源)
    if diag.get('struct_div', 1) < 0.35:
        m = s['mix']
        s['mix'] = [min(0.40, m[0] + 0.10), max(0.10, m[1] - 0.10), m[2], m[3], m[4]]
        reasons.append(f"结构多样性{diag.get('struct_div',0):.2f}(同质化) -> "
                       f"变异预算提至{s['mix'][0]:.0%}逼探索新信号源")
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
    # 出口统一护栏: 规则(含从旧state继承的cfg)算出任何 mix 都强制回到中金规格内,
    # 且修正前后不一致时留痕, 便于在 journal 里追踪护栏生效
    mix_raw = list(s['mix'])
    s['mix'] = guard_mix(s['mix'])
    if any(abs(x - y) > 1e-9 for x, y in zip(s['mix'], mix_raw)):
        reasons.append(f"配比护栏: 变异/交叉各≥{MIX_MIN:.0%}且合计50%重归一化, "
                       f"扰动/引导/随机固定15/20/15(中金规格) -> "
                       f"mix={[round(x, 3) for x in s['mix']]}")
    return s, reasons


def report(diag, sug, reasons, path):
    """诊断报告 markdown, 追加写入"""
    lines = []
    lines.append(f"\n## 第 {diag['gen']} 代 (B角诊断)\n")
    # 指标横排 md 表格(键行/分隔/值行): 源码3行, 渲染为横向对齐表格
    keys = ['n_l1', 'ic_med', 'ic_max', 'stab_med', 'stab_lt50',
            'leaf_conc', 'struct_div', 'known_ratio',
            'n_l2', 'n_pass', 'ex_max',
            'fail_calmar', 'fail_turn', 'fail_negyear', 'fail_lastyr', 'fail_ic']
    present = [k for k in keys if k in diag]

    def _fmt(k):
        v = diag[k]
        return f"{v:.3f}" if isinstance(v, float) else str(v)

    lines.append("| " + " | ".join(present) + " |")
    lines.append("| " + " | ".join("---" for _ in present) + " |")
    lines.append("| " + " | ".join(_fmt(k) for k in present) + " |")
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


# =====================================================================
# LLM 审查通道(可选): 引擎 --ai_critic auto/on/off, 默认 auto
# auto=找到 DeepSeek key(环境变量 DEEPSEEK_API_KEY 或桌面 1.txt)即每代自动做一次 AI 审查,
#      审查全文(含本代统计摘要+规则建议)追加进 loop_journal.md, 人可随时复核/采纳;
# 未配置 key / 调用失败一律自动跳过 -> 纯规则 B角照常, 绝不影响无人值守迭代。
# 2026-09-09: 底层客户端(api_key/chat_once)统一迁至 loop_llm.py(供 生成侧/审查侧/代末
# 复盘 三角色共用, 各自独立 system prompt 做角色隔离); 本文件仅作封装避免重复实现。
# =====================================================================
_DEEPSEEK_MODEL = 'deepseek-v4-flash'


def _deepseek_key():
    """DeepSeek key 探测(委托 loop_llm.api_key, 避免双份实现)"""
    from loop_llm import api_key
    return api_key()


def _chat_once(messages, timeout=120, tag=''):
    """单轮 DeepSeek chat 调用(委托 loop_llm.chat_once; tag 进对话录音)"""
    from loop_llm import chat_once
    return chat_once(messages, timeout=timeout, tag=tag)


def _fmt_l1(l1, n=6):
    if l1 is None or not len(l1):
        return '(无 L1 候选)'
    df = l1.copy()
    if 'ic' in df:
        df = df.sort_values('ic', ascending=False)
    lines = []
    for _, r in df.head(n).iterrows():
        try:
            stab = float(r.get('stab', float('nan')))
        except (TypeError, ValueError):
            stab = float('nan')
        lines.append(f"- ic={r.get('ic', 0):.3f} stab={stab:.2f}  {r['expr']}")
    return '\n'.join(lines)


def _fmt_l2(l2, n=4):
    if l2 is None or not len(l2):
        return '(无 L2 结果)'
    df = l2.copy()
    if 'passed' in df:
        bad = df[~df['passed']]
        show = bad.head(n) if len(bad) else df.head(n)
    else:
        show = df.head(n)
    lines = []
    for _, r in show.iterrows():
        try:
            cal = float(r.get('calmar', float('nan')))
        except (TypeError, ValueError):
            cal = float('nan')
        lines.append(f"- calmar={cal:.2f} turn={r.get('turn', 0):.2f} "
                     f"neg_yr={r.get('neg_yr', 0)} passed={bool(r.get('passed', True))}  {r['expr']}")
    return '\n'.join(lines) if lines else '(无样本)'


def ai_review(diag, l1, l2, gen, journal_path, reasons=None, sug=None, force=False):
    """B角 LLM 审查: 调 DeepSeek 对第 gen 代诊断做体检并点评规则建议, 全文追加进 journal。
    返回 'ok'/'no_key'/'err'; 任何失败均跳过, 不影响主流程(规则 B角照常执行)。"""
    if not _deepseek_key():
        print("[AI审查] 未找到 DeepSeek key(环境变量 DEEPSEEK_API_KEY 或桌面 1.txt), "
              "本代跳过 -> 沿用规则B角")
        return 'no_key'
    keys = ['n_l1', 'ic_med', 'ic_max', 'stab_med', 'stab_lt50', 'leaf_conc',
            'struct_div', 'known_ratio', 'n_l2', 'n_pass', 'ex_max',
            'fail_calmar', 'fail_turn', 'fail_negyear', 'fail_lastyr', 'fail_ic']
    stat = ', '.join(f"{k}={diag.get(k):.3f}" if isinstance(diag.get(k), float)
                     else f"{k}={diag.get(k)}" for k in keys if k in diag)
    leaf_hist = diag.get('leaf_hist')
    rule_txt = '; '.join(reasons) if reasons else '(无)'
    sug_txt = (f"mix={sug['mix']} depth={sug['depth']} min_stab={sug.get('min_stab')} "
               f"decorr={sug.get('decorr')} fsa_th={sug.get('fsa_th')} "
               f"bank_skel_max={sug.get('bank_skel_max')}") if sug else '(无)'
    user_txt = (
        f"第 {gen} 代诊断统计:\n{stat}\n"
        f"叶子使用: {leaf_hist}\n\n"
        f"L1 头部候选(按ic降序):\n{_fmt_l1(l1)}\n\n"
        f"L2 样本:\n{_fmt_l2(l2)}\n\n"
        f"规则B角建议(引擎将按此执行):\n- {rule_txt}\n"
        f"下代表格: {sug_txt}\n")
    sys_txt = (
        "你是资深A股量价因子研究员, 在中金 Loop Engineering 双Agent框架里扮演 B角(审查者/启发者)。"
        "输入是一轮因子挖掘迭代的诊断统计与规则B角建议。请只做三件事:\n"
        "(1) 用一句话点出本轮最核心的病根;\n"
        "(2) 逐条点评规则B角建议是否对症, 指出可能无效或互相冲突的点;\n"
        "(3) 给出你自己对下代 mix(变异/交叉/扰动/引导/随机)/depth/min_stab/decorr 的取值与一句话理由。\n"
        "硬性要求: 中文, 全文≤260字, 用(1)(2)(3)分条, 禁止markdown表格/管道符/代码块。")
    import time
    try:
        t0 = time.time()
        resp = _chat_once([{'role': 'system', 'content': sys_txt},
                           {'role': 'user', 'content': user_txt}],
                          tag='B角代末审查(ai_review)')
        cost = time.time() - t0
    except Exception as e:
        print(f"[AI审查] DeepSeek 调用失败({type(e).__name__}: {e}) -> 跳过, 沿用规则B角")
        return 'err'
    block = (f"\n**AI 审查(DeepSeek {_DEEPSEEK_MODEL}, {cost:.0f}s)**:\n\n"
             + '\n'.join('> ' + x for x in resp.splitlines()) + '\n')
    os.makedirs(os.path.dirname(journal_path), exist_ok=True)
    with open(journal_path, 'a', encoding='utf-8') as f:
        f.write(block)
    preview = resp.replace('\n', ' ')[:220]
    print(f"[AI审查] DeepSeek 审查完成({cost:.0f}s), 已写入 {journal_path}\n"
          f"  {preview}...")
    return 'ok'
