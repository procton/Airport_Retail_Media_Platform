# AGENTS.md — Airport Retail Media Platform Challenge

## 1. Mission

Build a locally runnable, demo-ready prototype of an airport retail media platform.

The platform schedules ads and promotions on airport screens using flight movements, passenger-flow estimates, campaign targeting, and live engagement metrics.

The submission must:
- Run locally with one command.
- Work offline without paid services or API keys.
- Include a fully working, deployed playground URL for reviewers during the challenge.
- Look like a finished product.
- Demonstrate compelling cross-role cause and effect in a 15-minute presentation.

The central demonstration is:

> Inject a flight delay → update the airline dashboard and passenger-presence estimate → change the ad at the affected gate → claim the offer on a phone → show the redemption and attributed revenue on the retailer dashboard.

This must be a functioning end-to-end workflow, not disconnected animations or hard-coded dashboard counters.

The locked technology stack in Section 3 is the required implementation choice. It takes precedence over conflicting technology guidance elsewhere in the repository.

---

## 2. Working Instructions and Requirement Labels

### Before implementation

1. Inspect the repository, existing code, tooling, assets, and attachments.
2. Preserve useful existing code where compatible with the locked stack.
3. Inspect reference fixtures and schemas under repository-root `playground/`.
4. Create a requirement checklist covering every mandatory feature.
5. Record missing information and assumptions explicitly.
6. Confirm the implementation follows the locked stack.
7. Create a phased plan centered on an early working vertical slice.

### Implementation principles

- Deliver a complete vertical slice early: feed → canonical state → presence → decision → screen → claim → dashboard.
- Use one backend-owned simulation clock.
- Isolate source adapters from business logic.
- Make all role views read from shared canonical state.
- Prefer coherent functionality over disconnected feature breadth.
- Do not silently downgrade mandatory requirements.
- Implement stretch features only after mandatory workflows are reliable.
- Test relevant behavior after changes.
- Never claim a feature, deployment, or test works without verification.
- Document limitations honestly.
- Preserve supplied fixtures and upstream schemas unchanged.
- Distinguish organizer requirements from implementation decisions.
- Do not invent facts about reference files that have not been inspected.

### Labels

- **MUST**: Mandatory challenge requirement.
- **SHOULD**: Optional challenge feature earning extra credit.
- **IMPLEMENTATION DECISION**: A project-specific choice the agent must follow.
- **IMPLEMENTATION GUIDANCE**: Suggested approach within the required architecture.
- **OPEN QUESTION**: Unspecified or ambiguous detail requiring a documented assumption.

The organizer permits an open stack. Section 3 locks the submitter's implementation choice; it is not an additional organizer restriction.

---

## 3. Locked Technology Stack and Architecture

### Mandatory implementation decision

The project is Python-first, with a separate React frontend.

Do not substitute frameworks, databases, or architecture without explicit user approval.

| Layer | Required technology |
|---|---|
| Backend language | Python |
| Backend framework | FastAPI |
| Validation | Pydantic |
| Frontend | React + TypeScript |
| Database | SQLite |
| Database access | SQLAlchemy |
| Migrations | Alembic |
| API | REST |
| Real-time transport | WebSockets |
| Local orchestration | Docker Compose |
| AI integration | Python provider interfaces with offline mock implementations |

Select compatible, maintained dependency versions at implementation time. Pin dependencies and commit appropriate lockfiles.

Frontend build tooling, styling, charts, and test libraries may be chosen within this stack. Document the choices.

Do not substitute Streamlit, Dash, Gradio, or another Python dashboard framework for React.

### README rationale

Explain:
- Python owns adapters, simulation, presence, forecasting, scoring, evidence validation, and persistence.
- FastAPI provides REST, validation, OpenAPI, and WebSockets.
- React/TypeScript provides polished interactive dashboards, screen rendering, and mobile claims.
- SQLite keeps local operation self-contained.
- SQLAlchemy separates persistence from domain logic.
- Alembic provides reproducible migrations.
- Docker Compose provides one-command startup.
- Offline AI providers require no credentials.

### Backend responsibilities

- Source parsing and canonical normalization.
- Simulation time, event ordering, and flight state.
- Gate assignments and catchments.
- Passenger profiles and presence.
- Forecasts.
- Eligibility, scoring, evidence validation, and fallback.
- Budgets, pacing, frequency limits, and competitor separation.
- Playlist selection and virtual playback.
- Promo expiration, sharing, and redemption validation.
- Metrics and revenue attribution.
- Database writes and shared configuration.
- Real-time event publication.

### Frontend responsibilities

- Presentation and navigation.
- Role/company switching.
- Forms and interactions.
- Maps, charts, tables, and inventory calendar.
- Screen/creative rendering.
- Mobile claims.
- Themes and localization.
- Displaying backend state and explanations.

The frontend must not calculate authoritative presence, campaign scores, eligibility, budget validity, promo validity, or revenue.

Presentation-only formatting and countdown interpolation are allowed.

### Suggested backend organization

```text
backend/
  app/
    main.py
    api/
    adapters/
      aodb/
      aidx/
      acris/
    domain/
    services/
      simulation/
      presence/
      decisions/
      forecasting/
      promotions/
      metrics/
    providers/
    persistence/
    realtime/
    config/
  migrations/
  tests/
```

Names may vary; responsibility boundaries must remain.

API routes delegate to services. Business logic does not parse source payloads. AI providers return structured proposals, not unchecked executable decisions.

### One simulation engine

