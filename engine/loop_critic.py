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
# 长周期算子(稳定性友好) —— ★ 2026-09-15 加 `ema60`：EMA 是**指数平滑**，
#   对近期加权但尾部衰减 ⇒ 天然**低换手/高稳定**，正是这一档想要的 ✓
SLOW_OPS = ['ts_mean20', 'ts_mean10', 'ts_rank60', 'ts_std60', 'ts_max20', 'ts_min20',
            'ema60']
FAST_OPS = ['ts_mean5', 'ts_delay1', 'ts_delta5']

# =====================================================================
# ★★★ 规则「动作」登记表 + 饱和检测 + LLM 否决(2026-09-14, docs/loop_todo.md §1.1)
# ---------------------------------------------------------------------
# 为什么必须给动作起**稳定 ID**（三条独立的理由）：
#   ① **饱和检测**：一个"条件触发"的规则若**条件恒真**，它就退化成**固定偏移**，
#      并会在多代间**累积**直到撞边界（实测 `depth` 被永久推到 [3,4,4]、`mix` 交叉撞 0.4）。
#      ⇒ 必须能识别"**这已经是第 N 代施加同一个动作了**" ⇒ 需要动作有名字。
#   ② **LLM 否决/降权通道**：LLM 审查此前只能写散文（"深度加深有害"），而散文**无法回写
#      `sug`** ⇒ 85/98 次独立反驳全部被浪费。给了 ID，LLM 才能输出**机器可读**的否决。
#   ③ **留痕**：journal 里能写清"这代施加了什么 / 哪条被拦、为什么" ⇒ 人工可复核、可推翻。
RULE_NAMES = {
    'r1_leaf_conc':    '叶子过度集中 -> 压低该叶子权重',
    'r2_stab_low':     '稳定性差 -> min_stab+ / 偏好长周期算子',
    'r3_struct_div':   '结构多样性低 -> 变异预算+10%',
    'r4_fail_turn':    'L2 多因换手失败 -> min_stab 再+0.10',
    'r5_calmar_cross': 'L2 多因 Calmar 不足 -> 交叉+15% / 深度加深',
    'r6_known_ratio':  '候选仍绕已知族 -> decorr 收紧',
    'r7_zero_pass':    '本代 0 通过 -> 深度放宽到 3~5',
}
# 饱和检测：同一动作**连续 SAT_N 代**被施加 ⇒ 视为饱和，冷却 COOL_N 代不再施加。
#   SAT_N=2 的依据：rule5 在 96/96 代上都触发（`fail_calmar` 区间 0.846~1.000）
#   ⇒ 连续 2 代足以判定"它不是自适应，是固定动作"，无需等到更多代才叫停。
SAT_N = 2
COOL_N = 3

# =====================================================================
# ★★★ 动作「有效性」追踪（2026-09-14, docs/loop_todo.md §1.15）
# ---------------------------------------------------------------------
# **要解决什么**：饱和检测只回答"**别重复**"，**不回答"为什么无效"**。
#   ★ 实测（全A 池 gen61~gen73）：`r1_leaf_conc` **连续 13 代**都在压同一个叶子
#     `barra_residual_volatility`，而 `leaf_conc` **始终回到 62%~100%**
#     ⇒ **动作施加了，但完全无效** ✗
#   **根因**：压权重治不了"它是当前面板里最强的信号源" —— 压到 0.25 只是**降低出现频率**，
#     不改变"它一出现就赢"。
# ⇒ 所以必须**记住施加前的指标基线**，等它下次有机会再施加时，**先算账**：
#   施加了一段(含冷却期)之后，**目标指标真的改善了吗**？没改善 ⇒ **判定无效**。
#
# 判"改善"的方向与容差：
#   `up=True`  = 越大越好（如 struct_div / n_pass / stab_med）
#   `up=False` = 越小越好（如 leaf_conc / fail_* / known_ratio）
#   `EPS` = **必须超过的改善幅度**（否则视为噪声）—— 不能设 0，否则同值也会算"没恶化"。
#   ⚠ 指标**缺失**时**一律不判定**（不臆造，roadmap §8.45 铁律）。
ACTION_METRIC = {
    'r1_leaf_conc':    ('leaf_conc',   False),
    'r2_stab_low':     ('stab_med',    True),
    'r3_struct_div':   ('struct_div',  True),
    'r4_fail_turn':    ('fail_turn',   False),
    'r5_calmar_cross': ('fail_pool_calmar', False),   # 池口径优先，缺失时退回 fail_calmar
    'r6_known_ratio':  ('known_ratio', False),
    'r7_zero_pass':    ('n_pass',      True),
}
METRIC_EPS = 0.02          # 必须改善的最小幅度（低于此视为噪声/无效）
INEFF_MUTE_N = 2           # 判「无效」达到该次数 ⇒ **永久停用**（与 LLM 否决同级的证伪）
INVALID_COOL_MULT = 2      # 判无效一次 ⇒ 冷却时长**翻倍**（3 -> 6 -> 12 ...）


def _metric_of(diag, aid):
    """取该动作的**目标指标**当前值；取不到返回 `None`（⇒ **不判定**，不臆造）。"""
    key, up = ACTION_METRIC.get(aid, (None, None))
    if key is None:
        return None, None, None
    v = diag.get(key)
    if v is None and aid == 'r5_calmar_cross':
        key, v = 'fail_calmar', diag.get('fail_calmar')      # 池口径缺失 -> 退回全A 口径
    try:
        fv = float(v)
    except (TypeError, ValueError):
        return None, None, None
    return (fv if np.isfinite(fv) else None), up, key


def _improved(old, new, up):
    """`new` 相对 `old` 是否**有实质改善**（方向 + 容差）。"""
    if old is None or new is None:
        return None                       # 不可比 ⇒ 不判定
    d = (new - old) if up else (old - new)
    return bool(d > METRIC_EPS)


