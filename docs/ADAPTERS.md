# Adapters guide (AGENTS §6)

Sources never hand raw payloads to business logic. Every feed goes through a
typed adapter that produces **canonical entities only**; core services
(presence, decisions, playback) cannot tell where a row came from.

```text
playground/MQI_aodb_flights_2026-10-14_SYNTHETIC.csv  ─┐
playground/AIDX_FlightLegNotifRQ_XH960_...xml        ─┤→ adapters → canonical → evidence_records → services
MockAcrisFeed (in-code, deterministic)               ─┘
```

Directory note: the repository-root fixture directory is `playground/`.
Original fixtures are treated as read-only reference material and are never
rewritten by app code or tests.

---

## 1. Contracts (backend/app/adapters/base.py)

| Protocol | Produces | Mock (default) | Live stub |
|---|---|---|---|
| `FlightSource` | `(list[Flight], list[GateAssignment])` + `rejected()` | `AodbCsvAdapter` (`name="mock-aodb"`) | `AodbVendorStub` |
| `FlightEventSource` | `list[FlightEvent]` (`parse_notification`, `mock_amendments`) | `AidxXmlAdapter` (`name="mock-aidx"`) | `AidxVendorStub` |
| `QueueSource` | `list[QueueMeasurement]` | `MockAcrisFeed` (`name="mock-acris"`) | `AcrisVendorStub` |
| `CreativeAssistantProvider` (providers/creative.py) | structured creative draft dicts | `OfflineTemplateAssistant` | `LiveStubAssistant` (501) |

Selection is configuration-driven (`backend/app/config.py`, no prefix):

```env
FLIGHT_SOURCE=mock-aodb      # alt: vendor-aodb-http (stub raises/labels unconfigured)
ACRIS_SOURCE=mock-acris
CREATIVE_PROVIDER=offline-template    # alt: llm-openai-compatible or live stub (501)
```

A live stub raising `NotImplementedError` is intentional for unknown providers.
The optional `llm-openai-compatible` creative provider uses the configured
OpenAI-compatible chat-completions endpoint and returns only a validated
structured draft; selecting it does not change core business logic. Every stub
message names the unconfigured integration instead of silently degrading.

---

## 2. AODB CSV → `Flight` + `GateAssignment`

Authoritative reference: `playground/MQI_aodb_flights_2026-10-14_SYNTHETIC.csv`
(synthetic; fixed operating day 2026-10-14). Parser: `backend/app/adapters/aodb.py`.

### Header contract

Exactly these **33 columns** in this order (mismatch = `ValueError`, no guesses):

```text
aodb_flight_id, linked_flight_id, direction, airline_iata, airline_icao,
flight_number, callsign, service_type, flight_nature, origin, destination,
via, terminal, STA_STD, ETA_ETD, ELDT_ETOT, ALDT_ATOT, AIBT_AOBT,
TOBT, TSAT, stand, gate, checkin_counters, baggage_belt, aircraft_reg,
aircraft_type_icao, seats, pax_total, status, delay_codes, codeshares,
handler, last_update_utc
```

### 33-column mapping table

