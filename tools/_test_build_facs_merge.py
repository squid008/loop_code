# -*- coding: utf-8 -*-
"""_test_build_facs_merge.py — `build_facs.py --only-new` 的回归测试（2026-09-14）

## 为什么必须测这一块
`--only-new` 的两个高风险点，**失败时都是静默的**（文件还在、格式也对，但数据没了/错了）：

1. ★★ **`_merge_csv` 不能退化成覆盖**：`docs/loop_strip_style_bank.csv` 是 **52 个因子的剥风格实测**
   （精选池 L3 的**闸门依据**）。旧代码每次 `open(...,'w')` 只写本次的行 ⇒ 配合增量模式会
   **把已有的 52 行清空**，只剩那几个新因子 ⇒ 下游 `cross_pool_review.py` 会误判成
   "库里只有 3 个因子"，而且**不报错**。
2. ★ **分流判定要准**：`full`(需重算) / `quant_only`(只缺 `values_q.h5`) / `skipped`(已就绪)。
   判错会导致"该重算的跳过了"（数据陈旧却不自知）或"没必要的重算"（白等 20 分钟）。

## 用法
    python tools/_test_build_facs_merge.py
"""
import csv
import importlib.util
import io
import os
import shutil
import sys
import tempfile

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DOCS = os.path.join(ROOT, 'docs')
OK = [0, 0]


def chk(cond, msg):
    OK[0] += 1
    if not cond:
        OK[1] += 1
    print('  [{}] {}'.format('OK ' if cond else 'FAIL', msg))


def load_mod():
    spec = importlib.util.spec_from_file_location('bfd', os.path.join(HERE, 'build_facs.py'))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


COLS = ['name', 'pool', 'expr', 'ic', 'calmar', 'ann_ex',
        'strip_ic', 'strip_calmar', 'strip_ann_ex', 'strip_sharpe', 'grade']


def t_merge():
    print('\n[1] _merge_csv —— 增量模式绝不能清空已有数据')
    m = load_mod()
    src = os.path.join(DOCS, 'loop_strip_style_bank.csv')
    if not os.path.exists(src):
        chk(False, '前置缺失: {}（先跑 build_facs.py）'.format(src))
        return
    n0 = len(list(csv.DictReader(io.open(src, encoding='utf-8-sig', newline=''))))
    tmp = os.path.join(tempfile.mkdtemp(prefix='mergetest_'), 't.csv')
    shutil.copy(src, tmp)
    chk(n0 > 0, '前置: 已有 {} 条剥风格记录'.format(n0))

    new = [dict(name='ZZZ_NEW', pool='1000', expr='fake_new(x)', ic=0.01, calmar=0.5,
                ann_ex=0.05, strip_ic=0.01, strip_calmar=0.4, strip_ann_ex=0.04,
                strip_sharpe=1.0, grade='A'),
           dict(name='F07', pool='all', expr='overwritten', ic=9.9, calmar=9.9,
                ann_ex=9.9, strip_ic=9.9, strip_calmar=9.9, strip_ann_ex=9.9,
                strip_sharpe=9.9, grade='C')]
    n1 = m._merge_csv(tmp, new, COLS)
    rows = list(csv.DictReader(io.open(tmp, encoding='utf-8-sig', newline='')))
    names = [r['name'] for r in rows]
    chk(n1 == n0 + 1, '合并后 {} 条 = 原有 {} + 新增 1（**没有清空**）'.format(n1, n0))
    chk('ZZZ_NEW' in names, '新因子已入表')
    chk([r for r in rows if r['name'] == 'F07'][0]['calmar'] == '9.9',
        '同名行被**覆盖**（新数据优先）')
    chk(len(names) == len(set(names)), '无重名（去重生效）')
    chk(len(rows) == n0 + 1, '旧行数未丢（校验第二遍）')
    shutil.rmtree(os.path.dirname(tmp), ignore_errors=True)
    # 真实文件必须分毫未动
    n_after = len(list(csv.DictReader(io.open(src, encoding='utf-8-sig', newline=''))))
    chk(n_after == n0, '★ 真实 docs/loop_strip_style_bank.csv **未被改动**（{} 条）'.format(n_after))


def t_plan():
    print('\n[2] plan —— 三档分流判定')
    m = load_mod()
    root = os.path.join(ROOT, 'facs')
    items = [dict(no='FA', pool='all', expr='x_one(a)'),
             dict(no='FB', pool='300', expr='x_two(b)')]
    full, qo, sk = m.plan(items, root, True, False)
    chk(len(full) == 2 and not qo and not sk,
        '全部不存在 -> 全部进 full（实得 full={} q={} skip={}）'.format(len(full), len(qo), len(sk)))
    # 造一个只缺 values_q.h5 的场景：拿真实的第一个已落地因子
    import factor_store as FS
    fsd = FS.list_factors(root)
    if fsd:
        nm, p, at = fsd[0]
        expr = str(at.get('expr'))
        pq = os.path.join(os.path.dirname(p), 'values_q.h5')
        bak = pq + '.bak'
        had = os.path.exists(pq)
        if had:
            os.replace(pq, bak)
        try:
            _f, _q, _s = m.plan([dict(no=nm, pool='all', expr=expr)], root, True, False)
            chk(len(_q) == 1 and not _f,
                '值在、副本缺 -> 进 quant_only（**不重算**）')
            _f2, _q2, _s2 = m.plan([dict(no=nm, pool='all', expr=expr)], root, True, True)
            chk(len(_f2) == 1 and not _q2, '--force -> 强制进 full')
        finally:
            if had:
                os.replace(bak, pq)
        _f3, _q3, _s3 = m.plan([dict(no=nm, pool='all', expr=expr)], root, True, False)
        chk(len(_s3) == 1 and not _f3, '两者都在 -> 进 skipped（**不载面板**）')


def main():
    print('=' * 78)
    print('build_facs.py --only-new 回归测试')
    print('=' * 78)
    t_merge()
    t_plan()
    print('\n' + '=' * 78)
    print('通过 {}/{}'.format(OK[0] - OK[1], OK[0]) + ('' if OK[1] else '  ✓ 全部通过'))
    return 1 if OK[1] else 0


if __name__ == '__main__':
    sys.exit(main())
