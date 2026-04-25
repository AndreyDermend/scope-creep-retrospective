"""Generate a self-contained HTML report from saved transcripts.

Reads `transcripts/*.json` and produces `docs/report.html` — a single file
with three columns (one per agent), a timeline of events, and expandable
LLM conversation history.

Usage:
    python -m scope_creep.ui.report
    # or
    python scripts/generate_report.py
"""

from __future__ import annotations

import html
import json
from datetime import datetime
from pathlib import Path

AGENT_COLORS = {
    "Dr. Hong":  {"accent": "#0F6E56", "bg": "#E1F5EE", "text": "#04342C"},
    "Andrey":    {"accent": "#854F0B", "bg": "#FAEEDA", "text": "#412402"},
    "Dimitar":   {"accent": "#3C3489", "bg": "#EEEDFE", "text": "#26215C"},
}

KIND_ICONS = {
    "status":   "●",
    "input":    "←",
    "thinking": "…",
    "output":   "→",
    "qa":       "QA",
    "result":   "✓",
    "error":    "✗",
}


def render_event(ev: dict) -> str:
    ts = datetime.fromtimestamp(ev["timestamp"]).strftime("%H:%M:%S")
    kind = ev["kind"]
    icon = KIND_ICONS.get(kind, "·")
    content = html.escape(ev["content"])
    return f"""<div class="event evt-{kind}">
        <span class="ts">{ts}</span>
        <span class="icon">{icon}</span>
        <span class="content">{content}</span>
    </div>"""


def render_messages(messages: list[dict]) -> str:
    if not messages:
        return "<p class='no-messages'>(No conversation recorded)</p>"
    parts = []
    for m in messages:
        role = m.get("role", "?")
        content = html.escape(m.get("content", ""))
        parts.append(
            f'<details class="msg msg-{role}">'
            f'<summary><strong>{role}</strong> '
            f'({len(m.get("content", ""))} chars)</summary>'
            f'<pre>{content}</pre></details>'
        )
    return "\n".join(parts)


