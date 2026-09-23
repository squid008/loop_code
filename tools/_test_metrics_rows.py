# -*- coding: utf-8 -*-
"""★★★★ 守门：**指标表的"行完整性 / 行真实性"**（2026-09-23 新增；进全量回归 ✓）。

两处都是用户 2026-09-23 之问"昨天挖的那些审查正常吗？是不是 5 日 20 日都审查了？"查出来的 ✓：

【A】跨池同式子的**别名行**必须各落一份（真缺口 ✓）
    同一表达式在多个池各有编号，实测 `corr100(cs_scale(mf_x_sell), mf_l_sell)`
    = **300:F02 / 500:F01 / 1000:F01** ✓；而 `factor_metrics.py` 原来"**先按 `expr` 去重、
    再按名字查 CSV**" ✗ ⇒ 只剩池序最靠前那个（`F02_300`）⇒ `F01_500`/`F01_1000`
    **永远进不了待算队列** ⇒ 20 日指标表缺这两行、看板口径标签永远显示"缺" ✗

【B】`in_bank` 必须**与当前权威库对齐**（看板会说谎 ✗）
    它原来只在"该行被重算那一刻"才更新 ⇒ 长期停在旧值 ✗。实测：`F01_500`/`F01_1000`
    明明在库，5 日表里那两行却写着 `in_bank=0`/空 ⇒ 看板三态徽标显示成**已移出** ✗
    （前端读的就是这一列：`dashboard/api/app/sources/factors.py::_inb` ✓）

本守门钉五件：
  【1】静态：`plan_rows()` + 两处扇出 + 增量判据 = **any(别名缺)**；老写法绝迹 ✓
  【2】功能 `plan_rows`：三池同式子 ⇒ 算 1 条、别名 3 条（留下的是池序最靠前那条 ✓）
  【3】功能：**复现缺口**（旧判据说"不用算" ✗ / 新判据说"要算" ✓，两者结论必须相反）
  【4】功能：`build_facs.plan(alias=)` —— 别名缺**值文件** ⇒ 判"要重算" ✓（不带 alias 判不到 ✗）
  【5】功能：`factor_metrics.refresh_in_bank()` —— 只在**本次跑的池**内刷新、按权威库给 1/0 ✓
        ＋ 静态：收尾的 20 日那两步带 `--ic_tol=1.0`（换口径**必然**超差 ⇒ 别再刷假警报 ✗）
"""
import io
import os
import re
import shutil
import sys
import tempfile

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ENG = os.path.join(ROOT, 'engine')
for _p in (HERE, ENG):
    if _p not in sys.path:
        sys.path.insert(0, _p)

BF_SRC = io.open(os.path.join(HERE, 'build_facs.py'), encoding='utf-8').read()
FM_SRC = io.open(os.path.join(HERE, 'factor_metrics.py'), encoding='utf-8').read()
RT_SRC = io.open(os.path.join(HERE, 'run_tracks.py'), encoding='utf-8').read()
FAIL = []


def chk(desc, cond, hint=''):
    print('  %s %s' % ('✓' if cond else '✗', desc))
    if not cond:
        FAIL.append(desc + ('（%s）' % hint if hint else ''))


print('[1] 静态：算一次 + 每个名字各落一份 + `in_bank` 会刷新')
chk('`build_facs.py` 有纯函数 `plan_rows(`（⇒ 可单测 ✓）', 'def plan_rows(' in BF_SRC)
chk('`plan_rows` 建别名表（`alias.setdefault(it[\'expr\'], []).append(it)` ✓）',
    re.search(r"alias\.setdefault\(it\['expr'\], \[\]\)\.append\(it\)", BF_SRC) is not None)
chk('★ `factor_metrics.py` 用 `BF.plan_rows(items)`（不再自己按 expr 去重 ✗）',
    'uniq, alias = BF.plan_rows(items)' in FM_SRC)
chk('★ 老的"按 expr 去重 + `also`"写法在 `factor_metrics.py` 绝迹',
    "seen[it['expr']]['also']" not in FM_SRC)
chk('★ 增量判据 = **任一别名缺行**（`if done:` + `any(` ✓）',
    re.search(r"if done:\n\s+uniq = \[it for it in uniq\n\s+if any\(", FM_SRC) is not None)
