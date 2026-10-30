"""Repository functions — all short transactions, no shared sessions."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from .database import get_sessionmaker
from .models import (
    AdvertisersRow,
    AirlinesRow,
    CampaignRow,
    CreativeRow,
    DecisionRow,
    DestinationsRow,
    EvidenceRecord,
    ExposureRow,
    FeedHealthRow,
    FlightEventRow,
    FlightRow,
    HistoryDayRow,
    IncidentRow,
    LearningRow,
    MasterDataRow,
    OutletsRow,
    PromoCodeRow,
    PromoTokenRow,
    RuleConfigRow,
    ScreensRow,
    SimRun,
    ZonePresenceRow,
)

_DECISION_COLS = (
    "id", "run_id", "screen_id", "slot_at", "winner_campaign", "winner_creative",
    "fallback", "record",
)


def _d(v: Any) -> dict | None:
    return json.loads(json.dumps(v))


class Dao:
    def __init__(self) -> None:
        self.sm = get_sessionmaker()

    # ------------------------------------------------------------------ runs
    async def create_run(self, run_id: str, seed: int, mode: str, day: str, scenario: str = "") -> None:
        async with self.sm() as s:
            s.add(SimRun(id=run_id, seed=seed, mode=mode, operating_day=day, scenario=scenario))
            await s.commit()

    async def active_run_id(self) -> str | None:
        async with self.sm() as s:
            row = (await s.execute(select(SimRun).order_by(SimRun.created_at.desc()).limit(1))).scalar_one_or_none()
            return row.id if row else None

    async def purge_everything(self) -> None:
        """Delete all persisted state (fresh seed/regenerate)."""
        tables = [
            PromoTokenRow, ExposureRow, DecisionRow, ZonePresenceRow, FlightEventRow, FlightRow,
            EvidenceRecord, LearningRow, IncidentRow, FeedHealthRow, RuleConfigRow, PromoCodeRow,
            CreativeRow, CampaignRow, OutletsRow, ScreensRow, AdvertisersRow, AirlinesRow,
            MasterDataRow,
            DestinationsRow, HistoryDayRow, SimRun,
        ]
        async with self.sm() as s:
            for t in tables:
                await s.execute(delete(t))
            await s.commit()

    async def purge_run(self, run_id: str) -> None:
        tbls = [
            (ExposureRow, ExposureRow.run_id), (DecisionRow, DecisionRow.run_id),
            (ZonePresenceRow, ZonePresenceRow.run_id), (FlightEventRow, FlightEventRow.run_id),
            (FlightRow, FlightRow.id), (EvidenceRecord, EvidenceRecord.id), (IncidentRow, IncidentRow.run_id),
            (PromoTokenRow, PromoTokenRow.run_id), (PromoCodeRow, PromoCodeRow.run_id),
        ]
        async with self.sm() as s:
            for t, col in tbls:
                await s.execute(delete(t).where(col == run_id))
            await s.execute(delete(SimRun).where(SimRun.id == run_id))
            await s.commit()

    # --------------------------------------------------------- master data
    async def upsert_master(self, *, airlines: dict, destinations: dict, advertisers: dict,
                            outlets: dict, screens: dict) -> None:
        async with self.sm() as s:
            for k, v in airlines.items():
                await s.merge(AirlinesRow(iata=k, data=_d(v)))
            for k, v in destinations.items():
                await s.merge(DestinationsRow(code=k, data=_d(v)))
            for k, v in advertisers.items():
                await s.merge(AdvertisersRow(id=k, data=_d(v)))
            for k, v in outlets.items():
                await s.merge(OutletsRow(id=k, data=_d(v)))
            for k, v in screens.items():
                await s.merge(ScreensRow(id=k, data=_d(v)))
            await s.commit()

    async def load_master(self) -> dict:
        async with self.sm() as s:
            out: dict[str, dict] = {}
            for name, row, pk in (
                ("airlines", AirlinesRow, "iata"),
                ("destinations", DestinationsRow, "code"),
                ("advertisers", AdvertisersRow, "id"),
                ("outlets", OutletsRow, "id"),
                ("screens", ScreensRow, "id"),
            ):
                rows = (await s.execute(select(row))).scalars().all()
                out[name] = {getattr(r, pk): r.data for r in rows}
        return out

    async def load_master_overrides(self) -> list[dict]:
        async with self.sm() as s:
            rows = (await s.execute(select(MasterDataRow).order_by(MasterDataRow.kind, MasterDataRow.id))).scalars().all()
            return [{"kind": r.kind, "id": r.id, "data": r.data} for r in rows]

    async def upsert_master_entity(self, kind: str, entity_id: str, data: dict) -> None:
        async with self.sm() as s:
            await s.merge(MasterDataRow(kind=kind, id=entity_id, data=_d(data)))
            await s.commit()

    async def delete_master_entity(self, kind: str, entity_id: str) -> bool:
        async with self.sm() as s:
            row = await s.get(MasterDataRow, {"kind": kind, "id": entity_id})
            if row is None:
                return False
            await s.delete(row)
            await s.commit()
            return True

    async def upsert_campaigns(self, campaigns: list[dict], creatives: list[dict]) -> None:
        async with self.sm() as s:
            for c in campaigns:
                existing = await s.get(CampaignRow, c["id"])
                data = _d({k: v for k, v in c.items() if True})
                if existing:
                    existing.data = data
                else:
                    s.add(CampaignRow(id=c["id"], data=data,
                                      advertiser_id=c.get("advertiser_id", ""),
                                      status=c.get("status", "APPROVED")))
            for cr in creatives:
                existing = await s.get(CreativeRow, cr["id"])
                if existing:
                    existing.data = _d(cr)
                else:
                    s.add(CreativeRow(id=cr["id"], data=_d(cr)))
            await s.commit()

    async def load_campaigns(self) -> tuple[dict[str, dict], dict[str, dict]]:
        async with self.sm() as s:
            cs = {r.id: {**r.data, "status": r.status, "advertiser_id": r.advertiser_id}
                  for r in (await s.execute(select(CampaignRow))).scalars()}
            crs = {r.id: r.data for r in (await s.execute(select(CreativeRow))).scalars()}
        return cs, crs

    async def set_campaign_status(self, campaign_id: str, status: str) -> None:
        async with self.sm() as s:
            row = await s.get(CampaignRow, campaign_id)
            if row:
                row.status = status
                row.data = {**row.data, "status": status}
                await s.commit()

    # ---------------------------------------------------------------- flights
    async def upsert_flights(self, rows: list[dict]) -> None:
        async with self.sm() as s:
            for r in rows:
                await s.merge(FlightRow(**r))
            await s.commit()

    async def load_flights(self) -> list[dict]:
        async with self.sm() as s:
            rows = []
            for r in (await s.execute(select(FlightRow).order_by(FlightRow.sched_std))).scalars():
                rows.append({
                    "aodb_flight_id": r.aodb_flight_id, "linked": r.linked_flight_id,
                    "direction": r.direction, "airline_iata": r.airline_iata,
                    "airline_icao": r.airline_icao, "number": r.flight_number,
                    "nature": r.flight_nature, "origin": r.origin, "destination": r.destination,
                    "terminal": r.terminal, "sched_std": r.sched_std.isoformat(),
                    "tobt": r.tobt.isoformat() if r.tobt else None,
                    "tsat": r.tsat.isoformat() if r.tsat else None,
                    "etd": r.etd.isoformat() if r.etd else None,
                    "eldt": r.eldt.isoformat() if r.eldt else None,
                    "aldt": r.aldt.isoformat() if r.aldt else None,
                    "aibt": r.aibt.isoformat() if r.aibt else None,
                    "stand": r.stand, "gate": r.gate, "aircraft_type": r.aircraft_type,
                    "aircraft_reg": r.aircraft_reg,
                    "seats": r.seats, "pax": r.pax, "status_raw": r.status_raw,
                    "cancelled": r.cancelled, "delay_codes": r.delay_codes,
                    "handler": r.handler, "evidence_id": r.evidence_id, "source": r.source,
                })
        return rows

    # ------------------------------------------------------------------ evidence
    async def add_evidence(self, records: list[dict]) -> None:
        if not records:
            return
        async with self.sm() as s:
            for r in records:
                await s.merge(EvidenceRecord(**r))
            await s.commit()

    # ---------------------------------------------------------- flight events
    async def add_flight_events(self, rows: list[dict]) -> None:
        async with self.sm() as s:
            for r in rows:
                await s.merge(FlightEventRow(**r))
            await s.commit()

    async def load_flight_events(self, run_id: str) -> list[dict]:
        async with self.sm() as s:
            return [dict(
                id=r.id, flight_leg_id=r.flight_leg_id, kind=r.kind, at=r.at.isoformat(),
                delay=r.delay_minutes, gate=r.new_gate, status=r.new_status,
                source=r.source, message_id=r.message_id, evidence_id=r.evidence_id, replay=r.replay,
            ) for r in (await s.execute(
                select(FlightEventRow).where(FlightEventRow.run_id == run_id).order_by(FlightEventRow.at)
            )).scalars()]

    # ---------------------------------------------------------------- presence
    async def upsert_presence(self, rows: list[dict]) -> None:
        async with self.sm() as s:
            for r in rows:
                await s.merge(ZonePresenceRow(**r))
            await s.commit()

    # ---------------------------------------------------------------- decisions
    async def add_decisions(self, rows: list[dict]) -> None:
        if not rows:
            return
        # 60x batch insert: executemany in chunks instead of per-row merge
        # (the tick loop can produce thousands of rows per flush, §21).
        async with self.sm() as s:
            for i in range(0, len(rows), 300):
                chunk = []
                for r in rows[i:i + 300]:
                    row = {k: r.get(k) for k in _DECISION_COLS}
                    if isinstance(row["slot_at"], str):
                        row["slot_at"] = datetime.fromisoformat(row["slot_at"])
                    row["fallback"] = bool(row["fallback"])
                    if not isinstance(row["record"], dict):
                        row["record"] = {}
                    chunk.append(row)
                await s.execute(
                    sqlite_insert(DecisionRow).on_conflict_do_nothing(index_elements=["id"]),
                    chunk,
                )
            await s.commit()

    async def load_decisions(
        self, run_id: str, screen: str | None = None, campaign: str | None = None,
        search: str | None = None, limit: int = 200,
    ) -> list[dict]:
        """Searchable audit: by screen, campaign, substring incl. rejection reasons."""
        async with self.sm() as s:
            q = select(DecisionRow).where(DecisionRow.run_id == run_id).order_by(DecisionRow.slot_at.desc()).limit(limit)
            if screen:
                q = q.where(DecisionRow.screen_id == screen)
            rows = (await s.execute(q)).scalars().all()
            out = []
            for r in rows:
                rec = r.record or {}
                rec["id"] = r.id
                rec["screen_id"] = r.screen_id
                rec["slot_at"] = r.slot_at.isoformat()
                rec["winner_campaign_id"] = r.winner_campaign
                rec["fallback"] = r.fallback
                if campaign and rec.get("winner_campaign_id") != campaign and campaign not in str(rec.get("candidates", "")):
                    continue
                if search and search.lower() not in json.dumps(r.record).lower():
                    continue
                out.append(rec)
            return out

    # ------------------------------------------------------------------- exposure
    async def add_exposure(self, rows: list[dict]) -> None:
        if not rows:
            return
        async with self.sm() as s:
            for r in rows:
                await s.execute(sqlite_insert(ExposureRow).values(r).on_conflict_do_nothing(index_elements=["id"]))
            await s.commit()

    async def exposure_rollup(self, run_id: str, since: datetime | None = None) -> dict:
        """screen-agnostic rollups: totals + per campaign + per hour."""
        async with self.sm() as s:
            q = select(
                ExposureRow.campaign_id,
                func.count(ExposureRow.id),
                func.sum(ExposureRow.est_viewers),
            ).where(ExposureRow.run_id == run_id).group_by(ExposureRow.campaign_id)
            if since:
                q = q.where(ExposureRow.at >= since)
            by_c: dict[str, dict] = {}
            for cid, n, viewers in (await s.execute(q)).all():
                by_c[cid or ""] = {"slots": n, "viewers": int(viewers or 0)}
            return by_c

    # ------------------------------------------------------------------ promos
    async def add_promo_codes(self, rows: list[dict]) -> None:
        async with self.sm() as s:
            for r in rows:
                await s.merge(PromoCodeRow(**r))
            await s.commit()

    async def load_promo_codes(self, run_id: str | None = None) -> list[dict]:
        async with self.sm() as s:
            q = select(PromoCodeRow).order_by(PromoCodeRow.window_start)
            if run_id:
                q = q.where(PromoCodeRow.run_id == run_id)
            return [dict(
                id=r.id, campaign_id=r.campaign_id, code=r.code, kind=r.kind,
                window_start=r.window_start.isoformat() if r.window_start else None,
                window_end=r.window_end.isoformat() if r.window_end else None,
                flight_leg_id=r.flight_leg_id, family_cap=r.family_cap, value=r.value,
            ) for r in (await s.execute(q)).scalars()]

    async def add_token(self, token: dict) -> None:
        async with self.sm() as s:
            await s.merge(PromoTokenRow(**token))
            await s.commit()

    async def get_promo_code(self, code_id: str) -> dict | None:
        async with self.sm() as s:
            r = await s.get(PromoCodeRow, code_id)
            if not r:
                return None
            return dict(
                id=r.id, campaign_id=r.campaign_id, code=r.code, kind=r.kind,
                window_start=r.window_start.isoformat() if r.window_start else None,
                window_end=r.window_end.isoformat() if r.window_end else None,
                family_cap=r.family_cap, value=r.value,
            )

    async def get_token(self, token: str) -> dict | None:
        async with self.sm() as s:
            r = await s.get(PromoTokenRow, token)
            if not r:
                return None
            return dict(
                token=r.token, promo_code_id=r.promo_code_id, run_id=r.run_id,
                issued_at=r.issued_at.isoformat(), expires_at=r.expires_at.isoformat(),
                redeemed_at=r.redeemed_at.isoformat() if r.redeemed_at else None,
                scanned_at=r.scanned_at.isoformat() if r.scanned_at else None,
                family_index=r.family_index, mode=r.mode, revenue_value=r.revenue_value,
            )

    async def scan_token(self, token: str, at: datetime) -> bool:
        async with self.sm() as s:
            r = await s.get(PromoTokenRow, token)
            if not r:
                return False
            r.scanned_at = at
            await s.commit()
            return True

    async def set_family_index(self, token: str, idx: int) -> None:
        async with self.sm() as s:
            r = await s.get(PromoTokenRow, token)
            if r:
                r.family_index = idx
                await s.commit()

    async def void_family_siblings(self, promo_code_id: str, run_id: str, at: datetime, exclude_token: str) -> None:
        """One-time family-bundle redemption: when one member redeems, the
        remaining sibling code is voided (redeemed_at stamped)."""
        from sqlalchemy import select

        async with self.sm() as s:
            rows = (
                await s.execute(
                    select(PromoTokenRow)
                    .where(PromoTokenRow.promo_code_id == promo_code_id)
                    .where(PromoTokenRow.run_id == run_id)
                    .where(PromoTokenRow.redeemed_at.is_(None))
                    .where(PromoTokenRow.token != exclude_token)
                )
            ).scalars().all()
            for r in rows:
                r.redeemed_at = at
            await s.commit()

    async def redeem_token(self, token: str, at: datetime, revenue: float) -> bool:
        """Single redemption update; returns True if this call performed it."""
        async with self.sm() as s:
            r = await s.get(PromoTokenRow, token)
            if not r:
                return False
            if r.redeemed_at is not None:
                return False
            r.redeemed_at = at
            r.revenue_value = revenue
            await s.commit()
            return True

    # ----------------------------------------------------------------- metrics
    async def add_learning(self, rows: list[dict]) -> None:
        async with self.sm() as s:
            for r in rows:
                await s.merge(LearningRow(**r))
            await s.commit()

    async def load_learning(self) -> dict[str, dict]:
        async with self.sm() as s:
            return {r.id: dict(campaign_id=r.campaign_id, segment=r.segment, exposure=r.exposure_obs,
                               conversions=r.conversions_obs, rate=r.rate)
                    for r in (await s.execute(select(LearningRow))).scalars()}

    # ----------------------------------------------------------------- incidents
    async def upsert_incident(self, row: dict) -> None:
        async with self.sm() as s:
            await s.merge(IncidentRow(**row))
            await s.commit()

    async def load_incidents(self, run_id: str) -> list[dict]:
        async with self.sm() as s:
            return [dict(id=r.id, severity=r.severity, title=r.title, detail=r.detail,
                         where=r.where, status=r.status, owner=r.owner,
                         opened_at=r.opened_at.isoformat(),
                         resolved_at=r.resolved_at.isoformat() if r.resolved_at else None)
                    for r in (await s.execute(select(IncidentRow).where(IncidentRow.run_id == run_id)
                                              .order_by(IncidentRow.opened_at.desc()))).scalars()]

    # ------------------------------------------------------------- feeds & rules
    async def upsert_feed(self, row: dict) -> None:
        async with self.sm() as s:
            await s.merge(FeedHealthRow(**row))
            await s.commit()

    async def load_feeds(self) -> list[dict]:
        async with self.sm() as s:
            return [dict(source=r.source, adapter=r.active_adapter, healthy=r.healthy,
                         last=r.last_message_at.isoformat() if r.last_message_at else None,
                         rate=r.messages_last_minute, note=r.note)
                    for r in (await s.execute(select(FeedHealthRow))).scalars()]

    async def set_rule(self, key: str, value: dict) -> None:
        async with self.sm() as s:
            await s.merge(RuleConfigRow(key=key, value=value))
            await s.commit()

    async def get_rule(self, key: str) -> dict | None:
        async with self.sm() as s:
            row = await s.get(RuleConfigRow, key)
            return row.value if row else None

    # ------------------------------------------------------------------ history
    async def add_history(self, rows: list[dict]) -> None:
        async with self.sm() as s:
            for r in rows:
                await s.merge(HistoryDayRow(**r))
            await s.commit()

    async def load_history(self, campaign_id: str | None = None) -> list[dict]:
        async with self.sm() as s:
            q = select(HistoryDayRow).order_by(HistoryDayRow.day)
            if campaign_id:
                q = q.where(HistoryDayRow.campaign_id == campaign_id)
            return [dict(id=r.id, day=r.day, campaign_id=r.campaign_id, impressions=r.impressions,
                         scans=r.scans, redemptions=r.redemptions, spend=r.spend, revenue=r.revenue)
                    for r in (await s.execute(q)).scalars()]
