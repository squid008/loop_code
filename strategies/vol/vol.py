# from rqalpha_try.rqalpha import run_func
from rqalpha import run_func

#from rqalpha_try.rqalpha import run_func
import pandas as pd
from time import time
'''
conda activate rq
python vol.py
'''
# ===================== 策略参数（集中在这里改） =====================
# ---- 回测区间 ----
start_date = "2015-01-01"
end_date = "2018-07-09"                 # 此处注释掉就是最新的数据
# ---- 策略 ----
select_num = 20                         # 选股数量
# ---- 交易成本 ----
stock_min_commission = 5                # 股票最小手续费，单位元，默认 5
stock_commission_multiplier = 0.5       # 股票佣金倍率，默认佣金万八，0.5 即万四，0.125 即万1
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

    scheduler.run_weekly(rebalance,tradingday=1)                # 周一调仓
    context.select_num = select_num

def handle_bar(context, bar_dict):
    pass


def rebalance(context, bar_dict):

    current_date = context.now.strftime("%Y-%m-%d")
    print(current_date)

    df = pd.DataFrame(index=all_instruments(type='CS')['order_book_id'])

    # ============================ 前置过滤 ============================
    ser = df.index

    normal_set_not_st = {s for s in ser if not is_st_stock(s)}
    normal_set_not_suspended = {s for s in ser if not is_suspended(s)}
    not_limit_set = {s for s in ser if (bar_dict[s] is not None and bar_dict[s].limit_up > bar_dict[s].last)}

    tradable_set = normal_set_not_st & normal_set_not_suspended & not_limit_set

    df = df[df.index.isin(tradable_set)]

    # ============================选股===============================
    df["turnover"] = [bar_dict[s].total_turnover for s in df.index]

    # 成交额最低的context.select_num只股票
    df = df.sort_values(by="turnover").head(context.select_num)

    # 权重总和留出 5% 现金缓冲，覆盖手续费，避免满仓导致最后几只资金不足拒单
    df["weight"] = 0.95 / df.shape[0]
    target_stocks = dict(zip(df.index, df["weight"]))

    # 清仓（get_positions() 返回当前所有持仓对象，替代已过时的 account.positions）
    # 跳过停牌持仓：停牌卖不掉，硬发卖单会被拒，反而挤占可用资金，导致后面多只买单连环拒单
    current_positions = {p.order_book_id for p in get_positions()}
    to_close = current_positions - set(target_stocks) - {s for s in current_positions if is_suspended(s)}
    target_stocks.update({s: 0 for s in to_close})
    order_target_portfolio(target_stocks)

    # 输出本次调仓选出的股票，按成交额从小到大排序，并附调仓后的实际持仓数量（聚宽风格日志）
    pos_quantity = {p.order_book_id: p.quantity for p in get_positions()}
    for i, (s, row) in enumerate(df.iterrows(), 1):
        logger.info(f"{i:>2}. {s}: {row['turnover']:.2f}  持仓 {pos_quantity.get(s, 0)}")


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
            'data_bundle_path':r'E:\rq\bundle',  # 配置bundle路径 ，不配置就是默认路径
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