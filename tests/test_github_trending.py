from __future__ import annotations

from daily_brief.config.settings import GitHubTrendingSourceConfig, HttpConfig
from daily_brief.sources.base import SourceFetchContext
from daily_brief.sources.github_trending import (
    GitHubTrendingReposSource,
    parse_trending_repos,
)


def test_parse_trending_repos_normalizes_items() -> None:
    repos = [
        {
            "id": 1001,
            "full_name": "example/cool-llm-project",
            "html_url": "https://github.com/example/cool-llm-project",
            "description": "A cool new LLM project",
            "created_at": "2026-04-10T12:00:00Z",
            "stargazers_count": 150,
            "forks_count": 20,
            "language": "Python",
            "owner": {"login": "example"},
        },
        {
            "id": 1002,
            "full_name": "example/agent-framework",
            "html_url": "https://github.com/example/agent-framework",
            "description": "Multi-agent orchestration framework",
            "created_at": "2026-04-10T14:00:00Z",
            "stargazers_count": 80,
            "forks_count": 5,
            "language": "TypeScript",
            "owner": {"login": "example"},
        },
    ]

    items = parse_trending_repos(repos, run_id="run-1", keywords=[])

    assert len(items) == 2
    assert items[0].source == "github_trending"
    assert items[0].source_type == "repo"
    assert items[0].engagement.stars == 150
    assert items[0].metadata["github"]["repo"] == "example/cool-llm-project"
    assert items[0].metadata["github"]["language"] == "Python"
    assert items[1].engagement.stars == 80
    assert "trending" in items[0].tags


def test_parse_trending_repos_with_keyword_filter() -> None:
    repos = [
        {
            "id": 1001,
            "full_name": "example/cool-llm-project",
            "html_url": "https://github.com/example/cool-llm-project",
            "description": "A cool LLM project",
            "stargazers_count": 150,
            "language": "Python",
            "owner": {"login": "example"},
            "created_at": "2026-04-10T12:00:00Z",
        },
        {
            "id": 1002,
            "full_name": "example/boring-tool",
            "html_url": "https://github.com/example/boring-tool",
            "description": "A generic utility",
            "stargazers_count": 200,
            "language": "Go",
            "owner": {"login": "example"},
            "created_at": "2026-04-10T14:00:00Z",
        },
    ]

    items = parse_trending_repos(repos, run_id="run-1", keywords=["llm"])

    assert len(items) == 1
    assert "cool-llm-project" in items[0].title


def test_parse_trending_repos_skips_invalid_items() -> None:
    repos = [
        {"id": None, "full_name": "example/repo"},
        {"id": 1001, "full_name": ""},
        {
            "id": 1002,
            "full_name": "example/valid",
            "html_url": "https://github.com/example/valid",
            "stargazers_count": 10,
            "owner": {"login": "example"},
            "created_at": "2026-04-10T12:00:00Z",
        },
    ]

    items = parse_trending_repos(repos, run_id="run-1", keywords=[])

    assert len(items) == 1
    assert items[0].source_item_id == "1002"


def test_trending_source_fetch_with_fake_fetcher() -> None:
    search_response = {
        "total_count": 1,
        "items": [
            {
                "id": 2001,
                "full_name": "trending/hot-repo",
                "html_url": "https://github.com/trending/hot-repo",
                "description": "Very hot repo",
                "created_at": "2026-04-10T12:00:00Z",
                "stargazers_count": 500,
                "forks_count": 50,
                "language": "Rust",
                "owner": {"login": "trending"},
            }
        ],
    }

    class FakeFetcher:
        def __init__(self, response: object) -> None:
            self._response = response

        def get_json(self, url: str, params: dict | None = None) -> object:
            return self._response

    config = GitHubTrendingSourceConfig(enabled=True, max_results=3, keywords=[])
    http_config = HttpConfig()
    source = GitHubTrendingReposSource(config, http_config, fetcher=FakeFetcher(search_response))

    context = SourceFetchContext(
        run_id="test-run",
        max_items=10,
        raw_payload_dir="var/raw",
        persist_raw_payloads=False,
    )
    items = source.fetch(context)

    assert len(items) == 1
    assert items[0].source == "github_trending"
    assert items[0].engagement.stars == 500
    assert items[0].metadata["github"]["language"] == "Rust"


def test_trending_source_handles_empty_response() -> None:
    class FakeFetcher:
        def get_json(self, url: str, params: dict | None = None) -> object:
            return {"total_count": 0, "items": []}

    config = GitHubTrendingSourceConfig(enabled=True, max_results=3, keywords=[])
    http_config = HttpConfig()
    source = GitHubTrendingReposSource(config, http_config, fetcher=FakeFetcher())

    context = SourceFetchContext(
        run_id="test-run",
        max_items=10,
        raw_payload_dir="var/raw",
        persist_raw_payloads=False,
    )
    items = source.fetch(context)

    assert items == []
