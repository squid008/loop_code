/**
 * API 客户端。
 *
 * ★★★ 关键设计（用户 2026-09-15 要求"端口只改一处"）：
 *   本文件**只请求相对路径 `/api/*`** —— 由 Vite dev-server 的 proxy 转发到后端。
 *   ⇒ 前端代码里**没有任何端口号**；改端口只需改 `dashboard/config.json` ✓
 */

const BASE = '/api'

async function get<T>(path: string, timeoutMs = 30000): Promise<T> {
  const ctl = new AbortController()
  const t = setTimeout(() => ctl.abort(), timeoutMs)
  try {
    const r = await fetch(BASE + path, { signal: ctl.signal })
    if (!r.ok) throw new Error(`${r.status} ${r.statusText} — ${path}`)
    return (await r.json()) as T
  } finally {
    clearTimeout(t)
  }
}

/** ★ POST：后端把业务错误放在 `detail` 里（HTTP 400/409），这里把它抬成异常消息 ⇒ UI 直接可展示 */
async function post<T>(path: string, body: unknown, timeoutMs = 60000): Promise<T> {
  const ctl = new AbortController()
  const t = setTimeout(() => ctl.abort(), timeoutMs)
  try {
    const r = await fetch(BASE + path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: ctl.signal,
    })
    const txt = await r.text()
    const j = txt ? JSON.parse(txt) : {}
    if (!r.ok) throw new Error(j?.detail || `${r.status} ${r.statusText}`)
    return j as T
  } finally {
    clearTimeout(t)
  }
}

// ---------------------------------------------------------------- 类型
export interface PoolDef { key: string; label: string; index: string; color: string }

export interface PoolStatus {
  key: string
  label: string
  running: boolean
  runningPids: number[]
  state: {
    bank_n?: number; bank_ex_n?: number; n_tested?: number
    seeds_n?: number; fsa_n?: number; frozen_n?: number; fail_lib_n?: number
    cfg?: Record<string, unknown>; sizeMB?: number; mtime?: number
  } | null
  librarySize: number | null
  tested: number | null
  journal: { gens: number; maxGen: number | null; path: string | null; mtime: string | null }
  archive: { rows: number; passed: number; maxGen: number | null; path: string | null }
}

export interface ProcessInfo {
  pid: number; kind: string; script: string; pools: string[]
  start: string; memMB: number; cmd: string
}

export interface StatusDto {
  generatedAt: string
  anyRunning: boolean
  processes: ProcessInfo[]
  processError: string | null
  pools: PoolStatus[]
  summary: {
    poolCount: number; runningPoolCount: number
    totalLibrary: number; totalTested: number; totalArchiveRows: number
  }
}

/** ★ 2026-09-16：明细段 + 统一口径指标（点开"详情"用） */
export interface LibraryFactor {
  code: string; pool: string; gen: string; family: string
  summary: string; status: string
  /** ★ **完整公式**（来自明细段）；注意总览表那一列是被截断的 */
  expr: string
  /** 该编号是否**仍在当前有效库**（`state.bank`）里；`false` = 只剩历史编号 */
  inBank?: boolean
  detail?: {
    sign: string; family: string; leaves: string; skeleton: string
    poolTag: string; poolTagNote: string; strip: string; metricsDocText: string
    /** ★ 2026-09-17：`sign` 不是库文档写的、而是**退回重算指标表**取的时候标出来路
     *  （库文档当时写的是"未记录"⇒ 空 ⇒ 显示 —；指标表里有真值 ⇒ 用它 ✓ **不冒充**库记录 ✓） */
    signFrom?: string
  }
  /** 统一口径的费后指标（`tools/factor_metrics.py` 重算；缺失项为 null） */
  metrics?: Record<string, number | null>
  /** ★★★★★ 2026-09-21（用户："指标连 20 日一起重算"）—— **20 日口径**的同一套指标 ✓
   *  （列名与 `metrics` 完全一致，只有口径不同 ⇒ 详情页切换时整块换它 ✓） */
  metrics20?: Record<string, number | null>
  /** ★★★ 2026-09-21：口径强项标签 = `'5'` / `'20'` / `'双'` / `''`（后端 `_hzn_tag` 判好 ✓） */
  hzn?: string
  /** 便于列表直接展示（免得前端去翻 `metrics20` ✓） */
  cal20?: number | null
  /** ★★ 2026-09-22（用户："因子库加一列**卡玛**…注意是卡玛，**不是剥后卡玛，也不是超额卡玛**"）
   *  = **组合自身**卡玛（Top10% 等权绝对口径 ✓ 指标表 `calmar_top` ✓）
   *  ⚠ 不要拿 `metrics.calmar`（**超额**卡玛 ✗）或 `metrics.strip_calmar`（剥后 ✗）冒充 ✓ */
  cal_top?: number | null
  ic20?: number | null
  turn20?: number | null
  }

