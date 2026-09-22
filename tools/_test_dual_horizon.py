# -*- coding: utf-8 -*-
"""★★★★★ 守门：**引擎双口径评估（(乙)）**（2026-09-22 · v1.21.29 新增）

★ 为什么需要（今天血的教训 ✓ 全是"静默出错"那类 ✗）：
  1. **`FWD` 是模块全局** ⇒ 副口径求值若不在 `finally` 复原 ✗ ⇒ **后面所有候选都按副口径评估** ✓
     而且**不报错** ✓（★ 本守门钉死"必须 try/finally 复原" ✓）
  2. **函数内裸写 `FWD = …`** ✗ ⇒ 没有 `global` 声明 ⇒ Python 当**局部变量** ⇒ 既改不到全局、
     又会 `UnboundLocalError` ✗（我第一版就是这么写的 ✓ 本守门静态扫出来 ✓）
  3. **`ok2/rr2/strip2` 必须在 `try` 之前初始化** ✗ ⇒ 中途异常跳到 except ⇒ `NameError` ✓
  4. **archive 加列必须"只在开启时"** ✗ ⇒ 否则关着也改表头 ⇒ 与改造前不再"逐字一致" ✓
  5. **`_save_state` 必须收到副口径的两个字典** ✗ ⇒ 否则副口径入选时才 `NameError`（**延迟报错** ✓）
  6. **动态铁证**：`evaluate_real` 在 `FWD=20` 与 `FWD=5` 下必须给出**不同的**卡玛/期数 ✓
     —— 证明"切全局 ⇒ 真的换了口径" ✓（而不是像 `factor_stability` 那样在 def 时固化 ✗）
"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ROOT = r'd:\loop_code'
ENG = os.path.join(ROOT, 'engine', 'loop_engine.py')
FAIL = []


def chk(desc, cond, hint=''):
    print('  %s %s' % ('✓' if cond else '✗', desc))
    if not cond:
        FAIL.append(desc + ('（%s）' % hint if hint else ''))


src = io.open(ENG, encoding='utf-8').read()

print('【1】命令行入口（默认关 ⇒ 行为不变 ✓）')
chk('有 `--dual_fwd`（默认 0 = 关 ✓）',
    re.search(r"add_argument\('--dual_fwd', type=int, default=0", src) is not None)
chk('有副口径门槛 `--min_calmar2` / `--min_sharpe2` / `--min_ic2`',
    all(re.search(r"add_argument\('%s'" % k, src) for k in
        ('--min_calmar2', '--min_sharpe2', '--min_ic2')))

print('\n【2】★ 全局口径切换：切了必须复原（否则静默污染后续候选 ✗）')
chk('副口径求值在 `args.dual_fwd` 分支里 ✓',
    re.search(r'if args\.dual_fwd and rr is not None:', src) is not None)
chk('★ 用 `_FM.set_fwd(int(args.dual_fwd))` 切（切的是 factor_miner 的全局 ✓）',
    '_FM.set_fwd(int(args.dual_fwd))' in src)
chk('★ **有 finally 复原**（`_FM.set_fwd(int(FWD))`）',
    re.search(r'finally:\s*\n\s*#[^\n]*\n(\s*#[^\n]*\n)*\s*_FM\.set_fwd\(int\(FWD\)\)', src) is not None,
    '没有 finally ⇒ 中途异常会让后续候选全按副口径评估 ✗ 且不报错 ✓')

print('\n【3】★ 不许在**函数体内**裸写 `FWD = …`（无 global 声明 = 局部变量陷阱 ✗）')
# ⚠ 必须用 ast 判"在不在函数里" ✗ —— 我第一版用"缩进就报"⇒ 把 `if __name__ == '__main__':`
#   块里的**模块级**赋值 `    FWD = _FM.FWD` 误报 ✗（那是合法的模块全局 ✓）
_bad = []
try:
    import ast
    _tree = ast.parse(src)
    for _fn in [n for n in ast.walk(_tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
        _glob = {g for st in ast.walk(_fn) if isinstance(st, ast.Global) for g in st.names}
        for _st in ast.walk(_fn):
            if isinstance(_st, ast.Assign) and 'FWD' not in _glob:
                for _t in _st.targets:
                    if isinstance(_t, ast.Name) and _t.id == 'FWD':
                        _bad.append((_fn.name, _st.lineno))
except Exception as e:                                           # noqa: BLE001
    FAIL.append('ast 解析失败: %s' % e)
chk('函数体内没有 `FWD = …` 赋值（有 `global FWD` 声明的除外 ✓）',
    not _bad, '位置 %s ⇒ 会变局部变量 + UnboundLocalError ✗' % _bad)

print('\n【4】★ `ok2/rr2/strip2` 必须在 try 之前初始化（异常路径不留 NameError ✗）')
chk('循环内有 `rr2, strip2, ok2 = None, None, False` 预置 ✓',
    re.search(r'rr2, strip2, ok2 = None, None, False', src) is not None)

print('\n【5】★ 合并语义 + archive 加列"只在开启时"')
chk('★ 双口径合并 = **任一通过即入库**（`if args.dual_fwd and ok2 and not ok:` ✓）',
    re.search(r'if args\.dual_fwd and ok2 and not ok:', src) is not None)
chk('★ archive 副口径列是**条件写入**（`if args.dual_fwd else {}` ✓）',
    re.search(r'passed2=bool\(ok2\)\) if args\.dual_fwd else \{\}', src) is not None,
    '无条件加列 ⇒ 关着也改表头 ⇒ 与改造前不再逐字一致 ✗')

print('\n【6】★ 文档按口径分组落（`_save_state` 收下两个字典 ✓ 否则延迟 NameError ✗）')
chk('`_save_state` 签名新增 `_strip2_by_expr=None, _hzn2_by_expr=None` ✓',
    re.search(r'_strip2_by_expr=None, _hzn2_by_expr=None\):', src) is not None)
chk('调用点**真的传了**这两个字典 ✓',
    re.search(r'_strip2_by_expr, _hzn2_by_expr\)', src) is not None)
_m2 = re.search(r'strip_grades=_strip2_by_expr,[\s\S]{0,160}?horizon=int\(args\.dual_fwd\)\)', src)
chk('★ 副口径组用 `horizon=int(args.dual_fwd)` 落文档 ✓（且与 `_strip2_by_expr` 同一次调用 ✓）',
    _m2 is not None,
    '两处必须同一次 `_lib_sync` 调用 ⇒ 否则文档里写的是**另一个口径**的剥风格数字 ✗')
chk('主口径组仍**不带** horizon（默认 5 日 ⇒ 历史写法不变 ✓）',
    re.search(r'pool_tags=_tag_by_expr, strip_grades=_strip_by_expr\)', src) is not None)

print('\n【7】★ 动态铁证：切全局 ⇒ 真的换了口径（不是 def 时固化 ✗）')
try:
    sys.path.insert(0, os.path.join(ROOT, 'tools'))
    sys.path.insert(0, os.path.join(ROOT, 'engine'))
    import numpy as np
    import pandas as pd
    import build_facs as BF
    import factor_miner as FM
    import loop_engine as LE
    from factor_miner import evaluate_real, cs_rank

    BF._prep_main()
    LE.set_panel_cache('use')
    bf = LE.base_fields()
    B, dates, cols, close = bf['B'], bf['dates'], bf['cols'], bf['close']
    _cap = LE.LLM_MAX_SIZE
    LE.LLM_MAX_SIZE = 10 ** 9
    try:
        nd = LE.parse_expr('ts_mean20(overnight)')
    finally:
        LE.LLM_MAX_SIZE = _cap
    v = LE.eval_expr(nd, B, {})
    f = cs_rank(pd.DataFrame(v, index=dates, columns=cols).astype('float64'))
    _old = FM.FWD
    FM.set_fwd(5)
    r5 = evaluate_real(f, close, 'qa5', cost=0.004, window='full')
    FM.set_fwd(20)
    r20 = evaluate_real(f, close, 'qa20', cost=0.004, window='full')
    FM.set_fwd(_old)
    chk('FWD=5 与 FWD=20 的 `n_rebal` 明显不同（实 %s vs %s ⇒ 口径确实换了 ✓）'
        % (r5.get('n_rebal'), r20.get('n_rebal')),
        r5.get('n_rebal') is not None and r20.get('n_rebal') is not None
        and r20['n_rebal'] < r5['n_rebal'] * 0.5)
    chk('两者卡玛不同（实 %.3f vs %.3f ✓）' % (r5['calmar'], r20['calmar']),
        abs(float(r5['calmar']) - float(r20['calmar'])) > 1e-9)
    chk('测试后 `FM.FWD` 已复原为 %s ✓' % _old, FM.FWD == _old)
except Exception as e:                                           # noqa: BLE001
    chk('能跑动态铁证（需面板缓存 ✓）', False, '%s: %s' % (type(e).__name__, str(e)[:110]))

print()
print('★ 全过 ✓ 双口径已接线（默认关 ⇒ 行为逐字不变 ✓；开启 ⇒ 任一通过即入库 + 按口径落文档 ✓）'
      if not FAIL else '✗ 有 %d 项没过：\n  - %s' % (len(FAIL), '\n  - '.join(FAIL)))
sys.exit(1 if FAIL else 0)
