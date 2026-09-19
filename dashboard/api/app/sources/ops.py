# -*- coding: utf-8 -*-
"""算子手册（看板「算子手册」按钮的数据源）—— **中文说明 + 用法** ✓

## 为什么需要它（用户 2026-09-19）
用户看到公式 ts_std100(mul(cs_demean(hl_ratio), ts_mean5(cs_demean(turn_ratio))))
说不知道 cs_demean 什么意思 ⇒ 要在首页「立即刷新」旁加个**算子手册**按钮，
点开是**带滚动条的弹窗**，列出各算子的中文含义 ✓

## ★ 一条纪律：算子名单**不在这里抄** ✗
名单的**唯一事实源**仍是 `engine/ops_registry.py`（它本身就是为了防名单漂移而建的 ✓）⇒
本模块只做两件事：
  ① `import ops_registry`，用 `unary_names() / binary_names()` **派生**全部算子名 ✓
     （这两个函数**自包含**：不传 fastops / local_ns 也能列名 ⇒ 不会把引擎整套依赖拖进来 ✓）
  ② 给每个**前缀**加中文（`OPS_ZH`）+ 给每个**字段**加中文（`FIELDS_ZH`）✓
守门 `tools/_test_ops_manual.py` 钉住「派生出的每个前缀 / 每个字段都必须有中文」✗（防漏 ✓）

## ⚠ 文案纪律（`tools/_test_ui_quotes.py` 会扫本文件 ✓）
本模块的字符串**会直接渲染到看板**⇒ **不许出现引号**（「」『』“”‘’ 全禁 ✗），
也不要用 ★ ✓ ✗ ⇒ 这类工程符号 ⇒ 一律写成自然中文句子 ✓
"""
import os
import sys

from . import core   # noqa: F401  （复用它的路径解析：settings.ENGINE ✓）

if core.ENGINE not in sys.path:
    sys.path.insert(0, core.ENGINE)

import ops_registry as OPS      # noqa: E402
import loop_fields as LF        # noqa: E402

# ================================================================ 算子中文（按前缀）
# 格式：前缀 -> (中文名, 一句话说明)
OPS_ZH = {
    # ---- 时序 ts_（同一只股票沿时间算）----
    'ts_mean':  ('时序均值', '过去若干期的平均值，窗口越长越平滑'),
    'ts_std':   ('时序标准差', '过去若干期的波动幅度，越大越不稳'),
    'ts_max':   ('时序最大值', '过去若干期内的最高值'),
    'ts_min':   ('时序最小值', '过去若干期内的最低值'),
    'ts_rank':  ('时序分位', '当前值在过去若干期里排第几成，取值 0 到 1，抗极端值'),
    'ts_delay': ('时序滞后期', '若干期之前的值，做变化率时用'),
    'ts_delta': ('时序差分', '当前值减去若干期之前的值，看变化量'),
    'ts_sum':   ('时序求和', '过去若干期的累加值'),
    'ts_slope': ('时序斜率', '过去若干期对时间做回归的斜率，即趋势的方向与力度'),
    'ts_rsqr':  ('时序拟合优度', '回归的 R 方，衡量走势有多接近一条直线'),
    'ts_resi':  ('时序残差', '剔掉线性趋势之后剩下的部分，即偏离趋势的程度'),
    'ts_skew':  ('时序偏度', '分布的不对称程度，看尖峰偏在涨的一侧还是跌的一侧'),
    'ts_kurt':  ('时序峰度', '分布的尖峰与厚尾程度'),
    # ---- 截面 cs_（同一时刻在所有股票之间算）----
    'cs_rank':   ('截面分位', '当天把所有股票排序后取百分位，取值 0 到 1，最抗极端值'),
    'cs_demean': ('截面去均值', '当天减去全市场均值，只保留相对高低，去掉大盘共同涨跌'),
    'cs_scale':  ('截面标准化', '当天按截面均值与标准差归一，让不同日子可比'),
    # ---- 指数均线 ----
    'ema':      ('指数均线', '指数移动平均，越近的样本权重越大，比普通均值灵敏'),
    # ---- 通用变换 ----
    'log':      ('对数', '取对数，压缩量纲并把乘性关系变成加性'),
    'abs':      ('绝对值', '取绝对值，只关心幅度不关心方向'),
    'neg':      ('取负', '整体取负号，用来翻转因子方向'),
    'sign':     ('符号', '只取正负号，得到加一、减一或零'),
    # ---- 双目 ----
    'add':      ('相加', '两个表达式逐点相加'),
    'sub':      ('相减', '前者减后者，做差值或构造超额'),
    'mul':      ('相乘', '两个表达式逐点相乘，常用来做条件筛选或放大信号'),
    'div':      ('相除', '前者除后者，做比率，分母接近零时记为缺失'),
    'corr':     ('时序相关', '过去若干期两条序列的相关系数，看共振还是背离'),
    'min':      ('取较小', '逐点取两者中较小的那个'),
    'max':      ('取较大', '逐点取两者中较大的那个'),
}

