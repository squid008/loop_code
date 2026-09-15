# -*- coding: utf-8 -*-
"""combo_check.py -- 合成因子的「交付前检查」（roadmap §8.37）

合成结果（§8.36）看起来很好（方案 C：年化超额 +11.75% / Calmar 1.104 / 夏普 1.523 / 3 段全正），
但**在下结论前必须回答两件事**：

  ① **是不是靠小盘倾斜赚的？** 全A 宽池的"等权基准"含小盘溢价（§8.13/§8.31 反复出现）。
     ⇒ 必须同时看 **市值加权基准** 口径（`tilt = 市值口径 − 等权口径`）。
     若 `tilt` 很大 ⇒ "超额"里一大块不是选股。
  ② **能不能做指数增强（300/500）？** 产品口径是**池内 + 对真实指数**。
     ⇒ 必须在 **300/500 成分内**重跑，看池内超额与市值口径。

做法（复用 `evaluate_real` 的 `mcap=` 与 `loop_pools.pool_mask`）：
  · 全A   : 等权基准 / 市值加权基准 / tilt
  · 300 内: 同上
  · 500 内: 同上
外加分段稳定性（3 段）与年度明细。

用法: python tools/combo_check.py [--fac=tools/_combo_fac.pkl] [--pool_all=all]
"""
import io
import os
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
import loop_pools as LP            # noqa: E402

OUT = os.path.join(HERE, '_combo_check_report.md')


def seg_of(ex, k=3):
    if ex is None or len(ex) < 30:
        return [], 0
    parts = np.array_split(np.asarray(ex, dtype='float64'), k)
    s = [float((1 + pd.Series(x)).prod() - 1) for x in parts if len(x)]
    return s, sum(1 for x in s if x > 0)


