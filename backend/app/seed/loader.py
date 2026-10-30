"""Seed loader: builds/loads deterministic state (AGENTS §7, §22 boot/data).

Composition:
- `full` mode: synthetic 880-leg operating day via generator → AODB adapter
  (same parsing layer as the fixtures; provenance synthetic).
- `reference` mode: the verbatim fixture CSV through the same adapter.
- scenario `gate42`: the organizer worked-example flights welded on after the
  adapter output (labelled worked-example, never presented as CSV-sourced).
- platform master data, 25 campaigns + creatives, promo codes, learning rates,
  30-day synthetic history, all persisted before first run.
"""
from __future__ import annotations

import time
from datetime import UTC, datetime
from pathlib import Path

from ..adapters.acris import build_platform_layout
from ..adapters.aodb import AodbCsvAdapter
from ..config import Settings
from ..domain.canonical import Direction, Flight
from ..persistence.dao import Dao
from ..seed import airport_data, generator
from ..seed.worked_example import scenario_campaigns, scenario_flights, scenario_promos


def _row_to_flight(r: dict) -> Flight:
    def t(s: str | None) -> datetime | None:
        if not s:
            return None
        dt = datetime.fromisoformat(s)
        return dt if dt.tzinfo else dt.replace(tzinfo=UTC)

    return Flight(
        id=f"aodb:{r['aodb_flight_id']}",
        aodb_flight_id=r["aodb_flight_id"],
        linked_flight_id=r["linked"] or None,
        airline_iata=r["airline_iata"],
        airline_icao=r["airline_icao"],
        flight_number=r["number"],
        direction=Direction(r["direction"]),
        flight_nature=r["nature"],
        origin=r["origin"],
        destination=r["destination"],
        terminal=r["terminal"],
        sched_std=t(r["sched_std"]),
        tobt=t(r["tobt"]),
        tsat=t(r["tsat"]),
        etd=t(r["etd"]),
        eldt=t(r.get("eldt")),
        aldt=t(r["aldt"]),
        aibt=t(r.get("aibt")),
        stand=r["stand"] or None,
        gate=r["gate"] or None,
        aircraft_type=r["aircraft_type"] or None,
        aircraft_reg=r.get("aircraft_reg") or None,
        seats=r["seats"],
        pax=r["pax"],
        status_raw=r["status_raw"],
        cancelled=r["cancelled"],
        delay_codes=[c for c in (r.get("delay_codes") or "").split("/") if c],
        handler=r.get("handler") or None,
        source=r.get("source", "aodb"),
    )


async def _seed_all(dao: Dao, s: Settings) -> None:
    run_id = f"run-{int(time.time())}-seed"
    await dao.purge_everything()
    await dao.create_run(run_id, s.seed_seed, s.seed_mode, s.operating_day, s.scenario)

    # ---------------- flights through the real adapter ---------------------
    if s.seed_mode == "reference":
        csv_path = Path(s.aodb_csv)
        adapter = AodbCsvAdapter(csv_path)
        provenance = "reference-fixture"
    else:
        csv_text = generator.generate_day_csv(s.operating_day, pairs=440, seed=s.seed_seed)
        adapter = AodbCsvAdapter(csv_text.encode(), source_label="generated-day")
        provenance = "synthetic-generated"
    legs, assignments = adapter.legs()
    assert not adapter.rejected_rows, f"AODB adapter rejected rows: {adapter.rejected_rows[:5]}"
    flights = list(legs)

    airline_master = generator.AIRLINES
    dest_master = {}
    for code in generator.DOM_DEST + generator.INTL_DEST:
        dest_master[code] = {}
    ads = airport_data.build_advertisers()
    outlets = airport_data.build_outlets()

    screens_tmp = build_platform_layout()
    zones = [z.model_dump(mode="json") for z in screens_tmp[1]]
    screens = airport_data.build_screens(zones, target=180)

    campaigns = list(airport_data.build_campaigns()[0])
    creatives = dict(airport_data.build_campaigns()[1])
    if s.scenario == "gate42":
        wx_campaigns, wx_creatives = scenario_campaigns()
        campaigns.extend(wx_campaigns)
        for cid, cs in wx_creatives.items():
            creatives[cid] = cs

    promos = airport_data.build_promos(campaigns, s.operating_day, s.seed_seed)
    if s.scenario == "gate42":
        promos.extend(scenario_promos())
    for row in promos:
        for k in ("window_start", "window_end"):
            if isinstance(row.get(k), str):
                row[k] = datetime.fromisoformat(row[k])
    history = airport_data.build_history(campaigns, s.operating_day, s.seed_seed)

    await dao.upsert_master(airlines=airline_master, destinations=dest_master,
                            advertisers=ads, outlets=outlets, screens=screens)
    await dao.upsert_campaigns([dict(c, status=c["status"]) for c in campaigns],
                               [cr for cs in creatives.values() for cr in cs])
    await dao.add_promo_codes([dict(row, run_id=run_id) for row in promos])
    await dao.add_history(history)
    flight_rows = []
    evidence = []
    for f in flights:
        flight_rows.append(dict(
            id=f.id, aodb_flight_id=f.aodb_flight_id,
            linked_flight_id=f.linked_flight_id or "",
            direction=f.direction.value, airline_iata=f.airline_iata, airline_icao=f.airline_icao,
            flight_number=f.flight_number, flight_nature=f.flight_nature, origin=f.origin,
            destination=f.destination, terminal=f.terminal, sched_std=f.sched_std,
            tobt=f.tobt, tsat=f.tsat, etd=f.etd, eldt=f.eldt, aldt=f.aldt, aibt=f.aibt,
            stand=f.stand or "",
            gate=f.gate or "", aircraft_type=f.aircraft_type or "", seats=f.seats, pax=f.pax,
            status_raw=f.status_raw, cancelled=f.cancelled,
            delay_codes="/".join(f.delay_codes), handler=f.handler or "",
            evidence_id=f"evid:{f.id}", source=f.source, aircraft_reg=f.aircraft_reg or "",
        ))
        evidence.append(dict(
            id=f"evid:{f.id}", source=f"adapter:aodb:{provenance}",
            source_record_id=f.aodb_flight_id, source_timestamp=None,
            ingestion_timestamp=datetime.now(tz=UTC), adapter="mock-aodb",
            freshness="scheduled", provenance=provenance,
            payload={"sched_std": f.sched_std.isoformat(), "gate": f.gate or "",
                     "status": f.status_raw, "pax": f.pax},
        ))
    await dao.upsert_flights(flight_rows)
    await dao.add_evidence(evidence)
    await dao.set_rule("learning", {})
    await dao.upsert_feed({"source": "aodb", "active_adapter": "mock-aodb", "healthy": True,
                           "last_message_at": None, "messages_last_minute": 0,
                           "note": f"{len(flights)} legs; provenance={provenance}"})


