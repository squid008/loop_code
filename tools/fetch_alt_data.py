# -*- coding: utf-8 -*-
"""fetch_alt_data.py — 拉「替代数据」并落 `engine/alt_data.h5`（与 panel.h5 **同轴** T×S）

★ 为什么（A 方案，2026-10-22 用户拍板）：本机现有 63 个叶子全在
  「量价 / 资金流 / 财报 / Barra 风格」四族里，与风格天然纠缠（剥两者后 94% 转负）。
  实测 gen194~203 十代 0 入库、`calmar2` 达标 0 条 ⇒ **候选池枯竭**，必须换信号源。

★ 数据源：tushare pro（token 在 `config.local.json` 的 `sources.tushare.token`，**不入库**）

★ 落 4 个字段（都用面板现成的 `mktcap`/`turnover` 当分母，**零额外请求**）：

  | 叶子 | 含义 | 计算 |
  |---|---|---|
  | `mg_bal_ratio`   | 融资余额 / 总市值   | `margin_detail.rzye / mktcap` |
  | `mg_buy_ratio`   | 融资买入额 / 成交额 | `margin_detail.rzmre / turnover` |
  | `lhb_net_ratio`  | 龙虎榜净买入 / 成交额 | `top_list.net_amount / turnover`（**未上榜 = 0**）|
  | `lhb_inst_ratio` | 龙虎榜**机构席位**净买入 / 成交额 | `top_inst.buy−sell / turnover`（未上榜 = 0）|
  | `block_vol_ratio`| **大宗交易额** / 成交额 | `block_trade.amount / turnover`（无方向，只测活跃度）|

  ⚠⚠ **`hk_hold` 不能用**（2026-10-22 实测）：它返回的是**港股**（`00001.HK` 長和 …），
    不是 A 股北向持股 ⇒ 我第一版拿它做 `north_ratio`，覆盖率 4.8% 且**全是错配的脏数据** ✗
    （A 股北向个股持股在这个套餐里拿不到，只有 `hsgt_top10` 的 10 只/日，不可用）

  ⚠ 口径说明：`mktcap` 是**总市值**（不是流通市值）⇒ `mg_bal_ratio` 是"融资余额占总市值"。

用法::

    python tools/fetch_alt_data.py                       # 默认近 3 年（约 25 分钟）
    python tools/fetch_alt_data.py --start=20130104      # 全历史（约 1.5 小时）
"""
import argparse
import io
import json
import os
import sys
import time

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PANEL = os.path.join(ROOT, 'engine', 'panel.h5')
OUT = os.path.join(ROOT, 'engine', 'alt_data.h5')
CFG = os.path.join(ROOT, 'config.local.json')

_SUF = {'.SZ': '.XSHE', '.SH': '.XSHG', '.BJ': '.XBSE'}


def _token():
    if not os.path.isfile(CFG):
        raise SystemExit('缺 %s（要写 sources.tushare.token）' % CFG)
    cfg = json.load(io.open(CFG, encoding='utf-8'))
    tok = ((cfg.get('sources') or {}).get('tushare') or {}).get('token')
    if not tok:
        raise SystemExit('config.local.json 里没有 sources.tushare.token')
    return tok


def _axis():
    with pd.HDFStore(PANEL, 'r') as st:
        close = st['/close']
        mktcap = st['/mktcap']
        turnover = st['/turnover']
    return close.index.values, list(close.columns), mktcap, turnover


def _to_col(ts_code):
    s = str(ts_code)
    for a, b in _SUF.items():
        if s.endswith(a):
            return s[:-len(a)] + b
    return None


def _new(dates, cols, fill=None):
    a = np.full((len(dates), len(cols)), np.nan, dtype='float32')
    if fill is not None:
        a[:] = fill
    return a


# ---- 按年分片（断点续拉；2026-10-22 踩过的坑：全历史单次跑被外部结束，66 分钟白费）----
PARTS = os.path.join(ROOT, 'engine', 'alt_parts')


def _parts():
    import glob
    return sorted(glob.glob(os.path.join(PARTS, 'alt_*.h5')))


def _part_path(year):
    return os.path.join(PARTS, 'alt_%d.h5' % year)


def _save_part(year, dates, cols, arrs):
    """把某一年的切片写成分片（原子写：.tmp -> replace）。"""
    os.makedirs(PARTS, exist_ok=True)
    tmp = _part_path(year) + '.tmp'
    with pd.HDFStore(tmp, 'w') as st:
        for nm, arr in arrs.items():
            st[nm] = pd.DataFrame(arr, index=dates, columns=cols)
    os.replace(tmp, _part_path(year))


def _load_part(year):
    p = _part_path(year)
    if not os.path.isfile(p):
        return None
    with pd.HDFStore(p, 'r') as st:
        return {k.lstrip('/'): st[k].values for k in st.keys()}


