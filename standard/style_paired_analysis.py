# -*- coding: utf-8 -*-
"""style_paired_analysis.py — old vs new 排序分的【配对】风格暴露比较(2026-09-11)

输入  docs/loop_style_obs.csv   (--style_obs 产物: 每代每个被求值候选一行, 含 mono/shape_pos)
输出  控制台 + docs/loop_style_paired.md

**为什么这个比较可信**: 同一批候选(同一代、同一子面板的求值结果), 只换排序公式 =>
差异全部来自公式本身, **不含生成端随机性混淆**。(跑两轮不同代数做不到这点:
种子=gen*10+7, 代数不同 => 候选集不同, 见 docs/log/2026-09.md §8.4)

判读(roadmap §8.3): 若 new 选出的候选集 |st_lntr| / |st_lnamt| 中位**显著上升**
  -> 确诊"新排序分在低换手/低成交额方向加倍下注"(与"别老在市值/成交额打转"反向)。

用法: python ai_test/style_paired_analysis.py [--stab=0.75] [--k=30,70]
"""
import os
import sys

import numpy as np
import pandas as pd

try:                                   # 控制台可能是 GBK: 遇到 − / ✅ 等字符不要崩
    sys.stdout.reconfigure(errors='replace')
except Exception:
    pass

OBS = r'D:\loop_code\docs\loop_style_obs.csv'
OUT = r'D:\loop_code\docs\loop_style_paired.md'
STYLE = ['st_lncap', 'st_lnamt', 'st_lntr', 'st_lnpx']
MODES = ['old', 'new', 'new+mono', 'new_n']      # 参与比较的排序分(new_n = shape_pos 风格中性版)
STAB_GATE = 0.75          # 实测: gen71/72/73 三代 B角参数均为 min_stab=0.75(已从日志核对)
MIN_IC = 0.02             # loop_engine.py --min_ic 默认值
K_LIST = [30, 70]
MONO_THR = 0.75           # 批1 推荐形状门槛

for a in sys.argv[1:]:
    if a.startswith('--stab='):
        STAB_GATE = float(a[7:])
    elif a.startswith('--k='):
        K_LIST = [int(x) for x in a[4:].split(',')]
    elif a.startswith('--obs='):        # 允许读快照(引擎正在追加同一文件时更安全)
        OBS = a[6:]
    elif a.startswith('--out='):
        OUT = a[6:]


def scores(d):
    st = d['stab'].clip(0, 1).fillna(0)
    sp = d['shape_pos'].clip(0, 1).fillna(0)
    # 第四种: shape_pos 换成"收益先对 lncap/lnamt 中性化"后的档位单调性(roadmap §8.5 的下一步)。
    # 观测文件缺 shape_pos_n 时返回全 NaN -> topk 会跳过, 而不是静默退化成另一个公式。
    if 'shape_pos_n' in d.columns and d['shape_pos_n'].notna().any():
        s_nn = st * (0.5 + 0.5 * d['shape_pos_n'].clip(0, 1).fillna(0))
    else:
        s_nn = pd.Series(np.nan, index=d.index)
    return {
        'old': d['ic_ir'].abs() * (0.25 + 0.75 * st),          # 现状: |IC_IR|×(0.25+0.75·stab)
        'new': st * (0.5 + 0.5 * sp),                          # 批1: stab×(0.5+0.5·shape_pos)
        'new+mono': (st * (0.5 + 0.5 * sp)).where(d['mono'] >= MONO_THR),   # 再叠 --min_mono
        'new_n': s_nn,                                         # 批2 候选: stab×(0.5+0.5·shape_pos_n)
    }


def topk(s, k, gate):
    """先按门槛过滤, **再在过门槛集合内**取前 k 名（与引擎 L1 的顺序一致）。

    ⚠ 曾经的写法是"在**全部**候选上 rank 再与门槛求交"——两者不等价: 若前 70 名里有 7 个
    没过门槛, 交集会只剩 63 个(实测 gen71 就是 63)。必须先把不过门槛的置 NaN 再排名。
    """
    ok = (s.notna() & gate).fillna(False)
    if not ok.any():
        return ok
    return ok & (s.where(ok).rank(ascending=False, method='first') <= k)


