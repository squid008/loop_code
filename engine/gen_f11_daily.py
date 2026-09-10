# -*- coding: utf-8 -*-
"""
gen_f11_daily.py —— 从 engine/panel.h5 生成 F11 日频因子面板(入库方向 = -F11)
F11 原始: ts_mean60( (H/L) / low * intraday^2 * ret );  engine 入库取反(正IC), 故存 -F11
输出: strategies/all04/f11_daily.pkl  { 'raw': DataFrame(int日期 x obid), 与 g6_daily 同构 }
用法: cd D:\\loop_code\\engine && D:\\miniconda3\\envs\\rqdata\\python.exe gen_f11_daily.py
"""
import os
import sys
import time

import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import factor_miner as fm

OUT = r"D:\loop_code\strategies\all04\f11_daily.pkl"
t0 = time.time()

P = fm.load_panel()
P = fm.prepare(P)
cl = P["close"].astype("float64")
o, h, l = P["open"].astype("float64"), P["high"].astype("float64"), P["low"].astype("float64")
lo = l.where(l > 1e-9)
intraday = cl / o - 1.0
hl_ratio = h / lo
with np.errstate(divide="ignore", invalid="ignore"):
    f11 = (hl_ratio / l) * intraday * intraday * P["ret"]
f11 = fm.ts_mean(f11, 60)            # rolling(60, min_periods=30).mean()
fac = -f11                            # 取反入库(正 IC 方向)
print("F11 覆盖 %.1f%%, 形态 %s, 耗时 %.0fs" %
      (100 * float(np.isfinite(fac.values).mean()), fac.shape, time.time() - t0))
os.makedirs(os.path.dirname(OUT), exist_ok=True)
fac.to_pickle(OUT)
print("已保存:", OUT)
print("index[0/2]:", fac.index[:2].tolist(), "末:", fac.index[-1])
print("cols[:3]:", list(fac.columns[:3]), " 全部列数", fac.shape[1])
