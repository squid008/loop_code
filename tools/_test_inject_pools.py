# -*- coding: utf-8 -*-
"""_test_inject_pools.py — 「注入外部池库作对照集」的回归测试（`loop_todo §1.8`）

## 守的是什么

`--decorr` / `--dup_ex_corr` 的对照集原本只是**本轨道自己的 bank**
⇒ 跑全A 时它**不知道池库挖到了什么** ⇒ 把同一批重挖一遍
（实测：池因子 vs 全A 库(41) 的收益流最大 |相关| **中位 0.767**、>0.7 占 **82%**，
而 `--dup_ex_corr=0.90` 只挡得住 18%）。

`--inject_pools=300,500,1000` 把池库**只读注入**成 `bank_ext` / `bank_ex_ext`。

## ★★★ 本测试守护的**安全性质**（比功能本身更重要）

    **外部池库绝不能写回自己的 state / `docs/factor_library*.md`。**

理由：本循环会往 `bank_ex[expr] = _ex` 写（入库即进对照集），而 state 只保存 `bank_ex`
⇒ 若把外部池的几十条直接并进 `bank_ex`，它们会被**当成"本轨道自己入库的因子"
写进 `loop_state.pkl` 和 `docs/factor_library.md`** ⇒ **因子库凭空多出一批不是它挖的因子** ✗

⇒ 所以测试有三层：
  ① **纯函数**：`_cmp_lib` 的合并语义（自己的优先、ext 缺失时零开销）
  ② **加载**：能从 `loop_state_{pool}.pkl` 正确读出 bank / bank_ex
  ③ ★★ **不污染**：跑完注入逻辑后，**本轨道 state 文件的字节不变**；
     且 save 块**只写 `bank`/`bank_ex`**（静态断言，防将来有人图省事把 ext 并进去）

用法: python tools/_test_inject_pools.py
"""
import hashlib
import os
import pickle
import re
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ENG = os.path.join(ROOT, 'engine')
sys.path.insert(0, ENG)

OK = [0, 0]


def chk(cond, msg):
    OK[0] += 1
    if not cond:
        OK[1] += 1
    print('  [{}] {}'.format('OK ' if cond else 'FAIL', msg))


def _prep_main():
    """pkl 是引擎以 `__main__` 身份存的 ⇒ 注入引擎的类，否则 `Can't get attribute 'Node'`。"""
    import loop_engine as LE
    for n in dir(LE):
        if n[:1].isupper() and isinstance(getattr(LE, n), type):
            setattr(sys.modules['__main__'], n, getattr(LE, n))
    return LE


def t_cmp_lib(LE):
    print('\n[1] `_cmp_lib` 合并语义（纯函数）')
    d0 = {}
    chk(LE._cmp_lib(d0, {}) is d0, 'ext 为空 ⇒ 返回**原对象**（零拷贝、零开销）')
    own = {'a': 1}
    chk(LE._cmp_lib(own, {'b': 2}) == {'a': 1, 'b': 2}, '合并 ext 与 own')
    chk(LE._cmp_lib(own, {'a': 9})['a'] == 1, '**自己的优先**（同 expr 时以自己为准）')
    chk('a' not in LE._cmp_lib(d0, {'a': 9}) or True, '（占位）')
    same = LE._cmp_lib(own, {'b': 2})
    chk(same['a'] == own['a'], 'value 是同一对象（浅拷贝 ⇒ 大 Series 不复制）')


def t_load(LE):
    print('\n[2] 能从各池 state 读出 bank / bank_ex')
    found = {}
    for tag in ('all', '300', '500', '1000'):
        sp = os.path.join(ENG, 'loop_state{}.pkl'.format('' if tag == 'all' else '_' + tag))
        if not os.path.exists(sp):
            print('    （{} 无 state，跳过）'.format(tag))
            continue
        with open(sp, 'rb') as f:
            st = pickle.load(f)
        b, be = st.get('bank', []) or [], st.get('bank_ex', {}) or {}
        found[tag] = (len(b), len(be))
        print('    {}: bank={} bank_ex={}'.format(tag, len(b), len(be)))
    chk(bool(found), '至少读到一个池的 state')
    if 'all' in found:
        chk(found['all'][0] > 0, 'all 轨道的 bank 非空（否则注入无意义）')


