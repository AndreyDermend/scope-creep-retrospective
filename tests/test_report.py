"""Tests for the HTML report generator."""

import json

import pytest

from scope_creep.ui.report import (
    generate_report,
    render_agent_column,
    render_event,
)


def test_render_event_escapes_html():
    ev = {
        "agent": "Andrey",
        "kind": "output",
        "content": "<script>alert(1)</script>",
        "timestamp": 1700000000.0,
        "phase": "coding",
    }
    result = render_event(ev)
    assert "<script>alert(1)</script>" not in result
    assert "&lt;script&gt;" in result


def test_render_event_includes_icon_and_timestamp():
    ev = {
        "agent": "Andrey",
        "kind": "output",
        "content": "ok",
        "timestamp": 1700000000.0,
        "phase": "",
    }
    html = render_event(ev)
    assert "→" in html  # output icon
    assert "class=\"event evt-output\"" in html


def test_render_agent_column_contains_name_and_events():
    t = {
        "agent": "Dr. Hong",
        "model": "gpt-4.1-mini",
        "start_time": 1700000000.0,
        "end_time": 1700000060.0,
        "events": [
            {
                "agent": "Dr. Hong",
                "kind": "status",
                "content": "Drafted scope",
                "timestamp": 1700000001.0,
                "phase": "scope",
            }
        ],
        "messages": [{"role": "system", "content": "..."}],
    }
    html = render_agent_column(t)
    assert "Dr. Hong" in html
    assert "Drafted scope" in html
    assert "gpt-4.1-mini" in html


def test_generate_report_end_to_end(tmp_path):
    transcripts_dir = tmp_path / "transcripts"
    transcripts_dir.mkdir()
    (transcripts_dir / "dr_hong.json").write_text(json.dumps({
        "agent": "Dr. Hong",
        "model": "gpt-4.1-mini",
        "start_time": 1700000000.0,
        "end_time": 1700000060.0,
        "events": [],
        "messages": [],
    }))
    (transcripts_dir / "andrey.json").write_text(json.dumps({
        "agent": "Andrey",
        "model": "gpt-4.1-mini",
        "start_time": 1700000000.0,
        "end_time": 1700000030.0,
        "events": [],
        "messages": [],
    }))
    out = tmp_path / "report.html"
    generate_report(
        transcripts_dir=str(transcripts_dir), output_file=str(out)
    )
    assert out.exists()
    html = out.read_text()
    assert "Dr. Hong" in html
    assert "Andrey" in html
    assert "<!DOCTYPE html>" in html


def test_generate_report_fails_on_missing_dir(tmp_path):
    with pytest.raises(FileNotFoundError):
        generate_report(
            transcripts_dir=str(tmp_path / "nonexistent"),
            output_file=str(tmp_path / "out.html"),
        )
