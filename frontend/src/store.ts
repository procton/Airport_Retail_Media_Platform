import { wsUrl } from './api'
/** App-wide shared state: role/company scope + simulation snapshot store.
    All authoritative values come from backend; store is display-scope only. */
import { create } from 'zustand'
import { api } from './api'
import type { Control, CampaignRow, FlightRow, Metrics, PublicBranding, Slot, ZoneRow } from './api'

export type Role = 'admin' | 'retailer' | 'media' | 'airline' | 'screen'

export const RETAILERS = [
  { id: 'aurora-df', name: 'Aurora Duty-Free', kind: 'duty-free' },
  { id: 'kestrel-coffee', name: 'Kestrel Coffee', kind: 'coffee' },
]
export const AIRLINES = [
  { id: 'XD', name: 'Skylark Air (low-cost)' },
  { id: 'YA', name: 'Aurora National (full-service)' },
]

interface StoreState {
  theme: 'dark' | 'light'
  role: Role
  retailerId: string
  airlineId: string
  split: boolean
  control: Control | null
  metrics: Metrics | null
  zones: ZoneRow[]
  flights: FlightRow[]
  screens: any[]
  campaigns: CampaignRow[]
  slots: Record<string, Slot>          // screen_id -> current slot
  lastRedemption: { token: string; at: string } | null
  connected: boolean
  branding: PublicBranding
  setRole: (r: Role) => void
  setRetailer: (id: string) => void
  setAirline: (id: string) => void
  setSplit: (v: boolean) => void
  patchControl: (c: Partial<Control>) => void
  pull: () => Promise<void>
  pullScreen: (screenId: string) => Promise<void>
  applyWs: (topic: string, data: any) => void
}

export const useStore = create<StoreState>((set, get) => ({
  theme: 'light',
  role: 'admin',
  retailerId: 'aurora-df',
  airlineId: 'XD',
  split: false,
  control: null,
  metrics: null,
  zones: [],
  flights: [],
  screens: [],
  campaigns: [],
  slots: {},
  lastRedemption: null,
  connected: false,
  branding: { name: 'Meridian Retail Media', logo: 'M', primary: '#0ea5e9', accent: '#f59e0b', lang_primary: 'en', lang_secondary: 'es' },

  setRole: (r) => set({ role: r, theme: r === 'admin' ? 'dark' : 'light' }),
  setRetailer: (id) => set({ retailerId: id }),
  setAirline: (id) => set({ airlineId: id }),
  setSplit: (v) => set({ split: v }),
  patchControl: (c) => set({ control: { ...(get().control as any), ...c } as Control }),

  pull: async () => {
    const [ctrl, met, z, f, s, cm, branding] = await Promise.all([
      api.control(),
      api.metrics().then((j) => j.metrics).catch(() => null),
      api.zones(),
      api.flights('?limit=400'),
      api.screens().catch(() => ({ screens: [] })),
      api.campaigns(),
      api.publicConfig(),
    ])
    const slots: Record<string, Slot> = {}
    for (const sc of s.screens) if (sc.current_slot) slots[sc.id] = sc.current_slot
    set({ control: ctrl, metrics: met, zones: z.zones, flights: f.flights, screens: s.screens, campaigns: cm.campaigns, slots, branding })
  },

  pullScreen: async (screenId) => {
    const slot = await api.screen(screenId)
    set((st) => ({ slots: { ...st.slots, [screenId]: slot } }))
  },

  applyWs: (topic, data) => {
    const st = get()
    if (topic === 'state.control') set({ control: { ...(st.control as any), ...data } })
    else if (topic === 'state.resync') st.pull().catch(() => {})
    else if (topic === 'heartbeat') set({ connected: true, control: st.control ? { ...st.control, at: data.at } : st.control })
    else if (topic === 'screens.playlist') {
      for (const slot of data.slots) {
        st.slots[slot.screen_id] = slot
        set({ slots: { ...st.slots, [slot.screen_id]: slot } })
      }
    } else if (topic === 'screen.playlist') {
      if (data) set({ slots: { ...st.slots, [data.screen_id]: data } })
    } else if (topic === 'presence.zone') {
      const zones = st.zones.slice()
      const i = zones.findIndex((z) => z.zone_id === data.zone_id)
      if (i >= 0) zones[i] = { ...zones[i], ...data }
      else zones.push(data as ZoneRow)
      set({ zones })
    } else if (topic === 'flight.update') {
      const flights = st.flights.slice()
      const i = flights.findIndex((f) => f.id === data.id)
      if (i >= 0) flights[i] = { ...flights[i], ...data }
      else flights.push(data as FlightRow)
      set({ flights })
    } else if (topic === 'screen.state') {
      const screens = st.screens.slice()
      const i = screens.findIndex((s) => s.id === data.screen_id)
      if (i >= 0) screens[i] = { ...screens[i], online: data.online }
      set({ screens })
    } else if (topic === 'campaign.status') {
      st.pull().catch(() => {})
    } else if (topic === 'redemption.live') {
      set({ lastRedemption: { token: data.token, at: data.at } })
    }
  },
}))

/** Global websocket with reconnect; store is duplicated state kept in sync. */
export function connectWs() {
  let ws: WebSocket | null = null
  let retry = 0
  const open = () => {
    ws = new WebSocket(wsUrl())
    ws.binaryType = 'arraybuffer'
    ws.onopen = () => { retry = 0; useStore.setState({ connected: true }) }
    ws.onmessage = (m) => {
      try {
        const text = typeof m.data === 'string' ? m.data : new TextDecoder().decode(m.data)
        const { topic, data } = JSON.parse(text)
        useStore.getState().applyWs(topic, data)
      } catch { /* ignore malformed */ }
    }
    ws.onclose = () => {
      useStore.setState({ connected: false })
      if (retry++ < 8) setTimeout(open, Math.min(3000, 400 * retry))
      else setTimeout(open, 3000)
    }
  }
  open()
}
