# -*- coding: utf-8 -*-
"""守门：生产参数**单一事实源**（`engine/loop_params.py`）不漂移。

为什么必须有（2026-10-21，用户要求前端可改参数）：
  前端展示"默认值"来自 `PARAM_SPECS[*].default`，而 `run_tracks` 真正用命令行的是
  `_LEGACY_EXTRA`（代码里那份）⇒ **两处一旦不一致，页面就会显示错的默认值** ✗
  本守门把这件事钉死：
    [1] `PARAM_SPECS` 里每个出现在 `DEFAULT_EXTRA` 的键，default 必须与它一致
    [2] `merge_extra({})` 必须逐字等于 `DEFAULT_EXTRA`
    [3] 覆盖项只替换、不追加重复 flag
    [4] `validate` 拒绝越界 / 未知键（未知键进 warnings，不静默生效）
    [5] 危险等级 1/2 的项必须有说明（页面靠它提示）
    [6] save/load 往返（临时文件）
用法: python tools/_test_loop_params.py
"""
import io
import os
import sys
import tempfile

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'engine'))

import loop_params as LP  # noqa: E402

OK = BAD = 0


def chk(cond, msg):
    global OK, BAD
    if cond:
        OK += 1
        print('  [OK ] %s' % msg)
    else:
        BAD += 1
        print('  [FAIL] %s' % msg)


def main():
    print('=' * 78)
    print('[1] PARAM_SPECS.default 必须与 DEFAULT_EXTRA 一致（防"页面显示值"漂移）')
    print('=' * 78)
    spec = {s['key']: s for s in LP.PARAM_SPECS}
    bad = []
    for item in LP.DEFAULT_EXTRA:
        flag = item.split('=', 1)[0]
        key = flag.lstrip('-').replace('-', '_')
        s = spec.get(key)
        if s is None:
            bad.append('%s 在 DEFAULT_EXTRA 里但不在 PARAM_SPECS' % key)
            continue
        if '=' in item:
            raw = item.split('=', 1)[1]
            dv = s['default']
            if s['type'] == 'float':
                same = abs(float(raw) - float(dv)) < 1e-12
            elif s['type'] == 'int':
                same = int(raw) == int(dv)
            else:
                same = str(raw) == str(dv)
            if not same:
                bad.append('%s: DEFAULT_EXTRA=%s 但 default=%s' % (key, raw, dv))
        else:
            if s['type'] != 'bool' or not s['default']:
                bad.append('%s: 开关型在 DEFAULT_EXTRA 里但 default 不是 True' % key)
    chk(not bad, '全部一致（%d 项）' % len(LP.DEFAULT_EXTRA) if not bad else '不一致: %s' % bad)

    print('=' * 78)
    print('[2] merge_extra({{}}) 必须逐字等于 DEFAULT_EXTRA')
    print('=' * 78)
    chk(LP.merge_extra({}) == LP.DEFAULT_EXTRA, '无覆盖时与默认逐字相同')

    print('=' * 78)
    print('[3] 覆盖只替换、不重复')
    print('=' * 78)
    m = LP.merge_extra({'min_strip_calmar': 0.2, 'n': 700})
    n_cal = sum(1 for x in m if x.startswith('--min_strip_calmar='))
    n_n = sum(1 for x in m if x.startswith('--n='))
    chk(n_cal == 1 and '--min_strip_calmar=0.2' in m, 'min_strip_calmar 只出现一次且已替换')
    chk(n_n == 1 and '--n=700' in m, 'n（默认 extra 里没有）被追加且只一次')

    print('=' * 78)
    print('[4] validate 拒绝越界 / 未知键')
    print('=' * 78)
    clean, errs = LP.validate({'n': 99999, 'bogus': 1})
    chk('n' not in clean, '越界被拒（n=99999）')
    chk(any('bogus' in e for e in errs), '未知键进 warnings')
    clean2, errs2 = LP.validate({'score_mode': 'bad'})
    chk('score_mode' not in clean2, '枚举越界被拒')
    clean3, _ = LP.validate({'n': 500, 'score_mode': 'mono_n'})
    chk(clean3 == {'n': 500, 'score_mode': 'mono_n'}, '合法值原样通过')

    print('=' * 78)
    print('[5] 危险项（danger 1/2）必须有说明')
    print('=' * 78)
    miss = [s['key'] for s in LP.PARAM_SPECS if s.get('danger', 0) >= 1 and not s.get('desc')]
    chk(not miss, '全部有 desc' if not miss else '缺说明: %s' % miss)

    print('=' * 78)
    print('[6] save/load 往返（临时文件）')
    print('=' * 78)
    tmp = os.path.join(tempfile.mkdtemp(), 'params.json')
    n = LP.save_overrides({'n': 600, 'min_strip_calmar': 0.25}, path=tmp)
    got = LP.load_overrides(path=tmp)
    chk(n == 2 and got.get('n') == 600 and abs(got.get('min_strip_calmar') - 0.25) < 1e-12,
        '写读往返一致')
    chk(LP.load_overrides(path=os.path.join(tempfile.mkdtemp(), 'nope.json')) == {},
        '文件不存在 -> {}（不抛）')

    print('=' * 78)
    print('通过 %d/%d' % (OK, OK + BAD))
    return 0 if BAD == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
