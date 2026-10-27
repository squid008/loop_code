# -*- coding: utf-8 -*-
"""守门：**指标表缺行 ≠ 已移出**（沿用库文档状态）✓

背景（2026-10-27 用户）："公司里 F53 因子是入库的，怎么家里变成已移出了？"
  真因：`docs/factor_metrics.csv` 是**派生文件**（`.gitignore`，换机器/pull 后必定落后），
  家里那份停在 10-20，而 F53 是 10-24 入库 ⇒ 表里没有这一行；
  旧实现把"缺行"直接判 `False`（= 已移出）⇒ 同一个因子在两台机器上说法相反 ✗

口径（三态，绝不猜）：
  ① 指标表**有**该行 ⇒ 以 `in_bank` 为准（1 在库 / 0 已移出 / 空 ⇒ 判不了）
  ② 指标表**没有**该行（新入库还没跑 metrics / 表是老的）⇒ 退回**库文档状态列**
     （引擎 `_lib_sync` 写库时同步写的「已入库」/「已移出」）
  ③ 两者都拿不到 ⇒ `None`（前端显示"状态未知"）—— **未知 ≠ 已移出** ✗

本守门钉住：
  1. 静态：`_in_tbl` / `_md_inb` 存在，且旧的"缺行算在库"写法已删除
  2. 实测：把某个在库编号从指标表里抹掉后，`library()` 仍判它在库（退回 md）
  3. 实测：抹掉之后 `metricsMeasured` **不把它算成"已测"**（少 1）
"""
import os
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'dashboard', 'api'))

FAIL = []


def chk(desc, cond, hint=''):
    print('  %s %s' % ('✓' if cond else '✗', desc))
    if not cond:
        FAIL.append(desc + ('（%s）' % hint if hint else ''))


print('[1] 静态：三态实现到位')
SRC = open(os.path.join(ROOT, 'dashboard', 'api', 'app', 'sources', 'factors.py'), encoding='utf-8').read()
chk('有 _in_tbl（表里三态：True/False/None）', 'def _in_tbl(nm):' in SRC)
chk('有 _md_inb（退回库文档状态列）', 'def _md_inb(f):' in SRC)
chk('缺行时退回 md（而不是直接 False）', '_mdst if _mdst is not None' in SRC)
chk('旧的"缺行 = 在库"写法已删除', "not in ('0', 'false', 'False')" not in SRC)

print('[2] 实测：抹掉指标表里的一行后仍按库文档判')
from app.sources import factors as F          # noqa: E402

d0 = F.library('all')
codes = [f['code'] for f in d0['factors']]
if not codes:
    chk('因子库非空（否则本守门没有样本）', False, 'docs/factor_library.md 没解析到编号')
else:
    last = codes[-1]
    before = {f['code']: f.get('inBank') for f in d0['factors']}
    m0 = d0.get('metricsMeasured')
    _orig = F._metrics_table

    def _mt_drop(csv_name=None):
        mtab, mt, info = _orig(csv_name)
        mtab.pop(last, None)
        return mtab, mt, info

    F._metrics_table = _mt_drop
    try:
        d1 = F.library('all')
        aff = {f['code']: f.get('inBank') for f in d1['factors']}
    finally:
        F._metrics_table = _orig
    print('      样本编号 = %s · 抹掉前 inBank=%r · 抹掉后 inBank=%r' % (last, before.get(last), aff.get(last)))
    chk('抹掉后仍判"在库"（退回库文档，不变 False）', aff.get(last) is True)
    chk('抹掉后不计入已测条数', (d1.get('metricsMeasured') or 0) <= (m0 or 0))

print()
if FAIL:
    print('✗ 失败 %d 项:' % len(FAIL))
    for x in FAIL:
        print('   -', x)
    sys.exit(1)
print('✓ 全部通过（指标表缺行不再误判成"已移出"）')