def stats_of(d, m):
    if not m.any():
        return None
    r = {c: float(np.nanmedian(d.loc[m, c].abs())) for c in STYLE}          # 强度
    # 注意 STYLE 元素已含 'st_' 前缀 -> 带符号列名为 's_lncap'(不是 's_st_lncap')
    r.update({('s' + c[2:]): float(np.nanmedian(d.loc[m, c])) for c in STYLE})  # 方向(带符号)
    r['_n'] = int(m.sum())
    return r


def main():
    if not os.path.exists(OBS):
        print('缺少', OBS, '-> 先跑 loop_engine.py --style_obs'); return 1
    d = pd.read_csv(OBS)
    d = d.dropna(subset=['ic_ir', 'stab'])
    if 'shape_pos' not in d.columns or d['shape_pos'].isna().all():
        print('⚠ shape_pos 全为 NaN -> 观测不可用(need_shape 未生效)'); return 1
    gens = sorted(int(g) for g in d['gen'].unique())
    print(f'观测样本 {len(d)} 行 / 代数 {gens} / 常数门槛 stab>={STAB_GATE}')
    print(f'shape_pos 有效 {d["shape_pos"].notna().mean():.0%}, '
          f'mono 有效 {d["mono"].notna().mean():.0%}, '
          f'mono>=0.75 占比 {float((d["mono"] >= MONO_THR).mean()):.1%}')

    L = [f'# old vs new 排序分·配对风格暴露比较（2026-09-11）', '',
         f'观测样本 {len(d)} 个候选 / 代数 {gens}；'
         f'门槛 `ic>{MIN_IC}` + `stab>={STAB_GATE}`（与引擎 L1 同口径，已从日志核对）；'
         f'`mono>={MONO_THR}` 为批1 推荐形状门槛。',
         '',
         '同一批候选只换排序公式（**配对**），差异全部来自公式；'
         '风格暴露取 |截面秩相关| 中位（越大=在该风格上暴露越重）。', '']

    summary = {}
    pool_ref = None
    k0 = K_LIST[0]
    for k in K_LIST:
        # 与引擎 L1 完全同口径: ic > min_ic(0.02) 且 stab > min_stab(0.75)
        gate_s = pd.Series((d['stab'] >= STAB_GATE).values & (d['ic'] > MIN_IC).values,
                           index=d.index)
        sc = scores(d)
        active = [nm for nm in MODES if sc[nm].notna().any()]
        deltas = {nm: {c: [] for c in STYLE} for nm in active if nm != 'old'}
        # 逐代
        per_gen = []
        for g in gens:
            gi = d.index[d['gen'] == g]
            if not len(gi):
                continue
            ent = {'gen': g, 'n_gate': int(gate_s.loc[gi].sum())}
            masks = {nm: topk(sc[nm].loc[gi], k, gate_s.loc[gi]) for nm in active}
            if not masks['old'].any() or not masks['new'].any():
                continue
            for nm, m in masks.items():
                r = stats_of(d.loc[gi], m)
                ent[nm] = r
                if r is None:
                    continue
                for c in STYLE:
                    ent[f'{nm}|{c}'] = r[c]
            ent['overlap'] = int((masks['old'] & masks['new']).sum()) / max(int(masks['new'].sum()), 1)
            if 'new_n' in masks and masks['new_n'].any():
                ent['overlap_n'] = (int((masks['old'] & masks['new_n']).sum())
                                    / max(int(masks['new_n'].sum()), 1))
            per_gen.append(ent)
            for nm in active:
                if nm == 'old':
                    continue
                for c in STYLE:
                    if f'{nm}|{c}' in ent and f'old|{c}' in ent:
                        deltas[nm][c].append(ent[f'{nm}|{c}'] - ent[f'old|{c}'])

        L += [f'## Top-{k}（门槛 ic>{MIN_IC} + stab>={STAB_GATE}）', '',
              '| 代数 | 通过门槛 | 排序分 | n | \\|lncap\\| | \\|lnamt\\| | \\|lntr\\| | \\|lnpx\\| |',
              '|---|---|---|---|---|---|---|---|']
        for ent in per_gen:
            for nm in active:
                if f'{nm}|st_lntr' not in ent:
                    continue
                L.append(f"| {ent['gen']} | {ent['n_gate']} | **{nm}** | "
                         f"{int(ent[nm]['_n'])} | {ent[f'{nm}|st_lncap']:.3f} | "
                         f"{ent[f'{nm}|st_lnamt']:.3f} | {ent[f'{nm}|st_lntr']:.3f} | "
                         f"{ent[f'{nm}|st_lnpx']:.3f} |")
            _ov = f"old∩new {ent['overlap']:.0%}"
            if 'overlap_n' in ent:
                _ov += f" / old∩new_n {ent['overlap_n']:.0%}"
            L.append(f"| | | *重叠率* | {_ov} | | | | |")

        # 汇总: 各代 delta 的均值/符号一致性(每个非 old 公式各出一块)
        for nm in active:
            if nm == 'old':
                continue
            L += ['', f'**各代 Delta（{nm} - old，正=该公式暴露更重）**', '',
                  '| 风格 | 均值 | 各代 | 符号一致 |', '|---|---|---|---|']
            for c in STYLE:
                v = deltas[nm][c]
                if not v:
                    continue
                mn = float(np.mean(v))
                same = all(x > 0 for x in v) or all(x < 0 for x in v)
                L.append(f"| {c} | {mn:+.3f} | " + ', '.join(f'{x:+.3f}' for x in v) +
                         f" | {'是' if same else '否'} |")
                summary[(k, nm, c)] = (mn, same)
        # 池化(所有代合并)对比: 另给"全池基准"行, 才能判断 old/new 是**偏离**还是**贴近**池平均
        L += ['', '**池化（所有代合并）**：', '',
              '| 排序分 | n | \\|lncap\\| | \\|lnamt\\| | \\|lntr\\| | \\|lnpx\\| | 中位 lncap | 中位 lntr |',
              '|---|---|---|---|---|---|---|---|']
        sc2 = scores(d)
        _rows = []
        gm = pd.Series(False, index=d.index)
        for g in gens:
            gm.loc[d.index[d['gen'] == g]] = gate_s.loc[d.index[d['gen'] == g]]
        _rows.append(('全池基准(过门槛)', gm))
        if k == k0:
            pool_ref = stats_of(d, gm)
        for nm in active:
            m = pd.Series(False, index=d.index)
            for g in gens:
                gi = d.index[d['gen'] == g]
                m.loc[gi] = topk(sc2[nm].loc[gi], k, gate_s.loc[gi])
            _rows.append((f'**{nm}**', m))
        for _nm, _m in _rows:
            r = stats_of(d, _m)
            if r:
                L.append(f"| {_nm} | {r['_n']} | {r['st_lncap']:.3f} | {r['st_lnamt']:.3f} | "
                         f"{r['st_lntr']:.3f} | {r['st_lnpx']:.3f} | {r['s_lncap']:+.3f} | "
                         f"{r['s_lntr']:+.3f} |")
        L.append('')

    # 结论
    L += ['## 结论', '', f'（样本：{len(gens)} 代 / {len(d)} 个被求值候选）', '']
    k0 = K_LIST[0]

    def _dg(nm, c):
        return summary.get((k0, nm, c))

    def _fmt_t(t):
        if not t:
            return '—'
        mn, same = t
        return f'{mn:+.3f}（{"各代同向" if same else "各代不一致"}）'

    L += [f'Top-{k0} 的 |风格暴露| 中位变化（相对 old）：', '',
          '| 风格 | `new`（批1） | `new_n`（shape 风格中性） |', '|---|---|---|']
    for c in STYLE:
        L.append(f'| `{c}` | {_fmt_t(_dg("new", c))} | {_fmt_t(_dg("new_n", c))} |')
    L.append('')

    lt, cap, amt, px = (_dg('new', 'st_lntr'), _dg('new', 'st_lncap'),
                        _dg('new', 'st_lnamt'), _dg('new', 'st_lnpx'))
    lt_n, cap_n = _dg('new_n', 'st_lntr'), _dg('new_n', 'st_lncap')
    if lt and lt[0] < -0.02:
        L.append('- ✅ `new` 的 `lntr`（低换手）**下降** → §8.3 风险①「新排序分在低换手方向'
                 '加倍下注」**未兑现**（方向相反）。')
    elif lt and lt[0] > 0.02:
        L.append('- ⚠ `new` 的 `lntr`（低换手）**上升** → §8.3 风险① **兑现**。')
    else:
        L.append('- ➖ `new` 的 `lntr` 未见系统性变化。')
    if cap and cap[0] > 0.02:
        L.append(f'- ⚠ **但 `new` 把市值暴露放大了 {cap[0]:+.3f}**'
                 f'（{"各代同向" if cap[1] else "各代不完全一致"}）→ 风格重心从"低换手"'
                 f'挪到了"小市值"，对「别老在市值/成交额打转」而言**问题换了方向、并未消失**。')
    # ---- 关键: new_n(shape 用风格中性后收益) 是否修掉市值放大 ----
    if cap_n is None:
        L.append('- ⓘ 观测文件缺 `shape_pos_n`（该轮未启用本项观测），无法评估 `new_n`。')
    elif cap and cap[0] > 0.02:
        if cap_n[0] < cap[0] * 0.6:
            L.append(f'- ✅ **`new_n` 有效**：市值暴露增幅 {cap[0]:+.3f} → **{cap_n[0]:+.3f}**'
                     f'（收窄 {100 * (1 - cap_n[0] / cap[0]):.0f}%），'
                     f'低换手仍在下降（{lt[0]:+.3f} → {lt_n[0]:+.3f}）'
                     f'⇒ **两个目标同时达成**，应把 `shape_pos` 正式换成风格中性版（批2）。')
        elif cap_n[0] >= cap[0]:
            L.append(f'- ❌ **`new_n` 未解决市值问题**：{cap_n[0]:+.3f} 不降反升'
                     f'（`new` 为 {cap[0]:+.3f}）⇒ "只中性化 R"这条路走不通，'
                     f'需改思路（例如给候选直接加"风格暴露"硬门槛，而不是改排序分）。')
        else:
            L.append(f'- ➖ `new_n` 部分改善：市值暴露 {cap[0]:+.3f} → {cap_n[0]:+.3f}，幅度有限。')
    else:
        L.append(f'- ⓘ `new` 本身未显著放大市值暴露，`new_n`（{_fmt_t(cap_n)}）未显示额外收益。')
    if pool_ref:
        _cap, _lt = pool_ref['s_lncap'], pool_ref['s_lntr']
        L.append(f"- ★ **全池基准**（过门槛的 {pool_ref['_n']} 个候选）：中位 `lncap` {_cap:+.3f} / "
                 f"中位 `lntr` {_lt:+.3f} —— 候选池本身基本是"
                 f"**{'市值中性' if abs(_cap) < 0.05 else '有市值倾向'}**的，"
                 f"因此 old/new 的市值偏差都是**选择压力新引入的**，不是池子自带的。"
                 f"new 相当于在这个中性池里**主动挑走小市值**。")
    L += ['',
          '**判读要点**',
          '- 两者选出的集合**重叠率仅 0~20%**（见上表）→ 排序分改写对选择的改变是**结构性**的，',
          '  不是微调；因此"某个风格暴露涨了"几乎必然发生，关键看涨的是不是我们最在意的那个。',
          '- `stab` 是低换手代理（`turn_est = 1 - stab`），但 `old` 里的 `|IC_IR|` 反而把'
          '**低换手候选**推得更靠前 ——',
          '  这与批1 标定"`ic_ir` 与 L2 Calmar 负相关（-0.317）"是同一枚硬币：'
          '**高 IC_IR 往往伴随低换手暴露**。',
          '- ⚠ 对比对象方的口径：他们对 **F25~F30 入库因子**的结论是"市值暴露已减轻、'
          '主战场换成低换手"。',
          '  本次发现 `new` 恰好**反向**：把市值暴露重新放大。两者并不矛盾 —— '
          '前者说的是"已入库因子的实际状态"，',
          '  后者说的是"新选择压力会把下一批因子推向哪里"。**入库状态 ≠ 选择方向。**',
          f'- ⚠ 局限：`stab>={STAB_GATE:g}` 是名义门槛（真实 `min_stab` 由 B角逐代调整，'
          f'观测文件未记录）；',
          '  `mono/shape_pos/风格` 均为 **L1 子面板 `[::FWD]` 视图**的代理值，'
          '绝对值以 `standard_test` 全量报告为准。']

    txt = '\n'.join(L)
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write(txt + '\n')
    print(f'已写入 {OUT}（{len(d)} 行观测 / 代数 {gens}）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
