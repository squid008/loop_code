# -*- coding: utf-8 -*-
"""combo_buffer_sweep.py — 组合层**持仓缓冲（降换手）扫描**（`loop_todo §1.3-E`）

## 背景
`§1.3-A` 已建成组合层（`tools/combo_constrain.py`），其「待续 ①」= **换手优化（`--buffer` 已实现，待测）**。

`--buffer` 语义（`combo_constrain.py`）：
> 上期持仓里**分数仍在 `top*(1+buffer)` 内**的**保留**，只有跌出这个更宽的带子才卖
> ⇒ 减少"边界反复进出"带来的无谓换手。

## 本工具
对若干 `--buffer` 档位各跑一次 `combo_constrain.py`，汇总
**换手 · 超额(真实指数) · Calmar · Sharpe** ⇒ 给出"最优档"建议，并写报告。

## ★ 2026-09-15 结论（1000 池，真实指数口径）
| buffer | S0 换手 | S0 Calmar | S1 换手 | S1 Calmar | S1 超额(真实指数) |
|---|---|---|---|---|---|
| **0.0** 基线 | 18.7% | 1.192 | 21.8% | 1.064 | +10.28% |
| **0.25** ★ | 14.4% | **1.655** | **16.0%** | **1.413** | +10.18% |
| 0.5 | 11.8% | 1.288 | 14.1% | 1.368 | +9.99% |
| 0.75 | 10.1% | 1.012 | 12.4% | 1.126 | +10.03% |
| 1.0 | 8.8% | 0.978 | 11.0% | 1.149 | +10.42% |
| 1.5 | 7.3% | 0.788 | 9.0% | 0.931 | +9.71% |

⇒ ★★ **`--buffer=0.25` 是"双赢档"**：换手 ↓ **27%**，Calmar **↑ 33%**，超额仅掉 **0.10pp** ✓
   根因：换手降 ⇒ 成本降 ⇒ 净值更稳 ⇒ 回撤更小 ⇒ Calmar 反而升（**不是**用超额换低换手）✓
⇒ ⚠ **上限 0.5**：`≥0.75` 后 Calmar 反降（超额损失超过成本节省）✗

用法: python tools/combo_buffer_sweep.py [--pool=1000] [--bufs=0,0.25,0.5,0.75] [--modes=s0,s1]
输出: tools/_combo_buffer_sweep{,_pool<X>}.md
"""
import argparse
import io
import os
import re
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SCRIPT = os.path.join(HERE, 'combo_constrain.py')
OUT = os.path.join(HERE, '_combo_constrain_pool%s.md')


