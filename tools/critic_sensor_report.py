# -*- coding: utf-8 -*-
"""critic_sensor_report.py — 三方对比：**B角建议 vs LLM建议 vs 实际产出**

为什么需要它（2026-09-13 立；**2026-09-14 起身份变了 —— 见下**）：
  **【修复前它用来立论】** `engine/loop_critic.py:94` 的 `fail_calmar` 曾用**硬编码 0.5 + 全A 口径**，
  而池内挖掘的**判定**用的是**池口径**（`任一池 Calmar > 0.15 或 全A 口径`）
  ⇒ 诊断与判定**脱钩**：`fail_calmar` 恒为 1.000（实测 1000 gen1 有 2 个 Calmar 0.66/0.56
  通过并入库，仍报 1.000）⇒ B角 规则5 每代必触发 ⇒ **B角 按错误信号调参**。
  该问题已用本脚本产出的 **96 代**数据坐实，并已**修复**（roadmap §8.45）。

  **【修复后它用作长期监控】** 现在 `fail_calmar` 与**生效门槛对账**、并新增
  `fail_calmar_neg`（真·信号弱）与 `fail_pool_calmar`（池口径）；
  动作有**饱和检测**、LLM 有**否决权**（连续否决 ⇒ 永久停用）。
  ⇒ 本脚本继续回答三个"健康度"问题：
    ① `fail_calmar` 是否**还在恒定**（恒 = 对账又漂了，`==1.000` 会报警）；
    ② 规则动作是否**还在每代重复施加**（§1.1 修法③ 若失效会重现）；
    ③ LLM 建议与 B角 是否仍**方向相反**（分歧数就是"纠偏机会"的量）。
  ⇒ 并排摆出「B角建议 / LLM建议 / 实际产出」，**用数据说话而不是靠印象**。

用法: python tools/critic_sensor_report.py [--pools=1000,300,500] [--out=ai_test/_critic_sensor.md]
"""
import argparse
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

# LLM 审查里出现这些词 => 认为它在**反驳/质疑** B角 的规则建议
DOUBT_WORDS = ('冲突', '过拟合', '不够', '偏保守', '稀释', '锁死', '放大噪声', '打折', '失效')


def read_text(p):
    if not os.path.exists(p):
        return ''
    raw = open(p, 'rb').read()
    for enc in ('utf-8', 'gbk', 'cp936'):
        try:
            s = raw.decode(enc)
            if s.count('\ufffd') == 0:
                return s
        except Exception:
            continue
    return raw.decode('utf-8', errors='replace')


def parse_journal(pool):
    """把一个 journal 拆成 [ {gen, diag, b_sug, llm, doubt} ... ]。"""
    p = os.path.join(DOCS, 'loop_journal{}.md'.format('' if pool == 'all' else '_' + pool))
    txt = read_text(p)
    if not txt:
        return []
    out = []
    chunks = re.split(r'\n##\s*第\s*(\d+)\s*代', txt)
    # chunks = [前言, gen1, body1, gen2, body2, ...]
    for i in range(1, len(chunks) - 1, 2):
        gen, body = int(chunks[i]), chunks[i + 1]
        rec = {'gen': gen, 'diag': {}, 'b_sug': [], 'llm': '', 'doubt': False}
        # 1) 诊断表：找以 `| n_l1` 开头的表头行，取其下一非分隔行作为值行
        lines = body.splitlines()
        for j, l in enumerate(lines):
            if l.strip().startswith('| n_l1'):
                keys = [x.strip() for x in l.strip().strip('|').split('|')]
                for k in range(j + 1, min(j + 4, len(lines))):
                    v = lines[k].strip()
                    if v.startswith('|') and not re.match(r'^\|[\s\-|:]+\|$', v):
                        vals = [x.strip() for x in v.strip('|').split('|')]
                        if len(vals) == len(keys):
                            rec['diag'] = dict(zip(keys, vals))
                        break
                break
        # 2) B角建议 bullets
        m = re.search(r'\*\*B角建议\(下一代策略\)\*\*:(.*?)(?:\n\n|```)', body, re.S)
        if m:
            rec['b_sug'] = [x.strip(' -') for x in m.group(1).splitlines()
                            if x.strip().startswith('-')]
        # 3) LLM 审查正文（`>` 引用行）
        m = re.search(r'\*\*AI 审查.*?\*\*:(.*)$', body, re.S)
        if m:
            rec['llm'] = ' '.join(x.strip(' >') for x in m.group(1).splitlines()
                                  if x.strip().startswith('>')).strip()
            rec['doubt'] = any(w in rec['llm'] for w in DOUBT_WORDS)
        out.append(rec)
    return out


