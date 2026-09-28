# -*- coding: utf-8 -*-
"""ab_generation.py —— **同 seed A/B**：把"改前 / 改后产物逐字对照"做成一条命令。

## 背景（R7 铁律的自动化）

`docs/maintainability.md` R7：**搬函数/拆模块后必须跑「名字解析检查 + 同 seed A/B」**，
缺一不可 —— 2026-09-26 `v1.23.0` 就是**只跑 `py_compile` + 全量回归**、漏了 A/B，
结果发版后重启挖掘**第一批就崩**（4 处 `NameError` + 1 处静默口径污染 ✗，用户白等一晚）。

* 「名字解析检查」= `tools/_test_undefined_names.py` ✓（已有常驻守门）
* 「同 seed A/B」= **本工具** ✓ —— 它在**同一份代码**上真跑一代并保存产物快照，
  于是"改前跑一次、改后跑一次、`--diff` 对照"就能证明**行为逐字未变** ✓

> ⚠ 与 `tools/_test_gen_determinism.py` 的分工（别混 ✗）：
> · `_test_gen_determinism` 只跑 `--gen_only`（**不跑 L1/L2**）⇒ 快、只查"生成段有没有随机性漂移" ✓
> · 本工具**真跑完整 L1+L2**（含剥风格/池内指标/副口径）⇒ 慢（~3 分钟），但覆盖**全部**产物 ✓

## 用法

    # ① 改动前：存一份基线
    python tools/ab_generation.py --out ai_test/_ab/base

    # ② 改代码 …

    # ③ 改动后：再存一份，然后对照
    python tools/ab_generation.py --out ai_test/_ab/after
    python tools/ab_generation.py --diff ai_test/_ab/base ai_test/_ab/after

## 安全（与端到端守门同源）

· **挖掘在跑时拒绝执行** ✗（本工具会真写池的轨迹 ✓）
· 池 = `--pool`（默认 `50`，最小池 ⇒ 最便宜 ✓）；跑前**备份**、跑完**还原**并**逐字节校验** ✓
"""
import argparse
import io
import os
import pickle
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _pool_traj as T                                                 # noqa: E402

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
FAIL = []


def chk(desc, cond, hint=''):
    print('  %s %s' % ('✓' if cond else '✗', desc))
    if not cond:
        FAIL.append(desc + ('（%s）' % hint if hint else ''))


def do_out(a):
    files = T.pool_files('_' + a.pool)
    busy = T.mining_busy()
    print('=' * 96)
    print('A/B 快照：池 %s · gen %d · n=%d · l2=%d · seed=%d' %
          (a.pool, a.gen, a.n, a.l2, a.seed))
    print('=' * 96)
    if busy:
        print('✗ 挖掘正在跑（%s）⇒ 拒绝执行（会真写池轨迹 ✗）' % '; '.join(busy))
        return 2
    bak = os.path.join(T.ROOT, 'ai_test', '_ab_bak')
    print('\n【1】备份 %d 个轨迹文件 -> %s' % (T.backup(files, bak), os.path.relpath(bak, T.ROOT)))
    before = T.snap(files)
    try:
        print('【2】真跑一代 …（生产同款 flag + 最小规模 ✓）')
        rc, out, err, dt = T.run_generation(a.pool, a.gen, n=a.n, l2=a.l2, seed=a.seed,
                                           timeout=a.timeout or None)   # ★ 0 ⇒ 交给默认/环境变量 ✓
        print('    用时 %.0fs · 退出码=%d' % (dt, rc))
        os.makedirs(a.out, exist_ok=True)
        io.open(os.path.join(a.out, 'stdout.log'), 'w', encoding='utf-8').write(out + '\n' + err)
        n = 0
        for p in files:
            if os.path.exists(p):
                shutil.copy2(p, os.path.join(a.out, os.path.basename(p)))
                n += 1
        print('    产物 %d 个 -> %s' % (n, a.out))
        chk('退出码 0', rc == 0, '尾部: %s' % out.strip().splitlines()[-1][:120] if out.strip() else '')
        chk('无 Traceback/NameError',
            'Traceback' not in out + err and 'NameError' not in out + err)
        # ⚠ 不能要求 factor_library 一定变：小规模跑常常"入库 0"（真实门槛 ✓）⇒ 只看这三样 ✓
        chk('产物真的变了（state / archive / journal 各 1 处 ✓）',
            all(T.sha(files[i]) != before[files[i]] for i in (0, 1, 3)),
            'state=%s archive=%s journal=%s' % tuple(
                T.sha(files[i]) != before[files[i]] for i in (0, 1, 3)))
    finally:
        print('【3】还原池 %s 的轨迹' % a.pool)
        bad = T.restore(files, bak)
        after = T.snap(files)
        diff = [os.path.basename(p) for p in files if before.get(p) != after.get(p)]
        chk('★ 还原后与跑前逐字节一致', not diff and not bad, '仍不一致: %r %r' % (diff, bad))
        shutil.rmtree(bak, ignore_errors=True)
    print()
    return 1 if FAIL else 0


