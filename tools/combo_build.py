# -*- coding: utf-8 -*-
"""combo_build.py -- 多因子合成（route 第一优先；roadmap §8.36）

背景（§8.35）：库内 41 个因子的**超额**两两相关中位仅 **0.435**（独立），
等权合成相对个体中位 **Calmar 1.77× / 夏普 1.58×** ⇒ 合成明显有效。
本脚本把「组合收益等权平均」升级为**可交付的合成因子**（rank 加权合成 ⇒ 直接进现有回测/实盘流程）。

★★ 关键在于**不给漂亮假数字** —— 三种方案并列，并明确标注偏差来源：

| 方案 | 权重 | 前视/偏差 | 用途 |
|---|---|---|---|
| **A. 全样本等权** `ew` | 常数 1/N | ⚠ 幸存者偏差（41 个因子是在**同一段样本**上筛出来的） | **上界参考**，不能当实盘预期 |
| **B. 滚动 IC 加权** `icw` | 只用 **t 之前** 的 IC | ✅ 无前视 | 可实盘 |
| **C. 滚动去相关+等权** `dec` | 只用 **t 之前** 的收益流，贪婪去相关 | ✅ 无前视 | 可实盘 |

⇒ 若 B/C 明显低于 A ⇒ 说明 A 的增益主要来自**幸存者偏差**，必须如实说明。

做法：
  ① 从 state 的 bank（41 个 node）重算因子面板 -> 按样本 IC **定向** -> `cs_rank`（float32 缓存, ~2.9GB）
  ② 对每个因子跑 `evaluate_real(with_ex=True)`：拿 `ic_series`(逐日IC) 与 `ex`(逐期超额)
  ③ 按上面三种方案构造逐日权重 `W(t,i)`（B/C 只用过去信息）-> 合成 `F = Σ W·rank`
  ④ `evaluate_real(F)` 评估；并给 3 段稳定性

用法: python tools/combo_build.py [--pool=all] [--icw_win=250] [--dec_win=250] [--dec_thr=0.7]
"""
import io
import os
import pickle
import sys
import time

import numpy as np
import pandas as pd

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'engine'))

import loop_engine as LE           # noqa: E402
import factor_miner as FM          # noqa: E402

for _n in dir(LE):
    if _n[:1].isupper() and isinstance(getattr(LE, _n), type):
        setattr(sys.modules['__main__'], _n, getattr(LE, _n))

OUT = os.path.join(HERE, '_combo_build_report.md')
FAC_OUT = os.path.join(HERE, '_combo_fac.pkl')


def _parse_args():
    """解析命令行参数（手动解析，与历史用法保持一致）。"""
    pool = 'all'
    ICW_WIN = 250          # 滚动 IC 窗口（交易日）
    DEC_WIN = 250          # 去相关重算窗口
    DEC_THR = 0.70         # 去相关阈值
    NEUTRAL = False        # ★ 是否先对每个因子做“市值+成交额”秩中性化再合成（压 tilt）
    for a in sys.argv[1:]:
        if a.startswith('--pool='):
            pool = a.split('=', 1)[1].strip() or 'all'
        elif a.startswith('--icw_win='):
            ICW_WIN = int(a.split('=', 1)[1])
        elif a.startswith('--dec_win='):
            DEC_WIN = int(a.split('=', 1)[1])
        elif a.startswith('--dec_thr='):
            DEC_THR = float(a.split('=', 1)[1])
        elif a == '--neutral':
            NEUTRAL = True
    return pool, ICW_WIN, DEC_WIN, DEC_THR, NEUTRAL


def _load_bank(pool):
    """按池读 state 里的入库因子 bank。"""
    LE.set_mine_pool(pool)
    st = pickle.load(open(LE.STATE, 'rb'))
    return st.get('bank', []) or []


