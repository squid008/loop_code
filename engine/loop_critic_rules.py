# -*- coding: utf-8 -*-
"""loop_critic_rules.py — B角 `suggest()` 的**规则状态机**（2026-09-28 拆出 · `docs/loop_todo.md §1.37`）
================================================================================================
`loop_critic.py` 的 `suggest()` 曾 **207 行**、文件 **998 行** ⇒ 双双超 `docs/maintainability.md`
的 R1（函数 ≤120）/ R2（文件 ≤800）✗。本模块把其中**有状态的那一块**整块搬出来 ✓。

## ★ 关键判断：**不做机械抽块**（这条是机器算出来的，别再试 ✗）

`tools/_extract_block.py loop_critic.py suggest 581 752 <名>` 用 **AST** 算出：那 7 个嵌套 `def`
「**块里读了、块外才有**」的名字是 **13 个** ——
`_ctx · act · base · cmul · cool · diag · ineff · n_blocked · n_ineff · reasons · s · tgt · veto`，
而「块里赋值、块外还读」的**只有 `n_blocked`**。

⇒ 机械抽成独立函数 ⇒ 每个子函数都得背 **13 个形参** ✗✗ —— 那正是 `maintainability.md` §七
   警告的「**上帝函数换成上帝参数表**」✗（`_run_l2_phase` 试抽 `_l2_judge` 时已因此回退过一次 ✓）。
⇒ 改用**方法**（`self.xxx` 取状态）⇒ **形参 0 个** ✓；`n_blocked` / `n_ineff` 留在对象上
   **就地自增** ⇒ **连回传都不需要** ✓✓
   （原实现写 `n_blocked = [0]` 这个单元素列表，只是因为闭包**改不动**外层变量 ✗ ——
     对象化后 `self.n_blocked += 1` 直写即可 ⇒ 这个变通顺手拆掉 ✓）。

## 依赖方向（★ 单向：`loop_critic` → 本模块）

本模块要用 `loop_critic` 的常量与纯函数（`MUTE`/`SAT_N`/`COOL_N`/… + `_get_param`/`_set_param`/
`_metric_of`/`_improved`/`_rollback_plan`/`_no_fire`/`_fired`/`_saturated`/`_cooling`/`_muted`/`_fmtv`）
⇒ 顶部 `from loop_critic import …`；而 `loop_critic` **只在函数内** import 本模块
（`suggest` / `report` / `ai_review`）⇒ 到那一刻 `loop_critic` 已完全初始化 ⇒ **不成环** ✓
（同一条理由见 `loop_critic._op_names` 里"惰性 import `loop_engine`"的注释 ✓）。
★ 反过来说：**不许把 `import loop_critic_rules` 提到 `loop_critic` 的模块级** ✗（那才会成环 ✓）。

## 内容

· `_SugState` —— 那 13 个共享状态的宿主：`__init__`（原 `_init_sug`）+ **7 个方法**
  `_set` · `_ineff_muted` · `_begin` · `_mark` · `_rollback` · `_guard` · `_settle`
  —— 正文**逐字搬运** ✓，只把 `s`/`base`/`reasons`/`act`/… 改成 `self.xxx`（形参 0 个 ✓）
· `_fmt` / `_fmt_l1` / `_fmt_l2` —— **纯格式化**（零状态 ✓；journal 表格 与 AI 审查提示 共用）
  ⇒ 一并搬来，同时把 `loop_critic.py` 稳在 R2 线（≤800 行）以内 ✓
"""
from loop_critic import (
    # ---- 常量：§1.1 动作登记/饱和检测 · §1.15 有效性判定 ----
    MUTE, SAT_N, COOL_N, LLM_MUTE_N, INEFF_MUTE_N, INVALID_COOL_MULT, METRIC_EPS,
    # ---- 纯函数：一律**复用 `loop_critic` 的单一实现**（R5 不许复制一份 ✗）----
    _get_param, _set_param, _fmtv, _metric_of, _improved, _rollback_plan,
    _no_fire, _fired, _saturated, _cooling, _muted,
)


