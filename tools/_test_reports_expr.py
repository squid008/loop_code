# -*- coding: utf-8 -*-
"""_test_reports_expr.py — 报告里的**因子表达式必须完整**（回归测试）

## 为什么有这条测试（用户 2026-09-14 反馈）

用户原话：
> 「factor_pool_selected.md 里，我看几个精选因子的表达式好像都被截断了嘛…
>   这个不行啊，我肯定要完整表达式啊，**不然我还得费劲去找对应的因子库去翻表达式**」

根因：`cross_pool_review.py` 生成精选清单时写了 `meta[n]['expr'][:58]`（硬截断），
而 **`factor_pool_selected.md` 是"只有一个表格、没有明细段"的文件** ——
对比 `factor_library*.md` 是「**总览（截断 + `…`）+ 明细（全文）**」两层，
所以它**截了就真没了** ✗

## ★ 本测试编码的规则（区分"可以省略"与"不可以省略"）

| 文件类型 | 允许省略? | 理由 |
|---|---|---|
| 有**明细段**的（`factor_library*.md`：总览 + 每因子一节）| ✅ 总览可省略 | 全文在明细段，**查得到** |
| **没有明细段**的（`factor_pool_selected.md`）| ❌ **绝对不许** | 截了就**无处可查** → 用户被迫去翻别的文件 |

⇒ 所以断言分两层：
1. **通用契约**：任何**被反引号包裹**的表达式，**括号必须配平**
   （合法表达式括号必配平 ⇒ 不配平 = 被切了；比"按长度猜"可靠）
2. **精确针对根因**：**没有明细节的文件里，代码段中不许出现 `…`/`...` 省略号**，
   且精选池必须给 `sign`（**方向**，不乘它因子就是反的）和 h5 路径

## ⚠ 已知盲区（诚实说明）

**不加反引号**的截断（如 `factor_library*.md` 总览表里的 `div(ts_min100(corr100(overnight, ts_std60…`）
本测试**抓不到** —— 那是**有意的**：它是导航用的总览，全文在明细段 ✓
（若要连它一起禁，请先给 `factor_library*.md` 补别的导航方式。）

用法: python tools/_test_reports_expr.py
"""
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
OK = [0, 0]

# 反引号包裹的、以叶子/函数名开头的候选表达式
RX = re.compile(r'`([a-z_][a-z_0-9]*(?:\([^`\n]*)?)`')
RX_FENCE = re.compile(r'```[a-z]*\n([^\n]+)\n```')
# 明细块（`### F07 · gen11 入库` -> 正文）
RX_BLOCK = re.compile(r'^###\s*(F\d+)\s*·[^\n]*\n(.*?)(?=^###\s|\n## |\Z)', re.M | re.S)
# `sign` 行的**宽松**标记（两种形态都覆盖：有值 / 未记录）
SIGN_MARK = '符号 `sign`：'


def chk(cond, msg):
    OK[0] += 1
    if not cond:
        OK[1] += 1
    print('  [{}] {}'.format('OK ' if cond else 'FAIL', msg))


def bal(s):
    return s.count('(') - s.count(')')


