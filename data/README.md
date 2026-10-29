# data/ —— 拉取类数据（不入库）

这里放**从外部接口拉下来**的数据，与代码（`engine/` / `tools/`）分开。
`data/` 下除本文件外**全部被 `.gitignore` 忽略**（`data/*` + `!data/README.md`）。

| 文件 / 目录 | 来源 | 重建命令 | 约 |
|---|---|---|---|
| `rc_parts/rc_YYYYMMDD_YYYYMMDD.parquet` | tushare `report_rc`（券商盈利预测），**每 7 天一个分片** | `python tools/fetch_rc_data.py --start=... --end=...` | 0.1 MB / 分片 |
| `rc_data.parquet` | 上面所有分片的合并明细 | `python tools/fetch_rc_data.py --build-only` | 76 MB（全历史） |
| `rc_factors.h5` | 聚合后的因子矩阵（`(日期 × 股票)`，供引擎读） | `python tools/build_rc_factors.py` | 待定 |

## 为什么要分片

`report_rc` 有两条硬限制（2026-10-29 实测）：

* **10 次/小时** 的总配额（不是 1 次/分钟那种瞬时限制）
* **单次最多 5000 行**，超了**静默截断** —— 1 个月/10 天都会撞上限 ⇒ 只能**按 7 天**切

⇒ 全历史约 700 个分片 ≈ **3 天**；近 1 年 52 个 ≈ **5 小时**。
分片是为了**断点续拉**：中途断了只丢当前那 7 天，不会白跑几小时。

## 与 `engine/*.h5` 的区别

`engine/panel.h5`、`barra.h5`、`fa_pit.h5`、`alt_data.h5` 是**已构建好的面板字段**，
由 `engine/build_*.py` 从原始数据（`E:\rq`，经 `engine/loop_env.py` 解析）生成，属于「项目自带的输入」。
`data/` 则是**从联网接口拉下来的原始/中间数据**。两者都不入库，但性质不同，故分开放。