def _merge_parts(dates, cols):
    """所有分片按日期拼成 (T,S) 数组；缺的年份保持 NaN。"""
    got = {}
    for p in _parts():
        try:
            year = int(os.path.basename(p)[4:8])
        except ValueError:
            continue
        d = _load_part(year)
        if d:
            got[year] = d
    if not got:
        return None
    names = list(next(iter(got.values())).keys())
    out = {}
    for nm in names:
        frames = []
        for year in sorted(got):
            sub = got[year].get(nm)
            if sub is None:
                continue
            pos = [k for k, d in enumerate(dates) if int(d) // 10000 == year]
            if not pos:
                continue
            # ⚠ 分片**本身就是该年的切片**（`_flush` 用 `dates[pos]` 写的，行序一致）
            #   ⇒ 直接用 `sub`，**不能**再用全局索引去切它（2026-10-22 越界一次 ✗）
            # ⚠⚠ index 必须用 `dates[pos]`（**同 dtype**）—— 用 python `int` 列表会与
            #   面板的 `np.int64` 索引对不上，`reindex` 之后**全是 NaN**（2026-10-22 实测 ✗）
            if len(sub) != len(pos):
                print('  [合并] %d 年分片行数 %d != 面板 %d ⇒ 跳过该年'
                      % (year, len(sub), len(pos)))
                continue
            frames.append(pd.DataFrame(sub, index=dates[pos], columns=cols))
        if frames:
            s = pd.concat(frames)
            out[nm] = s.reindex(index=dates, columns=cols).values.astype('float32')
        else:
            out[nm] = np.full((len(dates), len(cols)), np.nan, dtype='float32')
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--start', default=None)
    ap.add_argument('--end', default=None)
    ap.add_argument('--out', default=OUT)
    ap.add_argument('--sleep', type=float, default=0.32, help='每次请求后休眠（限流）')
    ap.add_argument('--only', default=None, help='只拉某一组（margin/topinst/block），调试用')
    a = ap.parse_args()

    import tushare as ts
    pro = ts.pro_api(_token())

    dates, cols, mktcap, turnover = _axis()
    pos = {c: i for i, c in enumerate(cols)}
    end = a.end or str(int(dates[-1]))
    start = a.start or (str(int(dates[-750])) if len(dates) > 750 else str(int(dates[0])))
    dsel = [int(d) for d in dates if start <= str(int(d)) <= end]
    print('面板轴 %d 日 × %d 股；本次拉 %s ~ %s 共 %d 个交易日'
          % (len(dates), len(cols), start, end, len(dsel)))

    MG_BAL = _new(dates, cols)
    MG_BUY = _new(dates, cols)
    LHB = _new(dates, cols, fill=0.0)        # 未上榜 = 0（"没上榜"是有意义的信息）
    LHBI = _new(dates, cols, fill=0.0)
    BLK = _new(dates, cols, fill=0.0)        # 无大宗 = 0

    # ★ 断点续拉：先吃已有分片，跳过已完成的年份（2026-10-22 教训：单次跑被外部结束，66 分钟白费）
    _done = {int(os.path.basename(p)[4:8]) for p in _parts()}
    _pre = _merge_parts(dates, cols) if _done else None
    if _pre:
        MG_BAL, MG_BUY = _pre['mg_bal_ratio'], _pre['mg_buy_ratio']
        LHB, LHBI, BLK = _pre['lhb_net_ratio'], _pre['lhb_inst_ratio'], _pre['block_vol_ratio']
        print('  已加载 %d 个年分片（%s）⇒ 这些年份跳过'
              % (len(_done), ','.join(str(y) for y in sorted(_done))))
    _todo = [d for d in dsel if int(d) // 10000 not in _done]
    if len(_todo) != len(dsel):
        print('  待拉 %d 日（总 %d 日）' % (len(_todo), len(dsel)))
    dsel = _todo

    _pos_of_year = {y: [k for k, d in enumerate(dates) if int(d) // 10000 == y]
                    for y in sorted({int(d) // 10000 for d in dsel})}

    def _flush(year):
        """把该年的切片写成分片（中断只丢当年）。"""
        pos = _pos_of_year.get(year) or []
        if not pos:
            return
        _save_part(year, dates[pos], cols, dict(
            mg_bal_ratio=MG_BAL[pos], mg_buy_ratio=MG_BUY[pos],
            lhb_net_ratio=LHB[pos], lhb_inst_ratio=LHBI[pos], block_vol_ratio=BLK[pos]))

    tk2i = {str(int(d)): k for k, d in enumerate(dates)}
    t0 = time.time()
    n_miss = 0
    cur_year = None

    def _ratio(i, j, num, den):
        if not (np.isfinite(den) and den > 0):
            return np.nan
        return float(num) / den

    for k, d in enumerate(dsel):
        _y = int(d) // 10000
        if cur_year is not None and _y != cur_year:
            _flush(cur_year)                     # 上一年收尾 → 写分片（可断点续拉）
            print('  %d 年完成 → 分片已写' % cur_year, flush=True)
        cur_year = _y
        ds = str(d)
        i = tk2i[ds]

        if a.only in (None, 'margin'):
            try:                                                # ---- 融资融券 ----
                df = pro.margin_detail(trade_date=ds)
                if df is not None and len(df):
                    for r in df.to_dict('records'):
                        j = pos.get(_to_col(r.get('ts_code')))
                        if j is None:
                            continue
                        mv = float(mktcap.iat[i, j])
                        tv = float(turnover.iat[i, j])
                        v = _ratio(i, j, r.get('rzye') or 0.0, mv)
                        if np.isfinite(v):
                            MG_BAL[i, j] = v
                        v = _ratio(i, j, r.get('rzmre') or 0.0, tv)
                        if np.isfinite(v):
                            MG_BUY[i, j] = v
            except Exception as e:                              # noqa: BLE001
                n_miss += 1
                if n_miss <= 3:
                    print('  [margin %s] %s: %s' % (ds, type(e).__name__, str(e)[:70]))
            time.sleep(a.sleep)

        if a.only in (None, 'topinst'):
            try:                                                # ---- 龙虎榜（营业部）----
                df = pro.top_list(trade_date=ds)
                if df is not None and len(df):
                    for r in df.to_dict('records'):
                        j = pos.get(_to_col(r.get('ts_code')))
                        if j is None:
                            continue
                        tv = float(turnover.iat[i, j])
                        na = r.get('net_amount')
                        if na is None or not np.isfinite(float(na)):
                            na = float(r.get('l_buy') or 0.0) - float(r.get('l_sell') or 0.0)
                        v = _ratio(i, j, na, tv)
                        if np.isfinite(v):
                            LHB[i, j] = v
            except Exception as e:                              # noqa: BLE001
                n_miss += 1
                if n_miss <= 3:
                    print('  [top_list %s] %s: %s' % (ds, type(e).__name__, str(e)[:70]))
            time.sleep(a.sleep)
            try:                                                # ---- 龙虎榜（机构席位）----
                df = pro.top_inst(trade_date=ds)
                if df is not None and len(df):
                    agg = {}
                    for r in df.to_dict('records'):
                        c = _to_col(r.get('ts_code'))
                        if c is None:
                            continue
                        agg[c] = agg.get(c, 0.0) + float(r.get('buy') or 0.0) - float(r.get('sell') or 0.0)
                    for c, net in agg.items():
                        j = pos.get(c)
                        if j is None:
                            continue
                        v = _ratio(i, j, net, float(turnover.iat[i, j]))
                        if np.isfinite(v):
                            LHBI[i, j] = v
            except Exception as e:                              # noqa: BLE001
                n_miss += 1
                if n_miss <= 3:
                    print('  [top_inst %s] %s: %s' % (ds, type(e).__name__, str(e)[:70]))
            time.sleep(a.sleep)

        if a.only in (None, 'block'):
            try:                                                # ---- 大宗交易（无方向）----
                df = pro.block_trade(trade_date=ds)
                if df is not None and len(df):
                    agg = {}
                    for r in df.to_dict('records'):
                        c = _to_col(r.get('ts_code'))
                        if c is None:
                            continue
                        agg[c] = agg.get(c, 0.0) + float(r.get('amount') or 0.0)
                    for c, amt in agg.items():
                        j = pos.get(c)
                        if j is None:
                            continue
                        v = _ratio(i, j, amt, float(turnover.iat[i, j]))
                        if np.isfinite(v):
                            BLK[i, j] = v
            except Exception as e:                              # noqa: BLE001
                n_miss += 1
                if n_miss <= 3:
                    print('  [block_trade %s] %s: %s' % (ds, type(e).__name__, str(e)[:70]))
            time.sleep(a.sleep)

        if (k + 1) % 50 == 0:
            print('  %d/%d 日 · 用时 %.0fs（失败 %d）' % (k + 1, len(dsel), time.time() - t0, n_miss),
                  flush=True)

    if cur_year is not None:
        _flush(cur_year)                         # 最后一年
        print('  %d 年完成 → 分片已写' % cur_year, flush=True)
    out = a.out if os.path.isabs(a.out) else os.path.join(ROOT, a.out)
    _merged = _merge_parts(dates, cols)
    frame = _merged if _merged else dict(
        mg_bal_ratio=MG_BAL, mg_buy_ratio=MG_BUY,
        lhb_net_ratio=LHB, lhb_inst_ratio=LHBI, block_vol_ratio=BLK)
    with pd.HDFStore(out, 'w') as st:
        for nm, arr in frame.items():
            st[nm] = pd.DataFrame(arr, index=dates, columns=cols)
    # 全历史合并完 ⇒ 分片可以清掉（下次重拉会重建）
    for f in _parts():
        try:
            os.remove(f)
        except OSError:
            pass
    print('\n已写 %s' % out)
    for nm, arr in frame.items():
        fin = np.isfinite(arr)
        nz = np.isfinite(arr) & (arr != 0)
        print('  %-16s 覆盖 %.1f%%  非零 %.1f%%  中位 %.4g' % (
            nm, 100.0 * fin.mean(), 100.0 * nz.mean(),
            float(np.nanmedian(arr[fin])) if fin.any() else float('nan')))
    print('完成：%d 日、%d 次失败、用时 %.0fs' % (len(dsel), n_miss, time.time() - t0))
    return 0


if __name__ == '__main__':
    sys.exit(main())
