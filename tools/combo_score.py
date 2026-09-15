# -*- coding: utf-8 -*-
"""combo_score.py -- 用**合成因子**算分并选股（生产/实盘口径；roadmap §8.36/§8.39）

合成因子就是一个**普通因子面板**（dates x stocks, float32）——
所以你既可以拿它回测（`standard_test.py --fac=...`），也可以拿它**每日算分选股**。
本脚本做后者：给定日期 -> 输出该日合成因子最高的 N 只（默认前 10%）+ 可执行性过滤。

★ 与回测口径的对应关系（`evaluate_real`）
   · 打分：`cs_rank(合成因子)` 取**前 10%**，**等权**持有，每 **FWD=5** 个交易日调仓
   · 可执行性：T 日收盘算分 → **T+1 买入**，剔除 T+1 **涨停/停牌**（买不进）；
     卖出时跌停/停牌顺延（由回测的 `next_sell` 处理）
   · 基准：等权口径（规模中性）与市值加权口径都已在 `combo_check.py` 给出

★ ⚠ 重要：**中性化（neu）版本的成分因子已经先做过市值+成交额秩中性化**，
  所以**不要再对合成因子做一次中性化** —— 那会把选股信号一起削掉。
  公式链见 `_combo_recipe_{raw|neu}.md`。

用法:
  python tools/combo_score.py --fac=tools/_combo_all_neu_B.pkl          # 最新一日
  python tools/combo_score.py --fac=tools/_combo_all_neu_B.pkl --date=20260815 --n=200
  python tools/combo_score.py --fac=... --pool=500 --top=0.10 --csv=tools/_picks.csv
"""
import io
import os
import sys

import numpy as np
import pandas as pd

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'engine'))

import factor_miner as FM           # noqa: E402
import loop_pools as LP             # noqa: E402


