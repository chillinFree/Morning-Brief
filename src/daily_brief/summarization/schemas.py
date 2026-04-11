from __future__ import annotations

from pydantic import BaseModel, Field

from daily_brief.models.briefing import BriefSection


class BriefDraft(BaseModel):
    run_id: str
    subject: str
    sections: list[BriefSection]


class SectionSummary(BaseModel):
    name: str
    summary: str


class BriefSummary(BaseModel):
    overview: str = ""
    sections: list[SectionSummary] = Field(default_factory=list)
