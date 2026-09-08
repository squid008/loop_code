# -*- coding: utf-8 -*-
"""
把 D:\\mydata 的每日资金流 CSV 转成 h5。

设计要点
--------
* 按【日期】组织(而非按股票): 回测是逐日推进, 每天要取全市场数据,
  按日期排序 + 日期索引可以 O(1) 切片, 避免打开 5000 个文件。
* sid 编码: 用 instruments.pk 里 type=CS 的全集排序后统一编号,
  保证各年份文件的 sid 完全一致(跨年通用)。
* 数值用 float32: 金额单位万元/占比单位%, 7 位有效数字足够。
* 输出: E:\\rq\\moneyflow\\mf_{year}.h5
    /data  : (date i4, sid i4, 11 个数值字段 f4)  按 (date, sid) 排序
    /index : (date i4, line_no u4, count u4)      每天起始行与行数
    /sid   : S16 数组, sid -> order_book_id
"""
import os
import io
import sys
import csv
import re
import time
import codecs
import pickle
import argparse
from collections import Counter
import numpy as np
import h5py

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

SRC = r'D:\mydata'
PK = r'E:\rq\bundle\instruments.pk'
OUTDIR = r'E:\rq\moneyflow'

C_DATE, C_CODE, C_NAME = 0, 1, 2
VAL_COLS = [
    ('change_pct',      3),
    ('net_amount_main', 4),
    ('net_pct_main',    5),
    ('net_amount_xl',   6),
    ('net_pct_xl',      7),
    ('net_amount_l',    8),
    ('net_pct_l',       9),
    ('net_amount_m',   10),
    ('net_pct_m',      11),
    ('net_amount_s',   12),
    ('net_pct_s',      13),
]
FIELDS = [n for n, _ in VAL_COLS]


def to_obid(code):
    """数字代码 -> order_book_id
    兼容两种写法: '000001' 与个别文件导出时丢失前导零的 '1'
    """
    d = re.sub(r'\D', '', str(code).strip())
    if not d or len(d) > 6:
        return None
    d = d.zfill(6)                      # 补齐前导零
    if d[0] == '6':
        return d + '.XSHG'
    if d[0] in '035':
        return d + '.XSHE'
    if d[0] in '48':
        return d + '.XSHG'
    return None


def to_date(s):
    """'2019-03-31' / '20190331' / '2026/6/18' -> 20190331"""
    s = str(s).strip()
    m = re.match(r'^(\d{4})\D+(\d{1,2})\D+(\d{1,2})$', s)
    if m:
        return int(m.group(1)) * 10000 + int(m.group(2)) * 100 + int(m.group(3))
    d = re.sub(r'\D', '', s)
    return int(d) if len(d) == 8 else None


def sniff(path):
    """探测编码与分隔符 (兼容个别 GBK + Tab 分隔 + 日期 2026/6/18 的异常文件)

    用增量解码器, 避免 head 恰好在多字节字符中间截断造成误判;
    分隔符只看表头行, 更可靠。
    """
    with open(path, 'rb') as f:
        head = f.read(8192)
    for enc in ['utf-8-sig', 'gbk', 'gb18030']:
        try:
            txt = codecs.getincrementaldecoder(enc)().decode(head)
            first = txt.split('\n')[0] if '\n' in txt else txt
            delim = '\t' if first.count('\t') > first.count(',') else ','
            return enc, delim
        except Exception:
            continue
    return 'latin-1', ','


def to_f(x):
    try:
        return float(x)
    except Exception:
        return np.nan


def build_sid_map():
    """全局 sid: 基于 type=CS 全集排序, 各年份保持一致"""
    with open(PK, 'rb') as f:
        inst = pickle.load(f)
    cs = sorted({it['order_book_id'] for it in inst
                 if it.get('type') == 'CS' and it.get('order_book_id')})
    return {obid: i for i, obid in enumerate(cs)}, cs


