"""Pull executable Python code out of LLM responses."""

from __future__ import annotations

import re

_PYTHON_FENCE = re.compile(r"```python\s*(.*?)```", re.DOTALL | re.IGNORECASE)
_ANY_FENCE = re.compile(r"```\s*(.*?)```", re.DOTALL)


def extract_python_code(text: str) -> str:
    """Return pure Python from a response that may wrap it in code fences.

    Handles three cases in order of preference:
    1. ```python ... ```  (explicit language tag)
    2. ```        ... ```  (generic fenced block)
    3. No fences — return the text as-is (best effort)
    """
    matches = _PYTHON_FENCE.findall(text)
    if matches:
        return "\n\n".join(m.strip() for m in matches)

    matches = _ANY_FENCE.findall(text)
    if matches:
        return "\n\n".join(m.strip() for m in matches)

    return text.strip()


def strip_code_fences(text: str) -> str:
    """Return everything OUTSIDE code fences — useful for extracting prose."""
    return re.sub(r"```.*?```", "", text, flags=re.DOTALL).strip()
