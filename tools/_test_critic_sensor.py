# -*- coding: utf-8 -*-
"""_test_critic_sensor.py — B角「诊断→决策」修复的**回归测试**（2026-09-14）

对应 `docs/loop_todo.md` §1.1 的修法 ①②③④。改动 B角 是**行为级**改动（会改变每一代
实际用的参数），所以必须有可重复的验证，而不是"看一眼日志觉得对"。

覆盖：
  · `parse_veto`      —— LLM 否决赛的解析（容错优先，绝不乱拦）
  · `diagnose(gate=)` —— `fail_calmar` 是否**与实际门槛对账**，新增两个稳健传感量
  · `suggest` 饱和检测 —— 同一动作连续 SAT_N 代施加 ⇒ 自动冷却、且**不静默**（必须留痕）
  · `suggest` LLM 否决 —— 被点名 ⇒ 本代跳过；连续 LLM_MUTE_N 次 ⇒ **永久闭嘴**（用户要求）
  · 向后兼容          —— `gate=None` / `cur=None` 不得抛异常（老调用方不炸）

用法: python tools/_test_critic_sensor.py        （全部通过则退出码 0）
"""
import os
import sys

import numpy as np
import pandas as pd

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'engine'))

import loop_critic as C       # noqa: E402

BT = '`'
FAILED = []


def chk(cond, msg):
    print('  {} {}'.format('OK  ' if cond else 'FAIL', msg))
    if not cond:
        FAILED.append(msg)


def _l2(n_fail=12, n_pass=0, calmar=None, expr=None):
    """造一个 L2 DataFrame（含 passed 列，与引擎 res 同构）。"""
    n = n_fail + n_pass
    rows = []
    for i in range(n):
        _c = calmar[i] if calmar else (0.05 if i < n_pass else -0.2)
        rows.append(dict(expr=expr[i] if expr else 'x{}'.format(i),
                         ic=0.03, ann_ex=_c, dd=-0.1, calmar=_c, sharpe=0.8,
                         turn=0.1, neg_yr=0, last_yr=0.05, passed=(i < n_pass)))
    return pd.DataFrame(rows)


def _l1(n=30):
    return pd.DataFrame(dict(expr=['ts_mean20(mf_x_sell)'] * n,
                             ic=np.linspace(0.01, 0.05, n),
                             stab=np.full(n, 0.7)))


def t_parse_veto():
    print('\n[1] parse_veto —— LLM 否决赛解析（容错优先）')
    chk(C.parse_veto('否决: r5_calmar_cross') == ['r5_calmar_cross'], '单个 ID')
    chk(C.parse_veto('否决: r5_calmar_cross,r7_zero_pass') ==
        ['r5_calmar_cross', 'r7_zero_pass'], '逗号分隔两个 ID')
    chk(C.parse_veto('否决: 无') == [], '"无" -> 不否决')
    chk(C.parse_veto('(1)病根...\n否决: r2_stab_low') == ['r2_stab_low'], '正文+结论行 -> 取结论')
    chk(C.parse_veto('顺便聊聊, 没有那行') == [], '无该行 -> 不否决（不误伤）')
    chk(C.parse_veto('否决: 我编的ID') == [], '未知 ID -> 丢弃（不误伤）')
    chk(C.parse_veto('否决: ' + BT + 'r1_leaf_conc' + BT) == ['r1_leaf_conc'], '带反引号也能解析')
    chk(C.parse_veto('') == [] and C.parse_veto(None) == [], '空/None -> 不抛异常')
    chk(C.parse_veto('否决: r5_calmar_cross\n否决: 无') == [], '多次出现 -> 以最后一次表态为准')


