# -*- coding: utf-8 -*-
"""check_strip_style_pool.py — 池库因子的「**剥风格体检**」（2026-09-14）

## 为什么必须做（用户指出的问题）

用户对 `sub(ts_min20(barra_beta), ts_mean60(barra_non_linear_size))`（我先前标为"本批质量最高、
`all3` 真 alpha"）提出质疑：**"剥离市值后就不行了，发现就是市值类因子"**。
核实 —— **成立且更严重**：

    原:     Calmar 0.763 | 年化超额 +12.48%
    剥风格: Calmar 0.064 | 年化超额  +2.24%     ← ★ Calmar 掉到 1/12

## 根因：**入库判定根本没经过"剥风格"这道关**（配置漏洞）

`run_tracks.py` 传了 `--strip_style`（**开记录**）但**没传** `--min_strip_calmar`
⇒ 该参数默认 **`-1.0`** ⇒ 引擎里 `if args.min_strip_calmar > 0 ...` 不成立
⇒ **只记录不拦**（见 `loop_engine` 的「剥风格入库门槛(默认关)」段）。

★ 而且 roadmap §8.43 里**我自己写过**判读诀：
  「**全A 超额正但剥风格后转负 ⇒ 纯风格因子**（池门槛已挡住）」
  ⇒ **实测没挡住** —— 因为池门槛（`任一池 Calmar > 0.15`）用的也是**未剥风格**的口径。

## 连带影响：`all3` 的"真 alpha"是**过度声称**

`loop_pools.derive_tag` 的 `ok_all` = `ann_ex > 0 and calmar >= TAG_CAL_MIN(0.30)`
—— 全部是**未剥风格**口径 ⇒ **标签体系整体没考虑风格暴露**。

## 本脚本做什么

对**池库里每个入库条目**，从 `docs/loop_strip_style_{pool}.csv` 取出「原 vs 剥风格」，
按下面的档位分类并汇总：

    A 独立有效    strip_calmar >= 0.30            （与 TAG_CAL_MIN 对齐）
    B 弱独立      0 < strip_calmar < 0.30         （有独立信息但不强）
    C 纯风格      strip_ann_ex <= 0 或 strip_calmar <= 0  ⇒ **剥完就没了/变负，应拒**
    D 无记录      该 m 代没算剥风格（缺数据，不臆断）

## 用法
    python tools/check_strip_style_pool.py
"""
import argparse
import csv
import io
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DOCS = os.path.join(ROOT, 'docs')


def _f(v):
    try:
        x = float(v)
        return x if x == x else None      # NaN -> None
    except Exception:
        return None


def parse_library(pool):
    """读 `factor_library_{pool}.md` → [{no, gen, expr}]（文档 = 入库历史主口径）。"""
    f = os.path.join(DOCS, 'factor_library_{}.md'.format(pool))
    if not os.path.exists(f):
        return []
    t = io.open(f, encoding='utf-8').read()
    parts = re.split(r'\n### (F\d+) · ', t)
    out = []
    for k in range(1, len(parts) - 1, 2):
        no, body = parts[k], parts[k + 1]
        m_g = re.search(r'gen(\d+) 入库', body)
        m_e = re.search(r'```\n([^\n]+)', body)
        m_t = re.search(r'池标签：\*\*.([^\*\n]+)', body)
        if m_e:
            out.append(dict(no=no, gen=int(m_g.group(1)) if m_g else None,
                            expr=m_e.group(1).strip(),
                            tag=m_t.group(1).strip() if m_t else None))
    return out


def load_strip(pool):
    """`docs/loop_strip_style_{pool}.csv` → {(gen, expr): row}"""
    p = os.path.join(DOCS, 'loop_strip_style_{}.csv'.format(pool))
    if not os.path.exists(p):
        return {}
    out = {}
    for r in csv.DictReader(open(p, encoding='utf-8-sig', newline='')):
        try:
            out[(int(r['gen']), r['expr'])] = r
        except Exception:
            continue
    return out


