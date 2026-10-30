/** Retailer — outlet KPIs, nearby flow, live match preview, campaigns (§14). */
import { useEffect, useMemo, useState } from 'react'
import { api, fmtHM, pct } from '../api'
import { RETAILERS, useStore } from '../store'

type Tab = 'live' | 'flow' | 'campaigns' | 'codes'

export default function RetailerView() {
  const { retailerId, zones, slots, lastRedemption, campaigns } = useStore()
  const [tab, setTab] = useState<Tab>('live')
  const company = RETAILERS.find((r) => r.id === retailerId)!
  const myCampaigns = useMemo(
    () => campaigns.filter((c) => c.outlet_id.startsWith(outletPrefix(company.kind))),
    [campaigns, company]
  )
  const myZones = useMemo(() => {
    const zs = new Set(myCampaigns.flatMap((c) => c.zone_ids))
    return zones.filter((z) => zs.has(z.zone_id))
  }, [zones, myCampaigns])

  // live outlet activity: redemptions route into the promo's outlet; impressions
  // roll up from current slots of campaigns targeting this outlet
  const myScreensSlots = useMemo(() => {
    const ids = new Set(myCampaigns.map((c) => c.id))
    return Object.values(slots).filter((s) => s.campaign_id && ids.has(s.campaign_id))
  }, [slots, myCampaigns])

  const impressions = myScreensSlots.reduce((a, s) => a + s.est_viewers, 0)
  const lastOutlet = lastRedemption

  return (
    <div className="grid">
      <div className="row" style={{ margin: '2px 0' }}>
        <span className="chip">{company.name}</span>
        <nav className="tabs">
          {(['live', 'flow', 'campaigns', 'codes'] as Tab[]).map((t) => (
            <button key={t} className={tab === t ? 'on' : ''} onClick={() => setTab(t)}>
              {t === 'live' ? 'Live outlet' : t === 'flow' ? 'Nearby flow' : t === 'campaigns' ? 'Campaigns' : 'Promo codes'}
            </button>
          ))}
        </nav>
        <div className="spacer" />
        <span className="chip muted">live demo window</span>
      </div>

      {tab === 'live' && (
        <>
          <div className="grid cols-4">
            <div className="card"><div className="kpi"><span className="v">{impressions.toLocaleString()}</span><span className="l">impressions (current slots, est.)</span></div></div>
            <div className="card"><div className="kpi"><span className="v">{myScreensSlots.length}</span><span className="l">active screens playing your campaigns</span></div></div>
            <div className="card"><div className="kpi"><span className="v">{lastOutlet ? '1' : '0'}</span><span className="l">redemptions (latest run)</span><span className="n">{lastOutlet ? `token …${lastOutlet.token.slice(-6)} @ ${fmtHM(lastOutlet.at)}` : 'scan a QR to trigger one'}</span></div></div>
            <div className="card"><div className="kpi"><span className="v">{myCampaigns.filter((c) => c.status === 'APPROVED').length}</span><span className="l">approved campaigns</span></div></div>
          </div>
          <div className="card">
            <h3>Campaign activity <span className="live">LIVE</span></h3>
            {myCampaigns.length === 0 ? <section className="empty">No campaigns for this company in the seed.</section> : (
              <table className="list">
                <thead><tr><th>Campaign</th><th>Status</th><th>Targeting</th><th>Trigger</th><th>Playing now</th></tr></thead>
                <tbody>
                  {myCampaigns.map((c) => {
                    const live = myScreensSlots.filter((s) => s.campaign_id === c.id)
                    return (
                      <tr key={c.id}>
                        <td>{c.name}<br /><small className="muted mono">{c.id}</small></td>
                        <td><span className={'chip ' + (c.status === 'APPROVED' ? 'good' : c.status === 'PENDING' ? 'warn' : 'muted')}>{c.status}</span></td>
                        <td>{segmentsOf(c)}</td>
                        <td>{c.trigger === 'delay' ? <span className="chip warn">delay ≥ {c.trigger_delay_min}′ ×{c.trigger_boost}</span> : <span className="chip muted">none</span>}</td>
                        <td className="mono">{live.length ? `${live.length} screen(s)` : '—'}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            )}
          </div>
          {myScreensSlots.length > 0 && (
            <div className="card">
              <h3>Now on screens near your outlets</h3>
              <div className="grid cols-3">
                {myScreensSlots.slice(0, 6).map((s) => (
                  <div key={s.slot_id} className="card" style={{ background: 'var(--bg-soft)' }}>
                    <div className="mono" style={{ fontSize: 11 }}>{s.screen_id} · {fmtHM(s.at)}</div>
                    <strong>{s.creative.headline_en}</strong>
                    <div className="est">match {(s.why.profile.crowd)} pax · score of top {s.why.top_candidates[0]?.score.toFixed(2) ?? '—'}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}

      {tab === 'flow' && <NearbyFlow zones={myZones} />}

      {tab === 'campaigns' && (
        <>
          <CampaignPreview myCampaigns={myCampaigns} />
          <CreativeAssistant />
          <RetailerHistory companyKind={company.kind} />
        </>
      )}

      {tab === 'codes' && <PromoCodes campaigns={myCampaigns} />}
    </div>
  )
}

const outletPrefix = (kind: string) => (kind === 'coffee' ? 'out-t2-cafe' : 'out-t2-df')

const segmentsOf = (c: any) => {
  const seg = c.target_segments || {}
  return Object.entries(seg).map(([k, v]) => `${k} ${(Number(v) * 100).toFixed(0)}%`).join(' · ') || 'any crowd'
}

function NearbyFlow({ zones }: { zones: any[] }) {
  if (!zones.length) return <section className="empty card">No zones targeted by your campaigns yet.</section>
  return (
    <>
      <div className="grid cols-2">
        {zones.slice(0, 4).map((z) => (
          <div className="card" key={z.zone_id}>
            <h3>{z.name} <span className="live">LIVE</span></h3>
            <div className="grid cols-2">
              <div><div className="est">now in zone</div><div className="kpi"><span className="v">{z.passenger_count}</span></div></div>
              <div><div className="est">next 2 h (forecast)</div><span className="chip forecast">{z.next120_count} expected</span></div>
            </div>
            <DataBars title="Purpose" items={([['holiday', Number(z.shares?.purpose_holiday ?? 0)], ['business', Number(z.shares?.purpose_business ?? 0)], ['family', Number(z.shares?.party_family_with_children ?? 0)]] as [string, number][])} />
            <DataBars title="Top destinations" items={(z.top_destinations || []).slice(0, 4).map((dw: any) => [String(dw[0]), Number(dw[1])])} max={1} />
            <div className="row" style={{ marginTop: 8 }}>
              <span className="chip">intl share {pct(z.intl_count / Math.max(z.passenger_count, 1), 0)}</span>
              <span className="chip">dwell {Math.round(z.dwell_median_min)}′</span>
              <span className="chip">languages {z.languages?.slice(0, 3).join(', ')}</span>
            </div>
          </div>
        ))}
      </div>
    </>
  )
}

function DataBars({ title, items, max = 1 }: { title: string; items: [string, number][]; max?: number }) {
  return (
    <div style={{ marginTop: 10 }}>
      <div style={{ fontSize: 11, color: 'var(--ink-dim)', fontWeight: 700, textTransform: 'uppercase' }}>{title}</div>
      {items.filter((item) => Number(item[1]) > 0).slice(0, 5).map((item) => (
        <div key={String(item[0])} className="row" style={{ margin: '4px 0' }}>
          <span style={{ width: 90, fontSize: 12 }}>{String(item[0])}</span>
          <div className="bar warm" style={{ flex: 1 }}><i style={{ width: `${Math.min(100, (Number(item[1]) / max) * 100)}%` }} /></div>
          <span className="mono" style={{ width: 44, textAlign: 'right' }}>{(Number(item[1]) * 100).toFixed(0)}%</span>
        </div>
      ))}
    </div>
  )
}

/** Live audience-match preview (§12 retailer transparency). */
function CampaignPreview({ myCampaigns }: { myCampaigns: any[] }) {
  const { zones } = useStore()
  const [zoneId, setZoneId] = useState<string | null>(null)
  const [screenId, setScreenId] = useState<string | null>(null)
  const [preview, setPreview] = useState<any>(null)
  const [err, setErr] = useState('')

  useEffect(() => {
    if (zoneId) return
    api.screens('?zone=T2-1-gates').then((j) => j.screens[0] && setZoneId('T2-1-gates')).catch(() => {})
  }, [zoneId])

  const pickZone = async (zid: string) => {
    setZoneId(zid)
    const j = await api.screens(`?zone=${encodeURIComponent(zid)}`)
    setScreenId(j.screens[0]?.id ?? null)
  }

  useEffect(() => {
    if (!screenId) return
    const run = () => api.matchPreview(screenId).then(setPreview).catch((e) => setErr(String(e)))
    run()
    const iv = setInterval(run, 10000)
    return () => clearInterval(iv)
  }, [screenId])

  const [reco, setReco] = useState<any | null>(null)
  const [recoBusy, setRecoBusy] = useState<string>('')
  const bestTomorrow = async (campaignId: string) => {
    setRecoBusy(campaignId)
    try {
      setReco(await api.recommendSlots(campaignId))
    } finally {
      setRecoBusy('')
    }
  }

  const zoneOpts = useMemo(() => ['T2-1-gates', 'T2-5-gates', 'T2-retail-main', 'T1-A-gates'], [])
  const myZones = useMemo(() => zones.filter((z) => zoneOpts.includes(z.zone_id)), [zones, zoneOpts])

  return (
    <div className="card">
      <h3>Live audience-match preview <span className="live">LIVE 10s</span></h3>
      <div className="row">
        <label htmlFor="prevzone" className="est">Zone</label>
        <select id="prevzone" className="input" value={zoneId ?? ''} onChange={(e) => pickZone(e.target.value)}>
          {myZones.map((z) => <option key={z.zone_id} value={z.zone_id}>{z.name}</option>)}
        </select>
        {preview && (
          <span className="chip">
            {preview.profile.crowd} pax · intl {pct(preview.profile.intl_share, 0)} · dwell {Math.round(preview.profile.dwell_min)}′ · est. {preview.est_viewers_slot} viewers/slot
          </span>
        )}
      </div>
      <div className="row" style={{ marginTop: 8 }}>
        <label htmlFor="besttom" className="est">Forecast tomorrow</label>
        <select id="besttom" className="input" onChange={(e) => e.target.value && bestTomorrow(e.target.value)} value="">
          <option value="">pick a campaign…</option>
          {myCampaigns.filter((c) => c.status === 'APPROVED').map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
        {recoBusy && <span className="chip muted">computing…</span>}
      </div>
      {reco && (
        <div style={{ marginTop: 10 }}>
          <table className="list">
            <thead>
              <tr><th>Rank</th><th>Screen</th><th>Zone</th><th>Hour</th><th>Predicted impressions</th><th>Redemptions</th><th>Audience fit</th><th>Why</th></tr>
            </thead>
            <tbody>
              {reco.items.map((it: any) => (
                <tr key={`${it.screen_id}-${it.hour}`}>
                  <td className="mono">#{it.rank}</td>
                  <td className="mono">{it.screen_id}</td>
                  <td>{it.zone_id}</td>
                  <td className="mono">{it.hour}</td>
                  <td className="mono forecast"><b>{it.predicted_impressions}</b></td>
                  <td className="mono forecast">{it.predicted_redemptions}</td>
                  <td className="mono">{pct(it.audience_fit, 1)}</td>
                  <td><small className="muted">{(it.reasons || []).slice(0, 2).join('; ')}</small></td>
                </tr>
              ))}
              {reco.items.length === 0 && <tr><td colSpan={8} className="muted">No eligible slot forecast for this campaign window.</td></tr>}
            </tbody>
          </table>
          <p className="est" style={{ marginTop: 6 }}>Forecast for simulation day {reco.day} (tomorrow) — {reco.assumptions.slice(0, 3).join(' · ')}</p>
        </div>
      )}
      {err && <div className="chip bad" style={{ marginTop: 8 }}>{err}</div>}
      {preview && (
        <table className="list" style={{ marginTop: 10 }}>
          <thead>
            <tr><th>Campaign</th><th>Match</th><th>Boost</th><th>Score</th><th>Eligible</th><th>Impressions/h</th><th>Redemptions/h</th><th>Reasons</th></tr>
          </thead>
          <tbody>
            {preview.candidates.slice(0, 12).map((c: any) => (
              <tr key={c.campaign_id} className={c.eligible ? '' : 'dimrow'}>
                <td>{c.name}</td>
                <td className="mono">{pct(c.match, 1)}</td>
                <td className="mono">×{c.boost}</td>
                <td className="mono"><b>{c.score.toFixed(2)}</b></td>
                <td>{c.eligible ? <span className="chip good">yes</span> : <span className="chip bad">filtered</span>}</td>
                <td className="mono forecast">{c.est_impressions_per_hour ?? '—'}</td>
                <td className="mono forecast">{c.est_redemptions_per_hour ?? '—'}</td>
                <td><small className="muted">{c.reasons.join('; ') || 'all checks pass'}</small></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <p className="est" style={{ marginTop: 8 }}>{preview?.cv_note}</p>
      <p className="est">Totals for {myCampaigns.length} campaigns; impressions are exposure opportunities, never verified viewers.</p>
    </div>
  )
}

/** Creative assistant (§18 WOW): brief → bilingual offline template draft. */
function CreativeAssistant() {
  const [brief, setBrief] = useState('Festive sweets, 20% off, families flying domestic')
  const [out, setOut] = useState<any>(null)
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const draft = async () => {
    if (!brief.trim()) { setErr('brief is required'); return }
    const product = brief.split(',')[0].trim()
    const discountMatch = brief.match(/(\d+(?:\.\d+)?)\s*%/)
    const discount = discountMatch ? Number(discountMatch[1]) : undefined
    const aud = /famil|child|kids/i.test(brief) ? 'family' : /business|lounge/i.test(brief) ? 'business' : 'any'
    setBusy(true)
    setErr('')
    try {
      setOut(await api.assistCreative({ product, discount_pct: discount, audience: aud, note: brief.trim() }))
    } catch (e: any) {
      setErr(String(e?.message || e))
    } finally { setBusy(false) }
  }
  const c = out?.creative
  return (
    <div className="card">
      <h3>Creative assistant <span className="chip muted">offline AI · template draft</span></h3>
      <div className="row" style={{ flexWrap: 'wrap' }}>
        <textarea className="input" aria-label="creative brief" placeholder="Festive sweets, 20% off, families flying domestic" value={brief} onChange={(e) => setBrief(e.target.value)} rows={2} style={{ minWidth: 320, resize: 'vertical' }} />
        <button className="btn small" onClick={draft} disabled={busy}>Draft ad</button>
        {busy && <span className="chip muted">composing…</span>}
      </div>
      {err && <div className="chip bad" style={{ marginTop: 8 }}>{err}</div>}
      {c && (
        <div className="grid cols-2" style={{ marginTop: 10 }}>
          <div className="card" style={{ background: c.bg, color: c.fg }}>
            <div className="mono" style={{ fontSize: 11, opacity: 0.85 }}>{out.provider} · {c.id}</div>
            <strong style={{ display: 'block', marginTop: 4 }}>{c.headline_en}</strong>
            <div style={{ opacity: 0.95 }}>{c.body_en}</div>
            <div className="chip" style={{ marginTop: 10, color: 'inherit' }}>{c.cta}</div>
            <div className="est" style={{ marginTop: 10 }}>EN → {out.lang[1]}</div>
          </div>
          <div className="card" style={{ background: c.bg, color: c.fg }}>
            <div className="mono" style={{ fontSize: 11, opacity: 0.85 }}>{out.lang[0]} (2nd language)</div>
            <strong style={{ display: 'block', marginTop: 4 }}>{c.headline_alt}</strong>
            <div style={{ opacity: 0.95 }}>{c.body_alt}</div>
            <div className="est" style={{ marginTop: 10, opacity: 0.8 }}>{out.notes}</div>
          </div>
        </div>
      )}
    </div>
  )
}

function PromoCodes({ campaigns }: { campaigns: any[] }) {
  // codes rendered on screens of the retailer's campaigns (read from live slots)
  const sources = useStore((s) => s.slots)
  const tokens = Object.values(sources).filter((s) => s.promo && s.campaign_id && campaigns.some((c) => c.id === s.campaign_id))

  return (
    <div className="card">
      <h3>Codes currently on screen (live QR) <span className="live">LIVE</span></h3>
      {tokens.length === 0 && <section className="empty">No promo-bearing slot right now — codes appear when a QR campaign wins a slot. Try the worked example: jump to 14:10 and inject a delay on XY501.</section>}
      <div className="grid cols-3">
        {tokens.map((s) => (
          <ClaimCard key={s.slot_id + s.promo!.token} token={s.promo!.token} name={s.campaign_name} />
        ))}
      </div>
    </div>
  )
}

export function ClaimCard({ token, name }: { token: string; name?: string }) {
  const [data, setData] = useState<any>(null)
  const [err, setErr] = useState('')
  useEffect(() => {
    api.claim(token).then(setData).catch((e) => setErr(String(e)))
  }, [token])
  if (err) return <div className="chip bad">{err}</div>
  if (!data) return <div className="est">loading claim page…</div>
  return (
    <div className="card" style={{ background: 'var(--bg-soft)' }}>
      <div className="mono" style={{ fontSize: 11 }}>{name}</div>
      <strong>{data.code}</strong>
      <div className="est">valid to {fmtHM(data.expires_at)} · value {data.value_label}</div>
      <a className="btn small" style={{ marginTop: 6 }} href={data.claim_url} target="_blank" rel="noreferrer">Open claim page ↗</a>
    </div>
  )
}

/** Campaign history (§14): 30-day ledger + one-action run-again. */
function RetailerHistory({ companyKind }: { companyKind: string }) {
  const outlet = outletPrefix(companyKind)
  const [rows, setRows] = useState<any[] | null>(null)
  const [note, setNote] = useState<string>('')
  const [busy, setBusy] = useState('')
  const [rerun, setRerun] = useState<any>(null)
  const load = () => api.retailerHistory(outlet).then((j) => setRows(j.campaigns)).catch((e) => setNote(String(e)))
  useEffect(() => { load() }, [outlet])
  const again = async (campaignId: string) => {
    setBusy(campaignId)
    setRerun(null)
    try {
      const j = await api.rerunCampaign(campaignId)
      setRerun(j.campaign)
      useStore.setState((s: any) => ({ campaigns: [...s.campaigns, j.campaign] }))
      await load()
    } catch (e: any) {
      setNote(String(e?.message || e))
    } finally {
      setBusy('')
    }
  }
  return (
    <div className="card">
      <h3>Campaign history — 30-day ledger <span className="chip muted">simulated accounting</span></h3>
      {rows === null && <div className="est">loading history…</div>}
      {rows !== null && (
        <table className="list">
          <thead><tr><th>Campaign</th><th>Status</th><th>Days</th><th>Impressions</th><th>Scans</th><th>Redemptions</th><th>Ad spend ($)</th><th>Attributed revenue ($)</th><th>ROI</th><th>Run again</th></tr></thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.campaign_id}>
                <td>{r.name}<br /><small className="mono muted">{r.campaign_id}</small></td>
                <td><span className={'chip ' + (r.status === 'APPROVED' ? 'good' : r.status === 'PENDING' ? 'warn' : 'muted')}>{r.status}</span></td>
                <td className="mono">{r.days}</td>
                <td className="mono">{r.impressions.toLocaleString()}</td>
                <td className="mono">{r.scans.toLocaleString()}</td>
                <td className="mono">{r.redemptions.toLocaleString()}</td>
                <td className="mono">{r.spend.toFixed(2)}</td>
                <td className="mono">{r.revenue.toFixed(2)}</td>
                <td className="mono"><b>{r.roi === null ? 'n/a' : `${r.roi.toFixed(2)}×`}</b></td>
                <td>
                  <button className="btn small" disabled={busy !== ''} onClick={() => again(r.campaign_id)}>
                    {busy === r.campaign_id ? '…' : r.running ? 'Run again' : 'Run again'}
                  </button>
                </td>
              </tr>
            ))}
            {rows.length === 0 && <tr><td colSpan={10} className="muted">No history for this outlet prefix.</td></tr>}
          </tbody>
        </table>
      )}
      {note && <div className="chip bad" style={{ marginTop: 8 }}>{note}</div>}
      {rerun && (
        <div className="chip good" style={{ marginTop: 8 }}>
          Run-again created editable campaign <b>{rerun.name}</b> ({rerun.id}) — status PENDING, awaiting Media Manager approval; approval is required before playback.
        </div>
      )}
      <p className="est" style={{ marginTop: 8 }}>
        ROI = attributed revenue / platform ad spend (n/a when spend is 0). Attributed revenue is simulated
        accounting, not payments; history is the seeded 30-day ledger, separate from today's live run.
      </p>
    </div>
  )
}
