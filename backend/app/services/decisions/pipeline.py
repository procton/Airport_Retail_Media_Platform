"""Evidence-first decision pipeline (AGENTS §10).

Per slot: profile → filter → score → business rules → validate → choose/log.
Every executed decision cites persisted evidence and stores a full audit.
Learning updates engagement estimates (metrics.learning), not eligibility.

Hard-filter semantics (documented; assumptions 6/17):
- `min_intl_share` gates the *international audience share* of the catchment.
- `domestic` campaign setting: "D" requires intl share ≤ 0.5 (domestic-majority
  crowd), "I" requires ≥ max(min_intl_share, 0.5), "any" no gate.
- placement: zones (`zone_ids`) and terminal. Missing placement info = ineligible
  (fail-closed).
- budget/daily cap/pacing are spending gates; pacing slows a campaign inside the
  first half-day once it has consumed its configured share of the day cap
  (documented constant PACING_FRACTION/HALF_DAY boundary).
- decorrelated: competitor separation keeps same-advertiser creatives off one
  screen within ADvertiser STALENESS gap.
- airline boarding priority: a screen inside an airline boarding window may run
  *only* airline-priority content if that airline sets one (rules context).
Rejects are explicit reason strings — nothing is implicit.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from ...domain.canonical import Campaign, CampaignStatus, Flight, Screen, TriggerKind, ZonePresence
from . import scoring

DECISION_MODEL_VERSION = "sm-1.0"
COMPETITOR_GAP_MIN = 10.0
PACING_FRACTION = 0.75          # fraction of daily cap that pacing protects
PACING_BOUNDARY_HOUR = 13       # slowdown applies until 13:00 sim time
FREQUENCY_WINDOW_MIN = 60.0


@dataclass
class FlightDelay:
    flight: Flight
    delay_min: int


@dataclass
class SlotContext:
    t: datetime
    run_id: str
    screen: Screen
    zone_id: str
    presence: ZonePresence
    catchment: dict               # {"pax","intl","dwell","shares","dest"}
    flights: dict[str, tuple[Flight, float]]    # leg -> (flight, weight)
    delays: list[FlightDelay] = field(default_factory=list)
    boarding_airline: str | None = None
    festival_day: bool = False


@dataclass
class Candidate:
    campaign_id: str
    name: str
    match: float
    boost: float
    score: float
    eligible: bool
    reasons: list[str] = field(default_factory=list)
    pinned: bool = False
    creative_id: str | None = None


@dataclass
class DecisionOutcome:
    slot_at: datetime
    screen_id: str
    zone_id: str
    candidates: list[Candidate]
    winner: Candidate | None
    fallback: bool
    fallback_reason: str = ""
    override: tuple[str, str] | None = None  # (campaign_id, reason) when a pinned candidate won
    exploration: dict | None = None          # ε-greedy pick details (logged; default off)
    record: dict = field(default_factory=dict)


class RulesContext:
    """Play bookkeeping kept by the playback planner; decisions read only."""

    def __init__(self) -> None:
        self.recent_plays: dict[str, list[tuple[datetime, str]]] = {}
        self.category_last: dict[tuple[str, str], tuple[datetime, str]] = {}
        self.spend_today: dict[str, float] = {}
        self.spend_total: dict[str, float] = {}
        self.impress_today: dict[str, int] = {}
        self.boarding_window: dict[str, str] = {}       # gate -> airline
        # Admin-tunable global rules (AGENTS §12): defaults keep the documented
        # worked example; overrides are persisted in rule_config ("media_rules").
        self.gap_min: float = COMPETITOR_GAP_MIN
        self.freq_window_min: float = FREQUENCY_WINDOW_MIN
        self.exploration_epsilon: float = 0.0  # 0 = pure highest-score (worked example)
        self.audience_weight: float = 1.0
        self.context_weight: float = 1.0

    def register_play(self, at: datetime, screen_id: str, campaign: Campaign | None, viewers: int = 0) -> None:
        if campaign:
            self.recent_plays.setdefault(screen_id, []).append((at, campaign.id))
            self.category_last[(screen_id, campaign.advertiser_id)] = (at, campaign.id)
            self.spend_today[campaign.id] = self.spend_today.get(campaign.id, 0.0) + 0.0
            self.impress_today[campaign.id] = self.impress_today.get(campaign.id, 0) + max(0, viewers)

    def frequency_count(self, screen_id: str, campaign_id: str, t: datetime) -> int:
        since = t - timedelta(minutes=self.freq_window_min)
        return sum(1 for at, cid in self.recent_plays.get(screen_id, []) if cid == campaign_id and at >= since)

    def competitor_gap_clear(self, screen_id: str, campaign: Campaign, at: datetime) -> tuple[bool, str]:
        """Separation is between *confusable* creatives: two DIFFERENT
        campaigns of the same advertiser never rotate back-to-back; the
        campaign's own repeat is governed by the frequency cap instead."""
        if not campaign.advertiser_id:
            return True, ""
        last = self.category_last.get((screen_id, campaign.advertiser_id))
        if last and last[1] != campaign.id and (at - last[0]).total_seconds() < self.gap_min * 60:
            return False, f"competitor-separation<{self.gap_min:.0f}min({campaign.advertiser_id})"
        return True, ""





