import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  api,
  type CurvesDto, type LibraryDto, type LibraryFactor, type MetaDto, type MineStateDto,
  type PoolStatus, type SelectedDto, type SelectedFactor, type StatusDto,
} from './api'

type TabKey = 'pools' | 'library' | 'selected' | 'process' | 'meta'

const fmt = (n: number | null | undefined) =>
  n === null || n === undefined ? '—' : n.toLocaleString('en-US')

const ago = (iso: string | null | undefined, nowMs: number) => {
  if (!iso) return '—'
  const t = new Date(iso.replace(' ', 'T')).getTime()
  if (Number.isNaN(t)) return iso
  const s = Math.max(0, Math.round((nowMs - t) / 1000))
  if (s < 60) return `${s} 秒前`
  if (s < 3600) return `${Math.round(s / 60)} 分钟前`
  if (s < 86400) return `${Math.round(s / 3600)} 小时前`
  return `${Math.round(s / 86400)} 天前`
}

export default function App() {
  const [status, setStatus] = useState<StatusDto | null>(null)
  const [meta, setMeta] = useState<MetaDto | null>(null)
  const [libs, setLibs] = useState<LibraryDto[]>([])
  const [selected, setSelected] = useState<SelectedDto | null>(null)
  const [tab, setTab] = useState<TabKey>('pools')
  const [pool, setPool] = useState('1000')
  const [auto, setAuto] = useState(true)
  const [interval, setIntervalSec] = useState(10)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [nowMs, setNowMs] = useState(Date.now())
  const [lastAt, setLastAt] = useState<string | null>(null)
  const busyRef = useRef(false)
  // ★ 挖掘控制
  const [mine, setMine] = useState<MineStateDto | null>(null)
  const [rounds, setRounds] = useState(50)
  // ★★★ 2026-09-16（用户之问「前端还没把并行切换加上是吧？」）：把 `run_tracks.py` **v1.4.0 就有**的
  //   「调度模式 + 面板共享」暴露出来。★ **默认 = 现状**（轮转 + 面板缓存关）⇒ 不碰这些控件时，
  //   发出的命令与改造前**逐字一致**（旧行为一行不改）✓
  // ★★ 2026-09-16：UI 上**只留"模式"一个开关**（用户要求）——
  //   · **并行数**：后端按可用内存**自动算**（"一键启动就全部五池，快爆就自动少一个池"）
  //   · **预算**：撤掉（实测它是"排队闸门"不是内存上限，改了没用 ✗）
  //   · **面板共享**：**默认常开**（无副作用：结果逐位相同、载入 28.6s→1.8s、内存更低；
  //      缓存失效时后端**自动降级为 off** 并在提示里说明 ⇒ 不需要用户操心）
  // ★★ 2026-09-16（用户："测试既然可以并行了，就干脆把轮转/并行按钮都隐藏了，先直接默认并行吧"）：
  //   ⇒ 模式按钮**撤掉**，看板一律走**并行**（`rotate` 仍保留在 CLI/API 里，随时能切回来）✓
  //   · 并行数：后端按可用内存自动算 · 面板共享：默认常开 · 预算：不暴露
  //   ⚠ "状态区显示的模式"仍以**真实进程命令行**为准：万一真有轮转调度器在跑（如从命令行起的），
  //     状态区会如实显示"轮转"，点启动会被后端 409 拦下并提示先全部停止 ✓
  const MODE: 'parallel' = 'parallel'
  const [mineBusy, setMineBusy] = useState(false)
  const [toast, setToast] = useState<{ kind: 'ok' | 'err' | 'info'; msg: string } | null>(null)
  // ★★★ 2026-09-16 修：**不用 `window.confirm`** ——
  //   它在 IDE 内置浏览器/部分环境里会被**阻止**（不弹窗、直接返回 false）
  //   ⇒ `if (!confirm(...)) return` 就变成"点了完全没反应" ✗（用户实测：
  //     后端日志里连 POST /api/mine/start 都没有 ⇒ 请求根本没发出去）
  //   ⇒ 当时改用**自定义弹窗**（React 组件）⇒ 任何环境都能用 ✓
  // ★★ 2026-09-16 再次修（用户要求）：**弹窗全部去掉** —— 点按钮直接执行、不再二次确认 ✓

  const loadAll = useCallback(async (fresh = false) => {
    if (busyRef.current) return
    busyRef.current = true
    setBusy(true)
    try {
      const [st, mt, lb, se, ms] = await Promise.all([
        api.status(fresh), api.meta(), api.libraries(), api.selected(), api.mineState(),
      ])
      setStatus(st); setMeta(mt); setLibs(lb.libraries); setSelected(se); setMine(ms)
      setRounds(r => (r === 50 ? ms.defaultRounds : r))
      setLastAt(new Date().toLocaleTimeString('zh-CN'))
      setErr(null)
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      busyRef.current = false
      setBusy(false)
    }
  }, [])

  // ---- 挖掘控制 ----
  const say = (kind: 'ok' | 'err' | 'info', msg: string) => {
    setToast({ kind, msg })
    window.setTimeout(() => setToast(t => (t && t.msg === msg ? null : t)), kind === 'err' ? 12000 : 6000)
  }

  // ★★★ 2026-09-16（用户要求：「把一键启动、停止等的弹窗提示都去掉，不用提示」）：
  //   **连自定义确认弹窗也去掉** ⇒ 点按钮**直接执行**，结果由顶部 toast 反馈 ✓
  //   ⚠ 原本弹窗里的说明（一键启动会清掉「停止」标记 / 当前代会作废 …）已移进**按钮的鼠标提示** ✓

  const doStart = useCallback(async (pools: string[]) => {
    setMineBusy(true)
    try {
      // ★ 只传"模式=并行"；并行数由后端按内存自动算、面板共享固定 use（缓存失效自动降级）✓
      const r = await api.mineStart(pools, rounds, { execMode: MODE, panelCache: 'use' })
      if (r.reused) {
        say('ok', `调度器已在运行（PID ${(r.schedulerPids ?? []).join(',')}），已更新设置：启用池 ${(r.enabled ?? []).join(',')}，${r.rounds} 轮（没有重复启动）`)
      } else {
        const st = r.started.map(x => `PID ${x.pid}`).join(' ') || '无'
        say('ok', `已启动调度器 ${st}，启用池：${(r.enabled ?? []).join(',')}，每池 ${r.rounds} 轮`)
      }
      await loadAll(true)
    } catch (e) {
      say('err', `启动失败：${e instanceof Error ? e.message : String(e)}`)
      await loadAll(true)
    } finally { setMineBusy(false) }
  }, [rounds, loadAll])

  const doStop = useCallback(async (pool?: string) => {
    setMineBusy(true)
    try {
      const r = await api.mineStop(pool)
      const k = r.killed.filter(x => x.rc === 0).map(x => `${x.kind}#${x.pid}`).join(', ')
      say(r.ok ? 'ok' : 'err',
        r.ok ? `已停止${pool ? `池 ${pool}（其他池不受影响）` : '全部'}，结束进程：${k || '无'}`
          + (r.tail ? `；已开始收尾审查（PID ${r.tail.pid}）` : '')
             : `有进程没停掉：${r.stillRunning.map(s => `${s.kind}#${s.pid}`).join(', ')}`)
      await loadAll(true)
    } catch (e) {
      say('err', `停止失败：${e instanceof Error ? e.message : String(e)}`)
      await loadAll(true)
    } finally { setMineBusy(false) }
  }, [loadAll])

  // 单独启动 / 恢复某个池（调度器不在时会自动重启）
  const doStartPool = useCallback(async (pool: string) => {
    setMineBusy(true)
    try {
      const r = await api.mineStartPool(pool)
      // ★ 2026-09-16（用户："停止一个池然后重新启动，怎么没马上开挖？"）：
      //   并行模式下**运行期动态加入**（不用等下一轮）⇒ 提示要分模式说清楚 ✓
      const _par = mine?.execMode === 'parallel'
      say('ok', r.restarted
        ? `调度器之前没在运行，已自动重启。池 ${pool} 已加入${_par ? '并行' : '轮转'}（当前启用：${r.enabled.join(',')}）`
        : (r.merged
          ? `池 ${pool} 已重新加入${_par ? '并行' : '轮转'}：${_par ? '马上就会起一个引擎（不用等下一轮）' : '下一轮轮到它'}`
          : `池 ${pool} 已重新加入${_par ? '并行' : '轮转'}`))
      await loadAll(true)
    } catch (e) {
      say('err', `启动本池失败：${e instanceof Error ? e.message : String(e)}`)
      await loadAll(true)
    } finally { setMineBusy(false) }
  }, [loadAll])

  useEffect(() => { loadAll() }, [loadAll])
  useEffect(() => {
    const t = window.setInterval(() => setNowMs(Date.now()), 1000)
    return () => window.clearInterval(t)
  }, [])
  useEffect(() => {
    if (!auto) return
    const t = window.setInterval(() => { loadAll() }, Math.max(3, interval) * 1000)
    return () => window.clearInterval(t)
  }, [auto, interval, loadAll])

  const curLib = useMemo(() => libs.find(l => l.pool === pool) ?? null, [libs, pool])
  const runColor = status?.anyRunning ? 'var(--ok)' : 'var(--idle)'

  return (
    <div className="wrap">
      <header className="top">
        <div className="brand">
          <span className="logo" style={{ background: runColor }} />
          <div>
            <h1>Loop 挖掘看板</h1>
            <div className="sub">
              {status?.anyRunning
                ? <>引擎 <b style={{ color: 'var(--ok)' }}>正在挖掘</b> — {status.summary.runningPoolCount} 个池在跑</>
                : <>引擎 <b style={{ color: 'var(--idle)' }}>空闲</b>（无挖掘进程）</>}
              {lastAt && <> · 更新于 {lastAt}</>}
            </div>
          </div>
        </div>
        <div className="ctrls">
          {/* 顶部状态条：空闲 / 挖掘中 / 收尾审查中 */}
          <span className={`phase ${mine?.phase ?? 'idle'}`} title={
            `当前状态：${mine?.phaseLabel ?? '—'}\n` +
            (mine?.curText ? `正在跑：${mine.curText}\n` : '') +
            (mine?.roundText ? `${mine.roundText}，共 ${mine?.rounds ?? '?'} 轮\n` : '') +
            `参与的池：${(mine?.enabled ?? []).join(',') || '无'}\n` +
            (mine?.updated ? `状态更新于 ${mine.updated}` : '')}>
            <i className="pdot" />
            <b>{mine?.phaseLabel ?? '—'}</b>
            {mine?.curText && <em>{mine.curText}</em>}
            {mine?.roundText && <small>{mine.roundText}/{mine?.rounds ?? '?'}</small>}
          </span>
          {/* ★★ 2026-09-16（用户："顶上 19.4 GB 5 池已配置这里的鼠标提示还有引号…干脆把这里的提示
              全部删掉"）⇒ **那个 tooltip 直接去掉**（`memNote` 后端仍在，只是不再挂在悬停上）✓
              —— 该说明（并行数怎么算、面板共享省多少内存）属于"配置/口径"信息，
                 挂在内存数字上纯属噪音；要查口径请看「配置/口径」页 ✓ */}
          <span className="res">
            <b className={mine && mine.freeGB !== null && mine.freeGB < 6 ? 'warn' : ''}>
              {mine?.freeGB !== null && mine?.freeGB !== undefined ? `${mine.freeGB} GB` : '—'}
            </b>
            {/* ★ 当前**实际**在跑的模式（以进程命令行为准，不是 UI 上选的那个） */}
            {mine?.running && (
              <em className="mode">
                {/* ★ 并行数是**自动**的 ⇒ 标出来（否则用户看到 ×1 会以为"只能跑一个" ✗） */}
                {mine.execMode === 'parallel'
                  ? `并行×${mine.maxParallel}${mine.autoParallel ? '（自动）' : ''}` : '轮转'}
                {mine.panelCache !== 'off' ? ' · 共享' : ''}
              </em>
            )}
            {/* 区分“正在轮转”与“只是配置了但调度器没跑”（★ 文字缩短，免得把顶栏挤出一条滚动条 ✗） */}
            <small>{mine?.running
              ? `${(mine?.runningPools ?? []).length}/${(mine?.enabled ?? []).length} 池在跑`
              : ((mine?.enabled ?? []).length
                ? `${(mine?.enabled ?? []).length} 池已配置`
                : '未配置')}</small>
          </span>
          <span className="rounds" title={`每个池要跑的轮数，范围 1~${mine?.roundsRange?.[1] ?? 200}。一轮 = 每个参与的池各跑 1 代`}>
            轮数
            <input type="number" min={mine?.roundsRange?.[0] ?? 1} max={mine?.roundsRange?.[1] ?? 200}
                   value={rounds} disabled={mineBusy}
                   onChange={e => setRounds(Math.max(1, Math.min(200, Number(e.target.value) || 1)))} />
          </span>
          {/* ★★★ 2026-09-16（用户："把轮转/并行按钮都隐藏了，先直接默认并行吧"）：
              模式按钮**撤掉** —— 看板一律并行（并行数按内存自动算、面板共享默认开、预算不暴露）✓
              ⚠ 想回到"轮转"：CLI/API 仍支持（`--exec_mode=rotate`），随时能再放出来 ✓ */}
          <button className="btn start" disabled={mineBusy || !!mine?.running} onClick={() => doStart([])}
                  title={mine?.running
                    ? `调度器已经在运行了（${mine.execMode === 'parallel' ? `并行×${mine.maxParallel} · 共享` : '轮转 · 共享'}）。` +
                      '要改模式或并行设置的话，先点全部停止再启动（那些是启动参数，不能热改）'
                    : '启动并行调度器（并行数按可用内存自动定 · 面板共享），让所有池参与。' +
                      '之前单独停止过的池也会重新加入；已经在跑的话就地更新设置'}>
            {mine?.running ? '已在运行' : (mineBusy ? '处理中…' : '一键启动全部')}
          </button>
          <button className="btn stop" disabled={mineBusy || !mine?.running} onClick={() => doStop()}
                  title={mine?.running
                    ? '全部停止：结束当前那一代，然后自动做收尾审查再退出。正在跑的那一代会作废，下次重跑'
                    : '当前没有在运行，无需停止'}>
            全部停止
          </button>
          {/* 「收尾审查」按钮已按用户要求隐藏（后端 /api/mine/global 仍在）：
             现在每轮结束会自动收尾，「全部停止」后也会自动收尾，无需手动点 */}
          <button onClick={() => loadAll(true)} disabled={busy} className="btn">
            {busy ? '刷新中…' : '立即刷新'}
          </button>
          <label className="chk">
            <input type="checkbox" checked={auto} onChange={e => setAuto(e.target.checked)} />
            自动
          </label>
          <select value={interval} onChange={e => setIntervalSec(Number(e.target.value))} className="sel">
            {[5, 10, 30, 60].map(s => <option key={s} value={s}>{s}s</option>)}
          </select>
        </div>
      </header>

      {toast && (
        <div className={toast.kind === 'err' ? 'err' : toast.kind === 'ok' ? 'ok' : 'info'}>
          {toast.kind === 'err' ? '⚠ ' : toast.kind === 'ok' ? '✓ ' : 'ℹ '}{toast.msg}
          <button className="x" onClick={() => setToast(null)}>×</button>
        </div>
      )}
      {err && <div className="err">⚠ {err}</div>}

      {/* ★ 2026-09-16 用户要求：**不再有确认弹窗** ⇒ 启动/停止点一下就执行，结果看上面的 toast ✓ */}

      {status && (
        <section className="summary">
          <Kpi label="在跑的池" value={`${status.summary.runningPoolCount} / ${status.summary.poolCount}`}
               tone={status.anyRunning ? 'ok' : 'idle'} />
          <Kpi label="入库因子合计" value={fmt(status.summary.totalLibrary)} tone="indigo" />
          <Kpi label="已测候选合计" value={fmt(status.summary.totalTested)} tone="sky" />
          <Kpi label="L2 候选流水" value={fmt(status.summary.totalArchiveRows)} tone="amber" />
          <Kpi label="相关进程" value={String(status.processes.length)} tone="slate" />
        </section>
      )}

      <nav className="tabs">
        {([['pools', '池运行状态'], ['library', '因子库'], ['selected', '精选池'],
           ['process', '进程'], ['meta', '配置/口径']] as [TabKey, string][]).map(([k, t]) => (
          <button key={k} className={tab === k ? 'tab on' : 'tab'} onClick={() => setTab(k)}>{t}</button>
        ))}
      </nav>

      {/* ★★★★★ 2026-09-16 修（用户报「把全A停了再启动，剩下的等候轮转的池子都给取消掉了」）：
          池卡片的「启动本池」原来接的是 `doStart([p.key])` ⇒ 走 `/api/mine/start`（**整体启动接口**）
          ⇒ 后端 `start(['all'])` 会把 `enabled` **改写为 `['all']`** ⇒ **其余 4 个池全被移出轮转** ✗✗
          ⇒ 正确语义 = 「**只把这一池加回轮转**」= `POST /api/mine/start_pool` ⇒ 只动该池 ✓
          ⚠ 我在 v1.3.9 写了 `doStartPool()` 却**忘了接到这里**（成了死代码）✗
            —— 而当时的"端到端测试"是**直接打 API** ⇒ **没覆盖到前端接线** ✗（这是漏洞）
          ⇒ 已加 `tools/_test_frontend_wiring.py` 进回归，专门盯这类"写了没接" ✗ */}
      {tab === 'pools' && status && (
        <section className="cards">
          {status.pools.map(p => (
            <PoolCard key={p.key} p={p} nowMs={nowMs} mine={mine} busy={mineBusy}
                      onStart={() => doStartPool(p.key)} onStop={() => doStop(p.key)} />
          ))}
        </section>
      )}

      {tab === 'library' && (
        <section className="panel">
          <div className="poolpick">
            {libs.map(l => (
              <button key={l.pool} className={pool === l.pool ? 'pill on' : 'pill'}
                      onClick={() => setPool(l.pool)}>
                {l.label}
                <span className="cnt">{l.stateBank ?? l.count}</span>
              </button>
            ))}
          </div>
          {curLib && <LibraryTable lib={curLib} />}
        </section>
      )}

      {tab === 'selected' && selected && <SelectedPanel s={selected} />}

      {tab === 'process' && (
        <section className="panel">
          {status?.processes.length ? (
            <table className="tbl">
              <thead><tr><th>PID</th><th>类型</th><th>池</th><th>启动</th><th>内存</th><th>脚本</th></tr></thead>
              <tbody>
                {status.processes.map(p => (
                  <tr key={p.pid}>
                    <td className="mono">{p.pid}</td>
                    <td><Tag kind={p.kind} /></td>
                    <td>{p.pools.length ? p.pools.join(', ') : '—'}</td>
                    <td className="mono">{p.start}</td>
                    <td className="mono">{p.memMB} MB</td>
                    <td className="mono small">{p.script}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : <div className="empty">当前无相关 python 进程{status?.processError ? `（查询报错：${status.processError}）` : ''}</div>}
        </section>
      )}

      {tab === 'meta' && meta && <MetaPanel m={meta} />}

      <footer className="foot">
        <span>Loop 挖掘看板 · 项目版本 <b>v{meta?.version ?? '?'}</b></span>
        <span>·</span>
        <span>版本来自 <code>VERSION</code></span>
        <span>·</span>
        <span>端口来自 <code>dashboard/config.json</code>（各改一处）</span>
      </footer>
    </div>
  )
}

function Kpi({ label, value, tone }: { label: string; value: string; tone: string }) {
  return (
    <div className={`kpi t-${tone}`}>
      <div className="kpi-v">{value}</div>
      <div className="kpi-l">{label}</div>
    </div>
  )
}

function Tag({ kind }: { kind: string }) {
  const map: Record<string, [string, string]> = {
    driver: ['调度 run_tracks', '#6366f1'],
    engine: ['引擎 loop_engine', '#10b981'],
    watcher: ['守望 loop_watch', '#f59e0b'],
    other: ['其它', '#94a3b8'],
  }
  const [t, c] = map[kind] ?? map.other
  return <span className="tag" style={{ background: c + '22', color: c, borderColor: c + '55' }}>{t}</span>
}

function PoolCard({ p, nowMs, mine, busy, onStart, onStop }:
  { p: PoolStatus; nowMs: number; mine: MineStateDto | null; busy: boolean;
    onStart: () => void; onStop: () => void }) {
  const st = p.state
  const slot = mine?.byPool?.[p.key]
  const mining = !!slot?.mining                     // ★ 正在跑它这一代
  // ★★★ 2026-09-16 修 BUG F：`inRotation` **必须**加"调度器在跑"这个前提！
  //   原写法只看 `enabled` ⇒ 调度器停止后（`enabled` 仍保留上次的配置）⇒ 卡片**谎报"轮转中"**
  //   且「启动本池」被禁用 ⇒ 用户看到"上写空闲、卡片却写已参与轮转"的**自相矛盾** ✗
  //   ⇒ 语义拆分：`configured` = "已配置参与轮转"（意图）；`inRotation` = "此刻真的在轮转"（在跑）✓
  const schedRunning = !!mine?.running
  const configured = !!slot?.enabled && !slot?.stopped
  // ★ `inRotation` = **此刻真的在轮转**（调度器在跑 + 该池在启用集合且未被剔除）
  const inRotation = schedRunning && configured
  // ★★ `mining && !inRotation` = **在跑但已移出轮转**（它那一代还没结束，跑完就会停）
  const leaving = mining && !inRotation
  const stopped = !!slot?.stopped || (slot != null && !slot.enabled)
  const isRunning = mining || p.running
  const cls = mining ? 'card run' : (inRotation ? 'card armed' : 'card')
  // ★ 2026-09-16（用户："怎么它又加入轮转、没有马上开挖？"）：**文案要跟实际模式一致**
  //   —— 并行模式下说"轮转中/加入轮转"会让人以为"要排队等"，而实际是**马上就会起引擎** ✗
  const qword = mine?.execMode === 'parallel' ? '并行' : '轮转'
  const badge = mining ? (leaving ? '运行中·已移出' : '挖掘中')
    : (inRotation ? (qword + '中')
      : (configured ? '待启动' : (stopped ? '已停止' : '空闲')))
  const dotColor = mining ? 'var(--ok)'
    : (inRotation ? 'var(--sky)' : (configured ? 'var(--amber)' : 'var(--idle)'))
  return (
    <div className={cls}>
      <div className="card-h">
        <span className="dot" style={{ background: dotColor }} />
        <b>{p.label}</b>
        <span className="pid">{p.key === 'all' ? '全A' : p.key}</span>
        <span className="state">{badge}</span>
      </div>
      <div className="grid">
        <Field k="当前库（权威）" v={fmt(p.librarySize)} strong />
        <Field k="已测候选" v={fmt(p.tested)} />
        <Field k="跑过代数" v={fmt(p.journal.gens)} />
        <Field k="最新代" v={p.journal.maxGen === null ? '—' : `gen ${p.journal.maxGen}`} />
        <Field k="L2 候选流水" v={fmt(p.archive.rows)} />
        <Field k="其中通过" v={fmt(p.archive.passed)} />
        <Field k="冻结" v={fmt(st?.frozen_n)} />
        <Field k="失败库" v={fmt(st?.fail_lib_n)} />
      </div>
      {/* ★★★★ 2026-09-16 按钮规则定稿（**两按钮完全互补、无重叠**）：
          · 启动本池 ⇒ 可点条件 = **"不在轮转里"**（`!inRotation`）——
            已经在轮转里就无需启动 ✓；★ "在跑但已移出轮转"（`leaving`）**可点** ⇒
            点它 = 把该池**重新加入**轮转，让它继续跑 ✓（合理的救回操作）
          · 停止本池 ⇒ 可点条件 = **"在轮转里 或 正在跑"**（`inRotation || mining`）——
            两者都没有 ⇒ 才灰 ✓（"剔除"是状态变更、**随时可做**；正在跑的顺带结束当前代）✓
      */}
      <div className="card-a">
        <button className="btn start sm" disabled={busy || inRotation} onClick={onStart}
                title={inRotation
                  ? (qword === '并行'
                    ? `${p.label} 已在并行队列里（内存够就会起引擎；没在跑说明在等空位）`
                    : `${p.label} 已在轮转里（下一轮就会轮到它）`)
                  : (leaving
                    ? `${p.label} 正在跑但已移出${qword}。点它 = 重新加入，让它继续参与`
                    : (qword === '并行'
                      ? `把 ${p.label} 加入并行：马上就会起一个引擎（不用等下一轮）。如果调度器没在运行，会自动启动`
                      : `把 ${p.label} 加入轮转。如果调度器没在运行，会自动启动`))}>
          {inRotation ? `已参与${qword}` : (leaving ? `重新加入${qword}` : '启动本池')}
        </button>
        <button className="btn stop sm" disabled={busy || (!inRotation && !mining)} onClick={onStop}
                title={(!inRotation && !mining)
                  ? `${p.label} 既不参与${qword}也没在跑`
                  : (mining
                    ? (leaving
                      ? `${p.label} 已移出${qword}，正在跑完当前这一代（跑完就会停）。点它可立即结束`
                      : `停止 ${p.label}：从${qword}中移除，并结束它当前那一代。其他池不受影响`)
                    : `把 ${p.label} 从${qword}中移除（它当前没在跑，所以只影响后续轮次）`)}>
          停止本池
        </button>
      </div>
      <div className="card-f">
        <span>journal {ago(p.journal.mtime, nowMs)}</span>
        {slot && slot.engine.length > 0 && <span className="mono">engine {slot.engine.join(',')}</span>}
      </div>
    </div>
  )
}

function Field({ k, v, strong }: { k: string; v: string; strong?: boolean }) {
  return (
    <div className="field">
      <span className="fk">{k}</span>
      <span className={strong ? 'fv strong' : 'fv'}>{v}</span>
    </div>
  )
}

function LibraryTable({ lib }: { lib: LibraryDto }) {
  const c = lib.caliber
  const [sel, setSel] = useState<LibraryFactor | null>(null)
  const known = lib.inBankKnown === true
  const nIn = known ? lib.factors.filter(f => f.inBank === true).length : null
  const stale = !known && (lib.metricsMeasured ?? 0) > 0
  return (
    <div className="libwrap">
      <div className="caliber">
        <b>口径说明</b>（这里三个数字不一样，以第一个为准）：
        <ul>
          <li><b>当前有效库 = {fmt(lib.stateBank)}</b> —— <span>权威：引擎实际在用的对照集，来自 <code>loop_state_{lib.pool}.pkl</code></span></li>
          <li>本表行数 = {fmt(lib.count)} —— <span>累计入库编号，该文件只增不改{known ? <>（<b>其中 {nIn} 个仍在当前库</b>）</> : null}</span></li>
          <li>文件声明 = {fmt(lib.declaredCount)} —— <span>引擎同步的快照，可能落后</span></li>
        </ul>
        <div className="note">
          行数比当前有效库多的原因：编号是累计的，而因子会被移出库（比如剥风格后发现它只是纯风格因子）。
          带历史标记的行就是已不在当前库的编号；点编号可以看完整公式和各项指标。
        </div>
        {(lib.orphans ?? []).length > 0 && (
          <div className="note">
            另有 {(lib.orphans ?? []).length} 个因子在当前库里，但库文档没有它们的编号（当年同步漏记的历史缺口）：
            <ul className="orph">
              {(lib.orphans ?? []).map(o => (
                <li key={o.name}>
                  <code>{o.name}</code> · {o.expr || '（表达式待补）'}
                  {o.ann_ex !== null && o.ann_ex !== undefined ? ` · 超额年化 ${(o.ann_ex * 100).toFixed(2)}%` : ''}
                </li>
              ))}
            </ul>
            所以有效库比本表里在库的行数多 {lib.orphans?.length} 个。
          </div>
        )}
        {stale && (
          <div className="note">
            指标表还没跑完（本池 {lib.metricsMeasured} / 有效库 {fmt(lib.stateBank)} 条），
            所以暂时不标历史。跑完 python tools/factor_metrics.py 即可对齐。
          </div>
        )}
        {!known && !stale && (
          <div className="note">
            还没有指标表，所以暂不知道哪些编号仍在当前库（也不会标历史）。
            跑一次 python tools/factor_metrics.py 生成后即可。
          </div>
        )}
      </div>
      <table className="tbl">
        <thead><tr><th>编号</th><th>入库代数</th><th>家族</th><th>一句话（公式可能被截断）</th><th>状态</th><th>详情</th></tr></thead>
        <tbody>
          {lib.factors.map((f, i) => (
            <tr key={`${f.code}-${i}`} className={f.inBank === false ? 'outbank' : ''}>
              <td className="mono strong">
                <button className="fcode" onClick={() => setSel(f)}
                        title={f.inBank === false
                          ? '该编号已不在当前有效库，只剩历史编号（文件只增不改）。点开仍能看到公式与指标'
                          : '点开看完整公式（可复制）、池标签与各项费后指标'}>
                  {f.code}{f.inBank === false ? ' · 历史' : ''}
                </button>
              </td>
              <td className="mono">{f.gen}</td>
              <td>{f.family}</td>
              <td className="sum">{f.summary}</td>
              <td><span className={f.inBank === false ? 'status hist' : 'status'}>{f.status}</span></td>
              <td><button className="btn sm" onClick={() => setSel(f)}>详情</button></td>
            </tr>
          ))}
        </tbody>
      </table>
      {!lib.factors.length && <div className="empty">（本池无表格数据）</div>}
      {sel && <FactorDetail f={sel} metricsInfo={lib.metricsInfo} metricsMtime={lib.metricsMtime}
                            onClose={() => setSel(null)} />}
    </div>
  )
}

/** 指标定义：`[字段, 名称, 类型]`。
 *
 * ★★ 2026-09-16 重新分组（用户指出「组合自身最大回撤 −34.7% 与日频 −13.1% 并列，后者不可能更浅」）：
 *   真因是**口径** —— `dd_d/calmar_d/sharpe_d` 一直是「**超额**」口径的日频（与 `dd/calmar/sharpe` 配对），
 *   却被放在「组合自身」旁边 ⇒ 看起来像同一口径的两个数（其实恒等式是 `dd_d <= dd`，**不是** `dd_d <= dd_top`）✗
 *   ⇒ 现在**按「超额 / 组合自身」× 「期频 / 日频」四个格子摆**，同格才能比 ✓
 */
const METRIC_GROUPS: Array<[string, Array<[string, string, 'pct' | 'num' | 'int']>]> = [
  ['超额口径 · 期频打点（组合 − 池内等权基准）', [
    ['ann_ex', '超额年化', 'pct'], ['dd', '超额最大回撤', 'pct'],
    ['calmar', '超额卡玛', 'num'], ['sharpe', '超额夏普', 'num'],
  ]],
  ['超额口径 · 日频打点（同一策略逐日 mark）', [
    // ★ 2026-09-16（用户要求）：日频也补上**年化** —— 它与期频**同值**（锚定后终值/年数一致，
    //   引擎里就是这么定义的：`calmar_d = ann_ex/|dd_d|`）⇒ 复制过来让**四格都能上下对齐** ✓
    ['ann_ex', '超额年化（同期频）', 'pct'], ['dd_d', '超额最大回撤', 'pct'],
    ['calmar_d', '超额卡玛', 'num'], ['sharpe_d', '超额夏普', 'num'],
  ]],
  ['组合自身口径 · 期频打点（Top10% 等权）', [
    ['ann_top', '年化', 'pct'], ['dd_top', '最大回撤', 'pct'],
    ['calmar_top', '卡玛', 'num'], ['sharpe_top', '夏普', 'num'],
  ]],
  ['组合自身口径 · 日频打点（同一策略逐日 mark）', [
    ['ann_top', '年化（同期频）', 'pct'], ['dd_top_d', '最大回撤', 'pct'],
    ['calmar_top_d', '卡玛', 'num'], ['sharpe_top_d', '夏普', 'num'],
  ]],
  ['其他', [
    ['last_yr', '最近一年超额', 'pct'], ['turn', '单期换手', 'pct'],
    ['neg_yr', '负年个数（年度超额 ≤0）', 'int'], ['ic', 'IC', 'num'], ['ic_ir', 'IC_IR', 'num'],
  ]],
]

const fmtM = (v: number | null | undefined, kind: 'pct' | 'num' | 'int') => {
  if (v === null || v === undefined || Number.isNaN(v)) return '—'
  if (kind === 'pct') return `${(v * 100).toFixed(2)}%`
  if (kind === 'int') return String(v)
  return v.toFixed(3)
}

/** 详情面板能接受的"最小因子形状" —— 库表与精选池卡片都能喂给它（同一套展示 ✓） */
type FactorLike = Pick<LibraryFactor, 'code' | 'expr' | 'detail' | 'metrics'> & {
  family?: string
  summary?: string
  pool?: string
  /** ★ 三态：true 在库 / false 已移出 / null|undefined 未知（指标表不完整） */
  inBank?: boolean | null
}

const fmtD8 = (d: number) => `${String(d).slice(0, 4)}-${String(d).slice(4, 6)}-${String(d).slice(6, 8)}`

// ================================================================ 曲线（SVG，零依赖）
// ★ 2026-09-16（用户要求：指标下面加曲线图）：数据**离线预算**（`tools/factor_curves.py`），
//   这里只负责画 ⇒ 打开详情 = 读一个几十 KB 的 JSON + 画 SVG，**对性能没有影响** ✓
//   ★ 用**手写 SVG** 而不是引图表库：本项目前端零依赖（只有 react/react-dom），
//     引库要多几十万字节 + 多一个升级面；这些图（折线/面积）手写 60 行足够 ✓
const CPAL = ['#6366f1', '#22d3ee', '#f59e0b', '#34d399', '#f472b6',
              '#a78bfa', '#facc15', '#38bdf8', '#fb7185', '#4ade80']
const dLab = (d: number) => `${String(d).slice(2, 4)}-${String(d).slice(4, 6)}`

type ChSeries = { label: string; color: string; data: (number | null)[]; dashed?: boolean }

function Chart({ series, dates, height = 132, kind = 'line', yFmt, zero = false }:
  { series: ChSeries[]; dates: number[]; height?: number
    kind?: 'line' | 'area'; yFmt?: (v: number) => string; zero?: boolean }) {
  // ★★ 2026-09-16（用户要求）：「所有的图，点图例要能**显隐曲线**」
  //   ⇒ 图例项变成可点按钮；隐藏的曲线**同时退出 Y 轴取值范围**（否则坐标轴被藏着的那条撑住，
  //     等于"藏了也没用" ✗）· 换因子（图例变了）时**自动重置**显隐状态 ✓
  const [off, setOff] = useState<Record<number, boolean>>({})
  const sig = series.map(s => s.label).join('|')
  useEffect(() => { setOff({}) }, [sig])
  const vis = series.map((s, i) => ({ s, i })).filter(x => !off[x.i])

  const W = 720, H = height, PL = 48, PR = 10, PT = 8, PB = 16
  const vals: number[] = []
  vis.forEach(x => x.s.data.forEach(v => { if (v !== null && Number.isFinite(v)) vals.push(v) }))
  if (!vals.length || !dates.length) {
    return (
      <div className="ch">
        <div className="ch-empty">
          {series.length && !vis.length ? '（曲线已全部隐藏 —— 点下方图例恢复）' : '（无数据）'}
        </div>
        {series.length > 0 && (
          <div className="ch-lg">
            {series.map((s, i) => (
              <button key={i} className={`ch-lgbtn${off[i] ? ' off' : ''}`}
                      onClick={() => setOff(o => ({ ...o, [i]: !o[i] }))}
                      title="点击显示 / 隐藏这条曲线">
                <i style={{ background: s.color }} />{s.label}
              </button>
            ))}
          </div>
        )}
      </div>
    )
  }
  let lo = Math.min(...vals), hi = Math.max(...vals)
  if (zero) { lo = Math.min(lo, 0); hi = Math.max(hi, 0) }
  const span = (hi - lo) || Math.abs(hi || 1) * 0.2
  lo -= span * 0.06; hi += span * 0.06
  const n = dates.length
  const X = (i: number) => PL + (W - PL - PR) * (n <= 1 ? 0.5 : i / (n - 1))
  const Y = (v: number) => PT + (H - PT - PB) * (1 - (v - lo) / (hi - lo || 1))
  const fmt = yFmt ?? ((v: number) => v.toFixed(2))
  const yticks = [0, 0.25, 0.5, 0.75, 1].map(t => lo + (hi - lo) * t)
  const xi = [0, Math.floor((n - 1) / 2), n - 1].filter((v, i, a) => a.indexOf(v) === i)
  return (
    <div className="ch">
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img">
        {yticks.map((tv, i) => (
          <g key={`y${i}`}>
            <line x1={PL} y1={Y(tv)} x2={W - PR} y2={Y(tv)} stroke="#1e2846" strokeWidth="1" />
            <text x={PL - 6} y={Y(tv) + 3.5} fontSize="10" fill="#8b9ac0" textAnchor="end">{fmt(tv)}</text>
          </g>
        ))}
        {zero && lo < 0 && hi > 0 && (
          <line x1={PL} y1={Y(0)} x2={W - PR} y2={Y(0)} stroke="#4b5b83" strokeDasharray="3 3" />
        )}
        {vis.map(({ s, i: oi }) => {
          let d = '', pen = false
          s.data.forEach((v, i) => {
            if (v === null || !Number.isFinite(v)) { pen = false; return }
            d += `${pen ? 'L' : 'M'}${X(i).toFixed(1)},${Y(v).toFixed(1)}`
            pen = true
          })
          if (!d) return null
          // 面积图固定在**第一条**（原始序号 0）那条上；它被隐藏时其余只画线 ✓
          if (kind === 'area' && oi === 0) {
            return <path key={`s${oi}`} d={`${d}L${X(n - 1).toFixed(1)},${Y(0).toFixed(1)}` +
                                         `L${X(0).toFixed(1)},${Y(0).toFixed(1)}Z`}
                         fill={s.color + '2e'} stroke={s.color} strokeWidth="1.2" />
          }
          return <path key={`s${oi}`} d={d} fill="none" stroke={s.color} strokeWidth="1.6"
                       strokeDasharray={s.dashed ? '4 3' : undefined} />
        })}
        {xi.map(i => (
          <text key={`x${i}`} x={X(i)} y={H - 4} fontSize="10" fill="#8b9ac0"
                textAnchor={i === 0 ? 'start' : (i === n - 1 ? 'end' : 'middle')}>
            {dLab(dates[i])}
          </text>
        ))}
      </svg>
      <div className="ch-lg">
        {series.map((s, i) => (
          <button key={i} className={`ch-lgbtn${off[i] ? ' off' : ''}`}
                  onClick={() => setOff(o => ({ ...o, [i]: !o[i] }))}
                  title={off[i] ? '点击显示这条曲线' : '点击隐藏这条曲线'}>
            <i style={{ background: s.color }} />{s.label}
          </button>
        ))}
      </div>
    </div>
  )
}

const fmtN3 = (v: number | null | undefined) =>
  v === null || v === undefined || Number.isNaN(v) ? '—' : v.toFixed(3)

/** ★★ 横向条形图（风格相关性用）—— 2026-09-16
 *  · 每行两根：上=**原始**、下=**剥离后**（剥总市值+行业）；0 在中间，左负右正
 *  · `domain` 给了就固定值域（风格相关性固定 ±1 ⇒ **跨因子可比** ✓）；不给则按数据自适应（行业用）
 *  · 图例可点（与折线图同约定） */
type BarRow = { label: string; v1: number | null; v2?: number | null }

function BarChart({ rows, rowH = 15, domain, fmt, tag2 = '剥后' }:
  { rows: BarRow[]; rowH?: number; domain?: number; fmt?: (v: number) => string; tag2?: string }) {
  const [hide, setHide] = useState<{ a: boolean; b: boolean }>({ a: false, b: false })
  const sig = rows.map(r => r.label).join('|')
  useEffect(() => { setHide({ a: false, b: false }) }, [sig])
  const W = 720, LX = 112, RX = 104, gap = 5
  const vs: number[] = []
  rows.forEach(r => {
    if (!hide.a && r.v1 !== null && Number.isFinite(r.v1)) vs.push(r.v1)
    if (!hide.b && r.v2 !== undefined && r.v2 !== null && Number.isFinite(r.v2)) vs.push(r.v2)
  })
  if (!rows.length || !vs.length) return <div className="ch-note">（无数据）</div>
  const mx = domain ?? Math.max(0.05, Math.max(...vs.map(Math.abs)) * 1.15)
  const H = rows.length * (rowH + gap) + 10
  const X = (v: number) => LX + (W - LX - RX) * (v + mx) / (2 * mx)
  const fv = fmt ?? ((v: number) => v.toFixed(2))
  const bar = (v: number | null | undefined, y: number, h: number, color: string) => {
    if (v === null || v === undefined || !Number.isFinite(v)) return null
    const x0 = X(0), x1 = X(v)
    return <rect x={Math.min(x0, x1)} y={y} width={Math.max(1, Math.abs(x1 - x0))}
                 height={h} fill={color} rx="1.5" />
  }
  return (
    <div className="ch">
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img">
        <line x1={X(0)} y1={2} x2={X(0)} y2={H - 6} stroke="#4b5b83" strokeWidth="1" />
        <line x1={X(-mx)} y1={2} x2={X(-mx)} y2={H - 6} stroke="#1e2846" />
        <line x1={X(mx)} y1={2} x2={X(mx)} y2={H - 6} stroke="#1e2846" />
        {rows.map((r, i) => {
          const y = i * (rowH + gap) + 2
          const hh = Math.max(3, (rowH - 2) / 2)
          return (
            <g key={i}>
              <text x={LX - 6} y={y + rowH / 2 + 3} fontSize="10.5" fill="#c8d3ee"
                    textAnchor="end">{r.label}</text>
              {!hide.a && bar(r.v1, y - 0.5, hh, CPAL[0])}
              {!hide.b && bar(r.v2, y + hh + 0.5, hh, CPAL[2])}
              <text x={W - RX + 6} y={y + rowH / 2 + 3} fontSize="9.5" fill="#8b9ac0">
                {fv(r.v1 ?? NaN)}{r.v2 !== undefined && r.v2 !== null ? ` / ${fv(r.v2)}` : ''}
              </text>
            </g>
          )
        })}
      </svg>
      <div className="ch-lg">
        <button className={`ch-lgbtn${hide.a ? ' off' : ''}`}
                onClick={() => setHide(o => ({ ...o, a: !o.a }))}
                title="点击隐藏或显示原始这一根">
          <i style={{ background: CPAL[0] }} />原始
        </button>
        <button className={`ch-lgbtn${hide.b ? ' off' : ''}`}
                onClick={() => setHide(o => ({ ...o, b: !o.b }))}
                title="点击隐藏或显示剥离后这一根">
          <i style={{ background: CPAL[2] }} />{tag2}（剥总市值+行业）
        </button>
        <span className="ch-lg-hint">右侧数字：原始 / 剥后</span>
      </div>
    </div>
  )
}

/** 风格名 → 中文（Barra 11 + 自有 4） */
const STYLE_LABEL: Record<string, string> = {
  lncap: '对数总市值', lnamt: '对数成交额', lntr: '对数换手率', lnpx: '对数股价',
  barra_size: '规模 size', barra_non_linear_size: '非线性规模', barra_momentum: '动量',
  barra_liquidity: '流动性', barra_book_to_price: '账面市值比', barra_leverage: '杠杆',
  barra_growth: '成长 growth', barra_earnings_yield: '盈利收益率', barra_beta: 'Beta',
  barra_residual_volatility: '残差波动率', barra_comovement: '共动性',
}
const styleName = (s: string) => STYLE_LABEL[s] ?? s.replace('barra_', '')

/** 累计和（跳过 null；前端现算，不需要后端多存一列） */
const cumsum = (a: (number | null)[]): (number | null)[] => {
  let s = 0
  return a.map(v => {
    if (v === null || !Number.isFinite(v)) return null
    s += v
    return s
  })
}

// ⚠ 类型断言（`as Record<string,string>`）**不能写在 JSX 属性里的内联对象中** ——
//   TSX 解析器会把 `<string, string>` 当 JSX 标签 ⇒ 一堆莫名其妙的语法错 ✗
//   ⇒ 提到模块级常量（2026-09-16 实测踩到）
const STRIP_LABEL: Record<string, string> =
  { raw: '原', lncap: '剥市值', lnamt: '剥成交额', both: '剥两者',
    floatcap: '剥流通市值', caplimit: '剥总市值+限售' }

/** 详情页图表区：打开时**才**拉曲线（离线预算好的），拉到前显示占位 ✓ */
function FactorCharts({ name, pool }: { name: string; pool?: string }) {
  const [c, setC] = useState<CurvesDto | null>(null)
  const [err, setErr] = useState<string | null>(null)
  useEffect(() => {
    let dead = false
    setC(null); setErr(null)
    api.curves(pool || 'all', name)
      .then(d => { if (!dead) setC(d) })
      .catch(e => { if (!dead) setErr(e instanceof Error ? e.message : String(e)) })
    return () => { dead = true }
  }, [name, pool])
  if (err) return <div className="ch-note">曲线读取失败：{err}</div>
  if (!c) return <div className="ch-note">曲线加载中…</div>
  if (!c.found) return <div className="ch-note">暂无曲线数据。{c.hint}</div>
  const dl = c.daily, pd = c.period, st = c.strip, sp = c.style
  const pctf = (v: number) => `${(v * 100).toFixed(0)}%`
  // 风格相关性：按 |原始 mean| 排序（一眼看出"最像哪个风格"）
  const styleRows: BarRow[] = sp
    ? sp.styles.map(s => ({ label: styleName(s),
                            v1: sp.raw[s]?.mean ?? null, v2: sp.neut?.[s]?.mean ?? null }))
        .sort((a, b) => Math.abs(b.v1 ?? 0) - Math.abs(a.v1 ?? 0))
    : []
  const indRows: BarRow[] = sp
    ? sp.ind_names.map((nm, j) => ({ label: nm,
        v1: sp.ind.raw[j]?.mean ?? null, v2: sp.ind.neut?.[j]?.mean ?? null }))
        .sort((a, b) => Math.abs(b.v1 ?? 0) - Math.abs(a.v1 ?? 0)).slice(0, 15)
    : []
  const topStat = sp ? styleRows.slice(0, 6) : []
  return (
    <div className="chwrap">
      <div className="dt-sec">
        <span>曲线</span>
        <em className="mut">
          离线预算（{c.n_rebal} 期 · {c.cost} 往返）
          {c.start ? ` · 区间 ${c.start}~${c.end}` : ''}
          {c.mtime ? ` · 生成于 ${c.mtime}` : ''}
        </em>
      </div>
      {dl && (
        <>
          <div className="ch-t">净值（日频，起点 = 1）—— 组合 / 基准 / 超额</div>
          <Chart dates={dl.dates} yFmt={v => v.toFixed(1)} series={[
            { label: '组合（Top10% 等权）', color: CPAL[0], data: dl.navT },
            { label: '基准（池内等权）', color: CPAL[1], data: dl.navM },
            { label: '超额', color: CPAL[2], data: dl.navE },
          ]} />
          <div className="ch-t">回撤（日频）—— 超额（面积）/ 组合（虚线）</div>
          <Chart dates={dl.dates} kind="area" zero yFmt={pctf} series={[
            { label: '超额回撤', color: CPAL[2], data: dl.ddE },
            { label: '组合回撤', color: CPAL[0], data: dl.ddT, dashed: true },
          ]} />
        </>
      )}
      {pd && (
        <>
          <div className="ch-t">IC / RankIC（期频）</div>
          <Chart dates={pd.dates} zero yFmt={v => v.toFixed(2)} series={[
            { label: 'RankIC（Spearman，引擎口径）', color: CPAL[0], data: pd.rankIc },
            { label: 'IC（Pearson）', color: CPAL[3], data: pd.ic },
          ]} />
          <div className="ch-t">十分位分组累计净值（费前；第 10 档 = 因子值最高）</div>
          <Chart dates={pd.dates} yFmt={v => v.toFixed(1)}
                 series={pd.decile.map((d, i) => ({
                   label: `第 ${i + 1} 档`, color: CPAL[i % CPAL.length], data: d,
                 }))} />
          <div className="ch-t">多空（第 10 档 − 第 1 档，费前）</div>
          <Chart dates={pd.dates} yFmt={v => v.toFixed(1)}
                 series={[{ label: '多空', color: CPAL[4], data: pd.ls }]} />
          <div className="ch-t">RankIC 累计（看信息是否稳定累积；斜率变平 = 近期失效）</div>
          <Chart dates={pd.dates} zero yFmt={v => v.toFixed(1)}
                 series={[{ label: 'RankIC 累计和', color: CPAL[5], data: cumsum(pd.rankIc) }]} />
          {(pd.turn ?? []).some(v => v !== null) && (
            <>
              <div className="ch-t">单期换手（每期换掉的 Top 组比例）</div>
              <Chart dates={pd.dates} zero yFmt={v => `${(v * 100).toFixed(0)}%`}
                     series={[{ label: '单期换手', color: CPAL[6], data: pd.turn ?? [] }]} />
            </>
          )}
        </>
      )}
      {st ? (
        <>
          <div className="ch-t">剥风格对比（期频超额净值）—— 原 / 剥市值 / 剥成交额 / 剥两者</div>
          <Chart dates={st.dates} yFmt={v => v.toFixed(1)}
                 series={['raw', 'lncap', 'lnamt', 'both', 'floatcap', 'caplimit']
                   .filter(k => (st.navs[k] ?? []).length > 0)
                   .map((k, i) => ({
                     label: STRIP_LABEL[k] ?? k,
                     color: CPAL[i], data: st.navs[k],
                   }))} />
          <div className="ch-lg2">
            剥风格 Calmar：原 {fmtN3(st.calmars.raw)} · 剥市值 {fmtN3(st.calmars.lncap)} ·
            剥成交额 {fmtN3(st.calmars.lnamt)} · 剥两者 {fmtN3(st.calmars.both)}
            {st.calmars.floatcap !== undefined &&
              <> · 剥流通市值 {fmtN3(st.calmars.floatcap)} · 剥总市值+限售 {fmtN3(st.calmars.caplimit)}</>}
          </div>
        </>
      ) : (
        <div className="ch-note">
          剥风格曲线还没生成 —— 跑 python tools/factor_curves.py --stage=strip
        </div>
      )}
      {sp && sp.n_periods > 0 && (
        <>
          <div className="ch-t">
            风格相关性（逐期截面 Spearman · {sp.n_periods} 期换仓日）—— 条长 = 相关系数均值，
            0 在中间、右正左负；上根 = 原始，下根 = 剥总市值 + 行业
          </div>
          <BarChart rows={styleRows} domain={1} />
          <table className="st-tab">
            <thead>
              <tr>
                <th>风格</th><th>均值</th><th>|均值|</th><th>IR</th><th>t</th><th>t朴素</th>
                <th>胜率</th><th>自相关</th><th>剥后均值</th><th>剥后 IR</th>
              </tr>
            </thead>
            <tbody>
              {topStat.map(r => {
                const s = sp.styles.find(x => styleName(x) === r.label) ?? ''
                return (
                  <tr key={r.label}>
                    <td>{r.label}</td>
                    <td>{fmtN3(r.v1)}</td>
                    <td>{fmtN3(sp.raw[s]?.meanAbs)}</td>
                    <td>{fmtN3(sp.raw[s]?.ir)}</td>
                    <td>{fmtN3(sp.raw[s]?.tAdj)}</td>
                    <td>{fmtN3(sp.raw[s]?.t)}</td>
                    <td>{sp.raw[s]?.win === null || sp.raw[s]?.win === undefined
                         ? '—' : `${(sp.raw[s].win! * 100).toFixed(0)}%`}</td>
                    <td>{fmtN3(sp.raw[s]?.ac1)}</td>
                    <td>{fmtN3(r.v2)}</td>
                    <td>{fmtN3(sp.neut?.[s]?.ir)}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
          <div className="ch-t">
            行业暴露 —— 行业 R²（因子对 31 个申万一级哑变量的解释力）：
            原始 {fmtN3(sp.r2.raw)} → 剥后 {fmtN3(sp.r2.neut)}；下面是 |相关| 前 15 个行业
          </div>
          <BarChart rows={indRows} />
          <div className="ch-lg2">
            口径：{sp.caliber}
            <br />
            t = 按 AR(1) 有效样本量校正（右列自相关是 ac1）—— 实测相关序列 ac1≈0.93~0.97，
            所以朴素 t（IR 乘根号 T）会放大数倍，别直接看它。
          </div>
        </>
      )}
      {!sp && (
        <div className="ch-note">
          风格相关性还没算 —— 跑 python tools/factor_curves.py --stage=style+strip2
        </div>
      )}
    </div>
  )
}

/** 因子详情：完整公式（可复制）+ 池标签 + 各项费后指标 */
function FactorDetail({ f, metricsInfo, metricsMtime, onClose }:
  { f: FactorLike; metricsInfo?: LibraryDto['metricsInfo']
    metricsMtime?: string | null; onClose: () => void }) {
  const [copied, setCopied] = useState(false)
  const m = f.metrics ?? {}
  // ★★ 2026-09-16 修（用户："精选池详情页里的指标数据比如超额年化之类的怎么都是 -"）：
  //   根因 = 数值渲染原来只认**库表**路径传进来的 `metricsInfo.found`，而精选池那条路**不传**它
  //   ⇒ `undefined?.found` 为假 ⇒ **所有指标都显示 —**，可数据其实就在 `f.metrics` 里（29 个字段齐全）✗
  //   ⇒ 没传 `metricsInfo` 时退化成"这个因子自己有没有指标"（有 ⇒ 照常显示）✓
  const metricsReady = metricsInfo ? !!metricsInfo.found : Object.keys(m).length > 0
  const d = f.detail ?? ({} as NonNullable<LibraryFactor['detail']>)
  const expr = f.expr || f.summary || ''
  const doCopy = async () => {
    try {
      await navigator.clipboard.writeText(expr)
    } catch {
      const ta = document.createElement('textarea')
      ta.value = expr
      ta.style.position = 'fixed'
      ta.style.opacity = '0'
      document.body.appendChild(ta)
      ta.select()
      document.execCommand('copy')
      document.body.removeChild(ta)
    }
    setCopied(true)
    window.setTimeout(() => setCopied(false), 2500)
  }
  return (
    <div className="dt-mask" onClick={onClose}>
      <div className="dt" onClick={e => e.stopPropagation()}>
        <div className="dt-h">
          <b className="mono">{f.code}</b>
          {!f.inBank && <span className="out">已不在当前有效库（历史编号）</span>}
          <span className="mut">{f.family}</span>
          <button className="x" onClick={onClose}>×</button>
        </div>
        <div className="dt-b">
          <div className="dt-row">
            <span className="k">池标签</span>
            <span className="v">
              {d.poolTag ? <b className="mono">{d.poolTag}</b> : '—'}
              {d.poolTagNote ? <em>{d.poolTagNote}</em> : null}
            </span>
          </div>
          <div className="dt-row">
            <span className="k">方向 sign</span>
            <span className="v">
              {d.sign
                ? <><b className="mono">{d.sign}</b><em>因子值须乘它才是"越大越好"；不乘会反向选股</em></>
                : '—'}
            </span>
          </div>
          {d.strip && (
            <div className="dt-row"><span className="k">剥风格</span><span className="v">{d.strip}</span></div>
          )}
          {d.leaves && (
            <div className="dt-row"><span className="k">叶子</span><span className="v mono">{d.leaves}</span></div>
          )}
          {d.skeleton && (
            <div className="dt-row"><span className="k">骨架</span><span className="v mono">{d.skeleton}</span></div>
          )}

          <div className="dt-sec">
            <span>完整公式</span>
            <button className="btn sm" onClick={doCopy}>{copied ? '已复制' : '复制公式'}</button>
          </div>
          <pre className="dt-expr">{expr}</pre>

          <div className="dt-sec">
            <span>费后指标</span>
            <em className="mut">
              {metricsInfo && !metricsInfo.found
                ? '指标表未生成：先跑 python tools/factor_metrics.py'
                : `统一口径重算（成本 ${m.cost ?? 0.004} 往返 · 5 日调仓 · 全A 面板`
                  + (m.bt_start && m.bt_end
                     ? ` · 回测区间 ${fmtD8(m.bt_start)}~${fmtD8(m.bt_end)}` : ' · 回测区间未记录')
                  + `）${metricsMtime ? ` · 更新于 ${metricsMtime}` : ''}`}
            </em>
          </div>
          {!metricsReady && (
            // ★★ 2026-09-17（用户："中证500 的 F01·历史因子，详情里指标都是 - ，正常吗？"）：
            //   **正常，但要说明白**：指标表以引擎的 `state.bank`（**当前有效库**）为准，
            //   已移出的历史编号不在其中 ⇒ 没有费后指标（曲线同理，只覆盖当前库那 51 个）✓
            //   ⚠ 别只甩一个 `—` 让人以为"出错了/数据丢了" ✗
            <div className="dt-note">
              这个编号没有统一口径指标：指标表和曲线都只覆盖<b>当前有效库</b>
              （引擎 state.bank 里的因子）。本编号带<b>历史</b>标签 = 已移出当前库，
              所以没有做费后重算 —— 数据没丢，是它当前不在库里。
            </div>
          )}
          <div className="dt-note">
            日频打点 = 同一策略在持有期内<b>逐日</b>记净值（所以回撤不会被低估，只会更深）。
            同口径内可比（超额日频 vs 超额期频、组合日频 vs 组合期频）；
            <b>超额口径与组合自身口径不能互相比较</b>（前者要减掉基准腿）。
          </div>
          {METRIC_GROUPS.map(([title, defs]) => (
            <div key={title} className="dt-grp">
              <div className="dt-grp-h">{title}</div>
              <div className="dt-grid">
                {defs.map(([key, label, kind]) => (
                  <div key={key} className="dt-cell">
                    <span className="dk">{label}</span>
                    <span className="dv">{metricsReady ? fmtM(m[key], kind) : '—'}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
          <FactorCharts name={f.code} pool={f.pool} />
          {m.ic_doc !== undefined && m.ic_doc !== null && m.ic !== null && m.ic !== undefined &&
            Math.abs(m.ic - m.ic_doc) > 0.002 && (
              <div className="dt-warn">
                归档时记录的 IC 是 {m.ic_doc.toFixed(4)}，这里重算是 {m.ic.toFixed(4)}（口径可能不同：
                早期条目的成本档/窗口未必与现在一致）。本面板一律用上面这套统一口径。
              </div>
            )}
          {d.metricsDocText && (
            <div className="dt-doc">归档时的指标行：{d.metricsDocText}</div>
          )}
        </div>
      </div>
    </div>
  )
}

function SelectedPanel({ s }: { s: SelectedDto }) {
  const [sel, setSel] = useState<SelectedFactor | null>(null)
  return (
    <section className="panel">
      <div className="sec-h">
        <b>精选因子池（L3 双闸门）</b>
        <span className="mut">{s.count ?? 0} 个 · 来源 <code>{s.path}</code></span>
      </div>
      {s.gates.length > 0 && (
        <ul className="gates">{s.gates.map((g, i) => <li key={i}>{g.replace(/\*\*/g, '')}</li>)}</ul>
      )}
      <div className="selgrid">
        {s.factors.map((f, i) => (
          <div key={i} className="selcard">
            <div className="sel-h">
              <b className="mono">{f.code}</b>
              <span className="grade">{f.grade}</span>
              <span className="sc">剥Calmar <b>{f.stripCalmar.replace(/\*/g, '')}</b></span>
              <button className="btn sm det" onClick={() => setSel(f)}>详情</button>
            </div>
            <code className="expr">{f.expr || '—'}</code>
          </div>
        ))}
      </div>
      {s.notes.length > 0 && (
        <details className="notes">
          <summary>下游使用须知</summary>
          <ul>{s.notes.map((n, i) => <li key={i}>{n}</li>)}</ul>
        </details>
      )}
      {sel && (
        <FactorDetail f={{ code: sel.code, expr: sel.expr, detail: sel.detail,
                           metrics: sel.metrics, inBank: sel.inBank, pool: sel.pool }}
                      onClose={() => setSel(null)} />
      )}
    </section>
  )
}

function MetaPanel({ m }: { m: MetaDto }) {
  const s = m.settings
  return (
    <section className="panel">
      <div className="sec-h"><b>配置与端口</b><span className="mut">改端口只改 <code>config.json</code> 一处</span></div>
      <table className="tbl">
        <tbody>
          <tr><td>配置文件</td><td className="mono">{s.configPath}</td></tr>
          <tr><td>项目根</td><td className="mono">{s.projectRoot}</td></tr>
          <tr><td>后端</td><td className="mono">http://{s.backend.host}:{s.backend.port}</td></tr>
          <tr><td>前端</td><td className="mono">http://{s.frontend.host}:{s.frontend.port}</td></tr>
          <tr><td>需避让的保留端口</td><td className="mono">
            {Object.entries(s.reservedPorts || {}).map(([k, v]) => `${k}=${v}`).join(' · ') || '—'}
          </td></tr>
          <tr><td>数据库</td><td className="mono">
            {String((s.database?.enabled ?? false)) ? String(s.database?.url ?? '') : '未启用（当前读 docs/*.csv + engine/*.pkl）'}
          </td></tr>
        </tbody>
      </table>
      <div className="sec-h" style={{ marginTop: 18 }}><b>API</b></div>
      <ul className="eps">{m.endpoints.map(e => <li key={e} className="mono">{e}</li>)}</ul>
    </section>
  )
}
