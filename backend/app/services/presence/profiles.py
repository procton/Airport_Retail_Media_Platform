"""Per-flight passenger profile generator (synthetic, deterministic).

Inputs reachable from the AODB fixture only: origin/destination, direction,
day-of-week/hour, aircraft footprint, school-holiday calendar (platform-owned
synthetic table), festival flag. Everything else (country, region, nationality,
language, purpose/party/age mixes) is documented synthetic enrichment:
fictional values for fictional destinations, labelled `simulated` everywhere
they influence decisions (assumption A3).
"""
from __future__ import annotations

import hashlib
from datetime import datetime

from ...domain.canonical import Flight, FlightProfile, SegmentShares

# Fictional geography (synthetic enrichment; nothing inferred from real codes).
_COUNTRY: dict[str, tuple[str, str, str]] = {
    # code: (city, country, language)
    "ADN": ("Aldmere", "Tarnland", "Meridian English"),
    "BWZ": ("Brightwater", "Corvane", "Meridian English"),
    "CBP": ("Calder Bay", "Marrow Isles", "Meridian English"),
    "CPZ": ("Coralport", "Marrow Isles", "Meridian English"),
    "DMQ": ("Dunmore", "Tarnland", "Meridian English"),
    "EHQ": ("Eastholm", "Corvane", "Meridian English"),
    "FHQ": ("Fairhaven", "Solance", "Meridian English"),
    "GRH": ("Glenrock", "Vellmark", "Meridian English"),
    "GSZ": ("Goldsand", "Solance", "Meridian English"),
    "HCX": ("Highcliff", "Vellmark", "Meridian English"),
    "IVQ": ("Ironvale", "Tarnland", "Meridian English"),
    "JFQ": ("Juniper Falls", "Corvane", "Meridian English"),
    "LMW": ("Lakemont", "Vellmark", "Meridian English"),
    "NGV": ("Northgate", "Tarnland", "Meridian English"),
    "OKZ": ("Oakridge", "Solance", "Meridian English"),
    "BVQ": ("Belvista", "Belvia", "Belvik"),
    "KST": ("Kastell", "Kastelle", "Kastellish"),
    "NVQ": ("Novaterra", "Novaria", "Novan"),
    "PVQ": ("Port Valen", "Valendor", "Valene"),
    "SCJ": ("Santa Corvina", "Corvinia", "Corvinian"),
    "SMG": ("Solmara", "Solmara Isles", "Solmaran"),
    "ZHQ": ("Zarhan", "Zarhania", "Zarhane"),
    "MQI": ("Meridian City", "Meridia", "Meridian English"),
}
_REGIONS: dict[str, str] = {
    "Inland Belt": "baseline", "Coast Belt": "baseline", "Highland Belt": "baseline",
    "Southern Reach": "baseline", "Archipelago Reach": "baseline", "Desert Reach": "baseline",
}
_COUNTRY_REGION: dict[str, str] = {
    "Tarnland": "Inland Belt", "Corvane": "Inland Belt", "Marrow Isles": "Coast Belt",
    "Solance": "Coast Belt", "Vellmark": "Highland Belt", "Belvia": "Southern Reach",
    "Kastelle": "Southern Reach", "Novaria": "Southern Reach", "Valendor": "Archipelago Reach",
    "Corvinia": "Archipelago Reach", "Solmara Isles": "Archipelago Reach",
    "Zarhania": "Desert Reach", "Meridia": "Home",
}
_INLAND_BUSINESS_REGIONS = {"Inland Belt", "Highland Belt"}
_BUSINESS_CONVENTION_COUNTRIES = {"Belvia", "Kastelle", "Corvinia"}
_MONTH_SCHOOL_HOLIDAY = {1, 7, 12}  # synthetic calendar


def enrich(code: str) -> tuple[str, str, str, str]:
    """(city, country, region, language) — documented synthetic enrichment."""
    ct, country, lang = _COUNTRY.get(code, ("Meridian City", "Meridia", "Meridian English"))
    return ct, country, _COUNTRY_REGION.get(country, "Home"), lang


def is_festival(day: str) -> bool:
    """Synthetic festival calendar for demo richness; empty for the default day."""
    return month_of(day) in ()


def month_of(day: str) -> int:
    try:
        return datetime.fromisoformat(f"{day}T00:00:00+00:00").month
    except ValueError:
        return 0