For this prototype:
- Run one FastAPI application worker.
- Start/stop one engine through application lifecycle management.
- Do not create an engine per request, WebSocket, browser, or role.
- Serialize conflicting simulation-control commands.
- Preserve ordering and use idempotent processing where applicable.

All clients share simulation state.

Multiple workers/replicas require explicit simulation ownership and coordination and are outside the initial architecture.

### SQLite rules

- Use SQLAlchemy and Alembic.
- Persist the database in a Docker volume.
- Keep transactions short.
- Do not share mutable sessions across concurrent tasks.
- Do not hold transactions during provider calls or WebSocket delivery.
- Control concurrent writes and add appropriate indexes.
- Do not block the asynchronous event loop with substantial synchronous database or CPU work.

Choose an asynchronous database approach or a properly isolated synchronous approach. Document and benchmark it.

Do not introduce PostgreSQL, Redis, Kafka, Celery, or microservices without a measured need and user approval.

### Offline providers

Implement provider boundaries for:
1. Creative generation.
2. AI-assisted ranking/recommendations, if used.

Defaults must:
- Work offline without keys.
- Return structured results.
- Be deterministic where needed for tests and demos.
- Produce usable template-based ad pages.
- Support English and the configured second language.

Do not call a remote LLM for every screen slot. Optional calls require timeouts and cannot block fallback playback.

---

## 4. Scope, Roles, and Navigation

### Out of scope

Do not implement:
- Real authentication.
- Real payments.
- Physical screen hardware or production CMS/player integration.
- Production-grade hosting infrastructure.
- Per-passenger data collection.
- Boarding-pass, identity, or device tracking.

A deployed prototype playground is still mandatory.

Targeting is aggregated by flight, zone, and time window.

### Roles: MUST

Provide a header switcher for:
1. Platform Admin.
2. Retailer.
3. Media Manager.
4. Airline Representative.
5. Passenger screen simulator.

There is no login.

Retailer and Airline views also switch between fictional sample companies, including:
- Duty-free retailer.
- Coffee/F&B chain.
- Low-cost airline.
- Full-service airline.

Each role gets:
- One main dashboard.
- Up to three sub-pages.
- One shared design system.
- The same simulation clock.

Use tabs, drawers, and modals to avoid excessive pages.

Role/company switching changes scope, not simulation state.

Use fictional airport, airline, brand, advertiser, and outlet names, subject to the explicitly labelled organizer worked-example scenario.

---

## 5. Canonical Model and Shared State

### MUST separate

- Frontend.
- Backend API.
- Real-time transport.
- Source adapters.
- Canonical domain model.
- Simulation/event processing.
- Presence calculation.
- Decision engine.
- Persistence.

Core business logic consumes canonical entities/events only.

### Logical flow

```text
Source payload
→ adapter
→ canonical entity/event
→ persisted evidence
→ state projection
→ presence calculation
→ campaign decision
→ playlist/playback
→ impression/scan/redemption
→ dashboards
```

### Challenge canonical entities

- Flight.
- GateAssignment.
- AircraftType.
- FlightEvent.
- Terminal.
- Zone.
- Checkpoint.
- QueueMeasurement.
- Screen.
- Advertiser.
- Outlet.
- Campaign.
- Creative.
- PromoCode.
- Impression.
- Redemption.
- ZonePresence.

### Additional internal entities

May include:
- Decision.
- EvidenceRecord.
- Incident.
- InventoryBooking.
- SimulationEvent.
- SimulationRun.
- FeedHealth.
- Airline.
- Vendor.
- RuleConfiguration.
- ScanEvent.

These are internal entities, not claimed external-standard types.

### Consistency

- Approval affects eligibility everywhere.
- Outages affect screen health and playback.
- Gate changes affect assignments, catchments, airline views, and decisions.
- Redemptions update the relevant campaign/outlet.
- Budget, inventory, and performance use shared state.
- Role dashboards must not maintain independent mock datasets.

---

## 6. Reference Data and Adapters

### Location

Reference files are under repository-root `playground/`.

This directory is not the deployed reviewer playground.

Inspect actual headers, payloads, schemas, examples, and licences before implementing mappings.

| Path | Purpose | Status |
|---|---|---|
| `playground/MQI_aodb_flights_2026-10-14_SYNTHETIC.csv` | 320 rows, 160 linked arrival/departure pairs, 33 columns | Synthetic |
| `playground/AIDX_FlightLegNotifRQ_XH960_arrival_ILLUSTRATIVE.xml` | Arrival notification for XH960, matching CSV `aodb_flight_id = 100180` | Hand-written illustration |
| `playground/ACRIS-smart-data-models/` | ACRIS JSON Schemas, Swagger definitions, examples | Copied public-standard files under their own licence |

If files are missing or differ from descriptions:
- Report the discrepancy.
- Do not silently invent replacements.
- Document provisional mappings.

### Default airport

Use **Meridian International**, code `MQI`:
- T1: domestic.
- T2: international.

Airport, city, airline, handler, and registration values are fictional.

Aircraft type values use real ICAO designators; preserve them.

### 6.1 AODB

The CSV is authoritative for the POC source shape.

It includes:
- Schedule, estimates, and actual timestamps.
- TOBT, TSAT, AIBT, and AOBT.
- Stand, gate, counters, and belt.
- Registration, aircraft type, seats, and passenger count.
- Status, delay codes, codeshares, handler.
- Linked flight legs.

Canonical outputs:
- Flight.
- GateAssignment.
- AircraftType.

#### Parsing

