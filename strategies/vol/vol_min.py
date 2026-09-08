# -*- coding: utf-8 -*-
# 分钟线回测版：周一 9:35 调仓
# 选股因子 = 「最近一个完整交易日（T-1）」的全天成交额 total_turnover（昨日收盘后的数据）
# 成交价   = 周一 9:35 那一分钟 bar 的收盘价（matching_type 默认 current_bar，即以当前 bar 收盘价撮合）
from rqalpha import run_func
import pandas as pd
from time import time

'''
conda activate rqdata
python vol_min.py
'''
t = time()


def init(context):
    # 每周一 9:35 执行选股 + 调仓（575 = 9*60 + 35）
    scheduler.run_weekly(rebalance, tradingday=1, time_rule=575)
    context.select_num = 20


def handle_bar(context, bar_dict):
    pass


def rebalance(context, bar_dict):
    current_datetime = context.now.strftime("%Y-%m-%d %H:%M:%S")
    print(current_datetime)

    df = pd.DataFrame(index=all_instruments(type='CS')['order_book_id'])

    # ============================ 前置过滤（T 日 9:35 时点） ============================
    ser = df.index

    normal_set_not_st = {s for s in ser if not is_st_stock(s)}
    normal_set_not_suspended = {s for s in ser if not is_suspended(s)}
    not_limit_set = {s for s in ser if (bar_dict[s] is not None and bar_dict[s].limit_up > bar_dict[s].last)}

    tradable_set = normal_set_not_st & normal_set_not_suspended & not_limit_set
    df = df[df.index.isin(tradable_set)]

    # ============================ 选股：用「昨日收盘」数据 ============================
    # 分钟回测的 handle_bar 中调用 history_bars(s, 1, '1d') 返回的是 T-1 日 day bar
    turnover = {}
    for s in df.index:
        h = history_bars(s, 1, '1d', fields='total_turnover', skip_suspended=True)
        if h is not None and len(h):
            turnover[s] = float(h[-1])
    df['turnover'] = pd.Series(turnover, dtype=float)
    df = df.dropna(subset=['turnover'])
    df = df[df['turnover'] > 0]

    # 昨日成交额最低的 context.select_num 只股票
    df = df.sort_values(by="turnover").head(context.select_num)

    df["weight"] = 1 / df.shape[0]
    target_stocks = dict(zip(df.index, df["weight"]))

    # 清仓（不在目标中的持仓全部卖掉）
    current_positions = {p.order_book_id for p in get_positions()}
    target_stocks.update({s: 0 for s in current_positions - set(target_stocks)})

    order_target_portfolio(target_stocks)


if __name__ == '__main__':
    import os
    start_date = "2015-01-01"
    end_date = "2015-03-31"  # 先用短区间验证分钟回测能否跑通
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               os.path.splitext(os.path.basename(__file__))[0] + start_date + "-" + end_date)
    __config__ = {
        "base": {
            "start_date": start_date,
            "end_date": end_date,
            "frequency": "1m",  # 分钟线回测
            "accounts": {
                "stock": 10000000
            },
            'data_bundle_path': r'E:\rq\bundle',
        },
        "mod": {
            "sys_analyser": {
                "enabled": True,
                "plot": False,
                "benchmark": "000300.XSHG",
                "output_file": output_path + ".pkl",
                "plot_save_file": output_path + ".png",
            },
            "sys_transaction_cost": {
                "cn_stock_min_commission": None,
                "stock_min_commission": 5,
                "stock_commission_multiplier": 0.125,
                "futures_commission_multiplier": 1,
                "tax_multiplier": 1,
                "pit_tax": False,
            },
        }
    }
    run_func(init=init, handle_bar=handle_bar, config=__config__)
    print(__config__["base"])
    print(f"运行时间: {time() - t:.6f} 秒")
