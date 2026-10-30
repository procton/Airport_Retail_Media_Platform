/** Platform Admin — map, KPIs, incidents, feeds, master data (AGENTS §13). */
import { useEffect, useMemo, useState } from 'react'
import { api, fmtHM, money } from '../api'
import type { ZoneRow } from '../api'
import { useStore } from '../store'

type Tab = 'map' | 'incidents' | 'master' | 'rules'

const BAND_LAYOUT: Record<string, { col: number; row: number }> = {
  'T1-A-gates': { col: 0, row: 0 }, 'T1-B-gates': { col: 1, row: 0 }, 'T1-C-gates': { col: 2, row: 0 },
  'T1-BUS-gates': { col: 3, row: 0 }, 'T1-security': { col: 4, row: 0 }, 'T1-retail-main': { col: 5, row: 0 },
  'T2-1-gates': { col: 0, row: 1 }, 'T2-5-gates': { col: 1, row: 1 }, 'T2-6-gates': { col: 2, row: 1 },
  'T2-7-gates': { col: 3, row: 1 }, 'T2-8-gates': { col: 4, row: 1 }, 'T2-BUS-gates': { col: 5, row: 1 },
  'T2-security': { col: 6, row: 1 }, 'T2-retail-main': { col: 7, row: 1 },
}

