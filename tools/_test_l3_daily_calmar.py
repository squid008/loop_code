# -*- coding: utf-8 -*-
"""★★★★★ 守门：**精选池去重保留判据 = 日频剥后卡玛**（2026-09-22 · 用户："改成日频对齐"）

★ 为什么需要（这是个**口径打架**的隐患 ✓）：
  · 精选池的**准入档** A/B/C 由引擎按**日频**判（2026-09-14 §1.19 起判据改日频 ✓
    "期频漏掉持有期内回撤、回撤被低估"）
  · 而 `cross_pool_review.py` 的"**同族里留谁**"原来用**期频** `strip_calmar` ✗
  ⇒ 会出现 **"日频更强者被淘汰、日频更弱者留下"** ✗ ⇒ 精选池选错人（且**不报错** ✓ 本类坑典型）
  ⇒ 用户拍板"改成日频对齐" ✓ 取值/回退集中在 `strip_cal_daily()`（**单一事实源** ✓ 可单测 ✓）

★ 本守门钉住两件事：
  ① **静态**：决策与展示都走 `strip_cal_daily` ✓，且不再有任何地方**直取期频** `strip_calmar` ✗
  ② **动态**：`strip_cal_daily` 的**取值优先级 / 回退 / NaN / 字符串 / 缺省** 全对 ✓
     + 一个**语义断言**（日频更强的成员必须被保留 ✓）
"""
import io
import os
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ROOT = r'd:\loop_code'
SRC = os.path.join(ROOT, 'tools', 'cross_pool_review.py')
FAIL = []


def chk(desc, cond, hint=''):
    print('  %s %s' % ('✓' if cond else '✗', desc))
    if not cond:
        FAIL.append(desc + ('（%s）' % hint if hint else ''))


src = io.open(SRC, encoding='utf-8').read()

print('【1】静态：判据走日频 ✓')
chk('有 `def strip_cal_daily(`（单一事实源 ✓）', 'def strip_cal_daily(' in src)
chk('它的取值顺序 = **先日频后期频**（`for k in (\'strip_calmar_d\', \'strip_calmar\')` ✓）',
    "'strip_calmar_d', 'strip_calmar'" in src.replace('"', "'"))
chk('"留谁"的判据 `s_cal` 由它构造 ✓（不再直取期频 ✗）',
    re_ok := (('s_cal = {n: strip_cal_daily(strip.get(n)) for n in names}' in src)
              and ("float(strip[n]['strip_calmar'])" not in src)))
chk('`members.sort` / `sel.sort` 仍按 `-s_cal[n]` 排序 ✓（判据换了、排序方式没变 ✓）',
    '-s_cal[n]' in src)

print('\n【2】静态：展示与判据**同一口径**（不许一处期频一处日频 ✗）')
chk('全文不再有直取期频 `strip_calmar` 的**取值**（`r.get(\'strip_calmar\')` / `strip[...][\'strip_calmar\']`）✗',
    ("r.get('strip_calmar')" not in src) and ("['strip_calmar']" not in src.replace("'strip_calmar_d', 'strip_calmar'", '')))
chk('文档列名标明日频（`剥Calmar(日频)` 出现 ≥2 处 ✓）',
    src.count('剥Calmar(日频)') >= 2)
chk('控制台也标日频 ✓', '剥Calmar(日频)' in src)

print('\n【3】动态：`strip_cal_daily` 取值/回退/边界 ✓')
try:
    sys.path.insert(0, os.path.join(ROOT, 'tools'))
    sys.path.insert(0, os.path.join(ROOT, 'engine'))
    import cross_pool_review as CR
    f = CR.strip_cal_daily
    chk('★ 日频优先：{d:0.5, 期:0.9} ⇒ 0.5（**不是** 0.9 ✗）', f({'strip_calmar_d': 0.5, 'strip_calmar': 0.9}) == 0.5)
    chk('回退期频：只有期频 ⇒ 0.9 ✓', f({'strip_calmar': 0.9}) == 0.9)
    chk('字符串也吃（CSV 读出来常是字符串 ✓）：\'0.42\' ⇒ 0.42 ✓', f({'strip_calmar_d': '0.42'}) == 0.42)
    chk('★ NaN 不当有效值：{d:NaN, 期:0.7} ⇒ 0.7（回退 ✓ 不是 NaN ✗）',
        f({'strip_calmar_d': float('nan'), 'strip_calmar': 0.7}) == 0.7)
    chk('两者都缺 ⇒ 默认 −inf（排序排最后 ✓）', f({}) == float('-inf'))
    chk('`default=None` 时 ⇒ None（展示显示 — ✓）', f({}, None) is None)
    chk('`None` 行不崩 ⇒ 默认值 ✓', f(None) == float('-inf'))
    chk('空字符串 ⇒ 默认值 ✓（`float(\'\')` 会抛 ⇒ 被吞 ✓）', f({'strip_calmar_d': ''}) == float('-inf'))
    # ★ 语义断言：近重复两人，**日频**更强者必须被保留 ✓
    rows = {'A': {'strip_calmar_d': 0.40, 'strip_calmar': 0.99},     # 期频强、日频弱
            'B': {'strip_calmar_d': 0.55, 'strip_calmar': 0.10}}     # 日频强、期频弱
    keep = sorted(['A', 'B'], key=lambda n: -f(rows[n]))[0]
    chk('★ 语义：日频更强的 B 必须被保留（实保留 %s ✓）' % keep, keep == 'B',
        '若按期频排会留 A ✗ —— 这正是本次要修的 bug ✓')
except Exception as e:                                           # noqa: BLE001
    chk('能 import 并做动态验证', False, '%s: %s' % (type(e).__name__, str(e)[:110]))

print()
print('★ 全过 ✓ 精选池"留谁"已与准入档**统一到日频** ✓'
      if not FAIL else '✗ 有 %d 项没过：\n  - %s' % (len(FAIL), '\n  - '.join(FAIL)))
sys.exit(1 if FAIL else 0)
