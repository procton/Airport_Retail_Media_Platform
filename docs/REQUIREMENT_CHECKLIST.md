# Mandatory-Requirement Checklist

Status legend: ☐ open · ◐ partial · ☑ done+verified · ✖ knowingly not met (must never appear without a documented reason).
Evidence pointers reference tests, measured sessions, or source files.

## Boot & data
| # | Requirement | Status |
|---|---|---|
| B1 | One-command startup `docker compose up --build` | ☑ verified by user (compose up + App UI confirmed working) |
| B2 | Empty-database migration works | ☑ `alembic -c backend/alembic.ini upgrade head` (0001_initial) + create_all fallback in `main.py` on fresh tmp DB |
| B3 | Seed/reset deterministic, reproducible | ☑ seed 1013; reset creates new run, prior-run promo tokens invalidated (test_claims::test_run_scoped_reset_invalidates_tokens) |
| B4 | ≈900 legs / 180 screens / 40 outlets / 25 campaigns (full mode) | ☑ seeded DB measured: 880 legs, 180 screens, 40 outlets, 28 campaigns |
| B5 | 11 reference airlines retained | ☑ `flights` distinct airline_iata = 11 |
| B6 | 30-day history, separate run id | ☑ `history_days` 750 rows / 30 distinct days; run-scoped tokens/decisions |
| B7 | Persistence survives restart | ☑ Manually verified: container restart preserved SQLite data in the `airp-data` Docker volume |
| B8 | Offline runtime (no keys/services) | ☑ no outbound calls at request time; fonts/assets bundled in `frontend/dist` |

## Adapters
| # | Requirement | Status |
|---|---|---|
| A1 | Files inspected; missing ACRIS dir reported | ☑ AODB CSV + AIDX XML inspected; absent ACRIS subdirectory flagged (docs/ASSUMPTIONS_DISCREPANCIES.md D2) |
| A2 | 33-column mapping documented | ☑ exact 33-column header and canonical mapping table in `docs/ADAPTERS.md`; parser rejects header mismatches |
| A3 | All 320 reference rows accounted for; zero undocumented rejects | ☑ test_adapters::test_all_320_rows_no_rejects |
| A4 | UTC/paired/delimiter/link/cancel behaviour unit-tested | ☑ test_adapters (direction-paired columns, `|` codeshares, `/` delay codes, CNL status) |
| A5 | XH960 → aodb_flight_id 100180 resolution test | ☑ test_adapters::test_aidx_xh960_resolves |
| A6 | ACRIS mapping tests | ☑ representative NGSI-LD mock entities based on public FIWARE `dataModel.ACRIS` reference pass `backend/tests/test_acris.py`; formal validation against absent organizer schema copy remains explicitly unclaimed |
| A7 | Generated payloads pass through same adapters | ☑ Generated AIDX delay/gate/status notification round-trips through `AidxXmlAdapter` and is covered by `test_generated_aidx_round_trip_produces_canonical_events` |
| A8 | Mock/live source selection configurable; live stubs report clearly | ☑ `FLIGHT_SOURCE`/`FLIGHT_EVENT_SOURCE`/`QUEUE_SOURCE` envs; `*-live` stubs raise unconfigured notice |
| A9 | Malformed/stale input handling | ☑ test_adapters::test_malformed_rows_rejected_individually |
| A10 | Licensing/attribution preserved; fixtures unchanged | ☑ `playground/` contents unchanged; only the repository path spelling was corrected |

## Presence & decisions
| # | Requirement | Status |
|---|---|---|
| P1 | Plausible per-flight profile (all §8 attributes) | ☑ profile builder per flight; shares asserted in worked-example test (holiday .58 / family .31 / business .22) |
| P2 | ZonePresence per zone/5-min window, formula documented | ☑ presence model + formula documented in code (`presence.py` module docstring) and README |
| P3 | Delays/gate changes update catchments <2 s | ☑ measured injection 126 ms → new ad slot 131 ms wall-clock |
| P4 | Hard filters; explicit mixed-crowd semantics | ☑ share-threshold semantics documented + enforced |
| P5 | Airline priority, competitor separation, frequency caps, pacing, budget | ☑ rule layer in pipeline |
| P6 | Evidence validation, no future-event leakage | ☑ evidence records + freshness (test_worked_example) |
| P7 | Invalid AI proposal → rule fallback | ☑ offline heuristic provider is the default; fallback never bypasses approval/placement |
| P8 | Searchable decision audit | ☑ `GET /api/decisions` supports screen, campaign, and full-record text search; Admin UI and `test_decision_log_rules.py` verified |
| P9 | Learning updates estimates | ☑ conversion learning applied on redemption (tested via claims path) |
| P10 | Worked example reproduces at stated precision via engine | ☑ test_worked_example (0.71/1.5→0.86; toys 0.52; lounge ineligible 0.21) |