class _SugState:
    """`suggest()` 的状态机：13 个共享名 + 7 个方法（原来都是 `suggest()` 里的闭包 ✓）。

    ★ 为什么是一个**普通类**而不是 dataclass：这里全是**可变**的跨代记忆
      （`_act`/`_veto`/`_cool`/`_base`/`_ineff`/`_cool_mul` 会被逐代改写 ✓），
      没有"只读口径"那一半 ⇒ 不必造 frozen 对象（与 `loop_l2._L2In/_L2Acc` 的分工不同 ✓）。
    """

    def __init__(self, diag, cur):
        """初始化策略状态 + 动作历史 + 审计理由（= 原 `loop_critic._init_sug` 的**逐字搬运** ✓）。"""
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
        # ---- 13 个共享名（AST 机器算出的清单）挂到对象上 ⇒ 7 个方法**形参 0 个** ✓ ----
        self.diag = diag
        self.s = s
        self.reasons = []
        self.tgt = gen + 1     # ★ 本策略服务的**目标代**：代首(gen=args.gen-1)/代末(gen=args.gen) 恒等 ✓
        self.act = s['_act']
        self.veto = s['_veto']
        self.cool = s['_cool']
        self.base = s['_base']
        self.ineff = s['_ineff']
        self.cmul = s['_cool_mul']
        # ★★ 计数用**普通属性**（不再是 `[0]` 单元素列表）：原写法只是"闭包改得动外层变量"的
        #    变通 ✗ ⇒ `self.n_blocked += 1` 直写即可，**连回传都不需要** ✓✓（见模块头注 ✓）
        self.n_blocked = 0
        self.n_ineff = 0
        # ---- ★ 当前动作上下文：让 `_set()` 自动把"改了哪些参数"归到**本动作**名下 ----
        #   为什么用上下文而不是让每个调用点手写旧值：
        #     同一代内**多个动作会改同一个参数**（`r2`/`r4` 都改 `min_stab`；`r5`/`r7` 都改 `depth`）
        #     旧值必须取"**本动作下手之前**"的值 —— 每个调用点手写极易写错，且新增动作时必然漏。
        self._ctx = {'aid': None, 'pre': {}}

    def _set(self, p, v):
        """改一个参数（**唯一入口**）—— 自动登记"本动作名下该参数的首个旧值"。

        ⚠ 所有动作改 `s` 都必须走它，否则该改动**不会进入快照** ⇒ 将来无法回退（静默漏记）。
        """
        if self._ctx['aid'] is not None:
            self._ctx['pre'].setdefault(p, _get_param(self.s, p))
        _set_param(self.s, p, v)

    def _ineff_muted(self, aid):
        """是否已被"**实测无效**"永久停用（与 LLM 否决同级，但来源可辨）。"""
        v = self.ineff.get(aid) or []
        return MUTE in v

    def _settle(self, aid):
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
        b = self.base.get(aid) or {}
        mrec = b.get('metric')
        if not mrec or not b.get('due'):
            return True                     # 没有基线 / 一段还没闭合 ⇒ 不结算（不臆造）
        old_v, _g0, key = mrec[0], mrec[1], mrec[2]
        new_v, up, key2 = _metric_of(self.diag, aid)
        if new_v is None:
            _no_fire(self.reasons, aid, '有效性待评：本代取不到目标指标 `{}` ⇒ **不判定**（不臆造）'
                                        .format(key2 or key))
            return True
        verdict = _improved(old_v, new_v, up)
        if verdict is None:
            return True
        arrow = '↑' if up else '↓'
        if verdict:
            self.reasons.append('【{}】✅ 有效性复核：`{}` {} → {}（期望{}）⇒ **有效**，'
                                '继续施加'.format(aid, key2 or key, _fmtv(old_v), _fmtv(new_v), arrow))
            # 本段已结清 ⇒ 下段重新记基线（`due` 也要清，否则下段刚记基线就会被误结算）
            self.base[aid].pop('metric', None)
            self.base[aid].pop('due', None)
            return True
        # ---- 判无效 ----
        self.n_ineff += 1
        hist = self.ineff.setdefault(aid, [])
        hist.append(self.tgt)
        n_times = len([g for g in hist if g is not MUTE])
        self.cmul[aid] = min(self.cmul.get(aid, 1) * INVALID_COOL_MULT, 64)
        self.cool[aid] = self.tgt + COOL_N * self.cmul[aid]
        msg = ('❌ 有效性判定：`{}` {} → {}（期望{}，需 >{:.2f}）⇒ **施加无效**'
               '（第 {} 次判定；冷却×{} ⇒ 到第 {} 代再评估）'.format(
                   key2 or key, _fmtv(old_v), _fmtv(new_v), arrow, METRIC_EPS,
                   n_times, self.cmul[aid], self.cool[aid]))
        self.base[aid].pop('metric', None)
        self.base[aid].pop('due', None)
        if n_times >= INEFF_MUTE_N:
            hist.append(MUTE)
            self._rollback(aid, '实测无效 {} 次'.format(n_times))
            msg += ' ⇒ 累计 {} 次判无效 -> **永久停用**（等同被证伪）'.format(n_times)
        self.reasons.append('【{}】{}'.format(aid, msg))
        self.n_blocked += 1
        return False

    def _rollback(self, aid, why, quiet=False):
        """★ §1.1「参数棘轮」：某动作被**永久停用**时，**保守回退**它改过的参数。

        只回退「本动作确实改过、且**之后没人再动过**」的参数（见 `_rollback_plan` 的说明）。
        全程写进 `self.reasons` ⇒ journal 里可复核、可人工恢复 ✓

        ## ★★ 为什么要能**重试**（`quiet=True`）—— 2026-09-14 实测发现的顺序问题
        多个动作会改同一参数，而"永久停用"是**逐个动作触发**的（`_guard` 里的检查顺序固定）。
        实测：`r5`/`r7` **都改 `depth`**，且**都判无效** ⇒ 应当**两个都撤、回到最初值**；
        但 `r5` 先被处理时，`depth` 还是 `r7` 写的值 ⇒ 判据不匹配 ⇒ **跳过** ✗
        等 `r7` 撤完（`depth` 回到 `r5` 写的值）时，`r5` 已经不再检查 ⇒ **停在半路** ✗
        ⇒ 修法：**被永久停用的动作每次被拦时都重试一次回退**（`_rollback_plan` 会自然收敛：
          跳过时**保留** `params` 记录）。**不需要给动作排序**，多试几次就一致了 ✓
        ⇒ 而 `quiet=True` 让"重试但没进展"不留痕（否则每代刷屏）。
        """
        done, skip = _rollback_plan(self.s, aid, (self.base.get(aid) or {}).get('params'))
        if done or (skip and not quiet):
            self.reasons.append('【{}】↩ 参数棘轮（因{}）：恢复 {}；跳过 {}'.format(
                aid, why,
                # ⚠ `None` 不是"恢复成 None"，而是"**删掉这个键**"（施加前它不存在）——
                #   日志必须写清，否则看 journal 的人会以为真值就是 None ✗（2026-09-17 厘清）
                ', '.join('{}={}'.format(p, _fmtv(v)) if v is not None
                          else '{}（删除该键：施加前它不存在）'.format(p)
                          for p, v in done) or '（无）',
                ', '.join('{}（{}）'.format(p, r) for p, r in skip) or '（无）'))
        # ★★ 只清理**已成功恢复**的记录，**保留跳过的** —— 否则重试机制失效 ✗
        #   （2026-09-14 实录：初版写 `if done: pop('params')`，把跳过的 `depth` 记录一起丢了
        #    ⇒ 下次 `_guard` 重试时 `params` 为空 ⇒ **永远停在半路** ✗）
        pr = (self.base.get(aid) or {}).get('params')
        if pr:
            for p, _v in done:
                pr.pop(p, None)
            if not pr:
                (self.base.get(aid) or {}).pop('params', None)

    def _begin(self, aid):
        """`_guard` 通过 ⇒ 进入"本动作"上下文（之后的 `_set` 都归到它名下）。"""
        self._ctx['aid'], self._ctx['pre'] = aid, {}

    def _guard(self, aid):
        """动作闸门。返回 True=可施加；False=已拦下并**写明原因**（绝不静默）。"""
        if _muted(self.veto, aid):
            _no_fire(self.reasons, aid, 'LLM 已【永久】否决，后续各代一律不再施加')
            self.n_blocked += 1
            return False
        if self._ineff_muted(aid):
            # ★★ 补做未完成的回退（见 `_rollback` 的"为什么要能重试"）：
            #   多个动作改同一参数且都判无效时，先处理的那个会因"当前值还是后处理者写的"而跳过；
            #   等后处理者撤完，这里再试一次就能撤到最初值 ⇒ **自然收敛，无需排序** ✓
            if (self.base.get(aid) or {}).get('params'):
                self._rollback(aid, '实测无效（补做未完成的回退）', quiet=True)
            _no_fire(self.reasons, aid, '已被【实测无效】永久停用（连续 {} 次判无效），'
                                        '后续各代一律不再施加'.format(INEFF_MUTE_N))
            self.n_blocked += 1
            return False
        _vg = [g for g in (self.veto.get(aid) or []) if g is not MUTE]
        if self.tgt in _vg:
            if len(_vg) >= LLM_MUTE_N:
                self.veto.setdefault(aid, []).append(MUTE)
                self._rollback(aid, 'LLM 连续否决 {} 次 -> 永久停用'.format(len(_vg)))
                _no_fire(self.reasons, aid, 'LLM 连续否决 {} 次 -> 升级为【永久】停用'.format(len(_vg)))
            else:
                _no_fire(self.reasons, aid, 'LLM 本代明确否决（第 {} 次）'.format(len(_vg)))
            self.n_blocked += 1
            return False
        if _cooling(self.cool, aid, self.tgt):
            _no_fire(self.reasons, aid, '饱和冷却中（第 {} 代自动解禁）'.format(self.cool.get(aid)))
            self.n_blocked += 1
            return False
        if _saturated(self.act, aid, self.tgt):
            self.cool[aid] = self.tgt + COOL_N * self.cmul.get(aid, 1)
            # ★ §1.15：一段到此**闭合** ⇒ 标记 `due`，等解禁后重触发时**结算有效性** ✓
            self.base.setdefault(aid, {})['due'] = True
            _no_fire(self.reasons, aid, '已连续 {} 代施加 -> 判为饱和（条件恒真=固定偏移），'
                                        '冷却到第 {} 代再评估'.format(SAT_N, self.cool[aid]))
            self.n_blocked += 1
            return False
        # ★★ §1.15：即将重新施加 ⇒ 先给上一段算账（可能刚判无效、把本代也拦下）
        if not self._settle(aid):
            return False
        self._begin(aid)
        return True

    def _mark(self, aid, txt):
        """登记施加 + 留痕（ID 前缀便于在 journal 里 grep 审计）+ **写施加前快照**。

        快照两用：§1.15 用 `metric` 判有效性；§1.1 用 `params` 做棘轮回退。
        """
        _fired(self.act, aid, self.tgt)
        b = self.base.setdefault(aid, {})
        # ---- §1.15 指标基线：**只在本段第一次施加时记**（同一段重复施加不覆盖）----
        m, up, key = _metric_of(self.diag, aid)
        if m is not None and 'metric' not in b:
            b['metric'] = [m, self.tgt, key]
        # ---- §1.1 参数旧值：本动作名下、该参数的**首个**旧值 ----
        if self._ctx['pre']:
            pr = b.setdefault('params', {})
            for p, oldv in self._ctx['pre'].items():
                if p not in pr:
                    pr[p] = [oldv, _get_param(self.s, p)]
                else:
                    pr[p][1] = _get_param(self.s, p)      # 同段内又改同参数 -> 更新「最后写入」
        self.reasons.append('【{}】{}'.format(aid, txt))


def _fmt(diag, k):
    """诊断表一格（`report` 用）：float 三位小数，其余 `str()` —— 与拆前**逐字相同** ✓。"""
    v = diag[k]
    return f"{v:.3f}" if isinstance(v, float) else str(v)


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