def classify(r):
    sc, sa = _f(r.get('strip_calmar')), _f(r.get('strip_ann_ex'))
    if sc is None:
        return 'D', '无记录'
    if sa is not None and sa <= 0:
        return 'C', '**纯风格**（剥完超额转负）'
    if sc <= 0:
        return 'C', '**纯风格**（剥完 Calmar<=0）'
    if sc >= 0.30:
        return 'A', '独立有效'
    return 'B', '弱独立'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pools', default='300,500,1000')
    a = ap.parse_args()
    pools = [x.strip() for x in a.pools.split(',') if x.strip()]

    rows = []
    for pool in pools:
        st = load_strip(pool)
        for en in parse_library(pool):
            key = (en['gen'], en['expr'])
            r = st.get(key)
            if r is None:      # 该代表达式没记录 -> 退回该池任意代
                cands = [v for (g, e), v in st.items() if e == en['expr']]
                r = cands[0] if cands else None
            rows.append(dict(pool=pool, no=en['no'], gen=en['gen'],
                             expr=en['expr'], tag=en['tag'], rec=r))

    print('=' * 104)
    print('池库因子「剥风格体检」  条目 {} 个'.format(len(rows)))
    print('=' * 104)
    print('{:<5s} {:<4s} {:<4s} {:>9s} {:>9s} {:>9s} {:>9s}  {:<24s} {}'.format(
        '池', '编号', '代', '原Calmar', '剥Calmar', '原超额', '剥超额', '判定', '表达式'))
    print('-' * 104)
    cnt = {}
    bad = []
    for x in sorted(rows, key=lambda y: (y['pool'], y['no'] or '')):
        r = x['rec']
        if r is None:
            print('{:<5s} {:<4s} {:<4} {:>9s} {:>9s} {:>9s} {:>9s}  {:<24s} {}'.format(
                x['pool'], x['no'], str(x['gen']), '-', '-', '-', '-', 'D 无记录', x['expr'][:44]))
            cnt['D'] = cnt.get('D', 0) + 1
            continue
        k, txt = classify(r)
        cnt[k] = cnt.get(k, 0) + 1
        if k == 'C':
            bad.append(x)
        print('{:<5s} {:<4s} {:<4} {:>9s} {:>9s} {:>9s} {:>9s}  {:<24s} {}'.format(
            x['pool'], x['no'], str(x['gen']),
            ('%.3f' % _f(r['calmar'])) if _f(r['calmar']) is not None else '-',
            ('%.3f' % _f(r['strip_calmar'])) if _f(r['strip_calmar']) is not None else '-',
            ('%+.1f%%' % (100 * _f(r['ann_ex']))) if _f(r['ann_ex']) is not None else '-',
            ('%+.1f%%' % (100 * _f(r['strip_ann_ex']))) if _f(r['strip_ann_ex']) is not None else '-',
            '{} {}'.format(k, txt), x['expr'][:44]))
    print('-' * 104)
    print('汇总: ' + ' | '.join('{} {}={}'.format(k, v, cnt.get(k, 0))
                                for k, v in (('A', '独立有效'), ('B', '弱独立'),
                                             ('C', '纯风格'), ('D', '无记录'))))
    print()
    if bad:
        print('★★ **判定为「纯风格」的 {} 个（剥完风格就没有独立超额）**：'.format(len(bad)))
        for x in bad:
            r = x['rec']
            print('   [{} {}] {:<60s} 原 {:.3f} -> 剥 {:.3f}'.format(
                x['pool'], x['no'], x['expr'][:60],
                _f(r['calmar']) or 0, _f(r['strip_calmar']) or 0))
        print()
        print('⇒ **根因不是候选不行，是入库判定漏了一道关**：'
              '`run_tracks.py` 传了 `--strip_style` 但**没传** `--min_strip_calmar`'
              '（默认 -1 = 只记录不拦）⇒ 剥风格结果**从未参与入库判定**。')
        print('⇒ **修法**：给池轨道加 `--min_strip_calmar=0.15`（与 `--min_pool_calmar` 同档），'
              '并把 `derive_tag` 的 `ok_all` 一并改为**剥风格口径**（否则 `all3`="真 alpha" 仍是过度声称）。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
