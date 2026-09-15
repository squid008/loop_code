import os
import pandas as pd

# 基于脚本所在目录拼出绝对路径，避免在不同工作目录下运行时找不到文件
script_dir = os.path.dirname(os.path.abspath(__file__))
pkl_path = os.path.join(script_dir, 'vol2015-01-01-2015-05-01.pkl')

result = pd.read_pickle(pkl_path)

# 目前只需导出 stock_positions 和 trades 两个表
# 想导出其他表时，把对应行取消注释即可
EXPORT_KEYS = [
    'stock_positions',
    'trades',
    # 'summary',                 # 回测汇总指标（dict）
    # 'portfolio',               # 每日账户净值
    # 'benchmark_portfolio',     # 基准每日净值
    # 'stock_account',           # 股票账户信息
    # 'positions_weight',        # 每日持仓权重统计
    # 'yearly_risk_free_rates',  # 年度无风险利率
]

for key in EXPORT_KEYS:
    value = result[key]
    if isinstance(value, pd.DataFrame):
        df = value
    elif isinstance(value, dict):
        # dict 转成两列：指标名 / 值
        df = pd.DataFrame(list(value.items()), columns=['metric', 'value'])
    else:
        print(f'跳过无法导出为表格的 key: {key} (类型: {type(value).__name__})')
        continue

    csv_path = os.path.join(script_dir, f'{key}.csv')
    df.to_csv(csv_path, encoding='utf-8-sig')
    print(f'已导出: {csv_path} (共 {len(df)} 行)')

print('\n全部导出完成。')
