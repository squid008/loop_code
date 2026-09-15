# -*- coding: utf-8 -*-
"""
LLM 子代理(中金 Loop Engineering 对齐) —— 共享基础设施 + 双角色隔离
========================================================================
中金原版"生成-审查-验证"三端:
  - 生成侧: LLM 子代理 A角(带自己的 Skill), 负责生成预算 20% 的"机制族语义引导":
            A角输入 失败库/叶子权重/已入库骨架/本代假设 -> 输出候选表达式(带机制族假设);
  - 审查侧: LLM 子代理 B角(带自己的 Skill), 负责候选级语义审查:
            输入 单个候选表达式+其结构统计 -> 输出 PASS/KILL(直接参与候选去留);
  - 验证端: 费后回测(硬编码, 引擎内, 非 LLM) —— 引擎 loop_engine.py 已对齐。

角色隔离(防自证):
  * 两个子代理使用【各自独立 system prompt】(各自挂自己的 Skill, 职责与知识面刻意不同);
  * B角审查输入【只有候选表达式与结构统计】, 不知道候选来源 / A角生成假设 / 生成原因;
  * A角生成输入【只有搜索策略与失败统计】, 不知道 B角会如何否决 / 不知道审查口径细节;
  * 可选 --ai_gen_model / --ai_jury_model 配不同模型(如 deepseek-flash vs deepseek-v4-pro)
    进一步物理隔离; 缺省同模型时靠 system 角色隔离 + 输入隔离。
无人值守铁律: key 缺失/调用失败/超时一律回退规则引擎, 绝不阻塞迭代(所有异常由调用方兜底)。
"""
import os
import re
import json
import time

# ---------------------------------------------------------------- 基础设施
_DEEPSEEK_URL = 'https://api.deepseek.com/chat/completions'
DEFAULT_MODEL = 'deepseek-flash'
# ★模型名变更(2026-09-12): 官方名由 `deepseek-v4-flash` 改为 **`deepseek-flash`**。
#   实测(tools/probe_models.py, GET /models + 逐个最小请求):
#     /models 权威名单 = ['deepseek-flash', 'deepseek-v4-pro']  ← **只有这两个**
#     deepseek-flash  OK / deepseek-v4-pro OK
#     deepseek-v4-flash 仍可用(别名兼容, 但已不在名单 -> 随时可能下线, 不应再依赖)
#     deepseek-pro   400: "The supported API model names are deepseek-flash, deepseek-v4-pro"
#     deepseek-chat / deepseek-reasoner 能通但不在名单(legacy)
#   ⚠ 换名/换模型后请重跑 `python tools/probe_models.py` 确认, 别照猜写(2026-09-09 曾因
#     "deepseek-flash-v4" 被 400 拒)。
# 2026-09-09: 该系列默认深度推理, max_tokens 会被 reasoning_content 吃光
# 导致 content 恒为空(finish=length) —— 实测 6000 tok 仍全被推理占用。
# 必须显式 reasoning_effort=none(实测 gen 长任务 3s 出完整 JSON / low 仍吃光 token)。
_REASONING_EFFORT = 'none'   # 'none' | 'low' | 'medium' | 'high'

# ---------------------------------------------------------------- LLM 对话录音
# 可选: 引擎每代启动时 set_conv_path() 指向本代录音文件; 之后 chat_once 每次
# (成功/失败) 都追加 时间戳+角色tag+messages+reply —— 供跑代后人工回溯 A角/B角
# 与 DeepSeek 的完整往返。automation 无人值守时人看不到实时对话, 靠这份落盘文件
# (引擎写 ai_test/loop_conv/gen{gen}C_conv.md, .gitignore 排除, 可整删)。
_CONV_PATH = None   # 非空 = 录音中
_CONV_T0 = time.time()


def set_conv_path(path):
    """开启本进程 LLM 对话录音(loop_engine 每代启动时调用); path=None 关闭。"""
    global _CONV_PATH, _CONV_T0
    _CONV_PATH = path
    _CONV_T0 = time.time()
    if not path:
        return
    try:
        with open(path, 'w', encoding='utf-8') as f:
            f.write("# Loop 引擎 LLM 对话录音 (A角生成侧/B角审查侧 与 DeepSeek 全部往返)\n")
    except OSError:
        _CONV_PATH = None   # 录不上不阻塞主流程


def _conv_cut(text, n=6000):
    text = str(text or '')
    return text if len(text) <= n else text[:n] + f"...[截断, 共{len(text)}字符]"


