# Platform Admin and Media Manager Workflows

**Requirement ID:** REQ_2w2eow

---

Based on my analysis of the submission, I can now produce the comprehensive report:

### 1. Summary

- **ID:** REQ_2w2eow
- **Title:** Platform Admin and Media Manager Workflows
- **Constraints:** [CONSTR_xsxjgj] Platform Admin experience; [CONSTR_qmyycd] Media Manager experience

### 2. Implementation Evidence

- **Main File:** `/workspace/TC-AI-Workflows/TC-AI-Reviewer/workspace/submission/code/frontend/src/views/AdminView.tsx` (Admin), `/workspace/TC-AI-Workflows/TC-AI-Reviewer/workspace/submission/code/frontend/src/views/MediaView.tsx` (Media)
- **Key Functions/Components:** `AdminView()` component with Map tab (MapSvg), heat overlay toggle, KPI display, incidents tracking, master data CRUD, decision log with rules; `MediaView()` component with inventory calendar, pricing calculator, approval workflows, advertiser overview
- **How it covers requirement:** AdminView provides terminal network visualization (MapSvg at line 307), real-time screen states (line 36, 369), passenger presence heat overlay (line 22, 342-347), KPI strip (lines 56-67), incident tracking (lines 96-137), searchable decision log (lines 147-301), and master data management (MasterData function, lines 413-475). MediaView delivers screen-by-hour inventory calendar (lines 50-83), presence-driven pricing formula (Pricing function, lines 205-232), campaign approval workflow (lines 88-118), and advertiser delivery analytics (Advertisers function, lines 234-272).
- **Dependencies:** React store (useStore), REST API client (api.ts), zone/screen/campaign data models

### 3. Constraint Verification

| Constraint | Status | Evidence |
|------------|--------|----------|
| [CONSTR_xsxjgj] Terminal network map | ✅ | AdminView.tsx:307-376 MapSvg renders terminal layout with T1/T2 zones, screen positioning, online/offline visual states |
| [CONSTR_xsxjgj] Screen states display | ✅ | AdminView.tsx:369 dot colors show online (blue accent) vs offline (red), line 374 legend explains state visual encoding |
| [CONSTR_xsxjgj] Passenger heat overlay | ✅ | AdminView.tsx:22 heat state toggle, lines 342-347 heatCol() function derives color from zone.passenger_count thresholds, line 359 applies heat coloring conditionally |
| [CONSTR_xsxjgj] KPI strip | ✅ | AdminView.tsx:56-67 displays 8 KPI cards: screens_online_pct, plays_today, impressions_today, revenue_today, active_campaigns, playlist_latency_ms, delayed_legs, configured_slot_price |
| [CONSTR_xsxjgj] Incident tracking | ✅ | AdminView.tsx:96-120 Incidents & feeds tab shows severity/title/where/status/remediation with re-enable action (line 112), health status updates |
| [CONSTR_xsxjgj] Master data workflows | ✅ | MasterData function (lines 413-475): list view (line 452), create button (line 449), edit mode (line 461), delete action (line 468), JSON editor (line 465), full CRUD via api.createMasterData/updateMasterData/deleteMasterData |
| [CONSTR_xsxjgj] Decision log with rules | ✅ | DecisionsAndRules function (lines 147-301): searchable log (lines 188-196), global rule sliders for competitor_gap_min/frequency_window_min/exploration_epsilon/audience_weight/context_weight (lines 267-291) |
| [CONSTR_qmyycd] Screen-by-hour inventory calendar | ✅ | MediaView.tsx:50-83 table with 12-hour horizon, screen × hour cells showing booked (campaign chip) vs open slots, zone selection (line 40) |
| [CONSTR_qmyycd] Passenger-presence pricing | ✅ | Pricing function (lines 205-232): formula base 1.2 + 1.4×(pax/100) + 0.8×(dwell/60) drives suggested CPM per zone, displayed with passenger_count/next30_count/next120_count columns |
| [CONSTR_qmyycd] Campaign approval actions | ✅ | MediaView.tsx:88-118 Approvals tab shows PENDING campaigns with Approve/Reject buttons (lines 108-109), brand-safety checklist display (line 105) |
| [CONSTR_qmyycd] Advertiser delivery overview | ✅ | Advertisers function (lines 234-272) aggregates by advertiser_id: campaign count, playing now, est. exposure from slots, under-delivery flag for campaigns ≥4 and playing <2 |

### 4. Coverage Assessment

- **Score:** 1.0
- **Verdict:** COVERED
- **Justification:** Both the Platform Admin (CONSTR_xsxjgj) and Media Manager (CONSTR_qmyycd) requirements are fully implemented with all specified features present in code. The Admin view provides all required operational components (map, heat, KPIs, incidents, master data, decision log, rules). The Media view delivers all specified inventory and yield-management capabilities (calendar, pricing formula, approvals, advertiser analytics).
- **Gaps:** None

### 5. Quality Notes

- **Complexity:** Medium
- **Error Handling:** Present — API errors caught (lines 163, 172-177, 425-431), user confirmations added (line 434), messaging feedback to user (lines 175-176, 430, 435)
- **Concerns:** Master data JSON editor lacks schema validation hints; incident remediation limited to single action type (screen online/offline); no pagination shown for large master data lists (slice(0, 80) may truncate silently)

### 6. Clean Code Quality

- **Score:** 4
- **Readability:** Good
- **Modularity:** Well-structured — components separated by concern (Admin/Media views, subcomponents like MapSvg/MasterData/Pricing/Advertisers), clear naming conventions
- **Documentation:** Adequate — component jsdoc headers explain purpose (AdminView line 1, MediaView line 1, DecisionsAndRules line 146), formula documented inline (line 229), but missing descriptions for MasterData entity types and heat threshold logic
- **Style Consistency:** Mostly consistent — React hooks pattern followed throughout, TypeScript interfaces typed, consistent className/classNames usage, though some prop drilling could be reduced
- **DRY Adherence:** Mostly — zone/screen data fetched once via useStore; Pricing/Advertisers computed with useMemo to avoid recalculation; minor repetition in tab navigation patterns (Admin/Media both use similar button map)
- **Justification:** Code is production-ready with clear component boundaries, proper state management via React hooks and store pattern, and meaningful error feedback. Minor improvements could include entity schema hints in master data editor and pagination for large lists.