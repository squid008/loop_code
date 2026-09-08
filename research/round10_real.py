# -*- coding: utf-8 -*-
"""
Round10: 【费后/可实现性】口径重检关键因子
============================================
背景: 研究框架 evaluate() 系统性高估约 5~8pp(见 factor_roadmap.md Round10 标定),
      本轮用 evaluate_real() 重检, 该口径包含:
        1) T+1 买入日剔除涨停/停牌(买不进的不算)
        2) 卖出日跌停/停牌顺延到下一个可卖日
        3) 按实际换手率扣往返成本 0.5%(佣金千二双边 + 印花税千一)
      只有【费后仍有超额】的因子才配叫"可用"。

检验对象(各轮代表 + all03 在用的):
  基准类 : ln_mktcap(小市值) / amt_log(小成交额)      <- all03 现有收益来源
  量价类 : rev_20d(反转) / vol60(低波)
  财报类 : net_margin_ttm / roe_ttm / roic_ttm
  聚宽类 : inc_op_profit_qoq / sq_op_yoy / ocf_to_asset
  复合   : combo_g6 / combo_growth
四口径: raw / lnmc(B) / barra(B) / strat(D)
"""
import os
import sys
import gc
import time
import pickle
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from factor_miner import (load_panel, prepare, cs_rank, evaluate, evaluate_real,
                          get_tradability)
from round5_fund import (FundPanels, BarraNeut, cs_neutralize_lnmc, sd, log,
                         build_size_bucket, strat_rank, ind_demean)
from round5b_fund import make_sq, growth, ratio
from round7_growth import build_components, G6, G5B

DEV = os.path.join(HERE, 'all01_dev')
GRID = os.path.join(DEV, 'fund_grid_jq.pkl')
OUT_CSV = os.path.join(HERE, 'round10_real.csv')
NB = 20
t0 = time.time()


def build_all(P, FP):
    """返回 {name: (T,S) 因子面板}"""
    close = P['close']
    dates = close.index.values
    cols = list(close.columns)
    amt = P['turnover'].reindex(index=dates, columns=cols)
    F = {}

    # ---- 量价 ----
    F['ln_mktcap'] = (-np.log(P['mktcap'].reindex(index=dates, columns=cols)
                              .astype('float64'))).values.astype(np.float32)
    F['amt_log'] = (-np.log(amt.rolling(20, min_periods=10).mean() + 1.0)).values.astype(np.float32)
    F['rev_20d'] = (-(close / close.shift(20) - 1.0)).values.astype(np.float32)
    F['vol60'] = (-close.pct_change().rolling(60, min_periods=30).std()).values.astype(np.float32)
    gc.collect()

    # ---- 财报/聚宽(复用 round7 成分) ----
    C = build_components(FP)
    for k in ['net_margin_ttm']:
        pass
    # 财报三兄弟单独构造
    g = FP.daily
    F['net_margin_ttm'] = sd(g('net_profitTTM'), g('operating_revenueTTM'))
    F['roe_ttm'] = sd(g('np_parent_company_ownersTTM'), g('equity_parent_company'))
    F['roic_ttm'] = sd(g('ebitTTM'), g('total_assets') - g('current_liabilities'))
    for k in ['inc_op_profit_qoq', 'sq_op_yoy', 'ocf_to_asset']:
        F[k] = C[k]
    # 复合
    def combo(names):
        acc, n = None, None
        for c in names:
            rk = cs_rank(pd.DataFrame(C[c], index=dates, columns=cols)).values
            good = np.isfinite(rk)
            acc = np.where(good, rk, 0.0) if acc is None else acc + np.where(good, rk, 0.0)
            n = good.astype(np.float32) if n is None else n + good.astype(np.float32)
        return (acc / np.maximum(n, 1.0)).astype(np.float32)
    F['combo_g6'] = combo(G6)
    F['combo_growth'] = combo(G5B)
    del C
    gc.collect()
    return F


def main():
    log("[1] 载入 + 预计算可交易性")
    P = load_panel(['close', 'mktcap', 'turnover'])
    close = P['close'].astype('float64')
    dates = close.index.values
    cols = list(close.columns)
    mkt = P['mktcap'].reindex(index=dates, columns=cols).values.astype(np.float64)
    TR = get_tradability()
    log(f"  可买比例 {TR['buyable'].mean()*100:.1f}%  (涨停/停牌被剔)")

    FP = FundPanels(GRID, dates)
    BN = BarraNeut(os.path.join(HERE, 'barra.h5'), dates, cols)
    bkt = build_size_bucket(mkt.astype(np.float32), NB)

    log("[2] 构造因子")
    F = build_all(P, FP)

    log("[3] 费后检验(四口径) —— 与旧口径对照")
    rows = []
    for nm in ['ln_mktcap', 'amt_log', 'rev_20d', 'vol60',
               'net_margin_ttm', 'roe_ttm', 'roic_ttm',
               'inc_op_profit_qoq', 'sq_op_yoy', 'ocf_to_asset',
               'combo_g6', 'combo_growth']:
        fac = pd.DataFrame(F[nm], index=dates, columns=cols)
        rk = cs_rank(fac).values
        for mode in ['raw', 'lnmc', 'barra', 'strat']:
            if mode == 'raw':
                X = rk
            elif mode == 'lnmc':
                X = cs_neutralize_lnmc(rk, mkt)
            elif mode == 'barra':
                X = BN(rk)
            else:
                X = ind_demean(strat_rank(rk, bkt, NB), BN)
            X = np.asarray(X, dtype=np.float64)
            f = cs_rank(pd.DataFrame(X, index=dates, columns=cols))
            r_new = evaluate_real(f, close, nm)
            r_old = evaluate(f, close, nm)
            del X, f
            gc.collect()
            if r_new is None or r_old is None:
                continue
            rows.append(dict(name=nm, mode=mode,
                             费后超额=r_new['ann_ex'], 费后Calmar=r_new['calmar'],
                             费后回撤=r_new['dd'], 换手=r_new.get('turn', np.nan),
                             旧口径超额=r_old['ann_ex'],
                             损耗=(r_old['ann_ex'] - r_new['ann_ex']),
                             ic=r_new['ic'], ic_ir=r_new['ic_ir'],
                             最近年=r_new['last_yr']))
            log(f"  {nm:18s} {mode:5s} 旧 {r_old['ann_ex']*100:+6.2f}% -> "
                f"费后 {r_new['ann_ex']*100:+6.2f}%  (损耗 "
                f"{(r_old['ann_ex']-r_new['ann_ex'])*100:5.2f}pp) "
                f"Calmar {r_new['calmar'] if r_new['calmar'] else 0:5.2f} "
                f"换手 {r_new.get('turn', np.nan)*100:4.1f}%")
        del fac, rk
        gc.collect()

    res = pd.DataFrame(rows)
    res.to_csv(OUT_CSV, index=False, encoding='utf-8-sig')

    log("\n[4] 结论: 费后仍有正超额且 Calmar>0.5 的因子")
    ok = res[(res['费后超额'] > 0) & (res['费后Calmar'] > 0.5)]
    if len(ok):
        log(ok.round(4).to_string(index=False))
    else:
        log("  (无)")
    log("\n[5] 损耗统计")
    log(res.groupby('mode')['损耗'].describe().round(4).to_string())
    log(f"\n已保存 {OUT_CSV}   耗时 {time.time()-t0:.0f}s")


if __name__ == '__main__':
    main()
