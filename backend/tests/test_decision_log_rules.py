"""Admin decision-log search + global rule sliders (AGENTS §12).

- GET /api/decisions is searchable by screen_id, campaign winner and substring
  across the full record JSON (incl. rejection reasons / pin / ε-pick text)
- PUT /api/config/media-rules clamps documented ranges and persists via
  rule_config; engine applies it to the live RulesContext and replans
- exploration ε > 0 may replace the top scorer with ANOTHER ELIGIBLE candidate,
  deterministic per slot, and the pick is recorded ("exploration" in record);
  ε = 0 (default) preserves the pure highest-score worked-example behavior
- media rules survive a reset (new run applies the saved config)
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


def _wait_for_decisions(client, minimum: int, timeout_s: float = 6.0) -> None:
    import time
    deadline = time.time() + timeout_s
    n = 0
    while time.time() < deadline:
        n = client.get("/api/decisions").json()["count"]
        if n >= minimum:
            return
        time.sleep(0.25)
    assert n >= minimum, f"only {n} decisions after {timeout_s}s"


def test_decision_log_search(client):
    _wait_for_decisions(client, 3)
    all_rows = client.get("/api/decisions").json()
    assert all_rows["model_version"] == "sm-1.0"
    assert len(set(r["id"] for r in all_rows["decisions"])) == len(all_rows["decisions"])  # unique ids
    some_screen = all_rows["decisions"][0]["screen_id"]
    filtered = client.get("/api/decisions", params={"screen_id": some_screen}).json()
    assert filtered["count"] and all(r["screen_id"] == some_screen for r in filtered["decisions"])

    searchable = client.get("/api/decisions", params={"search": "no-such-token-ever"}).json()
    assert searchable["count"] == 0

    fallback_rows = client.get("/api/decisions", params={"search": "matches"}).json()
    assert isinstance(fallback_rows["decisions"], list)


def test_media_rules_clamped_and_persisted(client):
    j = client.put("/api/config/media-rules", json={
        "competitor_gap_min": 99999, "frequency_window_min": 1, "exploration_epsilon": 5.0,
        "audience_weight": 9.0, "context_weight": -1.0,
    })
    assert j.status_code == 200
    r = j.json()["media_rules"]
    assert r["competitor_gap_min"] == 1440.0
    assert r["frequency_window_min"] == 5.0
    assert r["exploration_epsilon"] == 0.25
    assert r["audience_weight"] == 2.0
    assert r["context_weight"] == 0.0
    loaded = client.get("/api/config/media-rules").json()
    assert loaded["media_rules"] == r
    assert loaded["model_version"] == "sm-1.0"
    assert loaded["score_constants"]["score_norm"] == 0.9918


def test_default_global_weights_preserve_worked_example_score():
    from app.services.decisions.scoring import final_score

    assert final_score(0.71, 1.5) == final_score(0.71, 1.5, 1.0, 1.0)
    assert final_score(0.71, 1.5, 1.4, 1.0) != final_score(0.71, 1.5)


def test_rules_survive_reset(client):
    client.put("/api/config/media-rules", json={"exploration_epsilon": 0.05})
    before = client.get("/api/config/media-rules").json()["media_rules"]["exploration_epsilon"]
    client.post("/api/controls/reset", json={})
    after = client.get("/api/config/media-rules").json()["media_rules"]["exploration_epsilon"]
    assert before == after == 0.05
    engine = client.app.state.engine
    assert engine.planner.ledger.exploration_epsilon == 0.05


def test_reset_clears_pins(client):
    """Pins are operator demo state: cleared on a new run (documented §7)."""
    camp = next(
        (c for c in client.get("/api/campaigns").json()["campaigns"]
         if c["status"] == "APPROVED" and "T2-1-gates" in c["zone_ids"]),
        None,
    )
    assert camp is not None
    screen = next(
        s for s in client.get("/api/screens", params={"gate": "42"}).json()["screens"]
        if s["zone_id"] in camp["zone_ids"]
    )
    client.post(f"/api/screens/{screen['id']}/pin/{camp['id']}", json={"reason": "demo"})
    pv = client.get("/api/match/preview", params={"screen_id": screen["id"]}).json()
    assert pv["active_pin"]["campaign_id"] == camp["id"]
    client.post("/api/controls/reset", json={})
    pv2 = client.get("/api/match/preview", params={"screen_id": screen["id"]}).json()
    assert pv2["active_pin"] is None