export default function AdminView() {
  const { zones, screens, metrics, flights } = useStore()
  const [tab, setTab] = useState<Tab>('map')
  const [incidents, setIncidents] = useState<any[]>([])
  const [feeds, setFeeds] = useState<any[]>([])
  const [heat, setHeat] = useState(true)
  const [selScreen, setSelScreen] = useState<string | null>(null)
  const [tick, setTick] = useState(0)

  useEffect(() => {
    const onRed = useStore.subscribe(() => setTick((t) => t + 1))
    return onRed
  }, [])

  useEffect(() => {
    api.incidents().then((j) => setIncidents(j.incidents)).catch(() => {})
    api.feeds().then((j) => setFeeds(j.feeds)).catch(() => {})
  }, [tick])

  const online = screens.filter((s) => s.online).length

  return (
    <div className="grid">
      <div className="row" style={{ margin: '2px 0' }}>
        <nav className="tabs">
          {(['map', 'incidents', 'master', 'rules'] as Tab[]).map((t) => (
            <button key={t} className={tab === t ? 'on' : ''} onClick={() => setTab(t)}>
              {t === 'map' ? 'Terminal map' : t === 'incidents' ? 'Incidents & feeds' : t === 'master' ? 'Master data' : 'Decisions & rules'}
            </button>
          ))}
        </nav>
        <div className="spacer" />
        {tab === 'map' && (
          <button className="btn small" onClick={() => setHeat(!heat)}>{heat ? '🔥 Heat on' : '🧊 Heat off'}</button>
        )}
      </div>

      {tab === 'map' && (
        <>
          <div className="grid cols-4">
            <div className="card"><div className="kpi"><span className="v">{metrics?.screens_online_pct ?? (online && Math.round(100 * online / Math.max(screens.length, 1)))}%</span><span className="l">screens online ({online}/{screens.length})</span></div></div>
            <div className="card"><div className="kpi"><span className="v">{metrics?.plays_today ?? 0}</span><span className="l">ad plays today</span></div></div>
            <div className="card"><div className="kpi"><span className="v">{(metrics?.impressions_today ?? 0).toLocaleString()}</span><span className="l">impressions today <span className="est">(est. exposure)</span></span></div></div>
            <div className="card"><div className="kpi"><span className="v">{money(metrics?.revenue_today ?? 0)}</span><span className="l">ad revenue today <span className="est">(simulated CPM)</span></span></div></div>
          </div>
          <div className="grid cols-4">
            <div className="card"><div className="kpi"><span className="v">{metrics?.active_campaigns ?? 0}</span><span className="l">active campaigns</span></div></div>
            <div className="card"><div className="kpi"><span className="v">{metrics?.playlist_latency_ms?.toFixed(0) ?? '—'} ms</span><span className="l">playlist rebuild (wall-clock)</span></div></div>
            <div className="card"><div className="kpi"><span className="v">{flights.filter((f) => f.delay_min > 0).length}</span><span className="l">delayed legs (live)</span></div></div>
            <div className="card"><div className="kpi"><span className="v">{mediaMoney(metrics, zones)}</span><span className="l">configured slot price <span className="est">(presence-driven avg)</span></span></div></div>
          </div>

          <div className="card" style={{ padding: 8 }}>
            <MapSvg heat={heat} zones={zones} screens={screens} onPick={setSelScreen} />
          </div>
          {selScreen && <ScreenInspector screenId={selScreen} onClose={() => setSelScreen(null)} />}

          <div className="card">
            <h3>Presence by zone <span className="live">LIVE</span></h3>
            <table className="list">
              <thead><tr><th>Zone</th><th>Pax</th><th>Next 30m</th><th>2h</th><th>Dwell</th><th>Intl</th><th>Top destinations</th></tr></thead>
              <tbody>
                {zones.map((z) => (
                  <tr key={z.zone_id}>
                    <td>{z.name}</td>
                    <td className="mono">{z.passenger_count}</td>
                    <td className="mono forecast">{z.next30_count}</td>
                    <td className="mono forecast">{z.next120_count}</td>
                    <td className="mono">{Math.round(z.dwell_median_min)}′</td>
                    <td className="mono">{Math.round((z.intl_count / Math.max(z.passenger_count, 1)) * 100)}%</td>
                    <td>{z.top_destinations ? z.top_destinations.slice(0, 3).map((d) => <span key={d[0]} className="chip" style={{ marginRight: 4 }}>{d[0]} ×{d[1]}</span>) : null}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {tab === 'incidents' && (
        <>
          <div className="card">
            <h3>Auto alerts (outages raise an incident immediately; thresholds are simulation-time)</h3>
            {incidents.length === 0 ? <section className="empty">No incidents open — inject a screen outage to trigger one.</section> : (
              <table className="list">
                <thead><tr><th>Severity</th><th>Title</th><th>Where</th><th>Status</th><th>Opened (sim)</th><th>Remediation</th></tr></thead>
                <tbody>
                  {incidents.slice(-12).map((i) => (
                    <tr key={i.id + i.opened_at}>
                      <td><span className={`chip ${i.severity === 'high' ? 'bad' : 'warn'}`}>{i.severity}</span></td>
                      <td>{i.title}<br /><small className="muted">{i.detail}</small></td>
                      <td>{i.where}</td>
                      <td><span className="chip">{i.status}</span></td>
                      <td className="mono">{fmtHM(i.opened_at)}</td>
                      <td>
                        <button className="btn small" onClick={async () => { await api.screenOnline(i.related, true); setIncidents((xs) => xs.map((x) => (x.id === i.id ? { ...x, status: 'resolved' } : x))) }}>
                          Re-enable {i.related}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
          <div className="card">
            <h3>Adapters / feed health</h3>
            <table className="list">
              <thead><tr><th>Source</th><th>Adapter</th><th>Health</th><th>Note</th></tr></thead>
              <tbody>
                {feeds.map((f) => (
                  <tr key={f.source}>
                    <td>{f.source}</td><td className="mono">{f.adapter}</td>
                    <td><span className={'chip ' + (f.healthy ? 'good' : 'bad')}>{f.healthy ? 'healthy' : 'degraded'}</span></td>
                    <td>{f.note}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {tab === 'master' && <MasterData />}
      {tab === 'rules' && <DecisionsAndRules screens={screens} />}
    </div>
  )
}

/** Admin decision log (searchable) + global rule sliders (AGENTS §12). */
function DecisionsAndRules({ screens }: { screens: any[] }) {
  const [rows, setRows] = useState<any[] | null>(null)
  const [meta, setMeta] = useState<any>(null)
  const [q, setQ] = useState('')
  const [screenFilter, setScreenFilter] = useState('')
  const [searchInput, setSearchInput] = useState('')
  const [rules, setRules] = useState<any | null>(null)
  const [savedMsg, setSavedMsg] = useState('')

  const loadLog = (query: string, sid: string) => {
    setRows(null)
    const params = new URLSearchParams()
    if (query) params.set('search', query)
    if (sid) params.set('screen_id', sid)
    params.set('limit', '120')
    api.get(`/decisions?${params.toString()}`).then((j) => { setRows(j.decisions); setMeta(j) })
      .catch((e) => setMeta({ note: String(e) }))
  }
  useEffect(() => { loadLog('', '') }, [])
  useEffect(() => {
    api.get('/config/media-rules').then((j) => setRules(j.media_rules)).catch(() => setRules(null))
  }, [])
  const save = async (patch: any) => {
    const merged = { ...rules, ...patch }
    setRules(merged)
    try {
      const j = await api.put('/config/media-rules', merged)
      setRules(j.media_rules)
      setSavedMsg('saved; applies at the next slot boundary (rules persisted for restarts)')
      setTimeout(() => setSavedMsg(''), 6000)
    } catch (e: any) { setSavedMsg(String(e?.message || e)) }
  }
  const fmtCandidates = (d: any) => {
    const cands = d?.why?.top_candidates || []
    return cands.map((c: any) => `${c.campaign_id} ${c.score?.toFixed?.(2)}${c.eligible ? '' : '(filtered)'}`).join(' · ') || 'house'
  }
  return (
    <>
      <div className="card">
        <h3>Decision log <span className="chip muted">model_version {meta?.model_version ?? '—'} · run {meta?.run_id ?? '—'}</span></h3>
        <div className="row">
          <input style={{ flex: 1 }} placeholder="search reason/pin/exploration/any record text …"
                 value={searchInput} onChange={(e) => setSearchInput(e.target.value)}
                 onKeyDown={(e) => { if (e.key === 'Enter') { setQ(searchInput); loadLog(searchInput, screenFilter) } }} />
          <select value={screenFilter} onChange={(e) => { setScreenFilter(e.target.value); loadLog(q, e.target.value) }}>
            <option value="">all screens</option>
            {(screens.length ? screens : []).slice(0, 60).map((s: any) => <option key={s.id} value={s.id}>{s.id}</option>)}
          </select>
          <button className="btn small" onClick={() => { setQ(searchInput); loadLog(searchInput, screenFilter) }}>Search</button>
          <button className="btn small" onClick={() => { setSearchInput(''); setScreenFilter(''); setQ(''); loadLog('', '') }}>Reset</button>
        </div>
        {meta?.note && <div className="est" style={{ marginTop: 6 }}>{meta.note}</div>}
        {rows !== null && (
          <table className="list" style={{ marginTop: 8 }}>
            <thead><tr><th>Time</th><th>Screen</th><th>Winner</th><th>Candidates (top)</th><th>Fallback</th><th>Flag</th></tr></thead>
            <tbody>
              {rows.map((d) => (
                <tr key={d.id}>
                  <td className="mono">{fmtHM(d.slot_at)}</td>
                  <td className="mono">{d.screen_id}</td>
                  <td>{d.winner_campaign_id || <span className="muted">house</span>}</td>
                  <td className="mono">{fmtCandidates(d)}</td>
                  <td>{d.fallback ? <span className="chip warn">fallback</span> : ''}</td>
                  <td>
                    {d.override && <span className="chip muted" title={`reason: ${d.override.reason}`}>pinned</span>}
                    {d.exploration && <span className="chip muted" title={d.exploration.reason}>ε-pick</span>}
                  </td>
                </tr>
              ))}
              {rows.length === 0 && <tr><td colSpan={6} className="muted">No decisions match the search.</td></tr>}
            </tbody>
          </table>
        )}
      </div>
      <div className="card">
        <h3>Global rules <span className="chip muted">sm-1.0 constants fixed; global weights are bounded controls</span></h3>
        {rules ? (
          <table className="list">
            <thead><tr><th>Rule</th><th>Value</th><th>Range</th><th>Effect</th></tr></thead>
            <tbody>
              <tr>
                <td>Competitor separation (min)</td>
                <td className="mono">{Number(rules.competitor_gap_min).toFixed(1)}</td>
                <td>0–1440</td>
                <td>different campaigns of one advertiser stay at least this many minutes apart on a screen</td>
                <td colSpan={0} style={{ display: 'none' }} />
                <td rowSpan={3} style={{ verticalAlign: 'top' }}>
                  <button className="btn small primary" onClick={() => save(rules)}>Save all</button>
                  {savedMsg && <div className="est" style={{ maxWidth: 180, marginTop: 6 }}>{savedMsg}</div>}
                </td>
              </tr>
              <tr>
                <td>Frequency window (min)</td>
                <td className="mono">{Number(rules.frequency_window_min).toFixed(0)}</td>
                <td>5–480</td>
                <td>per-screen frequency cap window (counts repeats of the same campaign)</td>
              </tr>
              <tr>
                <td>Exploration ε</td>
                <td className="mono">{Number(rules.exploration_epsilon).toFixed(3)}</td>
                <td>0–0.25</td>
                <td>0.0 = pure highest score (worked-example preset); &gt;0 = deterministic ε-greedy decoy pick, logged as ε-pick</td>
              </tr>
              <tr>
                <td>Audience-fit weight</td>
                <td className="mono">{Number(rules.audience_weight).toFixed(3)}</td>
                <td>0–2</td>
                <td>scales the audience-match exponent; 1.0 preserves the worked example</td>
              </tr>
              <tr>
                <td>Context/boost weight</td>
                <td className="mono">{Number(rules.context_weight).toFixed(3)}</td>
                <td>0–2</td>
                <td>scales delay/boarding/festival context response; 1.0 preserves the worked example</td>
              </tr>
            </tbody>
          </table>
        ) : <div className="est">loading rule config…</div>}
        <div className="row" style={{ marginTop: 8 }}>
          {rules && <>
            <label className="chip muted">competitor gap
              <input type="range" min={0} max={1440} step={5} value={rules.competitor_gap_min}
                     onChange={(e) => setRules({ ...rules, competitor_gap_min: Number(e.target.value) })} />
              {Number(rules.competitor_gap_min).toFixed(0)} min
            </label>
            <label className="chip muted">frequency window
              <input type="range" min={5} max={480} step={5} value={rules.frequency_window_min}
                     onChange={(e) => setRules({ ...rules, frequency_window_min: Number(e.target.value) })} />
              {Number(rules.frequency_window_min).toFixed(0)} min
            </label>
            <label className="chip muted">exploration ε
              <input type="range" min={0} max={0.25} step={0.005} value={rules.exploration_epsilon}
                     onChange={(e) => setRules({ ...rules, exploration_epsilon: Number(e.target.value) })} />
              {Number(rules.exploration_epsilon).toFixed(3)}
            </label>
            <label className="chip muted">audience weight
              <input type="range" min={0} max={2} step={0.01} value={rules.audience_weight}
                     onChange={(e) => setRules({ ...rules, audience_weight: Number(e.target.value) })} />
              {Number(rules.audience_weight).toFixed(2)}
            </label>
            <label className="chip muted">context weight
              <input type="range" min={0} max={2} step={0.01} value={rules.context_weight}
                     onChange={(e) => setRules({ ...rules, context_weight: Number(e.target.value) })} />
              {Number(rules.context_weight).toFixed(2)}
            </label>
          </>}
        </div>
        <p className="est">
          Sliders change the live engine's workbook immediately and persist in rule_config for restarts.
          Changing values replans affected zones; ε &gt; 0 must remain eligibility-safe (a decoy is only drawn
          among candidates that already passed every hard rule) and is recorded in the decision log.
        </p>
      </div>
    </>
  )
}

const mediaMoney = (metrics: any, zones: ZoneRow[]) =>
  metrics && zones.length ? '$' + Math.round((metrics.revenue_today / Math.max(1, metrics.plays_today)) * 1000) / 1000 * 1 : '$—'

function MapSvg({ heat, zones, screens, onPick }: {
  heat: boolean; zones: ZoneRow[]; screens: any[]; onPick: (id: string) => void
}) {
  const zoneById = useMemo(() => Object.fromEntries(zones.map((z) => [z.zone_id, z])), [zones])

  const bands = useMemo(() => {
    const out: { zone_id: string; x: number; y: number; w: number; h: number }[] = []
    for (const s of screens) {
      const lay = BAND_LAYOUT[s.zone_id]
      if (!lay) continue
      out.push({
        zone_id: s.zone_id,
        x: 20 + lay.col * 136,
        y: lay.row === 0 ? 44 : 186,
        w: 128, h: 84,
      })
    }
    return out
  }, [screens])

  const dots = useMemo(() => {
    const idx: Record<string, number> = {}
    return screens.map((s) => {
      const lay = BAND_LAYOUT[s.zone_id]
      if (!lay) return null
      const i = idx[s.zone_id] ?? 0
      idx[s.zone_id] = i + 1
      return {
        s,
        x: 20 + lay.col * 136 + 10 + (i % 9) * 13,
        y: (lay.row === 0 ? 44 : 186) + 24 + Math.floor((i % 90) / 9) * 16,
      }
    }).filter(Boolean) as { s: any; x: number; y: number }[]
  }, [screens])

  const heatCol = (zid: string) => {
    const z: ZoneRow | undefined = zoneById[zid]
    if (!z) return 'transparent'
    const p = z.passenger_count
    return p > 260 ? 'var(--heat3)' : p > 140 ? 'var(--heat2)' : p > 40 ? 'var(--heat1)' : 'var(--heat0)'
  }

  const seen = new Set<string>()
  return (
    <svg viewBox="0 0 1110 300" role="img" aria-label="MQI terminal map, screens and presence heat">
      <rect x="10" y="10" width="1090" height="130" rx="18" fill="rgba(127,160,210,0.07)" stroke="var(--panel-line)" />
      <rect x="10" y="160" width="1090" height="130" rx="18" fill="rgba(127,160,210,0.07)" stroke="var(--panel-line)" />
      <text x="24" y="34" fontSize="13" fontWeight="800" fill="var(--ink)">T1 — Domestic</text>
      <text x="24" y="184" fontSize="13" fontWeight="800" fill="var(--ink)">T2 — International</text>

      {bands.filter((b) => (seen.has(b.zone_id) ? false : (seen.add(b.zone_id), true))).map((b) => (
        <rect key={b.zone_id} x={b.x} y={b.y} width={b.w} height={b.h} rx="10"
          fill={heat ? heatCol(b.zone_id) : 'transparent'} opacity="0.6" stroke={heat ? 'none' : 'var(--panel-line)'} />
      ))}

      {dots.map(({ s, x, y }) => {
        const z = zoneById[s.zone_id] as ZoneRow | undefined
        return (
          <g key={s.id} className="mapdot" tabIndex={0} role="button" onClick={() => onPick(s.id)}
            onKeyDown={(e) => e.key === 'Enter' && onPick(s.id)}
            aria-label={`screen ${s.id}, ${s.zone_id}, ${s.online ? 'online' : 'offline'}`}>
            <title>{`${s.id} · ${s.zone_id} · ${s.online ? 'online' : 'OFFLINE'} · ${z ? z.passenger_count : 0} pax nearby`}</title>
            <circle cx={x} cy={y} r="4.5" fill={s.online ? 'var(--accent)' : 'var(--bad-ink)'}
              stroke={s.current_slot && !s.current_slot.fallback ? 'var(--good)' : 'transparent'} strokeWidth="2" />
          </g>
        )
      })}
      <text x="24" y="296" fontSize="11" fill="var(--ink-dim)">dot = screen · blue online / red offline · green ring = active paid slot · band fill = live presence heat (5-min window)</text>
    </svg>
  )
}

function ScreenInspector({ screenId, onClose }: { screenId: string; onClose: () => void }) {
  const slot = useStore((s) => s.slots[screenId])
  const [busy, setBusy] = useState(false)
  return (
    <div className="card" style={{ borderColor: 'var(--accent)' }}>
      <div className="row" style={{ marginBottom: 8 }}>
        <strong>Screen {screenId}</strong>
        <div className="spacer" />
        <button className="btn small" onClick={async () => { setBusy(true); await api.screenOnline(screenId, false); setBusy(false) }} disabled={busy}>Take offline</button>
        <button className="btn small" onClick={async () => { setBusy(true); await api.screenOnline(screenId, true); setBusy(false) }} disabled={busy}>Bring online</button>
        <button className="btn small" onClick={onClose}>Close</button>
      </div>
      {slot ? (
        <div className="mono" style={{ fontSize: 12 }}>
          <div>slot {slot.slot_id} @ {fmtHM(slot.at)} · <b>{slot.campaign_id ?? 'house'}</b> — {slot.campaign_name} · est. viewers {slot.est_viewers}</div>
          {slot.creative && <div>“{slot.creative.headline_en}”{slot.creative.fallback ? ' · house fill' : ''}</div>}
          {slot.promo && <div>promo {slot.promo.code ?? slot.promo.token}</div>}
          {slot.why?.top_candidates && (
            <ul style={{ margin: '8px 0 0 16px' }}>
              {slot.why.top_candidates.map((c) => (
                <li key={c.campaign_id} style={c.eligible ? undefined : { opacity: 0.55 }}>
                  {c.campaign_id} — score {c.score.toFixed(2)} · match {(c.match * 100).toFixed(0)}% · boost ×{c.boost}{c.eligible ? '' : ` · filtered: ${c.reasons.join(', ')}`}{c.pinned ? ' · PINNED' : ''}
                </li>
              ))}
            </ul>
          )}
        </div>
      ) : (
        <div className="est">no slot yet — first slot arrives on the next 15 s boundary (or after an injection)</div>
      )}
    </div>
  )
}

function MasterData() {
  const kinds = ['vendors', 'outlets', 'airlines', 'terminals', 'zones', 'gates', 'screens']
  const [tab, setTab] = useState('screens')
  const [items, setItems] = useState<{ id: string; data: any }[]>([])
  const [selected, setSelected] = useState<string | null>(null)
  const [entityId, setEntityId] = useState('')
  const [json, setJson] = useState('{}')
  const [msg, setMsg] = useState('')
  const load = () => api.masterData(tab).then((j) => { setItems(j.items); setSelected(null); setEntityId(''); setJson('{}') }).catch((e) => setMsg(String(e)))
  useEffect(() => { load() }, [tab])
  const select = (row: { id: string; data: any }) => { setSelected(row.id); setEntityId(row.id); setJson(JSON.stringify(row.data, null, 2)); setMsg('') }
  const save = async () => {
    try {
      const data = JSON.parse(json)
      if (!entityId.trim()) throw new Error('id is required')
      if (selected) await api.updateMasterData(tab, selected, { id: selected, data })
      else await api.createMasterData(tab, { id: entityId.trim(), data })
      setMsg(`${tab}/${entityId} saved`); await load()
    } catch (e: any) { setMsg(e?.message || 'data must be valid JSON') }
  }
  const remove = async () => {
    if (!selected || !window.confirm(`Delete ${tab}/${selected}?`)) return
    try { await api.deleteMasterData(tab, selected); setMsg(`${tab}/${selected} deleted`); await load() }
    catch (e: any) { setMsg(e?.message || String(e)) }
  }
  return (
    <div className="card">
      <nav className="tabs" style={{ marginBottom: 12 }}>
        {kinds.map((t) => (
          <button key={t} className={tab === t ? 'on' : ''} onClick={() => setTab(t)}>{t}</button>
        ))}
      </nav>
      <div className="master-data-layout">
        <div>
          <div className="row" style={{ justifyContent: 'space-between', marginBottom: 8 }}>
            <strong>{items.length} {tab}</strong>
            <button className="btn small" onClick={() => { setSelected(null); setEntityId(''); setJson('{}'); setMsg('new record') }}>＋ New</button>
          </div>
          <table className="list">
            <thead><tr><th>ID</th><th>Summary</th></tr></thead>
            <tbody>{items.slice(0, 80).map((row) => (
              <tr key={row.id} onClick={() => select(row)} style={{ cursor: 'pointer', background: selected === row.id ? 'var(--bg-soft)' : undefined }}>
                <td className="mono">{row.id}</td><td>{row.data.name ?? row.data.kind ?? row.data.terminal ?? 'platform record'}</td>
              </tr>
            ))}</tbody>
          </table>
        </div>
        <div className="card" style={{ margin: 0 }}>
          <h3>{selected ? `Edit ${selected}` : `Create ${tab.slice(0, -1) || tab}`}</h3>
          <label className="est" htmlFor="master-id">Identifier</label>
          <input id="master-id" className="input mono" value={entityId} disabled={!!selected} onChange={(e) => setEntityId(e.target.value)} placeholder="stable-id" />
          <label className="est" htmlFor="master-json" style={{ marginTop: 8 }}>Fields (JSON)</label>
          <textarea id="master-json" className="input mono" rows={12} value={json} onChange={(e) => setJson(e.target.value)} />
          <div className="row" style={{ marginTop: 8 }}>
            <button className="btn small primary" onClick={save}>Save</button>
            {selected && <button className="btn small danger" onClick={remove}>Delete</button>}
          </div>
          {msg && <div className="est" style={{ marginTop: 8 }}>{msg}</div>}
        </div>
      </div>
    </div>
  )
}