def _rollback_plan(s, aid, base):
    """★ §1.1「参数棘轮」的**保守回退**：只回退**本动作确实改过、且之后没人再动**的参数。

    ## 要解决什么
    饱和/永久闭嘴只阻止动作**继续**施加，**不会撤销它已经改过的值**。
    ★ 实测：gen1 的 `r5`+`r7` 把 `depth` 推到 `[3,4,5]`，此后即使永久闭嘴，
      `depth` **仍停在 `[3,4,5]`**（LLM 建议的是 `[2,3]`）⇒ **历史漂移永久固化** ✗

    ## 为什么"保守"（判据 = 当前值是否仍等于本动作写入的值）
    多个动作会改**同一个参数**（`r2` 与 `r4` 都改 `min_stab`；`r5` 与 `r7` 都改 `depth`）
    ⇒ 无脑恢复会**覆盖掉别的动作的修改** ✗
    ⇒ 只在「**该参数当前值 == 本动作最后写入的值**」时才回退（= 之后没人动过它 ⇒ 安全）；
      否则**跳过并留痕**（宁可少回退，不可误撤）。

    :param base: `{参数名: (旧值, 新值)}`（只含**本动作**改过的）
    :return: (恢复列表 [(参数, 恢复为)], 跳过列表 [(参数, 原因)])
    """
    done, skip = [], []
    for p, (old, new) in (base or {}).items():
        cur = _get_param(s, p)
        if cur is None:
            skip.append((p, '参数不存在'))
            continue
        if cur != new:
            skip.append((p, '已被后续动作改过（当前 {} ≠ 本动作写入 {}）'.format(_fmtv(cur), _fmtv(new))))
            continue
        _set_param(s, p, old)
        done.append((p, old))
    return done, skip


def _get_param(s, p):
    """扁平参数名 -> 值（`leaf_w.<leaf>` / `op_bias.<op>` 走嵌套）。取不到返回 `None`。"""
    if '.' in p:
        head, sub = p.split('.', 1)
        return (s.get(head) or {}).get(sub)
    return s.get(p)


def _set_param(s, p, v):
    """扁平参数名 -> 写回（嵌套同理）。"""
    if '.' in p:
        head, sub = p.split('.', 1)
        s.setdefault(head, {})[sub] = v
    else:
        s[p] = v


def _fmtv(v):
    """紧凑打印参数值（列表如 `depth`/`mix` 用 `[3,4,5]`）。"""
    if isinstance(v, (list, tuple)):
        return '[{}]'.format(','.join(('%g' % x) if isinstance(x, (int, float)) else str(x)
                                      for x in v))
    if isinstance(v, float):
        return '%.3f' % v
    return str(v)
# 特殊常量：★ LLM 否决专用**持久哨兵**（2026-09-14 用户拍板「**让它永久闭嘴**」）。
#   语义与"冷却"完全不同：冷却到期会**自动解禁**（规则还会再来一遍）；
#   哨兵 = **一旦被 LLM 否决过，该动作对后续所有代永久失效**，直到人工改 `_muted`。
#   存法用 gens 里的 `None`（不是代号）⇒ 与"按代幂等"的普通否决共存、互不干扰。
MUTE = None


def _no_fire(reasons, aid, why):
    """统一的"动作未施加"留痕（★ 静默是禁止的，见 roadmap §8.44 铁律）。

    ⚠ **必须带动作 ID**（2026-09-14 回归测试抓到）：初版只写 `【拦截】(未施加) <原因>`，
      没带 ID ⇒ 在 journal 里**无法按动作 grep**（想查"r5 到底被拦了几代"只能肉眼翻）。
      ⇒ 格式统一为 `【拦截】[<id>] <原因> —— <动作名>`。
    """
    reasons.append('【拦截】[{}] {} —— {}'.format(aid, why, RULE_NAMES.get(aid, aid)))


def _fired(act, aid, gen):
    """登记"本代施加了该动作"（**按代幂等**：同代被登记两次不会重复追加）。

    ⚠ 为什么必须幂等：`loop_engine` 每代会调 `suggest()` **两次**
      （代首 L1132 用上代数据定本代策略 + 代末 L2078 定下代策略），
      两者 `diag['gen']` 分别是 `gen-1` 与 `gen`，且**都可能登记同一动作**
      ⇒ 不幂等就会把历史记成两份，饱和检测判断全错。
    """
    gs = act.setdefault(aid, [])
    if None not in gs and gen not in gs:
        gs.append(gen)
    return gs


def _saturated(act, aid, gen):
    """饱和检测：该动作在 `gen-1 .. gen-SAT_N` **连续**都触发过？"""
    gs = set(act.get(aid) or [])
    if MUTE in gs:          # 已被 LLM 永久闭嘴 -> 永远视为饱和
        return True
    return all((gen - k) in gs for k in range(1, SAT_N + 1))


def _cooling(cool, aid, gen):
    """冷却中？（`_cool` 记 {aid: 解禁代}) —— 饱和后停手 COOL_N 代再重新评估。"""
    return gen < int(cool.get(aid, -10 ** 9))


def _muted(veto, aid):
    """被 LLM **永久否决**过？（`_veto[aid]` 含哨兵 `MUTE`）

    用户原话（2026-09-14）：「**让它永久闭嘴**」——
    LLM 对同一条动作**连续多次**反对时，不再一代一代地拦，而是**一次性永久关掉**它。
    判"连续多次"用 `LLM_MUTE_N`；达到即写入哨兵。
    """
    return MUTE in set(veto.get(aid) or [])


LLM_MUTE_N = 2      # LLM 连续否决达到该次数 -> 该动作**永久**停用（写哨兵）


def _leaf_of(expr):
    """粗暴提取表达式里出现的叶子字段名(全集=loop_fields.LEAVES, 与引擎生成池同步)"""
    import re
    toks = set(re.findall(r'[A-Za-z_][A-Za-z0-9_]*', expr))
    return [t for t in toks if t in LEAVES]


_OP_CACHE = []


def _op_names():
    """★ **算子名单一事实源** = 引擎的 `UNARY` + `BINARY`（惰性导入 + 缓存）。

    **为什么用惰性 import**：`loop_engine` 会 `import loop_critic`（B角 是它的一部分），
    所以顶部 `import loop_engine` 会**循环导入** ⇒ 必须放到函数里 + 缓存（只取一次）✓
    """
    if not _OP_CACHE:
        import loop_engine as LE
        _OP_CACHE.append(tuple(LE.UNARY.keys()) + tuple(LE.BINARY.keys()))
    return _OP_CACHE[0]