def _load_state(path):
    """读 state（要把 engine/ 放进 path 才能解开 Node ✓）"""
    sys.path.insert(0, os.path.join(T.ROOT, 'engine'))
    import loop_expr                                                # noqa: F401
    with open(path, 'rb') as f:
        return pickle.load(f)


def _flat_equal(a, b, prefix=''):
    """递归比较两个对象，返回差异描述清单（最多 12 条）✓"""
    out = []
    if type(a) is not type(b):
        return ['%s: 类型 %s != %s' % (prefix, type(a).__name__, type(b).__name__)]
    if isinstance(a, dict):
        ka, kb = set(a), set(b)
        if ka != kb:
            out.append('%s: 键不同 只A=%r 只B=%r' % (prefix, sorted(ka - kb)[:6], sorted(kb - ka)[:6]))
        for k in sorted(ka & kb):
            out += _flat_equal(a[k], b[k], '%s[%r]' % (prefix, k))
    elif isinstance(a, (list, tuple)):
        if len(a) != len(b):
            out.append('%s: 长度 %d != %d' % (prefix, len(a), len(b)))
        else:
            for i, (x, y) in enumerate(zip(a, b)):
                out += _flat_equal(x, y, '%s[%d]' % (prefix, i))
    else:
        try:
            if isinstance(a, (int, float, str, bool, bytes, type(None))):
                same = bool(a == b)
                if not same and isinstance(a, float) and isinstance(b, float) \
                        and a != a and b != b:
                    same = True                       # NaN == NaN（按"都是 NaN"算同 ✓）
            else:
                # ★ Node 之类**没有 `__eq__`** ⇒ `==` 退化成身份比较 ✗
                #   （自检时实测：两条内容**完全相同**的种子被判成不同 ✗）
                #   ⇒ 这类对象按**表达式文本**比 ✓
                same = str(a) == str(b)
        except Exception:
            same = repr(a) == repr(b)
        if not same:
            out.append('%s: %r != %r' % (prefix, str(a)[:60], str(b)[:60]))
    return out[:12]


