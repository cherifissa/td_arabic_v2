"""Load the project's ``.env`` file into the environment (no extra dependency).

The Hugging Face libraries read ``HF_TOKEN`` from the environment only: without this, a token
written in ``.env`` is ignored and downloads are anonymous (lower rate limit, pauses).
"""

from __future__ import annotations

import os
from pathlib import Path

from td_arabic.config import PATHS


def load_env(path: Path | None = None) -> list[str]:
    """Copy the ``KEY=value`` lines of ``.env`` into ``os.environ``.

    Variables already set in the environment win (they are not overwritten). Blank lines,
    comments and lines without ``=`` are ignored; surrounding quotes are removed.

    Args:
        path: File to read; defaults to ``<project root>/.env``.

    Returns:
        The names of the variables that were set (never their values).
    """
    path = path or PATHS.root / ".env"
    if not path.exists():
        return []
    loaded = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.removeprefix("export ").partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value
            loaded.append(key)
    return loaded
