from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from pydantic import BaseModel, Field

from daily_brief.models.briefing import BriefSection


class Digest(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    run_id: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    timezone_name: str = "UTC"
    subject: str
    overview: str
    sections: list[BriefSection]
    html_body: str
    text_body: str
