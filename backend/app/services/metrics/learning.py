"""Engagement learning (AGENTS §10 step 7): aggregate conversion estimation.

Documented update:
    rate(campaign, segment) = (α0 + conversions) / (α0 + β0 + exposures)
    α0 = 2, β0 = 8  (weak prior, mean 0.2 before evidence)

Exposures are the recorded per-slot exposure OPPORTUNITIES of slots whose
creative carried a promo; conversions are recorded scan→redeem events (phone
or simulated-engagement, both labelled by mode). Passengers are never
identified — learning is aggregate only.
"""
from __future__ import annotations

ALPHA0 = 2.0
BETA0 = 8.0


def rate(exposures: int, conversions: int) -> float:
    return round((ALPHA0 + max(0, conversions)) / (ALPHA0 + BETA0 + max(0, exposures)), 4)


async def apply_conversion(dao, campaign_id: str, _unused: float = 0.0) -> None:
    """Called after a redemption records itself against campaign learning."""
    key = f"lrn:{campaign_id}:holiday"
    current = await dao.get_rule("learning")
    rows = current or {}
    row = rows.setdefault(key, {"exposure": 0, "conversions": 0})
    row["conversions"] += 1
    row["rate"] = rate(row["exposure"], row["conversions"])
    await dao.set_rule("learning", rows)
