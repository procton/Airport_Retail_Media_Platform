"""REST + WebSocket API (AGENTS §25).

All routes delegate to the running SimulationEngine / ClaimsService. No
business logic lives here; request validation via Pydantic models.
"""
from __future__ import annotations

import asyncio
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from ..services.promotions.claims import ClaimError

router = APIRouter(prefix="/api")


def _engine(request: Request):
    eng = request.app.state.engine
    if eng is None or not eng._started:
        raise HTTPException(503, "engine not started")
    return eng


def _ws_url_for_claim(request: Request, token: str) -> str:
    """Never encode localhost for a phone: prefer configured claim base, else
    the request's host header (LAN-reachable) (AGENTS §20)."""
    import os

    eng = request.app.state.engine
    base = eng.settings.claim_base_url or os.environ.get("AIRP_CLAIM_BASE_URL", "")
    if base:
        base = base.rstrip("/")
        if base.endswith("/claim"):  # config already encodes the claim route
            base = base[: -len("/claim")]
        return f"{base}/claim/{token}"
    host = request.headers.get("host", "127.0.0.1:8000")
    scheme = "https" if request.url.scheme == "https" else "http"
    return f"{scheme}://{host}/claim/{token}"


# ------------------------------------------------------------------ controls
class TransportBody(BaseModel):
    playing: bool | None = None
    speed: Literal[1, 10, 60] | None = None


class JumpBody(BaseModel):
    at: str


class ResetBody(BaseModel):
    keep_injected: bool = True


MASTER_KINDS = {"vendors", "outlets", "airlines", "terminals", "zones", "gates", "screens"}


class MasterDataBody(BaseModel):
    id: str
    data: dict[str, Any]


class FlightEventBody(BaseModel):
    flight_id: str
    kind: Literal["delay", "gate_change", "cancel"]
    minutes: int = 0
    gate: str | None = None


class ScreenBody(BaseModel):
    online: bool


class ClaimRedeemBody(BaseModel):
    mode: Literal["phone", "counter"] = "phone"


@router.get("/state/control")
async def control_state(request: Request):
    return _engine(request).control_state()


@router.post("/controls")
async def set_transport(body: TransportBody, request: Request):
    eng = _engine(request)
    if body.playing is None and body.speed is None:
        raise HTTPException(422, "nothing to change")
    return await eng.set_transport(body.playing if body.playing is not None else eng.clock.playing,
                                   body.speed)


@router.post("/controls/jump")
async def jump(body: JumpBody, request: Request):
    return await _engine(request).jump_to(body.at)


@router.post("/controls/reset")
async def reset(body: ResetBody, request: Request):
    return await _engine(request).reset_day(keep_injected=body.keep_injected)


@router.post("/controls/flight-event")
async def flight_event(body: FlightEventBody, request: Request):
    eng = _engine(request)
    try:
        return await eng.inject_flight_event(
            body.flight_id, body.kind, minutes=body.minutes, new_gate=body.gate)
    except eng.EngineError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/screens/{screen_id}/online-state")
async def screen_toggle(screen_id: str, body: ScreenBody, request: Request):
    eng = _engine(request)
    if screen_id not in eng.screens:
        raise HTTPException(404, f"unknown screen {screen_id}")
    eng.inject_screen(screen_id, body.online)
    return {"ok": True, "screen": screen_id, "online": body.online}


# ---------------------------------------------------------------- flights
@router.get("/flights")
async def flights(request: Request, airline: str | None = None, direction: str | None = None,
                  status: str | None = None, q: str | None = None, limit: int = 400):
    rows = _engine(request).flights_at()
    if airline:
        rows = [r for r in rows if r["airline_iata"] == airline.upper()]
    if direction:
        rows = [r for r in rows if r["direction"] == direction.upper()]
    if status:
        rows = [r for r in rows if r["status"].lower() == status.lower()]
    if q:
        ql = q.lower()
        rows = [r for r in rows if ql in r["designator"].lower() or ql in (r["gate"] or "").lower()
                or ql in r["destination"].lower()]
    rows.sort(key=lambda r: r["sched_std"])
    return {"count": len(rows), "flights": rows[:limit]}


