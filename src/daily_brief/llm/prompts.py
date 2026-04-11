from __future__ import annotations

import json
from importlib.resources import files

from daily_brief.llm.schemas import ItemEvaluation, SectionPlan
from daily_brief.models.brief import BriefItem


def build_item_evaluation_prompt(item: BriefItem) -> str:
    template = _load_template("item_evaluation_prompt.txt")
    payload = {
        "item_id": item.id,
        "source": item.source,
        "source_type": item.source_type,
        "title": item.title,
        "url": str(item.url),
        "published_at": item.published_at.isoformat() if item.published_at else None,
        "summary_short": item.summary_short,
        "content_text": item.content_text,
        "topics": item.topics,
        "tags": item.tags,
        "section_hint": item.section,
        "engagement": item.engagement.model_dump(mode="json"),
        "heuristic_scores": {
            "relevance_score": item.relevance_score,
            "importance_score": item.importance_score,
            "novelty_score": item.novelty_score,
            "final_score": item.final_score,
        },
        "metadata": item.metadata,
    }
    return template.format(item_json=json.dumps(payload, indent=2, sort_keys=True))


def build_brief_planning_prompt(
    items: list[BriefItem],
    evaluations: list[ItemEvaluation],
    min_sections: int,
    max_sections: int,
) -> str:
    template = _load_template("brief_planning_prompt.txt")
    evaluation_by_id = {evaluation.item_id: evaluation for evaluation in evaluations}
    payload: list[dict[str, object]] = []
    for item in items:
        evaluation = evaluation_by_id.get(item.id)
        payload.append(
            {
                "item_id": item.id,
                "title": item.title,
                "source": item.source,
                "summary_short": item.summary_short,
                "why_it_matters": evaluation.why_it_matters if evaluation else item.why_it_matters,
                "category": evaluation.category if evaluation else item.section,
                "target_audience": evaluation.target_audience if evaluation else "general",
                "importance_score": evaluation.importance_score if evaluation else item.importance_score,
                "novelty_score": evaluation.novelty_score if evaluation else item.novelty_score,
            }
        )
    return template.format(
        min_sections=min_sections,
        max_sections=max_sections,
        items_json=json.dumps(payload, indent=2, sort_keys=True),
    )


def build_section_summary_prompt(
    section: SectionPlan,
    items: list[BriefItem],
    evaluations: list[ItemEvaluation],
) -> str:
    template = _load_template("section_summary_prompt.txt")
    evaluation_by_id = {evaluation.item_id: evaluation for evaluation in evaluations}
    payload: list[dict[str, object]] = []
    for item in items:
        evaluation = evaluation_by_id.get(item.id)
        payload.append(
            {
                "item_id": item.id,
                "title": item.title,
                "source": item.source,
                "summary_short": item.summary_short,
                "main_idea": evaluation.main_idea if evaluation else item.title,
                "why_it_matters": evaluation.why_it_matters if evaluation else item.why_it_matters,
                "importance_score": evaluation.importance_score if evaluation else item.importance_score,
                "novelty_score": evaluation.novelty_score if evaluation else item.novelty_score,
            }
        )
    return template.format(
        section_json=json.dumps(section.model_dump(mode="json"), indent=2, sort_keys=True),
        items_json=json.dumps(payload, indent=2, sort_keys=True),
    )


def _load_template(name: str) -> str:
    return files("daily_brief.llm.templates").joinpath(name).read_text(encoding="utf-8")
