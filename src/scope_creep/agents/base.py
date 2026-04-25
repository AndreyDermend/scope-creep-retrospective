"""Base class for all three agents.

Each agent is an `mp.Process`. Instead of printing, agents call `emit()`
which pushes UIEvents onto a shared `ui_queue` that the main process reads
and renders via Rich.
"""

from __future__ import annotations

import multiprocessing as mp
import time

from scope_creep.utils.transcript import UIEvent

TASK_DONE = "TASK_DONE"
QA_FAILED = "QA_FAILED"


class Agent(mp.Process):
    """Parent class for Coder, TeamLead, and ScrumMaster.

    Subclasses override `run()`. The shared behaviour lives here: inbox
    setup, UI event emission, outbox setup.
    """

    def __init__(
        self,
        name: str,
        system_prompt: str,
        inbox: mp.Queue,
        ui_queue: mp.Queue | None = None,
        model: str = "gpt-4.1-mini",
        temperature: float = 0.2,
    ) -> None:
        super().__init__()
        self.agent_name = name
        self.system_prompt = system_prompt
        self.inbox = inbox
        self.outbox: mp.Queue | None = None
        self.ui_queue = ui_queue
        self.model = model
        self.temperature = temperature
        self.current_phase = ""
        # Per-process local log, written to the transcript at shutdown.
        self._events: list[dict] = []

    # ------------------------------------------------------------
    # Messaging helpers
    # ------------------------------------------------------------
    def set_outbox(self, outbox: mp.Queue) -> None:
        self.outbox = outbox

    def set_phase(self, phase: str) -> None:
        self.current_phase = phase

    def emit(self, kind: str, content: str, phase: str | None = None) -> None:
        """Publish a UI event. Persists locally AND pushes to the UI queue."""
        event = UIEvent(
            agent=self.agent_name,
            kind=kind,
            content=content,
            phase=phase or self.current_phase,
            timestamp=time.time(),
        )
        event_dict = event.to_dict()
        self._events.append(event_dict)
        if self.ui_queue is not None:
            self.ui_queue.put(event_dict)
        else:
            # fallback: plain print when no UI is attached (useful for tests)
            print(f"[{self.agent_name}] {kind}: {content}")

    @staticmethod
    def task_done() -> str:
        return TASK_DONE

    def run(self) -> None:  # pragma: no cover
        raise NotImplementedError
