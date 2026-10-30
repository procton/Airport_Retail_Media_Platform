# Assumptions, Open Questions, Discrepancies

Status, one line each, updated as implementation proceeds. Numbering mirrors AGENTS.md §26 where applicable.

## Delivery verification

- Docker restart persistence was manually verified: restarting the application
  preserved the seeded SQLite state through the `airp-data` named volume.

## Reference-data discrepancies (actual inspection, 2026-10-23)

| # | Finding | Resolution |
|---|---|---|
| D2 | `ACRIS-smart-data-models/` directory is **absent**, although `playground/README.md` documents it as “copied unchanged … under its own licence”. Per administrator clarification, the public FIWARE Smart Data Models `dataModel.ACRIS` repository is accepted as the reference, so the adapter now processes representative NGSI-LD mock entities for `TerminalFacility`, `CheckpointFacility`, and `PassengerQueue`. | The representative mapping is tested; formal validation against a pinned upstream schema copy is not claimed. Mock queue measurements remain labelled synthetic platform data, not measured ACRIS data. |

## Facts verified in the fixture (not assumptions)

- CSV: 320 data rows, all rows 33 fields; 157 ARR / 157 DEP / 6 CNL (3 cancelled A/D pairs linked to each other).
- Every `linked_flight_id` exists; all 160 pairs reciprocal; ids unique.
- Times ISO-8601 UTC with `Z`; paired columns behave as documented (`STA_STD` used as departure instant on `D` rows, arrival instant on `A` rows, etc.).
- Gates populated for all 160 departures; 125 of 160 arrivals have empty `gate`; the 35 populated arrival gates always equal the linked departure's gate (0 mismatches).
- `pax_total` empty exactly on the 6 CNL rows; `pax ≤ seats` always; `seats` always present; `stand` always present.
- `via` empty on all rows; `service_type` `J` on all rows; `codeshares` values: `XD\|XH`, `XH\|YB`, `YA\|YG` or empty; `delay_codes`: 41, 89, 81, 93, 63/11; `last_update_utc` identical (`2026-10-15T02:00:00Z`) on all rows → snapshot dump time, NOT per-record freshness (evidence model uses explicit freshness policy, see A6).
- AIDX XML: XH960 arrival ↔ CSV row `aodb_flight_id=100180` (northstar evidence reopened and re-verified at implementation): same airline XH/HCZ, ZHQ→MQI, T2, stand/parking `C38`, status ARR, aircraft `A359` (XML `359`), reg `QH-BC`, seats 30+253=283, pax 27+197=224, codeshare XD|XH. Structural mapping validated; **no XSD available in repo → conformance unverified** (documented, not claimed).
- T1 gates: `A2–A9`, `B1–B11`, `C2–C12`, `BUS1–7`; T2 gates: `41–88` numeric and `BUS1–8`.

## Working-example cross-reference (AGENTS §11)

- XY501→DXB, ZQ88 and DXB **do not exist** in the MQI fixture (different fictional universe). Exact scenario lives in a labelled engine regression fixture (`backend/app/seed/worked_example.py`) and a labelled scenario loader for demos; the production demo dataset keeps MQI identifiers. Never presented as CSV-sourced.

## Assumptions (documented decisions)

