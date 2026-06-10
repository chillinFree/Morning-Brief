"""Packaged data files shipped inside the wheel.

These let a ``pip install``ed copy of the agent run out of the box from any
directory, without needing the source checkout's ``data/`` or ``.env.example``.
"""

from __future__ import annotations

from importlib.resources import files

SAMPLE_BRIEF_ITEMS = "sample_brief_items.json"
DEFAULT_ENV = "default.env"


def read_text(name: str) -> str:
    """Return the text content of a bundled resource."""
    return (files(__package__) / name).read_text(encoding="utf-8")


def sample_brief_items_text() -> str:
    """Return the bundled demo brief items as JSON text."""
    return read_text(SAMPLE_BRIEF_ITEMS)


def default_env_text() -> str:
    """Return the bundled ``.env`` template text."""
    return read_text(DEFAULT_ENV)