export interface LibraryDto {
  pool: string; label: string; found: boolean
  declaredCount: number | null
  count: number
  stateBank: number | null
  stateTested: number | null
  stateFrozen: number | null
  /** 指标表（`docs/factor_metrics.csv`）是否可用 + 其中属于本池的条数 */
  metricsFound?: boolean
  metricsInfo?: { found: boolean; path?: string; rows?: number }
  /** ★ 2026-09-21：20 日口径表的元信息（前端据此判"20 日那档能不能切" ✓） */
  metrics20Info?: { found: boolean; path?: string; rows?: number }
  metricsMtime?: string | null
  /** ★ 本池**在库且已测**的条数（与 `stateBank` 比才说明"表跑完了没"） */
  metricsMeasured?: number
  /** ★ 表里**已移出的历史编号**也算过指标的条数（`--include_history`；默认 0） */
  metricsHistory?: number
  /** ★ 敢不敢判"在不在库"：新格式（表带 `in_bank` 列）恒为 true；老格式需条数恰好相等 */
  inBankKnown?: boolean
  /** ★ 「在库里、但库文档没有编号」的因子（文档同步漏记的历史缺口，如实展示） */
  orphans?: Array<{ name: string; expr: string; ann_ex: number | null }>
  caliber?: {
    authoritative: string; mdTableRows: number; mdTableMeans: string
    mdDeclared: number | null; mdDeclaredMeans: string
    stateBank: number | null; stateBankMeans: string
  }
  path: string; mtime: string | null; factors: LibraryFactor[]
}

/** ★ 2026-09-17 新增：**新入库事件**（看板「新入库日志」卡片）。
 *
 * 用户之问：「我发现又入库了一个新因子，但**找不到什么时候入库的、入的哪个库**」⇒ 加这张卡 ✓
 * 时间口径分两种（后端在 `tsSource`/`tsNote` 里说明，看板要显示出来，不许含糊 ✗）：
 *  · `engine`      = 引擎入库那一刻写的**真实时间** ✓
 *  · `backfill`    = 历史条目回填：`gen_log`（该代引擎日志时间）/ `md_mtime`（该池库文档最后修改）
 *  · `unknown`     = 早期入库、**没有时间证据** ⇒ 时间留空（不臆造 ✓，看板标"时间未知"）
 */
