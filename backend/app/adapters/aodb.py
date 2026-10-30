"""AODB adapter: parses the MQI synthetic CSV (33 columns) into canonical legs.

Verified fixture behaviour (docs/ASSUMPTIONS_DISCREPANCIES.md):
- 320 rows, 160 reciprocal linked A/D pairs, 157 ARR / 157 DEP / 6 CNL.
- Times ISO-8601 UTC with `Z`; paired columns direction-dependent.
- Gates populated for all departures; 125/160 arrivals lack a gate (35 populated
  arrival gates always equal the linked departure gate).
- last_update_utc identical on all rows (snapshot dump time, NOT per-record freshness).
"""
from __future__ import annotations

import csv
from datetime import datetime, timedelta
from io import StringIO
from pathlib import Path

from ..domain.canonical import Direction, Flight, GateAssignment

_COLUMNS = [
    "aodb_flight_id", "linked_flight_id", "direction", "airline_iata", "airline_icao",
    "flight_number", "callsign", "service_type", "flight_nature", "origin", "destination",
    "via", "terminal", "STA_STD", "ETA_ETD", "ELDT_ETOT", "ALDT_ATOT", "AIBT_AOBT",
    "TOBT", "TSAT", "stand", "gate", "checkin_counters", "baggage_belt", "aircraft_reg",
    "aircraft_type_icao", "seats", "pax_total", "status", "delay_codes", "codeshares",
    "handler", "last_update_utc",
]


def parse_time(s: str | None) -> datetime | None:
    if not s:
        return None
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def parse_list(s: str | None, sep: str) -> list[str]:
    return [x for x in (s or "").split(sep) if x]


class AodbCsvAdapter:
    name = "mock-aodb"

    def __init__(self, csv_path: str | Path | bytes, source_label: str = "MQI_aodb") -> None:
        if isinstance(csv_path, (str, Path)):
            text = Path(csv_path).read_text(encoding="utf-8")
            self.source_label = Path(csv_path).name
        else:
            text = csv_path.decode("utf-8")
            self.source_label = source_label
        self.rows, self.rejected_rows = self._parse(text)
        self._legs: list[Flight] = []
        self._assignments: list[GateAssignment] = []

    # ------------------------------------------------------------------ parse
    def _parse(self, text: str) -> tuple[list[dict], list[str]]:
        reader = csv.DictReader(StringIO(text))
        rejected: list[str] = []
        rows: list[dict] = []
        header = list(reader.fieldnames or [])
        if header != _COLUMNS:
            missing = set(_COLUMNS) - set(header)
            extra = set(header) - set(_COLUMNS)
            raise ValueError(
                f"AODB header mismatch: missing={sorted(missing)} unexpected={sorted(extra)}"
            )
        for i, row in enumerate(reader, start=1):
            try:
                row = {k: (v or "").strip() for k, v in row.items()}
                if len({k for k in _COLUMNS}) != 33:
                    raise ValueError("column count")
                direction = row["direction"]
                if direction not in ("A", "D"):
                    raise ValueError(f"direction={direction!r}")
                if row["flight_nature"] not in ("D", "I"):
                    raise ValueError(f"flight_nature={row['flight_nature']!r}")
                sta = parse_time(row["STA_STD"])
                if sta is None:
                    raise ValueError("missing STA_STD")
                for col in ("ETA_ETD", "ELDT_ETOT", "ALDT_ATOT", "AIBT_AOBT", "TOBT", "TSAT"):
                    parse_time(row[col])  # raises if malformed
                seats = int(row["seats"]) if row["seats"] else 0
                pax = int(row["pax_total"]) if row["pax_total"] else 0
                if seats and pax > seats:
                    raise ValueError("pax_total>seats")
                status = row["status"]
                if status not in ("ARR", "DEP", "CNL"):
                    raise ValueError(f"status={status!r}")
                rows.append(row)
            except Exception as exc:  # collect per-row; tests assert count/reasons
                rejected.append(f"row {i} (aodb_flight_id={row.get('aodb_flight_id', '?')}): {exc}")
        return rows, rejected

    # ------------------------------------------------------------- canonical
    def legs(self) -> tuple[list[Flight], list[GateAssignment]]:
        if self._legs:
            return self._legs, self._assignments
        out: list[Flight] = []
        assgns: list[GateAssignment] = []
        id_set = {r["aodb_flight_id"] for r in self.rows}
        for r in self.rows:
            cancelled = r["status"] == "CNL"
            arrival = r["direction"] == "A"
            leg = Flight(
                id=f"aodb:{r['aodb_flight_id']}",
                aodb_flight_id=r["aodb_flight_id"],
                linked_flight_id=r["linked_flight_id"] if r["linked_flight_id"] in id_set else None,
                airline_iata=r["airline_iata"],
                airline_icao=r["airline_icao"],
                flight_number=r["flight_number"],
                direction=Direction(r["direction"]),
                service_type=r["service_type"] or "J",
                flight_nature=r["flight_nature"],
                origin=r["origin"],
                destination=r["destination"],
                terminal=r["terminal"],
                sched_std=parse_time(r["STA_STD"]),
                etd=parse_time(r["ETA_ETD"]),
                eldt=parse_time(r["ELDT_ETOT"]),
                aldt=parse_time(r["ALDT_ATOT"]),
                aibt=parse_time(r["AIBT_AOBT"]),
                tobt=parse_time(r["TOBT"]),
                tsat=parse_time(r["TSAT"]),
                stand=r["stand"] or None,
                gate=(r["gate"] or None),
                checkin_counters=r["checkin_counters"] or None,
                baggage_belt=r["baggage_belt"] or None,
                aircraft_reg=r["aircraft_reg"] or None,
                aircraft_type=r["aircraft_type_icao"] or None,
                seats=int(r["seats"]) if r["seats"] else 0,
                pax=int(r["pax_total"]) if r["pax_total"] else 0,
                status_raw=r["status"],
                delay_codes=parse_list(r.get("delay_codes"), "/"),
                codeshares=parse_list(r.get("codeshares"), "|"),
                handler=r["handler"] or None,
                last_update_utc=r["last_update_utc"] or None,
                cancelled=cancelled,
            )
            out.append(leg)
            if r["gate"]:
                if arrival:
                    a_start = (leg.aldt or leg.etd or leg.sched_std) - timedelta(minutes=45)
                    a_end = None
                else:
                    a_start = leg.boarding_start()
                    a_end = leg.effective_std() + timedelta(minutes=10)
                assgns.append(
                    GateAssignment(
                        flight_leg_id=leg.id,
                        gate=r["gate"],
                        terminal=leg.terminal,
                        kind="gate",
                        valid_from=a_start,
                        valid_to=a_end,
                        source=self.name,
                    )
                )
        self._legs, self._assignments = out, assgns
        return out, assgns


# ---------------------------------------------------------------- live stub
class AodbVendorStub:
    """Vendor API stub — clearly reports unconfigured integration."""

    name = "vendor-aodb-http"

    def legs(self):
        raise NotImplementedError(
            "vendor-aodb-http not configured for this build; flights come from the AODB mock adapter."
        )

    def rejected(self) -> list[str]:
        return []
