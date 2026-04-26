"""Tests for the FastAPI dashboard server."""

from __future__ import annotations

import multiprocessing as mp
import time

from fastapi.testclient import TestClient

from scope_creep.web.server import _sse_message, make_app


def _make_state() -> dict:
    return {
        "started_at": time.time(),
        "done": False,
        "event_count": 0,
        "agents": ["Dr. Hong", "Andrey", "Dimitar"],
        "backlog": [],
    }


def test_sse_message_format():
    msg = _sse_message("event", {"agent": "Andrey", "kind": "status"})
    assert msg.startswith("event: event\n")
    assert "data: " in msg
    assert msg.endswith("\n\n")
    # One blank line between message and next message — the SSE protocol delimiter
    assert msg.count("\n\n") == 1


def test_index_returns_html():
    ui_queue = mp.Queue()
    state = _make_state()
    client = TestClient(make_app(ui_queue, state))

    r = client.get("/")
    assert r.status_code == 200
    assert "scope-creep" in r.text.lower()
    assert "Dr. Hong" in r.text
    assert "Andrey" in r.text
    assert "Dimitar" in r.text


def test_static_assets_served():
    ui_queue = mp.Queue()
    state = _make_state()
    client = TestClient(make_app(ui_queue, state))

    r = client.get("/static/style.css")
    assert r.status_code == 200
    assert "lane" in r.text  # one of the CSS classes from index.html

    r = client.get("/static/app.js")
    assert r.status_code == 200
    assert "EventSource" in r.text


def test_state_endpoint():
    ui_queue = mp.Queue()
    state = _make_state()
    state["event_count"] = 7
    client = TestClient(make_app(ui_queue, state))

    r = client.get("/api/state")
    assert r.status_code == 200
    data = r.json()
    assert data["event_count"] == 7
    assert "Dr. Hong" in data["agents"]
    assert data["done"] is False
    assert data["elapsed"] >= 0


def test_events_endpoint_streams_buffered_then_done():
    """Buffered events are replayed; when state['done']=True and the queue is
    empty, the stream emits a 'done' event and closes."""
    ui_queue = mp.Queue()
    state = _make_state()

    # Pre-buffer two events and mark the run done so the stream returns quickly
    state["backlog"] = [
        {"agent": "Andrey", "kind": "status", "content": "starting", "timestamp": time.time()},
        {"agent": "Dr. Hong", "kind": "output", "content": "→ prediction.csv", "timestamp": time.time()},
    ]
    state["done"] = True

    client = TestClient(make_app(ui_queue, state))

    with client.stream("GET", "/events") as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")

        # Read the whole stream — it should terminate quickly because done=True
        body = "".join(response.iter_text())

    # Both buffered events should have been replayed
    assert "starting" in body
    assert "prediction.csv" in body
    # And the stream emits a done event
    assert "event: done" in body


def test_events_endpoint_drains_live_queue():
    """Events pushed to the queue mid-stream get emitted to the client."""
    ui_queue = mp.Queue()
    state = _make_state()

    # Pre-load three events on the queue, mark done
    for i, kind in enumerate(["status", "thinking", "output"]):
        ui_queue.put({
            "agent": "Andrey",
            "kind": kind,
            "content": f"event {i}",
            "timestamp": time.time(),
        })
    state["done"] = True

    client = TestClient(make_app(ui_queue, state))
    with client.stream("GET", "/events") as response:
        body = "".join(response.iter_text())

    assert "event 0" in body
    assert "event 1" in body
    assert "event 2" in body
    assert "event: done" in body