chk('★★ 指标**按别名扇出**（`for _x in _als:` + `name=BF._name_of(_x)` ✓）',
    re.search(r"for _x in _als:\n\s+rows\.append\(dict\(\n\s+name=BF\._name_of\(_x\)", FM_SRC)
    is not None)
chk('★★ 因子值也**按别名扇出**（`st.write(_nmx, expr, ...)` ✓）',
    re.search(r"st\.write\(_nmx, expr, fac\.values", BF_SRC) is not None)
chk('`build_facs.plan()` 收 `alias` 参数（同式子任一编号缺文件 ⇒ 要重算 ✓）',
    re.search(r'def plan\(items, root, only_new, force, alias=None\)', BF_SRC) is not None)
chk('`factor_metrics.py` 有 `refresh_in_bank(`（顺带修徽标 ✓）', 'def refresh_in_bank(' in FM_SRC)
chk('★ 收尾的 20 日指标那两步带 `--ic_tol=1.0`（换口径必然超差 ⇒ 不刷假警报 ✗）',
    RT_SRC.count("'--fwd', '20', '--ic_tol=1.0'") == 2,
    '找到 %d 处' % RT_SRC.count("'--fwd', '20', '--ic_tol=1.0'"))

print()
print('[2] 功能 `plan_rows`：三池同式子 ⇒ 算 1 条、别名 3 条')
EXPR = 'corr100(cs_scale(mf_x_sell), mf_l_sell)'          # ★ 实测的真实式子
EXPR2 = 'neg(open)'
try:
    import build_facs as BF
    _imp = True
except Exception as e:                                                          # noqa: BLE001
    _imp = False
    print('  ✗ 导入 build_facs 失败：%r' % (e,))
    FAIL.append('导入 build_facs 失败：%r' % (e,))

