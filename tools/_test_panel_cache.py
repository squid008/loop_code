# -*- coding: utf-8 -*-
"""★★★ 面板只读缓存 回归测试（2026-09-16 新增；命名 `_test_*` ⇒ 进全量回归）。

为什么要有它（这个功能的**固有风险**）：
  共享面板一旦"吃错东西"，后果不是崩溃而是**静默的数值漂移** ⇒
  只测"能跑通"**毫无意义**，必须证明「**缓存读出来的**」与「**现场构造的**」**逐位相同** ✓

断言分两类：

【A 静态/廉价】**总是跑**（毫秒级，用合成缓存，不载真面板）：
  A1 缓存缺失        ⇒ `load()` 抛 CacheError（**不静默降级**）
  A2 构造代码指纹不符 ⇒ 抛 CacheError（防"改了构造逻辑还用旧面板"）
  A3 来源数据指纹不符 ⇒ 抛 CacheError（防"数据更新了还用旧面板"）
  A4 只读保护        ⇒ 缓存的数组 `writeable is False`，写入**抛异常**（fail-loud）
  A5 `set_panel_cache` 非法取值 ⇒ SystemExit
  A6 `save/load` 往返  ⇒ 合成面板逐位一致、manifest 字段齐全

【B 逐位对拍】真实缓存**存在时**才跑（缺失则 SKIP，**不自动构建**）：
  B1 `load()` 的 B / close / dates / cols 与 `_build_panel_fresh()` **逐字段逐位相同**（含 NaN）
  B2 dtype/shape 必须完全一致（**降 dtype 会静默改变 L2 结果**）
"""
import io
import json
import os
import shutil
import sys
import tempfile

import numpy as np

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'engine'))

import loop_engine as LE          # noqa: E402
import panel_cache as PC          # noqa: E402

FAIL = []


def chk(desc, cond, hint=''):
    print('  %s %s' % ('[OK]' if cond else '[FAIL]', desc))
    if not cond:
        FAIL.append(desc + ('（%s）' % hint if hint else ''))


def raises(fn, exc=Exception):
    try:
        fn()
    except exc:
        return True
    except Exception:
        return False
    return False


def same_array(a, b, step=256):
    """逐位比较（分块，避免一次性 tobytes 占内存）；NaN 视为相等。"""
    a, b = np.asarray(a), np.asarray(b)
    if a.shape != b.shape or a.dtype != b.dtype:
        return False, 'shape/dtype 不同（%s %s vs %s %s）' % (a.shape, a.dtype, b.shape, b.dtype)
    eq_nan = bool(np.issubdtype(a.dtype, np.floating))
    for i in range(0, a.shape[0], step):
        x, y = a[i:i + step], b[i:i + step]
        if not np.array_equal(x, y, equal_nan=eq_nan):
            return False, '第 %d 行起不同' % i
    return True, ''