# ================================================================ 字段中文（叶子）
FIELDS_ZH = {
    'close': ('收盘价', '当日收盘价'),
    'open': ('开盘价', '当日开盘价'),
    'high': ('最高价', '当日最高价'),
    'low': ('最低价', '当日最低价'),
    'vwap': ('成交均价', '成交额除以成交量'),
    'volume': ('成交量', '当日成交股数'),
    'turnover': ('成交额', '当日成交金额'),
    'mktcap': ('总市值', '当日总市值'),
    'ln_mktcap': ('对数市值', '总市值取对数，规模风格常用形态'),
    'ln_volume': ('对数成交额', '成交额取对数，衡量流动性'),
    'ret': ('日收益', '当日涨跌幅'),
    'turn_ratio': ('换手率', '成交股数除以流通股数，衡量相对活跃度'),
    'overnight': ('隔夜收益', '今开除以昨收再减一，即隔夜跳空'),
    'intraday': ('日内收益', '今收除以今开再减一，即盘中涨跌'),
    'amplitude': ('振幅', '最高价与最低价之差除以昨收'),
    'up_shadow': ('上影线', '最高价与开收价较高者的差除以昨收，代表上方抛压'),
    'down_shadow': ('下影线', '开收价较低者与最低价的差除以昨收，代表下方支撑'),
    'hl_ratio': ('高低位置比', '收盘价在当日最高最低区间里的位置，越接近一表示收在偏上'),
    'true_range': ('真实波幅', '含跳空的当日波幅，取高低差与跳空幅度的最大值'),
    'barra_size': ('规模', 'Barra 风格：市值规模，大票为正'),
    'barra_non_linear_size': ('非线性规模', 'Barra 风格：中盘偏离，刻画大小票之外的那一段'),
    'barra_momentum': ('动量', 'Barra 风格：过去一段时间的涨跌惯性'),
    'barra_liquidity': ('流动性', 'Barra 风格：换手与成交额相关的活跃度'),
    'barra_book_to_price': ('账面市值比', 'Barra 风格：净资产除以市值，价值属性'),
    'barra_leverage': ('杠杆', 'Barra 风格：负债水平'),
    'barra_growth': ('成长', 'Barra 风格：盈利与收入的增速'),
    'barra_earnings_yield': ('盈利收益率', 'Barra 风格：盈利除以价格'),
    'barra_beta': ('贝塔', 'Barra 风格：相对市场的敏感度'),
    'barra_residual_volatility': ('残差波动', 'Barra 风格：剔掉市场因素后的个股波动'),
    'barra_comovement': ('共同波动', 'Barra 风格：与同类股票一起波动的程度'),
    # 财务（PIT：按公告日可见，不含未来信息）
    'fa_np_yoy': ('净利润同比', '财务：净利润同比增速'),
    'fa_rev_yoy': ('营收同比', '财务：营业收入同比增速'),
    'fa_op_yoy': ('营业利润同比', '财务：营业利润同比增速'),
    'fa_ocf_yoy': ('经营现金流同比', '财务：经营现金流同比增速'),
    'fa_gm': ('毛利率', '财务：毛利除以营收'),
    'fa_np_margin': ('净利率', '财务：净利润除以营收'),
    'fa_roe': ('净资产收益率', '财务：净利润除以净资产'),
    'fa_lev': ('资产负债率', '财务：总负债除以总资产'),
    'fa_pb': ('市净率', '财务：市值除以净资产'),
    'fa_accrual': ('应计项', '财务：应计利润占比，衡量盈余质量'),
    'fa_asset_turn': ('总资产周转率', '财务：营收除以总资产'),
    'fa_gw': ('商誉占比', '财务：商誉除以总资产'),
    'fa_inv_turn': ('存货周转率', '财务：营业成本除以存货'),
    'fa_recv_turn': ('应收周转率', '财务：营收除以应收账款'),
    'fa_sell_exp': ('销售费用率', '财务：销售费用除以营收'),
}

