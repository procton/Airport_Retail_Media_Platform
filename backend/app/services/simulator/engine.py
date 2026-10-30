"""SimulationEngine — one engine per FastAPI worker (AGENTS §3).

Owns: the simulation clock, canonical flight state (reconstructed through the
AODB/AIDX adapters), presence, decision pipeline, playback, promo tokens,
metrics aggregates, rule bookkeeping and the WebSocket event bus.

Concurrency rules honoured here:
- started/stopped through FastAPI lifespan; never per request/browser/role;
- conflicting control commands serialized via `self._ctl_lock`;
- all DB writes are batched through short transactions off the hot path;
- slot decisions follow a 15 s simulated cadence, while injected events bypass
  the cadence immediately (<2 s wall-clock budget, AGENTS §7).
"""
from __future__ import annotations

import asyncio
import contextlib
import itertools
import random
import time
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta

from ...adapters.acris import MockAcrisFeed, build_platform_layout
from ...adapters.aidx import AidxXmlAdapter
from ...config import get_settings
from ...domain.canonical import (
    Campaign,
    CampaignStatus,
    Flight,
    FlightEvent,
    Incident,
    Screen,
    ScreenKind,
    Zone,
)
from ...persistence.dao import Dao
from ...realtime.bus import EventBus
from ..decisions.pipeline import RulesContext
from ..playback import PlaybackPlanner
from ..presence.presence import PresenceEngine, effective_departure
from .clock import SimClock

# --------------------------------------------------------------------- types
SLOT_CADENCE_S = 15
PRESENCE_WINDOW_S = 300
FLUSH_INTERVAL_S = 1.5            # wall seconds between DB flush batches
WALL_2S_BUDGET = 2.0


class EngineError(RuntimeError):
    """Raised for operator-visible domain violations (broken refs, bad kinds)."""


