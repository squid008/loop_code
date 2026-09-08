# -*- coding: utf-8 -*-
"""广发双重同伴效应(Dual Peer Effect)验证
===========================================
方法(移植广发, 网络=申万31一级行业, 每日归属):
  对基准因子 f(已截面rank) 拆成:
    peer_avg[j] = 同行业其他股票的 f 均值(不含自己)   -> 同伴/板块效应
    peer_dev[j] = f[j] - peer_avg[j]                  -> 个体偏离(已去板块)
  组合因子 H_w = cs_rank(peer_dev + w * peer_avg)      (允许两成分不同权重 w)
检验(费后 evaluate_real, cost=单边千1.5档):
  原因子 vs peer_avg / peer_dev / 不同 w 组合。
  关注: ① 已失效因子(rev20/vol60)能否被拆出可用的板块+个体信号?
        ② 强因子(ln_mktcap)拆分是否更稳?
运行: D:\miniconda3\envs\rqdata\python.exe peer_effect.py
"""
import time
import numpy as np
import pandas as pd
import factor_miner as FM
import ml_common as MC

FWD = 5
COST = FM.COST_PRESETS['单边千1.5']     # 0.004 往返
W_GRID = [0.0, 0.3, 0.6, 1.0]           # 0.0 = 纯个体偏离


def peer_split(rf, G):
    """rf: DataFrame(截面rank). 返回 peer_avg, peer_dev (同构DataFrame)"""
    vals = rf.values
    Gv = G
    T, S = vals.shape
    avg = np.full_like(vals, np.nan, dtype=np.float64)
    dev = np.full_like(vals, np.nan, dtype=np.float64)
    for t in range(T):
        g = Gv[t]
        f = vals[t]
        m = np.isfinite(f) & (g >= 0)
        if m.sum() < 30:
            continue
        gg = g[m]
        ff = f[m]
        sm = np.bincount(gg, weights=ff, minlength=32)
        cn = np.bincount(gg, minlength=32)
        # 同行均值(不含自己)
        a = (sm[g[m]] - ff) / np.maximum(cn[g[m]] - 1, 1)
        avg[t][m] = a
        dev[t][m] = ff - a
    return pd.DataFrame(avg, index=rf.index, columns=rf.columns), \
        pd.DataFrame(dev, index=rf.index, columns=rf.columns)


def make_base_factors(P, cols):
    """日频基础因子(列=comm cols)。正值=预期收益高的方向(做多)。"""
    close = P['close']
    mc = P['mktcap']
    ret = close.pct_change()
    out = {
        # 小市值: 已知费后最强(正)
        'ln_mktcap(小市值)': -np.log(mc),
        # 20日反转: 已知费后为负(失效基准)
        'rev20(反转)': -(close / close.shift(20) - 1.0),
        # 低波动60: 已知费后为负(失效基准)
        'lvol60(低波)': -ret.rolling(60, min_periods=30).std(),
    }
    return out


def main():
    t0 = time.time()
    ML = MC.load()
    dates, comm = ML['dates'], ML['cols']
    G = ML['G']
    P = {k: v.reindex(index=dates, columns=comm) for k, v in ML['P'].items()}
    print(f"数据 {len(dates)}日 x {len(comm)}股 {time.time()-t0:.1f}s")

    FM.close_full = None
    panel = FM.load_panel(['close'])
    close_full = panel['close'].astype('float64')
    F = make_base_factors(P, comm)
    print(f"基准因子: {list(F.keys())}")

    rows = []
    for nm, fac in F.items():
        rf = FM.cs_rank(fac)                       # 0~1 截面rank
        avg, dev = peer_split(rf, G)
        # 组合: 先对 dev+w*avg 做截面 rank 再评估(内部再 qcut)
        def ev(f, tag):
            r = FM.evaluate_real(f.reindex(index=dates), close_full,
                                 f"{nm}|{tag}", cost=COST, window='full')
            if r is None:
                return
            rows.append(dict(
                factor=nm, variant=tag, ic=r['ic'], ic_ir=r['ic_ir'],
                ann_ex=r['ann_ex'] * 100, calmar=r['calmar']
                if r['calmar'] else 0, sharpe=r['sharpe'],
                turn=r.get('turn', np.nan) * 100,
                neg_yr=sum(1 for v in r['yr'].values() if v <= -0.02),
                last_yr=r['last_yr'] * 100))
            print(f"  [{nm}|{tag}] IC={r['ic']:+.4f} 超额={r['ann_ex']*100:+6.2f}% "
                  f"Calmar={r['calmar'] if r['calmar'] else 0:5.2f} "
                  f"换手={r.get('turn', np.nan)*100:4.1f}% 负年={rows[-1]['neg_yr']}")

        ev(rf, '原始')
        ev(avg, 'peer_avg(板块)')
        ev(dev, 'peer_dev(个体)')
        for w in W_GRID:
            if w == 0.0:
                continue
            comp = FM.cs_rank(dev.add(avg * w, axis=0))
            ev(comp, f'组合w={w:.1f}')

    res = pd.DataFrame(rows)
    print("\n===== 汇总(按因子分组, 费后 2018起, 往返成本0.4%) =====")
    for nm, g in res.groupby('factor'):
        print(f"\n[{nm}]")
        g2 = g.sort_values('ann_ex', ascending=False)
        for _, r in g2.iterrows():
            print(f"  {r['variant']:16s} IC={r['ic']:+.4f} 超额={r['ann_ex']:+6.2f}% "
                  f"Calmar={r['calmar']:5.2f} 夏普={r['sharpe']:5.2f} "
                  f"换手={r['turn']:4.1f}% 最近年={r['last_yr']:+.1f}% 负年={int(r['neg_yr'])}")
    print(f"\ntotal {time.time()-t0:.0f}s")


if __name__ == '__main__':
    main()
