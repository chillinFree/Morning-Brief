from __future__ import annotations

import json
from pathlib import Path

from daily_brief.config.settings import (
    ArxivSourceConfig,
    GitHubSourceConfig,
    HackerNewsSourceConfig,
    HttpConfig,
    RssSourceConfig,
)
from daily_brief.sources.arxiv import ARXIV_API_URL, ArxivSource
from daily_brief.sources.base import SourceFetchContext
from daily_brief.sources.github import GITHUB_API_BASE, GitHubRepoUpdatesSource
from daily_brief.sources.hackernews import HN_API_BASE, HackerNewsSource
from daily_brief.sources.rss import RssFeedSource


class FakeFetcher:
    def __init__(
        self,
        text_responses: dict[str, str] | None = None,
        json_responses: dict[str, object] | None = None,
    ) -> None:
        self._text_responses = text_responses or {}
        self._json_responses = json_responses or {}

    def get_text(self, url: str, params: dict[str, object] | None = None) -> str:
        return self._text_responses[url]

    def get_json(self, url: str, params: dict[str, object] | None = None) -> object:
        return self._json_responses[url]


FIXTURES = Path("tests/fixtures")


def test_arxiv_source_fetch_from_recorded_fixture(tmp_path: Path) -> None:
    fetcher = FakeFetcher(
        text_responses={ARXIV_API_URL: (FIXTURES / "arxiv_live.xml").read_text(encoding="utf-8")}
    )
    source = ArxivSource(
        ArxivSourceConfig(enabled=True, categories=["cs.AI"], keywords=["agent"], max_results=5),
        HttpConfig(),
        fetcher=fetcher,
    )

    items = source.fetch(
        SourceFetchContext(
            run_id="arxiv-live", max_items=5, raw_payload_dir=tmp_path, persist_raw_payloads=True
        )
    )

    assert len(items) == 1
    assert items[0].raw_ref is not None
    assert "arxiv" in items[0].raw_ref


def test_github_source_fetch_from_recorded_fixture(tmp_path: Path) -> None:
    repo = "example/repo"
    fetcher = FakeFetcher(
        json_responses={
            f"{GITHUB_API_BASE}/repos/{repo}/events": json.loads(
                (FIXTURES / "github_events.json").read_text(encoding="utf-8")
            )
        }
    )
    source = GitHubRepoUpdatesSource(
        GitHubSourceConfig(
            enabled=True, tracked_repos=[repo], keywords=["release", "tracing"], events_per_repo=5
        ),
        HttpConfig(),
        fetcher=fetcher,
    )

    items = source.fetch(
        SourceFetchContext(
            run_id="github-live", max_items=5, raw_payload_dir=tmp_path, persist_raw_payloads=True
        )
    )

    assert len(items) == 2
    assert all(item.raw_ref for item in items)


def test_hackernews_source_fetch_from_recorded_fixture(tmp_path: Path) -> None:
    fetcher = FakeFetcher(
        json_responses={
            f"{HN_API_BASE}/topstories.json": json.loads(
                (FIXTURES / "hn_topstories.json").read_text(encoding="utf-8")
            ),
            f"{HN_API_BASE}/item/101.json": json.loads(
                (FIXTURES / "hn_item_101.json").read_text(encoding="utf-8")
            ),
            f"{HN_API_BASE}/item/102.json": json.loads(
                (FIXTURES / "hn_item_102.json").read_text(encoding="utf-8")
            ),
        }
    )
    source = HackerNewsSource(
        HackerNewsSourceConfig(
            enabled=True, story_lists=["top"], keywords=["agent"], max_stories=5
        ),
        HttpConfig(),
        fetcher=fetcher,
    )

    items = source.fetch(
        SourceFetchContext(
            run_id="hn-live", max_items=5, raw_payload_dir=tmp_path, persist_raw_payloads=True
        )
    )

    assert len(items) == 1
    assert items[0].source_item_id == "101"
    assert items[0].raw_ref is not None


def test_rss_source_fetch_from_recorded_fixture(tmp_path: Path) -> None:
    feed_url = "https://example.com/feed.xml"
    fetcher = FakeFetcher(
        text_responses={feed_url: (FIXTURES / "rss_feed.xml").read_text(encoding="utf-8")}
    )
    source = RssFeedSource(
        RssSourceConfig(enabled=True, feeds=[feed_url], keywords=["llm"], max_items_per_feed=5),
        HttpConfig(),
        fetcher=fetcher,
    )

    items = source.fetch(
        SourceFetchContext(
            run_id="rss-live", max_items=5, raw_payload_dir=tmp_path, persist_raw_payloads=True
        )
    )

    assert len(items) == 1
    assert items[0].raw_ref is not None