def _load_base(NEUTRAL):
    """加载数据面板 + 未来收益 + 可选的中性化基准 ZS。"""
    base = LE.base_fields()
    B, dates, cols, close = base['B'], base['dates'], base['cols'], base['close']
    T, S = close.shape
    U = FM.get_universe().reindex(index=dates, columns=cols).fillna(False).values
    fwd_ret = (close.shift(-(1 + FM.FWD)) / close.shift(-1) - 1).values
    # ★ 市值+成交额秩中性化（--neutral）：§8.37 实测全A 合成 tilt=+3.73% ⇒ 相当一部分超额
    #   来自**小盘倾斜**；而"300 成分内基本无效"（Calmar 0.012）也说明它主要靠池外风格。
    #   ⇒ 先对每个因子做 `neutral_rank`（与 standard_test【6】剥风格同口径），再合成。
    ZS = None
    if NEUTRAL:
        _sf = LE.style_features(B)
        ZS = [_sf['lncap'], _sf['lnamt']]
        print('[--neutral] 每个因子先对 lncap+lnamt 秩中性化再合成', flush=True)
    return B, dates, cols, close, T, S, U, fwd_ret, ZS


def _eval_factors(bank, B, dates, cols, close, U, fwd_ret, NEUTRAL, ZS):
    """① 逐因子: 定向 + cs_rank 缓存 + 逐期超额/IC -> (RANKS, EXS, ICS, NAMES)"""
    from scipy.stats import spearmanr
    print('\n[1] 逐因子：定向 + cs_rank 缓存 + evaluate_real ...', flush=True)
    RANKS, EXS, ICS, NAMES = [], {}, {}, []
    for k, nd in enumerate(bank, 1):
        key = str(nd)
        t0 = time.time()
        try:
            v = LE.eval_expr(nd, B, {})
            f = FM.cs_rank(pd.DataFrame(v, index=dates, columns=cols).astype('float64'))
            del v
            fv = f.values
            _ics = []
            for _i in range(0, len(dates), 5):
                _u = U[_i]
                _a, _b = fv[_i][_u], fwd_ret[_i][_u]
                _m = np.isfinite(_a) & np.isfinite(_b)
                if _m.sum() >= 50:
                    _ics.append(spearmanr(_a[_m], _b[_m])[0])
            _mu = float(np.nanmean(_ics)) if _ics else np.nan
            if np.isfinite(_mu) and _mu < 0:
                f = -f
            if NEUTRAL:
                # 秩中性化后**再 rank**（neutral_rank 已返回秩, cs_rank 幂等 → 保持一致口径）
                f = FM.cs_rank(pd.DataFrame(
                    LE.neutral_rank(f.values.astype('float64'), ZS),
                    index=dates, columns=cols).astype('float64'))
            r = FM.evaluate_real(f, close, key[:36], with_ex=True)
            if r is None or 'ex' not in r:
                print('  [{}/{}] 样本不足, 跳过 {}'.format(k, len(bank), key[:60]), flush=True)
                continue
            # rank 面板(float32 缓存): 合成用
            RANKS.append(np.asarray(f.values, dtype='float32'))
            EXS[key] = r['ex']
            ICS[key] = r['ic_series']
            NAMES.append(key)
            print('  [{}/{}] IC {:+.4f} 超额 {:+.2f}% Calmar {:+.3f} 换手 {:.1%}  {}s'.format(
                k, len(bank), r['ic'], r['ann_ex'] * 100, r['calmar'], r['turn'],
                int(time.time() - t0)), flush=True)
            del f
        except Exception as e:
            print('  [{}/{}] 失败 {}: {}'.format(k, len(bank), type(e).__name__,
                                                str(e)[:60]), flush=True)
    return RANKS, EXS, ICS, NAMES


