# -*- coding: utf-8 -*-
"""standard_test.py — 统一因子检验模板 (my_test/standard)
一次跑齐: ①引擎指标复现校验 ②全A宽池频率扫描 ③沪深300/中证500成分内 ④风格归因 ⑤分段独立验证
输出 <name>_<时间戳>_<起>_<止>_report.txt + 同名 _report.png (4子图)

用法:
  python standard_test.py --fac=D:\\...\\xxx_fac.pkl --name=gen31 \
     --e-ic=0.0607 --e-icir=0.586 --e-ann=5.3 --e-dd=-9.2 --e-cal=0.576 --e-sh=0.794 --e-turn=35.7 --e-nego=2
  python standard_test.py --fac=b:f11   --name=f11        # 内置: f11/barra/gen31
可选: --start=20180101 --freq=15 --cost=0.007 --cost-name=实盘(滑点千1.5)
      --freqs=5,10,15,21 --seg_n=3 --seg_need=2 --pool_mode=A --neg
口径: T日信号->T+1收盘买入(涨停停牌剔)->持有FWD日(跌停停牌顺延);池=universe;基准=同池等权
成分内: --pool_mode=A 池内排名(默认, 原行为) / B 全市场排名后取成分内 / S 静态成分(验幸存者偏差)
成本: 单一事实源 engine/cost_presets.py（往返成本, 扣在单向换手率上）
      档位: 实盘(滑点千1.5)=0.0046 / 实盘(滑点千2)=0.0056 / 主用档=0.004 / 压力档=0.007(默认)
"""
import os, sys, time, bisect
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
MYTEST = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(MYTEST, 'engine'))
from cost_presets import COST_PRESETS, STRESS_COST, resolve_cost, cost_label  # noqa: E402  成本档单一事实源
PANEL = r"D:\loop_code\engine\panel.h5"
UNIVERSE = r"D:\loop_code\engine\universe.h5"
BARRA = r"D:\loop_code\engine\barra.h5"
IDX_PATH = {'300': r'E:\rq\constituents\index\000300.XSHG.h5',
            '500': r'E:\rq\constituents\index\000905.XSHG.h5'}

FAC_SRC, NAME, START, FWD_MAIN, COST = None, None, 20180101, 15, STRESS_COST
FREQS, FORCE_NEG, ENGINE = [5, 10, 15, 21], False, {}
SEG_N, SEG_NEED = 3, 2                 # 分段独立验证: 分几段 / 至少几段为正
POOL_MODE = 'A'                        # 成分内口径:
                                       #   A=先取成分再在成分内排名(默认, 原行为)
                                       #   B=先在全池排名再取成分内 pct>1-top_pct
                                       #   S=静态成分(始终用最新一次快照) -> 用于验证幸存者偏差
for a in sys.argv[1:]:
    if a.startswith('--pool_mode='): POOL_MODE = a[12:].upper()
    if a.startswith('--fac='): FAC_SRC = a[6:]
    elif a.startswith('--name='): NAME = a[7:]
    elif a.startswith('--start='): START = int(a[8:])
    elif a.startswith('--freq='): FWD_MAIN = int(a[7:])
    elif a.startswith('--cost='): COST = float(a[7:])
    elif a.startswith('--cost-name='): COST = resolve_cost(a[12:])   # 按档名指定(见 cost_presets.py)
    elif a.startswith('--freqs='): FREQS = [int(x) for x in a[8:].split(',')]
    elif a.startswith('--seg_n='): SEG_N = int(a[8:])
    elif a.startswith('--seg_need='): SEG_NEED = int(a[11:])
    elif a == '--neg': FORCE_NEG = True
    elif a.startswith('--e-'): ENGINE[a[4:].split('=')[0]] = float(a.split('=')[1])
if not FAC_SRC:
    print("需要 --fac=<pkl|b:f11|b:barra|b:gen31>"); sys.exit(1)
if FWD_MAIN not in FREQS:               # 主口径必须在扫描集内, 否则 [1]/[4]/图 会错标频率
    FREQS = sorted(set(FREQS) | {FWD_MAIN})
if not NAME:
    NAME = 'builtin_' + FAC_SRC.split(':')[1] if FAC_SRC.startswith('b:') \
        else os.path.splitext(os.path.basename(FAC_SRC))[0]
STAMP, t0 = time.strftime('%Y-%m-%d %H:%M:%S'), time.time()

# ---------- 数据 ----------
P = {}
with pd.HDFStore(PANEL, 'r') as st:
    for k in ['close', 'open', 'high', 'low', 'turnover', 'mktcap',
              'limit_up', 'limit_down']:
        P[k] = st[k].astype('float64')
close = P['close']; T_, S_ = close.shape
with pd.HDFStore(UNIVERSE, 'r') as st:
    universe = st['universe'].reindex(index=close.index, columns=close.columns).fillna(False)
cv, vol = close.values, P['turnover'].values
mcv = P['mktcap'].values                 # 市值(指数池市值加权基准)
lu, ld = P['limit_up'].values, P['limit_down'].values
bad = ~(np.isfinite(cv) & (cv > 0)) | ~(vol > 0)
buyable = (~(np.isfinite(lu) & (cv >= lu - 1e-6))) & (~bad)
sellable = (~(np.isfinite(ld) & (cv <= ld + 1e-6))) & (~bad)
next_sell = np.minimum.accumulate(
    np.where(sellable, np.arange(T_)[:, None], T_ - 1)[::-1], axis=0)[::-1].astype(np.int32)
