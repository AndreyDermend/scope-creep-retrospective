"""Main entry point for the three-agent scope-creep pipeline.

This script:
1. Prepares training.csv and scoring.csv (if not present).
2. Spawns Andrey, Dr. Hong, and Dimitar as separate mp.Processes.
3. Runs the Rich live UI in the main process, consuming their events.
4. After all three processes join, generates the HTML report.
"""

from __future__ import annotations

import multiprocessing as mp
import os
from pathlib import Path

from scope_creep.agents import Coder, ScrumMaster, TeamLead
from scope_creep.data_prep import prepare_data
from scope_creep.roles import ANDREY, DIMITAR, DR_HONG, SCOPE_DOCUMENT
from scope_creep.ui.live import LiveUI


def run(
    model: str = "gpt-4.1-mini",
    skip_data_prep: bool = False,
    max_qa_attempts: int = 3,
) -> None:
    if not os.environ.get("OPENAI_API_KEY"):
        from getpass import getpass

        os.environ["OPENAI_API_KEY"] = getpass("Enter your OpenAI API key: ")

    # --- Prep data (unless caller says it's already there)
    if not skip_data_prep:
        if not (Path("training.csv").exists() and Path("scoring.csv").exists()):
            print("Preparing training.csv and scoring.csv ...")
            prepare_data()
            print("Data ready.")

    # --- Queues
    lead_in = mp.Queue()
    coder_in = mp.Queue()
    scrum_in = mp.Queue()
    ui_queue = mp.Queue()

    # --- Agents
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
        coder=coder,
        scrum_master=scrum,
        scope_document=SCOPE_DOCUMENT,
        target_csv="prediction.csv",
        model=model,
    )

    # --- Launch
    coder.start()
    scrum.start()
    lead.start()

    # --- Drive the UI in the main process while children work
    ui = LiveUI([DR_HONG.name, ANDREY.name, DIMITAR.name], ui_queue)
    ui.consume_until_done(timeout=600)

    coder.join(timeout=30)
    lead.join(timeout=30)
    scrum.join(timeout=30)

    # --- Generate the HTML report
    try:
        from scope_creep.ui.report import generate_report

        path = generate_report()
        print(f"\nHTML report: {path}")
    except Exception as e:  # noqa: BLE001
        print(f"\n(Report generation skipped: {e})")


if __name__ == "__main__":
    run()
