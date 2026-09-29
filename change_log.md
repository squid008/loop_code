# Change Log / 变更日志

本文件**事无巨细**地记录每一次改动。格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [语义化版本 SemVer](https://semver.org/lang/zh-CN/)：
**MAJOR**（不兼容改动）· **MINOR**（向后兼容的功能新增）· **PATCH**（向后兼容的修复）。

> ★ **归档约定（2026-09-27 起）**：本文件**只保留最近 15 个版本**，
> 更早的条目整段搬到 [`history/change_log_archive.md`](history/change_log_archive.md)（**原文一字未改** ✓；
> 2026-09-28 从仓库根目录挪进 `history/` ✓ —— 根目录只留活跃文件，历史归 `history/` ✓）。
> 为什么：本文件曾长到 **549 KB / 7683 行 / 154 个版本** ⇒ 查最近改动得先翻过一年份的历史 ✗
> （八维评分里「文档」扣分的正是这一条 ✓）。新增条目照旧写在**最上方** ✓。

> **改动 → 版本 → tag 的动作约定**（沿用 README「版本与回退」）：
> 每次改动 = **一次 commit**；每个版本 = **一个 annotated tag**（`git tag -a vX.Y.Z -F <说明>`）。

---

> ★ **旁注（2026-09-15）**：本文件历史条目里出现的 `docs/history/` 归档区，
> 已于 2026-09-15 整体移到**仓库根 `history/`**（`docs/` 只放活跃文档）。
> 历史条目**有意保留原文**（不改写记录）✓

> ⚠ **归档动作（2026-09-28）**：本文件头部承诺"只保留最近 15 个版本" ✓，而当时已累积 **24 条** ✗（约定只在 v1.24.0 执行过一次 ⇒ 之后每版漂一格 ✗）
> ⇒ 已把最旧的 9 条**整段原文**搬进 `history/change_log_archive.md` ✓（逐字校验 ✓：条目数 旧 = 新 + 搬走、无重复、版本号集合不变 ✓）。

> ⚠ **归档动作（2026-09-29）**：本文件头部承诺"只保留最近 15 个版本" ✓，而当时已累积 **17 条** ✗（约定只在 v1.24.0 执行过一次 ⇒ 之后每版漂一格 ✗）
> ⇒ 已把最旧的 2 条**整段原文**搬进 `history/change_log_archive.md` ✓（逐字校验 ✓：条目数 旧 = 新 + 搬走、无重复、版本号集合不变 ✓）。

> ⚠ **归档动作（2026-09-29）**：本文件头部承诺"只保留最近 15 个版本" ✓，而当时已累积 **16 条** ✗（约定只在 v1.24.0 执行过一次 ⇒ 之后每版漂一格 ✗）
> ⇒ 已把最旧的 1 条**整段原文**搬进 `history/change_log_archive.md` ✓（逐字校验 ✓：条目数 旧 = 新 + 搬走、无重复、版本号集合不变 ✓）。

> ⚠ **归档动作（2026-09-29）**：本文件头部承诺"只保留最近 15 个版本" ✓，而当时已累积 **16 条** ✗（约定只在 v1.24.0 执行过一次 ⇒ 之后每版漂一格 ✗）
> ⇒ 已把最旧的 1 条**整段原文**搬进 `history/change_log_archive.md` ✓（逐字校验 ✓：条目数 旧 = 新 + 搬走、无重复、版本号集合不变 ✓）。

---

## [1.33.0] — 2026-09-29

> 主题：**可移植性平台化「收尾」** —— 把上一版留下的 **6 处** PowerShell/Win32 专有查询
> **全部收进 `engine/os_compat.py`** ✓，于是有了一条**可机器检查的不变量** ✓：
> 「全仓库专有代码只剩 `os_compat` 的 **Windows 分支** ✓（Linux 走它的 POSIX 分支 ✓）」
> ⚠ **引擎数值路径零改动** ✓（本版没碰 `loop_engine`/`loop_eval`/`loop_l1`/`loop_l2` ✗）；
> 三处**开发工具**的输出细节有微调 ⇒ 按 SemVer **MINOR** 如实记 ✓（逐条列在第四节 ✗）。

### 一、为什么要收尾（上一版留下的账）

v1.32.0 已把「可用内存 / 列进程 / 杀进程 / 判存活」四件收敛进 `os_compat` ✓，并替换 5 个文件 ✓；
但当时**如实记账**还剩 4~6 处 PS 查询在调用方各自拼字符串 ✗（`loop_status` · `loop_watch` **×2** ·
`tracks_status` **×2** · `horizon_admit_write` ✓）——它们的**输出字段各不相同** ✗，
所以不能"换个函数名"了事，得逐处改**消费端** ✓。本版就是把这些账结清 ✓。

### 二、本版替换的 6 处（+ 顺手 3 处同源残留 ✗）

| 文件 | 原实现 | 现在 |
|---|---|---|
| `engine/loop_status.py` `running_engine()` | `Get-CimInstance … -match 'loop_engine'` ⇒ `{pid, run, mem}` | `OC.list_procs()` + Python 侧过滤 ✓（**字段不变** ✓） |
| `engine/loop_watch.py` `is_engine_running()` | 同上 + **`shell=True`** ✗ ⇒ 只要**个数** | 新增 `_count_procs(need, forbid)` ✓（判据逐条对齐 ✓） |
| `engine/loop_watch.py` `already_running()` | 同上（`loop_watch`/`--pool`）| 同上 ✓（**`> 1` 含自身** 的语义照旧 ✓） |
| `tools/tracks_status.py` 引擎列表 | `Get-CimInstance … -match 'loop_engine\|run_tracks'` | `OC.list_procs()` ✓ |
| `tools/tracks_status.py` 可用内存 | `Win32_OperatingSystem \| FreePhysicalMemory` ✗ | `OC.mem_status()` ✓ |
| `tools/horizon_admit_write.py` 安全闸 | PS 取 pid 列表 | `OC.list_procs()` ✓ |
| （顺手 ✗）`tools/curves_job_status.py` | **`wmic`** ✗ 进程表 | `OC.list_procs()` ✓ |
| （顺手 ✗）`tools/factor_curves.py` `_pid_alive` | `tasklist /FI "PID eq …"` ✗ | `OC.alive()` ✓（**同一条设计** ✓） |
| （顺手 ✗）`tools/sysinfo.py` CPU 核数 | **`wmic cpu get …`** ✗ | `os.cpu_count()` ✓ |
| （顺手 ✗）`tools/_verify_port_change.py` | PS `Stop-Process` | `OC.kill_tree()` ✓ |
| （顺手 ✗）`tools/_test_dynamic_add.py` | 裸 `taskkill`（清自己起的调度器） | `OC.kill_tree()` ✓ |

★ **两条"值得单独说"的**：
1. `factor_curves._pid_alive` 的 docstring 里存着一条**血泪教训** ✓：_"不能用 `os.kill(pid, 0)` ——
   Windows 上它**会真的杀进程**"_ ✗ —— 而 `os_compat.alive()` **正是同一条设计** ✓（Windows 用
   `tasklist` ✓、POSIX 才用 `os.kill(pid,0)` ✓）⇒ 那条教训**没丢** ✓，只是不再散落在各处 ✗；
2. `curves_job_status._procs()` 原来在异常时 `return {}` ✗，而调用方紧接着 `q['curves']` ⇒
   **会 KeyError 崩掉** ✗✗（与它自己注释里写的"状态脚本不该因为查不到进程就挂"**自相矛盾** ✗）
   ⇒ 现改为**返回全 0** ✓（照它声明的意图 ✓）。⚠ 这是一处**行为修正**，如实记账 ✗。

### 三、验证（★ 逐条对拍，不是"看着对"）

1. ★★ **旧 PS 版 ←→ 新 Python 版「逐条对拍」**（`ai_test/_chk_proc_dual.py` ✓，**全过** ✓）：
   空跑对拍没意义 ✗（没有引擎时两边都是 0 ✓）⇒ 脚本**造一个合成进程**（命令行带
   `loop_engine --mine_pool=999` ✓）让三条判据都真的走到 ✓：
   · 池视角：旧 == 新 == 基线 + 1 ✓；
   · **all 视角：必须排除它** ✓ —— 旧 PS 的负向前瞻 `--mine_pool=(?!all)` 最容易实现错 ✗，
     对拍确认新旧一致（都 0 ✓）✓；
   · `curves_job_status._procs()` 认得出它是"挖矿"（`{'mine': 1}` ✓）；
   · `is_engine_running()` 池视角 True / all 视角 False ✓；
   · 杀掉后两边都回落一致 ✓。
2. ★★ **常驻守门**（`tools/_test_win32_residue.py` ✓ ⇒ **已进全量回归** ✓）：扫
   `engine/`+`tools/`+`dashboard/`（排除注释与说明文字 ✓，判据按**命中位置** ✓）⇒
   **只剩 `engine/os_compat.py` 的 5 处 Windows 分支** ✓✓
   ⇒ 以后谁再散落一处，**发版守门当场报出来** ✓（不再依赖"记得别写" ✗）。
   守门自带两条**判据自证** ✓（喂一行专有代码 ⇒ 必须判违规 ✓；喂一行注释 ⇒ 必须判说明文字 ✓）
   —— 否则"零违规"可能是判据写死了 ✗（本项目一贯要求守门先证明自己有鉴别力 ✓）。
3. **冒烟**：`loop_status.py` / `tracks_status.py` / `sysinfo.py` / `curves_job_status.py` 各真跑一次 ✓
   （输出正常 ✓、`[3] 正在跑的引擎` 正确显示"无" ✓、CPU 逻辑核 12 ✓）。
4. `tools/_test_undefined_names.py` ⇒ **0 处** ✓（181 文件）· `_audit_deadcode`（清掉 4 个变死的 import ✓）·
   `tools/release_check.py`（**55/55**）✓。

### 四、⚠ 如实记账：三处**开发工具的可观察微调**（故本版记 MINOR ✗）

1. `tracks_status` 的进程列表**有意收窄** ✗：原 PS 不限进程名 ⇒ 连**命令行里含这俩词的 shell 包装进程**
   也会列出来 ✗；现在只列 python 进程 ✓（那正是不关心的 ✓，包装进程是噪音 ✓）。
2. `sysinfo` 的 CPU 只报**逻辑核** ✗（原 `wmic` 还给物理核 ✓）—— wmic 在新版 Windows 上**已被移除** ✗，
   换 `os.cpu_count()` 顺带修了这个隐患 ✓；想看物理核请用别的工具 ✓。
3. `horizon_admit_write` 的"安全闸"**原样保留** ✓：查询失败时 `running=[]` ⇒ **放行** ✓ ——
   本版**照旧** ✗（改成"查询失败即拒写"更安全 ✓，但那是**行为变化** ✗，得单独决定 ✓，已在注释里写明 ✓）。

### 五、⚠ 未做 / 不在范围内（不许当成已做 ✗）

* **`ai_test/` 下一次性的排查脚本**（`_kill_mine.py` · `_measure_parallel_mem.py` · `_memprof_1000.py` ·
  `_probe_dynamic_add.py` · `_watch_mining.py` ✓）里仍有 PS/`taskkill` ✗ —— 它们是一次性 scratch ✓
  **不进正式路径** ✓（不变量脚本已按设计排除该目录 ✓）；要用它们请先自己改 ✓。
* **无 Linux 机 ⇒ POSIX 分支仍未真机验证** ✗（`os_compat` 顶部与每个函数都写明了这一点 ✓，
  **不假装验证过** ✗）。⇒ 本版**仍不宣称"可移植性达标"** ✗：真正要跑 Linux 时，
  还需一台 Linux 机把 `os_compat` 的 POSIX 分支 + 看板端到端过一遍 ✓。

---

## [1.32.0] — 2026-09-29

> 主题：**性能 ①②（去相关不再重算 · L2 剥风格不再重算）＋ 飞书通道 ＋ 可移植性平台化（第一段）**
> ⚠ **引擎数值结果零变化** ✓ —— ① 的 A/B：**8 产物逐字节相同** ＋ stdout **只差声明的那 1 行** ✓；
> ② 的 A/B：**8 产物逐字节相同** ＋ stdout **归一化后 0 差异**（连文案都没动 ✓）✓（两个规模各验一遍 ✓）
> ⇒ 属"向后兼容的功能新增 / 结构整治"⇒ SemVer **MINOR** ✓

### 一、① 去相关：把"重算一遍"改成"**批内就地判定**"（一代省约 **25 min** ✓）

**根因（生产日志三处数字互相印证 ✓）**：`_C.VCACHE` 存的是**原始 float64 值**（4.46 MB/条 ✓）
⇒ `--vreuse_cap_mb=800` 只装得下 ~170 条（日志里 `缓存 803MB` = **顶到上限** ✗）
⇒ **539 个候选在"去相关"里被重新求值** ⇒ **1912 s** ✗（≈3.55 s/候选 × 539 ≈ 1910 s ✓ **自洽** ✓✓）。

**改法**：`_l1_batches` 批内**已经**算了 `rs = rank_rows(v[::FWD])`（形状/风格要用的那份 ✓）——
那**正是**去相关循环里 `v = rank_rows(v0)` 要的对象 ✓（同一输入 ⇒ 同一结果 ✓）
⇒ **就地判定** ✓（对照集 `Kr` 只有 **9** 个已知因子 ✓，提到批循环之前建 ✓）
⇒ **零重复求值、零额外内存** ✓✓。
**落点**（`engine/loop_l1.py`）：新增 `_known_rank_map`（`Kr` 的**唯一构造处** ✓）·
`_decorr_keep`（判据，与旧实现**逐字同义** ✓）· `_vreuse_fill`（原 VCACHE 填充块原样搬出 ✓ 守 R1）；
`_l1_batches` 批内判定并回传 `dec_keep / len(Kr) / t_dec` ✓；`_l1_filter` **删掉重算循环** ✗、
只按 `dec_keep` 过滤 ✓（顺手去掉因此变**死参**的 `B`/`bank`/`bank_ext` ✓ 不留幽灵参数 ✓）。
⚠ **保住一处既存怪癖**：旧写法是 `if keep_rows: l1 = pd.DataFrame(keep_rows)` ⇒ **全被拦下时反倒不筛** ✗ ——
本版**照旧不动** ✗（改它 = 改行为 ✗，要改须单独 A/B ✓），只在注释里写明 ✓。

**性能（★ 诚实口径：哪段实测、哪段推算，分开写 ✓）**：
* 旧（生产 `n=800` **实测** ✓）：去相关 **1912 s**、命中 170/709 ⇒ **539 次重算** ✓；
* 相关开销（本版两规模 **实测** ✓）：`19~20 s / 33 个候选` ⇒ **≈0.58 s/候选**；
* ⇒ 709 个候选 ≈ **410 s**（这段是**推算** ✗）⇒ **一代省 ≈ 25 min** ✓。
⚠ **修正先前口算的 31 min** ✗ —— 那是按"相关开销 ≈60 s"估的，实测相关性本身要 0.58 s/候选 ✓。

### 二、② L2 剥风格：**同一份输入不再算两遍**（一代省约 **2.9 min** ✓）

**根因（cProfile 实测 ✓）**：`neutral_rank` **全仓库只有 2 个调用点**，都在 `_l2_strip_dual`，
且**入参逐字相同**（主口径 ✓ / 副 `--dual_fwd` ✓，同一个 `f` ＋ 同一对 `STYLE_FULL` ✓）；
每次内部 4 个**全量** `rank_rows` ⇒ cProfile 实测 **36.3 s / 4 次 = 9.1 s/次** ✗ ⇒ 每候选白算一次 ✗。

**改法**：算一次、副口径**直接复用** ✓。三处保险（都写进了注释 ✓）：
① 复用时给**独立数组**（`np.array(..., copy=True)` ✓，代价仅一次 memcpy）⇒ 与旧代码各自独立算出来的
**完全同语义** ✓（防万一 `evaluate_real` 就地改入参 ✗）；
② `_fn` **先置 None** ⇒ 主口径那次若抛异常（被 `except` 吞掉 ✓），副口径**按原语义补算** ✓ 不静默降级 ✗；
③ `_l2_strip_dual` **102 行** ✓（R1 线 120 ✓）。

**证据**：pool-50（n=12）＋ pool-1000（n=120）各跑 base/after ⇒ **8 产物逐字节相同** ✓ ＋
stdout **归一化后 0 差异**（103↔103 · 134↔134 ✓）✓✓ —— 比①还干净 ✓。
⚠ **墙钟测不出** ✗：这台机器同时跑着**别的项目**（L1 自身就差 6% ✗、after 反而慢 20 s ✗）
⇒ **不拿墙钟当性能证据** ✓；性能数字只用"剖析实测 9.1 s/次 × 19 候选 ≈ **2.9 min/代**"（**推算** ✓）。

### 三、飞书通道：**发**通知（各群独立 webhook）＋ **收**手机回复（共用 app，按 chat_id 隔离）

用户 2026-09-29：_"我飞书开了机器人…可以用来将 IDE 的消息发到飞书，我手机上就能看了；
然后我手机发的信息 WORKBUDDY 能读…**⚠ 注意别串台**" ✓

**落点**：`tools/feishu.py`（从 `E:\quant\trader_code\backend\app\services\feishu.py` **搬来** ✓，
连它踩过的两个坑一起：① `im/v1/messages` 的 `start_time` 是**秒**级 ✗（按毫秒传会被拒 `code=230001`）；
② 判发送成功必须要求字段**存在**且为 0 ✗（写成 `int(d.get("code") or 0) == 0` ⇒ **缺字段被当成成功** ✗）。
**配置**：仓库根 `config.local.json`（★ 已加进 `.gitignore` ✓ —— 内含 `app_secret`，**绝不入库/绝不写进文档** ✗）。

**★★ 别串台（机器已验证 ✓）**：`--find-chat` 实测**同一个 app 在三个群里** ✗ ——
| 群 | chat_id | webhook | 本仓库 |
|---|---|---|---|
| Loop_code机器人 ✓ | `oc_885d4d0d…` | `45300305-…` ✓ | **只许用这个** ✓ |
| Trader_code机器人 ✗ | `oc_c412ecb7…` | `967ecde3-…` ✗ | 硬拦 ✗ |
| Data_wash机器人 ✗ | `oc_47d11dc9…` | 另一个 ✗ | 硬拦 ✗ |
⇒ 工具里 `_FOREIGN_CHAT_IDS` / `_FOREIGN_WEBHOOK_TAILS` **硬拦**"配成了别人的群" ✓（宁可不发，也不发错群 ✗✗）。
★ **反查证据**：发一条测试消息后，用 app 接口逐一列三个群 ⇒ **只有 Loop_code 群含它** ✓
（trader / data_wash 都"否" ✓）—— 这条比"看着发成功"强得多 ✓。

**纪律**（与 trader 一致 ✓）：① 绝不因发通知影响主流程（异常全吞 ✓）；② **收到的聊天文本永远
不当命令执行** ✗（`--poll/--wait` 只落 `ai_test/notify/inbox.jsonl` ✓，"干不干、干什么"由人或调用方定 ✓）；
③ 默认关（没配齐连网络请求都不发 ✓）；④ 不猜、不吞 ✓。

★ **两个实测坑（都记进项目记忆 ✓）**：`--send` 的正文里**带换行会被 shell 拆成多个参数** ✗
（报 `unrecognized arguments`）⇒ 新增 **`--send-file`**（正文写 UTF-8 文件再发 ✓）；
写那个正文文件**只能用编辑器**（`python -c` 的三引号会被 PowerShell 吃掉 ✗ ⇒ 文件没写成、
`--send-file` 反而把**上一条**重发了一遍 ✗✗ —— 发前要确认文件是刚写的 ✓）。
**IDE 侧**：CodeBuddy 的 hooks 文档是 JS 渲染页、抓不到正文 ✗ ⇒ **不猜格式** ✗，
改为"**每条回复由 agent 直接调 `--send`**" ✓（已写进项目记忆 ⇒ 跨会话生效 ✓）。

### 四、可移植性平台化（**第一段 · 未完成** ✗）

新增 **`engine/os_compat.py`**：把"操作系统专有"的四件事**收敛到一处** ✓ ——
可用内存 ✓ / 列进程 ✓ / 杀进程 ✓ / 判存活 ✓；**Windows 分支逐字搬**（类字段、命令行、键名一字不差 ✓），
**POSIX 分支是新增的** ✓（`/proc/meminfo` ✓ · `ps` ✓ · `SIGTERM→SIGKILL` ✓ · `os.kill(pid,0)` ✓）。
⚠ **没有 Linux 机 ⇒ POSIX 分支只能保证"降级不崩 / 尽力而为"，不能保证端到端可用** ✗ ——
每个函数上都写明了它的 POSIX 口径与已知差异 ✓（**不假装验证过** ✗✓）。

**本段已替换 5 个文件** ✓：`tools/parallel_runner.avail_gb`（契约仍是"查不到 ⇒ `inf`" ✓，冒烟同值 ✓）·
`dashboard/api/app/mine.py` ×4（`avail_gb` ✓ / `_alive` ✓ / **两处** `taskkill` ✓ ⇒ 该文件**代码层已无 Win32 专有点** ✓）·
`tools/sysinfo.py`（内存 ＋ 进程表 ✓ 冒烟通过 ✓）· `tools/curves_job_status.py`（内存 ✓）·
`dashboard/api/app/sources/pools.py`（进程列表 ✓，过滤在 Python 里**等价复刻** ✓ ⇒ 下游 `classify_proc()` 一字未改 ✓）。

⚠ **如实记账（未完成 ✗）**：还有 **4 处** PS 列进程没搬（`engine/loop_status` · `engine/loop_watch` ·
`tools/tracks_status` · `tools/horizon_admit_write` ✓）—— 它们的**输出字段各不相同**（要 `run`分钟 /
`pid+cmd` 原文 / 只要**个数** / 只要 pid 串 ✓）⇒ 得逐处改**消费端**，不是换个函数名 ✗ ⇒ 留作下一段 ✓。
**故本版不宣称"可移植性达标"** ✗（八维那一项**先不动** ✓）。

### 五、验证（★ 四条硬证据）

1. **① 的 A/B**：`_ab/v1320_base1000`（旧版=HEAD ✓）←→ `_ab/v1320_after1000`（新版 ✓）⇒
   8 产物逐字节相同 ✓、stdout 只差声明的那 1 行 ✓、**计数完全一致** ✓；
2. **② 的 A/B**：`_ab/v1320_l2base{50,1000}` ←→ `_ab/v1320_l2after{50,1000}` ⇒
   8 产物逐字节相同 ✓、stdout 归一化 **0 差异** ✓；
3. **语义同源的机器证据**：`ai_test/_perf_vcache_probe.py`（`rank_rows` 幂等逐位 ✓ ·
   `corrcoef` 缓存排名 vs 现场 rank **逐位 6/6** ✓）· ② 的判据来自 `ai_test/_perf_l2_prof.py` 的 cProfile ✓；
4. `tools/_test_undefined_names.py` ⇒ **0 处** ✓（181 文件）· `_audit_deadcode`（清掉 2 处新死码 ✓）·
   `tools/release_check.py`（**55/55**）⇒ 全绿 ✓。

★ **守门同步（防护内容一字不减 ✓，只是跟着代码搬位置）**：`tools/_test_stop_scope.py` 会**打桩
`mine.subprocess`** 并断言收到 `['taskkill','/PID','111','/T','/F']` ✓ —— 而本次把 taskkill 搬进了
`os_compat.kill_tree()` ✗ ⇒ 若不同步，`KILLS` 会**永远是空的** ⇒ 这个守门就**再也证明不了"只杀目标池"**
✗✗（典型的"防护静默失效" ✓）。
⇒ 改法：`setup()` 里**再多打一桩** —— 用被测代码自己的取件函数 `mine._OC()` 拿到那个模块、
把它的 `subprocess` 也换成 `FakeSubprocess` ✓（顺带把"`_OC()` 真能取到模块"也证了 ✓）；
**断言一个字没改** ✓（`KILLS` 里仍是同一份 argv ✓）⇒ 单独跑该守门 ⇒ **全部通过** ✓✓。

★ **另一处守门同步**：`tools/_test_engine_mem_budget.py` 断言"`trim_cache_mb` 被调用 **4** 次
（`_LRU` 批末＋批内 · `cache2` 去相关＋去重）" ✗ —— 而 ① 把去相关那个循环删了 ⇒ 它那份 `cache2`
**已经不存在了** ✓ ⇒ 期望值改 **3** ✓；另一条"两处 `cache2` 都接字节版"改**1** ✓
（⚠ 这**不是**"少接一处" ✗：原来该被它裁的缓存已随重算一起消失 ✓；新模块 `_known_rank_map` 里建 `Kr`
用的 `cache2` 与旧代码"bank 批量求值"那段**同形**、**旧版也没裁过** ✓ ⇒ 无回归 ✓，故不新增裁剪点 ✗）。
两条的**判据意图未减弱** ✓（"凡还在用 `cache2` 的地方必须有字节上限" ✓）。

---

## [1.31.0] — 2026-09-29

> 主题：**journal 每代标题下也写"开工时间"** —— `时间: … · 开工 … · 已跑 …`
> （用户 2026-09-29 要求：_"我停了，**让 journal 也写"开工时间"**"_ ✓）
> ⚠ **引擎数值路径零改动** ✓ —— 同 seed A/B：**7 个产物逐字节相同** ＋ journal **只差那一行**
> （3023 行 vs 3023 行 · 差异 **1 行** ✓）＋ stdout **103 行 0 差异** ✓
> ⇒ 属"向后兼容的功能新增"（只是**多写一个字段** ✓）⇒ SemVer **MINOR** ✓

### 一、为什么（用户的真实痛点）

journal 之前每代只有"**诊断落档时刻**"一个时间 ✓（`loop_log` 落地的 v1.26.0 ✓），
而"这一代**什么时候开的工**"无处可查 ✗ —— 想知道"这代跑了多久 / 卡没卡 / 开工到落档隔了几小时"，
只能去翻 `ai_test/_tracks/` 下面的日志 ✗。⇒ 本版把**开工**（= 本代引擎进程启动时刻 ✓）写进 journal ✓。

### 二、落点（4 个文件，改动极小）

| 位置 | 改动 |
|---|---|
| `engine/loop_log.py` | `stamp()` 加第三态 `finished=False` ⇒ `时间: … · 开工 … · 已跑 …` ✓（**格式仍只有一份实现** ✓）|
| `engine/loop_critic.py` | `report(diag, sug, reasons, path, t0=None)` —— 新增 `t0` ✓ |
| `engine/loop_eval.py` | `_agg_style_diag(…, t0)` **必传形参** ✓ ⇒ `critic.report(…, t0=t0)` ✓ |
| `engine/loop_stage.py` | 调用点把 `ctx['t0']` 传下去 ✓（与 stdout 那条**同一个 `t0`** ✓）|

### 三、★ 关键取舍：**只写"已跑"，绝不写"完工/耗时"** ✓（宁缺勿假）

诊断落档那一刻，**整代还没跑完** ✗（`--ai_critic` 的 AI 审查、写 state、写因子库全在后面 ✓）
⇒ 若此刻写"耗时"，那个数必然**偏小**（少掉后半段 ✓），而它又**没人会去对账** ✗ ⇒ 那就是**编造** ✗。
⇒ 本版一律写"**已跑**" ✓，并在尾巴上写明"此刻 AI 审查/存盘未跑完 ⇒ 只报已跑" ✓；
整代的**终态**记录仍由 stdout（`loop_persist._save_state` ✓）与 `_engine_exits.log` 负责 ✓。
★ 好处：journal 的"开工"与 stdout 的"开工"是**同一个 `t0`** ✓ ⇒ 两边**可互相核对** ✓✓。

### 四、验证

1. **★ 直拍**（`ai_test/_chk_journal_t0.py` ✓，8 条断言全过）：
   `stamp()` 三态逐条验 —— `t0=None` 不编造 ✓ · `finished=True` 三时刻齐全且 `完工−开工==耗时` ✓ ·
   `finished=False` **只有"已跑"** ✓ · 两种模式**开工时刻完全相同** ✓；
   并**真的**调 `critic.report(…, t0=…)` 写临时 md（不碰真实 journal ✓），
   断言那行同时含开工+已跑、且**不含**完工/耗时 ✓。
   ⚠ 这个自检**当场抓到一处语义瑕疵** ✗：不传 `t0`（旧调用形态 ✓）时尾巴仍写"只报已跑"
   ⇒ **指向一个不存在的字段** ✗ ⇒ 已改成**尾巴随 `t0` 分支** ✓，并补一条断言钉住它 ✓。
2. **同 seed A/B**：`ai_test/_ab/base_jt0`（189 s ✓）←→ `_ab/after_jt0`（191 s ✓），
   同 `--pool=50 --gen=9999 --seed=777` + 生产同款 flag ⇒ **7 个产物逐字节相同** ✓ ＋
   `loop_journal_50.md` **只差 1 行**（＝**预期那一行** ✓）＋ stdout **0 差异** ✓；
   —— ★ 这一版 A/B 的价值不在"逐字相同"，而在"**差异恰好只有我声明的那一行**" ✓
   （比"全都相同"更严格地证明了**改动范围** ✓）。
3. `tools/_test_undefined_names.py` ⇒ **0 处** ✓（179 文件 ✓）；
4. 相关守门 + `tools/release_check.py`（**55/55**）⇒ 全绿 ✓。

### 五、⚠ 记账：一处**快照目录撞车**（已处理，但证据链受影响 ✗）

v1.30.0 的验收文字引用的是 `ai_test/_ab/after3`（＋ `base3` ✓），而本次 A/B 起初**又用了同名目录** ✗
⇒ 那两个目录的内容已被本次"改动前/后"快照**覆盖** ✗（随后我把它俩改名为 `base_jt0` / `after_jt0` ✓，免得再撞 ✓）。
⇒ **v1.30.0 的结论本身不受影响**（当时确实验过 ✓），但它引用的**快照文件**已不是原件 ✗ —— 据实记账 ✗。
★ 教训：`ai_test/_ab/` 的快照目录名要**带版本号/主题**（如 `_ab/v1310_base` ✓），
别只用 `base3/after3` 这种序号 ✗（跨会话一定会撞 ✓）。

**如实记账（未做 ✗）**：journal 的**历史代**（已落档的 1~198 代 ✓）**不追加开工时间** ✗
—— 那是**改写历史记录** ✗（本项目一贯"历史条目有意保留原文" ✓）；从下一**新跑**的代起生效 ✓。

### 六、顺带（本版同批做的文档维护）

* **兑现"只保留最近 15 个版本"的承诺** ✓：本文件当时已 **17 条** ✗（v1.30.0 那次归档后又漂了 2 格 ✗）
  ⇒ 用 `ai_test/_cl_archive.py`（**无损**：逐字校验 + 版本集合不变 ✓）把最旧的 **2 条**
  （`1.22.3` / `1.22.2`）整段搬进 `history/change_log_archive.md` ✓
  ⇒ 现**主文件 15 条 · 归档 155 条**、两文件**无交集、无重复** ✓（归档头部"v… 及以前"也一并更新 ✓）。
  ⚠ 顺手修掉那个工具**自己会撒谎**的毛病 ✗：它的"归档动作"说明文字**写死了**
  「2026-09-28 / 24 条」（那是上一次的实情 ✗）⇒ 再跑必**说错**、还会**重复插一段** ✗
  ⇒ 已改成**按本次实情算**（日期 + 当时条数 + 搬走条数 ✓）—— 与它要修的"承诺漂移"同一条道理 ✓。

---

## [1.30.0] — 2026-09-28

> 主题：**R1 收官 —— `engine/` 侧 >120 行函数清零**（`build_fa_pit.main` 145→102 · `_save_state` 140→102）
> ＋ **修掉让它们藏了很久的根因**：体检工具只点名 `>150`/`>300` 两档 ⇒ **121~150 一直没人看见** ✗
> ⚠ **引擎行为零改动** ✓（三方证据：`_save_state` 8 用例**逐字节**对拍 · `fa_pit.h5` 80 只股票**逐位**对拍 ·
> 同 seed A/B 8 产物 + stdout 逐字相同 ✓）⇒ 属结构整治 ⇒ SemVer **MINOR** ✓

### 一、为什么要做（`§1.36` 顺带查明的两条**既存** R1 违规）

`build_fa_pit.main()` **145** ✗ · `loop_persist._save_state()` **140** ✗ —— 都是**既存**违规 ✓（非本次引入 ✓）。
★ **真根因不是"没人拆"，而是"没人看见"** ✗：`tools/_audit_codebase.py`【3】只单列 `>300` 与 `150~300`
两档 ⇒ **121~150 这一档**从来没被点名过 ✗✗（R1 写的却是"函数 **≤120** 行" ✓）。

### 二、修根因（体检工具）

`_audit_codebase.py` 现输出 **R1 违规全清单**：凡 **>120 全部点名** ✓，并按
「**评分范围 `engine/`** / 非评分范围（`tools/` `strategies/` 等脚本）」**分组** ✓ ——
避免再把"engine 里的违规"和"脚本里的长 `main`"混为一谈 ✗。本版实测：
**`engine/` = 0 个** ✓（“R1 全达标”）、非评分范围 23 个（供参考 ✓）。

### 三、两条违规的拆法（都是**最小切口** ✓）

| 位置 | 改前 | 改后 | 抽出的 helper |
|---|---|---|---|
| `engine/build_fa_pit.py` | `main()` **145** ✗ | **102** ✓（文件 295 → 326）| `_load_pit_stock`（读 h5 + 解析 quarter/info_date）**67** ✓ |
| `engine/loop_persist.py` | `_save_state()` **140** ✗ | **102** ✓（文件 528 → 579）| `_bank_admit`（入库准入循环）**56** ✓ · `_lib_doc_sync`（分口径落文档）**27** ✓ |

★ `build_fa_pit` 只抽**一段**（49 行）就够 ✓ ⇒ 循环里"选股/填充/落盘"**一字未动** ✓；
★ `_save_state` 里 **「原子写 state」那段绝对没碰** ✓ —— `pickle.dump(dict(...))` 的**键顺序决定字节** ✗，
  动它 A/B 就过不了 ✓；`by_expr`/`n_bank_old` 刻意**留在调用方**（后面还要用 ✓）。
★ **逐字搬运 + 块内零改名**（同 ③ 的铁律 ✓）：形参**刻意取名贴合块内原名**（`bank`/`lib_added` ✓），
  其余用"开头绑回原名"（`_dup_ex_corr, _ex_by_expr, _n_dup_ex = dup_th, ex_by_expr, n_dup_in` ✓）。

### 四、★★ 三道闸门各抓到一个真错（留痕，别再犯 ✗）

| # | 错 | 抓它的闸门 |
|---|---|---|
| 1 | IC 块漏搬 `ics = []` ✗（helper 里 `ics.append` 必 NameError）| `--dump` 人工审阅 |
| 2 | 逐期块残留 `mc_ = None if mcap is None …` ✗（`mc_` 已是形参、`mcap` 不存在）| `--dump` 人工审阅 |
| 3 | `_load_pit_stock` 形参写成 `last_date` 而块里用 `dates[-1]` ✗ | `--dump` 人工审阅 |
| 4 | `_bank_admit` 漏传 `frozen` ✗（块里 `fset = set(frozen)…`）| `tools/_test_undefined_names.py` |
| 5 | `_lib_doc_sync` 形参 `n_bank`/`added` 与块里 `bank`/`lib_added` 不符 ✗ | `--dump` 人工审阅 |

⇒ 结论（已写进各脚本头注 ✓）：**"拼接式手术"必须过两道闸门 —— `--dump` 人工审阅 ＋ `_test_undefined_names`**，
只信"dry-run 报的行数"就 apply 一定会翻车 ✗。

### 五、验证（★ 因为 A/B 一代**覆盖不到**这些分支 ⇒ 必须自己造对拍）

1. ★★ **`_save_state` 逐字节对拍**（`ai_test/_ab_save_state_dual.py` ✓）：旧版(HEAD) vs 新版
   在 **8 个用例**上 ⇒ **state pkl 原始字节 + md + jsonl(`ts` 归一化) + stdout + 异常** 全同 ✓
   （用例：早退 0 通过 · 单入库+池标签+剥风格"纯风格 C" · **双口径分流**（一个副口径一个 5 日 ✓）·
   **收益流去重命中** · **FSA 冻结命中** · **骨架上限命中** · 库内已有同表达式 · 入 2 个+收益流进对照集 ✓）
   —— ⚠ 为什么非造不可：`ab_generation` 的最小规模一代**常"入库 0"** ✗ ⇒ `_save_state` 第一句就早退 ✗✗
   （`if len(res) and res['passed'].any():`），**准入循环与分口径落文档根本不执行** ✗；
2. ★★ **`fa_pit.h5` 逐位对拍**（`ai_test/_ab_fa_pit_dual.py` ✓）：**80 只股票**各跑一遍旧版/新版 ⇒
   产物**逐 key / 逐数组 / float32 原始字节级相同** ✓（2,001,791 字节 ✓）＋ stdout 逐行相同（耗时归一化 ✓）；
3. **同 seed A/B**：`_ab/after3` ←→ 改后 ⇒ **8 产物逐字节 + stdout 逐行相同** ✓；
4. 相关静态守门：`_test_fsa_freeze` **22/22** · `_test_inject_pools` **17/17** · `_test_node_single` ✓ ·
   `_test_library_log` **44/44** · `_test_critic_sensor` ✓ · `_test_action_efficacy` **42/42** ·
   `_test_unbound_return` ✓ · `_test_undefined_names` **0 处** ✓；
5. `tools/release_check.py` ⇒ **55/55 全绿** ✓。

### 六、★ 顺带：给 A/B 工具加**超时预算开关**（否则"别的项目占着机器"时验不完 ✗）

本版跑 A/B 时撞上真实场景：本机同时跑着**别的项目**的重活
（`E:\quant\data_wash\tools\build_multiwindow_panel.py` ✗ —— **不是本项目、没动它** ✓），
一代从 ~190s 变成 >900s ✗ ⇒ `ab_generation.py` 报 **`退出码=-9`**（**是超时、不是行为差异** ✗✗，
极易误判成"改动坏了" ✗）。★ 顺带确认了工具的**自我保护有效** ✓：超时后 `finally` 仍把池轨迹
**逐字节还原** ✓（输出里就有那行 ✓）—— 这正是 `v1.25.0` 建这套隔离的目的 ✓。
⇒ 加**可选**预算（**默认值一字未变** ✓，既有调用方行为不变 ✓）：
`tools/_pool_traj.run_generation(timeout=None)` ⇒ 取 `LOOP_AB_TIMEOUT` 环境变量、再退回 **900** ✓；
`tools/ab_generation.py` 加 `--timeout`（0 = 用默认 ✓）✓。

### 七、顺带清死码（R4）

`loop_critic.pd` ✓ · `gen_f11_daily.pd` ✓ · `augment_panel.glob` ✓ —— 实测三者在本文件出现 **0 次** ✓
（删前确认 ✓，删后编译 + 名字检查 + 守门全过 ✓）。
⚠ **两处工具误报，故意不删** ✗：① `factor_miner.COST_PRESETS` —— 它是**有意转出**的兼容出口 ✓
（注释写着"转出, 勿在此再定义" ✓）；② `engine/_dump_state.py` / `_dump_skel.py` 的 `Node`（或 `E`）——
**pickle 反序列化需要该类在加载方命名空间可见** ✓（脚本里写明了 ✓）。⇒ 已在台账注明，免后人再误删 ✗。

---

## [1.29.0] — 2026-09-28

> 主题：**最后一个大函数拆分 —— `factor_miner.evaluate_real()` 275 → 47 行**（`loop_todo §1.36/§1.37 ③`）
> ⚠ **引擎行为零改动** ✓ —— 因这是**数值路径**，本次用**逐位**证据：**46 次调用**
> （23 用例 × `FWD=5/20`）在 **float64 原始字节级完全相同** ✓ ＋ 同进程重跑 ✓ ＋ **跨进程 `--digest`** ✓
> ＋ 同 seed A/B **8 产物 + stdout 逐字相同** ✓ ⇒ 属结构整治 ⇒ SemVer **MINOR** ✓

### 一、拆法：**原地拆**（不搬模块）＋ **逐字搬运、块内零改名**（★ 与 ①② 不同）

①② 是"搬到新模块 + 闭包变方法"；③ **原地拆**（`factor_miner.py` 只 609 行 ✓ 无 R2 压力 ✓）。
而它是**数值路径**（`calmar`/`sharpe`/`ann_ex`/`dd` 直接进 L2 入库门槛 ✗）⇒ 差 1e-16 就可能翻转
"入库/不入库" ✗✗ ⇒ 唯一安全做法是：

> **每一块逐字搬运、块内一个名字都不改** ✗ —— 只在新函数开头补几行把"原来的局部名"重新绑好
> （`ann_e = res['ann_ex']` / `yrs = len(tr) * FWD / 243` ✓）⇒ **算术顺序、结合、字面量全未动** ✓
> 手术脚本由**内容锚点**定位块（不硬编码行号 ✓），块文本直接从原文件取 ✓。

### 二、落点（`ast` 实测）

| 位置 | 改前 | 改后 |
|---|---|---|
| `evaluate_real` | **275** ✗（R1 线 120）| **47** ✓（只剩编排 ✓）|
| `engine/factor_miner.py` | 609 | **683** ✓ |
| `_er_periods`（逐期主循环 + 3 行几何映射 + `cv`）| 内联 99 行 | **112** ✓ |
| `_er_ic` | 内联 | **27** ✓ |
| `_er_base_res`（期频 + 组合自身指标 + `res` 字面量）| 内联 | **46** ✓ |
| `_er_cw_marks`（市值加权口径）| 内联 | **38** ✓ |
| `_er_daily_marks`（日频 mark-to-market 两段）| 内联 | **50** ✓ |
| 8 条平行累积列表 | — | `_ErAcc`（`NamedTuple`）✓ |

★ `_ErAcc` **故意不用** `loop_l2._L2Acc` 那种"可取属性的可变对象" ✗ ——
可变对象意味着要在 **99 行循环里逐处改名**（`acc.top_r.append(…)` ✗）⇒ **逐位风险上升** ✗
⇒ 宁可用"有名记录 + 8 项返回" ✓（两种选择各自的理由都写进了代码注释 ✓）。

### 三、诚实记账（三条"不是没动" ✗）

1. **两段论述注释搬了家**：原 docstring 的 7（mcap，12 行）/8（with_daily，10 行）两段 essay
   **搬进 `_er_cw_marks` / `_er_daily_marks` 的 docstring** ✓（主 docstring 只留 1~6 号契约 + 指路行 ✓）
   —— 属**文档搬家**（对运行行为零影响 ✓）；
2. **日频两段的守卫合并**：`if with_daily and ex_d_parts:` / `if with_daily and tr_d_parts:`
   ⇒ 调用方一处 `if with_daily and (acc.ex_d or acc.tr_d):` ✓（等价 ✓）；
3. **顺带删一行真死 import**：`factor_miner.py` 的 `import time` ✓ —— 实测 **HEAD 里 `time.` 出现 0 次** ✓
   ⇒ **既存**死码（非本次引入 ✓）。⚠ 另查到 `loop_critic.py` 的 `import pandas as pd` 同为既存死码 ✗
   （`pd.` 在 HEAD 与工作区均出现 **0 次** ✓），**本版未动** ✓（属 ① 的文件，另记台账 ✓）。

### 四、★★ 手术脚本自己犯的两个真错（留痕，别再犯 ✗）

`ai_test/_cut_eval_real.py` 初版：① IC 块锚点从 `fv_all = …` 起 ⇒ **漏搬 `ics = []`** ✗（helper 里
`ics.append` 必 `NameError` ✗）；② 逐期块里残留一行 `mc_ = None if mcap is None else …` ✗ ——
而 `mc_` 已是**形参**、`mcap` 在 helper 里根本不存在 ⇒ 同样 `NameError` ✗✗。
**抓住它们的两道闸门**：先 `--dump` 出全文**人工审阅** ✓ ＋ 事后 `tools/_test_undefined_names.py`
（作用域感知 ✓，实测 **0 处** ✓）。⇒ 结论写进脚本头注：这类"拼接式手术"**必须**这两道 ✓。

### 五、验证（★ 逐位 + 确定性 = 用户点名的两条）

1. `_test_undefined_names` ⇒ **0 处** ✓（179 文件）· `_test_unbound_return`（含 `factor_miner`）✓；
2. ★★ **逐位差分对拍**（`ai_test/_ab_eval_dual.py`）：**旧版（`HEAD:factor_miner.evaluate_real`）
   vs 新版**在 **23 用例 × FWD=5/20 = 46 次调用**上 **float64 原始字节级完全相同** ✓✓
   （直接比 `ndarray.tobytes()` ⇒ 连 `-0.0`、NaN 负载都比 ✓；**键集合/类型/索引/列、以及键的顺序**也一并比 ✓）。
   用例：真实面板派生因子 ×4（`cs_rank(close)`/`-close`/`ts_mean(turnover,20)`/`-mktcap`）· 确定性噪声 ·
   全常数 · **全 NaN（两边都 `None` ⇒ 期数不足早退 ✓）** · **半 NaN** · `window` full/recent600 ·
   `with_ex`/`with_daily`/两者 · `mcap`（无/**真实市值**/**常数市值**（恒等式：市值加权==等权 ✓））·
   `cost=0.002+cash=0.95` ✓；
3. **同 seed 确定性**：同进程连跑两次逐位相同（前 3 例 ✓）＋ **跨进程两遍 `--digest` 输出一致** ✓
   ＋ 端到端 A/B 本身即**跨进程**产物对照 ✓；
4. **同 seed A/B**：`_ab/after2`（改前）←→ `_ab/after3`（改后）⇒ **8 产物逐字节 + stdout 103 行 0 差异** ✓
   （⚠ 基线用 `after2`：③ 与 ② 之间只差注释搬家 ⇒ 行为同一 ✓）；
5. 相关守门：`_test_excess_caliber`（**静态**查四条式子 ✓ 仍在同文件 ⇒ 仍命中 ✓）· `_test_fwd_wiring` ✓ ·
   `_test_daily_dd`（日频口径 23/23 ✓）· `_test_dual_horizon` ✓；
6. `tools/release_check.py` ⇒ **55/55 全绿** ✓（13.x 分钟）。

**⇒ 收官口径**：`engine` 侧 R1 违规**只剩两条既存**（`build_fa_pit.main` **145** ✗ ·
`loop_persist._save_state` **140** ✗，均非本次引入 ✓，已记 `maintainability.md §五` ✓）；
§1.36 点名的三个大函数（`suggest` 207 · `_lib_sync` 186 · `evaluate_real` 275）**全部达标** ✓。

---

## [1.28.0] — 2026-09-28

> 主题：**库文档簇拆成 `engine/loop_libdoc.py`** —— `loop_persist.py` **796 → 528 行**、
> `_lib_sync()` **186 → 61 行**（`docs/loop_todo.md §1.36/§1.37 ②`）
> ⚠ **引擎行为零改动** ✓ —— 同 seed A/B **8 产物 + stdout 逐字相同** ✓ ＋ **18 用例旧版 vs 新版逐字节差分** ✓
> ⇒ 属"向后兼容的结构整治"（同 v1.25.x / v1.27.0 口径）⇒ SemVer **MINOR** ✓

### 一、为什么要"搬"而不是"就地拆"

`loop_persist._lib_sync()` **186 行** ✗（R1 线 120）；而它所在的 `loop_persist.py` 当时 **796 行**，
离 R2 线（800）**只剩 4 行** ✗✗ ⇒ 就地拆（新增 `def`/docstring/`return` 都要占行）**必然把文件顶过线** ✗
⇒ 把「**库文档**」这一件事整簇搬成**单一职责模块** ✓
（同 `v1.25.x` 拆 `loop_l1`/`loop_l2`、`v1.27.0` 拆 `loop_critic_rules` ✓）。

### 二、落点（`ast` 实测）

| 位置 | 改前 | 改后 |
|---|---|---|
| `engine/loop_persist.py` | **796**（贴线 ✗）| **528** ✓ |
| 新模块 `engine/loop_libdoc.py` | — | **347** 行 ✓ |
| `_lib_sync` | **186** ✗ | **61** ✓ |
| 拆出的两段 | — | `_lib_rows`（渲染总览行/明细块/入库事件 · **113** ✓）· `_lib_insert_md`（md 三处锚点 · **31** ✓）|
| 逐字搬的 3 个 | — | `_tag_desc` **4** · `_mk_library_skeleton` **38** · `append_library_entries` **33** ✓ |

★ **`_lib_rows` 一度 121 行** ✗（超 R1 线 1 行）⇒ 用本项目**已有手法**「上移论述注释」压回 **113** ✓
（`v1.25.x` 的 "comment hoist only" ✓）。⚠ **诚实记账**：**没做到**"token 级逐字相同" ✗ ——
上移时顺手把那段注释写得更清楚（并加了 §1.37 的来历）⇒ 属**注释增量**（对行为零影响 ✓）。

### 三、依赖方向（★ 单向，无环）

`loop_libdoc` 只依赖**叶子模块**（`loop_paths` · `loop_expr.skeleton` · `cost_presets` ·
`loop_pools`（惰性 import ✓））⇒ **不 import `loop_persist` / `loop_engine`** ✓；
`loop_persist` 反向 **只** `from loop_libdoc import _lib_sync`（`_save_state` 的代末双口径同步仍要它 ✓）；
`loop_engine` 顶部 **re-export 那 4 个名字** ✓ —— ⚠ `tools/horizon_admit_write.py` /
`tools/backfill_library_pool.py` 走的是 `LE._lib_sync` / `LE._mk_library_skeleton`，
**删掉那行会让两个工具静默失联** ✗ ⇒ 已在原处写明"不许删" ✗。

### 四、验证（★ 其中第 3 条是"必须直拍"的）

1. `tools/_test_undefined_names.py` ⇒ **0 处** ✓（179 个文件 ✓）；
2. **同 seed A/B**：`_ab/base2`（187 s）←→ `_ab/after2`（192 s）⇒ **8 产物逐字节 + stdout 103 行 0 差异** ✓
   —— ⚠ 但它**证明不了 `_lib_sync` 本身** ✗✗：该函数第一句就是 `if not added_exprs: return`，
   而 `ab_generation` 跑的是**最小规模**（"常常入库 0" ✓）⇒ **主体根本没执行** ✗；
3. ★★ **直拍（本版的关键证据）**：`ai_test/_ab_libdoc_dual.py` ——
   **旧版（`HEAD:loop_persist._lib_sync`）vs 新版（`loop_libdoc` 三段）逐字节差分** ✓：
   沙箱把 `loop_paths.LIBRARY/LIB_ENTRIES/MINE_POOL` 指到临时目录（两边各自的副本 ✓），
   **18 个用例**覆盖 早退（无入库/明细为空）· **骨架自动创建** · 表尾插入 · **刚建骨架无数据行（`elif` 分支）** ·
   **缺「相关文件导航」（`p<0` 分支）** · 池标签有/无 · 剥风格 **4 元组 / 6 元组 / 日频 NaN** ·
   `sign` 有/无/坏值 · 口径有/无（含无期数）· 来源 `engine`/`promote` · **编号 F99→F100 边界** ·
   `jsonl` 幂等 · `jsonl` 坏行 ⇒ **18/18 逐字节相同**（md + jsonl（`ts` 归一化）+ **stdout** + 异常）✓；
4. 相关守门：`_test_library_log` **44/44** ✓ · `_test_admit_write` ✓ · `_test_reports_expr` **34/34** ✓ ·
   `_test_dual_horizon` ✓ · `_test_unbound_return`（**新模块已纳入扫描** ✓）✓ · `_audit_deadcode`（无新死码 ✓）✓；
5. `tools/release_check.py`（全量 **55/55**）⇒ 全绿 ✓。

### 五、守门/工具取源同步（防护一字未减 ✓）＋ 顺手修掉一个真缺陷 ✓

* 三处"按文件路径做静态断言"的取源改到 `loop_libdoc.py` ✓：
  `_test_library_log`（`append_library_entries` 有定义且被调用）· `_test_admit_write`（`def _lib_sync(...source=None)`）·
  `_test_reports_expr`（`sign` 行）✓；
* `tools/_test_unbound_return.py` 的默认文件清单加 `engine/loop_libdoc.py` ✓（R7：搬来的代码必须被扫 ✓）；
* ★ **`tools/_mk_pool_library_skeleton.py` 的 `ENGINE_SRC` 原先写 `loop_engine.py`** ✗ ——
  而 `_mk_library_skeleton` **从来不在** loop_engine 里定义（那边只有 import）⇒ **ast 提取每次都失败、
  静默回退内置 `FALLBACK` 副本** ✗（= 引擎改模板、工具照抄旧副本；**实测两份确实有一处不同** ✗）。
  本次把路径指到真正的家 ✓，并用 `ai_test/_check_skeleton_tpl.py` 证明：
  **旧路径提取失败** ✓ / **新路径与引擎模板逐字相同** ✓（该工具**不覆盖已有文件**（`if os.path.exists: exit 0` ✓）
  ⇒ 只影响"将来新建的池骨架"，风险可控 ✓）。
* `loop_persist.py` 里随簇搬走而**变成死 import** 的 `json` / `re` / `cost_label` 已删 ✓（R4 无死码 ✓）。

**遗留（如实记账 ✗）**：① `factor_miner.evaluate_real()` **275 行** ⇒ 下一版（③，碰数值路径 ⇒
需同 seed 确定性 + **逐位对拍** ✓）；② 顺带查明两条**既存** R1 违规（**不是本版引入** ✗）：
`build_fa_pit.main()` **145** · `loop_persist._save_state()` **140** ⇒ 已记入 `maintainability.md §五` 台账 ✓
（根因：`_audit_codebase`【3】只点名 `>150`/`>300` 两档 ⇒ **121~150 这一档一直没被看见** ✗）。

---

## [1.27.0] — 2026-09-28

> 主题：**既存 R2 违规清零 —— `loop_critic.py` 998 → 774 行、`suggest()` 207 → 30 行**
> （`docs/loop_todo.md §1.37` ①：**先对象化、再把 7 个闭包转方法**，走 B 路「整改」✓）
> ⚠ **引擎行为零改动** ✓ —— A/B 证据：**8 个产物逐字节 + stdout 103 行逐行相同（差异 0）** ✓
> ⇒ 属"向后兼容的结构整治"（同 v1.25.x 口径）⇒ SemVer **MINOR** ✓

### 一、为什么要做（§1.36 查出的**既存**违规，口径要一致）

`loop_critic.py` 改前就 **991 行**、v1.26.0 后又 **998 行** ✗（R2 线 = 800）——
它上一轮审计里已是 **engine 最大文件**，却**从未进过 §五 的扣分项** ✗
（而新文件都按 ≤800 算 ✓）⇒ **口径不一致** ✗。两条路里选了 **B（整改）**：A（承认遗产）给不出理由 ✓。

### 二、★ 关键判断：**不做机械抽块**（这条是 AST 机器算出来的，不是人眼猜 ✓）

`tools/_extract_block.py loop_critic.py suggest 581 752 <名>` 的结论：那 7 个嵌套 `def`
「**块里读了、块外才有**」的名字 **13 个** ——
`_ctx · act · base · cmul · cool · diag · ineff · n_blocked · n_ineff · reasons · s · tgt · veto`；
而「块里赋值、块外还读」的**只有 `n_blocked`**。

⇒ 机械抽成函数 ⇒ 每个子函数要背 **13 个形参** ✗✗ —— 正是 `maintainability.md §七` 警告的
   「**上帝函数换成上帝参数表**」✗（`_run_l2_phase` 试抽 `_l2_judge` 已因此回退过一次 ✓）
⇒ 改用**方法**（`self.xxx`）⇒ **形参 0 个** ✓；`n_blocked` / `n_ineff` 留在对象上**就地自增**
   ⇒ **连回传都不需要** ✓✓（原 `n_blocked = [0]` 的单元素列表只是"闭包改不动外层变量"的变通 ✗ ⇒ 顺手拆掉 ✓）。

### 三、落点（`ast` 实测行数）

| 位置 | 改前 | 改后 |
|---|---|---|
| `engine/loop_critic.py` | **998** ✗ | **774** ✓（R2 线 800 ✓）|
| `loop_critic.suggest()` | **207** ✗（R1 线 120）| **30** ✓ |
| 新文件 `engine/loop_critic_rules.py` | — | **312** ✓ |
| 7 个方法（7 个闭包 ⇒ 方法） | — | `_set` **8** · `_ineff_muted` **4** · `_begin` **3** · `_mark` **20** · `_rollback` **34** · `_guard` **43** · `_settle` **54** ✓（**与 §1.37 预估逐数吻合** ✓）|
| `_SugState.__init__`（原 `_init_sug` **并入** ✓）| 30 行模块级函数 | **43** ✓ |
| `_fmt` / `_fmt_l1` / `_fmt_l2` | 闭包 + 2 个模块级 | 一并搬入（**4 / 14 / 18** ✓）|
| **留在原文件** | — | `_apply_rules`（7 条规则表 · **67** ✓）+ `_finalize_sug`（出口 mix 护栏 · **28** ✓）|

★ **两处按实情修正了原方案**（不假装照抄 ✓）：
1. **`_init_sug` 也并进了对象** —— 状态布局的**唯一知情人**就是对象本身 ✓，否则构造时还得再抄 6 行
   "从 `s` 取别名"（重复 ✗）；代价是新模块 312 行（原估 ≈220），仍远在 800 线内 ✓。
2. **`n_blocked`/`n_ineff` 由 `[0]` 单元素列表改为对象整数** ✓（理由见 §二）。

### 四、依赖方向（★ 单向，不成环）

`loop_critic_rules` 顶部 `from loop_critic import …`（**复用**其常量与纯函数 ⇒ **R5 未复制第二份** ✓）；
`loop_critic` **只在函数内** import 它（`suggest` / `report` / `ai_review` 三处）⇒ 到那一刻
`loop_critic` 已完全初始化 ⇒ **不成环** ✓（与 `_op_names` 惰性 import `loop_engine` 同一条理由 ✓）。
模块头注写明「**不许**把它提到 `loop_critic` 的模块级」✗。

### 五、验证（R7 铁律：名字解析 + 同 seed A/B，缺一不可 ✓）

1. `tools/_test_undefined_names.py` ⇒ **0 处** ✓；
2. **A/B 逐字节**：改前 `_ab/base`（219 s ✓）←→ 改后 `_ab/after37`（186 s ✓），
   同 `--pool=50 --gen=9999 --seed=777` + 生产同款 flag ⇒
   **8 个产物逐字节相同**（journal 归一化后逐行相同 ✓）+ **stdout 103 vs 103 行、差异 0** ✓；
3. 相关守门：`_test_critic_sensor`（饱和/否决/永久闭嘴）✓ · `_test_action_efficacy` **42/42** ✓ ·
   `_test_unbound_return`（**新模块已纳入扫描** ✓）✓ · `_test_ops_sync` 28/28 ✓ ·
   `_test_ops_registry` 17/17 ✓ · `_test_critic_firstgen` ✓；
4. `tools/release_check.py`（版本一致 → 未定义名 → 全量 55 条守门）⇒ **全绿** ✓。

**守门同步（防护内容一字未减 ✓）**：`_test_action_efficacy` 的两处静态取源改为
「`loop_critic.py` + `loop_critic_rules.py` **拼接**」✓（动作区正则仍命中原文件里的 `_apply_rules` ✓、
`_set` 计数 10 ✓、"无直接 `s[...]` 赋值" ✓）；`_test_unbound_return` 的默认文件清单加新模块 ✓。

**遗留（如实记账 ✗）**：`engine` 侧仍有 `factor_miner.evaluate_real()` **275 行**、
`loop_persist._lib_sync()` **186 行** ⇒ 即 `loop_todo §1.36` 顺带记的那两笔（**②③ 待办** ✓）。

---

## [1.26.0] — 2026-09-28

> 主题：**给挖掘留"时间线"** —— journal 与 stdout 加**秒级时间**、耗时改**人类可读**、
> `_engine_exits.log` 补上**成功代**记录（用户之问："这些 journal 记录后面要不要把北京时间加进去？"✓）
> ⚠ 引擎**数值行为零改动** ✓（A/B 逐字节 ✓）；改动属**向后兼容的新日志字段** ⇒ SemVer **MINOR** ✓

### 一、为什么要做（用户实测驱动的三个痛点）

1. **journal 里没有时间** ✗ ⇒ 要定位"某一代何时跑的"**只能靠文件 mtime 反推** ✓（用户问"50 池怎么还没挖完"、
   我排查"300 才挖两代吗"时，都是这么硬推的 ✓）；
2. **`_engine_exits.log` 只记非零退出** ✗✗ ⇒ 翻它**只会看到"被停/异常"**，成功完成的代**一行都不写** ✗
   —— 我 2026-09-28 就据此**误判过**"300 才挖两代"（实际已到第 194 代 ✓）；
3. **`耗时 7142s` 不好读** ✗ ⇒ 用户要求改成 `1h59m2s` ✓。

### 二、做了什么（四步 · 每一步都有独立验证 ✓）

| 步 | 内容 | 落点 |
|---|---|---|
| **1** | A/B 比对器**先容忍**新格式 ✓：① `noise` 正则覆盖 `1h59m2s` 复合耗时（放最前，否则短的咬碎长的 ✗）；② **把归一化提到产物比对之前**，并让 **journal 等文本产物也逐行归一化** ✓（原先只有 stdout 做 ⇒ journal 一加时间戳就**每次误报** ✗✗） | `tools/ab_generation.py` |
| **2 (C)** | stdout 新增一行：`时间: … +08:00 · 开工 … · 完工 … · 耗时 1h59m2s` ✓；`保存状态:` 的耗时改用人类可读 ✓ | `engine/loop_persist.py` |
| **3 (A)** | journal 代标题下新增**同格式时间行** ✓ | `engine/loop_critic.py` |
| **4 (B)** | `_engine_exits.log` **三类都留痕**：成功 / 被停 / 异常 ✓（`_log_exit` 加 `tag` ✓）；成功行 = `… 成功  入库 N 个  耗时 1h59m2s` ✓ | `tools/parallel_runner.py` |

**语义定死**（避免歧义 ✓）：`开工` = 进程启动（**开始挖** ✓）；`完工` = 收尾写完（**诊断 + LLM/AI 审查 + 落盘全部完成** ✓）
⇒ 三者**同源**（同一个 `t0` ✓）⇒ 恒有 `完工 − 开工 == 耗时` ✓。
⚠ **journal 只写"诊断落档时刻"** ✗ —— 那一刻 `完工` **还不可知**（AI 审查在其后 ✓）⇒ **不编造** ✓（宁缺勿假 ✓）；
`开工/完工/耗时` 由 stdout 的 `时间:` 行与 `_engine_exits.log` 的成功行给出 ✓。
⚠ **时区用 `%z` 实测** ✓，**不硬编码 `+08:00`** ✗（本机在北京时即 `+0800` ✓；换机器**不会撒谎** ✓）。

### 三、R5/R2 的账（做完才敢说 ✓）

- **R5 单一实现** ✓：把 `fmt_dur()` / `stamp()` 抽进**新增 `engine/loop_log.py`**（**45 行** ✓）——
  先前"工具端自己再写一份格式化"的做法**被否掉** ✗（那是第二份实现 ✗）；
  `tools/parallel_runner.py` 改为**照抄引擎打印的字符串** ✓（不重建 ✓）。
- **R2 文件长度** ✓：改完一度把 `loop_persist.py` 顶到 **816 行** ✗（线 = 800）⇒ 抽出后 **796 行** ✓ 回线内 ✓。
  ⚠ **如实记账**：`engine/loop_critic.py` 现 **998 行** ✗ —— 它**本来就是 991 行**（上一轮审计里 engine 最大文件 ✓），
  本次净增 **+7** ✗ ⇒ 这是**既存**的 R2 违规 ✓，本次**未拆** ✗（不硬塞进本改动 ✓），列入台账待办 ✓。

### 验证

- **A/B ①（基线 = 改动前 ✓）**：7/8 产物**逐字节相同** ✓；`journal` 与 `stdout` 的差异**只有"多一行"** ✓
  （纯插入：A 的第 3001 行 == B 的第 3003 行 ✓）⇒ **数值行为零改动** ✓；并**反证基线确实跑的是旧代码** ✓（A 侧无 `时间:` 行 ✓）
- **A/B ②（抽取 `loop_log.py` 前后 ✓）**：**8/8 全绿** ✓ —— 7 个逐字节相同 ✓ ＋ journal `✓ 归一化后逐行相同` ✓
  ＋ stdout `✓ 逐行相同（101 vs 101，差异 0 行）` ✓ ⇒ **抽取是纯重构** ✓，且第 1 步的归一化**运行时成立** ✓
- **守门**：`_test_undefined_names` —— 期间**抓到过我漏 `import time`**（1 处 ✗）⇒ 修后 **0 处** ✓（扫 177 文件 ✓）
- **全量 `release_check.py`**：改动落地时 **55/55** ✓（13.3 分钟 ✓，含 `_test_e2e_l1l2` **192 s** ✓＝真跑一代 L1+L2 ✓
  ⇒ 证明新增的 stdout/journal 行**没撞坏端到端** ✓；`_test_parallel_runner` **185 s** ✓ 覆盖 B 所在文件 ✓）
- ⚠ **尚未拿到**：B 的**运行时首行**要等**下一代跑完**才会出现在 `_engine_exits.log` ✓（本条**如实标注** ✗，不当作已验证 ✓）

---

## [1.25.3] — 2026-09-27

> 主题：**R1/R2 整治收官** —— 「先对象化、再抽块」，六个超标函数全部达标，`loop_stage.py` 一拆为三
> ⚠ **引擎行为零改动**（每个提交都有 A/B 逐字节证据 ✓）；用户拍板走「**先对象化再拆**」而非「机械抽块」✓

### 一、为什么不是"直接抽块"

机械抽 `_run_l2_phase` 的候选循环会得到「**67 行调用方 + 一个 30 形参的子函数**」✗ ——
正是 `docs/maintainability.md` 自己警告的**「上帝函数换成上帝参数表」** ⚠。那 30 个形参的来源是
函数开头 **24 行 `x = ctx['y']`** ✓。⇒ 用户选 **B：先把口径对象化，再抽块** ✓。

### 二、做了两件事

**① 对象化（`_L2In` / `_L2Acc`，提交 `28e4429`）**

| 对象 | 语义 | 内容 |
|---|---|---|
| `_L2In`（`frozen=True` ✓） | L2 阶段**只读**口径 | 23 项；`frozen` ⇒ 手误写它**立刻抛错** ✓（这是它存在的理由之一 ✓）|
| `_L2Acc`（可变 ✓） | 本代**累积结果** | `rows / seg_ok_list / strip_rows / pool_rows / n_pool_nogate / nd` ✓ |

- **名字对应只有一个来源** ✓：模块级 `_L2IN_MAP`（键 = 旧局部名 = 当时的 ctx 键 ✓，逐字来自源码 ✓）
  ⇒ `_L2In.of(ctx)` **不猜**同名键 ✗，缺键立刻 `KeyError` ✓
- ⚠ `nd` 会被 `_dump_pool_obs` **重绑** ⇒ 必须放**可变**侧 ✗（塞进 `frozen` 会直接抛错 ✓）
- 24 行解包 → `cal = _L2In.of(ctx)` ＋ `acc = _L2Acc(nd=ctx['nd'])`（2 行 ✓）；5 行累加器初始化收进字段默认值 ✓
- **78 处裸名改名**（29 个名字 ✓）⇒ 块内写入全变成**属性写入**（`acc.rows.append(...)` ✓）

**② 抽块（提交 `1348814` / `a182ebe` / `32e84a8`）**

| 函数 | 原 | 现 | 抽出的子函数 |
|---|---|---|---|
| `_run_l1_phase` | 197 | **62** ✓ | `_l1_calib` ✓ |
| `_l1_eval` | 174 | **55** ✓ | `_l1_batches`（111 行 ✓）|
| `_run_l2_phase` | 251 | **41** ✓ | `_l2_candidates`（119 行 ✓）|

★ 抽块的**形参与回传都由 AST 机器算** ✓（不人眼挑 ✗）：形参 = 块里读到、块外才有 ✓；
回传 = 块里赋值、块外还读 ✓；**条件赋值**（只在嵌套分支里绑 ⇒ 可能一次都没执行 ✗）⇒ 子函数内先置 `None` ✓。
对象化之后这项工作**天然归零**：写入全是属性写入 ⇒ `_l2_candidates` 回传只剩 `acc`、再无"条件赋值" ✗✓。

### 三、验证协议（本轮真正的资产 ✓）

每次抽块都跑同一条链，**三次全部 8/8 逐字节** ✓：

```
① .bak 跑基线（改动前 ✓）→ ② 换新版跑一次 → ③ ab_generation.py --diff：8 个产物逐字节 + stdout 逐行
④ 极小跑（--n=8 --l2=1，~110 s ✓）当快闸门  ⑤ release_check.py 全量（55 条 ✓）
```

**这条链抓到达 6 个「编译/静态检查全过、真跑一代才炸」的缺陷** ✗，全部在**写盘前或提交前**拦下 ✓：

| # | 缺陷 | 谁抓住的 |
|---|---|---|
| 1 | 条件赋值名 `k` 被无条件 `return`（可能从未绑定 ✗） | 极小跑 `NameError` ✓ |
| 2 | `n_eval += 1`（先读后写 ✗）既没当形参又要回传 | 工具的 dry-run ✓ |
| 3 | 删 24 行后下方位移方向写反 ✗ | 脚本的 `assert`（**写盘前**退出 ✓）|
| 4 | 类算好了却**忘了插** ✗ | 极小跑 `NameError` ✓ |
| 5 | ★ **`col_offset` 是 UTF-8 字节偏移、不是字符偏移** ✗ —— 行里含中文时按字符切片切歪 ✓ | 逐处断言「切出来必须正是原名字」✓ |
| 6 | 守门 `_test_dual_horizon` 的坐标过期（引用点搬走了 ✗） | 全量闸门 54/55 ✓ |

⚠ **坑 5 值得写进规则**（本仓库满屏中文注释 ✓）：任何"按 AST 列号切字符串"的脚本**必须**先做
字节→字符转换 ✓，且**每处切完都要断言取到的正是原名字** ✓。

### 四、守门坐标随重构更新（`c7fc1da`）

`_test_dual_horizon` 的 ③④ 断言要求「`pass_filter` 在持有 L2 循环的函数里以**全局名**取」✓。
循环搬进 `_l2_candidates` 后坐标过期 ✗ ⇒ 断言改看**新家**（`sys.modules['loop_l2']` ✓ ——
`loop_engine` 只**转发** `_run_l2_phase` ✓、没导出新函数 ✗）。
⚠ **保护一点没减** ✗：仍是「不许函数内绑定」✓ ＋「必须以全局名取（`co_names`）」✓，且 ③ 从"一个函数"扩成"**两个都查**" ✓。

### 五、八维评分（`docs/maintainability.md`）

| 维度 | 09-27 前 | **09-27** | 依据 |
|---|---|---|---|
| 可读性 | 8 | **9** | ★ §五 明列的扣分项**只有两条** ⇒ 两条全清 ✓：**R1 六函数 41/62/55/115/120/119 全 ≤120** ✓ |
| 可维护性 | 8 | **9** | ★ **R2 达标**：`loop_stage.py` **1332 → 437 行** ✓（同族 `loop_l1.py` 588 ✓ / `loop_l2.py` 510 ✓，均 ≤800 ✓）|
| **综合** | **8.0** | **8.25** | 66 / 8 = 8.25 |

> ⚠ **未动**（不是忘了 ✗）：**性能 6**（一次优化都没做 ✗，重构期硬约束是"行为不变"⇒不许顺手改数值路径 ✗）；
> **可移植性 7**（看板仍 Windows 专有 ✗）；功能性 8（行为逐字不变 ✓ 是本次硬约束 ✓）；
> 测试/工程纪律/文档 9 ✓（v1.24.0 已挣到 ✓）。

### 验证

- **A/B 逐字节 3 次全过** ✓：`_l1_calib`（`base2↔s3d`）· 对象化（`b0↔b3`）· 抽块（`b6↔b5`、`b5↔b7`）
  —— 每个都是 **8 个产物逐字节相同 + stdout 逐行相同** ✓
- **极小跑**：`rc=0` · 无 `Traceback`/`NameError` · 产物真落盘 · **还原后与跑前逐字节一致** ✓
- **`release_check.py`**：**54/55** ⇒ 唯一失败是 §四 的坐标过期 ✓ ⇒ 修复后**单独复验全过** ✓
  （与重构直接相关的守门全绿 ✓：`_test_e2e_l1l2` 179 s ✓ · `_test_parallel_runner` 153 s ✓ ·
  `_test_unbound_return` ✓ · `_test_undefined_names` ✓ · `_test_style_neut` ✓）
- ⚠ **冷缓存辨析** ✓：同一条最小链路实测 **500 s vs 110 s** ✗ ⇒ 逐字节相同、且热缓存重跑 110 s ✓
  ⇒ **是面板缓存冷热，不是代码变慢** ✓（以后比耗时必须连跑两次 ✓）

---

## [1.25.2] — 2026-09-27

> 主题：**函数级拆分 S2 —— L1 组搬出 `loop_stage.py`** ⇒ ★ **R2 达标**（`loop_stage.py` 1349 → **399 行** ✓）
> ⚠ 引擎行为逐字未变（A/B 实证 ✓）；★ **本版 A/B 抓到一个真缺陷** ✓（见下）

* **搬迁**：`_run_l1_phase` / `_l1_eval` / `_l1_filter`（**510 行**）→ 新文件 **`engine/loop_l1.py`**（538 行 ✓）
  ⇒ `loop_stage.py` **909 → 399 行** ✓ · `loop_l2.py` 467 ✓ · `loop_l1.py` 538 ✓ ⇒ **三个文件全 ≤800** ✓
  （`_audit_codebase.py`：巨型文件 0 ✓）
* ★★ **A/B 抓到一个真缺陷（它上一次的自我价值证明 ✓）**：
  `FWD → _S.FWD` 的替换**越界到了 f-string 的字面文本** ✗ ——
  `print(f"...子面板[::FWD] ...")` 里的 `[::FWD]` 是**要打印出来的字**（不是变量 ✓），被改成了 `[::_S.FWD]` ✗
  ⇒ 8 个产物**逐字节相同** ✓ 但 **stdout 多出 1 行差异** ✗ ⇒ 被 A/B 精确指出 ✓
  ⇒ 修：(a) 那处字面文本还原 ✓；(b) 替换**只作用于搬过来的正文**、不碰生成的文件头 ✓；
    (c) **注释行**里的误改也还原（`loop_l1` 5 处 + `loop_l2` 6 处 ✓，代码里的切片 `[::_S.FWD]` 保留 ✓）
  ⚠ **教训（写进 §七 7.5）**：**文本替换必须区分"代码引用"与"注释 / 字符串字面文本"** ✗
* **同步点命中**（§七 7.4 预告；这次是 2 个守门 ✗）：
  `loop_engine` 的 import ✓ ·
  `_test_engine_mem_budget.py`（它的 pattern **全是 L1 的** ⇒ 改看 `loop_l1.py` ✓）·
  `_test_inject_pools.py`（改成按"**阶段层三份拼起来**"搜 ⇒ 对今后搬迁也稳 ✓；它原读 `loop_stage.py` 找 `--decorr` 对照集 ✗）·
  `_test_dual_horizon.py`（AST 检查覆盖三个文件 ✓）
* **验证**：`_test_undefined_names` **0 处** ✓ · 受影响守门 **7/7** ✓ ·
  ★★ **同 seed A/B**：`base2` ←→ `s2b` ⇒ **8 个产物逐字节相同 + stdout 逐行相同（0 差异）** ✓✓
  （**修复前**那一次 stdout 有 1 行差异、被抓住 ✓；轨迹还原逐字节校验 ✓）
* **R1 仍差**：6 个函数 >120 行（`_run_l2_phase` 251 · `_run_l1_phase` 197 · `_l1_eval` 174 ·
  `_run_prepare` 151 · `_run_gen` 135 · `_l1_filter` 133）⇒ **S3** ✓

> ⚠ 一处**如实记账**：新增的 `tools/_pool_traj.py` 带了一个 `HERE`/`ROOT` 常量 ✗ ⇒
> `_audit_codebase` 的 `ROOT`/`HERE` 出现次数 +1（96 个**同名常量**的组数未变 ✓）。
> 这是全项目通用写法（`ROOT` 本就 ×110 ✓），非新增违规种类 ✓，故不动 ✓。

---

## [1.25.1] — 2026-09-27

> 主题：**函数级拆分 S1 —— L2 组搬出 `loop_stage.py`**（可读性/可维护性 → 9 的第 1 步）
> ⚠ **引擎行为逐字未变**（下述 A/B 实证 ✓）

* **搬迁**：`_run_l2_phase` / `_l2_strip_dual` / `_l2_pool_tags`（**436 行**）→ 新文件 **`engine/loop_l2.py`** ✓
  ⇒ `loop_stage.py` **1349 → 909 行**（R2 还差一步：L1 组待搬 ⇒ 目标 ≤800 ✓）
* **怎么搬的**（避免手抄改行为 ✗）：脚本 `ai_test/_split_l2.py` 按 **AST 行范围**切片、**原文搬运** ✓，
  只做两件可控的事：① 按"用了哪些名字"**挑 import**（23 → 12 条 ✓ 不留死 import）
  ② `FWD` → **`_S.FWD`**（★ `FWD` 是主口径快照，**仍只准在 `loop_stage.py` 定义一处** ✓；
     `loop_l2.py` 用 `import loop_stage as _S` **运行时读** ✓ —— **禁止**值拷贝 ✗）
  ★ 写盘前有护栏：**任何模块级名字没被覆盖 ⇒ 拒绝写盘** ✓（本次报告"无 ✓"）
* **同步点**（`maintainability.md §七 7.4` 预告的三个 ✓，本次命中 1 个守门）：
  `loop_engine.py` 的 import 行改成 `from loop_l2 import (...)` ✓（**仍在 loop_engine 层 re-export**，
  因为多个守门按 `loop_engine._run_l2_phase.__code__` 做断言 ✓）；
  `tools/_test_dual_horizon.py` 的 L2 pattern 改看 `loop_l2.py` ✓，并**新增两条防退化断言**：
  ① `loop_l2.py` **不许自己再定义 `FWD`** ✗ ② 必须**运行时读** `_S.FWD` ✓

### ★★ 验证（本项目的铁律：名字解析 + 同 seed A/B，两条都跑 ✓）

* `_test_undefined_names.py` **0 处** ✓ · `py_compile` ✓
* 受影响守门 **7/7 全过**：`_test_dual_horizon` · `_test_fsa_freeze` · `_test_node_single` ·
  `_test_inject_pools` · `_test_engine_mem_budget` · `_test_undefined_names` · `_test_version_sync` ✓
* ★★ **同 seed A/B（`tools/ab_generation.py`）**：改前 `_ab/base2` ←→ 搬运后 `_ab/s1`
  ⇒ **8 个产物逐字节相同 + stdout 逐行相同（0 差异）** ✓✓
  （`state` 走逐字段比 ✓；对照工具此前已自证可信 ✓）
* 轨迹已还原并**逐字节校验** ✓（池 50 未被污染 ✓）

> **下一步（S2）**：同法搬 L1 组（`_run_l1_phase`/`_l1_eval`/`_l1_filter`，504 行）→ `engine/loop_l1.py`
> ⇒ `loop_stage.py` ≈ 405 行（R2 达标 ✓）；随后 S3 = 按注释段落把那 6 个函数切到 ≤120 行（R1 ✓）。

---

## [1.25.0] — 2026-09-27

> 主题：**把「同 seed A/B」落成一条命令**（并**自证可信**）· 端到端守门去重 · **函数级整治方案定稿**
> —— 为「可读性 / 可维护性 → 9」做前置：先把**验证手段**建好，再动 `loop_stage.py`（v1.23.0 的教训 ✓）
> ⚠ **引擎行为零改动**（本次只加工具/文档 + 守门重构 ✓；`git status` 可证 `engine/` 一字未动 ✓）

### 一、新增 `tools/ab_generation.py` + `tools/_pool_traj.py`：**同 seed A/B 一条命令** ✓

`docs/maintainability.md` R7 早写明「**搬函数/拆模块后必须跑「名字解析检查 + 同 seed A/B」**」✗，
但"名字解析"有常驻守门、"**A/B 一直靠人手跑**" ✗ —— 而 **v1.23.0 就是漏了 A/B 才发版即崩** ✗（用户白等一晚）。

* `tools/_pool_traj.py` —— 池轨迹的**快照/还原/真跑一代**（单一实现 ✓，供守门与 A/B 共用 ✓）。
  隔离只能靠备份还原 ✗：引擎产物路径是 `__file__` 派生、**无参数/环境变量出口** ✓
* `tools/ab_generation.py` —— `--out <dir>` 跑一代存产物；`--diff A B` 逐文件对照
  （`state` 走**逐字段**比、CSV/md 走逐字节、stdout 剔耗时后逐行 ✓）

★★ **自证可信（关键）**：用**未改动的代码**跑两遍再对照 ⇒
**8 个产物逐字节相同 + stdout 逐行相同（0 差异）** ✓✓ —— 这样"改后出现差异"才一定是**真差异** ✓
> 自检当场抓出并修掉工具自己的两个坑（否则会**假报差异** ✗）：
> ① `Node` **没有 `__eq__`** ⇒ `==` 退化成身份比较，把内容相同的种子判成不同 ✗（改为按表达式文本比 ✓）；
> ② 诊断行 `leaf_hist {...}` 的**字典键序**随 `PYTHONHASHSEED` 变 ✗（内容相同）⇒ 固定 `PYTHONHASHSEED=0` ✓
>   （⚠ 只影响那条诊断行的**键序**，对数值无影响；生产没设它，本工具只是把它变成可控实验 ✓）

### 二、端到端守门改用共用库（去重复实现 · R5）

`tools/_test_e2e_l1l2.py` 原来的备份/还原/起引擎是**自己一份** ✗ ⇒ 与 `ab_generation` 撞车 ✗
⇒ 现统一走 `_pool_traj` ✓，重跑 **20/20 全过** ✓（里程碑 / 产物 / 隔离 / 还原逐字节一致 ✓）

### 三、`docs/maintainability.md §七`：函数级整治方案定稿（**可执行**）

* 侦察（`ai_test/_ls_inventory.py`）：`loop_stage.py` = **1349 行 / 9 函数 / 69 个 ctx 键**，
  6 个函数超 R1（251/197/174/151/135/133 ✓）
* ★ **关键判断：不需要新造 dataclass 配置对象** ✓ —— 先前"20 个口径参数没法传"的结论**不成立** ✗：
  **`ctx` 就是状态对象**、**`args` 就是口径对象**（本来就是属性读 ✓）；
  "参数爆炸"**只在 4 个子函数签名上**（`_l2_pool_tags` **18** / `_l1_eval` **13** / …）——
  它们把 **ctx 里的东西拆开传**了 ✗ ⇒ 改传 `(ctx, args, 少量)` ✓
* ★★ 列出**三个必须同步的点**（漏一个就静默崩 ✗）：`loop_engine` 的 import 行 ·
  **`_LS.FWD = _FM.FWD` 同步**（`FWD` 是主口径快照，拆文件后仍须**单处定义 + 运行时读** ✓）·
  **3 个直接读 `loop_stage.py` 的静态守门**（`_test_inject_pools` / `_test_fsa_freeze` / `_test_dual_horizon` ✓）
* 验收协议：每步 `_test_undefined_names` + **A/B 逐字节** + `release_check`（55 条 · ~11 分钟 ✓）

### 验证

* `tools/_test_e2e_l1l2.py` 重跑 **20/20** ✓ · A/B 工具自证 **8/8 产物逐字节 + stdout 0 差异** ✓
* `git status` 证明 **`engine/` 未改动** ✓ ⇒ 已存基线 `ai_test/_ab/base2` 即"改前"参照 ✓
* 全量回归与 tag 前的 `release_check` 见下一条提交（拆分执行时同步 ✓）

---

## [1.24.0] — 2026-09-27

> 主题：**把「发版前检查」从文档纪律落成一条命令** · **补上项目最大的测试空白（真跑 L1/L2）** · **change_log 归档**
> —— 用户指令："把除了功能性以外所有的项目都提升到 9 分"（先做前三项：可测试性 / 工程纪律 / 文档）
> ⚠ **引擎行为零改动**（本次只加测试/工具/文档 ✓）

### 一、补上最大的测试空白：**真跑一代的完整 L1 + L2**（可测试性 8 → 9）

**问题有多严重**（v1.23.0 真事故的根因）：本项目此前**没有任何测试跑过 L1/L2** ✗ ——
存活的"真起引擎"测试（`smoke_gen_only.py` / `_test_parallel_runner.py` / `_test_dynamic_add.py`）
**一律用 `--gen_only`，而它恰好跳过 L1+L2** ✗✗（`_test_ghost_args.py` 自己都写明了这点）。
⇒ v1.23.0 拆分后 `loop_stage.py` 少了 4 个 import（`HERE` / `trim_cache_mb` / `ts_mean` / `_P.LIB_ENTRIES`），
**全部测试照样全绿**，而真实挖掘**每代秒崩** ✗ ⇒ 用户白等一整晚。

**新增 `tools/_test_e2e_l1l2.py`**（20 项断言 · 实测 **184 s**）：
- **生产同款 flag**：`--strip_style --style_obs --pool_obs --min_pool_calmar --pool_gate_or_all --dual_fwd=20 --min_calmar2=0.701`
  —— 那 4 个 `NameError` 就住在这几条路上 ✓
- **规模压到最小**：`--mine_pool=50`（最小池）· `--n=12` · `--l2=2` ⇒ 全链路 ~3 分钟（不是 50~80 分钟 ✓）
- **隔离靠备份/还原**：引擎产物路径是 `__file__` 派生的、**没有参数/环境变量出口** ✗
  （`loop_paths.set_mine_pool` 只接受真实池名 ✓）⇒ 备份 8 个文件 → 跑 → 断言 → **还原并逐字节校验** ✓
- **断言**：里程碑齐全（候选生成 → L1 分批 → L1 结果 → L2 精筛 → L2 结论 → 诊断写 journal → 代末落盘）
  · 无 `Traceback`/`NameError` · state/archive/journal **真的被更新** · **别的池分毫未动**（防"写错池"）✓
- **安全前提做成硬检查**：挖掘在跑 ⇒ **直接失败退出**（不静默跳过，否则发版可能不经它 ✗）

### 二、"同 seed A/B"终于自动化了（可测试性）

**新增 `tools/_test_gen_determinism.py`**（14 项断言 · 2 × 27 s）：
本项目铁律"搬函数后必须跑『名字解析检查 + 同 seed A/B』"里，**"名字解析"早有守门、"A/B"一直靠人手跑** ✗。
⇒ 用 `--gen_only`（不跑 L1/L2、不写状态 ✓）同 seed 跑**两遍**、剔掉耗时/时刻后**逐行比对** ✓。
指纹含各拦截计数与 **`尝试36`**（对 RNG 流极敏感 ✓）、本代参数/五维配比/亲本策略、上一代 state 的诊断数值 ✓。
实测：**0 差异行** ✓（生成确实可复现 ✓）。
> ⚠ 覆盖边界（如实说）：`--gen_only` 只打印**摘要计数**、不打印 30 条表达式 ⇒
> 这**不能**证明"候选集合逐字节相同" ✗（那要 L1，~25 分钟 ✗）；
> 它能抓的是**随机性/顺序漂移**（漏播种的 `random`、`set` 迭代顺序、`hash` 随机化 …）—— 正是重构最易踩的那类 ✓

### 三、发版纪律落成**一条命令 + 一个退出码**（工程纪律 8 → 9）

**新增 `tools/release_check.py`**（发版前**唯一入口**）：
```
① 版本一致性（VERSION / README / change_log / package.json / settings …）
② 未定义名（拆分/搬函数最容易漏的那类 NameError）
③ 全部守门（tools/_test_*.py 串行跑，逐个落日志 ai_test/_release_logs/）
④ 汇总：通过 x/y · 失败清单 · 最慢 3 个 · 总耗时 · 非零退出
```
★ 为什么需要：此前"发版纪律"**只写在文档里** ✗（`change_log` v1.21.16 那条"全量回归必须先跑完全绿"），
而回归入口 `ai_test/_run_all_tests.py` 自己就是个**临时脚本**、还在"可随时删"的目录里 ✗
⇒ "发版前该跑什么"**依赖人记得** ✗（v1.23.0 的教训正是"记得跑的不够、该自动的没自动" ✗）。
★ 硬前提：**挖掘在跑 ⇒ 拒绝执行**（两个 heavy 守门一个真写轨迹、一个依赖 state 稳定 ✓
  且既有守门会写控制文件 ✓ 与"挖掘运行时禁跑全量回归"同源 ✓）。
★ 支持 `--list` / `--only <子串>` ✓

### 四、`change_log.md` 归档（文档 6 → 9）

本文件曾 **549 KB / 7683 行 / 154 个版本** ⇒ 查最近改动得先翻过一年份历史 ✗（"文档"扣分的就是这条 ✓）。
⇒ 主文件**只保留最近 15 个版本**（**549 KB → 71 KB，‑87%** ✓），其余 **139 个版本**整段搬到
**新增 [`change_log_archive.md`](change_log_archive.md)**（478 KB）。
★ **原文一字未改** + 切分器与校验：版本数 **15 + 139 = 154** ✓ 无重复 ✓ 无丢字 ✓（只多出前言/指针/归档头 277 字符 ✓）。

### 五、八维评分更新（`docs/maintainability.md`）

| 维度 | 09-26 | **09-27** | 变化依据 |
|---|---|---|---|
| 可测试性 | 8 | **9** | 补上"完整 L1/L2 端到端"（§一 ✓）+ "同 seed A/B"自动化（§二 ✓）；守门 52 → **55 条** |
| 工程纪律 | 8 | **9** | 发版前检查落成 `release_check.py`（一条命令 + 退出码 + 挖掘护栏 ✓，§三 ✓） |
| 文档 | 6 | **9** | change_log 归档（549 KB → 71 KB ✓，§四 ✓） |
| **综合** | **7.4** | **8.0** | 64 / 8 = 8.0 |

> ⚠ 未动的三项（**不是忘了** ✗）：**功能性 8**（行为逐字不变 ✓ 是本次的硬约束）；
> **性能 6**（**一次性能优化都没做** —— 重构期明令"不许动数值路径"，要做须用户明确授权"允许改实现、但结果逐位不变"✗）；
> **可移植性 7**（看板仍是 Windows 专有：`taskkill` / `ctypes` Win32 内存 API / `CREATE_NO_WINDOW` ✗）；
> **可读性 8 / 可维护性 8**（`loop_stage.py` 仍 1332 行、2 个函数 >300 ⇒ **违反本项目自己的 R1/R2** ✗，
> 再拆的前提是先把 ~20 个口径参数收进一个 dataclass，否则只是"上帝函数换上帝参数表" ✗）。

### 验证

- ★ **`tools/release_check.py` 全量：55/55 全过 ✓（总耗时 10.0 分钟）** ——
  含新增两个守门：`_test_e2e_l1l2.py` **186 s** ✓ · `_test_gen_determinism.py` **57 s** ✓
  （最慢三名：e2e 186s · `_test_parallel_runner` 152s · `_test_daily_dd` 61s ✓）
- 单独实跑：e2e **20/20** ✓ · 确定性 **14/14**（0 差异行 ✓）· crash 徽标 **14/14** ✓
- change_log 切分校验：154 → 15 + 139 ✓ 无重复 ✓ 无丢字 ✓
- 引擎行为：**零改动**（本次未碰 `engine/` ✓）

---

## [1.23.2] — 2026-09-26

> 主题：**修「停止之后，池卡片仍挂着『启动即崩』红字徽标」** —— 用户实测驱动，纯看板侧修复

### 现象（用户实测）

> "我全部停止了，然后看到俩池子现在都是启动即崩的状态，这跟以前好像不一样？
>  以前应该是回到已停止的状态才对吧~"

### 真因（**不是文案 bug，也不是本次拆分引入的回归** ✓）

前端**本来就**会把状态文案显示成「已停止」✓（`App.tsx`：`configured ? '待启动' : (stopped ? '已停止' : '空闲')`）；
用户看到的是**多出来的红色徽标**「启动即崩 ×1」✗。

徽标的语义是「**此刻**启动即崩」（见 `tools/parallel_runner.py` 2026-09-20 的设计说明 ✓），
但它**只有一个撤销触发点：跑通一代（`rc==0` 且 stderr 为空）** ✗ ——
而「**被用户停掉**」的退出码是 `rc=1` ⇒ 走 `if rc != 0` 分支、`killed=True`
⇒ **既不写徽标、也不撤徽标** ✗✗ ⇒ 一次真崩留下的徽标会**一直挂着** ✓

**实测时间线**（`ai_test/_tracks/_engine_exits.log`）：

| 时刻 | 池 / 代 | rc | 耗时 | 判定 | 效果 |
|---|---|---|---|---|---|
| 22:22:02 | `all` gen81 | 1 | 0.6min | **异常** `NameError: 'HERE'` | **写徽标** ✓ |
| 22:22:42 | `300` gen191 | 1 | 1.3min | **异常** `NameError: 'trim_cache_mb'` | **写徽标** ✓ |
| 23:42:14 | `all` gen81 | 1 | **24.9min** | **被停**（err=0） | **没撤** ✗ |
| 23:46:14 | `300` gen191 | 1 | 0.5min | **被停**（err=0） | **没撤** ✗ |

⇒ 两池其实**早已恢复正常**（`v1.23.1` 那次各跑了 **24.9 分钟、stderr 为空**，
是用户主动停的 ✓）⇒ 徽标是**过期证据** ✓

⚠ **为什么以前没见过**：这个缺口自 2026-09-20 就在 ✗，只是**以前那两池没经历过"真崩"**
（v1.23.0 是第一次）⇒ 没有徽标可残留 ✓ —— 所以用户"感觉不一样"是对的，但不是"停止逻辑变了" ✓

### 修法

`dashboard/api/app/mine.py` 新增 `clear_crashes(pools=None)`，并在**停止**时调用：
- **单池停止** ⇒ `clear_crashes([pool])` ✓（只撤该池，**别的池的徽标不许误撤** ✗）
- **全部停止** ⇒ `clear_crashes()` ✓

★ **语义**：**停止 = 用户的明确动作、该池已回到空闲** ⇒ 徽标"此刻已不成立" ⇒ 一并撤掉 ✓
★ **保护不减弱**：真·必崩的池**下次启动还会崩** ⇒ 一分钟内徽标自动回来 ✓
  （撤的是「过期证据」，**不是关掉报警** ✓ —— 守门里专门钉住这条 ✓）

### 验证

- **新增守门 `tools/_test_crash_badge.py`（14 项全过 ✓）**：
  静态 3 项（接线 + "非被停的异常退出仍写徽标"）＋ **行为 8 项**（导入 `app.mine`、
  换到**临时控制文件**真调 `clear_crashes`：只撤指定池 · 不误撤他池 · 幂等 ·
  「不碰 `exits` / `enabled` / `stopped`」· 原子写 ✓）
- **清掉当前残留**：`_control.json` 的 `crashes` 由 `{all:[81], 300:[191]}` → `{}` ✓
- **重启后端**（`dashboard/api/run.py`，`reload:false` ⇒ 必须重启 ✓）；
  接口复核：`/api/mine/state` 的 `crashes = {}` ✓ ⇒ 卡片恢复干净「已停止」✓

---

## [1.23.1] — 2026-09-26

> 主题：**修 `v1.23.0` 的 4 处 `NameError`（拆分漏 import / 用了调用方局部）
> + 修「副口径复原成 no-op」造成的口径静默污染** —— **纯修复，恢复正常挖掘**

### 真事故（v1.23.0 发版后，重启挖掘第一批就崩）

| 现象 | 真因 |
|---|---|
| `all` 池：`NameError: name 'HERE' is not defined` | `loop_stage.py` 用了 `HERE`（引擎目录）但**没定义/没 import** ✗ |
| `300` 池：`NameError: name 'trim_cache_mb' is not defined` | `loop_stage.py` 用了 `trim_cache_mb` 但**没 import** ✗ |
| **L2 每个候选**都只打一行 `[j] ERR NameError`（被 `except` 吞掉） ⇒ **一个候选都入不了库** ✗✗ | `_l2_pool_tags` 里用了 **调用方 `_run_l2_phase` 的局部变量 `pool_rows`** ✗（同类：`ts_mean` 没 import、`loop_persist` 的 `LIB_ENTRIES` 没改成 `_P.`、`run_tracks._rotate_schedule` 漏了 `panel_cache` 形参） |
| **池内指标静默改口径**（实测池门槛 `+0.254`，正确值 `+0.192`）| 文件级拆分时把 `FWD` **一律替换成 `_FM.FWD`** ✗ ⇒ 副口径块的 `finally: _FM.set_fwd(int(FWD))` 变成 `int(_FM.FWD)` ⇒ `set_fwd(20)` 之后 `_FM.FWD` **自己就是 20** ⇒ **"复原"是 no-op** ✗✗ |

### 为什么没被拦住（★ 诚实记账）

`v1.23.0` 的 **L3 Step 4（文件级拆分）只跑了 `py_compile` + 全量回归**，
**漏掉了 Step 1~3 一直在用的「同 seed 复跑 + `state` 逐字段对照」** ✗。
而全量回归**不覆盖完整 L1/L2 路径**（`_test_parallel_runner` 用 `--gen_only` 跳过 L1/L2），
且那 4 个名字**只在特定参数/特定池下才走到** —— 典型：`HERE` 那行只在 `all` 池
「外部池注入」时执行，而我的对照命令是 `--mine_pool=500` ⇒ **正好跳过了它** ✗。
⇒ **教训**：**`py_compile` 只查语法、不查名字**；搬函数后必须做一次**作用域感知**的名字解析检查 ✓

### 修法

1. `loop_stage.py`：补 `HERE` / `from loop_cache import trim_cache, trim_cache_mb` / `from loop_ops import …, ts_mean`
2. `loop_persist.py`：补 `import re`（`_mk_library_skeleton` 用）+ `LIB_ENTRIES` → `_P.LIB_ENTRIES`
3. `loop_stage.py`：`pool_rows.extend(pool_rec)` **从 `_l2_pool_tags` 移回调用方** `_run_l2_phase`（那里才是它的作用域 ✓）
4. `run_tracks.py`：`_rotate_schedule` 补 `panel_cache` 形参（**轮转模式一起就崩** ✓，生产用并行模式所以没暴露）
5. **`loop_stage.py` 恢复模块级 `FWD`**（`FWD = _FM.FWD`）：
   `[::FWD]` 切片与副口径 `finally` 复原**都回到它** ✓；`loop_engine.main()` 的 `--fwd` 同步块
   **同时同步 `loop_stage.FWD`** ✓（否则 `--fwd` 只改一个模块 ✗）
6. `loop_stage.py` 的 L2 异常打印**补上异常消息**（原来只有 `type(e).__name__` ⇒ 排查时看不到名字 ✗）

### ★ 新增常驻守门 `tools/_test_undefined_names.py`（作用域感知）

扫「**用了、却在本作用域链上都没绑定过**」的名字（自建，因为本机没装 `pyflakes`）：
形参 / 赋值 / `for` / `with` / `except` / import / 嵌套 def 名 / `global`+`nonlocal` 都算绑定，
再沿**闭包链**解析到模块级与内置名 ⇒ 四条都不满足就报 ✓
⚠ 关键：**必须是作用域感知的** —— 第一版用「全文件绑过就算」的宽松判据，
**抓不到「用了调用方的局部变量」**（`pool_rows` 正好被 `_run_l2_phase` 绑过 ✗）。
⇒ 现在扫描 167 个文件、**未定义名 0 处** ✓

### 验证（★ 这次是 **A/B**，不是"看起来对"）

把 `engine/` 用 `git checkout 1129380`（**文件级拆分之前**）恢复，跑**完全相同**的命令
（`--mine_pool=500 --seed=777 --n=20 --l2=3 --strip_style --style_obs --pool_obs
--pools=300,500,1000 --dup_ex_corr=0.90 --min_pool_calmar=0.15 --pool_gate_or_all
--min_strip_calmar=0.15 --dual_fwd=20 --min_calmar2=0.701`）：

| 项 | 拆分前（`1129380`） | 拆分后（本版） |
|---|---|---|
| 候选 [1] 池内指标 | `300:+3.15%/Cal+0.19(市值2.42%/倾斜-0.74%) 500:+1.88%/Cal+0.11 …` | **逐字相同** ✓ |
| 池门槛 | `过(+0.192)` | **`过(+0.192)`** ✓ |
| 种子 / 入库 / 收益流库 / 冻结骨架 / 失败库 / 冻结记账 | 3 / 10 / 10 / 3 / 584 / 17 | **完全相同** ✓ |
| `ERR` / `NameError` | 0 | **0** ✓ |

⇒ 全量回归 **52/52** ✓（含新守门）

### 连带：诚实修订八维评分（7.6 → **7.4**）

`v1.23.0` 这次事故**正好暴露了两个维度的真实缺口** ⇒ 修订（依据与全文见 `docs/maintainability.md §五`）：
- **可测试性 9 → 8**：守门虽到 52 条，但**仍不覆盖完整 L1/L2**（`_test_parallel_runner` 用 `--gen_only` 跳过）✗；
- **工程纪律 9 → 8**：`v1.23.0` **验收不完整**（Step 4 漏了同 seed A/B）⇒ 发版即崩 ✗（现已补规则 ✓）

⇒ 综合 **6.4 → 7.4**（59 / 8 = 7.375）；结构短板（巨型文件/God function）确实已补齐 ⇒ 分数较基线仍显著上升 ✓

---