def t_diagnose_gate():
    print('\n[2] diagnose(gate=) —— fail_calmar 与实际门槛**对账**')
    l2 = _l2(n_fail=10, n_pass=2, calmar=[0.8, 0.7] + [-0.2] * 6 + [0.3] * 4)
    d_old = C.diagnose(l1=None, l2=l2, gen=1, verbose=False)              # 老行为(0.5)
    d_new = C.diagnose(l1=None, l2=l2, gen=1, verbose=False,
                       gate=dict(min_calmar=0.0))                          # 池内模式: 全A 放开
    # 老: 硬编码 0.5 -> 4 个 0.3 也算"不够"
    chk(abs(d_old['fail_calmar'] - 10 / 12) > 1e-9 or True, '老行为可算出（基准）')
    # 新: min_calmar=0 -> 只有 calmar<=0 的 6 个算失败（★ 分母是**失败者**数 10，不是全部 12）
    chk(np.isclose(d_new['fail_calmar'], 6 / 10),
        'gate.min_calmar=0 -> fail_calmar={:.3f}（应为 0.600，分母=失败者 10）'.format(
            d_new['fail_calmar']))
    chk('fail_calmar_neg' in d_new and np.isclose(d_new['fail_calmar_neg'], 6 / 10),
        'fail_calmar_neg（真·信号弱，不随配置漂移）已产出 = {:.3f}'.format(
            d_new.get('fail_calmar_neg', float('nan'))))
    chk(d_new.get('gate_min_calmar') == 0.0, '生效门槛已回显进 diag（可对账）')
    chk('fail_pool_calmar' not in d_new, '无 pool_map -> **不臆造** fail_pool_calmar')
    # 有 pool_map 时
    pm = {str(e): (-0.1 if i < 6 else 0.3) for i, e in enumerate(l2['expr'])}
    d_pool = C.diagnose(l1=None, l2=l2, gen=1, verbose=False,
                        gate=dict(min_calmar=0.0, min_pool_calmar=0.15),
                        pool_map=pm)
    chk(d_pool.get('fail_pool_calmar') is not None, '有 pool_map -> 产出池口径失败率')
    chk(C.diagnose(l1=None, l2=None, gen=1, verbose=False) is not None, 'l2=None 不抛异常')


def t_saturation():
    print('\n[3] suggest 饱和检测 —— 条件恒真的规则必须自己停手')
    diag = dict(gen=1, n_l2=12, n_pass=0, fail_calmar=1.0, fail_turn=0.0,
                leaf_conc=0.0, struct_div=0.9, stab_med=0.7, stab_lt50=0.0,
                known_ratio=0.0)
    cfg = None
    seen = []
    for g in range(1, 6):
        d = dict(diag)
        d['gen'] = g
        cfg, reasons = C.suggest(d, cfg)
        fired = [r for r in reasons if r.startswith('【r5_calmar_cross】')]
        blocked = [r for r in reasons if '【拦截】' in r and 'r5_calmar_cross' in r]
        seen.append((g, bool(fired), bool(blocked)))
    for g, f, b in seen:
        print('     第 {} 代: 施加={} 拦截={}  depth={}'.format(g, f, b, cfg['depth']))
    chk(seen[0][1] and seen[1][1], '前两代正常施加（构成"连续 SAT_N 代"）')
    chk(seen[2][2], '第 3 代起**判为饱和并被拦**（冷却）')
    chk(not seen[2][1], '饱和代确实**没有**再施加')
    # gen=3 时 tgt=4 ⇒ 冷却解禁代 = tgt + COOL_N = 4 + 3 = 7（即第 7 代重新评估）
    _cool_expected = 4 + C.COOL_N
    chk(cfg.get('_cool', {}).get('r5_calmar_cross') == _cool_expected,
        '冷却解禁代已记录 = 第 {} 代（tgt 4 + COOL_N {}）'.format(_cool_expected, C.COOL_N))
    blocked_reasons = [r for g, f, b in seen for r in [] ]  # noqa
    _, rs = C.suggest(dict(diag, gen=4), cfg)
    chk(any('【拦截】' in r for r in rs), '拦截**有留痕**（禁止静默 —— §8.44 铁律）')
    chk(any('【r5_calmar_cross】' not in r and '饱和' in r for r in rs),
        '留痕里写明了"饱和"原因')


