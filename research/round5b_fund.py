# -*- coding: utf-8 -*-
"""
Round 5b: 财报因子(单季口径 + 业绩超预期)
=========================================
Round5 用的是 YTD 累计同比(噪声大)。本轮改为**单季**口径:
  单季值 sq(q) = YTD(q) - YTD(q-1)   (Q1 时 sq = YTD)
  TTM 差 也用 TTM(q) - TTM(q-1) 得到"单季滚动增量"
因子:
  sq_np_yoy / sq_rev_yoy    单季归母净利/营收同比(q vs q-4)
  sq_np_qoq / sq_rev_qoq    单季环比(q vs q-1)
  ttm_np_chg / ttm_rev_chg / ttm_cfo_chg   TTM 环比变化率
  sue_np                    标准化业绩惊喜 (sq - sq_去年同季)/std(近8季单季)
  sq_margin / sq_margin_chg 单季净利率及其同比变化
  sq_gp_margin              单季毛利率
三组检验: raw / ln市值中性 / BARRA(size+31行业)中性
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
from factor_miner import load_panel, evaluate, pass_filter, cs_rank, START
from round5_fund import FundPanels, BarraNeut, cs_neutralize_lnmc, sd, log

DEV = os.path.join(HERE, 'all01_dev')
GRID = os.path.join(DEV, 'fund_grid.pkl')
OUT_CSV = os.path.join(HERE, 'round5b_fund.csv')
OUT_IC = os.path.join(HERE, 'ic_round5b.pkl')

t0 = time.time()


def ratio(a, b):
    """比值 a/b, 分母过小时置 NaN"""
    b = np.where(np.abs(b) > 1e-6, b, np.nan)
    return sd(a, b)


def growth(a, b):
    """增长率 (a-b)/|b|, 分母过小时置 NaN; 用绝对值缩放, 负基数也不失真"""
    b = np.where(np.abs(b) > 1e-6, b, np.nan)
    return sd(a - b, np.abs(b))


def make_sq(FP):
    """返回 (sq, sq_lag): 单季值 = YTD(q) - YTD(q-1), Q1 时单季=YTD, 缺上期则 NaN"""
    g = FP.daily
    q1 = FP.is_q1

    def sq(field):
        y = g(field)
        y1 = g(field, 1)
        return (y - np.where(q1(field), np.float32(0.0), y1)).astype(np.float32)

    def sq_lag(field, n):
        y = g(field, n)
        y1 = g(field, n + 1)
        return (y - np.where(q1(field), np.float32(0.0), y1)).astype(np.float32)

    return sq, sq_lag


def gen_factors(FP):
    g = FP.daily
    sq, sq_lag = make_sq(FP)

    # ---- 单季同比/环比 ----
    s_np, s_rev = sq('net_profit_parent_company'), sq('operating_revenue')
    yield 'sq_np_yoy', growth(s_np, sq_lag('net_profit_parent_company', 4))
    yield 'sq_rev_yoy', growth(s_rev, sq_lag('operating_revenue', 4))
    yield 'sq_np_qoq', growth(s_np, sq_lag('net_profit_parent_company', 1))
    yield 'sq_rev_qoq', growth(s_rev, sq_lag('operating_revenue', 1))
    del s_np, s_rev
    gc.collect()

    # ---- TTM 环比变化率(单季滚动增量 / 上期TTM) ----
    for fld, nm in [('net_profitTTM', 'ttm_np_chg'),
                    ('operating_revenueTTM', 'ttm_rev_chg'),
                    ('net_operate_cashflowTTM', 'ttm_cfo_chg'),
                    ('gross_profitTTM', 'ttm_gp_chg')]:
        a, b = g(fld), g(fld, 1)
        yield nm, growth(a, b)

    # ---- SUE: 标准化业绩惊喜 ----
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
    yield 'sue_np', np.where(std > 1e-6, (s0 - s4) / np.where(std > 1e-6, std, 1), np.nan).astype(np.float32)
    del acc, acc2, cnt, mean, std, s0, s4
    gc.collect()

    # ---- 单季利润率 ----
    s_np = sq('net_profit_parent_company')
    s_rev = sq('operating_revenue')
    m_now = ratio(s_np, s_rev)
    yield 'sq_margin', m_now
    m_1 = ratio(sq_lag('net_profit_parent_company', 4), sq_lag('operating_revenue', 4))
    yield 'sq_margin_chg', (m_now - m_1).astype(np.float32)
    del s_np, s_rev, m_now, m_1
    gc.collect()

    gp0, gp1 = g('gross_profitTTM'), g('gross_profitTTM', 1)
    rv0, rv1 = g('operating_revenueTTM'), g('operating_revenueTTM', 1)
    yield 'sq_gp_margin', ratio(gp0 - gp1, rv0 - rv1)
    del gp0, gp1, rv0, rv1
    gc.collect()


def main():
    log("[1] 载入面板")
    P = load_panel(['close', 'mktcap'])
    close = P['close'].astype('float64')
    dates = close.index.values
    cols = list(close.columns)
    mkt = P['mktcap'].reindex(index=close.index, columns=cols).values.astype(np.float32)
    FP = FundPanels(GRID, dates)
    BN = BarraNeut(os.path.join(HERE, 'barra.h5'), dates, cols)

    log("[2] 三组检验")
    rows, ic_store = [], {}
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    for nf0, (name, arr) in enumerate(gen_factors(FP), 1):
        if lim and nf0 > lim:
            break
        fac = pd.DataFrame(arr, index=dates, columns=cols)
        cov = float(np.isfinite(arr).mean())
        for mode in ['raw', 'lnmc', 'barra']:
            if mode == 'raw':
                X = fac.values
            elif mode == 'lnmc':
                X = cs_neutralize_lnmc(fac.values, mkt.astype(np.float64))
            else:
                X = BN(fac.values)
            if not np.isfinite(X).any():
                continue
            f = cs_rank(pd.DataFrame(X, index=dates, columns=cols))
            r = evaluate(f, close, name)
            del f, X
            if r is None:
                continue
            ic_store[f'{name}|{mode}'] = r.pop('ic_series')
            ok, msg = pass_filter(r)
            r['mode'] = mode
            r['cov'] = cov
            r['pass'] = 'PASS' if ok else msg[:36]
            rows.append(r)
            gc.collect()
        for x in [x for x in rows if x['name'] == name]:
            log(f"  [{nf0:>2}] {name:16s} {x['mode']:5s} cov={cov*100:4.1f}% "
                f"IC={x['ic']:+.4f} IR={x['ic_ir']:+.3f} 超额={x['ann_ex']*100:+6.2f}% "
                f"Calmar={x['calmar'] if x['calmar'] else 0:5.2f} | {x['pass']}")
        del fac, arr
        gc.collect()

    res = pd.DataFrame(rows)
    res.to_csv(OUT_CSV, index=False, encoding='utf-8-sig')
    with open(OUT_IC, 'wb') as f:
        pickle.dump(ic_store, f)
    for mode in ['raw', 'lnmc', 'barra']:
        sub = res[res['mode'] == mode].sort_values('ann_ex', ascending=False)
        if not len(sub):
            continue
        log("\n" + "=" * 96)
        log(f"Round5b 单季/超预期因子 [{mode}]  通过 {(sub['pass']=='PASS').sum()}/{len(sub)}")
        log("=" * 96)
        log(sub[['name', 'ic', 'ic_ir', 'ic_win', 'ann_ex', 'dd', 'calmar',
                 'last_yr', 'cov', 'pass']].round(4).to_string(index=False))
    log(f"\n已保存 {OUT_CSV}   耗时 {time.time()-t0:.0f}s")


if __name__ == '__main__':
    main()