def _ops_of(expr):
    """粗暴提取表达式里出现的**算子**名（白名单 = 引擎单一事实源，见 `_op_names`）。

    ★★★ 2026-09-15 修（`loop_todo §1.25`）—— **原实现硬编码 28 个算子**，
      而引擎实际有 `UNARY(35) + BINARY(10) = 45` 个 ⇒ **缺 15 个**：
      `ts_mean60/100/120/150/200` · `ts_std100/150/200` · `ts_rank100/200` ·
      `ts_max100` · `ts_min100` · `ts_delta60/120` · `ts_sum100` · `corr100/200`
      ⇒ **长窗口算子一直被 B角 的结构诊断忽视** ✗
      ★ 这与项目史上「`loop_critic` 硬编码旧 12 字段」（见 `loop_fields.py` 头注）
        是**同一类漂移** ⇒ 所以这次**不再补名单，而是改成派生** ✓
    ⇒ 已加回归测试 `tools/_test_ops_sync.py` 锁住它（以后加算子若忘了同步会**直接报错**）✓
    """
    import re
    toks = set(re.findall(r'[A-Za-z_][A-Za-z0-9_]*', expr))
    return [t for t in toks if t in _op_names()]


def diagnose(l1, l2, gen, verbose=True, gate=None, pool_map=None):
    """l1: L1候选DataFrame(需含 expr/ic/ic_ir/stab/sign);
       l2: L2精筛结果DataFrame(需含 expr/ann_ex/calmar/sharpe/turn/neg_yr/last_yr/passed) 或 None

    ★★★ 2026-09-14 起新增 `gate` / `pool_map` —— 修 `docs/loop_todo.md` §1.1 的**传感器失真**：

    **旧实现的病**：`fail_calmar` 写死 `(fail['calmar'] <= 0.5)` —— ① **0.5 是硬编码**，
    与实际生效的 `--min_calmar` 可以完全不相干；② 取的是**全A 口径**，而**池内模式**的判定
    用的是**池口径**（`任一池 Calmar > --min_pool_calmar`）⇒ 它**回答不了"离真正卡住你的那道门差多远"**。
    实测：`pool=1000 gen1` 报 `fail_calmar=1.000`，而同代**确有 2 个候选 Calmar 0.661/0.561 通过入库**
    ⇒ **指标自相矛盾**，且 96/96 代都触发规则5 ⇒ 自适应退化成固定动作。

    **新实现给三个量**（前两个是"对账"，第三个是"不随配置漂移"的锚）：
      · `fail_calmar`       —— 用**生效的** `min_calmar` 判（对账 ✓）
      · `fail_calmar_neg`   —— `calmar <= 0` 占比 = **真·信号弱**（**不随任何配置漂移** ✓）
      · `fail_pool_calmar`  —— **池口径**：失败者里"**没有任何一个池**过 `min_pool_calmar`"的占比
                               ⇒ 池内模式下**这才是真实卡点**（需 `pool_map`）

    :param gate: 生效门槛 dict（`min_calmar`/`min_sharpe`/`min_pool_calmar`/`pool_gate_on`/
                 `pool_mode`/`or_all`）。由 `loop_engine._gate_of(args)` 提供，**单一事实源**。
                 缺省/None ⇒ 退回旧行为（0.5），保证老调用方不炸。
    :param pool_map: `{expr: 该候选最好池的 calmar}`。由引擎从 `pool_rows` 聚合。
                     缺省 ⇒ 不产出 `fail_pool_calmar`（**宁可缺，不臆造**）。
    """
    gate = gate or {}
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
        # ★ 生效门槛回显（让 journal 里"诊断用的门槛"与"实际生效的门槛"可直接对账）
        _mc = float(gate.get('min_calmar', 0.5)) if gate else 0.5
        d['gate_min_calmar'] = _mc
        if gate:
            d['gate_min_pool_calmar'] = float(gate.get('min_pool_calmar', -1.0))
            # 池门槛的 OR/AND 语义（供 rule5 的留痕文字说明"卡在哪种语义上"）
            d['gate_pool_mode'] = gate.get('pool_mode', 'any')
            d['gate_or_all'] = bool(gate.get('or_all', False))
        if len(fail):
            # ★ 对账后的 fail_calmar：用**生效的** min_calmar（不再是硬编码 0.5）
            d['fail_calmar'] = float((fail['calmar'] <= _mc).mean())
            # ★★ 稳定锚：真·信号弱 = 连 Calmar>0 都没到（不随任何配置漂移）
            d['fail_calmar_neg'] = float((fail['calmar'] <= 0).mean())
            d['fail_turn'] = float((fail['turn'] > 0.30).mean())
            d['fail_negyear'] = float((fail['neg_yr'] > 1).mean())
            d['fail_lastyr'] = float((fail['last_yr'] <= 0).mean())
            d['fail_ic'] = float((fail['ic'] < 0.02).mean())
            # ★★ 池口径（池内模式下**真实卡点**）：失败者里"没有一个池达标"的占比。
            #    口径与引擎的 `pool_gate_ok` 一致：任一池 calmar > min_pool_calmar 即达标。
            #    ⚠ pool_map 缺失(未开池观测/上代没存) -> **不产出该键**（宁可缺，不臆造 ——
            #      与 strip/池门槛/LLM 同一条"缺失即放行不误杀"的铁律）。
            _mpc = gate.get('min_pool_calmar', -1.0)
            if pool_map is not None and _mpc is not None and _mpc >= 0:
                _pm = [pool_map.get(str(e)) for e in fail['expr']]
                _pm = [x for x in _pm if x is not None and np.isfinite(x)]
                if _pm:
                    d['fail_pool_calmar'] = float(np.mean([x <= _mpc for x in _pm]))
            # 分段独立验证击杀(基础指标可能全达标, 仅因某段失效被拦; 缺失则=0)
            if 'seg_ok' in l2.columns:
                d['seg_kill'] = float((l2['seg_ok'] == False).mean())
            else:
                d['seg_kill'] = 0.0
        else:
            for k in ['fail_calmar', 'fail_calmar_neg', 'fail_turn', 'fail_negyear',
                      'fail_lastyr', 'fail_ic']:
                d[k] = 0.0
            d['seg_kill'] = 0.0
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
    """根据诊断输出下一代搜索策略(规则透明, 每条带触发原因)

    ★★★ 2026-09-14 重构（`docs/loop_todo.md` §1.1 修法 ②③④）—— 加了三件事：

    **(A) 动作记忆 + 饱和检测**：每条规则动作有**稳定 ID**（见 `RULE_NAMES`）。
        同一动作**连续 `SAT_N` 代**被施加 ⇒ 判为**饱和** ⇒ **冷却 `COOL_N` 代不再施加**，并留痕。
        **动机**：实测 rule5 在 **96/96 代**上都触发（`fail_calmar` 区间仅 0.846~1.000）
        ⇒ 它不是"自适应"而是**固定偏移** ⇒ `depth` 被**永久**推到 `[3,4,4]`、`mix` 交叉撞 0.4。

    **(B) LLM 否决 / 降权通道**：`cur['_veto']` 里被 LLM 点名否决的动作，本代**跳过**；
        同一动作被 LLM **连续否决 `LLM_MUTE_N` 次** ⇒ 升级为**永久哨兵 `MUTE`**
        —— 用户原话「**让它永久闭嘴**」，不再一代一代地拦。
        **动机**：`ai_review()` 的返回值此前**只打印、从不回写 `sug`** ⇒ 85/98 次独立、一致的反驳**全被浪费**。

    **(C) 用"真正卡住的那道门"当判据**：池内模式下 rule5 改看 **`fail_pool_calmar`**（池口径 = 真实卡点）；
        无池数据时退回**对账后**的 `fail_calmar`。

    ⚠ **禁止静默**（见 roadmap §8.44 铁律）：任何"动作没施加"都必须由 `_guard` 写进 `reasons`，
    这样 journal 里永远能回答"这代为什么没加交叉"。
    """
    cur = cur or {}
    gen = int(diag.get('gen') or 0)
    s = dict(leaf_w=dict(cur.get('leaf_w', {})),
             op_bias=dict(cur.get('op_bias', {})),
             depth=list(cur.get('depth', [2, 3, 4])),
             mix=list(cur.get('mix', [0.25, 0.25, 0.15, 0.20, 0.15])),
             min_stab=cur.get('min_stab', 0.30),
             decorr=cur.get('decorr', 0.75),
             fsa_th=cur.get('fsa_th', 0.15),
             bank_skel_max=cur.get('bank_skel_max', 1))
    # ★ 这些键**必须原样带下去**（引擎会把 s 存进 state 的 cfg）—— 否则跨代就忘了:
    #   `_act` = 动作施加史 · `_veto` = LLM 否决史 · `_cool` = 冷却解禁代
    #   `_base` = ★ 施加前快照（§1.15 指标基线 + §1.1 参数旧值）· `_ineff` = ★ 判无效史
    #   `_cool_mul` = ★ 某动作的冷却倍率（判无效后翻倍，见 §1.15）
    s['_act'] = {k: list(v) for k, v in (cur.get('_act') or {}).items()}
    s['_veto'] = {k: list(v) for k, v in (cur.get('_veto') or {}).items()}
    s['_cool'] = dict(cur.get('_cool') or {})
    s['_base'] = {k: dict(v) for k, v in (cur.get('_base') or {}).items()}
    s['_ineff'] = {k: list(v) for k, v in (cur.get('_ineff') or {}).items()}
    s['_cool_mul'] = dict(cur.get('_cool_mul') or {})
    s['_sat_n'], s['_cool_n'] = SAT_N, COOL_N
    reasons = []
    tgt = gen + 1        # ★ 本策略服务的**目标代**：代首(gen=args.gen-1)/代末(gen=args.gen) 恒等 ✓
    act, veto, cool = s['_act'], s['_veto'], s['_cool']
    base, ineff, cmul = s['_base'], s['_ineff'], s['_cool_mul']
    n_blocked = [0]
    n_ineff = [0]

    # ---- ★ 当前动作上下文：让 `_set()` 自动把"改了哪些参数"归到**本动作**名下 ----
    #   为什么用上下文而不是让每个调用点手写旧值：
    #     同一代内**多个动作会改同一个参数**（`r2`/`r4` 都改 `min_stab`；`r5`/`r7` 都改 `depth`）
    #     旧值必须取"**本动作下手之前**"的值 —— 每个调用点手写极易写错，且新增动作时必然漏。
    _ctx = {'aid': None, 'pre': {}}

    def _set(p, v):
        """改一个参数（**唯一入口**）—— 自动登记"本动作名下该参数的首个旧值"。

        ⚠ 所有动作改 `s` 都必须走它，否则该改动**不会进入快照** ⇒ 将来无法回退（静默漏记）。
        """
        if _ctx['aid'] is not None:
            _ctx['pre'].setdefault(p, _get_param(s, p))
        _set_param(s, p, v)

    def _ineff_muted(aid):
        """是否已被"**实测无效**"永久停用（与 LLM 否决同级，但来源可辨）。"""
        v = ineff.get(aid) or []
        return MUTE in v

    def _settle(aid):
        """★★ §1.15：给**上一段施加**算账 —— 目标指标真的改善了吗？

        ## ⚠ 时机（2026-09-14 首版写错，被既有测试当场抓到）
        §1.15 原文是「**冷却解禁时**比对」—— 即必须等**一段真正闭合**（判过饱和并冷却过）
        才结算。首版写成"只要即将重新施加就结算" ⇒ **在第二次施加前就下结论**，
        而那时指标只过了 1 代，**样本太短**（而且会让"连续 SAT_N 代"这条路径根本走不到，
        破坏既有语义）✗
        ⇒ 现在用 `due` 标记：**只有 `_saturated` 分支才置 `due`**（= 一段结束、要结算了）✓

        :return: True=可以继续施加本代；False=**刚判无效并拦下本代**（同一动作刚被证伪，
                 本代不该再压一次）
        """
        b = base.get(aid) or {}
        mrec = b.get('metric')
        if not mrec or not b.get('due'):
            return True                     # 没有基线 / 一段还没闭合 ⇒ 不结算（不臆造）
        old_v, _g0, key = mrec[0], mrec[1], mrec[2]
        new_v, up, key2 = _metric_of(diag, aid)
        if new_v is None:
            _no_fire(reasons, aid, '有效性待评：本代取不到目标指标 `{}` ⇒ **不判定**（不臆造）'
                                   .format(key2 or key))
            return True
        verdict = _improved(old_v, new_v, up)
        if verdict is None:
            return True
        arrow = '↑' if up else '↓'
        if verdict:
            reasons.append('【{}】✅ 有效性复核：`{}` {} → {}（期望{}）⇒ **有效**，'
                           '继续施加'.format(aid, key2 or key, _fmtv(old_v), _fmtv(new_v), arrow))
            # 本段已结清 ⇒ 下段重新记基线（`due` 也要清，否则下段刚记基线就会被误结算）
            base[aid].pop('metric', None)
            base[aid].pop('due', None)
            return True
        # ---- 判无效 ----
        n_ineff[0] += 1
        hist = ineff.setdefault(aid, [])
        hist.append(tgt)
        n_times = len([g for g in hist if g is not MUTE])
        cmul[aid] = min(cmul.get(aid, 1) * INVALID_COOL_MULT, 64)
        cool[aid] = tgt + COOL_N * cmul[aid]
        msg = ('❌ 有效性判定：`{}` {} → {}（期望{}，需 >{:.2f}）⇒ **施加无效**'
               '（第 {} 次判定；冷却×{} ⇒ 到第 {} 代再评估）'.format(
                   key2 or key, _fmtv(old_v), _fmtv(new_v), arrow, METRIC_EPS,
                   n_times, cmul[aid], cool[aid]))
        base[aid].pop('metric', None)
        base[aid].pop('due', None)
        if n_times >= INEFF_MUTE_N:
            hist.append(MUTE)
            _rollback(s, aid, base, reasons, '实测无效 {} 次'.format(n_times))
            msg += ' ⇒ 累计 {} 次判无效 -> **永久停用**（等同被证伪）'.format(n_times)
        reasons.append('【{}】{}'.format(aid, msg))
        n_blocked[0] += 1
        return False

    def _rollback(s_, aid, base_, reasons_, why, quiet=False):
        """★ §1.1「参数棘轮」：某动作被**永久停用**时，**保守回退**它改过的参数。

        只回退「本动作确实改过、且**之后没人再动过**」的参数（见 `_rollback_plan` 的说明）。
        全程写进 `reasons_` ⇒ journal 里可复核、可人工恢复 ✓

        ## ★★ 为什么要能**重试**（`quiet=True`）—— 2026-09-14 实测发现的顺序问题
        多个动作会改同一参数，而"永久停用"是**逐个动作触发**的（`_guard` 里的检查顺序固定）。
        实测：`r5`/`r7` **都改 `depth`**，且**都判无效** ⇒ 应当**两个都撤、回到最初值**；
        但 `r5` 先被处理时，`depth` 还是 `r7` 写的值 ⇒ 判据不匹配 ⇒ **跳过** ✗
        等 `r7` 撤完（`depth` 回到 `r5` 写的值）时，`r5` 已经不再检查 ⇒ **停在半路** ✗
        ⇒ 修法：**被永久停用的动作每次被拦时都重试一次回退**（`_rollback_plan` 会自然收敛：
          跳过时**保留** `params` 记录）。**不需要给动作排序**，多试几次就一致了 ✓
        ⇒ 而 `quiet=True` 让"重试但没进展"不留痕（否则每代刷屏）。
        """
        done, skip = _rollback_plan(s_, aid, (base_.get(aid) or {}).get('params'))
        if done or (skip and not quiet):
            reasons_.append('【{}】↩ 参数棘轮（因{}）：恢复 {}；跳过 {}'.format(
                aid, why,
                ', '.join('{}={}'.format(p, _fmtv(v)) for p, v in done) or '（无）',
                ', '.join('{}（{}）'.format(p, r) for p, r in skip) or '（无）'))
        # ★★ 只清理**已成功恢复**的记录，**保留跳过的** —— 否则重试机制失效 ✗
        #   （2026-09-14 实录：初版写 `if done: pop('params')`，把跳过的 `depth` 记录一起丢了
        #    ⇒ 下次 `_guard` 重试时 `params` 为空 ⇒ **永远停在半路** ✗）
        pr = (base_.get(aid) or {}).get('params')
        if pr:
            for p, _v in done:
                pr.pop(p, None)
            if not pr:
                (base_.get(aid) or {}).pop('params', None)

    def _begin(aid):
        """`_guard` 通过 ⇒ 进入"本动作"上下文（之后的 `_set` 都归到它名下）。"""
        _ctx['aid'], _ctx['pre'] = aid, {}

    def _guard(aid):
        """动作闸门。返回 True=可施加；False=已拦下并**写明原因**（绝不静默）。"""
        if _muted(veto, aid):
            _no_fire(reasons, aid, 'LLM 已【永久】否决，后续各代一律不再施加')
            n_blocked[0] += 1
            return False
        if _ineff_muted(aid):
            # ★★ 补做未完成的回退（见 `_rollback` 的"为什么要能重试"）：
            #   多个动作改同一参数且都判无效时，先处理的那个会因"当前值还是后处理者写的"而跳过；
            #   等后处理者撤完，这里再试一次就能撤到最初值 ⇒ **自然收敛，无需排序** ✓
            if (base.get(aid) or {}).get('params'):
                _rollback(s, aid, base, reasons, '实测无效（补做未完成的回退）', quiet=True)
            _no_fire(reasons, aid, '已被【实测无效】永久停用（连续 {} 次判无效），'
                                   '后续各代一律不再施加'.format(INEFF_MUTE_N))
            n_blocked[0] += 1
            return False
        _vg = [g for g in (veto.get(aid) or []) if g is not MUTE]
        if tgt in _vg:
            if len(_vg) >= LLM_MUTE_N:
                veto.setdefault(aid, []).append(MUTE)
                _rollback(s, aid, base, reasons, 'LLM 连续否决 {} 次 -> 永久停用'.format(len(_vg)))
                _no_fire(reasons, aid, 'LLM 连续否决 {} 次 -> 升级为【永久】停用'.format(len(_vg)))
            else:
                _no_fire(reasons, aid, 'LLM 本代明确否决（第 {} 次）'.format(len(_vg)))
            n_blocked[0] += 1
            return False
        if _cooling(cool, aid, tgt):
            _no_fire(reasons, aid, '饱和冷却中（第 {} 代自动解禁）'.format(cool.get(aid)))
            n_blocked[0] += 1
            return False
        if _saturated(act, aid, tgt):
            cool[aid] = tgt + COOL_N * cmul.get(aid, 1)
            # ★ §1.15：一段到此**闭合** ⇒ 标记 `due`，等解禁后重触发时**结算有效性** ✓
            base.setdefault(aid, {})['due'] = True
            _no_fire(reasons, aid, '已连续 {} 代施加 -> 判为饱和（条件恒真=固定偏移），'
                                   '冷却到第 {} 代再评估'.format(SAT_N, cool[aid]))
            n_blocked[0] += 1
            return False
        # ★★ §1.15：即将重新施加 ⇒ 先给上一段算账（可能刚判无效、把本代也拦下）
        if not _settle(aid):
            return False
        _begin(aid)
        return True

    def _mark(aid, txt):
        """登记施加 + 留痕（ID 前缀便于在 journal 里 grep 审计）+ **写施加前快照**。

        快照两用：§1.15 用 `metric` 判有效性；§1.1 用 `params` 做棘轮回退。
        """
        _fired(act, aid, tgt)
        b = base.setdefault(aid, {})
        # ---- §1.15 指标基线：**只在本段第一次施加时记**（同一段重复施加不覆盖）----
        m, up, key = _metric_of(diag, aid)
        if m is not None and 'metric' not in b:
            b['metric'] = [m, tgt, key]
        # ---- §1.1 参数旧值：本动作名下、该参数的**首个**旧值 ----
        if _ctx['pre']:
            pr = b.setdefault('params', {})
            for p, oldv in _ctx['pre'].items():
                if p not in pr:
                    pr[p] = [oldv, _get_param(s, p)]
                else:
                    pr[p][1] = _get_param(s, p)      # 同段内又改同参数 -> 更新「最后写入」
        reasons.append('【{}】{}'.format(aid, txt))

    # 1) 叶子过度集中 -> 压低该叶子
    if diag.get('leaf_conc', 0) > 0.40 and _guard('r1_leaf_conc'):
        top = diag['leaf_top'][0]
        _set('leaf_w.' + top, 0.25)
        _mark('r1_leaf_conc', f"叶子[{top}]占比{diag['leaf_conc']:.0%}过高 -> 权重压到0.25, 逼引擎换字段")
    # 2) 稳定性差 -> 抬高门槛 + 偏好长周期算子
    if (diag.get('stab_med', 1) < 0.60 or diag.get('stab_lt50', 0) > 0.40) and _guard('r2_stab_low'):
        _set('min_stab', min(0.60, s['min_stab'] + 0.15))
        for o in SLOW_OPS:
            _set('op_bias.' + o, 1.8)
        for o in FAST_OPS:
            _set('op_bias.' + o, 0.4)
        _mark('r2_stab_low', f"稳定性中位{diag.get('stab_med',0):.2f}(低) -> min_stab提到{s['min_stab']:.2f}, "
                             f"偏好长周期算子")
    # 3) 结构多样性低 -> 加强探索(随机槽固定15%走数据驱动加权, 故提变异逼换新信号源)
    if diag.get('struct_div', 1) < 0.35 and _guard('r3_struct_div'):
        m = s['mix']
        _set('mix', [min(0.40, m[0] + 0.10), max(0.10, m[1] - 0.10), m[2], m[3], m[4]])
        _mark('r3_struct_div', f"结构多样性{diag.get('struct_div',0):.2f}(同质化) -> "
                               f"变异预算提至{s['mix'][0]:.0%}逼探索新信号源")
    # 4) L2 主要因换手失败 -> 再抬稳定性
    if diag.get('fail_turn', 0) > 0.40 and _guard('r4_fail_turn'):
        _set('min_stab', min(0.75, s['min_stab'] + 0.10))
        _mark('r4_fail_turn', f"L2中{diag['fail_turn']:.0%}因换手过高失败 -> min_stab再+0.10")
    # 5) L2 主要因 Calmar 不足 -> 加强交叉(把已有信号组合起来) / 深度加深
    #    ★ (C) **判据选"真正卡住的那道门"**：池内模式下池口径才是真实卡点。
    #      为什么不能只看全A：pool=1000 实测「全A 门槛已放开（--min_calmar=0）却仍报 100%」，
    #      而真正决定成败的是「任一池 Calmar > --min_pool_calmar」这道池门槛。
    #    ★ 另给一个**不随配置漂移**的锚 `fail_calmar_neg`（真·信号弱），用于人工对照。
    _sig, _sig_src = None, ''
    if diag.get('fail_pool_calmar') is not None:
        _sig = float(diag['fail_pool_calmar'])
        _sig_src = '池口径: {}池 Calmar > {:g}'.format(
            '任一' if diag.get('gate_pool_mode', 'any') == 'any' else '全部',
            float(diag.get('gate_min_pool_calmar', 0)))
    elif diag.get('fail_calmar') is not None:
        _sig = float(diag['fail_calmar'])
        _sig_src = '全A 口径: Calmar <= {:g}'.format(float(diag.get('gate_min_calmar', 0.5)))
    if _sig is not None and _sig > 0.55 and diag.get('n_l2', 0) >= 8 and _guard('r5_calmar_cross'):
        m = s['mix']
        _set('mix', [m[0] * 0.85, min(0.45, m[1] + 0.15), m[2], m[3], m[4]])
        _set('depth', [3, 4, 4])
        _mark('r5_calmar_cross', f"L2中{_sig:.0%}因Calmar不足[{_sig_src}] -> 交叉+15%, 深度加深")
    # 6) 又绕回已知族 -> 收紧去相关阈值(对象=人工基准+历代入库bank, 对齐中金"入库IC<0.70")
    #    ⚠ 原实现 known_ratio 高时放宽到0.85是反的: 已知族候选占满L1却无法入库,
    #    应把更像已知者的拦在L2外, 逼搜索离开已知族; 放宽只会放更多同族进L2.
    if diag.get('known_ratio', 0) > 0.60 and _guard('r6_known_ratio'):
        floor = 0.65 if diag.get('n_pass', 0) == 0 else 0.70
        if s['decorr'] > floor:
            _set('decorr', max(floor, s['decorr'] - 0.05))
            _mark('r6_known_ratio', f"{diag['known_ratio']:.0%}候选仍含已知族字段 -> decorr收紧到"
                                    f"{s['decorr']:.2f}(0.70≈中金入库IC相关口径)")
        else:
            _mark('r6_known_ratio', f"{diag['known_ratio']:.0%}候选仍含已知族字段，"
                                    f"但 decorr={s['decorr']:.2f} 已达 floor={floor:.2f} -> 不重复收紧")
    # 7) 连续无产出 -> 换方向: 提高深度 + 提高随机
    if diag.get('n_pass', 0) == 0 and diag.get('n_l2', 0) >= 10 and _guard('r7_zero_pass'):
        _set('depth', [3, 4, 5])
        _mark('r7_zero_pass', "本代0通过 -> 深度放宽到3~5, 探索更复杂结构")
    if not reasons:
        reasons.append("各项指标正常, 维持当前策略")
    # ★ 审计小结：让 journal 一眼看出"这代被拦下了几条动作"（否则静默=未来的排查噩梦）
    if n_blocked[0]:
        reasons.append("—— 本代共拦截 {} 条动作（饱和/LLM 否决），详见上面【拦截】行".format(n_blocked[0]))
    # 出口统一护栏: 规则(含从旧state继承的cfg)算出任何 mix 都强制回到中金规格内,
    # 且修正前后不一致时留痕, 便于在 journal 里追踪护栏生效
    mix_raw = list(s['mix'])
    s['mix'] = guard_mix(s['mix'])
    if any(abs(x - y) > 1e-9 for x, y in zip(s['mix'], mix_raw)):
        reasons.append(f"配比护栏: 变异/交叉各≥{MIX_MIN:.0%}且合计50%重归一化, "
                       f"扰动/引导/随机固定15/20/15(中金规格) -> "
                       f"mix={[round(x, 3) for x in s['mix']]}")
        # ★★ 必须**同步快照里的「新值」**（2026-09-14）：`guard_mix` 在动作之后改了 `mix`，
        #   而 §1.1 的回退判据是「**当前值 == 本动作写入的值**」⇒ 不同步的话
        #   `mix` 永远匹配不上 ⇒ **回退被静默跳过**（棘轮对 mix 失效）✗
        for _aid, _b in base.items():
            _pm = (_b.get('params') or {}).get('mix')
            if _pm and list(_pm[1]) != list(s['mix']):
                _pm[1] = list(s['mix'])
    return s, reasons


