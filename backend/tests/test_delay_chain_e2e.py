"""End-to-end two-second delay chain (AGENTS §18 live cause & effect).

Injecting an AIDX delay must, within two wall-clock seconds:
  1. update the airline flight state (delay minutes on the live flight row),
  2. re-plan the affected gate screens (offer boosted, slot re-assigned),
  3. raise the affected zone presence per the documented dwell model
     (delay pushes a flight's holding passengers back into the boarding window,
     so XY501 at gate 42 rises from the 0.35-band to the 1.0-band weight).

Uses the gate-42 scenario flights (wx:XY501) with the engine's real adapter
path (POST /api/controls/flight-event → AIDX notification → canonical event).
"""
from __future__ import annotations

import time

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


def _wait_settle(c) -> dict:
    """After a jump, wait until the zone projection stops changing."""
    last = None
    c.get("/api/screens?gate=42").json()["screens"][0]["zone_id"]
    for _ in range(30):
        z = {x["zone_id"]: x for x in c.get("/api/zones").json()["zones"]}
        crowd = {k: v["passenger_count"] for k, v in z.items()}
        if crowd == last:
            break
        last = crowd
        time.sleep(0.1)
    return z


def test_two_second_delay_chain(client):
    c = client
    c.post("/api/controls/jump", json={"at": "2026-10-14T14:51:00+00:00"})
    time.sleep(1.0)
    z = _wait_settle(c)
    scr = c.get("/api/screens?gate=42").json()["screens"][0]
    zid = scr["zone_id"]
    base = c.get(f"/api/screens/{scr['id']}").json()
    crowd0 = z[zid]["passenger_count"]
    base_slot_id = base["slot_id"]

    t0 = time.monotonic()
    inject = c.post(
        "/api/controls/flight-event",
        json={"flight_id": "wx:XY501", "kind": "delay", "minutes": 40},
    )
    assert inject.status_code == 200, inject.text

    delay_seen = False
    boosted = False
    raised = False
    slot_reassigned = False
    while time.monotonic() - t0 < 2.0:
        fl = c.get("/api/flights?q=XY501").json()["flights"][0]
        delay_seen = int(fl.get("delay_min") or 0) >= 40
        s = c.get(f"/api/screens/{scr['id']}").json()
        slot_reassigned = s["slot_id"] != base_slot_id
        top = {x["campaign_id"]: x for x in (s.get("why") or {}).get("top_candidates", [])}
        cand = top.get("wx-DUTY-PERFUME") or {}
        boosted = float(cand.get("boost", 0.0)) >= 1.5
        znow = {x["zone_id"]: x for x in c.get("/api/zones").json()["zones"]}
        raised = znow[zid]["passenger_count"] >= crowd0 + 80
        if delay_seen and boosted and raised and slot_reassigned:
            break
        time.sleep(0.04)

    elapsed = time.monotonic() - t0
    assert delay_seen, "airline flight state must show the delay"
    assert boosted, "delay-triggered offer must be boosted (1.5)"
    assert slot_reassigned, "gate screen must have been re-planned"
    assert raised, "zone presence must rise per the dwell model"
    assert elapsed <= 2.0, f"propagation took {elapsed:.2f}s (> 2s budget)"

    post = c.get(f"/api/zones/{zid}").json()
    contrib = post["contributing_flights"]
    assert "wx:XY501" in contrib, contrib
    assert contrib["wx:XY501"] > 150, contrib  # 0.35→~0.93 band of 240 pax
