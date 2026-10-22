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

扩展(2026-09-09 一期+二期, 落地记录见 docs/factor_roadmap.md 附录 B):
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
             'fa_gm', 'fa_np_margin', 'fa_roe', 'fa_lev',
             # ★ 2026-09-15 扩展 +7（用户问起「财报数据不是有一堆吗」；roadmap §8.51）
             #   ⚠ **必须追加在末尾** —— 本文件注释写明「顺序即 loop_critic 结构去重时
             #     字符串替换的优先级, 追加新族时放到末尾」✓
             #   实测**逐日截面 rank 相关**（引擎的真实口径）：
             #     fa_pb 最独立（与所有旧叶子最高才 +0.063）· 其余 0.14~0.54 ✓
             #   ⚠ 试过但删掉的 5 个（见 `engine/build_fa_pit.py` 顶部详述）：
             #     覆盖率不够：fa_int_cov(0.01%) · fa_rnd(9.95%) · fa_rnd_cap(2.29%)
             #     信息重复：  fa_roe_wa(与 fa_roe 截面 0.855) · fa_roa(与 fa_np_margin 0.867)
             'fa_pb', 'fa_accrual', 'fa_asset_turn', 'fa_gw',
             'fa_inv_turn', 'fa_recv_turn', 'fa_sell_exp',
             # ★★ 2026-10-14 再 +2（用户："算子里有没有自由现金流/ROE/ROA？" ⇒
             #   ① 加自由现金流 ② ROA 换口径重放）—— 口径**先实测后定**（逐日截面
             #   rank 相关，引擎口径；脚本 `ai_test/dedup_check.py` + `--cand_out`）：
             #   · `fa_fcf_yield` 自由现金流/总市值 = (经营现金流TTM − 资本开支TTM)/日 mktcap
             #     实测与全部 61 个旧叶子的最大 |相关| 仅 **0.485**（barra_earnings_yield）✓
             #     ⚠ 资本开支源里**没有 TTM 版** ⇒ 自己按 YTD 滚 4 季（`build_fa_pit._ttm`）✓
             #   · `fa_ocf_ta` **现金 ROA** = 经营现金流TTM/总资产（实测 **0.553**，fa_accrual）✓
             #   ⚠ **净利润口径的 ROA 实测全部共线、故本版不加** ✗（详见 build_fa_pit 顶部）：
             #     np/总资产 0.844(fa_roe) · 营业利润/总资产 0.834 · np/(总资产−货币资金) 0.824
             #     · ROA 同比 0.947(fa_np_yoy，总资产变化慢 ⇒ 数学必然)
             'fa_fcf_yield', 'fa_ocf_ta']

# ---- 派生/衍生叶子(loop_engine.base_fields 运行时计算, 生成与诊断均可见) ----
LEAVES_DERIVED = ['vwap', 'ret', 'turn_ratio', 'ln_mktcap', 'ln_volume',
                  'overnight', 'intraday', 'amplitude', 'up_shadow', 'down_shadow',
                  'hl_ratio', 'true_range']

# ---- 完整叶子池(候选生成/B角诊断/结构去重的字段全集) ----
# 注意顺序即 loop_critic 结构去重时字符串替换的优先级, 追加新族时放到末尾
# ---- 替代数据（2026-10-22，A 方案：tushare 拉；见 tools/fetch_alt_data.py）----
# ★ 为什么加：现有 63 个叶子全在「量价 / 资金流 / 财报 / Barra」四族，与风格天然纠缠
#   （剥两者后 94% 转负）⇒ 实测 gen194~203 十代 0 入库、calmar2 达标 0 条。
#   这 5 个都是**风格外**的行为数据：两融杠杆、龙虎榜（营业部/机构席位）、大宗交易。
# ⚠ **必须追加在末尾**（本文件已有约定：顺序即 loop_critic 结构去重与库文档的编号依据）
ALT_LEAVES = ['mg_bal_ratio', 'mg_buy_ratio',
              'lhb_net_ratio', 'lhb_inst_ratio', 'block_vol_ratio']

LEAVES = FIELDS_BASE + LEAVES_DERIVED + MF16 + BARRA_LEAVES + FA_LEAVES + ALT_LEAVES

# ---- panel.h5 需 load_panel 读取的字段集合(基础7 + 资金流16) ----
FIELDS = FIELDS_BASE + MF16
