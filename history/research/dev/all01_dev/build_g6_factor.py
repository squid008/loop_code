# -*- coding: utf-8 -*-
"""
把 Round7 的 combo_g6 固化为**日频因子面板**, 供 rqalpha 策略(all04)使用
==========================================================================
combo_g6 = 等权 rank(inc_op_profit_qoq, inc_total_rev_qoq, sq_op_yoy,
                    sq_np_yoy2, ocf_to_asset)
输出三个口径(Round7 验证: barra 最好, lnmc 次之, raw 有明显市值倾斜):
  raw   : cs_rank(combo)                       —— 有大盘倾斜, 仅作对照
  lnmc  : cs_rank( 对 ln(市值) 回归取残差 )       —— 2013 起可得
  barra : cs_rank( 对 BARRA size+31行业 取残差 ) —— 2017-01 起可得(申万行业数据起点)

无未来函数保证:
  1) 财报值来自 PIT, 按【公告日 info_date】生效(round5_fund.FundPanels)
  2) 截面 rank / 中性化回归 每个交易日只用"当日已披露"的数据
  3) 中性化用的市值与行业哑变量均为当日值(barra.h5 为逐日行业归属)
输出: strategies/all04/g6_daily.pkl = {'raw': df, 'lnmc': df, 'barra': df}
      df: DataFrame(index=交易日int, columns=obid, float32)
"""
import os
import sys
import gc
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from factor_miner import load_panel, cs_rank
from round5_fund import FundPanels, BarraNeut, cs_neutralize_lnmc
from round7_growth import build_components, G6

DEV = os.path.dirname(os.path.abspath(__file__))
GRID = os.path.join(DEV, 'fund_grid_jq.pkl')
OUT_DIR = r'd:\rqalpha_demo\strategies\all04'
OUT = os.path.join(OUT_DIR, 'g6_daily.pkl')


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    P = load_panel(['close', 'mktcap'])
    close = P['close']
    dates = close.index.values
    cols = list(close.columns)
    mkt = P['mktcap'].reindex(index=dates, columns=cols).values.astype(np.float64)
    print(f"面板: {len(dates)} 日 x {len(cols)} 股  {dates.min()}~{dates.max()}")

    FP = FundPanels(GRID, dates)
    F = build_components(FP)
    acc, n = None, None
    for c in G6:
        rk = cs_rank(pd.DataFrame(F[c], index=dates, columns=cols)).values
        good = np.isfinite(rk)
        acc = np.where(good, rk, 0.0) if acc is None else acc + np.where(good, rk, 0.0)
        n = good.astype(np.float32) if n is None else n + good.astype(np.float32)
        print(f"  + {c:22s} 覆盖 {good.mean()*100:5.1f}%")
        del rk, good
    combo = (acc / np.maximum(n, 1.0)).astype(np.float32)
    combo[n < 1] = np.nan                      # 五个成分全缺 -> NaN(不能当 0)
    print(f"\ncombo 覆盖 {np.isfinite(combo).mean()*100:.1f}%  (每只股票至少一个成分有值)")
    del acc, n, F
    gc.collect()

    raw = cs_rank(pd.DataFrame(combo, index=dates, columns=cols)).values
    print(f"[1/3] raw 完成   覆盖 {np.isfinite(raw).mean()*100:.1f}%")

    lnmc = cs_neutralize_lnmc(raw, mkt)
    lnmc = cs_rank(pd.DataFrame(lnmc, index=dates, columns=cols)).values
    print(f"[2/3] lnmc 完成  覆盖 {np.isfinite(lnmc).mean()*100:.1f}%")
    del combo
    gc.collect()

    BN = BarraNeut(os.path.join(HERE, 'barra.h5'), dates, cols)
    barra = BN(raw)
    barra = cs_rank(pd.DataFrame(barra, index=dates, columns=cols)).values
    print(f"[3/3] barra 完成 覆盖 {np.isfinite(barra).mean()*100:.1f}%")

    out = {}
    for k, v in [('raw', raw), ('lnmc', lnmc), ('barra', barra)]:
        df = pd.DataFrame(v.astype(np.float32), index=dates, columns=cols)
        out[k] = df
        print(f"  {k:6s}: {df.shape}  可用日期 {int(np.isfinite(df.values).any(axis=1).sum())} "
              f"(首 {df.index[np.isfinite(df.values).any(axis=1)][0]})")
    with open(OUT, 'wb') as f:
        pd.to_pickle(out, f, protocol=4)
    print(f"\n已保存 {OUT}  ({os.path.getsize(OUT)/1e6:.1f} MB)")

    # 自检
    s = '000651.XSHE'
    if s in out['barra'].columns:
        v = out['barra'][s].dropna()
        print(f"\n自检 {s} barra: 有值 {len(v)} 日, 首日 {v.index[0]}")
    # Tick 测试: 某只股票在公告日前后的因子值不应跳变
    print("\n逐日可用股票数(抽样):")
    for d in [20141008, 20161010, 20180102, 20210301, 20260805]:
        i = int(np.searchsorted(dates, d, 'left'))
        if i < len(dates):
            print(f"  {dates[i]}: lnmc {int(np.isfinite(lnmc[i]).sum())} 只, "
                  f"barra {int(np.isfinite(barra[i]).sum())} 只")


if __name__ == '__main__':
    main()
