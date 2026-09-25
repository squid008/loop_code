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


# ---- 算子族归一化 + 骨架/结构族（2026-09-26 L3 Step 2b-1 追加）----
def norm_op(op):
    """算子族归一化: ts_mean20 -> ts_mean / corr60 -> corr (剥窗口数字, 保留算子族)"""
    for p in ('ts_mean', 'ts_std', 'ts_sum', 'ts_max', 'ts_min',
              'ts_rank', 'ts_delay', 'ts_delta', 'corr'):
        if op.startswith(p):
            return p
    return op


def skeleton(node):
    """骨架键 = 算子族名 + 树结构 + 叶子身份(保留叶子名), 完全剥离窗口数字。
    对齐中金 FSA 的'抽象因子结构': ts_std60/ts_std100/ts_std150 视为同一骨架,
    只换窗口的同族候选会被识别为重复骨架, 由冻结/入库上限机制拦下。"""
    if not node.args:
        return node.op
    return norm_op(node.op) + '(' + ','.join(
        skeleton(a) if isinstance(a, Node) else str(a)
        for a in node.args) + ')'


def skeleton_freq(nodes):
    """统计一组表达式的完整骨架频次(用于FSA冻结与库内骨架去重)"""
    c = {}
    for nd in nodes:
        s = skeleton(nd)
        c[s] = c.get(s, 0) + 1
    return c


def subtree_skels(node):
    """候选的全部【非叶子】子树骨架集合(叶子/字段名不算结构, 防'某字段出现>15%'误冻结)"""
    out = set()
    for x in collect(node):
        if x.args:
            out.add(skeleton(x))
    return out


def has_frozen_skel(node, frozen):
    """候选是否含任一已冻结的结构骨架(中金: 冻结骨架禁止复用 -> 生成端丢弃/入库端审查)"""
    return bool(frozen and (subtree_skels(node) & set(frozen)))


# ---- ★★★ 2026-09-17 FSA 冻结**期数化 + 冷却期**（用户拍板："先按 2→4→8 代封顶 + 日志留痕，时间先暂时不管"）----
#  为什么改（旧规则的问题，实测）：
#    · 旧规则 = 「本代超阈值 ⇒ 冻结；**上代冻结的骨架本代不再出现 ⇒ 立刻解冻**」
#      ⇒ 冻结的"记忆"**只活一代** ✗ ⇒ 隔几代复发的结构**完全拦不住** ✗
#    · 实测（2026-09-17，全部池日志的 `冻结骨架:` 行）：被冻结过的 **120** 个骨架里 **7 个（6%）**复发过，
#      复发间隔 最小 1 · **中位 2** · 最大 **10 代** ⇒ 确实存在"隔几代再来"的结构 ✓
#  新规则（逐次翻倍、8 代封顶）：
#    · 首次超阈值 ⇒ 冻结 **2** 代；解冻后若在冷却期 `FSA_COOL_GENS` 内**再犯** ⇒ **4** 代；再犯 ⇒ **8** 代（封顶）
#    · 冻结期内**每代递减**；**即使本代不再出现也保持冻结**（这就是"记忆"✓ —— 也是与旧规则的关键差别）
#    · 冻结期内又超阈值 ⇒ **续期**（refresh 回本期数，**不叠加** ✗）
#    · 解冻后连续 `FSA_COOL_GENS` 代都未超阈值 ⇒ **遗忘**（次数归零，下次回到 2 代 ✓）⇒ 防永久拉黑 ✓
#  ⚠ 判据只用**代数**（时间维度暂不做）：实测各池"一代"的物理时长差 **~20 倍**
#    （300 池 21 分/代 vs 500 池 7.5 h/代 ✗）⇒ 将来若要严格一致，应改成"代数 + 时间"双条件 ✓
#  ⚠ 为什么上限不设 16 代：复发间隔最大 10 代、8 代已能挡住 **86%** 的复发（见上），
#    而 16 代在 500 池 ≈ 5 天 ⇒ 边益极小而**锁死风险**（冻结是"含该子树就全拦"的连坐惩罚 ✗）大 ✓
FSA_FREEZE_SEQ = (2, 4, 8)    # 冻结期序列（逐次翻倍；末项 = 封顶）
FSA_COOL_GENS = 4             # 解冻后的冷却期：连续这么多代未再超阈值 ⇒ 忘掉它（次数归零）


def fsa_period(cnt):
    """第 `cnt` 次冻结该冻几代（`cnt` 从 1 起算；超出序列 ⇒ 取封顶值）✓"""
    return FSA_FREEZE_SEQ[min(max(int(cnt), 1), len(FSA_FREEZE_SEQ)) - 1]


# ---- 结构族聚类(QuantaAlpha 冗余检测移植): 拦"外层模板固定、内层微调"的同构霸榜族 ----
FAM_CUT = 3          # 模板指纹展开算子层数(cut 层以下折叠)
FAM_QUOTA = 2        # L1 同模板族候选进 L2/种子池上限
FAM_BLOCK_THR = 0.5  # 上代 L1 同模板族占比 >= 该值 -> 本代生成端禁产该模板族


def sole_leaf(node):
    """若 node 经"纯单目算子链"化简后恰为单一叶子, 返回该叶名; 否则 None。
    ts_min20(cs_rank(barra_leverage)) -> 'barra_leverage'; div(leverage, gm) -> None。"""
    cur = node
    while isinstance(cur, Node) and cur.args:
        if len(cur.args) != 1:
            return None
        cur = cur.args[0]
    return cur.op if isinstance(cur, Node) else None


def leaf_proxy_key(node):
    """gen51 叶子代理族键: 顶层 max/min 若有一支经"纯单目算子链"化简后恰为单一叶子,
    则该候选信息量≈该叶(numerically 也确如此: ts_min20(cs_rank(barra_leverage)) 与
    barra_leverage 相关 0.997), 只是"某叶套壳+地板" -> 返回族键, 把"同叶不同壳"的候选
    合并为一族, 由 fam_quota 拦重复(防不同外壳反复重发现同一叶、制造虚假多样性)。
    键含另一支(地板)若为裸叶则一并纳入, 避免把不同地板结构误并。
    返回 None 表示非叶子代理, 回落常规 root_fam 指纹。"""
    if not isinstance(node, Node) or node.op not in ('max', 'min') or len(node.args) != 2:
        return None
    a, b = node.args
    for inner, other in ((a, b), (b, a)):
        if isinstance(inner, Node) and inner.args:
            sl = sole_leaf(inner)
            if sl is not None:
                ol = other.op if (isinstance(other, Node) and not other.args) else ''
                return '~' + sl + ('|' + ol if ol else '')
    return None


def root_fam(node, cut=FAM_CUT, use_sole=True):
    """模板族指纹: 叶子统一'X'(身份无关) + 窗口剥除 + 距根cut层以下折叠'#'。
    mul(turnover,ts_min100(corr100(overnight, <任意深>))) 成员 -> 同一指纹, 判同族。
    gen51 起增补"单叶变换"维度: 顶层 max/min 的内层若只是某叶的单目变换(=叶子代理),
    直接返回 '~<叶名>[|<地板叶>]' 作为族键 -> 同叶不同壳的代理候选合并同族。"""
    if use_sole:
        pk = leaf_proxy_key(node)
        if pk is not None:
            return pk

    def rec(nd, d):
        if not nd.args:
            return 'X'
        if d >= cut:
            return '#'
        return norm_op(nd.op) + '(' + ','.join(
            rec(a, d + 1) if isinstance(a, Node) else 'X' for a in nd.args) + ')'
    return rec(node, 0)