def main():
    print('=' * 96)
    print('报告表达式完整性 回归测试')
    print('=' * 96)

    files = sorted(glob.glob(os.path.join(ROOT, 'docs', '*.md'))) + \
        [os.path.join(ROOT, 'README.md')]

    print('\n[1] 通用契约：**反引号包裹的表达式**括号必须配平（= 没被截断）')
    for p in files:
        t = io.open(p, encoding='utf-8', errors='replace').read()
        cand = [m.group(1) for m in RX.finditer(t) if '(' in m.group(1)]
        if not cand:
            continue
        bad = [s for s in cand if bal(s) != 0]
        name = os.path.relpath(p, ROOT).replace('\\', '/')
        chk(not bad, '{}（{} 个表达式，最长 {}）{}'.format(
            name, len(cand), max(len(s) for s in cand),
            '' if not bad else '  ✗ 截断 {} 个: {}'.format(len(bad), bad[0][:60])))

    print('\n[2] 代码块里的表达式也必须配平（明细段的全文）')
    for p in files:
        t = io.open(p, encoding='utf-8', errors='replace').read()
        cand = [m.group(1).strip() for m in RX_FENCE.finditer(t)]
        cand = [s for s in cand if '(' in s]
        if not cand:
            continue
        bad = [s for s in cand if bal(s) != 0]
        chk(not bad, '{}（{} 个代码块表达式）{}'.format(
            os.path.relpath(p, ROOT).replace('\\', '/'), len(cand),
            '' if not bad else '  ✗ {}'.format(bad[0][:60])))

    print('\n[3] ★★ 精确针对本次根因：**没有明细段的文件**不许有省略号')
    for name, must_have_sign in (('docs/factor_pool_selected.md', True),):
        p = os.path.join(ROOT, name)
        if not os.path.exists(p):
            print('    （{} 不存在，跳过）'.format(name))
            continue
        t = io.open(p, encoding='utf-8', errors='replace').read()
        chk(t.count('…') == 0 and '___' not in t,
            '{} 里 **0 个 `…` 省略号**（实得 {} 个）—— 该文件没有明细段，'
            '截了就无处可查'.format(name, t.count('…')))
        chk('## 精选因子明细' in t or '明细' in t, '{} 有明细段（全文可复制）'.format(name))
        if must_have_sign:
            chk('sign' in t and '必须乘' in t,
                '{} 给出 `sign`（**方向**）—— 不乘它因子值是反的'.format(name))
            chk('facs/' in t, '{} 给出因子值 h5 路径（下游不用再找）'.format(name))

    print('\n[5] ★★ `sign`（**方向**）必须出现在所有"给人挑因子"的报告里（§1.23）')
    # 为什么：引擎求值时对 sign<0 的候选**取负**；下游直接排序选股不乘 sign
    # ⇒ **方向反了、组合反向选股** ✗（精选池实测 7 个里 6 个 sign=-1）
    for p in sorted(glob.glob(os.path.join(ROOT, 'docs', 'factor_library*.md'))):
        t = io.open(p, encoding='utf-8', errors='replace').read()
        blocks = RX_BLOCK.findall(t)
        if not blocks:
            continue
        n_s = sum(1 for _, b in blocks if SIGN_MARK in b)
        dup = sum(1 for _, b in blocks if b.count(SIGN_MARK) > 1)
        chk(n_s == len(blocks) and dup == 0,
            '{}：**每个明细块**都有 `sign`（{}/{}）且无重复 —— 缺的下游会反向选股'.format(
                os.path.relpath(p, ROOT).replace('\\', '/'), n_s, len(blocks)))
    p = os.path.join(ROOT, 'docs', 'factor_library_crosspool.md')
    if os.path.exists(p):
        t = io.open(p, encoding='utf-8', errors='replace').read()
        chk('**`sign`**' in t, 'crosspool 视图的**表头含 `sign` 列**')
        chk(t.count('未记录') >= 0 and '不臆造' in t, 'crosspool 说明里声明「缺失不臆造」')
    src_le = io.open(os.path.join(ROOT, 'engine', 'loop_engine.py'),
                     encoding='utf-8').read()
    chk('符号 `sign`' in src_le or '符号 \\`sign\\`' in src_le,
        '★ `loop_engine._lib_sync` 会给**新入库**因子写 `sign` 行（+ 不改表格列）')

    print('\n[4] 生成器源码里不许有"表达式截断"（防止再手滑加回去）')
    src = io.open(os.path.join(ROOT, 'tools', 'cross_pool_review.py'),
                  encoding='utf-8').read()
    # 只看"写进 md"的那条 L.append —— 控制台那处允许截断（有正当理由）
    md_zone = src[max(0, src.find('## 精选清单')):]
    md_zone = md_zone[:max(1, md_zone.find('被淘汰'))] if '被淘汰' in md_zone else md_zone
    hits = re.findall(r"expr'?\]\[:(\d+)\]", md_zone)
    chk(not hits, '★ 写进 md 的表达式**没有** `[:N]` 硬截断（实得 {}）'.format(hits))
    chk('_cell(' in src, '表格单元格转义 `|`（防静默切断）')

    print('\n' + '=' * 96)
    print('通过 {}/{}'.format(OK[0] - OK[1], OK[0]) + ('' if OK[1] else '  ✓ 全部通过'))
    return 1 if OK[1] else 0


if __name__ == '__main__':
    sys.exit(main())
