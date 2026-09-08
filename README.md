# loop_code — Loop 式因子自动挖掘引擎

从 `D:\rqalpha_demo` 整理迁移（2026-09-08），原目录保留备份。机器外部数据依赖：米筐 bundle `E:\rq`（本地数据盘）。

## 目录结构
- `engine/` — **Loop 挖掘引擎（可独立运行，相互引用均用相对自身路径）**
  - `loop_engine.py` 主引擎（五维演化 + 跨量纲审查 + 失败模式库 + FSA 冻结 + 两级筛选 + 费后验证）
  - `loop_critic.py` B角诊断（每代自动写 gen 建议进 journal）
  - `loop_status.py` 进度/进程/档案查询
  - `factor_miner.py` 因子挖掘基础框架（panel 加载/预筛选/两段式验证）
  - `fastops.py` L1 向量化快速算子
  - `panel.h5` / `universe.h5` L1 筛选用数据（由 `build_*.py` 从 E:\rq 重建）
  - `loop_state.pkl` / `loop_archive.csv` 引擎滚动状态（运行中会变）
  - `_check_*.py` 机制自检（dry-run 零误杀验证）
- `docs/` — 结论文档：`loop_journal.md`（B角代际诊断）/ `factor_roadmap.md`（研发留痕、续做入口）/ `factor_archive.md/.csv`（因子归档）
- `strategies/` — 定稿 rqalpha 回测策略：`all01/`（all00/01/03 + factor_snapshot 数据）、`all04/`（barra 落地 + g6 数据）、`vol/`、`big_small/`，共享 `bt_utils.py`
- `research/` — 早期挖掘轮次 `round*.py` 与专题研究脚本（方法留档；运行需与 `engine` 同目录或放回原 `ai_test` 全套依赖）

## 运行
```powershell
# 引擎一代（后台）：参数与三道闸详见 loop_engine.py argparse
cd D:\loop_code\engine
D:\miniconda3\envs\rqdata\python.exe loop_engine.py --gen=13 --n=800 --l2=30 --seed=123

# 进度查询
D:\miniconda3\envs\rqdata\python.exe loop_status.py

# 定稿策略回测（示例）
cd D:\loop_code\strategies\all04
D:\miniconda3\envs\rqdata\python.exe all04.py
```

## 说明
- 引擎所有文件读写都相对 `engine/` 定位，`loop_code` 可整体搬移；唯一外部依赖是 `E:\rq` 数据盘。
- `loop_state.pkl` 当前进度为 gen12 结束态（种子 18 / 入库因子 8 / 冻结骨架 1 / 失败库 28 条）。
- 数据文件（*.h5/*.pkl）体积大且可由 `build_*.py` 重建，git 入库时按 `.gitignore` 排除。