- Times are ISO 8601 UTC.
- `direction = A`: arrival.
- `direction = D`: departure.
- Paired fields are direction-dependent:
  - `STA_STD`: scheduled arrival/departure.
  - `ALDT_ATOT`: actual landing/take-off.
- Inspect and document other paired fields.
- `flight_nature = D`: domestic.
- `flight_nature = I`: international.
- Status:
  - `ARR`: arrived.
  - `DEP`: departed.
  - `CNL`: cancelled.
- `codeshares`: `|`-separated.
- `delay_codes`: `/`-separated.
- Preserve identifiers, links, and `Q`-prefix registrations.
- Do not invent timestamps for missing values.

Document all 33 columns and their canonical mappings, including retained/unused fields.

Reconstruct flight state at simulation time rather than displaying the final snapshot status throughout the day.

Treat each row as one flight leg, not one aircraft rotation.

Validate unique identifiers, expected linked references, pairing, and direction-aware mapping. Do not assume reciprocal links without inspecting the fixture.

### 6.2 AIDX

The XML describes XH960, corresponding to CSV flight `100180`.

Verify resolution to the existing flight without duplication.

Canonical output:
- FlightEvent.

Mock stream supports:
- Delay.
- Gate change.
- Status change.

Injected flight events must pass through the source-format adapter, not directly modify frontend state.

#### Conformance boundary

The XML is illustrative.

Parsing it does not establish formal IATA AIDX conformance.

Before treating it as standards-compliant:
- Validate against an applicable official IATA AIDX XSD.
- Record version and result.

If unavailable:
- Keep parsing/mapping tests.
- Label conformance unverified.
- Do not claim certification or fully validated integration compatibility.

Generated messages follow the inspected structure and are labelled simulated.

### 6.3 ACRIS

Inspect supplied models for:
- Airport.
- Terminal.
- Concourse.
- Checkpoint.
- Passenger process.
- Passenger queue.
- Measurement.

Canonical outputs include:
- Terminal.
- Zone.
- Checkpoint.
- QueueMeasurement.

Document how NGSI-LD-style mock entities relate to supplied schemas/examples. Do not assume every example is already NGSI-LD.

If `Zone` lacks a direct source equivalent, define an explicit mapping or platform-owned spatial relationship. Do not invent a standard entity type.

Preserve upstream licences/attribution. Keep extensions separate. Never alter copied schemas merely to pass tests.

### 6.4 Platform-owned data

Persist screens, advertisers, outlets, campaigns, creatives, codes, impressions, and redemptions.

Do not present platform-owned fields as external-standard fields.

### Adapter contracts

Each source requires:
- Python interface.
- Working mock implementation.
- Stub live implementation.
- Configuration-based selection.

Illustrative contract:

```python
from collections.abc import AsyncIterator
from typing import Protocol

class FlightSource(Protocol):
    def stream(self) -> AsyncIterator["FlightEvent"]:
        ...
```

Illustrative configuration:

```env
FLIGHT_SOURCE=mock-aidx
# Alternative: vendor-api
```

Exact names/types may vary within the locked Python stack.

Live stubs must clearly report unconfigured integration.

Adding/selecting a live adapter must not change core business logic.

### Evidence metadata

Retain:
- Evidence ID.
- Source/feed identity.
- Source record ID.
- Source timestamp where supplied.
- Ingestion timestamp.
- Relevant original/normalized values.
- Adapter identity.
- Freshness evaluation.
- Synthetic/illustrative provenance.

Do not invent source timestamps. Document simulation timestamp policies separately.

### Fixture tests

- Account for all 320 rows.
- Valid reference rows parse.
- Investigate/document rejected reference rows individually.
- Unexpected rejection fails tests.
- Verify the actual 33-column header.
- Verify UTC, paired fields, delimiters, links, and cancellations.
- Verify XH960 maps to `100180`.
- Validate applicable ACRIS examples against supplied schemas.
- Verify generated data passes through the same adapters.
- Test malformed inputs separately.

Keep parsing tests distinct from formal standards-conformance tests.

---

## 7. Mock Dataset and Simulation

### Required scale

Approximately:
- 900 flight legs for one operating day.
- 180 screens.
- 40 outlets.
- 10 airlines.
- 25 campaigns.
- 30 days of campaign/performance history.

**Implementation decision:** retain all 11 reference airlines and document the interpretation of the approximate target.

Include:
- T1/T2, zones, gates, outlets, and screen relationships.
- Varied aircraft, routes, loads, and statuses.
- Screen size, orientation, zone, nearest gates.
- Approved, pending, historical, and constrained campaigns.
- Reliable fixtures for mandatory demos.

### Generator

- Deterministic seed.
- Unique identifiers.
- Coherent rotations/links.
- Plausible timestamps, seats, and passenger counts.
- Same 33-column CSV shape.
- Correct paired-field and delimiter semantics.
- AIDX updates resolving to generated flights.
- ACRIS entities connected to airport layout.
- Generated airport data enters through adapters.
- Original fixtures remain unchanged.
- Historical metrics remain separate from current-run metrics.

Provide reset/reseed operations.

### Reference airlines

| IATA | ICAO | Name | Market |
|---|---|---|---|
| XD | SKJ | Skylark Air | Domestic/regional low-cost |
| YA | AUQ | Aurora National Airlines | Domestic full-service |
| YN | KSQ | Kestrel Air | Domestic low-cost |
| XU | CWQ | Coralwing Express | Domestic low-cost |
| YF | SVZ | Sunvale Airlines | Domestic low-cost |
| ZO | SLQ | Solano Airways | International |
| XH | HCZ | Halcyon Airways | International |
| YG | ACZ | Alpine Continental Airlines | International |
| XI | CRU | Crescent Airways | International |
| YU | LPZ | Lumen Pacific Airlines | International |
| YB | NSZ | Northstar Atlantic | International |