export interface LibraryEntryDto {
  ts: string | null
  tsSource?: string
  tsNote?: string
  source?: string
  pool: string
  gen: number | null
  code: string | null
  expr: string
  family?: string | null
  summary?: string
  oneLiner?: string | null
  /** ★★ 2026-09-17（用户："把已入库、已移出的状态也加上，加在 F06 文字旁边"）：
   *  **三态**（后端每条都显式给）：true 当前有效库 / false 已移出 / null 判不了（不猜 ✓）
   *  判据与「因子库」页签同源：指标表 `in_bank` 列 → 库文档行 → 都没有就是 null ✓ */
  inBank?: boolean | null
  inLibrary?: boolean
  detail?: LibraryFactor['detail']
  metrics?: Record<string, number | null>
  /** ★★★★★ 2026-09-25（用户："这 F47 为啥…20 日的那个按钮我点不了，提示还未生成"）——
   *  **口径强项标签 + 20 日那一套指标**（与「因子库」表 / 精选池 **同源** ✓）：
   *  后端 `/api/library/entries` 从 `_lib(pool)` 照抄这五项（`detail/metrics/metrics20/status/hzn` ✓）
   *  ⚠ **原来这里漏了 `hzn` / `metrics20`** ✗ ⇒ 从「新入库日志」卡点开的详情弹层拿不到
   *     `metrics20` ⇒ 详情页 `has20` 恒为假 ⇒ **20 日口径按钮被误置灰**（提示"还未生成" ✗，
   *     而数据其实早就算好了 ✓）—— 三条入口里**只有这条**漏了（因子库 / 精选池两条都传了 ✓）*/
  hzn?: string | null
  metrics20?: Record<string, number | null>
  status?: string
}

export interface LibraryEntriesDto {
  count: number; limit: number; entries: LibraryEntryDto[]; note: string
}

export interface SelectedFactor {
  code: string; pool: string; grade: string; stripCalmar: string; expr: string
  /** ★★ 2026-09-22（用户："精选池里因子除了显示剥卡玛，也显示**原始卡玛**吧"）——
   *  **未剥**的费后超额卡玛，来自 `loop_strip_style_bank.csv` 的 `calmar` 列 ✓
   *  ⚠ 与 `stripCalmar` **同一次评估**（可直接对比"剥掉了多少" ✓）
   *  —— 不是统一口径指标表那次重算（那是另一次评估 ✗） */
  calmar?: string | null
  /** ★★ 2026-09-22（用户之问："精选池这个卡玛是不是搞错了？我点开详情**日频打点**卡玛只有 0.369"）
   *  —— 数值都没错 ✗，是**口径没写清** ✗：
   *    · `calmar` = **超额**口径（组合 − 基准）· **期频**打点（只在换仓日 ✓）
   *    · `calmarD` = 同一口径的**日频**（逐日 mark-to-market ⇒ 回撤更真 ⇒ 通常更低 ✓）
   *    · 详情页那个 0.369 是 `calmar_top_d` = **组合自身**口径 + 日频 ✗（与上面两个都不是一回事 ✓）
   *  ⇒ 卡片上把期频/日频**并排摆出来** ✓，免得再对不上 ✓ */
  calmarD?: string | null
  stripCalmarD?: string | null
  /** ★ 2026-09-16：精选池也能「点开看详情」—— 与库表同一套字段（联表自各池库文档 + 指标表） */
  detail?: LibraryFactor['detail']
  metrics?: Record<string, number | null>
  inBank?: boolean | null
  /** ★★★★★ 2026-09-21（用户："精选池那里还只有 A 标签，没有 5、20、双标签"）——
   *  口径强项标签（与库表**同源**：后端 `_hzn_tag` ✓）＋ 20 日那一套指标（详情弹层要用 ✓） */
  hzn?: string
  metrics20?: Record<string, number | null>
}

export interface SelectedDto {
  found: boolean; path?: string; mtime?: string
  count?: number; factors: SelectedFactor[]; gates: string[]; notes: string[]
}

