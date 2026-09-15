# -*- coding: utf-8 -*-
"""library_kpi.py -- 核心 KPI：**库的平均两两收益流相关**（roadmap §8.33）

为什么这是核心 KPI（2026-09-13 实测）：
  库内 30 个入库因子的**组合收益序列两两相关中位 0.967**（max 0.994）
  ⇒ 它们是同一块钱的不同写法；等权合成 Calmar(0.978) 还**低于**最好的单因子(1.146)
  ⇒ **合成无效 = 库里只有"一个因子"**。
  ⇒ ⇒ **这个数不降下来，加再多因子都没用** —— 所以把它做成常看的 KPI
     （目标 < 0.7；现状 ~0.97）。

★ 本工具**不需要面板**（直接读 state 里的 `bank_ex`），所以是**秒级**的，可以随时看。

用法: python tools/library_kpi.py [--pool=all|300|500] [--detail]
"""
import io
import os
import pickle
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'engine'))

import numpy as np                 # noqa: E402
import pandas as pd                # noqa: E402

import loop_engine as LE           # noqa: E402

for _n in dir(LE):
    if _n[:1].isupper() and isinstance(getattr(LE, _n), type):
        setattr(sys.modules['__main__'], _n, getattr(LE, _n))

TARGET = 0.70          # 目标：平均两两相关低于该值