def _conv_append(tag, model, messages, reply, err=None):
    """追加一次调用记录(含请求 messages 与回复/异常)。写失败静默跳过。"""
    if not _CONV_PATH:
        return
    try:
        t = time.time() - _CONV_T0
        head = (f"\n## [T+{t:7.1f}s] {tag or 'chat'} @ {model}"
                f"{'  **ERROR**' if err else ''}\n")
        with open(_CONV_PATH, 'a', encoding='utf-8') as f:
            f.write(head)
            for m in messages or []:
                f.write(f"- **{m.get('role', '?')}**:\n\n```\n"
                        f"{_conv_cut(m.get('content', ''))}\n```\n\n")
            if err:
                f.write(f"- **error**: `{_conv_cut(err, 2000)}`\n\n")
            else:
                f.write(f"- **reply**:\n\n```\n{_conv_cut(reply)}\n```\n\n")
    except OSError:
        pass


def _key_from_file(path):
    """读 key 文件并智能挑选 token: 优先含 sk- 的连续串, 否则第一个长度>16 的非空行。
    兼容文件带中文说明/非 UTF-8 编码(GBK) 等杂讯。返回 None 表示未取到。"""
    if not os.path.isfile(path):
        return None
    text = None
    for enc in ('utf-8-sig', 'utf-8', 'gb18030'):
        try:
            with open(path, encoding=enc) as f:
                text = f.read()
            break
        except (OSError, UnicodeDecodeError):
            continue
    if not text:
        return None
    import re
    m = re.search(r'sk-[A-Za-z0-9_\-]+', text)
    if m:
        return m.group(0)
    for ln in text.splitlines():
        ln = ln.strip()
        if ln and len(ln) > 16:
            return ln
    return None


def api_key():
    """DeepSeek key: 环境变量 DEEPSEEK_API_KEY > 项目本地 .deepseek_key(不上传) > 桌面 1.txt。
    项目 key 文件推荐放 d:/loop_code/.deepseek_key(与 .gitignore 配套), 单行裸 key 即可;
    文件若带中文说明/非 UTF-8 编码, 由 _key_from_file 智能挑 sk- token 兜底。"""
    env = os.environ.get('DEEPSEEK_API_KEY')
    if env:
        return env.strip()
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # d:/loop_code
    for rel in ['.deepseek_key', 'engine/.deepseek_key']:
        key = _key_from_file(os.path.join(base, rel))
        if key:
            return key
    home = os.path.expanduser('~')
    for rel in ['Desktop', 'OneDrive/Desktop', 'OneDrive/桌面', '桌面']:
        key = _key_from_file(os.path.join(home, rel, '1.txt'))
        if key:
            return key
    return None


def chat_once(messages, model=DEFAULT_MODEL, timeout=120,
              temperature=0.4, max_tokens=1200, tag=''):
    """单轮 DeepSeek chat 调用(OpenAI 兼容), 失败抛异常由调用方兜底。
    tag: 调用角色标记(如 'A角生成侧'), 仅用于对话录音归位。"""
    import urllib.request
    body = json.dumps({'model': model, 'messages': messages,
                       'temperature': temperature,
                       'max_tokens': max_tokens,
                       'reasoning_effort': _REASONING_EFFORT}).encode('utf-8')
    req = urllib.request.Request(
        _DEEPSEEK_URL, data=body, method='POST',
        headers={'Content-Type': 'application/json',
                 'Authorization': 'Bearer ' + api_key()})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode('utf-8'))
    except Exception as e:
        _conv_append(tag, model, messages, None, err=repr(e))
        raise
    content = data['choices'][0]['message']['content'].strip()
    _conv_append(tag, model, messages, content)
    return content


def ask(sys_txt, user_txt, model=DEFAULT_MODEL, timeout=120,
        temperature=0.4, max_tokens=1200, tag=''):
    """安全封装: 返回 (ok, text); 任何异常返回 (False, 原因), 永不抛出。"""
    if not api_key():
        return False, 'no_key'
    try:
        resp = chat_once([{'role': 'system', 'content': sys_txt},
                          {'role': 'user', 'content': user_txt}],
                         model=model, timeout=timeout,
                         temperature=temperature, max_tokens=max_tokens, tag=tag)
        return True, resp
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def _extract_json(text):
    """从 LLM 回复里提取第一个 {..} JSON 块(容忍 markdown 围栏/前后说明文字)。"""
    if not text:
        return None
    s = text.find('{')
    e = text.rfind('}')
    if s < 0 or e <= s:
        return None
    try:
        return json.loads(text[s:e + 1])
    except Exception:
        return None


