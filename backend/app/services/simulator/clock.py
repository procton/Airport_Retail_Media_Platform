"""Simulation clock. One clock per process; all clients share its state.

- wall time is used only for transport/process latency;
- simulation time advances from `operating_day 00:00 UTC` shifted by
  `-sim_start_offset_min` and follows play/pause/speed controls;
- while paused the clock does not move; injections stamp current sim time.
"""
from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta


class SimClock:
    def __init__(self, day: str, start_offset_min: int = 0, speed: int = 1) -> None:
        self.day = day
        self._origin = datetime.fromisoformat(f"{day}T00:00:00+00:00") + timedelta(minutes=start_offset_min)
        self.sim_now: datetime = self._origin
        self.speed = speed
        self.playing = True  # demo-first default: the clock runs on boot
        self._last_wall = time.monotonic()

    def reset(self, offset_min: int | None = None) -> None:
        if offset_min is not None:
            self.sim_now = datetime.fromisoformat(f"{self.day}T00:00:00+00:00") + timedelta(minutes=offset_min)

    # ------------------------------------------------------------ dynamics
    def tick_wall(self, now: float | None = None) -> timedelta:
        """Advance sim clock per elapsed real time while playing (no-op when paused)."""
        now = time.monotonic() if now is None else now
        elapsed_wall = max(0.0, min(now - self._last_wall, 1.0))
        self._last_wall = now
        if not self.playing:
            return timedelta(0)
        return self.advance(elapsed_wall * self.speed)

    def advance(self, seconds: float) -> timedelta:
        if seconds <= 0:
            return timedelta(0)
        self.sim_now = self.sim_now + timedelta(seconds=seconds)
        return timedelta(seconds=seconds)

    def jump_to(self, target: datetime) -> None:
        assert target.tzinfo is not None
        self.sim_now = target

    @property
    def sim_elapsed(self) -> int:
        """Whole simulated seconds since origin."""
        return int((self.sim_now - self._origin).total_seconds())

    def iso(self) -> str:
        return self.sim_now.isoformat()


def utc_wall_now() -> datetime:
    return datetime.now(tz=UTC)
