"""Synthetic operating-day generator.

Produces a 33-column CSV in the EXACT MQI fixture shape (same header, paired
direction-dependent timestamps, `|` codeshares, `/` delay codes) and feeds it
through the AODB CSV adapter — generated payloads never bypass the source
parsing layer (AGENTS §6.4). Deterministic for a given seed; provenance is
labelled synthetic everywhere it surfaces.

Scale: default 880 legs = 440 verified rotation pairs for the operating day,
satisfying the "approximately 900 legs" benchmark while retaining all 11
reference airlines.
"""
from __future__ import annotations

import csv
import io
import random
from datetime import datetime, timedelta

COLUMNS = [
    "aodb_flight_id", "linked_flight_id", "direction", "airline_iata", "airline_icao",
    "flight_number", "callsign", "service_type", "flight_nature", "origin", "destination",
    "via", "terminal", "STA_STD", "ETA_ETD", "ELDT_ETOT", "ALDT_ATOT", "AIBT_AOBT",
    "TOBT", "TSAT", "stand", "gate", "checkin_counters", "baggage_belt", "aircraft_reg",
    "aircraft_type_icao", "seats", "pax_total", "status", "delay_codes", "codeshares",
    "handler", "last_update_utc",
]

AIRLINES: dict[str, dict] = {
    "XD": {"icao": "SKJ", "name": "Skylark Air", "market": "domestic-lcc", "weight": 46},
    "YA": {"icao": "AUQ", "name": "Aurora National Airlines", "market": "domestic-fs", "weight": 15},
    "YN": {"icao": "KSQ", "name": "Kestrel Air", "market": "domestic-lcc", "weight": 10},
    "XU": {"icao": "CWQ", "name": "Coralwing Express", "market": "domestic-lcc", "weight": 9},
    "YF": {"icao": "SVZ", "name": "Sunvale Airlines", "market": "domestic-lcc", "weight": 4},
    "ZO": {"icao": "SLQ", "name": "Solano Airways", "market": "international", "weight": 5},
    "XH": {"icao": "HCZ", "name": "Halcyon Airways", "market": "international", "weight": 3},
    "YG": {"icao": "ACZ", "name": "Alpine Continental Airlines", "market": "international", "weight": 3},
    "XI": {"icao": "CRU", "name": "Crescent Airways", "market": "international", "weight": 2},
    "YU": {"icao": "LPZ", "name": "Lumen Pacific Airlines", "market": "international", "weight": 2},
    "YB": {"icao": "NSZ", "name": "Northstar Atlantic", "market": "international", "weight": 1},
}
DOM_DEST = ["ADN", "BWZ", "CBP", "CPZ", "DMQ", "EHQ", "FHQ", "GRH", "GSZ", "HCX",
            "IVQ", "JFQ", "LMW", "NGV", "OKZ"]
INTL_DEST = ["BVQ", "KST", "NVQ", "PVQ", "SCJ", "SMG", "ZHQ"]
HANDLERS = ["Skylark self-handling", "Meridian Ground Services", "Harbor Aviation Services", "Compass Ground Handling"]
AIRCRAFT = [("A20N", 186), ("A21N", 240), ("B38M", 189), ("AT76", 78), ("B738", 189),
            ("A320", 180), ("A321", 220), ("B739", 215), ("E290", 120), ("DH8D", 86)]
WIDEBODY = [("A359", 283), ("B77W", 396), ("B788", 250), ("B789", 296), ("A388", 489)]
T1_GATES = ([f"A{i}" for i in range(2, 10)] + ["B1", "B2", "B6", "B8", "B9", "B11"]
            + ["C2", "C3", "C4", "C6", "C8", "C10", "C12"] + [f"BUS{u}" for u in range(1, 8)])
T2_GATES = ["41", "42", "43", "44", "45", "46", "50", "51", "52", "53", "54", "56",
            "60", "61", "62", "63", "65", "66", "67", "68", "69", "72", "73", "74",
            "75", "77", "78", "79", "80", "81", "82", "83", "84", "85", "86", "87", "88"]
STANDS = [f"V{n}" for n in range(1, 33)] + [f"R{n}" for n in range(1, 13)]
HOUR_PITCH = [3, 3, 2, 2, 2, 3, 4, 5, 6, 6, 5, 4, 4, 3, 3, 3, 3, 3, 3, 4, 5, 6, 7, 8]


def _fmt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:00Z")


def _pick_airline(rng: random.Random) -> str:
    total = sum(a["weight"] for a in AIRLINES.values())
    pick = rng.uniform(0, total)
    acc = 0
    for code, data in AIRLINES.items():
        acc += data["weight"]
        if pick <= acc:
            return code
    return "XD"


