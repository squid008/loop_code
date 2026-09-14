# -*- coding: utf-8 -*-
"""_test_parent_sel.py — 亲本选择策略 `top_percent_plus_random` 的回归测试（`loop_todo §1.3-C`）

## 背景

引擎原来抽亲本用 `rng.choice(seeds)`（**全池均匀随机**）⇒ ★★ **L1 里第 1 名和第 30 名
被选中的概率完全一样，排名信息一点没用上**。我们只有「**堵**」的手段（`--fam_quota`
配额 / `fam_block_thr` 黑名单 / `--decorr`），**没有「疏」**（显式的探索/利用配比）。

本次补 `--parent_sel`（对齐 QuantaAlpha `configs/experiment.yaml:83-92` +
`pipeline/evolution/crossover.py:423-437`）：
`uniform`（默认 = 现状，行为不变）/ `best` / **`top_percent_plus_random`**（top 30% 保底 + 余量随机）。

## ★★★ 本测试守护的**头号坑**（最容易写错、且错了会静默失效）

`top_percent_plus_random` 的「否则」分支**必须从全池随机**，
**不能**写成「只从 rest 随机」—— 后者会让 top 段和 rest 的权重**正好抵消**，**退化成 uniform**：

    ✗  `rng.choice(seeds[:n_top] if rng.random() < thr else seeds[n_top:])`
       n=30, n_top=9 时：P(某个 top)=0.3/9=0.0333, P(某个 rest)=0.7/21=0.0333 **完全相同** ✗
    ✓  `rng.choice(seeds[:n_top]) if rng.random() < thr else rng.choice(seeds)`
       P(某个 top)=0.3/9 + 0.7/30 = 0.0567, P(某个 rest)=0.7/30 = 0.0233 ⇒ **2.43×** ✓

⇒ 所以 `[3]` 用**统计检验**把两者分开：**top 段权重 ÷ rest 段权重 必须 ≈ 2.43，不能 ≈ 1.0** ✓
（QuantaAlpha 的 `rest_candidates` 只是"**补剩余名额**"的来源，不是唯一来源 ✓）

用法: python tools/_test_parent_sel.py
"""
import os
import random
import re
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ENG = os.path.join(ROOT, 'engine')
sys.path.insert(0, ENG)

OK = [0, 0]


def chk(cond, msg):
    OK[0] += 1
    if not cond:
        OK[1] += 1
    print('  [{}] {}'.format('OK ' if cond else 'FAIL', msg))


def _freq(pick, seeds, n, **kw):
    """跑 n 次抽样，返回每个位置被选中的次数列表。"""
    rng = random.Random(20260914)
    cnt = [0] * len(seeds)
    idx = {id(s): i for i, s in enumerate(seeds)}
    for _ in range(n):
        s = pick(rng, seeds, **kw)
        cnt[idx[id(s)]] += 1
    return cnt


def t_default(LE):
    print('\n[1] 默认 = 现状（`uniform`）⇒ **行为不变**')
    seeds = list(range(30))
    chk(LE.PARENT_SEL_MODES[0] == 'uniform', '`PARENT_SEL_MODES[0]` 是 uniform')
    chk('uniform' in LE.PARENT_SEL_MODES, '模式表含 uniform/best/top_percent_plus_random: {}'
        .format('/'.join(LE.PARENT_SEL_MODES)))
    # uniform 与旧的 rng.choice(seeds) 必须**逐次同分布**
    c_get = _freq(LE.pick_parent, seeds, 40000)
    rng = random.Random(20260914)
    c_old = [0] * len(seeds)
    for _ in range(40000):
        c_old[seeds.index(rng.choice(seeds))] += 1
    chk(c_get == c_old, '`uniform` 与旧写法 `rng.choice(seeds)` **逐位计数完全相同**'
                        '（⇒ 换代码后行为真的一点没变）')
    lo, hi = min(c_get), max(c_get)
    chk(hi / lo < 1.15, '均匀性 OK（最大/最小 = {:.3f}）'.format(hi / lo))


def t_best(LE):
    print('\n[2] `best` ⇒ 恒取第 1 名（seed 池按 score **降序**）')
    seeds = ['第1名', '第2名', '第3名', '第4名', '第5名']
    rng = random.Random(1)
    picks = {LE.pick_parent(rng, seeds, 'best') for _ in range(200)}
    chk(picks == {'第1名'}, '`best` 200 次全是第 1 名（实得 {} 种）'.format(len(picks)))
    chk(LE.pick_parent(random.Random(0), [], 'best') is None, '空池 ⇒ None（不崩）')


