/** Mobile claim page (§17): no identity, no device data; redemption IS the claim. */
import { useEffect, useState } from 'react'
import { QRCodeSVG } from 'qrcode.react'
import { api } from '../api'

export default function ClaimView({ token }: { token: string }) {
  const [page, setPage] = useState<any>(null)
  const [err, setErr] = useState('')
  const [redeemed, setRedeemed] = useState<any>(null)
  const [family, setFamily] = useState<any>(null)
  const [busy, setBusy] = useState(false)
  const [now, setNow] = useState(Date.now())

  useEffect(() => {
    api.claim(token).then(setPage).catch((e: any) => setErr(String(e.status ? e.message : e)))
  }, [token])

  useEffect(() => {
    const iv = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(iv)
  }, [])

  const expiry = page ? Date.parse(page.expires_at) : 0
  const secs = Math.max(0, Math.round((expiry - now) / 1000))
  const warn = secs < 900

  const doRedeem = async () => {
    setBusy(true)
    try {
      const r = await api.redeem(token)
      setRedeemed(r)
      setPage((p: any) => p && { ...p, state: r.already ? 'redeemed' : 'redeemed', redeemed_at: r.redeemed_at })
    } catch (e: any) { setErr(e.message) }
    setBusy(false)
  }

  const doFamily = async () => {
    setBusy(true)
    try { setFamily(await api.familyShare(token)) } catch (e: any) { setErr(e.message) }
    setBusy(false)
  }

  if (err && !page) {
    return <div className="claim" data-testid="claim-page">
      <header><BrandLogo value={page?.branding?.logo} /><h2>Claim page</h2></header>
      <div className="code">—</div>
      <p className="chip bad">This link is not valid: {err}</p>
      <p className="est">Claims validate against server-side expiry and run validity. Old-run tokens never regain validity.</p>
    </div>
  }

  if (!page) return <div className="claim"><p className="est">loading offer…</p></div>

  return (
    <div className="claim" data-testid="claim-page" style={{ position: 'relative' }}>
      <header>
        <BrandLogo value={page.branding?.logo} />
        <h2 style={{ margin: 4 }}>{page.branding?.title ?? 'Meridian Retail Media'}</h2>
        <small className="muted">No identity or device identifiers are collected.</small>
      </header>

      <div style={{ background: page.campaign_bg ?? '#0ea5e9', color: '#fff', borderRadius: 16, padding: 14 }}>
        <strong style={{ fontSize: 17 }}>{page.headline_en ?? 'Special offer'}</strong>
        <p style={{ margin: '6px 0 0', opacity: 0.95 }}>{page.body_en ?? 'Open this page at the counter.'}</p>
      </div>

      {redeemed || page.state === 'redeemed' ? (
        <div className="card" style={{ textAlign: 'center', padding: 20 }}>
          <div style={{ fontSize: 40 }}>✅</div>
          <h3 style={{ margin: '6px 0' }}>{redeemed?.already ? 'Already claimed' : 'Claim recorded'}</h3>
          <p className="est">Share code at the counter — the platform attributes the redemption to this offer.</p>
          <div className="code" style={{ fontSize: 24 }}>{page.code}</div>
          <button className="btn" onClick={() => { setRedeemed(null); setFamily(null) }}>Back</button>
        </div>
      ) : (
        <>
          <div className="code">{page.code}</div>
          <div className={'exp' + (warn ? ' warn' : '')}>
            {page.valid_now ? (secs > 0 ? `valid for ${Math.floor(secs / 3600)}h ${Math.floor((secs % 3600) / 60)}m ${secs % 60}s` : 'valid while the boarding window is open') : 'ⓘ current window may have closed — the server re-validates on claim'}
            {' · window ends ' + page.expires_at.slice(11, 16)}
          </div>

          <button className="btn primary big" disabled={busy} onClick={doRedeem}>Claim code</button>

          {!page.family_shared && (
            <button className="btn big" disabled={busy} onClick={doFamily}>Share with companion (2nd code)</button>
          )}

          {family && (
            <div className="card">
              <strong>Family code issued</strong>
              <div className="mono" style={{ margin: '6px 0' }}>{family.code}</div>
              <div className="row" style={{ marginTop: 6 }}>
                <QRCodeSVG value={family.link} size={120} />
                <div className="est">share this link; it carries its own one-time token ({family.token?.slice(0, 6)}…)</div>
              </div>
            </div>
          )}

          {!family && (
            <div className="card">
              <strong>{page.campaign_name ?? 'Offer'} details</strong>
              <ul className="est" style={{ margin: '8px 0 0 18px', textAlign: 'left' }}>
                <li>one-time redemption per token; bounded sharing via one companion code</li>
                <li>this claim = the redemption in this prototype (simulated accounting)</li>
                <li>shows in the retailer dashboard within ~1.5 s</li>
              </ul>
            </div>
          )}
        </>
      )}

      {err && <div className="chip bad">{err}</div>}

      <div className="spacer" style={{ flex: 1 }} />
      <footer className="est" style={{ textAlign: 'center', fontSize: 11 }}>
        {page.branding?.title ?? 'Meridian Retail Media'} POC · claim token {token.slice(0, 6)}… · no tracking cookies
      </footer>
    </div>
  )
}

function BrandLogo({ value }: { value?: string }) {
  const logo = value || 'M'
  return /^(https?:|data:|\/)/.test(logo)
    ? <img className="logo" src={logo} alt="brand logo" />
    : <div className="logo">{logo}</div>
}
