from __future__ import annotations

from abc import ABC, abstractmethod

from daily_brief.summarization.schemas import BriefDraft, BriefSummary


class BriefSummarizer(ABC):
    @abstractmethod
    def summarize_brief(self, draft: BriefDraft) -> BriefSummary:
        raise NotImplementedError
