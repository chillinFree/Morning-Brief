from __future__ import annotations

from daily_brief.aggregation.diversity import interleave_by_key, source_channel
from daily_brief.models.brief import BriefItem
from daily_brief.sources.base import SourceFetchContext
from daily_brief.sources.composite import CompositeBriefSource


def _item(source: str, title: str, feed_url: str | None = None) -> BriefItem:
    metadata: dict[str, object] = {}
    if feed_url is not None:
        metadata = {"fetch": {"provider": "rss", "feed_url": feed_url}}
    return BriefItem(
        source=source,
        source_type="news",
        title=title,
        url=f"https://example.com/{title.replace(' ', '-')}",
        metadata=metadata,
    )


def test_interleave_round_robins_across_groups() -> None:
    items = ["a1", "a2", "a3", "b1", "c1", "c2"]
    ordered = interleave_by_key(items, key=lambda value: value[0])
    # One from each group per round, preserving within-group order.
    assert ordered == ["a1", "b1", "c1", "a2", "c2", "a3"]


def test_interleave_limit_keeps_every_group_represented() -> None:
    items = ["a1", "a2", "a3", "a4", "b1", "c1"]
    ordered = interleave_by_key(items, key=lambda value: value[0], limit=3)
    assert ordered == ["a1", "b1", "c1"]


def test_source_channel_splits_rss_into_x_and_wechat() -> None:
    arxiv = _item("arxiv", "A paper")
    github = _item("github", "A repo")
    x_tweet = _item("rss", "A tweet", feed_url="http://localhost:1200/twitter/user/OpenAI")
    wechat = _item("rss", "A WeChat article", feed_url="http://localhost:4000/feeds/all.rss")
    news = _item("rss", "A news story", feed_url="https://techcrunch.com/feed/")

    assert source_channel(arxiv) == "arxiv"
    assert source_channel(github) == "github"
    assert source_channel(x_tweet) == "x"
    assert source_channel(wechat) == "wechat"
    assert source_channel(news) == "rss"


class _StubSource:
    def __init__(self, name: str, items: list[BriefItem]) -> None:
        self.name = name
        self._items = items

    def fetch(self, context: SourceFetchContext) -> list[BriefItem]:
        return self._items


def test_composite_cap_keeps_multiple_sources() -> None:
    arxiv_items = [_item("arxiv", f"paper {idx}") for idx in range(10)]
    github_items = [_item("github", f"repo {idx}") for idx in range(5)]
    x_items = [
        _item("rss", f"tweet {idx}", feed_url="http://localhost:1200/twitter/user/sama")
        for idx in range(5)
    ]
    composite = CompositeBriefSource(
        [
            _StubSource("arxiv", arxiv_items),  # type: ignore[list-item]
            _StubSource("github", github_items),  # type: ignore[list-item]
            _StubSource("rss", x_items),  # type: ignore[list-item]
        ]
    )

    fetched = composite.fetch(SourceFetchContext(run_id="run", max_items=6))

    channels = {source_channel(item) for item in fetched}
    # The old naive cap would have returned arXiv-only; now every feed survives.
    assert channels == {"arxiv", "github", "x"}
    assert len(fetched) == 6
