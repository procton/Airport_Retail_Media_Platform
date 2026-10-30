# Passenger Presence and Crowd Profiling

**Requirement ID:** REQ_i2dnbq

---

Perfect. I have gathered sufficient evidence. Let me compile the report now:

### 1. Summary

- **ID:** REQ_i2dnbq
- **Title:** Passenger Presence and Crowd Profiling
- **Constraints:** [CONSTR_1x398h] ZonePresence or equivalent model combining flight passenger counts, gate/screen proximity, boarding/dwell time, queue measurements per zone and 5-min window; [CONSTR_amh4cq] Crowd profiles with aggregated audience attributes, variations by route/time, without individual passenger tracking

### 2. Implementation Evidence

- **Main File:** backend/app/services/presence/presence.py
- **Key Functions/Components:** PresenceEngine class, presence_for() method, zone_counts() method, security_counts() method, window_floor() function, dep_leg_weight() function, arr_leg_weight() function
- **How it covers requirement:** The PresenceEngine implements a documented ZonePresence engine that derives aggregated passenger-presence profiles by zone, screen, and time window from nearby flights and queue information. It combines flight passenger counts, gate proximity via zone assignment, boarding/dwell time via weight functions, and queue measurements (ACRIS) for security zones. Each profile is computed per 5-minute window and aggregates passenger attributes without tracking individuals.
- **Dependencies:** Flight, Zone, ZoneKind, QonePresence, QueueMeasurement, FlightProfile, SegmentShares from domain.canonical; profile_for() from profiles.py

### 3. Constraint Verification

| Constraint | Status | Evidence |
|------------|--------|----------|
| ZonePresence or equivalent model exists | ✅ | backend/app/domain/canonical.py:401-416 defines ZonePresence with zone_id, window_start, passenger_count, dwell_median_min, shares dict, contributing_flights |
| Combines flight passenger counts | ✅ | presence.py:193 uses flight.pax and presence.py:202 accumulates contrib = pax * w for departures |
| Gate/screen proximity integration | ✅ | presence.py:191 checks if gate is in zone via gate_index lookup; presence.py:95-96 defines screen_catchment_weight(); presence.py:30-32 documents screen catchment weights (1.0/0.5/0.25) |
| Boarding/dwell time weighting | ✅ | presence.py:73-84 dep_leg_weight() implements ramp/plateau/decay weights based on seconds to effective STD; presence.py:87-92 arr_leg_weight() implements arrival weighting |
| Queue measurements integrated | ✅ | presence.py:139-144 set_queue_measurements() loads and indexes QueueMeasurement by zone; presence.py:231-241 security_counts() applies freshness decay (1→0 over 15 min) to checkpoint headcount |
| Per-zone, per-5-min-window granularity | ✅ | presence.py:56-58 window_floor() rounds to 5-minute boundaries; presence.py:267-287 presence_for() computes zone presence at time t for given zone; presence.py:276-278 ZonePresence stores window_start and window label |
| Aggregated audience attributes without individual tracking | ✅ | presence.py:172-177 mixing() aggregates weighted segment shares per zone; presence.py:273 normalizes to per-capita shares; canonical.py:411 shares dict contains only aggregated percentages (purpose_*, party_*, intl_share, etc.) with no identifiers |
| Route/time variations | ✅ | profiles.py:78-216 profile_for() implements documented rules generating route-dependent (domestic/intl, origin/destination region) and time-dependent (weekday, hour, school-holiday) share variations; presence.py:201 uses profile for each flight |

### 4. Coverage Assessment

- **Score:** 1.0
- **Verdict:** COVERED
- **Justification:** The implementation fully satisfies both constraints. The ZonePresence model is complete with all required data elements (flight passenger counts, zone/gate proximity, boarding/dwell weighting, queue measurements, 5-minute windows, and aggregated crowd profiles). The crowd profiles are genuinely aggregated without individual tracking—they contain only segment shares (purpose, party type, demographics, international split) computed across contributing flights.
- **Gaps:** None

### 5. Quality Notes

- **Complexity:** medium
- **Error Handling:** present (zone lookup, flight validation, division-by-zero protection on dwell averaging, staleness checks on queue measurements)
- **Concerns:** None

### 6. Clean Code Quality

- **Score:** 4
- **Readability:** good
- **Modularity:** well-structured
- **Documentation:** thorough
- **Style Consistency:** consistent
- **DRY Adherence:** mostly
- **Justification:** The code is well-organized with clear separation of concerns (PresenceEngine class, weight functions, profile generation). Comprehensive inline documentation explains the weighting model and synthetic profile rules. The structure is modular and maintainable. Minor DRY opportunity exists in the retail zone aggregation (lines 247-263) which duplicates patterns from zone_counts, but this is acceptable given the distinct logic flow.

Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>