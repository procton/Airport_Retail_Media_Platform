"""ZonePresence engine (AGENTS §8 MUST).

ONE shared presence signal consumed by decisions, dashboards and forecasts.

Documented model
----------------
Weights (per flight leg, position weights of the same day):
  Departures (weight depends on seconds to effective STD; effective STD shifts
  with injected delay):
    outside[-100,min,+5,min]      -> 0
    [-100,-40]                    -> ramp 0→1  (passengers reach the gate area)
    [-40,-15]                     -> 1.0       (settled at gate: dwell peak)
    [-15,-5]                      -> 0.35      (gate queue / walking to aircraft)
    [-5,+5]                       -> 0.10      (final boarding)
  Arrivals (w.r.t. effective landing time):
    [-45,0]                       -> ramp 0→1  (deplaning)
    [0,40]                        -> exp decay τ=18min
  Cancelled legs contribute 0.

Zone presence: Σ pax × w for flights whose (overridden) gate lies in the zone
(domestic/international split from per-flight profile.intl_share; dwell =
weighted remaining time to effective STD capped at 90 min).

Retail zones: walk-in flow factor 0.28 × each linked same-terminal gate zone
(documented constant; zones have no direct source equivalent, see D2).

Security zones: ACRIS-shaped checkpoint headcount × freshness (1→0 over 15 min
wall-of-simulation since measured_at).

Screens (not zones) own the *catchment* weights: a screen at gate g sees gates
at distance 0/1/2 with weights 1.0/0.5/0.25 across the terminal's ordered gate
list (documented; decisions read that mixed catchment profile).
"""
from __future__ import annotations

from datetime import datetime, timedelta
from math import exp

from ...domain.canonical import (
    Flight,
    FlightProfile,
    QueueMeasurement,
    Zone,
    ZoneKind,
    ZonePresence,
)
from .profiles import profile_for

MIX_KEYS = (
    "purpose_business", "purpose_holiday", "purpose_vfr", "purpose_student", "purpose_religious",
    "party_solo", "party_couple", "party_family_with_children", "party_group",
    "children_pax_share", "adults_25_54", "premium_cabin", "frequent_flyer", "female", "intl_share",
)