/** ★ 2026-09-16：因子曲线（离线预算，详情页图表用；已下采样 ≤700 点） */
export interface CurvesDto {
  found: boolean
  /** ★ 2026-09-21：这条曲线是**哪个调仓口径**（5 / 20）—— 由后端按请求回填 ✓ */
  fwd?: number
  name?: string
  pool?: string
  expr?: string
  sign?: number
  start?: number
  end?: number
  n_rebal?: number
  cost?: number
  window?: number
  caliber?: string
  path?: string
  mtime?: string | null
  hint?: string
  err?: string
  daily?: {
    dates: number[]; navT: (number | null)[]; navM: (number | null)[]
    navE: (number | null)[]; ddE: (number | null)[]; ddT: (number | null)[]
  }
  period?: {
    dates: number[]; ic: (number | null)[]; rankIc: (number | null)[]
    decile: (number | null)[][]; ls: (number | null)[]
    turn?: (number | null)[]
  }
  strip?: {
    dates: number[]
    navs: Record<string, (number | null)[]>
    calmars: Record<string, number | null>
    caliber?: string
  } | null
  /** ★ 风格相关性画像（逐期截面 Spearman；raw=原始 / neut=剥总市值+行业） */
  /**
   * ★★★★★ 2026-09-20（用户："加个图，可以看 11 个风格的动态暴露曲线，鼠标移动显示每个风格的
   * 动态暴露值，再加个按钮全部隐藏/全部显示"）—— **组合的动态风格暴露** ✓
   *   · 值 = Barra **原生值**（市值加权 0 均值口径 ⇒ **中性线 0** ✓，不可拿池内等权均值当参照 ✗）
   *   · 组合 = 该因子最强十分之一等权（后端 `factor_curves.expo_for` 算好 ✓，仅换仓日 ✓）
   */
  expo?: {
    dates: number[]
    styles: string[]
    series: Record<string, (number | null)[]>
    neutral?: number
    caliber?: string
    styCal?: string
  } | null
  style?: StyleProfileDto | null
}

export interface StyleSummDto {
  mean: number | null
  meanAbs: number | null
  ir: number | null
  /** 朴素 t = IR·√T（⚠ 相关序列自相关高时会被放大，别直接看） */
  t: number | null
  /** ★ AR(1) 校正后的 t（T_eff = T·(1−ac1)/(1+ac1)）—— 该看这个 */
  tAdj: number | null
  win: number | null
  ac1: number | null
}

export interface StyleProfileDto {
  n_periods: number
  styles: string[]
  ind_names: string[]
  caliber: string
  raw: Record<string, StyleSummDto>
  neut: Record<string, StyleSummDto>
  /** ★★ 2026-09-18（用户要求）：**剥全部**（15 个连续风格秩回归 + 行业内去均值）——
   *  用来验证"剥干净了没有"（各风格 |均值| 应≈0 ✓）；老文件没有这个键 ⇒ 页面按"未生成"处理 ✓ */
  allsty?: Record<string, StyleSummDto>
  ind: { raw: StyleSummDto[]; neut: StyleSummDto[]; allsty?: StyleSummDto[] }
  r2: { raw: number | null; neut: number | null; allsty?: number | null }
}

export interface MetaDto {
  app: string; version: string
  settings: {
    configPath: string; projectRoot: string; docsDir: string; engineDir: string
    backend: { host: string; port: number }
    frontend: { host: string; port: number }
    reservedPorts: Record<string, number>
    database: Record<string, unknown>
  }
  pools: PoolDef[]
  endpoints: string[]
}

// ---------------------------------------------------------------- 挖掘控制（v1.3.0：单调度器 + 池轮转）
export interface PoolSlot {
  enabled: boolean      // 是否参与轮转
  stopped: boolean      // 是否被单独停掉
  mining: boolean       // 是否正在跑它这一代
  /** ★ 2026-09-19：是否正在**收尾审查**（池内收尾指名它，或全局收尾进行中）*/
  reviewing?: boolean
  /** ★ 2026-09-19：该池**本轮已完成几代**（不限模式下快池涨得快）*/
  gensRound?: number
  engine: number[]      // 该池当前引擎 PID
  /** ★ 2026-09-17：最近几次"启动即崩"的代数（空 = 没崩过）。崩了必须在卡片上看得见 */
  crashes: number[]
}

