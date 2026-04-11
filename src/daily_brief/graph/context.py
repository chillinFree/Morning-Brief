from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from daily_brief.config.settings import AppSettings
from daily_brief.delivery.base import EmailSender
from daily_brief.graph.artifacts import WorkflowArtifactStore
from daily_brief.llm.base import WorkflowReasoner
from daily_brief.sources.base import BriefSource


@dataclass(frozen=True, slots=True)
class DeliveryTarget:
    provider: str
    sender: EmailSender


@dataclass(slots=True)
class WorkflowDependencies:
    settings: AppSettings
    source: BriefSource
    reasoner: WorkflowReasoner
    senders: list[DeliveryTarget]
    artifact_store: WorkflowArtifactStore
    checkpointer: Any | None = None