### Reference destinations

Domestic:
- ADN — Aldmere.
- BWZ — Brightwater.
- CBP — Calder Bay.
- CPZ — Coralport.
- DMQ — Dunmore.
- EHQ — Eastholm.
- FHQ — Fairhaven.
- GRH — Glenrock.
- GSZ — Goldsand.
- HCX — Highcliff.
- IVQ — Ironvale.
- JFQ — Juniper Falls.
- LMW — Lakemont.
- NGV — Northgate.
- OKZ — Oakridge.

International:
- BVQ — Belvista.
- KST — Kastell.
- NVQ — Novaterra.
- PVQ — Port Valen.
- SCJ — Santa Corvina.
- SMG — Solmara.
- ZHQ — Zarhan.

Handlers:
- Skylark self-handling.
- Meridian Ground Services.
- Harbor Aviation Services.
- Compass Ground Handling.

Use reference names by default.

Country, region, nationality, language, seasonality, and purpose attributes absent from sources require documented synthetic enrichment. Do not infer real geography from fictional codes.

### Controls: MUST, visible to all roles

- Play/pause.
- Speed: 1x / 10x / 60x.
- Jump to time.
- Inject delay.
- Inject gate change.
- Inject screen offline.

On the mobile claim page, prioritize claiming rather than exposing operator simulation controls.

### Clock/date

Default reference-based operating day: **October 14, 2026**.

The simulation is independent of the laptop's current date:
- “Today” means simulation day.
- “Tomorrow” means the next simulation calendar day.
- Campaigns, expiration, history, and forecasts follow this convention.

Display date/time clearly. Shift timestamps coherently when generating another day.

Use one clock for flight state, boarding, schedules, presence, pacing, expiry, and decisions.

Measure transport/processing latency in wall-clock time.

### Slots and immediate events

Normally evaluate slots approximately every 15 simulated seconds per relevant screen.

Relevant events must immediately:
- Update canonical state.
- Recalculate affected presence.
- Reevaluate playlists.
- Publish within two wall-clock seconds.

The slot cadence cannot delay required event handling.

For the required delay demo, visibly display the new offer within two seconds. Log current-slot replacement.

Injection works while paused:
- Clock remains unchanged.
- Event uses current simulation time.
- State/views update immediately.

Claims/redemptions work while paused.

### Time jumps and reset: implementation decision

- Forward jumps process intervening state changes without replaying every UI animation.
- Define how skipped playback/metrics are accounted for; avoid omissions or duplication.
- Backward jumps create a new run and reconstruct state from seed plus replayable events.
- Reset creates a new run.
- Document which injected events persist/replay.
- Separate live records by run ID.
- Keep seeded history separate.
- Resynchronize clients after jumps/reset.
- Previous-run promo tokens never regain validity.

Do not rewind time while retaining incompatible future state or duplicate metrics.

---

## 8. Passenger Presence and Crowd Profiles

### MUST

Compute `ZonePresence` per zone and five-minute window.

Estimate:
- Passenger count.
- Destination/nationality distribution.
- Domestic/international share.
- Dwell time.

Use passenger counts, gate proximity, time to boarding, flight updates, and ACRIS measurements.

All ad decisions and presence-dependent KPIs use this shared signal.

Provide current estimates and forecasts for:
- Next 30 minutes.
- Retailer next two hours.
- Inventory pricing.
- Tomorrow's slots.
- Seven-day forecasts with documented extrapolation.

### Per-flight profile

| Attribute | Required representation | POC source |
|---|---|---|
| Destination/arrival source | City, country, region, domestic/international, connecting origin | AODB plus enrichment |
| Trip purpose | Business, holiday, visiting friends/family, student, religious shares | Route/day/time mock rules |
| Party type | Solo, couple, family with children, group shares | Route/season mocks |
| Age | Under 12, 12–17, 18–24, 25–34, 35–44, 45–54, 55+ | Route distributions |
| Gender | Female/male percentages | Mock distributions |
| Cabin/spend | Economy, premium economy, business, frequent-flyer share | Aircraft configuration and fare mocks |
| Nationality/language | Top three of each | Route aggregates |
| Time context | Dwell, delay, time of day, festival/holiday | Flight times and event calendar |
| Crowd size | Current and next-30-minute passengers | Flights, proximity, queues |

Every flight has a plausible profile:
- Monday 07:00 domestic routes skew business, ages 25–44.
- Friday evening holiday routes skew families/couples.
- School holidays increase family shares.

These are general generator rules, not claims that the default operating day falls on Monday or Friday.

Profiles contain aggregates only.

### Provenance and formulas

Persist synthetic profile inputs and label them as simulated, not measured real demographics.

Document:
- Presence formula.
- Gate/catchment weights.
- Boarding/departure effects.
- Queue contribution.
- Aggregation.
- Dwell calculation.
- Forecast assumptions.
- Double-counting prevention.

Shares within mutually exclusive dimensions must be coherent. Different dimensions need not sum to 100% together.

Do not sum repeated presence windows and label the result unique passengers.

---

## 9. Campaign Targeting

### MUST support

**Segment weights**
- Values from 0 to 1.
- Example: family 1.0, holiday 0.8, business 0.1.