def build_year(year, sid_map, compress=4, verbose=True):
    files = sorted(fn for fn in os.listdir(SRC)
                   if fn.lower().endswith('.csv') and fn[:4] == str(year))
    if not files:
        print(f"  [{year}] 无 CSV 文件")
        return None

    t0 = time.time()
    col_date, col_sid = [], []
    cols = {n: [] for n in FIELDS}
    n_rows = n_skip_code = n_skip_date = n_skip_sid = 0
    unknown = set()

    enc_stat, delim_stat = Counter(), Counter()
    for fn in files:
        path = os.path.join(SRC, fn)
        enc, delim = sniff(path)
        enc_stat[enc] += 1
        delim_stat['tab' if delim == '\t' else 'comma'] += 1
        with open(path, 'r', encoding=enc, newline='') as f:
            rdr = csv.reader(f, delimiter=delim)
            for i, row in enumerate(rdr):
                if i == 0 or len(row) < 14:
                    continue
                code = row[C_CODE].strip()
                obid = to_obid(code)
                if obid is None:
                    n_skip_code += 1
                    continue
                dt = to_date(row[C_DATE])
                if dt is None:
                    n_skip_date += 1
                    continue
                sid = sid_map.get(obid)
                if sid is None:
                    n_skip_sid += 1
                    unknown.add(obid)
                    continue
                n_rows += 1
                col_date.append(dt)
                col_sid.append(sid)
                for n, ci in VAL_COLS:
                    cols[n].append(to_f(row[ci]))

    if n_rows == 0:
        print(f"  [{year}] 无有效数据")
        return None

    # 组装结构化数组
    dtype = np.dtype([('date', '<i4'), ('sid', '<i4')] + [(n, '<f4') for n in FIELDS])
    arr = np.empty(n_rows, dtype=dtype)
    arr['date'] = np.asarray(col_date, dtype='<i4')
    arr['sid'] = np.asarray(col_sid, dtype='<i4')
    for n in FIELDS:
        arr[n] = np.asarray(cols[n], dtype='<f4')

    # 按 (date, sid) 排序
    arr = arr[np.lexsort((arr['sid'], arr['date']))]

    # 日期索引 (arr 已按 date 排序)
    uniq, starts, counts = np.unique(arr['date'], return_index=True, return_counts=True)
    idx = np.empty(len(uniq), dtype=[('date', '<i4'), ('line_no', '<u4'), ('count', '<u4')])
    idx['date'] = uniq
    idx['line_no'] = starts
    idx['count'] = counts

    # 写盘
    os.makedirs(OUTDIR, exist_ok=True)
    out = os.path.join(OUTDIR, f'mf_{year}.h5')
    with h5py.File(out, 'w') as f:
        f.create_dataset('data', data=arr, compression='gzip', compression_opts=compress)
        f.create_dataset('index', data=idx, compression='gzip', compression_opts=compress)
        f.attrs['year'] = int(year)
        f.attrs['n_rows'] = int(n_rows)
        f.attrs['n_dates'] = int(len(uniq))
        f.attrs['fields'] = ','.join(FIELDS)
        f.attrs['source'] = SRC
        f.attrs['unit'] = 'amount=万元, pct=%'

    size_mb = os.path.getsize(out) / 1024 / 1024
    nan_cnt = int(sum(np.isnan(arr[n]).sum() for n in FIELDS))
    if verbose:
        print(f"  [{year}] 文件={len(files)}  有效行={n_rows:,}  交易日={len(uniq)}")
        print(f"         编码={dict(enc_stat)} 分隔符={dict(delim_stat)}")
        print(f"         跳过: 代码异常={n_skip_code} 日期异常={n_skip_date} 非CS={n_skip_sid}")
        print(f"         日期范围: {uniq[0]} ~ {uniq[-1]}   每日股票数: {counts.min()}~{counts.max()} (均值{counts.mean():.0f})")
        print(f"         NaN 单元格合计: {nan_cnt:,}")
        print(f"         输出: {out}  ({size_mb:.1f} MB)  用时 {time.time()-t0:.1f}s")
        if unknown:
            print(f"         [!] 非 CS 代码 {len(unknown)} 个: {sorted(unknown)[:5]}")
    return out


def write_sid(sid_list):
    """sid 映射表单独存一份, 各年份共用"""
    os.makedirs(OUTDIR, exist_ok=True)
    out = os.path.join(OUTDIR, 'sid.h5')
    arr = np.array([s.encode('ascii') for s in sid_list], dtype='S16')
    with h5py.File(out, 'w') as f:
        f.create_dataset('sid', data=arr)
        f.attrs['n'] = len(sid_list)
    print(f"  sid 映射表: {out}  ({len(sid_list)} 条)")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--years', default='2019',
                    help='逗号分隔的年份, 或 all')
    args = ap.parse_args()

    print("=" * 96)
    print("构建资金流 h5")
    print("=" * 96)
    t0 = time.time()
    sid_map, sid_list = build_sid_map()
    print(f"  sid 全集(type=CS): {len(sid_list)}")

    if args.years.strip().lower() == 'all':
        years = sorted({fn[:4] for fn in os.listdir(SRC) if fn.lower().endswith('.csv')})
    else:
        years = [y.strip() for y in args.years.split(',') if y.strip()]

    print(f"  待处理年份: {years}\n" + "-" * 96)
    outs = []
    for y in years:
        r = build_year(y, sid_map)
        if r:
            outs.append(r)
        print("-" * 96)

    write_sid(sid_list)
    print(f"\n完成: {len(outs)} 个文件, 总用时 {time.time()-t0:.1f}s")
    for o in outs:
        print(f"    {o}")


if __name__ == '__main__':
    main()
