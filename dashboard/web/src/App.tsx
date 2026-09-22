import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  api,
  type CurvesDto, type LibraryDto, type LibraryEntriesDto, type LibraryEntryDto,
  type LibraryFactor, type MetaDto, type MineStateDto, type OpsDto,
  type PoolStatus, type SelectedDto, type SelectedFactor, type StatusDto,
} from './api'

type TabKey = 'pools' | 'library' | 'selected' | 'process' | 'meta'

const fmt = (n: number | null | undefined) =>
  n === null || n === undefined ? '—' : n.toLocaleString('en-US')

/** ★ 2026-09-22：小数展示（卡玛一列用 ✓）。缺失 ⇒ `—`（**不当 0** ✗ —— 当 0 会看成"卡玛 0 分" ✓） */
const fmt3 = (x?: number | null) =>
  (typeof x === 'number' && Number.isFinite(x) ? x.toFixed(3) : '—')

/** ★ 排序键：缺值给 `-∞` ⇒ **永远排最后** ✓（不许当成 0 ✗） */
const calKey = (x?: number | null) =>
  (typeof x === 'number' && Number.isFinite(x) ? x : Number.NEGATIVE_INFINITY)

// ★★★★★ 2026-09-22（用户："也在哪儿找个位置加个排序按钮，但是精选池排序要可以**自己选参数**，
//   比如超额排序、年化排序、卡玛排序、超额卡玛排序等"）——
//   精选池下拉里的排序键。一律**降序**（这些指标都越大越好 ✓）；**缺值排最后** ✓。
//   ⚠ 「卡玛 · 原始」用**卡片上显示的那个**（`f.calmar` ✓ 来自剥风格评估的未剥列 ✓）
//     —— 不是统一口径指标表那次重算 ✗（两个数字不同，混用会张冠李戴 ✓）
const selNum = (x?: number | null) =>
  (typeof x === 'number' && Number.isFinite(x) ? x : Number.NEGATIVE_INFINITY)
/** `calmar` / `stripCalmar` 是**字符串**（且可能带 `**` 标记 ✓）⇒ 抠出数字 ✓ */
const selNumStr = (x?: string | null) => {
  const v = Number((x || '').replace(/[^0-9.+-]/g, ''))
  return Number.isFinite(v) ? v : Number.NEGATIVE_INFINITY
}
/** ★★ 2026-09-22（用户："原始卡玛小数太多了，3 位就行"）——
 *  卡玛类数值**统一 3 位小数** ✓。两个来源都要过它：
 *    · `calmar`（原始）= strip bank CSV 的**长浮点**（`0.8202561687921084` ✗ 实测）
 *    · `stripCalmar`（剥后）= md 里取来的**字符串**（本来就是 3 位 ✓ 但别假设它永远规整 ✗）
 *  ⇒ 取不到数就原样显示（**不臆造 0** ✗），缺失给 `—` ✓ */