def profile_for(flight: Flight, day: str) -> FlightProfile:
    """Build a plausible aggregated passenger profile for one leg.

    Generator rules (documented, deterministic per leg+day):
    - domestic morning routes in Inland/Highland belts skew business 25–54;
    - international coast/archipelago routes and school-holiday months skew
      holiday/family;
    - cabin mix from aircraft footprint (widebody intl raises premium share);
    - median-dwell hints: intl 58 min, domestic 42, +8 for >260-seat aircraft.
    """
    inbound = flight.direction.value == "D"
    other = flight.destination if inbound else flight.origin
    dep_city, dep_country, dep_region, dep_lang = enrich(flight.origin if inbound else flight.destination)
    arriving_country = enrich(other)[1]

    # Pinned aggregate crowd for the organizer's worked example
    # (AGENTS §11 — identifier universe XY501/ZQ88 does not exist in the MQI
    # fixture; sections 11 forbids presenting it as CSV-sourced. The engine
    # executes the same code path; only the profile inputs are pinned.)
    if flight.source == "worked-example":
        return FlightProfile(
            flight_leg_id=flight.id,
            origin_city=dep_city, origin_country=dep_country, origin_region=dep_region,
            domestic=False,
            shares=SegmentShares(
                purpose_business=0.22, purpose_holiday=0.58, purpose_vfr=0.14,
                purpose_student=0.03, purpose_religious=0.03,
                party_solo=0.41, party_couple=0.28, party_family_with_children=0.31,
                party_group=0.00,
                children_pax_share=0.1953, adults_25_54=0.70,
                premium_cabin=0.14, frequent_flyer=0.16, female=0.51,
                intl_share=0.57,
                top_destinations=[(dep_city, 0.6), (enrich(flight.origin)[0], 0.4)],
                nationalities=[dep_country, "Meridia", "Novaria"],
                languages=["Meridian English", "Zarhane", "Belvik"],
            ),
            dwell_hint_min=52.0,
            festival=False,
            evidence_ids=[f"evid:{flight.id}:profile"],
            synthetic=True,
        )

    domestic = flight.flight_nature == "D"
    digest = hashlib.sha256(f"{day}:{flight.id}".encode()).digest()
    jitter = digest[0] / 255.0 - 0.5  # ±0.5 uniform noise on split points
    hour = flight.sched_std.hour
    weekday = flight.sched_std.weekday()
    school_holiday = month_of(day) in _MONTH_SCHOOL_HOLIDAY

    # purpose shares (mutually exclusive; scaled to 1)
    business = 0.30 if (domestic and dep_region in _INLAND_BUSINESS_REGIONS and weekday < 5 and 5 <= hour <= 10) else 0.11
    arriving_is_convention = arriving_country in _BUSINESS_CONVENTION_COUNTRIES
    if not domestic and arriving_is_convention and weekday < 5:
        business = 0.36
    holiday = min(
        0.66,
        (0.30 if domestic else 0.34) + (0.15 if school_holiday else 0.0) + (0.10 if weekday >= 5 else 0.0)
        + jitter * 0.04,
    )
    student = 0.06 if (domestic and 15 <= hour <= 19 and weekday < 5) else 0.03
    religious = 0.05 if dep_region == "Desert Reach" else 0.03
    vfr = max(0.05, 1.0 - business - holiday - student - religious - 0.06)
    raw = {"business": business, "holiday": holiday, "vfr": vfr, "student": student, "religious": religious}
    total = sum(raw.values())
    purpose = {f"purpose_{k}": round(v / total, 3) for k, v in raw.items()}

    # party shares
    family_block = purpose["purpose_holiday"] * (0.62 if school_holiday else 0.46)
    couple = min(family_block * 0.5, 0.34)
    with_children = max(0.0, family_block - couple)
    solo = max(0.10, 1.0 - family_block - 0.16 - (0.04 if not domestic else 0.0))
    group = max(0.02, 1.0 - solo - couple - with_children)
    psum = solo + couple + with_children + group
    party = {
        "party_solo": round(solo / psum, 3),
        "party_couple": round(couple / psum, 3),
        "party_family_with_children": round(with_children / psum, 3),
        "party_group": round(group / psum, 3),
    }
    children_mass = min(0.22, party["party_family_with_children"] * (0.68 if school_holiday else 0.63))
    children_mass * 0.62
    children_mass * 0.38
    adult_mass = 1.0 - children_mass
    base = (0.13, 0.24, 0.28, 0.21, 0.14)  # 18-24,25-34,35-44,45-54,55+ shares of adults
    bsum = sum(base)
    b = [x / bsum for x in base]
    adults_25_54 = adult_mass * (b[1] + b[2] + b[3])
    adult_mass * b[0]
    adult_mass * b[4]

    wide = (flight.aircraft_type or "").startswith(("A38", "B77", "B74", "A35", "B78"))
    premium = 0.14 if wide else (0.06 if not domestic else 0.03)
    lcc = flight.airline_iata in {"XD", "YN", "XU", "YF"}
    frequent = 0.09 if lcc else 0.16
    female = max(0.36, 0.52 - (0.05 if purpose["purpose_business"] > 0.25 else 0.0))
    intl = 0.0 if domestic else round(min(0.90, 0.5 + 0.35 * purpose["purpose_holiday"]), 3)

    dest_city, dest_country, _, _ = enrich(flight.destination)
    nationalities = [dep_country, "Meridia"]
    if not domestic:
        nationalities.insert(0, dest_country)
    languages = [dep_lang, "Meridian English"] if not domestic else ["Meridian English"]

    dwell_hint = 58.0 if not domestic else 42.0
    if (flight.pax or 0) > 260:
        dwell_hint += 8.0

    shares = SegmentShares(
        purpose_business=purpose["purpose_business"],
        purpose_holiday=purpose["purpose_holiday"],
        purpose_vfr=purpose["purpose_vfr"],
        purpose_student=purpose["purpose_student"],
        purpose_religious=purpose["purpose_religious"],
        party_solo=party["party_solo"],
        party_couple=party["party_couple"],
        party_family_with_children=party["party_family_with_children"],
        party_group=party["party_group"],
        children_pax_share=round(children_mass, 3),
        adults_25_54=round(adults_25_54, 3),
        premium_cabin=round(premium, 3),
        frequent_flyer=round(frequent, 3),
        female=round(female, 3),
        intl_share=intl,
        top_destinations=[(dest_city, 1.0)],
        nationalities=nationalities[:3],
        languages=languages[:3],
    )
    return FlightProfile(
        flight_leg_id=flight.id,
        origin_city=dep_city,
        origin_country=dep_country,
        origin_region=dep_region,
        domestic=domestic,
        shares=shares,
        dwell_hint_min=dwell_hint,
        festival=is_festival(day),
        evidence_ids=[f"evid:{flight.id}:profile"],
        synthetic=True,
    )