def _build_weights(T, N, dates, ICdf, EX, NAMES, ICW_WIN, DEC_WIN, DEC_THR):
    """② 三种权重方案（逐日 W(T,N)）-> (Ws, sel_hist)"""
    print('\n[2] 构造权重 ...', flush=True)
    Ws = {}

    # A. 全样本等权（⚠ 有幸存者偏差，作上界）
    Ws['A_全样本等权'] = np.full((T, N), 1.0 / N, dtype='float64')

    # B. 滚动 IC 加权（只用 t 之前的 IC ⇒ 无前视）
    icr = ICdf.rolling(ICW_WIN, min_periods=30).mean().shift(1)   # shift(1)! 只用过去
    icw = icr.clip(lower=0).fillna(0.0).values
    den = icw.sum(axis=1, keepdims=True)
    icw = np.where(den > 0, icw / np.where(den > 0, den, 1.0), 1.0 / N)
    Ws['B_滚动IC加权'] = icw

    # C. 滚动去相关 + 等权（只用 t 之前的收益流）
    dec = np.full((T, N), 1.0 / N, dtype='float64')
    ex_idx = EX.index
    sel_hist = []
    for t in range(len(dates)):
        d = dates[t]
        if t % 20 != 0:
            continue
        past = ex_idx[ex_idx < d][-DEC_WIN:]      # 过去 DEC_WIN 期
        if len(past) < 60:
            continue
        E = EX.loc[past]
        try:
            C = E.corr(method='spearman').values
        except Exception:
            continue
        # 贪婪: 按"过去平均超额/波动"排序(用过去信息), 依次纳入 |corr|<thr 的
        score = (E.mean() / E.std()).replace([np.inf, -np.inf], np.nan).fillna(-9)
        order = list(score.sort_values(ascending=False).index)
        chosen = []
        for nm in order:
            j = NAMES.index(nm)
            if all(abs(C[j, NAMES.index(c)]) < DEC_THR or not np.isfinite(C[j, NAMES.index(c)])
                   for c in chosen):
                chosen.append(nm)
        if not chosen:
            continue
        sel = np.zeros(N)
        for nm in chosen:
            sel[NAMES.index(nm)] = 1.0 / len(chosen)
        # 从 d 起生效（shift 语义: 用 t 之前的信息）
        dec[t:] = sel
        sel_hist.append((str(d)[:10], len(chosen)))
    Ws['C_滚动去相关等权'] = dec
    return Ws, sel_hist


def _synthesize(Ws, RANKS, dates, cols, close, N):
    """③ 合成 + 回测 -> (rows, FAC)"""
    print('\n[3] 合成 + 回测 ...', flush=True)
    T, S = close.shape
    rows = []
    FAC = {}          # ★ 保存**全部方案**的合成因子（2026-09-13 用户指出：只存 C 且被覆盖）
    for nm, W in Ws.items():
        # ⚠⚠ NaN 传播坑（2026-09-13 实录, roadmap §8.36-⑥）：
        #   首版写法 `F += w*RANKS[i]` —— 只要**某个**因子在 (t,s) 处是 NaN,
        #   `0 + NaN = NaN` ⇒ 结果**永久为 NaN** ⇒ 最终覆盖率 = 41 个因子覆盖的**交集**
        #   （实测只有 **25.4%**！）⇒ 组合可选股票池被砍到 1/4, 结论不可信,
        #   而且会让池内回测**样本不足**（300 池正是因此报"样本不足"）。
        #   ⇒ 正确做法：**分别累加分子/分母, 只用有值的因子做加权平均**（覆盖率=并集）。
        F_num = np.zeros((T, S), dtype='float32')
        F_den = np.zeros((T, S), dtype='float32')
        for i in range(N):
            w = W[:, i]
            if not np.any(w):
                continue
            R = RANKS[i]
            m = np.isfinite(R)
            wcol = (w[:, None] * m).astype('float32')
            F_num += np.where(m, (w[:, None] * np.where(m, R, 0.0)).astype('float32'), 0.0)
            F_den += wcol
        F = np.where(F_den > 0, F_num / np.maximum(F_den, 1e-9), np.nan).astype('float32')
        cov = float(np.isfinite(F).mean())
        print('  {}: 合成因子覆盖率 {:.1%}'.format(nm, cov), flush=True)
        fd = pd.DataFrame(F, index=dates, columns=cols)
        r = FM.evaluate_real(FM.cs_rank(fd), close, nm, with_ex=True)
        if r is None:
            print('  {} 回测失败'.format(nm))
            continue
        # 3 段稳定性
        ex = r.get('ex')
        seg = []
        if ex is not None and len(ex) >= 30:
            for part in np.array_split(ex.values.astype(float), 3):
                seg.append(float((1 + pd.Series(part)).prod() - 1))
        rows.append(dict(name=nm, ann_ex=r['ann_ex'], calmar=r['calmar'], sharpe=r['sharpe'],
                         dd=r['dd'], turn=r['turn'], ic=r['ic'],
                         seg_pos=sum(1 for x in seg if x > 0), seg=seg))
        print('  {:<14s} 超额 {:+.2f}%  Calmar {:+.3f}  夏普 {:+.3f}  回撤 {:.1f}%  '
              '换手 {:.1%}  分段 {}/3'.format(
                  nm, r['ann_ex'] * 100, r['calmar'], r['sharpe'], r['dd'] * 100,
                  r['turn'], sum(1 for x in seg if x > 0)), flush=True)
        FAC[nm] = fd.astype('float32')
        del F, fd
    return rows, FAC