@router.get("/flights/{flight_id}")
async def flight(request: Request, flight_id: str):
    eng = _engine(request)
    f = eng.flights.get(flight_id)
    if not f:
        raise HTTPException(404, f"unknown flight {flight_id}")
    prof = eng.presence.profile(f, eng.clock.day)
    return {**eng.flight_view(f), "profile": prof.model_dump(mode="json")}


# ---------------------------------------------------------------- presence
@router.get("/zones")
async def zones(request: Request):
    return {"zones": _engine(request).zones_summary()}


@router.get("/zones/{zone_id}")
async def zone_detail(request: Request, zone_id: str):
    eng = _engine(request)
    try:
        return eng.presence_of_zone(zone_id)
    except eng.EngineError as exc:
        raise HTTPException(404, str(exc)) from exc


# ---------------------------------------------------------------- screens
@router.get("/screens")
async def screens(request: Request, online: bool | None = None, zone: str | None = None,
                  gate: str | None = None):
    rows = _engine(request).screens_summary()
    if online is not None:
        rows = [r for r in rows if r["online"] == online]
    if zone:
        rows = [r for r in rows if r["zone_id"] == zone]
    if gate:
        rows = [r for r in rows if (r.get("gate") or "") == gate]
    return {"count": len(rows), "screens": rows}


@router.get("/master-data/{kind}")
async def master_data(kind: str, request: Request):
    if kind not in MASTER_KINDS:
        raise HTTPException(404, f"unknown master-data kind: {kind}")
    rows = _engine(request).master_data(kind)
    return {"kind": kind, "count": len(rows), "items": rows}


@router.post("/master-data/{kind}")
async def create_master_data(kind: str, body: MasterDataBody, request: Request):
    eng = _engine(request)
    if kind not in MASTER_KINDS:
        raise HTTPException(404, f"unknown master-data kind: {kind}")
    if not body.id.strip():
        raise HTTPException(422, "id is required")
    if any(row["id"] == body.id for row in eng.master_data(kind)):
        raise HTTPException(409, f"{kind}/{body.id} already exists")
    try:
        return await eng.save_master_data(kind, body.id, body.data)
    except eng.EngineError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.patch("/master-data/{kind}/{entity_id}")
async def update_master_data(kind: str, entity_id: str, body: MasterDataBody, request: Request):
    eng = _engine(request)
    if kind not in MASTER_KINDS:
        raise HTTPException(404, f"unknown master-data kind: {kind}")
    if body.id != entity_id:
        raise HTTPException(422, "body.id must match the path id")
    try:
        return await eng.save_master_data(kind, entity_id, body.data)
    except eng.EngineError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.delete("/master-data/{kind}/{entity_id}")
async def delete_master_data(kind: str, entity_id: str, request: Request):
    eng = _engine(request)
    if kind not in MASTER_KINDS:
        raise HTTPException(404, f"unknown master-data kind: {kind}")
    if not await eng.delete_master_data(kind, entity_id):
        raise HTTPException(404, f"unknown {kind}/{entity_id}")
    return {"ok": True, "kind": kind, "id": entity_id}


@router.get("/screens/{screen_id}")
async def screen_detail(request: Request, screen_id: str):
    eng = _engine(request)
    slot = eng.current_slot(screen_id)
    if slot is None:
        raise HTTPException(404, f"unknown screen {screen_id}")
    if slot.get("promo") and slot["promo"].get("token") and not slot.get("claim_url"):
        slot["claim_url"] = _ws_url_for_claim(request, slot["promo"]["token"])
    return slot


@router.post("/screens/{screen_id}/offline")
async def screen_offline(request: Request, screen_id: str):
    eng = _engine(request)
    if screen_id not in eng.screens:
        raise HTTPException(404, f"unknown screen {screen_id}")
    eng.inject_screen(screen_id, False)
    return {"ok": True, "screen": screen_id, "online": False}


@router.post("/screens/{screen_id}/online")
async def screen_online(request: Request, screen_id: str):
    eng = _engine(request)
    if screen_id not in eng.screens:
        raise HTTPException(404, f"unknown screen {screen_id}")
    eng.inject_screen(screen_id, True)
    return {"ok": True, "screen": screen_id, "online": True}


