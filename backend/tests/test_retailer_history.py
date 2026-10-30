"""Retailer history ledger & run-again duplication (AGENTS §14).

- history aggregates per campaign from seeded 30-day history_days rows
- ROI = revenue/spend; null when spend is 0 (no Infinity)
- run-again duplicates one past campaign into a NEW editable PENDING campaign
  with a fresh schedule; duplicate persists and is id-safe on repeat calls
- attributed revenue is simulated accounting, distinct from the live run
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


def test_history_aggregates_and_roi(client):
    j = client.get("/api/retailer/history", params={"outlet": "out-t2-df"}).json()
    assert j["outlet_prefix"] == "out-t2-df"
    rows = j["campaigns"]
    assert rows, "seeded 30-day history must produce rows for the duty-free outlet"
    top = rows[0]
    assert top["days"] >= 25
    assert top["impressions"] > 0 and top["revenue"] > 0
    if top["spend"] > 0:
        assert abs(top["roi"] - top["revenue"] / top["spend"]) < 0.01
    zero_spend = [r for r in rows if r["spend"] == 0]
    assert all(r["roi"] is None for r in zero_spend)
    assert "simulated accounting" in j["note"]


def test_rerun_creates_editable_pending_campaign(client):
    src = "cmp-df-perfume"
    r1 = client.post("/api/campaigns/rerun", json={"campaign_id": src})
    assert r1.status_code == 200, r1.text
    j = r1.json()
    new_id = j["campaign_id"]
    assert new_id != src and j["campaign"]["status"] == "PENDING"
    assert j["campaign"]["zone_ids"]  # schedule copied

    all_campaigns = {c["id"]: c for c in client.get("/api/campaigns").json()["campaigns"]}
    assert new_id in all_campaigns and all_campaigns[new_id]["status"] == "PENDING"
    assert all_campaigns[src]["status"] in ("APPROVED", "REJECTED", "PAUSED", "COMPLETE")

    r2 = client.post("/api/campaigns/rerun", json={"campaign_id": src})
    assert r2.status_code == 200 and r2.json()["campaign_id"] != new_id

    still = client.post("/api/campaigns/rerun", json={"campaign_id": "no-such"})
    assert still.status_code == 404
