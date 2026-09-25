# -*- coding: utf-8 -*-
"""loop_expr.py — 表达式树核心类型与遍历（2026-09-26 L3 拆分）

★★ 为什么单独拆出来：`Node` 是引擎最底层的类型，被 loop_engine / loop_critic /
多个 tools 反复 `from loop_engine import Node` 引用。抽到独立模块后，任何模块都能
import 它而不必 import 整个 loop_engine（缩短 import 链、避免循环依赖）✓

⚠ 语义：本模块是「纯类型 + 纯遍历」，**不 import loop_engine**（也不 import 任何
引擎状态）；`collect` 只做树遍历。迁移后 `Node` 类身份天然统一（不再有
"__main__.Node vs loop_engine.Node 两份"的问题 —— 见 v1.22.2 的修复背景 ✓）
"""


class Node(object):
    __slots__ = ('op', 'args')

    def __init__(self, op, args):
        self.op = op
        self.args = args

    def __str__(self):
        if not self.args:
            return self.op
        return f"{self.op}({', '.join(str(a) for a in self.args)})"

    def key(self):
        """结构哈希(用于FSA), 忽略叶子名差异时可用 op-only"""
        if not self.args:
            return self.op
        return (self.op, tuple(a.key() if isinstance(a, Node) else a
                               for a in self.args))

    def size(self):
        return 1 + sum(a.size() for a in self.args if isinstance(a, Node))


def collect(node, out=None):
    out = [] if out is None else out
    out.append(node)
    for a in node.args:
        if isinstance(a, Node):
            collect(a, out)
    return out
