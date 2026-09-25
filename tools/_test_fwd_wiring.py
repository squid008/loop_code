# -*- coding: utf-8 -*-
"""★★★★★ 守门：**调仓周期 `FWD` 的运行期接线**（2026-09-21 新增 · 前置改造驱动）

★ 为什么需要（用户拍板：(C) 双口径挖掘，前两步 = **前置改造 + (C3)**）：
  `factor_miner.set_fwd()`（注释 `1=日频 5=周频 20=月频` ✓）**早就写好、却全仓零调用** ✗，
  `FWD` 实际写死 5，引擎**没有任何口径入口** ✗。
  更麻烦的是三处"值拷贝 / 默认值固化"陷阱（都会让换口径**静默失效** ✗✗）：
    ① `loop_engine` 原来是 `from factor_miner import FWD` ⇒ **import 时的值拷贝** ✗
       （`set_fwd()` 改的是 fm 的全局、改不到本模块 ⇒ 14 处 `[::FWD]` 切片全部还是 5 ✗）
    ② `def factor_stability(..., fwd=FWD)` ⇒ 默认值在 **def 那一刻**固化 ✗（Python 经典坑 ✓）
    ③ 别的模块若也 `from factor_miner import FWD` ⇒ 同样失联 ✗（本守门扫全仓 ✓）

  本守门钉住：
    ① 全仓**不再有** `from factor_miner import … FWD`（值拷贝 ✗）
    ② `loop_engine` 有 `import factor_miner as _FM` ＋ 模块全局 `FWD = _FM.FWD` ✓
    ③ 引擎有 `--fwd`（默认 0 = 不改 ⇒ **行为逐位不变** ✓）
    ④ `parse_args()` 之后**真的同步**了（`_FM.set_fwd(...)` ＋ `FWD = _FM.FWD` ✓）
    ⑤ `factor_stability` 的 `fwd` 默认是 **None**（不是 FWD ✗）＋ 函数内取**当前**全局 ✓
    ⑥ ★ **动态数值验证**：造一份"每 20 行重复"的矩阵 ⇒ `fwd=20` 时相邻切片行**应完全相同**
       （稳定性 ≈ 1 ✓），`fwd=5` 时**不应相同** ✓ ⇒ 证明切片真的跟随运行期全局 ✓
"""
import io
import inspect
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENG = os.path.join(ROOT, 'engine', 'loop_engine.py')
FAIL = []


def chk(desc, cond, hint=''):
    print('  %s %s' % ('✓' if cond else '✗', desc))
    if not cond:
        FAIL.append(desc + ('（%s）' % hint if hint else ''))


src = io.open(ENG, encoding='utf-8').read()

print('【1】值拷贝陷阱：全仓不许再出现 `from factor_miner import … FWD` ✗')
_bad = []
for dp, _dn, fns in os.walk(os.path.join(ROOT, 'engine')):
    for fn in fns:
        if not fn.endswith('.py'):
            continue
        p = os.path.join(dp, fn)
        try:
            t = io.open(p, encoding='utf-8').read()
        except Exception:                                        # noqa: BLE001
            continue
        for m in re.finditer(r'^from factor_miner import \(?([^)\n]*(?:\n[^)\n]*)*)\)?', t, re.M):
            if re.search(r'\bFWD\b', m.group(1)):
                _bad.append(os.path.basename(p))
chk('engine/ 下没有 `from factor_miner import … FWD`（实 %d 处）' % len(_bad),
    not _bad, '值拷贝 ⇒ set_fwd() 改不到它 ✗（换口径会静默失效 ✓）')

print('\n【2】loop_engine 的接线（模块引用 + 全局 + 入口 + 同步）')
chk('有 `import factor_miner as _FM`', 'import factor_miner as _FM' in src)
chk('模块全局有 `FWD = _FM.FWD`（不是 import 拷贝 ✓）',
    re.search(r'^FWD = _FM\.FWD', src, re.M) is not None)
chk('有 `--fwd` 命令行入口（默认 0 = 不改 ✓）',
    re.search(r"add_argument\('--fwd', type=int, default=0", src) is not None)
chk('`--fwd` 的帮助说明写的是**调仓周期**、`--window` 仍是**样本区间** ✓',
    '调仓周期（交易日）' in src
    and re.search(r"ap\.add_argument\('--window', choices=\['full', 'recent600'\]", src) is not None)
chk('parse_args 之后**真的同步**（set_fwd + 全局赋值 ✓）',
    re.search(r'_args = ap\.parse_args\(\)[\s\S]{0,1400}?_FM\.set_fwd\(int\(_args\.fwd\)\)[\s\S]{0,400}?^\s+FWD = _FM\.FWD',
              src, re.M) is not None)
chk('同步发生在 `run(_args)` **之前**（否则 14 处切片全用旧值 ✗）',
    re.search(r'FWD = _FM\.FWD[\s\S]{0,2000}?run\(_args\)', src) is not None)

