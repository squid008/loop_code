# -*- coding: utf-8 -*-
"""scan_non_gbk.py — 找出源码里**逐字符无法用 GBK 编码**的位置

为什么要它：中文 Windows 控制台/重定向默认 GBK。引擎若 `print()` 出 GBK 编不出的字符
（如 [OK] ⇒ ⚠ 之外的符号），轻则 `--help` 崩，**重则无人值守跑到一半直接抛 UnicodeEncodeError 中断**。
（2026-09-12 实录：`--help` 因 `69%**` 的 `%*` 和 `[OK]` 两次崩掉。）

用法：python tools/scan_non_gbk.py [文件...]（默认扫 engine/*.py + standard/*.py）
"""
import io
import os
import sys

try:
    sys.stdout.reconfigure(errors='replace')
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def _safe_lines(src):
    """返回"不会被 print 出去"的行号集合：
      · 整行注释（lstrip 后以 # 开头）
      · 位于三引号块内（docstring）—— 引擎从不 print docstring（只 `--help` 打 argparse 的 help 串）
    仍在 `print(...)` / `help='...'` 里的字符才是真风险，故只报告这些。
    """
    safe = set()
    in_tri = False
    for ln, line in enumerate(src.splitlines(), 1):
        stripped = line.lstrip()
        if in_tri or stripped.startswith('#'):
            safe.add(ln)
        # 三引号开关（简单计数，够用：本项目无双引号内含三引号的花式写法）
        n = line.count('"""') + line.count("'''")
        if n % 2 == 1:
            in_tri = not in_tri
    return safe


def scan(path):
    """返回 [(行号, 列, 字符, 十六进制, 是否安全)]；安全 = 注释或 docstring 内。

    ⚠ 启发式，不是解析器：① 行尾 `#` 之后一律视为注释（若字符串里含 `#` 会漏报）；
      ② 三引号用奇偶计数判断。⇒ **本工具只作筛查，权威判定是实际运行**
      （引擎：`qa_engine_cli.py` 在 GBK 下跑 `--help`；脚本：真跑一次）。
    """
    out = []
    src = io.open(path, encoding='utf-8').read()
    safe_set = _safe_lines(src)
    for ln, line in enumerate(src.splitlines(), 1):
        in_doc = ln in safe_set
        hash_at = line.find('#')
        for col, ch in enumerate(line):
            try:
                ch.encode('gbk')
            except UnicodeEncodeError:
                safe = in_doc or (hash_at >= 0 and col > hash_at)
                out.append((ln, col + 1, ch, 'U+%04X' % ord(ch), safe))
    return out


def main():
    if len(sys.argv) > 1:
        files = sys.argv[1:]
    else:
        files = []
        for d in ('engine', 'standard'):
            p = os.path.join(ROOT, d)
            if os.path.isdir(p):
                files += [os.path.join(p, f) for f in sorted(os.listdir(p))
                          if f.endswith('.py')]
    total_bad = 0
    for f in files:
        try:
            hits = scan(f)
        except Exception as e:
            print(f"{f}: 读取失败 {e}")
            continue
        # 注释里的是安全的（不会 print）；只报告"非注释行"的
        risky = [h for h in hits if not h[4]]
        safe = [h for h in hits if h[4]]
        rel = os.path.relpath(f, ROOT)
        if not hits:
            continue
        print(f"\n=== {rel} === 真风险(print/help 文本) {len(risky)} / 安全(注释+docstring) {len(safe)}")
        # 按字符汇总，便于一次看清
        from collections import Counter
        cnt = Counter(f"{h[2]} {h[3]}" for h in risky)
        for k, v in cnt.most_common():
            print(f"   {k}  × {v}")
        for h in risky[:20]:
            print(f"     行 {h[0]} 列 {h[1]}")
        total_bad += len(risky)
    print(f"\n{'=' * 56}\n真风险(会被 print/--help 输出的)非 GBK 字符总数: {total_bad}")
    print("(这些位置一旦被 print 到 GBK 控制台就会抛 UnicodeEncodeError；"
          "注释/docstring 已排除)")
    return 0 if total_bad == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
