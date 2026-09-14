# -*- coding: utf-8 -*-
"""backfill_library_sign.py — 给各因子库的**历史明细块**补上「符号 `sign`」行

## 为什么需要（`loop_todo §1.23`）

引擎求值时对 `sign<0` 的候选**取负**（让"值越大越好"）。
下游若拿到因子值 h5 **直接排序选股、不乘 `sign`** ⇒ **方向反了、组合反向选股** ✗
而 `factor_library*.md` 的 **41 个明细块里，含 `sign` 的 0 处** —— 这条信息**根本无处可查**。

⇒ 引擎侧（`_lib_sync`）**新条目**已加这行；**历史条目**由本脚本一次性回填。

## 为什么是"写进明细块"而不是"加表格列"

`factor_library*.md` 是 **append-only**：总览表头只写一次，历史行已按固定 5 列存在
⇒ **加列会让历史行全部错位**（与 §8.30 的 CSV 同一个坑；该结论 2026-09-13 已写进
`loop_engine._lib_sync` 的注释）⇒ 池标签当初也是写进明细块 ✓ 本脚本沿用同一约定。

## sign 从哪来

`facs/<xx>/<name>/values.h5` 的 attrs（`FactorStore.list_factors()`），按**表达式字符串**
与库里的明细块**精确匹配**。
⚠ 匹配不到（该因子未在 `facs/` 落地）⇒ 写"**未记录**"，**绝不臆造**
（缺失时不猜 —— roadmap §8.45 铁律）。

## 用法

    python tools/backfill_library_sign.py            # DRY-RUN：先看会改哪些块
    python tools/backfill_library_sign.py --apply    # 写盘
"""
import argparse
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
sys.path.insert(0, os.path.join(ROOT, 'engine'))

# 「### F07 · gen11 入库...」-> 正文（到下一个 ### / ## / 文件末）
RX_BLOCK = re.compile(r'^###\s*(F\d+)\s*·[^\n]*\n(.*?)(?=^###\s|\n## |\Z)', re.M | re.S)
# 明细块里第一段 ``` 代码块 = 表达式
RX_EXPR = re.compile(r'```[a-z]*\n([^\n]+)\n```')
# ⚠⚠ 幂等检测必须用**宽松**标记（2026-09-14 实录的 bug）：
#   初版用 `- **符号 \`sign\`：`（带粗体）作标记，而"未落地"那条写的是
#   `- 符号 \`sign\`：**未记录**`（**不带开头粗体**）⇒ **检测不到** ⇒
#   第二次运行会给它**再插一行**（重复）✗
#   ⇒ 只要出现 `符号 \`sign\`：` 就认为已有 ⇒ 两种形态都覆盖 ✓
SIGN_LINE = '符号 `sign`：'
NO_SIGN = '- 符号 `sign`：**未记录**'


def build_sign_map():
    """`facs/` -> {表达式: sign}（按 expr 精确匹配；同一 expr 取第一个）。"""
    import factor_store as FS
    m = {}
    for nm, p, at in FS.list_factors():
        e = str(at.get('expr') or '').strip()
        s = at.get('sign')
        if e and s is not None and e not in m:
            try:
                m[e] = int(round(float(s)))
            except Exception:
                pass
    return m


def sign_line(v):
    if v is None:
        return NO_SIGN + '（该因子未在 `facs/` 落地 ⇒ 待落地后回填）\n'
    return ('- **符号 `sign`：`%d`**（★ 因子值须乘它才是"越大越好"的方向；'
            '不乘 ⇒ 反向选股）\n' % v)


def patch_file(path, smap, apply_):
    """给一个库文件回填 `sign` 行。

    ★ 实现要点（初版写得很绕、差点埋 bug）：
      直接**按区段拼接** —— `RX_BLOCK` 的 `span()` 精确给出每块的范围，
      「块内」再定位表达式代码块的位置，**在该代码块结束处插入一行**即可。
      不要去 `replace(body, ...)`（`body` 可能在文件里出现多次 ⇒ 替换到别处 ✗）。
    """
    t = io.open(path, encoding='utf-8').read()
    stats = dict(blocks=0, added=0, matched=0, missing=0, already=0)
    pieces, last = [], 0
    for m in RX_BLOCK.finditer(t):
        stats['blocks'] += 1
        body = m.group(2)
        if SIGN_LINE in body:
            stats['already'] += 1
            continue
        me = RX_EXPR.search(body)
        if not me:
            continue
        v = smap.get(me.group(1).strip())
        stats['matched' if v is not None else 'missing'] += 1
        stats['added'] += 1
        # 块内绝对偏移 = 块起点 + (组2 相对块起点的偏移) + 代码块末尾
        ins = m.start(2) + me.end()
        # 代码块末尾后面紧跟的就是换行（` ```\n- 家族...`）⇒ 在换行后插入整行
        nl = ins if t[ins:ins + 1] == '\n' else t.find('\n', ins)
        if nl < 0:
            nl = ins
        pieces.append(t[last:nl + 1])
        pieces.append(sign_line(v))
        last = nl + 1
    if not stats['added']:
        return stats, False
    pieces.append(t[last:])
    new_t = ''.join(pieces)
    if apply_ and new_t != t:
        io.open(path, 'w', encoding='utf-8').write(new_t)
    return stats, new_t != t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true', help='写盘（默认只 DRY-RUN）')
    a = ap.parse_args()
    smap = build_sign_map()
    print('=' * 96)
    print('回填「符号 sign」到各因子库明细块   模式: {}'.format('APPLY' if a.apply else 'DRY-RUN'))
    print('=' * 96)
    print('  facs/ 里有 sign 的因子: {} 个'.format(len(smap)))
    files = sorted(glob.glob(os.path.join(DOCS, 'factor_library*.md')))
    tot = dict(blocks=0, added=0, matched=0, missing=0, already=0)
    for p in files:
        st, changed = patch_file(p, smap, a.apply)
        for k in tot:
            tot[k] += st[k]
        print('  {:<34s} 明细块 {:>3d} · 新增 sign {:>3d}（匹配 {:>3d} / 未落地 {:>3d}）'
              ' · 已有 {:>3d}{}'.format(
                  os.path.basename(p), st['blocks'], st['added'],
                  st['matched'], st['missing'], st['already'],
                  '  → 已写盘' if (a.apply and changed) else
                  ('  （无改动）' if not changed else '  [DRY]')))
    print()
    print('  合计: 明细块 {} · 新增 {} · 匹配 {} / 未落地 {} · 原有 {}'.format(
        tot['blocks'], tot['added'], tot['matched'], tot['missing'], tot['already']))
    if not a.apply:
        print('\n  （DRY-RUN：未写盘。确认后加 --apply）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