# ---------------------------------------------------------------- claims
@router.post("/claims/{token}")
async def claim_page(request: Request, token: str):
    eng = _engine(request)
    try:
        data = await eng.claims.open_page(token)
        data["claim_url"] = _ws_url_for_claim(request, token)
        return data
    except ClaimError as exc:
        raise HTTPException(exc.status, exc.code) from exc


@router.post("/claims/{token}/redeem")
async def claim_redeem(request: Request, token: str, body: ClaimRedeemBody | None = None):
    eng = _engine(request)
    mode = body.mode if body else "phone"
    try:
        out = await eng.claims.redeem(token, mode=mode)
    except ClaimError as exc:
        raise HTTPException(exc.status, exc.code) from exc
    eng.bus.publish("redemption.live", out)
    return out


@router.post("/claims/{token}/family")
async def claim_family(request: Request, token: str):
    eng = _engine(request)
    try:
        out = await eng.claims.family_share(token)
    except ClaimError as exc:
        raise HTTPException(exc.status, exc.code) from exc
    out["link"] = _ws_url_for_claim(request, out["token"])
    return out


# ---------------------------------------------------------------- campaigns
@router.get("/campaigns")
async def campaigns(request: Request):
    eng = _engine(request)
    return {"count": len(eng.campaigns),
            "campaigns": [c.model_dump(mode="json") for c in eng.campaigns]}


@router.get("/config/public")
async def public_config(request: Request):
    """Public white-label values used by the shell and mobile claim page."""
    eng = _engine(request)
    return {
        "name": eng.settings.app_name,
        "logo": eng.settings.brand_logo,
        "primary": eng.settings.brand_primary,
        "accent": eng.settings.brand_accent,
        "lang_primary": eng.settings.lang_primary,
        "lang_secondary": eng.settings.lang_secondary,
    }


class CampaignStatusBody(BaseModel):
    status: Literal["APPROVED", "REJECTED", "PAUSED", "COMPLETE"]


class CreativeAssistBody(BaseModel):
    product: str
    discount_pct: float | None = None
    audience: Literal["any", "holiday", "family", "children", "business", "coffee", "duty_free"] = "any"
    zone_hint: str | None = None
    note: str | None = None


@router.post("/creative/assist")
async def creative_assist(body: CreativeAssistBody, request: Request):
    """Creative assistant (§18): brief → ready bilingual template ad draft,
    offline provider by default; `live-*` providers report unconfigured."""
    eng = _engine(request)
    try:
        return await eng.assist_creative(body.model_dump())
    except eng.EngineError as exc:
        message = str(exc)
        status = 501 if message.startswith("unconfigured-provider") else 502 if message.startswith("provider-invalid-response") else 400
        raise HTTPException(status, message) from exc


@router.post("/campaigns/{campaign_id}/status")
async def campaign_status(campaign_id: str, body: CampaignStatusBody, request: Request):
    eng = _engine(request)
    try:
        eng.set_campaign_status(campaign_id, body.status)
    except eng.EngineError as exc:
        raise HTTPException(400, str(exc)) from exc
    await eng.persist_campaign_status(campaign_id, body.status)
    return {"ok": True, "campaign_id": campaign_id, "status": body.status}


@router.get("/campaigns/{campaign_id}/recommend-slots")
async def recommend_slots(campaign_id: str, request: Request):
    """Slot recommendation (§18): best three screen-hours for this campaign
    tomorrow, with predicted impressions/fit/availability and forecast
    assumptions. Computed by the backend engine; the frontend never scores."""
    eng = _engine(request)
    try:
        return eng.recommend_tomorrow(campaign_id)
    except eng.EngineError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/retailer/history")
async def retailer_history(request: Request, outlet: str):
    """30-day campaign ledger for one retailer outlet (§14). Simulated
    accounting; clearly separated from current-run live metrics."""
    eng = _engine(request)
    return await eng.retailer_history(outlet)


@router.get("/decisions")
async def decisions(request: Request, screen_id: str | None = None,
                    campaign_id: str | None = None, search: str | None = None,
                    limit: int = 120):
    """Searchable decision log (§12 Admin): by screen, campaign or substring
    across the full record (reasons, overrides, pins). Audit-only."""
    eng = _engine(request)
    return await eng.decision_log(screen_id, campaign_id, search, limit)


