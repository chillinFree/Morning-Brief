from __future__ import annotations

from daily_brief.summarization.base import BriefSummarizer
from daily_brief.summarization.schemas import BriefDraft, BriefSummary, SectionSummary


class ExtractiveSummarizer(BriefSummarizer):
    def __init__(self, max_items: int = 5) -> None:
        self._max_items = max_items

    def summarize_brief(self, draft: BriefDraft) -> BriefSummary:
        sections: list[SectionSummary] = []
        overview_parts: list[str] = []
        for section in draft.sections:
            selected = section.items[: self._max_items]
            if not selected:
                summary_text = f"No notable updates in {section.name.lower()}."
            else:
                summary_text = " ".join(
                    f"{item.title}: {(item.summary_short or item.content_text or item.title)}"
                    for item in selected
                )
            sections.append(SectionSummary(name=section.name, summary=summary_text))
            if selected:
                overview_parts.append(f"{section.name} has {len(selected)} notable updates.")
        overview = " ".join(overview_parts) if overview_parts else "No notable updates today."
        return BriefSummary(overview=overview, sections=sections)
