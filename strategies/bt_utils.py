# -*- coding: utf-8 -*-
"""
回测产物统一工具(所有策略共用)
================================================================
规范:
  1. 每次回测必须输出 pkl 数据 + png 净值曲线图
  2. 命名: {策略名}_{回测时间}_{开始日}_{结束日}
     回测时间为 YYYYMMDD_HHMM_SS, 日期为 YYYYMMDD
     时间戳前置, 保证同一策略多次回测按文件名排序即为时间先后
     例: all01_20260905_1833_45_20141001_20260805
  3. 净值曲线图需含基准对比, 多版本(如加杠杆前后)画在同一张图

用法(策略文件末尾):
    from bt_utils import basename, finish, load_netval
    ...
    output_path = os.path.join(HERE, basename(__file__, start_date, end_date))
    run_func(...)
    nv, bench = load_netval(output_path + ".pkl")
    finish(__file__, start_date, end_date, output_path + ".pkl",
           curves={'策略A': nv}, bench=bench, title='xxx')
"""
import os
import glob
import pickle
from datetime import datetime
import numpy as np
import pandas as pd


def stem_of(file):
    return os.path.splitext(os.path.basename(os.path.abspath(file)))[0]


def basename(file, start_date, end_date):
    """产物命名: 策略名_回测时间戳_开始日_结束日
    时间戳前置, 使同一策略的多次回测按文件名排序即为时间先后
    例: all01_20260905_1833_45_20141001_20260805
    """
    stem = stem_of(file)
    ts = datetime.now().strftime('%Y%m%d_%H%M_%S')
    sd = start_date.replace('-', '')
    ed = end_date.replace('-', '')
    return f"{stem}_{ts}_{sd}_{ed}"


def latest_result(file, start_date, end_date):
    """取最近一次回测产物(pkl 全路径), 没有返回 None; 供 --plot-only 用"""
    stem = stem_of(file)
    sd = start_date.replace('-', '')
    ed = end_date.replace('-', '')
    fs = sorted(glob.glob(os.path.join(os.path.dirname(os.path.abspath(file)),
                                       f"{stem}_*_{sd}_{ed}.pkl")))
    return fs[-1] if fs else None


def stats(nv):
    """返回 (年化, 最大回撤, Sharpe, Calmar)"""
    r = nv.pct_change()
    years = (nv.index[-1] - nv.index[0]).days / 365.25
    ann = nv.iloc[-1] ** (1 / years) - 1
    dd = (nv / nv.cummax() - 1).min()
    sharpe = r.mean() / r.std() * np.sqrt(252) if r.std() > 0 else np.nan
    return ann, dd, sharpe, (ann / abs(dd) if dd < 0 else np.nan)


def load_netval(pkl_path):
    """读 rqalpha sys_analyser 产物, 返回 (策略净值, 基准净值)"""
    with open(pkl_path, 'rb') as f:
        res = pickle.load(f)
    pf = res['portfolio']
    nv = (pf['unit_net_value'] if 'unit_net_value' in pf.columns
          else pf['total_value'] / pf['total_value'].iloc[0])
    bp = res['benchmark_portfolio']
    bench = (bp['unit_net_value'] if 'unit_net_value' in bp.columns
             else bp['total_value'] / bp['total_value'].iloc[0])
    return nv, bench


def plot_curves(curves, path, bench=None, title=''):
    """净值曲线(对数坐标) + 回撤填充, 保存为 png
    curves: {图例名: 净值Series}, 可传多条做对比
    """
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False

    fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=True,
                             gridspec_kw={'height_ratios': [3, 1]})
    ax = axes[0]
    for name, nv in curves.items():
        a, d, s, _ = stats(nv)
        ax.plot(nv.index, nv.values, lw=1.3,
                label=u'%s  年化%.2f%%  回撤%.1f%%  Sharpe%.3f' % (name, a * 100, d * 100, s))
    if bench is not None:
        ab, db, sb, _ = stats(bench)
        ax.plot(bench.index, bench.values, lw=1.1, color='#7f7f7f', alpha=0.85,
                label=u'基准  年化%.2f%%  回撤%.1f%%' % (ab * 100, db * 100))
    ax.set_yscale('log')
    ax.set_ylabel(u'净值(对数坐标)')
    ax.set_title(title, fontsize=13)
    ax.legend(loc='upper left', fontsize=9)
    ax.grid(alpha=0.3)

    main = list(curves.values())[-1]
    dser = (main / main.cummax() - 1) * 100
    axes[1].fill_between(dser.index, dser.values, 0, color='#d62728', alpha=0.35)
    axes[1].set_ylabel(u'回撤 %')
    axes[1].grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def finish(file, start_date, end_date, pkl_path, curves=None, bench=None,
           title='', extra_tag=''):
    """回测收尾: 打印指标 + 存净值曲线图 + 列出产物"""
    out = os.path.splitext(pkl_path)[0]
    if curves is None:
        nv, bench = load_netval(pkl_path)
        curves = {stem_of(file): nv}

    print("=" * 78)
    if extra_tag:
        print(extra_tag)
    print(f"回测区间: {start_date} ~ {end_date}")
    print("-" * 78)
    for name, nv in curves.items():
        a, d, s, c = stats(nv)
        print(u"  %-18s 年化 %6.2f%%   回撤 %7.2f%%   Sharpe %5.3f   Calmar %5.3f"
              % (name, a * 100, d * 100, s, c))
    if bench is not None:
        ab, db, sb, cb = stats(bench)
        print(u"  %-18s 年化 %6.2f%%   回撤 %7.2f%%   Sharpe %5.3f   Calmar %5.3f"
              % (u'基准', ab * 100, db * 100, sb, cb))

    png = out + ".png"
    plot_curves(curves, png, bench=bench, title=title or stem_of(file))
    print("-" * 78)
    print(u"产物文件:")
    for f in [pkl_path, png]:
        print("  " + os.path.basename(f) + ("" if os.path.exists(f) else u"  (缺失)"))
    print("=" * 78)