dates_all = close.index.values
pos_of = {d: i for i, d in enumerate(dates_all)}
col_of = {c: j for j, c in enumerate(close.columns)}
ar = np.arange(S_); U = universe.values
idx = close.index[close.index >= START]
dpos = np.searchsorted(dates_all, idx)

def load_fac(src):
    if src.startswith('b:'):
        tag = src[2:]
        if tag == 'f11':
            o, h, l = P['open'], P['high'], P['low']
            ret = close.pct_change(fill_method=None)
            intraday = close / o - 1.0
            with np.errstate(divide='ignore', invalid='ignore'):
                f = ((h / l.where(l > 1e-9)) / l) * intraday * intraday * ret
            return f.rolling(60, min_periods=30).mean()
        if tag in ('barra', 'barra_style'):
            with pd.HDFStore(BARRA, 'r') as st:
                return (st['barra_residual_volatility'].astype('float64')
                        + st['barra_non_linear_size'].astype('float64')).shift(1)
        if tag == 'gen31':
            p = os.path.join(MYTEST, 'gen31', 'gen31_fac.pkl')
            if not os.path.exists(p): print("缺", p); sys.exit(1)
            return pd.read_pickle(p)
        print("未知内置:", tag); sys.exit(1)
    d = pd.read_pickle(src)
    return d.get('raw', list(d.values())[0]) if isinstance(d, dict) else d

fac_raw = load_fac(FAC_SRC)
if not isinstance(fac_raw, pd.DataFrame): fac_raw = pd.DataFrame(fac_raw)
fac_raw = fac_raw.reindex(index=close.index, columns=close.columns).astype('float64')
print(f"数据就绪 {time.time()-t0:.0f}s 覆盖 {100*float(np.isfinite(fac_raw.values).mean()):.1f}%", flush=True)

def ic_series(fac, FWD):
    fr_ = (close.shift(-(1 + FWD)) / close.shift(-1) - 1).reindex(index=idx)
    fv, rv = fac.reindex(index=idx).values, fr_.values
    out = []
    for i in range(len(idx)):
        u = U[dpos[i]]; m = np.isfinite(fv[i][u]) & np.isfinite(rv[i][u])
        out.append(np.nan if m.sum() < 50 else spearmanr(fv[i][u][m], rv[i][u][m])[0])
    return pd.Series(out, index=idx).dropna()

ic_raw = ic_series(fac_raw, 5)
_s = float(np.sign(ic_raw.mean())) or 1.0
if FORCE_NEG:
    sign, why = -1.0, '强制取反(--neg)'
elif 'ic' in ENGINE:
    # 令有效因子 IC 与引擎 IC 同号: sign = sign(引擎IC) x sign(原式IC)
    # (原式IC与引擎反号 => 取反, 即引擎入库方向 = 原式取反, 对应"文档缺取反标记")
    sign = (float(np.sign(ENGINE['ic'])) or 1.0) * _s
    why = f"按引擎IC {ENGINE['ic']:+.4f} 定向(原式IC {ic_raw.mean():+.4f})"
else:
    sign, why = _s, f"按样本IC {ic_raw.mean():+.4f} 自动定向"
fac = fac_raw * sign
ic5, ic15 = ic_series(fac, 5), ic_series(fac, 15)
print(f"方向 {sign:+.0f} ({why}); 原始IC5 {ic_raw.mean():+.4f} -> 采用后 {ic5.mean():+.4f}", flush=True)

