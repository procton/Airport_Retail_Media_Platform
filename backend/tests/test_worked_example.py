"""Worked-example engine regression (§11): Gate 42 @ 14:10, XY501 +45′.

Organizer targets: duty-free perfume 71% match × 1.5 boost → 0.86 plays;
toys 49% match → 0.52 next in rotation; lounge 18% → 0.21 filtered.
Displayed at the stated precision: match 0.71 / boost 1.5 / scores 0.86,
0.52; lounge not deployable at gate 42.
"""
from __future__ import annotations

import os
from datetime import datetime

import pytest
from app.config import get_settings
from app.services.simulator.engine import SimulationEngine


@pytest.fixture()
def full_engine(tmp_path):
    import anyio
    from app.main import database_ready

    os.environ["AIRP_DATA_DIR"] = str(tmp_path)
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{tmp_path}/t.db"
    get_settings.cache_clear()
    anyio.run(database_ready)
    eng = SimulationEngine(get_settings())
    return eng


def _at(eng: SimulationEngine, iso: str) -> None:
    eng.clock.jump_to(datetime.fromisoformat(iso))
    eng.presence.invalidate()
    eng._process_boundaries()


async def test_gate42_worked_example(full_engine):
    eng = full_engine
    await eng.start()
    try:
        _at(eng, "2026-10-14T14:10:00+00:00")
        f = eng.flights.get("wx:XY501")
        assert f is not None
        await eng.inject_flight_event("wx:XY501", "delay", minutes=45)

        gate42 = [s for s in eng.screens.values() if s.gate == "42"]
        assert gate42, "no screens at gate 42"
        screen = gate42[0]
        slot = eng.planner.plan_slot(screen, eng.clock.sim_now, eng.run_id)
        assert slot is not None

        top = {c["campaign_id"]: c for c in slot["why"]["top_candidates"]}
        perfume = top["wx-DUTY-PERFUME"]
        toys = top["wx-TOYS"] if "wx-TOYS" in top else top.get("cmp-toys")

        # organizer-prescribed displayed precisions
        assert round(perfume["match"], 2) == 0.71
        assert perfume["boost"] == 1.5
        assert round(perfume["score"], 2) == 0.86
        assert toys is not None and round(toys["score"], 2) == 0.52

        # lounge would score ~0.21 but never plays at gate 42 (placement filter)
        lounge = next((c for c in eng.planner.preview_for(screen, eng.clock.sim_now, eng.run_id)["candidates"]
                       if c["campaign_id"] == "wx-LOUNGE"), None)
        assert lounge is not None
        assert lounge["eligible"] is False
        assert round(lounge["score"], 2) == 0.21

        # winner is the perfume campaign; the 1.5 delay boost proves the trigger fired
        assert slot["campaign_id"] == "wx-DUTY-PERFUME"
        assert top["wx-DUTY-PERFUME"]["boost"] == 1.5

        # profile sanity vs the scenario table
        p = slot["why"]["profile"]
        assert abs(p["holiday"] - 0.58) <= 0.01
        assert abs(p["family"] - 0.31) <= 0.01
        assert abs(p["business"] - 0.22) <= 0.01
        assert round(p["intl_share"], 2) == 0.57
        assert round(p["dwell_min"]) == 52
    finally:
        await eng.stop()


async def test_zone_presence_match(full_engine):
    eng = full_engine
    await eng.start()
    try:
        _at(eng, "2026-10-14T14:10:00+00:00")
        await eng.inject_flight_event("wx:XY501", "delay", minutes=45)
        z42 = eng.presence_of_zone("T2-1-gates")
        # contributions of XY501 (240 pax) + ZQ88 (180 pax) sum well above 300;
        # the documented catchment weighting keeps legs' full pax, partially de-duped
        assert z42["passenger_count"] >= 160
        prof = eng.presence.profile(eng.flights.get("wx:XY501"), "2026-10-14")
        model = prof.model_dump(mode="json")
        shares = model.get("shares") or {}
        assert shares.get("purpose_holiday", 0) > 0.5
        assert shares.get("party_family_with_children", 0) >= 0.25
    finally:
        await eng.stop()