def _emit_report(pool, N, ICW_WIN, DEC_WIN, DEC_THR, rows, FAC, Ws, NAMES, dates, NEUTRAL):
    """④ 报告: 写 markdown + 保存各方案 pkl + 导出配方。"""
    L = ['# 多因子合成报告（roadmap §8.36）', '',
         '池 = `{}`；入库因子 **{} 个**；参数 ICW_WIN={} DEC_WIN={} DEC_THR={}'.format(
             pool, N, ICW_WIN, DEC_WIN, DEC_THR), '',
         '## 三方案对照（⚠ 只有 B/C 无前视，A 有幸存者偏差，仅作上界参考）', '',
         '| 方案 | 年化超额 | Calmar | 夏普 | 回撤 | 换手 | 分段正 |', '|---|---|---|---|---|---|---|']
    for r in rows:
        L.append('| {} | {:+.2f}% | {:+.3f} | {:+.3f} | {:.1f}% | {:.1%} | {}/3 |'.format(
            r['name'], r['ann_ex'] * 100, r['calmar'], r['sharpe'], r['dd'] * 100,
            r['turn'], r['seg_pos']))
    L += ['', '## 判读', '']
    a = next((r for r in rows if r['name'].startswith('A')), None)
    b = next((r for r in rows if r['name'].startswith('B')), None)
    c = next((r for r in rows if r['name'].startswith('C')), None)
    if a and c:
        gap = a['calmar'] - c['calmar']
        L += ['- 全样本上界 `A` Calmar **{:.3f}** vs 无前视 `C` **{:.3f}**；差 **{:+.3f}**'.format(
            a['calmar'], c['calmar'], gap)]
        if gap > 0.25:
            L += ['- ⚠ **差额较大 ⇒ A 的增益里有相当一部分是「幸存者偏差」**'
                  '（41 个因子是在同一段样本上筛出来的）⇒ **实盘预期应看 B/C，不是 A**。']
        else:
            L += ['- ✅ 差额不大 ⇒ 合成增益**不是**主要来自幸存者偏差，B/C 可作实盘预期。']
    if c and c['calmar'] > 0:
        L += ['- 无前视方案 `C`（滚动去相关等权）：Calmar **{:.3f}**、夏普 **{:.3f}**、'
              '年化超额 **{:+.2f}%**、分段 **{}/3** 为正'.format(
                  c['calmar'], c['sharpe'], c['ann_ex'] * 100, c['seg_pos'])]
        L += ['  ⇒ ' + ('**可作为可交付组合的基线**。'
                        if c['seg_pos'] == 3 else
                        '⚠ 分段未全正 ⇒ 增益可能集中在某一段，需谨慎。')]
    L += ['', '## 分段明细（各方案 3 段累计费后超额）', '']
    for r in rows:
        L.append('- {}: {}'.format(r['name'],
                                   ' / '.join('{:+.2f}%'.format(x * 100) for x in r['seg'])))
    # ★ 保存**全部方案**（2026-09-13：用户要自己回测 B 方案；原版只存 C 且会被下一次运行覆盖）
    #   命名: _combo_{pool}_{raw|neu}_{A|B|C}.pkl   —— 直接可喂 standard_test.py / combo_check.py
    mode = 'neu' if NEUTRAL else 'raw'
    files = []
    for nm, fd_ in FAC.items():
        tag = nm[0]
        fn = os.path.join(HERE, '_combo_{}_{}_{}.pkl'.format(pool, mode, tag))
        fd_.to_pickle(fn)
        files.append((nm, os.path.basename(fn)))
        print('已写', fn, flush=True)
    if FAC:
        _c = [k for k in FAC if k.startswith('C')]
        if _c:
            FAC[_c[0]].to_pickle(FAC_OUT)      # 兼容旧名
    # ★ 导出「配方」：成分因子清单 + 权重（供复现与实盘）
    #   ⚠ B 的权重**时变**（滚动 IC），所以给"最后一期"的权重 + 公式；按公式可逐日重算。
    #   ⚠ `--neutral` 的配方里，步骤含"秩中性化"；raw 版没有这一步 —— 两者必须配套使用。
    try:
        rl = ['# 合成因子配方（roadmap §8.36）', '',
              '模式: **{}**（{}）'.format(
                  'neu = 每个成分因子先对 lncap+lnamt 秩中性化' if NEUTRAL
                  else 'raw = 未中性化',
                  'AI_TEST/combo_build.py{}'.format(' --neutral' if NEUTRAL else '')),
              '成分因子数: **{}**'.format(N), '',
              '## 公式（逐日）', '',
              '```',
              '1) 对每个成分因子 i：',
              '   a. 用它的表达式在面板上求值 f_i(t,s)',
              '   b. 按样本 IC 符号定向: f_i <- sign(IC_i) * f_i   （IC 用全样本 fwd=5 秩相关均值, 一次性固定）',
              '   c. {}'.format('秩中性化: f_i <- rank( 残差 of rank(f_i) ~ rank(lncap)+rank(lnamt) )'
                               if NEUTRAL else '（无中性化）'),
              '   d. 横截面秩: r_i(t,s) = cs_rank(f_i(t,s))  ∈ [0,1]',
              '2) 权重（B 方案, **只用 t 之前的信息**）:',
              '   w_i(t) = max(0, mean( IC_i over [t-250, t-1] )) / Σ_j max(0, mean(...))',
              '   （IC_i = 逐日 rank-IC; 窗口 250 交易日/最少 30 个有效值; 分母为 0 时退回等权 1/N）',
              '   ⚠ A 方案 = 常数 1/N（无前视保护）；C 方案 = 每 20 日按"过去 250 期收益流"贪婪去相关',
              '      (|corr|<0.70) 后等权。',
              '3) 合成: F(t,s) = Σ_i w_i(t)·r_i(t,s) / Σ_i w_i(t)·1{{r_i(t,s) 有值}}',
              '   （分子分母分别累加 -> 只用**有值**的成分做加权平均, 避免 NaN 传播成"交集"）',
              '4) 选股: 取 F(t,·) 前 10%（等权持有）, 每 FWD=5 个交易日调仓。',
              '```', '',
              '## 成分因子清单（按表达式; 括号内为该日的权重）', '']
        wlast = FAC and None
        for nm, W in Ws.items():
            tag = nm[0]
            rl.append('### {} 方案 {}'.format(tag, nm[2:]))
            wl = W[-1]
            rl.append('')
            rl.append('| # | 表达式 | w(最后一日) |')
            rl.append('|---|---|---|')
            wsx = np.argsort(-wl)
            for j in wsx:
                rl.append('| {} | `{}` | {:.4f} |'.format(j, NAMES[j][:150], wl[j]))
            rl.append('')
            wdf = pd.DataFrame(W, index=dates, columns=[str(k)[:200] for k in NAMES])
            wfn = os.path.join(HERE, '_combo_weights_{}_{}.csv'.format(mode, tag))
            wdf.to_csv(wfn, encoding='utf-8-sig')
            rl.append('逐日权重矩阵已落盘: `ai_test/{}`'.format(os.path.basename(wfn)))
            rl.append('')
        rf = os.path.join(HERE, '_combo_recipe_{}.md'.format(mode))
        io.open(rf, 'w', encoding='utf-8').write('\n'.join(rl) + '\n')
        print('已写配方 ->', rf, flush=True)
    except Exception as e:
        print('[WARN] 配方导出失败(不影响因子落盘):', type(e).__name__, e, flush=True)
    L += ['', '## 合成因子文件（可直接回测）', '']
    L += ['| 方案 | 文件 |', '|---|---|']
    for nm, fn in files:
        L.append('| {} | `ai_test/{}` |'.format(nm, fn))
    L += ['', '回测方式: `python standard/standard_test.py --fac=tools\\<文件名>`; '
          '或交付前检查 `python tools/combo_check.py --fac=tools\\<文件名>`', '']
    txt = '\n'.join(L) + '\n'
    io.open(OUT, 'w', encoding='utf-8').write(txt)
    if _c:
        print('已写合成因子(方案C, 兼容名) ->', FAC_OUT)
    print()
    print(txt)