# ★★ 2026-09-21（我亲手踩过 ✗）：**缩进吞并**检查 —— 我第一次把同步块插成 0 缩进，
#   结果紧随其后的 `set_mine_pool / set_panel_cache / set_mem_budget / run(_args)`
#   **全被吞进 `if _args.fwd:` 里** ✗ ⇒ 不传 `--fwd` 时**整个 run 都不执行** ✗✗
#   ⇒ 这类"静默 no-op"光靠文本断言不可靠 ⇒ **用 ast 钉结构** ✓
print('\n【2b】★ 缩进结构：`__main__` 块的直接语句里必须**真的**有 run(_args) ✗')
try:
    import ast
    _tree = ast.parse(src)
    _main_if = None
    for _n in _tree.body:
        if isinstance(_n, ast.If):
            _t = ast.unparse(_n.test)
            if '__name__' in _t and '__main__' in _t:
                _main_if = _n
                break
    chk('找得到 `if __name__ == "__main__":` 块', _main_if is not None)
    _direct = [ast.unparse(_s).strip() for _s in (_main_if.body if _main_if else [])]
    chk('`run(_args)` 是 __main__ 块的**直接语句**（没被 `if _args.fwd:` 吞掉 ✗）',
        any(_d.startswith('run(_args)') for _d in _direct),
        '被吞进去 ⇒ 不传 --fwd 时整个 run 都不执行 ✗✗（静默 no-op ✓）')
    chk('`set_panel_cache(...)` / `set_mem_budget(...)` 也是直接语句 ✓',
        any(_d.startswith('set_panel_cache(') for _d in _direct)
        and any(_d.startswith('set_mem_budget(') for _d in _direct))
except Exception as e:                                           # noqa: BLE001
    chk('能做 ast 结构检查', False, '%s: %s' % (type(e).__name__, str(e)[:90]))

print('\n【3】`factor_stability` 的 def 时固化陷阱')
chk('签名里 `fwd=None`（不是 `fwd=FWD` ✗）',
    re.search(r'def factor_stability\(V, dates=None, start=START, fwd=None\)', src) is not None)
chk('函数内取**当前**全局（`fwd = FWD if fwd is None else fwd` ✓）',
    'fwd = FWD if fwd is None else fwd' in src)

print('\n【4】动态数值验证（切片真的跟随运行期全局 ✓）')
try:
    sys.path.insert(0, os.path.join(ROOT, 'engine'))
    import numpy as np
    import factor_miner as FM
    import loop_engine as LE
    chk('默认 FWD = 5（⇒ 不传 --fwd 时行为与改造前逐位一致 ✓）', LE.FWD == 5)
    chk('factor_stability 的 fwd 默认值就是 None（def 时不再固化 ✓）',
        inspect.signature(LE.factor_stability).parameters['fwd'].default is None)

    # 造"每 20 行重复"的矩阵：fwd=20 时切片里相邻两行**完全相同** ⇒ 稳定性 = 1 ✓
    # ⚠ 列数必须 ≥ 50 ✗ —— `factor_stability` 里有 `if m.sum() < 50: continue`（有效样本门槛 ✓），
    #   我第一次只造了 40 列 ⇒ 每对都被跳过 ⇒ 返回 **nan** ✗（测试自身的数据错 ✓）
    rng = np.random.default_rng(7)
    base = rng.normal(size=(20, 80))
    V = np.tile(base, (10, 1))                     # 200 行 × 80 列；行 i 与行 i+20 相同 ✓
    _old = FM.FWD
    FM.set_fwd(20)
    LE.FWD = FM.FWD                                # 模拟 main 里的同步 ✓
    s20 = LE.factor_stability(V)
    FM.set_fwd(5)
    LE.FWD = FM.FWD
    s5 = LE.factor_stability(V)
    FM.set_fwd(_old)
    LE.FWD = FM.FWD                                # 复原，别污染后续 ✓
    chk('fwd=20 ⇒ 稳定性 ≈ 1.0（实 %.4f）' % s20, abs(s20 - 1.0) < 1e-9,
        '切片没跟随全局 ⇒ 说明仍是 import 时固化的 5 ✗')
    chk('fwd=5  ⇒ 稳定性明显 < 1（实 %.4f）' % s5, s5 < 0.999)
    chk('两个口径结果**不同**（证明确实在按运行期值切 ✓）', abs(s20 - s5) > 0.01)
except Exception as e:                                           # noqa: BLE001
    chk('能 import loop_engine 并做数值验证', False,
        '%s: %s' % (type(e).__name__, str(e)[:110]))

print()
print('★ 全过 ✓ FWD 已是**运行期参数**（默认 5 ⇒ 行为不变 ✓；--fwd 20 ⇒ 双口径可用 ✓）'
      if not FAIL else '✗ 有 %d 项没过：\n  - %s' % (len(FAIL), '\n  - '.join(FAIL)))
sys.exit(1 if FAIL else 0)
