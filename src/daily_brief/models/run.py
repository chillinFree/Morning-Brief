from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import uuid4

from pydantic import BaseModel, Field


class RunRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    target_date: date = Field(default_factory=lambda: datetime.now(UTC).date())
    timezone_name: str = "UTC"
    mode: str = "manual"
    dry_run: bool = False
    force_send: bool = False
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    status: str = "running"
    item_count: int = 0
    error_message: str | None = None
