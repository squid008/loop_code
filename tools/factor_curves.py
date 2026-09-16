# -*- coding: utf-8 -*-
"""factor_curves.py — 为每个入库因子**离线预算**看板曲线 → `docs/factor_curves/<name>.json`

## 为什么"离线算"（用户之问：加这些图**影响性能吗**？）
网页上"现算"一条曲线 = **一次完整回测**（载面板 + 逐期选股 ≈ 10s）⇒ 点一下卡十秒 ✗
而**入库因子是少数**（当前 51 条）⇒ 离线算一次、存成小 JSON，看板打开详情时**只读一个文件**（几十 KB）
⇒ **对页面性能没有影响** ✓（新增因子用 `--only-new` 增量补算即可）

## 每因子存什么（口径写进 JSON，前端只负责画）
  · **日频**（持有期内逐日 mark）：`d_dates` + 组合净值 `nav_t` / 基准净值 `nav_m` / 超额净值 `nav_e`
    + 超额回撤 `dd_e` / 组合回撤 `dd_t`（面积图）
  · **期频**：`r_dates` + `ic`(Pearson) / `rank_ic`(Spearman，即引擎 IC 口径)
    + `decile`（**十档累计净值**，10 条）/ `ls`（多空=第10档−第1档）/ `turn` 明细
  · **剥风格**（`--stage=strip`）：原 / 剥市值(lncap) / 剥成交额(lnamt) / 剥两者 —— 四条**期频**净值

## 用法（分两段跑，避免一次等太久）
    python tools/factor_curves.py --stage=core            # 核心（~12 分钟）
    python tools/factor_curves.py --stage=strip           # 剥风格四条（~25 分钟）
    python tools/factor_curves.py --only-new --stage=core # 增量：只补没算过的
    python tools/factor_curves.py --limit=2 --stage=core  # 冒烟

★ 复用 `build_facs` 的公共件（`parse_library` / `load_bank_nodes` / `_prep_main` / `load_archive_ic`）
  —— **不复制实现**，避免两处口径漂移 ✓
★ **符号对齐**与 `factor_metrics.py` / `build_facs.py` **同一判据**（用库文档/归档的 IC 定方向）
  ⇒ 曲线方向与明细里的指标**同向**，不会出现"指标正、曲线却在跌" ✗
"""
import argparse
import io
import json
import os
import sys
import time

import numpy as np

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DOCS = os.path.join(ROOT, 'docs')
CURVE_DIR = os.path.join(DOCS, 'factor_curves')
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, 'engine'))

ROUND = 6


def _r(x, n=ROUND):
    try:
        v = float(x)
    except Exception:
        return None
    return round(v, n) if np.isfinite(v) else None


def _rl(seq, n=ROUND):
    return [_r(x, n) for x in np.asarray(seq).ravel()]


def _dates_of(idx):
    return [int(x) for x in idx]


def _aligned(it, B, dates, cols, close, cost, window):
    """求值 + **符号对齐**（与库记录同向）+ 一次完整回测。

    返回 `(fac, rr, sign)`；`fac` 已按 `sign` 取负 ⇒ 下游（十档/多空/剥风格）方向一致 ✓
    """
    import pandas as pd
    import factor_miner as fm
    import loop_engine as LE

    nm = it['_nm']
    v = LE.eval_expr(it['node'], B, {})
    fac = fm.cs_rank(pd.DataFrame(v, index=dates, columns=cols).astype('float64'))
    rr = fm.evaluate_real(fac, close, nm, cost=cost, window=window,
                          with_daily=True, with_ex=True)
    if rr is None:
        return None, None, 1
    sign = 1
    # ★ 符号参照必须与 `factor_metrics.py` / `build_facs.py` **完全同一规则**：
    #   优先用**库记录/归档的带符号 IC**；没有 IC 记录时才退到**文档里的分池超额**（老条目）。
    #   ⚠ 少了这个回退 ⇒ 那 8 个"无 IC 记录"的老因子会**方向反**（指标正、曲线却向下）✗
    ref = it.get('ic_ref')
    if ref in (None, 0):
        ref = it.get('ae_lib')
    if ref not in (None, 0) and np.sign(rr['ic']) != np.sign(ref):
        sign = -1
        fac = -fac
        rr2 = fm.evaluate_real(fac, close, nm, cost=cost, window=window,
                               with_daily=True, with_ex=True)
        if rr2 is not None:
            rr = rr2
    # ★ 期频曲线的公共网格（与 `evaluate_real` 内部一致）：`close.index >= START`
    rr['_close'] = close
    rr['_idx'] = close.index[close.index >= fm.START]
    return fac, rr, sign


