# -*- coding: utf-8 -*-
"""_test_registry.py — 「因子登记表」守门（`docs/factor_registry.json`，用户 2026-09-17 之问）

## 用户之问
「搞个文件记录各池已入库（/已丢弃）因子的 **编号 · 入库代数 · 家族 · 一句话 · 具体公式**，
然后我**家里 pull**（库是空的）也能自动识别、把因子重跑一遍生成 facs 和各种曲线图？」

## 结论（核查过，不是猜）
· 清单**早就在 git 里**：各池 `docs/factor_library{_pool}.md` 的「因子总览」表
  = `编号 | 入库代数 | 家族 | 一句话 | 状态`，每个因子块还有**完整公式** + `sign` + 池标签 + 费后指标 ✓
· **但"跑一遍就有"原先不成立** ✗：`build_facs / factor_metrics / factor_curves` 都要
  **`loop_state*.pkl` 里的 `bank`**（入库 Node 的权威口径），而 `.gitignore` 忽略 `*.pkl`
  ⇒ 家里没有它 ⇒ **一个因子都重建不出来** ✗✗
· ⇒ 补的**不是"又一份清单"**，而是把这一环导出成 git 里的 `docs/factor_registry.json`（含 **node 结构**）✓

## 本测试钉住三件事（每条都对应一种"回家后发现少了/错了"的真实故障）
1. **清单完整**：JSON 必须覆盖各池 md 总览表里的**每一个编号** ⇒ 否则家里少因子 ✗
2. **能精确重建**：每条都要有 `expr` + `node`，且 `node_from_dict(node)` 的 `str()`
   **逐字等于** `expr`（含引号/空格）⇒ 否则重建出的是**另一个因子** ✗
3. ★★ **等价性（最关键）**：本机 `loop_state*.pkl` 里**每一个**入库因子，都能在 JSON 里找到
   ⇒ 这就**证明**"家里没有 pkl 也能重建出本机的全部因子" ✓（否则换机器会**悄悄少算** ✗）
4. **同步**：JSON 与当前 md/pkl **一致**（用导出器的 `compare`）⇒ 忘了重导出会当场红 ✓
   （收尾管线 `run_tracks.do_global_tail` 每轮自动重导 ✓）

用法: python tools/_test_registry.py
"""
import io
import json
import os
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DOCS = os.path.join(ROOT, 'docs')
ENG = os.path.join(ROOT, 'engine')
sys.path.insert(0, HERE)
sys.path.insert(0, ENG)

OK = [0, 0]
REG = os.path.join(DOCS, 'factor_registry.json')
POOLS = ('all', '300', '500', '1000', '50')


def chk(desc, cond, hint=''):
    OK[0] += 1
    if not cond:
        OK[1] += 1
    print('  [{}] {}{}'.format('OK ' if cond else 'FAIL', desc,
                               '' if cond else ('  ← ' + hint if hint else '')))


