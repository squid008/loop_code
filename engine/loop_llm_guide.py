# -*- coding: utf-8 -*-
"""loop_llm_guide.py — 生成侧 LLM 引导（A角子代理，2026-09-26 L3 Step 2b-3c）

loop_llm 已定义 A角 Skill 与调用封装；本模块补两件事：
  ① parse_expr: LLM 表达式文本 -> 引擎 Node（严格反向解析，任一不合规返回 None）
  ② llm_fetch: 拼本代上下文 -> 调 gen_candidates -> 解析成 Node 池

失败安全: 无 key/超时/JSON坏/语法不合规 -> 一律静默回退本地 guided_expr，绝不阻塞迭代。
★ 依赖：loop_expr（Node/collect）+ loop_fields（LEAVES）+ loop_ops（UNARY/BINARY）
  —— 不 import loop_engine（无循环依赖）；loop_llm 在 llm_fetch 内惰性 import ✓
"""
import re

from loop_expr import Node, collect
from loop_fields import LEAVES
from loop_ops import UNARY, BINARY


_EXPR_TOK = re.compile(r'[A-Za-z_][A-Za-z0-9_]*|[(),]')


def tokenize_expr(text):
    """分词并校验: token 间只允许空白, 出现其它字符(如 + 1 中缀残留)返回 None
    (防止 LLM 输出 'cs_rank(volume) + 1' 时非法尾部被静默吞掉而误收)。"""
    s = str(text)
    toks, pos = [], 0
    for mt in _EXPR_TOK.finditer(s):
        if s[pos:mt.start()].strip():
            return None
        toks.append(mt.group(0))
        pos = mt.end()
    if s[pos:].strip():
        return None
    return toks


def _parse_sexp(toks, i):
    """递归下降单元素: 返回 (Node|None, 下一token下标)"""
    if i >= len(toks):
        return None, i
    name = toks[i]
    i += 1
    if i < len(toks) and toks[i] == '(':
        i += 1
        args = []
        while True:
            nd, i = _parse_sexp(toks, i)
            if nd is None:
                return None, i
            args.append(nd)
            if i < len(toks) and toks[i] == ',':
                i += 1
                continue
            if i < len(toks) and toks[i] == ')':
                return Node(name, args), i + 1
            return None, i
    return Node(name, []), i


def parse_expr(text, max_size=None):
    """LLM 表达式文本 -> Node(与 Node.__str__ 前缀式 op(a, b) 严格对齐)。
    校验: 叶子名∈LEAVES / 函数名∈UNARY∪BINARY / 参数个数匹配 / size≤上限;
    任一不合规返回 None, 由调用方静默丢弃(不修复不猜测)。

    :param max_size: ★ 2026-09-17 新增（**默认 `None` = 沿用 `LLM_MAX_SIZE`，行为一行不改**）——
      只为"**重建已经入库的因子**"这类**可信来源**放开上限：库里的公式是**已经过全部门槛**的，
      尺寸上限（本来是防 LLM 生成超大式子的护栏）对它没有意义，却会让**合法公式静默返回 None** ✗
      实测：全A `F01`（5 层嵌套）就因此解析不出来，下游报的是"'NoneType' has no attribute 'key'"
      （报错点离病根很远 —— 见 `tools/build_facs.load_bank_nodes` 的注释）⇒
      现在 `tools/export_factor_registry.py` 会用 `max_size=10**9` 重建这些历史条目 ✓
    """
    toks = tokenize_expr(text)
    if not toks:
        return None
    nd, i = _parse_sexp(toks, 0)
    if nd is None or i != len(toks):
        return None
    for x in collect(nd):
        if not x.args:
            if x.op not in LEAVES:
                return None
            continue
        if len(x.args) == 1:
            if x.op not in UNARY:
                return None
        elif x.op not in BINARY:          # len(x.args)==2
            return None
    if max_size is None:
        # ★ 2026-09-26 L3：`LLM_MAX_SIZE` 留在 loop_engine（被 tools 运行期临时放开
        #   `LE.LLM_MAX_SIZE=10**9`），这里**惰性 import 读同一份**——否则值拷贝会漏掉放开 ✗
        import loop_engine as _LE
        _cap = _LE.LLM_MAX_SIZE
    else:
        _cap = int(max_size)
    if nd.size() > _cap:
        return None
    return nd


def llm_fetch(args, cfg, seeds, bank, frozen, fail_lib, fam_black=''):
    """A角 LLM 拉一批候选: 拼上下文 -> loop_llm.gen_candidates -> 文本解析回 Node。
    返回 (ok, hyp, nodes); 任何失败 ok=False 且 nodes=[] (内部已打印原因)。"""
    import loop_llm
    diag = (f"第{args.gen}代搜索, 目标候选数{args.n}, 种子池{len(seeds)}个(上一代L1头部)。\n"
            f"当前已知: 入库因子{len(bank)}个(同骨架上限{args.bank_skel_max}), "
            f"冻结骨架{len(frozen)}个(禁止复用), "
            f"失败库{len(fail_lib)}条(多次全败骨架生成端排除)。\n"
            f"本代策略: mix(变异/交叉/扰动/引导/随机)={cfg['mix']}, depth={cfg['depth']}, "
            f"min_stab={cfg.get('min_stab')}, decorr={cfg.get('decorr')}, "
            f"fsa_th={cfg.get('fsa_th')}。\n"
            # ★ 让 A角 知道"亲本是怎么挑的"（2026-09-14, §1.3-C）：
            #   top_percent_plus_random 时亲本偏向前几名 ⇒ LLM 提的新方向宜**离这些远一点**
            #   才能补上策略本身造成的多样性缺口。
            f"亲本选择: parent_sel={getattr(args, 'parent_sel', 'uniform')}"
            + (f"（top {getattr(args, 'parent_top_pct', 0.30):.0%} 保底 + 余量随机）"
               if getattr(args, 'parent_sel', 'uniform') == 'top_percent_plus_random' else '')
            + "。\n"
            f"叶子权重: {cfg.get('leaf_w') or '(均匀)'}。")
    hint = ("请避开易重复结构: 纯市值/成交额/换手率的旧故事表达、同骨架只换窗口的参数变体"
            "都算重复; 优先给出有独立金融机制的表达式(跳空溢价/价量背离/波动结构/日内形态/"
            "流动性等), 宁少勿滥。")
    if fam_black:
        hint += ("\n[结构族黑名单] 上一代 L1 通过集被下列外层模板垄断(L1 高分但费后全灭), "
                 "本代请勿再产出同构模板(换内层参数/叶子不算新结构): " + fam_black)
    model = getattr(args, 'llm_model', None) or loop_llm.DEFAULT_MODEL
    ok, d = loop_llm.gen_candidates(diag, hint, n=args.llm_n, model=model)
    if not ok:
        print(f"  [LLM引导] 调用失败({d}) -> 回退本地引导")
        return False, '', []
    nodes = []
    for t in (d.get('exprs') or []):
        nd = parse_expr(t)
        if nd is not None:
            nodes.append(nd)
    print(f"  [LLM引导] 回复 {len(d.get('exprs') or [])} 条, "
          f"语法解析通过 {len(nodes)} 条")
    return True, (d.get('hyp') or '').strip(), nodes