def report(diag, sug, reasons, path):
    """诊断报告 markdown, 追加写入"""
    lines = []
    lines.append(f"\n## 第 {diag['gen']} 代 (B角诊断)\n")
    # 指标横排 md 表格(键行/分隔/值行): 源码3行, 渲染为横向对齐表格
    # ★ 2026-09-14 新增（§1.1 修法①）：诊断的门槛**与被判的量并列展示**，以便一眼对账。
    #   `gate_min_calmar` = 诊断实际用的全A calmar 门槛（应等于 --min_calmar）
    #   `gate_min_pool_calmar` = 池门槛（池内模式下的真实卡点）
    #   `fail_calmar_neg` = 真·信号弱（calmar<=0，**不随配置漂移**的锚）
    #   `fail_pool_calmar` = 池口径失败率（缺池数据时不产出 -> present 过滤掉）
    keys = ['n_l1', 'ic_med', 'ic_max', 'stab_med', 'stab_lt50',
            'leaf_conc', 'struct_div', 'fam_blocked', 'known_ratio',
            'n_l2', 'n_pass', 'ex_max',
            'gate_min_calmar', 'gate_min_pool_calmar',
            'fail_calmar', 'fail_calmar_neg', 'fail_pool_calmar',
            'fail_turn', 'fail_negyear', 'fail_lastyr', 'fail_ic',
            'seg_kill',
            # 风格暴露观测(--style_obs, 2026-09-11): 各组 |截面秩相关| 中位。
            # st_l2_=进L2组 / st_l1_=L1通过组; 入库组(st_ok_)样本过小, 只进 CSV 不进表。
            # 未开启观测时这些键不在 diag 里 -> present 过滤掉, 表头不受影响。
            'st_l2_lncap', 'st_l2_lnamt', 'st_l2_lntr', 'st_l2_lnpx',
            'st_l1_lncap', 'st_l1_lnamt', 'st_l1_lntr', 'st_l1_lnpx']
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
    # ★ 动作留痕（2026-09-14, §1.1 修法③④）：把"施加过什么 / 哪条被永久闭嘴"落到 journal，
    #   否则这些机制只活在内存里，人无法复核、更无法推翻（违反本文件"规则透明可解释"的设计原则）。
    _act = sug.get('_act') or {}
    _veto = sug.get('_veto') or {}
    _muted_aids = [a for a, gs in _veto.items() if MUTE in (gs or [])]
    if _act or _muted_aids:
        lines.append("\n**规则动作留痕**:")
        for aid, gs in sorted(_act.items()):
            gg = [g for g in gs if g is not None]
            mark = '（**已永久关闭**）' if aid in _muted_aids else ''
            lines.append(f"- `{aid}` {RULE_NAMES.get(aid,'?')} —— 施加于第 {gg} 代{mark}")
        if _muted_aids:
            lines.append(f"- ⛔ **被 LLM 永久否决的动作**（用户要求「让它永久闭嘴」）："
                         f"{', '.join('`%s`' % x for x in _muted_aids)}")
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
# ★模型名不再本地硬编码(2026-09-12): 本文件曾有一份 'deepseek-v4-flash' 副本 —— 官方改名
#  (-> `deepseek-flash`)后两处必然漂移。统一从 loop_llm 取(单一事实源, 与 loop_fields.py 同理)。
#  loop_llm 只 import os/json/time, 无循环依赖, 模块级导入安全。
from loop_llm import DEFAULT_MODEL as _DEEPSEEK_MODEL       # noqa: E402


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