| CSV column | Canonical field(s) | Notes |
|---|---|---|
| `aodb_flight_id` | `Flight.id` = `aodb:<id>`, `Flight.aodb_flight_id` | unique key; referenced by AIDX |
| `linked_flight_id` | `Flight.linked_flight_id` | kept only when it resolves inside the CSV id set; NOT forced reciprocal |
| `direction` | `Flight.direction` (`A`/`D`) | hard filter: other values → rejected row |
| `airline_iata`, `airline_icao`, `flight_number`, `callsign` | same-named Flight fields | identifiers preserved verbatim |
| `service_type` | `Flight.service_type` | defaults to `J` when blank |
| `flight_nature` | `Flight.flight_nature` (`D` domestic / `I` international) | hard filter; drives intl/domestic targeting |
| `origin`, `destination`, `via` | `Flight.origin/destination/via` | fictional codes; country/region are documented synthetic enrichment (generator), never inferred |
| `terminal` | `Flight.terminal` | |
| `STA_STD` | `Flight.sched_std` | paired: arrival STA / departure STD |
| `ETA_ETD`, `ELDT_ETOT` | `Flight.etd`, `Flight.eldt` | paired estimate/actual landing-takeoff estimates |
| `ALDT_ATOT`, `AIBT_AOBT` | `Flight.aldt`, `Flight.aibt` | actual times; blank stays `None` (never invented) |
| `TOBT`, `TSAT` | `Flight.tobt`, `Flight.tsat` | turnaround inputs (boarding start derivation) |
| `stand`, `gate` | `Flight.stand` / `Flight.gate` + `GateAssignment` | gate change events rewrite the assignment |
| `checkin_counters`, `baggage_belt` | same-named fields | informational |
| `aircraft_reg` | `Flight.aircraft_reg` | `Q`-prefix registrations preserved |
| `aircraft_type_icao` | `Flight.aircraft_type` + `AircraftType` rows (seats) | real ICAO designators (e.g. `A320`) |
| `seats` | `Flight.seats`, used for load factor | |
| `pax_total` | `Flight.pax` — presence weight input | |
| `status` | `Flight.status_raw`, `Flight.cancelled` (`CNL`) | `ARR`/`DEP`/`CNL`; live state is projected at sim time, not pasted from the snapshot |
| `delay_codes` | `Flight.delay_codes` | `/`-separated |
| `codeshares` | `Flight.codeshares` | `|`-separated |
| `handler` | `Flight.handler` | one of the four fictional handlers |
| `last_update_utc` | `Flight.last_update_utc`; evidence `source_timestamp` | UTC ISO 8601 |

Gate windows: arrival assignments run from `(ALDT|ETA|STA) − 45 min` to
end-of-day; departure assignments run from `boarding_start()` to
`effective_std() + 10 min`.

### Rejection policy

- Wrong header (missing/extra columns, count ≠ 33) → hard `ValueError`.
- Bad `direction`/`flight_nature`, missing `STA_STD`, unparseable secondary
  times → row appended to `rejected()` (fails tests when unexpected).
- All 320 reference rows parse clean (160 D + 160 A pairs, reciprocal links
  verified) — asserted in `backend/tests/test_adapters.py`.
- Times are interpreted as UTC ISO 8601 `Z`-suffixed.

---

## 3. AIDX XML → `FlightEvent`

Reference: `playground/AIDX_FlightLegNotifRQ_XH960_arrival_ILLUSTRATIVE.xml`
(hand-written illustration for the leg the CSV carries as `aodb_flight_id 100180`,
callsign/flight XH960). Parser: `backend/app/adapters/aidx.py`.

- `parse_notification(xml) -> list[FlightEvent]` — extracts operation records
  (delay / gate / status change) with their times, resolves the referenced leg
  to the **existing** flight (`aodb:<100180>`) via aodb_flight_id + designator;
  never duplicates the flight.
- `mock_amendments()` — deterministic demo stream built for seeded flights;
  goes through the same adapter path as operator injections.
- `generate_notification(...)` — writes simulated AIDX XML for injected
  operator events (labelled simulated), used for feed-evidence recording.

**Conformance boundary (honest):** the illustration has not been validated
against an official IATA AIDX XSD. Implementation compatibility ≠ certification;
parsing/mapping is regression-tested against this exact file, and conformance
stays labelled *unverified* in the checklist (AGENTS §6.2).

Operator/UI injections produce `FlightEvent`s carrying evidence ids and
`replay` flags so backward-jump reconstruction reuses the same adapter
stream rather than bypassing it.

---

## 4. ACRIS (queues/process) → `Zone`, `Checkpoint`, `QueueMeasurement`

