from __future__ import annotations

from collections import OrderedDict

from daily_brief.aggregation.explanations import explain_why_it_matters
from daily_brief.aggregation.topicing import TOPIC_GENERAL
from daily_brief.llm.base import WorkflowReasoner
from daily_brief.llm.schemas import EditorialPlan, ItemEvaluation, SectionPlan, SectionSummary
from daily_brief.models.brief import BriefItem


class ExtractiveWorkflowReasoner(WorkflowReasoner):
    def evaluate_item(self, item: BriefItem) -> ItemEvaluation:
        main_idea = _compact_sentence(item.summary_short or item.content_text or item.title)
        importance = _clamp(item.importance_score or item.final_score or 0.45)
        novelty = _clamp(item.novelty_score or 0.45)
        category = item.section or TOPIC_GENERAL
        audience = _audience_for_category(category)
        why_it_matters = item.why_it_matters or explain_why_it_matters(item)
        include = (item.final_score or 0.0) >= 0.38 or importance >= 0.52
        signals: list[str] = []
        if item.published_at is not None:
            signals.append("recent")
        if item.engagement.comments:
            signals.append(f"{item.engagement.comments} comments")
        if item.engagement.stars:
            signals.append(f"{item.engagement.stars} stars")
        if item.engagement.score:
            signals.append(f"HN score {int(item.engagement.score)}")
        return ItemEvaluation(
            item_id=item.id,
            main_idea=main_idea,
            importance_score=importance,
            novelty_score=novelty,
            category=category,
            target_audience=audience,
            why_it_matters=why_it_matters,
            include=include,
            confidence=0.55,
            supporting_signals=signals,
        )

    def plan_brief(
        self,
        items: list[BriefItem],
        evaluations: list[ItemEvaluation],
        min_sections: int,
        max_sections: int,
    ) -> EditorialPlan:
        if not items:
            return EditorialPlan(
                overview="No items cleared the selection threshold for this run.",
                sections=[
                    SectionPlan(
                        name="No major updates",
                        angle="The workflow ran successfully but found nothing strong enough to include.",
                        item_ids=[],
                        audience_focus="general",
                    )
                ],
            )

        evaluation_by_id = {evaluation.item_id: evaluation for evaluation in evaluations}
        grouped: OrderedDict[str, list[BriefItem]] = OrderedDict()
        for item in items:
            category = evaluation_by_id.get(item.id, ItemEvaluation(
                item_id=item.id,
                main_idea=item.title,
                importance_score=0.5,
                novelty_score=0.5,
                category=item.section or TOPIC_GENERAL,
                target_audience="general",
                why_it_matters=item.why_it_matters or item.title,
                include=True,
            )).category
            grouped.setdefault(category, []).append(item)

        sections = [
            SectionPlan(
                name=name,
                angle=f"{name} developments worth scanning first.",
                item_ids=[item.id for item in grouped_items],
                audience_focus=_section_audience(grouped_items, evaluation_by_id),
            )
            for name, grouped_items in grouped.items()
        ]

        if len(sections) > max_sections:
            sections = _merge_extra_sections(sections, max_sections)
        if len(sections) < min_sections and len(items) >= min_sections:
            midpoint = max(1, len(items) // 2)
            sections = [
                SectionPlan(
                    name="Top priorities",
                    angle="Items that look most useful to scan first.",
                    item_ids=[item.id for item in items[:midpoint]],
                    audience_focus="builders",
                ),
                SectionPlan(
                    name="Additional signals",
                    angle="Supporting items that add broader context for the morning brief.",
                    item_ids=[item.id for item in items[midpoint:]],
                    audience_focus="general",
                ),
            ]

        section_names = ", ".join(section.name for section in sections[:3])
        overview = f"Today's brief is organized around {section_names}."
        return EditorialPlan(overview=overview, sections=sections)

    def summarize_section(
        self,
        section: SectionPlan,
        items: list[BriefItem],
        evaluations: list[ItemEvaluation],
    ) -> SectionSummary:
        if not items:
            return SectionSummary(
                name=section.name,
                summary=f"No notable items were grouped under {section.name.lower()}.",
                item_ids=[],
            )
        evaluation_by_id = {evaluation.item_id: evaluation for evaluation in evaluations}
        key_points: list[str] = []
        for item in items[:2]:
            evaluation = evaluation_by_id.get(item.id)
            if evaluation is None:
                key_points.append(item.title)
                continue
            key_points.append(evaluation.main_idea)
        summary = f"{section.angle} " + " ".join(key_points)
        return SectionSummary(name=section.name, summary=summary.strip(), item_ids=[item.id for item in items])


def _audience_for_category(category: str) -> str:
    lowered = category.lower()
    if "research" in lowered:
        return "researchers and applied AI engineers"
    if "github" in lowered or "open-source" in lowered:
        return "builders maintaining AI tooling"
    if "news" in lowered:
        return "technical product and platform teams"
    return "general technical readers"


def _section_audience(
    items: list[BriefItem], evaluation_by_id: dict[str, ItemEvaluation]
) -> str:
    for item in items:
        evaluation = evaluation_by_id.get(item.id)
        if evaluation is not None:
            return evaluation.target_audience
    return "general technical readers"


def _merge_extra_sections(sections: list[SectionPlan], max_sections: int) -> list[SectionPlan]:
    kept = sections[: max_sections - 1]
    overflow = sections[max_sections - 1 :]
    merged_ids: list[str] = []
    for section in overflow:
        merged_ids.extend(section.item_ids)
    kept.append(
        SectionPlan(
            name="More signals",
            angle="Additional items that were kept for completeness but grouped into one section.",
            item_ids=merged_ids,
            audience_focus="general",
        )
    )
    return kept


def _compact_sentence(value: str) -> str:
    normalized = " ".join(value.split())
    if len(normalized) <= 220:
        return normalized
    return normalized[:217].rstrip() + "..."


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, round(float(value), 4)))
