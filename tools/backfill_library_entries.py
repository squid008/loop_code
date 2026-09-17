# -*- coding: utf-8 -*-
"""backfill_library_entries.py — 把**历史的**入库事件回填进 `docs/library_entries.jsonl`

## 为什么需要它（用户 2026-09-17 之问）
「我发现又入库了一个新因子，但**找不到什么时候入库的、入的哪个库**」
⇒ 看板加「新入库日志」卡片。但**过去的**入库没有记时间（引擎是今天才加上这个记录的）
⇒ 本工具负责**回填历史**，把"什么时候"尽量补上 —— 并且**注明是推算的**（不臆造，铁律）✓

## 时间从哪来（按可靠性排序，逐条标 `tsSource`）
1. `ai_test/_tracks/pool[_<池>]_gen<代数>.log` 的 **mtime** ⇒ `tsSource='gen_log'`
   —— 该代引擎跑完的时间，误差 ~1 代（这是**最接近真实入库时刻**的可用证据 ✓）
2. 该池库文档 `docs/factor_library[_<池>].md` 的 **mtime** ⇒ `tsSource='md_mtime'`
   —— ⚠ 粗：那是该池**最后一次**写库的时间 ⇒ 只对"最后一批"准确（老条目会偏晚）✗
3. 都没有 ⇒ `tsSource='unknown'`（时间留空，**绝不编一个** ✓）

## 幂等
按 `(pool, code)` 去重；**已存在的行一律保留**（尤其 `source='engine'` 的真实记录 ✓）

用法: python tools/backfill_library_entries.py [--dry]
"""
import argparse
import io
import json
import os
import sys
import time

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DOCS = os.path.join(ROOT, 'docs')
TRACKS = os.path.join(ROOT, 'ai_test', '_tracks')
OUT = os.path.join(DOCS, 'library_entries.jsonl')
REG = os.path.join(DOCS, 'factor_registry.json')


def _sfx(pool):
    return '' if pool == 'all' else '_' + pool


def _ts_for(pool, gen, is_last_batch=False):
    """`(ts, tsSource, note)` —— 按可靠性取时间；**取不到就留空，绝不编一个** ✓

    ⚠⚠ 2026-09-17 首版踩到的坑（自己发现并改掉）：
      首版对**所有**找不到引擎日志的条目都退化成"库文档 mtime" ⇒ 60 条历史条目拿到**同一个时间**
      ⇒ 看板上一片"同时入库"的假象 ✗✗（这比"时间未知"更糟：它会**误导**）
      ⇒ 现在：`md_mtime` **只给"该池最后一批"用**（那时确实刚追加过 ⇒ 准确 ✓），
        更早的条目一律 `ts=None + tsSource='unknown'` ✓
    """
    if gen is not None:
        for nm in filter(None, ('pool{}_gen{}.log'.format(_sfx(pool), gen),
                                'pool_gen{}.log'.format(gen) if pool == 'all' else None)):
            p = os.path.join(TRACKS, nm)
            if os.path.exists(p):
                return (time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(os.path.getmtime(p))),
                        'gen_log', '该代引擎日志的写入时间（最接近入库时刻的可用证据）')
    if is_last_batch:
        p = os.path.join(DOCS, 'factor_library{}.md'.format(_sfx(pool)))
        if os.path.exists(p):
            return (time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(os.path.getmtime(p))),
                    'md_mtime', '按该池库文档最后修改时间推算（只对该池最后一批入库准确）')
    return None, 'unknown', '早期入库，没有留下任何时间证据（如实留空，不臆造）'


