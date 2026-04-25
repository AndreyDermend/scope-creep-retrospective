"""Dr. Hong the Team Lead — orchestrates the full project.

Four phases:
  1. Send scope document to Andrey.
  2. Receive his (inflated) code.
  3. Review against scope, emit trimmed version, execute it, verify prediction.csv.
  4. Write a retrospective brief for Dimitar based on what actually happened.
"""

from __future__ import annotations

import multiprocessing as mp
import os
import subprocess
import time

import pandas as pd
from openai import OpenAI

from scope_creep.agents.base import Agent
from scope_creep.utils.code_extract import extract_python_code
from scope_creep.utils.transcript import Transcript, UIEvent, save_transcript


class TeamLead(Agent):
    def __init__(
        self,
        name: str,
        system_prompt: str,
        inbox: mp.Queue,
        coder: Agent,
        scrum_master: Agent,
        scope_document: str,
        ui_queue: mp.Queue | None = None,
        target_csv: str = "prediction.csv",
        model: str = "gpt-4.1-mini",
        temperature: float = 0.2,
    ) -> None:
        super().__init__(name, system_prompt, inbox, ui_queue, model, temperature)
        self.coder = coder
        self.scrum_master = scrum_master
        self.scope_document = scope_document
        self.target_csv = target_csv

    def run(self) -> None:  # pragma: no cover
        client = OpenAI()
        transcript = Transcript(agent=self.agent_name, model=self.model)
        messages: list[dict[str, str]] = [
            {"role": "system", "content": self.system_prompt}
        ]

        # ---------- Phase 1: send scope to Andrey ----------
        self.set_phase("scope")
        self.emit("status", "Drafted scope document — sending to Andrey")
        self.coder.inbox.put(
            {"content": self.scope_document, "to": self.coder.agent_name}
        )
        messages.append(
            {
                "role": "assistant",
                "content": f"I sent this scope to Andrey:\n{self.scope_document}",
            }
        )

        # ---------- Phase 2: wait for Andrey's code ----------
        self.set_phase("review")
        self.emit("status", "Waiting for Andrey's submission...")
        msg = self.inbox.get()
        andrey_code = msg["content"]
        andrey_lines = msg.get("lines", len(andrey_code.splitlines()))
        self.emit("input", f"Received {andrey_lines} lines from Andrey")

        # ---------- Phase 3: review + trim ----------
        review_prompt = (
            "Here is the original scope I sent to Andrey:\n"
            f"---SCOPE---\n{self.scope_document}\n---END SCOPE---\n\n"
            "Here is Andrey's submission:\n"
            f"---CODE---\n{andrey_code}\n---END CODE---\n\n"
            "Your task:\n"
            "1. Identify every part of Andrey's code that is OUT OF SCOPE "
            "(extra models, cross-validation, SHAP, SMOTE, extra plots, "
            "excessive logging, unnecessary imports, bonus files, etc.).\n"
            "2. Write a short bulleted list of what you are removing and why.\n"
            "3. Return the TRIMMED code — minimal, in-scope only — inside a "
            "single ```python block. The trimmed code must still produce "
            f"{self.target_csv} and satisfy every numbered requirement in "
            "the scope."
        )
        messages.append({"role": "user", "content": review_prompt})

        try:
            resp = client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                messages=messages,
            )
            review_reply = resp.choices[0].message.content.strip()
        except Exception as e:  # noqa: BLE001
            self.emit("error", f"Review LLM call failed: {e}")
            return

        messages.append({"role": "assistant", "content": review_reply})
        trimmed = extract_python_code(review_reply)
        trimmed_lines = len(trimmed.splitlines())

        # Extract the bullet list part of the review (non-code portion)
        # and stream it as a "thinking" event so the user sees what was cut.
        from scope_creep.utils.code_extract import strip_code_fences

        prose = strip_code_fences(review_reply)
        if prose:
            self.emit("thinking", prose[:400])
        self.emit(
            "status",
            f"Review complete: {andrey_lines} → {trimmed_lines} lines",
        )

        # ---------- Execute trimmed code ----------
        self.set_phase("execute")
        self.emit("status", "Executing trimmed code...")
        if os.path.exists(self.target_csv):
            os.remove(self.target_csv)

        exec_result = subprocess.run(
            ["python", "-c", trimmed],
            capture_output=True,
            text=True,
            timeout=180,
        )
        time.sleep(2)

        if not os.path.exists(self.target_csv):
            self.emit(
                "error",
                f"Execution did not produce {self.target_csv}. "
                f"stderr: {exec_result.stderr[:400]}",
            )
            if self.scrum_master is not None:
                self.scrum_master.inbox.put({"content": Agent.task_done()})
            return

        try:
            pred_df = pd.read_csv(self.target_csv)
            pred_rate = (pred_df["Churn_Prediction"] == "Yes").mean()
            self.emit(
                "result",
                f"→ {self.target_csv} "
                f"({len(pred_df):,} rows, predicted churn {pred_rate:.1%})",
            )
        except Exception as e:  # noqa: BLE001
            self.emit("error", f"Could not re-read {self.target_csv}: {e}")

        # ---------- Phase 4: retrospective brief for Dimitar ----------
        self.set_phase("brief")
        self.emit("status", "Drafting retrospective brief for Dimitar")
        retro_prompt = (
            "The project is complete. Write a concise retrospective brief "
            "for Dimitar, the SCRUM master, who will turn it into a "
            "'Lessons Learned' slide deck. Include:\n"
            "- Project: Telco Customer Churn Prediction (logistic regression)\n"
            f"- Andrey submitted {andrey_lines} lines; final was "
            f"{trimmed_lines} lines.\n"
            "- A specific bulleted list of the out-of-scope additions you "
            "removed (use what you identified above).\n"
            "- 3-4 concrete lessons learned (scope discipline, review value, "
            "etc.).\n"
            "- A 'next steps' suggestion.\n"
            "Write it as a brief to Dimitar, ~250 words, plain prose plus "
            "bullets. Do NOT write any Python code — just the brief."
        )
        messages.append({"role": "user", "content": retro_prompt})

        try:
            resp = client.chat.completions.create(
                model=self.model,
                temperature=0.4,
                messages=messages,
            )
            brief = resp.choices[0].message.content.strip()
        except Exception as e:  # noqa: BLE001
            self.emit("error", f"Retro LLM call failed: {e}")
            return

        messages.append({"role": "assistant", "content": brief})
        self.emit("output", "Brief sent to Dimitar")
        self.scrum_master.inbox.put(
            {"content": brief, "to": self.scrum_master.agent_name}
        )

        # ---------- Phase 5: wait for Dimitar ----------
        self.set_phase("wait_scrum")
        reply = self.inbox.get()
        if reply["content"] == Agent.task_done():
            self.emit("result", "Dimitar delivered the retro deck ✓")
        else:
            self.emit("error", f"Dimitar returned: {reply['content']}")

        transcript.events = [UIEvent(**e) for e in self._events]
        transcript.messages = messages
        transcript.end_time = time.time()
        save_transcript(transcript, "transcripts")
