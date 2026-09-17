# -*- coding: utf-8 -*-
"""_test_action_efficacy.py — 「动作有效性」+「参数棘轮」回归测试（`loop_todo §1.15` + `§1.1`）

## 守的是什么

**§1.15 动作有效性**：饱和检测只回答「**别重复**」，**不回答「为什么无效」**。
★ 实测（全A 池 gen61~gen73）：`r1_leaf_conc` **连续 13 代**压同一个叶子，
  而 `leaf_conc` **始终回到 62%~100%** ⇒ **动作施加了但完全无效** ✗
⇒ 记**施加前的指标基线**，等这一段闭合（判过饱和 + 冷却）后**结算**：没改善 ⇒ 判无效
  ⇒ 冷却翻倍；累计 `INEFF_MUTE_N` 次 ⇒ **永久停用**。

**§1.1 参数棘轮**：饱和/永久闭嘴只阻止动作**继续**施加，**不撤销它已经改过的值**
⇒ ★ 实测 `depth` 被永久推到 `[3,4,5]` 后**再也回不去**（LLM 建议的是 `[2,3]`）。
⇒ 记**参数旧值**，永久停用时**保守回退**（只回退"确实改过、且之后没人再动过"的）。

## ★★★ 本测试守护的三条硬性质

1. **判无效必须有证据**：目标指标取不到时**不判定**（不臆造，roadmap §8.45 铁律）。
2. **回退不能误撤**：多动作改同一参数时，只回退「当前值 == 本动作写入值」的那些。
3. ★★ **最终要收敛**：多个动作改同一参数**且都判无效** ⇒ 必须一路撤到**最初值**
   （不能因为"处理顺序"停在半路 —— 这个坑 2026-09-14 实测踩到并已修）。

用法: python tools/_test_action_efficacy.py
"""
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ENG = os.path.join(ROOT, 'engine')
sys.path.insert(0, ENG)

OK = [0, 0]


def chk(cond, msg):
    OK[0] += 1
    if not cond:
        OK[1] += 1
    print('  [{}] {}'.format('OK ' if cond else 'FAIL', msg))


# 一份"恒定指标"的诊断：所有动作的目标指标都**不动** ⇒ 必然被判定无效
DIAG = dict(gen=0, n_l2=10, n_pass=0, fail_pool_calmar=0.80, fail_calmar=0.80,
            leaf_conc=0.10, stab_med=0.90, stab_lt50=0.0, struct_div=0.90,
            fail_turn=0.0, known_ratio=0.0, leaf_top=[('x', 1)])


def run_gens(C, n, diag=None, cfg=None, start=0):
    """跑 `n` 代（**从 `start` 代起**），返回 (cfg, 每代 reasons, 下一个 start)。

    ⚠ 2026-09-14 实录：初版没有 `start`，每次都从 gen=0 跑 ⇒ 分段调用时**代编号错乱**
      （gen 回到 0 ⇒ 冷却/饱和/结算全错位）⇒ 测试假 FAIL ✗
      **教训**：测"跨代状态机"时，**代编号必须连续**（这是被测逻辑的输入，不能重来）。
    """
    cfg = cfg if cfg is not None else {}
    out = []
    for g in range(start, start + n):
        cfg, rs = C.suggest(dict(diag or DIAG, gen=g), cfg)
        out.append(rs)
    return cfg, out, start + n


def t_pure(C):
    print('\n[1] 纯函数：`_improved`（方向 + 容差）')
    chk(C._improved(0.5, 0.6, True) is True, '越大越好：0.5→0.6 判「改善」')
    chk(C._improved(0.5, 0.4, True) is False, '越大越好：0.5→0.4 判「没改善」')
    chk(C._improved(0.6, 0.5, False) is True, '越小越好：0.6→0.5 判「改善」')
    chk(C._improved(0.5, 0.5, False) is False, '持平 ⇒ 没改善（否则"不变"会被当成有效）')
    chk(C._improved(0.5, 0.505, True) is False,
        '改善幅度 {:.3f} < 容差 {:.2f} ⇒ 视为噪声、判没改善'.format(0.005, C.METRIC_EPS))
    chk(C._improved(None, 0.5, True) is None, '缺基线 ⇒ **不判定**（返回 None，不臆造）')
    chk(C._improved(0.5, None, True) is None, '缺当前值 ⇒ 不判定')


