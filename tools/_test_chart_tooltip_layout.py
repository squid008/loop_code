# -*- coding: utf-8 -*-
"""★★★★ 曲线图「悬停浮标」的**排版几何守门**（2026-09-21 新增 · 两次目测失误驱动 ✗）

★ 为什么需要（用户两次看图反馈）：
  ① "字都叠一块儿了" ✗ —— 列宽**写死 84px**，长标签（组合（Top10% 等权））压到数值上 ✓
  ② "日期跟下面的文字还是叠起来了" ✗ —— **行高给太紧**：日期基线 `by+11`、第一行 `by+17`
     只差 **6px**，而字号 **9px**（一行要 ~11px 行距）⇒ 必然叠 ✓

⇒ 本守门**从源码抠出真实常量**再断言"间距够不够"（不是照抄一份公式 ✗）：
  · 日期基线到第一行基线的间隔 ≥ 11px（字号 9 ⇒ 一行至少 11px ✓）
  · 行距 ≥ 字号 + 2 ✓
  · 盒高必须装得下最后一行（含字降部）✓
  · 列宽**不许写死** ✗（必须有按文字宽度自适应的实现 ✓）
  · 悬停四件套在位（十字准线 / 锚点圆点 / 半透明底 / 不抢鼠标 ✓）
"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ROOT, 'dashboard', 'web', 'src', 'App.tsx')
FAIL = []


def chk(desc, cond, hint=''):
    print('  %s %s' % ('✓' if cond else '✗', desc))
    if not cond:
        FAIL.append(desc + ('（%s）' % hint if hint else ''))


src = io.open(APP, encoding='utf-8').read()

print('【1】常量：从源码抠出来的排版参数（不是照抄一份 ✗）')
m = re.search(r'const ROW = (\d+), PX = (\d+), HEAD = (\d+), PY = (\d+)', src)
chk('找到浮标排版常量（ROW/PX/HEAD/PY）', m is not None)
if not m:
    print('\n✗ 常量都没找到 ⇒ 后面没法判 ✓')
    sys.exit(1)
ROW, PX, HEAD, PY = (int(x) for x in m.groups())
print('    ROW=%d · PX=%d · HEAD=%d · PY=%d' % (ROW, PX, HEAD, PY))

m_f = re.search(r'const ty = by \+ (\w+) \+ ri \* (\w+)', src)
chk('第一行基线的表达式是 `by + HEAD + ri*ROW`（口径明确 ✓）',
    m_f is not None and m_f.group(1) == 'HEAD' and m_f.group(2) == 'ROW')

m_d = re.search(r'y=\{by \+ (\d+)\} fontSize="(\d+)"[^>]*>\{dLab', src)
chk('找到日期那行的 y 与字号', m_d is not None)
DATE_Y, FONT = (int(m_d.group(1)), int(m_d.group(2))) if m_d else (0, 0)
print('    日期基线 = by + %d · 工具字号 = %dpx' % (DATE_Y, FONT))

print('\n【2】间距断言（这就是那两次翻车的地方 ✗）')
chk('日期 → 第一行 的基线间隔 ≥ 字号+2（实 %dpx）' % (HEAD - DATE_Y),
    (HEAD - DATE_Y) >= FONT + 2,
    '字叠字就是这么来的 ✗（上一版只有 6px）')
chk('行距 ROW ≥ 字号+2（实 %dpx）' % ROW, ROW >= FONT + 2, '行与行会挤在一起 ✗')
chk('日期文字顶部不出盒（by+%d - 字高 ≈ %d ≥ 1）' % (DATE_Y, DATE_Y - FONT),
    DATE_Y - FONT >= 1, '日期会顶到盒子上边 ✗')
m_b = re.search(r'const bh = HEAD \+ Math\.max\(per - 1, 0\) \* ROW \+ (\d+) \+ PY', src)
chk('盒高公式含"末行基线 + 字降部 + 下边距"', m_b is not None)
if m_b:
    desc = int(m_b.group(1))
    ok = []
    for per in (1, 2, 3, 5, 8):
        last = HEAD + max(per - 1, 0) * ROW + desc          # 末行文字底部 ✓
        bh = HEAD + max(per - 1, 0) * ROW + desc + PY       # 盒高 ✓
        ok.append(last + 1 <= bh)
    chk('1 / 2 / 3 / 5 / 8 行时末行都装得下（留 %dpx 下边距 ✓）' % PY, all(ok))

print('\n【3】列宽必须**自适应**（第一次翻车：写死 84px ✗）')
chk('有按文字宽度估算的实现（CJK/ASCII 分别算宽 ✓）',
    re.search(r'charCodeAt\(0\) > 0x2e80 \? [\d.]+ : [\d.]+', src) is not None)
chk('列宽由**逐列计算**得出（不是常量 ✗）',
    re.search(r'const cs = Array\.from\(\{ length: cl \}', src) is not None
    and re.search(r'CWs = L\.cs', src) is not None)
chk('每列宽度用了"点 + 标签 + 间隔 + 数值"四项之和',
    re.search(r'9 \+ tw\(nm\[k\]\) \+ \d+ \+ tw\(vt\[k\]\)', src) is not None)
chk('列宽有上限（不至于撑满整张图 ✓）', re.search(r'Math\.min\(w \+ 1, \d+\)', src) is not None)
chk('长标签**智能缩短**：只去尾部括号解释（不无条件截断 ✓）',
    ('stripParen' in src) and ('[（(][^）)]*[）)]' in src))
chk('缩短后**重名会退回全长**（绝不含糊 ✓）', 'new Set(baseL).size === baseL.length' in src)
chk('★★ **只有真的放不下才截断** ✗（用户："RankIC 累计这里咋还有省略号"）',
    ('MAXW' in src) and re.search(r's\.length > cutN \? s\.slice\(0, cutN\)', src) is not None
    and 't.length > 9 ? t.slice(0, 9)' not in src)
chk('排版有**回退链**：先两列 → 超宽退单列 → 还超宽才逐级截断 ✓',
    all(x in src for x in ('let L = mk(rows.length > 4 ? 2 : 1, 0)',
                           'if (L.wd > MAXW) L = mk(1, 0)',
                           'for (const nn of [16, 12, 10, 8, 6])')))
chk('数值精度：悬停值至少两位小数（`hvFmt` ✓）',
    ('hvFmt' in src) and ('v.toFixed(2)' in src))

print('\n【4】悬停四件套在位（整块功能别被后来改动删掉 ✗）')
chk('十字准线（随鼠标走的竖虚线 ✓）', re.search(r'<line x1=\{hx\} y1=\{PT\}', src) is not None)
chk('每条可见曲线的**锚点圆点** ✓（`cx={hx} cy={Y(值)}` + 独立 key `hd…` ✓）',
    ('cx={hx} cy={Y(r.v as number)}' in src) and ('`hd${k}`' in src))
chk('半透明底（后面曲线能透出来 ✓）', "fill=\"rgba(12,18,34,0.82)\"" in src)
chk('不抢鼠标（pointerEvents none ✓）', 'pointerEvents="none"' in src)
chk('透明捕获面（空处也响应 ✓）', 'fill="transparent"' in src)
chk('移开就收起（onMouseLeave ✓）', 'onMouseLeave={() => setHov(null)}' in src)

print('\n【5】两列的区分度（用户："左列数值离右边圆点太近，还以为是右边的数据"✗）')
m_g = re.search(r'GAP = (\d+)', src)
chk('有列间距 GAP 且 ≥ 12px（实 %s）' % (m_g.group(1) if m_g else '—'),
    m_g is not None and int(m_g.group(1)) >= 12, '两列贴在一起就会被误读 ✗')
chk('列位置把 GAP 算进去了（`+ ci * GAP` ✓）', re.search(r'\+ ci \* GAP', src) is not None)
chk('盒宽也把列间距算进去了（`(cl - 1) * GAP` ✓）',
    re.search(r'\(cl - 1\) \* GAP', src) is not None)
chk('多列时有**淡分隔线**（一眼分清哪列 ✓）', '`sep${i}`' in src)

print('\n【6】百分比格式器必须**两位小数**（用户："只有 -1%，应该是 -1.03%"✗）')
pcts = re.findall(r'\$\{\(v \* 100\)\.toFixed\((\d+)\)\}%', src)
chk('所有 ×100 的百分比格式器都是 2 位小数（实 %s）' % pcts,
    bool(pcts) and set(pcts) == {'2'}, '0 位 / 1 位都会把小数丢掉 ✗')
chk('回撤图接的是 `pctf`（同一处控制 ✓）', 'yFmt={pctf}' in src)

print('\n' + ('★ 全过 ✓ 悬停浮标的排版/列宽/精度/列间距/交互都合规' if not FAIL
             else '✗ 有 %d 项没过：\n  - %s' % (len(FAIL), '\n  - '.join(FAIL))))
sys.exit(1 if FAIL else 0)