def render_agent_column(transcript: dict) -> str:
    agent = transcript["agent"]
    colors = AGENT_COLORS.get(
        agent, {"accent": "#888", "bg": "#f5f5f5", "text": "#222"}
    )
    events_html = "\n".join(render_event(e) for e in transcript["events"]) or \
        '<p class="no-events">No events recorded.</p>'
    messages_html = render_messages(transcript.get("messages", []))

    duration = ""
    if transcript.get("end_time") and transcript.get("start_time"):
        d = transcript["end_time"] - transcript["start_time"]
        duration = f"{d:.1f}s"

    return f"""
    <section class="agent-col" style="
        --accent: {colors['accent']};
        --agent-bg: {colors['bg']};
        --agent-text: {colors['text']};
    ">
      <header class="agent-header">
        <h2>{html.escape(agent)}</h2>
        <div class="meta">
          <span>{transcript.get('model', '')}</span>
          <span>{duration}</span>
          <span>{len(transcript['events'])} events</span>
        </div>
      </header>
      <div class="events">
        {events_html}
      </div>
      <details class="conversation">
        <summary>Full LLM conversation ({len(transcript.get('messages', []))} turns)</summary>
        {messages_html}
      </details>
    </section>
    """


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Scope-Creep Retrospective — Run Report</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{
    font-family: -apple-system, system-ui, "Segoe UI", sans-serif;
    margin: 0;
    padding: 2rem;
    background: #fafaf8;
    color: #222;
    line-height: 1.5;
  }}
  h1 {{
    font-size: 22px;
    font-weight: 500;
    margin: 0 0 0.25rem;
  }}
  .subtitle {{
    color: #666;
    margin-bottom: 2rem;
    font-size: 14px;
  }}
  .columns {{
    display: grid;
    grid-template-columns: repeat({n_cols}, 1fr);
    gap: 16px;
  }}
  @media (max-width: 900px) {{
    .columns {{ grid-template-columns: 1fr; }}
  }}
  .agent-col {{
    background: white;
    border: 0.5px solid #ddd;
    border-top: 4px solid var(--accent);
    border-radius: 8px;
    padding: 1.25rem;
  }}
  .agent-header h2 {{
    margin: 0;
    font-size: 18px;
    color: var(--accent);
    font-weight: 500;
  }}
  .agent-header .meta {{
    display: flex;
    gap: 12px;
    font-size: 12px;
    color: #888;
    margin: 4px 0 1rem;
  }}
  .events {{
    border-top: 0.5px solid #eee;
    padding-top: 1rem;
    max-height: 500px;
    overflow-y: auto;
  }}
  .event {{
    display: grid;
    grid-template-columns: 70px 24px 1fr;
    gap: 8px;
    font-size: 13px;
    padding: 4px 0;
    border-bottom: 0.5px solid #f5f5f5;
    align-items: start;
  }}
  .event .ts {{
    color: #999;
    font-variant-numeric: tabular-nums;
  }}
  .event .icon {{
    color: var(--accent);
    font-weight: 500;
    text-align: center;
  }}
  .event .content {{
    word-wrap: break-word;
  }}
  .evt-thinking {{ font-style: italic; color: #555; }}
  .evt-thinking .content {{ background: var(--agent-bg); padding: 4px 8px; border-radius: 4px; }}
  .evt-error .content {{ color: #a32d2d; }}
  .evt-result .content {{ color: #0f6e56; font-weight: 500; }}
  .evt-output .content {{ color: var(--agent-text); }}
  .conversation {{
    margin-top: 1.5rem;
    border-top: 0.5px solid #eee;
    padding-top: 1rem;
    font-size: 13px;
  }}
  .conversation summary {{
    cursor: pointer;
    color: #666;
    font-weight: 500;
  }}
  .msg {{
    margin: 8px 0;
    padding: 8px 12px;
    background: #f8f8f6;
    border-radius: 4px;
    border-left: 3px solid #ccc;
  }}
  .msg-system {{ border-left-color: #888; }}
  .msg-user {{ border-left-color: #378add; }}
  .msg-assistant {{ border-left-color: var(--accent); }}
  .msg summary {{ cursor: pointer; font-size: 12px; color: #666; }}
  .msg pre {{
    white-space: pre-wrap;
    word-wrap: break-word;
    font-size: 12px;
    margin: 8px 0 0;
    background: white;
    padding: 8px;
    border-radius: 4px;
    max-height: 400px;
    overflow-y: auto;
  }}
  .no-events, .no-messages {{ color: #999; font-style: italic; font-size: 13px; }}
  footer {{
    margin-top: 3rem;
    font-size: 12px;
    color: #999;
    text-align: center;
  }}
</style>
</head>
<body>
<h1>Scope-Creep Retrospective — Run Report</h1>
<p class="subtitle">Generated {generated_at} from {n_transcripts} transcript(s)</p>
<div class="columns">
{columns}
</div>
<footer>
  scope-creep-retrospective · Three-agent ML pipeline with GPT-4.1-mini
</footer>
</body>
</html>
"""


def generate_report(
    transcripts_dir: str = "transcripts",
    output_file: str = "docs/report.html",
) -> str:
    """Read all transcripts in the directory and write an HTML report."""
    t_dir = Path(transcripts_dir)
    if not t_dir.exists():
        raise FileNotFoundError(f"No transcripts directory at {t_dir}")

    transcripts = []
    # preferred order — lead first, coder middle, scrum last
    order = ["dr_hong", "andrey", "dimitar"]
    seen = set()
    for slug in order:
        p = t_dir / f"{slug}.json"
        if p.exists():
            transcripts.append(json.loads(p.read_text()))
            seen.add(p.name)
    # any extras, in alphabetical order
    for p in sorted(t_dir.glob("*.json")):
        if p.name not in seen:
            transcripts.append(json.loads(p.read_text()))

    if not transcripts:
        raise RuntimeError(
            f"No JSON transcripts found in {t_dir}. Run `make run` first."
        )

    columns = "\n".join(render_agent_column(t) for t in transcripts)
    html_out = HTML_TEMPLATE.format(
        n_cols=len(transcripts),
        n_transcripts=len(transcripts),
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        columns=columns,
    )

    out_path = Path(output_file)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html_out)
    return str(out_path)


if __name__ == "__main__":
    import sys
    try:
        path = generate_report()
        print(f"Wrote report to {path}")
    except (FileNotFoundError, RuntimeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
