"""Playback planner: turns decisions into slots, owns virtual playback, issues
promo tokens for QR creatives and generates reproducible seeded engagement.

Exposure model (documented): an estimated exposure opportunity count per slot,
derived from the ZonePresence passenger estimate and the screen format:
    viewers = catchment_pax × VIEW_FACTOR[kind] × (0.25 + 0.75 × dwell_norm)
    dwell_norm = min(1, dwell/60)
Estimated impressions are exposure *opportunities*, never verified viewers;
the browser cannot create, duplicate or reduce them (AGENTS §17).
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from ..domain.canonical import Campaign, Screen, ScreenKind
from .decisions import pipeline
from .decisions.pipeline import RulesContext, SlotContext
from .presence.presence import PresenceEngine, effective_departure

VIEW_FACTOR: dict[str, float] = {
    ScreenKind.LGATE.value: 0.55,   # portrait by gate podium
    ScreenKind.LWIDE.value: 0.75,   # large visa wall
    ScreenKind.LTOTE.value: 0.35,   # totem in retail corridor
    ScreenKind.LDIGI.value: 0.5,    # digital banner
}


class PlaybackPlanner:
    def __init__(
        self,
        presence: PresenceEngine,
        ledger: RulesContext,
        dao,
        settings,
        on_event=None,
    ) -> None:
        self.presence = presence
        self.ledger = ledger
        self.dao = dao
        self.settings = settings
        self.on_event = on_event  # callback(topic, data)

        self.campaigns: list[Campaign] = []
        self.creatives: dict[str, list[dict]] = {}
        self.promos: dict[str, list[dict]] = {}       # campaign_id -> promo rows
        self.learn_rates: dict[str, dict[str, float]] = {}
        self.pinned: dict[str, tuple[str, str]] = {}
        self.last_creative_rotation: dict[str, int] = {}
        # 60x performance (AGENTS §21): zone-level caches, keyed by a 15 s
        # world bucket and a mutation version the engine bumps when flights,
        # campaigns, rules or screens change. Prevents hiding required work:
        # decisions are still evaluated per screen; only zone-static state
        # (catchment profile, catchment flights, zone-level candidate math)
        # is reused between screens in the same zone within one bucket.
        self.world_version = 0
        self._zone_bundle: dict[tuple, tuple] = {}
        self._zone_eval: dict[tuple, list] = {}

    # ---------------------------------------------------------------- slot
    def preview_for(self, screen: Screen, t: datetime, run_id: str,
                    pinned: tuple[str, str] | None = None) -> dict | None:
        """Read-only audience-match preview for a screen's catchment (AGENTS §12
        Retailer preview; no ledger writes, no slot side effects)."""
        if not screen.online:
            return None
        day = t.strftime("%Y-%m-%d")
        catch, _ = self.catchment_for(screen, t, day)
        flights = self.flights_in_catchment(screen, t, day)
        delays = [
            pipeline.FlightDelay(flight=f, delay_min=f.injected_delay_min)
            for f, _w in flights.values() if f.injected_delay_min > 0
        ]
        ctx = SlotContext(
            t=t, run_id=run_id, screen=screen, zone_id=screen.zone_id,
            presence=None,  # type: ignore[arg-type]
            catchment=catch, flights=flights, delays=delays,
            boarding_airline=self.boarding_airline_at(screen, t), festival_day=False,
        )
        outcome = pipeline.evaluate(self.campaigns, self.creatives, ctx, self.ledger,
                                    pinned=pinned)
        viewers = self.viewers_estimate(ctx, screen)
        slots_per_hour = max(1, 3600 // max(1, self.settings.slot_seconds))
        # Documented demo exposure model (AGENTS §12/§17):
        #   impressions/hour = per-slot viewers × MAX_GLANCES × turnover/hour
        #   turnover/hour = 60 / dwell_min (how many cohorts pass per hour)
        #   MAX_GLANCES bounds how many slots one passing passenger may notice.
        MAX_GLANCES = 3
        dwell_min = max(3.0, catch.get("dwell", 15.0) or 15.0)
        turnover = 60.0 / dwell_min
        cookie = viewers * MAX_GLANCES * turnover
        EST_CV = 0.05  # documented demo CV: 5% of exposure opportunities claim an offer
        cands = [
            {
                "campaign_id": c.campaign_id, "name": c.name, "match": c.match,
                "boost": c.boost, "score": c.score, "eligible": c.eligible,
                "reasons": c.reasons,
                "est_impressions_per_hour": int(cookie * (1.0 if c.eligible else 0.0)),
                "est_redemptions_per_hour": int(cookie * EST_CV * (1.0 if c.eligible else 0.0)),
            }
            for c in outcome.candidates
        ]
        cands.sort(key=lambda x: (-x["score"], x["campaign_id"]))
        # Media-manager conflict explanation (AGENTS §12/§15): group every
        # rejection reason as campaign → reasons, plus the active pin.
        conflicts = [
            {
                "campaign_id": c["campaign_id"], "name": c["name"],
                "reasons": c["reasons"], "eligible": c["eligible"],
            }
            for c in cands if not c["eligible"]
        ]
        return {
            "screen_id": screen.id,
            "at": t.isoformat(),
            "profile": {
                "crowd": int(round(catch.get("pax", 0))),
                "intl_share": catch.get("shares", {}).get("intl_share", 0.0),
                "dwell_min": round(catch.get("dwell", 0.0), 1),
                "holiday": catch.get("shares", {}).get("purpose_holiday", 0.0),
                "family": catch.get("shares", {}).get("party_family_with_children", 0.0),
                "business": catch.get("shares", {}).get("purpose_business", 0.0),
            },
            "est_viewers_slot": viewers,
            "slots_per_hour": slots_per_hour,
            "cv_note": "est redemptions/hour = exposures × 0.05 (documented demo CV)",
            "candidates": cands,
            "conflicts": conflicts,
            "active_pin": {"campaign_id": pinned[0], "reason": pinned[1]} if pinned else None,
        }

    # ------------------------------------------------------------- catchment
    def catchment_for(self, screen: Screen, t: datetime, day: str) -> tuple[dict, dict]:
        """Mixed screen catchment profile (own zone; documents simplification)."""
        zone = self.presence.zones.get(screen.zone_id)
        if zone is None:
            return {"pax": 0, "intl": 0, "dwell": 0.0, "shares": {}, "dest": {}}, {}
        raw = self.presence.raw_counts(zone, t, day)
        shares = {k: (round(v / raw["pax"], 3) if raw["pax"] > 0 else 0.0) for k, v in raw["mix"].items()}
        shares["intl_share"] = round(shares.get("intl_share", 0.0), 3)
        catch = {"pax": raw["pax"], "intl": raw["intl"], "dwell": raw["dwell"] / max(raw["pax"], 1e-9),
                 "shares": shares, "dest": raw.get("dest", {})}
        flights: dict[str, tuple] = {}
        return catch, flights

    def flights_in_catchment(self, screen: Screen, t: datetime, day: str) -> dict[str, tuple]:
        """Flights whose (overridden) gate sits in the screen's zone, weight>0."""
        out: dict[str, tuple] = {}
        zone = self.presence.zones.get(screen.zone_id)
        flights = self.presence._flights if self.presence._flights else []
        for f in flights:
            g = f.gate_override or f.gate or ""
            if zone and zone.kind.value == "gate":
                if g not in zone.gates:
                    continue
            elif zone and zone.kind.value == "retail":
                terminal_ok = f.terminal == zone.terminal
                if not terminal_ok:
                    continue
            else:
                continue
            if f.cancelled:
                continue
            if f.direction.value == "D":
                eff = effective_departure(f)
                dt = (eff - t).total_seconds()
                # normal catchment: up to 40 min pre-departure; delayed legs
                # remain triggerable for up to 2 h (operator delay demo).
                w = 1.0 if -600 <= dt <= 2400 else (0.35 if f.injected_delay_min > 0 and dt <= 7200 else 0.0)
            else:
                prof = self.presence.profile(f, day)
                w = 0.4 if prof else 0.0
            if w > 0:
                out[f.id] = (f, w)
        return out

    def boarding_airline_at(self, screen: Screen, t: datetime) -> str | None:
        """Airline whose boarding window covers this gate screen's time now."""
        flights = self.presence._flights or []
        zone = self.presence.zones.get(screen.zone_id)
        for f in flights:
            if f.cancelled or f.direction.value != "D":
                continue
            g = f.gate_override or f.gate or ""
            gate_ok = g == screen.gate or (zone and g in zone.gates)
            if not gate_ok:
                continue
            if f.boarding_start() <= t < f.gate_close():
                return f.airline_iata
        return None

    # ------------------------------------------------------------------ slot
    def zone_bundle(self, screen: Screen, t: datetime, day: str) -> tuple:
        """Zone-static (catchment + catchment flights + boarding windows) 15 s
        bucket cache. Boarding windows are computed once per flight per bucket;
        per-screen lookups are dict hits (60x hot path, §21)."""
        key = (self.world_version, screen.zone_id, int(t.timestamp()) // 15, day)
        hit = self._zone_bundle.get(key)
        if hit is None:
            if len(self._zone_bundle) > 600:
                self._zone_bundle.clear()
            catch, _empty = self.catchment_for(screen, t, day)
            flights = self.flights_in_catchment(screen, t, day)
            boarding_map: dict[str, str] = {}
            for f, _w in flights.values():
                if f.cancelled or f.direction.value != "D":
                    continue
                if f.boarding_start() <= t < f.gate_close():
                    boarding_map[f.gate_override or f.gate or ""] = f.airline_iata
            hit = (catch, flights, boarding_map)
            self._zone_bundle[key] = hit
        return hit

    def boarding_airline_from_bundle(self, screen: Screen, bundle: tuple) -> str | None:
        zone = self.presence.zones.get(screen.zone_id)
        allowed = set(zone.gates or []) if zone else set()
        if screen.gate:
            allowed.add(screen.gate)
        bmap = bundle[2]
        for g, airline in bmap.items():
            if g in allowed:
                return airline
        return None

    def invalidate_world(self) -> None:
        """Call after any mutation (flight event, campaign status, rules,
        screen online state) so cached zone bundles recompute."""
        self.world_version += 1
        if len(self._zone_bundle) > 64 or len(self._zone_eval) > 64:
            self._zone_bundle.clear()
            self._zone_eval.clear()

    def plan_slot(self, screen: Screen, t: datetime, run_id: str) -> dict | None:
        if not screen.online:
            return None
        day = t.strftime("%Y-%m-%d")
        bundle = self.zone_bundle(screen, t, day)
        catch, flights, _bmap = bundle
        delays = [
            pipeline.FlightDelay(flight=f, delay_min=f.injected_delay_min)
            for f, _w in flights.values()
            if f.injected_delay_min > 0
        ]
        ctx = SlotContext(
            t=t, run_id=run_id, screen=screen, zone_id=screen.zone_id,
            presence=None,  # type: ignore[arg-type]  (not used by evaluate)
            catchment=catch, flights=flights, delays=delays,
            boarding_airline=self.boarding_airline_from_bundle(screen, bundle),
            festival_day=False,
        )
        outcome = pipeline.evaluate(self.campaigns, self.creatives, ctx, self.ledger,
                                    pinned=self.pinned.get(screen.id),
                                    cache=self._zone_eval,
                                    bucket=(int(t.timestamp()) // 15, self.world_version))
        winner = outcome.winner
        slot_id = f"slot:{screen.id}:{int(t.timestamp())}"

        if winner is None:
            if not ctx.screen.degraded:
                creative = self.house_creative(screen, ctx)
                return self._assemble(slot_id, ctx, None, creative, fallback=True,
                                      outcome=outcome, run_id=run_id)
            return None  # offline/degraded screens stay dark; playless

        campaign = next(c for c in self.campaigns if c.id == winner.campaign_id)
        creative = self.pick_creative(screen, campaign)
        return self._assemble(slot_id, ctx, campaign, creative, fallback=False,
                              outcome=outcome, run_id=run_id)

    # ------------------------------------------------------------ internals
    def viewers_estimate(self, ctx: SlotContext, screen: Screen) -> int:
        pax = ctx.catchment.get("pax", 0.0)
        vf = VIEW_FACTOR.get(screen.kind.value, 0.5)
        dwell_norm = min(1.0, (ctx.catchment.get("dwell", 0.0) or 0.0) / 60.0)
        return int(max(0, round(pax * vf * (0.25 + 0.75 * dwell_norm))))

    def house_creative(self, screen: Screen, ctx: SlotContext | None) -> dict:
        idx = self.last_creative_rotation.get(f"house:{screen.id}", 0)
        variants = [
            {"headline_en": "Meridian Retail — taste the departure lounge", "headline_alt": "Meridian Retail — saboree la sala de salidas",
             "body_en": "Open until the last boarding call. Shops, cafés and services across T1 and T2.", "body_alt": "Abierto hasta el último embarque. Tiendas, cafeterías y servicios en T1 y T2.", "cta": "", "bg": "#134e4a", "fg": "#ffffff", "image": "motif-house", "show_code": False},
            {"headline_en": "Departures, upgraded", "headline_alt": "Salidas, mejoradas", "body_en": "Free Wi-Fi, rest zones and kids corners near every concourse.", "body_alt": "Wi-Fi gratis, zonas de descanso y rincones para niños en cada vestíbulo.", "cta": "", "bg": "#1e3a8a", "fg": "#ffffff", "image": "motif-house-2", "show_code": False},
        ]
        self.last_creative_rotation[f"house:{screen.id}"] = (idx + 1) % len(variants)
        return dict(variants[idx], creative_id=f"house-{idx + 1}")

    def pick_creative(self, screen: Screen, campaign: Campaign) -> dict:
        variants = self.creatives.get(campaign.id, [])
        if not variants:
            return dict(self.house_creative(  # never blank; documented house fill
                screen, None  # type: ignore[arg-type]
            ), fallback=True)
        i = self.last_creative_rotation.get(f"{screen.id}:{campaign.id}", 0)
        self.last_creative_rotation[f"{screen.id}:{campaign.id}"] = (i + 1) % len(variants)
        return dict(variants[i])

    def _assemble(self, slot_id, ctx, campaign, creative, *, fallback, outcome, run_id) -> dict:
        viewers = self.viewers_estimate(ctx, ctx.screen)
        t = ctx.t
        promo = None
        token_row = None
        if campaign and creative.get("show_code") and not fallback:
            promo = self.matching_promo(campaign, t)
            if promo:
                token_row = self.issue_token(promo, run_id, t)
        self.ledger.register_play(t, ctx.screen.id, campaign, viewers)
        if campaign:
            cost = campaign.cpm / 1000.0 * viewers
            self.ledger.spend_today[campaign.id] = self.ledger.spend_today.get(campaign.id, 0.0) + cost
            self.ledger.spend_total[campaign.id] = self.ledger.spend_total.get(campaign.id, 0.0) + cost
        ov = getattr(outcome, "override", None)
        ex = getattr(outcome, "exploration", None)
        return {
            "slot_id": slot_id,
            "screen_id": ctx.screen.id,
            "zone_id": ctx.zone_id,
            "at": t.isoformat(),
            "campaign_id": campaign.id if campaign else None,
            "campaign_name": campaign.name if campaign else "House content",
            "creative": creative,
            "est_viewers": viewers,
            "fallback": fallback,
            "override": (
                {"campaign_id": ov[0], "reason": ov[1]} if ov else None
            ),
            "exploration": ex,
            "promo": dict(promo, token=token_row["token"]) if promo else None,
            "token_row": token_row,
            "why": self.why(ctx, outcome, campaign, fallback),
            "duration_s": self.settings.slot_seconds,
        }

    @staticmethod
    def _aware(s: str | datetime) -> datetime:
        if isinstance(s, str):
            s = datetime.fromisoformat(s)
        return s if s.tzinfo else s.replace(tzinfo=UTC)

    def matching_promo(self, campaign: Campaign, t: datetime) -> dict | None:
        for row in self.promos.get(campaign.id, []):
            ws = row.get("window_start")
            we = row.get("window_end")
            if ws and t < self._aware(ws):
                continue
            if we and t > self._aware(we):
                continue
            return row
        return None

    def issue_token(self, promo: dict, run_id: str, t: datetime) -> dict:
        """One opaque redeemable token row per slot+code (scan then redeem).
        The token is issued by the backend only; the browser cannot mint one."""
        token = uuid.uuid4().hex[:20]
        expiry = self._aware(promo["window_end"]) if promo.get("window_end") else t + timedelta(minutes=120)
        return {
            "token": token, "promo_code_id": promo["id"], "run_id": run_id,
            "issued_at": t, "expires_at": expiry, "redeemed_at": None,
            "scanned_at": None, "family_index": 0, "mode": "simulated-engagement",
            "revenue_value": float(promo.get("value", 0.0)),
        }

    def why(self, ctx: SlotContext, outcome, campaign, fallback) -> dict:
        """Passenger-facing “Why this ad?” block (AGENTS §12)."""
        cands = sorted(
            outcome.candidates,
            key=lambda x: (0 if (x.eligible and x.pinned) else 1, -x.score if x.eligible else 2, x.campaign_id),
        )
        top = cands[:3]
        return {
            "profile": {
                "crowd": int(round(ctx.catchment.get("pax", 0))),
                "intl_share": ctx.catchment.get("shares", {}).get("intl_share", 0.0),
                "dwell_min": round(ctx.catchment.get("dwell", 0.0), 1),
                "holiday": ctx.catchment.get("shares", {}).get("purpose_holiday", 0.0),
                "family": ctx.catchment.get("shares", {}).get("party_family_with_children", 0.0),
                "business": ctx.catchment.get("shares", {}).get("purpose_business", 0.0),
            },
            "top_candidates": [
                {
                    "campaign_id": c.campaign_id, "name": c.name, "match": c.match,
                    "boost": c.boost, "score": c.score, "eligible": c.eligible,
                    "reasons": c.reasons[:3],
                }
                for c in top
            ],
            "winning": {
                "campaign_id": campaign.id if campaign else None,
                "rule": ("highest valid final score among eligible campaigns"
                         if not fallback else "no eligible campaign — house content"),
            },
        }
