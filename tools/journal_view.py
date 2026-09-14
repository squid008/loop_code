# -*- coding: utf-8 -*-
"""journal_view.py — 倒序查看 `docs/loop_journal*.md`（**不改引擎写入方式**）

## 为什么用"另做查看器"而不是把 journal 本体改成倒序（2026-09-14 判断）

用户提出「journal 要不要改成倒序（最新在前）」。评估后**不改本体**，三条理由：

1. ★★ **会毁掉追加的原子性**：引擎现在是 `open(path,'a')` **追加**（4 处：`loop_engine.py:2554/2567`、
   `loop_critic.py:475/645`）。POSIX/NTFS 的追加是**原子**的 ⇒ 崩溃最多丢**最后一段**。
   改成"倒序"就必须 **读全文 → 插入 → 重写全文**（`loop_journal.md` 已 **158 KB / 2782 行**）
   ⇒ 崩溃可能**毁掉整份 journal**。**用可靠性换阅读便利，是净负收益。**
2. ★ **journal 被当作"进度标记"**：`run_tracks.py:88` 与 `loop_watch.py:107` 都靠
   `re.findall(r'^##\\s*第\\s*(\\d+)\\s*代')` + **`max(gens)`** 判断"下一个该跑哪代"。
   虽然它们用 `max()`（**顺序无关** ✓），但 `loop_status.py:85` 用的是 **`gens[-1]`（依赖顺序）** ⇒ 要一起改。
3. **收益可以用零风险方式拿到** —— 即本脚本。

## 用法

    python tools/journal_view.py                      # 默认 pool=all，倒序看最近 3 代
    python tools/journal_view.py --pool=1000 --tail 5 # 中证1000 池最近 5 代
    python tools/journal_view.py --index              # 只要倒序目录（一代一行）
    python tools/journal_view.py --grep 拦截          # 全池范围内 grep（默认倒序）
    python tools/journal_view.py --pool=all --grep r5_calmar_cross --index

⚠ 若哪天确实要把 journal 本体改成倒序：**必须先停掉所有引擎/轨道**
  （代间写入方式突变会让 journal 结构不一致），并同步修 `loop_status.py:85` 的 `gens[-1]`。
"""
import io
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
DOCS = os.path.join(os.path.dirname(HERE), 'docs')


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
            pass
    return raw.decode('utf-8', errors='replace')


def split_gens(txt):
    """把 journal 拆成 `[(gen, body, 行号), ...]`（**保持文件原序**）。"""
    lines = txt.splitlines()
    marks = []
    for i, l in enumerate(lines):
        m = re.match(r'^##\s*第\s*(\d+)\s*代', l)
        if m:
            marks.append((i, int(m.group(1))))
    out = []
    for k, (i, g) in enumerate(marks):
        end = marks[k + 1][0] if k + 1 < len(marks) else len(lines)
        out.append((g, lines[i:end], i + 1))
    return lines, out


def pools_arg(s):
    return [x.strip() for x in s.split(',') if x.strip()]


def _digest(body):
    """取该代的一行摘要：优先 `**B角建议(下一代策略)**` 下的第一条 bullet。

    ⚠ 格式在两代间变过（2026-09-14 之前无 `【动作ID】` 前缀）⇒ 不能只匹配 `- 【`。
    """
    lines = list(body)
    for i, l in enumerate(lines):
        if 'B角建议' in l:
            for j in range(i + 1, min(i + 8, len(lines))):
                s = lines[j].strip()
                if s.startswith('-'):
                    return s.lstrip('- ').strip()
                if s.startswith('```'):
                    break
    # 兜底：该代的入库数 / 通过数
    for l in lines:
        if l.strip().startswith('|') and re.match(r'^\|[\s\-|:]+\|$', l.strip()):
            continue
        if l.strip().startswith('| ') and 'n_pass' not in l:
            v = [x.strip() for x in l.strip().strip('|').split('|')]
            if len(v) > 11:
                return 'n_l2={} n_pass={} fail_calmar={}'.format(v[9], v[10], v[12])
            break
    return ''


def main():
    a = sys.argv[1:]
    pool = 'all'
    tail = 3
    idx_only = False
    grep = None
    for x in a:
        if x.startswith('--pool='):
            pool = x.split('=', 1)[1]
        elif x.startswith('--tail='):
            tail = int(x.split('=', 1)[1])
        elif x.startswith('--grep='):
            grep = x.split('=', 1)[1]
        elif x == '--index':
            idx_only = True
        elif x == '--grep':
            grep = '__NEXT__'
        elif grep == '__NEXT__':
            grep = x
        elif not x.startswith('-'):
            pool = x
    if grep == '__NEXT__':
        grep = None

    total = 0
    for p in pools_arg(pool):
        jp = os.path.join(DOCS, 'loop_journal{}.md'.format('' if p == 'all' else '_' + p))
        txt = read_text(jp)
        if not txt:
            print('## pool={}  （无 journal）'.format(p))
            print()
            continue
        lines, gens = split_gens(txt)
        if not gens:
            print('## pool={}  （无代）'.format(p))
            print()
            continue

        if grep:
            # ---- grep 模式：全池倒序扫描，命中行带代数 + 行号 ----
            print('=' * 100)
            print('pool={}  grep="{}"  （全 {} 代，倒序）'.format(p, grep, len(gens)))
            print('=' * 100)
            n = 0
            for g, body, ln in reversed(gens):
                for k, l in enumerate(body):
                    if grep in l:
                        print('  [gen{} L{}] {}'.format(g, ln + k, l.strip()[:150]))
                        n += 1
            print('  —— 命中 {} 行'.format(n))
            print()
            total += n
            continue

        if idx_only:
            # ---- 索引模式：一代一行（倒序）----
            print('## pool={}  （{} 代，倒序）'.format(p, len(gens)))
            for g, body, ln in reversed(gens):
                print('  gen{:<4d} L{:<6d} {}'.format(g, ln, _digest(body)[:108]))
            print()
            total += len(gens)
            continue

        # ---- tail 模式：倒序看最近 N 代全文 ----
        print('=' * 100)
        print('pool={}  —— 共 {} 代，倒序显示最近 **{}** 代（最新在前）'.format(p, len(gens), tail))
        print('=' * 100)
        for g, body, ln in list(reversed(gens))[:tail]:
            print('\n'.join(body))
            print()
        total += min(tail, len(gens))

    print('（共 {} 代/行 · 源文件 docs/loop_journal*.md 本身仍是**正序追加**）'.format(total))
    return 0


if __name__ == '__main__':
    sys.exit(main())