**Hard filters**
- Domestic/international.
- Destination/region.
- Minimum dwell.
- Minimum crowd size.
- Other required eligibility constraints.

**Placement**
- Zones, screens, gates.
- Schedule.

**Budget/limits**
- Total budget.
- Daily cap.
- Frequency cap per screen.

**Optional triggers**
- Delay threshold.
- Gate change.
- Boarding starts.
- Festival day.

The required demo needs a functioning delay-triggered campaign even though a dedicated Retailer trigger editor is optional.

Define mixed-crowd hard-filter semantics explicitly: for example, whether “international only” means an international zone or a minimum international audience share.

Do not leave these semantics implicit.

---

## 10. Evidence-First Decision Pipeline

### MUST

Every executed decision is grounded in recorded inputs:
- AODB.
- AIDX.
- ACRIS.
- Screen health.
- Scan/redemption metrics.
- Recorded synthetic profiles.

AI may propose rankings. Unchecked assertions must never reach a screen.

### Pipeline

1. **Profile:** build the screen catchment profile.
2. **Filter:** enforce schedule, placement, approval, brand safety, audience filters, dwell/crowd, and available budget.
3. **Score:** use documented deterministic scoring and/or a pluggable AI provider.
4. **Business rules:** airline boarding priority, competitor separation, frequency caps, pacing.
5. **Validate:** confirm evidence exists, is trusted/fresh, rules pass, and scores reproduce.
6. **Choose/log:** select highest valid score and store the complete decision.
7. **Learn:** update aggregate conversion estimates using engagement.

### Decision record

Persist:
- Run ID, screen, slot time.
- Profile snapshot.
- Evidence IDs/timestamps.
- Candidates and eligibility.
- Scores/components.
- Rejection reasons.
- Applied rules.
- Winner/reason.
- Rule/segment-model version.
- Validation result.
- Fallback/override details.

### Failure handling

Reject invalid AI proposals and log why.

Use a rule-based safe default. If no paid campaign qualifies, use a house/default creative.

The fallback must not bypass approval, safety, placement, or budget constraints.

Manual pins/overrides require a reason and cannot silently bypass evidence or hard safety/eligibility rules.

### Temporal evidence/freshness

Separate simulation time from wall-clock ingestion and processing time.

- Scheduled future information may support forecasts.
- Actual events/measurements cannot affect decisions before their effective time.
- Completed-day fixtures must not reveal future actual movements to earlier simulation states.
- Static data uses version/validity rules.
- Scheduled snapshots use an explicit validity policy.
- Dynamic events/queues use simulation-time freshness.
- Transport health uses wall-clock measurements.

Do not reject all fixtures because their operating date differs from the laptop date.

Derived profiles retain underlying evidence references. Recalculation does not make stale evidence fresh.

### Learning

Use recorded aggregate segment exposure for estimated segment attribution.

Do not infer identified demographics for a claimant.

Document update formulas, priors, and smoothing. Tests must show engagement can affect later estimates/decisions.

### Tests

Include:
- Nonexistent evidence.
- Untrusted source.
- Stale input.
- Future-event leakage.
- Invalid score.
- Ineligible winner.
- Provider timeout/failure.
- Safe fallback.

---

## 11. Required Worked Example

Reproduce:

**Gate 42 at 14:10**
- XY501 to DXB: 240 passengers, delayed 45 minutes.
- ZQ88 to a beach destination: 180 passengers.

**Profile**
- Holiday: 58%.
- Family: 31%.
- Business: 22%.
- International: 57%.
- Median dwell: 52 minutes.

| Campaign | Targets | Match | Boost | Final score | Result |
|---|---|---:|---:|---:|---|
| Duty-free perfume, 15% off | International, holiday, adults 25–54 | 71% | 1.5 delay boost | 0.86 | Plays |
| Toy store, buy 2 get 1 | Family with children | 49% | 1.0 | 0.52 | Next in rotation |
| Business lounge day pass | Business, premium cabin | 18% | 1.0 | 0.21 | Filtered to other gates |

### Unspecified details

The organizer does not supply the exact scoring formula, full distributions, catchment weights, or lounge placement rule.

Simple match × boost does not reproduce final scores.

### Implementation requirements

- Preserve the reference values/results.
- Define reproducible score components/normalization.
- Document added assumptions or calibration.
- Create recorded inputs sufficient to reproduce the example.
- Make lounge placement and toy rotation rules explicit.
- Run it through the actual engine.
- Do not hard-code the displayed table/winner.
- Test displayed values at their stated precision.

### Identifier distinction

XY501/ZQ88/DXB differ from the reference fictional dataset.

Keep the exact example in a dedicated labelled scenario and engine regression test.

Do not alter original MQI files.

If offering a fictionalized UI version:
- Document mappings.
- Preserve target values/results.
- Retain the exact organizer scenario.
- Do not claim it came from the CSV.

---

## 12. Matching Transparency by Role

### Admin: MUST
- Global weights.
- Exploration percentage.
- Frequency caps.
- Competitor separation.
- Searchable decision log.
- Segment-model version.

### Retailer: MUST
- Live campaign audience-match preview.
- Estimated impressions/redemptions.
- Segment performance.
- Suggested weight changes.

Example style:
> Matches 64% of the crowd at Gates 40–45 from 14:00 to 16:00; expected 3,100 impressions and 95 redemptions.

Compute actual displayed values; label forecasts as estimates.

### Media Manager: MUST
- Segment × hour × zone heatmap.
- Campaign conflict explanation.
- Pin/override with recorded reason.