def parse_veto(resp):
    """从 LLM 回复里解析**机器可读的否决行**（2026-09-14, `docs/loop_todo.md` §1.1 修法④）。

    约定（已写进 system prompt）：**最后一行**形如
        `否决: r5_calmar_cross`   /   `否决: r5_calmar_cross,r7_zero_pass`   /   `否决: 无`

    为什么需要这一行：此前 LLM 只能写散文（"深度加深有害"），而**散文无法回写 `sug`**
    ⇒ 85/98 次独立反驳全部被浪费。有了结构化出口，LLM 才真正有**否决权**。

    **容错优先**（铁律）：解析失败 / 未知 ID / 空 ⇒ 返回 `[]`，**不否决任何东西**。
    ⚠ 宁可"少拦一条"，绝不可"因解析错而乱拦" —— LLM 侧任何问题都不得影响主流程。
    """
    import re
    if not resp:
        return []
    # 取**最后**一处"否决:"（LLM 可能先解释再给结论；以最后一次表态为准）
    ms = re.findall(r'否决\s*[:：]\s*([^\n]*)', resp)
    if not ms:
        return []
    raw = ms[-1].strip()
    if raw in ('无', 'none', 'None', '-', ''):
        return []
    out = []
    for tok in re.split(r'[,，、;；\s]+', raw):
        tok = tok.strip().strip('`*[]()"\'')
        if tok in RULE_NAMES and tok not in out:
            out.append(tok)
    return out


