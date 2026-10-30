"""Canonical domain models.

Everything the business logic consumes is expressed in this vocabulary. Source
payloads never leak beyond `app/adapters`. All entities are Pydantic models so
they can cross the API/WebSocket boundary unchanged.

Notes:
- Identifiers are stable strings (e.g. flight keys are `aodb:<id>`).
- Evidence is always referenced by evidence id, never embedded raw source data.
- Per-flight passenger profiles are synthetic aggregates (see presence.profiles).
"""
from __future__ import annotations

from datetime import datetime, timedelta
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

SimTime = datetime


class Direction(StrEnum):
    ARRIVAL = "A"
    DEPARTURE = "D"


class FlightStatus(StrEnum):
    """Projection of a flight leg at some simulation time (derived, not snapshot)."""

    SCHEDULED = "SCHEDULED"
    CHECKIN = "CHECKIN"
    BOARDING = "BOARDING"
    GONE = "GONE"  # airborne / already on stand departure slot past
    ARRIVING = "ARRIVING"
    ARRIVED = "ARRIVED"
    CANCELLED = "CANCELLED"


class Termination(StrEnum):
    NONE = "NONE"
    CNL = "CNL"


# ---------------------------------------------------------------- flights ---
class Airline(BaseModel):
    iata: str
    icao: str
    name: str
    market: Literal["domestic-lcc", "domestic-fs", "international", "regional-lcc"]
    is_lowcost: bool = False


class AircraftType(BaseModel):
    icao: str
    seats: int
    widebody: bool


class FlightKey(BaseModel):
    airline_iata: str
    number: str
    dep_date: str  # ISO date of the departing leg


class Flight(BaseModel):
    id: str  # `aodb:<id>` or `gen:<n>` / `wx:<n>` for worked example
    source: Literal["aodb", "generated", "worked-example"] = "aodb"
    aodb_flight_id: str
    linked_flight_id: str | None = None
    airline_iata: str
    airline_icao: str
    flight_number: str
    direction: Direction
    service_type: str = "J"
    flight_nature: Literal["D", "I"]
    origin: str
    destination: str
    terminal: str  # T1 | T2
    sched_std: datetime  # STA_STD (paired scheduled instant)
    tobt: datetime | None = None
    tsat: datetime | None = None
    etd: datetime | None = None  # ETD on D / ETA on A (paired)
    eldt: datetime | None = None
    aldt: datetime | None = None
    aibt: datetime | None = None  # AIBT on A / AOBT on D (paired) -- engine-off time for back resource
    stand: str | None = None
    gate: str | None = None  # boarding gate for departures; arrivals if assigned
    checkin_counters: str | None = None
    baggage_belt: str | None = None
    aircraft_reg: str | None = None
    aircraft_type: str | None = None
    seats: int = 0
    pax: int = 0
    status_raw: str = ""  # snapshot status from the source (ARR/DEP/CNL)
    delay_codes: list[str] = []
    codeshares: list[str] = []
    handler: str | None = None
    last_update_utc: str | None = None  # snapshot time, not per-record freshness
    cancelled: bool = False
    injected_delay_min: int = 0
    gate_override: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)

    @property
    def route_label(self) -> str:
        return f"{self.origin}{self.destination}"

    @property
    def designator(self) -> str:
        return f"{self.airline_iata}{self.flight_number}"

    def effective_std(self) -> datetime:
        """Scheduled take-off, including injected delay."""
        base = self.sched_std
        return base + timedelta(minutes=self.injected_delay_min)

    def boarding_start(self) -> datetime:
        return self.effective_std() - timedelta(minutes=40)

    def gate_close(self) -> datetime:
        return self.effective_std() - timedelta(minutes=5)


class FlightEvent(BaseModel):
    """A source amendment (AIDX notification / injected operator action).

    Effective time = simulated clock moment the amendment becomes authoritative.
    """

    id: str
    flight_leg_id: str
    kind: Literal["delay", "gate_change", "status_change", "cancel"]
    at: SimTime                      # effective time (simulation time)
    delay_minutes: int = 0
    new_gate: str | None = None
    new_status: str | None = None
    source: Literal["aidx", "operator", "generated"] = "aidx"
    message_id: str | None = None
    timestamp_source: SimTime | None = None  # source message timestamp if supplied
    evidence_id: str | None = None