class SimulationEngine:
    EngineError = EngineError  # exposed for API clients to catch by type

    def __init__(self, settings=None, dao: Dao | None = None) -> None:
        self.settings = settings or get_settings()
        self.dao = dao or Dao()
        self._media_rules_state: dict = dict(self.DEFAULT_MEDIA_RULES)
        self.bus = EventBus()
        self.aidx = AidxXmlAdapter()

        self.clock = SimClock(
            self.settings.operating_day, start_offset_min=self.settings.sim_start_offset_min,
            speed=self.settings.sim_speed,
        )
        self.run_id: str = "boot"
        self.seed = self.settings.seed_seed

        self.flights: dict[str, Flight] = {}
        self.zones: dict[str, Zone] = {}
        self.zone_list: list[Zone] = []
        self.checkpoints: list[dict] = []
        self.terminals: list[dict] = []
        self.screens: dict[str, Screen] = {}
        self.outlets: dict[str, dict] = {}
        self.advertisers: dict[str, dict] = {}
        self.airlines: dict[str, dict] = {}
        self.destinations: dict[str, dict] = {}
        self._master_overrides: dict[tuple[str, str], dict] = {}
        self.campaigns: list[Campaign] = []
        self.campaign_map: dict[str, Campaign] = {}
        self.creatives: dict[str, list[dict]] = {}
        self.queue_feed: MockAcrisFeed | None = None

        self.presence = PresenceEngine()
        self.ledger = RulesContext()
        self.planner = PlaybackPlanner(self.presence, self.ledger, self.dao, self.settings)
        from ..claims_service import attach
        attach(self)

        self.last_slot_floor = -1
        self.last_minute_floor = -1
        self._presence_written: set[str] = set()
        self._pending: dict[str, list] = defaultdict(list)
        self._exposure_acc: dict[tuple[str, str, str, str], dict] = {}
        self._last_flush = time.monotonic()
        self._flushing: bool = False
        self._ctl_lock = asyncio.Lock()
        self._started = False
        self._task: asyncio.Task | None = None
        self._screen_slot_seq: dict[str, str] = {}
        self._last_slot: dict[str, dict] = {}
        self._incidents_deque: deque[dict] = deque(maxlen=400)
        self._offline_since: dict[str, datetime] = {}
        self._live_metrics_cache: dict[str, dict] = {}
        self.padding_counter = itertools.count()
        self._decisions_today: deque[tuple[str, str, str]] = deque(maxlen=6000)  # (at, campaign, screen)
        self._last_playlist_ms = 0.0

    # ================================================================= boot
    async def start(self) -> None:
        if self._started:
            return
        state = await self._bootstrap_state()
        self._apply_state(state)
        saved = await self.dao.get_rule("media_rules") or {}
        self._media_rules_state = self.apply_media_rules(saved)
        self._started = True
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        self._started = False
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task

    async def _bootstrap_state(self) -> dict:
        from app.seed.loader import load_or_seed
        return await load_or_seed(self.dao, self.settings)

    def _apply_state(self, state: dict) -> None:
        self.run_id = state.get("run_id", "boot")
        self.seed = state.get("seed", self.seed)
        flights: list[Flight] = state["flights"]
        self.flights = {f.id: f for f in flights}
        self.settings.operating_day = state.get("day", self.settings.operating_day)

        terminals, zones, checkpoints = build_platform_layout()
        self.terminals = [t.model_dump() for t in terminals]
        self.zone_list = list(zones)
        self.checkpoints = [c.model_dump() for c in checkpoints]
        self.presence.configure(zones)
        self.presence.set_flights(list(self.flights.values()))
        self.queue_feed = MockAcrisFeed(state.get("day", "2026-10-14"), self.seed)
        self.presence.set_queue_measurements(self.queue_feed.measurements())

        self.screens = {
            sid: Screen(**{**payload, "kind": ScreenKind(payload["kind"])})
            for sid, payload in state["screens"].items()
        }
        self.outlets = state["outlets"]
        self.advertisers = state["advertisers"]
        self.airlines = state["airlines"]
        self.destinations = state["destinations"]
        self._master_overrides = {
            (r["kind"], r["id"]): r["data"] for r in state.get("master_overrides", [])
        }
        self.campaigns = [Campaign(**c) for c in state["campaigns"]]
        self.campaign_map = {c.id: c for c in self.campaigns}
        self.creatives = {cid: list(cs) for cid, cs in state["creatives"].items()}
        self.planner.campaigns = self.campaigns
        self.planner.creatives = self.creatives
        self.planner.promos = state.get("promos", {})
        self.planner.learn_rates = state.get("learn_rates", {})
        self.clock.day = state.get("day", self.settings.operating_day)

    def master_data(self, kind: str) -> list[dict]:
        """Return editable platform master data with runtime overlays."""
        if kind == "outlets":
            base = self.outlets
        elif kind == "airlines":
            base = self.airlines
        elif kind == "screens":
            base = {sid: s.model_dump(mode="json") for sid, s in self.screens.items()}
        elif kind == "terminals":
            base = {t.get("name", t.get("id", "")): t for t in self.terminals}
        elif kind == "zones":
            base = {z.id: z.model_dump(mode="json") for z in self.zone_list}
        elif kind == "gates":
            base = {
                f"{z.terminal}-{gate}": {"id": f"{z.terminal}-{gate}", "gate": gate, "terminal": z.terminal, "zone_id": z.id}
                for z in self.zone_list for gate in z.gates
            }
        else:
            base = {}
        rows = {key: dict(value) for key, value in base.items()}
        for (override_kind, entity_id), data in self._master_overrides.items():
            if override_kind == kind:
                rows[entity_id] = {**rows.get(entity_id, {}), **data}
        return [{"id": entity_id, "data": data} for entity_id, data in rows.items()]

    async def save_master_data(self, kind: str, entity_id: str, data: dict) -> dict:
        self._master_overrides[(kind, entity_id)] = data
        if kind == "outlets":
            self.outlets[entity_id] = {**self.outlets.get(entity_id, {}), **data}
        elif kind == "airlines":
            self.airlines[entity_id] = {**self.airlines.get(entity_id, {}), **data}
        elif kind == "screens":
            try:
                current = self.screens.get(entity_id)
                self.screens[entity_id] = Screen(**{**(current.model_dump() if current else {}), **data, "id": entity_id})
            except Exception as exc:
                self._master_overrides.pop((kind, entity_id), None)
                raise EngineError(f"invalid-screen:{exc}") from exc
        await self.dao.upsert_master_entity(kind, entity_id, data)
        return {"id": entity_id, "kind": kind, "data": self.master_data(kind)[next(i for i, r in enumerate(self.master_data(kind)) if r["id"] == entity_id)]["data"]}

    async def delete_master_data(self, kind: str, entity_id: str) -> bool:
        existed = (kind, entity_id) in self._master_overrides
        removed = await self.dao.delete_master_entity(kind, entity_id)
        self._master_overrides.pop((kind, entity_id), None)
        return existed or removed
    # ============================================================== control
    async def ctl(self) -> asyncio.Lock:
        return self._ctl_lock

    async def set_transport(self, playing: bool, speed: int | None = None) -> dict:
        async with self._ctl_lock:
            self.clock.playing = playing
            if speed is not None:
                assert speed in (1, 10, 60), "speed must be 1/10/60"
                self.clock.speed = speed
            self.clock._last_wall = time.monotonic()
            self.bus.publish("state.control", {"playing": self.clock.playing, "speed": self.clock.speed, "at": self.clock.iso()})
            return self.control_state()

    async def jump_to(self, iso: str) -> dict:
        async with self._ctl_lock:
            target = self._utc(iso)
            prev = self.clock.sim_now
            if target < prev:
                # backward jump = new run; reconstruct from seed + replay events
                await self._new_run(await self._replay_events_for_reset(target), target)
            else:
                self.clock.jump_to(target)
                self.presence.invalidate()
                self._presence_written.clear()
                self._last_slot_floor = int(target.timestamp()) // SLOT_CADENCE_S
                self._last_minute_floor = int(target.timestamp()) // 60
            self.bus.publish("state.resync", {"at": self.clock.iso(), "run_id": self.run_id})
            return self.control_state()

    async def reset_day(self, keep_injected: bool = True) -> dict:
        async with self._ctl_lock:
            target = datetime.fromisoformat(f"{self.settings.operating_day}T00:00:00+00:00") + timedelta(minutes=self.settings.sim_start_offset_min)
            await self._new_run(await self._replay_events_for_reset(target) if keep_injected else [], target)
            self.bus.publish("state.resync", {"at": self.clock.iso(), "run_id": self.run_id})
            return self.control_state()

    @staticmethod
    def _utc(v: str | datetime) -> datetime:
        if isinstance(v, str):
            v = datetime.fromisoformat(v)
        return v if v.tzinfo else v.replace(tzinfo=UTC)

    async def _replay_events_for_reset(self, target: datetime) -> list[dict]:
        rows = await self.dao.load_flight_events(self.run_id)
        return [r for r in rows if r["replay"] and self._utc(r["at"]) >= target]

    async def _new_run(self, replay: list[dict], target: datetime) -> None:
        # current run kept for rollups; new run constructed from seed + events
        was_playing = self.clock.playing
        self.clock.playing = False             # freeze loop work while rebuilding
        with contextlib.suppress(Exception):
            await self._flush_pending()        # drain outstanding writes first
        new_id = f"run-{int(time.time())}"
        await self.dao.create_run(new_id, self.seed, self.settings.seed_mode, self.settings.operating_day)
        self.run_id = new_id
        self._decisions_today.clear()
        self.ledger = RulesContext()          # per-run accounting starts fresh
        self.planner.ledger = self.ledger     # planner keeps its identity, ledger is new
        self.planner.pinned = {}              # pins are demo/manual state: new run starts clean
        self.apply_media_rules(self._media_rules_state)
        self._last_slot.clear()
        self._screen_slot_seq.clear()
        self._offline_since.clear()
        self._incidents_deque.clear()
        self._live_metrics_cache.clear()
        self.clock.jump_to(target)
        state = await self._bootstrap_state()
        self._apply_state(state)               # new run rebinds presence/screens/flights to the fresh seed entities
        for r in replay:
            self.apply_flight_event(FlightEvent(
                id=r["id"], flight_leg_id=r["flight_leg_id"], kind=r["kind"],
                at=self._utc(r["at"]), delay_minutes=int(r["delay"]),
                new_gate=r["gate"] or None, new_status=r["status"] or None,
                source="operator", message_id=r["message_id"],
            ))
        self.planner.invalidate_world()
        self.clock.playing = was_playing       # resume caller-visible playing state
    def control_state(self) -> dict:
        return {
            "playing": self.clock.playing,
            "speed": self.clock.speed,
            "at": self.clock.iso(),
            "run_id": self.run_id,
            "day": self.clock.day,
        }

    def metrics_live(self) -> dict:
        """Role KPIs; all values are live simulation aggregates (documented):
        traffic (plays/impressions) is the per-campaign ledger of estimated
        exposure, revenue is simulated CPM accounting, latency is the last
        playlist rebuild measured in wall-clock ms (AGENTS §21)."""
        ledger = self.ledger
        online = sum(1 for s in self.screens.values() if s.online)
        plays = len(self._decisions_today)
        impressions = sum(ledger.impress_today.values())
        spend = sum(ledger.spend_today.values())
        return {
            "screens_online_pct": round(100.0 * online / max(1, len(self.screens)), 1),
            "screens_online": online,
            "screens_total": len(self.screens),
            "plays_today": plays,
            "impressions_today": impressions,
            "revenue_today": round(spend, 2),
            "active_campaigns": len({c.id for c in self.campaigns if c.status is CampaignStatus.APPROVED}),
            "playlist_latency_ms": round(self._last_playlist_ms, 1),
            "last_redemption": self._live_metrics_cache.get("last_redemption"),
            "day": self.clock.day,
        }

    # ------------------------------------------------------- creative assist
    async def assist_creative(self, brief: dict) -> dict:
        """Creative assistant (§18 WOW): brief → ready template ad draft (EN +
        configured 2nd language) via the pluggable provider boundary. Returns
        a structured proposal only; nothing is persisted or scheduled."""
        from ...providers.creative import (
            CreativeBrief,
            ProviderInvalidResponse,
            ProviderUnconfigured,
            assistant_for,
        )

        parsed = CreativeBrief(**brief)
        try:
            provider = assistant_for(self.settings.creative_provider, settings=self.settings)
            return await provider.assist(parsed, self.settings.lang_secondary)
        except ProviderUnconfigured as exc:
            raise EngineError(f"unconfigured-provider: {exc}") from exc
        except ProviderInvalidResponse as exc:
            raise EngineError(f"provider-invalid-response: {exc}") from exc

    # ------------------------------------------------------- recommendations
    def recommend_tomorrow(self, campaign_id: str) -> dict:
        """Best three (screen, hour) slots for this campaign TOMORROW (AGENTS
        §18). Forecast extrapolation, documented and returned with the payload:
        tomorrow's flight plan is this operating day shifted +24 h (no
        day-of-week modelling), passenger profiles are held from the current
        pattern, queue measurements are not propagated (checkpoint
        contribution = 0) and screens are assumed online per current state.
        Exposure numbers reuse the documented impression model (§12/§17)."""
        campaign = next((c for c in self.campaigns if c.id == campaign_id), None)
        if campaign is None:
            raise EngineError(f"unknown campaign {campaign_id}")

        from copy import deepcopy

        from ..playback import PlaybackPlanner
        from ..presence.presence import PresenceEngine

        DAY_SHIFT = timedelta(hours=24)
        tomorrow = (datetime.fromisoformat(
            f"{self.settings.operating_day}T00:00:00+00:00") + DAY_SHIFT
        ).date().isoformat()

        def shift(f):
            return f.model_copy(update={
                k: v + DAY_SHIFT for k, v in f.model_dump().items()
                if isinstance(v, datetime)
            })

        pe = PresenceEngine()
        pe.configure(list(self.presence.zones.values()))
        pe.set_flights([shift(f) for f in self.presence._flights or []])
        pe.set_queue_measurements([])

        temp = PlaybackPlanner(
            presence=pe, ledger=deepcopy(self.ledger), dao=self.dao,
            settings=self.settings, on_event=None,
        )
        temp.campaigns = self.planner.campaigns
        temp.creatives = self.planner.creatives
        temp.promos = self.planner.promos
        temp.learn_rates = self.planner.learn_rates

        hours = range(
            campaign.hours_start if campaign.hours_start is not None else 6,
            campaign.hours_end if campaign.hours_end is not None else 23,
        )
        screens = [
            s for s in self.screens.values()
            if s.online
            and (not campaign.zone_ids or s.zone_id in campaign.zone_ids)
            and (not campaign.terminal or s.terminal == campaign.terminal)
        ]
        cand_rows: list[dict] = []
        for s in screens:
            for hh in hours:
                t = datetime.fromisoformat(f"{tomorrow}T{int(hh):02d}:20:00+00:00")
                pv = temp.preview_for(s, t, f"{self.run_id}-tmr")
                if pv is None:
                    continue
                row = next(
                    (x for x in pv["candidates"] if x["campaign_id"] == campaign.id),
                    None,
                )
                if row is None:
                    continue
                prop = pv["profile"]
                cand_rows.append({
                    "screen_id": s.id, "zone_id": s.zone_id, "hour": f"{int(hh):02d}:00",
                    "audience_fit": round(row["match"], 4),
                    "score": row["score"],
                    "predicted_impressions": int(row["est_impressions_per_hour"]),
                    "predicted_redemptions": int(row["est_redemptions_per_hour"]),
                    "crowd": prop["crowd"], "intl_share": prop["intl_share"],
                    "dwell_min": prop["dwell_min"],
                    "reasons": list(row["reasons"]) + [
                        f"{prop['crowd']} pax forecast at {s.zone_id} {int(hh):02d}:00",
                    ],
                    "eligible": row["eligible"],
                })

        cand_rows = [r for r in cand_rows if r["eligible"]]
        cand_rows.sort(key=lambda x: (-x["predicted_impressions"], -x["score"],
                                      x["screen_id"], x["hour"]))
        # diversify: one recommended slot per (zone, hour) so the three items
        # cover different inventory rather than duplicate adjacent screens;
        # if fewer than 3 zone-hours qualify, fill with next-best screen slots
        items: list[dict] = []
        seen: set[tuple[str, str]] = set()
        for r in cand_rows:
            key = (r["zone_id"], r["hour"])
            if key in seen:
                continue
            seen.add(key)
            items.append(dict(r, rank=len(items) + 1))
            if len(items) >= 3:
                break
        if len(items) < 3:
            used = {(r["screen_id"], r["hour"]) for r in items}
            for r in cand_rows:
                key = (r["screen_id"], r["hour"])
                if key in used:
                    continue
                used.add(key)
                items.append(dict(r, rank=len(items) + 1))
                if len(items) >= 3:
                    break
        spent = (self.ledger.spend_total.get(campaign.id, 0.0)
                 + self.ledger.spend_today.get(campaign.id, 0.0))
        assumptions = [
            f"Flight plan = operating day {self.settings.operating_day} shifted +24 h; day-of-week not modelled",
            "Passenger profiles held from the operating-day distribution",
            "Queue/checkpoint measurements not propagated (contribution = 0)",
            "Screens assumed online per current state; no bookings exist yet for tomorrow",
            "Exposure model: viewers × 3 glances × 60/dwell per screen-hour; demo CV 0.05",
            f"Budget pacing context: ${spent:,.2f} of ${campaign.budget_total:,.0f} spent so far",
        ]
        return {
            "campaign_id": campaign.id, "name": campaign.name, "day": tomorrow,
            "horizon": "tomorrow", "items": items, "assumptions": assumptions,
        }

    # ============================================================== mutation
    async def inject_flight_event(
        self, flight_id: str, kind: str, minutes: int = 0, new_gate: str | None = None
    ) -> dict:
        """Injection must pass through the source-format adapter (AGENTS §7)."""
        flight = self.flights.get(flight_id)
        if flight is None:
            raise EngineError(f"unknown flight {flight_id}")
        if kind not in ("delay", "gate_change", "cancel"):
            raise EngineError(f"unsupported injection kind {kind}")
        origin_date = flight.sched_std.strftime("%Y-%m-%d")
        dep, arr = (flight.origin, flight.destination)
        if kind == "delay":
            scheduled = {"OFB": flight.sched_std}
            xml = self.aidx.generate_notification(
                flight.airline_iata, flight.flight_number, origin_date, dep, arr,
                delay_min=minutes, scheduled_ops=scheduled,
                msg_ts=self.clock.sim_now,
            )
            events = self.aidx.parse_notification(xml)
        elif kind == "gate_change":
            xml = self.aidx.generate_notification(
                flight.airline_iata, flight.flight_number, origin_date, dep, arr,
                gate=new_gate or flight.gate, msg_ts=self.clock.sim_now,
            )
            events = self.aidx.parse_notification(xml)
        else:
            xml = self.aidx.generate_notification(
                flight.airline_iata, flight.flight_number, origin_date, dep, arr,
                new_status="CNL", msg_ts=self.clock.sim_now,
            )
            events = self.aidx.parse_notification(xml)
        assert events, "adapter produced no events for injection"
        for ev in events:
            self.apply_flight_event(ev)
        affected = self._affected_zone_ids(flight)
        await self.dao.add_flight_events([{
            "id": ev.id, "run_id": self.run_id, "flight_leg_id": ev.flight_leg_id,
            "kind": ev.kind, "at": ev.at, "delay_minutes": int(ev.delay_minutes or 0),
            "new_gate": ev.new_gate or "", "new_status": ev.new_status or "",
            "source": ev.source, "message_id": ev.message_id or "",
            "evidence_id": ev.evidence_id or "", "replay": True,
        }])
        self.presence.invalidate()
        self.planner.invalidate_world()
        self.replan_screens(affected)
        self.bus.publish("flight.update", self.flight_view(flight))
        return {"ok": True, "flight": self.flight_view(flight), "events": [e.model_dump(mode="json") for e in events]}

    def apply_flight_event(self, ev: FlightEvent) -> None:
        flight = self._resolve_leg(ev.flight_leg_id)
        if flight is None:
            raise EngineError(f"event references unknown leg {ev.flight_leg_id}")
        if ev.kind == "delay":
            flight.injected_delay_min = max(flight.injected_delay_min, int(ev.delay_minutes or 0))
        elif ev.kind == "gate_change":
            old_zone = self._affected_zone_ids(flight)
            flight.gate_override = ev.new_gate
            flight.gate = ev.new_gate
            for _zid in old_zone:
                self.presence.invalidate()
        elif ev.kind == "status_change" and (ev.new_status or "").upper() == "CNL":
            flight.cancelled = True
        self.presence.invalidate()

    def _resolve_leg(self, ref: str) -> Flight | None:
        """AIDX leg refs look like XH960@2026-10-14:ZHQ-MQI, we own ids aodb:<id>."""
        if ref in self.flights:
            return self.flights[ref]
        if "@" in ref:
            designator = ref.split("@")[0]
            for f in self.flights.values():
                if f.designator == designator:
                    return f
        return None

    def inject_screen(self, screen_id: str, online: bool) -> dict:
        screen = self.screens.get(screen_id)
        if not screen:
            raise EngineError(f"unknown screen {screen_id}")
        screen.online = online
        self.planner.invalidate_world()
        if not online:
            self._offline_since[screen_id] = self.clock.sim_now
            self._add_offline_incident(screen)          # auto-alert: outage
            self.bus.publish("screen.state", {"screen_id": screen_id, "online": False, "at": self.clock.iso()})
        else:
            self._offline_since.pop(screen_id, None)
            self.bus.publish("screen.state", {"screen_id": screen_id, "online": True, "at": self.clock.iso()})
        return {"ok": True}

    def _add_offline_incident(self, sc: Screen) -> None:
        t = self.clock.sim_now
        inc = Incident(
            id=f"inc-{sc.id}-{int(t.timestamp())}", severity="medium",
            title=f"Screen {sc.id} offline",
            detail="Operator marked the virtual screen offline (simulated outage).",
            where=sc.terminal, opened_at=t, related=sc.id,
        )
        self._incidents_deque.append(inc.model_dump(mode="json"))
        self._pending["incidents"].append(inc.model_dump(mode="json"))

    def _affected_zone_ids(self, flight: Flight) -> set[str]:
        zones: set[str] = set()
        for g in filter(None, [flight.gate, flight.gate_override, flight.stand]):
            if g in self.presence.gate_index:
                zones.add(self.presence.gate_index[g][0])
        zones.add(f"{flight.terminal}-retail-main")
        return {z for z in zones if z in self.presence.zones}

    def replan_screens(self, zone_ids: set[str] | None = None, screens: set[str] | None = None) -> None:
        """Immediate re-plan for screens affected by a flight/screen event.
        Runs synchronously; used from the <2 s wall-clock event path."""
        for sid, sc in self.screens.items():
            if screens and sid not in screens:
                continue
            if zone_ids and sc.zone_id not in zone_ids:
                continue
            slot = self.planner.plan_slot(sc, self.clock.sim_now, self.run_id)
            if slot is not None:
                self._screen_slot_seq[sid] = slot["slot_id"]
                self._last_slot[sid] = slot
                self._pending["decisions"].append(self._decision_row(slot))
                self._decisions_today.append((slot["at"], slot.get("campaign_id") or "house", sid))
                self._accumulate_exposure(slot)
                trow = slot.pop("token_row", None)
                if trow:
                    self._pending["tokens"].append(trow)
                self.bus.publish("screen.playlist", slot)
                self._simulated_engagement(slot)

    # =============================================================== the loop
    async def _run_loop(self) -> None:
        while self._started:
            now = time.monotonic()
            self.clock.tick_wall(now)
            self._process_boundaries()
            if now - self._last_flush >= FLUSH_INTERVAL_S and not self._flushing:
                self._last_flush = now
                self._flushing = True
                asyncio.create_task(self._flush_then_clear())
            await asyncio.sleep(
                0.02 if (self.clock.playing and self.clock.speed > 1) else
                (0.05 if self.clock.playing else 0.25)
            )

    async def _flush_then_clear(self) -> None:
        """Look-aside flush: never in the tick path (AGENTS §21); the clock
        keeps advancing while writes drain in the background."""
        try:
            await self._flush_pending()
        except Exception as exc:      # pragma: no cover - surfaced via WS feed
            # persistence is batched; losing one tick's rows must not kill the clock
            self.bus.publish("engine.flush-error", {"at": self.clock.iso(), "error": repr(exc)[:200]})
        finally:
            self._flushing = False

    def _process_boundaries(self) -> None:
        t = self.clock.sim_now
        slot_idx = int(t.timestamp()) // SLOT_CADENCE_S
        if self.clock.playing and slot_idx != self.last_slot_floor:
            # Forward jumps collapse to the nearest boundary: intervening slots
            # do not emit per-slot metrics (documented jump accounting, A9).
            crossed = slot_idx - self.last_slot_floor
            self.last_slot_floor = slot_idx
            boundaries = [slot_idx] if crossed > 3 else list(range(self.last_slot_floor - crossed, slot_idx + 1))
            for c in boundaries:
                boundary_t = datetime.fromtimestamp(c * SLOT_CADENCE_S, tz=UTC)
                self._plan_all_screens(boundary_t)
        minute_idx = int(t.timestamp()) // 60
        if minute_idx != self.last_minute_floor:
            self.last_minute_floor = minute_idx
            self._check_incidents(t)
            if self.clock.playing:
                self._publish_presence_tick(t)

    def _check_incidents(self, t: datetime) -> None:
        for sid in self._offline_since:
            inc = Incident(
                id=f"inc-{sid}", severity="medium", title=f"Screen {sid} offline",
                detail="Operator marked the virtual screen offline (simulated outage).",
                where=self.screens.get(sid, Screen(id=sid, terminal="T?", concourse="?", zone_id="?", zone="?", kind=ScreenKind.LGATE)).terminal,
                opened_at=t, related=sid,
            )
            row = inc.model_dump(mode="json")
            row["run_id"] = self.run_id
            if not any(i["id"] == inc.id for i in self._incidents_deque):
                self._incidents_deque.append(row)
                self._pending["incidents"].append(row)

    def _plan_all_screens(self, t: datetime) -> None:
        started = time.perf_counter()
        changed: list[dict] = []
        for sid, sc in self.screens.items():
            if not sc.online:
                continue
            slot = self.planner.plan_slot(sc, t, self.run_id)
            if slot is None:
                continue
            prev = self._screen_slot_seq.get(sid)
            self._screen_slot_seq[sid] = slot["slot_id"]
            self._last_slot[sid] = slot
            if prev != slot["slot_id"]:
                changed.append(slot)
            self._pending["decisions"].append(self._decision_row(slot))
            self._decisions_today.append((slot["at"], slot.get("campaign_id") or "house", sid))
            self._accumulate_exposure(slot)
            trow = slot.pop("token_row", None)
            if trow:
                self._pending["tokens"].append(trow)
            self._simulated_engagement(slot)
            self._maybe_incident_offline(sc, t)
        self._last_playlist_ms = (time.perf_counter() - started) * 1000.0
        if changed:
            self.bus.publish("screens.playlist", {"slots": changed, "at": t.isoformat(), "latency_ms": round((time.perf_counter() - started) * 1000, 1)})

    def _maybe_incident_offline(self, sc: Screen, t: datetime) -> None:
        if not sc.online and sc.id not in self._offline_since:
            self._offline_since[sc.id] = t
            inc = Incident(
                id=f"inc-{sc.id}-{int(t.timestamp())}",
                severity="medium", title=f"Screen {sc.id} offline",
                detail="Operator marked the virtual screen offline (simulated outage).",
                where=sc.terminal, opened_at=t, related=sc.id,
            )
            self._incidents_deque.append(inc.model_dump(mode="json"))
            self._pending["incidents"].append(inc.model_dump(mode="json"))

    def _publish_presence_tick(self, t: datetime) -> None:
        for zid in self.presence.zones:
            zone = self.presence.zones[zid]
            p = self.presence.presence_for(zone, t, self.clock.day)
            p.next30_count = self.presence.forecast_next(zone, t, self.clock.day, 30)
            p.next120_count = self.presence.forecast_next(zone, t, self.clock.day, 120)
            self._live_metrics_cache[f"presence:{zid}"] = p.model_dump(mode="json")
            window_key = f"{zid}@{p.window}"
            if window_key not in self._presence_written and self.clock.playing:
                self._presence_written.add(window_key)
                self._pending["presence"].append({
                    "id": f"{self.run_id}:{window_key}",
                    "run_id": self.run_id, "zone_id": zid,
                    "window_start": p.window_start, "passenger_count": p.passenger_count,
                    "intl_count": p.intl_count, "dwell_median_min": p.dwell_median_min,
                    "segments": {k: v for k, v in p.shares.items()},
                    "contributing_flights": p.contributing_flights,
                })
            self.bus.publish("presence.zone", p.model_dump(mode="json"))

    # ------------------------------------------------------- engagement sim
    def _simulated_engagement(self, slot: dict) -> None:
        """Auto-generated engagement: reproducibly seeded per slot, labelled
        simulated-engagement; it mint a SEPARATE engagement token (phantom
        passenger claim) so it never consumes the on-screen promo token that
        the phone demo must redeem (AGENTS §17)."""
        campaign_id = slot.get("campaign_id")
        if not campaign_id or slot.get("fallback"):
            return
        promo = slot.get("promo")
        if not promo or not promo.get("token"):
            return
        rng = random.Random(f"{campaign_id}:{slot['screen_id']}:{slot['slot_id']}:{self.run_id}")
        rate = self.planner.learn_rates.get(campaign_id, {}).get("holiday", 0.055)
        t0 = self.clock.sim_now
        if rng.random() < min(0.85, rate * 2.5):
            # own token for the simulated passenger
            trow = self.planner.issue_token(promo, self.run_id, t0)
            trow["mode"] = "simulated-engagement"
            self._pending["tokens"].append(trow)
            if rng.random() < rate * 4.0:
                self._pending["redemptions"].append(
                    {"token": trow["token"], "at": t0 + timedelta(seconds=rng.uniform(8, 30)), "mode": "simulated-engagement"}
                )

    # ------------------------------------------------------------- row assembly
    def _decision_row(self, slot: dict) -> dict:
        # token_row carries datetimes for the DAO; the audit record keeps the
        # JSON-safe payload (token id stays in promo.token) so big batches
        # never fail serialization.
        record = {k: v for k, v in slot.items() if k != "token_row"}
        return {
            "id": f"{self.run_id}:{slot['slot_id']}",
            "run_id": self.run_id,
            "screen_id": slot["screen_id"],
            "slot_at": datetime.fromisoformat(slot["at"]),
            "winner_campaign": slot.get("campaign_id") or "",
            "winner_creative": (slot.get("creative") or {}).get("creative_id", ""),
            "fallback": bool(slot.get("fallback")),
            "record": dict(record, model_version="sm-1.0"),
        }

    def _accumulate_exposure(self, slot: dict) -> None:
        t = datetime.fromisoformat(slot["at"])
        win = (int(t.timestamp()) // PRESENCE_WINDOW_S) * PRESENCE_WINDOW_S
        cid = slot.get("campaign_id") or ""
        kind = "campaign" if cid else "house"
        key = (self.run_id, slot["screen_id"], cid, str(win))
        row = self._exposure_acc.setdefault(key, {
            "id": f"{self.run_id}:{win}:{slot['screen_id']}:{cid}", "run_id": self.run_id,
            "at": datetime.fromtimestamp(win, tz=UTC), "screen_id": slot["screen_id"],
            "campaign_id": cid, "kind": kind, "est_viewers": 0,
        })
        row["est_viewers"] += slot["est_viewers"]

    async def _flush_pending(self) -> None:
        if not self._pending and not self._exposure_acc:
            return
        decisions = self._pending.pop("decisions", [])
        if len(decisions) > 24000:
            decisions = decisions[:24000]
        tokens = self._pending.pop("tokens", [])
        presence = self._pending.pop("presence", [])
        incidents = self._pending.pop("incidents", [])
        scans = self._pending.pop("scans", [])
        redemptions = self._pending.pop("redemptions", [])
        exposure = list(self._exposure_acc.values())
        self._exposure_acc.clear()
        try:
            if exposure:
                await self.dao.add_exposure(exposure)
            if presence:
                await self.dao.upsert_presence(presence)
            for trow in tokens:
                await self.dao.add_token(trow)
            for srow in scans:
                await self.dao.scan_token(srow["token"], srow["at"])
            for rrow in redemptions:
                redeemed = await self.dao.redeem_token(
                    rrow["token"], rrow["at"], rrow.get("revenue", 0.0)
                )
                if redeemed:
                    tok = await self.dao.get_token(rrow["token"])
                    if tok:
                        code = await self.dao.get_promo_code(tok["promo_code_id"])
                        if code:
                            from app.services.metrics.learning import apply_conversion
                            await apply_conversion(self.dao, code["campaign_id"], 1.0)
                    self._live_metrics_cache["last_redemption"] = {
                        "token": rrow["token"], "at": rrow["at"].isoformat(), "mode": rrow["mode"],
                    }
                    self.bus.publish("redemption.live", {"token": rrow["token"], "at": rrow["at"].isoformat(), "mode": rrow["mode"]})
            if incidents:
                for inc in incidents:
                    await self.dao.upsert_incident(inc)
            if decisions:
                await self.dao.add_decisions(decisions)
        except Exception:
            # persistence is batched; losing one tick's rows must not kill the clock
            self.bus.publish("engine.flush-error", {"at": self.clock.iso()})

    # ------------------------------------------------------------- snapshots
    def flight_view(self, f: Flight, t: datetime | None = None) -> dict:
        t = t or self.clock.sim_now
        status = self.flight_status(f, t)
        return {
            "id": f.id, "aodb_flight_id": f.aodb_flight_id, "designator": f.designator,
            "airline_iata": f.airline_iata, "airline_icao": f.airline_icao, "number": f.flight_number,
            "direction": f.direction.value, "origin": f.origin, "destination": f.destination,
            "terminal": f.terminal, "gate": f.gate_override or f.gate, "stand": f.stand,
            "sched_std": f.sched_std.isoformat(),
            "effective_std": effective_departure(f).isoformat() if f.direction.value == "D" else (f.aldt or f.etd or effective_departure(f)).isoformat(),
            "tobt": f.tobt.isoformat() if f.tobt else None,
            "tsat": f.tsat.isoformat() if f.tsat else None,
            "etd": f.etd.isoformat() if f.etd else None,
            "aldt": f.aldt.isoformat() if f.aldt else None,
            "aircraft_type": f.aircraft_type, "aircraft_reg": f.aircraft_reg, "seats": f.seats, "pax": f.pax,
            "status": status, "status_raw": f.status_raw, "cancelled": f.cancelled,
            "delay_min": f.injected_delay_min, "codeshares": f.codeshares,
            "delay_codes": f.delay_codes, "source": f.source,
        }

    def flight_status(self, f: Flight, t: datetime) -> str:
        if f.cancelled:
            return "CANCELLED"
        if f.direction.value == "D":
            eff = effective_departure(f)
            if t >= eff + timedelta(minutes=3):
                return "GONE"
            if f.boarding_start() <= t < f.gate_close():
                return "BOARDING"
            if f.gate_close() <= t < eff + timedelta(minutes=3):
                return "GATE_CLOSED"
            if f.tobt and f.tobt - timedelta(minutes=1) <= t:
                return "READY"
            return "CHECKIN" if f.tobt and f.tobt - timedelta(minutes=150) <= t else "SCHEDULED"
        eff_land = f.aldt or f.etd or effective_departure(f)
        if t >= eff_land:
            return "ARRIVED"
        if t >= eff_land - timedelta(minutes=15):
            return "ARRIVING"
        return "SCHEDULED"

    def flights_at(self, t: datetime | None = None) -> list[dict]:
        out = []
        for f in self.flights.values():
            if f.direction.value == "D" or (f.gate_override or f.gate):
                out.append(self.flight_view(f, t))
        return out

    def zones_summary(self) -> list[dict]:
        t = self.clock.sim_now
        out = []
        for _zid, zone in self.presence.zones.items():
            p = self.presence.presence_for(zone, t, self.clock.day)
            p.next30_count = self.presence.forecast_next(zone, t, self.clock.day, 30)
            p.next120_count = self.presence.forecast_next(zone, t, self.clock.day, 120)
            out.append(p.model_dump(mode="json"))
        return out

    def screens_summary(self) -> list[dict]:
        out = []
        for sid, sc in self.screens.items():
            slot = self._last_slot.get(sid)
            out.append({
                **sc.model_dump(mode="json"),
                "current_slot": slot,
            })
        return out

    def current_slot(self, screen_id: str) -> dict | None:
        sc = self.screens.get(screen_id)
        if not sc:
            return None
        cached = self._last_slot.get(screen_id)
        if cached is not None:
            return cached
        # never planned yet (fresh boot or paused start): plan once, persist
        slot = self.planner.plan_slot(sc, self.clock.sim_now, self.run_id)
        if slot is not None:
            self._last_slot[screen_id] = slot
            self._screen_slot_seq[screen_id] = slot["slot_id"]
            self._pending["decisions"].append(self._decision_row(slot))
            self._decisions_today.append((slot["at"], slot.get("campaign_id") or "house", screen_id))
            trow = slot.pop("token_row", None)
            if trow:
                self._pending["tokens"].append(trow)
            return slot
        return {"screen_id": screen_id, "offline": bool(not sc.online),
                "why": {"rule": "screen offline"}, "creative": {}, "at": self.clock.iso()}

    def presence_of_zone(self, zone_id: str) -> dict:
        zone = self.presence.zones.get(zone_id)
        if zone is None:
            raise EngineError(f"unknown zone {zone_id}")
        p = self.presence.presence_for(zone, self.clock.sim_now, self.clock.day)
        p.next30_count = self.presence.forecast_next(zone, self.clock.sim_now, self.clock.day, 30)
        p.next120_count = self.presence.forecast_next(zone, self.clock.sim_now, self.clock.day, 120)
        series = self.presence.zone_forecast_series(zone_id, self.clock.sim_now, 120, self.clock.day, {})
        return {
            **p.model_dump(mode="json"),
            "series_2h": series,
            "top_destinations": [list(d) for d in self.presence.top_destinations(zone_id, self.clock.sim_now, self.clock.day)],
        }

    def set_campaign_status(self, campaign_id: str, status: str) -> dict:
        """Media-manager approval action; affects eligibility everywhere and
        re-plans the affected zones immediately (AGENTS §5 consistency)."""
        idx = next((i for i, c in enumerate(self.campaigns) if c.id == campaign_id), None)
        if idx is None:
            raise EngineError(f"unknown campaign {campaign_id}")
        try:
            st = CampaignStatus(status)
        except ValueError as exc:
            raise EngineError(f"invalid status {status}") from exc
        self.campaigns[idx] = self.campaigns[idx].model_copy(update={"status": st})
        self.campaign_map[campaign_id] = self.campaigns[idx]
        self.planner.invalidate_world()
        zone_ids = set(self.campaigns[idx].zone_ids or [])
        self.replan_screens(zone_ids=zone_ids or None)
        self.bus.publish("campaign.status", {"campaign_id": campaign_id, "status": st.value})
        return {"ok": True, "campaign_id": campaign_id, "status": st.value}

    async def persist_campaign_status(self, campaign_id: str, status: str) -> None:
        await self.dao.set_campaign_status(campaign_id, status)

    # ------------------------------------------------------- retailer tools
    async def retailer_history(self, outlet_prefix: str) -> dict:
        """30-day campaign ledger for one retailer outlet (§14 history).
        Attributed revenue is simulated accounting; ROI = revenue/spend using
        platform ad spend (spend=0 rows report ROI as null, never Infinity)."""
        rows = await self.dao.load_history()
        by_campaign: dict[str, dict] = {}
        for r in rows:
            a = by_campaign.get(r["campaign_id"])
            if a is None:
                a = by_campaign[r["campaign_id"]] = dict(
                    impressions=0, scans=0, redemptions=0, spend=0.0, revenue=0.0, days=0,
                )
            a["impressions"] += r["impressions"]
            a["scans"] += r["scans"]
            a["redemptions"] += r["redemptions"]
            a["spend"] += r["spend"]
            a["revenue"] += r["revenue"]
            a["days"] += 1
        out_rows = []
        for c in self.campaigns:
            if not c.outlet_id.startswith(outlet_prefix):
                continue
            a = by_campaign.get(c.id)
            if a is None:
                continue
            spend = round(a["spend"], 2)
            out_rows.append({
                "campaign_id": c.id, "name": c.name,
                "status": c.status.value if hasattr(c.status, "value") else str(c.status),
                "days": a["days"], "impressions": a["impressions"], "scans": a["scans"],
                "redemptions": a["redemptions"], "spend": spend,
                "revenue": round(a["revenue"], 2),
                "roi": round(a["revenue"] / a["spend"], 2) if spend > 0 else None,
                "running": c.status is CampaignStatus.APPROVED,
            })
        out_rows.sort(key=lambda r: (-r["revenue"], r["campaign_id"]))
        return {
            "outlet_prefix": outlet_prefix,
            "campaigns": out_rows,
            "note": "attributed revenue is simulated accounting, not payments; "
                    "ROI = attributed revenue / platform ad spend (null when spend is 0); "
                    "separate from current-run live metrics",
        }

    async def rerun_campaign(self, campaign_id: str) -> dict:
        """Run-again: duplicate a past campaign in one action into a NEW
        editable PENDING campaign with a valid fresh schedule (§14). The new
        schedule starts this simulation day; approval still required."""
        src = self.campaign_map.get(campaign_id)
        if src is None:
            raise EngineError(f"unknown campaign {campaign_id}")
        new_id = f"rerun-{campaign_id}-{int(self.clock.sim_now.timestamp())}"
        while any(c.id == new_id for c in self.campaigns):  # uniqueness inside a paused clock
            new_id += "x"
        young = src.model_copy(update={
            "id": new_id,
            "status": CampaignStatus.PENDING,
            "created_at": self.clock.sim_now,
        })
        self.campaigns.append(young)
        self.campaign_map[new_id] = young
        self.planner.campaigns = self.campaigns
        await self.dao.upsert_campaigns([young.model_dump(mode="json")], [])
        self.planner.invalidate_world()
        self.bus.publish("campaign.status", {"campaign_id": new_id, "status": "PENDING", "rerun": True})
        return {"ok": True, "campaign_id": new_id, "campaign": young.model_dump(mode="json")}

    # ------------------------------------------------------- pin / override
    def pin_campaign(self, screen_id: str, campaign_id: str, reason: str) -> dict:
        """Media-manager manual pin (§10/§12/§15): requires a recorded reason
        and CANNOT bypass approval, placement or budget gates — the pinned
        candidate must still pass those hard rules this slot; a fail keeps the
        scored winner and the pin is not honored silently."""
        if not str(reason).strip():
            raise EngineError("a pin reason is required")
        screen = self.screens.get(screen_id)
        if screen is None:
            raise EngineError(f"unknown screen {screen_id}")
        campaign = self.campaign_map.get(campaign_id)
        if campaign is None:
            raise EngineError(f"unknown campaign {campaign_id}")
        if campaign.zone_ids and screen.zone_id not in campaign.zone_ids:
            raise EngineError(
                f"pin rejected: placement — screen {screen_id} is in zone {screen.zone_id}, "
                f"campaign targets {campaign.zone_ids}"
            )
        status = getattr(campaign.status, "value", str(campaign.status))
        if status != "APPROVED":
            raise EngineError(f"pin rejected: campaign status {status} is not APPROVED")
        self.planner.pinned[screen_id] = (campaign_id, str(reason))
        self.replan_screens(screens={screen_id})
        return {"screen_id": screen_id, "campaign_id": campaign_id, "reason": str(reason)}

    def clear_pin(self, screen_id: str, reason: str = "") -> dict:
        """Un-pin with (optional but preferred) recorded reason; immediate re-plan."""
        screen = self.screens.get(screen_id)
        if screen is None:
            raise EngineError(f"unknown screen {screen_id}")
        was = self.planner.pinned.pop(screen_id, None)
        self.replan_screens(screens={screen_id})
        return {"screen_id": screen_id, "removed": was, "reason": str(reason)}

    # --------------------------------------------------- admin: decision log
    async def decision_log(self, screen_id: str | None = None, campaign_id: str | None = None,
                           search: str | None = None, limit: int = 120) -> dict:
        from ..decisions.pipeline import DECISION_MODEL_VERSION
        rows = await self.dao.load_decisions(
            self.run_id, screen=screen_id, campaign=campaign_id,
            search=search or None, limit=max(1, min(int(limit), 500)),
        )
        return {
            "run_id": self.run_id,
            "model_version": DECISION_MODEL_VERSION,
            "count": len(rows),
            "decisions": rows,
            "note": "audit-only view of the per-screen decision records; search covers "
                    "the full record JSON including rejection reasons, overrides and pins",
        }

    # --------------------------------------------- admin: global rule config
    DEFAULT_MEDIA_RULES = {
        "competitor_gap_min": 10.0,
        "frequency_window_min": 60.0,
        "exploration_epsilon": 0.0,        # 0 = pure highest-score (worked example)
        "audience_weight": 1.0,
        "context_weight": 1.0,
    }

    def apply_media_rules(self, rules: dict | None) -> dict:
        """Load admin overrides (in-memory immediately, persisted rule_config)."""
        cur = dict(self.DEFAULT_MEDIA_RULES)
        if isinstance(rules, dict):
            try:
                cur["competitor_gap_min"] = max(0.0, min(float(rules.get("competitor_gap_min", cur["competitor_gap_min"])), 1440.0))
                cur["frequency_window_min"] = max(5.0, min(float(rules.get("frequency_window_min", cur["frequency_window_min"])), 480.0))
                cur["exploration_epsilon"] = max(0.0, min(float(rules.get("exploration_epsilon", cur["exploration_epsilon"])), 0.25))
                cur["audience_weight"] = max(0.0, min(float(rules.get("audience_weight", cur["audience_weight"])), 2.0))
                cur["context_weight"] = max(0.0, min(float(rules.get("context_weight", cur["context_weight"])), 2.0))
            except (TypeError, ValueError):
                self.bus.publish("media-rules.invalid", {"rules": str(rules)})
        self.planner.ledger.gap_min = cur["competitor_gap_min"]
        self.planner.ledger.freq_window_min = cur["frequency_window_min"]
        self.planner.ledger.exploration_epsilon = cur["exploration_epsilon"]
        self.planner.ledger.audience_weight = cur["audience_weight"]
        self.planner.ledger.context_weight = cur["context_weight"]
        return cur

    async def set_media_rules(self, rules: dict) -> dict:
        cur = self.apply_media_rules(rules)
        await self.dao.set_rule("media_rules", cur)
        self.bus.publish("media-rules", {**cur, "replanning": "next slot boundary"})
        self.planner.invalidate_world()
        self.replan_screens()
        return {"ok": True, "media_rules": cur, "note": "clamped per documented ranges; "
                "competitor gap and frequency window apply at the next slot; ε=0 keeps pure highest-score"}

    async def get_media_rules(self) -> dict:
        saved = await self.dao.get_rule("media_rules") or {}
        cur = self.apply_media_rules(saved)
        return {
            "media_rules": cur,
            "model_version": "sm-1.0",
            "score_constants": {"score_norm": 0.9918, "exp_a": 0.905, "exp_b": 0.4105},
            "model_note": "segment-model sm-1.0; score constants are fixed, while global audience/context "
                          "weights default to 1.0 and are bounded admin controls",
        }

    def feed_health(self) -> list[dict]:
        return [
            {"source": "aodb", "adapter": "mock-aodb", "healthy": True,
             "note": f"{len(self.flights)} legs loaded through AODB adapter", "rate": 0, "last": None},
            {"source": "aidx", "adapter": "mock-aidx", "healthy": True,
             "note": "mock amendments via generated AIDX XML", "rate": 0, "last": None},
            {"source": "acris", "adapter": "mock-acris", "healthy": True,
             "note": "platform-mock checkpoint measurements", "rate": 0, "last": None},
        ]
