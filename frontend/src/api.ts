/** REST helpers + shared types (all values originate backend-side). */

async function get<T = any>(path: string): Promise<T> {
  const r = await fetch(`/api${path}`)
  if (!r.ok) throw new Error(`${r.status} ${path}`)
  return r.json()
}

async function post<T = any>(path: string, body?: unknown): Promise<T> {
  const r = await fetch(`/api${path}`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: body === undefined ? '{}' : JSON.stringify(body),
  })
  const j = await r.json().catch(() => ({}))
  if (!r.ok) throw Object.assign(new Error(j.detail || `${r.status}`), { status: r.status })
  return j as T
}

export interface Control {
  playing: boolean
  speed: number
  at: string
  run_id: string
  day: string
}

export interface PublicBranding {
  name: string
  logo: string
  primary: string
  accent: string
  lang_primary: string
  lang_secondary: string
}

export interface FlightRow {
  id: string
  designator: string
  airline_iata: string
  flight_number: string
  direction: 'A' | 'D'
  origin: string
  destination: string
  terminal: string
  gate: string | null
  stand: string | null
  sched_std: string
  effective_std: string
  tobt: string | null
  tsat: string | null
  etd: string | null
  aircraft_type: string | null
  aircraft_reg: string | null
  seats: number
  pax: number
  status: string
  status_raw: string
  cancelled: boolean
  delay_min: number
  codeshares: string[]
  delay_codes: string[]
}

export interface ZoneRow {
  zone_id: string
  name: string
  kind: string
  terminal: string
  passenger_count: number
  domestic_count: number
  intl_count: number
  dwell_median_min: number
  next30_count: number
  next120_count: number
  shares: Record<string, number>
  top_destinations: [string, number][]
  nationalities: string[]
  languages: string[]
}

export interface ScreenRow {
  id: string
  terminal: string
  concourse: string
  zone_id: string
  zone: string
  gate: string | null
  nearest_gates: string[]
  kind: string
  width_px: number
  height_px: number
  online: boolean
  degraded: boolean
  current_slot?: Slot | null
}

export interface Candidate {
  campaign_id: string
  name: string
  match: number
  boost: number
  score: number
  eligible: boolean
  pinned?: boolean
  reasons: string[]
  est_impressions_per_hour?: number
  est_redemptions_per_hour?: number
}

export interface Slot {
  slot_id: string
  screen_id: string
  zone_id: string
  at: string
  campaign_id: string | null
  campaign_name: string
  creative: {
    headline_en: string
    headline_alt: string
    body_en: string
    body_alt: string
    cta: string
    bg: string
    fg: string
    image: string
    show_code: boolean
    creative_id: string
    fallback?: boolean
  }
  est_viewers: number
  fallback: boolean
  promo: { token: string; code?: string; window?: string; value?: number } | null
  why: {
    profile: { crowd: number; intl_share: number; dwell_min: number; holiday: number; family: number; business: number }
    top_candidates: Candidate[]
    winning: { campaign_id: string | null; rule: string }
  }
  duration_s: number
  claim_url?: string
}

export interface CampaignRow {
  id: string
  advertiser_id: string
  outlet_id: string
  name: string
  status: string
  domestic: string
  min_intl_share: number
  target_segments: Record<string, number>
  zone_ids: string[]
  terminal: string | null
  hours_start: number
  hours_end: number
  budget_total: number
  daily_cap: number
  frequency_cap_per_screen_hour: number
  trigger: string
  trigger_delay_min: number
  trigger_boost: number
  airline_iata: string | null
  cpm: number
}

export interface Metrics {
  screens_online_pct: number
  screens_online: number
  screens_total: number
  plays_today: number
  impressions_today: number
  revenue_today: number
  active_campaigns: number
  playlist_latency_ms: number
  last_redemption?: { token: string; at: string; mode: string } | null
  day: string
}

export interface IncidentRow {
  id: string
  severity: string
  title: string
  detail: string
  where: string
  status: string
  owner: string
  opened_at: string
  related: string
}

