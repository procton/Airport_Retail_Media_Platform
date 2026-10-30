from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = REPO_ROOT / "playground"


class Settings(BaseSettings):
    """Runtime configuration (env-driven). Every value has an offline-safe default."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Meridian Retail Media"
    airport_name: str = "Meridian International"
    airport_code: str = "MQI"
    brand_primary: str = "#0ea5e9"
    brand_accent: str = "#f59e0b"
    brand_logo: str = "M"  # text/emoji or a local/public image path

    # database
    database_url: str = "sqlite+aiosqlite:///./data/app.db"

    # seed behaviour
    seed_mode: str = "full"  # full | reference
    seed_seed: int = 1013
    operating_day: str = "2026-10-14"
    scenario: str = "gate42"  # default demo scenario enabled at boot

    # source adapters
    flight_source: str = "mock-aodb"
    flight_event_source: str = "mock-aidx"
    queue_source: str = "mock-acris"
    aodb_csv: str = str(FIXTURE_DIR / "MQI_aodb_flights_2026-10-14_SYNTHETIC.csv")

    # simulation
    sim_speed: int = 1
    sim_start_offset_min: int = -15  # start 15 sim minutes post-midnight
    slot_seconds: int = 15
    decision_history_limit: int = 5000

    # providers
    creative_provider: str = "offline-template"
    ranking_provider: str = "offline-heuristic"
    provider_call_timeout_s: float = 1.0
    provider_enabled: bool = False  # when false, slots never wait for AI providers
    llm_api_base_url: str = ""  # OpenAI-compatible `/chat/completions` endpoint
    llm_api_key: str = ""
    llm_model: str = ""

    # realtime / network
    ws_tick_ms: int = 250
    public_base_url: str = ""
    claim_base_url: str = ""  # if empty, derives request.host

    # demo targets
    currency: str = "USD"
    currency_symbol: str = "$"
    lang_primary: str = "en"
    lang_secondary: str = "es"
    timezone_display: str = "UTC"

    # rate / freshness
    aidx_staleness_s: int = 600
    queue_staleness_s: int = 300

    @property
    def claim_url_base(self) -> str:
        return self.claim_base_url.rstrip("/") if self.claim_base_url else self.public_base_url.rstrip("/")


@lru_cache
def get_settings() -> Settings:
    env_overrides = {}
    # allow docker env var to seed data dir INSIDE container mounts
    s = Settings()
    env_overrides = None  # noqa: F841
    if os.environ.get("AIRP_DATA_DIR") and "aiosqlite" in s.database_url:
        s.database_url = f"sqlite+aiosqlite:///{os.environ['AIRP_DATA_DIR']}/app.db"
    return s
