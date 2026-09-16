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

export interface LibraryFactor {
  code: string; pool: string; gen: string; family: string
  summary: string; status: string; expr: string
}

export interface LibraryDto {
  pool: string; label: string; found: boolean
  declaredCount: number | null
  count: number
  stateBank: number | null
  stateTested: number | null
  stateFrozen: number | null
  caliber?: {
    authoritative: string; mdTableRows: number; mdTableMeans: string
    mdDeclared: number | null; mdDeclaredMeans: string
    stateBank: number | null; stateBankMeans: string
  }
  path: string; mtime: string | null; factors: LibraryFactor[]
}

export interface SelectedFactor {
  code: string; pool: string; grade: string; stripCalmar: string; expr: string
}

export interface SelectedDto {
  found: boolean; path?: string; mtime?: string
  count?: number; factors: SelectedFactor[]; gates: string[]; notes: string[]
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

// ---------------------------------------------------------------- 挖掘控制
export interface PoolProcs { driver: number[]; engine: number[]; running: boolean }

export interface MineStateDto {
  mode: string                    // 'per-pool'
  knownPools: string[]
  runningPools: string[]
  byPool: Record<string, PoolProcs>
  drivers: ProcessInfo[]
  engines: ProcessInfo[]
  anyRunning: boolean
  freeGB: number | null
  gbPerEngine: number
  canStartMore: number | null
  maxParallel: number | null
  defaultRounds: number
  roundsRange: [number, number]
  script: string
  note: string
}

export interface MineStartResp {
  ok: boolean
  started: { pool: string; pid: number; alive: boolean | null; cmd: string; log: string }[]
  skipped: { pool: string; why: string; pids: number[] }[]
  noGlobal?: boolean
  freeGB?: number | null
  note: string
}

export interface MineStopResp {
  ok: boolean
  scope: string
  killed: { pid: number; kind: string; pools: string[] | null; rc: number; out: string }[]
  stillRunning: { pid: number; kind: string; pools: string[] | null }[]
  note: string
}

// ---------------------------------------------------------------- 接口
export const api = {
  meta: () => get<MetaDto>('/meta'),
  status: (fresh = false) => get<StatusDto>(`/status${fresh ? '?fresh=true' : ''}`, 40000),
  libraries: () => get<{ libraries: LibraryDto[]; totalFactors: number }>('/library'),
  library: (pool: string) => get<LibraryDto>(`/library/${pool}`),
  selected: () => get<SelectedDto>('/selected'),
  stripBank: () => get<{ found: boolean; count: number; rows: Record<string, string>[] }>('/strip-bank'),
  poolObs: (pool: string, limit = 200) =>
    get<{ found: boolean; columns: string[]; rows: Record<string, string>[] }>(`/pool-obs/${pool}?limit=${limit}`),
  // ★ 挖掘控制（每池独立进程）
  mineState: () => get<MineStateDto>('/mine/state', 40000),
  mineStart: (pools: string[], rounds: number) =>
    post<MineStartResp>('/mine/start', { pools, rounds, noGlobal: true }),
  mineStop: (pool?: string) =>
    post<MineStopResp>('/mine/stop', pool ? { scope: 'pool', pool } : { scope: 'all' }),
  mineGlobal: () => post<{ ok: boolean; pid: number; alive: boolean | null; log: string; note: string }>(
    '/mine/global', {}, 60000),
}
