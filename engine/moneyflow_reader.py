# -*- coding: utf-8 -*-
"""
资金流数据读取器 —— 配合 E:\\rq\\moneyflow\\ 下的 h5 使用

数据结构
--------
E:\\rq\\moneyflow\\
    sid.h5      /sid : S16 数组, sid -> order_book_id
    mf_{yyyy}.h5
        /data  : (date i4, sid i4, 11 个数值字段 f4), 按 (date, sid) 排序
        /index : (date i4, line_no u4, count u4)

数值字段(11)
--------
    change_pct       涨跌幅(%)
    net_amount_main  主力净额(万元)   = 超大单 + 大单
    net_pct_main     主力净占比(%)
    net_amount_xl    超大单净额(万元)  ≥50万股 或 100万元
    net_pct_xl       超大单净占比(%)
    net_amount_l     大单净额(万元)
    net_pct_l        大单净占比(%)
    net_amount_m     中单净额(万元)
    net_pct_m        中单净占比(%)
    net_amount_s     小单净额(万元)
    net_pct_s        小单净占比(%)

单位: 金额=万元, 占比=%
"""
import os
import numpy as np
import h5py

FIELDS = ['change_pct', 'net_amount_main', 'net_pct_main',
          'net_amount_xl', 'net_pct_xl',
          'net_amount_l', 'net_pct_l',
          'net_amount_m', 'net_pct_m',
          'net_amount_s', 'net_pct_s']


class MoneyFlow:
    def __init__(self, root=r'E:\rq\moneyflow'):
        self.root = root
        with h5py.File(os.path.join(root, 'sid.h5'), 'r') as f:
            self.sid_list = [s.decode() for s in f['sid'][:]]
        self.obid2sid = {s: i for i, s in enumerate(self.sid_list)}
        self._cache = {}          # year -> (h5file, {date: (line_no, count)})

    # ---------- 内部 ----------
    def _open_year(self, y):
        if y not in self._cache:
            p = os.path.join(self.root, f'mf_{y}.h5')
            if not os.path.exists(p):
                raise FileNotFoundError(p)
            f = h5py.File(p, 'r')
            idx = f['index'][:]
            self._cache[y] = (f, {int(r['date']): (int(r['line_no']), int(r['count']))
                                  for r in idx})
        return self._cache[y]

    def years(self):
        return sorted(int(fn[3:7]) for fn in os.listdir(self.root)
                      if fn.startswith('mf_') and fn.endswith('.h5'))

    def all_dates(self):
        out = []
        for y in self.years():
            _, idx = self._open_year(y)
            out.extend(sorted(idx.keys()))
        return out

    # ---------- 查询 ----------
    def get_day(self, date):
        """取某天全市场。date: int(20190304)。返回按 sid 升序的结构化数组, 无数据返回 None"""
        try:
            f, idx = self._open_year(int(date) // 10000)
        except FileNotFoundError:
            return None
        if date not in idx:
            return None
        ln, cnt = idx[date]
        return f['data'][ln:ln + cnt]

    def get_stock(self, obid):
        """取单只股票全部历史, 按日期升序"""
        sid = self.obid2sid.get(obid)
        if sid is None:
            return None
        parts = []
        for y in self.years():
            f, _ = self._open_year(y)
            d = f['data']
            m = d['sid'][:] == sid
            if m.any():
                parts.append(d[m])
        return np.concatenate(parts) if parts else None

    def obid(self, sid):
        return self.sid_list[sid]

    def day_frame(self, date):
        """便捷: 返回 (obid列表, 各字段 dict of ndarray), 便于排序选股"""
        rows = self.get_day(date)
        if rows is None:
            return None
        obids = [self.sid_list[i] for i in rows['sid']]
        cols = {n: rows[n].astype('f8') for n in FIELDS}
        return obids, cols

    def close(self):
        for f, _ in self._cache.values():
            f.close()
        self._cache.clear()


# ---------------------------------------------------------------- 使用示例
if __name__ == '__main__':
    mf = MoneyFlow()
    print(f"可用年份: {mf.years()}")
    dates = mf.all_dates()
    print(f"交易日总数: {len(dates)}  范围: {dates[0]} ~ {dates[-1]}")

    d = 20190304
    obids, cols = mf.day_frame(d)
    print(f"\n{d} 共 {len(obids)} 只")

    # 1) 主力净流入 TOP10
    order = np.argsort(-cols['net_amount_main'])[:10]
    print(f"\n主力净流入 TOP10 ({d})")
    print(f"  {'代码':<14}{'涨跌幅%':>9}{'主力净额(万)':>14}{'主力占比%':>11}{'超大单(万)':>13}")
    for i in order:
        print(f"  {obids[i]:<14}{cols['change_pct'][i]:>9.2f}"
              f"{cols['net_amount_main'][i]:>14.1f}{cols['net_pct_main'][i]:>11.2f}"
              f"{cols['net_amount_xl'][i]:>13.1f}")

    # 2) 单只股票时间序列
    obid = '000001.XSHE'
    hist = mf.get_stock(obid)
    print(f"\n{obid} 历史: {len(hist)} 个交易日  ({hist['date'][0]} ~ {hist['date'][-1]})")
    print(f"  主力净额: 均值={np.nanmean(hist['net_amount_main']):.1f}万  "
          f"最大={np.nanmax(hist['net_amount_main']):.1f}万  "
          f"最小={np.nanmin(hist['net_amount_main']):.1f}万")

    # 3) 全市场某天主力净流入总额(市场情绪指标)
    tot = np.nansum(cols['net_amount_main'])
    print(f"\n{d} 全市场主力净流入合计: {tot:,.0f} 万元 ({tot/10000:.2f} 亿元)")

    # 4) 连续几日主力净流入排行(动量用法)
    print(f"\n连续 3 日主力净额累计 TOP5 (截至 {d})")
    di = dates.index(d)
    win = dates[di - 2:di + 1]
    acc = {}
    for dd in win:
        rows = mf.get_day(dd)
        for r in rows:
            acc[int(r['sid'])] = acc.get(int(r['sid']), 0.0) + float(r['net_amount_main'])
    top = sorted(acc.items(), key=lambda x: -x[1])[:5]
    for sid, v in top:
        print(f"  {mf.obid(sid):<14} 3日累计={v:>12.1f} 万元")

    mf.close()
