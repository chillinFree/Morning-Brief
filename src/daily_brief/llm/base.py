from __future__ import annotations

from abc import ABC, abstractmethod

from daily_brief.llm.schemas import EditorialPlan, ItemEvaluation, SectionPlan, SectionSummary
from daily_brief.models.brief import BriefItem


class WorkflowReasoner(ABC):
    @abstractmethod
    def evaluate_item(self, item: BriefItem) -> ItemEvaluation:
        raise NotImplementedError

    @abstractmethod
    def plan_brief(
        self,
        items: list[BriefItem],
        evaluations: list[ItemEvaluation],
        min_sections: int,
        max_sections: int,
    ) -> EditorialPlan:
        raise NotImplementedError

    @abstractmethod
    def summarize_section(
        self,
        section: SectionPlan,
        items: list[BriefItem],
        evaluations: list[ItemEvaluation],
    ) -> SectionSummary:
        raise NotImplementedError