def t_top_pct(LE):
    print('\n[3] ★★ `top_percent_plus_random`：top 段必须**真的**被加权（守护"只从 rest 随机"的坑）')
    seeds = list(range(30))
    thr, n, N = 0.30, 30, 120000
    cnt = _freq(LE.pick_parent, seeds, N, mode='top_percent_plus_random', thr=thr)
    n_top = max(1, int(n * thr))
    p_top = sum(cnt[:n_top]) / N / n_top
    p_rest = sum(cnt[n_top:]) / N / (n - n_top)
    ratio = p_top / p_rest
    exp = (thr / n_top + (1 - thr) / n) / ((1 - thr) / n)
    print('      n_top={} · P(top个体)={:.5f} · P(rest个体)={:.5f} · 比值={:.3f}（理论 {:.3f}）'
          .format(n_top, p_top, p_rest, ratio, exp))
    chk(abs(ratio - exp) < 0.20, '★ 比值 ≈ 理论 {:.2f}（实得 {:.2f}）'.format(exp, ratio))
    chk(ratio > 1.8, '★★ **不是 1.0** —— 即"只从 rest 随机"那个错误写法已被排除（1.0 会 FAIL）')
    chk(ratio < 3.2, '也没偏得离谱（>3.2 说明实现跑偏了）')
    # thr → 1.0 应退化成 uniform
    c1 = _freq(LE.pick_parent, list(range(30)), 40000,
               mode='top_percent_plus_random', thr=1.0)
    chk(max(c1) / max(1, min(c1)) < 1.15, '`thr=1.0` ⇒ 退化成 uniform（每点都进 top 段）✓')


def t_edge(LE):
    print('\n[4] 边界')
    chk(LE.pick_parent(random.Random(0), [], 'top_percent_plus_random') is None, '空池 ⇒ None')
    one = ['唯一']
    chk(LE.pick_parent(random.Random(0), one, 'top_percent_plus_random') == '唯一', '单元素池 ✓')
    two = ['a', 'b']
    r = random.Random(7)
    chk({LE.pick_parent(r, two, 'top_percent_plus_random', 0.3) for _ in range(40)} == {'a', 'b'},
        '`len(seeds) <= n_top` 时退回全池（两个都能被抽到，不崩）')
    chk(LE.pick_parent(random.Random(0), one, '未知模式') == '唯一', '未知模式 ⇒ 兜底 uniform')
    chk(isinstance(LE.pick_parent(random.Random(0), ['x'], None), str), 'mode=None ⇒ 兜底不崩')


def t_wired():
    print('\n[5] 静态断言：接线正确 + 默认行为不变')
    src = open(os.path.join(ENG, 'loop_engine.py'), encoding='utf-8').read()
    chk("default='uniform'" in src, 'argparse `--parent_sel` 默认 = uniform（**行为不变**）')
    chk("'--parent_top_pct', type=float, default=0.30" in src, '`--parent_top_pct` 默认 0.30 ✓')
    n_pick = len(re.findall(r'pick_parent\(rng, seeds, _psel, _ptop\)', src))
    chk(n_pick == 2, '两处亲本抽取（变异 + 交叉第二亲本）都改走 `pick_parent`，实得 {}'.format(n_pick))
    # ★ 精确断言：剥掉注释 + 屏蔽 `pick_parent` 函数体后，不应再有 `rng.choice(seeds` 直抽。
    #   （初版用 `str.replace` 拼凑，漏掉函数内的第 3 种形态 ⇒ 假 FAIL；写测试也要避免"脆断言"）
    body_m = re.search(r'\ndef pick_parent\(.*?\n(?=\n\ndef |\n\n# )', src, re.S)
    masked = src
    if body_m:
        masked = src[:body_m.start()] + '\n' + src[body_m.end():]
    masked = re.sub(r'#[^\n]*', '', masked)          # 去掉行注释（含提到旧写法的说明）
    n_left = len(re.findall(r'rng\.choice\(seeds', masked))
    chk(n_left == 0, '★ `pick_parent` 之外**没有**遗留的 `rng.choice(seeds` 直抽（实得 {} 处）'
                     .format(n_left))
    chk('PARENT_SEL_MODES' in src and 'def pick_parent' in src, '纯函数 + 模式表已定义')


def main():
    print('=' * 96)
    print('亲本选择策略 回归测试（loop_todo §1.3-C）')
    print('=' * 96)
    import loop_engine as LE
    t_default(LE)
    t_best(LE)
    t_top_pct(LE)
    t_edge(LE)
    t_wired()
    print('\n' + '=' * 96)
    print('通过 {}/{}'.format(OK[0] - OK[1], OK[0]) + ('' if OK[1] else '  ✓ 全部通过'))
    return 1 if OK[1] else 0


if __name__ == '__main__':
    sys.exit(main())