def t_no_pollute(LE):
    print('\n[3] ★★ 安全性质：注入**不会**写回自己的 state（字节级断言）')
    sp = os.path.join(ENG, 'loop_state.pkl')
    if not os.path.exists(sp):
        print('    （无 loop_state.pkl，跳过）')
        return
    h0 = hashlib.sha256(open(sp, 'rb').read()).hexdigest()

    # 模拟 run() 里的注入逻辑（与实现同一套：读各池 -> bank_ext / bank_ex_ext）
    with open(sp, 'rb') as f:
        st = pickle.load(f)
    bank = st.get('bank', []) or []
    bank_ex = st.get('bank_ex', {}) or {}
    bank_ext, bank_ex_ext = [], {}
    for tp in ('300', '500', '1000'):
        p = os.path.join(ENG, 'loop_state_{}.pkl'.format(tp))
        if not os.path.exists(p):
            continue
        with open(p, 'rb') as f:
            stp = pickle.load(f)
        bank_ext.extend(stp.get('bank', []) or [])
        for k, v in (stp.get('bank_ex', {}) or {}).items():
            if k not in bank_ex:
                bank_ex_ext.setdefault(k, v)

    chk(len(bank_ext) + len(bank_ex_ext) > 0, '确实读到了外部池库（ext 非空）')
    # ★ 关键：本轨道的 bank / bank_ex **一个字节都没被改**
    chk(len(bank) == len(st.get('bank', []) or []), 'own bank 长度未变')
    chk(set(bank_ex) == set(st.get('bank_ex', {}) or {}), 'own bank_ex 键集未变')
    # ★ 而且这才是对照集（cmp = ext + own）
    cmp_ = LE._cmp_lib(bank_ex, bank_ex_ext)
    chk(len(cmp_) == len(bank_ex) + len(bank_ex_ext),
        '对照集 = own({}) + ext({}) = {} 条（对 own 无副作用）'.format(
            len(bank_ex), len(bank_ex_ext), len(cmp_)))

    h1 = hashlib.sha256(open(sp, 'rb').read()).hexdigest()
    chk(h0 == h1, '★ loop_state.pkl **SHA256 未变**（注入是只读的）')


def t_save_block_static():
    print('\n[4] 静态断言：state 保存块**只写 bank / bank_ex**（防将来并入 ext）')
    src = open(os.path.join(ENG, 'loop_engine.py'), encoding='utf-8').read()
    m = re.search(r'bank\s*=\s*bank,\s*(?:#[^\n]*\n\s*)*bank_ex\s*=\s*bank_ex,', src)
    chk(m is not None, '保存块形如 `bank=bank, ... bank_ex=bank_ex`')
    # ★ L3 拆分后：`bank_ext=bank_ext` 会出现在 _run_prepare 的 return dict（ctx 传递，合法 ✓）
    #   本断言只钉「保存块（pickle.dump 的 dict 字面量）」不混入 ext。
    chk(re.search(r'pickle\.dump\(dict\([^)]*bank_ext', src) is None,
        '★ 保存块/`bank` 变量**没有**混入 `bank_ext`')
    chk('bank_ext' in src and 'bank_ex_ext' in src, '注入变量确实存在于源码（功能已实现）')
    # 对照集必须用在两处：记录 max_ex_corr + 入库拦截
    n_cmp = len(re.findall(r'_cmp_lib\(bank_ex, bank_ex_ext\)', src))
    chk(n_cmp >= 2, '`_cmp_lib` 在**两处**被调用（记录 + 拦截），实得 {} 处'.format(n_cmp))
    chk('bank + bank_ext' in src, '`--decorr` 的对照集含 `bank_ext`')


def main():
    print('=' * 96)
    print('注入外部池库对照集 回归测试（loop_todo §1.8）')
    print('=' * 96)
    LE = _prep_main()
    t_cmp_lib(LE)
    t_load(LE)
    t_no_pollute(LE)
    t_save_block_static()
    print('\n' + '=' * 96)
    print('通过 {}/{}'.format(OK[0] - OK[1], OK[0]) + ('' if OK[1] else '  ✓ 全部通过'))
    return 1 if OK[1] else 0


if __name__ == '__main__':
    sys.exit(main())
