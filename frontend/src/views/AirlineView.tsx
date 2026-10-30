/** Airline Representative — my flights, gate messaging, delay goodwill (§16). */
import { useEffect, useMemo, useState } from 'react'
import { api, fmtHM } from '../api'
import { useStore } from '../store'

type Tab = 'flights' | 'messages' | 'goodwill'

export default function AirlineView() {
  const { airlineId, flights, slots, campaigns, control } = useStore()
  const [tab, setTab] = useState<Tab>('flights')
  const [tidy, setTidy] = useState(0)

  useEffect(() => useStore.subscribe(() => setTidy((t) => t + 1)), [])

  const mine = useMemo(() => flights.filter((f) => f.airline_iata === airlineId).sort((a, b) => a.effective_std.localeCompare(b.effective_std)), [flights, airlineId, tidy])

  // gates of my delayed departures (for goodwill checks)
  const delayedGates = useMemo(() => mine.filter((f) => f.delay_min >= 15 && f.status !== 'GONE').map((f) => f.gate).filter(Boolean) as string[], [mine])


  const ads = useMemo(() => {
    const out: { s: any; f: any }[] = []
    for (const s of Object.values(slots)) {
      if (!s.why?.profile) continue
      const f = mine.find((x) => x.gate && zoneHasGate(s.zone_id, x.gate))
      if (f) out.push({ s, f })
    }
    return out.slice(0, 8)
  }, [slots, mine, tidy])

  return (
    <div className="grid">
      <div className="row" style={{ margin: '2px 0' }}>
        <span className="chip">{airlineId}</span>
        <nav className="tabs">
          {(['flights', 'messages', 'goodwill'] as Tab[]).map((t) => (
            <button key={t} className={tab === t ? 'on' : ''} onClick={() => setTab(t)}>
              {t === 'flights' ? 'My flights' : t === 'messages' ? 'Gate messaging' : 'Delay goodwill'}
            </button>
          ))}
        </nav>
        <div className="spacer" />
        <span className="chip muted">{control?.day}</span>
      </div>

      {tab === 'flights' && (
        <div className="card">
          <h3>Departures today <span className="live">LIVE</span></h3>
          <table className="list">
            <thead><tr><th>Flight</th><th>Dest</th><th>Gate</th><th>STD</th><th>Status</th><th>Load</th><th>Actions</th></tr></thead>
            <tbody>
              {mine.filter((f) => f.direction === 'D').slice(0, 30).map((f) => (
                <tr key={f.id} className={f.delay_min >= 15 ? 'hl' : ''}>
                  <td><b>{f.designator}</b><br /><small className="muted mono">{f.aircraft_type ?? ''} {f.aircraft_reg ?? ''}</small></td>
                  <td>{f.destination}</td>
                  <td className="mono">{f.gate ?? '—'}</td>
                  <td className="mono">{fmtHM(f.effective_std)}</td>
                  <td>
                    <span className={'chip ' + statusChip(f.status)}>{f.status}</span>
                    {f.delay_min > 0 && <span className="chip warn">+{f.delay_min}′</span>}
                  </td>
                  <td className="mono">{f.seats ? Math.round((f.pax / f.seats) * 100) : '—'}%</td>
                  <td>
                    <button className="btn small" onClick={() => api.injectFlightEvent(f.id, 'delay', 45)}>Inject +45′</button>
                    <button className="btn small" style={{ marginLeft: 6 }} onClick={() => api.injectFlightEvent(f.id, 'gate_change', 0, '24')}>Move gate</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === 'messages' && (
        <>
          <div className="card">
            <h3>Ads at my gates <span className="live">LIVE</span></h3>
            {ads.length === 0 ? <section className="empty">No screens in my-gate zones are currently in view of this run slot cache.</section> : (
              <table className="list">
                <thead><tr><th>Screen</th><th>Gate/flights</th><th>Playing</th><th>Audience</th><th>Why / candidates</th></tr></thead>
                <tbody>
                  {ads.map(({ s, f }) => (
                    <tr key={s.slot_id + s.screen_id}>
                      <td className="mono">{s.screen_id}</td>
                      <td><b>{f.designator}</b> gate {f.gate} · {f.destination} · {fmtHM(f.effective_std)}{(f.delay_min > 0) ? <span className="chip warn">+{f.delay_min}′</span> : null}</td>
                      <td><b>{s.campaign_id ?? 'house'}</b> — {s.campaign_name}</td>
                      <td className="mono">{s.why.profile.crowd} pax · dwell {Math.round(s.why.profile.dwell_min)}′ · intl {(s.why.profile.intl_share * 100).toFixed(0)}%</td>
                      <td>
                        <small>{s.why.winning.rule}{s.fallback ? ' (house fill)' : ''}</small>
                        <div className="est">{(s.why.top_candidates || []).slice(0, 3).map((c: any) => (
                          <div key={c.campaign_id}>
                            <span className={c.eligible ? 'good' : 'bad'}>{c.eligible ? 'eligible' : 'filtered'}</span>{' '}
                            {c.campaign_id} · match {(c.match * 100).toFixed(0)}% · score {c.score.toFixed(2)}
                            {!c.eligible && c.reasons?.length ? ` · ${c.reasons.join(', ')}` : ''}
                          </div>
                        ))}</div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
          <div className="card">
            <h3>Sponsored-content candidates (airline co-op campaigns)</h3>
            <table className="list">
              <thead><tr><th>Campaign</th><th>Status</th><th>Trigger</th><th>Zones</th><th>Partner</th></tr></thead>
              <tbody>
                {campaigns.filter((c) => c.airline_iata === airlineId || c.trigger === 'boarding').map((c) => (
                  <tr key={c.id}>
                    <td>{c.name}</td><td><span className="chip">{c.status}</span></td>
                    <td><span className="chip">{c.trigger} {c.trigger === 'delay' ? `≥${c.trigger_delay_min}′` : ''}</span></td>
                    <td><small>{c.zone_ids.join(', ')}</small></td>
                    <td className="mono">{c.advertiser_id}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {tab === 'goodwill' && (
        <>
          <div className="card">
            <h3>Delay goodwill policy (configurable threshold · simulated accounting)</h3>
            <div className="row">
              <label htmlFor="thr" className="est">Voucher pathway at delay ≥</label>
              <select id="thr" className="input mono" defaultValue={45}>
                {[20, 30, 45, 60, 90].map((v) => <option key={v} value={v}>{v}′</option>)}
              </select>
              <span className="chip">partner outlet: Kestrel Coffee & duty-free</span>
            </div>
            <p className="est">When a flight arrival/departure passes the threshold, a co-funded F&B voucher creative wins gate screens in the boarding window; costs split airline/retailer in platform accounting only.</p>
          </div>
          <div className="card">
            <h3>My delayed departures right now</h3>
            {delayedGates.length === 0 ? <section className="empty">No delayed legs at the moment. Inject a delay on any flight and the goodwill creative chain triggers at that gate.</section> : (
              <ul>{delayedGates.map((g) => <li key={g}>gate {g}</li>)}</ul>
            )}
          </div>
        </>
      )}
    </div>
  )
}

const statusChip = (s: string) =>
  s === 'BOARDING' ? 'good' : s === 'GATE_CLOSED' || s === 'CANCELLED' ? 'bad' : s === 'GONE' ? 'muted' : ''

const zoneHasGate = (zoneId: string, gate: string) => {
  // zone id like T2-5-gates covering gates 50–59; also T2-1
  const m = /^(T\d)-(A|B|C|\d+|BUS)-/.exec(zoneId.toUpperCase())
  if (!m) return false
  const [, term, key] = m
  if (key === 'BUS') return gate.startsWith(term.replace('T', 'T'))
  if (['A', 'B', 'C'].includes(key)) return gate.startsWith(key)
  const z = parseInt(key, 10)
  const g = parseInt(gate, 10)
  if (Number.isNaN(z) || Number.isNaN(g)) return false
  return g >= z * 10 && g < z * 10 + 10
}
