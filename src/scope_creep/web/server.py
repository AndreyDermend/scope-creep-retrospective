"""FastAPI web server for the live three-agent dashboard.

Runs in the main process alongside the agents. Three agents publish
UIEvent dicts to a shared mp.Queue; this server drains that queue
and re-emits to connected browsers via Server-Sent Events.

Architecture:
    [Agent process] → ui_queue → [SSE pump] → [Browser EventSource]

Entry point: serve(ui_queue, host, port)
"""

from __future__ import annotations

import asyncio
import json
import multiprocessing as mp
import queue
import time
from collections.abc import AsyncGenerator
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

_STATIC_DIR = Path(__file__).parent / "static"


def make_app(ui_queue: mp.Queue, state: dict) -> FastAPI:
    """Build a FastAPI app wired to a UI queue and a shared state dict.

    The `state` dict carries run metadata that the dashboard polls (or
    receives via SSE): `started_at`, `done`, `event_count`.
    """
    app = FastAPI(title="Scope-Creep Retrospective")

    # ----- Static UI -----
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

    @app.get("/")
    async def index() -> FileResponse:
        return FileResponse(_STATIC_DIR / "index.html")

    @app.get("/api/state")
    async def get_state() -> dict:
        return {
            "started_at": state.get("started_at"),
            "done": state.get("done", False),
            "event_count": state.get("event_count", 0),
            "agents": state.get("agents", []),
            "elapsed": (
                time.time() - state["started_at"]
                if state.get("started_at")
                else 0
            ),
        }

    # ----- SSE stream -----
    @app.get("/events")
    async def events() -> StreamingResponse:
        return StreamingResponse(
            _event_stream(ui_queue, state),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",  # for nginx if proxied
            },
        )

    return app


async def _event_stream(
    ui_queue: mp.Queue, state: dict
) -> AsyncGenerator[str, None]:
    """Drain the queue, yield SSE-formatted messages.

    Yields a heartbeat every 15s if the queue is quiet so proxies/browsers
    don't disconnect. Yields a final 'done' event when state['done'] is True
    AND the queue is empty.
    """
    # Replay the buffered backlog first so a late-connecting browser
    # sees everything that already happened.
    for buffered in list(state.get("backlog", [])):
        yield _sse_message("event", buffered)

    last_heartbeat = time.time()

    while True:
        try:
            event = ui_queue.get_nowait()
            state["event_count"] = state.get("event_count", 0) + 1
            state.setdefault("backlog", []).append(event)
            yield _sse_message("event", event)
            last_heartbeat = time.time()
        except queue.Empty:
            await asyncio.sleep(0.1)

            if time.time() - last_heartbeat > 15:
                yield _sse_message(
                    "heartbeat",
                    {"elapsed": time.time() - state.get("started_at", 0)},
                )
                last_heartbeat = time.time()

            if state.get("done") and ui_queue.empty():
                yield _sse_message("done", {"event_count": state.get("event_count", 0)})
                return


def _sse_message(event_type: str, data: dict) -> str:
    """Format a Server-Sent Events message."""
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


def serve(
    ui_queue: mp.Queue,
    state: dict,
    host: str = "127.0.0.1",
    port: int = 8000,
) -> None:
    """Start uvicorn. Blocks until killed.

    Used by main.py — the FastAPI app is the foreground process,
    the agents run in the background as mp.Processes.
    """
    import uvicorn

    app = make_app(ui_queue, state)
    config = uvicorn.Config(
        app, host=host, port=port, log_level="warning", access_log=False
    )
    server = uvicorn.Server(config)
    server.run()
