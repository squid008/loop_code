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
  }
  /** 统一口径的费后指标（`tools/factor_metrics.py` 重算；缺失项为 null） */
  metrics?: Record<string, number | null>
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
  status?: string
}

export interface LibraryEntriesDto {
  count: number; limit: number; entries: LibraryEntryDto[]; note: string
}

export interface SelectedFactor {
  code: string; pool: string; grade: string; stripCalmar: string; expr: string
  /** ★ 2026-09-16：精选池也能「点开看详情」—— 与库表同一套字段（联表自各池库文档 + 指标表） */
  detail?: LibraryFactor['detail']
  metrics?: Record<string, number | null>
  inBank?: boolean | null
}

export interface SelectedDto {
  found: boolean; path?: string; mtime?: string
  count?: number; factors: SelectedFactor[]; gates: string[]; notes: string[]
}

/** ★ 2026-09-16：因子曲线（离线预算，详情页图表用；已下采样 ≤700 点） */
export interface CurvesDto {
  found: boolean
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
  ind: { raw: StyleSummDto[]; neut: StyleSummDto[] }
  r2: { raw: number | null; neut: number | null }
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
  /** ★ 调度器在跑 ⇒ 只是"把该池并回启用集"（并行下**马上**会起引擎；轮转下等下一轮） */
  merged?: boolean
  restarted?: boolean
  note: string
}

// ---------------------------------------------------------------- 接口
export const api = {
  meta: () => get<MetaDto>('/meta'),
  status: (fresh = false) => get<StatusDto>(`/status${fresh ? '?fresh=true' : ''}`, 40000),
  libraries: () => get<{ libraries: LibraryDto[]; totalFactors: number }>('/library'),
  library: (pool: string) => get<LibraryDto>(`/library/${pool}`),
  /** ★ 新入库日志（最近 N 条；`/library/entries` **必须**在路由里排在 `/library/{pool}` 之前） */
  libraryEntries: (limit = 50) => get<LibraryEntriesDto>(`/library/entries?limit=${limit}`),
  selected: () => get<SelectedDto>('/selected'),
  // ★ 因子曲线（离线预算好，读文件 + 下采样 ⇒ 打开详情几乎零开销）
  curves: (pool: string, name: string, maxPts = 700) =>
    get<CurvesDto>(`/curves/${pool}/${encodeURIComponent(name)}?max_pts=${maxPts}`, 60000),
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
  mineStartPool: (pool: string) =>
    post<MinePoolResp>('/mine/start_pool', { pool }),
  mineGlobal: () => post<{ ok: boolean; pid: number; alive: boolean | null; log: string; note: string }>(
    '/mine/global', {}, 60000),
}