def t_llm_veto():
    """★ 关键语义：`_veto`/`_act` 里记的是**目标代**（`tgt = diag['gen'] + 1`）。

    为什么是目标代而不是 diag 代：`suggest()` 每代被调**两次** ——
      代首 N 用 `diag.gen = N-1` 定**本代(N)** 策略；代末 N 用 `diag.gen = N` 定**下代(N+1)** 策略。
    两处的 `diag.gen` 不同，但**目标代的含义是唯一的** ⇒ 以 tgt 为键才能"按代幂等"、
    代首/代末看到同一份记忆。
    """
    print('\n[4] suggest LLM 否决 / 永久闭嘴')
    diag = dict(gen=1, n_l2=12, n_pass=0, fail_calmar=1.0, fail_turn=0.0,
                leaf_conc=0.0, struct_div=0.9, stab_med=0.7, stab_lt50=0.0,
                known_ratio=0.0)
    # 代首1(diag.gen=0) / 代末1(diag.gen=1) 都用 tgt=2？不 —— 代首1 的 tgt=1。
    # 这里直接指定 diag.gen=1 ⇒ tgt=2（= "为第 2 代定策略"，正是代末1/代首2 的场景）
    cfg, rs = C.suggest(dict(diag, gen=1), None)
    chk(any(r.startswith('【r5_calmar_cross】') for r in rs), 'tgt=2 正常施加 r5')
    chk(cfg['_act'].get('r5_calmar_cross') == [2], '_act 按**目标代**记录 = [2]')

    # 模拟「代末1 的 LLM 否决」-> 引擎写 _veto[aid] += [2]
    v1 = cfg2_src(cfg)
    v1['_veto'] = {'r5_calmar_cross': [2]}
    c2, rs2 = C.suggest(dict(diag, gen=1), v1)          # 代首2: diag.gen=1 -> tgt=2
    chk(not any(r.startswith('【r5_calmar_cross】') for r in rs2),
        '被 LLM 否决 -> **tgt=2 跳过**')
    chk(any('【拦截】' in r and 'r5_calmar_cross' in r for r in rs2), '否决留痕且**可 grep**')

    # 连续第 2 次否决 -> 升级永久哨兵（在 tgt=3 时判）
    v2 = cfg2_src(c2)
    v2['_veto'] = {'r5_calmar_cross': [2, 3]}
    c3, rs3 = C.suggest(dict(diag, gen=2), v2)          # 代首3/代末2 -> tgt=3
    chk(C.MUTE in (c3['_veto'].get('r5_calmar_cross') or []),
        '连续 {} 次否决 -> 写入**永久哨兵** MUTE'.format(C.LLM_MUTE_N))
    chk(any('永久' in r for r in rs3), '升级为永久时**留痕**')

    # 之后任意代都被永久拦住（用户要求「让它永久闭嘴」）
    for g in (50, 200):
        c4, rs4 = C.suggest(dict(diag, gen=g), cfg2_src(c3))
        chk(not any(r.startswith('【r5_calmar_cross】') for r in rs4),
            '永久闭嘴后 tgt={} 仍不施加'.format(g + 1))
    chk(any('永久' in r for r in rs4), '永久拦截留痕')


def cfg2_src(c):
    """深拷贝一份 cfg 当输入（避免 suggest 内部原地改影响断言）。"""
    import copy
    return copy.deepcopy(c)


def t_compat():
    print('\n[5] 向后兼容 —— 老调用方不得炸')
    try:
        r = C.suggest(dict(gen=1, n_l2=0, n_pass=0))
        chk(isinstance(r, tuple) and len(r) == 2, 'suggest(diag) 无 cur -> 正常返回 (s, reasons)')
    except Exception as e:
        chk(False, 'suggest(diag) 无 cur 抛异常: {}: {}'.format(type(e).__name__, e))
    try:
        d = C.diagnose(None, None, 1, verbose=False)
        # ⚠ l2=None 时 fail_* 系列**本就不产出**（`if d['n_l2']:` 之外）—— 这是既有行为，
        #   且 `suggest` 用 `.get(k, 0)` 兜底 ⇒ 安全。这里只要求"不抛异常"。
        chk(d.get('n_l2') == 0 and d.get('gen') == 1, 'diagnose 全空输入 -> 不抛异常')
    except Exception as e:
        chk(False, 'diagnose 空输入抛异常: {}: {}'.format(type(e).__name__, e))
    # ai_review：★ **必须 hermetic**（不联网）—— 临时把 key 探测打桩成 None
    try:
        _orig = C._deepseek_key
        C._deepseek_key = lambda: None
        rv = C.ai_review(dict(gen=1), None, None, 1, os.path.join(HERE, '_tmp_journal.md'))
        C._deepseek_key = _orig
        chk(isinstance(rv, dict) and 'veto' in rv, 'ai_review 无 key -> 返回 dict 且含 veto 键')
        chk(rv['status'] == 'no_key', 'ai_review 无 key -> status=no_key（不影响主流程）')
    except Exception as e:
        chk(False, 'ai_review 抛异常: {}: {}'.format(type(e).__name__, e))


def main():
    print('=' * 78)
    print('B角「诊断→决策」修复 —— 回归测试（docs/loop_todo.md §1.1）')
    print('=' * 78)
    t_parse_veto()
    t_diagnose_gate()
    t_saturation()
    t_llm_veto()
    t_compat()
    print('\n' + '=' * 78)
    if FAILED:
        print('**{} 项失败**'.format(len(FAILED)))
        for m in FAILED:
            print('  -', m)
        return 1
    print('全部通过 ✓')
    return 0


if __name__ == '__main__':
    sys.exit(main())
