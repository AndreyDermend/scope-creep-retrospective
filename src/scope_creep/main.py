"""Main entry point for the three-agent scope-creep pipeline.

Two UI modes:
- terminal:  Rich live UI in the main process (default for `make run`)
- web:       FastAPI server on localhost; browser opens to a live dashboard

The agents themselves are identical in both modes — they emit UIEvents to
a shared mp.Queue. The mode just decides who consumes that queue.
"""

from __future__ import annotations

import argparse
import multiprocessing as mp
import os
import threading
import time
from pathlib import Path

from scope_creep.agents import Coder, ScrumMaster, TeamLead
from scope_creep.data_prep import prepare_data
from scope_creep.roles import ANDREY, DIMITAR, DR_HONG, SCOPE_DOCUMENT

# Use spawn on every platform so child processes start clean and only
# mp.Queue / mp.Event objects (not Process handles) cross the boundary.
# This is already the macOS default but being explicit prevents surprises.
_ctx = mp.get_context("spawn")


def _ensure_data() -> None:
    if not (Path("training.csv").exists() and Path("scoring.csv").exists()):
        print("Preparing training.csv and scoring.csv ...")
        prepare_data()
        print("Data ready.")


def _ensure_api_key() -> None:
    if not os.environ.get("OPENAI_API_KEY"):
        from getpass import getpass

        os.environ["OPENAI_API_KEY"] = getpass("Enter your OpenAI API key: ")


def _build_agents(
    ui_queue: mp.Queue, model: str, max_qa_attempts: int
) -> tuple[Coder, ScrumMaster, TeamLead, mp.Queue, mp.Queue, mp.Queue]:
    lead_in = _ctx.Queue()
    coder_in = _ctx.Queue()
    scrum_in = _ctx.Queue()

    coder = Coder(
        name=ANDREY.name,
        system_prompt=ANDREY.system_prompt,
        inbox=coder_in,
        ui_queue=ui_queue,
        model=model,
        temperature=0.5,
    )
    coder.set_outbox(lead_in)

    scrum = ScrumMaster(
        name=DIMITAR.name,
        system_prompt=DIMITAR.system_prompt,
        inbox=scrum_in,
        ui_queue=ui_queue,
        target_file="presentation.pptx",
        required_topics=["scope", "lesson", "churn"],
        min_slides=5,
        max_attempts=max_qa_attempts,
        model=model,
    )
    scrum.set_outbox(lead_in)

    lead = TeamLead(
        name=DR_HONG.name,
        system_prompt=DR_HONG.system_prompt,
        inbox=lead_in,
        ui_queue=ui_queue,
        coder_inbox=coder_in,
        scrum_inbox=scrum_in,
        coder_name=ANDREY.name,
        scrum_name=DIMITAR.name,
        scope_document=SCOPE_DOCUMENT,
        target_csv="prediction.csv",
        model=model,
    )
    return coder, scrum, lead, lead_in, coder_in, scrum_in


def _generate_report() -> None:
    try:
        from scope_creep.ui.report import generate_report

        path = generate_report()
        print(f"\nHTML report: {path}")
    except Exception as e:  # noqa: BLE001
        print(f"\n(Report generation skipped: {e})")


# ----------------------------------------------------------------------
# Terminal mode (Rich)
# ----------------------------------------------------------------------
def run_terminal(model: str, max_qa_attempts: int) -> None:
    from scope_creep.ui.live import LiveUI

    _ensure_api_key()
    _ensure_data()

    ui_queue = _ctx.Queue()
    coder, scrum, lead, *_ = _build_agents(ui_queue, model, max_qa_attempts)

    coder.start()
    scrum.start()
    lead.start()

    ui = LiveUI([DR_HONG.name, ANDREY.name, DIMITAR.name], ui_queue)
    ui.consume_until_done(timeout=600)

    coder.join(timeout=30)
    lead.join(timeout=30)
    scrum.join(timeout=30)

    _generate_report()


# ----------------------------------------------------------------------
# Web mode (FastAPI + SSE)
# ----------------------------------------------------------------------
def run_web(
    model: str,
    max_qa_attempts: int,
    host: str = "127.0.0.1",
    port: int = 8000,
) -> None:
    """Run agents in background, serve the dashboard in the foreground.

    The FastAPI server runs on the main thread so Ctrl-C cleanly shuts
    everything down. Agents are mp.Processes spawned in a worker thread
    so they kick off after uvicorn is up and ready to receive events.
    """
    from scope_creep.web.server import serve

    _ensure_api_key()
    _ensure_data()

    ui_queue = _ctx.Queue()
    state: dict = {
        "started_at": None,
        "done": False,
        "event_count": 0,
        "agents": [DR_HONG.name, ANDREY.name, DIMITAR.name],
        "backlog": [],
    }

    coder, scrum, lead, *_ = _build_agents(ui_queue, model, max_qa_attempts)

    def _run_pipeline() -> None:
        # Tiny delay so the browser has time to connect before agents start
        # talking. Without this, the first few events go into the backlog
        # rather than streaming live (which is fine — the SSE endpoint
        # replays the backlog — but it looks better when events stream in
        # rather than all appearing at once).
        time.sleep(2)
        state["started_at"] = time.time()

        coder.start()
        scrum.start()
        lead.start()

        coder.join(timeout=600)
        lead.join(timeout=600)
        scrum.join(timeout=600)

        # Drain a brief moment so trailing events make it through
        time.sleep(1)
        state["done"] = True
        _generate_report()

    worker = threading.Thread(target=_run_pipeline, daemon=True)
    worker.start()

    print("\n  ◐  scope-creep control room")
    print(f"      open http://{host}:{port}  in your browser\n")
    print("      (Ctrl-C to stop)\n")

    try:
        serve(ui_queue, state, host=host, port=port)
    except KeyboardInterrupt:
        print("\nshutting down...")
        for p in [coder, scrum, lead]:
            if p.is_alive():
                p.terminate()


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------
def run(
    model: str = "gpt-4.1-mini",
    skip_data_prep: bool = False,
    max_qa_attempts: int = 3,
    ui: str = "terminal",
    host: str = "127.0.0.1",
    port: int = 8000,
) -> None:
    """Entry-point used by `python -m scope_creep` and the console script."""
    if ui == "web":
        run_web(model, max_qa_attempts, host=host, port=port)
    else:
        run_terminal(model, max_qa_attempts)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="scope-creep",
        description="Three-agent scope-creep retrospective pipeline.",
    )
    p.add_argument(
        "--ui",
        choices=("terminal", "web"),
        default="terminal",
        help="UI mode (default: terminal)",
    )
    p.add_argument("--model", default="gpt-4.1-mini")
    p.add_argument("--max-qa-attempts", type=int, default=3)
    p.add_argument("--host", default="127.0.0.1", help="Web mode: host")
    p.add_argument("--port", type=int, default=8000, help="Web mode: port")
    return p.parse_args()


def main_cli() -> None:
    args = _parse_args()
    run(
        model=args.model,
        max_qa_attempts=args.max_qa_attempts,
        ui=args.ui,
        host=args.host,
        port=args.port,
    )


if __name__ == "__main__":
    main_cli()