export interface MineStateDto {
  mode: string                    // 'scheduler'
  phase: string                   // idle | mine | tail
  phaseLabel: string              // 空闲 / 挖掘中 / 收尾审查中
  running: boolean
  stopAll: boolean
  schedulerPids: number[]
  scheduler: { pid: number; cmd: string; memMB?: number }[]
  engines: { pid: number; pools: string[] | null; memMB?: number }[]
  curPool: string | null
  curGen: number | null
  /** ★ 2026-09-19：正在做**池内收尾**的那个池（看板显示"审查中"✓）*/
  tailPool?: string | null
  /** ★ 2026-09-19：每池**本轮已完成代数** {池: n}（用户要"各池自己的进度"✓）*/
  gensRound?: Record<string, number>
  /** ★ 每个**正在跑**的池 + 它这一代的代数（来自控制文件 `active`；并行时会有多条） */
  active?: Array<{ pool: string; gen: number | null; pid: number | null }>
  round: number | null
  rounds: number | null
  roundText: string | null
  curText: string | null
  tailAt: string | null
  updated: string | null
  knownPools: string[]
  enabled: string[]
  stopped: string[]
  byPool: Record<string, PoolSlot>
  /** ★ 2026-09-17：各池最近几次"启动即崩"的代数（{池: [gen, ...]}） */
  crashes?: Record<string, number[]>
  runningPools: string[]
  freeGB: number | null
  gbPerEngine: number
  memNote: string
  defaultRounds: number
  roundsRange: [number, number]
  script: string
  note: string
  // ★★★ 调度模式 / 面板共享（2026-09-16；**以真实进程命令行为准**）
  execMode: string                 // rotate | parallel
  maxParallel: number
  /** ★★ 2026-09-23（统一口径）：**此刻按内存真能跑几个**（= `parallel_runner.slot_cap` ✓，
   *  与"启动那一刻"和"运行期闸门"同一个公式；口径见「配置/口径」页 ✓） */
  slotCap?: number | null
  /** ★ 调度器**运行期**实际生效的上限（控制文件写回；没在跑时为 null ✓） */
  effMaxParallel?: number | null
  /** ★ 参与并行的池数（= 启用池 − 已单独停止；与调度器的 `runnable` 同口径 ✓） */
  runnableCount?: number
  /** ★ 并行上限是"自动"的（按可用内存与启用池数动态重算；加池会立刻放宽） */
  autoParallel: boolean
  memPerEngine: number
  panelCache: string               // off | use | build
  execModes: string[]
  parallelRange: [number, number]
  memDefault: number
  panelCacheInfo: {
    exists: boolean
    gb?: number
    builtAt?: string
    fields?: number
    sourceOk?: boolean
    staleSources?: string[]
    hint?: string
    err?: string
  }
}

export interface MineStartResp {
  ok: boolean
  started: { pool: string; pid: number; alive: boolean | null; cmd: string; log: string }[]
  reused?: boolean
  schedulerPids?: number[]
  enabled?: string[]
  rounds?: number
  freeGB?: number | null
  note: string
}

export interface MineStopResp {
  ok: boolean
  scope: string
  killed: { pid: number; kind: string; pools: string[] | null; rc: number; out: string }[]
  stillRunning: { pid: number; kind: string; pools: string[] | null }[]
  tail?: { pid: number; note: string } | null
  note: string
}

export interface MinePoolResp {
  ok: boolean
  pool: string
  enabled: string[]
  stopped: string[]
  /** ★ 2026-09-23：本次**实际生效**的轮数上限（面板回读用 ✓；不传 rounds 时 = 沿用的 ctl 值） */
  rounds?: number
  /** ★ 调度器在跑 ⇒ 只是"把该池并回启用集"（并行下**马上**会起引擎；轮转下等下一轮） */
  merged?: boolean
  restarted?: boolean
  note: string
}

