# -*- coding: utf-8 -*-
"""一次性修复: 把 gen8 入库因子塞回 state.bank(decorr 对比对象)。

背景: gen8 破零入库的 1 个因子当时 bank 维护代码还未加入 state,
     导致 gen9/gen10 载入时 bank=0, decorr 闸门空转两代(只对比 ln_mktcap/amt_log)。
本脚本: 解析 gen8 因子表达式 -> Node, 与现有 bank 做表达式去重后 append, 重存 state。
用法: D:\\miniconda3\\envs\\rqdata\\python.exe ai_test\\loop_fix_bank_gen8.py
"""
import os
import pickle
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from loop_engine import Node, STATE  # noqa: E402

# gen8 入库因子(factor_roadmap.md Round19 存档):
# add(ts_sum20(ts_std20(cs_demean(log(turn_ratio)))), cs_demean(log(ts_mean5(ts_std20(volume)))))
GEN8_EXPR = ("add(ts_sum20(ts_std20(cs_demean(log(turn_ratio)))), "
             "cs_demean(log(ts_mean5(ts_std20(volume)))))")


def leaf(name):
    return Node(name, [])


def u(op, a):
    return Node(op, [a])


def b(op, x, y):
    return Node(op, [x, y])


def build_gen8():
    """手工构造 gen8 因子 Node(与 __str__ 输出一致性校验)"""
    inner = b('add',
              u('ts_sum20', u('ts_std20', u('cs_demean', u('log', leaf('turn_ratio'))))),
              u('cs_demean', u('log', u('ts_mean5', u('ts_std20', leaf('volume'))))))
    return inner


def main():
    if not os.path.exists(STATE):
        print(f"state 不存在: {STATE}")
        return 1
    with open(STATE, 'rb') as f:
        st = pickle.load(f)
    bank = st.get('bank', [])
    print(f"当前 bank 因子数: {len(bank)}")
    for i, nd in enumerate(bank):
        print(f"  [{i}] {nd}")
    nd = build_gen8()
    s = str(nd)
    print(f"gen8 因子构造 str : {s}")
    print(f"gen8 因子期望 str : {GEN8_EXPR}")
    assert s == GEN8_EXPR, "构造与存档表达式不一致, 中止"
    if any(str(x) == s for x in bank):
        print("gen8 因子已在 bank 中, 无需追加")
    else:
        bank.append(nd)
        st['bank'] = bank[-30:]
        with open(STATE, 'wb') as f:
            pickle.dump(st, f)
        print(f"已追加 gen8 因子 -> bank 现有 {len(bank)} 个")
    # 校验
    with open(STATE, 'rb') as f:
        st2 = pickle.load(f)
    print("重存校验 bank:")
    for i, x in enumerate(st2.get('bank', [])):
        print(f"  [{i}] {x}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