# 资金流：四档单量乘四种口径，程序生成（免得手工抄十六行 ✓）
_MF_SIZE = {'s': '小单', 'm': '中单', 'l': '大单', 'x': '超大单'}
_MF_KIND = {'buy': ('买入额', '主动性买入金额'),
            'sell': ('卖出额', '主动性卖出金额'),
            'bqty': ('买入量', '主动性买入股数'),
            'sqty': ('卖出量', '主动性卖出股数')}
for _s, _sz in _MF_SIZE.items():
    for _k, (_kn, _kd) in _MF_KIND.items():
        FIELDS_ZH['mf_%s_%s' % (_s, _k)] = ('%s%s' % (_sz, _kn),
                                           '资金流：%s的%s' % (_sz, _kd))

NOTES = [
    ('命名规则', 'ts_ 开头表示沿时间算，同一只股票的历史；cs_ 开头表示当天在所有股票之间算'),
    ('窗口数字', '算子名末尾的数字就是窗口期数，ts_mean5 用过去 5 期，ts_std100 用过去 100 期，日频即 100 个交易日'),
    ('cs_demean 是干什么的', '当天减去全市场均值，只留下相对高低，去掉大盘共同涨跌，所以数值本身没有绝对意义'),
    ('cs_rank 为什么常用', '当天排序取百分位，最抗极端值，本项目整条链路都是这类秩基口径'),
    ('怎么写公式', '先写算子再写括号，mul(a, b) 表示 a 乘 b，ts_std100(x) 表示对 x 取过去 100 期的标准差'),
]


def manual():
    """给 /api/ops 用：算子、字段、说明（全部中文 ✓）"""
    ops = []
    for prefix, wins, _bind, group in OPS.UNARY_SPECS:
        zh, tip = OPS_ZH.get(prefix, ('（缺中文说明）', ''))
        for w in (wins if wins else [None]):
            nm = prefix if w is None else '%s%d' % (prefix, w)
            ops.append({
                'name': nm, 'zh': zh, 'tip': tip, 'group': group,
                'kind': 'unary', 'window': w, 'sig': '%s(x)' % nm,
                'winText': ('不涉及窗口' if w is None else '过去 %d 期' % w),
            })
    for prefix, wins, _bind, group in OPS.BINARY_SPECS:
        zh, tip = OPS_ZH.get(prefix, ('（缺中文说明）', ''))
        for w in (wins if wins else [None]):
            nm = prefix if w is None else '%s%d' % (prefix, w)
            ops.append({
                'name': nm, 'zh': zh, 'tip': tip, 'group': group,
                'kind': 'binary', 'window': w, 'sig': '%s(a, b)' % nm,
                'winText': ('逐点运算' if w is None else '过去 %d 期' % w),
            })
    fields = []
    for nm in LF.LEAVES:
        zh, tip = FIELDS_ZH.get(nm, ('（缺中文说明）', ''))
        fields.append({'name': nm, 'zh': zh, 'tip': tip})
    return {
        'ops': ops,
        'fields': fields,
        'notes': [{'k': k, 'v': v} for k, v in NOTES],
        'counts': {'ops': len(ops), 'fields': len(fields)},
        'source': '名单来自 engine/ops_registry.py（唯一事实源），中文说明来自本模块',
    }
