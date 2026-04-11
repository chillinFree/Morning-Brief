from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(slots=True)
class ExecutionOptions:
    mode: str = "manual"
    target_date: date | None = None
    dry_run: bool = False
    force_send: bool = False
    fetch_retries: int | None = None
    send_retries: int | None = None