def id_of(f: Flight) -> str:
    return f.aodb_flight_id


async def load_or_seed(dao: Dao, s: Settings) -> dict:
    run_id = await dao.active_run_id()
    if not run_id:
        await _seed_all(dao, s)
        run_id = await dao.active_run_id()
    assert run_id

    master = await dao.load_master()
    flight_rows = await dao.load_flights()
    flights = [_row_to_flight(r) for r in flight_rows]
    campaigns_rows, creative_rows = await dao.load_campaigns()
    campaigns = list(campaigns_rows.values())
    creatives: dict[str, list[dict]] = {}
    for cr in creative_rows.values():
        creatives.setdefault(cr.get("campaign_id", ""), []).append(cr)
    promos_rows = await dao.load_promo_codes(run_id)
    # Existing Docker volumes may predate the Gate-42 worked-example promo
    # seed. Reconcile the scenario-owned promo row on every load so a
    # persisted campaign/creative cannot advertise "Scan to claim" while the
    # planner has no matching promo window and therefore cannot issue a QR
    # token. This is idempotent by the promo primary key.
    if s.scenario == "gate42":
        scenario_rows = scenario_promos()
        existing_ids = {row["id"] for row in promos_rows}
        missing = [row for row in scenario_rows if row["id"] not in existing_ids]
        if missing:
            persisted = []
            for row in missing:
                item = dict(row, run_id=run_id)
                for key in ("window_start", "window_end"):
                    if isinstance(item.get(key), str):
                        item[key] = datetime.fromisoformat(item[key])
                persisted.append(item)
            await dao.add_promo_codes(persisted)
            promos_rows.extend(missing)
    learn = await dao.get_rule("learning") or {}
    learn_rates: dict[str, dict[str, float]] = {}
    for key, row in learn.items():
        cid = key.split(":")[1]
        learn_rates.setdefault(cid, {})[key.split(":")[2]] = float(row.get("rate", 0.05))

    if s.scenario == "gate42" and not any(f.id.startswith("wx:") for f in flights):
        flights.extend(scenario_flights())

    screens: dict[str, dict] = master.get("screens", {})
    outlets = master.get("outlets", {})
    advertisers = master.get("advertisers", {})
    airlines = master.get("airlines", {})
    destinations = master.get("destinations", {})
    master_overrides = await dao.load_master_overrides()
    for row in master_overrides:
        target = row["kind"]
        if target == "airlines":
            airlines[row["id"]] = {**airlines.get(row["id"], {}), **row["data"]}
        elif target == "outlets":
            outlets[row["id"]] = {**outlets.get(row["id"], {}), **row["data"]}
        elif target == "screens":
            screens[row["id"]] = {**screens.get(row["id"], {}), **row["data"]}

    promos_map: dict[str, list[dict]] = {}
    for row in promos_rows:
        promos_map.setdefault(row["campaign_id"], []).append(row)

    return {
        "run_id": run_id, "seed": s.seed_seed, "day": s.operating_day,
        "flights": flights,
        "screens": screens, "outlets": outlets, "advertisers": advertisers,
        "airlines": airlines, "destinations": destinations,
        "campaigns": campaigns, "creatives": creatives,
        "promos": promos_map, "learn_rates": learn_rates,
        "master_overrides": master_overrides,
    }
