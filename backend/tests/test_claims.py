"""Claims pipeline tests (§17): scan → redeem idempotency, family code,
simulated-engagement tokens never phone-redeemable, run/expiry rules."""
from __future__ import annotations

import asyncio
import time
from datetime import UTC

import pytest
from app.main import app
from app.persistence.models import PromoTokenRow
from sqlalchemy import select
from tests.support_client import SyncASGIClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    from app.config import get_settings
    from app.persistence import database

    monkeypatch.setenv("AIRP_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path}/t.db")
    monkeypatch.setenv("AIRP_CLAIM_BASE_URL", "http://lan-host.example/claim")
    get_settings.cache_clear()
    database.reset_engine()
    with SyncASGIClient(app) as c:
        # deterministic demo setup: gate 42 delay → WX-PERFUME15 on a gate-42 screen
        c.post("/api/controls/jump", json={"at": "2026-10-14T13:30:00+00:00"})
        c.post("/api/controls/flight-event", json={"flight_id": "wx:XY501", "kind": "delay", "minutes": 45})
        deadline = time.time() + 10
        row = None
        while time.time() < deadline:
            v = c.get("/api/screens?gate=42").json()["screens"]
            if v and v[0].get("current_slot") and v[0]["current_slot"].get("promo"):
                row = v[0]
                break
            time.sleep(0.2)
        assert row is not None, "gate-42 slot never showed a QR within 10 s"
        yield c, row


def _token(row) -> str:
    return row["current_slot"]["promo"]["token"]


def test_claim_scan_then_redeem_once(client):
    c, row = client
    tok = _token(row)
    page = c.post(f"/api/claims/{tok}").json()
    assert page["code"] == "WX-PERFUME15"
    assert page["valid_now"] is True
    assert "localhost" not in page["claim_url"], page["claim_url"]

    first = c.post(f"/api/claims/{tok}/redeem", json={"mode": "phone"}).json()
    assert first["already"] is False
    assert first["campaign_id"] == "wx-DUTY-PERFUME"
    assert first["value"] == 15.0

    second = c.post(f"/api/claims/{tok}/redeem", json={"mode": "counter"}).json()
    assert second["already"] is True, second
    assert second["campaign_id"] == first["campaign_id"]


def test_gate42_qr_contains_reachable_claim_route(client):
    """The worked-example screen exposes a browser route a phone can open."""
    c, row = client
    config = c.get("/api/config/public")
    assert config.status_code == 200
    assert config.json()["name"] == "Meridian Retail Media"
    assert config.json()["logo"] == "M"
    slot = row["current_slot"]
    tok = _token(row)
    detail = c.get(f"/api/screens/{row['id']}").json()
    detail_slot = detail.get("current_slot", detail)

    assert row["gate"] == "42"
    assert slot["campaign_id"] in {"cmp-df-perfume", "wx-DUTY-PERFUME"}
    assert slot["promo"]["code"] == "WX-PERFUME15"
    assert detail_slot["claim_url"] == f"http://lan-host.example/claim/{tok}"

    # The QR target is a real SPA route, not only an API token string.
    page = c.get(f"/claim/{tok}")
    assert page.status_code == 200
    assert "<div id=\"root\">" in page.text