def ai_review(diag, l1, l2, gen, journal_path, reasons=None, sug=None, force=False):
    """B角 LLM 审查: 调 DeepSeek 对第 gen 代诊断做体检并点评规则建议, 全文追加进 journal。

    返回 **dict**（2026-09-14 起；旧版返回裸字符串 `'ok'`，引擎已同步改用 `.get()`）：
        `{'status': 'ok'|'no_key'|'err', 'veto': [规则动作ID, ...], 'text': LLM原文或''}`

    ★ 为什么返回值从"字符串"升级为"带 `veto` 的 dict"：这是**修法④**的核心 ——
      此前 `ai_review()` 的返回值**只用于打印、从不回写 `sug`** ⇒ LLM 的独立判断被完全浪费。
      现在把 `veto` 交回引擎，引擎写进 `next_cfg['_veto']` ⇒ 下一代 `suggest()` 会**真的跳过**
      被否决的动作（连续否决 `LLM_MUTE_N` 次则**永久闭嘴**）。

    ⚠ 铁律不变：任何失败（无 key / 网络 / 解析）都只是**跳过**，绝不影响主流程。
    """
    if not _deepseek_key():
        print("[AI审查] 未找到 DeepSeek key(环境变量 DEEPSEEK_API_KEY 或桌面 1.txt), "
              "本代跳过 -> 沿用规则B角")
        return {'status': 'no_key', 'veto': [], 'text': ''}
    keys = ['n_l1', 'ic_med', 'ic_max', 'stab_med', 'stab_lt50', 'leaf_conc',
            'struct_div', 'fam_blocked', 'known_ratio', 'n_l2', 'n_pass', 'ex_max',
            'fail_calmar', 'fail_turn', 'fail_negyear', 'fail_lastyr', 'fail_ic',
            'seg_kill']
    stat = ', '.join(f"{k}={diag.get(k):.3f}" if isinstance(diag.get(k), float)
                     else f"{k}={diag.get(k)}" for k in keys if k in diag)
    leaf_hist = diag.get('leaf_hist')
    rule_txt = '; '.join(reasons) if reasons else '(无)'
    sug_txt = (f"mix={sug['mix']} depth={sug['depth']} min_stab={sug.get('min_stab')} "
               f"decorr={sug.get('decorr')} fsa_th={sug.get('fsa_th')} "
               f"bank_skel_max={sug.get('bank_skel_max')}") if sug else '(无)'
    # ★ 给 LLM「可引用的动作名」——**没有 ID 它就无法否决**（这是修法④的前提）。
    #   只列**本代真正施加过**的动作（没施加的动作谈不上"反对"），并标出**哪些已被永久关掉**，
    #   否则 LLM 会年复一年地否决同一件事（实测它在 85/98 代上重复同一判断）。
    _act = (sug or {}).get('_act') or {}
    _veto_h = (sug or {}).get('_veto') or {}
    _applied = [a for a in _act if a in RULE_NAMES and MUTE not in (_veto_h.get(a) or [])]
    _muted_now = [a for a, gs in _veto_h.items() if MUTE in (gs or [])]
    act_txt = '; '.join('`{}`={}'.format(a, RULE_NAMES[a]) for a in _applied) or '(本代未施加任何规则动作)'
    mute_txt = ('已永久关闭: ' + ', '.join('`%s`' % a for a in _muted_now)) if _muted_now else ''
    user_txt = (
        f"第 {gen} 代诊断统计:\n{stat}\n"
        f"叶子使用: {leaf_hist}\n\n"
        f"L1 头部候选(按ic降序):\n{_fmt_l1(l1)}\n\n"
        f"L2 样本:\n{_fmt_l2(l2)}\n\n"
        f"规则B角建议(引擎将按此执行):\n- {rule_txt}\n"
        f"下代表格: {sug_txt}\n\n"
        f"本代**实际施加**的规则动作(可被否决):\n{act_txt}\n"
        f"{mute_txt}\n")
    sys_txt = (
        "你是资深A股量价因子研究员, 在中金 Loop Engineering 双Agent框架里扮演 B角(审查者/启发者)。"
        "输入是一轮因子挖掘迭代的诊断统计与规则B角建议。请做四件事:\n"
        "(1) 用一句话点出本轮最核心的病根;\n"
        "(2) 逐条点评规则B角建议是否对症, 指出可能无效或互相冲突的点;\n"
        "(3) 给出你自己对下代 mix(变异/交叉/扰动/引导/随机)/depth/min_stab/decorr 的取值与一句话理由;\n"
        "(4) **否决**: 上面「本代实际施加的规则动作」里, 你认为**下代应当停掉**的, 用反引号里的 ID 列出。\n"
        "硬性要求: 中文, 正文≤260字, 用(1)(2)(3)分条, 禁止markdown表格/管道符;\n"
        "**最后一行必须且只能是** `否决: <ID列表或 无>`（ID 之间用英文逗号分隔, 例 `否决: r5_calmar_cross`；"
        "若认为都该保留则写 `否决: 无`）。这一行是**机器读取**的, 请勿改写格式。")
    import time
    try:
        t0 = time.time()
        resp = _chat_once([{'role': 'system', 'content': sys_txt},
                           {'role': 'user', 'content': user_txt}],
                          tag='B角代末审查(ai_review)')
        cost = time.time() - t0
    except Exception as e:
        print(f"[AI审查] DeepSeek 调用失败({type(e).__name__}: {e}) -> 跳过, 沿用规则B角")
        return {'status': 'err', 'veto': [], 'text': ''}
    veto = parse_veto(resp)
    block = (f"\n**AI 审查(DeepSeek {_DEEPSEEK_MODEL}, {cost:.0f}s)**:\n\n"
             + '\n'.join('> ' + x for x in resp.splitlines()) + '\n')
    if veto:
        # ★ 否决必须**显式留痕**：这是"规则负责稳定、LLM 负责纠偏"的可审计接口
        block += ("\n**⚖️ 规则动作否决（机器读取）**: " +
                  ', '.join('`%s`（%s）' % (a, RULE_NAMES.get(a, '?')) for a in veto) + '\n')
    os.makedirs(os.path.dirname(journal_path), exist_ok=True)
    with open(journal_path, 'a', encoding='utf-8') as f:
        f.write(block)
    preview = resp.replace('\n', ' ')[:220]
    print(f"[AI审查] DeepSeek 审查完成({cost:.0f}s), 已写入 {journal_path}")
    if veto:
        print(f"  [否决] 下代将跳过: {', '.join(veto)}")
    print(f"  {preview}...")
    return {'status': 'ok', 'veto': veto, 'text': resp}
