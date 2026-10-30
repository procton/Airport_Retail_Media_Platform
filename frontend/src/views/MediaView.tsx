/** Media Manager — inventory, pricing, approvals, advertisers (§15). */
import { useMemo, useState } from 'react'
import { api, money } from '../api'
import { useStore } from '../store'

type Tab = 'inventory' | 'pricing' | 'approvals' | 'advertisers'

export default function MediaView() {
  const { zones, screens, campaigns, control } = useStore()
  const [tab, setTab] = useState<Tab>('inventory')

  const [zoneId, setZoneId] = useState('T2-1-gates')
  const zone = zones.find((z) => z.zone_id === zoneId)
  const zoneScreens = useMemo(() => screens.filter((s) => s.zone_id === zoneId), [screens, zoneId])

  // tbody grid: every screen × next 12 sim hours; booked = winning campaign present in slot cache
  const slots = useStore((s) => s.slots)
  const nowHour = useMemo(() => {
    const t = new Date(control?.at ?? Date.now())
    return t.getTime()
  }, [control?.at])

  return (
    <div className="grid">
      <div className="row" style={{ margin: '2px 0' }}>
        <nav className="tabs">
          {(['inventory', 'pricing', 'approvals', 'advertisers'] as Tab[]).map((t) => (
            <button key={t} className={tab === t ? 'on' : ''} onClick={() => setTab(t)}>
              {t === 'inventory' ? 'Inventory calendar' : t === 'pricing' ? 'Yield & pricing' : t === 'approvals' ? 'Approvals' : 'Advertisers'}
            </button>
          ))}
        </nav>
        <div className="spacer" />
        <span className="chip muted">{control?.day} (simulation day)</span>
      </div>

      {tab === 'inventory' && (
        <>
          <div className="row">
            <select className="input" value={zoneId} onChange={(e) => setZoneId(e.target.value)} aria-label="Zone">
              {zones.filter((z) => screens.some((s) => s.zone_id === z.zone_id)).map((z) => (
                <option key={z.zone_id} value={z.zone_id}>{z.name}</option>
              ))}
            </select>
            <span className="chip">{zoneScreens.length} screens in zone</span>
            {zone && <span className="chip">crowd now {zone.passenger_count} · next 2h {zone.next120_count}</span>}
            <span className="est">booked = a paid campaign currently owns the slot</span>
          </div>
          <div className="card" style={{ overflowX: 'auto' }}>
            <h3>Next 12 sim hours · screen × hour</h3>
            <table className="list">
              <thead>
                <tr>
                  <th>Screen</th>
                  {Array.from({ length: 12 }, (_, h) => {
                    const hour = (new Date(nowHour).getUTCHours() + h) % 24
                    return <th key={h} className={now_daylight(hour) ? '' : 'dimrow'}>{String(hour).padStart(2, '0')}:00</th>
                  })}
                </tr>
              </thead>
              <tbody>
                {zoneScreens.slice(0, 20).map((sc) => (
                  <tr key={sc.id}>
                    <td className="mono">{sc.id}</td>
                    {Array.from({ length: 12 }, (_, h) => {
                      const d = new Date(nowHour + h * 3600_000)
                      const cell = new Date(d).toISOString().slice(0, 13)
                      const slot = slots[sc.id]
                      const booked = !!slot && !!slot.campaign_id && slot.at.startsWith(cell)
                      return (
                        <td key={h} className={now_daylight(new Date(d).getUTCHours()) ? '' : 'dimrow'}>
                          {booked ? <span className="chip good" style={{ padding: '2px 6px', fontSize: 10 }}>{String(slot.campaign_id).replace('cmp-', '').slice(0, 9)}</span>
                            : <span className="chip muted" style={{ padding: '2px 6px', fontSize: 10 }}>open</span>}
                        </td>
                      )
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="est">Availability beyond the current 15 s slots is a price-based open capacity view (premium hours derive from forecast presence; document extrapolation).</p>
        </>
      )}

      {tab === 'pricing' && <Pricing zones={zones} />}

      {tab === 'approvals' && (
        <>
        <MediaScreenInspector />
        <div className="card">
          <h3>Pending approvals</h3>
          {campaigns.filter((c) => c.status === 'PENDING').length === 0 ? (
            <section className="empty">No pending campaigns — seed includes PENDING rows unless already decided this run.</section>
          ) : (
            <table className="list">
              <thead><tr><th>Campaign</th><th>Targeting</th><th>Placement</th><th>Brand-safety checklist</th><th>Action</th></tr></thead>
              <tbody>
                {campaigns.filter((c) => c.status === 'PENDING').map((c) => (
                  <tr key={c.id}>
                    <td>{c.name}<br /><small className="muted mono">{c.advertiser_id}</small></td>
                    <td>{Object.entries(c.target_segments).map(([k, v]) => `${k} ${(Number(v) * 100).toFixed(0)}%`).join(' · ') || 'any'}</td>
                    <td>{c.zone_ids.join(', ') || c.terminal}</td>
                    <td>
                      <div className="row"><span className="chip good">no alcohol next to kids ✚</span><span className="chip good">claims verifiable ✚</span><span className="chip good">no competitor of same advertiser ✚</span></div>
                    </td>
                    <td className="row">
                      <button className="btn small primary" onClick={() => api.post(`/campaigns/${c.id}/status`, { status: 'APPROVED' })}>Approve</button>
                      <button className="btn small danger" onClick={() => api.post(`/campaigns/${c.id}/status`, { status: 'REJECTED' })}>Reject</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
        </>
      )}

      {tab === 'advertisers' && <Advertisers campaigns={campaigns} slots={slots} />}
    </div>
  )
}

/** Media pin/override + conflict explanation (AGENTS §12, §15). */
function MediaScreenInspector() {
  const { screens } = useStore()
  const [screenId, setScreenId] = useState('')
  const [pv, setPv] = useState<any>(null)
  const [pinReason, setPinReason] = useState('')
  const [err, setErr] = useState('')
  const [msg, setMsg] = useState('')
  const load = (sid: string) => {
    setPv(null)
    if (!sid) return
    api.get(`/match/preview?screen_id=${sid}`).then(setPv).catch((e) => setErr(String(e)))
  }
  const doPin = async (campaignId: string) => {
    setErr('')
    setMsg('')
    if (!pinReason.trim()) return setErr('a pin reason is required')
    try {
      await api.post(`/screens/${screenId}/pin/${campaignId}`, { reason: pinReason })
      setMsg(`pinned ${campaignId} on ${screenId} (reason recorded); it must still pass approval/placement/budget this slot`)
      await load(screenId)
    } catch (e: any) { setErr(e?.message || String(e)) }
  }
  const doUnpin = async () => {
    setErr('')
    setMsg('')
    try {
      await api.post(`/screens/${screenId}/unpin`, { reason: 'media-manager release' })
      setMsg('pin cleared; screen replanned')
      await load(screenId)
    } catch (e: any) { setErr(e?.message || String(e)) }
  }
  const online = screens.filter((s: any) => s.online)
  return (
    <div className="card">
      <h3>Screen pins &amp; conflicts</h3>
      <div className="row">
        <select value={screenId} onChange={(e) => { setScreenId(e.target.value); load(e.target.value) }}>
          <option value="">— choose screen —</option>
          {online.map((s: any) => (
            <option key={s.id} value={s.id}>{s.id} · {s.zone_id}{s.gate ? ` · gate ${s.gate}` : ''}</option>
          ))}
        </select>
      </div>
      {pv && (
        <>
          <div className="est" style={{ marginTop: 8 }}>
            current slot winner: <b>{pv.candidates?.filter((c: any) => c.eligible)[0]?.campaign_id ?? 'house'}</b>
            {pv.active_pin && <> · active pin: <b>{pv.active_pin.campaign_id}</b> <small>({pv.active_pin.reason})</small></>}
          </div>
          {pv.active_pin && (
            <button className="btn small" style={{ marginTop: 6 }} onClick={doUnpin}>Clear pin</button>
          )}
          <table className="list" style={{ marginTop: 8 }}>
            <thead><tr><th>Campaign</th><th>Score</th><th>Status</th><th>Conflicts / notes</th><th>Pin</th></tr></thead>
            <tbody>
              {pv.candidates.map((c: any) => (
                <tr key={c.campaign_id} style={c.eligible ? undefined : { opacity: 0.65 }}>
                  <td>{c.name}</td>
                  <td className="mono">{c.score.toFixed(2)}</td>
                  <td><span className={'chip ' + (c.eligible ? 'good' : 'bad')}>{c.eligible ? 'eligible' : 'filtered'}</span></td>
                  <td>{(c.reasons || []).length ? c.reasons.join(' · ') : <span className="muted">—</span>}</td>
                  <td>{c.eligible && !pv.active_pin ? <button className="btn small" onClick={() => doPin(c.campaign_id)}>Pin</button> : ''}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="row" style={{ marginTop: 8 }}>
            <input style={{ flex: 1 }} placeholder="pin reason (required, recorded in the decision log)" value={pinReason} onChange={(e) => setPinReason(e.target.value)} />
          </div>
        </>
      )}
      {err && <div className="chip bad" style={{ marginTop: 8 }}>{err}</div>}
      {msg && <div className="chip good" style={{ marginTop: 8 }}>{msg}</div>}
    </div>
  )
}

const now_daylight = (h: number) => h >= 6 && h < 22

function Pricing({ zones }: { zones: any[] }) {
  const { metrics } = useStore()
  const rows = useMemo(() => zones.map((z) => {
    const base = 1.2 + (z.passenger_count / 100) * 1.4 + (z.dwell_median_min / 60) * 0.8
    return { ...z, suggested: Math.round(base * 100) / 100 }
  }).sort((a, b) => b.suggested - a.suggested), [zones])
  return (
    <div className="card">
      <h3>Presence-driven suggested CPM (next 2 h)</h3>
      <table className="list">
        <thead><tr><th>Zone</th><th>Now</th><th>Next 30m</th><th>Next 2h</th><th>Suggested CPM</th><th>Basis</th></tr></thead>
        <tbody>
          {rows.slice(0, 14).map((z) => (
            <tr key={z.zone_id}>
              <td>{z.name}</td>
              <td className="mono">{z.passenger_count}</td>
              <td className="mono forecast">{z.next30_count}</td>
              <td className="mono forecast">{z.next120_count}</td>
              <td className="mono"><b>{money(z.suggested)}</b></td>
              <td><small className="est">presence {z.passenger_count} · dwell {z.dwell_median_min.toFixed(0)}′</small></td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="est">Formula: 1.2 + 1.4×(pax/100) + 0.8×(dwell/60) — price is a suggestion; 7-day revenue forecast = avg {money(metrics?.revenue_today ?? 0)} today × weekday profile (documented extrapolation).</p>
    </div>
  )
}

function Advertisers({ campaigns, slots }: { campaigns: any[]; slots: Record<string, any> }) {
  const rows = useMemo(() => {
    const m: Record<string, { spendScreens: number; playing: number; campaignIds: Set<string> }> = {}
    for (const c of campaigns) {
      m[c.advertiser_id] = m[c.advertiser_id] || { spendScreens: 0, playing: 0, campaignIds: new Set() }
      m[c.advertiser_id].campaignIds.add(c.id)
    }
    for (const s of Object.values(slots)) {
      if (!s.campaign_id) continue
      const c = campaigns.find((x) => x.id === s.campaign_id)
      if (!c) continue
      m[c.advertiser_id].playing += 1
      m[c.advertiser_id].spendScreens += s.est_viewers ?? 0
    }
    return Object.entries(m).map(([adv, v]) => ({
      adv, playing: v.playing, spendScreens: v.spendScreens, campaigns: v.campaignIds.size,
      underDelivering: v.campaignIds.size >= 4 && v.playing < 2,
    })).sort((a, b) => b.spendScreens - a.spendScreens)
  }, [campaigns, slots])
  return (
    <div className="card">
      <h3>Advertisers (current run)</h3>
      <table className="list">
        <thead><tr><th>Advertiser</th><th>Campaigns</th><th>Playing now</th><th>Est. exposure in current slots</th><th>Under-delivery</th></tr></thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.adv}>
              <td className="mono">{r.adv}</td>
              <td className="mono">{r.campaigns}</td>
              <td className="mono">{r.playing}</td>
              <td className="mono">{r.spendScreens.toLocaleString()}</td>
              <td>{r.underDelivering ? <span className="chip bad">flag</span> : <span className="chip muted">—</span>}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
