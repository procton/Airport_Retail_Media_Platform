"""Alembic environment. URL comes from settings (env DATABASE_URL wins)."""
from __future__ import annotations

from logging.config import fileConfig
from pathlib import Path

from alembic import context
from app.config import get_settings
from app.persistence import models  # noqa: F401  (register tables)
from sqlalchemy import engine_from_config, pool

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = models.Base.metadata


def _sqlite_url_sync() -> str:
    url = get_settings().database_url.replace("sqlite+aiosqlite", "sqlite")
    # ensure parent directory for the primary database file
    if url.startswith("sqlite"):
        path = url.partition(":///")[2] or url.partition(":///")[0]
        if path.startswith("/"):
            Path(path).parent.mkdir(parents=True, exist_ok=True)
    return url


def run_migrations_offline() -> None:
    context.configure(url=_sqlite_url_sync(), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    cfg = {"sqlalchemy.url": _sqlite_url_sync()}
    connectable = engine_from_config(cfg, prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