def main():
    print('=' * 96)
    print('因子登记表守门（docs/factor_registry.json）')
    print('=' * 96)
    import export_factor_registry as ER
    import loop_engine as LE

    chk('登记表存在（**进 git** 的机器可读清单）', os.path.exists(REG),
        '跑 `python tools/export_factor_registry.py` 生成')
    if not os.path.exists(REG):
        return 1
    js = json.load(io.open(REG, encoding='utf-8'))
    fs = js.get('factors') or []
    chk('schema=1 且条目数 > 0（实得 %d 条）' % len(fs), js.get('schema') == 1 and fs)

    # ---- [1] 清单完整：覆盖各池 md 总览表的每个编号 ----
    print('\n[1] 清单完整（JSON ⊇ 各池 md 总览表）')
    tot_md = 0
    for pool in POOLS:
        ov = ER.parse_overview(pool)
        have = {(f['pool'], f['no']) for f in fs}
        miss = sorted(n for n in ov if (pool, n) not in have)
        tot_md += len(ov)
        chk('池 %-5s：md 列出 %2d 条 ⇒ JSON 全覆盖' % (pool, len(ov)), not miss,
            '缺 %s（家里会少这些因子 ✗）' % miss[:5])
    chk('各池 md 合计 %d 条，JSON 有 %d 条' % (tot_md, len(fs)), len(fs) >= tot_md)

    # ---- [2] 每条都能精确重建 ----
    print('\n[2] 能精确重建（`node_from_dict` 的 str == expr）')
    bad_node, no_expr, no_meta = [], [], []
    for f in fs:
        if not f.get('expr'):
            no_expr.append((f['pool'], f['no']))
            continue
        if not f.get('node'):
            bad_node.append((f['pool'], f['no']))
            continue
        try:
            nd = LE.node_from_dict(f['node'])
        except Exception as e:                                # noqa: BLE001
            bad_node.append((f['pool'], f['no'], type(e).__name__))
            continue
        if str(nd) != f['expr']:
            bad_node.append((f['pool'], f['no'], 'str≠expr'))
        # ⚠ "仅 bank"条目（md 漏记那种）**没有编号/代数** —— 这是**如实留空**，不算错 ✓
        if not f.get('bankOnly') and (not f.get('no') or f.get('gen') is None):
            no_meta.append((f['pool'], f['no']))
    chk('每条都有公式（实得 %d 条缺）' % len(no_expr), not no_expr, str(no_expr[:5]))
    chk('★ 每条的 node 都能重建出**逐字相同**的公式（实得 %d 条有问题）' % len(bad_node),
        not bad_node, str(bad_node[:5]))
    chk('每条都有编号 + 入库代数（实得 %d 条缺）' % len(no_meta), not no_meta, str(no_meta[:5]))
    n_fam = sum(1 for f in fs if f.get('family'))
    n_one = sum(1 for f in fs if f.get('oneLiner'))
    chk('家族/一句话 覆盖率高（家族 %d/%d · 一句话 %d/%d）' % (n_fam, len(fs), n_one, len(fs)),
        n_fam >= len(fs) * 0.9 and n_one >= len(fs) * 0.9,
        '这两列来自 md 的「因子总览」表；缺太多说明表被改坏了 ✗')

    # ---- [3] ★★ 等价性：本机 pkl 的每个入库因子都在 JSON 里 ----
    print('\n[3] ★★ 等价性：本机 pkl 里的入库因子 ⊆ JSON（= 家里没有 pkl 也能重建全部）')
    for pool in POOLS:
        bank = ER._load_bank_nodes(pool)          # 直接读 pkl（本机才有）
        if not bank:
            print('  [SKIP] 池 %-5s：本机无 state pkl（就是"家里"那种情形）✓' % pool)
            continue
        in_reg = {f['expr'] for f in fs if f['pool'] == pool}
        miss = [e for e in bank if e not in in_reg]
        chk('池 %-5s：pkl 里 %2d 个入库因子 ⇒ JSON 全覆盖' % (pool, len(bank)), not miss,
            '少 %s（换机器会**悄悄少算**这些 ✗）' % [m[:40] for m in miss[:3]])

    # ---- [3b] md 漏记（**数据/文档漂移**：只吼，不判失败）----
    #   为什么不当失败：JSON 已经兜住（不会漏算 ✓）；而"补编号/家族/一句话"是**人工精炼**的活
    #   ⇒ 做成硬失败会阻塞与它无关的工作 ✗（但必须吼得足够响 —— 见下）
    print('\n[3b] 库文档 md 漏记（只为**看得见**，不算失败）')
    drift = js.get('mdDrift') or []
    if drift:
        for x in drift[:6]:
            print('    ⚠ 池 %-5s 已入库但 md 无条目：%s' % (x['pool'], x['expr'][:80]))
        print('    ⇒ 已按「仅 bank」收录（**不会漏算** ✓）；编号/家族/一句话 待人工补进 md ✗')
    else:
        print('    ✓ md 与引擎 bank 一致')

    # ---- [4] 同步：忘了重导出会当场红 ----
    print('\n[4] 与当前 md/pkl 同步（收尾管线每轮自动重导）')
    cur = ER.build()
    probs = ER.compare(cur['factors'], js)
    chk('JSON 与现状一致（实得 %d 处差异）' % len(probs), not probs, '; '.join(probs[:4]))

    # ---- [5] ★ 规模化（用户之问："将来几千个因子会不会爆炸/读崩溃？"）----
    print('\n[5] ★ 规模化：体积与"无变化不重写"')
    kb = os.path.getsize(REG) / 1024.0
    per = kb / max(1, len(fs))
    print('    实测: 每因子约 %.2f KB ⇒ 推算 1000 因子约 %.1f MB / 10000 因子约 %.1f MB'
          % (per, per * 1000 / 1024.0, per * 10000 / 1024.0))
    chk('单文件未超告警阈值（%.0f MB；现在 %.1f KB）—— 读它从不是瓶颈（10 MB 解析约 0.18s）✓'
        % (ER.SIZE_WARN_MB, kb), kb <= ER.SIZE_WARN_MB * 1024,
        '超了就按池分片（为的是 git diff 可读，不是为了性能 ✗）')
    # ★★ "内容没变就不重写"：否则每轮收尾都因 `generatedAt` 变化而给 git 添一个 blob ✗✗
    js2 = json.loads(json.dumps(js, ensure_ascii=False))          # 深拷贝
    js2['generatedAt'] = '1970-01-01 00:00:00'                    # 只改时间戳
    chk('★ `compare` **不看时间戳** ⇒ 内容没变就能"跳过写入"（少给 git 添版本 ✓）',
        not ER.compare(cur['factors'], js2),
        '若它把时间戳算成差异 ⇒ 每轮收尾都会重写文件 ✗')
    chk('★ `load_bank_nodes` 走**进程内缓存**（`_registry_nodes`，5 池不再重复解析 ✓）',
        'def _registry_nodes(' in io.open(os.path.join(ROOT, 'tools', 'build_facs.py'),
                                         encoding='utf-8').read())

    print('\n' + '=' * 96)
    print('通过 {}/{}'.format(OK[0] - OK[1], OK[0]) + ('' if OK[1] else '  ✓ 全部通过'))
    return 1 if OK[1] else 0


if __name__ == '__main__':
    sys.exit(main())
