"""SQLAlchemy ORM tables. Domain logic does not depend on these directly;
persistence/dao.py owns the mapping."""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(tz=UTC)


class Base(DeclarativeBase):
    pass


class SimRun(Base):
    __tablename__ = "sim_runs"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    seed: Mapped[int] = mapped_column(Integer)
    mode: Mapped[str] = mapped_column(String(20))
    scenario: Mapped[str] = mapped_column(String(40), default="")
    operating_day: Mapped[str] = mapped_column(String(10))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    status: Mapped[str] = mapped_column(String(20), default="active")


class EvidenceRecord(Base):
    __tablename__ = "evidence_records"
    id: Mapped[str] = mapped_column(String(48), primary_key=True)
    source: Mapped[str] = mapped_column(String(64))
    source_record_id: Mapped[str] = mapped_column(String(96), default="")
    source_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ingestion_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    adapter: Mapped[str] = mapped_column(String(48))
    freshness: Mapped[str] = mapped_column(String(24), default="scheduled")
    provenance: Mapped[str] = mapped_column(String(24), default="synthetic")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)


class FlightRow(Base):
    __tablename__ = "flights"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    aodb_flight_id: Mapped[str] = mapped_column(String(16))
    linked_flight_id: Mapped[str] = mapped_column(String(16), default="")
    direction: Mapped[str] = mapped_column(String(1))
    airline_iata: Mapped[str] = mapped_column(String(3))
    airline_icao: Mapped[str] = mapped_column(String(3))
    flight_number: Mapped[str] = mapped_column(String(5))
    flight_nature: Mapped[str] = mapped_column(String(1))
    origin: Mapped[str] = mapped_column(String(4))
    destination: Mapped[str] = mapped_column(String(4))
    terminal: Mapped[str] = mapped_column(String(2))
    sched_std: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    tobt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    tsat: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    etd: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    eldt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    aldt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    aibt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    stand: Mapped[str] = mapped_column(String(12), default="")
    gate: Mapped[str] = mapped_column(String(12), default="")
    aircraft_type: Mapped[str] = mapped_column(String(6), default="")
    aircraft_reg: Mapped[str] = mapped_column(String(12), default="")
    seats: Mapped[int] = mapped_column(Integer, default=0)
    pax: Mapped[int] = mapped_column(Integer, default=0)
    status_raw: Mapped[str] = mapped_column(String(4))
    cancelled: Mapped[bool] = mapped_column(Boolean, default=False)
    delay_codes: Mapped[str] = mapped_column(String(48), default="")
    handler: Mapped[str] = mapped_column(String(48), default="")
    evidence_id: Mapped[str] = mapped_column(String(48), default="")
    source: Mapped[str] = mapped_column(String(24), default="aodb")
    Index("ix_flights_std", "sched_std")


class FlightEventRow(Base):
    __tablename__ = "flight_events"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(40), ForeignKey("sim_runs.id"))
    flight_leg_id: Mapped[str] = mapped_column(String(40))
    kind: Mapped[str] = mapped_column(String(16))
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    delay_minutes: Mapped[int] = mapped_column(Integer, default=0)
    new_gate: Mapped[str] = mapped_column(String(12), default="")
    new_status: Mapped[str] = mapped_column(String(8), default="")
    source: Mapped[str] = mapped_column(String(12), default="aidx")
    message_id: Mapped[str] = mapped_column(String(64), default="")
    evidence_id: Mapped[str] = mapped_column(String(48), default="")
    replay: Mapped[bool] = mapped_column(Boolean, default=False)


class ZonePresenceRow(Base):
    __tablename__ = "zone_presence"
    id: Mapped[str] = mapped_column(String(56), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(40), ForeignKey("sim_runs.id"))
    zone_id: Mapped[str] = mapped_column(String(24))
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    passenger_count: Mapped[int] = mapped_column(Integer)
    intl_count: Mapped[int] = mapped_column(Integer, default=0)
    dwell_median_min: Mapped[float] = mapped_column(Float, default=0.0)
    segments: Mapped[dict] = mapped_column(JSON, default=dict)
    contributing_flights: Mapped[dict] = mapped_column(JSON, default=dict)
    UniqueConstraint("run_id", "zone_id", "window_start")
    Index("ix_presence_zone_win", "zone_id", "window_start")


class DecisionRow(Base):
    __tablename__ = "decisions"
    id: Mapped[str] = mapped_column(String(48), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(40), ForeignKey("sim_runs.id"), index=True)
    screen_id: Mapped[str] = mapped_column(String(24), index=True)
    slot_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    winner_campaign: Mapped[str] = mapped_column(String(32), default="")
    winner_creative: Mapped[str] = mapped_column(String(32), default="")
    fallback: Mapped[bool] = mapped_column(Boolean, default=False)
    record: Mapped[dict] = mapped_column(JSON)


class CampaignRow(Base):
    __tablename__ = "campaigns"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    data: Mapped[dict] = mapped_column(JSON)
    advertiser_id: Mapped[str] = mapped_column(String(24), default="")
    status: Mapped[str] = mapped_column(String(16), default="APPROVED")


class CreativeRow(Base):
    __tablename__ = "creatives"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    data: Mapped[dict] = mapped_column(JSON)


