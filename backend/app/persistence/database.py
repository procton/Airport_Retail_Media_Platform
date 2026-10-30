"""SQLite access with an async-facing synchronous SQLAlchemy session.

The DAO and service APIs remain async, but SQLite operations execute through
SQLAlchemy's synchronous driver in the single application worker. This is the
isolated synchronous approach supported by the project architecture and avoids
the worker-thread connection path used by ``aiosqlite``.
"""
from __future__ import annotations

from app.config import get_settings
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

_engine: Engine | None = None
_sessionmaker: AsyncSessionFactory | None = None


def _sync_url(url: str) -> str:
    """Accept the existing public ``sqlite+aiosqlite`` setting unchanged."""
    return url.replace("sqlite+aiosqlite", "sqlite")


class AsyncSessionAdapter:
    """Async facade over one short-lived synchronous SQLAlchemy session."""

    def __init__(self, session: Session) -> None:
        self._session = session

    async def __aenter__(self) -> AsyncSessionAdapter:
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        if exc_type is not None:
            self._session.rollback()
        self._session.close()

    def add(self, value) -> None:
        self._session.add(value)

    async def delete(self, value) -> None:
        self._session.delete(value)

    async def execute(self, *args, **kwargs):
        return self._session.execute(*args, **kwargs)

    async def get(self, *args, **kwargs):
        return self._session.get(*args, **kwargs)

    async def merge(self, *args, **kwargs):
        return self._session.merge(*args, **kwargs)

    async def commit(self) -> None:
        self._session.commit()


class AsyncSessionFactory:
    def __init__(self, factory: sessionmaker) -> None:
        self._factory = factory

    def __call__(self) -> AsyncSessionAdapter:
        return AsyncSessionAdapter(self._factory())


def reset_engine() -> None:
    global _engine, _sessionmaker
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _sessionmaker = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(_sync_url(get_settings().database_url), echo=False, future=True)
        _prime_sqlite(_engine)
    return _engine


def _prime_sqlite(engine: Engine) -> None:
    @event.listens_for(engine, "connect")
    def _set_pragma(dbapi_conn, _record):  # pragma: no cover - driver hook
        cur = dbapi_conn.cursor()
        for pragma, val in (
            ("journal_mode", "WAL"),
            ("synchronous", "NORMAL"),
            ("busy_timeout", 4500),
            ("foreign_keys", "ON"),
        ):
            cur.execute(f"PRAGMA {pragma} = {val}")
        cur.close()


def get_sessionmaker() -> AsyncSessionFactory:
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = AsyncSessionFactory(sessionmaker(get_engine(), expire_on_commit=False))
    return _sessionmaker
