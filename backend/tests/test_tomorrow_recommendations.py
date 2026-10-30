"""Backend-owned tomorrow slot recommendations (AGENTS §18)."""
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


def test_tomorrow_recommendation_returns_at_most_three_ranked_eligible_slots(client):
    response = client.get("/api/campaigns/cmp-df-perfume/recommend-slots")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["horizon"] == "tomorrow"
    assert body["day"] == "2026-10-15"
    assert len(body["items"]) <= 3
    assert body["assumptions"]
    assert all(item["eligible"] for item in body["items"])
    assert all(item["predicted_impressions"] >= 0 for item in body["items"])
    assert body["items"] == sorted(
        body["items"],
        key=lambda item: (-item["predicted_impressions"], -item["score"], item["screen_id"], item["hour"]),
    )


def test_tomorrow_recommendation_rejects_unknown_campaign(client):
    response = client.get("/api/campaigns/no-such/recommend-slots")
    assert response.status_code == 404
