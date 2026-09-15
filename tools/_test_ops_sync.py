# -*- coding: utf-8 -*-
"""_test_ops_sync.py — 算子表「单一事实源」+ `ts_ema` 正确性（`loop_todo §1.25`）

## 为什么有这个测试（2026-09-15，加 `ema` 时发现的**漂移**）

引擎的算子白名单原在 `loop_engine.UNARY/BINARY`，但**下游有 3 处副本**：
  · `loop_critic.SLOW_OPS`（B角"偏好长周期算子"）
  · `loop_critic._ops_of()` ← ★★ **硬编码 28 个**，而引擎有 **45 个** ⇒ **缺 15 个**
    （`ts_mean60/100/120/150/200` · `ts_std100/150/200` · `ts_rank100/200` ·
      `ts_max100` · `ts_min100` · `ts_delta60/120` · `ts_sum100` · `corr100/200`）
    ⇒ **长窗口算子一直被 B角 的结构诊断忽视** ✗
  · `loop_llm` 的 A角 prompt（**声明式**清单，必须人工同步）
★ 这与项目史上「`loop_critic` 硬编码旧 12 字段」（见 `loop_fields.py` 头注）是**同一类漂移**。

## ★★★ 2026-09-15 晚（架构清扫 P0-1）：**根因已消除，本测试的角色随之升级**

上述副本**全部改成从单一事实源派生**：
```
engine/ops_registry.py   ← ★ 算子**唯一声明处**（+ `SLOW_OPS` + prompt 名单生成）
engine/loop_fields.py    ← ★ 叶子**唯一声明处**（更早已经存在）
        ↓ 派生
loop_engine.UNARY/BINARY · loop_critic.SLOW_OPS · loop_llm 的 prompt（**占位符注入**）
```
⇒ 从此**结构上不可能漂移**（不是靠本测试提醒，是**根本没得抄**）✓

★★★ **但 P0-1 过程中，本测试抓到一个"正在漏水"的真 bug**（价值极高，记在这）：
  `engine/skills/gen_skill.md` 是**运行时真正生效**的 A角 prompt，却**落后 21 个算子**
  （`ema*` 5 个 · `ts_slope/rsqr/resi*` 12 个 · `ts_skew/kurt*` 4 个）
  与 **7 个财报叶子**（`fa_pb/fa_accrual/fa_asset_turn/fa_gw/fa_inv_turn/fa_recv_turn/fa_sell_exp`）；
  而 prompt 又硬性要求「**窗口必须是上述枚举值**」「禁止出现叶子字段以外的名字」
  ⇒ **A角 LLM 即使想用也会被自己的规则拒掉** ⇒ v0.13.0/v0.13.1 新加的算子
     **对 A角 语义引导实际从未生效** ✗✗
  ★ **教训**：**「文件存在就用它」的外置副本 = 最容易过期的副本** ——
    因为改 prompt 时通常只改源码里那份（`_GEN_SYSTEM_FALLBACK`），忘了 .md。
    ⇒ 而这正是本测试**旧版查不出来**的：它 grep 的是 `loop_llm.py` 源码
      （= **回退份**），恰好**不是生效的那份** ✗

## 本测试的断言（升级后）

1. **`_ops_of` 必须与引擎同步**（已派生 ⇒ 结构性保证；再断言一次防回退）
2. **穷尽搜**：全仓 `.py` 里出现"算子名清单"的位置**只允许**在
   `ops_registry.py`（**声明处**）与经人工确认的少数文件 —— 别处出现就报警
3. **A角 prompt（★ 渲染后）必须列出全部算子** —— 同时覆盖 `GEN_SYSTEM`
   （= `skills/gen_skill.md`，**生效版**）与 `_GEN_SYSTEM_FALLBACK`（回退版），
   并断言**没有未渲染的占位符** ✓
4. **`ts_ema` 数值正确性**：手算递归 / 衰减因子 / 满窗 / **无未来信息** / 能组合出 MACD
5. **能组合出 MACD**（`sub(ema12(x), ema26(x))` ⇒ 无需单独加 `MACD` 算子）
6. **叶子字段（★ 渲染后）必须列全** —— 治上面那个 bug 的**第二半**（缺 7 个财报叶子）✓
"""
import io
import os
import re
import sys

