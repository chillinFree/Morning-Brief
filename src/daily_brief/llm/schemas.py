from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class ItemEvaluation(BaseModel):
    item_id: str
    main_idea: str
    importance_score: float = Field(ge=0.0, le=1.0)
    novelty_score: float = Field(ge=0.0, le=1.0)
    category: str
    target_audience: str
    why_it_matters: str
    include: bool
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    supporting_signals: list[str] = Field(default_factory=list)

    @field_validator("main_idea", "category", "target_audience", "why_it_matters", mode="before")
    @classmethod
    def _strip_text(cls, value: object) -> str:
        return " ".join(str(value).split())


class SectionPlan(BaseModel):
    name: str
    angle: str
    item_ids: list[str] = Field(default_factory=list)
    audience_focus: str = "general"

    @field_validator("name", "angle", "audience_focus", mode="before")
    @classmethod
    def _strip_text(cls, value: object) -> str:
        return " ".join(str(value).split())


class EditorialPlan(BaseModel):
    overview: str
    sections: list[SectionPlan] = Field(default_factory=list)

    @field_validator("overview", mode="before")
    @classmethod
    def _strip_overview(cls, value: object) -> str:
        return " ".join(str(value).split())


class SectionSummary(BaseModel):
    name: str
    summary: str
    item_ids: list[str] = Field(default_factory=list)

    @field_validator("name", "summary", mode="before")
    @classmethod
    def _strip_text(cls, value: object) -> str:
        return " ".join(str(value).split())
