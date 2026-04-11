from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any, TypedDict

from pydantic import BaseModel, Field

from daily_brief.aggregation.types import DedupeCluster
from daily_brief.llm.schemas import EditorialPlan, ItemEvaluation, SectionSummary
from daily_brief.models.brief import BriefItem
from daily_brief.models.briefing import DailyBrief
from daily_brief.models.digest import Digest


class StageTrace(BaseModel):
    stage: str
    status: str
    started_at: datetime
    completed_at: datetime
    details: dict[str, Any] = Field(default_factory=dict)


class WorkflowError(BaseModel):
    stage: str
    error_type: str
    message: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class DeliveryResult(BaseModel):
    provider: str
    status: str
    external_id: str | None = None
    preview_path: str | None = None


class MorningBriefState(TypedDict, total=False):
    run_id: str
    target_date: date
    timezone_name: str
    mode: str
    dry_run: bool
    force_send: bool
    subject_prefix: str
    artifact_dir: str
    ingested_items: list[BriefItem]
    cleaned_items: list[BriefItem]
    rejected_items: list[BriefItem]
    dedupe_clusters: list[DedupeCluster]
    candidate_items: list[BriefItem]
    item_evaluations: list[ItemEvaluation]
    selected_items: list[BriefItem]
    rejected_evaluations: list[ItemEvaluation]
    selection_threshold: float
    needs_fallback: bool
    fallback_used: bool
    editorial_plan: EditorialPlan
    section_summaries: list[SectionSummary]
    brief: DailyBrief
    digest: Digest
    markdown_body: str
    delivery_results: list[DeliveryResult]
    stage_history: list[StageTrace]
    errors: list[WorkflowError]
