/** Passenger screen (§17): full-screen creative, FIDS strip, QR, “Why this ad?” */
import { useEffect, useMemo, useState } from 'react'
import { QRCodeSVG } from 'qrcode.react'
import { api, fmtTime, fmtHM } from '../api'
import type { Slot } from '../api'
import { useStore } from '../store'

export default function ScreenView({ screenId, inSplit = false }: { screenId?: string; inSplit?: boolean }) {
  const { screens, flights, control } = useStore()
  const [sid, setSid] = useState<string | undefined>(undefined)
  const [slot, setSlot] = useState<Slot | null>(null)
  const [why, setWhy] = useState(false)
  const [claim, setClaim] = useState(false)
  const [, setNow] = useState(Date.now())

  // default screen: a gate-42 screen if present, else first gate screen
  useEffect(() => {
    if (screenId) { setSid(screenId); return }
    api.screens('?gate=42').then((j) => j.screens[0]?.id ?? api.screens().then((k) => k.screens[0].id))
      .then((id) => id && setSid(id)).catch(() => {})
  }, [screenId])

  // poll the current slot for this screen (WS keeps it fresh too)
  useEffect(() => {
    if (!sid) return
    let alive = true
    const run = () => api.screen(sid).then((s) => alive && setSlot(s)).catch(() => {})
    run()
    const iv = setInterval(run, 5000)
    return () => { alive = false; clearInterval(iv) }
  }, [sid])

  // live slot updates from websocket take precedence within same slot id
  const wsStore = useStore((s) => s.slots)
  useEffect(() => {
    if (sid && wsStore[sid]) setSlot(wsStore[sid])
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [wsStore, sid])

  useEffect(() => {
    const iv = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(iv)
  }, [])

  const gateScreens = useMemo(() => screens.filter((s) => s.kind === 'gate').slice(0, 60), [screens])

  // nearby flights for FIDS: departures whose gate shares this screen's zone-ish list
  const fids = useMemo(() => {
    if (!slot) return []
    const t = Date.now()
    return flights
      .filter((f) => f.direction === 'D' && f.status !== 'GONE' && !f.cancelled)
      .filter((f) => {
        const eff = Date.parse(f.effective_std)
        return eff > t - 10 * 60_000 && eff < t + 110 * 60_000
      })
      .sort((a, b) => Date.parse(a.effective_std) - Date.parse(b.effective_std))
      .slice(0, 8)
  }, [flights, slot?.zone_id, sid])

  const creative = slot?.creative
  const head = creative?.headline_en ?? 'Meridian Retail'
  const body = creative?.body_en ?? 'Departs on screens across T1 and T2.'
  const condensed = !slot || slot.fallback

  return (
    <div className="screenwrap" data-testid="screen-view">
      <div className="row" style={{ gap: 8, padding: inSplit ? '6px 10px' : '10px 16px', background: '#04070d', borderBottom: '1px solid #1c2942' }}>
        <select className="input" value={sid ?? ''} onChange={(e) => setSid(e.target.value)} aria-label="Choose screen">
          <option value="" disabled>choose screen…</option>
          {gateScreens.map((s) => <option key={s.id} value={s.id}>{s.id} · {s.zone_id} · gate {s.gate ?? '—'}</option>)}
        </select>
        <span className="chip" style={{ background: '#0c1526', color: '#8ea3c8' }}>{sid ?? '…'}</span>
        {!condensed && <span className="chip mono" style={{ background: '#0c1526', color: '#34d399', borderColor: '#134e4a' }}>{fmtHIP(slot!.at)} · slot 15s</span>}
        <div className="spacer" />
        <button className="btn small" onClick={() => setWhy(!why)}>{why ? 'Hide' : 'Why this ad?'}</button>
        {slot?.promo && <button className="btn small primary" onClick={() => setClaim(true)}>Open claim</button>}
        {!inSplit && <span className="chip mono" style={{ background: '#0c1526', color: '#8ea3c8' }}>sim clock {fmtTime(control?.at)}</span>}
      </div>

      <div className="adframe">
        {creative && (
          <div className={'adcanvas' + ((creative.image || '').startsWith('wide') ? ' wide' : '')}
            style={{ background: creative.bg ?? '#0ea5e9', color: creative.fg ?? '#fff' }}>
            <Motif motif={creative.image ?? 'motif-house'} />
            <div style={{ zIndex: 1 }}>
              <h1>{head}</h1>
              <p>{body}</p>
              {creative.cta ? <div className="cta" style={{ color: creative.cta === '' ? undefined : creative.fg }}>{creative.cta}</div> : null}
              {condensed && <small className="est" style={{ display: 'block', marginTop: 20 }}>house content — no eligible paid campaign</small>}
            </div>
            {slot?.promo && (
              <div className="qrbox">
                <QRCodeSVG value={slot.claim_url ?? `${location.origin}/claim/${slot.promo.token}`} size={92} />
                <div className="t">Scan to claim {slot.promo.code ?? ''}</div>
                {!inSplit && <div className="exp">claims validate server-side · expires 15:40</div>}
              </div>
            )}
          </div>
        )}

        {why && slot?.why && (
          <div className="whycover" role="dialog" aria-label="Why this ad explanation">
            <div style={{ maxWidth: 560, width: '92%' }}>
              <h2 style={{ margin: '0 0 6px' }}>Why this ad?</h2>
              <ProfileBars w={slot.why.profile} />
              <table className="list" style={{ background: 'transparent' }}>
                <thead><tr><th>Candidate</th><th>Match</th><th>Boost</th><th>Score</th><th>Status</th></tr></thead>
                <tbody>
                  {slot.why.top_candidates.map((c) => (
                    <tr key={c.campaign_id} style={c.eligible ? undefined : { opacity: 0.5 }}>
                      <td>{c.name}</td>
                      <td className="mono">{(c.match * 100).toFixed(0)}%</td>
                      <td className="mono">×{c.boost}</td>
                      <td className="mono">{c.score.toFixed(2)}</td>
                      <td>
                        {c.eligible ? <span className="chip" style={{ background: '#0c1526', color: '#34d399', borderColor: '#134e4a' }}>eligible</span>
                          : <span className="chip" style={{ background: '#0c1526', color: '#fbbf24', borderColor: '#54320b' }}>filtered: {c.reasons[0] ?? ''}</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="est" style={{ color: '#8ea3c8' }}>winning rule: {slot.why.winning.rule}</p>
              <button className="btn" onClick={() => setWhy(false)}>Close</button>
            </div>
          </div>
        )}

        {claim && slot?.promo && <ClaimModal slot={slot} onClose={() => setClaim(false)} />}
      </div>

      <div className="fids" aria-label="Flight information display strip">
        {fids.length === 0 ? <div className="b"><span style={{ color: '#8ea3c8' }}>no nearby departures in window</span></div> : fids.map((f) => (
          <div key={f.id} className={'b ' + (f.delay_min > 0 ? 'delayed' : f.status === 'BOARDING' ? 'boarding' : '')}>
            <div className="d">{f.designator}</div>
            <div className="t">{f.destination} · {f.gate ?? '—'} · {fmtHIP(f.effective_std)}</div>
            <div className="s">
              {f.status}
              {f.delay_min > 0 ? ` +${f.delay_min}′` : ''}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

const fmtHIP = (iso: string) => fmtHM(iso)

function ProfileBars({ w }: { w: any }) {
  const items: [string, number][] = [
    ['holiday', w.holiday], ['family', w.family], ['business', w.business],
  ]
  return (
    <div style={{ marginBottom: 10 }}>
      <div className="row" style={{ marginBottom: 6 }}>
        <span className="chip">{w.crowd} pax</span>
        <span className="chip">intl {(w.intl_share * 100).toFixed(0)}%</span>
        <span className="chip">dwell {Math.round(w.dwell_min)}′</span>
      </div>
      {items.map(([k, v]) => (
        <div key={k} className="row" style={{ margin: '3px 0' }}>
          <span style={{ width: 80, fontSize: 12 }}>{k}</span>
          <div className="bar warm" style={{ flex: 1, background: '#0c1526' }}><i style={{ width: `${v * 100}%` }} /></div>
          <span className="mono" style={{ width: 40, textAlign: 'right', color: '#8ea3c8' }}>{(v * 100).toFixed(0)}%</span>
        </div>
      ))}
    </div>
  )
}

export function ClaimModal({ slot, onClose }: { slot: Slot; onClose: () => void }) {
  const [data, setData] = useState<any>(null)
  const [err, setErr] = useState('')
  useEffect(() => {
    api.claim(slot.promo!.token).then(setData).catch((e) => setErr(String(e)))
  }, [slot.promo!.token])

  return (
    <div className="whycover" role="dialog" aria-label="Claim offer">
      <div style={{ maxWidth: 420, width: '90%' }}>
        <h2 style={{ color: '#fff' }}>Open claim page on your phone</h2>
        <p style={{ color: '#8ea3c8' }}>Scan the QR (or tap below); the claim page validates expiry and run validity server-side.</p>
        {data &&
          <div className="card" style={{ textAlign: 'center' }}>
            <QRCodeSVG value={data.claim_url} size={160} />
            <div className="mono" style={{ marginTop: 8 }}>{data.claim_url}</div>
            <a className="btn primary" style={{ marginTop: 10 }} href={data.claim_url} target="_blank" rel="noreferrer">Open claim page</a>
          </div>}
        {err && <div className="chip bad">{err}</div>}
        <button className="btn" style={{ marginTop: 10 }} onClick={onClose}>Close</button>
      </div>
    </div>
  )
}

function Motif({ motif }: { motif: string }) {
  const key = (motif || '').toLowerCase()
  const art = key.includes('bottle') ? 'wine glass' :
    key.includes('arc') ? 'arch' : key.includes('tropic') ? 'sun palms' : key.includes('coffee') ? 'cup' : key.includes('toy') ? 'blocks' : 'gate'
  return (
    <svg className="motif" viewBox="0 0 200 200" aria-hidden>
      <circle cx="100" cy="100" r="86" fill="none" stroke="currentColor" strokeWidth="2" strokeDasharray="4 6" />
      <text x="34" y="176" fontSize="11" fill="currentColor">{art}</text>
      <path d="M40 120 L100 50 L160 120 Z" fill="none" stroke="currentColor" strokeWidth="3" />
      <circle cx="100" cy="96" r="26" fill="none" stroke="currentColor" strokeWidth="2" />
    </svg>
  )
}