import numpy as np

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'engine'))

OK = [0, 0]
# 允许出现"算子名清单"的文件（**均已人工确认**，见各条理由）
ALLOW = {
    'ops_registry.py',       # ★★★ **算子唯一声明处**（P0-1 之后单一事实源的本体）
    'loop_engine.py',        # ★ 现在只是**接线**（UNARY/BINARY 均派生）；留白以备注释举例
    'loop_llm.py',           # ★ **占位符版** prompt（名单已不手写）；由 [3] 锁**渲染后**覆盖
    'loop_critic.py',        # ★ `FAST_OPS` = **子集偏好**（`SLOW_OPS` 已改派生）；
                             #   真正要同步的 `_ops_of` 已**派生** ⇒ 由 [1] 结构性保证
    'loop_fix_bank_gen8.py',  # 一次性修复脚本里的具体因子表达式（不是清单）
    # 以下为各测试/诊断脚本里引用的具体表达式示例（非清单）
    #   ⚠ 2026-09-15：`calib_gates.py` 已**改名**为 `calib_dedup_leaf.py`
    #     （与 `calib_gate.py` 只差一个 `s` 却用途不同 ⇒ 极易混淆；
    #      被删的是 `_calib_quality_gate.py`/`_calib_novelty.py`，见 `change_log.md:559`）
    '_test_ops_sync.py', '_test_critic_sensor.py', 'calib_dedup_leaf.py', '_test_daily_dd.py',
    '_check_faildim.py', '_test_ok_gate.py', '_test_action_efficacy.py',
    '_test_parent_sel.py', '_test_inject_pools.py', '_test_reports_expr.py',
    '_test_build_facs_merge.py',
}


def chk(cond, msg):
    OK[0] += 1
    if not cond:
        OK[1] += 1
    print('  [{}] {}'.format('OK ' if cond else 'FAIL', msg))


def t_sync():
    print('\n[1] `_ops_of` 与引擎算子表**同步**（单一事实源）')
    import loop_engine as LE
    import loop_critic as C
    eng = set(LE.UNARY) | set(LE.BINARY)
    got = set(C._op_names())
    chk(got == eng, '`_op_names()` == `UNARY+BINARY`（{} 个）'.format(len(eng)))
    # ★ 结构性保证：`_ops_of` 体内**不应**再出现硬编码算子名
    src = io.open(os.path.join(ROOT, 'engine', 'loop_critic.py'), encoding='utf-8').read()
    body = re.search(r'\ndef _ops_of\(expr\):(.*?)(?=\n\ndef )', src, re.S)
    chk(body is not None, '找到 `_ops_of` 函数体')
    hard = re.findall(r"'((?:ts_|corr|cs_)\w+)'", body.group(1)) if body else ['(未找到)']
    chk(not hard, '★ `_ops_of` 体内**没有硬编码算子名**（实得 {}）'
                  ' —— 已改成从引擎派生'.format(hard))
    # 长窗/ema 必须能被认出（这是本次修掉的 bug）
    chk(set(C._ops_of('ts_mean150(mul(ts_std100(x), corr200(a,b)))')) >=
        {'ts_mean150', 'ts_std100', 'corr200', 'mul'},
        '★ 长窗口算子能被 `_ops_of` 认出（原实现漏了 15 个）')
    chk(set(C._ops_of('sub(ema12(close), ema26(close))')) >= {'ema12', 'ema26', 'sub'},
        'ema 算子能被认出')


