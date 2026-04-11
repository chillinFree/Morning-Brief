from __future__ import annotations

from datetime import UTC, datetime

from daily_brief.aggregation.dedup import deduplicate_items
from daily_brief.aggregation.grouping import group_by_topic
from daily_brief.aggregation.ranking import score_items, select_items
from daily_brief.aggregation.topicing import (
    TOPIC_AI_RESEARCH,
    TOPIC_APPLICATIONS,
    TOPIC_GENERAL,
    TOPIC_OPEN_SOURCE,
    TOPIC_SPORTS,
    TOPIC_TECH_NEWS,
)
from daily_brief.config.settings import RankingConfig
from daily_brief.models.brief import BriefItem
from daily_brief.models.briefing import BriefSection, DailyBrief
from daily_brief.rendering.markdown import render_markdown_brief
from daily_brief.summarization.base import BriefSummarizer
from daily_brief.summarization.schemas import BriefDraft, BriefSummary


def build_daily_brief(
    items: list[BriefItem],
    run_id: str,
    subject: str,
    config: RankingConfig,
    summarizer: BriefSummarizer,
) -> DailyBrief:
    dedupe_result = deduplicate_items(items, config)
    scored_items = score_items(dedupe_result.items, config)
    selected_items = select_items(scored_items, config)
    grouped_items = group_by_topic(selected_items)
    ordered_topics = [
        TOPIC_AI_RESEARCH,
        TOPIC_OPEN_SOURCE,
        TOPIC_TECH_NEWS,
        TOPIC_APPLICATIONS,
        TOPIC_SPORTS,
        TOPIC_GENERAL,
    ]
    draft = BriefDraft(
        run_id=run_id,
        subject=subject,
        sections=[
            BriefSection(name=name, summary="", items=grouped_items.get(name, []))
            for name in ordered_topics
        ],
    )
    summary = summarizer.summarize_brief(draft)
    sections = _merge_sections(draft.sections, summary)
    markdown = render_markdown_brief(subject, summary.overview, sections)
    return DailyBrief(
        run_id=run_id,
        subject=subject,
        generated_at=datetime.now(UTC),
        overview=summary.overview,
        sections=sections,
        markdown_body=markdown,
    )


def _merge_sections(
    draft_sections: list[BriefSection], summary: BriefSummary
) -> list[BriefSection]:
    summaries_by_name = {section.name: section.summary for section in summary.sections}
    return [
        BriefSection(
            name=section.name, summary=summaries_by_name.get(section.name, ""), items=section.items
        )
        for section in draft_sections
    ]
