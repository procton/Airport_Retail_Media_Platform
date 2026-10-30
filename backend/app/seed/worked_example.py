"""The organizer's Gate-42 worked example (AGENTS §11).

Reference values (organizer, fixed):
    Gate 42 @ 14:10 — XY501 → DXB, 240 pax, delayed 45 min;
                       ZQ88 → beach destination, 180 pax.
    Profile: holiday 58%, family 31%, business 22%, international 57%,
             median dwell 52 min.
    Campaign result table: perfume (71% match × 1.5 boost → 0.86, plays);
                           toys (49% × 1.0 → 0.52, next in rotation);
                           lounge pass (18% × 1.0 → 0.21, filtered to other gates).

XY501/ZQ88/DXB are NOT the MQI fixture universe — kept in this dedicated
scenario module with its own id prefix `wx:`, engine regression test
`worked_example` in `backend/tests`, and UI panel clearly labelled
"Organizer worked example" (never presented as CSV-sourced).
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from ..domain.canonical import Direction, Flight

DAY = "2026-10-14"


def scenario_flights() -> list[Flight]:
    t = lambda mins: datetime(2026, 10, 14, 0, 0, tzinfo=UTC) + timedelta(minutes=mins)  # noqa: E731
    x501 = Flight(
        id="wx:XY501", source="worked-example", aodb_flight_id="wx501",
        airline_iata="XY", airline_icao="XYC", flight_number="501",
        direction=Direction("D"), flight_nature="I", origin="MQI", destination="DXB",
        terminal="T2", sched_std=t(14 * 60 + 55), etd=t(14 * 60 + 55),
        tobt=t(14 * 60 + 53), tsat=t(14 * 60 + 55), gate="42", stand="V26",
        checkin_counters="T2-B11-36", aircraft_type="B77W", aircraft_reg="QX-BD",
        seats=300, pax=240, status_raw="", handler="Meridian Ground Services",
        codeshares=["YB"],
    )
    zq88 = Flight(
        id="wx:ZQ88", source="worked-example", aodb_flight_id="wx88",
        airline_iata="ZQ", airline_icao="ZQC", flight_number="88",
        direction=Direction("D"), flight_nature="I", origin="MQI", destination="SMG",
        terminal="T2", sched_std=t(15 * 60 + 5), etd=t(15 * 60 + 5),
        tobt=t(15 * 60 + 3), tsat=t(15 * 60 + 5), gate="43", stand="V27",
        checkin_counters="T2-B48-71", aircraft_type="A20N", aircraft_reg="QZ-FS",
        seats=186, pax=173, status_raw="", handler="Harbor Aviation Services",
        codeshares=["YU"],
    )
    return [x501, zq88]


def scenario_campaigns() -> tuple[list[dict], dict[str, list[dict]]]:
    campaigns = [
        dict(
            id="wx-DUTY-PERFUME", advertiser_id="wx-adv-aromatics", outlet_id="out-t2-df-perfume",
            name="Duty-free perfume 15% off (workshop example)",
            status="APPROVED", domestic="I", min_intl_share=0.0,
            target_segments={"holiday": 0.25, "international": 0.25, "adult25_54": 0.25, "dwell": 0.25},
            hard_dwell_min=40, min_crowd=0, zone_ids=["T2-1-gates"], terminal=None,
            hours_start=13, hours_end=16, budget_total=4000.0, daily_cap=1200.0,
            frequency_cap_per_screen_hour=6, pacing_rate=0.9, dwell_floor_min=53.0,
            trigger="delay", trigger_delay_min=30, trigger_boost=1.5,
            festival_day_boost=1.0, airline_iata=None, airline_priority=False,
            cpm=1.5,
        ),
        dict(
            id="wx-TOYS", advertiser_id="wx-adv-sprockets", outlet_id="out-t2-toys",
            name="Toy store buy-2-get-1 (workshop example)",
            status="APPROVED", domestic="any", min_intl_share=0.0,
            target_segments={"family": 0.34, "children": 0.33, "dwell": 0.33},
            hard_dwell_min=40, min_crowd=40, zone_ids=["T2-1-gates", "T2-5-gates"], terminal=None,
            hours_start=13, hours_end=16, budget_total=4000.0, daily_cap=1200.0,
            frequency_cap_per_screen_hour=6, pacing_rate=0.9, dwell_floor_min=54.0,
            trigger="none", trigger_delay_min=30, trigger_boost=1.0,
            festival_day_boost=1.0, airline_iata=None, airline_priority=False,
            cpm=1.2,
        ),
        dict(
            id="wx-LOUNGE", advertiser_id="wx-adv-lounge", outlet_id="out-t2-lounge",
            name="Business lounge day pass (workshop example)",
            status="APPROVED", domestic="I", min_intl_share=0.3,
            target_segments={"business": 0.5, "premium": 0.5},
            hard_dwell_min=0, min_crowd=0, zone_ids=["T2-8-gates"], terminal=None,
            hours_start=5, hours_end=22, budget_total=4000.0, daily_cap=1200.0,
            frequency_cap_per_screen_hour=6, pacing_rate=0.9, dwell_floor_min=60.0,
            trigger="none", trigger_delay_min=30, trigger_boost=1.0,
            festival_day_boost=1.0, airline_iata=None, airline_priority=False,
            cpm=1.0,
        ),
    ]
    creatives = {
        "wx-DUTY-PERFUME": [dict(
            id="wx-cre-perfume-a", campaign_id="wx-DUTY-PERFUME", variant="a",
            headline_en="Duty-free perfume — 15% off while delayed",
            headline_alt="Perfumería duty-free — 15% mientras esperas",
            body_en="International holiday travellers, sample the exclusive scent set before boarding.",
            body_alt="Viajeros internacionales: prueba el set exclusivo antes de embarcar.",
            cta="Scan to claim", bg="#9d174d", fg="#ffffff", image="motif-arc", show_code=True,
        )],
        "wx-TOYS": [dict(
            id="wx-cre-toys-a", campaign_id="wx-TOYS", variant="a",
            headline_en="Buy 2 toys, get 1 free — kids await your return",
            headline_alt="Compra 2 juguetes, lleva 3",
            body_en="Family favourite near gate 42 — claim the bundle for the little ones.",
            body_alt="El favorito de la familia junto a la puerta 42.", cta="Scan to claim",
            bg="#5b21b6", fg="#ffffff", image="motif-toys", show_code=True,
        )],
        "wx-LOUNGE": [dict(
            id="wx-cre-lounge", campaign_id="wx-LOUNGE", variant="a",
            headline_en="Business lounge day pass",
            headline_alt="Pase de sala de negocios", body_en="Premium cabin passengers — day pass, showers and suites.",
            body_alt="Pasajeros premium: pase, duchas y suites.", cta="See lounge desk",
            bg="#155e75", fg="#ffffff", image="motif-lounge", show_code=False,
        )],
    }
    return campaigns, creatives


def scenario_promos() -> list[dict]:
    """Expiry tied to the delayed flight's boarding close (15% off perfume)."""
    from datetime import datetime
    exp = datetime(2026, 10, 14, 15, 40, tzinfo=UTC)
    return [
        dict(
            id="pc:wx-DUTY-PERFUME:0:std", campaign_id="wx-DUTY-PERFUME",
            code="WX-PERFUME15", kind="standard",
            window_start=datetime(2026, 10, 14, 13, 0, tzinfo=UTC).isoformat(),
            window_end=exp.isoformat(),
            flight_leg_id="wx:XY501", family_cap=2, value=15.0,
        ),
    ]
