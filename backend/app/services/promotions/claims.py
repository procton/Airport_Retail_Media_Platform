"""Promo tokens and claims (AGENTS §17).

Semantics:
- Tokens are opaque, minted ONLY by the backend at slot time (browser views
  never mint, duplicate or extend them).
- `scan` records a page-open separately from redemption; `redeem` converts to a
  Redemption exactly once (idempotent by PK token; repeat calls return the
  original redemption).
- Window validity: sim-time expiry ≥ clock now, active run, and the promo code
  window; tokens of previous runs never redeem (AGENTS §7 runs rule).
- Family sharing issues ONE additional code per token (family_cap=2) with the
  same validity; only one of the two codes may ultimately redeem — sharing is
  bounded and one-time.
- No passenger identity or device identifiers are collected, ever.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime


class ClaimError(Exception):
    def __init__(self, code: str, status: int = 400) -> None:
        super().__init__(code)
        self.code = code
        self.status = status


class ClaimsService:
    def __init__(self, engine) -> None:
        self.engine = engine

    # ------------------------------------------------------------------ views
    def _expiry_ok(self, expires_at: str | datetime, now: datetime) -> bool:
        dt = expires_at if isinstance(expires_at, datetime) else datetime.fromisoformat(expires_at)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt >= now

    @staticmethod
    def _aware(s: str) -> datetime:
        dt = datetime.fromisoformat(s)
        return dt if dt.tzinfo else dt.replace(tzinfo=UTC)

    async def _find_token(self, token: str) -> dict | None:
        row = await self.engine.dao.get_token(token)
        if row:
            return row
        # tokens not yet flushed live in the engine's pending batch
        pending = self.engine._pending.get("tokens", [])
        for p in pending:
            if p["token"] == token:
                return dict(p)
        return None

    async def _ensure_persisted(self, row: dict) -> None:
        """A token pending flush is materialized on first claim interaction
        (idempotency by PK requires the DB row to exist)."""
        if await self.engine.dao.get_token(row["token"]) is None:
            row["mode"] = "phone"       # phone claimance of not-yet-flushed token
            await self.engine.dao.add_token(row)
    # ------------------------------------------------------------------ views
    async def open_page(self, token: str) -> dict:
        engine = self.engine
        now = engine.clock.sim_now
        row = await self._find_token(token)
        if row is None:
            raise ClaimError("token_not_found", 404)
        await self._ensure_persisted(row)
        code_rows = {c["id"]: c for c in await engine.dao.load_promo_codes()}
        code = code_rows.get(row["promo_code_id"])
        if not code:
            raise ClaimError("code_not_found", 404)
        valid = row["run_id"] == engine.run_id and self._expiry_ok(row["expires_at"], now)
        await engine.dao.scan_token(token, now)
        slot_creative = self._browser_facing_payload()
        return {
            "token": token,
            "code": code["code"],
            "campaign_id": code["campaign_id"],
            "expires_at": row["expires_at"],
            "valid_now": valid,
            "state": "redeemed" if row["redeemed_at"] else "scan",
            "redeemed_at": row["redeemed_at"],
            "family_shared": row["family_index"] > 0,
            "value_label": code["value"],
            "branding": dict(
                title=engine.settings.app_name,
                logo=engine.settings.brand_logo,
                primary=engine.settings.brand_primary,
            ),
            **slot_creative,
        }

    def _browser_facing_payload(self) -> dict:
        return {"claim_mode": "phone", "collect_identity": False}

    async def redeem(self, token: str, mode: str = "phone") -> dict:
        engine = self.engine
        now = engine.clock.sim_now
        row = await self._find_token(token)
        if row is None:
            raise ClaimError("token_not_found", 404)
        await self._ensure_persisted(row)
        row = await engine.dao.get_token(token)
        code_rows = {c["id"]: c for c in await engine.dao.load_promo_codes()}
        code = code_rows.get(row["promo_code_id"])
        if not code:
            raise ClaimError("code_not_found", 404)
        # idempotency: a previously redeemed token returns its redemption as-is
        if row["redeemed_at"]:
            if row["mode"] == "simulated-engagement":
                raise ClaimError("already_redeemed_simulated", 409)
            return {
                "id": f"rdp:{token}", "token": token, "campaign_id": code["campaign_id"],
                "already": True, "redeemed_at": row["redeemed_at"],
                "value": row["revenue_value"], "mode": "phone",
            }
        # simulated-engagement tokens are backend-owned autoplay records and
        # must never be convertible by a phone claim (AGENTS §17)
        if row["mode"] == "simulated-engagement":
            raise ClaimError("simulated_not_claimable", 409)
        if row["run_id"] != engine.run_id:
            raise ClaimError("stale_run", 409)
        if not self._expiry_ok(row["expires_at"], now):
            raise ClaimError("expired", 410)
        if code.get("window_start") and now < self._aware(code["window_start"]):
            raise ClaimError("window_not_started", 409)
        if code.get("window_end") and self._aware(code["window_end"]) < now:
            raise ClaimError("window_ended", 410)
        value = float(code.get("value", 0.0))
        performed = await engine.dao.redeem_token(token, now, value)
        existing = await engine.dao.get_token(token)
        from app.services.metrics.learning import apply_conversion

        await apply_conversion(engine.dao, code["campaign_id"], 1.0)
        campaign = engine.campaign_map.get(code["campaign_id"])
        out = {
            "id": f"rdp:{token}", "token": token, "campaign_id": code["campaign_id"],
            "outlet_id": campaign.outlet_id if campaign else "", "already": not performed,
            "redeemed_at": existing["redeemed_at"] if existing else now.isoformat(),
            "value": value, "mode": mode,
        }
        engine.bus.publish("redemption.live", out)
        # one-time family bundle: a redeemed member voids remaining siblings
        if code.get("kind") == "family" and performed:
            await engine.dao.void_family_siblings(code["id"], row["run_id"], now, token)
        return out

    async def family_share(self, token: str) -> dict:
        engine = self.engine
        now = engine.clock.sim_now
        row = await self._find_token(token)
        if row is None:
            raise ClaimError("token_not_found", 404)
        code = {c["id"]: c for c in await engine.dao.load_promo_codes()}[row["promo_code_id"]]
        if code.get("kind") != "family":
            raise ClaimError("not_family_code", 400)
        if row["family_index"] > 0 or row["redeemed_at"]:
            raise ClaimError("family_share_already_used", 409)
        new_token = uuid.uuid4().hex[:20]
        await engine.dao.add_token({
            "token": new_token, "promo_code_id": row["promo_code_id"], "run_id": row["run_id"],
            "issued_at": now, "expires_at": self._aware(row["expires_at"]), "redeemed_at": None,
            "scanned_at": None, "family_index": 1, "mode": "phone",
            "revenue_value": row["revenue_value"],
        })
        await engine.dao.set_family_index(token, 2)
        return {"token": new_token, "link": f"/claim/{new_token}", "expires_at": row["expires_at"]}