def core_for(nm, fac, rr, cost, window, verbose=True):
    """核心曲线：日频净值/回撤 + 期频 IC(Pearson)/RankIC/十档/多空。"""
    import pandas as pd
    import factor_miner as fm

    # ---- ★★ 期频曲线**必须全部对齐到"换仓日网格"** `rb`（= `rr['ex'].index`，418 个）----
    #   ⚠⚠ 2026-09-16 实测踩坑：原实现把 IC/十档算在**全日频网格**（3309 个日期）上，
    #      却用 418 个换仓日当横轴 ⇒ 前 418 天被拉满整张图，**图与数不对应** ✗（长度不等也会误画）
    #   ⇒ 现在：IC(Pearson)/RankIC/十档/多空/换手**一律只取换仓日**的那一行 ✓ 且省 87% 计算量
    idx = rr['_idx']
    close = rr['_close']
    rb = rr['ex'].index
    pos = {int(d): i for i, d in enumerate(idx)}
    fwd_ret = (close.shift(-(1 + fm.FWD)) / close.shift(-1) - 1).reindex(index=idx)
    U = fm.get_universe().reindex(index=idx, columns=close.columns).fillna(False)
    fac_i = fac.reindex(index=idx, columns=close.columns)
    fv, rv, uv = fac_i.values, fwd_ret.values, U.values
    n_grp = fm.N_GRP
    ics_p, dec_parts, turns = [], [], []
    prev_top = None
    for d in rb:
        i = pos.get(int(d))
        if i is None:
            ics_p.append(np.nan)
            dec_parts.append([np.nan] * n_grp)
            turns.append(None)
            continue
        u = uv[i]
        f_, r_ = fv[i][u], rv[i][u]
        m = np.isfinite(f_) & np.isfinite(r_)
        if m.sum() < 50:
            ics_p.append(np.nan)
            dec_parts.append([np.nan] * n_grp)
            continue
        ff, rr_ = f_[m], r_[m]
        ics_p.append(float(np.corrcoef(ff, rr_)[0, 1]))             # Pearson IC
        pct = pd.Series(ff).rank(pct=True).values                   # 0~1 分位
        grp = np.clip((pct * n_grp).astype(int), 0, n_grp - 1)
        dec_parts.append([float(np.mean(rr_[grp == g])) if (grp == g).any() else np.nan
                          for g in range(n_grp)])
        # 逐期换手（引擎同义：Top 组换掉的比例）—— ★ 用**列位置当股票 id**，
        #   ⚠ 不能用 `ff` 的下标（它是 universe∩有限 的子集）去索引整行，那是两个长度 ✗
        pos_m = np.nonzero(u)[0][m]
        k = max(10, len(pos_m) // 10)
        top = set(pos_m[np.argsort(-ff)[:k]].tolist())
        # ★ 每期都 append（第一期没有"上期" ⇒ None）—— 否则 `turn_series` 会比日期轴**少一条** ✗
        turns.append((1.0 - len(top & prev_top) / max(len(prev_top), 1)) if prev_top else None)
        prev_top = top
    dec = np.array(dec_parts, dtype='float64')
    dec_nav = np.cumprod(1.0 + np.nan_to_num(dec, nan=0.0), axis=0)

    exd = np.asarray(rr.get('ex_d'), dtype='float64')
    trd = np.asarray(rr.get('tr_d'), dtype='float64')
    d_dates = rr.get('d_dates') or []
    if len(d_dates) != len(exd) or len(trd) != len(exd):
        print('    [!] %s 日频序列长度不符 ⇒ 跳过日频曲线' % nm)
        return None
    mrd = trd - exd
    nav_t = np.cumprod(1.0 + trd)
    nav_m = np.cumprod(1.0 + mrd)
    nav_e = np.cumprod(1.0 + exd)
    dd_e = nav_e / np.maximum.accumulate(nav_e) - 1.0
    dd_t = nav_t / np.maximum.accumulate(nav_t) - 1.0
    ls = np.cumprod(1.0 + np.nan_to_num(dec[:, -1] - dec[:, 0], nan=0.0))

    out = {
        'name': nm, 'cost': cost, 'window': window,
        'start': int(rr['ex'].index[0]), 'end': int(rr['ex'].index[-1]),
        'n_rebal': int(rr['n_rebal']),
        'r_dates': _dates_of(rb),
        'd_dates': [int(x) for x in d_dates],
        'nav_t': _rl(nav_t), 'nav_m': _rl(nav_m), 'nav_e': _rl(nav_e),
        'dd_e': _rl(dd_e), 'dd_t': _rl(dd_t),
        'ic': _rl(ics_p),
        # ★ RankIC 也只取**换仓日**那条（与横轴同长）；引擎的 `ic_series` 是全日频的 ⇒ 这里 reindex
        'rank_ic': _rl(rr['ic_series'].reindex(rb).values),
        'decile': [_rl(dec_nav[:, g]) for g in range(n_grp)],
        'ls': _rl(ls), 'turn_series': _rl(turns),
        'caliber': ('日频=持有期内逐日 mark；期频=每 %d 交易日一条；'
                    '十档/多空=费前（与 IC 同一套前视收益，未做涨跌停/停牌可交易性处理）'
                    % fm.FWD),
    }
    if verbose:
        print('    core ✓ 日频 %d 点 · 期频 %d 期 · PearsonIC %+.4f · RankIC %+.4f'
              % (len(d_dates), len(rr['ex']), float(np.nanmean(ics_p)),
                 float(np.nanmean(rr['ic_series'].values))))
    return out


def strip_for(nm, fac, rr, B, dates, cols, close, cost, window, STYLE, verbose=True):
    """剥风格四条净值（原 / 剥市值 / 剥成交额 / 剥两者）—— 期频；`raw` 直接复用已算好的 `rr`。"""
    import pandas as pd
    import factor_miner as fm
    from loop_metrics import neutral_rank

    fv = fac.values.astype('float64')
    variants = {}
    for k, sty in (('lncap', ['lncap']), ('lnamt', ['lnamt']), ('both', ['lncap', 'lnamt'])):
        variants[k] = pd.DataFrame(
            neutral_rank(fv, [STYLE[x] for x in sty]), index=dates, columns=cols)
    navs = {'raw': _rl(np.cumprod(1.0 + np.asarray(rr['ex'], dtype='float64')))}
    calmars = {'raw': _r(rr['calmar'])}
    for k, x in variants.items():
        r = fm.evaluate_real(x, close, nm + '#' + k, cost=cost, window=window, with_ex=True)
        if r is None:
            return None
        navs[k] = _rl(np.cumprod(1.0 + np.asarray(r['ex'], dtype='float64')))
        calmars[k] = _r(r['calmar'])
    if verbose:
        print('    strip ✓ 剥Calmar 原 %s / 市值 %s / 成交额 %s / 两者 %s'
              % (calmars.get('raw'), calmars.get('lncap'), calmars.get('lnamt'),
                 calmars.get('both')))
    return {'dates': _dates_of(rr['ex'].index), 'navs': navs, 'calmars': calmars,
            'caliber': '期频超额净值（成本已扣）；剥市值=对 lncap 截面秩中性化，'
                       '剥成交额=lnamt，剥两者=同时做'}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pools', default='all,300,500,1000')
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--only-new', action='store_true', help='只补缺该段数据的因子')
    ap.add_argument('--stage', default='all', choices=['core', 'strip', 'all'])
    ap.add_argument('--cost', type=float, default=0.004)
    ap.add_argument('--window', type=int, default=5)
    ap.add_argument('--panel_cache', default='off', choices=['off', 'use', 'build'])
    a = ap.parse_args()

    import build_facs as BF
    LE = BF._prep_main()
    LE.set_panel_cache(a.panel_cache)
    os.makedirs(CURVE_DIR, exist_ok=True)

    items = []
    for p in [x.strip() for x in a.pools.split(',') if x.strip()]:
        nodes = BF.load_bank_nodes(p)
        if not nodes:
            continue
        ics = BF.load_archive_ic(p)
        lib = {r['expr']: r for r in BF.parse_library(p)}
        for expr, nd in nodes.items():
            L = lib.get(expr) or {}
            items.append(dict(pool=p, no=L.get('no') or BF._fallback_name(expr), expr=expr,
                              node=nd, gen=L.get('gen') or '',
                              ic_ref=(ics.get(expr) if ics.get(expr) is not None else L.get('ic')),
                              ae_lib=L.get('ann_ex'), _nm=None))
    seen, uniq = set(), []
    for it in items:
        if it['expr'] in seen:
            continue
        seen.add(it['expr'])
        it['_nm'] = BF._name_of(it)
        uniq.append(it)

    def _path(nm):
        return os.path.join(CURVE_DIR, '%s.json' % nm)

    def _need(it):
        p = _path(it['_nm'])
        if not os.path.exists(p):
            return True
        if not a.only_new:
            return True
        try:
            d = json.load(io.open(p, encoding='utf-8'))
        except Exception:
            return True
        if a.stage == 'core':
            return 'nav_e' not in d
        if a.stage == 'strip':
            return 'strip' not in d
        return ('nav_e' not in d) or ('strip' not in d)

    uniq = [it for it in uniq if _need(it)]
    if a.limit:
        uniq = uniq[:a.limit]
    print('=' * 96)
    print('因子曲线离线预算 → %s' % os.path.relpath(CURVE_DIR, ROOT))
    print('  stage=%s · 待算 %d 个%s' % (a.stage, len(uniq),
                                        '  [增量 --only-new]' if a.only_new else ''))
    print('=' * 96)
    if not uniq:
        print('  ⇒ 无待算因子')
        return 0

    t0 = time.time()
    bf = LE.base_fields()
    B, dates, cols, close = bf['B'], bf['dates'], bf['cols'], bf['close']
    print('面板载入完成: %d 日 x %d 股 (%.0fs)' % (len(dates), len(cols), time.time() - t0))

    STYLE = None
    if a.stage in ('strip', 'all'):
        sf = LE.style_features(B)
        STYLE = {k: sf[k] for k in ('lncap', 'lnamt')}
        del sf
        print('风格特征(lncap/lnamt) 就绪')

    ok, bad = 0, []
    for i, it in enumerate(uniq, 1):
        nm = it['_nm']
        t1 = time.time()
        print('[%d/%d] %s  %s' % (i, len(uniq), nm, it['expr'][:56]))
        p = _path(nm)
        cur = {}
        if os.path.exists(p):
            try:
                cur = json.load(io.open(p, encoding='utf-8'))
            except Exception:
                cur = {}
        try:
            fac, rr, sign = _aligned(it, B, dates, cols, close, a.cost, a.window)
            if rr is None:
                bad.append(nm)
                continue
            if a.stage in ('core', 'all'):
                c = core_for(nm, fac, rr, a.cost, a.window)
                if c is None:
                    bad.append(nm)
                    continue
                c.update(pool=it['pool'], expr=it['expr'], sign=sign, gen=it['gen'])
                cur.update(c)
            if a.stage in ('strip', 'all'):
                s = strip_for(nm, fac, rr, B, dates, cols, close, a.cost, a.window, STYLE)
                if s is not None:
                    cur['strip'] = s
            cur.setdefault('pool', it['pool'])
            cur.setdefault('expr', it['expr'])
            cur.setdefault('sign', sign)
            with io.open(p, 'w', encoding='utf-8') as f:
                json.dump(cur, f, ensure_ascii=False, separators=(',', ':'))
            ok += 1
        except Exception as e:
            print('    [!] 失败 %s: %s: %s' % (nm, type(e).__name__, e))
            bad.append(nm)
        print('    （%.0fs · 文件 %.1f KB）'
              % (time.time() - t1, os.path.getsize(p) / 1024.0 if os.path.exists(p) else 0))
    print()
    print('完成 %d 个 · 失败 %d 个 · 用时 %.0fs' % (ok, len(bad), time.time() - t0))
    if bad:
        print('  失败清单: %s' % ', '.join(bad[:12]))
    return 0


if __name__ == '__main__':
    sys.exit(main())
