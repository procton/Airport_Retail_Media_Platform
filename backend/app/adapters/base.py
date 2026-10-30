"""Adapter contracts. Sources communicate ONLY canonical entities.

Each source has: a protocol, a working mock implementation (deterministic,
offline) and a live/vendor stub that clearly reports being unconfigured.
Selection is configuration-driven (`Settings.flight_source` etc.).
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from ..domain.canonical import Flight, FlightEvent, GateAssignment, QueueMeasurement


@runtime_checkable
class FlightSource(Protocol):
    """AODB-shaped bulk flight legs (csv today; vendor API tomorrow)."""

    name: str

    def legs(self) -> tuple[Sequence[Flight], Sequence[GateAssignment]]:
        """Return canonical flight legs + gate assignments (all rows accounted)."""
        ...

    def rejected(self) -> list[str]:
        ...


@runtime_checkable
class FlightEventSource(Protocol):
    """AIDX-shaped amendments (XML notifications today)."""

    name: str

    def parse_notification(self, xml: bytes) -> list[FlightEvent]:
        ...

    def mock_amendments(self) -> list[FlightEvent]:
        ...


@runtime_checkable
class QueueSource(Protocol):
    """ACRIS-shaped checkpoint measurements."""

    name: str

    def measurements(self) -> list[QueueMeasurement]:
        ...