if _imp:
    items = [dict(pool='300', no='F02', expr=EXPR, in_bank=1, gen=1),
             dict(pool='500', no='F01', expr=EXPR, in_bank=1, gen=1),
             dict(pool='1000', no='F01', expr=EXPR, in_bank=1, gen=1),
             dict(pool='all', no='F99', expr=EXPR2, in_bank=1, gen=3)]
    uniq, alias = BF.plan_rows(items)
    chk('去重后只算 **2** 条式子（EXPR 只算 1 次 ✓）', len(uniq) == 2, '得到 %d' % len(uniq))
    chk('★ 留下的是**池序最靠前**那条（300/F02 ⇒ `F02_300` ✓）',
        BF._name_of(uniq[0]) == 'F02_300', '得到 %s' % BF._name_of(uniq[0]))
    chk('★ 别名表把**三个编号**都记住了（F02_300 / F01_500 / F01_1000 ✓）',
        sorted(BF._name_of(x) for x in alias[EXPR])
        == ['F01_1000', 'F01_500', 'F02_300'],
        '得到 %r' % ([BF._name_of(x) for x in alias[EXPR]],))
    chk('不同式子各自一条（不误合并 ✓）', len(alias[EXPR2]) == 1)

    print()
    print('[3] 功能：**复现缺口** —— 只用主名判"要不要算"会漏掉别名')
    done = {'F02_300'}                                  # 20 日表里已有主名那行 ✓
    _old_need = BF._name_of(uniq[0]) not in done        # 旧判据（只看主名）
    _new_need = any(BF._name_of(x) not in done for x in alias[EXPR])   # 新判据（任一别名缺）
    chk('旧判据说"不用算" ✗（`F02_300` 已在表里）', _old_need is False)
    chk('★ 新判据说"**要算**" ✓（`F01_500`/`F01_1000` 缺行）', _new_need is True)
    chk('★ 两者**结论相反** ⇒ 这就是那 2 行永远补不上的病根（复现 ✓）',
        _old_need != _new_need)

    print()
    print('[4] 功能：`build_facs.plan(alias=)` —— 别名缺文件必须判"要重算"')
    import numpy as np
    import factor_store as FS
    tmp = tempfile.mkdtemp(prefix='_test_rows_')
    try:
        it_a = dict(pool='300', no='F02', expr=EXPR, node=None)
        it_b = dict(pool='500', no='F01', expr=EXPR, node=None)
        al = {EXPR: [it_a, it_b]}
        st = FS.FactorStore(root=tmp)
        D = np.arange(4, dtype='float32').reshape(2, 2)
        # ⚠ `dates` 必须是**数值**（`factor_store.write` 里直接进 h5 attr ⇒ 传字符串会 TypeError ✗）
        DT = np.array([20200101, 20200102])
        st.write('F02_300', EXPR, D, DT, ['a', 'b'])
        full1, q1, sk1 = BF.plan([it_a], tmp, True, False, al)      # ★ 带 alias（修好后）
        full0, q0, sk0 = BF.plan([it_a], tmp, True, False, None)    # 旧行为（不带 alias）
        chk('★ 带 `alias` ⇒ 判 **full**（`F01_500` 的值文件还缺 ✓）',
            [x['no'] for x in full1] == ['F02'], '得到 full=%r' % (full1,))
        chk('不带 `alias` ⇒ **判不到"要重算"**（落进 quant_only/skipped ⇒ 别名永远补不上 ✗，复现 ✓）',
            [x['no'] for x in full0] == [] and [x['no'] for x in (q0 + sk0)] == ['F02'],
            '得到 full=%r quant=%r skipped=%r' % (full0, q0, sk0))
        st.write('F01_500', EXPR, D, DT, ['a', 'b'])
        full2, q2, sk2 = BF.plan([it_a], tmp, True, False, al)
        chk('两个名字值都在、缺 `values_q.h5` ⇒ 判 **quant_only**（不载面板 ✓）',
            [x['no'] for x in q2] == ['F02'], '得到 quant=%r full=%r' % (q2, full2))
        st.write_quant_copy('F02_300', EXPR, overwrite=True)
        st.write_quant_copy('F01_500', EXPR, overwrite=True)
        full3, q3, sk3 = BF.plan([it_a], tmp, True, False, al)
        chk('两个名字都齐 ⇒ 判 **skipped**（增量模式不重复算 ✓）',
            [x['no'] for x in sk3] == ['F02'], '得到 skipped=%r' % (sk3,))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    print('[5] 功能：`refresh_in_bank()` —— 徽标按**当前权威库**对齐（只在本次跑的池内 ✓）')
    try:
        import factor_metrics as FM
        _items = [dict(pool='500', no='F01', expr='e1', in_bank=1),
                  dict(pool='500', no='F09', expr='e9', in_bank=1),
                  dict(pool='300', no='F07', expr='e7', in_bank=1)]     # 别的池（本次不跑）
        _old = [dict(name='F01_500', pool='500', in_bank='0'),        # 在库 ⇒ 必须改成 1 ✓
                dict(name='F09_500', pool='500', in_bank='1'),        # 已对 ⇒ 不许进结果 ✓
                dict(name='F99_500', pool='500', in_bank='1'),        # 已移出 ⇒ 改成 0 ✓
                dict(name='F01_500', pool='300', in_bank='1'),        # 别的池的同名行 ⇒ 不许动 ✓
                dict(name='F07_300', pool='300', in_bank='0')]        # 池不在本次 ⇒ 不许动 ✓
        _fix = FM.refresh_in_bank(_old, _items, ['500'])
        _got = sorted((r['name'], r['pool'], r['in_bank']) for r in _fix)
        chk('在库却写着 0 的行 ⇒ 改成 `1` ✓', ('F01_500', '500', '1') in _got, '得到 %r' % (_got,))
        chk('已移出却写着 1 的行 ⇒ 改成 `0` ✓', ('F99_500', '500', '0') in _got, '得到 %r' % (_got,))
        chk('★ 已经对的行**不进结果**（不制造无谓写入 ✓）',
            ('F09_500', '500', '1') not in _got, '得到 %r' % (_got,))
        chk('★★ **本次没跑的池**的行一律不动（`--pools=500` 不许把 300 改掉 ✗）',
            all(r['pool'] == '500' for r in _fix), '得到 %r' % (_got,))
        chk('空 `in_bank`（老行）也按权威库补成 1/0 ✓',
            FM.refresh_in_bank([dict(name='F01_500', pool='500', in_bank='')], _items,
                               ['500'])[0]['in_bank'] == '1')
    except Exception as e:                                                      # noqa: BLE001
        chk('导入/调用 `factor_metrics.refresh_in_bank`', False, repr(e))

print()
if FAIL:
    print('✗ 失败 %d 项：' % len(FAIL))
    for x in FAIL:
        print('   - %s' % x)
    sys.exit(1)
print('✓ 全部通过：别名行（算一次 + 每个编号各落一份）+ `in_bank` 与权威库对齐')