def t_no_stray():
    """检测**真正的"白名单副本"** —— 特征：**单行里出现 ≥4 个算子名字面量**。

    ⚠ 2026-09-15 实录：初版判定是"文件中出现任一算子名 ⇒ 报警" ⇒ **误报 5 个文件** ✗
      （它们都是**注释/docstring 里举例**，或 `SLOW_OPS`/`FAST_OPS` 这种"**子集偏好**"，
        或一次性修复脚本里的具体表达式）
    ⇒ 改为按"**聚集度**"判定（副本一定是一串名字写在一起）✓
    ★ 而真正**必须同步**的两处是：`loop_critic._ops_of`（已改成**派生** ⇒ 结构性保证，见 [1]）
      与 `loop_llm` 的 prompt（**声明式，无法派生** ⇒ 由 [3] 专门锁）✓
    """
    print('\n[2] 检测"白名单副本"（**列表字面量**里 ≥4 个算子名 = 疑似全量清单）')
    one = r'ts_(?:mean|std|max|min|rank|sum|delta|delay)\d+|corr\d+|ema\d+|cs_(?:rank|demean|scale)'
    # ⚠ 只查**列表/元组字面量**（`[...]` 里一串名字）—— 那才是"副本"的形态；
    #   注释/docstring 里举例不算。且 `loop_critic` / `loop_fix_bank_gen8` 经人工确认
    #   是"声明式子集偏好（SLOW_OPS/FAST_OPS）"与"一次性修复脚本里的具体表达式" ⇒ 合法 ✓
    rx_list = re.compile(r'[[(][^\])]*?(?:' + one + r')[^\])]*?[\])]')
    bad = []
    for sub in ('engine', 'tools', 'standard'):
        d = os.path.join(ROOT, sub)
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            if not fn.endswith('.py') or fn in ALLOW:
                continue
            t = io.open(os.path.join(d, fn), encoding='utf-8', errors='replace').read()
            for m in rx_list.finditer(t):
                if len(set(re.findall(one, m.group(0)))) >= 4:
                    ln = t[:m.start()].count('\n') + 1
                    bad.append('{}/{}:L{}'.format(sub, fn, ln))
    chk(not bad, '★ 没有可疑的算子名清单副本 —— 实得 {}'.format(bad or '无'))


def _expand_abbrev(src):
    """把 prompt 里的**斜杠简写**展开成完整算子名集合。

    例：`ts_mean5/10/20/60` ⇒ {ts_mean5, ts_mean10, ts_mean20, ts_mean60}

    ⚠ 2026-09-15 实录：初版直接查 `k in src` ⇒ 因为 prompt 用的是**简写**，
      把 `ts_mean10` 等 **20 个算子误判为"缺失"** ✗ ⇒ 必须展开后再比 ✓
    """
    out = set()
    # 形如 `base 5/10/20/60` 或 `base5/10/20/60`
    for m in re.finditer(r'\b((?:ts_[a-z]+|corr|ema))(\d+(?:/\d+)+)', src):
        base = m.group(1)
        for n in m.group(2).split('/'):
            out.add('{}{}'.format(base, n))
    # 单个完整名也算
    out |= set(re.findall(r'\b(?:ts_[a-z]+\d+|corr\d+|ema\d+)\b', src))
    return out


def _prompt_variants():
    """两份 A角 prompt 的**渲染后文本**（生效版 + 回退版）。

    ★ 为什么必须**两份都测**：`GEN_SYSTEM` 才是**运行时生效**的那份
      （`_load_skill` 优先读 `skills/gen_skill.md`），`_GEN_SYSTEM_FALLBACK` 仅在
      .md 缺失/为空时回退 ⇒ **旧版测试 grep 的是源码（= 回退份）**，
      恰好**看不见生效的那份** ⇒ 漏掉了"生效版缺 21 个算子"这个真 bug ✗
    """
    import loop_llm as LL
    return (('GEN_SYSTEM（skills/gen_skill.md · **生效版**）', LL.GEN_SYSTEM),
            ('_GEN_SYSTEM_FALLBACK（回退版）', LL.render_prompt(LL._GEN_SYSTEM_FALLBACK)))


