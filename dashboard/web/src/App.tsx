import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  api,
  type LibraryDto, type MetaDto, type MineStateDto, type PoolStatus,
  type SelectedDto, type StatusDto,
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
      const r = await api.mineStart(pools, rounds)
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
      say('ok', r.restarted
        ? `调度器之前没在运行，已自动重启。池 ${pool} 已加入轮转（当前启用：${r.enabled.join(',')}）`
        : `池 ${pool} 已重新加入轮转，下一轮轮到它`)
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
          <span className="res" title={
            `始终只有一个引擎在跑，约占 ${mine?.gbPerEngine ?? 9} GB。\n` +
            `当前可用内存 ${mine?.freeGB ?? '?'} GB。`}>
            <b className={mine && mine.freeGB !== null && mine.freeGB < 6 ? 'warn' : ''}>
              {mine?.freeGB !== null && mine?.freeGB !== undefined ? `${mine.freeGB} GB` : '—'}
            </b>
            {/* 区分“正在轮转”与“只是配置了但调度器没跑” */}
            <small>{mine?.running
              ? `${(mine?.enabled ?? []).length} 个池正在轮转`
              : ((mine?.enabled ?? []).length
                ? `${(mine?.enabled ?? []).length} 个池已配置，未运行`
                : '未配置')}</small>
          </span>
          <span className="rounds" title={`每个池要跑的轮数，范围 1~${mine?.roundsRange?.[1] ?? 200}。一轮 = 每个参与的池各跑 1 代`}>
            轮数
            <input type="number" min={mine?.roundsRange?.[0] ?? 1} max={mine?.roundsRange?.[1] ?? 200}
                   value={rounds} disabled={mineBusy}
                   onChange={e => setRounds(Math.max(1, Math.min(200, Number(e.target.value) || 1)))} />
          </span>
          <button className="btn start" disabled={mineBusy || !!mine?.running} onClick={() => doStart([])}
                  title={mine?.running
                    ? '调度器已经在运行了。要改设置的话，先全部停止再重新启动'
                    : '启动调度器，让所有池参与轮转。之前单独停止过的池也会重新加入。已经在跑的话就地更新设置，不会重复启动'}>
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
  const badge = mining ? (leaving ? '运行中·已移出' : '挖掘中')
    : (inRotation ? '轮转中'
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
                  ? `${p.label} 已在轮转里（下一轮就会轮到它）`
                  : (leaving
                    ? `${p.label} 正在跑但已移出轮转。点它 = 重新加入轮转，让它继续参与`
                    : `把 ${p.label} 加入轮转。如果调度器没在运行，会自动启动`)}>
          {inRotation ? '已参与轮转' : (leaving ? '重新加入轮转' : '启动本池')}
        </button>
        <button className="btn stop sm" disabled={busy || (!inRotation && !mining)} onClick={onStop}
                title={(!inRotation && !mining)
                  ? `${p.label} 既不在轮转也没在跑`
                  : (mining
                    ? (leaving
                      ? `${p.label} 已移出轮转，正在跑完当前这一代（跑完就会停）。点它可立即结束`
                      : `停止 ${p.label}：从轮转中移除，并结束它当前那一代。其他池不受影响`)
                    : `把 ${p.label} 从轮转中移除（它当前没在跑，所以只影响后续轮次）`)}>
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
  return (
    <div className="libwrap">
      <div className="caliber">
        <b>口径说明</b>（这里三个数字不一样，以第一个为准）：
        <ul>
          <li><b>当前有效库 = {fmt(lib.stateBank)}</b> —— <span>权威：引擎实际在用的对照集，来自 <code>loop_state_{lib.pool}.pkl</code></span></li>
          <li>本表行数 = {fmt(lib.count)} —— <span>累计入库编号，该文件只增不改</span></li>
          <li>文件声明 = {fmt(lib.declaredCount)} —— <span>引擎同步的快照，可能落后</span></li>
        </ul>
        <div className="note">注意：不要把「累计编号」当成「当前库」，页面一律以<b>当前有效库</b>为准。</div>
      </div>
      <table className="tbl">
        <thead><tr><th>编号</th><th>入库代数</th><th>家族</th><th>一句话</th><th>状态</th></tr></thead>
        <tbody>
          {lib.factors.map((f, i) => (
            <tr key={`${f.code}-${i}`}>
              <td className="mono strong">{f.code}</td>
              <td className="mono">{f.gen}</td>
              <td>{f.family}</td>
              <td className="sum">{f.summary}</td>
              <td><span className="status">{f.status}</span></td>
            </tr>
          ))}
        </tbody>
      </table>
      {!lib.factors.length && <div className="empty">（本池无表格数据）</div>}
    </div>
  )
}

function SelectedPanel({ s }: { s: SelectedDto }) {
  return (
    <section className="panel">
      <div className="sec-h">
        <b>精选因子池（L3 双闸门）</b>
        <span className="mut">{s.count ?? 0} 个 · 来源 <code>{s.path}</code></span>
      </div>
      {s.gates.length > 0 && (
        <ol className="gates">{s.gates.map((g, i) => <li key={i}>{g.replace(/\*\*/g, '')}</li>)}</ol>
      )}
      <div className="selgrid">
        {s.factors.map((f, i) => (
          <div key={i} className="selcard">
            <div className="sel-h">
              <b className="mono">{f.code}</b>
              <span className="grade">{f.grade}</span>
              <span className="sc">剥Calmar <b>{f.stripCalmar.replace(/\*/g, '')}</b></span>
            </div>
            <code className="expr">{f.expr || '—'}</code>
          </div>
        ))}
      </div>
      {s.notes.length > 0 && (
        <details className="notes">
          <summary>⚠ 下游使用须知</summary>
          <ul>{s.notes.map((n, i) => <li key={i}>{n}</li>)}</ul>
        </details>
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
