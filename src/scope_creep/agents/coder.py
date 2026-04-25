"""Andrey the Coder — generates over-scoped code, does not execute."""

from __future__ import annotations

from openai import OpenAI

from scope_creep.agents.base import Agent
from scope_creep.utils.code_extract import extract_python_code, strip_code_fences
from scope_creep.utils.transcript import Transcript, UIEvent, save_transcript


class Coder(Agent):
    """One-shot worker. Receives scope, returns code.

    Unlike the original notebook's Worker, Coder does NOT execute.
    Review and execution happen in TeamLead — that's the whole design bet.
    """

    def run(self) -> None:  # pragma: no cover - covered via integration test
        client = OpenAI()
        transcript = Transcript(agent=self.agent_name, model=self.model)
        messages: list[dict[str, str]] = [
            {"role": "system", "content": self.system_prompt}
        ]

        self.set_phase("waiting")
        self.emit("status", "Awaiting scope document from lead")

        msg = self.inbox.get()
        scope_text = msg.get("content", "")
        if scope_text == Agent.task_done():
            return

        self.set_phase("coding")
        self.emit("input", f"Received scope: {scope_text[:120]}...")
        messages.append({"role": "user", "content": scope_text})

        try:
            resp = client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                messages=messages,
            )
            reply = resp.choices[0].message.content.strip()
        except Exception as e:  # noqa: BLE001
            self.emit("error", f"LLM call failed: {e}")
            if self.outbox is not None:
                self.outbox.put(
                    {"from": self.agent_name, "content": f"ERROR: {e}"}
                )
            return

        messages.append({"role": "assistant", "content": reply})
        code = extract_python_code(reply)
        prose = strip_code_fences(reply)

        if prose:
            self.emit("thinking", prose[:300])
        line_count = len(code.splitlines())
        self.emit("output", f"Submitted {line_count} lines of code")

        if self.outbox is not None:
            self.outbox.put(
                {
                    "from": self.agent_name,
                    "content": code,
                    "raw_reply": reply,
                    "lines": line_count,
                }
            )

        transcript.events = [UIEvent(**e) for e in self._events]
        transcript.messages = messages
        import time as _t

        transcript.end_time = _t.time()
        save_transcript(transcript, "transcripts")
