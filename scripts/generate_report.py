#!/usr/bin/env python
"""Regenerate the HTML report from saved transcripts."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from scope_creep.ui.report import generate_report  # noqa: E402

if __name__ == "__main__":
    path = generate_report()
    print(f"Wrote {path}")
