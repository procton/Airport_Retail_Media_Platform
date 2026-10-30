"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-23
"""
from __future__ import annotations

from alembic import op
from app.config import get_settings
from app.persistence import models
from sqlalchemy import create_engine, inspect

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def _sync_url() -> str:
    return get_settings().database_url.replace("sqlite+aiosqlite", "sqlite")


def upgrade() -> None:
    engine = create_engine(_sync_url(), future=True)
    try:
        models.Base.metadata.create_all(engine)
        insp = inspect(op.get_bind())
        created = set(insp.get_table_names())
        for table in ("flights", "evidence_records", "decisions"):
            assert table in created, f"migration missing table {table}"
    finally:
        engine.dispose()


def downgrade() -> None:
    engine = create_engine(_sync_url(), future=True)
    try:
        models.Base.metadata.drop_all(engine)
    finally:
        engine.dispose()