def test_family_issue_second_code(client):
    """Bounded sharing: only family-kind codes can issue a companion code;
    the companion token is independent and one-time."""
    c, _row = client
    eng = c.app.state.engine
    import asyncio
    from datetime import datetime

    loop = asyncio.new_event_loop()
    try:
        codes = loop.run_until_complete(eng.dao.load_promo_codes())
    finally:
        loop.close()

    def win(r):
        s, e = r.get("window_start"), r.get("window_end")
        def p(v):
            return datetime.fromisoformat(v).replace(tzinfo=UTC) if isinstance(v, str) else v
        return (p(s) if s else None, p(e) if e else None)

    now = eng.clock.sim_now
    rows_flat = [c for c in codes if c.get("kind") == "family"]
    assert rows_flat, "seed must contain family-kind promo codes"
    covering = [(c["campaign_id"], c) for c in rows_flat if win(c)[0] and win(c)[0] <= now < win(c)[1]]
    campaign, code_row = covering[0] if covering else (rows_flat[0]["campaign_id"], rows_flat[0])
    if not covering:
        # pick a family code whose window has not fully passed; jump if needed
        future = [c for c in rows_flat if (win(c)[1] or now) > now]
        assert future, "seed must contain a not-yet-expired family code"
        code_row = min(future, key=lambda c: win(c)[0] or now)
        campaign = code_row["campaign_id"]
        start = win(code_row)[0]
        if start and start > now:
            c.post("/api/controls/jump", json={"at": start.isoformat()})
    loop = asyncio.new_event_loop()
    try:
        tok = loop.run_until_complete(_mint(eng, code_row, campaign))
    finally:
        loop.close()
    fam = c.post(f"/api/claims/{tok}/family").json()
    assert fam["token"] and fam["token"] != tok
    page = c.post(f"/api/claims/{fam['token']}").json()
    assert page["family_shared"] is True
    red = c.post(f"/api/claims/{fam['token']}/redeem", json={}).json()
    assert red["already"] is False
    # sharing is one-time: a second companion request is rejected
    again = c.post(f"/api/claims/{tok}/family")
    assert again.status_code in (400, 409), again.text
    # one-time bundle: redeeming one member voids the sibling code
    owner = c.post(f"/api/claims/{tok}/redeem", json={})
    assert owner.status_code == 200 and owner.json()["already"] is True, owner.text


async def _mint(eng, code_row, campaign) -> str:
    from datetime import datetime, timedelta
    from uuid import uuid4

    def aware(v):
        if not isinstance(v, str):
            return v
        dt = datetime.fromisoformat(v)
        return dt if dt.tzinfo else dt.replace(tzinfo=UTC)

    t = eng.clock.sim_now
    expiry = aware(code_row.get("window_end")) if code_row.get("window_end") else t + timedelta(hours=2)
    tok = uuid4().hex[:20]
    await eng.dao.add_token({
        "token": tok, "promo_code_id": code_row["id"], "run_id": eng.run_id,
        "issued_at": t, "expires_at": expiry,
        "redeemed_at": None, "scanned_at": None, "family_index": 0,
        "mode": "phone", "revenue_value": float(code_row.get("value", 5.0)) or 5.0,
    })
    return tok


def test_unknown_token_404(client):
    c, _ = client
    assert c.post("/api/claims/bogusbogus").status_code == 404
    assert c.post("/api/claims/bogusbogus/redeem", json={}).status_code == 404


def test_simulated_engagement_tokens_not_phone_claimable(client):
    """Auto-issued engagement tokens mimic ad engagement for metrics; a phone
    cannot redeem one (recorded distinction §17)."""
    c, _row = client
    eng = c.app.state.engine
    time.sleep(0.5)
    tokens = []
    for _ in range(20):  # poll up to ~6s: one flush cadence (1.5 s idle) must persist engagement tokens
        tokens = asyncio.new_event_loop().run_until_complete(_all_tokens(eng))
        if any(r.get("mode") == "simulated-engagement" for r in tokens):
            break
        time.sleep(0.3)
    sim_tokens = [r for r in tokens if (r.get("mode") == "simulated-engagement")]
    assert sim_tokens, "simulated-engagement tokens must be recorded in the DB"
    target = sim_tokens[0]["token"]
    r = c.post(f"/api/claims/{target}/redeem", json={})
    assert r.status_code == 409, f"simulated token must be blocked: got {r.status_code}"
    assert "simulated" in r.text.lower(), r.text


def test_run_scoped_reset_invalidates_tokens(client):
    """Previous-run tokens never regain validity after reset (§7)."""
    c, row = client
    tok = _token(row)
    r = c.post("/api/controls/reset", json={})
    assert r.status_code == 200, r.text
    time.sleep(1.0)
    page = c.post(f"/api/claims/{tok}").json()
    assert page.get("valid_now") is False, page
    red = c.post(f"/api/claims/{tok}/redeem", json={})
    assert red.status_code in (409, 410), red.json()


async def _all_tokens(eng) -> list[dict]:
    async with eng.dao.sm() as s:
        rows = (await s.execute(select(PromoTokenRow))).scalars().all()
        return [
            {
                "token": r.token,
                "mode": r.mode,
                "run_id": r.run_id,
                "redeemed_at": r.redeemed_at,
                "code": r.promo_code_id,
            }
            for r in rows
        ]