def main():
    fac_path = os.path.join(HERE, '_combo_fac.pkl')
    for a in sys.argv[1:]:
        if a.startswith('--fac='):
            fac_path = a.split('=', 1)[1]
    if not os.path.exists(fac_path):
        print('缺合成因子文件:', fac_path)
        return 1
    t0 = time.time()
    base = LE.base_fields()
    B, dates, cols, close = base['B'], base['dates'], base['cols'], base['close']
    print('面板 {} 日 x {} 股'.format(len(dates), len(cols)), flush=True)
    MCAP = np.where(B['mktcap'] > 0, B['mktcap'].astype('float64'), np.nan)

    fd = pd.read_pickle(fac_path)
    fd = fd.reindex(index=dates, columns=cols).astype('float64')
    print('合成因子载入: 覆盖 {:.1f}%'.format(
        100 * float(np.isfinite(fd.values).mean())), flush=True)

    rows = []
    print('\n[全A 宽池] ...', flush=True)
    r = FM.evaluate_real(FM.cs_rank(fd), close, 'combo_all', with_ex=True, mcap=MCAP)
    if r is not None:
        s, sp = seg_of(r.get('ex'))
        rows.append(dict(tag='全A 宽池', **{k: r.get(k, np.nan) for k in
                                            ('ann_ex', 'ann_ex_cw', 'tilt', 'calmar',
                                             'calmar_cw', 'sharpe', 'dd', 'turn')},
                         seg=s, seg_pos=sp))
        print('  等权基准 超额 {:+.2f}% Calmar {:+.3f} | 市值基准 超额 {:+.2f}% Calmar {:+.3f}'
              ' | tilt {:+.2f}%'.format(r['ann_ex'] * 100, r['calmar'],
                                        r.get('ann_ex_cw', np.nan) * 100,
                                        r.get('calmar_cw', np.nan),
                                        r.get('tilt', np.nan) * 100), flush=True)

    for tag in ('300', '500'):
        print('\n[{} 成分内] ...'.format(tag), flush=True)
        try:
            M = LP.pool_mask(tag, dates, cols)
        except Exception as e:
            print('  池掩码失败:', type(e).__name__, e)
            continue
        fv = np.where(M, fd.values, np.nan)
        fp = FM.cs_rank(pd.DataFrame(fv, index=dates, columns=cols))
        r = FM.evaluate_real(fp, close, 'combo_' + tag, with_ex=True, mcap=MCAP)
        if r is None:
            print('  样本不足')
            continue
        s, sp = seg_of(r.get('ex'))
        rows.append(dict(tag='{} 成分内'.format(tag), **{k: r.get(k, np.nan) for k in
                                                         ('ann_ex', 'ann_ex_cw', 'tilt',
                                                          'calmar', 'calmar_cw', 'sharpe',
                                                          'dd', 'turn')},
                         seg=s, seg_pos=sp))
        print('  等权基准 超额 {:+.2f}% Calmar {:+.3f} | 市值基准 超额 {:+.2f}% Calmar {:+.3f}'
              ' | tilt {:+.2f}%'.format(r['ann_ex'] * 100, r['calmar'],
                                        r.get('ann_ex_cw', np.nan) * 100,
                                        r.get('calmar_cw', np.nan),
                                        r.get('tilt', np.nan) * 100), flush=True)

    L = ['# 合成因子「交付前检查」报告（roadmap §8.37）', '',
         '因子文件: `{}`'.format(os.path.relpath(fac_path, ROOT)), '',
         '## 1. 两个口径 × 三个池', '',
         '| 口径 | 年化超额(等权基准) | **Calmar(等权)** | 年化超额(市值基准) | '
         'Calmar(市值) | **tilt** | 夏普 | 回撤 | 换手 | 分段正 |',
         '|---|---|---|---|---|---|---|---|---|---|']
    for r in rows:
        L.append('| {} | {:+.2f}% | {:+.3f} | {:+.2f}% | {:+.3f} | **{:+.2f}%** | '
                 '{:+.3f} | {:.1f}% | {:.1%} | {}/3 |'.format(
                     r['tag'], r['ann_ex'] * 100, r['calmar'],
                     r['ann_ex_cw'] * 100, r['calmar_cw'], r['tilt'] * 100,
                     r['sharpe'], r['dd'] * 100, r['turn'], r['seg_pos']))
    L += ['', '## 2. 分段明细（各段累计费后超额, 用等权基准）', '']
    for r in rows:
        L.append('- **{}**: {}'.format(
            r['tag'], ' / '.join('{:+.2f}%'.format(x * 100) for x in r['seg'])))
    L += ['', '## 3. 判读', '']
    if rows:
        a = rows[0]
        L.append('- 全A: 等权基准 Calmar **{:+.3f}** vs 市值基准 **{:+.3f}**，'
                 '`tilt` **{:+.2f}%**'.format(a['calmar'], a['calmar_cw'], a['tilt'] * 100))
        if a['tilt'] * 100 > 2:
            L.append('  - ⚠ **tilt 很大** ⇒ 全A 的"超额"里有相当一部分来自**小盘倾斜**，'
                     '**不能直接当作可交付产品的超额**。')
        else:
            L.append('  - ✅ tilt 不大 ⇒ 全A 口径的超额**主要来自选股**，不是小盘倾斜。')
        for r in rows[1:]:
            L.append('- {}: 等权 Calmar **{:+.3f}**、市值 Calmar **{:+.3f}**、'
                     '分段 **{}/3**'.format(r['tag'], r['calmar'], r['calmar_cw'],
                                            r['seg_pos']))
            if r['calmar'] > 0.3 and r['seg_pos'] == 3:
                L.append('  - ✅ 在该池内**有效且稳定** ⇒ 可作为对应指数增强的候选。')
            elif r['calmar'] > 0:
                L.append('  - 🟡 池内为正但偏弱/不稳 ⇒ 需再看 tilt 与分段。')
            else:
                L.append('  - ❌ 池内无效 ⇒ **不能**做该池的指数增强'
                         '（很可能全靠池外的风格暴露）。')
        # 衰减提示
        if a['seg'] and len(a['seg']) == 3:
            L.append('- ⚠ **注意衰减**：全A 三段 {:.1f}% / {:.1f}% / {:.1f}%'.format(
                a['seg'][0] * 100, a['seg'][1] * 100, a['seg'][2] * 100))
            if a['seg'][2] < a['seg'][0] * 0.6:
                L.append('  ⇒ 第三段明显低于第一段 ⇒ **存在衰减趋势**，实盘预期应下调。')
    txt = '\n'.join(L) + '\n'
    io.open(OUT, 'w', encoding='utf-8').write(txt)
    print()
    print(txt)
    print('用时 {:.0f}s  -> {}'.format(time.time() - t0, OUT))
    return 0


if __name__ == '__main__':
    sys.exit(main())