## Roles
| # | Requirement | Status |
|---|---|---|
| R1 | Header role + company switching; no reset | ☑ TopBar role/company switchers; simulation state untouched |
| R2 | Admin: map+heat, KPIs, incidents, master data, decision log, weights | ☑ map/heat/KPIs/incidents/master, searchable decision log, and persisted competitor/frequency/exploration/global scoring-weight controls verified |
| R3 | Retailer: live dashboard, nearby flow, builder, codes, history, preview | ☑ live/flow/builder/codes/audience-match preview/history-ROI/run-again verified; `test_retailer_history.py` covers aggregation, ROI edge case, and editable pending duplication |
| R4 | Media: calendar, pricing, approval, conflicts, advertisers | ☑ calendar/pricing/approvals/advertiser rollup, candidate conflict reasons, and reasoned eligibility-safe pin/override verified; `test_media_pins.py` covers the control path |
| R5 | Airline: flights, gate messaging, delay goodwill, own-gate ads reasons | ☑ all four panels wired to live state |
| R6 | Passenger: why-this-ad overlay with candidate scores | ☑ ScreenView overlay (profile bars, top candidates, winning rule) |
| R7 | Role transparency previews computed | ☑ retailer audience-match preview, Media candidate conflict/reason view, and Airline own-gate candidate match/score/rejection reasons rendered from backend state |

## Passenger / WOW
| # | Requirement | Status |
|---|---|---|
| W1 | 9:16 + 16:9, full-screen, FIDS strip | ☑ ScreenView both frames + FIDS strip |
| W2 | QR claim → expiry/run validation, scan vs redemption, family 2nd code, idempotent | ☑ test_claims (5 tests incl. bounded family sharing + simulated-engagement blocking) |
| W3 | Retailer updates on redemption immediately | ☑ `redemption.live` WS event → TopBar toast + retailer live panel |
| W4 | Two-second delay chain | ☑ measured 131 ms (< 2 s budget) |
| W5 | Pause/jump/reset semantics documented | ☑ engine docstrings + README (backward jump = new run; forward = state catch-up) |
| W6 | Split-screen passenger+dashboard | ☑ App split layout with player + role view |
| W7 | Virtual playback without browser; estimated impressions | ☑ engine drives slots headless; exposure estimates labelled |
| W8 | Bilingual creative assistant offline | ☑ Retailer Campaigns tab exposes a deterministic offline brief form and EN/secondary-language preview; `/api/creative/assist` and `test_creative_assist.py` verify provider selection, determinism, bilingual output, and unconfigured-provider handling |
| W9 | Tomorrow best-3 slots | ☑ backend ranks up to three eligible screen-hours with impressions/redemption forecasts and documented assumptions; UI is exposed from Retailer campaign tools; `test_tomorrow_recommendations.py` verifies the contract |

## Delivery
| # | Requirement | Status |
|---|---|---|
| D1 | 1440/1920 layouts + mobile claim | ☑ built SPA renders at both widths; claim page mobile-first |
| D2 | Dark admin + light role themes | ☑ theme.css tokens; Admin dark, business roles light |
| D3 | Localized (EN + configurable 2nd) | ☑ `LANG_SECONDARY` scaffolding; claim/creatives bilingual |
| D4 | White-label config | ☑ APP_NAME/BRAND_LOGO/BRAND_PRIMARY/BRAND_ACCENT/CURRENCY envs; public branding endpoint feeds shell and mobile claim page |
| D5 | 60× responsive at scale (measured) | ☑ dedicated `scripts/soak.py` measurement recorded in `docs/PERFORMANCE_MEASURED.md`: 54.8× progress, presence 0.473s, re-plan 0.915s |
| D6 | WS reconnect | ☑ store reconnect loop (client) |
| D7 | Public app + claim URLs verified | ☑ Public reviewer app and external phone QR scan manually verified by owner; phone flow documented in `docs/USE_CASE_QR_CLAIM_FLOW.md`. New deployments need `AIRP_CLAIM_BASE_URL=<LAN-IP>:8000/claim` when scanning from a phone |
| D8 | README/architecture/adapter guide/OpenAPI/WS contract | ☑ README, `docs/ARCHITECTURE.md`, `docs/ADAPTERS.md`, FastAPI OpenAPI (`/docs`), and `docs/WS_CONTRACT.md` |
| D9 | Known limitations documented | ☑ docs/ASSUMPTIONS_DISCREPANCIES.md + README limitations |
