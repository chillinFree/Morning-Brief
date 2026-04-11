from __future__ import annotations

from datetime import UTC, datetime
from math import exp

from daily_brief.aggregation.explanations import explain_why_it_matters
from daily_brief.aggregation.topicing import assign_topic
from daily_brief.config.settings import RankingConfig
from daily_brief.models.brief import BriefItem

SOURCE_QUALITY = {
    "arxiv": 1.0,
    "github": 0.9,
    "hackernews": 0.75,
    "rss": 0.7,
    "gradcafe": 0.6,
    "nba": 0.55,
}

TOPIC_AFFINITY = {
    "AI research": 1.0,
    "Open-source / GitHub": 0.95,
    "Tech news": 0.8,
    "Applications / grad-related": 0.6,
    "Sports / NBA": 0.45,
    "General": 0.35,
}


def score_items(items: list[BriefItem], config: RankingConfig) -> list[BriefItem]:
    now = datetime.now(UTC)
    scored: list[BriefItem] = []
    for item in items:
        topic = assign_topic(item, config)
        item.section = topic
        recency = _recency_score(item, now)
        engagement = _engagement_score(item)
        source_quality = SOURCE_QUALITY.get(item.source, 0.5)
        keyword_affinity = _keyword_affinity(item, config)
        topic_affinity = TOPIC_AFFINITY.get(topic, TOPIC_AFFINITY["General"])
        item.relevance_score = round(keyword_affinity, 4)
        item.importance_score = round((source_quality + engagement + topic_affinity) / 3.0, 4)
        item.novelty_score = round(recency, 4)
        item.final_score = round(
            recency * config.recency_weight
            + engagement * config.engagement_weight
            + source_quality * config.source_quality_weight
            + keyword_affinity * config.keyword_affinity_weight
            + topic_affinity * config.topic_affinity_weight,
            4,
        )
        item.why_it_matters = explain_why_it_matters(item)
        scored.append(item)
    return sorted(scored, key=lambda item: item.final_score or 0.0, reverse=True)


def select_items(items: list[BriefItem], config: RankingConfig) -> list[BriefItem]:
    selected: list[BriefItem] = []
    counts_by_topic: dict[str, int] = {}
    for item in items:
        topic = item.section or "General"
        if counts_by_topic.get(topic, 0) >= config.max_items_per_topic:
            continue
        selected.append(item)
        counts_by_topic[topic] = counts_by_topic.get(topic, 0) + 1
        if len(selected) >= config.max_total_items:
            break
    return selected


def _recency_score(item: BriefItem, now: datetime) -> float:
    timestamp = item.published_at or item.fetched_at
    age_hours = max((now - timestamp).total_seconds() / 3600.0, 0.0)
    return exp(-age_hours / 72.0)


def _engagement_score(item: BriefItem) -> float:
    raw = (
        float(item.engagement.score or 0.0) / 250.0
        + float(item.engagement.comments or 0) / 150.0
        + float(item.engagement.stars or 0) / 5000.0
        + float(item.engagement.likes or 0) / 500.0
    )
    return min(raw, 1.0)


def _keyword_affinity(item: BriefItem, config: RankingConfig) -> float:
    if not config.priority_keywords:
        return 0.5
    text = " ".join(
        [
            item.title,
            item.summary_short or "",
            item.content_text or "",
            " ".join(item.tags),
            " ".join(item.topics),
        ]
    ).lower()
    matches = sum(1 for keyword in config.priority_keywords if keyword.lower() in text)
    return min(matches / max(len(config.priority_keywords) / 3.0, 1.0), 1.0)