def generate_day_csv(day: str, pairs: int = 440, seed: int = 1013) -> str:
    rng = random.Random(seed)
    rows: list[dict] = []
    base = datetime.fromisoformat(f"{day}T00:00:00+00:00")
    dump = _fmt(base + timedelta(hours=26))
    fid = 200000
    for _ in range(pairs):
        fid += 2
        code = _pick_airline(rng)
        intl = AIRLINES[code]["market"] == "international"
        aircraft, seats = (rng.choice(WIDEBODY) if (intl and rng.random() < 0.65) else rng.choice(AIRCRAFT))
        dest = rng.choice(INTL_DEST if intl else DOM_DEST)
        hour = rng.choices(range(24), weights=HOUR_PITCH, k=1)[0]
        dep_time = base + timedelta(hours=hour, minutes=rng.randrange(0, 58, 3))
        block = rng.randint(50, 185)
        arr_time = dep_time + timedelta(hours=21 + block / 60)  # rotation wrap: last evening in
        if arr_time > base + timedelta(hours=24):
            arr_time -= timedelta(hours=24)
        number = rng.randrange(100, 9699)
        callsign = f"{AIRLINES[code]['icao']}{number}"
        gate = rng.choice(T2_GATES if intl else T1_GATES)
        stand = rng.choice(STANDS)
        reg = f"Q{rng.choice('ABCDEFGHJKLMNPQRSTUVWXYZ')}-{rng.choice('ABCDEFGHJK')}{rng.randrange(10, 99)}"
        pax = int(seats * rng.uniform(0.72, 0.98))
        roll = rng.random()
        cancelled = roll < 0.02
        dep_delay = rng.choice([10, 15, 20, 25, 30, 40, 45, 60, 75]) if (not cancelled and roll > 0.86) else 0
        arr_delay = rng.choice([10, 15, 20, 25, 30]) if (not cancelled and roll > 0.9) else 0
        codeshares = ""
        if rng.random() < 0.18:
            codeshares = "|".join(rng.choice([("XD", "XH"), ("XH", "YB"), ("YA", "YG")]))
        belt = str(rng.choice(range(1, 15))) if intl else ""
        counters = (f"T{'2' if intl else '1'}-{rng.choice('ABC')}{rng.randrange(10, 30):02d}-"
                    f"{rng.randrange(30, 56):02d}") if not cancelled else ""
        status = "CNL" if cancelled else "DEP"
        dep_row = dict(
            aodb_flight_id=str(fid), linked_flight_id=str(fid + 1), direction="D",
            airline_iata=code, airline_icao=AIRLINES[code]["icao"], flight_number=str(number),
            callsign=callsign, service_type="J", flight_nature="I" if intl else "D",
            origin="MQI", destination=dest, via="", terminal="T2" if intl else "T1",
            STA_STD=_fmt(dep_time + timedelta(minutes=dep_delay)),
            ETA_ETD=_fmt(dep_time + timedelta(minutes=dep_delay)),
            ELDT_ETOT=_fmt(dep_time + timedelta(minutes=dep_delay - 8) if dep_delay >= 8 else dep_time),
            ALDT_ATOT=_fmt(dep_time + timedelta(minutes=dep_delay + 3)),
            AIBT_AOBT=_fmt(dep_time + timedelta(minutes=dep_delay)),
            TOBT=_fmt(dep_time + timedelta(minutes=dep_delay - 2)),
            TSAT=_fmt(dep_time + timedelta(minutes=dep_delay)),
            stand=stand, gate="" if cancelled else gate,
            checkin_counters=counters, baggage_belt="",
            aircraft_reg=reg, aircraft_type_icao=aircraft, seats=seats,
            pax_total=0 if cancelled else pax, status=status,
            delay_codes=(rng.choice(["41", "81", "89", "93", "63/11"]) if dep_delay else ""),
            codeshares=codeshares, handler=rng.choice(HANDLERS), last_update_utc=dump,
        )
        status = "CNL" if cancelled else "ARR"
        arr_row = dict(
            aodb_flight_id=str(fid + 1), linked_flight_id=str(fid), direction="A",
            airline_iata=code, airline_icao=AIRLINES[code]["icao"], flight_number=str(number),
            callsign=callsign, service_type="J", flight_nature="I" if intl else "D",
            origin=dest, destination="MQI", via="", terminal="T2" if intl else "T1",
            STA_STD=_fmt(arr_time), ETA_ETD=_fmt(arr_time + timedelta(minutes=arr_delay)),
            ELDT_ETOT=_fmt(arr_time + timedelta(minutes=max(0, arr_delay - 8))),
            ALDT_ATOT=_fmt(arr_time + timedelta(minutes=arr_delay)),
            AIBT_AOBT=_fmt(arr_time + timedelta(minutes=arr_delay)),
            TOBT="", TSAT="", stand=stand, gate="",
            checkin_counters="", baggage_belt=belt,
            aircraft_reg=reg, aircraft_type_icao=aircraft, seats=seats,
            pax_total=0 if cancelled else pax, status=status,
            delay_codes="", codeshares=codeshares,
            handler=dep_row["handler"], last_update_utc=dump,
        )
        rows.append(dep_row)
        rows.append(arr_row)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=COLUMNS)
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()
