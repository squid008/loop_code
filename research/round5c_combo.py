# -*- coding: utf-8 -*-
"""
Round 5c: 财报批次收尾 —— 盈利/成长族**复合因子**检验
======================================================
Round5/5b 单因子几乎全军覆没, 但两个方向有稳定正超额(市值中性后):
  盈利质量: net_margin_ttm +5.75%(PASS) / op_margin_ttm +4.93%(PASS)
            / sq_margin +8.20%(仅最近年超额-1.6%未过)
  单季成长: sq_np_yoy +4.31% / ttm_np_chg +3.67%
本轮:
  1. 复合: combo_margin(3个利润率) / combo_profit(7个盈利) / combo_growth(5个单季成长)
  2. 输出成分间 IC 相关性(避免重复计数)
  3. 三组检验: raw / ln市值中性 / BARRA(size+行业)中性
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
from round5_fund import FundPanels, BarraNeut, cs_neutralize_lnmc, sd, log
from round5b_fund import make_sq, growth, ratio

DEV = os.path.join(HERE, 'all01_dev')
GRID = os.path.join(DEV, 'fund_grid.pkl')
OUT_CSV = os.path.join(HERE, 'round5c_combo.csv')

t0 = time.time()

PROFIT = ['net_margin_ttm', 'op_margin_ttm', 'sq_margin', 'roic_ttm',
          'roe_ttm', 'roa_ttm', 'gp_asset']
MARGIN = ['net_margin_ttm', 'op_margin_ttm', 'sq_margin']
GROWTH = ['sq_np_yoy', 'ttm_np_chg', 'sq_rev_yoy', 'ttm_rev_chg', 'sue_np']


def build(FP, mkt):
    g = FP.daily
    sq, sq_lag = make_sq(FP)
    F = {}
    ni_ttm = g('net_profitTTM')
    rev_ttm = g('operating_revenueTTM')
    F['net_margin_ttm'] = sd(ni_ttm, rev_ttm)
    F['op_margin_ttm'] = sd(g('operating_profitTTM'), rev_ttm)
    F['roic_ttm'] = sd(g('ebitTTM'), g('total_assets') - g('current_liabilities'))
    F['roe_ttm'] = sd(g('np_parent_company_ownersTTM'), g('equity_parent_company'))
    F['roa_ttm'] = sd(ni_ttm, g('total_assets'))
    F['gp_asset'] = sd(g('gross_profitTTM'), g('total_assets'))
    s_np, s_rev = sq('net_profit_parent_company'), sq('operating_revenue')
    F['sq_margin'] = ratio(s_np, s_rev)
    del s_np, s_rev
    gc.collect()
    snp4 = sq_lag('net_profit_parent_company', 4)
    srv4 = sq_lag('operating_revenue', 4)
    F['sq_np_yoy'] = growth(sq('net_profit_parent_company'), snp4)
    F['sq_rev_yoy'] = growth(sq('operating_revenue'), srv4)
    del snp4, srv4
    gc.collect()
    for fld, nm in [('net_profitTTM', 'ttm_np_chg'),
                    ('operating_revenueTTM', 'ttm_rev_chg')]:
        a, b = g(fld), g(fld, 1)
        F[nm] = growth(a, b)
        del a, b
    # SUE
    s0 = sq('net_profit_parent_company')
    s4 = sq_lag('net_profit_parent_company', 4)
    acc = np.zeros_like(s0)
    acc2 = np.zeros_like(s0)
    cnt = np.zeros_like(s0)
    for n in range(1, 9):
        v = sq_lag('net_profit_parent_company', n)
        m = np.isfinite(v)
        acc += np.where(m, v, 0.0)
        acc2 += np.where(m, v * v, 0.0)
        cnt += m
        del v, m
    cnt = np.maximum(cnt, 1)
    mean = acc / cnt
    std = np.sqrt(np.maximum(acc2 / cnt - mean * mean, 0))
    F['sue_np'] = np.where(std > 1e-6, (s0 - s4) / np.where(std > 1e-6, std, 1),
                           np.nan).astype(np.float32)
    return F


def main():
    log("[1] 载入")
    P = load_panel(['close', 'mktcap'])
    close = P['close'].astype('float64')
    dates = close.index.values
    cols = list(close.columns)
    mkt = P['mktcap'].reindex(index=close.index, columns=cols).values.astype(np.float32)
    FP = FundPanels(GRID, dates)
    BN = BarraNeut(os.path.join(HERE, 'barra.h5'), dates, cols)

    log("[2] 构造成分因子")
    F = build(FP, mkt)
    ic_store = {}
    rows = []

    def run(nm, arr):
        fac = pd.DataFrame(arr, index=dates, columns=cols)
        for mode in ['raw', 'lnmc', 'barra']:
            if mode == 'raw':
                X = fac.values
            elif mode == 'lnmc':
                X = cs_neutralize_lnmc(fac.values, mkt.astype(np.float64))
            else:
                X = BN(fac.values)
            f = cs_rank(pd.DataFrame(X, index=dates, columns=cols))
            r = evaluate(f, close, nm)
            ic_store[f'{nm}|{mode}'] = r.pop('ic_series') if r else None
            del f, X
            if r is None:
                continue
            ok, msg = pass_filter(r)
            r['mode'] = mode
            r['pass'] = 'PASS' if ok else msg[:40]
            rows.append(r)
            log(f"  {nm:16s} {mode:5s} IC={r['ic']:+.4f} IR={r['ic_ir']:+.3f} "
                f"超额={r['ann_ex']*100:+6.2f}% 回撤={r['dd']*100:5.1f}% "
                f"Calmar={r['calmar'] if r['calmar'] else 0:5.2f} | {r['pass']}")
            gc.collect()
        del fac

    log("[3] 单成分复检(对齐 round5/5b 口径)")
    for nm in PROFIT + ['sq_np_yoy', 'ttm_np_chg']:
        run(nm, F[nm])

    log("\n[4] 复合因子")
    for nm, comp in [('combo_margin', MARGIN), ('combo_profit', PROFIT),
                     ('combo_growth', GROWTH)]:
        acc = None
        for c in comp:
            rk = cs_rank(pd.DataFrame(F[c], index=dates, columns=cols)).values
            acc = rk if acc is None else acc + rk
            del rk
        arr = (acc / len(comp)).astype(np.float32)
        del acc
        gc.collect()
        run(nm, arr)
        del arr
        gc.collect()

    res = pd.DataFrame(rows)
    res.to_csv(OUT_CSV, index=False, encoding='utf-8-sig')
    with open(os.path.join(HERE, 'ic_round5c.pkl'), 'wb') as f:
        pickle.dump(ic_store, f)

    log("\n[5] 成分 IC 相关性(barra 中性化后)")
    keys = [k for k in ic_store if k.endswith('|barra') and
            k.split('|')[0] in PROFIT + GROWTH]
    m = pd.DataFrame({k.split('|')[0]: ic_store[k] for k in keys}).dropna(how='all')
    corr = m.corr(min_periods=200).round(2)
    log(corr.to_string())

    log("\n[6] 汇总")
    sub = res[res['name'].str.startswith('combo')]
    log(sub[['name', 'mode', 'ic', 'ic_ir', 'ann_ex', 'dd', 'calmar',
             'last_yr', 'pass']].round(4).to_string(index=False))
    log(f"\n已保存 {OUT_CSV}  耗时 {time.time()-t0:.0f}s")


if __name__ == '__main__':
    main()