class GateAssignment(BaseModel):
    flight_leg_id: str
    gate: str
    terminal: str
    kind: Literal["stand", "gate"]
    valid_from: datetime
    valid_to: datetime | None = None
    source: str = "aodb"


# ---------------------------------------------------------------- airport ---
class Terminal(BaseModel):
    name: str
    kind: Literal["domestic", "international", "mixed"]


class ZoneKind(StrEnum):
    GATE = "gate"
    RETAIL = "retail"
    SECURITY = "security"
    CHECKPOINT = "checkpoint"


class Zone(BaseModel):
    id: str
    terminal: str
    name: str
    kind: ZoneKind
    concourse: str | None = None  # e.g. T2-C
    gates: list[str] = []
    # coupling towards other zones (share of audience spillover)
    neighbours: dict[str, float] = {}


class Checkpoint(BaseModel):
    id: str
    terminal: str
    name: str
    feeds_zone: str | None = None


class QueueMeasurement(BaseModel):
    checkpoint_id: str
    measured_at: SimTime
    wait_min: float
    headcount_est: int
    source: str = "acris-mock"


class ScreenKind(StrEnum):
    LGATE = "gate"       # portrait by gate podium
    LWIDE = "wide"       # landscape visa wall
    LTOTE = "tote"       # totem in retail
    LDIGI = "digital"    # digital mall banner


class Screen(BaseModel):
    id: str
    terminal: str
    concourse: str
    zone_id: str
    zone: str
    gate: str | None = None
    nearest_gates: list[str] = []
    kind: ScreenKind
    width_px: int = 1080
    height_px: int = 1920
    online: bool = True
    degraded: bool = False
    last_seen: SimTime | None = None
    offline_reason: str | None = None

    @property
    def aspect(self) -> Literal["9:16", "16:9"]:
        return "9:16" if self.height_px >= self.width_px else "16:9"


# ---------------------------------------------------------------- media ----
class Advertiser(BaseModel):
    id: str
    name: str
    category: str  # competitor_group key
    colour: str = "#7c3aed"


class Outlet(BaseModel):
    id: str
    name: str
    terminal: str
    zone_id: str
    zone: str
    kind: Literal["duty-free", "coffee", "fnb", "retail", "services", "toys"]
    advertiser_id: str | None = None
    dwell_focus: bool = False


class Creative(BaseModel):
    id: str
    campaign_id: str
    variant: Literal["a", "b"] = "a"
    headline_en: str
    headline_alt: str
    body_en: str = ""
    body_alt: str = ""
    cta: str = ""
    bg: str = "#0ea5e9"
    fg: str = "#ffffff"
    image: str = ""  # inline SVG motif key, never remote
    show_code: bool = False


class CampaignStatus(StrEnum):
    DRAFT = "DRAFT"
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    PAUSED = "PAUSED"
    COMPLETE = "COMPLETE"


class TriggerKind(StrEnum):
    NONE = "none"
    DELAY = "delay"
    GATE_CHANGE = "gate_change"
    BOARDING = "boarding"
    FESTIVAL = "festival"


class Campaign(BaseModel):
    id: str
    advertiser_id: str
    outlet_id: str
    name: str
    status: CampaignStatus = CampaignStatus.PENDING
    created_at: SimTime | None = None

    # audience (0..1 weights / hard filters)
    domestic: Literal["any", "D", "I"] = "any"
    min_intl_share: float = 0.0
    target_segments: dict[str, float] = {}         # e.g. {"holiday": 0.35, "international": 0.35, "adult25_54": 0.30}
    hard_dwell_min: int = 0
    min_crowd: int = 0
    age_targets: list[str] = []
    destination_targets: list[str] = []
    region_targets: list[str] = []

    # placement
    zone_ids: list[str] = []
    terminal: str | None = None
    hours_start: int = 0
    hours_end: int = 23

    # limits
    budget_total: float = 1000.0
    daily_cap: float = 400.0
    frequency_cap_per_screen_hour: int = 4
    pacing_rate: float = 0.8   # fraction of cap per half-day by default
    dwell_floor_min: float = 60.0  # scoring dwell-benchmark (documented)

    # triggers
    trigger: TriggerKind = TriggerKind.NONE
    trigger_delay_min: int = 30
    trigger_boost: float = 1.0
    festival_day_boost: float = 1.0

    # airline co-marketing
    airline_iata: str | None = None
    airline_priority: bool = False

    # category affinity calibration (audience fit extra weight, see scoring)
    category_affinity: float = 1.0

    cpm: float = 1.25


