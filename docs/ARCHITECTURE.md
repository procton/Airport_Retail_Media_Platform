# Architecture (AGENTS §5)

```text
                        FRONTEND (React + TypeScript, Vite)
        Admin | Retailer | Media Manager | Airline | Passenger screens | /claim
        REST (fetch /api/*)   ─────   WebSocket /ws (state + slots + events)
                                        ▲                 │
                     ┌──────────────────┴─────────────────▼──────────────────┐
                     │                 FASTAPI  (backend/app/api)            │
                     │  routes delegate → services; validation via Pydantic  │
                     └───────┬───────────────┬───────────────┬───────────────┘
         simulation control  │               │ queries        │ claims / pins / rules
                     ┌───────▼───────┐  ┌────▼─────┐  ┌──────▼───────┐
                     │ SIMULATOR     │  │ METRICS  │  │ PROMOTIONS   │
                     │ engine.py     │  │ learning ├── │ claims.py    │
                     │  · clock      │  │ exposure │  │ (expiry/run, │
                     │  · event loop │  └────┬─────┘  │  family,     │
                     │  · injections │       │        │  idempotent) │
                     │  · snapshots  │       │        └──────────────┘
                     └───┬───┬───┬───┘       │
      presence/profiles  │   │   │  playback │            providers/
      (presence/, prof.) │   │   └─► playback.py ─ decisions/ pipeline.py
                         │   │         │ (slot planner, virtual playback, pinned)
                         │   │         └────────► scoring (calibrated sm-1.0)
                         ▼   ▼
            ┌──────────────────────────┐   ┌──────────────────────────────┐
            │ adapters/ (aodb, aidx,   │──►│ persistence/                 │
            │ acris) → canonical only  │   │ models + DAO (SQLAlchemy)    │
            └──────────────────────────┘   │ alembic migrations / SQLite  │
                                           └──────────────────────────────┘
                       EventBus (WS fanout)          evidence_records
```

## Logical flow (§5)

```text
Source payload → adapter → canonical entity/event → persisted evidence
→ state projection → presence calculation → campaign decision (filter→score→rules→validate)
→ playlist/playback → impression/scan/redemption → dashboards
```

Frontend never computes authoritative presence, eligibility, scores, revenue
or promo validity: it renders server state (allowed: formatting, countdown
interpolation).

## One simulation engine

Single FastAPI worker owns ONE engine (backend/app/services/simulator/engine.py):
started in app lifespan, one event loop task drives

- simulation clock (`clock.py`: UTC sim day 2026-10-14, speeds 1×/10×/60×,
  pause, jump, backward jump = new run),
- slot cadence (15 s per screen) + immediate re-plan on injected events,
- batched persistence + EventBus publication (WS push).

Control commands serialize on an asyncio lock (`ctl()`) so pause/jump/reset
ordering is preserved; all role views share the same state — role switching
never forks the simulation.

## Clock & runs

| Action | Behavior |
|---|---|
| forward jump | state recomputed to target; skipped UI animation not replayed; exposure accounting continues from target |
| backward jump / reset | `run-<ts>` new run, seed reconstruction + replayable injected `FlightEvent`s re-applied through the adapters; per-run tables keyed by `run_id` (tokens/decisions/exposures); previous-run promo tokens stay invalid |
| pause | clock frozen; injections/claims work at frozen sim time |

Manual pin/override state is operator demo state and clears on a new run;
media rules (competitor gap/frequency window/ε) persist via `rule_config`.

## Presence (§8)

5-minute `ZonePresence` per zone: per-flight dep-leg weight bands
(0.10 / 0.35 / 1.00 ramp documented in presence.py), gate catchment
coupling between neighbouring zones, ACRIS queue contribution, plus
per-flight synthetic profiles (purpose/party/age/language leanings by
route/time-of-day rules). All decisions and KPIs read the same engine
object — no view keeps its own crowd counters.

## Decision pipeline (§10)

`pipeline.evaluate` per slot:
profile → hard filters (status/approval, placement, intl/domestic share,
dwell floor, crowd floor, budget/daily/pacing) → score
(`final_score = clamp01(0.9918 × match^0.905 × boost^0.4105)`, sm-1.0)
→ rules (boarding priority context, competitor gap, frequency window, exploration ε)
→ pinned candidate wins only among ELIGIBLE candidates
→ winner, recorded with profile snapshot, candidate rejections, override
and validation, persisted per run.

The calibrated score uses audience/context weights from the persisted Admin
rule configuration:
`0.9918 × match^(0.905 × audience_weight) × boost^(0.4105 × context_weight)`.
Both weights default to `1.0`, preserving the worked example, and are bounded
to `0..2`.

Safe fallback = house creative (never bypasses approval/safety/placement).
AI provider boundary (creative assistant) returns structured proposals only.

## Claims / promotions (§17)

`claims.py` validates run + expiry (token ← planner-issued promo window),
records scan/page-open separately from redemption, idempotent redeem,
bounded family sharing (companion phone token, one-time family bundle),
and never issues tokens for paused-forever runs (run-scoped validity).

## Realtime

EventBus topics (WS `/ws`): `slots.*` (per screen), `presence`, `flights.*`,
`controls`, `campaign.status`, `media-rules`, `incidents`, `redemption.live`.
The full envelope/topic contract is in `docs/WS_CONTRACT.md`. Two-wall-clock-second propagation target is met by immediate event-driven
re-plan; the 15 s slot cadence is independent (§7).
