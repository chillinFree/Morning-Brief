from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from daily_brief.config.settings import HackerNewsSourceConfig, HttpConfig
from daily_brief.models.brief import BriefItem, Engagement
from daily_brief.sources.base import BriefSource, SourceFetchContext
from daily_brief.sources.filtering import filter_items
from daily_brief.utils.http import HttpFetcher
from daily_brief.utils.raw_capture import persist_json_payload
from daily_brief.utils.urls import parse_http_url

HN_API_BASE = "https://hacker-news.firebaseio.com/v0"
logger = logging.getLogger(__name__)


def parse_hn_items(
    items_json: list[dict[str, Any]],
    run_id: str,
    keywords: list[str],
    raw_refs: dict[str, str] | None = None,
) -> list[BriefItem]:
    items: list[BriefItem] = []
    for payload in items_json:
        item = _normalize_hn_item(
            payload, run_id, raw_ref=(raw_refs or {}).get(str(payload.get("id")))
        )
        if item is not None:
            items.append(item)
    return filter_items(items, keywords)


class HackerNewsSource(BriefSource):
    name = "hackernews"

    def __init__(
        self,
        config: HackerNewsSourceConfig,
        http_config: HttpConfig,
        fetcher: HttpFetcher | None = None,
    ) -> None:
        self._config = config
        self._fetcher = fetcher or HttpFetcher(http_config)

    def fetch(self, context: SourceFetchContext) -> list[BriefItem]:
        story_ids: list[int] = []
        per_list_limit = max(1, self._config.max_stories // max(len(self._config.story_lists), 1))
        for list_name in self._config.story_lists:
            endpoint = f"{HN_API_BASE}/{list_name}stories.json"
            logger.info(
                "fetching hacker news list",
                extra={
                    "run_id": context.run_id,
                    "source": self.name,
                    "stage": "fetch",
                    "status": "started",
                    "list_name": list_name,
                },
            )
            payload = self._fetcher.get_json(endpoint)
            if isinstance(payload, list):
                persist_json_payload(
                    context.raw_payload_dir,
                    context.persist_raw_payloads,
                    self.name,
                    context.run_id,
                    f"{list_name}_stories",
                    payload[:per_list_limit],
                )
                story_ids.extend(int(story_id) for story_id in payload[:per_list_limit])

        unique_story_ids = list(dict.fromkeys(story_ids))
        story_payloads: list[dict[str, Any]] = []
        raw_refs: dict[str, str] = {}
        for story_id in unique_story_ids[: self._config.max_stories]:
            item_payload = self._fetcher.get_json(f"{HN_API_BASE}/item/{story_id}.json")
            if isinstance(item_payload, dict):
                raw_ref = persist_json_payload(
                    context.raw_payload_dir,
                    context.persist_raw_payloads,
                    self.name,
                    context.run_id,
                    f"item_{story_id}",
                    item_payload,
                )
                if raw_ref is not None:
                    raw_refs[str(story_id)] = raw_ref
                story_payloads.append(item_payload)
        items = parse_hn_items(
            story_payloads, context.run_id, self._config.keywords, raw_refs=raw_refs
        )[: context.max_items]
        logger.info(
            "hacker news fetch completed",
            extra={
                "run_id": context.run_id,
                "source": self.name,
                "stage": "normalize",
                "status": "completed",
                "item_count": len(items),
            },
        )
        return items


def _normalize_hn_item(
    payload: dict[str, Any], run_id: str, raw_ref: str | None = None
) -> BriefItem | None:
    if payload.get("type") != "story":
        return None
    story_id = payload.get("id")
    title = str(payload.get("title", "")).strip()
    if not story_id or not title:
        return None
    url = payload.get("url") or f"https://news.ycombinator.com/item?id={story_id}"
    summary = payload.get("text")
    timestamp = payload.get("time")
    published_at = None
    if isinstance(timestamp, int):
        published_at = datetime.fromtimestamp(timestamp, tz=UTC)
    author = payload.get("by")
    score = payload.get("score")
    descendants = payload.get("descendants")
    return BriefItem(
        run_id=run_id,
        source="hackernews",
        source_item_id=str(story_id),
        source_type="news",
        title=title,
        url=parse_http_url(url),
        authors=[author] if author else [],
        published_at=published_at,
        content_text=summary,
        summary_short=summary,
        engagement=Engagement(
            score=float(score) if isinstance(score, int | float) else None,
            comments=descendants if isinstance(descendants, int) else None,
        ),
        tags=["hackernews"],
        topics=["tech_news"],
        metadata={
            "source_id": str(story_id),
            "fetch": {"provider": "hackernews"},
            "hackernews": {"story_id": story_id},
        },
        raw_ref=raw_ref,
    )
