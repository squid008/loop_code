# -*- coding: utf-8 -*-
"""
用 rqalpha 数据构造前复权 / 后复权价, 跑同一个因子, 与 qlib 前复权结果对比。

qlib 参照值(test_adjust_mode.py, forward/backward):
    触发(日截面) 0.7299%   未触发(日截面) 1.0793%   触发样本 51,719

rqalpha 复权构造:
    后复权价 = 真实价 × rqf
    前复权价 = 真实价 × rqf / rqf_end      (rqf_end = 该股最后一个交易日的因子)
    rqf 来自 E:\rq\bundle\ex_cum_factor.h5, 为分段常数(start_date 起生效)

注意: open/high/low/close 与 limit_up/limit_down/prev_close 必须同比例缩放,
      否则涨停判定(close >= limit_up)会失真。
"""
import os
import io
import sys
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd
import h5py

STOCKS = r'E:\rq\bundle\stocks.h5'
FACTOR = r'E:\rq\bundle\ex_cum_factor.h5'
START, END, FWD = 20210101, 20260812, 20
WARMUP = 120

PRICE_COLS = ['open', 'high', 'low', 'close', 'limit_up', 'limit_down', 'prev_close']


def load_factors():
    """读全部标的的复权因子段"""
    segs = {}
    with h5py.File(FACTOR, 'r') as f:
        for k in f.keys():
            a = f[k][:]
            segs[k] = ((a['start_date'] // 1000000).astype('int64'),
                       a['ex_cum_factor'].astype('float64'))
    return segs


def daily_factor(seg, dates):
    """分段常数 -> 每日序列"""
    starts, vals = seg
    order = np.argsort(starts)
    starts, vals = starts[order], vals[order]
    idx = np.searchsorted(starts, dates, side='right') - 1
    idx = np.clip(idx, 0, len(vals) - 1)
    return vals[idx]


def apply_adj(arr, fac):
    """按因子缩放价格列(含涨跌停价, 保证涨停判定不受影响)"""
    out = arr.copy()
    for c in PRICE_COLS:
        if c in out.dtype.names:
            out[c] = arr[c] * fac
    return out


def main():
    from test import compute_one

    out = sys.stdout
    segs = load_factors()
    print(f"复权因子标的数量: {len(segs)}", file=out)

    with h5py.File(STOCKS, 'r') as f:
        keys = list(f.keys())
        base = (f['000001.XSHE']['datetime'][:] // 1000000).astype('int64')
    pos = int(np.searchsorted(base, START))
    data_start = base[max(0, pos - WARMUP)]
    print(f"读取起点: {data_start}", file=out)

    buckets = {'none': [], 'bwd': [], 'fwd': []}
    n_no_factor = 0
    t0 = time.time()

    with h5py.File(STOCKS, 'r') as f:
        for i, obid in enumerate(keys):
            arr = f[obid][:]
            d = arr['datetime'] // 1000000
            m = (d >= data_start) & (d <= END)
            if m.sum() < WARMUP // 2:
                continue
            sub = arr[m]
            dates = (sub['datetime'] // 1000000).astype('int64')

            if obid in segs:
                rqf = daily_factor(segs[obid], dates)
                rqf_end = rqf[-1] if rqf[-1] != 0 else 1.0
                arr_fwd = apply_adj(sub, rqf / rqf_end)
                arr_bwd = apply_adj(sub, rqf.copy())
            else:
                n_no_factor += 1
                arr_fwd = arr_bwd = sub

            sel_dates = dates
            for tag, a in (('none', sub), ('bwd', arr_bwd), ('fwd', arr_fwd)):
                df = compute_one(a, drop_suspended=False, fwd=FWD)
                df['obid'] = obid
                buckets[tag].append(df[(df['date'] >= START) & (df['date'] <= END)])

            if (i + 1) % 1500 == 0:
                print(f"    ... {i+1}/{len(keys)}  {time.time()-t0:.0f}s", file=out)

    print(f"无复权因子的标的: {n_no_factor}", file=out)

    LABELS = {'none': 'rqalpha 不复权', 'bwd': 'rqalpha 后复权', 'fwd': 'rqalpha 前复权'}

    def stat(df, use_excl):
        if use_excl:
            ex = df['is_lu'] | df['is_lu_t1'] | df['susp_t1']
            df = df[~ex]
        sub = df[['date', 'signal', 'fwd_t1_21']].dropna()
        trig = sub[sub['signal']]['fwd_t1_21']
        notr = sub[~sub['signal']]['fwd_t1_21']
        d_t = sub[sub['signal']].groupby('date')['fwd_t1_21'].mean()
        d_n = sub[~sub['signal']].groupby('date')['fwd_t1_21'].mean()
        se = d_t.std(ddof=1) / (len(d_t) ** 0.5) * 100
        return dict(n=len(trig), pt=trig.mean() * 100, pn=notr.mean() * 100,
                    dt=d_t.mean() * 100, dn=d_n.mean() * 100, days=len(d_t), se=se)

    frames = {tag: pd.concat(buckets[tag], ignore_index=True) for tag in buckets}
    res = {}
    for excl in [False, True]:
        print("\n" + "=" * 108, file=out)
        print(f"rqalpha 三种复权   三重剔除={'开' if excl else '关'}   "
              f"{'(与 qlib 同口径)' if excl else '(此前的不公平对比)'}", file=out)
        print("=" * 108, file=out)
        print(f"  {'来源':<22}{'触发样本':>10}{'触发(观测)':>12}{'触发(日截)':>12}"
              f"{'未触发(日截)':>13}{'SE':>9}{'天数':>7}", file=out)
        print("-" * 108, file=out)
        for tag in ['none', 'bwd', 'fwd']:
            r = stat(frames[tag], excl)
            res[(tag, excl)] = r
            print(f"  {LABELS[tag]:<22}{r['n']:>10,}{r['pt']:>11.4f}%{r['dt']:>11.4f}%"
                  f"{r['dn']:>12.4f}%{r['se']:>8.4f}%{r['days']:>7}", file=out)

    # ---- 与 qlib 对照(同为 none / 同为 fwd, 均为剔除后) ----
    # qlib_code v1.6.6(涨停判定修复后) 的实测值, 同为全市场+三重剔除
    QLIB = {
        'none': dict(n=55754, pt=3.5535, dt=0.4986, dn=0.7721),
        'fwd': dict(n=51672, pt=4.0401, dt=0.7316, dn=1.0817),
    }
    print("\n" + "=" * 108, file=out)
    print("公平对比: rqalpha vs qlib (同复权、同剔除)", file=out)
    print("=" * 108, file=out)
    print(f"  {'复权':<10}{'指标':<16}{'rqalpha':>12}{'qlib':>12}{'差异':>12}", file=out)
    print("-" * 108, file=out)
    for tag, tname in [('none', '不复权'), ('fwd', '前复权')]:
        r = res[(tag, True)]
        q = QLIB[tag]
        for key, kname in [('n', '触发样本'), ('pt', '触发·观测加权'),
                           ('dt', '触发·日截面'), ('dn', '未触发·日截面')]:
            d = r[key] - q[key]
            unit = 'pp' if key != 'n' else ''
            dv = f"{d:+,.4f}{unit}" if key != 'n' else f"{d:+,}"
            print(f"  {tname:<10}{kname:<16}{r[key]:>12,.4f}{q[key]:>12,.4f}{dv:>12}", file=out)
        print("-" * 108, file=out)

    # ---- 不复权 vs 前复权 的差异(两套系统各自内部) ----
    print("\n" + "=" * 108, file=out)
    print("复权带来的差异 (前复权 − 不复权)，两套系统应高度一致", file=out)
    print("=" * 108, file=out)
    print(f"  {'指标':<20}{'rqalpha':>14}{'qlib':>14}{'两者之差':>14}", file=out)
    print("-" * 108, file=out)
    rn, rf = res[('none', True)], res[('fwd', True)]
    qn, qf = QLIB['none'], QLIB['fwd']
    for key, kname in [('pt', '触发·观测加权'), ('dt', '触发·日截面'), ('dn', '未触发·日截面')]:
        dr = rf[key] - rn[key]
        dq = qf[key] - qn[key]
        print(f"  {kname:<20}{dr:>+13.4f}pp{dq:>+13.4f}pp{dr-dq:>+13.4f}pp", file=out)
    print("-" * 108, file=out)
    print(f"\n  耗时 {time.time()-t0:.0f}s", file=out)


if __name__ == '__main__':
    main()
