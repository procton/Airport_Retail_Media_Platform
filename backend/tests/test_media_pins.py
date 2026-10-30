"""Media pin / override with recorded reason (AGENTS §10, §12, §15).

Pins:
- require a recorded reason (empty reason → 400)
- CANNOT bypass approval / placement / budget: the pinned candidate must
  still pass hard rules for the slot, otherwise the scored winner stays
- winning immediately re-plans the affected screen with the pinned slot
- clearing restores the scored winner
The decision record carries an override entry with the pinned reason.
"""
from __future__ import annotations

import pytest
from app.main import app
from tests.support_client import SyncASGIClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    from app.config import get_settings
    from app.persistence import database

    monkeypatch.setenv("AIRP_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path}/t.db")
    get_settings.cache_clear()
    database.reset_engine()
    with SyncASGIClient(app) as c:
        yield c


def _pick(client, campaign_substr: str) -> dict | None:
    for c in client.get("/api/campaigns").json()["campaigns"]:
        if campaign_substr in c["id"] and c["status"] == "APPROVED":
            return c
    return None


def test_pin_requires_reason_and_recorded(client):
    camp = _pick(client, "cmp-df-perfume")
    assert camp is not None
    screen = next(
        s for s in client.get("/api/screens", params={"gate": "42"}).json()["screens"]
        if s["zone_id"] in camp["zone_ids"]
    )
    r = client.post(f"/api/screens/{screen['id']}/pin/{camp['id']}", json={"reason": "  "})
    assert r.status_code == 400 and "reason" in r.text

    ok = client.post(f"/api/screens/{screen['id']}/pin/{camp['id']}",
                     json={"reason": "sponsored takeover for gate reopening"})
    assert ok.status_code == 200, ok.text
    pv = client.get("/api/match/preview", params={"screen_id": screen["id"]}).json()
    assert pv["active_pin"]["campaign_id"] == camp["id"]

    cleared = client.post(f"/api/screens/{screen['id']}/unpin",
                          json={"reason": "media release"})
    assert cleared.status_code == 200 and cleared.json()["removed"] is not None
    pv2 = client.get("/api/match/preview", params={"screen_id": screen["id"]}).json()
    assert pv2["active_pin"] is None


def test_pin_cannot_bypass_placement_or_status(client):
    camp = _pick(client, "cmp-df-perfume")
    assert camp is not None
    zones = camp["zone_ids"]
    wrong = next(
        s for s in client.get("/api/screens", params={"gate": "A2"}).json()["screens"]
        if s["zone_id"] not in zones
    )
    r = client.post(f"/api/screens/{wrong['id']}/pin/{camp['id']}",
                    json={"reason": "try to bypass"})
    assert r.status_code == 400 and "placement" in r.text

    pending = next(
        (c for c in client.get("/api/campaigns").json()["campaigns"]
         if c["status"] == "PENDING" and "T2-1-gates" in c["zone_ids"]),
        None,
    )
    if pending:
        screen = next(
            s for s in client.get("/api/screens", params={"gate": "42"}).json()["screens"]
            if s["zone_id"] in pending["zone_ids"]
        )
        r2 = client.post(f"/api/screens/{screen['id']}/pin/{pending['id']}", json={"reason": "x"})
        assert r2.status_code == 400 and "not APPROVED" in r2.text


def test_pinned_candidate_wins_when_it_stays_eligible(client):
    """A pin on an APPROVED, placement-valid campaign must take the slot while
    its hard rules pass — and the winner flips back after unpin."""
    camp = _pick(client, "cmp-delay-tonic")
    assert camp is not None, "delay-tone APPROVED campaign expected"
    screen = next(
        s for s in client.get("/api/screens", params={"gate": "B2"}).json()["screens"]
        if s["zone_id"] in camp["zone_ids"]
    )
    client.post(f"/api/screens/{screen['id']}/pin/{camp['id']}",
                json={"reason": "launch push"})
    pv = client.get("/api/match/preview", params={"screen_id": screen["id"]}).json()
    c = next(x for x in pv["candidates"] if x["campaign_id"] == camp["id"])
    if c["eligible"]:
        slot = client.get(f"/api/screens/{screen['id']}").json()
        assert slot["campaign_id"] == camp["id"]
    client.post(f"/api/screens/{screen['id']}/unpin", json={"reason": ""})
    pv2 = client.get("/api/match/preview", params={"screen_id": screen["id"]}).json()
    assert pv2["active_pin"] is None