def evaluate(
    campaigns: list[Campaign],
    creatives: dict[str, list[dict]],
    ctx: SlotContext,
    ledger: RulesContext,
    pinned: tuple[str, str] | None = None,        # (campaign_id, reason)
    cache: dict | None = None,                    # zone eval cache (planner-owned)
    bucket: tuple | None = None,                  # (15s index, world_version)
) -> DecisionOutcome:
    zone_key = (ctx.zone_id, bucket[0], bucket[1]) if (cache is not None and bucket is not None) else None
    zone_base = cache.get(zone_key) if zone_key else None
    if zone_base is None:
        # Stage 1 — zone-static math (catchment profile, placement, budget,
        # scoring). Shared by every screen in the zone within this bucket;
        # per-screen rules/boosts run in stage 2. Placement checks read
        # ctx.screen's terminal, invariant within the zone (zone_id encodes it).
        zone_base = []
        share_d = dict(ctx.catchment.get("shares", {}))
        catch_pax = int(ctx.catchment.get("pax", 0))
        dest_w = ctx.catchment.get("dest", {})
        dwell = ctx.catchment.get("dwell", 0.0)
        for c in campaigns:
            match = scoring.audience_match(
                c.target_segments, share_d, dest_w, catch_pax,
                dwell=dwell, campaign_dwell_floor=c.dwell_floor_min,
            )
            boost, why = _boost_zone(c, ctx)
            score = scoring.final_score(match, boost, ledger.audience_weight, ledger.context_weight)
            cj = _hard_filters_zone(c, ctx, ledger)
            zone_base.append((c, match, boost, why, cj))
        if zone_key:
            if len(cache) > 256:  # type: ignore[union-attr]
                cache.clear()  # type: ignore[union-attr]
            cache[zone_key] = zone_base  # type: ignore[index]

    # Stage 2 — per-screen rules: frequency cap, competitor separation,
    # boarding-held gate, boarding boost; then pinned/exploration selection.
    candidates: list[Candidate] = []
    for c, match, zboost, zwhy, cj in zone_base:
        rj = list(cj)
        freq = ledger.frequency_count(ctx.screen.id, c.id, ctx.t)
        if freq >= c.frequency_cap_per_screen_hour:
            rj.append(f"frequency_cap({freq}>={c.frequency_cap_per_screen_hour}/hour")
        clear, why = ledger.competitor_gap_clear(ctx.screen.id, c, ctx.t)
        if not clear:
            rj.append(why)
        boarding = ctx.boarding_airline
        boost, _wwhy = zboost, zwhy
        if c.airline_priority and boarding and c.airline_iata != boarding:
            rj.append(f"airline-boarding-window held by {boarding}")
        if (boarding and c.airline_iata == boarding and c.trigger == TriggerKind.BOARDING):
            boost = c.trigger_boost
        score = scoring.final_score(match, boost, ledger.audience_weight, ledger.context_weight)
        candidates.append(
            Candidate(
                campaign_id=c.id, name=c.name, match=match, boost=boost, score=score,
                eligible=not rj, reasons=rj,
                pinned=bool(pinned and pinned[0] == c.id),
            )
        )
    return _select(ctx, candidates, pinned, ledger)