def t_rollback_plan(C):
    print('\n[2] `_rollback_plan`：保守回退（不误撤别的动作）')
    s = dict(min_stab=0.45, depth=[3, 4, 4], leaf_w={'a': 0.25})
    done, skip = C._rollback_plan(s, 'r2', {'min_stab': [0.30, 0.45]})
    chk(done == [('min_stab', 0.30)] and s['min_stab'] == 0.30,
        '当前值==写入值 ⇒ 恢复到旧值 0.30')
    s2 = dict(min_stab=0.55)
    done2, skip2 = C._rollback_plan(s2, 'r2', {'min_stab': [0.30, 0.45]})
    chk(not done2 and s2['min_stab'] == 0.55,
        '★ 当前值 0.55 ≠ 本动作写入 0.45（被 r4 改过）⇒ **跳过、不动**（不误撤 r4）')
    s3 = dict(leaf_w={'a': 0.25})
    done3, _ = C._rollback_plan(s3, 'r1', {'leaf_w.a': [1.0, 0.25]})
    chk(done3 == [('leaf_w.a', 1.0)] and s3['leaf_w']['a'] == 1.0, '嵌套参数（`leaf_w.a`）✓')
    s4 = dict()
    _d, sk4 = C._rollback_plan(s4, 'r1', {'not_exist': [1, 2]})
    chk(sk4 and not _d, '参数不存在 ⇒ 跳过（并留原因）')


def t_efficacy(C):
    print('\n[3] 有效性判定全流程（恒定指标 ⇒ 必然判无效）')
    cfg, rs, g = run_gens(C, 3)                      # gen 0,1,2
    chk(any(r.startswith('【r5_calmar_cross】L2中') for r in rs[0]),
        'gen0：r5 正常施加（记为一段的开始）')
    # ⚠ 快照要查**数据**而不是查文案（初版去 reasons 里找"施加"两个字 ⇒ 假 FAIL，见下）
    _p0 = (cfg['_base'].get('r5_calmar_cross') or {}).get('params') or {}
    chk('depth' in _p0 and 'mix' in _p0,
        '★ `_mark` 里同步记了**参数旧值**（棘轮用）：depth/mix 各有 (旧,新) —— 实得 {}'.format(
            sorted(_p0)))
    chk(any('r5_calmar_cross' in r and '饱和' in r for r in rs[2]),
        'gen2：连续 2 代 ⇒ 判饱和（这一段闭合）')
    chk(cfg['_base'].get('r5_calmar_cross', {}).get('due') is True,
        '★ 饱和时**标记 `due`** ⇒ 解禁后才结算（否则会在第二次施加前就下结论）')
    cfg, rs, g = run_gens(C, 6, cfg=cfg, start=g)    # gen 3..8（冷却到第 6 代解禁）
    # ⚠ `rs` 是「每代的 reasons **列表**」⇒ 必须**先摊平**再按字符串找
    #   （初版直接 `for r in rs` ⇒ r 是 list ⇒ 永远找不到 ⇒ 假 FAIL ✗）
    flat = [r for rr in rs for r in rr]
    first = [r for r in flat if '有效性判定' in r]
    chk(bool(first) and '施加无效' in first[0],
        '解禁后**结算**：0.80 → 0.80 无改善 ⇒ 判「施加无效」{}'.format(
            '' if first else '（没找到判定行！）'))
    chk(cfg['_cool_mul'].get('r5_calmar_cross') == C.INVALID_COOL_MULT,
        '★ 判无效一次 ⇒ **冷却倍率 ×{}**（不是简单重复冷却）'.format(C.INVALID_COOL_MULT))
    chk(not cfg['_base'].get('r5_calmar_cross', {}).get('due'),
        '结算后清 `due`（否则下段刚记基线就会被误结算）')
    # 跑到第 2 次判无效 ⇒ 永久停用
    cfg, rs, g = run_gens(C, 14, cfg=cfg, start=g)
    flat = [r for rr in rs for r in rr]
    chk(any('永久停用' in r for r in flat),
        '累计 {} 次判无效 ⇒ **永久停用**'.format(C.INEFF_MUTE_N))
    chk(C.MUTE in (cfg['_ineff'].get('r5_calmar_cross') or []), '`_ineff` 写入哨兵 MUTE')
    cfg, rs, g = run_gens(C, 3, cfg=cfg, start=g)
    chk(all(any('r5_calmar_cross' in r and '实测无效' in r and '永久停用' in r for r in rr)
            for rr in rs), '此后各代**一律被拦**（且留痕写明原因）')