# ============================================================ A角 Skill 内置底稿
# 生成侧子代理 —— 挂"机制族语义引导 Skill"(引擎 skills/gen_skill.md 为其外置副本):
#   职责: 根据搜索策略(失败库病根/叶子权重/已入库骨架/算子偏好)提出【机制族假设】
#        并把假设落成受控语法表达式; 输出给 GP 引导位当候选。
#   刻意不被告知: B角审查口径、跨量纲审查规则细节、FSA/失败库排除阈值。
_GEN_SYSTEM_FALLBACK = (
    "你是资深A股量价因子研究员, 在中金 Loop Engineering 自动化因子发现引擎里扮演"
    "【A角=生成侧子代理】, 挂的 Skill 是《机制族语义引导》。\n"
    "你的任务: 依据一段'本代搜索诊断', 先给出 1 条机制族假设(用一句话说清你猜什么市场"
    "行为能预测未来5日截面收益), 再把这假设落成若干条可计算的因子表达式。\n"
    "表达式语法(必须严格遵守, 只允许前缀式, 小写):\n"
    "  叶子字段(全部为计算原料, 禁止自造名字, 按族给全):\n"
    # ★ 名单**不手写** —— `{{...}}` 由 `render_prompt()` 从 `loop_fields` 实时注入（P0-1）
    "    量价族: {{LEAF_PRICE}}\n"
    "    资金流族(前缀 mf_, 原始拆分无未来函数; 带 _buy/_sell 结尾=主动买入/卖出金额"
    "(元,量纲A), _bqty/_sqty 结尾=主动买入/卖出股数(量纲V); 净额请用 sub 自组合): "
    "{{LEAF_MF}}\n"
    "    风格族(前缀 barra_, 每日截面风格暴露, 已做截面处理): {{LEAF_BARRA}}\n"
    "    财报族(前缀 fa_, PIT口径按公告日对齐无未来函数; _yoy=TTM同比, gm=毛利率, "
    "np_margin=净利率, roe=ROE, lev=杠杆, pb=市净率, accrual=应计, gw=商誉占比): "
    "{{LEAF_FA}}\n"
    # ★ 算子名单同样**不手写** —— 由 `render_prompt()` 从 `ops_registry` 实时注入（P0-1）
    "  单目算子(1参): {{OPS_CORE}}\n"
    "  ★指数均线(1参): {{OPS_EMA}} "
    "(指数加权, 衰减因子 2/(n+1)。与 ts_mean 的**等权**不同 ⇒ 提供另一条平滑通道; "
    "注意 ema12/ema26 可组合出 MACD: sub(ema12(A), ema26(A)))\n"
    "  ★回归族(1参): {{OPS_REG}} "
    "(对时间做滚动线性回归: slope=趋势斜率(方向+强度); rsqr=拟合度R²(路径多接近直线, "
    "**但不含方向** ⇒ 建议与 slope 组合: mul(ts_rsqr20(close), ts_slope20(close))); "
    "resi=最后一点相对趋势线的偏离。注意: 它们描述**趋势**而非**水平**, 与 ts_mean 是不同通道)\n"
    "  ★分布形状(1参): {{OPS_MOMENT}} "
    "(滚动偏度/超额峰度。与波动率**不等价** —— 同样 σ 时厚尾的尾部风险更大; "
    "偏度看尾巴往哪边, 峰度看极端值密度。建议作用在 ret 或已中性化的量上, "
    "直接对价格水平算意义有限)\n"
    "  双目算子(2参): {{OPS_BINARY}}\n"
    "  例子: sub(ts_mean20(overnight), ts_mean60(overnight))  表示'短期隔夜跳空均值相对"
    "长期回落=跳空溢价衰减';\n"
    "        sub(ema12(close), ema26(close)) 表示'MACD 式快慢均线背离';\n"
    "        neg(corr60(ts_delta5(close), volume)) 表示'价量背离';\n"
    "  硬性要求: 1)每行恰好一条表达式, 禁止出现叶子字段以外的名字, 窗口必须是上述枚举值;"
    " 2)子表达式外层不要再包无意义函数; 3)优先 sub/div/背离/平滑结构, 少用纯单字段均值;"
    " 4)输出只给表达式, 不得解释(你的假设放在 JSON 的 hyp 字段)。\n"
    "  新信号族机制引导(扩展叶子池, 可在 hyp 中优先描述这些方向, 表达式可跨族组合):\n"
    "    - 资金流失衡: 大/超大单主动净买入占比、中小单与超大单方向背离、量额不匹配"
    "(价格变化与资金流强度背离);\n"
    "    - 风格轮动/暴露: 风格动量的延续与反转(barra_momentum/growth/earnings_yield "
    "等的长窗 ts_mean vs 短窗)、成长与价值/质量背离;\n"
    "    - 财报景气: 盈利/营收同比的动量与加速度(ts_delta 同比、roc 平滑)、盈利质量"
    "(高 roe+高 gm)与估值风格的交互;\n"
    "回复必须是严格 JSON: {\"hyp\":\"一句话机制族假设\",\"exprs\":[\"expr1\",\"expr2\",...]}"
    " , 表达式 8~16 条, 多样化但不重复。"
)

