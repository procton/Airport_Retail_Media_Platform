"""Attach role services to a running engine (single place to wire)."""
from __future__ import annotations


def attach(engine) -> None:
    from .promotions.claims import ClaimsService  # local import, no cycle

    engine.claims = ClaimsService(engine)