def t_ratchet(C):
    print('\n[4] ★★ 参数棘轮：永久停用 ⇒ 回退到旧值；多动作改同一参数 ⇒ 收敛到最初')
    # 用"恒定指标"让 r5/r7 都被判无效（都改 depth）
    cfg, rs, _g = run_gens(C, 26)
    rolled = [r for rr in rs for r in rr if '棘轮' in r]
    chk(rolled, '出现了回退留痕（journal 里可复核）✓')
    chk(cfg['depth'] == [2, 3, 4],
        '★★ 最终 depth 回到**最初默认 [2,3,4]**（实测 r5 写 [3,4,4]、r7 写 [3,4,5]，'
        '两者都无效 ⇒ 必须一路撤到最初）—— 实得 {}'.format(cfg['depth']))
    chk(abs(cfg['mix'][0] - 0.25) < 1e-9, 'mix 也回到最初（变异 0.25）')
    chk(not any((v or {}).get('params') for v in cfg['_base'].values()),
        '★ 回退完成后 `_base[*].params` **清空**（无残留，不会无限重试）')
    # 不误撤：一个仍活跃的动作改过的参数，不该被无效动作撤掉
    print('  --- 不误撤验证 ---')
    C2 = C
    cfg2, _rs2, _g2 = run_gens(C2, 1)               # gen0: r5+r7 都施加
    _b = cfg2['_base']['r5_calmar_cross']['params']
    chk('depth' in _b and _b['depth'][1] == [3, 4, 4], 'r5 的快照记录 depth 写入了 [3,4,4]')
    chk(cfg2['_base']['r7_zero_pass']['params']['depth'][1] == [3, 4, 5],
        'r7 的快照记录 depth 写入了 [3,4,5]（**同参数、不同动作**都各记一份）')


def t_none_weight(C):
    print('\n[6] ★★★★ `None` 权重**绝不能写进 cfg**（真 BUG：引擎秒崩 ⇒ 用户看到"蓝点、像轮转"）')
    # 1) `_set_param` 写 None ⇒ **删键**（不是塞个 None 进去）
    s = dict(leaf_w={'a': 0.25, 'b': 0.5}, min_stab=0.3)
    C._set_param(s, 'leaf_w.a', None)
    chk('a' not in s['leaf_w'] and s['leaf_w'] == {'b': 0.5},
        '`leaf_w.a` 写 None ⇒ **键被删除**、值不是 None —— 实得 {}'.format(s['leaf_w']))
    C._set_param(s, 'min_stab', None)
    chk('min_stab' not in s, '顶层参数写 None ⇒ 同样删键')
    # 2) 棘轮回退：`old=None` 的语义是"**施加前这个键不存在**" ⇒ 回退必须**删键**（实测根因就在这里）
    s2 = dict(leaf_w={'barra_growth': 0.25})
    done, _sk = C._rollback_plan(s2, 'r1_leaf_conc', {'leaf_w.barra_growth': [None, 0.25]})
    chk(done == [('leaf_w.barra_growth', None)],
        '回退计划如实返回 old=None（日志里要写明"删键"而不是"恢复成 None"）')
    chk('barra_growth' not in s2['leaf_w'] and None not in s2['leaf_w'].values(),
        '★★ 回退后 cfg 里**不含任何 None**（这就是不崩的关键）—— 实得 {}'.format(s2['leaf_w']))
    chk('删除该键' in open(os.path.join(ENG, 'loop_critic.py'), encoding='utf-8').read(),
        '回退留痕写明"删除该键"（否则 journal 会让人以为真值就是 None）')