The organizer fixture set does **not** contain the referenced
`ACRIS-smart-data-models/` directory (documented gap — not silently replaced).
Per the administrator clarification, the public FIWARE Smart Data Models
`dataModel.ACRIS` repository is the reference for representative NGSI-LD
entities; the implementation does not claim that the missing organizer copy
was formally schema-validated. The public model lists ACRIS concepts such as
`TerminalFacility`, `CheckpointFacility`, `PassengerQueue`, and
`QueueMeasurement`.

Implementation ships an in-code deterministic mock and adapter:

- `build_platform_layout()` constructs the fictional MQI layout (T1/T2
  terminals, concourses, gate zones, `T2-BUS-gates`, security checkpoints)
  = canonical `Terminal`, `Zone`, `Checkpoint`.
- `MockAcrisFeed(day, seed)` emits deterministic per-checkpoint wait/queue
  measurements for the operating day = `QueueMeasurement`, feeding presence
  queue contributions (§8).
- `AcrisShapeAdapter.parse_entity/canonical_from_entities` maps both the
  legacy flat mock and representative NGSI-LD payloads (Property
  `{type: "Property", value: ...}` and Relationship `{type: "Relationship",
  object: ...}` shapes) into the same canonical rows. Unknown entity types and
  incomplete queue measurements are rejected rather than guessed. The
  representative round-trip is covered by
  `backend/tests/test_acris.py`.

Mapping rules:

| ACRIS concept | Canonical | Note |
|---|---|---|
| `Airport`, `Terminal`, `Concourse` | `Terminal` (+ hierarchy) | names fictional |
| Checkpoint zone under a concourse | `Checkpoint` + `Zone` | zones are **platform-owned** spatial objects (no direct upstream entity type); documented mapping, not a standard claim |
| Passenger-process / queue measurement | `QueueMeasurement` | timestamps preserved from payload; mock times derive from seed, labelled simulated |

The sample entities are platform-owned representative mocks, not copied
upstream fixtures. The public reference is
`https://github.com/smart-data-models/dataModel.ACRIS`; no formal online-schema
validation or certification is claimed. If upstream files are later added
under `playground/`, they must remain unchanged, with licences/attribution
preserved and any extension kept in separate files.

---

## 5. Evidence metadata (§6, §10)

Every accepted source payload can cite an `EvidenceRecord`
(`evidence_records` table):

| Column | Meaning |
|---|---|
| `source` | feed identity (e.g. `MQI_aodb`, `mock-aidx`, `operator-controls`) |
| `source_record_id` | row/message id (`aodb_flight_id`, AIDX flight key, event id) |
| `source_timestamp` | value **supplied by the source** (`last_update_utc`, message ts) — absent stays `None` |
| `ingestion_timestamp` | recorded when the adapter emitted it (wall clock) |
| `adapter` | adapter class name that mapped it |
| `freshness` | `scheduled` \| `measured` \| `stale` per §10 temporal policy |
| `provenance` | `synthetic` \| `illustrative` \| `platform-owned` |
| `payload` | normalized key values kept for the decision audit |

Decisions reference these ids in their records; previews and the passenger
"Why this ad?" block surface them. Freshness policy separates scheduled
future data (promos/rosters), measured data (queues/actual movements), and
wall-clock transport health.

---

## 6. Adding a vendor adapter (walk-through)

1. Add `class MyVendorFlightSource` in a new module; implement `name`,
   `legs() -> (Flights, GateAssignments)` and `rejected()`.
2. Map its wire format into `domain/canonical.py` entities — do not leak
   vendor field names into services.
3. Record one `EvidenceRecord` per emitted fact (with adapter identity and
   supplied timestamps).
4. Register it in the settings selector (`flight_source=…`) alongside the
   existing mocks and stubs; core logic needs zero changes.
5. Reuse `test_adapters.py` patterns for fixture/regression tests, keeping
   parsing tests separate from standards-conformance claims.
