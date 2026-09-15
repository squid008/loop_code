# -*- coding: utf-8 -*-
"""闸门阈值标定:
1) 用引擎去重段精确口径(rank_rows(v[::FWD])[::step])算 F14~F23 两两相关 ->
   定 --dedup_corr / --leaf_proxy_thr。
2) 算每个因子与 BARRA 风格叶的最大|corr|(主导叶) -> 定叶子代理阈值。
注: step = max(1, 418 // dedup_days), dedup_days 默认 60 -> step=6。
"""
import sys
sys.path.insert(0, r'D:\loop_code\engine')
import numpy as np
import loop_engine as E

EXPR = {
    'F13': 'ts_delay1(add(barra_residual_volatility, barra_non_linear_size))',
    'F14': 'add(log(barra_non_linear_size), ts_std150(ts_delay1(ts_sum20(ln_volume))))',
    'F15': 'ts_mean20(ts_mean60(sub(corr100(turnover, barra_non_linear_size), sub(barra_residual_volatility, true_range))))',
    'F17': 'add(ts_mean100(corr100(corr100(fa_ocf_yoy, fa_gm), barra_residual_volatility)), max(ts_rank200(ts_max100(amplitude)), barra_residual_volatility))',
    'F18': 'add(ts_mean100(corr100(corr100(fa_ocf_yoy, fa_gm), add(barra_residual_volatility, fa_ocf_yoy))), max(ret, barra_residual_volatility))',
    'F19': 'max(ts_min20(cs_rank(div(mf_s_buy, ts_min20(ts_std200(corr200(ln_volume, mf_s_bqty)))))), barra_residual_volatility)',
    'F20': 'max(ts_mean120(cs_rank(div(barra_leverage, fa_gm))), barra_residual_volatility)',
    'F21': 'max(add(barra_residual_volatility, barra_leverage), max(ts_min20(cs_rank(div(fa_ocf_yoy, fa_gm))), barra_residual_volatility))',
    'F22': 'max(ts_min20(cs_rank(add(fa_ocf_yoy, barra_leverage))), barra_residual_volatility)',
    'F23': 'max(ts_min20(cs_rank(barra_leverage)), barra_residual_volatility)',
}


def _corr(v, w):
    m = np.isfinite(v) & np.isfinite(w)
    if m.sum() < 100:
        return np.nan
    c = np.corrcoef(v[m], w[m])[0, 1]
    return float(c) if np.isfinite(c) else np.nan


def main():
    base = E.base_fields()
    Bsub = base['B_sub']
    FWD = E.FWD
    step = max(1, 418 // 60)          # dedup_days 默认 60
    samp = slice(None, None, step)

    ded, dom = {}, {}
    leaf_rank = {lf: E.rank_rows(Bsub[lf][::FWD]) for lf in E.BARRA_LEAVES}
    for k, ex in EXPR.items():
        v = E.eval_expr(E.parse_expr(ex), Bsub)
        rv = E.rank_rows(v[::FWD])
        ded[k] = rv[samp]              # 引擎去重口径
        # 主导叶(相关用全 rebalance 日, 更稳)
        best, bl = 0.0, ''
        for lf, lr in leaf_rank.items():
            c = _corr(rv, lr)
            if np.isfinite(c) and abs(c) > best:
                best, bl = abs(c), lf
        dom[k] = (bl, best)

    print('===== 1. 引擎去重口径 两两|corr| (F19~F23 vs F13~F23) =====')
    ks = ['F13', 'F14', 'F15', 'F17', 'F18', 'F19', 'F20', 'F21', 'F22', 'F23']
    print('        ' + ''.join(f'{x:>7}' for x in ks))
    for a in ks:
        row = ''
        for b in ks:
            c = abs(_corr(ded[a], ded[b])) if a != b else 1.0
            row += f'{c:>7.3f}'
        print(f'{a:<8}{row}')
    print('\n超阈值的对 (阈值 0.90 / 0.88 / 0.85):')
    for i, a in enumerate(ks):
        for b in ks[i + 1:]:
            c = abs(_corr(ded[a], ded[b]))
            if np.isfinite(c) and c >= 0.85:
                tag = '>=0.90' if c >= 0.90 else ('>=0.88' if c >= 0.88 else '>=0.85')
                print(f'   {a}<->{b}: {c:.3f}  {tag}')

    print('\n===== 2. 主导 BARRA 叶(=叶子代理判据) =====')
    for k in ks:
        bl, best = dom[k]
        flag = '  <== 叶子代理' if best >= 0.95 else ('  (接近)' if best >= 0.85 else '')
        print(f'{k:<6} 主导叶={bl:<32} |corr|={best:.3f}{flag}')


if __name__ == '__main__':
    main()