# ============================================================ B角 Skill 内置底稿
# 审查侧子代理 —— 挂"候选级语义审查 Skill"(引擎 skills/jury_skill.md 为其外置副本):
#   职责: 对单个候选表达式做【经济含义 + 过拟合结构边界】判断 -> PASS/KILL;
#   中金: 审查侧随机抽 5 个深判, verdict 直接参与候选去留(输出闭环)。
#   刻意不被告知: 候选来源(是不是 LLM/A角生成的)、A角假设、规则闸门细节。
_JURY_SYSTEM_FALLBACK = (
    "你是资深A股量价因子研究员, 在中金 Loop Engineering 框架里扮演"
    "【B角=审查侧子代理】, 挂的 Skill 是《候选级语义审查》。\n"
    "输入是一个待进费后回测的候选因子表达式及其结构统计。你要判断它:\n"
    "  (1) 经济含义: 该结构是否对应一个可理解的量价行为(跳空溢价/动量反转/流动性/波动率"
    "风险/价量背离等)? 若纯属数学巧合(如价格字段与成交量字段原始尺度相减、含义拼凑)判 KILL;\n"
    "  (2) 过拟合边界: 窗口/嵌套/参数是否有意义, 是否像'参数海里捞针'(如把窗口差1的同族"
    "变体全试一遍、叠加多层同源算子的冗余结构)? 高冗余/难解释判 KILL;\n"
    "  (3) 已知族嫌疑: 是否只是再表达一遍 市值(ln_mktcap/mktcap)/成交额(turnover/amt/"
    "ln_volume)/换手率(turn_ratio) 的老故事? 与已知大因子高度同构且无增量机制判 KILL;\n"
    "  注意: 只从结构与经济含义判, 不要臆测具体IC数字; 拿不准时宁 PASS 不误杀"
    "(回测+人工是最终裁决)。\n"
    "回复必须是严格 JSON: {\"verdict\":\"PASS\"或\"KILL\",\"reason\":\"≤40字中文理由\"}"
    " , 不得输出其它内容。"
)

# ============================================================ Skill 外置加载
# 中金: 生成侧/审查侧子代理各挂自己的 Skill 文件, 换资产/改口径只需改对应 .md。
# 优先读 engine/skills/{gen_skill,jury_skill}.md; 缺失/损坏回退内置常量, 不阻塞。
_SKILL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'skills')


def _load_skill(name, fallback):
    try:
        with open(os.path.join(_SKILL_DIR, name + '.md'), encoding='utf-8') as f:
            txt = f.read().strip()
        return txt if txt else fallback
    except OSError:
        return fallback


# ============================================================ ★★★ 占位符渲染（P0-1）
# 【为什么需要 —— 2026-09-15 实录：这是**正在漏水的 bug**，不是"洁癖"】
#
# A角 prompt 有**两份副本**：`engine/skills/gen_skill.md`（文件存在就用它）
# 与上一行的 `_GEN_SYSTEM_FALLBACK`（文件缺失才回退）。
# ★ 而**运行时生效的是 .md 那份**，它却**已经落后**：
#   · 算子：缺 `ema5/12/20/26/60`(5) + `ts_slope/ts_rsqr/ts_resi{5,10,20,60}`(12)
#           + `ts_skew/ts_kurt{20,60}`(4)  ⇒ **共 21 个**
#   · 叶子：缺 `fa_pb/fa_accrual/fa_asset_turn/fa_gw/fa_inv_turn/fa_recv_turn/fa_sell_exp`(7)
# ⇒ 而 prompt 同时硬性要求「**窗口必须是上述枚举值**」「禁止出现叶子字段以外的名字」
#   ⇒ **A角 LLM 即使想用这些算子/字段，也会被自己的规则拒掉** ✗✗
#   ⇒ 即 v0.13.0/v0.13.1 加的那批算子，**对 A角 语义引导实际从未生效**（真损失）✗
#
# ★ 正解：**机械清单不再手写**，改为占位符，运行时从**单一事实源**注入 ——
#     算子 ← `ops_registry`（算子声明处）· 叶子 ← `loop_fields`（LEAVES 声明处）
#   ⇒ 两份副本都会自动同步 ⇒ **结构上不可能再漂移** ✓
#   ⚠ 语义说明（如"R² 不含方向 ⇒ 建议与 slope 组合"）**仍手写** ——
#     那是**知识**，不是机械清单，不该自动化 ✓
#
# ★ 导入必须放在**本 dict 之前**（2026-09-15 实录）：初版把 import 写在 dict 后面，
#   而 `'{{OPS_BINARY}}': _OPS.prompt_binary` 是**构造 dict 时立刻求值**的 ⇒
#   `NameError: name '_OPS' is not defined` ✗
#   ★ 教训：**dict 字面量里的裸引用是即时求值** —— 只有 `lambda` 体内才是延迟求值 ✓
import ops_registry as _OPS      # ★ 算子单一事实源（声明处）
import loop_fields as _LF        # ★ 叶子单一事实源（`LEAVES` 声明处）

