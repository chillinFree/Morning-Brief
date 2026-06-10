"""Resolve where the agent reads/writes local state.

When run from a source checkout (or a directory scaffolded by ``daily-brief
init``) the agent keeps using repo-relative paths like ``var/`` and ``runs/``.
When installed with ``pip``/``pipx`` and run from an arbitrary directory, those
relative paths are instead rooted at a stable per-user home directory so the
SQLite DB, previews, and artifacts do not scatter across the filesystem.
"""

from __future__ import annotations

import os
from pathlib import Path

HOME_ENV_VAR = "DAILY_BRIEF_HOME"
SENTINEL_FILE = ".daily-brief-home"
DEFAULT_HOME = Path.home() / ".daily-brief"

# Markers that identify the current working directory as an intended workspace
# (a source checkout or an `init`-scaffolded directory).
_WORKSPACE_MARKERS = (
    ".env",
    SENTINEL_FILE,
    "data/sample_brief_items.json",
)


def _looks_like_workspace(directory: Path) -> bool:
    return any((directory / marker).exists() for marker in _WORKSPACE_MARKERS)


def daily_brief_home() -> Path:
    """Return the base directory for local state.

    Resolution order:
      1. ``$DAILY_BRIEF_HOME`` if set.
      2. The current working directory, if it looks like a workspace.
      3. ``~/.daily-brief`` (created on demand).
    """
    override = os.environ.get(HOME_ENV_VAR)
    if override:
        return Path(override).expanduser().resolve()

    cwd = Path.cwd()
    if _looks_like_workspace(cwd):
        return cwd

    return DEFAULT_HOME


def resolve_under_home(path: Path, home: Path | None = None) -> Path:
    """Root a relative ``path`` under the resolved home; leave absolute paths alone."""
    if path.is_absolute():
        return path
    base = home if home is not None else daily_brief_home()
    return base / path
