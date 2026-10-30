"""Creative assistant (AGENTS §18 WOW, §3 provider boundary).

- offline default: brief → ready bilingual template ad, deterministic
- provider selection is configuration-driven
- live stubs report unconfigured integration instead of faking payloads
- returns structured proposals only (no persistence/scheduling side effects)
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


def test_offline_assist_bilingual_deterministic(client):
    brief = {"product": "Festive sweets", "discount_pct": 20, "audience": "family"}
    j1 = client.post("/api/creative/assist", json=brief)
    assert j1.status_code == 200, j1.text
    p = j1.json()
    assert p["provider"] == "offline-template"
    c = p["creative"]
    assert "Festive sweets" in c["headline_en"] and "20% off" in c["headline_en"]
    assert c["headline_alt"] and "sweets" in c["headline_alt"].lower()
    assert set(p["lang"]) == {"es", "en"}
    copy = ["headline_en", "headline_alt", "body_en", "body_alt", "cta", "bg", "fg", "image"]
    assert all(k in c for k in copy)
    j2 = client.post("/api/creative/assist", json=brief).json()
    assert j2["creative"] == c  # deterministic


def test_assist_audiences_swap_templates(client):
    fam = client.post("/api/creative/assist", json={"product": "Blocks", "audience": "children"}).json()
    bus = client.post("/api/creative/assist", json={"product": "Lounge day", "audience": "business"}).json()
    assert fam["creative"]["image"] != bus["creative"]["image"]
    assert "2" in fam["creative"]["headline_en"] or "buy" in fam["creative"]["headline_en"].lower()


def test_unconfigured_provider_reports_clearly(client, monkeypatch):
    eng = client.app.state.engine
    from app.providers.creative import assistant_for

    monkeypatch.setattr(eng.settings, "creative_provider", "live-openai", raising=False)
    r = client.post("/api/creative/assist", json={"product": "Perfume"})
    assert r.status_code == 501, r.text
    assert "unconfigured" in r.text.lower()
    assert assistant_for("offline-template") is not None  # selection works


def test_openai_compatible_provider_validates_structured_response(monkeypatch):
    import asyncio

    from app.providers.creative import CreativeBrief, OpenAICompatibleAssistant

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self):
            import json
            draft = {
                "headline_en": "Perfume — 15% off",
                "headline_alt": "Perfume — 15% dto",
                "body_en": "Claim before boarding.",
                "body_alt": "Reclama antes de embarcar.",
                "cta": "Scan to claim",
                "bg": "#123456",
                "fg": "#ffffff",
                "image": "motif-arc",
                "show_code": True,
            }
            return json.dumps({"choices": [{"message": {"content": json.dumps(draft)}}]}).encode()

    def fake_urlopen(request, timeout):
        assert request.headers["Authorization"] == "Bearer test-key"
        assert timeout == 1.5
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    async def direct_call(fn, *args):
        return fn(*args)
    monkeypatch.setattr(asyncio, "to_thread", direct_call)
    provider = OpenAICompatibleAssistant("http://llm.test/v1", "test-key", "demo-model", 1.5)
    result = asyncio.run(provider.assist(CreativeBrief(product="Perfume"), "es"))
    assert result["provider"] == "llm-openai-compatible"
    assert result["creative"]["headline_en"] == "Perfume — 15% off"


def test_openai_compatible_provider_requires_configuration():
    from app.providers.creative import OpenAICompatibleAssistant, ProviderUnconfigured

    with pytest.raises(ProviderUnconfigured):
        OpenAICompatibleAssistant("", "", "", 1.0)


def test_bad_payload_422(client):
    r = client.post("/api/creative/assist", json={})
    assert r.status_code == 422
