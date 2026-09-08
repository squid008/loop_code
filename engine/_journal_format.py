# -*- coding: utf-8 -*-
"""loop_journal.md 指标表格式统一工具(幂等)。

目标格式 = 标准 markdown 横排表格三行式:
    | n_l1 | ic_med | ... |
    | ---  | ---    | ... |
    | 28   | 0.052  | ... |
渲染器(GitHub/IDE预览)会把它渲染成横向、列宽自动对齐的表格。

能处理的遗留状态:
  1. 历史竖表(| 指标 | 值 | ...) -> 转成三行横排表格
  2. 缺分隔行的两行式(键行+值行) -> 自动补一行分隔行升级为表格
  3. 已是标准三行表格 -> 幂等不动
旧进程(内存中旧代码)写出的竖表/两行式块, 下一次调用时会被自动清理。
"""
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
JOURNAL = os.path.join(os.path.dirname(HERE), 'docs', 'loop_journal.md')

KEY_ROW_HEAD = '| n_l1 |'       # 横排表格键行的首列(用于识别)
VERT_HEADER = '| 指标 | 值 |'   # 竖表表头
SEP_RE = re.compile(r'^\|[\s:\-|]+\|$')  # markdown 表格分隔行


def _cells(line):
    s = line.strip()
    if not (s.startswith('|') and s.endswith('|')):
        return None
    return [c.strip() for c in s[1:-1].split('|')]


def _sep_row(n):
    return '| ' + ' | '.join(['---'] * n) + ' |'


def convert(text):
    lines = text.split('\n')
    out = []
    i = 0
    n = 0
    while i < len(lines):
        s = lines[i].strip()

        # 1) 历史遗留竖表 -> 三行横排表格
        if s == VERT_HEADER:
            i += 2  # 跳过 "| 指标 | 值 |" 与其分隔行
            keys, vals = [], []
            while i < len(lines):
                m = re.match(r'^\| (\w+) \| (.*) \|$', lines[i].strip())
                if not m:
                    break
                keys.append(m.group(1))
                vals.append(m.group(2))
                i += 1
            if keys:
                out.append('| ' + ' | '.join(keys) + ' |')
                out.append(_sep_row(len(keys)))
                out.append('| ' + ' | '.join(vals) + ' |')
                n += 1
            continue

        # 2) 缺分隔行的两行式(键行后紧跟值行) -> 补分隔行
        if s.startswith(KEY_ROW_HEAD) and i + 1 < len(lines):
            keys = _cells(lines[i])
            nxt = lines[i + 1].strip()
            is_sep = bool(SEP_RE.fullmatch(nxt))
            if keys and nxt.startswith('|') and not is_sep:
                out.append(lines[i])
                out.append(_sep_row(len(keys)))
                i += 1
                n += 1
                continue

        # 3) 其余(含已是标准表格的行)原样保留
        out.append(lines[i])
        i += 1
    return '\n'.join(out), n


if __name__ == '__main__':
    with open(JOURNAL, encoding='utf-8') as f:
        text = f.read()
    new_text, n = convert(text)
    if n:
        with open(JOURNAL, 'w', encoding='utf-8') as f:
            f.write(new_text)
    print(f'formatted {n} metric tables -> standard md table ({JOURNAL})')