class PromoCode(BaseModel):
    id: str
    campaign_id: str
    code: str
    kind: Literal["standard", "family"] = "standard"
    window_start: SimTime | None = None
    window_end: SimTime | None = None
    flight_leg_id: str | None = None
    family_cap: int = 2
    value: float = 0.0


class Impression(BaseModel):
    slot_id: str
    screen_id: str
    campaign_id: str | None
    creative_id: str | None
    at: SimTime
    est_viewers: int = 0      # estimated exposure opportunities
    estimated: bool = True


class Redemption(BaseModel):
    id: str
    token: str
    promo_code_id: str
    campaign_id: str
    outlet_id: str
    at: SimTime
    mode: Literal["phone", "simulated-engagement"] = "phone"
    seat_share: str | None = None
    revenue_value: float = 0.0


# ------------------------------------------------------------- presence ----
class SegmentShares(BaseModel):
    """Mutually exclusive segment shares; separate dimensions documented."""
    purpose_business: float = 0.0
    purpose_holiday: float = 0.0
    purpose_vfr: float = 0.0
    purpose_student: float = 0.0
    purpose_religious: float = 0.0
    party_solo: float = 0.0
    party_couple: float = 0.0
    party_family_with_children: float = 0.0
    party_group: float = 0.0
    children_pax_share: float = 0.0
    adults_25_54: float = 0.0
    premium_cabin: float = 0.0
    frequent_flyer: float = 0.0
    female: float = 0.0
    intl_share: float = 0.0
    top_destinations: list[tuple[str, float]] = []  # (city, weighted share)
    nationalities: list[str] = []
    languages: list[str] = []

    def shares_by_name(self) -> dict[str, float]:
        d: dict[str, float] = {}
        for k, v in self.model_dump(exclude={"top_destinations", "nationalities", "languages"}).items():
            d[k] = v
        for k in ("purpose_holiday", "party_family_with_children", "adults_25_54", "intl_share"):
            # shared membership short-cuts for targeting
            d[k.replace("purpose_", "")] = d.get(k, 0.0)
        d["international"] = d.get("intl_share", 0.0)
        d["adult25_54"] = d.get("adults_25_54", 0.0)
        d["family"] = d.get("party_family_with_children", 0.0)
        return d


class FlightProfile(BaseModel):
    flight_leg_id: str
    origin_city: str
    origin_country: str
    origin_region: str
    domestic: bool
    shares: SegmentShares
    dwell_hint_min: float
    festival: bool = False
    evidence_ids: list[str] = []
    synthetic: bool = True


class ZonePresence(BaseModel):
    zone_id: str
    window_start: SimTime
    window: str  # "HH:MM" label of the 5-min window
    passenger_count: int
    domestic_count: int
    intl_count: int
    dwell_median_min: float
    next30_count: int = 0          # forecast, estimated
    next120_count: int = 0         # forecast, estimated (retailer 2h)
    shares: dict[str, float] = {}  # weighted segment mixture (documented)
    top_destinations: list[tuple[str, int]] = []
    nationalities: list[str] = []
    languages: list[str] = []
    contributing_flights: dict[str, float] = {}
    origin: Literal["computed", "forecast"] = "computed"


# --------------------------------------------------------------- control ----
class SimulationEvent(BaseModel):
    id: str
    at: SimTime | None = None  # effective sim time (None => wall processing time)
    kind: str
    subject: str  # flight id / screen id
    payload: dict = {}
    origin: str = "manual"
    evidence_id: str | None = None


class FeedHealth(BaseModel):
    source: str
    active_adapter: str
    healthy: bool
    last_message_at: SimTime | None = None
    messages_last_minute: int = 0
    note: str = ""


class Incident(BaseModel):
    id: str
    severity: Literal["low", "medium", "high"]
    title: str
    detail: str = ""
    where: str = ""
    status: Literal["open", "ack", "fixing", "resolved"] = "open"
    owner: str = ""
    opened_at: SimTime
    resolved_at: SimTime | None = None
    related: str = ""
