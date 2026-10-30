# Meridian Retail Media — Airport Retail Media Platform (POC)

A locally runnable prototype of an airport retail media platform for the fictional
**Meridian International (MQI)** airport: flight-driven ad scheduling, passenger-presence
estimates, evidence-backed campaign decisions, live gate screens with QR promo claims,
and role dashboards that all read one shared simulation state.

Demo day: **2026-10-14** (synthetic, seed 1013). The clock is backend-owned — "today"
is always the simulation day, never your laptop date.

- **Stack:** Python 3.12 · FastAPI · Pydantic · SQLAlchemy + SQLite · Alembic · WebSockets · React 19 + TypeScript (Vite, zustand, recharts, qrcode.react) · Docker Compose. SQLite writes use short-lived isolated SQLAlchemy sessions behind the async service boundary.
- **Why this stack:** Python keeps feed adapters, simulation, presence, scoring, evidence validation, and persistence in one testable backend; FastAPI supplies typed REST/OpenAPI and WebSockets; React/TypeScript provides the responsive role dashboards, screen player, and mobile claim UI; SQLite/Alembic keep local persistence reproducible without infrastructure; Docker Compose makes the complete demo one-command runnable. The provider interfaces keep AI optional and offline by default.
- **Offline:** no API keys, no CDNs, no cloud calls. Fonts/assets are local; the AI
  providers are offline template/heuristic mocks.

## What the demo shows (the required cause-and-effect chain)

1. Admin map: 180 screens, zones, heat overlay, health, live KPIs.
2. Inject an **AIDX flight delay** (e.g. XY 501-protégé stand-in at Gate 42 +45 min).
3. Within ~2 wall-clock seconds: airline view updates, zone presence rises,
   gate screens re-plan to the delay-triggered duty-free campaign.
4. Scan the gate-screen QR → mobile claim page → **Redeem**.
5. Retailer dashboard shows the redemption and attributed revenue immediately;
   Media Manager inventory and incident views stay consistent.
6. Reset/reseed deterministically at any time (top bar).

The Gate-42 worked example (match 0.71 / boost 1.5 / final 0.86, toys 0.52, lounge
filtered 0.21) is reproduced by the live engine — see `backend/tests/test_worked_example.py`.
For the timed presentation path covering the complete WOW sequence, follow
[`docs/WOW_DEMO_SCRIPT.md`](docs/WOW_DEMO_SCRIPT.md).

## Run it

### Verified reviewer playground URL

The reviewer endpoint and external phone QR claim flow have been manually
verified by the owner.

http://ec2-56-228-5-232.eu-north-1.compute.amazonaws.com:8000/

### Option A — Docker (one command, includes migrations + seed)

```bash
docker compose up --build
```

- App + API + WebSockets: http://localhost:8000 (built React SPA is served by FastAPI)
- OpenAPI: http://localhost:8000/docs
- SQLite persists in the `airp-data` volume; `alembic upgrade head` runs at startup.

### QR claim tester runbook

For the exact Gate-42 delay → QR scan → phone redemption → retailer revenue
journey, follow [`docs/USE_CASE_QR_CLAIM_FLOW.md`](docs/USE_CASE_QR_CLAIM_FLOW.md).
It includes the required simulation time, phone/LAN configuration, expected
state checkpoints, and troubleshooting.

### Option B — local development

```bash
# backend
uv venv .venv            # or: python3 -m venv .venv
uv sync --frozen         # installs pinned deps from uv.lock
.venv/bin/alembic -c backend/alembic.ini upgrade head
.venv/bin/uvicorn app.main:app --app-dir backend --port 8000

# frontend (dev server with proxy; only needed while iterating on UI)
cd frontend && npm install && npm run dev   # http://localhost:5173
```

The backend seeds itself on first boot (full mode: ~900 flight legs, 180 screens,
40 outlets, 25 campaigns, 30-day history). `AIRP_DATA_DIR` relocates the SQLite file.

### Offline / preparation

First `uv sync`, `npm install`, and `docker compose up --build` download packages.
After that, **runtime is fully offline** (no external calls at request time).
The fixture licences live in `playground/` unchanged.

## Configuration (env vars, no prefix)

