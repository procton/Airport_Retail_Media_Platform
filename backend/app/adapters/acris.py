"""ACRIS adapter (platform mock).

The reference `ACRIS-smart-data-models/` directory is ABSENT from the repo
(`playground/README.md` documents it, but the folder was not shipped — see
docs/ASSUMPTIONS_DISCREPANCIES.md, finding D2). Therefore:

* we did NOT invent ACRIS example payloads claiming to be the missing fixtures;
* this adapter consumes representative NGSI-LD ACRIS-shaped messages based on
  the public FIWARE `dataModel.ACRIS` reference. It also retains the original
  flat platform-mock format for compatibility; all such messages are
  explicitly labelled PLATFORM-MOCK;
* canonical outputs remain Terminal / Zone / Checkpoint / QueueMeasurement;
  `Zone` has no direct ACRIS source equivalent (per AGENTS §6.3), so zones are
  a platform-owned spatial projection built from the airport layout. When the
  real fixture directory is available it can be validated against supplied
  schemas without changing this adapter's contract.

Documented shape of an accepted legacy platform-mock checkpoint measurement message:

{
  "type": "PassengerQueue",          # accepted: Terminal | Checkpoint | PassengerQueue
  "AirportDeploymentVersion": 1,
  "CheckpointAreaLocation": {"ZoneId": "T2-CKP-3", "Identifier": "T2", "Name": "T2 North"},
  "CountMeasurementTime": "2026-10-14T09:05:00Z",
  "WaitTime": {"Unit": "Minutes", "Value": 14},
  "PassengerCount": {"Identifier": "security", "Value": 87}
}
"""
from __future__ import annotations

import json
import random
from datetime import datetime
from typing import Any

from ..domain.canonical import Checkpoint, QueueMeasurement, Terminal, Zone, ZoneKind

ACCEPTED_TYPES = (
    "Terminal",
    "TerminalFacility",
    "Checkpoint",
    "CheckpointFacility",
    "PassengerQueue",
    "QueueMeasurement",
)


def _value(entity: dict, *names: str, default: Any = None) -> Any:
    """Read legacy flat or NGSI-LD Property/Relationship attributes."""
    for name in names:
        if name not in entity:
            continue
        value = entity[name]
        if isinstance(value, dict) and value.get("type") in {"Property", "Relationship"}:
            return value.get("object") if value.get("type") == "Relationship" else value.get("value", default)
        return value
    return default


def _location(entity: dict) -> dict:
    location = _value(
        entity,
        "CheckpointAreaLocation",
        "checkpointAreaLocation",
        "QueueLocation",
        "queueLocation",
        "TerminalAreaLocation",
        "terminalAreaLocation",
    )
    if isinstance(location, str):
        return {"ZoneId": location, "identifier": location}
    return location if isinstance(location, dict) else {}


def _location_value(location: dict, *names: str, default: Any = None) -> Any:
    return _value(location, *names, default=default)


def _utc(s: Any) -> datetime:
    return datetime.fromisoformat(str(s).replace("Z", "+00:00"))


class AcrisShapeAdapter:
    """Parses ACRIS-shaped JSON (single object or list) — platform mock."""

    name = "mock-acris"

    def parse_entity(self, payload: bytes | str | dict | list) -> list[dict]:
        """Normalise + type-check; raise ValueError for malformed shapes."""
        if isinstance(payload, (bytes, str)):
            payload = json.loads(payload)
        items = payload if isinstance(payload, list) else [payload]
        accepted: list[dict] = []
        for i, it in enumerate(items):
            if not isinstance(it, dict):
                raise ValueError(f"entity {i}: not an object")
            et = it.get("type")
            if et not in ACCEPTED_TYPES:
                raise ValueError(f"entity {i}: unsupported type {et!r}")
            if et in ("Checkpoint", "CheckpointFacility", "PassengerQueue", "QueueMeasurement") and not _location(it):
                raise ValueError(f"entity {i}: {et} without queue/checkpoint location")
            if et in ("PassengerQueue", "QueueMeasurement"):
                timestamp = _value(it, "CountMeasurementTime", "countMeasurementTime", "measurementTime")
                count = _value(it, "PassengerCount", "passengerCount", "queueCount", "headcount")
                if timestamp is None or count is None:
                    raise ValueError(f"entity {i}: {et} requires measurement time and passenger count")
                if not timestamp:
                    raise ValueError(f"entity {i}: empty measurement time")
            accepted.append(it)
        return accepted

    def canonical_from_entities(
        self, entities: list[dict]
    ) -> tuple[list[Terminal], list[Checkpoint], list[QueueMeasurement]]:
        """Project terminal/checkpoint entities + queue measurements to canonical."""
        terminals: dict[str, Terminal] = {}
        checkpoints: list[Checkpoint] = []
        measures: list[QueueMeasurement] = []
        for it in entities:
            et = it.get("type")
            loc = _location(it)
            ident = str(
                _location_value(loc, "Identifier", "identifier", "ZoneId", "zoneId", "terminalId")
                or _value(it, "terminalId", default="")
                or ""
            )
            if et in ("Terminal", "TerminalFacility"):
                t = terminals.setdefault(ident, Terminal(name=ident or "T?", kind="mixed"))
                k = str(_value(it, "AirportTrafficFlowType", "airportTrafficFlowType", "trafficFlowType", default="")).strip().lower()
                if k == "domestic":
                    t.kind = "domestic"
                elif k == "international":
                    t.kind = "international"
            elif et in ("Checkpoint", "CheckpointFacility"):
                checkpoints.append(
                    Checkpoint(
                        id=str(it.get("id") or ident or f"ckp-{len(checkpoints) + 1}"),
                        terminal=str(_location_value(loc, "Terminal", "terminal", "terminalId", default=ident or "T?")),
                        name=str(_location_value(loc, "Name", "name", default=ident)),
                        feeds_zone=f"{ident}-security" if ident else None,
                    )
                )
            elif et in ("PassengerQueue", "QueueMeasurement"):
                wt = _value(it, "WaitTime", "waitTime", default={}) or {}
                pc = _value(it, "PassengerCount", "passengerCount", "queueCount", "headcount", default={}) or {}
                if not isinstance(wt, dict):
                    wt = {"Value": wt, "value": wt}
                if not isinstance(pc, dict):
                    pc = {"Value": pc, "value": pc}
                timestamp = _value(it, "CountMeasurementTime", "countMeasurementTime", "measurementTime")
                measures.append(
                    QueueMeasurement(
                        checkpoint_id=str(_location_value(loc, "ZoneId", "zoneId", "Identifier", "identifier", default=ident or "ckp")),
                        measured_at=_utc(timestamp),
                        wait_min=float(_value(wt, "Value", "value", default=0.0) or 0.0),
                        headcount_est=int(_value(pc, "Value", "value", default=0) or 0),
                        source=self.name,
                    )
                )
        return list(terminals.values()), checkpoints, measures