def main():
    pool, detail = 'all', False
    for a in sys.argv[1:]:
        if a.startswith('--pool='):
            pool = a.split('=', 1)[1].strip() or 'all'
        elif a == '--detail':
            detail = True
    LE.set_mine_pool(pool)
    print('=' * 74)
    if not os.path.exists(LE.STATE):
        print('状态文件不存在:', LE.STATE)
        return 1
    st = pickle.load(open(LE.STATE, 'rb'))
    bank = st.get('bank', []) or []
    bex = st.get('bank_ex', {}) or {}
    print('池 = {}   入库因子 {} 个   收益流库 {} 条'.format(pool, len(bank), len(bex)))
    if len(bex) < 2:
        print('收益流不足 2 条 —— 先跑 ai_test/backfill_bank_ex.py --pool=' + pool)
        return 1
    E = pd.DataFrame({k: pd.Series(v) for k, v in bex.items()})
    print('收益流共同期数: {}'.format(len(E.dropna())))
    C = E.corr(method='spearman')
    v = C.values
    # ★ 用 |corr|（与 `loop_engine.ex_max_corr` 判重同口径）—— 这样即使某些收益流
    #   因故**未按 IC 定向**（符号相反），KPI 也不会假性偏低。
    #   ⚠ 2026-09-13 实录：补齐首版没定向，raw node 跑出 −28%/−22% 的反向超额
    #     ⇒ 签名相关会算错（真相关显示为负）⇒ 故用绝对值 + 同时报签名中位供参考。
    va = np.abs(v)
    off = v[np.triu_indices_from(v, 1)]
    offa = va[np.triu_indices_from(va, 1)]
    m = np.isfinite(offa) & np.isfinite(off)
    off, offa = off[m], offa[m]
    if not len(offa):
        print('无可用的两两相关（重叠期数不足）')
        return 1
    med = float(np.median(offa))
    print()
    print('★ KPI 平均两两收益流相关（Spearman, 取 |.|）')
    print('   中位 {:.3f}   均值 {:.3f}   p90 {:.3f}   max {:.3f}'.format(
        med, float(offa.mean()), float(np.percentile(offa, 90)), float(offa.max())))
    print('   （签名中位 {:.3f} —— 若明显为负, 说明有收益流**未按 IC 定向**）'.format(
        float(np.median(off))))
    print('   >0.9 的因子对数: {}/{}  ({:.0%})'.format(
        int((offa > 0.9).sum()), len(offa), float((offa > 0.9).mean())))
    verdict = ('✅ **达标**（< {:.2f}）：库内因子已足够"独立"，因子数≈独立 alpha 数'.format(TARGET)
               if med < TARGET else
               '❌ **未达标**（目标 < {:.2f}）：库还在被"同一块钱"填满 ⇒ '
               '**加因子无用** ⇒ 需 §8.21-⑥ #5（语义单元+方向）。'.format(TARGET))
    print('   判读: ' + verdict)
    if detail:
        # 找出与别人最像的因子（最该被收益流去重拦下的）
        m = C.where(~np.eye(len(C), dtype=bool)).max(axis=1).sort_values(ascending=False)
        print()
        print('   与库内"最像"的因子 Top10（max |corr|）:')
        for k, x in m.head(10).items():
            print('     {:.3f}  {}'.format(x, str(k)[:96]))

    # ---- ★ 合成对照（默认开；零成本, 直接用 bank_ex）----
    #  ⚠⚠ 方法论纠正(2026-09-13, roadmap §8.35)：早先 `test_combine.py` 用 **`tr`(组合绝对收益)**
    #    算两两相关得 **0.967** 并据此断言"库其实只有一个因子" —— **那是错的**：
    #    `tr = ex + 基准收益`, 而**基准对所有因子完全相同** ⇒ 只要基准波动占主导,
    #    `corr(tr_i, tr_j)` 就必然趋近 1，**这是市场 β 的共性, 不是因子重复**。
    #    ⇒ 判"是不是赚同一块钱"必须用 **`ex`(超额)**。
    #  ⚠ 而且"合成有没有用"**不能与「事后挑出的最好单因子」比**（选择偏差）, 应与**个体中位/均值**比。
    E2 = E.dropna()
    if len(E2) >= 30 and E2.shape[1] >= 2:
        ex_c = E2.mean(axis=1)
        yrs = max(len(ex_c) * 5 / 243.0, 1e-9)          # FWD=5（evaluate_real 默认）
        nav = (1 + ex_c).cumprod()
        ann_c = nav.iloc[-1] ** (1 / yrs) - 1
        dd_c = float((nav / nav.cummax() - 1).min())
        cal_c = ann_c / abs(dd_c) if dd_c < 0 else float('nan')
        sh_c = (float(ex_c.mean() / ex_c.std() * np.sqrt(243.0 / 5))
                if ex_c.std() > 0 else float('nan'))
        ind_ann = E2.apply(lambda s: ((1 + s).cumprod().iloc[-1] ** (1 / yrs) - 1))
        ind_cal, ind_sh = [], []
        for c in E2.columns:
            s = E2[c]
            n2 = (1 + s).cumprod()
            d2 = float((n2 / n2.cummax() - 1).min())
            ind_cal.append((n2.iloc[-1] ** (1 / yrs) - 1) / abs(d2) if d2 < 0 else np.nan)
            ind_sh.append(s.mean() / s.std() * np.sqrt(243.0 / 5) if s.std() > 0 else np.nan)
        ind_cal, ind_sh = pd.Series(ind_cal), pd.Series(ind_sh)
        print()
        print('★ 等权合成对照（{} 个因子）—— ⚠ 与**个体中位/均值**比, 不与"事后最好"比'.format(
            E2.shape[1]))
        print('   {:12s} {:>12s} {:>10s} {:>10s}'.format('', '年化超额', 'Calmar', '夏普'))
        print('   {:12s} {:>11.2f}% {:>10.3f} {:>10.3f}'.format(
            '等权合成', ann_c * 100, cal_c, sh_c))
        print('   {:12s} {:>11.2f}% {:>10.3f} {:>10.3f}'.format(
            '个体中位', ind_ann.median() * 100, ind_cal.median(), ind_sh.median()))
        print('   {:12s} {:>11.2f}% {:>10.3f} {:>10.3f}'.format(
            '个体均值', ind_ann.mean() * 100, ind_cal.mean(), ind_sh.mean()))
        print('   {:12s} {:>11.2f}% {:>10.3f} {:>10.3f}   ← 事后挑选, 有选择偏差'.format(
            '个体最好*', ind_ann.max() * 100, ind_cal.max(), ind_sh.max()))
        lift_c = cal_c / ind_cal.median() if ind_cal.median() else np.nan
        lift_s = sh_c / ind_sh.median() if ind_sh.median() else np.nan
        print('   ⇒ 相对**个体中位**: Calmar **{:.2f}x**, 夏普 **{:.2f}x**'.format(lift_c, lift_s))
        print('   ⇒ 判读: ' + ('✅ **合成有效**（相对个体中位明显提升）'
                              if (np.isfinite(lift_c) and lift_c > 1.2) else
                              '🟡 合成提升有限'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
