from __future__ import annotations

from daily_brief.config.settings import SummarizerConfig
from daily_brief.llm.base import WorkflowReasoner
from daily_brief.llm.extractive import ExtractiveWorkflowReasoner
from daily_brief.llm.openai_compatible import OpenAICompatibleWorkflowReasoner


def build_reasoner(config: SummarizerConfig) -> WorkflowReasoner:
    if config.provider == "extractive":
        return ExtractiveWorkflowReasoner()
    if config.provider in {"openai_compatible", "glm"}:
        return OpenAICompatibleWorkflowReasoner(config)
    raise ValueError(f"Unsupported reasoning provider: {config.provider}")
