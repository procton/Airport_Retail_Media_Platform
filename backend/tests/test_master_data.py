"""Admin master-data CRUD (§13)."""
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


def test_master_data_crud_persists_and_updates_runtime(client):
    created = client.post("/api/master-data/vendors", json={
        "id": "vendor-demo", "data": {"name": "Demo Screens Ltd", "status": "active"}
    })
    assert created.status_code == 200, created.text
    assert any(row["id"] == "vendor-demo" for row in client.get("/api/master-data/vendors").json()["items"])

    updated = client.patch("/api/master-data/vendors/vendor-demo", json={
        "id": "vendor-demo", "data": {"name": "Demo Screens Ltd", "status": "approved"}
    })
    assert updated.status_code == 200, updated.text
    row = next(row for row in client.get("/api/master-data/vendors").json()["items"] if row["id"] == "vendor-demo")
    assert row["data"]["status"] == "approved"

    duplicate = client.post("/api/master-data/vendors", json={"id": "vendor-demo", "data": {}})
    assert duplicate.status_code == 409

    deleted = client.delete("/api/master-data/vendors/vendor-demo")
    assert deleted.status_code == 200
    assert not any(row["id"] == "vendor-demo" for row in client.get("/api/master-data/vendors").json()["items"])


def test_seeded_entities_are_editable(client):
    outlets = client.get("/api/master-data/outlets")
    airlines = client.get("/api/master-data/airlines")
    screens = client.get("/api/master-data/screens")
    assert outlets.status_code == airlines.status_code == screens.status_code == 200
    assert outlets.json()["count"] == 40
    assert airlines.json()["count"] == 11
    assert screens.json()["count"] == 180