def t_llm_prompt():
    print('\n[3] A角 LLM prompt（★**渲染后**）必须列出**全部**算子')
    import loop_engine as LE
    import loop_llm as LL
    need = set(LE.UNARY) | set(LE.BINARY)
    for label, txt in _prompt_variants():
        left = LL.unresolved_placeholders(txt)
        chk(not left, '{}：无未渲染的占位符（残留 {}）'.format(label, left or '无'))
        listed = _expand_abbrev(txt)
        # ⚠ 无窗口算子（`abs`/`log`/`add`/`sub`…）在 prompt 里是**空格分隔的字面名**，
        #   展开器抓不到 ⇒ 用 `k in txt` 兜底（但**先**展开，否则有窗口的漏项会被掩盖）
        miss = sorted(k for k in need - listed if k not in txt)
        chk(not miss, '{}：覆盖全部 {} 个算子（缺 {}）'.format(label, len(need), miss or '无'))
    chk('ema12' in _expand_abbrev(LL.GEN_SYSTEM)
        and 'ema26' in _expand_abbrev(LL.GEN_SYSTEM),
        '★ **生效版** prompt 含 `ema12`/`ema26`（MACD 可组合）')


def t_leaves():
    """★ 叶子字段也要"渲染后完整" —— 治 P0-1 抓到的 bug **第二半**。

    2026-09-15 实录：`skills/gen_skill.md` 的财报族只列 **8 个**，而
    `loop_fields.FA_LEAVES` 当天已扩到 **15 个**（+`fa_pb`/`fa_accrual`/`fa_asset_turn`/
    `fa_gw`/`fa_inv_turn`/`fa_recv_turn`/`fa_sell_exp`）⇒ **A角 看不到新增的 7 个** ✗
    而 prompt 又写着「禁止出现叶子字段以外的名字」⇒ 想用也用不了 ✗
    ⇒ 现在名单由 `{{LEAF_*}}` 从 `loop_fields` 注入 ⇒ 断言"渲染后包含全部叶子" ✓
    """
    print('\n[6] 叶子字段（★**渲染后**）必须列全（治 gen_skill.md 缺 7 个财报叶子）')
    import loop_engine as LE
    from loop_fields import LEAVES
    need = set(LEAVES)
    chk(set(LE.LEAVES) == need,
        '`loop_engine.LEAVES` == `loop_fields.LEAVES`（{} 个，单一事实源）'.format(len(need)))
    for label, txt in _prompt_variants():
        toks = set(re.findall(r'[A-Za-z_][A-Za-z_0-9]*', txt))
        miss = sorted(k for k in need - toks)
        chk(not miss, '{}：覆盖全部 {} 个叶子（缺 {}）'.format(label, len(need), miss or '无'))


