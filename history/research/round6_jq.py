# -*- coding: utf-8 -*-
"""
Round 6: 聚宽(JQ)因子批次 —— JQ indicator/valuation 风格因子
=============================================================
数据源: 米筐 PIT 扩展字段(fund_grid_jq.pkl, 45字段), 按 info_date 展开(无未来函数)
口径(见 factor_roadmap.md 「检验口径规范」):
  raw   : 原始因子(截面rank)
  lnmc  : B口径 —— rank 后对 ln(市值) 中性化
  barra : B口径 —— rank 后对 BARRA size+31行业 中性化
  strat : D口径 —— 市值20层内rank(非参数完全剥离市值) + 行业内demean
判定: **barra 与 strat 同向且都过门槛** 才算有效
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
from factor_miner import load_panel, evaluate, pass_filter, cs_rank
from round5_fund import (FundPanels, BarraNeut, cs_neutralize_lnmc, sd, log,
                         build_size_bucket, strat_rank, ind_demean)
from round5b_fund import growth, ratio

DEV = os.path.join(HERE, 'all01_dev')
GRID = os.path.join(DEV, 'fund_grid_jq.pkl')
OUT_CSV = os.path.join(HERE, 'round6_jq.csv')
OUT_IC = os.path.join(HERE, 'ic_round6.pkl')
NB = 20

t0 = time.time()


def gen_factors(FP):
    g = FP.daily

    def ttm_sq(fld, lag=0):
        """TTM 差 = 单季值(滚动), lag 个季度之前"""
        return g(fld, lag) - g(fld, lag + 1)

    # ---------- A. 平均余额口径盈利(JQ indicator 定义) ----------
    eq, eq4 = g('equity_parent_company'), g('equity_parent_company', 4)
    ta, ta4 = g('total_assets'), g('total_assets', 4)
    avg_eq = (np.nan_to_num(eq, nan=np.nan) + eq4) / 2.0
    avg_ta = (ta + ta4) / 2.0
    yield 'roe_avg', ratio(g('np_parent_company_ownersTTM'), avg_eq)
    yield 'roa_avg', ratio(g('net_profitTTM'), avg_ta)
    del eq, eq4, ta, ta4, avg_eq, avg_ta
    gc.collect()

    # ---------- B. 费用率(负向: 费用率越低越好) ----------
    rev_ttm = g('total_operating_revenueTTM')
    yield 'sell_exp_neg', -ratio(g('selling_expense'), g('operating_revenue'))
    yield 'admin_exp_neg', -ratio(g('administration_expenseTTM'), rev_ttm)
    yield 'fin_exp_neg', -ratio(g('financial_expenseTTM'), rev_ttm)
    yield 'op_exp_neg', -ratio(g('operating_expenseTTM'), rev_ttm)
    yield 'total_cost_neg', -ratio(g('total_operating_costTTM'), rev_ttm)
    yield 'gp_margin2', ratio(g('gross_profitTTM'), rev_ttm)
    del rev_ttm
    gc.collect()

    # ---------- C. 现金流质量 / 偿债 ----------
    cfo = g('net_operate_cashflowTTM')
    yield 'ocf_to_revenue', ratio(cfo, g('operating_revenueTTM'))
    yield 'ocf_to_opprofit', ratio(cfo, g('operating_profitTTM'))
    yield 'sale_cash_to_rev', ratio(g('cash_received_from_sales_of_goods'),
                                    g('operating_revenue'))
    yield 'cash_ratio', ratio(g('cash_equivalent'), g('current_liabilities'))
    yield 'quick_ratio', ratio(g('current_assets') - g('inventory'),
                               g('current_liabilities'))
    yield 'ocf_to_asset', ratio(cfo, g('total_assets'))
    del cfo
    gc.collect()

    # ---------- D. 利润构成 ----------
    tp = g('total_profitTTM')
    yield 'op_profit_to_profit', ratio(g('operating_profitTTM'), tp)
    yield 'inv_profit_neg', -ratio(g('ni_from_value_changeTTM'), tp)
    yield 'ded_to_profit', ratio(g('net_profit_deduct_non_recurring_pnl'),
                                 g('net_profit'))
    yield 'op_profit_to_asset', ratio(g('operating_profitTTM'), g('total_assets'))
    del tp
    gc.collect()

    # ---------- E. 成长(TTM 口径同比/环比 + 单季) ----------
    for fld, nm in [('total_operating_revenueTTM', 'inc_total_rev'),
                    ('operating_revenueTTM', 'inc_rev'),
                    ('operating_profitTTM', 'inc_op_profit'),
                    ('net_profitTTM', 'inc_np'),
                    ('np_parent_company_ownersTTM', 'inc_np_sh')]:
        yield nm + '_yoy', growth(g(fld), g(fld, 4))
    yield 'inc_total_rev_qoq', growth(g('total_operating_revenueTTM'),
                                      g('total_operating_revenueTTM', 1))
    yield 'inc_op_profit_qoq', growth(g('operating_profitTTM'),
                                      g('operating_profitTTM', 1))
    yield 'sq_op_yoy', growth(ttm_sq('operating_profitTTM', 0),
                              ttm_sq('operating_profitTTM', 4))
    yield 'sq_np_yoy2', growth(ttm_sq('net_profitTTM', 0),
                               ttm_sq('net_profitTTM', 4))
    gc.collect()

    # ---------- F. 杠杆 / 风险 ----------
    d1 = np.nan_to_num(g('short_term_loans'), nan=0.0)
    d2 = np.nan_to_num(g('long_term_loans'), nan=0.0)
    d3 = np.nan_to_num(g('bond_payable'), nan=0.0)
    cnt = (np.isfinite(g('short_term_loans')).astype(np.float32)
           + np.isfinite(g('long_term_loans')).astype(np.float32)
           + np.isfinite(g('bond_payable')).astype(np.float32))
    int_debt = np.where(cnt > 0, d1 + d2 + d3, np.nan).astype(np.float32)
    yield 'int_debt_neg', -ratio(int_debt, g('total_assets'))
    yield 'debt_to_equity_neg', -ratio(g('total_liabilities'),
                                       g('equity_parent_company'))
    yield 'goodwill_neg', -ratio(g('goodwill'), g('total_assets'))
    del d1, d2, d3, cnt, int_debt
    gc.collect()

    # ---------- G. 研发(低覆盖, 仅参考) ----------
    yield 'rnd_ratio', g('rnd_to_revenue')


def main():
    log("[1] 载入")
    P = load_panel(['close', 'mktcap'])
    close = P['close'].astype('float64')
    dates = close.index.values
    cols = list(close.columns)
    mkt = P['mktcap'].reindex(index=close.index, columns=cols).values.astype(np.float32)
    mkt64 = mkt.astype(np.float64)
    FP = FundPanels(GRID, dates)
    BN = BarraNeut(os.path.join(HERE, 'barra.h5'), dates, cols)
    bkt = build_size_bucket(mkt, NB)
    log(f"  grid 字段 {len(FP.val)}, Q={FP.Q}, S={FP.S}")

    log("[2] 四口径检验(raw / lnmc=B / barra=B / strat=D)")
    rows, ic_store = [], {}
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    for nf, (name, arr) in enumerate(gen_factors(FP), 1):
        if lim and nf > lim:
            break
        fac = pd.DataFrame(arr, index=dates, columns=cols)
        rk = cs_rank(fac).values
        cov = float(np.isfinite(arr).mean())
        for mode in ['raw', 'lnmc', 'barra', 'strat']:
            if mode == 'raw':
                X = rk
            elif mode == 'lnmc':
                X = cs_neutralize_lnmc(rk, mkt64)
            elif mode == 'barra':
                X = BN(rk)
            else:
                X = ind_demean(strat_rank(rk, bkt, NB), BN)
            if not np.isfinite(X).any():
                del X
                continue
            r = evaluate(cs_rank(pd.DataFrame(X, index=dates, columns=cols)),
                         close, name)
            del X
            gc.collect()
            if r is None:
                continue
            ic_store[f'{name}|{mode}'] = r.pop('ic_series')
            ok, msg = pass_filter(r)
            r['mode'] = mode
            r['cov'] = cov
            r['pass'] = 'PASS' if ok else msg[:36]
            rows.append(r)
        for x in [x for x in rows if x['name'] == name]:
            log(f"  [{nf:>2}] {name:20s} {x['mode']:5s} cov={cov*100:4.1f}% "
                f"IC={x['ic']:+.4f} IR={x['ic_ir']:+.3f} 超额={x['ann_ex']*100:+6.2f}% "
                f"Calmar={x['calmar'] if x['calmar'] else 0:5.2f} | {x['pass']}")
        del fac, rk, arr
        gc.collect()

    res = pd.DataFrame(rows)
    res.to_csv(OUT_CSV, index=False, encoding='utf-8-sig')
    with open(OUT_IC, 'wb') as f:
        pickle.dump(ic_store, f)

    for mode in ['raw', 'lnmc', 'barra', 'strat']:
        sub = res[res['mode'] == mode].sort_values('ann_ex', ascending=False)
        if not len(sub):
            continue
        log("\n" + "=" * 96)
        log(f"Round6 聚宽因子 [{mode}]  通过 {(sub['pass']=='PASS').sum()}/{len(sub)}")
        log("=" * 96)
        log(sub[['name', 'ic', 'ic_ir', 'ic_win', 'ann_ex', 'dd', 'calmar',
                 'last_yr', 'cov', 'pass']].round(4).to_string(index=False))

    # 双口径一致性(barra vs strat)
    p = res.pivot_table(index='name', columns='mode', values='ann_ex')
    if 'barra' in p and 'strat' in p:
        both = p[(p['barra'] > 0) & (p['strat'] > 0)].sort_values('barra', ascending=False)
        log("\n" + "=" * 96)
        log("barra 与 strat 双口径同为正(候选)")
        log("=" * 96)
        log(both.round(4).to_string())
    log(f"\n已保存 {OUT_CSV}   耗时 {time.time()-t0:.0f}s")


if __name__ == '__main__':
    main()