| Key | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `sqlite+aiosqlite:///./data/app.db` | SQLite location (async driver) |
| `AIRP_DATA_DIR` | – | Convenience dir override for the DB |
| `AIRP_CLAIM_BASE_URL` | – | Same as `CLAIM_BASE_URL`; route layer reads either |
| `OPERATING_DAY` | `2026-10-14` | Simulation day (dates regenerate coherently) |
| `SEED_MODE` / `SEED_SEED` | `full` / `1013` | Reference-only seed or full synthetic; determinism |
| `SIM_SPEED` | `1` | Initial speed (top bar can change 1×/10×/60×) |
| `FLIGHT_SOURCE` / `FLIGHT_EVENT_SOURCE` / `QUEUE_SOURCE` | `mock-aodb` / `mock-aidx` / `mock-acris` | Adapter selection (`*-live` stubs report "unconfigured") |
| `CREATIVE_PROVIDER` / `RANKING_PROVIDER` | `offline-template` / `offline-heuristic` | Pluggable AI boundaries, offline by default; set `CREATIVE_PROVIDER=llm-openai-compatible` for an optional LLM creative draft |
| `PROVIDER_ENABLED` | `false` | When false, decisions never wait on a provider |
| `LLM_API_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` | empty | OpenAI-compatible `/chat/completions` endpoint, credential, and model used by the optional creative assistant |
| `CLAIM_BASE_URL` | empty → derives from request host | **QR/claim base URL.** Set e.g. `http://192.168.1.50:8000/claim` so phones on the LAN can scan (never keep `localhost` when testing from a phone) |
| `PUBLIC_BASE_URL` | empty | Used for shareable links |
| `LANG_PRIMARY` / `LANG_SECONDARY` | `en` / `es` | UI/creative bilingual pair |
| `APP_NAME`, `BRAND_LOGO`, `BRAND_PRIMARY`, `BRAND_ACCENT`, `CURRENCY`, `CURRENCY_SYMBOL` | Meridian Retail Media, `M`, etc. | White-label knobs; `BRAND_LOGO` accepts text/emoji or a local/public image path |

Each ingest source has a `Protocol` adapter with a working mock and an
unconfigured live stub; see `docs/ADAPTERS.md` for the adapter guide, column
mappings and freshness policy, and `docs/ARCHITECTURE.md` for the data-flow
diagram.

The optional LLM creative assistant is restricted to structured creative drafts:
the response is schema-validated before it reaches the UI, and it never chooses
campaigns, schedules screens, or persists data. Keep the default offline
provider for demos without credentials. See `docs/LLM_INTEGRATION.md` for setup
and safety limits.

## Sim controls (visible on every role view)

- Play/pause, `1×/10×/60×`, jump-to-time — top bar, shared by all roles.
- Inject flight delay / gate change / cancel (AIDX-shaped events through the real adapter path).
- Reset day (new run; seeded state reconstructed, previous-run promo tokens invalid).
- Injection works while paused; claims work while paused.

## Tests

```bash
.venv/bin/pytest backend/tests -q      # 39 tests at the latest verification
./.venv/bin/ruff check backend
cd frontend && npm run lint && npm run build
```

Latest verification: the complete backend suite passes (`39 passed`), Ruff
reports no backend findings, and the frontend lint/build commands complete
successfully. Oxlint currently emits advisory React hook/purity warnings but
no lint errors.

Layers present: AODB/AIDX reference-fixture parsing (all 320 rows, pairing, UTC,
XH960→100180 resolution), worked-example regression via the live engine, claims
(scan/redeem idempotency, family sharing bounds, simulated-engagement blocking,
run-scoped reset invalidation).

## Known limitations & assumptions (also in docs/ASSUMPTIONS_DISCREPANCIES.md)

- ACRIS reference fixtures were expected under the fixtures directory but none
  ship with the AODB/AIDX set — queue entities follow the platform's documented
  ACRIS-style mapping instead (flagged in the adapter guide, not silently
  substituted).
- Impressions are estimated exposure opportunities (presence-driven), and some
  engagement is auto-generated and labelled `simulated-engagement`; phone claims
  never redeem simulated tokens, and no passenger identity is ever collected.
- The Gate-42 example uses the organizer's XY501/DXB identifiers in a labelled
  scenario/test; the MQI dataset keeps its own fictional flight ids.
- Revenue is simulated accounting, not payment processing.
- External phone QR claim flow was manually verified on the deployed reviewer
  endpoint. Configure `AIRP_CLAIM_BASE_URL` for any new deployment before
  scanning from a phone.
