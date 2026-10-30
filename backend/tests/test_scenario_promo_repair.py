"""Gate-42 scenario promo reconciliation for persistent databases."""
from __future__ import annotations

import asyncio

from app.config import get_settings
from app.persistence import database
from app.seed.loader import load_or_seed


def test_gate42_promo_is_reconciled_when_existing_run_lacks_it(tmp_path, monkeypatch):
    monkeypatch.setenv("AIRP_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path}/t.db")
    get_settings.cache_clear()
    database.reset_engine()

    async def exercise():
        from app.main import database_ready
        from app.persistence.dao import Dao

        await database_ready()
        dao = Dao()
        first = await load_or_seed(dao, get_settings())
        assert any(row["id"] == "pc:wx-DUTY-PERFUME:0:std" for row in first["promos"].get("wx-DUTY-PERFUME", []))

        # Simulate a persisted volume from before scenario promos were added.
        async with dao.sm() as session:
            from app.persistence.models import PromoCodeRow
            from sqlalchemy import delete
            await session.execute(delete(PromoCodeRow).where(PromoCodeRow.id == "pc:wx-DUTY-PERFUME:0:std"))
            await session.commit()

        repaired = await load_or_seed(dao, get_settings())
        repaired_rows = repaired["promos"].get("wx-DUTY-PERFUME", [])
        row = next(row for row in repaired_rows if row["id"] == "pc:wx-DUTY-PERFUME:0:std")
        assert row["code"] == "WX-PERFUME15"
        assert row["window_start"].startswith("2026-10-14T13:00:00")

    asyncio.run(exercise())