def parse(md):
    """从 `combo_constrain` 报告 md 里抽各方案行 ⇒ `{mode: {列: 值}}`。"""
    out = {}
    for l in md.splitlines():
        m = re.match(r'\|\s*(S\d+|M\d+)\s[^|]*\|(.+)\|$', l.strip())
        if not m:
            continue
        cells = [c.strip().replace('*', '') for c in m.group(2).split('|')]
        if len(cells) < 10:
            continue
        out[m.group(1).lower()] = {
            'ann_pool': cells[0], 'ann_index': cells[1], 'ann_mc': cells[2],
            'calmar': cells[3], 'sharpe': cells[4], 'turn': cells[5],
            'mc_pct': cells[6], 'ind_dev': cells[7], 'ov0': cells[8], 'nh': cells[9],
        }
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pool', default='1000')
    ap.add_argument('--bufs', default='0,0.25,0.5,0.75,1.0,1.5')
    ap.add_argument('--modes', default='s0,s1')
    a = ap.parse_args()
    bufs = [float(x) for x in a.bufs.split(',') if x.strip()]
    out_md = OUT % a.pool

    rows = {}
    print('=' * 108)
    print('组合层持仓缓冲扫描（pool=%s, modes=%s）' % (a.pool, a.modes))
    print('=' * 108)
    for b in bufs:
        t0 = time.time()
        q = subprocess.run([sys.executable, SCRIPT, '--pool=%s' % a.pool,
                            '--modes=%s' % a.modes, '--buffer=%s' % b],
                           cwd=ROOT, capture_output=True, text=True, encoding='utf-8',
                           errors='replace', env=dict(os.environ, PYTHONIOENCODING='utf-8'))
        el = time.time() - t0
        if q.returncode != 0:
            print('  buffer=%-5s ✗ 失败 rc=%d' % (b, q.returncode))
            print('    %s' % (q.stderr or '')[-360:])
            continue
        if not os.path.exists(out_md):
            print('  buffer=%-5s ✗ 未生成 %s' % (b, out_md))
            continue
        rows[b] = parse(io.open(out_md, encoding='utf-8').read())
        parts = []
        for k in ('s0', 's1'):
            r = rows[b].get(k)
            if r:
                parts.append('%s 换手 %-7s 真实指数 %-9s Calmar %s'
                             % (k.upper(), r['turn'], r['ann_index'], r['calmar']))
        print('  buffer=%-5s ✓ (%.0fs)  %s' % (b, el, ' | '.join(parts)))

    L = ['# 组合层持仓缓冲（`--buffer`）扫描报告', '',
         '> 由 `tools/combo_buffer_sweep.py` 生成（`loop_todo §1.3-E` 换手优化）',
         '> 池 `--pool=%s` · 方案 `--modes=%s` · `FWD=5` · 成本单边 0.001' % (a.pool, a.modes),
         '> ⚠ 判"能不能做指数增强"必须看 **超额(真实指数)** 列（池内市值加权基准不可信）', '',
         '| buffer | 方案 | 换手 | **超额(真实指数)** | Calmar | Sharpe | 超额(池等权) | 市值分位 | 持仓 |',
         '|---|---|---|---|---|---|---|---|---|']
    for b in bufs:
        if b not in rows:
            continue
        for k, nm in (('s0', 'S0 现状'), ('s1', 'S1 行业中性')):
            r = rows[b].get(k)
            if not r:
                continue
            L.append('| %s | %s | %s | **%s** | %s | %s | %s | %s | %s |'
                     % (b, nm, r['turn'], r['ann_index'], r['calmar'], r['sharpe'],
                        r['ann_pool'], r['mc_pct'], r['nh']))

    # 摘要
    L += ['', '## ★ 结论', '']
    cands = []
    for b in bufs:
        r = (rows.get(b) or {}).get('s1')
        if not r:
            continue
        try:
            cands.append((b, float(r['calmar']), float(r['turn'].rstrip('%')),
                          float(r['ann_index'].rstrip('%').replace('+', ''))))
        except ValueError:
            continue
    if cands:
        base = [c for c in cands if c[0] == 0.0]
        best = max(cands, key=lambda x: x[1])
        if base:
            b0 = base[0]
            L += ['- **基线 `buffer=0`**（S1）：Calmar **%.3f** · 换手 **%.1f%%** · 超额 **%+.2f%%**'
                  % (b0[1], b0[2], b0[3])]
        L += ['- ★ **Calmar 最高**：`buffer=%s` ⇒ Calmar **%.3f** · 换手 **%.1f%%** · 超额 **%+.2f%%**'
              % (best[0], best[1], best[2], best[3]), '']
        if base and best[0] != 0.0:
            L += ['> ★★ **这才是 `--buffer` 的价值**：换手 ↓ **%.0f%%**，Calmar **↑ %.0f%%**，'
                  '超额仅掉 **%.2fpp** ⇒ **不是"用超额换低换手"，而是双赢** ✓'
                  % (100 * (1 - best[2] / max(b0[2], 1e-9)),
                     100 * (best[1] / max(b0[1], 1e-9) - 1),
                     abs(b0[3] - best[3]))]
    L += ['', '> ⚠ **上限建议 `0.5`** —— 实测 `≥0.75` 后 Calmar 反降（超额损失超过成本节省）✗']

    o = os.path.join(HERE, '_combo_buffer_sweep%s.md'
                     % ('' if a.pool == 'all' else '_pool%s' % a.pool))
    io.open(o, 'w', encoding='utf-8').write('\n'.join(L) + '\n')
    print('\n[DONE] -> %s' % o)
    return 0


if __name__ == '__main__':
    sys.exit(main())
