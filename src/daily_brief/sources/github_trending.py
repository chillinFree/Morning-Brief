from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from daily_brief.config.settings import GitHubTrendingSourceConfig, HttpConfig
from daily_brief.models.brief import BriefItem, Engagement
from daily_brief.sources.base import BriefSource, SourceFetchContext
from daily_brief.sources.filtering import filter_items
from daily_brief.utils.http import HttpFetcher
from daily_brief.utils.raw_capture import persist_json_payload
from daily_brief.utils.urls import parse_http_url

GITHUB_API_BASE = "https://api.github.com"
logger = logging.getLogger(__name__)


def parse_trending_repos(
    items_json: list[dict[str, Any]],
    run_id: str,
    keywords: list[str],
    raw_ref: str | None = None,
) -> list[BriefItem]:
    items: list[BriefItem] = []
    for repo in items_json:
        normalized = _normalize_trending_repo(repo, run_id, raw_ref=raw_ref)
        if normalized is not None:
            items.append(normalized)
    return filter_items(items, keywords)


class GitHubTrendingReposSource(BriefSource):
    name = "github_trending"

    def __init__(
        self,
        config: GitHubTrendingSourceConfig,
        http_config: HttpConfig,
        fetcher: HttpFetcher | None = None,
    ) -> None:
        headers: dict[str, str] = {"Accept": "application/vnd.github+json"}
        if config.token:
            headers["Authorization"] = f"Bearer {config.token}"
        self._config = config
        self._fetcher = fetcher or HttpFetcher(http_config, headers=headers)

    def fetch(self, context: SourceFetchContext) -> list[BriefItem]:
        yesterday = (datetime.now(UTC) - timedelta(days=1)).strftime("%Y-%m-%d")
        url = f"{GITHUB_API_BASE}/search/repositories"
        params = {
            "q": f"created:>{yesterday}",
            "sort": "stars",
            "order": "desc",
            "per_page": self._config.max_results,
        }
        logger.info(
            "fetching github trending repos",
            extra={
                "run_id": context.run_id,
                "source": self.name,
                "stage": "fetch",
                "status": "started",
            },
        )
        data = self._fetcher.get_json(url, params=params)
        if not isinstance(data, dict) or "items" not in data:
            logger.warning(
                "github trending response missing 'items'",
                extra={
                    "run_id": context.run_id,
                    "source": self.name,
                    "stage": "fetch",
                    "status": "unexpected_response",
                },
            )
            return []
        raw_ref = persist_json_payload(
            context.raw_payload_dir,
            context.persist_raw_payloads,
            self.name,
            context.run_id,
            "trending_repos",
            data,
        )
        items = parse_trending_repos(
            data["items"], context.run_id, self._config.keywords, raw_ref=raw_ref
        )
        logger.info(
            "github trending repos normalized",
            extra={
                "run_id": context.run_id,
                "source": self.name,
                "stage": "normalize",
                "status": "completed",
                "item_count": len(items),
            },
        )
        return items[: context.max_items]


def _normalize_trending_repo(
    payload: dict[str, Any],
    run_id: str,
    raw_ref: str | None = None,
) -> BriefItem | None:
    repo_id = payload.get("id")
    if not repo_id:
        return None
    full_name = str(payload.get("full_name", "")).strip()
    if not full_name:
        return None
    description = payload.get("description") or ""
    html_url = payload.get("html_url") or f"https://github.com/{full_name}"
    owner = (payload.get("owner") or {}).get("login")
    stargazers_count = payload.get("stargazers_count")
    forks_count = payload.get("forks_count")
    language = payload.get("language")
    created_at_raw = str(payload.get("created_at", "")).strip()
    published_at = _parse_datetime(created_at_raw) if created_at_raw else None

    title = f"{full_name}: {_trim_summary(description) or 'No description'}"
    return BriefItem(
        run_id=run_id,
        source="github_trending",
        source_item_id=str(repo_id),
        source_type="repo",
        title=title[:300],
        url=parse_http_url(html_url),
        authors=[owner] if owner else [],
        published_at=published_at,
        content_text=description,
        summary_short=_trim_summary(description),
        engagement=Engagement(
            stars=stargazers_count if isinstance(stargazers_count, int) else None,
        ),
        tags=["github", "trending"] + ([language] if language else []),
        topics=["trending_repos"],
        metadata={
            "source_id": str(repo_id),
            "fetch": {"provider": "github", "endpoint": "search/repositories"},
            "github": {
                "repo": full_name,
                "stars": stargazers_count,
                "language": language,
                "forks": forks_count,
                "created_at": created_at_raw or None,
            },
        },
        raw_ref=raw_ref,
    )


def _trim_summary(summary: str | None) -> str | None:
    if summary is None:
        return None
    return " ".join(summary.split())[:400]


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