class PromoCodeRow(Base):
    __tablename__ = "promo_codes"
    id: Mapped[str] = mapped_column(String(48), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(40), default="")
    campaign_id: Mapped[str] = mapped_column(String(32))
    code: Mapped[str] = mapped_column(String(24))
    kind: Mapped[str] = mapped_column(String(12), default="standard")
    window_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    window_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    flight_leg_id: Mapped[str] = mapped_column(String(40), default="")
    family_cap: Mapped[int] = mapped_column(Integer, default=2)
    value: Mapped[float] = mapped_column(Float, default=0.0)
    Index("ix_codes_campaign", "campaign_id")


class PromoTokenRow(Base):
    __tablename__ = "promo_tokens"
    token: Mapped[str] = mapped_column(String(64), primary_key=True)
    promo_code_id: Mapped[str] = mapped_column(String(48), ForeignKey("promo_codes.id"))
    run_id: Mapped[str] = mapped_column(String(40), index=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    redeemed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scanned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    family_index: Mapped[int] = mapped_column(Integer, default=0)
    mode: Mapped[str] = mapped_column(String(20), default="simulated-engagement")
    revenue_value: Mapped[float] = mapped_column(Float, default=0.0)


class ExposureRow(Base):
    """Per-screen per-5-min estimated exposure bucket (one campaign)."""
    __tablename__ = "exposure"
    id: Mapped[str] = mapped_column(String(72), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(40), index=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    screen_id: Mapped[str] = mapped_column(String(24))
    campaign_id: Mapped[str] = mapped_column(String(32), default="")
    kind: Mapped[str] = mapped_column(String(12), default="campaign")  # campaign | house
    est_viewers: Mapped[int] = mapped_column(Integer, default=0)
    Index("ix_exposure_run_at", "run_id", "at")
    Index("ix_exposure_campaign", "campaign_id", "at")


class LearningRow(Base):
    __tablename__ = "learning"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    campaign_id: Mapped[str] = mapped_column(String(32))
    segment: Mapped[str] = mapped_column(String(32))
    exposure_obs: Mapped[int] = mapped_column(Integer, default=0)
    conversions_obs: Mapped[int] = mapped_column(Integer, default=0)
    rate: Mapped[float] = mapped_column(Float, default=0.0)


class IncidentRow(Base):
    __tablename__ = "incidents"
    id: Mapped[str] = mapped_column(String(48), primary_key=True)
    severity: Mapped[str] = mapped_column(String(8))
    title: Mapped[str] = mapped_column(String(120))
    detail: Mapped[str] = mapped_column(Text, default="")
    where: Mapped[str] = mapped_column(String(48), default="")
    status: Mapped[str] = mapped_column(String(10), default="open")
    owner: Mapped[str] = mapped_column(String(40), default="")
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    run_id: Mapped[str] = mapped_column(String(40), default="")
    related: Mapped[str] = mapped_column(String(64), default="")


class FeedHealthRow(Base):
    __tablename__ = "feed_health"
    source: Mapped[str] = mapped_column(String(32), primary_key=True)
    active_adapter: Mapped[str] = mapped_column(String(40))
    healthy: Mapped[bool] = mapped_column(Boolean, default=True)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    messages_last_minute: Mapped[int] = mapped_column(Integer, default=0)
    note: Mapped[str] = mapped_column(Text, default="")


class RuleConfigRow(Base):
    __tablename__ = "rule_config"
    key: Mapped[str] = mapped_column(String(48), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON)


class OutletsRow(Base):
    __tablename__ = "outlets"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    data: Mapped[dict] = mapped_column(JSON)


class ScreensRow(Base):
    __tablename__ = "screens"
    id: Mapped[str] = mapped_column(String(24), primary_key=True)
    data: Mapped[dict] = mapped_column(JSON)


class AdvertisersRow(Base):
    __tablename__ = "advertisers"
    id: Mapped[str] = mapped_column(String(24), primary_key=True)
    data: Mapped[dict] = mapped_column(JSON)


class AirlinesRow(Base):
    __tablename__ = "airlines"
    iata: Mapped[str] = mapped_column(String(3), primary_key=True)
    data: Mapped[dict] = mapped_column(JSON)


class MasterDataRow(Base):
    """Editable platform master data not represented by an upstream feed."""
    __tablename__ = "master_data"
    kind: Mapped[str] = mapped_column(String(24), primary_key=True)
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    data: Mapped[dict] = mapped_column(JSON)


class DestinationsRow(Base):
    __tablename__ = "destinations"
    code: Mapped[str] = mapped_column(String(4), primary_key=True)
    data: Mapped[dict] = mapped_column(JSON)


class HistoryDayRow(Base):
    __tablename__ = "history_days"
    id: Mapped[str] = mapped_column(String(48), primary_key=True)
    day: Mapped[str] = mapped_column(String(10))
    campaign_id: Mapped[str] = mapped_column(String(32))
    impressions: Mapped[int] = mapped_column(Integer, default=0)
    scans: Mapped[int] = mapped_column(Integer, default=0)
    redemptions: Mapped[int] = mapped_column(Integer, default=0)
    spend: Mapped[float] = mapped_column(Float, default=0.0)
    revenue: Mapped[float] = mapped_column(Float, default=0.0)
    is_history: Mapped[bool] = mapped_column(Boolean, default=True)


ALL_TABLES = [SimRun, EvidenceRecord, FlightRow, FlightEventRow, ZonePresenceRow, DecisionRow,
              CampaignRow, CreativeRow, PromoCodeRow, PromoTokenRow, ExposureRow, LearningRow,
              IncidentRow, FeedHealthRow, RuleConfigRow, OutletsRow, ScreensRow, AdvertisersRow,
              AirlinesRow, MasterDataRow, DestinationsRow, HistoryDayRow]
