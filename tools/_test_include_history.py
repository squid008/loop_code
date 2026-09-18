# -*- coding: utf-8 -*-
"""★★ 回归：**历史编号（已移出当前库）也能有费后指标与曲线**（2026-09-17 用户要求）。

用户原话：「想看历史编号的费后指标/曲线」
做法：两个离线工具都加 `--include_history` —— 库里没有 Node ⇒ 从库文档的公式**反向解析**。

⚠⚠ 这条路径上有一个**真坑**必须钉住：`loop_engine.parse_expr` 有一道 `LLM_MAX_SIZE`
   （节点数）上限，超限时**静默返回 None**（`load_bank_nodes` 的注释里记着：全A F01 就曾因此返回 None）
   ⇒ 反向解析前**必须临时放开上限**，否则大式子会被静默丢掉、历史编号"算不出来"且**无声**✗

另外两条配套不变量（不做就会出错）：
  · 指标表必须带 **`in_bank` 列**（1=当前库 / 0=已移出）—— 否则 API 那句"不在表里 = 已移出"
    的推断一旦面对"历史行也在表里"就**失效** ✗
  · API 的 `metricsMeasured` 必须只数**在库**的行 —— 否则表里多了历史行 ⇒ 误报"指标表还没跑完" ✗
"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ROOT = r'D:\loop_code'
FAIL = []


def rd(p):
    return io.open(os.path.join(ROOT, p), encoding='utf-8-sig').read()


def chk(desc, cond, hint=''):
    print('  %s %s' % ('✓' if cond else '✗', desc))
    if not cond:
        FAIL.append(desc + ('（%s）' % hint if hint else ''))


fm = rd('tools/factor_metrics.py')
fc = rd('tools/factor_curves.py')
api = rd('dashboard/api/app/sources/factors.py')
app = rd('dashboard/web/src/App.tsx')

print('=' * 96)
print('【1】离线工具：`--include_history`')
print('=' * 96)
chk('指标工具新增 `--include_history`', "'--include_history'" in fm)
chk('曲线工具新增 `--include_history`', "'--include_history'" in fc)
chk('★ 两者都**从库文档取公式**（`parse_library`）而不是只认 bank',
    'lib_rows = BF.parse_library(' in fm and 'lib_rows = BF.parse_library(' in fc)
chk('★ 反向解析**先放开 `LLM_MAX_SIZE`**（否则大式子静默返回 None ✗）',
    'LE.LLM_MAX_SIZE = 10 ** 9' in fm and 'LE.LLM_MAX_SIZE = 10 ** 9' in fc,
    '不放开 ⇒ 历史编号可能"算不出来"且无声')
chk('解析失败**不臆造**（打印并跳过）',
    '反解失败' in fm or '反解失败' in fc)

print()
print('=' * 96)
print('【2】指标表：`in_bank` 列（判"在不在库"的**显式**依据）')
print('=' * 96)
chk("`COLS` 里含 `'in_bank'`", re.search(r"COLS = \[[^\]]*'in_bank'", fm, re.S) is not None)
chk('每个结果行都写 `in_bank=it.get(...)`', 'in_bank=it.get(' in fm)

print()
print('=' * 96)
print('【3】API：读 `in_bank`，且 `metricsMeasured` 只数**在库**行')
print('=' * 96)
chk("API 认识 `in_bank` 列（`inBankCol`）", 'inBankCol' in api and "'in_bank' in" in api)
chk('★ `metricsMeasured` 用 `_inb(nm)` 而不是 `len(_mt_pool)`',
    '_measured = sum(1 for nm in _names if _inb(nm))' in api and
    "'metricsMeasured': _measured," in api,
    '用表条数 ⇒ 加进历史行后会误报"表没跑完" ✗')
chk('新格式下 `inbank_known` 恒为真（不再依赖"条数恰好相等"）',
    'and _has_ib' in api)
chk('顺带暴露 `metricsHistory`（表里有多少历史编号也算过）', "'metricsHistory': _nhist," in api)

print()
print('=' * 96)
print('【4】前端文案（含用户 2026-09-17 明确要求的那处改动）')
print('=' * 96)
# ⚠⚠ 断言前**必须先剔注释** —— 注释里往往**引用着**被删掉的那句话（本项目已踩过两次：
#   `.ctrls` 的 `overflow-x` 那次也是这个坑 ✗）⇒ 否则"已删除"的断言会被自己的注释判失败
# ⚠⚠⚠ 而且**不能用正则**：`/\*.*?\*/` 会从某处 `/*` 一路吞到很远（把真实 JSX 文案也删掉，
#   于是"必须存在"的断言反而失败 ✗ 实测踩到）⇒ 直接用 `_test_ui_quotes` 里那个**状态机** ✓
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from _test_ui_quotes import strip_js          # noqa: E402
_appc = strip_js(app)
chk('★ 口径说明已按要求改：**保留**"带历史标记的行就是已不在当前库的编号"',
    '带历史标记的行就是已不在当前库的编号' in _appc)
chk('★ 且**删掉**了"点编号可以看完整公式和各项指标"（历史行本来就没有指标，会误导）',
    '点编号可以看完整公式和各项指标' not in _appc)
chk('历史行的状态列改成「已移出当前库（历史）」（明细里写的"已入库"是当年记录，会读成还在库里 ✗）',
    '已移出当前库（历史）' in _appc)
chk('详情页在"没有指标"时**告诉你补的命令**（含 `--include_history`）',
    'factor_metrics.py --include_history' in _appc
    and 'factor_curves.py --include_history' in _appc)
# ★★ 2026-09-17（用户："中证500 F06 的方向 sign 为啥是 —？其他因子要么 1 要么 -1，是不是有问题？"）：
#   真因 = 那条 md 明细段里写的**就是**"符号 sign：未记录（缺失时不臆造）"⇒ 解析为空 ⇒ 显示 — ✗
#   而**指标表里有真值**（重算 IC 与库记录 IC 对齐求出）⇒ 空时**退回指标表**，并标出来路 ✓
chk('★ 库文档写"未记录"的 sign ⇒ **退回指标表**（真值，语义一致）',
    "if not f['detail'].get('sign'):" in api and "signFrom'] = '重算指标表'" in api,
    '否则用户看到 — 会以为出错（其实真值就在指标表里 ✓）')
chk('★★ 退回时**标出来路**（不是冒充"库文档记录" ✗），且详情页把它显示出来',
    'signFrom' in api and 'signFrom' in _appc and '库文档当时没记' in _appc)
# ★★ 2026-09-17 修（实测踩到）：**别名副本会丢掉"只有它自己有的段"** ✗
#   同一公式挂多个编号（实测 `F01_1000`/`F01_500`/`F02_300` 同一 expr）⇒ 写副本时若整份照抄
#   "规范名那份文件"的 `cur`，别名独有的段（如 `F01_1000` 的 `style`）就会被覆盖消失 ✗
_fc = io.open(os.path.join(ROOT, 'tools', 'factor_curves.py'), encoding='utf-8').read()
chk('★★ 别名副本**只合并本次算过的键**（`touched`），其余读"它自己那份"旧文件 ✓',
    'touched = {k: cur[k] for k in _touched if k in cur}' in _fc
    and "cc = json.load(io.open(_po, encoding='utf-8'))" in _fc
    and "cc.update(touched)" in _fc,
    '原来 `dict(cur, name=nm_o)` ⇒ 别名独有的段被规范名那份覆盖 ✗（实测 F01_1000 丢 strip/style 之一）')
chk('★★ `touched` 必须**显式记录**（`_touched.add(...)`）—— 不能靠"对象身份"推断 ✗',
    "_touched.add('strip')" in _fc and '_touched.add(\'style\')' in _fc,
    '`strip2` 那步是**原地修改** `cur[strip]` ⇒ 身份不变 ⇒ 会被漏掉（实测两个别名文件补完仍缺 strip2 ✗）')
chk('★★★ `_style_ok` 必须**放行退化条目**（否则门控恒 False ⇒ 每轮白烧 ~55 分钟全量重算 ✗✗）',
    "continue            # 退化条目（不可判定）⇒ 不要求三个统计量 ✓" in _fc
    and _fc.count("if v.get('mean') is None and v.get('ir') is None:") >= 1,
    '`_summ` 对退化条目只回 6 个键（无 tAdj/tYr/winYr）⇒ 原 `all(...)` 永远判"要重算"'
    '（实测：--only-new 待算 59/61 ⇒ 白跑 55 分钟 ✗）')

print()
print('=' * 96)
print('【5】实测数据（表已生成时校验；没生成则跳过）')
print('=' * 96)
csvp = os.path.join(ROOT, 'docs', 'factor_metrics.csv')
if not os.path.exists(csvp):
    print('  [SKIP] docs/factor_metrics.csv 还没生成')
else:
    import csv as _csv
    rows = list(_csv.DictReader(io.open(csvp, encoding='utf-8-sig', newline='')))
    hist = [r for r in rows if str(r.get('in_bank', '1')).strip() == '0']
    chk('表里有 `in_bank` 列', rows and 'in_bank' in rows[0])
    print('       总 %d 行 · 其中历史编号 %d 个%s' % (
        len(rows), len(hist), ('：' + ', '.join(r['name'] for r in hist[:8])) if hist else ''))
    chk('★ 历史行**确实带指标**（不是空行）',
        all((r.get('ann_ex') not in (None, '') and r.get('calmar') not in (None, '')) for r in hist)
        if hist else True,
        '历史行必须有值 —— 用户要的就是这个')
    cd = os.path.join(ROOT, 'docs', 'factor_curves')
    have = os.listdir(cd) if os.path.isdir(cd) else []
    miss = [r['name'] for r in hist if ('%s.json' % r['name']) not in have]
    if hist:
        print('       历史编号的曲线：已有 %d / %d' % (len(hist) - len(miss), len(hist)))
chk('★ 曲线工具在数据缺失时会**提示命令**（不是报错）',
    '暂无曲线数据' in app or '曲线加载中' in app)

print()
if FAIL:
    print('★★ 历史编号指标/曲线 回归失败 %d 项：' % len(FAIL))
    for x in FAIL:
        print('   ✗ %s' % x)
    sys.exit(1)
print('★★ 历史编号指标/曲线 回归全部通过 ✓')
sys.exit(0)
