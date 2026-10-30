"""AIDX adapter.

The repo ships one *illustrative* FlightLegNotifRQ (XH960 arrival, row 100180).
This adapter parses that shape into canonical FlightEvents. No XSD is shipped
in the repo, therefore formal IATA conformance is NOT claimed anywhere
(docs/ASSUMPTIONS_DISCREPANCIES.md); structural parsing and canonical mapping
are unit-tested instead.

Generated update messages are built in the same inspected structure and are
always labelled simulated (XML comment + `source="aidx"` with SIM- message ids).
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from lxml import etree

from ..domain.canonical import FlightEvent

NS = {"a": "http://www.iata.org/IATA/2007/00"}


def _utc(s: str | None) -> datetime | None:
    return datetime.fromisoformat(s.replace("Z", "+00:00")) if s else None


class AidxXmlAdapter:
    name = "mock-aidx"

    # ------------------------------------------------------------------ parse
    def parse_notification(self, xml: bytes | str) -> list[FlightEvent]:
        root = etree.fromstring(xml if isinstance(xml, bytes) else xml.encode())
        leg = root.find("a:FlightLeg", NS)
        if leg is None:
            raise ValueError("no FlightLeg element")
        ident = leg.find("a:LegIdentifier", NS)
        data = leg.find("a:LegData", NS)
        if ident is None or data is None:
            raise ValueError("missing LegIdentifier/LegData")
        airline = (ident.findtext("a:Airline", namespaces=NS) or "").strip()
        number = (ident.findtext("a:FlightNumber", namespaces=NS) or "").strip()
        dep = (ident.findtext("a:DepartureAirport", namespaces=NS) or "").strip()
        arr = (ident.findtext("a:ArrivalAirport", namespaces=NS) or "").strip()
        origin_date = (ident.findtext("a:OriginDate", namespaces=NS) or "").strip()
        msg_id = root.get("TransactionIdentifier", "SIM-unknown")
        msg_ts = _utc(root.get("TimeStamp"))

        def leg_ref() -> str:
            return f"{airline}{number}@{origin_date}:{dep}-{arr}"

        events: list[FlightEvent] = []

        def add(kind: str, **kw: Any) -> None:
            events.append(
                FlightEvent(
                    id=f"aidx:{msg_id}:{kind}",
                    flight_leg_id=leg_ref(),
                    kind=kind,
                    at=msg_ts or datetime.now(tz=UTC),
                    source="aidx",
                    message_id=msg_id,
                    timestamp_source=msg_ts,
                    **kw,
                )
            )

        data_status = (data.findtext("a:PublicStatus", namespaces=NS) or "").strip()
        if data_status:
            add("status_change", new_status=data_status)

        ops = data.findall("a:OperationTime", NS)
        scheduled: dict[str, datetime] = {}
        actual: dict[str, datetime] = {}
        for op in ops:
            q = op.get("OperationQualifier", "")
            t = _utc(op.text or "")
            if t is None:
                continue
            if (op.get("TimeType") or "ACT") == "SCT":
                scheduled[q] = t
            else:
                actual[q] = t
        leg_kind = "ONB" if arr == "MQI" else "OFB"
        if leg_kind in scheduled and leg_kind in actual:
            delta = int((actual[leg_kind] - scheduled[leg_kind]).total_seconds() // 60)
            if abs(delta) >= 5:
                add("delay", delay_minutes=delta)

        res = data.find("a:AirportResources", NS)
        if res is not None:
            resource = res.find("a:Resource[@Usage='Actual']", NS)
            if resource is not None:
                gate = resource.findtext("a:AircraftParkingPosition", namespaces=NS)
                if gate:
                    add("gate_change", new_gate=gate)
        return events

    # ----------------------------------------------------------- mock stream
    def mock_amendments(self) -> list[FlightEvent]:
        """Deterministic demo stream — empty by default: amendments are
        triggered via the operator controls / demo scenario, each one
        re-issued through parse_notification(generate_notification(...))."""
        return []

    # ------------------------------------------------------- generate message
    def generate_notification(
        self,
        airline: str,
        number: str,
        origin_date: str,
        dep: str,
        arr: str,
        *,
        new_status: str | None = None,
        gate: str | None = None,
        delay_min: int | None = None,
        scheduled_ops: dict[str, datetime] | None = None,
        actual_ops: dict[str, datetime] | None = None,
        msg_ts: datetime | None = None,
        transaction_id: str | None = None,
    ) -> str:
        """Build an AIDX-shaped update message from the inspected structure."""
        ts = (msg_ts or datetime.now(tz=UTC)).strftime("%Y-%m-%dT%H:%M:%SZ")
        tid = transaction_id or f"SIM-{airline}{number}-{delay_min or 0}-{gate or new_status or 'upd'}"
        op_lines: list[str] = []

        def op_line(q: str, t: datetime, kind: str) -> str:
            return (
                f'    <OperationTime OperationQualifier="{q}" CodeContext="9750" '
                f'TimeType="{kind}">{t.strftime("%Y-%m-%dT%H:%M:%SZ")}</OperationTime>'
            )

        for q, t in (scheduled_ops or {}).items():
            op_lines.append(op_line(q, t, "SCT"))
        if delay_min:
            ops_q = "ONB" if arr == "MQI" else "OFB"
            base = scheduled_ops.get(ops_q) if scheduled_ops else None
            if base:
                op_lines.append(op_line(ops_q, base + timedelta(minutes=delay_min), "ACT"))
        for q, t in (actual_ops or {}).items():
            op_lines.append(op_line(q, t, "ACT"))
        lines = "\n".join(op_lines)
        resource = ""
        if gate:
            resource = (
                f'    <AirportResources Usage="Actual">\n'
                f"      <Resource Usage=\"Actual\" DepartureOrArrival=\"{'Arrival' if arr == 'MQI' else 'Departure'}\">\n"
                f"        <AircraftParkingPosition>{gate}</AircraftParkingPosition>\n"
                f"      </Resource>\n"
                f"    </AirportResources>"
            )
        status_block = f"    <PublicStatus>{new_status}</PublicStatus>" if new_status else ""
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<!-- SIMULATED: generated by the platform AIDX mock adapter; not a live feed. -->
<IATA_AIDX_FlightLegNotifRQ xmlns="http://www.iata.org/IATA/2007/00"
    Version="16.1" Target="Test" TimeStamp="{ts}"
    TransactionIdentifier="{tid}">
  <Originator CompanyShortName="MQI" TravelSector="5" Code="MQI" CodeContext="3"/>
  <DeliveringSystem CompanyShortName="Simulation"/>
  <FlightLeg>
    <LegIdentifier>
      <Airline CodeContext="3">{airline}</Airline>
      <FlightNumber>{number}</FlightNumber>
      <DepartureAirport CodeContext="3">{dep}</DepartureAirport>
      <ArrivalAirport CodeContext="3">{arr}</ArrivalAirport>
      <OriginDate>{origin_date}</OriginDate>
    </LegIdentifier>
    <LegData>
{status_block}
{resource}
{lines}
    </LegData>
  </FlightLeg>
</IATA_AIDX_FlightLegNotifRQ>"""


class AidxVendorStub:
    name = "vendor-aidx-push"

    def parse_notification(self, xml: bytes | str) -> list[FlightEvent]:
        raise NotImplementedError(
            "vendor-aidx-push requires credentials/host config; use mock-aidx in this build."
        )

    def mock_amendments(self) -> list[FlightEvent]:
        return []
