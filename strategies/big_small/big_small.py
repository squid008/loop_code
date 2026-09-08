from rqalpha import run_func
#from rqalpha_try.rqalpha import run_func
import pandas as pd
from time import time
'''
conda activate rq
python big_small.py
'''
# ===================== 策略参数（集中在这里改） =====================
# ---- 回测区间 ----
start_date = "2014-11-18"
end_date = "2026-07-09"                 # 此处注释掉就是最新的数据
# ---- 大小盘轮动策略（参考 https://www.python88.com/topic/134681）----
# 核心逻辑：每日收盘前计算大盘/小盘指数"前20个交易日"涨跌幅，次日持有涨幅更好者；
# 开启空仓优化后，若大小盘涨幅均 <0，则次日空仓。
lookback = 20                           # 计算涨跌幅的窗口（交易日），网页默认前20日
big_index = "000300.XSHG"               # 大盘指数：沪深300
small_index = "000852.XSHG"             # 小盘指数：中证1000（若 bundle 缺该指数可换 000905.XSHG 中证500 或 399006.XSHE 创业板指）
enable_cashout = True                   # 空仓优化：大小盘涨幅均 <0 则次日空仓（网页优化版）
enable_plot_extra = True                # 方案B：用 plot() 把 策略/沪深300/中证1000 三条线画进收益图 png
# ---- 交易成本 ----
stock_min_commission = 5                # 股票最小手续费，单位元，默认 5
stock_commission_multiplier = 5         # 股票佣金倍率，默认佣金万八，0.5 即万四，0.125 即万1
tax_multiplier = 1                      # 印花税倍率，股票默认印花税千分之一，单边收取
pit_tax = False                         # 是否使用回测当时时间点对应的真实印花税率
# ---- 撮合（成交量限制）----
volume_limit = True                     # 每 bar 累计成交不超过市场总成交量的 volume_percent 比例；False 可全成交
volume_percent = 0.25                   # 可成交数量占市场总成交量比值，仅在 volume_limit=True 时生效,0.25是米筐默认
inactive_limit = True                   # 是否对"当前 bar 无成交量"的股票拒单；False 允许成交额极小的票成交（对齐聚宽需 False）
# ===================================================================

t = time()
def init(context):
    # 将 user_log 输出格式改成聚宽风格：时间 - INFO  -  消息
    from rqalpha.utils.logger import user_log
    from logbook import StderrHandler
    user_log.handlers = [StderrHandler(
        format_string='{record.time:%Y-%m-%d %H:%M:%S} - {record.level_name}  -  {record.message}',
        bubble=False)]

    # 每日收盘前判断，次日持仓
    scheduler.run_daily(rebalance)
    context.lookback = lookback
    context.big_index = big_index
    context.small_index = small_index
    context.enable_cashout = enable_cashout
    context.initial_cash = 10000000      # 与 __config__ 里的初始资金保持一致

def handle_bar(context, bar_dict):
    # 方案B：每天把 策略净值/沪深300/中证1000 三个序列打点，画进 sys_analyser 生成的收益图
    if not enable_plot_extra:
        return
    # 统一用"收益率"坐标系（起点=0），与 sys_analyser 的累计收益曲线对齐
    strategy_nav = context.portfolio.total_value / context.initial_cash
    plot("策略", strategy_nav - 1)
    big_close = history_bars(context.big_index, 1, '1d', 'close')
    small_close = history_bars(context.small_index, 1, '1d', 'close')
    if big_close is not None and len(big_close):
        if not hasattr(context, 'big_ref'):
            context.big_ref = big_close[-1]
        plot("沪深300", big_close[-1] / context.big_ref - 1)
    if small_close is not None and len(small_close):
        if not hasattr(context, 'small_ref'):
            context.small_ref = small_close[-1]
        plot("中证1000", small_close[-1] / context.small_ref - 1)


def _calc_ret(context, order_book_id):
    """计算指数"前 lookback 个交易日"的涨跌幅（含当日收盘）。"""
    # history_bars 返回时间升序的收盘价数组，最后一个为当前 bar
    close = history_bars(order_book_id, context.lookback + 1, '1d', 'close')
    if close is None or len(close) < context.lookback + 1:
        return None
    return close[-1] / close[0] - 1.0


def rebalance(context, bar_dict):
    current_date = context.now.strftime("%Y-%m-%d")
    big_ret = _calc_ret(context, context.big_index)
    small_ret = _calc_ret(context, context.small_index)

    if big_ret is None or small_ret is None:
        logger.info(f"{current_date} - 指数历史数据不足，跳过")
        return

    # 空仓优化：两者涨幅均 <0 则次日空仓
    if context.enable_cashout and big_ret < 0 and small_ret < 0:
        target = None
        action = "空仓"
    else:
        target = context.big_index if big_ret >= small_ret else context.small_index
        action = f"持有 {target}"

    logger.info(f"{current_date} - 大盘[{context.big_index}]20日涨跌={big_ret*100:.2f}%  "
                f"小盘[{context.small_index}]20日涨跌={small_ret*100:.2f}%  =>  {action}")

    # 调仓：只持有一只指数（或空仓）
    positions = {p.order_book_id for p in get_positions()}
    if target is None:
        for s in positions:
            order_target_percent(s, 0)
    else:
        if target not in positions:
            # 先清掉另一只（若有），再满仓买入目标
            for s in positions:
                order_target_percent(s, 0)
        order_target_percent(target, 0.99)


if __name__ == '__main__':
    import os
    # 起止日期统一用顶部变量，保证配置与输出文件名一致
    # 输出路径 = 脚本所在目录 + 脚本文件名（不含扩展名）+ 起止日期，保证 pkl/png 与 vol.py 在同一目录
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               os.path.splitext(os.path.basename(__file__))[0] + start_date + "-" + end_date)
    __config__ = {
        "base": {
            "start_date": start_date,
            "end_date": end_date,
            "accounts": {
                "stock": 10000000
            },
            'data_bundle_path': r'E:\rq\bundle',  # 配置bundle路径 ，不配置就是默认路径
        },
        "mod": {
            "sys_analyser": {
                "enabled": True,
                "plot": False ,
                "benchmark": "000300.XSHG",
                "output_file": output_path + ".pkl",
                "plot_save_file": output_path + ".png",
            },
            "sys_transaction_cost": {
                # 股票最小手续费，单位元（即将废弃）
                "cn_stock_min_commission": None,
                # 以下参数统一用顶部变量，改参数只需改文件顶部
                "stock_min_commission": stock_min_commission,
                "stock_commission_multiplier": stock_commission_multiplier,
                # 期货佣金倍率，即在默认的手续费率基础上按该倍数进行调整，期货默认佣金因合约而异
                "futures_commission_multiplier": 1,
                "tax_multiplier": tax_multiplier,
                "pit_tax": pit_tax,
            },
            "sys_simulation": {
                # 以下参数统一用顶部变量，改参数只需改文件顶部
                "volume_limit": volume_limit,
                "volume_percent": volume_percent,
                "inactive_limit": inactive_limit,
            },
        }
    }
    run_func(init=init,handle_bar=handle_bar,config=__config__)
    print(__config__["base"])
    print(f"运行时间: {time() - t:.6f} 秒")

    # 打印内存占用
    import psutil
    import os
    process = psutil.Process(os.getpid())
    mem_info = process.memory_info()
    print(f"内存占用: RSS={mem_info.rss / 1024 / 1024:.2f} MB, VMS={mem_info.vms / 1024 / 1024:.2f} MB")
