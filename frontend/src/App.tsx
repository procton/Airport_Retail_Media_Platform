import { useEffect, useState } from 'react'
import TopBar from './TopBar'
import { connectWs, useStore } from './store'
import AdminView from './views/AdminView'
import RetailerView from './views/RetailerView'
import MediaView from './views/MediaView'
import AirlineView from './views/AirlineView'
import ScreenView from './views/ScreenView'
import ClaimView from './views/ClaimView'

export default function App() {
  const role = useStore((s) => s.role)
  const split = useStore((s) => s.split)
  const theme = useStore((s) => s.theme)
  const connected = useStore((s) => s.connected)
  const pull = useStore((s) => s.pull)

  useEffect(() => {
    connectWs()
    pull().catch(() => {})
    const iv = setInterval(() => pull().catch(() => {}), 15000)
    return () => clearInterval(iv)
  }, [])

  useEffect(() => {
    document.body.dataset.theme = theme
  }, [theme])

  // claim route: /claim/<token> (server-routed) or #/claim/<token> (hash)
  const claimMatch =
    /^#\/claim\/([a-z0-9]+)/.exec(location.hash) ??
    /^\/(?:index\.html)?\/?claim\/([a-z0-9]+)/.exec(location.pathname)
  if (claimMatch) return <ClaimView token={claimMatch[1]} />

  const dashboard = (
    <>
      {role === 'admin' && <AdminView />}
      {role === 'retailer' && <RetailerView />}
      {role === 'media' && <MediaView />}
      {role === 'airline' && <AirlineView />}
      {role === 'screen' && <ScreenView />}
    </>
  )

  if (split && role !== 'screen') {
    return (
      <div className="split" data-testid="split-screen">
        <div className="left"><ScreenView inSplit /></div>
        <div className="right">
          <TopBar />
          <div className="main">{dashboard}</div>
        </div>
      </div>
    )
  }

  return (
    <div className="app" data-testid="app-root">
      <TopBar />
      <div className="main">{dashboard}</div>
      {!connected && (
        <div className="toast" role="status">Reconnecting live updates…<small>snapshot polling continues</small></div>
      )}
      <RedemptionToast />
    </div>
  )
}

function RedemptionToast() {
  const last = useStore((s) => s.lastRedemption)
  const [shown, setShown] = useState<string | null>(null)
  useEffect(() => {
    if (!last) return
    setShown(last.token)
    const t = setTimeout(() => setShown(null), 6000)
    return () => clearTimeout(t)
  }, [last?.token])
  if (!last || shown !== last.token) return null
  return (
    <div className="toast" role="status">
      🎉 Redemption recorded
      <small>token …{last.token.slice(-6)} @ {last.at.slice(11, 19)} · retailer dashboard updated</small>
    </div>
  )
}