def t_ema():
    print('\n[4] `ts_ema` 数值正确性（对齐 QuantaQuant/通达信 `EMA`）')
    import fastops as FO
    rng = np.random.RandomState(7)
    x = rng.randn(120, 3).astype(np.float64)

    for w in (5, 12, 26):
        a = 2.0 / (w + 1.0)
        # 手算递归（无 NaN 情形）
        exp = np.empty_like(x)
        prev = None
        for t in range(x.shape[0]):
            prev = x[t] if prev is None else a * x[t] + (1 - a) * prev
            exp[t] = prev
        got = FO.ts_ema(x, w)
        m = np.isfinite(got)
        chk(m.sum() > 0 and np.allclose(got[m], exp[m].astype(np.float32), atol=1e-4),
            'w={}：与手算递归一致（衰减因子 α=2/(w+1)={:.4f}）'.format(w, a))
        chk(bool(np.isnan(got[:w - 1]).all()) and bool(np.isfinite(got[w - 1]).any()),
            'w={}：**满窗**语义 —— 前 w−1 期 NaN，第 w 期起有值'.format(w))

    # ★ 与 ts_mean 必须**不同**（否则加它没意义）
    w = 20
    e = FO.ts_ema(x, w)
    mn = FO.ts_mean(x, w)
    m = np.isfinite(e) & np.isfinite(mn)
    differ = not np.allclose(e[m], mn[m], atol=1e-3)
    chk(differ, '★ `ts_ema` 与 `ts_mean` **确实不同**（等权 vs 指数加权 ⇒ 加它才有意义）')
    # ★ EMA 对**最近一期的突变**反应更快（这是"指数加权"的定义性质，必然成立）
    #   ⚠ 2026-09-15 实录：初版断言"EMA 末值更贴近最新观测" ⇒ **数学上不成立、偶发 FAIL** ✗
    #     （末值差距取决于序列方差结构，与"等权/指数加权"无必然关系）
    #   ⇒ 改成"**对末值加同一增量，看谁动得多**" —— 这个必然成立 ✓
    d = 5.0
    x2 = x.copy()
    x2[-1] = x[-1] + d
    de = abs(FO.ts_ema(x2, w)[-1] - e[-1])
    dm = abs(FO.ts_mean(x2, w)[-1] - mn[-1])
    chk(bool(np.all(de > dm)), '★ 末期突变时 EMA 反应({:.3f}) > `ts_mean`({:.3f}) —— '
                               '指数加权的基本性质'.format(float(np.mean(de)), float(np.mean(dm))))

    print('  --- 无未来信息（铁律）---')
    y = x.copy()
    y[60:] = rng.randn(60, 3) * 10          # **只改 t>=60 的数据**
    g1, g2 = FO.ts_ema(x, 10), FO.ts_ema(y, 10)
    chk(np.allclose(g1[:60], g2[:60], equal_nan=True),
        '★★ 改 t>=60 的数据**不影响 t<60 的输出** ⇒ **不引入未来信息** ✓')

    print('  --- NaN 处「跳过」（通达信口径）---')
    z = x.copy()
    z[40, 1] = np.nan
    gz = FO.ts_ema(z, 10)
    chk(np.isfinite(gz[40, 1]) and np.isfinite(gz[41, 1]),
        'NaN 处**保持上一个 EMA 值**（不是传播成整段 NaN）')
    z2 = x.copy()
    z2[:50, 2] = np.nan                    # 前 50 期全 NaN ⇒ 计数不足 ⇒ 仍 NaN
    chk(bool(np.isnan(FO.ts_ema(z2, 10)[:59, 2]).all()),
        '有效计数不足 w ⇒ 输出 NaN（不拿 NaN 当 0 补）')

    print('  --- 面板规模性能（回归：别偷偷变慢）---')
    import time
    big = rng.randn(3309, 2000)
    t0 = time.time()
    FO.ts_ema(big, 26)
    dt = time.time() - t0
    chk(dt < 1.5, '3309×2000 面板一次 `ts_ema` 用时 {:.2f}s（< 1.5s）'.format(dt))


def t_macd():
    print('\n[5] 能组合出 MACD（加 `ema` 的目的之一）')
    import loop_engine as LE
    B = {'close': np.random.RandomState(1).randn(300, 4).astype(np.float32)}
    nd = LE.parse_expr('sub(ema12(close), ema26(close))')
    chk(nd is not None, '`sub(ema12(x), ema26(x))` 能解析')
    v = LE.eval_expr(nd, B, {})
    chk(v.shape == (300, 4) and np.isfinite(v[40:]).any(),
        '★ 求值成功（MACD = 快慢 EMA 差，无需单独加 `MACD` 算子）✓')


def main():
    print('=' * 96)
    print('算子表单一事实源 + `ts_ema` 回归测试（loop_todo §1.25）')
    print('=' * 96)
    t_sync()
    t_no_stray()
    t_llm_prompt()
    t_ema()
    t_macd()
    t_leaves()
    print('\n' + '=' * 96)
    print('通过 {}/{}'.format(OK[0] - OK[1], OK[0]) + ('' if OK[1] else '  ✓ 全部通过'))
    return 1 if OK[1] else 0


if __name__ == '__main__':
    sys.exit(main())
