# -*- coding: utf-8 -*-
"""★★★ 前端「接线」回归检查（静态，不改运行状态）—— 防「处理函数写了却没接上」。

★ 为什么需要（2026-09-16 血泪）：
  我在 `v1.3.9` 写了 `doStartPool()`（走 `/api/mine/start_pool`，**只动该池**），
  但池卡片上接的仍是 `doStart([p.key])`（走 `/api/mine/start`，**会把 enabled 整体改写**）
  ⇒ 用户点「启动本池(全A)」⇒ **其余 4 个池全被移出轮转** ✗✗
  ★ 而当时的"端到端测试"是**直接打 API** ⇒ **完全没覆盖到前端接线** ✗

⇒ 本脚本做**静态接线断言**：
  ① 关键按钮必须接到**语义正确**的处理函数上；
  ② 处理函数必须**真的被引用**（否则就是"写了没接"的死代码）✗；
  ③ 页面用到的 `api.mine*` 必须在 `api.ts` 里有定义（防拼错 endpoint）。
"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
APP = r'D:\loop_code\dashboard\web\src\App.tsx'
API = r'D:\loop_code\dashboard\web\src\api.ts'

src = io.open(APP, encoding='utf-8').read()
FAIL = []


def chk(desc, cond, hint=''):
    print('  %s %s' % ('✓' if cond else '✗', desc))
    if not cond:
        FAIL.append(desc + ('（%s）' % hint if hint else ''))


print('【1】池卡片按钮的接线（★ 语义必须正确）')
# 池卡片的 onStart 必须走"**只动该池**"的接口 ⇒ doStartPool（而非 doStart）
chk('池卡片 onStart 接的是 doStartPool（只动该池）',
    re.search(r'onStart=\{\(\)\s*=>\s*doStartPool\(', src) is not None,
    '若接成 doStart([...]) ⇒ 会把 enabled 整体改写 ⇒ 其它池被移出轮转 ✗')
chk('池卡片 onStart **没有**误接成 doStart([',
    re.search(r'onStart=\{\(\)\s*=>\s*doStart\(', src) is None,
    '这就是 2026-09-16 的 bug 本体')
chk('池卡片 onStop 接的是 doStop(池)',
    re.search(r'onStop=\{\(\)\s*=>\s*doStop\(', src) is not None)

print()
print('【2】顶栏按钮的接线')
chk('「一键启动全部」接的是 doStart([])',
    re.search(r'doStart\(\[\]\)', src) is not None)
chk('「全部停止」接的是 doStop() 无参（= 全部停）',
    re.search(r'doStop\(\)\}', src) is not None)

print()
print('【3】处理函数必须**真的被引用**（防"写了没接"的死代码）')
for fn in ('doStart', 'doStop', 'doStartPool'):
    uses = list(re.finditer(r'\b%s\(' % fn, src))
    defined = re.search(r'const %s = useCallback' % fn, src) is not None
    n_call = len(uses) - (1 if defined else 0)
    chk('%-12s 已定义且被引用（引用 %d 次）' % (fn, n_call), defined and n_call >= 1,
        '定义了却没接线 ⇒ 功能点了会走旧路径 ✗')

print()
print('【4】接口常量名拼写（防止调到不存在的 endpoint）')
api = io.open(API, encoding='utf-8').read()
for name, path in (('mineState', '/mine/state'), ('mineStart', '/mine/start'),
                   ('mineStop', '/mine/stop'), ('mineStartPool', '/mine/start_pool')):
    ok = ('%s:' % name) in api and ("'%s'" % path) in api
    chk('api.%-13s -> %s' % (name, path), ok)
used = set(re.findall(r'api\.(mine\w+)', src))
known = set(re.findall(r'^\s*(mine\w+):', api, re.M))
unknown = sorted(used - known)
chk('页面里用到的 api.mine* 都已定义%s' % ('：缺 ' + ','.join(unknown) if unknown else ''),
    not unknown)

print()
print('【5】★ 因子曲线：图例必须能**点选显隐**（2026-09-16 用户要求「所有的图，点图例要能显隐曲线」）')
chk('图例是**按钮**而非纯文本（可点）',
    re.search(r'className=\{`ch-lgbtn\$\{off\[i\] \? \' off\' : \'\'\}`\}', src) is not None,
    '图例若仍是 <span> ⇒ 点了没反应 ✗')
chk('图例按钮绑定了 onClick 切换隐藏态',
    re.search(r'onClick=\{\(\) => setOff\(o => \(\{ \.\.\.o, \[i\]: !o\[i\] \}\)\)\}', src) is not None,
    '这是"能显隐"的本体')
chk('隐藏的曲线**退出 Y 轴取值范围**（否则坐标轴仍被撑住 ⇒ 藏了也白藏）',
    re.search(r'vis\.forEach\(x => x\.s\.data\.forEach', src) is not None,
    'Y 轴取值必须基于 vis 而不是 series ✗')
chk('换因子时**重置**显隐状态（否则换到别的因子会莫名少几条线）',
    re.search(r'useEffect\(\(\) => \{ setOff\(\{\}\) \}, \[sig\]\)', src) is not None)
chk('全部隐藏时有提示 + 图例仍可点回来',
    '（曲线已全部隐藏' in src)
# ⚠ 别写成 "`'/curves/`" —— api.ts 里是**模板字符串**（反引号），不是单引号 ✗（2026-09-16 自己踩到）
chk('曲线接口 api.curves -> /curves/ 已定义且被页面调用',
    ('curves:' in api and '/curves/' in api and 'api.curves(' in src))

print()
print('【5·补】★★ 精选池详情必须**真的显示出指标**（2026-09-16 用户："超额年化之类的怎么都是 -"）')
chk('数值渲染**不再只认库表的 `metricsInfo.found`**（精选池那条路不传它 ⇒ 原来全显示 — ✗）',
    re.search(r'const metricsReady = metricsInfo \? !!metricsInfo\.found : Object\.keys\(m\)\.length > 0',
              src) is not None,
    '要有"没传 metricsInfo ⇒ 看因子自己有没有指标"的回退 ✓')
chk('渲染用的是 `metricsReady`（而不是 `metricsInfo?.found`）',
    '{metricsReady ? fmtM(m[key], kind) : ' in src and '{metricsInfo?.found ? fmtM(' not in src)
chk('精选池详情确实把 `metrics: sel.metrics` 传进详情层',
    'metrics: sel.metrics' in src)
chk('★ 顶部内存数字的鼠标提示已**按用户要求删掉**（不要再挂 `memNote`）',
    'title={mine?.memNote' not in src)
# ★★ 2026-09-17（用户："中证500 的 F01·历史因子，详情里指标都是 - ，正常吗？"）：
#   正常（指标表/曲线都以 state.bank = 当前有效库为准），但**必须说明原因**，别甩一个 — 让人以为出错 ✗
chk('★ 没有指标时**要说明原因**，并**分两种情况**给出补数据的命令',
    ('没有统一口径指标' in src or '表比库旧' in src)
    and '已移出当前库' in src and 'factor_metrics.py --include_history' in src
    and 'factor_metrics.py --only-new' in src,
    '⚠ 断言别绑死措辞（文案已改过几轮 ✗）；且**两种原因**（历史编号 / 表比库旧）'
    '必须分别给对命令 —— 只甩一个 `—` 会让人以为出错 ✗')
chk('★ 指标表/曲线的取数口径写明是 **当前有效库（state.bank）**',
    'state.bank' in src or '当前有效库' in src)

print()
print('【7】★ 顶栏控件栏：**永远保持一行**（2026-09-17 用户："红框这行就干脆一直放在这一行吧，'
      '不然它会随着内存变动一会儿跳到第一行一会儿跳到第二行"）')
css = io.open(r'D:\loop_code\dashboard\web\src\styles.css', encoding='utf-8').read()
chk('控件栏内部**不换行**且**不被压缩**（整条整体换行交给 `.top`）',
    re.search(r'\.ctrls \{[^}]*flex-wrap: nowrap', css) is not None
    and re.search(r'\.ctrls \{[^}]*flex: 0 0 auto', css) is not None,
    '可收缩 + 内部 wrap ⇒ 空间一变就逐项折行（用户看到的"跳来跳去"✗）')
chk('★ **会变宽的内存数字**定宽 + 等宽数字（一变宽就把邻居挤走 ⇒ 跳行）',
    re.search(r'\.ctrls \.res b \{ min-width: 62px', css) is not None,
    '`3.1 GB` → `19.4 GB` 宽度会变 ⇒ 必须 min-width + tabular-nums')
# ⚠ 2026-09-17 更新：相位卡由 `min-width: 190px` 改成**定宽**（见下面那组断言），
#   这里只保留"启动按钮定宽"（"一键启动全部"/"已在运行"/"处理中…" 文案不同 ⇒ 不定宽就整体位移 ✗）
chk('启动按钮定宽（文案一变就整体位移 ✗）',
    '.ctrls .btn.start { min-width: 116px; }' in css)
chk('极窄屏**优雅降级**（先省次要文字，而不是折行或横滑）',
    '@media (max-width: 1000px)' in css)
# ★★ 2026-09-17 用户第二批：「这个一坨会随着轮次、内存数据变动而改变长度，就搞成**固定的宽度**吧，
#   卡片宽度不要变来变去的；第一个空闲的那个卡片宽度可以**对齐下面 0/5 那个卡片**」
# ★★★ 2026-09-17 第三批（**推翻上面那条**）：「这个卡片是不是可以窄很多了？空闲跟 1/50 之间
#   隔了太宽了，留的宽度够"空闲 9999/9999"的位置就行了」
#   ⇒ 现在 = **贴合内容**（不再有那段空白）+ **轮次槽定宽**（仍不抖 ✓）；旧断言同步改掉 ✓
chk('★★ 相位卡**贴合内容**（撤掉"定宽 218px + 轮次靠右"那一段空白 —— 用户："隔太宽了"）',
    re.search(r'\.ctrls \.phase \{ width: max-content', css) is not None
    and 'margin-left: auto' not in css.split('.ctrls .phase small')[1][:120],
    '仍是 218px / 轮次 `margin-left:auto` ⇒ 空闲时右边空一大段 ✗')
chk('★ 轮次槽**定宽**（"9999/9999" 也放得下，且数字变化**不推动卡宽**）',
    re.search(r'\.ctrls \.phase small \{ flex: none; min-width: 52px', css) is not None
    and 'tabular-nums' in css)
chk('★ 轮次槽**永远渲染**（没轮次时是**空槽** ⇒ 卡宽不抖，也不显示假数据）',
    "? `${compactRound(mine.roundText)}/${mine?.rounds ?? '?'}` : ''" in src)
chk('★ 内存卡**定宽 236px**（文案简化后收窄；仍按"运行中"最宽内容定 ⇒ 开始挖掘时不变宽）',
    re.search(r'\.ctrls \.res \{ width: 236px', css) is not None)
# ★★ 2026-09-17 用户第二批：「`并行×1（自动） · 共享` 改成 `并行 · 共享`」
chk('★ 内存卡模式文案**简化成"并行 · 共享"**（并行数/是否自动移出常显位）',
    re.search(r"\(mine\.execMode === 'parallel' \? '并行' : '轮转'\)", src) is not None
    and "' · 共享'" in src)
# ★★ 用户之问：「挖掘中 500 gen17 是 500 池在挖的意思吗？我不是并行了吗？」
chk('★ 并行时相位卡**不显示单个池名**（只显示 轮次；否则会被读成"只跑一个池"✗）',
    'mine.execMode !== ' in src and 'mine?.running && mine.execMode !== ' in src)
chk('★ 相位卡鼠标提示**逐池列出**"正在跑：<池> · gen <代数>"',
    '正在跑：${x.pool}' in src and 'runningList' in src)
# ★ 2026-09-17（用户问"要不要 MAD 去极值"引出）：两条 IC 的口径差必须写在图上
chk('★ IC 图下说明**以 RankIC 为准**（Pearson 的收益侧是原始值 ⇒ 会被肥尾拉偏）',
    '以 RankIC 为准' in src and '肥尾' in src)
# ★★ 2026-09-17（用户实测："几个池子蓝点、只有 300 绿点，像轮转"—— 那其实是**启动即崩**）
chk('★★ 池卡片会显示"启动即崩"（读 `slot.crashes`，红点 + 红字提示）',
    'crashN' in src and '启动即崩 ×' in src and 'crashes' in api,
    '崩溃不可见 ⇒ "蓝点（并行中）"会被误读成"在排队/轮转" ✗')
# ★★★★ 2026-09-17（用户："因子库里滚轮往下滚，发现顶部 F02 那一行跟表头重叠了、有重影"）：
#   真因 = 吸顶 `th` **没设 `z-index`**，而 `.tbl` 里有 `tr.outbank td { opacity: .62 }` ——
#   **`opacity < 1` 会给单元格新建层叠上下文** ⇒ 历史行的文字按 DOM 顺序**画在表头之上** ✗
#   （在库行没有 opacity ⇒ 正常；所以此前一直没暴露）⇒ **所有吸顶元素必须显式给 `z-index`** ✓
chk('★★ 吸顶表头有 `z-index`（否则 `opacity<1` 的单元格会盖住它 ⇒ 重影 ✗）',
    re.search(r'\.tbl th \{[^}]*z-index:\s*\d+', css) is not None,
    '`tr.outbank td` 的 opacity 新建层叠上下文 ⇒ "历史行"压住表头（用户实测的那个现象）✗')
chk('★ 详情弹层的吸顶标题同样有 `z-index`（同类隐患，一并堵住）',
    re.search(r'\.dt-h \{[^}]*z-index:\s*\d+', css) is not None)
# ★★★★ 2026-09-17 修（用户："新入库的 500 F06 为啥有曲线图，但超额年化那些指标都是 —？"）——
#   根因不是指标，是**曲线取错文件**：`F06.json` 是全A 的 F06、`F06_500.json` 才是 500 的 ✗✗
chk('★★ 详情页曲线**按池取对文件名**（`{code}_{pool}`；否则会拿到**全A 同名编号**的曲线 ✗✗）',
    "const file = (pool && pool !== 'all') ? `${name}_${pool}` : name" in src
    and "api.curves(pool || 'all', file)" in src,
    '命名规则散落在两处（写盘在 factor_curves.py、读取在前端）⇒ 必须用同一条规则 ✓')
chk('★ 内存卡的"模式"格**永远渲染**（未运行时显示占位 ⇒ 卡宽恒定且不留空白）',
    "'mode' + (mine?.running ? '' : ' off')" in src and '未运行' in src)
chk('相位卡文案**压缩**（卡窄了更要压；完整信息留在鼠标提示里）',
    'compactCur' in src and 'compactRound' in src)

print()
print('【6】★ 风格相关性画像：横向条形图 + 图例显隐 + 数据来源（2026-09-16 用户要求）')
chk('风格画像走**同一个 /curves 接口**的 style 字段（不另开接口），且**口径串过出口清洗**',
    'StyleProfileDto' in api and "'style': _plain_style(d.get('style'))" in io.open(
        r'D:\loop_code\dashboard\api\app\sources\factors.py', encoding='utf-8').read(),
    '另开接口要多一次请求、多一份缓存 ✗；口径串必须 `_plain` 过一遍 ✗')
chk('横向条形图组件已实现', 'function BarChart' in src)
# ⚠ 文案断言别绑**具体措辞里的引号**：用户 2026-09-16 要求"文案去掉引号" ⇒ 原来断言
#   `点击隐藏 / 显示「原始」这一根` 立刻失效 ✗ ⇒ 只断言"图例是按钮 + 提示里有隐藏/显示" ✓
chk('条形图图例同样**可点显隐**（与折线图同约定）',
    'ch-lgbtn' in src and re.search(r'title="点击隐藏或显示原始这一根"', src) is not None)
chk('风格图固定值域 ±1 ⇒ **跨因子可比**', 'domain={1}' in src,
    '自适应值域会让"0.05 看着和 0.5 一样长" ✗')
chk('行业条用自适应值域（相关性本身很小，固定 ±1 会看不见）',
    re.search(r'<BarChart rows=\{indRows\} />', src) is not None)
chk('统计表含 IR / t / 胜率 / 自相关（不是只给一个相关系数）',
    all(k in src for k in ('|均值|', '>IR<', '>t<', '胜率', '自相关')))
# ★ 2026-09-16 实测教训：相关序列 ac1≈0.93~0.97 ⇒ 朴素 t=IR·√T 会被放大数倍 ⇒ 必须显示**校正后**的 t
chk('表里同时有 **校正 t 与朴素 t**，且用 tAdj', '>t朴素<' in src and 'tAdj' in src)
chk('未生成时给可执行提示（不是空白）', '--stage=style+strip2' in src)
chk('新增两个剥法（剥流通市值 / 剥总市值+限售）已接进图例',
    all(k in src for k in ('floatcap', 'caplimit')))
# ★★ 2026-09-18（用户之问）：「风格相关性表加一列剥全部、剥前/剥后对比」+「净值曲线加一条剥全部，
#   第 7 个就叫剥全部」+「图例放一列就好了」
chk('★ 第 7 条剥法 `allsty`「剥全部」已接进图例', 'allsty' in src and '剥全部' in src)
chk('★ 剥风格图**按用户指定的竖排一列图例**（7 条横排会换行挤在一起 ✗）',
    'legendCol' in src and "flexDirection: 'column'" in src)
chk('★ 风格相关性表新增「剥全部均值」一列（剥前 / 剥市值+行业 / 剥全部 三态对比）',
    '剥全部均值' in src and 'allsty' in src)
chk('★ 风格条形图支持**第三根**（剥全部），右侧数字也随之三列',
    'v3' in src and 'const has3 =' in src)
chk('★★ 老曲线文件兼容：没有 `v3` 时**自动退回两根**（不编数据、不报错 ✗）',
    'has3 ? 3 : 2' in src)

print()
print('【7】★ 调度模式 / 面板共享：UI 控件必须接到位（2026-09-16 用户之问「前端还没把并行切换加上」）')
MINE = r'D:\loop_code\dashboard\api\app\mine.py'
minepy = io.open(MINE, encoding='utf-8').read()
# ★ 2026-09-16（用户："把轮转/并行按钮都隐藏了，先直接默认并行吧"）⇒ 按钮撤掉、固定并行 ✓
chk('★ 模式分段控件**已撤**（固定并行），启动固定传 execMode=parallel',
    'setExecMode' not in src and "MODE: 'parallel'" in src and 'execMode: MODE' in src)
# ★ 2026-09-16（用户要求）：**UI 只留"模式"一个开关** —— 并行数自动算、预算撤掉、共享默认开
chk('★ 并行数**输入框已撤**（后端按可用内存自动定：能开几个开几个）',
    'parallelRange' not in src and 'setMaxParallel' not in src)
chk('★「预算」输入框已撤（实测它是"排队闸门"不是"内存上限"，改了没用 ✗）',
    '每个引擎的内存预算' not in src and 'setMemPerEngine' not in src)
chk('★ 面板共享**勾选框已撤**（改为默认常开），启动固定传 panelCache=use',
    'setPanelCache' not in src and "panelCache: 'use'" in src)
MINE = r'D:\loop_code\dashboard\api\app\mine.py'
minepy = io.open(MINE, encoding='utf-8').read()
PARR = r'D:\loop_code\tools\parallel_runner.py'
prpy = io.open(PARR, encoding='utf-8').read()
chk('★ mine.py：并行数**自动算**（`floor((可用-余量)/每引擎)` 再夹到 1~池数）',
    'max_parallel = int(max(1, min(len(pool_list)' in minepy)
chk('★ mine.py：缓存不可用 ⇒ **自动降级为 off**（不让启动失败）+ note 说明',
    '_pc_degraded' in minepy and '自动关掉' in minepy)
chk('★★ parallel_runner：用户**单独停池**后**本轮不再补位**（空槽留给用户自己决定）',
    '不再自动补位' in prpy and 'deferred' in prpy)
chk('★★ parallel_runner：运行期「启动本池」**马上生效**（动态队列，不等下一轮）',
    'launched' in prpy and 'p not in launched' in prpy)
chk('★ 池卡片文案**跟实际模式一致**（并行下不写"轮转中"，免得像是要排队 ✗）',
    "qword = mine?.execMode === 'parallel'" in src and '已参与${qword}' in src)
# ★★ 用户实测"停完再启动变成了轮转"⇒ 根因是 UI 控件与后端"上次设置"脱钩（页面刷新回默认）
#   ⇒ 现在**模式固定并行**，这个坑从结构上消失了（不必再同步；状态区仍以真实命令行为准）✓
CSS = io.open(r'D:\loop_code\dashboard\web\src\styles.css', encoding='utf-8').read()
chk('★ 状态区仍以**真实进程命令行**为准显示模式（UI 固定并行 ≠ 实际在跑什么）',
    'mine.execMode === ' in src)
# ⚠ 必须**先剔注释**再断言 —— 注释里就写着 `overflow-x: auto` 这几个字（解释它为何被去掉）✗
_CSS_NC = re.sub(r'/\*.*?\*/', '', CSS, flags=re.S)
_m = re.search(r'\.ctrls \{[^}]*\}', _CSS_NC)
# ⚠ 2026-09-17 改：原来断言"整块换行（`flex-wrap: wrap`）"，但用户实测发现**整排会被压窄后
#   内部逐项折行**（内存数字一变宽就换位置 ⇒ "一会儿跳第一行一会儿跳第二行"✗）
#   ⇒ 新意图：**内部 nowrap + 不被压缩**（整条整体换行交给 `.top`）、且**不用 overflow-x** ✓
chk('★ 顶栏 `.ctrls` 不用 overflow-x（避免横条）+ 内部不换行、不被压缩',
    _m is not None and 'overflow-x' not in _m.group(0)
    and 'flex-wrap: nowrap' in _m.group(0) and 'flex: 0 0 auto' in _m.group(0),
    '实际规则：%s' % (_m.group(0).replace('\n', ' ') if _m else '(没匹配到 .ctrls 规则)'))
chk('★ 状态条文案已缩短（免得把顶栏挤爆）', '池在跑' in src)
chk('★ 调度器活着但没池可跑 ⇒ 不再谎报「挖掘中」（`_runnable` 判定）', '_runnable' in minepy)
chk('doStart 把模式参数**真的**发给接口', 'api.mineStart(pools, rounds, {' in src)
chk('api.mineStart 支持 opts 透传（含 execMode/panelCache）',
    'opts?' in api and 'execMode?: string' in api and 'panelCache?: string' in api)
chk('状态区显示**实际**在跑的模式（不是 UI 上选的那个）',
    'mine.execMode === ' in src and "'execMode': _mode" in minepy,
    '必须**以真实进程命令行为准** —— UI 选择 ≠ 实际运行 ✗')
chk('mine.py：**非默认才追加开关**（默认命令行逐字不变）',
    "if exec_mode != 'rotate':" in minepy and "if panel_cache != 'off':" in minepy)
chk('mine.py：启动参数不可热改 ⇒ 409 拒绝（不静默 no-op）',
    '不能热改' in minepy and 'e.code == 409' in open(r'D:\loop_code\tools\_test_mine_launch.py',
                                                  encoding='utf-8').read())
chk('mine.py：内存护栏**分档**（面板共享后按 GB_PER_ENGINE_SHARED 算）',
    'GB_PER_ENGINE_SHARED' in minepy)
chk('启动参数回归测试在册（假 Popen + 快照还原 ctl）',
    os.path.isfile(r'D:\loop_code\tools\_test_mine_launch.py')
    and '_control.json' in open(r'D:\loop_code\tools\_test_mine_launch.py', encoding='utf-8').read())

print()
if FAIL:
    print('★★ 接线检查失败 %d 项：' % len(FAIL))
    for f in FAIL:
        print('   ✗ %s' % f)
    sys.exit(1)
print('★★ 接线检查全部通过 ✓')
