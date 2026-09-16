# -*- coding: utf-8 -*-
"""_test_daily_dd.py — `evaluate_real(with_daily=True)` 的回归测试（loop_todo §1.19）

## 守的是什么

引擎现在的风险指标是「**期频打点**」口径：`nav = (1+ex).cumprod()`，而 `ex` 是**每换仓期**一条
⇒ 净值只在**期末**有点 ⇒ 漏掉持有期内的日内回撤 ⇒ **回撤系统性低估 ~3.6pp、Calmar 高估 ~1.4×**。
`with_daily=True` 补上「**持有期内逐日 mark**」的日频口径。

★ 本测试用一条**数学恒等式**钉死正确性（比"和外部审查数字对得上"更硬）：

    **期频净值曲线是日频曲线的子采样** ⇒ `dd_d <= dd_e` **必然成立**（日频只能更差或相等）

再配三条：
  · `ann_ex` 两种口径**必须相同**（终值一样、年数一样 ⇒ 年化只取决于终值）
  · 默认 `with_daily=False` ⇒ **不产生任何新键**（行为完全不变，老调用方不受影响）
  · 日频样本数 ≈ `n_rebal * FWD`（时间跨度对得上）

用法: python tools/_test_daily_dd.py
"""
import os
import pickle
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


def main():
    import numpy as np
    import pandas as pd
    import loop_engine as LE
    for n in dir(LE):
        if n[:1].isupper() and isinstance(getattr(LE, n), type):
            setattr(sys.modules['__main__'], n, getattr(LE, n))
    import factor_miner as fm

    print('=' * 96)
    print('evaluate_real(with_daily=True) 回归测试（loop_todo §1.19）')
    print('=' * 96)

    # ---- 取一个真实已入库因子（保证不是人造退化情形）----
    sp = os.path.join(ENG, 'loop_state_1000.pkl')
    if not os.path.exists(sp):
        print('  缺 {} -> 跳过'.format(sp))
        return 0
    st = pickle.load(open(sp, 'rb'))
    if not st.get('bank'):
        print('  1000 池 bank 为空 -> 跳过')
        return 0
    nd = st['bank'][0]
    print('\n[0] 用真实因子: {}...'.format(str(nd)[:70]))

    bf = LE.base_fields()
    B, dates, cols, close = bf['B'], bf['dates'], bf['cols'], bf['close']
    v = LE.eval_expr(nd, B, {})
    f = fm.cs_rank(pd.DataFrame(v, index=dates, columns=cols).astype('float64'))

    print('\n[1] 默认 with_daily=False 时**行为完全不变**')
    r0 = fm.evaluate_real(f, close, str(nd), cost=0.004, window=5)
    r1 = fm.evaluate_real(f, close, str(nd), cost=0.004, window=5, with_daily=False)
    chk(set(r0.keys()) == set(r1.keys()), '不传 / 传 False -> 返回键集合相同')
    chk(not any(k.endswith('_d') for k in r0.keys()), '不传 -> **没有**任何 _d 结尾的键')
    chk(abs(r0['dd'] - r1['dd']) < 1e-12, '不传 / 传 False -> dd 逐位相同')

    print('\n[2] with_daily=True 的产出')
    rd = fm.evaluate_real(f, close, str(nd), cost=0.004, window=5, with_daily=True)
    for k in ('dd_d', 'calmar_d', 'sharpe_d'):
        chk(k in rd and np.isfinite(rd[k]), '{} 存在且有限（= {:.4f}）'.format(
            k, rd.get(k, float('nan'))))
    chk('ex_d' not in rd, '未传 with_ex -> 不返回 ex_d（避免无谓的体积）')

    print('\n[3] ★ 数学恒等式：dd_d <= dd_e（期频是日频的**子采样**）')
    chk(rd['dd_d'] <= rd['dd'] + 1e-12,
        'dd_d {:.4f} <= dd_e {:.4f}（日频只能更差或相等）'.format(rd['dd_d'], rd['dd']))
    chk(abs(rd['dd_d'] - rd['dd']) > 1e-6,
        '两者**确实不同**（差 {:.4f}pp）⇒ with_daily 真的在算，不是复读期频'.format(
            100 * (rd['dd'] - rd['dd_d'])))

    print('\n[4] ann_ex 两种口径必须相同（终值/年数一样 ⇒ 年化只取决于终值）')
    chk(abs(rd['ann_ex'] - r0['ann_ex']) < 1e-12,
        'ann_ex 期频 {:.4f} == 日频 {:.4f}'.format(r0['ann_ex'], rd['ann_ex']))
    # calmar 的差别因此**只来自回撤** ⇒ 可直接验算
    _cal_d_expect = rd['ann_ex'] / abs(rd['dd_d'])
    chk(abs(rd['calmar_d'] - _cal_d_expect) < 1e-6,
        'calmar_d == ann_ex/|dd_d| = {:.4f}（与实现一致）'.format(_cal_d_expect))

    print('\n[5] 日频样本数 ≈ n_rebal * FWD（时间跨度对得上）')
    rex = fm.evaluate_real(f, close, str(nd), cost=0.004, window=5,
                           with_daily=True, with_ex=True)
    n_exp = rex['n_rebal'] * fm.FWD
    n_got = len(rex['ex_d'])
    chk(abs(n_got - n_exp) / max(n_exp, 1) < 0.05,
        '日频 {} 条 vs 期频 {} 期 x FWD{} = {}（误差 <5%）'.format(
            n_got, rex['n_rebal'], fm.FWD, n_exp))

    print('\n[6] 年化因子一致性：日频 sharpe 的年化用 sqrt(243)')
    ed = rex['ex_d']
    chk(abs(rex['sharpe_d'] - ed.mean() / ed.std() * np.sqrt(243.0)) < 1e-9,
        'sharpe_d == mean/std*sqrt(243) = {:.4f}'.format(rex['sharpe_d']))

    print('\n[7] ★★ 锚定验证：期频净值 == 日频净值在**每个期末**的取值')
    #   实现把每期的日超额 `seg` 等比缩放使 `prod(1+seg) == 1+ex_e`
    #   ⇒ 日频曲线**逐点通过**所有期频点 ⇒ 期频是日频的**严格子采样**（这是 [3] 恒等式的前提）。
    nav_d = (1 + ed).cumprod()
    #  期频序列（带 with_ex）的终值
    nav_e_end = float((1 + rex['ex']).cumprod().iloc[-1])
    chk(abs(float(nav_d.iloc[-1]) - nav_e_end) / abs(nav_e_end) < 1e-9,
        '日频终值 {:.6f} == 期频终值 {:.6f}（相对误差 <1e-9）'.format(
            float(nav_d.iloc[-1]), nav_e_end))
    #  逐点抽查：期频第 k 个点 应等于 日频中第 k 段末尾
    nav_e = (1 + rex['ex']).cumprod().values
    ok_pts, n_pts = 0, 0
    pos = 0
    seglen = int(round(len(ed) / max(len(nav_e), 1)))
    for k in range(len(nav_e)):
        pos += seglen
        if pos > len(nav_d):
            break
        n_pts += 1
        if abs(float(nav_d.iloc[pos - 1]) - float(nav_e[k])) / max(abs(float(nav_e[k])), 1e-9) < 1e-6:
            ok_pts += 1
    chk(n_pts >= 10 and ok_pts == n_pts,
        '逐点抽查 {}/{} 个期频点与日频曲线重合（段长 {}）'.format(ok_pts, n_pts, seglen))

    print('\n[8] ★★ 组合自身日频（2026-09-16 新增：`dd_top_d/calmar_top_d/sharpe_top_d`）')
    #   起因：用户看到「组合自身最大回撤 −34.7%」与「日频打点最大回撤 −13.1%」并列，直觉认为后者不可能更浅 ✗
    #   ★ 真因是**口径不同**（`dd_d` 是**超额**口径的日频）⇒ 本次把"组合自身的日频"也补上，
    #     让「期频 vs 日频」在**同一口径内**可比 ✓
    for k in ('dd_top_d', 'calmar_top_d', 'sharpe_top_d'):
        chk(k in rex and np.isfinite(rex[k]), '{} 存在且有限（= {:.4f}）'.format(
            k, rex.get(k, float('nan'))))
    chk(rex['dd_top_d'] <= rex['dd_top'] + 1e-12,
        '★ 恒等式 dd_top_d {:.4f} <= dd_top {:.4f}（组合日频只能更深）'.format(
            rex['dd_top_d'], rex['dd_top']))
    _cal_td = rex['ann_top'] / abs(rex['dd_top_d'])
    chk(abs(rex['calmar_top_d'] - _cal_td) < 1e-6,
        'calmar_top_d == ann_top/|dd_top_d| = {:.4f}'.format(_cal_td))
    # ★ 口径不可混：`dd_d` 与 `dd` 配对；把它和 `dd_top` 比就是错的口径
    chk(abs(rex['dd_d'] - rex['dd']) > 1e-6,
        'dd_d {:.4f} 与 dd {:.4f} 是一对（同口径）；**不要**拿 dd_d 和 dd_top {:.4f} 比 ✗'.format(
            rex['dd_d'], rex['dd'], rex['dd_top']))

    print('\n[9] 组合腿的锚定也要成立（期频 nav_t == 日频 nav_t 在每个期末）')
    td = rex['tr_d']
    nav_td = (1 + td).cumprod()
    nav_t_end = float((1 + rex['tr']).cumprod().iloc[-1])
    chk(abs(float(nav_td.iloc[-1]) - nav_t_end) / abs(nav_t_end) < 1e-9,
        '组合日频终值 {:.6f} == 组合期频终值 {:.6f}'.format(float(nav_td.iloc[-1]), nav_t_end))
    chk(abs(100 * (rex['dd_top'] - rex['dd_top_d'])) > 1e-6,
        '组合期频/日频回撤**确实不同**（差 {:.2f}pp）⇒ 真的算了日频，不是复读'.format(
            100 * (rex['dd_top'] - rex['dd_top_d'])))

    print('\n' + '=' * 96)
    print('通过 {}/{}'.format(OK[0] - OK[1], OK[0]) + ('' if OK[1] else '  ✓ 全部通过'))
    return 1 if OK[1] else 0


if __name__ == '__main__':
    sys.exit(main())
