from __future__ import annotations

from datetime import UTC, datetime, timedelta

from daily_brief.aggregation.dedup import deduplicate_items, normalize_url, title_similarity
from daily_brief.aggregation.ranking import score_items
from daily_brief.config.settings import RankingConfig
from daily_brief.models.brief import BriefItem, Engagement


def _item(
    *,
    title: str,
    url: str,
    source: str = "rss",
    source_type: str = "news",
    source_item_id: str | None = None,
    summary: str | None = None,
    published_hours_ago: int = 1,
    score: float | None = None,
) -> BriefItem:
    return BriefItem(
        source=source,
        source_item_id=source_item_id,
        source_type=source_type,  # type: ignore[arg-type]
        title=title,
        url=url,
        published_at=datetime.now(UTC) - timedelta(hours=published_hours_ago),
        summary_short=summary,
        engagement=Engagement(score=score),
        metadata={"source_id": source_item_id} if source_item_id else {},
    )


def test_normalize_url_strips_tracking_params() -> None:
    assert (
        normalize_url("https://example.com/post?utm_source=x&id=1")
        == "https://example.com/post?id=1"
    )


def test_deduplicate_uses_source_ids_and_title_similarity() -> None:
    config = RankingConfig(title_similarity_threshold=0.9)
    first = _item(
        title="OpenAI releases agent evaluation guide",
        url="https://example.com/a?utm_source=feed",
        source_item_id="abc",
    )
    second = _item(
        title="OpenAI releases agent evaluation guide",
        url="https://example.com/a",
        source_item_id="abc",
    )
    third = _item(
        title="OpenAI releases agent evaluation guide today",
        url="https://other.example.com/story",
        summary="A summary",
    )
    third.section = first.section = "Tech news"
    result = deduplicate_items([first, second, third], config)

    assert len(result.items) == 1
    assert title_similarity(first.title, third.title) > 0.9


def test_score_items_prefers_recent_ai_research() -> None:
    config = RankingConfig(
        priority_keywords=["agents", "reasoning"],
        max_items_per_topic=5,
        max_total_items=10,
    )
    paper = _item(
        title="Reasoning agents with verifier loops",
        url="https://arxiv.org/abs/1234.5678",
        source="arxiv",
        source_type="paper",
        published_hours_ago=2,
        summary="A strong paper on agents.",
    )
    news = _item(
        title="General cloud pricing update",
        url="https://example.com/cloud-pricing",
        source="rss",
        source_type="news",
        published_hours_ago=24,
        summary="Routine update.",
        score=5,
    )

    ranked = score_items([news, paper], config)

    assert ranked[0].source == "arxiv"
    assert ranked[0].section == "AI research"
    assert ranked[0].final_score is not None
