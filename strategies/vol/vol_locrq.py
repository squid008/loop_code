import pandas as pd
from rqalpha_try.rqalpha import run_func   # 原版是 from rqalpha import run_func
# ---- 回测区间 ----
start_date = "2015-01-01"
end_date = "2018-07-09"                 # 此处注释掉就是最新的数据
# ---- 策略 ----
select_num = 20                         # 选股数量
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

def init(context):
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

    for p in context.stock_account.positions:
        if p not in target_stocks:
            order_target_value(p, 0)
    for s in target_stocks:
        order_target_percent(s, target_stocks[s])

__config__ = {
    "base": {
        "start_date": start_date,
        "end_date": end_date,
        "accounts": {"stock": 1000000},      # 股票账户初始资金
        "benchmark": "000300.XSHG",          # 基准；不要基准就写 None
        # "mmap_data_service": "E:/rq",      # 本地跑必须写；网页端由服务端注入，写了不生效
    },
    "extra": {
        "log_level": "info",                 # verbose / debug / info / warning / error
    },
    "mod": {
        # 与仓库里已有对账数据同一口径：万一佣金（0.125 倍）、最低 5 元、印花税 1 倍
        "sys_transaction_cost": {
            "cn_stock_min_commission": None,
            "stock_min_commission": 5,
            "stock_commission_multiplier": 5,
            "futures_commission_multiplier": 1,
            "tax_multiplier": 1,
            "pit_tax": False,}
    }}
if __name__ == "__main__":
    # 回测入口。config 就是上面的 __config__ —— 策略和参数在同一个文件里。
    # 返回 {summary, portfolio, trades, stock_positions}；网页端会接走它画曲线列指标。
    result = run_func(init=init, handle_bar=handle_bar, config=__config__)
    print("total_returns =", result["summary"]["total_returns"])
    