class MockAcrisFeed:
    """Deterministic platform-mock queue measurements for the demo day."""

    name = "mock-acris"

    def __init__(self, day: str, seed: int = 1013) -> None:
        self.day = day
        self.seed = seed

    def measurements(self) -> list[QueueMeasurement]:
        import math

        rng = random.Random(self.seed)
        out: list[QueueMeasurement] = []
        for tid in ("T1", "T2"):
            for n in (1, 2, 3):
                cp = f"{tid}-CKP-{n}"
                for h in range(0, 24, 2):
                    wait = round(4 + 12 * rng.random() + 6 * math.sin(h / 3.5) ** 2, 1)
                    head = 20 + int(70 * rng.random())
                    out.append(
                        QueueMeasurement(
                            checkpoint_id=cp,
                            measured_at=datetime.fromisoformat(f"{self.day}T{h:02d}:05:00+00:00"),
                            wait_min=max(2.0, wait),
                            headcount_est=head,
                            source=self.name,
                        )
                    )
        return out


def build_platform_layout() -> tuple[list[Terminal], list[Zone], list[Checkpoint]]:
    """Platform-owned airport layout (fictional MQI labels; see assumptions)."""
    terminals = [Terminal(name="T1", kind="domestic"), Terminal(name="T2", kind="international")]
    zones: list[Zone] = []
    gates_by_concourse: dict[str, list[str]] = {
        "T1-A": [f"A{i}" for i in range(2, 10)],
        "T1-B": ["B1", "B2", "B6", "B8", "B9", "B11"],
        "T1-C": ["C2", "C3", "C4", "C6", "C8", "C10", "C12"],
        "T1-BUS": [f"BUS{u}" for u in range(1, 8)],
        "T2-1": ["41", "42", "43", "44", "45", "46"],
        "T2-5": ["50", "51", "52", "53", "54", "56"],
        "T2-6": ["60", "61", "62", "63", "65", "66"],
        "T2-7": ["67", "68", "69", "72", "73", "74"],
        "T2-8": ["75", "77", "78", "79", "80", "81", "82", "83", "84", "85", "86", "87", "88"],
        "T2-BUS": [f"BUS{u}" for u in range(1, 9)],
    }
    for conc, gates in gates_by_concourse.items():
        tid = conc.split("-")[0]
        zones.append(
            Zone(
                id=f"{conc}-gates",
                terminal=tid,
                name=f"{tid} Concourse {conc.split('-')[1]} gates",
                kind=ZoneKind.GATE,
                concourse=conc,
                gates=gates,
                neighbours={},
            )
        )
    for tid in ("T1", "T2"):
        zones.append(
            Zone(
                id=f"{tid}-retail-main",
                terminal=tid,
                name=f"{tid} Retail corridor",
                kind=ZoneKind.RETAIL,
                concourse=f"{tid}-R",
                neighbours={},
            )
        )
        zones.append(
            Zone(
                id=f"{tid}-security",
                terminal=tid,
                name=f"{tid} Security checkpoints",
                kind=ZoneKind.SECURITY,
                concourse=f"{tid}-S",
                neighbours={},
            )
        )
    checkpoints = [
        Checkpoint(
            id=f"{tid}-CKP-{n}", terminal=tid, name=f"{tid} checkpoint {n}", feeds_zone=f"{tid}-security"
        )
        for tid in ("T1", "T2")
        for n in (1, 2, 3)
    ]
    return terminals, zones, checkpoints


class AcrisVendorStub:
    name = "vendor-acris-push"

    def parse_entity(self, payload):
        raise NotImplementedError(
            "vendor-acris-push requires integration credentials; use mock-acris in this build."
        )
