"""Tests for transcript saving/loading."""

import json

from scope_creep.utils.transcript import (
    Transcript,
    UIEvent,
    load_transcript,
    save_transcript,
)


def test_uievent_roundtrip():
    ev = UIEvent(agent="Dr. Hong", kind="status", content="hello")
    d = ev.to_dict()
    assert d["agent"] == "Dr. Hong"
    assert d["kind"] == "status"
    assert d["content"] == "hello"
    assert "timestamp" in d


def test_save_and_load(tmp_path):
    t = Transcript(agent="Andrey", model="gpt-4.1-mini")
    t.events.append(UIEvent(agent="Andrey", kind="output", content="done"))
    t.messages.append({"role": "system", "content": "You are Andrey"})
    t.messages.append({"role": "user", "content": "scope"})
    t.messages.append({"role": "assistant", "content": "```python\nx=1\n```"})

    path = save_transcript(t, tmp_path)
    assert path.exists()
    assert path.name == "andrey.json"

    loaded = load_transcript(path)
    assert loaded["agent"] == "Andrey"
    assert loaded["model"] == "gpt-4.1-mini"
    assert len(loaded["events"]) == 1
    assert len(loaded["messages"]) == 3


def test_slug_handles_dots_and_spaces(tmp_path):
    t = Transcript(agent="Dr. Hong", model="gpt-4.1-mini")
    path = save_transcript(t, tmp_path)
    assert path.name == "dr_hong.json"


def test_transcript_to_dict_is_json_serializable(tmp_path):
    t = Transcript(agent="Dimitar", model="gpt-4.1-mini")
    t.events.append(UIEvent(agent="Dimitar", kind="qa", content="pass"))
    # Should not raise
    json.dumps(t.to_dict())
