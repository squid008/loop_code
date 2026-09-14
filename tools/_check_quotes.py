# -*- coding: utf-8 -*-
"""_check_quotes.py — 【早期预警，非权威】扫描「中文里用了 ASCII 双引号」的写法。

★★ 先说结论：**权威判据永远是 `py_compile`** —— 它一次都没漏过。
   本脚本只是**提前提示**，因为启发式规则做不到零假阳性。

背景（2026-09-13 实录）：我一天内在 Python 里写中文时**四次**误用 ASCII 双引号
（如 `"超额"`）导致 `SyntaxError`。三次不同的启发式判据都不够好：

| 判据 | 结果 |
|---|---|
| 引号个数为奇数 | ❌ **漏掉** 4 个引号的那行（`("> … 的"超额"主要 … ⇒ "`）—— 配对看着平衡，语法照样错 |
| 引号**单侧**紧邻汉字 | ❌ **166 处假阳性** —— `f"面板 {n} 日 x {n} 股"` 的**合法收尾引号**右侧就是汉字 |
| 引号**两侧**都是汉字 | 🟡 好多了，但仍会对**单引号外层**的字符串假阳性（`f'…从"低换手"…'` 语法本来没问题） |

⇒ 最终取值：**两侧都是汉字 + 跳过含单引号的行 + 跳过整行注释**（把假阳性压到很低）。

★ 教训（比脚本本身重要）：**当存在权威判据时，不要用启发式去替代它** ——
  启发式只能当预警，且**必须说清它的假阳性来源**，否则会浪费时间去删无害的告警。

用法: python tools/_check_quotes.py <file.py> [more.py ...]
      python tools/_check_quotes.py --all   (扫描本项目主要 .py)
"""
import io
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

CJK = re.compile(r'[\u4e00-\u9fff]')   # ⚠ 只收**汉字** —— 含全角标点(（）「」等)会假阳性


def scan(path):
    hits = []
    try:
        ls = io.open(path, encoding='utf-8', errors='replace').read().splitlines()
    except Exception as e:
        return [(-1, f'读失败 {type(e).__name__}: {e}')]
    in3 = False                       # 是否在三引号块内
    for i, l in enumerate(ls, 1):
        n3 = l.count('"""')
        if n3:
            in3 = not in3 if n3 % 2 else in3
            continue
        if in3:
            continue                  # docstring 内不判
        if l.lstrip().startswith('#') or "'" in l:
            continue                  # 整行注释 / 含单引号的行 -> 跳过(否则大量假阳性)
        code = l.rstrip()
        for j, ch in enumerate(code):
            if ch != '"':
                continue
            # ⚠ 判据必须是「**两侧都是汉字**」：
            #   中文里的内嵌引号(把"超额"主要)两侧都是汉字；
            #   而**合法**收尾引号(...股" / ...）")右侧一定不是汉字
            #   ⇒ 用"单侧相邻"会得到 166 处假阳性(实测), 用"两侧都是"才精确。
            before = code[j - 1] if j else ''
            after = code[j + 1] if j + 1 < len(code) else ''
            if CJK.search(before or '') and CJK.search(after or ''):
                hits.append((i, l.strip()[:110]))
                break
    return hits


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 2
    if args == ['--all']:
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        args = []
        for sub in ('engine', 'ai_test', 'standard'):
            d = os.path.join(root, sub)
            if os.path.isdir(d):
                args += [os.path.join(d, f) for f in sorted(os.listdir(d))
                         if f.endswith('.py')]
    bad = 0
    for p in args:
        h = scan(p)
        if h:
            bad += len(h)
            print(f"[!] {p}  —— {len(h)} 行可疑")
            for ln, txt in h:
                print(f"      {ln}: {txt}")
        else:
            print(f"[OK] {p}")
    print()
    print("结论: " + ("发现 %d 处「ASCII 引号紧邻中文」" % bad if bad
                     else "全部干净 ✓"))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
