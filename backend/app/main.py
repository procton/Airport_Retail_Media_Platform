"""FastAPI application entry — one engine per worker (AGENTS §3).

Startup: bootstrap SQLite (alembic-equivalent create_all for the prototype;
alembic remains the reproducible migration path used in Compose), start the
single SimulationEngine, expose REST under /api and the WebSocket at /ws,
and serve the built SPA (frontend/dist) when present.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api.routes import router
from .config import get_settings
from .services.simulator.engine import SimulationEngine

FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


async def database_ready() -> None:
    from .persistence import models
    from .persistence.database import get_engine

    eng = get_engine()
    with eng.begin():
        models.Base.metadata.create_all(bind=eng)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    await database_ready()
    engine = SimulationEngine(settings)
    app.state.engine = engine
    await engine.start()
    try:
        yield
    finally:
        await engine.stop()
        app.state.engine = None


def create_app() -> FastAPI:
    app = FastAPI(title=get_settings().app_name, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
    )
    app.include_router(router)

    if FRONTEND_DIST.exists():
        app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        async def spa(path: str):
            candidate = FRONTEND_DIST / path
            if path and candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(FRONTEND_DIST / "index.html")

    @app.get("/api/health")
    async def health():
        eng = app.state.engine
        return {
            "ok": True,
            "engine_started": bool(eng and eng._started),
            "ws_clients": eng.bus.n_clients() if eng else 0,
        }

    return app


app = create_app()