// ---------------------------------------------------------------- 算子手册（首页按钮 + 滚动弹窗）
export interface OpItem {
  name: string      // 算子名（含窗口，如 ts_std100）
  zh: string        // 中文名
  tip: string       // 一句话说明
  group: string
  kind: string      // unary | binary
  window: number | null
  sig: string       // 写法示例，如 mul(a, b)
  winText: string   // 过去 N 期 / 逐点运算
}

export interface OpsDto {
  ops: OpItem[]
  fields: { name: string; zh: string; tip: string }[]
  notes: { k: string; v: string }[]
  counts: { ops: number; fields: number }
  source: string
}

// ---------------------------------------------------------------- 接口
export const api = {
  meta: () => get<MetaDto>('/meta'),
  /** ★ 2026-09-19：算子手册（算子与字段的中文含义；名单唯一事实源仍是 ops_registry） */
  ops: () => get<OpsDto>('/ops'),
  status: (fresh = false) => get<StatusDto>(`/status${fresh ? '?fresh=true' : ''}`, 40000),
  libraries: () => get<{ libraries: LibraryDto[]; totalFactors: number }>('/library'),
  library: (pool: string) => get<LibraryDto>(`/library/${pool}`),
  /** ★ 新入库日志（最近 N 条；`/library/entries` **必须**在路由里排在 `/library/{pool}` 之前） */
  libraryEntries: (limit = 50) => get<LibraryEntriesDto>(`/library/entries?limit=${limit}`),
  selected: () => get<SelectedDto>('/selected'),
  // ★ 因子曲线（离线预算好，读文件 + 下采样 ⇒ 打开详情几乎零开销）
  // ★★ 2026-09-21（用户："切换到 20 日调仓所有指标曲线就都选成 20 日的"）：
  //   加 `fwd`（调仓口径）⇒ 后端按口径**换目录**读（5 日 = 基础目录 / 20 日 = `_fwd20` ✓）
  curves: (pool: string, name: string, maxPts = 700, fwd = 5) =>
    get<CurvesDto>(`/curves/${pool}/${encodeURIComponent(name)}?max_pts=${maxPts}&fwd=${fwd}`, 60000),
  stripBank: () => get<{ found: boolean; count: number; rows: Record<string, string>[] }>('/strip-bank'),
  poolObs: (pool: string, limit = 200) =>
    get<{ found: boolean; columns: string[]; rows: Record<string, string>[] }>(`/pool-obs/${pool}?limit=${limit}`),
  // ★ 挖掘控制（单调度器 + 池轮转）
  mineState: () => get<MineStateDto>('/mine/state', 40000),
  // ★ 调度模式 / 面板共享（2026-09-16）：不传 ⇒ 沿用上次设置 ⇒ 再没有就是历史默认（rotate/off）✓
  mineStart: (pools: string[], rounds: number,
              opts?: { execMode?: string; maxParallel?: number; memPerEngine?: number;
                       panelCache?: string }) =>
    post<MineStartResp>('/mine/start', { pools, rounds, ...(opts ?? {}) }),
  mineStop: (pool?: string) =>
    post<MineStopResp>('/mine/stop', pool ? { scope: 'pool', pool } : { scope: 'all' }),
  // ★★★★★ 2026-09-23（用户："我单池点启动，面板上轮数我填了 50，怎么轮数上限还是 1 呢？"）：
  //   原来这里**只发 `{pool}`** ✗ ⇒ 面板填的轮数根本没送出去 ⇒ 后端只能沿用控制文件里的旧值 ✗
  //   ⇒ 补上 `rounds`（不传 ⇒ 后端沿用现有 ctl，**旧行为不变** ✓）
  mineStartPool: (pool: string, rounds?: number) =>
    post<MinePoolResp>('/mine/start_pool', rounds == null ? { pool } : { pool, rounds }),
  mineGlobal: () => post<{ ok: boolean; pid: number; alive: boolean | null; log: string; note: string }>(
    '/mine/global', {}, 60000),
}
