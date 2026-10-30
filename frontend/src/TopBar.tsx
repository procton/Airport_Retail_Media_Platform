/** Shared controls (AGENTS §7 MUST): play/pause, speed, jump, inject delay /
    gate change / screen offline, reset — visible in every role view. */
import { useEffect, useRef, useState } from 'react'
import { api, fmtTime } from './api'
import { AIRLINES, RETAILERS, useStore } from './store'
import type { Role } from './store'

const ROLES: { id: Role; label: string }[] = [
  { id: 'admin', label: 'Platform Admin' },
  { id: 'retailer', label: 'Retailer' },
  { id: 'media', label: 'Media Manager' },
  { id: 'airline', label: 'Airline Rep' },
  { id: 'screen', label: 'Passenger Screen' },
]

export default function TopBar() {
  const { role, setRole, theme, control, connected, airlineId, setAirline, retailerId, setRetailer, split, setSplit, screens, branding } =
    useStore()
  const [jumpOpen, setJumpOpen] = useState(false)
  const [injectOpen, setInjectOpen] = useState(false)
  const [offlineScreenId, setOfflineScreenId] = useState('')
  const jumpRef = useRef<HTMLInputElement>(null)

  useEffect(() => { if (jumpOpen) jumpRef.current?.focus() }, [jumpOpen])
  const defaultOfflineScreenId = screens.find((s) => s.gate === '42')?.id ?? screens[0]?.id ?? ''
  const outageTarget = offlineScreenId || defaultOfflineScreenId

  const speed = control?.speed ?? 1
  const playing = control?.playing ?? true

  const inject = async (flight: string, kind: string, minutes: number, gate?: string) => {
    try { await api.injectFlightEvent(flight, kind, minutes, gate) } catch (e) { alert(String(e)) }
  }

  return (
    <header className="topbar" data-testid="topbar">
      <div className="brand">
        <BrandMark value={branding.logo} />
        {branding.name} <small>Retail Media · MQI</small>
      </div>

      <nav className="tabs" aria-label="Role switcher">
        {ROLES.map((r) => (
          <button key={r.id} className={role === r.id ? 'on' : ''} onClick={() => setRole(r.id)}>{r.label}</button>
        ))}
      </nav>

      {role === 'retailer' && (
        <select value={retailerId} onChange={(e) => setRetailer(e.target.value)} aria-label="Retailer company">
          {RETAILERS.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
        </select>
      )}
      {role === 'airline' && (
        <select value={airlineId} onChange={(e) => setAirline(e.target.value)} aria-label="Airline company">
          {AIRLINES.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
        </select>
      )}

      <div className="spacer" />

      <div className={'clock' + (!playing ? ' paused' : '')} title="Backend-owned simulation clock (shared by all views)">
        <span className={'dot' + (playing ? '' : ' paused')} aria-hidden />
        <span data-testid="simclock">{fmtTime(control?.at)}</span>
        <span className="run">{control?.day} · {speed}x · {connected ? 'live' : 'reconnecting…'}</span>
      </div>

      <button className={'btn small' + (playing ? ' active' : '')} onClick={() => api.setTransport(!playing)}>
        {playing ? '⏸ Pause' : '▶ Play'}
      </button>
      <div className="seg" role="group" aria-label="Simulation speed">
        {[1, 10, 60].map((s) => (
          <button key={s} className={speed === s ? 'on' : ''} onClick={() => api.setTransport(playing, s)}>{s}x</button>
        ))}
      </div>

      <button className="btn small" onClick={() => setJumpOpen(!jumpOpen)}>⏱ Jump</button>
      <button className="btn small" onClick={() => setInjectOpen(!injectOpen)}>⚡ Inject</button>
      <button className="btn small" onClick={() => setSplit(!split)} title="Passenger screen beside any dashboard">
        {split ? '↔ Exit split' : '↔ Split'}
      </button>

      {jumpOpen && (
        <div className="row">
          <input
            ref={jumpRef} id="jump-at" className="input mono" placeholder="2026-10-14T14:10:00Z"
            onKeyDown={(e) => { if (e.key === 'Enter' && jumpRef.current?.value) { api.jump(jumpRef.current.value); setJumpOpen(false) } }}
          />
          <button className="btn small primary" onClick={() => { if (jumpRef.current?.value) { api.jump(jumpRef.current.value); setJumpOpen(false) } }}>
            Jump to time
          </button>
        </div>
      )}

      {injectOpen && (
        <div className="row" style={{ background: 'var(--bg-soft)', borderRadius: 12, padding: '6px 10px' }}>
          <select id="inject-flight" className="input mono" defaultValue="wx:XY501">
            <option value="wx:XY501">XY501 → DXB (gate 42)</option>
            <option value="wx:ZQ88">ZQ88 → SMG (gate 43)</option>
            <option value="aodb:100180">XH960 (CSV 100180)</option>
          </select>
          <select id="inject-kind" className="input" defaultValue="delay">
            <option value="delay">Delay</option>
            <option value="gate_change">Gate change</option>
            <option value="cancel">Cancel</option>
          </select>
          <input id="inject-min" className="input mono" type="number" defaultValue={45} style={{ width: 70 }} min={0} max={300} />
          <input id="inject-gate" className="input mono" placeholder="gate 41" style={{ width: 82 }} />
          <button className="btn small primary" onClick={() => {
            const f = (document.getElementById('inject-flight') as HTMLSelectElement).value
            const k = (document.getElementById('inject-kind') as HTMLSelectElement).value
            const m = Number((document.getElementById('inject-min') as HTMLInputElement).value || 0)
            const g = (document.getElementById('inject-gate') as HTMLInputElement).value || undefined
            inject(f, k, m, g)
          }}>Apply</button>
          <select className="input mono" aria-label="Screen outage target" value={outageTarget} onChange={(e) => setOfflineScreenId(e.target.value)}>
            {screens.slice(0, 60).map((s) => <option key={s.id} value={s.id}>{s.id} · gate {s.gate ?? '—'}</option>)}
          </select>
          <button className="btn small danger" disabled={!outageTarget} onClick={() => api.screenOnline(outageTarget, false)}>Screen offline</button>
          <button className="btn small" disabled={!outageTarget} onClick={() => api.screenOnline(outageTarget, true)}>Screen online</button>
          <button className="btn small danger" onClick={() => api.reset(true)}>↺ Reset day</button>
        </div>
      )}

      {theme === 'dark' ? <span className="chip muted">control-room</span> : <span className="chip muted">business view</span>}
    </header>
  )
}

function BrandMark({ value }: { value: string }) {
  const image = /^(https?:|data:|\/)/.test(value)
  return image ? <img className="mark" src={value} alt="brand logo" /> : <div className="mark">{value || 'M'}</div>
}