def _select(
    ctx: SlotContext,
    candidates: list[Candidate],
    pinned: tuple[str, str] | None,
    ledger: RulesContext,
) -> DecisionOutcome:
    eligible = [x for x in candidates if x.eligible]
    eligible.sort(key=lambda x: (-x.score, -x.match, x.campaign_id))
    pinned = pinned if pinned is not None else (None, None)  # type: ignore[assignment]
    pinned_cand = next((x for x in eligible if x.pinned), None)
    exploration: dict | None = None
    if pinned_cand is not None:
        winner = pinned_cand  # manual pin wins among ELIGIBLE candidates only
    else:
        winner = eligible[0] if eligible else None
        # Exploration (AGENTS §26/§12; admin-tunable, default 0 = off):
        # ε-safe, deterministic per (time, screen, run) draw — a decoy eligible
        # candidate replaces the top scorer ONLY when ε > 0. The draw and the
        # pick are stored in the decision record; eligibility stays untouched.
        eps = ledger.exploration_epsilon
        if eps > 0 and len(eligible) > 1:
            import random as _random
            rng = _random.Random(f"explore|{ctx.t.isoformat()}|{ctx.screen.id}|{ctx.run_id}|{len(eligible)}")
            if rng.random() < eps:
                pool = [x for x in eligible[1:]]
                alt = pool[rng.randrange(len(pool))]
                exploration = {
                    "campaign_id": alt.campaign_id, "score": alt.score,
                    "reason": f"exploration draw (ε={eps:.3f})",
                }
                winner = alt
    return DecisionOutcome(
        slot_at=ctx.t,
        screen_id=ctx.screen.id,
        zone_id=ctx.zone_id,
        candidates=candidates,
        winner=winner,
        fallback=winner is None,
        override=(pinned[0], pinned[1]) if pinned and winner is not None and winner.pinned else None,  # type: ignore[index]
        exploration=exploration,
    )


def _boost_zone(c: Campaign, ctx: SlotContext) -> tuple[float, str]:
    """Zone-static boost part (delay/festival); boarding boost is per screen."""
    if c.trigger == TriggerKind.DELAY:
        for d in ctx.delays:
            if d.delay_min >= c.trigger_delay_min:
                return c.trigger_boost, f"delay-trigger({d.flight.designator}+{d.delay_min}min)"
    if ctx.festival_day:
        return c.festival_day_boost, "festival-day"
    return 1.0, ""