def parse_registered(pool):
    """从引擎日志里数每代实际入库数（比 journal 的 n_pass 更"落地"）。"""
    import glob
    d = os.path.join(ROOT, 'ai_test', '_tracks')
    res = {}
    for f in glob.glob(os.path.join(d, 'pool_{}_gen*.log'.format(pool))):
        g = re.search(r'gen(\d+)\.log$', f)
        if not g:
            continue
        t = read_text(f)
        m = re.findall(r'入库 (\d+) 个新因子', t)
        res[int(g.group(1))] = int(m[-1]) if m else None
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pools', default='1000,300,500')
    ap.add_argument('--out', default=os.path.join(HERE, '_critic_sensor.md'))
    a = ap.parse_args()

    L = ['# B角「诊断传感器」体检：B角建议 vs LLM建议 vs 实际产出', '']
    L += ['> 用途（2026-09-14 起）：**监控**传感器/动作/LLM 纠偏三条链路是否仍健康。'
          '（立论期的"脱钩"问题已在 roadmap §8.45 修复。）', '']
    L += ['`fail_calmar` **现行**定义 = `(fail["calmar"] <= 生效的 --min_calmar).mean()`'
          '（**已与门槛对账**，见 `engine/loop_critic.diagnose(gate=...)`）；', '']
    L += ['并列给出 `fail_calmar_neg`（`calmar <= 0`，**真·信号弱、不随配置漂移**）与 '
          '`fail_pool_calmar`（**池口径** = 池内模式的真实卡点）。', '']
    L += ['⚠ **`fail_calmar` == 1.000 的代数 > 0** ⇒ 说明对账又漂了，需立刻查 `gate` 是否传对。', '']

    any_bad = []
    all_fc = []          # 所有代的 fail_calmar（用于统计「规则5 触发比例」）
    n_doubt = 0          # LLM 反驳次数
    n_total = 0          # 总代数
    n_r5_fire = 0        # ★ r5 **实际施加**的代数（≠「条件成立」代数！）
    n_r5_block = 0       # ★ r5 被**拦截**的代数（饱和/LLM 否决）
    for pool in [x.strip() for x in a.pools.split(',') if x.strip()]:
        recs = parse_journal(pool)
        reg = parse_registered(pool)
        if not recs:
            L += ['## pool={}  （无 journal，跳过）'.format(pool), '']
            continue
        L += ['## pool={}'.format(pool), '']
        L += ['| 代 | n_l2 | n_pass | ic_med | ic_max | **fail_calmar** | 判据 | '
              'r5 动作 | LLM 反驳 B角? | 实际入库 |', '|---|---|---|---|---|---|---|---|---|---|']
        for r in recs:
            d = r['diag']
            fc = d.get('fail_calmar', '-')
            # 传感器是否"恒定"（= 对每代都几乎同一个值且接近 1）
            flag = '⚠ 恒为 1.000' if fc not in ('-', '') and abs(float(fc) - 1.0) < 1e-9 else ''
            if flag:
                any_bad.append((pool, r['gen']))
            try:
                all_fc.append((pool, r['gen'], float(fc)))
            except Exception:
                pass
            n_total += 1
            if r['doubt']:
                n_doubt += 1
            # ★★ 「条件成立」≠「动作施加」（2026-09-14 修的判据缺陷）：
            #   旧版只看 `fail_calmar > 0.55`（=条件），于是一旦条件恒真就报"饱和检测没生效"，
            #   而实际上动作可能已被**拦截**（`【拦截】[r5_...]`）—— 那是**机制生效**的表现。
            #   ⇒ 必须直接数 journal 里是「施加」还是「拦截」。
            _r5f = any(s.lstrip().startswith('【r5_calmar_cross】') for s in (r['b_sug'] or []))
            _r5b = any('【拦截】' in s and 'r5_calmar_cross' in s for s in (r['b_sug'] or []))
            n_r5_fire += 1 if _r5f else 0
            n_r5_block += 1 if _r5b else 0
            np_ = reg.get(r['gen'])
            L.append('| {} | {} | {} | {} | {} | **{}** {} | {} | {} | {} | {} |'.format(
                r['gen'], d.get('n_l2', '-'), d.get('n_pass', '-'),
                d.get('ic_med', '-'), d.get('ic_max', '-'), fc, flag,
                '与生效门槛脱钩' if flag else '已对账',
                ('**施加**' if _r5f else '') + ('**拦截**' if _r5b else '') or '—',
                '★ 是' if r['doubt'] else '—',
                '—' if np_ is None else np_))
        L += ['']
        # 逐代并列建议
        for r in recs:
            L += ['### 第 {} 代'.format(r['gen']), '']
            L += ['**B角（规则）建议**：', '']
            for s in (r['b_sug'] or ['(无)']):
                L += ['- {}'.format(s)]
            L += ['', '**LLM（DeepSeek）建议**{}：'.format(
                '—— ⚠ **与 B角 有分歧**' if r['doubt'] else ''), '']
            L += ['> {}'.format(r['llm'][:1200] if r['llm'] else '(无)'), '']

    # ---- 结论：三个层次的问题（与 docs/loop_todo.md 待改 #1 一一对应）----
    vals = [v for _, _, v in all_fc]
    L += ['## 结论', '']
    if not vals:
        L += ['- 没有可用的 journal 数据（可能轨道还没跑出结果）。', '']
    else:
        mx = max(vals)
        mn = min(vals)
        trig = sum(1 for v in vals if v > 0.55)
        L += ['**关键统计**（覆盖 {} 个世代）'.format(len(vals)), '']
        L += ['| 指标 | 值 |', '|---|---|']
        L += ['| `fail_calmar` == 1.000 的代数 | **{} / {}** |'.format(len(any_bad), len(vals))]
        L += ['| `fail_calmar` 取值区间 | **{:.3f} ~ {:.3f}** |'.format(mn, mx)]
        L += ['| 规则5 触发条件（`> 0.55`）成立比例 | **{} / {} = {:.0%}** |'.format(
            trig, len(vals), trig / max(len(vals), 1))]
        L += ['| LLM 审查中的反驳次数 | **{} / {}** |'.format(n_doubt, n_total)]
        # ★ 「条件成立」≠「动作施加」：两者并列，才能看出"机制有没有在生效"
        L += ['| **r5 实际施加代数** | **{} / {}** |'.format(n_r5_fire, len(vals))]
        L += ['| **r5 被拦截代数** | **{} / {}** |'.format(n_r5_block, len(vals))]
        L += ['']
        # ---- 健康度判读（2026-09-14 修复后：以下三条是"监控项"，不是"病因清单"）----
        L += ['⇒ **三条链路的健康度判读**（修复见 `docs/log/2026-09.md` §8.45；'
              '问题清单见 `docs/loop_todo.md` §1.1）：', '']
        if any_bad:
            L += ['- **① 传感器对账⚠ 又漂了**：**{} / {}** 代的 `fail_calmar` 恰为 `1.000`'
                  ' ⇒ 极可能 `gate` 没传对（`diagnose(gate=...)` 应等于生效的 `--min_calmar`），'
                  '或该池 `--min_calmar` 本身为 0 且**全部**失败者 `calmar<=0`（真弱，属正常）。'
                  '**先核对 journal 表里的 `gate_min_calmar` 列。**'.format(
                      len(any_bad), len(vals)), '']
        else:
            L += ['- **① 传感器对账 ✓ 健康**：无一代 `fail_calmar` 恰为 `1.000`'
                  '（取值区间 {:.3f} ~ {:.3f}）⇒ 判据跟得上实际门槛。'.format(mn, mx), '']
        # ★ 判据修正（2026-09-14）：**"条件成立" ≠ "动作施加"**。
        #   条件恒真（trig=100%）但动作被拦 ⇒ 那正是**饱和/否决机制在生效**，是**健康**的！
        #   旧版只看条件，会把"机制生效"误报成"机制没生效"。
        if n_r5_fire == len(vals) and len(vals) >= 3:
            L += ['- **② ⚠ r5 在**每一代**都被**施加****（条件成立比例 {:.0%} 且无拦截）'
                  '⇒ 说明**饱和检测/LLM 否决都没生效**（§1.1 修法③④）'
                  '⇒ 查 journal 的「规则动作留痕」段与 `sug[\'_act\']`。'.format(
                      trig / len(vals)), '']
        elif n_r5_block:
            L += ['- **② ✓ 饱和/否决机制在生效**：r5 施加 {} 代、**被拦 {} 代**'
                  '（虽然"条件成立"仍占 {:.0%} —— **但条件成立不等于动作施加**，'
                  '这正是自适应从"固定偏移"变回"有记忆"的证据）。'.format(
                      n_r5_fire, n_r5_block, trig / len(vals)), '']
        else:
            L += ['- **② r5 施加 {} 代 / 条件成立 {:.0%}** ⇒ 条件本身不常成立，'
                  '属正常自适应范围。'.format(n_r5_fire, trig / len(vals)), '']
        if n_doubt:
            L += ['- **③ LLM 纠偏机会: 本次范围内 LLM 与 B角 分歧 {} 次**'
                  '（共 {} 代）。修复后这些分歧会经 `_veto` **真的生效**；'
                  'journal 里可查「⚖️ 规则动作否决（机器读取）」与「【拦截】」行核实。'.format(
                      n_doubt, n_total), '']
        else:
            L += ['- **③ 无 LLM 分歧**（可能未配置 key，或 B角 与 LLM 判断一致）。', '']

    outp = a.out if os.path.isabs(a.out) else os.path.join(ROOT, a.out)
    io.open(outp, 'w', encoding='utf-8').write('\n'.join(L))
    print('[DONE] ->', outp)
    print('  共 {} 处传感器失真标记'.format(len(any_bad)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