def do_diff(a):
    print('=' * 96)
    print('A/B 对照：%s  ←→  %s' % (a.diff[0], a.diff[1]))
    print('=' * 96)
    A, B = a.diff
    # ★ 2026-09-28：把"必然不同"的噪声归一化**提到产物比对之前** ✓ —— 因为 **journal 这类文本产物
    #   也要用它** ✗（原先只有 stdout 段做归一化 ⇒ journal 一加时间戳就会**每次误报差异** ✗✗）
    import re
    #   剔掉：人类可读耗时（`1h59m2s` ✓，复合格式放最前，否则短的会把长的咬碎 ✗）· 旧式 `\d+s` ·
    #   日期 `YYYY-MM-DD` · 时刻 `HH:MM:SS` ✓（后两者自 2026-09-2x 起就在用 ✓）
    noise = re.compile(r'\d+h\d+m\d+s|\d+m\d+s|\d+(\.\d+)?s\b'
                       r'|\d{4}-\d{2}-\d{2}|\d{2}:\d{2}:\d{2}')
    names = [os.path.basename(p) for p in T.pool_files('_' + a.pool)]
    for nm in names:
        pa, pb = os.path.join(A, nm), os.path.join(B, nm)
        if not (os.path.exists(pa) and os.path.exists(pb)):
            print('  %-28s (缺文件，跳过)' % nm)
            continue
        ha, hb = T.sha(pa), T.sha(pb)
        head = nm.endswith('.pkl')
        if ha == hb:
            print('  %-28s ✓ 逐字节相同' % nm)
            continue
        if head:
            try:
                sa, sb = _load_state(pa), _load_state(pb)
                d = _flat_equal(sa, sb)
                print('  %-28s ✗ 字节不同；**逐字段**差异 %d 处：' % (nm, len(d)))
                for x in d:
                    print('        %s' % x)
                if not d:
                    print('        （字段全同 ⇒ 差异只在 pickle 序列化层，非行为差异 ✓）')
            except Exception as e:
                print('  %-28s ✗ 字节不同，且解不开: %r' % (nm, e))
            continue
        # ★ 文本产物（journal/archive/library …）**先按 noise 归一化再比** ✓
        #   理由：时间戳与耗时是**记录性**字段，不是行为 ✓ ⇒ 不该被报成差异 ✗
        la = [noise.sub('<T>', l)
              for l in io.open(pa, encoding='utf-8', errors='replace').read().splitlines()]
        lb = [noise.sub('<T>', l)
              for l in io.open(pb, encoding='utf-8', errors='replace').read().splitlines()]
        if la == lb:
            print('  %-28s ✓ 归一化后逐行相同（仅时间戳/耗时差异 ✓）' % nm)
            continue
        print('  %-28s ✗ 不同（**已归一化**）行数 %d vs %d' % (nm, len(la), len(lb)))
        shown = 0
        for i, (x, y) in enumerate(zip(la, lb)):
            if x != y:
                print('        #%d A=%s' % (i, x[:110]))
                print('            B=%s' % y[:110])
                shown += 1
                if shown >= 4:
                    break

    # stdout 对照（剔耗时/时刻 ✓）—— ★ `noise` 已在**产物比对之前**定义 ✓（见上 ✓），此处复用 ✓
    #   （历史注释：自检时实测，只写「耗时\s*\d+s」会漏掉「用时」与括号里的 `3.27s/候选` ⇒ 假差异 ✗）
    sa = [noise.sub('<T>', l).strip() for l in
          io.open(os.path.join(A, 'stdout.log'), encoding='utf-8', errors='replace')
          if l.strip()]
    sb = [noise.sub('<T>', l).strip() for l in
          io.open(os.path.join(B, 'stdout.log'), encoding='utf-8', errors='replace')
          if l.strip()]
    d = [(i, x, y) for i, (x, y) in enumerate(zip(sa, sb)) if x != y]
    print('  %-28s %s（行数 %d vs %d，差异 %d 行）'
          % ('stdout.log', '✓ 逐行相同' if (not d and len(sa) == len(sb)) else '✗ 不同',
             len(sa), len(sb), len(d)))
    for i, x, y in d[:6]:
        print('        #%d A=%s' % (i, x[:110]))
        print('            B=%s' % y[:110])
    print()
    if d or len(sa) != len(sb):
        FAIL.append('stdout 不一致')
    return 1 if FAIL else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='', help='跑一代并把产物存到这个目录')
    ap.add_argument('--diff', nargs=2, default=None, metavar=('A', 'B'), help='对照两个快照目录')
    ap.add_argument('--pool', default='50', help='池（默认 50，最小池 ✓）')
    ap.add_argument('--gen', type=int, default=9999, help='代号（默认 9999，远离真实进度 ✓）')
    ap.add_argument('--n', type=int, default=12)
    ap.add_argument('--l2', type=int, default=2)
    ap.add_argument('--seed', type=int, default=777)
    # ★ 2026-09-28：超时预算（0 = 用默认 900s / `LOOP_AB_TIMEOUT` ✓）——
    #   机器被别的项目占用时一代可能 >900s ⇒ 用 `--timeout 10800`（或环境变量）放宽 ✓，
    #   否则会看到 `退出码=-9`（**超时，不是行为差异** ✗）。
    ap.add_argument('--timeout', type=int, default=0)
    a = ap.parse_args()
    if a.diff:
        return do_diff(a)
    if a.out:
        return do_out(a)
    ap.print_help()
    return 0


if __name__ == '__main__':
    sys.exit(main())