export const api = {
  publicConfig: () => get<PublicBranding>('/config/public'),
  get,
  post,
  put: async <T = any>(path: string, body: unknown): Promise<T> => {
    const r = await fetch(`/api${path}`, {
      method: 'PUT',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(body),
    })
    const j = await r.json().catch(() => ({}))
    if (!r.ok) throw Object.assign(new Error(j.detail || `${r.status}`), { status: r.status })
    return j as T
  },
  control: () => get<Control>('/state/control'),
  flights: (q = '') => get<{ count: number; flights: FlightRow[] }>(`/flights${q}`),
  flight: (id: string) => get<FlightRow & { profile?: any }>(`/flights/${encodeURIComponent(id)}`),
  zones: () => get<{ zones: ZoneRow[] }>('/zones'),
  zone: (id: string) => get<ZoneRow & { series_2h: [string, number][]; top_destinations: [string, number][] }>(`/zones/${encodeURIComponent(id)}`),
  screens: (q = '') => get<{ count: number; screens: ScreenRow[] }>(`/screens${q}`),
  masterData: (kind: string) => get<{ kind: string; count: number; items: { id: string; data: any }[] }>(`/master-data/${kind}`),
  createMasterData: (kind: string, body: { id: string; data: any }) => post(`/master-data/${kind}`, body),
  updateMasterData: (kind: string, id: string, body: { id: string; data: any }) => apiPut(`/master-data/${kind}/${encodeURIComponent(id)}`, body),
  deleteMasterData: (kind: string, id: string) => apiDelete(`/master-data/${kind}/${encodeURIComponent(id)}`),
  screen: (id: string) => get<Slot>(`/screens/${encodeURIComponent(id)}`),
  screenOnline: (id: string, online: boolean) => post(`/screens/${id}/online-state`, { online }),
  campaigns: () => get<{ count: number; campaigns: CampaignRow[] }>('/campaigns'),
  matchPreview: (screenId: string) => get<any>(`/match/preview?screen_id=${encodeURIComponent(screenId)}`),
  recommendSlots: (campaignId: string) => get<any>(`/campaigns/${encodeURIComponent(campaignId)}/recommend-slots`),
  assistCreative: (b: { product: string; discount_pct?: number; audience?: string; zone_hint?: string; note?: string }) =>
    post('/creative/assist', b),
  retailerHistory: (outlet: string) => get<any>(`/retailer/history?outlet=${encodeURIComponent(outlet)}`),
  rerunCampaign: (campaignId: string) => post('/campaigns/rerun', { campaign_id: campaignId }),
  metrics: () => get<{ metrics: Metrics }>('/metrics/live'),
  feeds: () => get<{ feeds: any[] }>('/feeds'),
  incidents: () => get<{ count: number; incidents: IncidentRow[] }>('/incidents'),
  claim: (token: string) => post<any>(`/claims/${token}`),
  redeem: (token: string) => post<any>(`/claims/${token}/redeem`, { mode: 'phone' }),
  familyShare: (token: string) => post<any>(`/claims/${token}/family`),
  setTransport: (playing: boolean, speed?: number) => post('/controls', { playing, ...(speed ? { speed } : {}) }),
  jump: (at: string) => post('/controls/jump', { at }),
  reset: (keep_injected = true) => post('/controls/reset', { keep_injected }),
  injectFlightEvent: (flight_id: string, kind: string, minutes = 0, gate?: string) =>
    post('/controls/flight-event', { flight_id, kind, minutes, ...(gate ? { gate } : {}) }),
}

async function apiPut<T = any>(path: string, body: unknown): Promise<T> {
  const r = await fetch(`/api${path}`, { method: 'PATCH', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) })
  const j = await r.json().catch(() => ({}))
  if (!r.ok) throw Object.assign(new Error(j.detail || `${r.status}`), { status: r.status })
  return j as T
}

async function apiDelete<T = any>(path: string): Promise<T> {
  const r = await fetch(`/api${path}`, { method: 'DELETE' })
  const j = await r.json().catch(() => ({}))
  if (!r.ok) throw Object.assign(new Error(j.detail || `${r.status}`), { status: r.status })
  return j as T
}

export const wsUrl = () => {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  return `${proto}://${location.host}/api/ws`
}

export const fmtTime = (iso: string | null | undefined) =>
  iso ? new Date(iso).toISOString().slice(11, 19) : '—'

export const fmtHM = (iso: string | null | undefined) =>
  iso ? new Date(iso).toISOString().slice(11, 16) : '—'

export const money = (v: number, cur = '$') => `${cur}${v.toLocaleString(undefined, { maximumFractionDigits: 2 })}`

export const pct = (v: number, digits = 0) => `${(v * 100).toFixed(digits)}%`
