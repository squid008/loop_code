# -*- coding: utf-8 -*-
"""验证广发ML手册结论: "特征中性化(去行业+市值)对最终因子无明显改进"
====================================================================
做法(复刻广发语境, 用我方数据):
  同一批量价特征, 两种喂给 LGBM 的方式:
    A) raw      : 原始特征(含市值/换手等风格暴露特征), 直接训练
    B) neutral  : 每个特征先对 [行业哑变量 + ln市值] 逐日截面 OLS 取残差, 再训练
  训练 2018-2022 -> 测试 2023~ 逐5日截面, 比较测试期 排序IC / ICIR / 胜率,
  并看 Top 特征重要性是否被风格霸榜。
运行: D:\miniconda3\envs\rqdata\python.exe verify_neutral.py
"""
import time
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
import ml_common as MC
import lightgbm as lgb

FWD = 5
TRAIN_END = 20221231
TEST_START = 20230101
N_SAMPLE = 500000
PARAMS = dict(objective='regression', learning_rate=0.05, n_estimators=300,
              num_leaves=15, min_child_samples=300, subsample=0.8,
              colsample_bytree=0.8, verbose=-1, n_jobs=8, seed=0)


def main():
    t0 = time.time()
    D = MC.load()
    dates, cols, P, U, G = D['dates'], D['cols'], D['P'], D['U'], D['G']
    close = P['close']
    T, S = close.shape
    print(f"load ok {time.time()-t0:.1f}s  {T}日 x {S}股 "
          f"({dates[0]}..{dates[-1]})")

    # ---------- 特征面板(t日只用<=t信息) ----------
    ret = close.pct_change()
    mc = P['mktcap']
    feats = {
        'mom5': close / close.shift(5) - 1,
        'mom20': close / close.shift(20) - 1,
        'mom60': close / close.shift(60) - 1,
        'std20': ret.rolling(20, min_periods=10).std(),
        'std60': ret.rolling(60, min_periods=30).std(),
        'amt20': np.log(P['turnover'].rolling(20, min_periods=10).mean() + 1.0),
        'vp20': P['volume'] / P['volume'].rolling(20, min_periods=10).mean(),
        'turn20': (P['turnover'] / mc).rolling(20, min_periods=10).mean(),
        'amp20': ((P['high'] - P['low']) / close).rolling(20, min_periods=10).mean(),
        'ln_mktcap': np.log(mc),
    }
    FNAMES = list(feats.keys())
    fr = close.shift(-(1 + FWD)) / close.shift(-1) - 1.0     # 前瞻收益标签

    # ---------- 每 FWD 日采一个截面, 训练/测试按年度切 ----------
    rebal = np.arange(T)[::FWD]
    rebal = rebal[(rebal >= 5) & (rebal + 1 + FWD < T)]
    Rdates = dates[rebal]
    trb = np.where(Rdates <= TRAIN_END)[0]
    teb = np.where(Rdates >= TEST_START)[0]
    print(f"截面 {len(rebal)}: 训练 {len(trb)} "
          f"({Rdates[trb[0]]}~{Rdates[trb[-1]]}), 测试 {len(teb)} "
          f"({Rdates[teb[0]]}~{Rdates[teb[-1]]})")

    Xraw = np.stack([feats[f].values[rebal] for f in FNAMES], axis=2)  # (nR,S,F)
    fin = np.isfinite(Xraw)
    ln = np.log(mc.values[rebal])
    pool = (U.values & (G >= 0))[rebal]
    fwd_ok = np.isfinite(fr.values[rebal])
    base = pool & fwd_ok

    # ---------- neutral 特征: 每日截面 OLS 残差([1, lnmc, 行业]) ----------
    print("逐截面中性化(行业+市值) ...")
    Xneu = np.full_like(Xraw, np.nan)
    tn = time.time()
    for i in range(len(rebal)):
        m = base[i] & fin[i].all(axis=1)
        g = G[rebal[i]][m]
        m2 = g >= 0
        idx = np.where(m)[0][m2]
        if len(idx) < 50:
            continue
        yy = Xraw[i][idx]
        Xm = np.ones((len(idx), 1 + 1 + 31))
        Xm[:, 1] = ln[i][idx]
        Xm[np.arange(len(idx)), 2 + g[m2]] = 1.0
        coef, *_ = np.linalg.lstsq(Xm, yy, rcond=None)
        Xneu[i][idx] = yy - Xm @ coef
        if (i + 1) % 60 == 0:
            print(f"  neu {i+1}/{len(rebal)} {time.time()-tn:.0f}s")
    print(f"中性化完成 {time.time()-tn:.1f}s")

    # ---------- 组装训练样本 (y=截面rank) ----------
    def sample_rows(X3, idxs):
        Xs, ys = [], []
        for i in idxs:
            m = base[i] & fin[i].all(axis=1) & np.isfinite(X3[i]).all(axis=1)
            if m.sum() < 200:
                continue
            y = fr.values[rebal[i]][m]
            Xs.append(X3[i][m])
            ys.append(pd.Series(y).rank(pct=True).values)
        X = np.vstack(Xs)
        y = np.concatenate(ys)
        if len(y) > N_SAMPLE:
            rng = np.random.default_rng(0)
            sel = rng.choice(len(y), N_SAMPLE, replace=False)
            X, y = X[sel], y[sel]
        return X, y

    XA_tr, yA_tr = sample_rows(Xraw, trb)
    Xneu_drop = Xneu[:, :, :-1]        # ln_mktcap 中性化残差恒≈0(近常数) -> 删除,
    FN_NEU = FNAMES[:-1]               # 避免 LGBM 在噪声列上分裂的 importance 假象
    XN_tr, yN_tr = sample_rows(Xneu_drop, trb)
    print(f"训练样本 raw={len(yA_tr):,} neutral={len(yN_tr):,}")

    # ---------- 训练 + 测试 IC ----------
    def train_eval(Xtr, ytr, Xte_ref, fnames):
        model = lgb.LGBMRegressor(**PARAMS)
        model.fit(Xtr, ytr)
        ics = []
        for i in teb:
            m = (base[i] & fin[i].all(axis=1)
                 & np.isfinite(Xte_ref[i]).all(axis=1))
            if m.sum() < 200:
                continue
            y = fr.values[rebal[i]][m]
            p = model.predict(Xte_ref[i][m])
            ic = spearmanr(p, y)[0]
            if np.isfinite(ic):
                ics.append(ic)
        try:                                    # gain 比 split-count 更有意义
            impv = model.booster_.feature_importance(importance_type='gain')
        except Exception:
            impv = model.feature_importances_
        imp = sorted(zip(fnames, impv), key=lambda z: -z[1])[:5]
        return np.array(ics), imp

    out = {}
    for tag, Xtr, ytr, Xte, fn in [
            ('raw', XA_tr, yA_tr, Xraw, FNAMES),
            ('neutral', XN_tr, yN_tr, Xneu_drop, FN_NEU)]:
        ics, imp = train_eval(Xtr, ytr, Xte, fn)
        out[tag] = ics
        print(f"\n[{'raw' if tag=='raw' else 'neutral':7s}] 测试 {len(ics)} 截面 (gain重要性)")
        print(f"  RankIC={ics.mean():+.4f}  IR={ics.mean()/ics.std():+.3f}  "
              f"胜率={(ics>0).mean()*100:.0f}%  |IC|>0.02占={(np.abs(ics)>0.02).mean()*100:.0f}%")
        print(f"  Top重要: " + ", ".join(f"{k}={v:.0f}" for k, v in imp))
        # 年度明细
        yr = Rdates[teb][:len(ics)] // 10000
        dfi = pd.DataFrame({'yr': yr, 'ic': ics})
        g = dfi.groupby('yr')['ic'].agg(['mean', 'count'])
        print("  年度: " + "  ".join(f"{y}:{r['mean']:+.4f}({int(r['count'])})"
              for y, r in g.iterrows()))
    print(f"\ntotal {time.time()-t0:.0f}s")


if __name__ == '__main__':
    main()