1. **Seed scale vs fixture day:** the operating day = 2026-10-14. `SEED_MODE=full` (default) generates a synthetic ~900-leg operating day in the exact 33-column CSV shape through the same AODB adapter (labelled synthetic); `SEED_MODE=reference` loads verbatim `MQI_aodb_flights_2026-10-14_SYNTHETIC.csv`. Screens/outlets/campaigns/history identical in both modes.
2. **Simulation timestamps:** flight-event *effective* times are simulated clock times; transport/processing latencies are wall-clock. Delay/gate injections while paused stamp the current simulated clock.
3. **Synthetic enrichment** (destination country/region, nationality, language, purpose, party type, age, gender, cabin): deterministic per-route/day/hour generator rules, persisted and labelled `simulated`. No real-world geography inferred from fictional codes.
4. **Freshness policy:** static platform data is versionless-valid; AODB snapshot rows carry scheduled values usable for the whole day + freshness "scheduled"; AIDX events use simulation-time freshness (reject-threshold 10 min sim drift); ACRIS queue measurements 5 min. Ingestion wall-clock recorded separately.
5. **Match/final score semantics:** displayed "Match %" = `audience_match` (documented mean of campaign-criterion satisfactions against profile shares); "Final score" = `SCORE_NORM × audience_match^EXP_A × context_boost^EXP_B` clamp01; `SCORE_NORM=0.9918`, `EXP_A=0.905`, `EXP_B=0.4105` — calibrated constants reproduced from the organizer worked example (see docs/WORKED_EXAMPLE.md). Sublinear boost exponent documentration: diminishing returns, prevents saturation.
6. **Mixed-crowd hard filters:** "international only" means *audience-share gate*: eligible iff profile intl share ≥ campaign `min_intl_share` (default 0.5) computed on the 5-min ZonePresence snapshot; placement-level "international zones" equals gate terminal mapping T2.
7. **Impressions:** backend computes *estimated exposure opportunities* = presence-at-slot × creative-slot-stretch fraction; not unique-verified viewers. Browser views never create or duplicate plays; virtual playback makes plays without an open browser.
8. **Attributed revenue:** simulated accounting = redemptions × promo code fixed value assumption per campaign; not payments.
9. **Runs/jumps:** forward jump recomputes presence/decisions to the new point (skipped sub-15s slots accounted to the nearest boundary, one decision per boundary, no double metrics); backward jump/restart of day = new `run_id`, rebuild from seed + replayable injected-events log; injected flight mutations replay; claims/promos of previous runs never revive.
10. **Slots per screen cadence:** slot decisions every 15 s sim, cached 5-min ZonePresence profiles revalidated when an event touches a zone; immediate-event path bypasses cadence (2 s wall budget).
11. **Degraded/offline screens:** lasting outages pause placement at that screen with fallback house creative; house creative never violates budget (zero-spend) and is labelled non-campaign.
12. **Currencies:** USD default configurable (`CURRENCY=`), platform revenue = billed slot spend; retailer dashboards show attributed retail revenue distinctly.
13. **Live adapters:** vendor stubs `vendor-aodb-http`, `vendor-aidx-push` return distinct `FeedNotConfigured` errors; only mock adapters are exercised by tests/demos.
14. **Frontend second language:** configurable (`UI_LANG_2`), default Spanish; creative assistant always emits bilingual EN + configured language.
15. **Airline count:** all 11 reference airlines retained; "approximately 10 airlines" satisfied with documented interpretation (11 supplied by organizer lists).
16. **Incident thresholds:** simulated-time incident evaluation (screen offline > 5 min *sim*; feed lag measured wall-clock as transport health), thresholds configurable, both labelled in UI.
17. **Historical 30-day metrics:** generated with deterministic seed, labelled `synthetic-history`, stored with `is_history=1` and a different run id (`hist`), never mixed with live-run metrics.
18. **"Tomorrow" recommendations** operate on the next calendar day *of the generated full-scale fixture set* which covers ≥ 2 operating days (day is 2026-10-14 + generated 2026-10-15 for forecasting purposes, labelled synthetic).
19. **No.WebDriver/e2e harness:** browser-level end-to-end verified manually via a smoke script + API/e2e pytest flows; documented limitation.
20. **Charging/dev preview:** Vite dev server used only during development; production images serve `dist/` from FastAPI static mounts and a tiny static server — no dev servers in deployment.
21. **Optional LLM integration:** the administrator-suggested LLM-backed creative assistant is now available through `CREATIVE_PROVIDER=llm-openai-compatible`. It remains optional and is limited to schema-validated creative drafts; campaign decisions, scheduling, persistence, and the deterministic offline fallback remain independent of the LLM.
22. **Admin global scoring weights:** `audience_weight` and `context_weight` scale the corresponding calibrated scoring exponents. Both default to `1.0`, preserving the worked example; values are bounded to `0..2` and persisted in `rule_config`.

## Open questions (blocked nothing; raised for review)

- Q1: ACRIS fixture directory absent (D2) — cannot run supplied-schema validation without it.
- Q3: Whether organizer expects the *reference-day* fixture to occupy the default demo state — default decision: full-scale synthetic day (checklist item "approximately 900 legs" takes precedence in the default boot; reference day available via one env var / one command).
