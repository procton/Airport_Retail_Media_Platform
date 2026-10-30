"""Scoring functions and worked-example calibration.

The organizer's worked example (AGENTS §11) fixes three *displayed* outcomes:
match 71%/49%/18%, boosts 1.5/1.0/1.0 and finals 0.86/0.52/0.21 with
"plays / next-in-rotation / filtered-to-other-gates". Simple match × boost does
not reproduce them (0.71×1.5 ≠ 0.86). We therefore use a documented three-part
formulation and CALIBRATED constants (assumption A5, derivation below):

    AUDIENCE_MATCH = Σ_c (weight_c × satisfaction_c)          # criterion mix
    FINAL          = clamp01(SCORE_NORM × match^EXP_A × boost^EXP_B)

    SCORE_NORM = 0.9918   EXP_A = 0.905   EXP_B = 0.4105

Derivation (recorded): with match values {0.71, 0.49, 0.18} and boosts
{1.5, 1.0, 1.0} the three target finals are reproduced exactly to 2 decimals
(residuals ≤ 0.0011). Both exponents < 1 encode *sub-linear* response: a strong
boost raises reach potential, but returns diminish — this keeps the score
(monotone) in [0,1] without saturating and preserves relative spread.

Satisfaction per criterion comes from the profile shares of the *screen
catchment* (own zone + neighbouring gate zones by documented coupling).
Criterion keys and the profile keys they read:
    holiday      -> purpose_holiday          intl      -> intl_share
    family       -> party_family_with_children   adult25_54 -> adults_25_54
    business     -> purpose_business         premium   -> premium_cabin
    children     -> children_pax_share       frequent  -> frequent_flyer
    dest:<City>  -> share of catchment pax whose flights serve that city
    domestic     -> domestic share (1 - intl)
"""
from __future__ import annotations

SCORE_NORM = 0.9918
EXP_A = 0.905
EXP_B = 0.4105

MATCH_MIN = 0.0
SCORE_MAX = 1.0

CRITERIA_KEYS = {
    "holiday": "purpose_holiday",
    "international": "intl_share",
    "family": "party_family_with_children",
    "business": "purpose_business",
    "adult25_54": "adults_25_54",
    "premium": "premium_cabin",
    "children": "children_pax_share",
    "frequent": "frequent_flyer",
    "domestic": "domestic_share",  # computed as max(0, 1 - intl_share)
}


def audience_match(
    target_segments: dict[str, float],
    shares: dict[str, float],
    dest_weights: dict[str, float],
    total_pax: int,
    dwell: float | None = None,
    campaign_dwell_floor: float | None = None,
) -> float:
    """Weighted criterion satisfaction; missing criteria count 0 (fail-closed)."""
    if total_pax <= 0 or not target_segments:
        return 0.0
    total = 0.0
    for criterion, weight in target_segments.items():
        if criterion.startswith("dest:"):
            city = criterion[5:]
            share = (dest_weights.get(city, 0.0) / total_pax) if dest_weights else 0.0
        elif criterion == "dwell":
            floor = campaign_dwell_floor or 60.0
            share = min(1.0, (dwell or 0.0) / floor)
        else:
            key = CRITERIA_KEYS.get(criterion)
            if key == "domestic_share":
                share = max(0.0, 1.0 - (shares.get("intl_share") or 0.0))
            elif key is None:
                share = 0.0
            else:
                share = shares.get(key, 0.0)
        if not isinstance(share, (int, float)):
            share = 0.0
        total += weight * share
    return round(min(1.0, max(0.0, total)), 4)


def final_score(
    match: float,
    boost: float,
    audience_weight: float = 1.0,
    context_weight: float = 1.0,
) -> float:
    """Regenerable final score with admin-tunable global weights.

    A weight of 1.0 is the calibrated worked-example behavior. Weights scale
    the corresponding sub-linear exponent, so changes remain monotone and
    bounded while visibly affecting later decisions.
    """
    if match <= 0.0:
        return 0.0
    b = max(1.0, boost)
    aw = max(0.0, float(audience_weight))
    cw = max(0.0, float(context_weight))
    value = SCORE_NORM * (match ** (EXP_A * aw)) * (b ** (EXP_B * cw))
    return round(min(SCORE_MAX, max(0.0, value)), 4)
