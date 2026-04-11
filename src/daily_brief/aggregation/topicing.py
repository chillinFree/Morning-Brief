from __future__ import annotations

from daily_brief.config.settings import RankingConfig
from daily_brief.models.brief import BriefItem

TOPIC_AI_RESEARCH = "AI research"
TOPIC_OPEN_SOURCE = "Open-source / GitHub"
TOPIC_TECH_NEWS = "Tech news"
TOPIC_APPLICATIONS = "Applications / grad-related"
TOPIC_SPORTS = "Sports / NBA"
TOPIC_GENERAL = "General"


def assign_topic(item: BriefItem, config: RankingConfig) -> str:
    text = " ".join(
        [
            item.title,
            item.summary_short or "",
            item.content_text or "",
            " ".join(item.tags),
            " ".join(item.topics),
        ]
    ).lower()
    if item.source == "arxiv" or item.source_type == "paper":
        return TOPIC_AI_RESEARCH
    if item.source == "github" or item.source_type == "repo":
        return TOPIC_OPEN_SOURCE
    if _matches_any(text, config.grad_keywords):
        return TOPIC_APPLICATIONS
    if item.source == "nba" or _matches_any(text, config.sports_keywords):
        return TOPIC_SPORTS
    if item.source in {"hackernews", "rss"} or item.source_type in {"news", "post", "thread"}:
        return TOPIC_TECH_NEWS
    return TOPIC_GENERAL


def _matches_any(text: str, keywords: list[str]) -> bool:
    if not keywords:
        return False
    return any(keyword.lower() in text for keyword in keywords)
