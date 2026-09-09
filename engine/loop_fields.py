# -*- coding: utf-8 -*-
"""
叶子字段单一事实源(2026-09-09 扩展一期+二期后抽取)
==================================================
A角 loop_engine(生成侧) / B角 loop_critic(审查侧) 的叶子白名单必须完全一致:
所有可生成 / 可诊断 / 语义引导的字段名集中在此定义。任何模块**不得**自行硬编码
叶子名列表, 否则新增字段族会出现"引擎能生成、B角/LLM 却认不出"的漂移
(历史教训: loop_critic 曾两处硬编码旧 12 字段, 与引擎 21 字段池脱节)。

字段族速查:
  P  价格(close/open/high/low/vwap)
  V  股数(volume; mf_*_bqty/sqty, 由手×100)
  A  金额(turnover 成交额元; mf_*_buy/sell, 由万元×1e4)
  M  市值(mktcap)
  R  比率/收益率/风格暴露/财报 PIT 比率
  L  对数标尺(ln_mktcap/ln_volume)

扩展(2026-09-09 一期+二期, 详见 docs/loop_ext_leaves_v1.md):
  1. 资金流 moneyflow3 原始拆分 16 列: 面板列名即叶子名, 净额不预焊由 GP 自组合;
  2. BARRA 连续风格 11 个(barra.h5, 行业哑变量不入叶);
  3. 财报 PIT as-of 比率 8 个(fa_pit.h5, 按 info_date 对齐, 无未来函数)。
"""
# ---- 基础量价 7(panel.h5 基础块, 引擎 load_panel 直接读) ----
FIELDS_BASE = ['close', 'open', 'high', 'low', 'volume', 'turnover', 'mktcap']

# ---- 资金流原始拆分 moneyflow3: 金额(×1e4 元, 量纲A) + 量(×100 股, 量纲V) ----
MF16 = ['mf_s_buy', 'mf_m_buy', 'mf_l_buy', 'mf_x_buy',
        'mf_s_sell', 'mf_m_sell', 'mf_l_sell', 'mf_x_sell',
        'mf_s_bqty', 'mf_m_bqty', 'mf_l_bqty', 'mf_x_bqty',
        'mf_s_sqty', 'mf_m_sqty', 'mf_l_sqty', 'mf_x_sqty']

# ---- BARRA 连续风格(barra.h5; 行业哑不入叶) / 财报 PIT as-of 比率(fa_pit.h5) ----
BARRA_KEYS = ['size', 'non_linear_size', 'momentum', 'liquidity', 'book_to_price',
              'leverage', 'growth', 'earnings_yield', 'beta', 'residual_volatility',
              'comovement']
BARRA_LEAVES = ['barra_' + k for k in BARRA_KEYS]
FA_LEAVES = ['fa_np_yoy', 'fa_rev_yoy', 'fa_op_yoy', 'fa_ocf_yoy',
             'fa_gm', 'fa_np_margin', 'fa_roe', 'fa_lev']

# ---- 派生/衍生叶子(loop_engine.base_fields 运行时计算, 生成与诊断均可见) ----
LEAVES_DERIVED = ['vwap', 'ret', 'turn_ratio', 'ln_mktcap', 'ln_volume',
                  'overnight', 'intraday', 'amplitude', 'up_shadow', 'down_shadow',
                  'hl_ratio', 'true_range']

# ---- 完整叶子池(候选生成/B角诊断/结构去重的字段全集) ----
# 注意顺序即 loop_critic 结构去重时字符串替换的优先级, 追加新族时放到末尾
LEAVES = FIELDS_BASE + LEAVES_DERIVED + MF16 + BARRA_LEAVES + FA_LEAVES

# ---- panel.h5 需 load_panel 读取的字段集合(基础7 + 资金流16) ----
FIELDS = FIELDS_BASE + MF16