_PLACEHOLDERS = {
    '{{OPS_CORE}}':   lambda: _OPS.prompt_unary('core'),
    '{{OPS_EMA}}':    lambda: _OPS.prompt_unary('ema'),
    '{{OPS_REG}}':    lambda: _OPS.prompt_unary('reg'),
    '{{OPS_MOMENT}}': lambda: _OPS.prompt_unary('moment'),
    '{{OPS_BINARY}}': lambda: _OPS.prompt_binary(),
    '{{LEAF_PRICE}}': lambda: ' '.join(_LF.FIELDS_BASE + _LF.LEAVES_DERIVED),
    '{{LEAF_MF}}':    lambda: ' '.join(_LF.MF16),
    '{{LEAF_BARRA}}': lambda: ' '.join(_LF.BARRA_LEAVES),
    '{{LEAF_FA}}':    lambda: ' '.join(_LF.FA_LEAVES),
}


def render_prompt(txt):
    """把 prompt 里的 `{{...}}` 占位符替换为**实时生成**的清单。

    ★ 未识别的占位符**保持原样**（不抛错）—— 无人值守铁律：宁可少注入，不可跑挂。
    """
    for k, fn in _PLACEHOLDERS.items():
        if k in txt:
            txt = txt.replace(k, fn())
    return txt


def unresolved_placeholders(txt):
    """渲染后仍残留的 `{{...}}`（供测试断言"没有漏配的占位符"）。"""
    return sorted(set(re.findall(r'\{\{[A-Z_]+\}\}', txt)))


GEN_SYSTEM = render_prompt(_load_skill('gen_skill', _GEN_SYSTEM_FALLBACK))     # A角(生成侧)
JURY_SYSTEM = render_prompt(_load_skill('jury_skill', _JURY_SYSTEM_FALLBACK))  # B角(审查侧)

# ============================================================ META(代末复盘)
# 原有代末 AI 审查(--ai_critic) 保留为"代级复盘", 非中金候选级, 见 loop_critic.py。


def gen_candidates(diag_txt, cfg_txt, n=10, model=DEFAULT_MODEL):
    """A角子代理: 语义引导生成候选表达式。
    返回 (ok, dict) / (False, reason)。ok=True 时 dict={'hyp','exprs':[...]}。"""
    user_txt = (
        f"本代搜索诊断:\n{diag_txt}\n\n"
        f"本代搜索策略:\n{cfg_txt}\n\n"
        "请给机制族假设(hyp)并据此生成表达式(8~16条), 严格 JSON。")
    ok, resp = ask(GEN_SYSTEM, user_txt, model=model,
                   max_tokens=1800, temperature=0.7,
                   tag='A角生成侧引导(gen_candidates)')
    if not ok:
        return False, resp
    d = _extract_json(resp)
    if not d or not isinstance(d.get('exprs'), list):
        return False, f"JSON解析失败: {resp[:120]}"
    return True, d


def jury_verdict(expr, stat_txt, model=DEFAULT_MODEL):
    """B角子代理: 对单个候选精判。返回 (ok, verdict_dict|reason)。
    ok=True 时 dict={'verdict':'PASS'/'KILL','reason':...}; 解析失败不算 ok。"""
    user_txt = (f"候选表达式: {expr}\n\n候选结构统计:\n{stat_txt}\n\n"
                "给出你的 PASS/KILL 判断(严格 JSON)。")
    ok, resp = ask(JURY_SYSTEM, user_txt, model=model,
                   timeout=90, max_tokens=300, temperature=0.2,
                   tag='B角候选精判(jury_verdict)')
    if not ok:
        return False, resp
    d = _extract_json(resp)
    if not d or d.get('verdict') not in ('PASS', 'KILL'):
        return False, f"JSON解析失败: {resp[:120]}"
    return True, d