def main():
    sha = PC.code_sha1(LE._build_panel_fresh)
    tmp = tempfile.mkdtemp(prefix='_panel_cache_test_')
    try:
        print('=' * 84)
        print('【A】静态/廉价断言（合成缓存，不载真面板）')
        print('=' * 84)
        # A5 非法取值
        chk('A5 set_panel_cache 非法取值 ⇒ SystemExit',
            raises(lambda: LE.set_panel_cache('bogus'), SystemExit))
        chk('A5b set_panel_cache 合法取值可用（off/use/build）',
            LE.set_panel_cache('off') == 'off'
            and LE.set_panel_cache('use') == 'use'
            and LE.set_panel_cache('build') == 'build'
            and LE.set_panel_cache('off') == 'off')

        # A1 缺失
        chk('A1 缓存缺失 ⇒ CacheError（不静默降级）',
            raises(lambda: PC.load(sha, os.path.join(tmp, 'nope')), PC.CacheError))

        # A6 合成 save/load 往返
        B = {'close': np.array([[1., np.nan], [3., 4.]], dtype=np.float32),
             'turnover': np.arange(6, dtype=np.float32).reshape(3, 2)}
        dates = np.array([20200101, 20200102, 20200103], dtype=np.int64)
        cols = ['000001.XSHE', '600000.XSHG']
        cv = np.array([[1.5, 2.5], [3.5, np.nan], [5.5, 6.5]], dtype=np.float64)
        d1 = os.path.join(tmp, 'c1')
        PC.save(B, dates, cols, cv, sha, cache_dir=d1, quiet=True)
        B2, dt2, cl2, cv2, man2 = PC.load(sha, d1)
        ok1, _ = same_array(B2['close'], B['close'])
        ok2, _ = same_array(B2['turnover'], B['turnover'])
        ok3, _ = same_array(cv2, cv)
        chk('A6a save/load 往返逐位一致（含 NaN）', ok1 and ok2 and ok3)
        chk('A6b dates/cols 往返一致',
            np.array_equal(np.asarray(dt2), dates) and list(cl2) == cols)
        chk('A6c manifest 记录字段/dtype/指纹/代码 SHA1',
            set(man2['fields']) == set(B) and man2['code_sha1'] == sha
            and 'src' in man2 and man2['fields']['close']['dtype'] == 'float32')

        # A4 只读保护
        chk('A4a 缓存数组不可写（writeable=False）',
            all(not np.asarray(v).flags.writeable for v in B2.values()))

        def _write():
            np.asarray(B2['close'])[0, 0] = 9.9

        chk('A4b 对缓存数组写入 ⇒ 抛异常（fail-loud，不会静默污染共享面板）',
            raises(_write, ValueError), '若这里不抛，说明共享面板可能被就地改坏')

        # A2 代码指纹不符
        d2 = os.path.join(tmp, 'c2')
        PC.save(B, dates, cols, cv, sha, cache_dir=d2, quiet=True)
        _edit_manifest(os.path.join(d2, PC.MANIFEST), code_sha1='deadbeef')
        chk('A2 构造代码指纹不符 ⇒ CacheError（防"改了构造逻辑仍用旧面板"）',
            raises(lambda: PC.load(sha, d2), PC.CacheError))

        # A3 来源数据指纹不符
        d3 = os.path.join(tmp, 'c3')
        PC.save(B, dates, cols, cv, sha, cache_dir=d3, quiet=True)
        mf = os.path.join(d3, PC.MANIFEST)
        man = json.load(io.open(mf, encoding='utf-8'))
        src = dict(man['src'])
        k0 = sorted(src)[0]
        src[k0] = [1, 2]                       # 伪造"来源文件变了"
        _edit_manifest(mf, src=src)
        chk('A3 来源数据指纹不符 ⇒ CacheError（防"数据更新了还用旧面板"）',
            raises(lambda: PC.load(sha, d3), PC.CacheError))

        # A6d 形状不符
        d4 = os.path.join(tmp, 'c4')
        PC.save(B, dates, cols, cv, sha, cache_dir=d4, quiet=True)
        man = json.load(io.open(os.path.join(d4, PC.MANIFEST), encoding='utf-8'))
        man['fields']['close']['shape'] = [99, 99]
        with io.open(os.path.join(d4, PC.MANIFEST), 'w', encoding='utf-8') as f:
            json.dump(man, f, ensure_ascii=False, indent=1, sort_keys=True)
        chk('A6d 字段形状与 manifest 不符 ⇒ CacheError',
            raises(lambda: PC.load(sha, d4), PC.CacheError))

        print()
        print('=' * 84)
        print('【B】与"现场构造"逐位对拍（真实缓存存在时才跑）')
        print('=' * 84)
        ok, msg = PC.status(sha)
        if not ok:
            print('  [SKIP] 真实缓存不可用（%s）' % msg.splitlines()[0])
            print('         ⇒ 本项跳过（**测试不自动构建**；要跑请先 '
                  'python tools/build_panel_cache.py）')
        else:
            print('  %s' % msg)
            Bc, datesc, colsc, cvc, man = PC.load(sha)
            Bf, datesf, colsf, closef = LE._build_panel_fresh()
            chk('B1a 字段集合一致（%d 个）' % len(Bf), set(Bc) == set(Bf),
                '缓存=%d 现场=%d' % (len(Bc), len(Bf)))
            bad = []
            for k in sorted(Bf):
                okk, why = same_array(Bc[k], Bf[k])
                if not okk:
                    bad.append('%s: %s' % (k, why))
            chk('B1b 每个字段**逐位相同**（含 NaN）', not bad, '; '.join(bad[:4]))
            okk, why = same_array(cvc, closef.values)
            chk('B1c close（float64）逐位相同', okk, why)
            chk('B2a dates 完全一致', np.array_equal(np.asarray(datesc), np.asarray(datesf)))
            chk('B2b cols 完全一致', list(colsc) == list(colsf))
            chk('B2c dtype 未被降级（close=float64, 面板=float32）',
                str(np.asarray(cvc).dtype) == 'float64'
                and all(str(np.asarray(v).dtype) == 'float32' for v in Bc.values()),
                '降 dtype 会静默改变 L2 结果')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    if FAIL:
        print('★★ 面板缓存测试失败 %d 项：' % len(FAIL))
        for f in FAIL:
            print('   [FAIL] %s' % f)
        return 1
    print('★★ 面板缓存测试全部通过')
    return 0


def _edit_manifest(path, **kw):
    man = json.load(io.open(path, encoding='utf-8'))
    man.update(kw)
    with io.open(path, 'w', encoding='utf-8') as f:
        json.dump(man, f, ensure_ascii=False, indent=1, sort_keys=True)


if __name__ == '__main__':
    sys.exit(main())