# ---- Admin global rule config (§12) -----------------------------------------

class MediaRulesBody(BaseModel):
    competitor_gap_min: float | None = None
    frequency_window_min: float | None = None
    exploration_epsilon: float | None = None
    audience_weight: float | None = None
    context_weight: float | None = None

@router.get("/config/media-rules")
async def get_media_rules(request: Request):
    return await _engine(request).get_media_rules()


@router.put("/config/media-rules")
async def set_media_rules(body: MediaRulesBody, request: Request):
    eng = _engine(request)
    try:
        rules = {k: v for k, v in body.model_dump().items() if v is not None}
        merged = {**eng._media_rules_state, **rules}
        return await eng.set_media_rules(merged)
    except eng.EngineError as exc:
        raise HTTPException(400, str(exc)) from exc


class RerunBody(BaseModel):
    campaign_id: str

@router.post("/campaigns/rerun")
async def rerun_campaign(body: RerunBody, request: Request):
    """Run-again (§14): one-action duplicate into a NEW editable PENDING
    campaign with a valid schedule (needs approval)."""
    eng = _engine(request)
    campaign_id = body.campaign_id
    try:
        return await eng.rerun_campaign(campaign_id)
    except eng.EngineError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/match/preview")
async def match_preview(request: Request, screen_id: str):
    eng = _engine(request)
    sc = eng.screens.get(screen_id)
    if sc is None:
        raise HTTPException(404, f"unknown screen {screen_id}")
    prev = eng.planner.preview_for(sc, eng.clock.sim_now, eng.run_id,
                                   pinned=eng.planner.pinned.get(screen_id))
    if prev is None:
        raise HTTPException(409, "screen offline; no audience available")
    return prev


# ---- Media Manager pin / override (AGENTS §10, §12, §15) --------------------

class PinBody(BaseModel):
    reason: str

@router.post("/screens/{screen_id}/pin/{campaign_id}")
async def pin_campaign(screen_id: str, campaign_id: str, body: PinBody, request: Request):
    """Manual pin with a RECORDED reason. Cannot bypass approval, placement or
    budget: the pinned candidate must still pass those hard rules in the
    pipeline; a fail keeps the scored winner for the slot."""
    eng = _engine(request)
    try:
        return eng.pin_campaign(screen_id, campaign_id, body.reason)
    except eng.EngineError as exc:
        raise HTTPException(400, str(exc)) from exc


class PinClearBody(BaseModel):
    reason: str = ""

@router.post("/screens/{screen_id}/unpin")
async def clear_pin(screen_id: str, body: PinClearBody, request: Request):
    eng = _engine(request)
    try:
        return eng.clear_pin(screen_id, body.reason)
    except eng.EngineError as exc:
        raise HTTPException(404, str(exc)) from exc


# ---------------------------------------------------------------- metrics
@router.get("/metrics/live")
async def metrics_live(request: Request):
    eng = _engine(request)
    return {"metrics": eng.metrics_live(), "controls": eng.control_state()}


@router.get("/incidents")
async def incidents(request: Request):
    eng = _engine(request)
    return {"count": len(eng._incidents_deque), "incidents": list(eng._incidents_deque)}


@router.get("/feeds")
async def feeds(request: Request):
    return {"feeds": _engine(request).feed_health()}


# ---------------------------------------------------------------- websocket
@router.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    eng = websocket.app.state.engine
    if eng is None:
        await websocket.close(code=503)
        return
    await websocket.accept()
    q = eng.bus.subscribe()
    # initial resync snapshot so clients can hydrate before events stream
    import orjson
    await websocket.send_bytes(orjson.dumps({
        "topic": "state.resync",
        "data": {"at": eng.clock.iso(), "run_id": eng.run_id,
                 "control": eng.control_state()},
    }))
    try:
        while True:
            try:
                payload = await asyncio.wait_for(q.get(), timeout=15.0)
            except TimeoutError:
                await websocket.send_bytes(orjson.dumps({"topic": "heartbeat", "data": {"at": eng.clock.iso()}}))
                continue
            await websocket.send_bytes(payload)
    except WebSocketDisconnect:
        pass
    finally:
        eng.bus.unsubscribe(q)