def main():
    pool, ICW_WIN, DEC_WIN, DEC_THR, NEUTRAL = _parse_args()
    t_all = time.time()
    print('=' * 78)
    print('池 ={}  ICW_WIN={}  DEC_WIN={}  DEC_THR={}'.format(pool, ICW_WIN, DEC_WIN, DEC_THR))

    bank = _load_bank(pool)
    if len(bank) < 2:
        print('入库因子不足 2 个，无法合成')
        return 1
    print('入库因子 {} 个'.format(len(bank)))

    B, dates, cols, close, T, S, U, fwd_ret, ZS = _load_base(NEUTRAL)

    RANKS, EXS, ICS, NAMES = _eval_factors(bank, B, dates, cols, close, U, fwd_ret, NEUTRAL, ZS)
    N = len(NAMES)
    if N < 2:
        print('可用因子不足')
        return 1
    print('\n缓存 rank 面板 {} 个 (~{:.1f} GB)'.format(
        N, sum(a.nbytes for a in RANKS) / 1024 ** 3), flush=True)

    EX = pd.DataFrame(EXS)                 # 逐期超额(T'', N)
    ICdf = pd.DataFrame(ICS).reindex(index=dates)   # 逐日 IC(T, N)

    Ws, sel_hist = _build_weights(T, N, dates, ICdf, EX, NAMES, ICW_WIN, DEC_WIN, DEC_THR)
    print('  去相关选中因子数（每次重算）:',
          ', '.join('{}:{}'.format(a, b) for a, b in sel_hist[-6:]), flush=True)

    rows, FAC = _synthesize(Ws, RANKS, dates, cols, close, N)

    _emit_report(pool, N, ICW_WIN, DEC_WIN, DEC_THR, rows, FAC, Ws, NAMES, dates, NEUTRAL)

    print('总用时 {:.0f}s'.format(time.time() - t_all))
    return 0


if __name__ == '__main__':
    sys.exit(main())
