from __future__ import annotations

from daily_brief.aggregation.dedup import deduplicate_items
from daily_brief.aggregation.grouping import group_by_topic
from daily_brief.aggregation.ranking import score_items
from daily_brief.config.settings import RankingConfig
from daily_brief.models.brief import BriefItem


def dedupe_items(items: list[BriefItem]) -> list[BriefItem]:
    return deduplicate_items(items, RankingConfig()).items


def group_by_section(items: list[BriefItem]) -> dict[str, list[BriefItem]]:
    return group_by_topic(items)


def score_items_legacy(items: list[BriefItem]) -> list[BriefItem]:
    return score_items(items, RankingConfig())