def _hard_filters_zone(c: Campaign, ctx: SlotContext, ledger: RulesContext) -> list[str]:
    """Hard filters without screen-dependent bits (60x zone sharing)."""
    rej: list[str] = []
    if c.status != CampaignStatus.APPROVED:
        rej.append(f"status:{c.status.value}")
    hour = ctx.t.hour
    if hour < c.hours_start or hour > c.hours_end:
        rej.append(f"schedule:{hour} not in [{c.hours_start},{c.hours_end}]")
    if c.terminal and c.terminal != ctx.screen.terminal:
        rej.append(f"placement:terminal {ctx.screen.terminal} != {c.terminal}")
    if c.zone_ids and ctx.zone_id not in c.zone_ids:
        rej.append(f"placement:zone {ctx.zone_id} not in {c.zone_ids}")
    shares = ctx.catchment.get("shares", {})
    crowd = int(ctx.catchment.get("pax", 0))
    intl_share = shares.get("intl_share", 0.0) or 0.0
    dwell = ctx.catchment.get("dwell", 0.0) or 0.0
    if c.domestic == "I" and intl_share < max(0.5, c.min_intl_share):
        rej.append(f"audience:intl_share {intl_share:.2f} < {max(0.5, c.min_intl_share):.2f}")
    if c.domestic == "D" and intl_share > 0.5:
        rej.append(f"audience:domestic-majority required (intl {intl_share:.2f} > 0.5)")
    if c.min_intl_share > 0 and intl_share < c.min_intl_share:
        rej.append(f"audience:intl_share floor {c.min_intl_share:.2f}")
    if c.hard_dwell_min > 0 and dwell < c.hard_dwell_min:
        rej.append(f"dwell<{c.hard_dwell_min}min (got {dwell:.0f})")
    if c.min_crowd > 0 and crowd < c.min_crowd:
        rej.append(f"min_crowd<{c.min_crowd} (got {crowd})")
    if c.destination_targets:
        dest_weights = ctx.catchment.get("dest", {})
        if not any(dest_weights.get(d, 0.0) > 0 for d in c.destination_targets):
            rej.append(f"destination not served: {c.destination_targets}")
    if ledger.spend_total.get(c.id, 0.0) >= c.budget_total:
        rej.append("budget_total")
    if ledger.spend_today.get(c.id, 0.0) >= c.daily_cap:
        rej.append("daily_cap")
    if ledger.spend_today.get(c.id, 0.0) >= 0.5 * c.daily_cap and ctx.t.hour < PACING_BOUNDARY_HOUR:
        rej.append("pacing:protected capacity for first half-day")
    return rej


def build_record(
    outcome: DecisionOutcome,
    ctx: SlotContext,
    creative_id: str | None,
    evidence_rows: list[dict],
    validation: dict,
    model_version: str = DECISION_MODEL_VERSION,
) -> dict:
    return {
        "id": f"dec:{ctx.slot_at.strftime('%H%M%S')}-{ctx.screen.id}",
        "run_id": ctx.run_id,
        "screen_id": ctx.screen.id,
        "screen_kind": ctx.screen.kind.value,
        "zone_id": ctx.zone_id,
        "slot_at": ctx.slot_at.isoformat(),
        "profile_snapshot": {
            "pax": int(round(ctx.catchment.get("pax", 0))),
            "intl_share": round(ctx.catchment.get("shares", {}).get("intl_share", 0.0), 3),
            "dwell_min": round(ctx.catchment.get("dwell", 0.0), 1),
            "shares": {k: round(v, 3) for k, v in ctx.catchment.get("shares", {}).items()},
            "top_destinations": sorted(
                ctx.catchment.get("dest", {}).items(), key=lambda kv: -kv[1]
            )[:3],
        },
        "contributing_flights": {fid: round(w, 1) for fid, (f, w) in ctx.flights.items()},
        "delays": [(d.flight.id, d.delay_min) for d in ctx.delays],
        "boarding_airline": ctx.boarding_airline,
        "evidence": evidence_rows,
        "candidates": [
            {
                "campaign_id": x.campaign_id,
                "match": x.match,
                "boost": x.boost,
                "score": x.score,
                "eligible": x.eligible,
                "pinned": x.pinned,
                "reasons": x.reasons,
            }
            for x in outcome.candidates
        ],
        "winner": {
            "campaign_id": outcome.winner.campaign_id,
            "match": outcome.winner.match,
            "boost": outcome.winner.boost,
            "score": outcome.winner.score,
            "creative_id": creative_id,
        }
        if outcome.winner
        else None,
        "fallback": outcome.fallback,
        "override": (
            {"campaign_id": outcome.override[0], "reason": outcome.override[1]}
            if outcome.override
            else None
        ),
        "exploration": outcome.exploration,
        "validation": validation,
        "model_version": model_version,
    }
