from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from pydantic import BaseModel, Field

from daily_brief.models.brief import BriefItem


class BriefSection(BaseModel):
    name: str
    summary: str
    items: list[BriefItem]


class DailyBrief(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    run_id: str
    subject: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    overview: str
    sections: list[BriefSection]
    markdown_body: str