# ---------- 回测核心 ----------
def run_pool(FWD, cost=COST, members=None, top_pct=0.10, min_pool=100, min_hold=10):
    top_r, mkt_r, mkc_r, dts, turns, nh = [], [], [], [], [], []
    prev = None                       # 上期【实际持仓】(可买过滤后), 用于真实换手
    cdates = members[1] if members else None
    for d in idx[::FWD][:-1]:
        i_pos = int(np.searchsorted(dates_all, d))
        f = fac.loc[d][U[i_pos]].dropna()
        j_all = None
        if cdates is not None:
            j = (len(members[0]) - 1) if POOL_MODE == 'S' \
                else bisect.bisect_right(cdates, d) - 1   # S=静态成分(最新快照)->验幸存者偏差
            if j < 0: continue
            mem = members[0][j][1]
            f_mem = f[[s for s in f.index if s in mem]]      # 全成分池(基准口径, 两模式一致)
            j_all = np.array([col_of[s] for s in f_mem.index])
            if POOL_MODE == 'B':
                # B: 先在全池算分位, 再截取"成分内且位于全池前 top_pct"的股票
                pct_all = f.rank(method='average', pct=True)
                f = f_mem[[s for s in f_mem.index if pct_all[s] > 1.0 - top_pct]]
            else:
                f = f_mem
        if len(f) < min_pool: continue
        nxt = idx[idx > d]
        if len(nxt) <= FWD: continue
        d1, d2 = nxt[0], nxt[FWD]
        i1, i2 = pos_of[d1], pos_of[d2]
        # 顶档: 用分位秩(>1-top_pct)选取 -> 并列值不被人为打散(适配离散因子)
        # B 模式已由"全池分位"截取 -> 直接全持有(再做二次池内排名会只剩 3 只, 无意义)
        top = (list(f.index) if (POOL_MODE == 'B' and cdates is not None)
               else list(f.index[f.rank(method='average', pct=True) > 1.0 - top_pct]))
        j_top = np.array([col_of[s] for s in top])
        if j_all is None:
            j_all = np.array([col_of[s] for s in f.index])
        ok = buyable[i1]
        kt, ka = j_top[ok[j_top]], j_all[ok[j_all]]
        if len(kt) < min_hold or len(ka) < 40: continue
        r_all = cv[next_sell[i2], ar] / cv[i1] - 1.0
        rt, rm = np.nanmean(r_all[kt]), np.nanmean(r_all[ka])
        if not (np.isfinite(rt) and np.isfinite(rm)): continue
        # 市值加权基准(指数池更贴近指数本身; 宽池仅作参考)
        rk, w = r_all[ka], mcv[i1][ka]
        mw = np.isfinite(rk) & np.isfinite(w) & (w > 0)
        rmc = float((np.where(mw, rk, 0.0) * np.where(mw, w, 0.0)).sum() / w[mw].sum()) \
            if mw.any() else np.nan
        # 真实换手: 用"可买过滤后"的实际持仓集合(hold), 而非名义 Top 集合
        hold = set(np.asarray(top)[ok[j_top]])
        keep = len(hold & prev) / max(len(prev), 1) if prev else 0.0
        top_r.append(rt - (1 - keep) * cost); mkt_r.append(rm); mkc_r.append(rmc)
        dts.append(d); turns.append(1 - keep); nh.append(len(kt))
        prev = hold
    tr, mr = pd.Series(top_r, index=dts), pd.Series(mkt_r, index=dts)
    mc_ = pd.Series(mkc_r, index=dts)
    mc_ = mc_.where(mc_.notna(), mr)               # 权重异常期退回等权
    ex, exc = tr - mr, tr - mc_
    yrs = max(len(tr) * FWD / 243, 1e-9)
    nt, nm, nmc = (1 + tr).cumprod(), (1 + mr).cumprod(), (1 + mc_).cumprod()
    ne, nec = (1 + ex).cumprod(), (1 + exc).cumprod()
    ddt, dde = (nt / nt.cummax() - 1).min(), (ne / ne.cummax() - 1).min()
    ddec = (nec / nec.cummax() - 1).min()
    ant = nt.iloc[-1] ** (1 / yrs) - 1
    anm, anmc = nm.iloc[-1] ** (1 / yrs) - 1, nmc.iloc[-1] ** (1 / yrs) - 1
    ane, anec = ne.iloc[-1] ** (1 / yrs) - 1, nec.iloc[-1] ** (1 / yrs) - 1
    ann_f = np.sqrt(243.0 / FWD)  # 年化因子: 每期波动 -> 年化(Sharpe = mean/std*ann_f)
    sd = lambda s: s.std() / ann_f if s.std() > 0 else np.nan
    seg = [float((1 + x).prod() - 1)
           for x in np.array_split(ex.values.astype(float), max(1, SEG_N)) if len(x)]
    return dict(tr=tr, mr=mr, mc=mc_, ex=ex, exc=exc,
                ann_t=ant, ann_m=anm, ann_mc=anmc, ann_e=ane, ann_ec=anec,
                dd_t=ddt, dd_e=dde, dd_ec=ddec,
                cal_t=ant / abs(ddt) if ddt < 0 else np.nan,
                cal_e=ane / abs(dde) if dde < 0 else np.nan,
                cal_ec=anec / abs(ddec) if ddec < 0 else np.nan,
                sh_t=tr.mean() / sd(tr), sh_e=ex.mean() / sd(ex),
                turn=float(np.mean(turns)), n_hold=int(np.median(nh)),
                n_period=len(tr), seg=seg,
                yr={y: (1 + g).prod() - 1 for y, g in ex.groupby(ex.index // 10000)})

print("\n[1] 全A 宽池 Top10% 频率扫描")
scan = {}
for fwd in FREQS:
    scan[fwd] = run_pool(fwd)
    r = scan[fwd]
    print(f"  fwd={fwd:<3d} 组合{r['ann_t']*100:6.2f}% 池等权{r['ann_m']*100:6.2f}% "
          f"池市值{r['ann_mc']*100:6.2f}% 超额(等权){r['ann_e']*100:+6.2f}% "
          f"超额(市值){r['ann_ec']*100:+6.2f}% 回撤{r['dd_e']*100:7.2f}% "
          f"Calmar等权{r['cal_e']:5.2f} 市值{r['cal_ec']:5.2f} "
          f"Sharpe{r['sh_e']:5.2f} 换手{r['turn']*100:5.1f}% 期数{r['n_period']}", flush=True)
best_fwd = max(scan, key=lambda k: scan[k]['cal_e'] if np.isfinite(scan[k]['cal_e']) else -9)
main = scan.get(FWD_MAIN, scan[best_fwd])
print(f"  => 最优频率 {best_fwd} 日 (按Calmar), 主口径 {FWD_MAIN} 日", flush=True)

print(f"\n[2] 成分内增强 (freq={FWD_MAIN}, Top10%)")
def load_const(path):
    import h5py
    items = []
    with h5py.File(path, 'r') as f:
        cd = [x.decode() if isinstance(x, bytes) else str(x) for x in f['change_dates'][:]]
        for d in cd:
            mem = set(x.decode() if isinstance(x, bytes) else str(x) for x in f['components'][d][:])
            items.append((int(d.replace('-', '')), mem))
    return sorted(items, key=lambda x: x[0])

idx_res = {}
for tag in ('300', '500'):
    items = load_const(IDX_PATH[tag])
    r = run_pool(FWD_MAIN, members=(items, [x[0] for x in items]),
                 min_pool=(10 if POOL_MODE == 'B' else 50))
    idx_res[tag] = r
    print(f"  {tag}: 组合{r['ann_t']*100:6.2f}% 等权池{r['ann_m']*100:6.2f}% "
          f"市值加权池{r['ann_mc']*100:6.2f}% 超额(等权){r['ann_e']*100:+6.2f}% "
          f"超额(市值加权){r['ann_ec']*100:+6.2f}% 回撤{r['dd_ec']*100:7.2f}% "
          f"Calmar{r['cal_ec']:5.2f} 持仓中位{r['n_hold']}只 期数{r['n_period']}", flush=True)

print("\n[3] 风格归因快检 (截面秩相关; 负=偏小市值/低成交/低换手/低价)")
mc = P['mktcap'].replace(0, np.nan)
tr20 = (P['turnover'] / mc).rolling(20, min_periods=5).mean()
feat = {'lncap': np.log(mc.replace(0, np.nan).values),
        'lnamt': np.log(P['turnover'].rolling(20, min_periods=5).mean().replace(0, np.nan).values),
        'lntr': np.log(tr20.replace(0, np.nan).values),
        'lnpx': np.log(close.values)}
style = {}
for k, arr in feat.items():
    vals = []
    for d in idx[::5]:
        i_pos = int(np.searchsorted(dates_all, d)); u = U[i_pos]
        f_, x_ = fac.loc[d].values, arr[i_pos]
        m = u & np.isfinite(f_) & np.isfinite(x_)
        if m.sum() >= 200: vals.append(spearmanr(f_[m], x_[m])[0])
    s = pd.Series(vals)
    style[k] = (float(s.mean()), float((s > 0).mean()))
    print(f"  {k:6s} 均值 {s.mean():+.3f}  正相关期占比 {(s>0).mean():.0%}", flush=True)

# ---------- 风格归因: 逐步剥除 市值/成交额 暴露 (rank -> 逐日截面回归残差 -> rank; 项目 B 口径) ----------
def _rank_np(X):
    Xf = np.where(np.isfinite(X), X, np.inf)
    order = np.argsort(np.argsort(Xf, axis=1), axis=1).astype(np.float64)
    n = np.isfinite(X).sum(axis=1, keepdims=True)
    r = order / np.maximum(n - 1, 1)
    r[~np.isfinite(X)] = np.nan
    return r

def neutralize(f0, fields):
    """逐日截面: 因子 rank 对风格暴露(同样 rank 化)线性回归取残差, 再 rank。
    fields=[] 原样返回。剥后超额若大幅衰减 -> 因子收益主要来自该风格暴露。"""
    if not fields:
        return f0
    Y = _rank_np(f0.values.astype(np.float64))
    Zs = [_rank_np(np.asarray(z, dtype=np.float64)) for z in fields]
    out = np.full(Y.shape, np.nan)
    for t in range(Y.shape[0]):
        m = np.isfinite(Y[t])
        for z in Zs:
            m &= np.isfinite(z[t])
        k = int(m.sum())
        if k < 100:
            continue
        A = np.column_stack([np.ones(k)] + [z[t][m] for z in Zs])
        coef, *_ = np.linalg.lstsq(A, Y[t][m], rcond=None)
        out[t, m] = Y[t][m] - A @ coef
    return pd.DataFrame(_rank_np(out), index=f0.index, columns=f0.columns)

print(f"\n[风格归因] 逐步剥除 市值/成交额 暴露 (freq={FWD_MAIN})", flush=True)
_G0 = fac
ATTR_V = [('原版', []), ('剥市值', [feat['lncap']]),
          ('剥成交额', [feat['lnamt']]), ('剥两者', [feat['lncap'], feat['lnamt']])]
attr = []
for _nm, _fl in ATTR_V:
    fac = neutralize(_G0, _fl)
    r = run_pool(FWD_MAIN)
    icv = float(ic_series(fac, 5).mean())
    # ★ 双口径(2026-09-13, 用户要求固化): 等权=规模中性(纯 alpha); 市值加权=更接近真实指数。
    #   **零额外成本** —— run_pool 已同时返回两套 (见其返回 dict 的 ann_ec/cal_ec/dd_ec)。
    attr.append(dict(name=_nm, ic=icv, ann=r['ann_e'], dd=r['dd_e'], cal=r['cal_e'],
                     sh=r['sh_e'], turn=r['turn'],
                     ec=r['ann_ec'], ddc=r['dd_ec'], calc=r['cal_ec'],
                     ng=sum(1 for x in r['yr'].values() if x < 0)))
    print(f"  {_nm:<6s} IC{icv:+.4f} 超额(等权){r['ann_e']*100:+6.2f}% "
          f"超额(市值){r['ann_ec']*100:+6.2f}% 回撤(等权){r['dd_e']*100:7.2f}% "
          f"Calmar等权{r['cal_e']:5.2f} 市值{r['cal_ec']:5.2f} Sharpe{r['sh_e']:5.2f} "
          f"换手{r['turn']*100:5.1f}% 负年{attr[-1]['ng']}", flush=True)
fac = _G0                                     # 还原为对齐后的原始因子

# ---------- 十档分层: 检验"是否只有极端档有效 / 最优档在哪" ----------
def decile_stats(FWD, members=None, min_pool=100, n_grp=10):
    """D1=因子值最高档 … D10=最低档(与 Top10% 多头口径一致)。
    返回 (每档年化费后超额, 单调性Spearman, 最优档idx, 期数)。
    单调性 = Spearman(档位序 D1..D10, 超额); >0 表示"因子值越高超额越高"。
    若最优档 ≠ D1 或 单调性低 -> 该因子不适合"取最极端头部做多"。"""
    rows, pool_r = [], []
    cdates = members[1] if members else None
    for d in idx[::FWD][:-1]:
        i_pos = int(np.searchsorted(dates_all, d))
        f = fac.loc[d][U[i_pos]].dropna()
        if cdates is not None:
            j = bisect.bisect_right(cdates, d) - 1
            if j < 0: continue
            mem = members[0][j][1]
            f = f[[s for s in f.index if s in mem]]
        if len(f) < min_pool: continue
        nxt = idx[idx > d]
        if len(nxt) <= FWD: continue
        d1, d2 = nxt[0], nxt[FWD]
        i1, i2 = pos_of[d1], pos_of[d2]
        j_all = np.array([col_of[s] for s in f.index])
        okf = buyable[i1][j_all]
        k_all = j_all[okf]
        if len(k_all) < 40: continue
        r_all = cv[next_sell[i2], ar] / cv[i1] - 1.0
        dec = np.minimum((np.floor((1.0 - f.rank(pct=True).values) * n_grp)
                          ).astype(int), n_grp - 1)[okf]
        rk = r_all[k_all]
        rows.append([np.nanmean(rk[dec == g]) if (dec == g).sum() >= 5 else np.nan
                     for g in range(n_grp)])
        pool_r.append(np.nanmean(rk))
    Rd = pd.DataFrame(rows)
    pr = pd.Series(pool_r)
    yrs = max(len(Rd) * FWD / 243, 1e-9)
    ex = [float((1 + (Rd[g] - pr).dropna()).prod() ** (1 / yrs) - 1) for g in Rd.columns]
    mono = float(spearmanr(np.arange(n_grp, 0, -1), ex)[0])
    best = int(np.nanargmax(ex))
    return ex, mono, best, len(Rd)

print(f"\n[十档分层] freq={FWD_MAIN} (D1=因子值最高档, D10=最低档; 费前)", flush=True)
dec_ex, dec_mono, dec_best, dec_n = decile_stats(FWD_MAIN)
print('  ' + ' | '.join(f"D{i+1} {x*100:+.2f}%" for i, x in enumerate(dec_ex)), flush=True)
print(f"  单调性(档序vs超额){dec_mono:+.3f}  最优档 D{dec_best+1}  期数{dec_n}  "
      f"顶档校验 D1={dec_ex[0]*100:+.2f}% vs 主口径 {main['ann_e']*100:+.2f}%", flush=True)

# ---------- 报告 ----------
def mark(ok, warn):
    return '✅' if ok else ('⚠' if warn else '❌')

L = []
L.append("=" * 88)
L.append(f"标准因子检验报告 —— {NAME}")
L.append(f"生成 {STAMP}   因子源 {FAC_SRC}   采用方向 {sign:+.0f} ({why})")
L.append(f"区间 {START}~   口径: universe可交易池 Top10%等权, T+1收盘买入, "
         f"成本 {cost_label(COST)}   成分内口径 {POOL_MODE}")
L.append("=" * 88)
if ENGINE:
    L.append("")
    L.append("【0】引擎指标复现校验 (本地 freq=5 口径)")
    r5 = scan.get(5)
    L.append(f"{'指标':<10s}{'引擎':>10s}{'本地':>10s}{'差异':>10s}   判定")
    def row(nm, e, v, ok1, ok2, fmt='{:.4f}'):
        L.append(f"{nm:<10s}{e:>10.4f}{v:>10.4f}{v-e:>+10.4f}   {mark(ok1, ok2)}")
    if 'ic' in ENGINE:
        row('IC(fwd5)', ENGINE['ic'], ic5.mean(), abs(ic5.mean()-ENGINE['ic']) <= 0.005,
            abs(ic5.mean()-ENGINE['ic']) <= 0.015)
    if 'icir' in ENGINE:
        v = ic5.mean()/ic5.std()
        row('ICIR', ENGINE['icir'], v, abs(v-ENGINE['icir']) <= 0.08, abs(v-ENGINE['icir']) <= 0.20)
    if r5 is not None:
        if 'ann' in ENGINE:
            row('超额%/年', ENGINE['ann'], r5['ann_e']*100, abs(r5['ann_e']*100-ENGINE['ann']) <= 1,
                abs(r5['ann_e']*100-ENGINE['ann']) <= 3)
        if 'dd' in ENGINE:
            row('回撤%', ENGINE['dd'], r5['dd_e']*100, abs(r5['dd_e']*100-ENGINE['dd']) <= 2,
                abs(r5['dd_e']*100-ENGINE['dd']) <= 6)
        if 'cal' in ENGINE:
            row('Calmar', ENGINE['cal'], r5['cal_e'], abs(r5['cal_e']-ENGINE['cal']) <= 0.10,
                abs(r5['cal_e']-ENGINE['cal']) <= 0.25)
        if 'sh' in ENGINE:
            row('Sharpe', ENGINE['sh'], r5['sh_e'], abs(r5['sh_e']-ENGINE['sh']) <= 0.10,
                abs(r5['sh_e']-ENGINE['sh']) <= 0.30)
        if 'turn' in ENGINE:
            row('换手%/期', ENGINE['turn'], r5['turn']*100, abs(r5['turn']*100-ENGINE['turn']) <= 5,
                abs(r5['turn']*100-ENGINE['turn']) <= 10)
        if 'nego' in ENGINE:
            ng = sum(1 for x in r5['yr'].values() if x < 0)
            L.append(f"{'负年数':<10s}{ENGINE['nego']:>10.0f}{ng:>10d}{ng-ENGINE['nego']:>+10.0f}   "
                     f"{mark(ng == ENGINE['nego'], abs(ng-ENGINE['nego']) <= 1)}")
    L.append("  (✅|差≤阈值  ⚠|接近  ❌|偏差大; 方向已按引擎IC定向, 若整体反号说明文档缺取反标记)")
L.append("")
L.append("【1】全A 宽池 Top10% 频率扫描")
L.append(f"{'freq':<6s}{'组合年化':>10s}{'池等权':>10s}{'池市值加权':>12s}{'超额等权':>10s}"
         f"{'超额市值':>10s}{'Calmar等权':>11s}{'Calmar市值':>11s}"
         f"{'Sharpe':>8s}{'换手':>8s}{'负年':>5s}{'期数':>6s}")
for fwd in FREQS:
    r = scan[fwd]
    ng = sum(1 for x in r['yr'].values() if x < 0)
    L.append(f"{fwd:<6d}{r['ann_t']*100:9.2f}%{r['ann_m']*100:9.2f}%{r['ann_mc']*100:11.2f}%"
             f"{r['ann_e']*100:+9.2f}%{r['ann_ec']*100:+9.2f}%"
             f"{r['cal_e']:11.3f}{r['cal_ec']:11.3f}"
             f"{r['sh_e']:8.3f}{r['turn']*100:7.1f}%{ng:>5d}{r['n_period']:>6d}")
L.append("  (基准: 池等权=全A 可交易股票等权; 池市值加权=按 mktcap 加权(宽池下仅作参考)。"
         "'超额等权'是**规模中性**口径=纯选股 alpha; '超额市值'含规模倾斜, 更接近可交付产品。)")
L.append(f"  IC(fwd5) {ic5.mean():+.4f} / ICIR {ic5.mean()/ic5.std():+.3f}   "
         f"IC(fwd15) {ic15.mean():+.4f} / ICIR {ic15.mean()/ic15.std():+.3f}")
L.append("")
L.append(f"【2】成分内增强 (freq={FWD_MAIN}, Top10%)")
L.append(f"{'池':<8s}{'组合年化':>10s}{'池等权':>10s}{'池市值加权':>12s}{'超额等权':>12s}"
         f"{'超额市值加权':>14s}{'Calmar(市值加权)':>18s}{'持仓':>6s}{'换手':>8s}{'期数':>6s}")
for tag in ('300', '500'):
    r = idx_res[tag]
    L.append(f"idx{tag:<5s}{r['ann_t']*100:9.2f}%{r['ann_m']*100:9.2f}%{r['ann_mc']*100:11.2f}%"
             f"{r['ann_e']*100:+11.2f}%{r['ann_ec']*100:+13.2f}%{r['cal_ec']:18.3f}"
             f"{r['n_hold']:6d}{r['turn']*100:7.1f}%{r['n_period']:>6d}")
L.append("  (基准对照: 池等权=成分等权; 池市值加权≈指数本身。成分内超额≈0或负 -> 指数增强不可行)")
L.append("")
L.append("【3】风格归因 (截面秩相关均值 / 正相关期占比)")
for k in ('lncap', 'lnamt', 'lntr', 'lnpx'):
    L.append(f"  {k:6s} {style[k][0]:+.3f}   {style[k][1]:.0%}")
L.append("")
L.append(f"【4】年度超额 (主口径 freq={FWD_MAIN})")
for y in sorted(main['yr'].keys()):
    L.append(f"  {y}  {main['yr'][y]*100:+7.2f}%")
L.append(f"  负年 {sum(1 for x in main['yr'].values() if x < 0)} / {len(main['yr'])}")
L.append("")

def _segline(r):
    so = sum(1 for x in r['seg'] if x > 0)
    txt = " / ".join(f"段{i+1}{x*100:+.2f}%" for i, x in enumerate(r['seg']))
    return txt + f"  -> {'✅通过' if so >= SEG_NEED else '❌未通过'} ({so}/{len(r['seg'])}段为正)"

L.append(f"【5】分段独立验证 (费后超额序列均分 {SEG_N} 段, 需 >={SEG_NEED} 段累计为正; 防单段行情撑全样本)")
L.append(f"  主口径 freq={FWD_MAIN}(全A宽池): " + _segline(main))
for tag in ('300', '500'):
    L.append(f"  idx{tag}成分内: " + _segline(idx_res[tag]))
L.append("")
L.append(f"【6】风格归因: 逐步剥除 市值/成交额 暴露 (rank→逐日截面回归残差→rank; 主口径 freq={FWD_MAIN})")
L.append(f"{'版本':<8s}{'IC(fwd5)':>11s}{'超额等权':>11s}{'超额市值':>11s}{'回撤等权':>11s}"
         f"{'Calmar等权':>11s}{'Calmar市值':>11s}{'Sharpe':>9s}{'换手':>9s}{'负年':>5s}")
for a in attr:
    L.append(f"{a['name']:<8s}{a['ic']:>11.4f}{a['ann']*100:>10.2f}%{a['ec']*100:>10.2f}%"
             f"{a['dd']*100:>10.2f}%{a['cal']:>11.3f}{a['calc']:>11.3f}"
             f"{a['sh']:>9.3f}{a['turn']*100:>8.1f}%{a['ng']:>5d}")
L.append("  (剥后超额/Calmar 大幅衰减 -> 因子收益主要来自市值/成交额风格暴露, 独立信息有限)")
L.append("  ★ 双口径(2026-09-13): '超额等权'=规模中性=纯选股 alpha(主判据); "
         "'超额市值'=按 mktcap 加权基准(≈真实指数)。若**等权为正但市值口径转负** "
         "-> 该因子的'超额'主要来自组合等权带来的**规模倾斜**, 对指数增强不可用。")
L.append("")
L.append(f"【7】十档分层超额 (freq={FWD_MAIN}, D1=因子值最高档 … D10=最低档; 年化【费前】超额, 未扣成本)")
L.append('  ' + '  '.join(f"D{i+1} {x*100:+.2f}%" for i, x in enumerate(dec_ex)))
_poll = ('⚠️ D1<D2: 最极端档反而更差(顶档被污染), 宜剔D1或用D2'
         if dec_ex[0] < dec_ex[1] else 'D1 为最高档')
L.append(f"  单调性(档序 vs 超额 Spearman) {dec_mono:+.3f}   最优档 D{dec_best+1}   "
         f"期数 {dec_n}   {_poll}")
_lc = main['turn'] * COST * (243.0 / FWD_MAIN)
L.append(f"  顶档校验: D1费前 {dec_ex[0]*100:+.2f}% − 成本≈{_lc*100:.2f}%"
         f"(换手{main['turn']*100:.1f}%×{COST:.4f}×{243/FWD_MAIN:.1f}期) = "
         f"{(dec_ex[0]-_lc)*100:+.2f}%  vs 主口径费后 {main['ann_e']*100:+.2f}%")
L.append("  判读: 单调性>0.5 且最优=D1 -> 顶档做多可信; 最优档非D1 / 单调性≈0 -> "
         "该因子不适合取最极端头部(可试对应档 或多空两头)")

TS = time.strftime('%Y%m%d_%H%M_%S')            # 时间戳(约定: 放在名称后、起止日期前)
END = int(idx[-1]) if len(idx) else START
STEM = f'{NAME}_{TS}_{START}_{END}'
txt_path = os.path.join(HERE, f'{STEM}_report.txt')
with open(txt_path, 'w', encoding='utf-8') as f:
    f.write("\n".join(L) + "\n")
print("\n".join(L))

# ---------- 图 ----------
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
plt.rcParams['axes.unicode_minus'] = False
fig, axes = plt.subplots(2, 4, figsize=(22, 10))
ax = axes[0][0]
ax.plot(main['tr'].index.astype(str), (1+main['tr']).cumprod().values, lw=1.8,
        color='tab:red', label=f"组合 年化{main['ann_t']*100:.1f}%")
ax.plot(main['mr'].index.astype(str), (1+main['mr']).cumprod().values, lw=1.2,
        color='gray', label=f"池等权 年化{main['ann_m']*100:.1f}%")
ax.plot(main['ex'].index.astype(str), (1+main['ex']).cumprod().values, lw=1.3,
        color='tab:blue', ls='--', label=f"超额 年化{main['ann_e']*100:+.1f}% Cal{main['cal_e']:.2f}")
ax.axhline(1, color='k', lw=0.5); ax.legend(fontsize=9, loc='upper left')
# ★ 指标框(2026-09-13 用户要求): 左上净值图补「总收益 / 最大回撤 / 夏普 / 卡玛」
#   两行分别给【组合】与【超额(等权基准)】—— 超额那行才是我们真正关心的。
#   放右下角(ha=right): 净值曲线从 1 涨到右上, 右下区域通常是空的, 不会压曲线。
_nt = (1 + main['tr']).cumprod(); _ne = (1 + main['ex']).cumprod()
ax.text(0.985, 0.035,
        "组合  总收益{:+.1f}%  最大回撤{:.1f}%\n"
        "        夏普{:.2f}   卡玛{:.2f}\n"
        "超额  总收益{:+.1f}%  最大回撤{:.1f}%\n"
        "        夏普{:.2f}   卡玛{:.2f}".format(
            (_nt.iloc[-1] - 1) * 100, main['dd_t'] * 100, main['sh_t'], main['cal_t'],
            (_ne.iloc[-1] - 1) * 100, main['dd_e'] * 100, main['sh_e'], main['cal_e']),
        transform=ax.transAxes, fontsize=8.0, ha='right', va='bottom', linespacing=1.35,
        bbox=dict(boxstyle='round,pad=0.3', fc='lightyellow', ec='gray', alpha=0.93))
ax.set_title(f"{NAME} 全A宽池Top10% freq={FWD_MAIN} 费后{COST:.4f}"); ax.grid(alpha=0.3)
ax = axes[0][1]
xs = [str(k) for k in FREQS]
ax.bar(xs, [scan[k]['ann_e']*100 for k in FREQS], color='tab:green', alpha=0.8)
ax2 = ax.twinx()
ax2.plot(xs, [scan[k]['cal_e'] for k in FREQS], 'o-', color='tab:orange', label='Calmar')
ax.set_title('频率扫描: 超额(柱) vs Calmar(线)'); ax.set_xlabel('调仓周期(交易日)')
ax.grid(alpha=0.3); ax2.legend(fontsize=9)
ax.set_xticks(range(len(FREQS))); ax.set_xticklabels(xs)  # x 轴是 freq 整数
# [0,2] 风格归因表(逐步剥除市值/成交额)
ax = axes[0][2]; ax.axis('off')
_cells = [[a['name'], f"{a['ic']:+.4f}", f"{a['ann']*100:+.2f}%", f"{a['dd']*100:.2f}%",
           f"{a['cal']:.3f}", f"{a['sh']:.3f}", f"{a['turn']*100:.1f}%", f"{a['ng']}"]
          for a in attr]
_tb = ax.table(cellText=_cells,
               colLabels=['版本', 'IC', '超额/年', '回撤', 'Calmar', 'Sharpe', '换手', '负年'],
               loc='center', cellLoc='center')
_tb.auto_set_font_size(False); _tb.set_fontsize(9); _tb.scale(1.0, 1.6)
ax.set_title(f'风格归因: 逐步剥除 市值/成交额 (freq={FWD_MAIN})', fontsize=11)
# [0,3] 十档分层超额 (红=最优档)
ax = axes[0][3]
ax.bar([f'D{i+1}' for i in range(len(dec_ex))], [x*100 for x in dec_ex],
       color=['tab:red' if i == dec_best else 'tab:blue' for i in range(len(dec_ex))])
ax.axhline(0, color='k', lw=0.5)
ax.set_title(f'十档分层超额 (freq={FWD_MAIN})\n单调性 {dec_mono:+.2f}  最优 D{dec_best+1}',
             fontsize=10)
ax.grid(alpha=0.3)
ax = axes[1][0]
for tag, c in (('300', 'tab:purple'), ('500', 'tab:brown')):
    r = idx_res[tag]
    ax.plot(r['ex'].index.astype(str), (1+r['ex']).cumprod().values, lw=1.4, color=c,
            label=f"idx{tag} 超额{r['ann_e']*100:+.1f}% Cal{r['cal_e']:.2f}")
ax.axhline(1, color='k', lw=0.5); ax.legend(fontsize=9)
ax.set_title(f"成分内增强 (freq={FWD_MAIN}): 300/500 超额累计"); ax.grid(alpha=0.3)
ax = axes[1][1]
ys = sorted(main['yr'].keys())
ax.bar([str(y) for y in ys], [main['yr'][y]*100 for y in ys],
       color=['tab:red' if main['yr'][y] < 0 else 'tab:blue' for y in ys])
ax.axhline(0, color='k', lw=0.5); ax.set_title(f'{NAME} 年度超额 (freq={FWD_MAIN})')
ax.grid(alpha=0.3)
ax.set_xticks(range(len(ys))); ax.set_xticklabels([str(y) for y in ys], rotation=0)  # x 轴是年份
# [1,2] 剥风格后 超额(柱) vs Calmar(线)
ax = axes[1][2]
_nmz = [a['name'] for a in attr]
ax.bar(_nmz, [a['ann']*100 for a in attr], color='tab:green', alpha=0.8)
ax.axhline(0, color='k', lw=0.5)
ax2 = ax.twinx()
ax2.plot(_nmz, [a['cal'] for a in attr], 'o-', color='tab:orange', label='Calmar')
ax.set_title('剥风格后: 超额(柱) vs Calmar(线)'); ax.grid(alpha=0.3); ax2.legend(fontsize=9)
# [1,3] 分段独立验证: 各段累计费后超额
ax = axes[1][3]
_ss = [('全A', main['seg']), ('idx300', idx_res['300']['seg']),
       ('idx500', idx_res['500']['seg'])]
_w = 0.8 / len(_ss)
for _k, (_lb, _sg) in enumerate(_ss):
    ax.bar(np.arange(len(_sg)) + _k * _w, [x * 100 for x in _sg], width=_w, label=_lb)
ax.axhline(0, color='k', lw=0.5)
ax.set_xticks(np.arange(len(main['seg'])) + _w)
ax.set_xticklabels([f'段{i+1}' for i in range(len(main['seg']))])
ax.set_title('分段独立验证: 各段累计费后超额', fontsize=10)
ax.legend(fontsize=8); ax.grid(alpha=0.3)
# 仅对时间序列子图(净值/成分内)压缩日期刻度; 其余子图已显式设好
for a, is_ts in zip(axes.ravel(), [True, False, False, False, True, False, False, False]):
    if not is_ts:
        continue
    xt = list(main['tr'].index.astype(str))[::max(1, len(main['tr'])//12)]
    a.set_xticks(xt); a.set_xticklabels([x[:4] for x in xt], rotation=0)
fig.suptitle(f"标准因子检验 —— {NAME}  ({STAMP})", fontsize=14)
fig.tight_layout(rect=[0, 0, 1, 0.97])
png_path = os.path.join(HERE, f'{STEM}_report.png')
fig.savefig(png_path, dpi=110)
print(f"\n已保存: {txt_path}\n        {png_path}   耗时 {time.time()-t0:.0f}s")