### Airline: MUST
- Aggregate own-flight profiles.
- Partner offers ranked by fit.
- Ads played at own gates and reasons.

### Passenger: MUST
“Why this ad?” overlay:
- Profile bars.
- Top three candidates/scores.
- Winning rule.

Show filtered status/reasons where relevant. Never portray a rejected candidate as eligible.

---

## 13. Platform Admin Experience

### MUST

**Terminal map**
- T1/T2 stylized floor plan; SVG acceptable.
- All screens shown as dots.
- Online/degraded/offline states.
- Presence heat overlay.

**KPIs**
- Screens online percentage.
- Ad plays today.
- Impressions.
- Revenue today.
- Active campaigns.
- Average screen latency.
- Configurable currency.

**Incident/bug tracker**
- Auto alerts: offline over five minutes, feed lag, failed creative.
- Severity, owner, status.
- Working incident-management actions.

**Master data**
Lists and create/edit forms:
- Vendors.
- Outlets/F&B retailers.
- Airlines.
- Terminals, zones, gates.
- Screens: size, orientation, zone, nearest gates.

### SHOULD
- Feed status, messages/minute, last message, active adapter.
- API p95, playlist build time, seven-day uptime.

Document simulation versus wall-clock incident thresholds. Label synthetic historical operational metrics.

---

## 14. Retailer Experience

### MUST

**Live selected-outlet dashboard**
- Impressions.
- Scans.
- Redemptions.
- Conversion.
- Attributed revenue.

**Nearby flow**
- Next-two-hour forecast.
- Upcoming-departure-derived footfall.
- Top destinations/nationalities.
- International share.

**Campaign builder**
- Creative.
- Zones/screens.
- Destination, domestic/international, dwell, delay rules.
- Schedule and budget.
- Mock-screen preview.
- Audience-match preview.

**Creative library**
- Upload/reuse ad pages and templates.
- Duplicate past campaigns in one action.

**Promo codes**
- Time-boxed codes.
- QR.
- Expiry tied to crowd movement/boarding close.
- Family-share second code.

**History**
- Spend, impressions, redemptions, ROI.
- Run-again action.

### SHOULD
- Dedicated trigger editor.
- Stock-aware pause toggle.
- Budget pacing visualization.
- Simple A/B comparison.

### Metric rules

Document formulas and attribution assumptions.
- Distinguish platform ad revenue from attributed retail revenue.
- Handle zero denominators/spend.
- Historical duplication creates an editable campaign with a valid new schedule.
- Revenue is simulated accounting, not payment processing.

---

## 15. Media Manager Experience

### MUST

**Inventory calendar**
- Every screen × hour.
- Booked, available, premium.
- Premium driven by forecast presence.

**Yield/pricing**
- Presence-driven suggested slot price.
- Occupancy.
- Seven-day revenue forecast.

**Approval**
- Pending creatives/campaigns.
- Approve/reject.
- Brand-safety checklist.

**Advertisers**
- Top spenders.
- Running campaigns.
- Under-delivery flags.

### SHOULD
- Screen package builder.
- PDF/shareable advertiser report.

Efficiently render the large calendar.

Document forecast extension beyond the one-day seed. Do not portray inferred future schedules as source-provided.

---

## 16. Airline Representative Experience

### MUST

**My flights**
- Selected airline's departures.
- List/timeline.
- Gate, status, delay, load factor.

**Gate messaging**
- Sponsored content at own gates in own boarding windows.
- Upgrade, lounge, destination-partner offers.

**Delay goodwill**
- Configurable threshold.
- Auto meal/lounge voucher.
- Co-funded with F&B retailer.
- Relevant gate screens.

### SHOULD
- One-click co-marketing acceptance.
- Own-audience impressions/redemptions reporting.

Calculate load factor from passenger count/capacity.

Co-funding is simulated accounting.

Gate changes must update message placement.

---

## 17. Passenger Screen, Playback, and Claims

### MUST

- Choose physical screen by gate/zone.
- Full-screen mode.
- Current playlist.
- 9:16 and 16:9 frames.
- Nearby-flight FIDS strip.
- Visible ad changes as flights delay, board, move gates, or depart.
- Real QR with countdown.
- Mobile claim page.
- Configurable LAN claim URL.
- Successful claim records redemption.
- Retailer updates immediately.
- “Why this ad?” overlay.

### Claims

- Backend validates expiry and run validity.
- Link expiration to relevant flight/crowd window.
- Record scan/page-open separately from redemption.
- Clearly explain that successful claim represents redemption in this POC.
- Family sharing issues a second code.
- Define bounded sharing and one-time redemption semantics.
- Make submission idempotent.
- Use opaque tokens.
- Collect no passenger identity or device identifiers.

If expiry changes following a flight update, synchronize displayed countdown and server validation.

### Virtual playback

Online virtual screens continue scheduled playback without an open browser.

Backend owns plays and estimated impressions.

Additional browser views must not duplicate plays/impressions.

Document exposure estimation using presence and slot duration. Label impressions estimated exposure opportunities, not verified unique viewers.

Automatically generated engagement must:
- Be reproducibly seeded.
- Be labelled simulated.
- Remain distinguishable from real claim interactions.

Phone claims enter the same pipeline.

### Creative safety

Safely render uploaded/generated content using controlled templates, sanitization, or sandboxing.

Do not execute arbitrary uploaded scripts with application privileges.

---

## 18. Required WOW Features

