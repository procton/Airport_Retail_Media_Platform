# Live Simulation and Cross-Role Cause and Effect

**Requirement ID:** REQ_cczx79

---

Perfect! I now have enough evidence. Let me compile the report based on my findings.

### 1. Summary

- **ID:** REQ_cczx79
- **Title:** Live Simulation and Cross-Role Cause and Effect
- **Constraints:** CONSTR_e2xiv7 (simulation controls: play/pause/speeds/jump/events), CONSTR_4dbt4z (2-second update propagation)

### 2. Implementation Evidence

- **Main File:** `/workspace/TC-AI-Workflows/TC-AI-Reviewer/workspace/submission/code/backend/app/services/simulator/engine.py`, `/workspace/TC-AI-Workflows/TC-AI-Reviewer/workspace/submission/code/frontend/src/TopBar.tsx`, `/workspace/TC-AI-Workflows/TC-AI-Reviewer/workspace/submission/code/backend/app/api/routes.py`
- **Key Functions/Components:** `engine.set_transport()`, `engine.inject_flight_event()`, `engine.inject_screen()`, `engine.replan_screens()`, `TopBar.tsx` controls UI
- **How it covers requirement:** Frontend TopBar component (TopBar.tsx) provides unified simulation control UI with play/pause, 1x/10x/60x speed selection, time jump, and event injection (delay/gate-change/screen-offline). Backend engine (engine.py) implements: set_transport() for play/pause/speed (1/10/60 only), jump_to() for time jump, inject_flight_event() for flight events (delay/gate_change/cancel), inject_screen() for screen offline events. Event injection triggers flight state update, screen replanning within synchronous path (< 2 seconds).
- **Dependencies:** SimClock (clock.py), DAO persistence, event bus (bus.publish), presence invalidation, screen planner

### 3. Constraint Verification

| Constraint | Status | Evidence |
|------------|--------|----------|
| Global controls support play/pause | ✅ | TopBar.tsx:67-69 play/pause button, engine.py:221 set_transport method |
| Global controls support 1x/10x/60x speed | ✅ | TopBar.tsx:71-73 speed buttons [1,10,60], engine.py:225 assert speed in (1,10,60) |
| Global controls support time jump | ✅ | TopBar.tsx:76,82-92 jump input, engine.py:231 jump_to() method |
| Inject delay events | ✅ | TopBar.tsx:102, api.ts:233 injectFlightEvent, engine.py:471-488 delay event generation |
| Inject gate-change events | ✅ | TopBar.tsx:103, engine.py:490-495 gate_change event generation |
| Inject screen-offline events | ✅ | TopBar.tsx:118 screen offline button, routes.py:114-120 screen_toggle endpoint, engine.py:546 inject_screen method |
| Event updates flight/airline state within 2s | ✅ | engine.py:504 apply_flight_event(), test_delay_chain_e2e.py:71-90 validates propagation ≤2.0s, bus.publish("flight.update") at line 516 |
| Event updates passenger presence within 2s | ✅ | engine.py:513 presence.invalidate(), presence model updated synchronously within event path |
| Event updates campaign decision within 2s | ✅ | engine.py:514-515 planner.invalidate_world(), replan_screens() runs synchronously (line 582 comment: "<2 s wall-clock") |
| Event updates passenger-screen output within 2s | ✅ | engine.py:598 bus.publish("screen.playlist", slot) in replan_screens(), ScreenView observes playlist updates |

### 4. Coverage Assessment

- **Score:** 1.0
- **Verdict:** COVERED
- **Justification:** All simulation controls (play/pause/1x-10x-60x/jump) are implemented and exposed in the frontend TopBar. All required event types (delay, gate-change, screen-offline) are supported. The engine uses a synchronous event-injection path that guarantees updates propagate through flight state, presence, planner, and screen playlist within 2 seconds, validated by test_delay_chain_e2e.py which asserts elapsed ≤ 2.0s.
- **Gaps:** None. Documentation comment at engine.py:582 explicitly states "Runs synchronously; used from the <2 s wall-clock event path," confirming architectural commitment to the 2-second constraint.

### 5. Quality Notes

- **Complexity:** high
- **Error Handling:** present (EngineError raised for unknown flight/kind; HTTPException 400 returned to client; screen existence validated before injection)
- **Concerns:** Cancel event is partially supported (line 478 accepts "cancel" as valid kind, line 499 generates CNL status), but update logic in apply_flight_event handles only "status_change" type (line 531), which may create a mismatch if the adapter returns a different event kind for cancellation.

### 6. Clean Code Quality

- **Score:** 4
- **Readability:** good
- **Modularity:** well-structured
- **Documentation:** adequate
- **Style Consistency:** consistent
- **DRY Adherence:** mostly
- **Justification:** Code is well-organized with clear separation between API routes, engine simulation logic, and frontend controls. Method names are descriptive (inject_flight_event, replan_screens, apply_flight_event). One minor concern: event kind handling is scattered across multiple methods (validation, generation, parsing, application) which could benefit from a unified event type enum; however, current structure is maintainable. Comments exist for critical paths (e.g., "<2 s wall-clock" at line 582).