def main():
    fac_path = os.path.join(HERE, '_combo_all_neu_B.pkl')
    date = None
    n = None
    top = 0.10
    pool = 'all'
    csv_out = None
    for a in sys.argv[1:]:
        if a.startswith('--fac='):
            fac_path = a.split('=', 1)[1]
        elif a.startswith('--date='):
            date = a.split('=', 1)[1].strip()
        elif a.startswith('--n='):
            n = int(a.split('=', 1)[1])
            top = None
        elif a.startswith('--top='):
            top = float(a.split('=', 1)[1])
            n = None
        elif a.startswith('--pool='):
            pool = a.split('=', 1)[1].strip() or 'all'
        elif a.startswith('--csv='):
            csv_out = a.split('=', 1)[1]

    if not os.path.exists(fac_path):
        print('缺合成因子文件:', fac_path)
        return 1
    fd = pd.read_pickle(fac_path)
    if not isinstance(fd, pd.DataFrame):
        print('文件不是 DataFrame:', type(fd))
        return 1
    print('=' * 78)
    print('合成因子: {}   形状 {}   覆盖 {:.1%}'.format(
        os.path.basename(fac_path), fd.shape, float(np.isfinite(fd.values).mean())))
    fd = fd.astype('float64')

    # ---- 日期 ----
    idx = pd.Index(fd.index)
    if date:
        try:
            d = int(date)
        except ValueError:
            d = int(pd.Timestamp(date).strftime('%Y%m%d'))
        cand = [x for x in idx if int(x) <= d]
        if not cand:
            print('没有 <= {} 的日期'.format(d))
            return 1
        d = int(cand[-1])
    else:
        d = int(idx[-1])
    print('打分日 T = {}   （回测口径: T 日收盘算分 -> T+1 买入, 取前 {} 等权）'.format(
        d, '{:.0%}'.format(top) if n is None else '{} 只'.format(n)))

    row = fd.loc[d].dropna()
    if not len(row):
        print('该日合成因子全为空')
        return 1

    # ---- 池 / 可交易过滤 ----
    dates = np.asarray(fd.index)
    cols = list(fd.columns)
    if pool != 'all':
        try:
            M = LP.pool_mask(pool, dates, cols)
            i = int(np.searchsorted(dates, d))
            mem = M[i]
            keep = set(np.asarray(cols, dtype=object)[mem])
            before = len(row)
            row = row[row.index.isin(keep)]
            print('池 {} 过滤: {} -> {} 只'.format(pool, before, len(row)))
        except Exception as e:
            print('[WARN] 池过滤失败, 不按池过滤: {}: {}'.format(type(e).__name__, e))

    U = FM.get_universe().reindex(index=fd.index, columns=fd.columns).fillna(False)
    un = set(U.loc[d][U.loc[d]].index)
    row = row[row.index.isin(un)]
    print('universe 过滤后: {} 只可选'.format(len(row)))

    # T+1 可买（剔除涨停/停牌）—— 实盘用；回测口径由 evaluate_real 处理
    try:
        TR = FM.get_tradability()
        pos = {int(x): k for k, x in enumerate(np.asarray(fd.index))}
        k1 = pos.get(d, -1) + 1
        if 0 <= k1 < len(dates):
            d1 = int(dates[k1])
            buyable = TR['buyable'][k1]
            col_of = {c: j for j, c in enumerate(cols)}
            ok = set(c for c in row.index if buyable[col_of[c]])
            print('T+1({}) 可买过滤: {} -> {} 只'.format(d1, len(row), len(ok)))
            row = row[row.index.isin(ok)]
    except Exception as e:
        print('[WARN] 可买过滤跳过: {}: {}'.format(type(e).__name__, e))

    if not len(row):
        print('过滤后无可选股票')
        return 1

    # ---- 打分选股 ----
    rank = row.rank(pct=True)
    if n is None:
        n = max(1, int(round(len(row) * (top or 0.10))))
    picks = row.sort_values(ascending=False).head(n)

    print('\n★ 选中 {} 只（该日可选 {} 只的前 {}）'.format(len(picks), len(row),
                                                          '{:.0%}'.format(top) if top else n))
    print('  分数范围: {:.4f} ~ {:.4f}（合成因子值越小=排名越靠前则说明方向反了）'.format(
        picks.iloc[-1], picks.iloc[0]))
    print()
    print('  {:>6s}  {:>12s}  {:>8s}'.format('#', '股票代码', '合成因子值'))
    for i, (code, v) in enumerate(picks.items(), 1):
        if i <= 30:
            print('  {:>6d}  {:>12s}  {:>8.5f}'.format(i, str(code), v))
    if len(picks) > 30:
        print('  ...（共 {} 只，其余见 CSV）'.format(len(picks)))
    # ---- ★ 组合的市值/成交额倾斜：直接看"选中股票"的分布（比"整体秩相关"更贴近实盘） ----
    #   为什么必须看：`lncap` 秩暴露≈0 是**全样本**的秩相关；Top 10% 仍可能倾斜
    #   （非单调暴露对秩相关不敏感）。实盘关心的是**选中股票的市值分布**。
    try:
        MK = FM.load_panel(['mktcap'])['mktcap']
        MK = MK.reindex(index=fd.index, columns=fd.columns).astype('float64')
        pool_mc = MK.loc[d][list(row.index)]
        pct = pool_mc.rank(pct=True)              # 该日在“可选股票”里的市值分位
        p_pick = pct.reindex(picks.index)
        _mc = pool_mc.reindex(picks.index)
        print('\n[市值倾斜] 选中股票在当日可选池内的市值分位：')
        print('   中位 {:.1%}  均值 {:.1%}  （50% = 与池内中位一致；<50% 偏小盘, >50% 偏大盘）'.format(
            float(p_pick.median()), float(p_pick.mean())))
        print('   组合市值中位 {:.1f} 亿   vs  池内中位 {:.1f} 亿'.format(
            float(_mc.median()) / 1e8, float(pool_mc.median()) / 1e8))
        if p_pick.median() < 0.35:
            print('   ⚠ **偏小盘**（分位 {:.0%}）—— 注意风格反转风险'.format(
                float(p_pick.median())))
        elif p_pick.median() > 0.65:
            print('   ⚠ **偏大盘**（分位 {:.0%}）'.format(float(p_pick.median())))
        else:
            print('   ✅ 市值分布与池内接近（无明显倾斜）')
    except Exception as e:
        print('[WARN] 市值倾斜检查跳过: {}: {}'.format(type(e).__name__, e))

    if csv_out:
        pd.DataFrame({'code': picks.index.astype(str), 'score': picks.values}).to_csv(
            csv_out, index=False, encoding='utf-8-sig')
        print('\n已写选股结果 ->', csv_out)
    print()
    print('说明：选股用的就是**合成因子值取前 10% 等权**，不需要再对合成因子做中性化'
          '（neu 版的成分因子已各自中性化过）。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
