# -*- coding: utf-8 -*-
"""
因子公式注册表 —— 每个因子的经济学含义与计算式
notation:
  ret=日收益率, C=收盘(前复权), O=开, H=高, L=低, V=成交量, AMT=成交额(turnover)
  MC=总市值, TR=换手率(AMT/MC), VWAP=AMT/V, PC=昨收
  MFX=大单+特大单净流入/成交额, MFN=净流入/成交额
  mean(x,w)=w日均值, std(x,w)=w日标准差, corr(x,y,w)=w日相关
  pos(x,w)=(x-min(x,w))/(max(x,w)-min(x,w))  区间位置0~1
  delta(x,n)=x-x.shift(n), rank(·)=截面排名0~1
"""

FORMULA = {
    # ============ Round1: 动量/反转 ============
    'rev_1d': ('反转', '-ret', '1日反转'),
    'rev_5d': ('反转', '-mean(ret,5)', '5日反转'),
    'mom20_rev': ('反转', '-mean(ret,20)', '20日反转'),
    'mom60': ('动量', 'mean(ret,60)', '60日动量'),
    'price_pos20': ('反转', '-pos(C,20)', '价格在20日区间的相对位置(反向)'),
    'price_pos60': ('反转', '-pos(C,60)', '价格在60日区间的相对位置(反向)'),
    # ============ Round1: 波动率 ============
    'vol20': ('波动', '-std(ret,20)', '低波动(20日)'),
    'vol60': ('波动', '-std(ret,60)', '低波动(60日)'),
    'vol_ratio': ('波动', '-std(ret,20)/std(ret,60)', '短期波动相对长期(低=波动收敛)'),
    'vol_chg': ('波动', '-std(ret,20)/std(ret,20).shift(20)', '波动率变化(低=波动下降)'),
    # ============ Round1: 流动性/换手 ============
    'amt_log': ('流动性', '-log(mean(AMT,20)+1)', '小成交额(20日均)'),
    'amt_chg': ('流动性', 'mean(AMT,5)/mean(AMT,60)', '成交额放量'),
    'turn20': ('流动性', '-mean(TR,20)', '低换手率'),
    'turn_vol': ('流动性', '-std(TR,20)', '换手率稳定性'),
    'turn_chg': ('流动性', 'mean(TR,5)/mean(TR,60)', '换手率放大'),
    # ============ Round1: 量价关系 ============
    'corr_vr20': ('量价', '-corr(V,ret,20)', '量价相关性(20日)'),
    'corr_vr60': ('量价', '-corr(V,ret,60)', '量价相关性(60日)'),
    'corr_cp20': ('量价', '-corr(C,V,20)', '价量相关性'),
    'vol_ret_div': ('量价', '-std(ret,20)/mean(TR,20)', '单位换手的波动'),
    # ============ Round1: 资金流(moneyflow3) ============
    'mf_xl5': ('资金流', 'mean(MFX,5)', '大单特大单净流入占比(5日)'),
    'mf_xl10': ('资金流', 'mean(MFX,10)', '大单特大单净流入占比(10日)'),
    'mf_xl20': ('资金流', 'mean(MFX,20)', '大单特大单净流入占比(20日)'),
    'mf_xl_trd': ('资金流', 'delta(mean(MFX,10),10)', '资金流趋势(近10日减前10日)'),
    'mf_xl_vol': ('资金流', '-std(MFX,20)', '资金流稳定性'),
    'mf_net10': ('资金流', 'mean(MFN,10)', '净流入占比(10日)'),
    'mf_net20': ('资金流', 'mean(MFN,20)', '净流入占比(20日)'),
    'mf_net_trd': ('资金流', 'delta(mean(MFN,10),10)', '净流入趋势'),
    # ============ Round1: 价格结构/影线 ============
    'upper_shadow': ('价格结构', '-(H-max(O,C))/(H-L)', '上影线占比(反向)'),
    'lower_shadow': ('价格结构', '(min(O,C)-L)/(H-L)', '下影线占比'),
    'close_pos': ('价格结构', '-(C-L)/(H-L)', '收盘在日内区间位置(反向)'),
    'hl_range': ('价格结构', '-(H-L)/C', '日内振幅(反向)'),
    'amp20': ('价格结构', '-mean((H-L)/C,20)', '20日平均振幅(反向)'),
    'down_shadow': ('价格结构', 'mean((min(O,C)-L)/(H-L),20)', '20日平均下影线'),
    # ============ Round1: 跳空/日内 ============
    'gap': ('跳空', '-(O-PC)/PC', '跳空幅度(反向)'),
    'gap20': ('跳空', '-mean((O-PC)/PC,20)', '20日平均跳空(反向)'),
    'intraday': ('日内', '-(C-O)/O', '日内涨跌(反向)'),
    'intraday20': ('日内', '-mean((C-O)/O,20)', '20日平均日内涨跌(反向)'),
    'vwap_dev': ('日内', '-(C-VWAP)/VWAP', '收盘相对VWAP偏离(反向)'),
    'vwap_dev20': ('日内', '-mean((C-VWAP)/VWAP,20)', '20日平均VWAP偏离(反向)'),

    # ============ Round2: 成交额参数扰动 ============
    'amt_log3': ('流动性', '-log(mean(AMT,3)+1)', '小成交额(3日)'),
    'amt_log5': ('流动性', '-log(mean(AMT,5)+1)', '小成交额(5日)'),
    'amt_log10': ('流动性', '-log(mean(AMT,10)+1)', '小成交额(10日)'),
    'amt_log20': ('流动性', '-log(mean(AMT,20)+1)', '小成交额(20日)'),
    'amt_log40': ('流动性', '-log(mean(AMT,40)+1)', '小成交额(40日)'),
    'amt_log60': ('流动性', '-log(mean(AMT,60)+1)', '小成交额(60日)'),
    'amt_log120': ('流动性', '-log(mean(AMT,120)+1)', '小成交额(120日)'),
    'amt_rank20': ('流动性', '-pos(AMT,20)', '成交额在区间位置(反向)'),
    'amt_std20': ('流动性', '-std(AMT,20)', '成交额稳定性(反向)'),
    'amt_cv20': ('流动性', '-std(AMT,20)/mean(AMT,20)', '成交额变异系数(反向)'),
    'turnmc5': ('流动性', '-log(mean(TR,5)+1e-8)', '低换手率(5日)'),
    'turnmc10': ('流动性', '-log(mean(TR,10)+1e-8)', '低换手率(10日)'),
    'turnmc20': ('流动性', '-log(mean(TR,20)+1e-8)', '低换手率(20日)'),
    'turnmc60': ('流动性', '-log(mean(TR,60)+1e-8)', '低换手率(60日)'),
    'turnmc_rank20': ('流动性', '-pos(TR,20)', '换手率区间位置(反向)'),
    'turnmc_std20': ('流动性', '-std(TR,20)', '换手率稳定性(反向)'),
    'turnmc_chg': ('流动性', '-mean(TR,5)/mean(TR,60)', '换手率变化(反向)'),
    'ln_mktcap': ('市值', '-log(MC)', '小市值(对数总市值)'),
    # ============ Round2: 资金流族 ============
    'mfxl3': ('资金流', 'mean(MFX,3)', '资金流(3日)'),
    'mfxl5': ('资金流', 'mean(MFX,5)', '资金流(5日)'),
    'mfxl10': ('资金流', 'mean(MFX,10)', '资金流(10日)'),
    'mfxl20': ('资金流', 'mean(MFX,20)', '资金流(20日)'),
    'mfxl60': ('资金流', 'mean(MFX,60)', '资金流(60日)'),
    'mfxl_pos20': ('资金流', 'pos(MFX,20)', '资金流区间位置'),
    'mfxl_pos60': ('资金流', 'pos(MFX,60)', '资金流区间位置(60日)'),
    'mfxl_std20': ('资金流', '-std(MFX,20)', '资金流稳定性'),
    'mfxl_div': ('资金流', 'mean(MFX,5)/(std(MFX,20)+1e-8)', '资金流强度/波动'),
    'mfxl_max20': ('资金流', 'max(MFX,20)', '20日最大净流入'),
    'mfxl_min20': ('资金流', 'min(MFX,20)', '20日最大净流出'),
    'mfxl_trd20': ('资金流', 'delta(mean(MFX,10),10)', '资金流趋势'),
    'mfxl_cons20': ('资金流', 'mean(MFX>0,20)', '20日净流入为正的天数占比'),
    'mfxl_cons60': ('资金流', 'mean(MFX>0,60)', '60日净流入为正的天数占比'),
    'mfxl_str': ('资金流', 'mean(MFX,20)*mean(MFX>0,20)', '资金流强度x持续性'),
    'mfnet5': ('资金流', 'mean(MFN,5)', '净流入(5日)'),
    'mfnet20': ('资金流', 'mean(MFN,20)', '净流入(20日)'),
    'mfnet60': ('资金流', 'mean(MFN,60)', '净流入(60日)'),
    'mfnet_pos20': ('资金流', 'pos(MFN,20)', '净流入区间位置'),
    'mfnet_cons20': ('资金流', 'mean(MFN>0,20)', '净流入为正天数占比'),
    # ============ Round2: 交叉因子 ============
    'ix_amt_rev5': ('交叉', 'rank(amt_log20)*rank(rev_5d)', '小成交额 x 反转'),
    'ix_amt_mom20': ('交叉', 'rank(amt_log20)*rank(mom20)', '小成交额 x 动量'),
    'ix_amt_mfxl': ('交叉', 'rank(amt_log20)*rank(mfxl20)', '小成交额 x 资金流'),
    'ix_mfxl_rev': ('交叉', 'rank(mfxl10)*rank(rev_5d)', '资金流 x 反转'),
    'ix_amt_turnmc': ('交叉', 'rank(amt_log20)*rank(turnmc20)', '小成交额 x 低换手'),
    'mix_amt_rev': ('交叉', '0.5*rank(amt_log20)+0.5*rank(rev_5d)', '小成交额与反转等权'),
    # ============ Round2: 新结构 ============
    'up_dn_vol': ('波动结构', '-mean(ret+,20)/mean(ret-,20)', '上行波动/下行波动(反向)'),
    'ret_pos20': ('动量', 'pos(C,20)', '价格位置(正向)'),
    'accel': ('动量', 'mean(ret,5)-mean(ret,20)', '动量加速度'),
    'vol_price_corr': ('量价', '-corr(V,C,20)', '量价相关(成交量vs价格)'),
    'amt_price_corr': ('量价', '-corr(AMT,C,20)', '额价相关'),
    'body_ratio': ('价格结构', 'mean(|C-O|/(H-L),20)', '实体占比'),
    'close_high': ('价格结构', '-mean((H-C)/(H-L),20)', '收盘距最高(反向)'),
    'close_low': ('价格结构', 'mean((C-L)/(H-L),20)', '收盘距最低'),
    'ret_vol20': ('交叉', '-std(ret,20)*log(mean(AMT,20)+1)', '低波动 x 成交额'),
    'turn_amp': ('交叉', '-mean(TR,20)*mean((H-L)/C,20)', '换手 x 振幅(反向)'),

    # ============ Round4: BARRA CNE5 风格因子 ============
    'barra_size': ('BARRA', 'barra.size', '市值暴露(高=大市值)'),
    'barra_non_linear_size': ('BARRA', 'barra.non_linear_size', '非线性市值(中盘)'),
    'barra_momentum': ('BARRA', 'barra.momentum', '动量暴露'),
    'barra_liquidity': ('BARRA', 'barra.liquidity', '流动性暴露(高=高换手)'),
    'barra_book_to_price': ('BARRA', 'barra.book_to_price', '账面市值比(价值)'),
    'barra_leverage': ('BARRA', 'barra.leverage', '杠杆暴露'),
    'barra_growth': ('BARRA', 'barra.growth', '成长暴露'),
    'barra_earnings_yield': ('BARRA', 'barra.earnings_yield', '盈利收益率'),
    'barra_beta': ('BARRA', 'barra.beta', '贝塔暴露'),
    'barra_residual_volatility': ('BARRA', 'barra.residual_volatility', '残差波动暴露'),
    'barra_comovement': ('BARRA', 'barra.comovement', '共动性暴露'),

    # ============ Round5: 财报/基本面(PIT, 按 info_date 对齐) ============
    # 记号: NI=归母净利润TTM, NPT=净利润TTM, REV=营收TTM, CFO=经营现金流TTM,
    #      EBIT=ebitTTM, GP=毛利TTM, EQ=归母权益, TA=总资产, TL=总负债,
    #      CA/CL=流动资/负债, AR=应收, INV=存货, MC=总市值, SH=总股本,
    #      lag4(x)=去年同期(x 的 4 个季度前), 全部按公告日(info_date)生效
    'ep_ttm': ('财报-估值', 'NI/MC', '盈利收益率(归母TTM/市值)'),
    'ep_ttm_all': ('财报-估值', 'NPT/MC', '盈利收益率(全部净利润TTM/市值)'),
    'bp': ('财报-估值', 'EQ/MC', '账面市值比'),
    'sp_ttm': ('财报-估值', 'REV/MC', '营收市值比'),
    'cfp_ttm': ('财报-估值', 'CFO/MC', '现金流市值比'),
    'gp_mc': ('财报-估值', 'GP/MC', '毛利市值比'),
    'ebit_ev': ('财报-估值', 'EBIT/(MC+TL)', 'EBIT/简化企业价值'),
    'roe_ttm': ('财报-盈利', 'NI/EQ', 'ROE(归母TTM)'),
    'roe_waa': ('财报-盈利', 'return_on_equity_weighted_average', '加权ROE(YTD累计)'),
    'roa_ttm': ('财报-盈利', 'NPT/TA', 'ROA(TTM)'),
    'roic_ttm': ('财报-盈利', 'EBIT/(TA-CL)', 'ROIC(EBIT/投入资本)'),
    'gross_margin_ttm': ('财报-盈利', 'GP/REV', '毛利率TTM'),
    'net_margin_ttm': ('财报-盈利', 'NPT/REV', '净利率TTM'),
    'op_margin_ttm': ('财报-盈利', 'operating_profitTTM/REV', '营业利润率TTM'),
    'cost_ratio_neg': ('财报-盈利', '-operating_costTTM/REV', '成本率(反向)'),
    'eps_ttm': ('财报-盈利', 'NI/SH', 'EPS(归母TTM/总股本)'),
    'gp_asset': ('财报-盈利', 'GP/TA', '毛利率资产比(Novy-Marx)'),
    'rev_yoy': ('财报-成长', 'operating_revenue/lag4(operating_revenue)-1', '营收同比(YTD)'),
    'np_yoy': ('财报-成长', 'net_profit_parent_company/lag4(..)-1', '归母净利同比(YTD)'),
    'npttm_yoy': ('财报-成长', 'NPT/lag4(NPT)-1', '净利润TTM同比'),
    'revttm_yoy': ('财报-成长', 'REV/lag4(REV)-1', '营收TTM同比'),
    'dednp_yoy': ('财报-成长', 'net_profit_deduct_../lag4(..)-1', '扣非净利同比(YTD)'),
    'eps_yoy': ('财报-成长', 'basic_earnings_per_share/lag4(..)-1', 'EPS同比(YTD)'),
    'cfottm_yoy': ('财报-成长', 'CFO/lag4(CFO)-1', '经营现金流TTM同比'),
    'roe_chg': ('财报-成长', 'ROE-lag4(ROE)', 'ROE同比变化'),
    'margin_chg': ('财报-成长', '净利率-lag4(净利率)', '净利率同比变化'),
    'asset_growth_neg': ('财报-成长', '-(TA/lag4(TA)-1)', '资产扩张(反向)'),
    'equity_growth': ('财报-成长', 'EQ/lag4(EQ)-1', '净资产同比'),
    'cfo_np': ('财报-质量', 'CFO/NPT', '净利润现金含量'),
    'accrual_neg': ('财报-质量', '-(NPT-CFO)/TA', '应计项目(反向,低=利润实在)'),
    'debt_asset_neg': ('财报-质量', '-TL/TA', '资产负债率(反向)'),
    'current_ratio': ('财报-质量', 'CA/CL', '流动比率'),
    'equity_liab': ('财报-质量', 'total_equity/TL', '权益负债比'),
    'asset_turnover': ('财报-质量', 'REV/TA', '总资产周转率'),
    'ar_ratio_neg': ('财报-质量', '-AR/REV', '应收占营收比(反向)'),
    'inv_asset_neg': ('财报-质量', '-INV/TA', '存货占比(反向)'),
    'nonrecur_neg': ('财报-质量', '-non_recurring_pnl/net_profit', '非经常损益占比(反向)'),
    'ln_assets': ('财报-规模', 'log(TA)', '总资产对数(市值镜像, 中性化后应归零)'),
    'ln_equity': ('财报-规模', 'log(EQ)', '净资产对数'),
    'ln_shares': ('财报-规模', 'log(SH)', '总股本对数'),
    'circ_ratio': ('财报-规模', 'circulation_a_shares/SH', '流通股比例'),

    # ============ Round5b: 单季口径 / 业绩超预期 ============
    # sq(x) = 单季值 = YTD(q) - YTD(q-1), Q1 时 sq = YTD
    # growth(a,b) = (a-b)/|b|  (用绝对值缩放, 负基数不失真)
    'sq_np_yoy': ('财报-成长', 'growth(sq(归母净利), sq(归母净利,-4季))', '单季归母净利同比'),
    'sq_rev_yoy': ('财报-成长', 'growth(sq(营收), sq(营收,-4季))', '单季营收同比'),
    'sq_np_qoq': ('财报-成长', 'growth(sq(归母净利), sq(归母净利,-1季))', '单季净利环比'),
    'sq_rev_qoq': ('财报-成长', 'growth(sq(营收), sq(营收,-1季))', '单季营收环比'),
    'ttm_np_chg': ('财报-成长', 'growth(NPT, lag1(NPT))', '净利润TTM环比变化率'),
    'ttm_rev_chg': ('财报-成长', 'growth(REV, lag1(REV))', '营收TTM环比变化率'),
    'ttm_cfo_chg': ('财报-成长', 'growth(CFO, lag1(CFO))', '经营现金流TTM环比变化率'),
    'ttm_gp_chg': ('财报-成长', 'growth(GP, lag1(GP))', '毛利TTM环比变化率'),
    'sue_np': ('财报-成长', '(sq-sq(-4季))/std(sq(-1..-8季))', '标准化业绩惊喜SUE'),
    'sq_margin': ('财报-盈利', 'sq(归母净利)/sq(营收)', '单季净利率'),
    'sq_margin_chg': ('财报-盈利', 'sq净利率 - 去年同期sq净利率', '单季净利率同比变化'),
    'sq_gp_margin': ('财报-盈利', '(GP-lag1(GP))/(REV-lag1(REV))', '单季毛利率'),
    # ============ Round5c: 复合因子 ============
    'combo_margin': ('财报-复合', 'mean(rank(net_margin_ttm), rank(op_margin_ttm), rank(sq_margin))',
                     '利润率复合'),
    'combo_profit': ('财报-复合', 'mean(rank(7个盈利因子))',
                     '盈利能力复合(净利率/营业利润率/单季净利率/ROIC/ROE/ROA/毛利资产比)'),
    'combo_growth': ('财报-复合', 'mean(rank(sq_np_yoy), rank(ttm_np_chg), rank(sq_rev_yoy), '
                                  'rank(ttm_rev_chg), rank(sue_np))', '单季成长复合(唯一稳健正信号)'),

    # ============ Round6: 聚宽(JQ) indicator/valuation 风格 ============
    # 记号补充: TOTREV=营业总收入TTM, OP=营业利润TTM, TP=利润总额TTM, CASH=货币资金,
    #          avgEQ=(EQ+lag4(EQ))/2, avgTA=(TA+lag4(TA))/2,
    #          sq_ttm(x)=x-lag1(x) 即TTM差=单季滚动值, ID=有息负债(短贷+长贷+应付债券)
    'roe_avg': ('JQ-盈利', 'NI/avgEQ', 'ROE(平均净资产口径, JQ定义)'),
    'roa_avg': ('JQ-盈利', 'NPT/avgTA', 'ROA(平均总资产口径, JQ定义)'),
    'sell_exp_neg': ('JQ-费用', '-selling_expense/operating_revenue', '销售费用率(反向)'),
    'admin_exp_neg': ('JQ-费用', '-administration_expenseTTM/TOTREV', '管理费用率(反向)'),
    'fin_exp_neg': ('JQ-费用', '-financial_expenseTTM/TOTREV', '财务费用率(反向)'),
    'op_exp_neg': ('JQ-费用', '-operating_expenseTTM/TOTREV', '营业费用率(反向)'),
    'total_cost_neg': ('JQ-费用', '-total_operating_costTTM/TOTREV', '营业总成本率(反向)'),
    'gp_margin2': ('JQ-盈利', 'GP/TOTREV', '毛利率(营业总收入口径)'),
    'ocf_to_revenue': ('JQ-现金流', 'CFO/REV', '经营现金流/营业收入'),
    'ocf_to_opprofit': ('JQ-现金流', 'CFO/OP', '经营现金流/营业利润(利润含金量)'),
    'sale_cash_to_rev': ('JQ-现金流', 'cash_received_from_sales_of_goods/operating_revenue',
                         '销售收现比(收入含金量)'),
    'cash_ratio': ('JQ-偿债', 'CASH/CL', '现金比率'),
    'quick_ratio': ('JQ-偿债', '(CA-INV)/CL', '速动比率'),
    'ocf_to_asset': ('JQ-现金流', 'CFO/TA', '经营现金流/总资产(现金回报)'),
    'op_profit_to_profit': ('JQ-质量', 'OP/TP', '营业利润/利润总额(主业占比)'),
    'inv_profit_neg': ('JQ-质量', '-ni_from_value_changeTTM/TP', '价值变动净收益占比(反向)'),
    'ded_to_profit': ('JQ-质量', 'net_profit_deduct_non_recurring_pnl/net_profit',
                      '扣非净利润/净利润(盈利质量)'),
    'op_profit_to_asset': ('JQ-盈利', 'OP/TA', '营业利润/总资产'),
    'inc_total_rev_yoy': ('JQ-成长', 'growth(TOTREV, lag4(TOTREV))', '营业总收入TTM同比'),
    'inc_rev_yoy': ('JQ-成长', 'growth(REV, lag4(REV))', '营业收入TTM同比'),
    'inc_op_profit_yoy': ('JQ-成长', 'growth(OP, lag4(OP))', '营业利润TTM同比'),
    'inc_np_yoy': ('JQ-成长', 'growth(NPT, lag4(NPT))', '净利润TTM同比'),
    'inc_np_sh_yoy': ('JQ-成长', 'growth(NI, lag4(NI))', '归母净利TTM同比'),
    'inc_total_rev_qoq': ('JQ-成长', 'growth(TOTREV, lag1(TOTREV))', '营业总收入TTM环比'),
    'inc_op_profit_qoq': ('JQ-成长', 'growth(OP, lag1(OP))', '营业利润TTM环比'),
    'sq_op_yoy': ('JQ-成长', 'growth(sq_ttm(OP), sq_ttm(OP,-4季))', '单季营业利润同比'),
    'sq_np_yoy2': ('JQ-成长', 'growth(sq_ttm(NPT), sq_ttm(NPT,-4季))', '单季净利润同比(TTM差口径)'),
    'int_debt_neg': ('JQ-风险', '-ID/TA', '有息负债率(反向)'),
    'debt_to_equity_neg': ('JQ-风险', '-TL/EQ', '产权比率(反向)'),
    'goodwill_neg': ('JQ-风险', '-goodwill/TA', '商誉占比(反向)'),
    'rnd_ratio': ('JQ-其他', 'rnd_to_revenue', '研发费用率(覆盖仅27%, 参考)'),

    # ============ Round7: 基本面成长复合(唯一跨口径可用的因子) ============
    'combo_g6': ('成长-复合', 'mean(rank(inc_op_profit_qoq), rank(inc_total_rev_qoq), '
                             'rank(sq_op_yoy), rank(sq_np_yoy2), rank(ocf_to_asset))',
                 '★基本面成长复合(五虎): 四口径同向为正, 与市值因子正交, 分段稳定'),
    'combo_all': ('成长-复合', 'mean(rank(G6五虎), rank(G5b五因子))', '十因子成长复合'),
    'combo_qoq': ('成长-复合', 'mean(rank(inc_op_profit_qoq), rank(inc_total_rev_qoq), '
                               'rank(ttm_np_chg), rank(ttm_rev_chg))', '纯环比族复合'),
    'combo_sq': ('成长-复合', 'mean(rank(sq_op_yoy), rank(sq_np_yoy2), rank(sq_np_yoy), '
                              'rank(sq_rev_yoy), rank(sue_np))', '单季同比族复合'),
}


def get_formula(name):
    """返回 (分类, 公式, 说明); 未登记返回占位"""
    if name in FORMULA:
        return FORMULA[name]
    if name.startswith('S:'):
        return get_formula(name[2:])
    return ('其他', '(见代码)', name)