def t_none_weights_engine():
    """★ 真跑一遍引擎侧抽样（有 None 也不该抛异常 —— 这是让池子继续跑的第二道防线）。"""
    print('\n[7] ★★ 引擎侧抽样/混权/自愈：`None` 权重不再让整池停摆')
    import random
    import loop_engine as LE
    cfg = {'leaf_w': {'barra_growth': None}, 'op_bias': {'ts_std': None}}
    rng = random.Random(7)
    try:
        for _ in range(20):
            LE.pick_leaf(rng, cfg)
            LE.pick_op(rng, cfg, ['ts_std', 'ts_rank'])
        ok, err = True, None
    except Exception as e:                                 # noqa: BLE001
        ok, err = False, e
    chk(ok, '含 None 的 cfg 也能正常抽样（不再 TypeError）{}'.format('' if ok else ' —— ' + repr(err)))
    m = LE._mix_weights({'a': None, 'b': 2.0}, {'a': 1.0, 'b': 1.0}, ['a', 'b'])
    chk(all(v is not None for v in m.values()) and abs(m['b'] - 2.0) < 1e-9,
        '`_mix_weights`：None 回退 1.0，且**原样保留**已给的权重 —— 实得 {}'.format(m))
    cleaned = LE._clean_cfg({'leaf_w': {'x': None, 'y': 0.25}, 'op_bias': {'o': None}})
    chk(cleaned['leaf_w'] == {'y': 0.25} and cleaned['op_bias'] == {},
        '`_clean_cfg` 读 state 时剔除 None（旧脏 state 自愈）—— 实得 {}'.format(cleaned))
    chk(LE._wt({'k': 0.0}, 'k') == 0.0,
        '★ **0 权重不被当成 None**（"永不抽它"这个语义必须保住，别用 `or 1.0` 一刀切）')


def t_static(C):
    print('\n[5] 静态断言：所有动作都必须走 `_set`（防新增动作**静默漏记**）')
    src = open(os.path.join(ENG, 'loop_critic.py'), encoding='utf-8').read()
    m = re.search(r'(# 1\) 叶子过度集中.*?)(\n    if not reasons:)', src, re.S)
    chk(m is not None, '找到"动作区"（从 r1 到收尾）')
    body = m.group(1)
    bad = re.findall(r"^\s+s\['(?!_)(\w+)'\]\s*=(?!=)", body, re.M)
    bad += re.findall(r"^\s+s\['(\w+)'\]\[[^\]]+\]\s*=(?!=)", body, re.M)
    chk(not bad, '★ 动作区里**没有任何直接给 `s[...]` 赋值**（都走 `_set`）—— 实得 {}'.format(bad))
    chk(body.count('_set(') >= 7, '7 个动作都用 `_set`（实得 {} 处）'.format(body.count('_set(')))
    chk('_ctx[\'pre\'].setdefault' in src or "_ctx['pre'].setdefault" in src,
        '`_set` 会自动登记「本动作名下该参数的首个旧值」')
    chk('guard_mix' in src and '同步快照' in src,
        '★ `guard_mix` 之后**同步快照的新值**（否则 mix 永远匹配不上 ⇒ 棘轮对 mix 失效）')
    chk("b.get('due')" in src or 'b.get("due")' in src, '`_settle` 依赖 `due` 标记（时机正确）')


def main():
    print('=' * 96)
    print('动作有效性 + 参数棘轮 回归测试（loop_todo §1.15 + §1.1）')
    print('=' * 96)
    import loop_critic as C
    t_pure(C)
    t_rollback_plan(C)
    t_efficacy(C)
    t_ratchet(C)
    t_none_weight(C)
    t_none_weights_engine()
    t_static(C)
    print('\n' + '=' * 96)
    print('通过 {}/{}'.format(OK[0] - OK[1], OK[0]) + ('' if OK[1] else '  ✓ 全部通过'))
    return 1 if OK[1] else 0


if __name__ == '__main__':
    sys.exit(main())
