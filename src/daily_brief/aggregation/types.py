from __future__ import annotations

from pydantic import BaseModel, Field

from daily_brief.models.brief import BriefItem


class DedupeCluster(BaseModel):
    representative: BriefItem
    duplicates: list[BriefItem] = Field(default_factory=list)


class AggregationResult(BaseModel):
    items: list[BriefItem]
    clusters: list[DedupeCluster]