def _key(e):
    return (e.get('pool'), e.get('code') or e.get('expr'))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry', action='store_true', help='只报告，不写文件')
    a = ap.parse_args()
    print('=' * 96)
    print('回填历史入库事件 → %s' % os.path.relpath(OUT, ROOT))
    print('=' * 96)
    if not os.path.exists(REG):
        print('  ✗ 找不到 %s ⇒ 先跑 tools/export_factor_registry.py' % os.path.relpath(REG, ROOT))
        return 1
    js = json.load(io.open(REG, encoding='utf-8'))
    have = {}
    if os.path.exists(OUT):
        for ln in io.open(OUT, encoding='utf-8'):
            ln = ln.strip()
            if not ln:
                continue
            try:
                e = json.loads(ln)
            except Exception:
                continue
            have[_key(e)] = e            # 后者覆盖前者（同键只留一条 ✓）
    n_eng = sum(1 for e in have.values() if e.get('source') == 'engine')
    # ★★ 关键：**只有 `engine` 的真实记录不可动**；其它 `backfill` 行都是**派生**的
    #   ⇒ 每次重跑**全部重算** —— 否则首版那个"60 条同一时间"的错误推算会被永久固化 ✗
    keep = {k: e for k, e in have.items() if e.get('source') == 'engine'}
    # 每池"最后一批"的代数（= 该池 registry 里最大的 gen）⇒ 这一批允许用 md mtime 推算 ✓
    _maxg = {}
    for f in (js.get('factors') or []):
        g = f.get('gen')
        if isinstance(g, int):
            _maxg[f['pool']] = max(_maxg.get(f['pool'], -1), g)
    add, srcs = [], {}
    for f in (js.get('factors') or []):
        ev = dict(pool=f.get('pool'), gen=f.get('gen'), code=f.get('no'),
                  expr=f.get('expr'), family=f.get('family'), oneLiner=f.get('oneLiner'),
                  source='backfill')
        if _key(ev) in keep:
            continue                      # ★ engine 真实记录 ⇒ 绝不动 ✓
        _last = isinstance(f.get('gen'), int) and f['gen'] == _maxg.get(f['pool'])
        ts, s, nt = _ts_for(ev['pool'], ev['gen'], is_last_batch=_last)
        ev['ts'] = ts
        ev['tsSource'] = s
        ev['tsNote'] = nt
        srcs[s] = srcs.get(s, 0) + 1
        add.append(ev)
    have = keep
    print('  已有 %d 条（其中 engine 真实记录 %d 条，**一律保留**）' % (n_eng, n_eng))
    print('  本次回填 %d 条：%s' % (len(add), ' · '.join('%s=%d' % kv for kv in sorted(srcs.items()))))
    if srcs.get('unknown'):
        print('  ⚠ %d 条**没有时间证据**（早期入库，既无该代引擎日志、也不是最后一批）'
              '⇒ 时间如实留空 ✓（不臆造；看板会标"时间未知"）' % srcs['unknown'])
    allrows = list(have.values()) + add
    # 按时间排序（无时间的排最前，别让它们混在中间造成"时间倒流"的错觉 ✓）
    allrows.sort(key=lambda e: (e.get('ts') or ''))
    if a.dry:
        for e in allrows[-8:]:
            print('    %s  %-20s %-5s %-4s %s' % (e.get('ts') or '(未知)', e.get('tsSource'),
                                                  e.get('pool'), e.get('code') or '-',
                                                  (e.get('oneLiner') or e.get('expr') or '')[:40]))
        print('  （--dry：未写文件）')
        return 0
    tmp = OUT + '.tmp'
    with io.open(tmp, 'w', encoding='utf-8') as fh:
        for e in allrows:
            fh.write(json.dumps(e, ensure_ascii=False) + '\n')
    os.replace(tmp, OUT)
    print('  已写 %s：%d 条（%.1f KB）✓' % (os.path.relpath(OUT, ROOT), len(allrows),
                                            os.path.getsize(OUT) / 1024.0))
    print()
    print('★ 看板「新入库日志」卡取**最后 N 条**（默认 50）⇒ 文件内按时间递增 ✓')
    return 0


if __name__ == '__main__':
    sys.exit(main())