### Shared controls
Implement Section 7 controls across role views.

### Live cause and effect
Injected AIDX delay must within two wall-clock seconds:
- Update Airline.
- Re-plan screens.
- Trigger Retailer delay rule.
- Raise affected-zone presence.

Seed a scenario where the increase follows the documented dwell model.

### Split-screen
- Passenger left.
- Any role dashboard right.
- Shared state/clock.
- Readable at target resolutions.

### Creative assistant
- Brief input.
- Ready template ad.
- English plus configured second language.
- Offline mock by default.
- Pluggable real provider.

Example:
> Festive sweets, 20% off, families flying domestic.

### Slot recommendation
“Best three slots for this campaign tomorrow,” including:
- Predicted impressions.
- Audience fit.
- Availability/constraints.
- Understandable reasons.
- Forecast assumptions.

---

## 19. UI, Branding, and Localization

### MUST

- Polished at 1440px and 1920px.
- Dark Admin control-room theme.
- Light business-role themes.
- Mobile claim layout.
- Shared design system.
- White-label name, logo, colors.
- No real airport, airline, or brand marks.
- English plus one configurable second language for UI and ads.

### Guidance

- Consistent typography, spacing, charts, and formatting.
- Clear simulation clock.
- Distinguish live, historical, estimated, and forecast data.
- Loading/empty/error/disconnected states.
- Accessible labels and keyboard interaction.
- Do not rely only on color.
- Readable split-screen layouts.
- No dead controls or decorative placeholder panels.
- Bundle fonts, images, scripts, and required runtime assets locally.
- Do not require CDNs or external asset services offline.

---

## 20. Runtime, Networking, and Deployment

### MUST

Startup:

```bash
docker compose up --build
```

Include migrations and initial seed. Preserve data on restart.

Local runtime requires no cloud service or API key.

Reviewer playground:
- Working deployed URL.
- Preconfigured.
- Available during challenge duration.
- Same business logic as local app.

### Offline setup distinction

Normal runtime must work without internet.

If first setup downloads dependencies/images:
- State it.
- Explain preparation/caching.
- Do not claim uncached initial installation works offline.

### QR environments

1. Local: configurable phone-reachable LAN URL.
2. Deployed: public claim URL.

Never encode `localhost` for a phone.

Document host binding, ports, LAN setup, firewall/same-network needs, public base URL, and WebSocket configuration.

### Deployment resilience

- Built frontend assets, not development server.
- Correct public REST/WebSocket routing.
- Persistent storage appropriate to prototype.
- Deterministic reset/replay.
- Shared-state reset behavior clearly disclosed.
- No permanently exhausted demo budgets/codes.
- Optional missing provider credentials are nonfatal.
- Verify the public URL; never fabricate deployment status.

---

## 21. Performance Requirements

### MUST

- Dashboard updates within two wall-clock seconds of feed events.
- Required delay workflow within two seconds.
- Responsive 60x simulation.
- Full approximate seed scale.

### Planning workload

With 180 screens and 15-second slots:

```text
180 / 15 = 12 screen decisions per simulated second
12 × 60 = 720 decisions per wall-clock second at 60x
720 × 25 = up to 18,000 candidate evaluations per second
```

This is an approximate planning upper bound before filtering, not a guaranteed constant workload.

### Implementation guidance

- Cache five-minute profiles.
- Incrementally update affected catchments.
- Filter efficiently.
- Batch database writes and WebSocket updates.
- Avoid database round trips per candidate.
- Virtualize large views.
- Separate processing frequency from UI refresh frequency.
- Keep blocking work off the asynchronous event loop.
- Do not silently skip required decisions to claim 60x support.
- Measure actual propagation and responsiveness.
- Bound log retention/storage growth and document the policy.

---

## 22. Acceptance Checklist

Maintain a checklist mapped to mandatory requirements.

### Boot/data
- [ ] One-command startup works.
- [ ] Empty-database migrations work.
- [ ] Seed/reset works.
- [ ] Approximately 900 legs, 180 screens, 40 outlets, 25 campaigns.
- [ ] All 11 reference airlines retained and count interpretation documented.
- [ ] Thirty-day history.
- [ ] Persistence survives restart.
- [ ] Offline runtime without credentials.

### Adapters
- [ ] Actual reference files inspected.
- [ ] 33-column mapping documented.
- [ ] All reference rows accounted for.
- [ ] UTC/direction/delimiter/link behavior tested.
- [ ] AIDX XH960 resolves to `100180`.
- [ ] ACRIS mapping/schema tests.
- [ ] Generated payloads use adapters.
- [ ] Configurable mocks/live stubs.
- [ ] Malformed/stale input handling.
- [ ] Licensing preserved.

### Presence/decisions
- [ ] Every flight has plausible profile.
- [ ] Five-minute presence.
- [ ] Delays/gate changes update catchments.
- [ ] Hard filters.
- [ ] Airline priority.
- [ ] Competitor separation.
- [ ] Frequency/budget/pacing.
- [ ] Evidence/freshness/score validation.
- [ ] No future-event leakage.
- [ ] Invalid AI fallback.
- [ ] Searchable audit trail.
- [ ] Learning changes estimates.
- [ ] Worked example reproduces.

### Roles
- [ ] Role/company switching without reset.
- [ ] All Admin mandatory features.
- [ ] All Retailer mandatory features.
- [ ] All Media Manager mandatory features.
- [ ] All Airline mandatory features.
- [ ] Role-specific matching transparency.

