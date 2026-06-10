"""Source-diversity helpers used to keep the brief balanced across feeds.

The ranking signal naturally favours arXiv (high source-quality and AI-topic
affinity), so a pure score-ordered cut produces an arXiv-only brief even when
GitHub, Hacker News, RSS, and X items are available. These helpers interleave
items round-robin by a grouping key (typically ``source``) so every feed keeps
fair representation while still preserving the within-group ranking order.
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable, Iterable
from typing import TypeVar

from daily_brief.models.brief import BriefItem

T = TypeVar("T")


def source_channel(item: BriefItem) -> str:
    """Return a logical diversity channel for a brief item.

    Non-RSS sources map to their ``source`` name. RSS is split further so that
    X/Twitter and WeChat (公众号) feeds — which all share ``source == "rss"`` —
    get their own buckets and are not crowded out by generic news feeds.
    """

    if item.source != "rss":
        return item.source

    feed_url = ""
    fetch_meta = item.metadata.get("fetch") if isinstance(item.metadata, dict) else None
    if isinstance(fetch_meta, dict):
        feed_url = str(fetch_meta.get("feed_url", ""))
    lowered = feed_url.lower()

    if "twitter" in lowered or "nitter" in lowered or "/x/" in lowered:
        return "x"
    if ":4000/feeds" in lowered or "wewe" in lowered or "wechat" in lowered:
        return "wechat"
    return "rss"


def interleave_by_key(
    items: Iterable[T],
    key: Callable[[T], str],
    limit: int | None = None,
) -> list[T]:
    """Round-robin interleave ``items`` by ``key`` preserving per-group order.

    Items are grouped by ``key`` in first-seen order. The result takes one item
    from each group per round, so a single high-volume group cannot crowd out
    the others when ``limit`` truncates the output.
    """

    groups: OrderedDict[str, list[T]] = OrderedDict()
    for item in items:
        groups.setdefault(key(item), []).append(item)

    ordered: list[T] = []
    group_queues = list(groups.values())
    while group_queues:
        next_round: list[list[T]] = []
        for queue in group_queues:
            ordered.append(queue.pop(0))
            if limit is not None and len(ordered) >= limit:
                return ordered
            if queue:
                next_round.append(queue)
        group_queues = next_round
    return ordered
