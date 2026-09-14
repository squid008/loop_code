# -*- coding: utf-8 -*-
"""pool_grade_summary.py — 各池入库因子的**剥风格档位**汇总 + **防回归告警**

## 为什么需要它（`docs/loop_todo.md` §1.17 的验证清单第 ④ 条）

「`--pool_gate_or_all` 静默绕过硬门槛」这个 bug 之所以能潜伏一天多，是因为
**没有人在看"入库因子的档位分布"** —— 它需要人工偶然跑 `build_facs.py` 才发现。

⇒ 把这件事做成**随时可跑的一行命令**：只要入库因子里出现 C 档（纯风格），立刻吼出来。

档位（`loop_pools.strip_grade`，单一事实源）：
  **A** 剥风格后仍强 · **B** 剥风格后仍正但弱 · **C** 剥风格后**转负 = 纯风格（指数增强不可用）**

## 用法

    python tools/pool_grade_summary.py                  # 全部池
    python tools/pool_grade_summary.py --pool=1000      # 只看 1000
    python tools/pool_grade_summary.py --since-gen=7    # ★ 只看第 7 代及以后入库的（验证修复）
    python tools/pool_grade_summary.py --warn-c=0.30    # C 档占比超过 30% 就报 [!]

退出码：C 档占比超阈 ⇒ 返回 1（便于将来接进收尾做硬断言）。
"""
import argparse
import csv
import glob
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
AIT = os.path.join(ROOT, 'ai_test')

GRADE_DESC = {'A': '剥风格后仍强', 'B': '剥风格后仍正但弱', 'C': '**纯风格**（增强不可用）'}


def read_text(p):
    if not os.path.exists(p):
        return ''
    raw = open(p, 'rb').read()
    for e in ('utf-8-sig', 'utf-8', 'gbk', 'cp936'):
        try:
            s = raw.decode(e)
            if s.count('\ufffd') == 0:
                return s
        except Exception:
            pass
    return raw.decode('utf-8', errors='replace')


def lib_gen_map(pool):
    """从 `docs/factor_library_{pool}.md` 的总览表里取 `{F编号: 入库代数}`。"""
    sfx = '' if pool == 'all' else '_' + pool
    t = read_text(os.path.join(DOCS, 'factor_library{}.md'.format(sfx)))
    out = {}
    for m in re.finditer(r'^\|\s*(F\d+)\s*\|\s*gen(\d+)\s*\|', t, re.M):
        out[m.group(1)] = int(m.group(2))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pool', default='')
    ap.add_argument('--since-gen', type=int, default=0,
                    help='只看该代及以后入库的（0=全部）')
    ap.add_argument('--warn-c', type=float, default=0.30,
                    help='C 档占比超过该值即告警（默认 0.30）')
    a = ap.parse_args()

    rows = list(csv.DictReader(io.open(os.path.join(DOCS, 'loop_strip_style_bank.csv'),
                                       encoding='utf-8-sig', newline='')))
    if not rows:
        raise SystemExit('缺 docs/loop_strip_style_bank.csv（先跑 tools/build_facs.py）')

    pools = [a.pool] if a.pool else ['all', '300', '500', '1000']
    print('=' * 96)
    print('各池入库因子的剥风格档位汇总{}'.format(
        '（只看 gen>={} 入库的）'.format(a.since_gen) if a.since_gen else ''))
    print('=' * 96)

    warn_total = 0
    for pk in pools:
        want = [r for r in rows
                if (r['pool'] == pk)
                and (not a.since_gen
                     or lib_gen_map(pk).get(r['name'].split('_')[0], -1) >= a.since_gen)]
        if not want:
            print('\n## pool={}  （无符合条件的数据）'.format(pk))
            continue
        cnt = {}
        for r in want:
            cnt[r['grade']] = cnt.get(r['grade'], 0) + 1
        n = len(want)
        c_ratio = cnt.get('C', 0) / float(n)
        bad = c_ratio > a.warn_c
        print('\n## pool={}   （{} 个）'.format(pk, n))
        for r in want:
            gd = r['grade']
            mark = ' ★' if gd == 'C' else '  '
            print('  [{}]{} {:<12s} 原Calmar={:<8s} 剥后Calmar={:<10s} {}'.format(
                gd, mark, r['name'], r['calmar'][:7], r['strip_calmar'][:9], r['expr'][:44]))
        print('  档位: ' + ', '.join('{}×{}'.format(k, cnt[k]) for k in sorted(cnt))
              + '   ⇒ C 档占比 **{:.0%}**'.format(c_ratio))
        if bad:
            warn_total += 1
            print('  [!] C 档占比 {:.0%} > {:.0%} ⇒ **检查 --min_strip_calmar 是否真的生效**'
                  '（曾因 --pool_gate_or_all 的 OR 重建把门槛撤掉，见 loop_todo §1.17）'.format(
                      c_ratio, a.warn_c))
        else:
            print('  [OK] C 档占比未超阈（{:.0%} ≤ {:.0%}）'.format(c_ratio, a.warn_c))

    print('\n' + '=' * 96)
    if warn_total:
        print('结论: **{} 个池的 C 档占比超阈** ⇒ 有纯风格因子混进库，先查剥风格门槛'.format(warn_total))
        return 1
    print('结论: 全部池的 C 档占比都在阈值内 ✓')
    return 0


if __name__ == '__main__':
    sys.exit(main())