### Passenger/WOW
- [ ] Both orientations and full-screen.
- [ ] FIDS and dynamic playlist.
- [ ] Phone QR works.
- [ ] Expiry/run validity enforced.
- [ ] Family sharing.
- [ ] Idempotent redemption.
- [ ] Retailer updates.
- [ ] Two-second delay chain.
- [ ] Pause/jump/reset behavior.
- [ ] Split-screen.
- [ ] Offline bilingual creative.
- [ ] Tomorrow recommendations.

### Delivery
- [ ] 1440px/1920px checked.
- [ ] Mobile claim checked.
- [ ] Both languages.
- [ ] White-label config.
- [ ] 60x at scale.
- [ ] WebSocket reconnection.
- [ ] Public app and claim route verified.
- [ ] README/diagram/adapter guide/OpenAPI.
- [ ] Known limitations accurately documented.

### Test layers

- Unit: parsers, presence, scoring, rules, expiry, metrics.
- Integration: event → state → decision → playlist.
- API: management, approvals, claims, controls.
- End-to-end: roles, WOW, mobile claim, split-screen.
- Performance: propagation and accelerated simulation.

Test behavior, not only static snapshots.

---

## 23. Suggested Implementation Order

### Phase 1: Foundations
Stack, migrations, seed, canonical model, adapters, clock, transport.

### Phase 2: Complete vertical slice
Gate 42 scenario, presence, scoring/evidence, playback, delay, QR, redemption, Retailer update.

### Phase 3: Mandatory role workflows
Admin, Retailer, Media Manager, Airline, matching transparency.

### Phase 4: Demo polish
Split-screen, creative assistant, recommendations, localization, branding, reset/replay, performance.

### Phase 5: Submission
Full acceptance run, docs, deployment, phone/public verification, 15-minute rehearsal.

Stretch features only after mandatory workflows are healthy.

---

## 24. Suggested 15-Minute Demo

### 0–2 minutes
Admin map, heat, health, KPIs, fictional data, shared clock.

### 2–4 minutes
Retailer flow, campaign builder, targeting, forecast.

### 4–7 minutes
Split-screen, Gate 42, AIDX delay, changed flight/presence/ad within two seconds, evidence explanation.

### 7–9 minutes
Phone scan/claim, live redemption/revenue, family code, expiry.

### 9–11 minutes
Media inventory, pricing, approval, conflict, reasoned override.

### 11–13 minutes
Gate change/outage, propagation, incident, 60x/boarding effects.

### 13–15 minutes
Bilingual creative, tomorrow recommendations, offline operation, adapters, deployed URL.

Use deterministic state and rehearse. Do not depend on favorable randomness.

---

## 25. Documentation and Deliverables

### Deliverables

- Frontend/backend source.
- Compose startup.
- Migrations and seed/generator.
- README.
- Architecture diagram.
- Adapter guide.
- OpenAPI specification.
- WebSocket contract.
- Working reviewer URL.

### README

Explain:
- Stack rationale.
- Prerequisites/startup.
- Offline preparation.
- URLs and configuration.
- Seed/reset.
- Simulation behavior.
- Demo scenario.
- Tests.
- Theme/second language.
- LAN/public QR setup.
- Deployed URL.
- Limitations/assumptions.

### Adapter guide

Explain interfaces, canonical mappings, evidence, freshness, mock/live selection, source schema versions, licensing, and adding a vendor adapter.

### Architecture docs

Explain event flow, clock/runs, presence, scores, validation/fallback, learning, forecasts, persistence, and real-time synchronization.

### API docs

Cover master data, flights, presence, screens, playlists, campaigns, creatives, approvals, inventory, decisions/evidence, claims/sharing, controls, incidents, and configuration.

---

## 26. Assumptions and Gaps

Record explicitly:

1. Exact source mappings come from actual `playground/` files.
2. AIDX illustration lacks verified XSD conformance unless tested.
3. Eleven reference airlines versus approximate target of ten.
4. Organizer worked-example identifiers differ from MQI fixtures.
5. Synthetic enrichment provenance.
6. Missing scoring formula and calibration assumptions.
7. Missing complete worked-example weights/distributions/placement.
8. Configurable source-specific freshness.
9. Presence/dwell/queue formulas.
10. Forecast extension beyond one-day seed.
11. Revenue, ROI, pricing, and attribution formulas.
12. Scan/claim/redemption semantics.
13. Offline runtime versus initial downloads.
14. LAN versus public claim URLs.
15. Exploration versus highest-score selection.
16. Time-jump, replay, reset, and skipped-playback accounting.
17. Mixed-crowd hard-filter semantics.
18. Incident simulation-time versus wall-clock thresholds.

Default demo behavior must be deterministic.

Exploration, if enabled, must remain eligibility-safe, reproducible, and explicitly logged. Document how it interacts with highest-score selection. Use settings that preserve the required worked example.

When clarification is unavailable, make a reasonable documented assumption and keep it configurable where useful.

---

## 27. Completion Standard

Complete only when:
- Mandatory workflows work end to end.
- Role views use coherent shared state.
- Decisions are evidence-backed and reproducible.
- Delay → ad → phone redemption works reliably.
- Local offline runtime and deployed access work.
- Performance targets are measured.
- Documentation matches actual behavior.

Do not substitute:
- Decorative counters for state changes.
- Static score tables for an engine.
- Fabricated evidence for recorded inputs.
- Fake QR for accessible claims.
- Dead controls for management actions.
- Claimed deployment for verified access.

Prioritize reliability, traceability, clarity, and a compelling demonstration.