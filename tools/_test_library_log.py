# -*- coding: utf-8 -*-
"""_test_library_log.py — 「新入库日志」守门（用户 2026-09-17 要求）

## 用户要求（原话）
「我发现好像又入库了一个新因子，但是我**找不到什么时候入库的、入的哪个库**，要不池运行状态在上证50池
右边再加一个一样大小的卡片，记录新入库因子的挖掘时间日志吧，**带 Y 轴滚动条的（不要 X 轴滚动条哈）**，
可以查看**最近 50 条**信息，然后**右边也加详情按钮**我可以直接点开看」

## 本测试钉住什么（每条都对应一种"会骗人/会难用"的真实故障）
1. **数据源存在且格式正确**：`docs/library_entries.jsonl`（append-only，**进 git** ⇒ 换机器也看得到）
2. ★★ **时间诚实性**（最容易出问题的一条）：
   · `ts` 非空 ⇒ **必须**有 `tsSource` 说明来路（`engine` 真实时间 / `gen_log` / `md_mtime` 推算）
   · `tsSource='unknown'` ⇒ `ts` **必须是空**（没证据就留空，**绝不编一个** ✗）
3. **幂等**：`(pool, code|expr)` 不重复 —— 否则同一因子会在日志里出现多次 ✗
4. ★★ **回填不许覆盖真实记录**：`source='engine'` 的行是引擎写的**真时间**，回填只能补缺 ✗
   （工具源码里那条 `keep = {... source == 'engine'}` 是这条性质的实现 ⇒ 静态钉住）
5. ★ **路由顺序**：`/api/library/entries` **必须声明在** `/api/library/{pool}` **之前** ——
   否则会被更宽的路径吃掉（`pool='entries'` ⇒ 404「未知池」）✗（写反过，所以钉住）
6. **前端交互**：卡在池状态区 · **只纵向滚动**（`overflow-y:auto` + `overflow-x:hidden`）·
   长文本省略号（`text-overflow:ellipsis`，否则会横向溢出 ✗）· 详情按钮接**同一个** `FactorDetail` ✓

用法: python tools/_test_library_log.py
"""
import io
import json
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
LOG = os.path.join(DOCS, 'library_entries.jsonl')
OK = [0, 0]
TS_SRC = ('engine', 'gen_log', 'md_mtime')


def chk(desc, cond, hint=''):
    OK[0] += 1
    if not cond:
        OK[1] += 1
    print('  [{}] {}{}'.format('OK ' if cond else 'FAIL', desc,
                               '' if cond else ('  ← ' + hint if hint else '')))


