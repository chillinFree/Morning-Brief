from __future__ import annotations

from daily_brief.config.settings import SummarizerConfig
from daily_brief.summarization.base import BriefSummarizer
from daily_brief.summarization.extractive import ExtractiveSummarizer
from daily_brief.summarization.openai_compatible import OpenAICompatibleSummarizer


def build_summarizer(config: SummarizerConfig) -> BriefSummarizer:
    if config.provider == "extractive":
        return ExtractiveSummarizer(max_items=config.max_items)
    if config.provider in ("openai_compatible", "glm"):
        return OpenAICompatibleSummarizer(config)
    raise ValueError(f"Unsupported summarizer provider: {config.provider}")
