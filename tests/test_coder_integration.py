"""Integration tests using a fake OpenAI client.

Tests that agents produce the right UI events and route messages
correctly, without spending real API credits.
"""

import multiprocessing as mp
from unittest.mock import MagicMock, patch

FAKE_CODE_RESPONSE = """Here is my over-engineered solution:

```python
import pandas as pd
# just a stub
print("hello")
```
"""


def _make_fake_client(response_text: str) -> MagicMock:
    """Build a MagicMock that mimics the OpenAI v1 client shape."""
    client = MagicMock()
    resp = MagicMock()
    resp.choices = [MagicMock()]
    resp.choices[0].message.content = response_text
    client.chat.completions.create.return_value = resp
    return client


def test_coder_emits_expected_events_and_sends_code(tmp_path, monkeypatch):
    """Coder should emit input/thinking/output events and put code in outbox."""
    monkeypatch.chdir(tmp_path)  # so transcripts/ goes to tmp
    from scope_creep.agents.coder import Coder

    inbox = mp.Queue()
    outbox = mp.Queue()
    ui_queue = mp.Queue()

    coder = Coder(
        name="Andrey",
        system_prompt="You are Andrey",
        inbox=inbox,
        ui_queue=ui_queue,
        model="gpt-4.1-mini",
    )
    coder.set_outbox(outbox)

    # Feed the Coder a scope doc
    inbox.put({"content": "Write a classifier.", "to": "Andrey"})

    # Patch OpenAI in the coder's own module
    fake_client = _make_fake_client(FAKE_CODE_RESPONSE)
    with patch("scope_creep.agents.coder.OpenAI", return_value=fake_client):
        coder.run()  # synchronous — don't spawn a process, simpler for tests

    # ---- check outbox ----
    msg = outbox.get(timeout=1)
    assert msg["from"] == "Andrey"
    assert "print(" in msg["content"]
    assert msg["lines"] >= 1

    # ---- drain UI queue and verify event kinds ----
    events = []
    try:
        while True:
            events.append(ui_queue.get(timeout=0.2))
    except Exception:
        pass

    kinds = [e["kind"] for e in events]
    assert "status" in kinds      # "waiting for scope"
    assert "input" in kinds       # "received scope"
    assert "output" in kinds      # "submitted N lines"


def test_coder_handles_llm_error_gracefully(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from scope_creep.agents.coder import Coder

    inbox = mp.Queue()
    outbox = mp.Queue()
    ui_queue = mp.Queue()
    coder = Coder(
        name="Andrey", system_prompt="...", inbox=inbox, ui_queue=ui_queue
    )
    coder.set_outbox(outbox)
    inbox.put({"content": "do a thing"})

    bad_client = MagicMock()
    bad_client.chat.completions.create.side_effect = RuntimeError("no network")
    with patch("scope_creep.agents.coder.OpenAI", return_value=bad_client):
        coder.run()

    msg = outbox.get(timeout=1)
    assert "ERROR" in msg["content"]


def test_coder_handles_task_done_sentinel(tmp_path, monkeypatch):
    """If the inbox receives TASK_DONE, Coder should exit cleanly."""
    monkeypatch.chdir(tmp_path)
    from scope_creep.agents.base import Agent
    from scope_creep.agents.coder import Coder

    inbox = mp.Queue()
    outbox = mp.Queue()
    coder = Coder(name="Andrey", system_prompt="...", inbox=inbox)
    coder.set_outbox(outbox)
    inbox.put({"content": Agent.task_done()})

    # no LLM call expected — set a client that would blow up if called
    with patch("scope_creep.agents.coder.OpenAI") as mk:
        mk.return_value.chat.completions.create.side_effect = AssertionError(
            "should not be called"
        )
        coder.run()

    # outbox should be empty — coder exited without submitting
    assert outbox.empty()
