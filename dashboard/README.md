# Loop 挖掘看板（dashboard）

> **用途**：一眼看到「**几个池子在跑 / 跑多少轮 / 各池因子库 / 精选池**」——
> 你说「开 preview」时，不用再问我后端有没有在挖掘 ✓

---

## 一、★★★ 端口只改一个地方（`config.json`）

```
dashboard/config.json        ← ★★★ 唯一端口来源，改这里一处即可
   ├── api/app/settings.py       读它（后端启动）
   ├── backend/run.py            读它（还做端口冲突自检）
   └── web/vite.config.ts        读它（设 /api 代理）
       └── 前端业务代码 src/*.ts   ★ 只请求相对路径 /api/* ⇒ 完全不知道端口
```

**当前端口**（已避开 `qlib_code`）：

| 服务 | 端口 | 备注 |
|---|---|---|
| **本看板 后端** | **8101** | |
| **本看板 前端** | **5273** | |
| ~~qlib_code 前端~~ | `5173` | ⚠ **需避让**（已写在 `reservedPorts`）|
| ~~qlib_code 后端~~ | `8001` | ⚠ **需避让** |
| ~~qlib_code MongoDB~~ | `27017` | ⚠ **需避让** |

> 要改端口：编辑 `dashboard/config.json` 的 `backend.port` / `frontend.port`，
> **前后端会一起跟着变**（前端代码零硬编码端口 —— 有自动检查工具验证）✓
> `run.py` 启动时会**自检**是否与 `reservedPorts` 冲突 ✓

---

## 二、启动

```powershell
# ① 后端（自检 + 启动）
D:\miniconda3\envs\rqdata\python.exe dashboard\api\run.py
#    只自检不启动：  ... run.py --check

# ② 前端（另开一个终端）
cd dashboard\web
npm install          # 首次
npm run dev
```

浏览器打开 **http://127.0.0.1:5273/**（端口见 `config.json`）
后端 API 文档：**http://127.0.0.1:8101/docs**

依赖（后端）：`pip install -r dashboard/api/requirements.txt`

---

## 三、看板能看到什么

| 页签 | 内容 |
|---|---|
| **池运行状态** | 每池：**在跑/空闲** · 当前库 · 已测候选 · 跑过代数 · 最新代 · L2 候选流水 · 冻结数 · 失败库 |
| **因子库** | 各池（全A/300/500/1000/50）的因子总览表 + ★ **口径说明** |
| **精选池** | L3 双闸门后的精选因子（剥风格档 / 剥 Calmar / 完整表达式 / 下游须知）|
| **进程** | 相关 python 进程（调度 `run_tracks` / 引擎 `loop_engine` / 守望 `loop_watch`）|
| **配置/口径** | 端口来源 · 保留端口 · 项目路径 · API 清单 |

### ★★ 重要口径（"三个数字不一样"）

`factor_library_<池>.md` 里"当前有几个因子"其实有**三个数**：

| 口径 | 含义 | 权威性 |
|---|---|---|
| **`当前库`**（来自 `engine/loop_state[_<池>].pkl` 的 `bank`）| **当前有效库**（引擎实际在用的对照集）| ★ **权威**（看板以此为准）|
| 表格行数 | **累计入库编号**（该文件自己写着「**只增不改**」）| 参考 |
| 文件声明"当前 N 个入库" | 引擎同步时的**快照，可能落后** | ⚠ 可能过期 |

> 实测（2026-09-15）：`300` → 3 / 2 / 2 · `500` → 5 / 3 / 3 · `1000` → **10 / 4 / 5**
> ⇒ 看板一律以 **`当前库`（state.bank）** 为准，并把另两个作为口径说明一并给出 ✓

---

## 四、数据来源（全部只读，不改引擎）

| 看板数据 | 来源 |
|---|---|
| 池是否在跑 | Windows 进程查询（`loop_engine` / `run_tracks` / `loop_watch`）|
| 当前库 / 已测 / 冻结 | `engine/loop_state{,_300,_500,_1000,_50}.pkl`（★ **宽容 Unpickler**，不需 import 引擎）|
| 跑过多少代 | `docs/loop_journal{,_300,_500,_1000}.md` 的 `## 第 N 代` 块 |
| L2 候选流水 | `docs/loop_archive{,_300,_500,_1000}.csv` |
| 因子库清单 | `docs/factor_library{,_300,_500,_1000}.md` |
| 精选池 | `docs/factor_pool_selected.md` + `docs/loop_strip_style_bank.csv` |
| 池内观测 | `docs/loop_pool_obs{,_300,_500,_1000}.csv` |

---

## 五、★ 下一步：往「聚宽因子看板 + PostgreSQL」靠

已预留（`config.json` 的 `database` 段）：

```json
"database": { "enabled": false, "url": "", "schema": "loop" }
```

- 后端已有 `/api/factors/flat`：把各池库展平成**统一字段**记录
  （`code / pool / gen / family / summary / status / expr / calmar / stripCalmar / grade / annEx / ic / turn`）
  ⇒ 将来直接 `INSERT` 到 PG ✓
- 目标形态参考 [聚宽因子看板](https://www.joinquant.com/view/factorlib/list)：**因子列表 + 详情 + 绩效曲线** ✓

---

## 六、API 一览

```
GET /api/health          健康
GET /api/meta            配置透明化（端口从哪来 / 路径 / 版本）
GET /api/status          ★ 池运行状态快照（?fresh=true 强制重查进程）
GET /api/pools           池定义
GET /api/library         全部池的因子库
GET /api/library/{pool}  单池因子库（含 caliber 口径说明）
GET /api/selected        ★ 精选池（L3 双闸门）
GET /api/strip-bank      剥风格评估档
GET /api/pool-obs/{pool} 池内观测（?limit=）
GET /api/factors/flat    扁平化（面向 PG 导入）
```

---

## 七、文件结构

```
dashboard/
├── config.json              ★★★ 端口唯一来源
├── README.md                本文件
├── api/
│   ├── requirements.txt
│   ├── run.py               启动器（读 config.json + 端口冲突自检）
│   └── app/
│       ├── settings.py      配置加载（端口唯一读取处）
│       ├── main.py          FastAPI 应用 + 路由
│       └── sources/
│           ├── core.py      宽容 pickle / 文本 / CSV / journal 代数 / 缓存
│           ├── pools.py     池运行状态（进程 + 代数 + state + archive 四路交叉）
│           └── factors.py   因子库（各池 + 精选 + 剥风格 + 池内观测）
└── web/
    ├── package.json
    ├── vite.config.ts       ★ 读 ../config.json 设 proxy
    ├── index.html
    └── src/
        ├── api.ts           ★ 只请求相对路径 /api/*
        ├── App.tsx          看板主界面
        └── styles.css
```