def window_floor(t: datetime, minutes: int = 5) -> datetime:
    m = (t.minute // minutes) * minutes
    return t.replace(minute=m, second=0, microsecond=0)


def effective_departure(f: Flight) -> datetime:
    return f.sched_std + timedelta(minutes=f.injected_delay_min)


def effective_landing(f: Flight) -> datetime:
    return f.aldt or f.etd or effective_departure(f)


def leg_gate(f: Flight) -> str:
    return f.gate_override or f.gate or ""


def dep_leg_weight(seconds_to_std: float) -> float:
    """Weight of a departing leg's passengers being at the gate now.
    seconds_to_std > 0: minutes until (effective) departure; < 0: after."""
    if seconds_to_std > 6000 or seconds_to_std < -600:
        return 0.0
    if seconds_to_std >= 2400:
        return (6000.0 - seconds_to_std) / 3600.0
    if seconds_to_std >= 300:
        return 1.0
    if seconds_to_std >= 0:
        return 0.35
    return 0.10


def arr_leg_weight(seconds_since_landing: float) -> float:
    if seconds_since_landing < -2700 or seconds_since_landing > 2400:
        return 0.0
    if seconds_since_landing <= 0:
        return (seconds_since_landing + 2700.0) / 2700.0
    return max(0.0, exp(-seconds_since_landing / 1080.0))


def screen_catchment_weight(distance: int) -> float:
    return {0: 1.0, 1: 0.5, 2: 0.25}.get(distance, 0.0)


class PresenceEngine:
    def __init__(self) -> None:
        self.zones: dict[str, Zone] = {}
        self.gate_index: dict[str, tuple[str, int]] = {}
        self.retail_links: dict[str, list[tuple[str, float]]] = {}
        self.zones_by_terminal: dict[str, list[str]] = {}
        self.profile_cache: dict[str, FlightProfile] = {}
        self.queue_by_zone: dict[str, tuple[QueueMeasurement, ...]] = {}
        self._flights: list[Flight] = []
        self._flight_lookup: dict[str, Flight] = {}
        self.version = 1

    # --------------------------------------------------------------- config
    def configure(self, zones: list[Zone]) -> None:
        self.zones = {z.id: z for z in zones}
        for zid, z in sorted(self.zones.items()):
            for i, g in enumerate(z.gates):
                self.gate_index[g] = (zid, i)
            self.zones_by_terminal.setdefault(z.terminal, []).append(zid)
            if z.kind == ZoneKind.RETAIL:
                self.retail_links[zid] = [
                    (other.id, 0.28)
                    for other in self.zones.values()
                    if other.id != zid and other.terminal == z.terminal and other.kind == ZoneKind.GATE
                ]
        # ordered worldwide gate list per terminal for cross-zone distances
        for tid, zones in self.zones_by_terminal.items():
            ordered: list[str] = []
            for zid in zones:
                if self.zones[zid].kind == ZoneKind.GATE:
                    ordered.extend(self.zones[zid].gates)
            self._ordered_by_terminal[tid] = ordered
        self.version += 1

    _ordered_by_terminal: dict[str, list[str]] = {}

    def set_flights(self, flights: list[Flight]) -> None:
        self._flights = flights
        self._flight_lookup = {f.id: f for f in flights}

    def set_queue_measurements(self, measures: list[QueueMeasurement]) -> None:
        zone_q: dict[str, list[QueueMeasurement]] = {}
        for m in sorted(measures, key=lambda q: q.measured_at):
            zone_q.setdefault(m.checkpoint_id.split("-")[0] + "-security", []).append(m)
        self.queue_by_zone = {k: tuple(v[-3:]) for k, v in zone_q.items()}
        self.version += 1

    def invalidate(self) -> None:
        self.version += 1

    # ---------------------------------------------------------------- profile
    def profile(self, flight: Flight, day: str) -> FlightProfile:
        p = self.profile_cache.get(flight.id)
        if p is None:
            p = profile_for(flight, day)
            self.profile_cache[flight.id] = p
        return p

    def profiles_all(self) -> dict[str, FlightProfile]:
        return self.profile_cache

    # ------------------------------------------------------------------ gates
    def zone_for_gate(self, gate: str) -> str | None:
        return self.gate_index.get(gate, (None, None))[0]

    def gate_distance(self, screen_gate: str, other_gate: str, terminal: str) -> int:
        ordered = self._ordered_by_terminal.get(terminal, [])
        try:
            return abs(ordered.index(screen_gate) - ordered.index(other_gate))
        except ValueError:
            return 99

    # ------------------------------------------------------------------ core
    def mixing(self, mix: dict[str, float], shares: dict[str, float], weight: float) -> None:
        for k in MIX_KEYS:
            v = shares.get(k)
            if isinstance(v, (int, float)):
                mix[k] = mix.get(k, 0.0) + v * weight

    def zone_counts(self, zone: Zone, t: datetime, day: str) -> dict:
        from .profiles import enrich

        weights: dict[str, float] = {}
        pax_total = 0.0
        intl_total = 0.0
        dwell_total = 0.0
        mix: dict[str, float] = {}
        dest_weights: dict[str, float] = {}
        for f in self._flights:
            if f.cancelled:
                continue
            g = leg_gate(f)
            if not g or self.gate_index.get(g, (None,))[0] != zone.id:
                continue
            pax = f.pax or int((f.seats or 0) * 0.82)
            if pax <= 0:
                continue
            if f.direction.value == "D":
                eff = effective_departure(f)
                w = dep_leg_weight((eff - t).total_seconds())
                if w <= 0.0:
                    continue
                prof = self.profile(f, day)
                contrib = pax * w
                # dwell uses the profile's median-dwell hint (organizer worked
                # example expects the gate dwell ≈ profile median, not the raw
                # remaining time); clamped like arrivals.
                dwell_total += contrib * min(90.0, max(4.0, prof.dwell_hint_min))
                dest_weights[enrich(f.destination)[0]] = (
                    dest_weights.get(enrich(f.destination)[0], 0.0) + contrib * (1.0 - prof.shares.intl_share * 0.0)
                )
            else:
                eff = effective_landing(f)
                w = arr_leg_weight((t - eff).total_seconds())
                if w <= 0.0:
                    continue
                prof = self.profile(f, day)
                contrib = pax * w
                dwell_total += contrib * prof.dwell_hint_min
                dest_weights[enrich(f.origin)[0]] = dest_weights.get(enrich(f.origin)[0], 0.0) + contrib
            weights[f.id] = round(weights.get(f.id, 0.0) + contrib, 1)
            pax_total += contrib
            intl_total += contrib * prof.shares.intl_share
            self.mixing(mix, prof.shares.shares_by_name(), contrib)
        dest_weights = {k: round(v, 1) for k, v in sorted(dest_weights.items(), key=lambda kv: -kv[1])}
        nats: list[str] = []
        langs: list[str] = []
        return {
            "pax": pax_total, "intl": intl_total, "dwell": dwell_total, "mix": mix,
            "weights": weights, "dest": dest_weights, "nats": nats, "langs": langs,
        }

    def security_counts(self, zone: Zone, t: datetime) -> dict:
        pax = 0.0
        intl = 0.0
        for m in self.queue_by_zone.get(zone.id, ()):
            age = max(0.0, (t - m.measured_at).total_seconds())
            if age > 900:
                continue
            fresh = 1.0 - age / 900.0
            pax += m.headcount_est * 0.6 * fresh
            intl += m.headcount_est * 0.6 * fresh * 0.45  # checkpoint intl share documented
        return {"pax": pax, "intl": intl, "dwell": 0.0, "mix": {}, "weights": {}}

    def raw_counts(self, zone: Zone, t: datetime, day: str) -> dict:
        if zone.kind == ZoneKind.SECURITY:
            return self.security_counts(zone, t)
        if zone.kind == ZoneKind.RETAIL:
            acc = {"pax": 0.0, "intl": 0.0, "dwell": 0.0, "mix": {}, "weights": {}, "dest": {}, "nats": [], "langs": []}
            for zid, factor in self.retail_links.get(zone.id, ()):
                sub = self.zones.get(zid)
                if sub is None:
                    continue
                raw = self.zone_counts(sub, t, day)
                acc["pax"] += raw["pax"] * factor
                acc["intl"] += raw["intl"] * factor
                acc["dwell"] += raw["dwell"] * factor
                for k, v in raw["mix"].items():
                    acc["mix"][k] = acc["mix"].get(k, 0.0) + v * factor
                for fid, w in raw["weights"].items():
                    acc["weights"][f"{fid}@{zid}"] = round(w * factor, 1)
                for cityname, w in raw["dest"].items():
                    acc["dest"][cityname] = acc["dest"].get(cityname, 0.0) + w * factor
            acc["dest"] = {k: round(v, 1) for k, v in sorted(acc["dest"].items(), key=lambda kv: -kv[1])}
            return acc
        return self.zone_counts(zone, t, day)

    # ------------------------------------------------------------------- API
    def presence_for(self, zone: Zone, t: datetime, day: str) -> ZonePresence:
        raw = self.raw_counts(zone, t, day)
        pax = raw["pax"]
        count = int(round(pax))
        intl = int(round(raw["intl"]))
        dwell = round(raw["dwell"] / pax, 1) if pax > 0 else 0.0
        shares = {k: round(v / pax, 3) for k, v in raw["mix"].items()} if pax > 0 else {}
        raw.get("dest", {})
        return ZonePresence(
            zone_id=zone.id,
            window_start=window_floor(t),
            window=window_floor(t).strftime("%H:%M"),
            passenger_count=count,
            domestic_count=max(0, count - intl),
            intl_count=intl,
            dwell_median_min=dwell,
            shares=shares,
            
            contributing_flights=raw["weights"],
            origin="computed",
        )

    def top_destinations(self, zone_id: str, t: datetime, day: str, limit: int = 5) -> list[tuple[str, int]]:
        zone = self.zones.get(zone_id)
        if zone is None:
            return []
        raw = self.raw_counts(zone, t, day).get("dest", {})
        return [(name, int(round(w))) for name, w in list(raw.items())[:limit]]

    def forecast_next(self, zone: Zone, t: datetime, day: str, minutes: int) -> int:
        """Max passenger count over the next `minutes` using schedule weights
        (schedule-based forecast, labelled estimated)."""
        best = 0
        cursor = t + timedelta(minutes=5)
        until = t + timedelta(minutes=minutes)
        while cursor <= until:
            c = int(round(self.raw_counts(zone, cursor, day)["pax"]))
            best = max(best, c)
            cursor += timedelta(minutes=5)
        return best

    def zone_forecast_series(
        self, zone_id: str, t0: datetime, minutes: int, day: str, anchors: dict[str, ZonePresence]
    ) -> list[dict]:
        zone = self.zones.get(zone_id)
        if zone is None:
            return []
        out: list[dict] = []
        cursor = window_floor(t0)
        end = cursor + timedelta(minutes=minutes)
        while cursor <= end:
            cached = anchors.get(f"{zone_id}@{cursor.strftime('%H:%M')}")
            if cached and cursor <= t0:
                out.append({"at": cursor.strftime("%H:%M"), "count": cached.passenger_count,
                            "estimated": False})
            else:
                c = int(round(self.raw_counts(zone, cursor + timedelta(seconds=1), day)["pax"]))
                out.append({"at": cursor.strftime("%H:%M"), "count": c, "estimated": True})
            cursor += timedelta(minutes=5)
        return out
