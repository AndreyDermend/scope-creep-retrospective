"""Live terminal UI for the three-agent pipeline.

Reads UIEvents off a shared `mp.Queue` in the main process and renders
three side-by-side panels (one per agent) with rich. The UI shows what
each agent is *thinking* (LLM prose) and what it *outputs* (status,
results, QA feedback).

Color coding:
  Dr. Hong  → teal / green   (team lead)
  Andrey    → amber           (coder)
  Dimitar   → purple          (SCRUM)

Event kinds and their colors:
  status   → white  (what the agent is doing)
  input    → cyan   (what it received)
  thinking → italic dim  (LLM prose leaking through)
  output   → yellow (artifact submitted)
  qa       → red or green based on content
  result   → bold green (final success)
  error    → bold red
"""

from __future__ import annotations

import multiprocessing as mp
import queue
import time
from dataclasses import dataclass, field
from datetime import datetime

from rich.align import Align
from rich.columns import Columns
from rich.console import Group
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

AGENT_COLORS = {
    "Dr. Hong": "bright_green",
    "Andrey": "yellow",
    "Dimitar": "magenta",
}

KIND_STYLES = {
    "status": "white",
    "input": "cyan",
    "thinking": "italic grey70",
    "output": "yellow",
    "qa_pass": "green",
    "qa_fail": "red",
    "result": "bold green",
    "error": "bold red",
}

KIND_LABELS = {
    "status": "●",
    "input": "←",
    "thinking": "…",
    "output": "→",
    "qa": "QA",
    "result": "✓",
    "error": "✗",
}


@dataclass
class AgentPanelState:
    """Accumulated events for one agent."""

    name: str
    events: list[dict] = field(default_factory=list)

    def add(self, event: dict) -> None:
        self.events.append(event)

    def render(self, max_events: int = 14) -> Panel:
        color = AGENT_COLORS.get(self.name, "white")
        # Show the most recent N events; older ones roll off the top.
        visible = self.events[-max_events:]

        body = Text()
        if not visible:
            body.append("(idle)", style="dim")
        for ev in visible:
            ts = datetime.fromtimestamp(ev["timestamp"]).strftime("%H:%M:%S")
            kind = ev["kind"]
            content = ev["content"]

            marker = KIND_LABELS.get(kind, "·")

            if kind == "qa":
                style = KIND_STYLES["qa_pass"] if (
                    "pass" in content.lower() or "✓" in content
                ) else KIND_STYLES["qa_fail"]
            else:
                style = KIND_STYLES.get(kind, "white")

            body.append(f"{ts} ", style="dim")
            body.append(f"{marker} ", style=color)
            body.append(content + "\n", style=style)

        subtitle = ""
        if visible:
            last_phase = visible[-1].get("phase", "")
            if last_phase:
                subtitle = f"phase: {last_phase}"

        return Panel(
            body,
            title=f"[bold {color}]{self.name}[/]",
            subtitle=subtitle,
            border_style=color,
            padding=(0, 1),
        )


class LiveUI:
    """Consumer for the UI queue. Runs in the main process."""

    def __init__(self, agent_names: list[str], ui_queue: mp.Queue) -> None:
        self.panels = {name: AgentPanelState(name) for name in agent_names}
        self.queue = ui_queue
        self.start_time = time.time()
        self.total_events = 0
        self.done = False

    def _header(self) -> Panel:
        elapsed = time.time() - self.start_time
        txt = Text()
        txt.append("Three-Agent Pipeline", style="bold")
        txt.append("   ·   ", style="dim")
        txt.append(f"elapsed {elapsed:5.1f}s", style="white")
        txt.append("   ·   ", style="dim")
        txt.append(f"events: {self.total_events}", style="white")
        txt.append("   ·   ", style="dim")
        if self.done:
            txt.append("done", style="bold green")
        else:
            txt.append("running", style="bold yellow")
        return Panel(
            Align.center(txt),
            border_style="grey50",
            padding=(0, 1),
        )

    def _render(self) -> Group:
        panels = [
            self.panels[name].render() for name in self.panels
        ]
        # Use Columns for equal-width side-by-side rendering
        cols = Columns(panels, equal=True, expand=True)
        return Group(self._header(), cols)

    def consume_until_done(
        self, expected_final_events: int | None = None, timeout: float = 300.0
    ) -> None:
        """Drain the UI queue, refreshing the display as events arrive.

        We don't know in advance how many events there will be — instead
        we stop when (a) an explicit sentinel `{'__done__': True}` arrives
        or (b) no events for `idle_timeout` seconds after the first one.
        """
        # refresh_per_second is gentle to avoid flicker when streaming lots
        with Live(self._render(), refresh_per_second=6, screen=False) as live:
            idle_timeout = 15.0  # seconds of silence before we assume done
            last_event_at = time.time()
            deadline = time.time() + timeout

            while True:
                if time.time() > deadline:
                    break
                try:
                    item = self.queue.get(timeout=0.5)
                except queue.Empty:
                    # Quiet period: check idle timeout
                    if time.time() - last_event_at > idle_timeout:
                        break
                    continue

                if isinstance(item, dict) and item.get("__done__"):
                    break

                agent = item.get("agent", "")
                if agent in self.panels:
                    self.panels[agent].add(item)
                    self.total_events += 1
                    last_event_at = time.time()
                    live.update(self._render())

            self.done = True
            live.update(self._render())
            time.sleep(0.5)  # let final frame render
