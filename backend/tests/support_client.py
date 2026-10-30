"""Synchronous test client for the installed Starlette/HTTPX combination."""
from __future__ import annotations

import asyncio
import threading
from typing import Any

import httpx


class SyncASGIClient:
    """Keep one loop/lifespan alive while exposing sync test methods."""

    def __init__(self, app, *, base_url: str = "http://testserver") -> None:
        self.app = app
        self.base_url = base_url
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._startup_error: BaseException | None = None
        self._lifespan = None
        self._client: httpx.AsyncClient | None = None

    def __enter__(self) -> SyncASGIClient:
        self._thread = threading.Thread(target=self._run_loop, name="airp-test-loop", daemon=True)
        self._thread.start()
        if not self._ready.wait(timeout=30):
            raise TimeoutError("test ASGI client lifespan did not start")
        if self._startup_error:
            raise self._startup_error
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        if self._loop is None:
            return
        future = asyncio.run_coroutine_threadsafe(self._shutdown(), self._loop)
        future.result(timeout=30)
        self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread:
            self._thread.join(timeout=2)

    def _run_loop(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._startup())
        except BaseException as exc:
            self._startup_error = exc
        finally:
            self._ready.set()
        if self._startup_error is None:
            self._loop.run_forever()

    async def _startup(self) -> None:
        self._lifespan = self.app.router.lifespan_context(self.app)
        await self._lifespan.__aenter__()
        # Warm one deterministic boundary before exposing the client. The
        # synchronous SQLite adapter must not compete with the first request
        # while the virtual player is warming all 180 screens.
        engine = self.app.state.engine
        engine.clock.playing = True
        engine._process_boundaries()
        engine.clock.playing = False
        await engine._flush_pending()
        self._client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.app), base_url=self.base_url
        )

    async def _shutdown(self) -> None:
        if self._client:
            await self._client.aclose()
        if self._lifespan:
            await self._lifespan.__aexit__(None, None, None)

    def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        if self._loop is None or self._client is None:
            raise RuntimeError("client is not started")
        future = asyncio.run_coroutine_threadsafe(
            self._client.request(method, url, **kwargs), self._loop
        )
        return future.result(timeout=30)

    def get(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("POST", url, **kwargs)

    def put(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("PUT", url, **kwargs)

    def patch(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("PATCH", url, **kwargs)

    def delete(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("DELETE", url, **kwargs)