const fmtCal = (x?: string | number | null): string => {
  if (typeof x === 'number') return fmt3(x)
  const s = (x || '').replace(/[^0-9.+-]/g, '')
  if (!s) return '—'
  const v = Number(s)
  return Number.isFinite(v) ? v.toFixed(3) : s
}
const SEL_SORTS: { k: string; label: string; get: (f: SelectedFactor) => number }[] = [
  { k: '', label: '不排序（原始顺序）', get: () => 0 },
  { k: 'ann_ex', label: '年化 · 超额', get: f => selNum(f.metrics?.ann_ex) },
  { k: 'ann_top', label: '年化 · 组合自身', get: f => selNum(f.metrics?.ann_top) },
  { k: 'calmar_top_d', label: '卡玛 · 组合自身（日频）', get: f => selNum(f.metrics?.calmar_top_d) },
  { k: 'calmar_top', label: '卡玛 · 组合自身（期频）', get: f => selNum(f.metrics?.calmar_top) },
  { k: 'strip_calmar', label: '卡玛 · 剥后超额（期频）', get: f => selNumStr(f.stripCalmar) },
  { k: 'strip_calmar_d', label: '卡玛 · 剥后超额（日频）', get: f => selNumStr(f.stripCalmarD) },
  { k: 'calmar', label: '卡玛 · 超额原始（期频）', get: f => selNumStr(f.calmar) },
  { k: 'calmar_d', label: '卡玛 · 超额原始（日频）', get: f => selNumStr(f.calmarD) },
  { k: 'ic', label: 'IC · 超额', get: f => selNum(f.metrics?.ic) },
  { k: 'turn', label: '换手（越小越好）', get: f => -selNum(f.metrics?.turn) },
]

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
  // ★ 2026-09-17（用户："又入库了一个新因子，但找不到什么时候入库的、入的哪个库"）
  //   ⇒ 池状态区加「新入库日志」卡：最近 50 条（时间 / 池 / 代数 / 编号 / 一句话）+ 详情按钮 ✓
  const [entries, setEntries] = useState<LibraryEntriesDto | null>(null)
  const [entrySel, setEntrySel] = useState<LibraryEntryDto | null>(null)
  const [selected, setSelected] = useState<SelectedDto | null>(null)
  const [tab, setTab] = useState<TabKey>('pools')
  const [pool, setPool] = useState('1000')
  const [auto, setAuto] = useState(true)
  const [interval, setIntervalSec] = useState(10)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [nowMs, setNowMs] = useState(Date.now())
  const [lastAt, setLastAt] = useState<string | null>(null)
  // ★ 2026-09-19（用户之问：公式里的 cs_demean 不知道什么意思）：
  //   首页「立即刷新 / 自动 Ns」旁加「算子手册」按钮 ⇒ 点开是**带滚动条的弹窗**，
  //   列各算子与字段的中文含义 ✓（数据来自后端 /api/ops，名单派生自 ops_registry ✓）
  const [opsOpen, setOpsOpen] = useState(false)
  const [opsData, setOpsData] = useState<OpsDto | null>(null)
  const [opsQ, setOpsQ] = useState('')
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
      const [st, mt, lb, se, ms, le] = await Promise.all([
        api.status(fresh), api.meta(), api.libraries(), api.selected(), api.mineState(),
        api.libraryEntries(50),
      ])
      setStatus(st); setMeta(mt); setLibs(lb.libraries); setSelected(se); setMine(ms)
      setEntries(le)
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
  // ★★ 2026-09-17（用户要求相位卡的鼠标提示**逐池列出**"正在跑：300 · gen 54"）：
  //   优先用控制文件里的 `active`（调度器每起一个引擎就写 `{pool, gen, pid}` ⇒ 最准）✓
  //   拿不到时退化为"在跑的池名（不带代数）"，绝不编造代数 ✓
  const runningList = useMemo(() => {
    // ⚠ 权威是**活进程表**（`runningPools`，由进程扫描得出）；`active` 只用来补**代数** ——
    //   实测：控制文件里的 `active` 会**残留已被停掉的池**（300 明明在 stopped 里却还列着"正在跑" ✗）
    //   ⇒ 反过来"只信 active"就会在提示里报一个**没在跑**的池 ✗
    const live = mine?.runningPools ?? []
    const genOf: Record<string, number | null> = {}
    for (const a of (mine?.active ?? [])) {
      if (a && a.pool) genOf[String(a.pool)] = a.gen ?? null
    }
    if (live.length) return live.map(p => ({ pool: p, gen: p in genOf ? genOf[p] : null }))
    return []
  }, [mine])
  // ★★★ 2026-09-19（用户："鼠标放上去也显示各池自己的轮次"）：**逐池一行**
  //   每行 = 池 · 此刻在干嘛 · 本轮已跑几代 · 当前代数 ✓（三者都来自后端，不是编的 ✓）
  const poolLines = useMemo(() => {
    const en = mine?.enabled ?? []
    const gen: Record<string, number | null> = {}
    for (const a of (mine?.active ?? [])) if (a && a.pool) gen[String(a.pool)] = a.gen ?? null
    return en.map(p => {
      const s = mine?.byPool?.[p]
      // ★★★★ 2026-09-19 第九批：**已停的池不许再写"并行中"** ✗ ——
      //   实测（用户截图）：50 池明明已停，悬停里却写"并行中（在等本轮其它池）" ✗
      //   ⇒ 分三种：真在跑 ⇒ 挖掘中 ✓；已停但这一代还在跑 ⇒ 说清"跑完就退出"✓；
      //     已停且没在跑 ⇒ 已停止 ✓（只有真正参与轮转的池才配"并行中/审查中"✓）
      const what = s?.stopped
        ? (s?.mining ? '已停止（这一代跑完就退出）' : '已停止')
        : (s?.mining ? '挖掘中'
          : (s?.reviewing ? '审查中'
            : (mine?.running ? '并行中（在等本轮其它池）' : '未在跑')))
      const g = (p in gen && gen[p] !== null) ? ` · 当前 gen ${gen[p]}` : ''
      return `${p} · ${what} · 本轮已跑 ${s?.gensRound ?? 0} 代${g}`
    })
  }, [mine])
  // ★★★★ 2026-09-19 第五批（用户："索性改成：`50 3代 | 300 1代 | 500 1代`，
  //   **注意起始从 1 开始，不是 0** —— 1 表示正在挖第 1 代"）
  //   ⇒ N = **正在挖第几代** = 本轮已完成代数 + 1（`gensRound` 是"已完成" ⇒ +1 ✓）
  //     格式 `池 N代` + ` | ` 分隔 + 进度多的排前面 ✓（不与卡片上的"当前 gen"重复 ✓）
  const rollText = useMemo(() => {
    const en = mine?.enabled ?? []
    const rows = en.map((p, i) => ({ p, i, n: Math.max(0, mine?.byPool?.[p]?.gensRound ?? 0) }))
    rows.sort((a, b) => (b.n - a.n) || (a.i - b.i))
    return rows.map(r => `${r.p} ${r.n + 1}代`).join(' | ')
  }, [mine])
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
          {/* ★★★★★ 2026-09-19 第三批（用户："挖掘中的面板太宽啦，跟下面的在跑的池没对齐啊"）：
              相位卡**已移出这一排**，放进下面那行 `KPI 网格`（`section.summary`）的**第一个格子**
              —— 原因：写死像素**永远对不齐**（那行是自适应网格 `minmax(160px, 1fr)`，
              列宽随窗口/条目数变 ✗）⇒ 只有"同格"才能"同宽" ✓（那行第一个是"在跑的池"卡 ✓）*/}
          {/* ★★ 2026-09-16（用户："顶上 19.4 GB 5 池已配置这里的鼠标提示还有引号…干脆把这里的提示
              全部删掉"）⇒ **那个 tooltip 直接去掉**（`memNote` 后端仍在，只是不再挂在悬停上）✓
              —— 该说明（并行数怎么算、面板共享省多少内存）属于"配置/口径"信息，
                 挂在内存数字上纯属噪音；要查口径请看「配置/口径」页 ✓ */}
          <span className="res">
            <b className={mine && mine.freeGB !== null && mine.freeGB < 6 ? 'warn' : ''}>
              {mine?.freeGB !== null && mine?.freeGB !== undefined ? `${mine.freeGB} GB` : '—'}
            </b>
            {/* ★ 当前**实际**在跑的模式（以进程命令行为准，不是 UI 上选的那个）
                ★★ 2026-09-17：**这一格永远渲染** —— 否则"开始挖掘"时卡片会突然变宽 ✗
                （未运行时显示"未运行"占位 ⇒ 卡宽恒定、也不留空白）✓ */}
            {/* ★★ 2026-09-17（用户："`并行×1（自动） · 共享` 改成 `并行 · 共享`，这样卡片可以缩短点"）
                ⇒ 只留模式名 + 共享；**并行数/是否自动**属于"配置口径"（在「配置/口径」页有），
                  挂在常显位置纯属噪音 ⇒ 去掉，卡片宽度也随之收窄 ✓ */}
            <em className={'mode' + (mine?.running ? '' : ' off')}>
              {mine?.running
                ? ((mine.execMode === 'parallel' ? '并行' : '轮转')
                   + (mine.panelCache !== 'off' ? ' · 共享' : ''))
                : '未运行'}
            </em>
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
          {/* ★ 2026-09-19：算子手册（点开是带滚动条的弹窗，查算子与字段的中文含义）✓ */}
          <button className="btn" onClick={() => { setOpsOpen(true); if (!opsData) api.ops().then(setOpsData).catch(() => setErr('算子手册载入失败，稍后再试')) }}
                  title="查算子与字段的中文含义：ts_ 沿时间算、cs_ 当天在股票之间算，末尾数字是窗口期数">
            算子手册
          </button>
        </div>
      </header>

      {opsOpen && (
        <div className="modal" onClick={() => setOpsOpen(false)}>
          <div className="modal-box" onClick={e => e.stopPropagation()}>
            <div className="modal-h">
              <b>算子手册</b>
              <input className="sel ops-q" value={opsQ} onChange={e => setOpsQ(e.target.value)}
                     placeholder="搜索算子或字段，例如 cs_demean" />
              <span className="ops-cnt">
                {opsData ? `算子 ${opsData.counts.ops} 个 · 字段 ${opsData.counts.fields} 个` : '载入中…'}
              </span>
              <button className="btn" onClick={() => setOpsOpen(false)}>关闭</button>
            </div>
            <div className="modal-body">
              {!opsData && <div className="ops-v">正在载入算子手册…</div>}
              {opsData && (() => {
                const q = opsQ.trim().toLowerCase()
                const hit = (s: string) => !q || s.toLowerCase().includes(q)
                const ops = opsData.ops.filter(o => hit(o.name + o.zh + o.tip))
                const fld = opsData.fields.filter(o => hit(o.name + o.zh + o.tip))
                return (
                  <>
                    <div className="ops-sec">先看几条通用规则</div>
                    {opsData.notes.map(n => (
                      <div className="ops-row" key={n.k}>
                        <span className="ops-k">{n.k}</span><span className="ops-v">{n.v}</span>
                      </div>
                    ))}
                    <div className="ops-sec">算子（{ops.length} / {opsData.counts.ops}）</div>
                    {ops.map(o => (
                      <div className="ops-row" key={o.name}>
                        <span className="ops-k ops-mono">{o.sig}</span>
                        <span className="ops-v">
                          <b>{o.zh}</b>{o.tip ? `：${o.tip}` : ''}
                          <span className="ops-tag">{o.winText}</span>
                        </span>
                      </div>
                    ))}
                    <div className="ops-sec">字段（{fld.length} / {opsData.counts.fields}）</div>
                    {fld.map(o => (
                      <div className="ops-row" key={o.name}>
                        <span className="ops-k ops-mono">{o.name}</span>
                        <span className="ops-v"><b>{o.zh}</b>{o.tip ? `：${o.tip}` : ''}</span>
                      </div>
                    ))}
                    {ops.length === 0 && fld.length === 0 && (
                      <div className="ops-v">没有匹配的算子或字段，换个词试试</div>
                    )}
                  </>
                )
              })()}
            </div>
          </div>
        </div>
      )}

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
          {/* ★★★★★ 2026-09-19 第三批（用户："挖掘中的面板太宽啦，跟下面的在跑的池没对齐啊"）：
              相位卡放这里 = **和"在跑的池"卡同格**（同一网格模板 ⇒ **同宽、左右边缘自动对齐** ✓）。
              写死像素做不到这点 ✗（那行 `repeat(auto-fit, minmax(160px, 1fr))` 的列宽随窗口变 ✗） */}
          {/* ★★★★★ 2026-09-19 第七批（用户："还是没对齐" —— 我一直在调像素 ✗，那是治不好的 ✗）
              ⇒ 正解：**直接复用旁边那张卡的组件本身** = 同一个 `.kpi` 类 + 同样的
                `.kpi-v`（大数值行）/ `.kpi-l`（小标签行）⇒ 逐像素一致 ⇒ **天然对齐** ✓✓
              （`t-ok` 绿 / `t-sky` 蓝 跟着相位走 ⇒ 颜色也与 KPI 一致 ✓） */}
          <div className={`kpi phasecard t-${mine?.phase === 'mine' ? 'ok'
            : (mine?.phase === 'tail' ? 'sky' : 'idle')}`} title={
            `当前状态：${mine?.phaseLabel ?? '—'}\n` +
            // ★ 逐池列出（并行时会有多个）—— 原来只显示**最后一个**启动的池 ⇒ 看着像"只跑一个"✗
            (runningList.length
              ? runningList.map(x => `正在跑：${x.pool}${x.gen !== null ? ` · gen ${x.gen}` : ''}`)
                  .join('\n') + '\n'
              : '') +
            // ★★★ 2026-09-19（用户："鼠标放上去也显示各池自己的轮次"）：逐池一行列出
            //   **每个池自己的状态 + 本轮已跑几代 + 当前代数** ✓
            (poolLines.length ? poolLines.join('\n') + '\n' : '') +
            // ★★★★ 2026-09-20（用户："1000 都已经跑完 3 代了，鼠标放在挖掘中，怎么显示还是
            //   第 1 轮、共 500 轮，是不是以后这个轮次显示就没有意义了？"）—— 用户判断对 ✓：
            //   **不限模式**（`--gens_per_round=0`）下每池一轮能跑十几代，而全局轮次要
            //   **三池都收齐**才 +1 ⇒ 实测 `round=1` 时各池已跑 300/12 · 500/9 · 1000/3 代 ✓
            //   ⇒ 所以它**不能当进度看** ✗；但它**不该删** ✓：
            //     ① `--rounds` 是**总预算/终止条件**（跑满才停 ✓）
            //     ② 每收一轮会触发**全局收尾**（全库体检 + 快照 ✓）
            //   ⇒ ★ 2026-09-20 晚（用户）：提示里**不写解释**、也**不写合计** ✗
            //     ⇒ 只留最简的 `第 N 轮 · 轮次上限 M` ✓（口径细节留在代码注释里 ✓）
            (mine?.roundText
              ? `${mine.roundText} · 轮次上限 ${mine?.rounds ?? '?'}\n`
              : '') +
            // ★★★★★ 2026-09-19 第九批（用户："如果我停掉上证50、开启中证1000，这个面板会正确显示吗？"
            //   截图实证：悬停里 `参与的池：300,50,500` 与 `已停的池：50` **同时出现** ✗）——
            //   根因：`enabled`（长期配置）**不会**把刚停的池立刻剔掉 ✗（要等下一轮重配）
            //   ⇒ 显示时**从"参与的池"里剔除 `stopped`** ✓（两份名单不再打架 ✓）
            `参与的池：${(mine?.enabled ?? []).filter(
              p => !(mine?.stopped ?? []).includes(p)).join(',') || '无'}\n` +
            ((mine?.stopped ?? []).length ? `已停的池：${(mine?.stopped ?? []).join(',')}\n` : '') +
            (mine?.updated ? `状态更新于 ${mine.updated}` : '')}>
            {/* ★★★★★ 2026-09-19 第六批（用户："`50 4代 | 300 2代 | 500 1代` 这个得保持在**第二行**"）
                且"圆点必须跟'挖掘中'同一行" ✓ —— 所以把 **圆点 + 标签**包成一组 `.ph1`
                （否则卡片是竖排时，圆点会自己占一行 ✗ 那是上一版的错 ✗） */}
            <div className="kpi-v">
              <i className="pdot" />
              {mine?.phaseLabel ?? '—'}
            </div>
            {/* ★★ 2026-09-17（用户："挖掘中 500 gen17 是 500 池在挖的意思吗？我不是并行了吗？
                300、500 并行挖的话，那它就显示 挖掘中 1/50 不就行了"）
                ⇒ **并行模式不显示单个池名**（那只是最后启动的那个，会让人以为只跑一个 ✗）；
                   逐池明细移到鼠标提示；**轮转模式**仍然显示当前池（那时确实只跑一个）✓
                ⚠ 而且只在**真在跑**时才显示 —— 否则会拿 `curPool` 的**陈旧值**当现状 ✗ */}
            {/* ★ 轮转模式那个"当前池"小字**拿掉** —— 它会让这张卡变成三行、与邻居对不齐 ✗
                （要看当前池：悬停这张卡就有 ✓） */}
            {/* ★★ 2026-09-17（用户："空闲跟 1/50 之间隔了太宽了，留够'空闲 9999/9999'的位置就行"）：
                轮次槽**永远渲染** —— 没数据时是**空槽**（不显示假数据 ✓）；超长则省略号 ✓
                （完整内容在鼠标提示里 ✓）*/}
            <div className="kpi-l">{rollText}</div>
          </div>
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
          {/* ★★★ 2026-09-17（用户："池运行状态在上证50池右边再加一个一样大小的卡片，
              记录新入库因子的挖掘时间日志，带 Y 轴滚动条（不要 X 轴），可看最近 50 条，
              右边也加详情按钮我可以直接点开"）⇒ 卡片与池卡同款（`.card`）✓ */}
          <EntryLogCard d={entries} onDetail={setEntrySel} />
        </section>
      )}
      {/* 详情弹窗与「因子库」页签**同一个组件**（`FactorDetail`）⇒ 口径、字段、布局全一致 ✓ */}
      {entrySel && (
        <FactorDetail f={{ code: entrySel.code ?? '(无编号)', expr: entrySel.expr,
                           pool: entrySel.pool, summary: entrySel.summary,
                           family: entrySel.family ?? '', status: entrySel.status ?? '',
                           inBank: entrySel.inBank, detail: entrySel.detail,
                           metrics: entrySel.metrics } as LibraryFactor}
                      onClose={() => setEntrySel(null)} />
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
        <span>端口来自 <code>dashboard/config.json</code></span>
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
  // ★★★★ 2026-09-19（用户："300/500 一直都是并行中，是在审查呢还是在等 50 池挖完？" +
  //   "池徽标语义是不是加一个审查中？这样跟并行中就能区分开"）：
  //   把「挖掘中 / 审查中 / 并行中」分清 ✗ —— 三者语义：
  //     · 挖掘中 = **有它的引擎在跑**（真的在算）
  //     · 审查中 = 它**刚挖完、正在做收尾**（facs 落地 / 指标表 / 曲线；池内收尾指名它，
  //                或轮末全局收尾进行中）
  //     · 并行中 = 已参与并行，但此刻**既没在挖也没在审** —— 典型是"本轮它已跑完，
  //                在等其它池那一代结束"（以前这三种都显示"并行中" ⇒ 用户看不出在干嘛 ✗）
  const reviewing = !!slot?.reviewing
  const myGen = (mine?.active ?? []).find(a => String(a.pool) === String(p.key))?.gen ?? null
  const badge = mining ? (leaving ? '运行中·已移出'
                                  : (myGen !== null ? `挖掘中 · gen${myGen}` : '挖掘中'))
    : (reviewing ? '审查中'
      : (inRotation ? (qword + '中')
        : (configured ? '待启动' : (stopped ? '已停止' : '空闲'))))
  // ★★★★ 2026-09-17（用户实测："几个池子显示蓝点、只有 300 是绿点，像轮转"）：
  //   那几个池其实是**每代秒崩**（`None * float`）⇒ 永远等不到绿点 ✗
  //   ⇒ 卡片必须**明说"启动即崩"**，否则"蓝点（并行中）"会被误读成"在排队/轮转" ✗✗
  const crashN = slot?.crashes?.length ?? 0
  const crashed = !mining && crashN > 0
  const dotColor = mining ? 'var(--ok)'
    : (reviewing ? 'var(--amber)'
      : (crashed ? '#ef4444'
        : (inRotation ? 'var(--sky)' : (configured ? 'var(--amber)' : 'var(--idle)'))))
  return (
    <div className={cls}>
      <div className="card-h">
        <span className="dot" style={{ background: dotColor }} />
        <b>{p.label}</b>
        <span className="pid">{p.key === 'all' ? '全A' : p.key}</span>
        <span className="state"
              title={`${p.label} 本轮已跑 ${slot?.gensRound ?? 0} 代` +
                     (myGen !== null ? ` · 当前 gen ${myGen}` : '') +
                     (mining ? ' · 正在挖这一代' :
                      reviewing ? ' · 刚挖完，正在做收尾（facs 落地 / 指标表 / 曲线）' :
                      (inRotation ? ' · 已参与并行，此刻在等本轮其它池（它是快池，会立刻领下一代）'
                                  : ''))}>
          {badge}
        </span>
        {crashed && (
          <span className="crash"
                title={`${p.label} 最近 ${crashN} 次一启动就崩（gen ${slot!.crashes.join(',')}）——` +
                       `不是排队、不是轮转；去看 ai_test/_tracks/pool_${p.key}_gen*_err.log 的 traceback`}>
            启动即崩 ×{crashN}
          </span>
        )}
      </div>
      <div className="grid">
        <Field k="当前库（权威）" v={fmt(p.librarySize)} strong />
        <Field k="已测候选" v={fmt(p.tested)} />
        <Field k="跑过代数" v={fmt(p.journal.gens)} />
        {/* ★ 2026-09-19（用户："轮次显示逻辑按照我想要的改"）：**该池自己的进度**
            —— 不限模式下快池一轮能跑七八代，这个数就是它的"本轮轮次" ✓ */}
        <Field k="本轮已跑" v={`${slot?.gensRound ?? 0} 代`} />
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

/** ★★★ 2026-09-17 新增：**新入库日志**卡（池状态区最右，与池卡同款同高）。

用户之问：「我发现又入库了一个新因子，但**找不到什么时候入库的、入的哪个库**」
⇒ 这张卡回答两件事：**什么时候**（`ts`）· **哪个池**（池标签），并给完整公式的入口 ✓

用户对交互的原话：「**带 Y 轴滚动条（不要 X 轴）**、可以查看最近 50 条、右边也加详情按钮」:
  · Y 轴滚动 = `.loglist { overflow-y: auto }` ✓
  · **绝不出横向滚动条** = `overflow-x: hidden` + 文本 `white-space: nowrap; text-overflow: ellipsis` ✓
  · 详情 = 复用「因子库」页签**同一个** `FactorDetail` 组件（字段/口径/布局一致 ✓）
⚠ **时间口径必须让人看见**：`engine` = 入库那一刻的真实时间；历史条目是**推算**的
  （`gen_log` = 该代引擎日志时间 / `md_mtime` = 库文档最后修改）；**拿不到证据的一律标"时间未知"**
  —— 不臆造是项目铁律，而且"编一个时间"比"空着"更糟（会误导判断）✗
*/
/** ★★★ 2026-09-17（用户："新入库日志把那个已入库、已移出的状态也加上吧，加在 F06 文字旁边？"）：
 * 入库日志行「在不在库」的鼠标提示 —— **三态**，与「因子库」页签**完全同源**（同一个 `inBank`）✓
 *
 * ⚠ 两条铁律：
 *   · 判不了（指标表与库文档都没这条）就**如实说判不了** —— 绝不默认成「已入库」（编数据比留白更糟 ✗）
 *   · 文案里不许出现 `**` / ★ / ⇒ / ✓ 这类符号（`_test_ai_tone` 会判成 AI 味 ✗）
 */
const libStateTip = (inBank?: boolean | null) =>
  inBank === true ? '这条编号如今在引擎的有效库里（判据与因子库页签同源）'
    : inBank === false ? '入库过，但已不在当前有效库（只剩历史记录）。点详情仍能看到公式与指标'
      : '指标表与库文档都没收录这条编号，所以判不了它还在不在库（不默认成已入库）'

/** ★★★★ 2026-09-20（用户："因子库页加个 A、B、C 标签就好了，这样我一看就知道啥档位的；
 *   入库日志那里我看也放得下，也加上吧"）—— **剥风格档位标签** ✓
 *
 * 档位来自库文档/指标表里的 `detail.strip`（`loop_pools.STRIP_DESC` 生成，**单一事实源** ✓），
 * 它的开头就是档位字母（`A 独立有效…` / `B 弱独立…` / `C 纯风格…` / `D 未测…`）✓
 * ⇒ 取首字母即可，**不自己重算**（重算就有两个口径、迟早漂移 ✗）
 * ⚠ 语义提醒（用户 09-20 之问："弱有效不应该移出吗？"）：**档位只做标注，不改留库** ✓ ——
 *   有效库（bank）收的是"过了 L2 入库门槛"的因子（含 B/C ✓，它同时是引擎的**去重对照集** ✓），
 *   "只收 A"的是**精选池 L3** ✓ ⇒ 所以 B 档因子留在库里是**按设计** ✓
 */
const gradeOf = (strip?: string | null): string | null => {
  const m = /^\s*([ABCD])\b/.exec(strip || '')
  return m ? m[1] : null
}
const GRADE_COLOR: Record<string, string> = { A: '#10b981', B: '#f59e0b', C: '#ef4444', D: '#94a3b8', 未测: '#94a3b8' }
const GRADE_TIP: Record<string, string> = {
  A: 'A 独立有效：剥掉 11 个 Barra 风格后，日频 Calmar 仍不低于 0.30，且日频回撤优于 -0.20',
  B: 'B 弱独立：剥风格后日频 Calmar 在 0 到 0.30 之间，或回撤劣于 -0.20，因此不进精选池',
  C: 'C 纯风格：剥掉 lncap 与 lnamt 后超额和 Calmar 转负，指数增强不可用',
  D: 'D 未测：该代没开 --strip_style，没做剥风格检验',
  未测: '未测：库文档与指标表里都没有它的剥风格结果（多为早期入库，或入库那一代没开 --strip_style）',
}

function GradeTag({ strip }: { strip?: string | null }) {
  const g = gradeOf(strip)
  // ★★★★ 2026-09-20（用户："补一个未测标签"）—— **没记录也要看得见** ✓
  //   灰标「未测」= 库文档/指标表里**没有**它的剥风格结果（早期入库，或入库那代没开 --strip_style ✓）
  //   ⚠ 仍然**不臆造档位** ✓ —— 之前是"不显示"✗，那会被读成"漏了/没这功能" ✗；
  //     标成"未测"才是实话 ✓（"不知道"和"没有记录"是两件事 ✓）
  const t = (g === 'A' || g === 'B' || g === 'C') ? g : '未测'
  const c = GRADE_COLOR[t] ?? '#94a3b8'
  return (
    // ★ 2026-09-21（用户："这个标签好像比旁边的 A 大了一点，搞成一样的"）：
    //   根因 = **中日韩字形在同样字号下字面比拉丁字母大** ✗（`未测` 两个汉字尤其明显）
    //   ⇒ 给汉字档位加 `cjk` 类，由 CSS 把字号调小一档 + **统一盒子高度** ✓
    <span className={'tag grade' + (t === '未测' ? ' cjk' : '')} title={GRADE_TIP[t] || ''}
          style={{ background: c + '22', color: c, borderColor: c + '55' }}>{t}</span>
  )
}

/** ★★★★★ 2026-09-21（用户："这个标签 ABC 那块再加个 5、20、A 这种标签，5 表示 5 周期选出来牛逼，
 *   20 表示 20 日调仓牛逼，A 表示 5 天和 20 天都牛逼" ⇒ 用户随后拍板写法 = **`5` / `20` / `双`**）
 *   口径强项标签：**在哪个调仓口径下更强** ✓
 *   判据 = **固定阈值**（5 日超额 Calmar ≥ 0.624 · 20 日 ≥ 0.701），由后端 `factors._hzn_tag` 判好 ✓
 *   ⇒ 阈值**只有一处**（后端），前端只查表渲染 ✓
 *
 *   ⚠⚠ 为什么**没用单字母 A** ✗：`A` 已经被**剥风格档位**占用（见上面 `GRADE_COLOR`）——
 *     同一个字母两套语义 ⇒ 用户分不清哪个 A 是"独立有效"、哪个是"双口径都强" ✗（这是硬冲突 ✓）
 *
 *   ⚠ 用户之问"纯数字会有 BUG 吗" ⇒ **数字本身不会** ✓，但两处必须绕开：
 *     ① **CSS 类名不能用裸数字** ✗（`.5` / `.20` 是**非法选择器** ⇒ 样式会静默失效 ✗）
 *        ⇒ 这里用 `hz5` / `hz20` / `hzboth` **加前缀**的类名 ✓
 *     ② 别让这个数字被当**数值**参与比较/排序 ✗ ⇒ 后端给的是**字符串**（`'5'`/`'20'`/`'双'` ✓），
 *        前端只做**查表**（`HZN_TIP` / `HZN_COLOR`）⇒ 不做任何算术 ✓
 */
const HZN_CLASS: Record<string, string> = { '5': 'hz5', '20': 'hz20', '双': 'hzboth' }
const HZN_COLOR: Record<string, string> = { '5': '#60a5fa', '20': '#c084fc', '双': '#fbbf24' }
const HZN_TIP: Record<string, string> = {
  '5': '5 日调仓口径下更强：该口径超额 Calmar ≥ 0.624（2026-09-21 标定 · 全库 62 因子的中位）',
  '20': '20 日调仓口径下更强：该口径超额 Calmar ≥ 0.701（2026-09-21 标定 · 全库 62 因子的中位）',
  '双': '5 日与 20 日两个口径下都更强（各自过标定阈值）—— 这种最结实',
}

function HzTag({ hzn }: { hzn?: string | null }) {
  const h = (hzn ?? '').trim()
  if (!h || !HZN_TIP[h]) return null
  const c = HZN_COLOR[h]
  return (
    // ★ 2026-09-21：`双` 是汉字 ⇒ 加 `cjk`（字号收一档 + 盒子等高）⇒ 与旁边的 `A` 一样大 ✓
    <span className={'tag hz ' + (HZN_CLASS[h] ?? 'hzboth') + (h === '双' ? ' cjk' : '')}
          title={HZN_TIP[h]}
          style={{ background: c + '22', color: c, borderColor: c + '55' }}>{h}</span>
  )
}

function EntryLogCard({ d, onDetail }:
  { d: LibraryEntriesDto | null; onDetail: (e: LibraryEntryDto) => void }) {
  const rows = d?.entries ?? []
  return (
    <div className="card">
      <div className="card-h">
        <span className="dot" style={{ background: 'var(--indigo)' }} />
        <b>新入库日志</b>
        <span className="pid" title={d?.note || ''}>
          最近 {rows.length} 条{d ? ` · 共 ${d.count}` : ''}
        </span>
      </div>
      <div className="loglist">
        {rows.map((e, i) => (
          // ★★ 2026-09-17 用户要求「年份也加上」「详情按钮不要贴着滚动条」「公式短一点没关系」
          //   ⇒ 改成**两行式**：第一行 = 时间（含年份）· 池 · 编号 ·（右）详情；第二行 = 一句话/公式
          //     为什么必须两行：`2026-09-17 02:24` 就要 ~106px，一行里再塞池/编号/按钮 ⇒
          //     公式只剩十几个像素，等于没显示 ✗（用户允诺"公式可以短一点"= 它该让位 ✓）
          <div className="logrow" key={`${e.pool}-${e.code ?? 'x'}-${e.ts ?? i}-${i}`}>
            <div className="logr1">
              <span className="lt"
                    title={e.ts ? `${e.ts}（${e.tsNote || e.tsSource || ''}）` : (e.tsNote || '时间未知')}>
                {e.ts ? e.ts.slice(0, 16) : '时间未知'}
              </span>
              <span className="lp">{e.pool === 'all' ? '全A' : e.pool}</span>
              <span className="lc">{e.code ?? '无编号'}</span>
              <button className="btn sm" onClick={() => onDetail(e)}>详情</button>
            </div>
            {/* ★★★★★ 2026-09-21（用户："这个标签放不下了…然后 A、5、已入库这三个标签都放到第二行吧，
                把公式字符少显示一些就行了"）—— **三个标签从第一行搬到第二行** ✓
                为什么：第一行要放 时间（~106px）+ 池 + 编号 + 三个标签 + 详情按钮 ⇒ 必挤 ✗
                （这正是"标签放不下"的真因 ✓ 不是字号问题 ✓）
                ⇒ 现在：第一行 = 时间 · 池 · 编号 ·（右）详情 ✓
                        第二行 = 档位 A/B/C · 口径 5/20/双 · 状态 + 公式（放不下自动省略号 ✓ 悬停看全 ✓）*/}
            <div className="logr2">
              {/* ★ 2026-09-20：入库日志也带档位（用户："那里我看也放得下，也加上吧"）✓ */}
              <GradeTag strip={(e as { detail?: { strip?: string } }).detail?.strip} />
              {/* ★★★★★ 2026-09-21（用户："它没有 5、20、双的标签，也要加上"）✓ 与库表同源 ✓ */}
              <HzTag hzn={(e as { hzn?: string }).hzn} />
              {/* ★ 入库过 ≠ 还在库里（跨池去重会移出）⇒ 直接标出来，省得去别的页签对 ✗
                  （三态：已入库 / 已移出 / 状态未知；判不了就写未知，绝不默认成已入库 ✓） */}
              <span className={`stag ${e.inBank === true ? 'ok' : e.inBank === false ? 'out' : 'unk'}`}
                    title={libStateTip(e.inBank)}>
                {e.inBank === true ? '已入库' : e.inBank === false ? '已移出' : '状态未知'}
              </span>
              <span className="ls" title={e.expr || e.summary || ''}>
                {e.summary || e.oneLiner || e.expr || '—'}
              </span>
            </div>
          </div>
        ))}
        {!rows.length && <div className="empty">还没有入库记录（跑一次挖掘后就有了）</div>}
      </div>
      <div className="card-f">
        <span>标时间未知的 = 早期入库、没留记录（不臆造）</span>
        <span>点详情看完整公式</span>
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
  // ★★★★★ 2026-09-22（用户："我点卡玛那个列标题它能按照**卡玛从高到低**排序，再按一次**恢复原样**"）——
  //   ① 默认**不排序** ⇒ 就是 API 给的**原始顺序** ✓（不动现状 ✓）
  //   ② 再点一次 ⇒ 回到原始顺序 ✓（`useMemo` 只在 `calSort` 变化时重排 ✓ 不缓存结果 ⇒ 不会越点越乱 ✓）
  //   ③ 缺指标的排最后 ✓（`calKey` 给 -∞ ✓）
  //   ★ 「卡玛」= **组合自身**口径（`cal_top` ✓）—— 不是超额、也不是剥后 ✓（用户特别强调 ✓）
  const [calSort, setCalSort] = useState(false)
  const rows = useMemo(
    () => (calSort ? [...lib.factors].sort((a, b) => calKey(b.cal_top) - calKey(a.cal_top))
                   : lib.factors),
    [lib.factors, calSort])
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
          {/* ★ 2026-09-17 用户要求：删掉"点编号可以看完整公式和各项指标"（历史行本来就没有指标，
              再这么说会误导）✓ 文案合并成一句 */}
          行数比当前有效库多的原因：编号是累计的，而因子会被移出库（比如剥风格后发现它只是纯风格因子），
          带历史标记的行就是已不在当前库的编号。
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
        {(lib.metricsHistory ?? 0) > 0 && (
          <div className="note">
            另有 <b>{lib.metricsHistory}</b> 个已移出的历史编号也算过指标（跑参数带了
            <code>--include_history</code>），这类行点开详情能看到费后指标，不再是空的。
          </div>
        )}
        {stale && (
          <div className="note">
            指标表还没跑完（本池在库 {lib.metricsMeasured} / 有效库 {fmt(lib.stateBank)} 条），
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
        <thead><tr><th>编号</th><th>入库代数</th><th>家族</th>
          {/* ★ 2026-09-22（用户要的**可点排序** ✓）：点一次 ⇒ 卡玛从高到低 ✓；再点 ⇒ 恢复原样 ✓ */}
          <th className={'sortable' + (calSort ? ' on' : '')}
              onClick={() => setCalSort(v => !v)}
              title={'点一次：按【卡玛】从高到低排 —— 这里的卡玛是组合自身口径 '
                     + '(Top10% 等权绝对收益)，不是超额卡玛、也不是剥后卡玛；'
                     + '再点一次：恢复原始顺序；缺指标的排最后'}>
            卡玛{calSort ? ' ↓' : ''}
          </th>
          <th>一句话（公式可能被截断）</th><th>状态</th><th>详情</th></tr></thead>
        <tbody>
          {rows.map((f, i) => (
            <tr key={`${f.code}-${i}`} className={f.inBank === false ? 'outbank' : ''}>
              <td className="mono strong">
                {/* ★ 2026-09-20（用户："因子库页加个 A、B、C 标签"）⇒ 编号旁边直接标档位 ✓ */}
                <GradeTag strip={f.detail?.strip} />
                {/* ★★★★★ 2026-09-21（用户拍板写法 `5` / `20` / `双`）：**口径强项**标签 ✓
                    规则在后端（`factors._hzn_tag` ✓ 固定阈值 0.624 / 0.701 ✓）⇒ 前端只渲染 ✓
                    ★ 2026-09-21 用户要"双和 A 标签对调位置" ⇒ 现在是「**档位 A/B/C → 口径 5/20/双 → 编号**」✓ */}
                <HzTag hzn={f.hzn} />
                <button className="fcode" onClick={() => setSel(f)}
                        title={f.inBank === false
                          ? '该编号已不在当前有效库，只剩历史编号（文件只增不改）。点开仍能看到公式与指标'
                          : '点开看完整公式（可复制）、池标签与各项费后指标'}>
                  {f.code}{f.inBank === false ? ' · 历史' : ''}
                </button>
              </td>
              <td className="mono">{f.gen}</td>
              <td>{f.family}</td>
              {/* ★ 2026-09-22：**卡玛**列（组合自身口径 `cal_top` ✓ —— 不是超额、不是剥后 ✓） */}
              <td className="mono num">{fmt3(f.cal_top)}</td>
              {/* ★ 2026-09-21：一句话列**显示上截短**（`styles.css` 的 `.sum` 省略号 ✓）
                  ⇒ 必须给 `title`，否则截掉的内容**无处可看** ✗（用户只授权"少显示"，没授权"看不见" ✓） */}
              <td className="sum" title={f.summary}>{f.summary}</td>
              {/* ★ 历史行的**状态文案也要说实话** —— 明细行里写的还是"已入库"（当年入库时的记录，
                  文件只增不改）⇒ 会被读成"还在库里" ✗ ⇒ 这里直接标"已移出当前库" ✓ */}
              <td><span className={f.inBank === false ? 'status hist' : 'status'}>
                {f.inBank === false ? '已移出当前库（历史）' : f.status}
              </span></td>
              <td><button className="btn sm" onClick={() => setSel(f)}>详情</button></td>
            </tr>
          ))}
        </tbody>
      </table>
      {!lib.factors.length && <div className="empty">（本池无表格数据）</div>}
      {sel && <FactorDetail f={sel} metricsInfo={lib.metricsInfo} metricsMtime={lib.metricsMtime}
                            metrics20Info={lib.metrics20Info}
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
// ★ 2026-09-21：加 `metrics20` ⇒ 详情页的**口径开关**才能拿到 20 日那一套指标 ✓
type FactorLike = Pick<LibraryFactor, 'code' | 'expr' | 'detail' | 'metrics' | 'metrics20'> & {
  family?: string
  summary?: string
  pool?: string
  /** ★ 三态：true 在库 / false 已移出 / null|undefined 未知（指标表不完整） */
  inBank?: boolean | null
}

const fmtD8 = (d: number) => `${String(d).slice(0, 4)}-${String(d).slice(4, 6)}-${String(d).slice(6, 8)}`

// ★ 2026-09-17：顶栏相位卡的**紧凑文案**（卡片是定宽的 218px；完整信息在鼠标提示里）✓
/** `500 · gen 17` → `500 gen17` */
const compactCur = (t?: string | null) => (t || '').replace(/\s*·\s*gen\s*/, ' gen')
/** `第 1 轮` → `1`（配合后面的 `/50` 显示成 `1/50`） */
const compactRound = (t?: string | null) => (t || '').replace(/^第\s*/, '').replace(/\s*轮$/, '')

// ================================================================ 曲线（SVG，零依赖）
// ★ 2026-09-16（用户要求：指标下面加曲线图）：数据**离线预算**（`tools/factor_curves.py`），
//   这里只负责画 ⇒ 打开详情 = 读一个几十 KB 的 JSON + 画 SVG，**对性能没有影响** ✓
//   ★ 用**手写 SVG** 而不是引图表库：本项目前端零依赖（只有 react/react-dom），
//     引库要多几十万字节 + 多一个升级面；这些图（折线/面积）手写 60 行足够 ✓
const CPAL = ['#6366f1', '#22d3ee', '#f59e0b', '#34d399', '#f472b6',
              '#a78bfa', '#facc15', '#38bdf8', '#fb7185', '#4ade80']
const dLab = (d: number) => `${String(d).slice(2, 4)}-${String(d).slice(4, 6)}`

type ChSeries = { label: string; color: string; data: (number | null)[]; dashed?: boolean
  /** ★ 2026-09-18：图例项的可选说明（鼠标提示）—— 口径解释放这里，**不占标题栏** ✓ */
  tip?: string }

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
  // ★★★★★ 2026-09-21（用户："所有的图能不能加个功能 —— 我鼠标移动的时候，图上会有锚点出来跟着鼠标走，
  //   然后有个 tag 提示对应曲线的具体值；tag 要小点、别一大块盖住后面的曲线，或者稍微透明一点，
  //   让后面曲线透出来一丢丢；这样不影响性能吧？"）
  //   · 锚点 = 每条**可见**曲线在当前 x 上的一个小圆点（跟着鼠标走 ✓）
  //   · tag = **紧凑两列**小浮标 + **半透明底**（rgba 0.82 ⇒ 后面曲线能透一点 ✓）
  //   · 性能：只 setState 一个**下标**（值相同就交给 React 直接跳过 ✓）；折线的 `d` 串**一点没变**
  //     ⇒ React 不会写 DOM（属性相同不更新 ✓）⇒ 开销就是一帧几个 SVG 节点，可忽略 ✓
  const svgRef = useRef<SVGSVGElement | null>(null)
  const [hov, setHov] = useState<number | null>(null)

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
                      title={s.tip ?? '点击显示 / 隐藏这条曲线'}>
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
  // 鼠标位置 → **最近的数据下标**（用 svg 的实际宽度把 clientX 折算回 viewBox 坐标 ✓）
  const onMove = (e: { clientX: number }) => {
    const el = svgRef.current
    if (!el) return
    const r = el.getBoundingClientRect()
    const t = ((e.clientX - r.left) * (W / (r.width || W)) - PL) / (W - PL - PR)
    const i = Math.max(0, Math.min(n - 1, Math.round(t * (n - 1))))
    setHov(prev => (prev === i ? prev : i))        // 下标没变 ⇒ 不触发重渲染 ✓
  }
  return (
    <div className="ch">
      <svg ref={svgRef} viewBox={`0 0 ${W} ${H}`} width="100%" role="img"
           onMouseMove={onMove} onMouseLeave={() => setHov(null)}>
        {/* ★ 透明捕获面：空处也能收到 mousemove（否则只有画到线的地方才响应 ✗）*/}
        <rect x={PL} y={PT} width={W - PL - PR} height={H - PT - PB} fill="transparent" />
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
        {/* ★★★★★ 2026-09-21（用户要的"鼠标锚点 + 小 tag" ✓）：
            十字准线 + 每条可见曲线的**锚点圆点** + **紧凑半透明**值浮标
            （全部 `pointer-events: none` ⇒ 不抢鼠标、不挡交互 ✓；
              底 rgba(12,18,34,0.82) ⇒ 后面的曲线能透出来一丢丢 ✓ 用户要求 ✓）*/}
        {hov !== null && hov >= 0 && hov < n && (() => {
          const hx = X(hov)
          const rows = vis
            .map(({ s }) => ({ s, v: s.data[hov] }))
            .filter(r => r.v !== null && r.v !== undefined && Number.isFinite(r.v as number))
          if (!rows.length) return null
          // ★★ 2026-09-21 修（用户："字都叠一块儿了"✗ + "是不是看两位小数，一位太少了？"）：
          //   ① 列宽原来是**写死的 84px** ✗ ⇒ 长标签（如"组合（Top10% 等权）"）直接压到数值上 ✗
          //      ⇒ 改成**按文字实测宽度自适应**（CJK ≈9.2px / ASCII ≈5.2px ✓）；超宽就截断加省略号 ✓
          //   ② 数值原来沿用**坐标轴格式**（净值图是 1 位小数 ✗ 看着像 0.9 / 1.0 ✓）
          //      ⇒ 悬停值**至少两位小数** ✓（本身已是 2 位以上、或带 % 的，原样保留 ✓）
          const tw = (s: string) => {
            let w = 0
            for (const ch of s) w += ch.charCodeAt(0) > 0x2e80 ? 9.2 : 5.2
            return w
          }
          const hvFmt = (v: number) => {
            const t = fmt(v)
            return (/\.\d{2,}/.test(t) || t.includes('%')) ? t : v.toFixed(2)
          }
          // 标签**智能缩短**：只去掉尾部的括号解释（"组合（Top10% 等权）" → "组合" ✓ 图例里仍是全长 ✓）；
          // ⚠ 缩短后若**重名**（两条曲线缩成同一个名字）就退回全长 ⇒ 绝不含糊 ✓
          const fullL = rows.map(r => r.s.label)
          const stripParen = (s: string) => s.replace(/[（(][^）)]*[）)]\s*$/, '').trim() || s
          const baseL = fullL.map(stripParen)
          const names0 = new Set(baseL).size === baseL.length ? baseL : fullL
          // ★★★★★ 2026-09-21（用户："RANKIC 累计这里咋还有省略号，把这个省略号去掉"✓）——
          //   上一版把"超 9 字就截断加 …"**无条件**做了 ✗（哪怕只有一条曲线、明明放得下 ✗）
          //   ⇒ 改成**有回退链的排版**：
          //        ① 先按**两列**、**不截断**排 → 放得下就完事 ✓
          //        ② 两列超宽（MAXW）→ 退**单列**（仍然不截断 ✓）
          //        ③ 单列还超宽 → 才**逐级截断**（16→12→10→8→6 字 ✓）
          //   ⇒ 单条曲线（如 RankIC 累计和）现在**原样显示** ✓，只有真放不下才出现 … ✓
          const ROW = 12, PX = 5, HEAD = 21, PY = 4, GAP = 16, MAXW = 250
          const mk = (cl: number, cutN: number) => {
            const nm = names0.map(s => (cutN > 0 && s.length > cutN ? s.slice(0, cutN) + '…' : s))
            const vt = rows.map(r => hvFmt(r.v as number))
            const pr = Math.ceil(rows.length / cl)
            // 每列宽度 = 该列里最长那条的（点 + 标签 + 间隔 + 数值）实测宽度 ✓
            const cs = Array.from({ length: cl }, (_, ci) => {
              let w = 9
              for (let k = ci * pr; k < Math.min((ci + 1) * pr, rows.length); k++) {
                w = Math.max(w, 9 + tw(nm[k]) + 8 + tw(vt[k]))
              }
              return Math.min(w + 1, 200)        // 上限 200 兜底（防病态长名撑爆 ✓）
            })
            const wd = cs.reduce((a, b) => a + b, 0) + PX * 2 + (cl - 1) * GAP
            return { nm, vt, cl, pr, cs, wd }
          }
          let L = mk(rows.length > 4 ? 2 : 1, 0)
          if (L.wd > MAXW) L = mk(1, 0)
          if (L.wd > MAXW) {
            for (const nn of [16, 12, 10, 8, 6]) { L = mk(1, nn); if (L.wd <= MAXW) break }
          }
          const names = L.nm, valsT = L.vt, cols = L.cl, per = L.pr, CWs = L.cs
          // ★★ 2026-09-21（用户："十分位那里左边那列数字应该往左边挪点，不要离右边的圆点太近了，
          //   不然还以为是右边的数据 —— 后面图如果涉及两列数据也是一样调整" ✓）
          //   ⇒ 两列之间加 **16px 列间距** ＋ 一条**淡分隔线** ⇒ 一眼看清哪列归哪列 ✓
          const XO = CWs.map((_, ci) => PX + CWs.slice(0, ci).reduce((a, b) => a + b, 0) + ci * GAP)
          const bw = L.wd
          const bh = HEAD + Math.max(per - 1, 0) * ROW + 7 + PY     // 末行基线 + 字降部 + 下边距 ✓
          // 优先放准线右侧；右边放不下就翻到左侧；纵向夹在绘图区内 ✓
          const bx = hx + 8 + bw <= W - PR ? hx + 8 : Math.max(PL, hx - 8 - bw)
          const by = Math.max(PT, Math.min(H - PB - bh, Y(rows[0].v as number) - bh / 2))
          return (
            <g pointerEvents="none">
              <line x1={hx} y1={PT} x2={hx} y2={H - PB} stroke="#41527a" strokeDasharray="3 3" />
              <rect x={bx} y={by} width={bw} height={bh} rx="3"
                    fill="rgba(12,18,34,0.82)" stroke="#33456b" strokeWidth="1" />
              {/* 两列之间一条淡分隔线（多列时才画 ✓）—— 防止"左边数值被读成右边那条"✗ */}
              {cols > 1 && CWs.slice(1).map((_, i) => (
                <line key={`sep${i}`} x1={bx + XO[i + 1] - GAP / 2} y1={by + 5}
                      x2={bx + XO[i + 1] - GAP / 2} y2={by + bh - 5}
                      stroke="#2b3a5c" strokeWidth="1" />
              ))}
              <text x={bx + PX} y={by + 10} fontSize="9" fill="#8fa0c4">{dLab(dates[hov])}</text>
              {rows.map((r, k) => {
                const ci = Math.floor(k / per), ri = k % per
                const tx = bx + XO[ci]
                const ty = by + HEAD + ri * ROW
                return (
                  <g key={`hv${k}`}>
                    <circle cx={tx + 3} cy={ty - 3} r="2.4" fill={r.s.color} />
                    <text x={tx + 9} y={ty} fontSize="9" fill="#c3cee6">{names[k]}</text>
                    <text x={tx + CWs[ci] - 2} y={ty} fontSize="9" fill="#ffffff" textAnchor="end">
                      {valsT[k]}
                    </text>
                  </g>
                )
              })}
              {rows.map((r, k) => (
                <circle key={`hd${k}`} cx={hx} cy={Y(r.v as number)} r="2.6"
                        fill={r.s.color} stroke="#0b1220" strokeWidth="1" />
              ))}
            </g>
          )
        })()}
      </svg>
      <div className="ch-lg">
        {series.map((s, i) => (
          <button key={i} className={`ch-lgbtn${off[i] ? ' off' : ''}`}
                  onClick={() => setOff(o => ({ ...o, [i]: !o[i] }))}
                  title={s.tip ?? (off[i] ? '点击显示这条曲线' : '点击隐藏这条曲线')}>
            <i style={{ background: s.color }} />{s.label}
          </button>
        ))}
      </div>
    </div>
  )
}

const fmtN3 = (v: number | null | undefined) =>
  v === null || v === undefined || Number.isNaN(v) ? '—' : v.toFixed(3)

/** ★★ 横向条形图（风格相关性用）—— 2026-09-16；★ 2026-09-18 加第三根「剥全部」
 *  · 每行 2 或 3 根：上=**原始**、中=**剥总市值 + 行业**、下=**剥全部**（11 个 Barra 风格 + 行业内去均值）
 *    ；0 在中间，左负右正
 *  · `domain` 给了就固定值域（风格相关性固定 ±1 ⇒ **跨因子可比** ✓）；不给则按数据自适应（行业用）
 *  · 图例可点（与折线图同约定）· 第三根**只在真有 `v3` 时才画**（老文件没有 ⇒ 自动退回两根 ✓，不编数据 ✗）
 */
type BarRow = { label: string; v1: number | null; v2?: number | null; v3?: number | null }

function BarChart({ rows, rowH = 15, domain, fmt, tag2 = '剥后', tag3 = '剥全部' }:
  { rows: BarRow[]; rowH?: number; domain?: number; fmt?: (v: number) => string
    tag2?: string; tag3?: string }) {
  const [hide, setHide] = useState<{ a: boolean; b: boolean; c: boolean }>(
    { a: false, b: false, c: false })
  const sig = rows.map(r => r.label).join('|')
  useEffect(() => { setHide({ a: false, b: false, c: false }) }, [sig])
  const has3 = rows.some(r => r.v3 !== undefined && r.v3 !== null)
  const nbar = has3 ? 3 : 2
  const W = 720, LX = 112, RX = 104, gap = 5
  const vs: number[] = []
  rows.forEach(r => {
    if (!hide.a && r.v1 !== null && Number.isFinite(r.v1)) vs.push(r.v1)
    if (!hide.b && r.v2 !== undefined && r.v2 !== null && Number.isFinite(r.v2)) vs.push(r.v2)
    if (has3 && !hide.c && r.v3 !== undefined && r.v3 !== null && Number.isFinite(r.v3)) {
      vs.push(r.v3)
    }
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
          const hh = Math.max(3, (rowH - 2) / nbar)
          const nums = [fv(r.v1 ?? NaN)]
          if (r.v2 !== undefined && r.v2 !== null) nums.push(fv(r.v2))
          if (has3 && r.v3 !== undefined && r.v3 !== null) nums.push(fv(r.v3))
          return (
            <g key={i}>
              <text x={LX - 6} y={y + rowH / 2 + 3} fontSize="10.5" fill="#c8d3ee"
                    textAnchor="end">{r.label}</text>
              {!hide.a && bar(r.v1, y - 0.5, hh, CPAL[0])}
              {!hide.b && bar(r.v2, y + hh + 0.5, hh, CPAL[2])}
              {has3 && !hide.c && bar(r.v3, y + 2 * hh + 1.5, hh, CPAL[4])}
              <text x={W - RX + 6} y={y + rowH / 2 + 3} fontSize="9.5" fill="#8b9ac0">
                {nums.join(' / ')}
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
        {has3 && (
          <button className={`ch-lgbtn${hide.c ? ' off' : ''}`}
                  onClick={() => setHide(o => ({ ...o, c: !o.c }))}
                  title="点击隐藏或显示剥全部这一根">
            <i style={{ background: CPAL[4] }} />{tag3}（剥 11 个 Barra 风格 + 行业）
          </button>
        )}
        <span className="ch-lg-hint">
          右侧数字：原始 / 剥后{has3 ? ' / 剥全部' : ''}
        </span>
      </div>
    </div>
  )
}

/** 风格名 → 中文（Barra 11 + 自有 4）
 *  ★★ 2026-09-21（用户："其他标签都是英文的，全都搞成中文吧"）
 *  ⇒ 把此前**中英混排**的三条也收干净 ✓：`规模 size` → `规模`、
 *    `成长 growth` → `成长`、`Beta` → `贝塔`（用户要的是全中文，不留英文尾巴 ✓）*/
const STYLE_LABEL: Record<string, string> = {
  lncap: '对数总市值', lnamt: '对数成交额', lntr: '对数换手率', lnpx: '对数股价',
  barra_size: '规模', barra_non_linear_size: '非线性规模', barra_momentum: '动量',
  barra_liquidity: '流动性', barra_book_to_price: '账面市值比', barra_leverage: '杠杆',
  barra_growth: '成长', barra_earnings_yield: '盈利收益率', barra_beta: '贝塔',
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
    floatcap: '剥流通市值', caplimit: '剥总市值+限售',
    // ★ 2026-09-18（用户命名）：第 7 条叫「剥全部」= 11 个 Barra 风格 + 行业内去均值 ✓
    //   （用户："重跑剥 11 + 行业…正规一点"；4 个自有风格与 Barra 重叠 ⇒ 不参与回归 ✓）
    allsty: '剥全部', indneu: '行业中性' }

/** ★ 2026-09-18（用户："这个很丑啊…改成剥风格对比就好啦"）：
 *  口径解释**搬到图例项的鼠标提示里**（`ChSeries.tip`）⇒ 标题栏保持一行、图例保持一行 ✓
 *  ⚠ 这些串会**显示给用户** ⇒ 一律自然语言，不许 `**` / ★ / ✗ 这类符号（`_test_ai_tone` 会判 AI 味 ✗） */
const STRIP_TIP: Record<string, string> =
  { raw: '原 = 不做任何风格中性化的原始信号',
    lncap: '剥市值 = 对总市值做截面秩中性化',
    lnamt: '剥成交额 = 对成交额做截面秩中性化',
    both: '剥两者 = 同时剥总市值与成交额',
    floatcap: '剥流通市值 = 用流通市值做中性化',
    caplimit: '剥总市值加限售比例 = 总市值与流通市值之比一起剥',
    allsty: '剥全部 = 秩回归剥掉 11 个 Barra 风格，再把残差按行业内去均值（4 个自有风格与 Barra 重叠，不参与回归）' }

/** 详情页图表区：打开时**才**拉曲线（离线预算好的），拉到前显示占位 ✓
 *
 * ★★★★ 2026-09-17 修**真 BUG**（用户："新入库的 `500 F06` 为啥**有曲线图**，但超额年化那些
 *   指标都是 `—`？"）—— 根因不在指标，在**曲线取错了文件** ✗✗：
 *   · 曲线文件按 `factor_curves.py` 的命名落盘：`all` 池 = `F06.json`，**其它池 = `F06_500.json`**
 *   · 而这里原来直接用 `f.code`（`F06`）+ `pool` 只是拼进 **URL**（后端**只按文件名读**，
 *     URL 里的池名它不看 ✗）⇒ 500 池的 F06 读到了 `F06.json` = **全A 池的另一个因子**的曲线 ✗✗
 *     （两者是完全不同的公式！用户看到的那张图根本不是这个因子的）
 *   ⇒ 修：**在这里按同一规则补池后缀**（单一规则：`no` for `all` / `{no}_{pool}` 其它池 ✓），
 *     并且**缺失时如实报"暂无曲线"**（而不是去拿别的池的图顶上 ✗）
 *   ⚠ 这就是"命名规则散落在两处"的典型代价：写文件的地方在 `tools/factor_curves.py`，
 *     读文件的地方在这里 —— 两处必须用同一个规则 ✓（已加守门 `_test_frontend_wiring`）
 */
function FactorCharts({ name, pool, fwd = 5 }:
  { name: string; pool?: string; fwd?: number }) {
  const [c, setC] = useState<CurvesDto | null>(null)
  // ★ 2026-09-20：动态暴露图里"哪些风格显示"—— null = 还没点过 ⇒ 默认**全部显示** ✓
  const [expoVis, setExpoVis] = useState<Set<string> | null>(null)
  const [err, setErr] = useState<string | null>(null)
  // ★ 曲线文件名 = `tools/factor_curves.py::_name_of` 的同一条规则（all 不带后缀，其它池带 `_<池>`）
  // ★★★★★ 2026-09-19 第八批（用户："我发现精选池还有好几个因子没有曲线嘛！"）
  //   查实：**不是没算曲线，是文件名拼重了** ✗ ——
  //     精选池里 `F07_1000`（pool=1000）与 `F05_500`（pool=500）：代码**本身已带池后缀** ⇒
  //     再拼一次 ⇒ 去找 `F07_1000_1000.json` / `F05_500_500.json`，
  //     而磁盘上确实是 `F07_1000.json` / `F05_500.json` ✓ ⇒ 面板显示"暂无曲线数据" ✗
  //   ⇒ 修：**已经带该池后缀就不再重复拼** ✓（生成侧规则不变 ✓ `factor_curves.py::_name_of`）
  const file = (pool && pool !== 'all')
    ? (name.endsWith(`_${pool}`) ? name : `${name}_${pool}`)
    : name
  useEffect(() => {
    let dead = false
    setC(null); setErr(null)
    // ★ 2026-09-21：把**口径**一起传下去 ✓（换口径 ⇒ 后端换目录读 ⇒ 整块曲线都变 ✓）
    api.curves(pool || 'all', file, 700, fwd)
      .then(d => { if (!dead) setC(d) })
      .catch(e => { if (!dead) setErr(e instanceof Error ? e.message : String(e)) })
    return () => { dead = true }
  }, [name, pool, file, fwd])
  if (err) return <div className="ch-note">曲线读取失败：{err}</div>
  if (!c) return <div className="ch-note">曲线加载中…</div>
  if (!c.found) return <div className="ch-note">暂无曲线数据。{c.hint}</div>
  const dl = c.daily, pd = c.period, st = c.strip, sp = c.style
  const pctf = (v: number) => `${(v * 100).toFixed(2)}%`
  // 风格相关性：按 |原始 mean| 排序（一眼看出"最像哪个风格"）
  const styleRows: BarRow[] = sp
    ? sp.styles.map(s => ({ label: styleName(s),
                            v1: sp.raw[s]?.mean ?? null, v2: sp.neut?.[s]?.mean ?? null,
                            v3: sp.allsty?.[s]?.mean ?? null }))
        .sort((a, b) => Math.abs(b.v1 ?? 0) - Math.abs(a.v1 ?? 0))
    : []
  const indRows: BarRow[] = sp
    ? sp.ind_names.map((nm, j) => ({ label: nm,
        v1: sp.ind.raw[j]?.mean ?? null, v2: sp.ind.neut?.[j]?.mean ?? null,
        v3: sp.ind.allsty?.[j]?.mean ?? null }))
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
          <Chart dates={dl.dates} yFmt={v => v.toFixed(2)} series={[
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
          {/* ★ 2026-09-17（用户问"要不要做 MAD 去极值" ⇒ 顺手把两条 IC 的口径差说清）：
              因子那侧两边都是秩（安全）；差别在**收益那侧** —— RankIC 也取了秩，而 Pearson IC 用的是
              **原始收益** ⇒ 会被涨跌停/重组这种肥尾拉偏 ⇒ **以 RankIC 为准** ✓ */}
          <div className="ch-note">
            以 RankIC 为准（两侧都取截面秩，与引擎入库判据同口径）
            —— IC（Pearson）那一侧的收益用的是原始值，会被涨跌停或重组这类肥尾拉偏，仅作参考。
          </div>
          <div className="ch-t">十分位分组累计净值（费前；第 10 档 = 因子值最高）</div>
          <Chart dates={pd.dates} yFmt={v => v.toFixed(2)}
                 series={pd.decile.map((d, i) => ({
                   label: `第 ${i + 1} 档`, color: CPAL[i % CPAL.length], data: d,
                 }))} />
          <div className="ch-t">多空（第 10 档 − 第 1 档，费前）</div>
          <Chart dates={pd.dates} yFmt={v => v.toFixed(2)}
                 series={[{ label: '多空', color: CPAL[4], data: pd.ls }]} />
          <div className="ch-t">RankIC 累计（看信息是否稳定累积；斜率变平 = 近期失效）</div>
          <Chart dates={pd.dates} zero yFmt={v => v.toFixed(2)}
                 series={[{ label: 'RankIC 累计和', color: CPAL[5], data: cumsum(pd.rankIc) }]} />
          {(pd.turn ?? []).some(v => v !== null) && (
            <>
              <div className="ch-t">单期换手（每期换掉的 Top 组比例）</div>
              <Chart dates={pd.dates} zero yFmt={v => `${(v * 100).toFixed(2)}%`}
                     series={[{ label: '单期换手', color: CPAL[6], data: pd.turn ?? [] }]} />
            </>
          )}
        </>
      )}
      {st ? (
        <>
          <div className="ch-t">剥风格对比（期频超额净值）</div>
          <Chart dates={st.dates} yFmt={v => v.toFixed(2)}
                 series={['raw', 'lncap', 'lnamt', 'both', 'floatcap', 'caplimit',
                          'allsty', 'indneu']
                   .filter(k => (st.navs[k] ?? []).length > 0)
                   .map((k, i) => ({
                     label: STRIP_LABEL[k] ?? k,
                     color: CPAL[i], data: st.navs[k], tip: STRIP_TIP[k],
                   }))} />
          <div className="ch-lg2">
            剥风格 Calmar：原 {fmtN3(st.calmars.raw)} · 剥市值 {fmtN3(st.calmars.lncap)} ·
            剥成交额 {fmtN3(st.calmars.lnamt)} · 剥两者 {fmtN3(st.calmars.both)}
            {st.calmars.floatcap !== undefined &&
              <> · 剥流通市值 {fmtN3(st.calmars.floatcap)} · 剥总市值+限售 {fmtN3(st.calmars.caplimit)}</>}
            {st.calmars.allsty !== undefined && (
              // ★ 2026-09-18（用户）：这一行太长了 ⇒ **「剥全部」另起一行**（前面 6 项保持一行 ✓）
              <>
                <br />
                <b>剥全部 {fmtN3(st.calmars.allsty)}</b>
                （对照：只剥风格不剥行业 {fmtN3(st.calmars.allsty_noind)}
                {st.calmars.indneu !== undefined && <> · <b>行业中性 {fmtN3(st.calmars.indneu)}</b></>}）
              </>
            )}
          </div>
        </>
      ) : (
        <div className="ch-note">
          剥风格曲线还没生成 —— 跑 python tools/factor_curves.py --stage=strip
        </div>
      )}
      {/* ★★★★★ 2026-09-20（用户："加个图，可以看 11 个风格的动态暴露曲线？鼠标移动的时候显示
          每个风格的动态暴露值，然后加个按钮全部隐藏、全部显示，这样我可以只看某一个风格暴露的曲线"）
          · 值 = Barra **原生值** ⇒ **中性线 0** ✓（原生值即"市值加权 0 均值"口径 ⇒ 市值加权全市场天然 0 ✓；
            ⚠ 绝不能拿池内等权均值当参照 ✗ —— 实测 size 等权均值 −1.68 / 市值加权 +0.09 ✓）
          · 组合 = 该因子**最强十分之一等权**（后端 `expo_for` 已算好 ✓）
          · 交互：一排风格芯片可**逐个开关** ✓ ＋ 全部显示 / 全部隐藏 ✓ ＋ 悬停显示各条当值 ✓ */}
      {c?.expo && c.expo.styles.length > 0 && (() => {
        const ex = c.expo
        const vis = expoVis ?? new Set(ex.styles)
        // ★★ 2026-09-21（用户："comovement 是啥，为啥是一条水平线"）—— 排查结论：
        //   数据源里 **`barra_comovement` 全库恒为 1**（418 期 std = 0 · 唯一值 = 1 ✗）
        //   = **占位值 / 该风格没算出数据** ✗（其余 10 个风格 std 0.11 ~ 0.57 ✓ 都是真值 ✓）
        //   ⇒ 画出来就是一条死直线 ✓（不是"它真的平稳" ✗）⇒ 前端**把它从图里隐去** ✓
        //     并给一行说明 ⇒ 免得看着像我们的图画错了 ✗（等接入真实共动性数据会自动出现 ✓）
        const _flat = (s: string) => {
          const a = (ex.series[s] ?? []).filter(v => v !== null && Number.isFinite(v)) as number[]
          if (a.length < 30) return true
          return Math.max(...a) - Math.min(...a) < 1e-6
        }
        const dead = ex.styles.filter(_flat)
        const live = ex.styles.filter(s => !dead.includes(s))
        const picked = live.filter(s => vis.has(s))
        // ★★★★★ 2026-09-21（用户："这个全部显示全部隐藏按钮有点丑啊，改成跟其他按钮一样的多好看，
        //   然后其他标签都是英文的，全都搞成中文吧"）
        //   ⇒ ① 两个批量按钮**改成与风格芯片同一套药丸样式** ✓（此前是 `className="state"`
        //        那个米色方按钮 ⇒ 跟右边一排药丸不同族，看着突兀 ✗）
        //      ② 芯片与图例**一律走 `styleName()`** ⇒ 中文 ✓（此前直接 `s.replace('barra_','')` ✗）
        //      ③ 顺带清掉标题里原本露给用户看的 `✗`（用户可见文案不许带符号 ✓）
        const chip = (active: boolean, col: string) => ({
          cursor: 'pointer', padding: '2px 10px', borderRadius: 999, fontSize: 11.5,
          background: 'transparent', border: '1px solid ' + (active ? col : 'var(--bd)'),
          color: active ? col : 'var(--mut)', opacity: active ? 1 : 0.55,
        })
        return (
          <>
            <div className="ch-t">
              动态风格暴露（{live.length} 个 Barra 风格 · {ex.dates.length} 期换仓日）——
              值 = 组合在 Barra <b>原生暴露</b>上的均值，<b>0 = 中性</b>
              （原生值即市值加权 0 均值口径 ⇒ 市值加权全市场天然为 0；不能拿池内等权均值当参照）
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, margin: '6px 0 8px' }}>
              <button style={chip(vis.size < live.length, 'var(--mut)')}
                      onClick={() => setExpoVis(new Set(live))}>全部显示</button>
              <button style={chip(vis.size > 0, 'var(--mut)')}
                      onClick={() => setExpoVis(new Set())}>全部隐藏</button>
              {live.map((s, i) => {
                const on = vis.has(s)
                const col = CPAL[i % CPAL.length]
                return (
                  <button key={s} onClick={() => {
                    const n = new Set(vis)
                    if (on) { n.delete(s) } else { n.add(s) }
                    setExpoVis(n)
                  }} style={chip(on, col)}>
                    {styleName(s)}
                  </button>
                )
              })}
            </div>
            {dead.length > 0 && (
              <div className="ch-note">
                {dead.map(styleName).join('、')}：当前数据源里这列是常量（没有真实暴露值），已从图中隐去
              </div>
            )}
            {picked.length > 0 ? (
              <Chart dates={ex.dates} zero yFmt={v => v.toFixed(2)}
                     series={picked.map(s => ({
                       label: styleName(s),
                       color: CPAL[ex.styles.indexOf(s) % CPAL.length],
                       data: (ex.series[s] ?? []).map(v => (v === null ? NaN : v)),
                       tip: '组合在' + styleName(s) + '上的原生暴露（0 = 中性）',
                     }))} />
            ) : (
              <div className="ch-note">11 条全收起了 —— 点上面的风格芯片就能只看某一个 ✓</div>
            )}
          </>
        )
      })()}
      {sp && sp.n_periods > 0 && (
        <>
          <div className="ch-t">
            风格相关性（逐期截面 Spearman · {sp.n_periods} 期换仓日）—— 条长 = 相关系数均值，
            0 在中间、右正左负；上根 = 原始，中根 = 剥总市值 + 行业，
            下根 = 剥全部（剥掉 11 个 Barra 风格 + 行业）
          </div>
          <BarChart rows={styleRows} domain={1} />
          <table className="st-tab">
            <thead>
              <tr>
                <th>风格</th><th>均值</th><th>|均值|</th><th>IR</th><th>t</th><th>t朴素</th>
                <th>胜率</th><th>自相关</th><th>剥后均值</th><th>剥后 IR</th><th>剥全部均值</th>
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
                    <td>{fmtN3(sp.allsty?.[s]?.mean)}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
          <div className="ch-t">
            行业暴露 —— 行业 R²（因子对 31 个申万一级哑变量的解释力）：
            原始 {fmtN3(sp.r2.raw)} → 剥后 {fmtN3(sp.r2.neut)}
            {sp.r2.allsty !== undefined && <> → 剥全部 {fmtN3(sp.r2.allsty)}</>}
            ；下面是 |相关| 前 15 个行业
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
function FactorDetail({ f, metricsInfo, metricsMtime, metrics20Info, onClose }:
  { f: FactorLike; metricsInfo?: LibraryDto['metricsInfo']
    metricsMtime?: string | null
    /** ★ 2026-09-21：20 日口径表元信息（判"那一档能不能切" ✓） */
    metrics20Info?: LibraryDto['metrics20Info']
    onClose: () => void }) {
  const [copied, setCopied] = useState(false)
  // ★★★★★ 2026-09-21（用户："详情页点进去…在 F01 资金流…旁边加切换的选项卡，可以选 5 日调仓
  //   或者 20 日调仓，切换到 20 日调仓**所有指标曲线就都选成 20 日的**"）—— 详情页**口径开关** ✓
  //   一处状态同时驱动：① 上面「费后指标」整块 ② 下面**所有曲线**（净值/剥风格/动态暴露 ✓）
  const [fwd, setFwd] = useState(5)
  // 20 日那档**有没有数据**：表在 ✓ 且这个因子在表里有数 ✓
  // ⚠ 缺数据 ⇒ 按钮**置灰**（不是点完才说没有 ✗）免得用户以为坏了 ✓
  const m20 = f.metrics20 ?? {}
  const has20 = (metrics20Info ? !!metrics20Info.found : true)
    && Object.keys(m20).length > 0
  const use20 = fwd === 20 && has20
  // ⚠ 兜底：切到 20 但没数据 ⇒ **仍按 5 日显示**（宁可显示旧口径，也不显示一片「—」✗）
  const m = use20 ? m20 : (f.metrics ?? {})
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
          {/* ★ 2026-09-17：这里原来写 `!f.inBank` ⇒ `null`（判不了）也会显示"已不在当前有效库" ✗
              —— **编结论比留白更糟**（用户会以为这个编号被淘汰了）⇒ 只有**确证 false** 才这么说 ✓ */}
          {f.inBank === false && <span className="out">已不在当前有效库（历史编号）</span>}
          <span className="mut">{f.family}</span>
          {/* ★★★★★ 2026-09-21（用户："在 F01 资金流…旁边加切换的选项卡，可以选 5 日调仓或者
              20 日调仓，切换到 20 日调仓所有指标曲线就都选成 20 日的"）—— **口径开关** ✓
              ⚠ 20 日没数据时置灰（不点了才报错 ✗）✓ */}
          {/* ⚠ 用户可见文案**不许带引号**（`_test_ui_quotes.py` 会判 ✗）⇒ 用普通标点 ✓ */}
          <span className="seg hzseg" role="group"
                title="调仓口径：切换后，费后指标与下面所有曲线（净值 / 剥风格 / 动态暴露）一起切">
            {[5, 20].map(k => (
              <button key={k} className={fwd === k ? 'on' : ''}
                      disabled={k === 20 && !has20}
                      title={k === 20 && !has20
                        ? '20 日口径数据还没生成：先跑 tools/factor_metrics.py --fwd 20，'
                          + '再跑 tools/factor_curves.py --fwd=20 --out_dir=factor_curves_fwd20'
                        : `${k} 日调仓口径`}
                      onClick={() => setFwd(k)}>{k} 日</button>
            ))}
          </span>
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
                ? <><b className="mono">{d.sign}</b><em>因子值须乘它才是"越大越好"；不乘会反向选股{d.signFrom ? `（来自${d.signFrom}，库文档当时没记）` : ''}</em></>
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
                : `统一口径重算（成本 ${m.cost ?? 0.004} 往返 · ${use20 ? 20 : 5} 日调仓 · 全A 面板`
                  + (m.bt_start && m.bt_end
                     ? ` · 回测区间 ${fmtD8(m.bt_start)}~${fmtD8(m.bt_end)}` : ' · 回测区间未记录')
                  + `）${metricsMtime ? ` · 更新于 ${metricsMtime}` : ''}`}
            </em>
          </div>
          {!metricsReady && (
            // ★★ 2026-09-17（用户："中证500 的 F01·历史因子，详情里指标都是 - ，正常吗？"
            //   + 后来："新入库的 500 F06 为啥有曲线图，但超额年化那些指标都是 —？"）：
            //   **都是"正常但要说清"**，且**两种原因完全不同** ⇒ 必须分情况给命令 ✓：
            //     · 历史编号（已移出当前库）⇒ 指标表默认不算它 ⇒ 要 `--include_history` ✓
            //     · 在库但**表比库旧**（新入库还没重算）⇒ 跑 `--only-new` 即可 ✓
            //   ⚠ 只甩一个 `—` 会让人以为"出错了/数据丢了" ✗（而且会误导去翻错的地方）
            <div className="dt-note">
              {f.inBank === false ? (
                <>这个编号已移出当前库（历史），而指标表默认只算<b>当前有效库</b> ⇒ 所以没有数。
                  想补它：跑 <code>python tools/factor_metrics.py --include_history</code> 与
                  <code>python tools/factor_curves.py --include_history --only-new</code> ✓</>
              ) : (
                <>指标表里还没有这个编号 —— 说明<b>表比库旧</b>（新入库的因子还没重算），
                  不是出错。补一条命令即可：<code>python tools/factor_metrics.py --only-new</code>
                  （约 8~12 分钟）；曲线是**另一套离线产物**，单独跑
                  <code>python tools/factor_curves.py --only-new --stage=core</code> ✓</>
              )}
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
          {/* ★ 2026-09-21：曲线跟着**口径开关**走 ✓（换口径 = 后端换目录读 ⇒ 整块图都变 ✓） */}
          <FactorCharts name={f.code} pool={f.pool} fwd={use20 ? 20 : 5} />
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
  // ★★★★★ 2026-09-22（用户："也在哪儿找个位置加个排序按钮，但是精选池排序要可以**自己选参数**，
  //   比如超额排序、年化排序、卡玛排序、超额卡玛排序等"）——
  //   · 排序键**由用户在下拉里选** ✓（不是写死某一列 ✓）
  //   · 默认 `''` = **不排序** ⇒ 原始顺序 ✓（与库表同一套语义：不擅自改现状 ✓）
  //   · 一律**降序**（这些指标都是越大越好 ✓）；**缺值排最后** ✓（给 −∞ ⇒ 不当成 0 分 ✓）
  const [sortKey, setSortKey] = useState('')
  const list = useMemo(() => {
    const of = SEL_SORTS.find(o => o.k === sortKey)
    if (!of) return s.factors
    return [...s.factors].sort((a, b) => of.get(b) - of.get(a))
  }, [s.factors, sortKey])
  return (
    <section className="panel">
      <div className="sec-h">
        <b>精选因子池（L3 双闸门）</b>
        <span className="mut">{s.count ?? 0} 个 · 来源 <code>{s.path}</code></span>
        {/* ★ 排序控件：选一个指标 ⇒ 按它从高到低排；选「不排序」⇒ 恢复原样 ✓ */}
        <label className="selsort">
          排序
          <select className="sel" value={sortKey} onChange={e => setSortKey(e.target.value)}
                  title={'选一个指标，就按它从高到低排（缺指标的排最后）；'
                         + '选第一项则不排序，恢复原始顺序。'}>
            {SEL_SORTS.map(o => <option key={o.k || 'off'} value={o.k}>{o.label}</option>)}
          </select>
        </label>
      </div>
      {s.gates.length > 0 && (
        <ul className="gates">{s.gates.map((g, i) => <li key={i}>{g.replace(/\*\*/g, '')}</li>)}</ul>
      )}
      <div className="selgrid">
        {list.map((f, i) => (
          <div key={i} className="selcard">
            <div className="sel-h">
              <b className="mono">{f.code}</b>
              <span className="grade">{f.grade}</span>
              {/* ★★★★★ 2026-09-21（用户："精选池那里还只有 A 标签，没有 5、20、双标签"）：
                  口径标签与库表**同源**（后端联表时从 `library()` 照抄 ✓ 阈值只有一处 ✓）⇒ 这里只渲染 ✓ */}
              <HzTag hzn={f.hzn} />
              {/* ★ 2026-09-22（用户："除了显示剥卡玛，也显示**原始卡玛**吧"）——
                  两个数字来自**同一次剥风格评估** ⇒ 并排看就是"剥掉了多少" ✓
                  原始 = 未剥的费后超额卡玛（`calmar` ✓）；剥后 = `stripCalmar` ✓ */}
              {/* ★★★★★ 2026-09-22（用户："我不要看超额卡玛啊，我要看**组合自身的日频卡玛**，改一下。
                  后面那个数可以显示**剥后超额卡玛**，这样不就清楚了。然后就显示日频的，
                  这样详情按钮就可以跟它们放在同一行了"）——
                  ⇒ 卡片只留**两个数**（标签也短 ⇒ 详情按钮回到同一行 ✓）：
                    · 组合日频卡玛 = `calmar_top_d`（Top10% 等权组合的**绝对**收益，逐日 mark ✓）
                    · 剥后超额卡玛 = `strip_calmar`（剥掉市值+成交额之后的超额 ✓）
                  ⚠ 「超额卡玛」（`calmar`）**不再显示** ✗（用户明确不要 ✓）—— 但仍留在排序下拉里 ✓ */}
              <span className="sc" title={'组合日频卡玛：Top10% 等权组合的绝对收益卡玛，'
                                           + '逐日 mark-to-market（含持仓期内回撤）。'
                                           + '这是组合自身口径，与超额口径的数字不可直接比。'}>
                组合日频卡玛 <b>{fmt3(f.metrics?.calmar_top_d)}</b>
              </span>
              <span className="sc" title={'剥后超额卡玛：剥掉市值与成交额之后的超额卡玛'
                                           + '（组合减基准）。与左边的组合自身口径不同，别直接比。'}>
                剥后超额卡玛 <b>{fmtCal(f.stripCalmar)}</b>
              </span>
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
      {/* ★ 2026-09-21：精选池点开的详情也带上 `metrics20` ⇒ **口径开关**在这里同样可用 ✓
          ⚠ 注释必须放在 `{sel && (` **外面** ✗ —— 那对括号里只能是**一个表达式**，
            塞 JSX 注释会让解析器当场报 TS1005 ✗（我第一版就是这样、被 `tsc` 抓住 ✓） */}
      {sel && (
        <FactorDetail f={{ code: sel.code, expr: sel.expr, detail: sel.detail,
                           metrics: sel.metrics, metrics20: sel.metrics20,
                           inBank: sel.inBank, pool: sel.pool }}
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