def main():
    print('=' * 96)
    print('新入库日志守门（docs/library_entries.jsonl + 接口 + 前端接线）')
    print('=' * 96)
    chk('事件日志存在（**进 git** 的 append-only JSONL）', os.path.exists(LOG),
        '跑 `python tools/backfill_library_entries.py` 生成历史的')
    if not os.path.exists(LOG):
        return 1
    evs, bad = [], 0
    for ln in io.open(LOG, encoding='utf-8'):
        ln = ln.strip()
        if not ln:
            continue
        try:
            evs.append(json.loads(ln))
        except Exception:
            bad += 1
    chk('每行都是合法 JSON（坏行 %d 个）' % bad, bad == 0)
    chk('条目数 > 0（实得 %d）' % len(evs), bool(evs))

    # ---- [1] 时间诚实性 ----
    print('\n[1] ★★ 时间诚实性（"编一个时间"比"空着"更糟 ✗）')
    no_src = [e for e in evs if e.get('ts') and not e.get('tsSource')]
    chk('有时间 ⇒ 必有 `tsSource`（说明来路；实得 %d 条没有）' % len(no_src), not no_src,
        str([(e.get('pool'), e.get('code')) for e in no_src[:3]]))
    bad_src = [e for e in evs if e.get('tsSource') not in TS_SRC + ('unknown',)]
    chk('`tsSource` 取值合法（engine / gen_log / md_mtime / unknown）', not bad_src,
        str([(e.get('pool'), e.get('tsSource')) for e in bad_src[:3]]))
    unk_ts = [e for e in evs if e.get('tsSource') == 'unknown' and e.get('ts')]
    chk('★★ `unknown` ⇒ `ts` **必须为空**（没证据不许编时间 ✗；实得 %d 条违规）' % len(unk_ts),
        not unk_ts, str([(e.get('pool'), e.get('code')) for e in unk_ts[:3]]))
    n_eng = sum(1 for e in evs if e.get('source') == 'engine')
    n_ts = sum(1 for e in evs if e.get('ts'))
    print('    统计: 有时间的 %d 条（其中 engine 真实记录 %d 条）· 时间未知 %d 条'
          % (n_ts, n_eng, len(evs) - n_ts))

    # ---- [2] 幂等 + 排序 ----
    print('\n[2] 幂等与排序（同一因子不许出现两次；文件按时间递增 ⇒ 取尾部就是"最近"✓）')
    keys = [(e.get('pool'), e.get('code') or e.get('expr')) for e in evs]
    chk('无重复 (池, 编号|公式)', len(keys) == len(set(keys)),
        '%d 条重复' % (len(keys) - len(set(keys))))
    known = [e['ts'] for e in evs if e.get('ts')]
    chk('有时间的那段**递增**（取尾部 = 最近 ✓）', known == sorted(known))
    head_unknown = all(not e.get('ts') for e in evs[:len(evs) - len(known)])
    chk('"时间未知"的排在**文件最前**（= 视作最旧 ⇒ 列表底部，不会挤掉最近的 ✓）', head_unknown)

    # ---- [3] 回填不许覆盖真实记录（静态钉住实现）----
    print('\n[3] ★★ 回填不许覆盖 engine 的真实记录')
    src = io.open(os.path.join(HERE, 'backfill_library_entries.py'), encoding='utf-8').read()
    chk("源码里显式保留 `source == 'engine'` 的行（`keep = {...}`）",
        re.search(r"keep = \{k: e for k, e in have\.items\(\) if e\.get\('source'\) == 'engine'\}",
                  src) is not None,
        '否则一次重跑就会把真时间抹掉 ✗')
    chk("派生行（backfill）**每次重算**（首版把 60 条算成同一时间，必须能自我纠正 ✓）",
        'have = keep' in src and 'md_mtime' in src and 'is_last_batch' in src)
    src_eng = io.open(os.path.join(ROOT, 'engine', 'loop_engine.py'), encoding='utf-8').read()
    chk('★ 引擎入库时**真的**写了这条日志（`append_library_entries` 在 `_lib_sync` 里被调用 ✓）',
        'def append_library_entries(' in src_eng
        and re.search(r'append_library_entries\(evs\)', src_eng) is not None)
    chk('入库日志**失败也只告警**（不许影响入库主流程 ✓ —— 与 `_lib_sync` 同一契约）',
        '不影响入库' in src_eng)

    # ---- [4] 路由顺序（写反过 ⇒ 钉住）----
    print('\n[4] ★ 路由顺序：`/api/library/entries` 必须在 `/api/library/{pool}` **之前**')
    mp = io.open(os.path.join(ROOT, 'dashboard', 'api', 'app', 'main.py'),
                 encoding='utf-8').read()
    i_e = mp.find("'/api/library/entries'")
    i_p = mp.find("'/api/library/{pool}'")
    chk('两条路由都在（entries %d · {pool} %d）' % (i_e, i_p), i_e > 0 and i_p > 0)
    chk('★★ entries 声明在 {pool} **之前**（否则被更宽路径吃掉 ⇒ 404 未知池 ✗）',
        0 < i_e < i_p)
    fp = io.open(os.path.join(ROOT, 'dashboard', 'api', 'app', 'sources', 'factors.py'),
                 encoding='utf-8').read()
    chk('后端实现 `library_entries()`（倒序取最近 N 条 + 补齐 detail/metrics ⇒ 复用详情弹层 ✓）',
        'def library_entries(' in fp and 'reversed(tail)' in fp)

    # ---- [5] 前端交互（用户明确要求的三条）----
    print('\n[5] 前端：只纵滚 + 长文本省略 + 详情按钮（用户原话逐条对）')
    css = io.open(os.path.join(ROOT, 'dashboard', 'web', 'src', 'styles.css'),
                  encoding='utf-8').read()
    src_tsx = io.open(os.path.join(ROOT, 'dashboard', 'web', 'src', 'App.tsx'),
                      encoding='utf-8').read()
    m = re.search(r'\.loglist \{([^}]*)\}', css)
    chk('`.loglist` 有**纵向**滚动（Y 轴 ✓）', bool(m) and 'overflow-y: auto' in m.group(1))
    chk('★ `.loglist` **禁止横向**滚动（用户："不要 X 轴滚动条哈"）',
        bool(m) and 'overflow-x: hidden' in m.group(1),
        '缺了它，长公式会把卡片撑出横向滚动条 ✗')
    m2 = re.search(r'\.logrow \.ls \{([^}]*)\}', css)
    chk('长文本一格：`nowrap` + `text-overflow: ellipsis` + `min-width: 0`（三件套缺一即溢出 ✗）',
        bool(m2) and all(x in m2.group(1) for x in
                         ('white-space: nowrap', 'text-overflow: ellipsis', 'min-width: 0')))
    chk('卡片与池卡**同款**（`className="card"` ⇒ 尺寸/边框一致 ✓）',
        'function EntryLogCard' in src_tsx and '<div className="card">' in src_tsx)
    chk('卡被渲染在**池状态区**（`section.cards` 内、池卡之后）',
        'EntryLogCard d={entries}' in src_tsx
        and src_tsx.find('<EntryLogCard') > src_tsx.find('<PoolCard'))
    chk('每行**右边**有「详情」按钮，且点开的是**同一个**详情组件（口径一致 ✓）',
        'onClick={() => onDetail(e)}>详情</button>' in src_tsx and 'entrySel &&' in src_tsx
        and '<FactorDetail f={{ code: entrySel.code' in src_tsx)
    chk('默认取**最近 50 条**（用户要求的条数 ✓）', 'api.libraryEntries(50)' in src_tsx)
    # ★★ 2026-09-17 用户追改三条：「年份也加上」「详情按钮不要贴着滚动条」「公式短一点没关系」
    chk('★ 时间**带年份**（`slice(0, 16)` = `2026-09-17 02:24`；不能再截成 `MM-DD HH:mm` ✗）',
        'e.ts.slice(0, 16)' in src_tsx and 'e.ts.slice(5, 16)' not in src_tsx,
        '用户原话："入库日志把年份也加上吧"')
    m3 = re.search(r'\.loglist \{([^}]*)\}', css)
    chk('★ 滚动条**不贴内容**：`.loglist` 有 `padding-right`（用户："详情按钮不要贴着滚动条"）',
        bool(m3) and 'padding-right' in m3.group(1),
        '不预留的话按钮会紧贴滚动条，看着挤 ✗')
    chk('★ `scrollbar-gutter: stable`（滚动条出现/消失时内容不左右跳 ✓）',
        bool(m3) and 'scrollbar-gutter: stable' in m3.group(1))
    # ⚠ 断言里**别把 CSS 的 `.` 前缀**带进 TSX 检查（TSX 里是 `className="logr1"`）✗ —— 实测踩到
    chk('行改为**两行式**（时间/池/编号/详情 一行 · 公式另一行整行宽 ⇒ 公式不再被挤没 ✓）',
        'className="logr1"' in src_tsx
        and re.search(r'\.logrow \{[^}]*flex-direction: column', css) is not None
        and re.search(r'\.logr1 \{', css) is not None,
        '一行里塞 年份+池+编号+按钮 ⇒ 公式只剩十几像素（用户允诺"公式可以短一点"= 让位 ✓）')
    chk('详情按钮**靠右**（`margin-left: auto`）且公式那行**跨整行**',
        re.search(r'\.logrow \.btn\.sm \{[^}]*margin-left: auto', css) is not None)

    # ---- [6] ★★ 收尾管线必须把"入库之后的数据"也补齐（否则看板全是 —，用户以为出错）----
    print('\n[6] ★★ 收尾管线：新入库后 指标表/曲线 要自动跟上')
    rt = io.open(os.path.join(ROOT, 'tools', 'run_tracks.py'), encoding='utf-8').read()
    chk('★ 收尾跑 `factor_metrics.py --only-new`（否则详情页"超额年化"等全是 — ✗）',
        "tools/factor_metrics.py', '--only-new'" in rt,
        '用户实测：新入库的 F06_500 指标全空，就是因为收尾没算指标 ✗')
    chk('★ 收尾跑 `factor_curves.py --only-new --stage=core`（否则详情页图表缺、'
        '而且**前端曾因此拿到全A 同名编号的曲线** ✗✗）',
        "tools/factor_curves.py', '--only-new', '--stage=core'" in rt)
    chk('两条都**只告警不中断**收尾（与其它步骤同一契约 ✓）',
        rt.count('-> 仍继续') >= 2)
    # ★★ 2026-09-17（用户："怎么入库的有些因子没有剥风格曲线？我记得之前还有啊"）：
    #   真因 = 收尾只跑了 `--stage=core` ⇒ 新因子只有核心曲线，strip / style 两段从没算 ✗
    chk('★ 收尾也跑 `--stage=strip`（否则详情页"剥风格"永远显示"还没生成" ✗）',
        "'--stage=' + _stage" in rt and "('⑤', 'strip'" in rt)
    chk('★ 收尾也跑 `--stage=style+strip2`（否则"风格相关性"永远空着 ✗）',
        "'style+strip2'" in rt)
    chk('★★ 两段都带 `--only-new` ⇒ **按 stage 只补缺的**（不会把已有的重算一遍 ✗）',
        rt.count("'--stage=' + _stage, '--panel_cache=use'") >= 1
        and "'--only-new'" in rt)

    # ---- [7] ★ 状态徽标（2026-09-17 用户："把已入库、已移出的状态也加上吧，加在 F06 文字旁边？"）----
    print('\n[7] ★ 状态徽标：这条编号**还在不在当前有效库**（三态，与「因子库」页签同源）')
    chk('后端给每条**显式**写 `inBank`（三态）—— 不是"有就带、没有就没有"',
        "row['inBank'] = _inb_of(" in fp)
    chk('★ 首选**指标表 `in_bank` 列**（够 `--include_history` 时连历史编号都写着 ⇒ 覆盖最全 ✓）',
        '_has_ib' in fp and "str(v.get('in_bank', '')).strip().lower()" in fp,
        '只读库文档行 ⇒ 早已不在文档里的编号拿不到状态，只能显示"未知" ✗')
    chk('★★ 两条路都拿不到 ⇒ **None（判不了）**，绝不默认 True/False —— "不知道"≠"在库" ✗',
        "if isinstance(f, dict) and f.get('inBank') is not None:" in fp
        and re.search(r"return bool\(f\['inBank'\]\)\s*\n\s*return None", fp) is not None,
        '默认成"已入库"= 编数据（比留白更糟 ✗）')
    chk('前端在**编号旁**渲染三态徽标（已入库 / 已移出 / 状态未知）',
        'libStateTip(e.inBank)' in src_tsx and '已入库' in src_tsx
        and '已移出' in src_tsx and '状态未知' in src_tsx
        and 0 < src_tsx.find('className="lc"') < src_tsx.find('libStateTip(e.inBank)'),
        '用户原话："加在 F06 文字旁边"')
    chk('★ 徽标**可收缩**（`flex: 0 1 auto` + 省略号）—— 宁可缩写，也不许把「详情」按钮挤没 ✗',
        re.search(r'\.logrow \.stag \{[^}]*flex: 0 1 auto', css) is not None
        and re.search(r'\.logrow \.stag \{[^}]*text-overflow: ellipsis', css) is not None,
        '卡片只 ~310px；徽标不可收缩 + `overflow-x: hidden` ⇒ 按钮被裁掉、用户点不到 ✗')
    chk('★ 详情弹层里"已不在当前有效库"只在**确证 false** 时显示（原来 `!f.inBank` ⇒ null 也误报 ✗）',
        'f.inBank === false && <span className="out">' in src_tsx)
    # ★★ 2026-09-20 修（v1.21.15 回归暴露 ✗）：原窗口取到 `function EntryLogCard` 为止 ✗ ——
    #   v1.21.15 在两者之间插入了 `GradeTag` 组件（注释里有 ★/⇒ ✓ 属维护者可见、非用户文案 ✓）
    #   ⇒ 被误判成"文案有机味符号" ✗ ⇒ 窗口收窄到 **`libStateTip` 这一个语句** ✓
    _tip = src_tsx[src_tsx.find('const libStateTip'):]
    _tip = re.split(r'\n(?:const |function |/\*\*)', _tip)[0]
    chk('徽标鼠标提示**不臆断**（未知时明说"判不了"），且文案里没有 `**`/★/⇒ 这类符号（AI 味守门 ✗）',
        _tip and '判不了它还在不在库' in _tip
        and not any(s in _tip for s in ('**', '★', '⇒', '✓', '✗')))

    # ---- [8] ★ 收尾三个工具的默认池必须覆盖**全部挖矿池**（2026-09-18 实测缺口）----
    print('\n[8] ★ 收尾三个工具的默认 `--pools` 必须覆盖全部挖矿池（含 50）')
    _tp = {}
    for _f in ('build_facs.py', 'factor_metrics.py', 'factor_curves.py'):
        with open(os.path.join(ROOT, 'tools', _f), encoding='utf-8-sig') as _h:
            _tp[_f] = _h.read()
    _lp = ''
    with open(os.path.join(ROOT, 'engine', 'loop_pools.py'), encoding='utf-8-sig') as _h:
        _lp = _h.read()
    chk('★ 三个工具都从 `loop_pools.tool_pools()` **派生**默认池（不再硬编码 ✗）',
        all('_LP.tool_pools()' in t for t in _tp.values()),
        '原来三处各硬编码 all,300,500,1000 ⇒ **漏了 50 池** ✗ ⇒ 50 池有因子入库时收尾不会给它出图/指标 ✗')
    chk('★★ 不许再出现硬编码的池清单（防回退）',
        not any("'all,300,500,1000'" in t or '"all,300,500,1000"' in t for t in _tp.values()))
    chk('★ `tool_pools()` 由池定义（`loop_pools.POOLS`）派生 —— **单一来源**，以后加池不会漏 ✓',
        'def tool_pools' in _lp and "','.join(['all'] + list(POOLS))" in _lp)

    print('\n' + '=' * 96)
    print('通过 {}/{}'.format(OK[0] - OK[1], OK[0]) + ('' if OK[1] else '  ✓ 全部通过'))
    return 1 if OK[1] else 0


if __name__ == '__main__':
    sys.exit(main())
