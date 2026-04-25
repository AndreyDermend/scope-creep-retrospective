"""Save full agent transcripts to JSON for post-run inspection."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class UIEvent:
    """A single visible event from an agent.

    These are what the live Rich UI renders and what gets persisted
    to the transcript for the HTML viewer.
    """

    agent: str
    kind: str  # status | input | thinking | output | qa | result | error
    content: str
    phase: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Transcript:
    """Full record of one agent's run: UI events + raw LLM messages."""

    agent: str
    model: str
    start_time: float = field(default_factory=time.time)
    end_time: float | None = None
    events: list[UIEvent] = field(default_factory=list)
    messages: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "agent": self.agent,
            "model": self.model,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "events": [e.to_dict() for e in self.events],
            "messages": self.messages,
        }


def save_transcript(transcript: Transcript, output_dir: str | Path) -> Path:
    """Write a transcript to {output_dir}/{agent_slug}.json."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    slug = transcript.agent.lower().replace(" ", "_").replace(".", "")
    path = output_dir / f"{slug}.json"
    path.write_text(json.dumps(transcript.to_dict(), indent=2))
    return path


def load_transcript(path: str | Path) -> dict:
    """Load a transcript JSON as a plain dict."""
    return json.loads(Path(path).read_text())
