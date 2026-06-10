from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from daily_brief.config.settings import GitHubSourceConfig, HttpConfig
from daily_brief.models.brief import BriefItem, Engagement
from daily_brief.sources.base import BriefSource, SourceFetchContext
from daily_brief.sources.filtering import filter_items
from daily_brief.utils.http import HttpFetcher
from daily_brief.utils.raw_capture import persist_json_payload
from daily_brief.utils.urls import parse_http_url

GITHUB_API_BASE = "https://api.github.com"
logger = logging.getLogger(__name__)


def parse_github_events(
    repo: str,
    events: list[dict[str, Any]],
    run_id: str,
    keywords: list[str],
    raw_ref: str | None = None,
) -> list[BriefItem]:
    items: list[BriefItem] = []
    for event in events:
        event_type = event.get("type", "")
        normalized = _normalize_event(
            repo=repo,
            event=event,
            run_id=run_id,
            event_type=event_type,
            raw_ref=raw_ref,
        )
        if normalized is not None:
            items.append(normalized)
    return filter_items(items, keywords)


class GitHubRepoUpdatesSource(BriefSource):
    name = "github"

    def __init__(
        self,
        config: GitHubSourceConfig,
        http_config: HttpConfig,
        fetcher: HttpFetcher | None = None,
    ) -> None:
        headers: dict[str, str] = {"Accept": "application/vnd.github+json"}
        if config.token:
            headers["Authorization"] = f"Bearer {config.token}"
        self._config = config
        self._fetcher = fetcher or HttpFetcher(http_config, headers=headers)

    def fetch(self, context: SourceFetchContext) -> list[BriefItem]:
        items: list[BriefItem] = []
        if not self._config.tracked_repos:
            return items
        keep_per_repo = max(1, min(self._config.events_per_repo, context.max_items))
        # The /events feed is dominated by WatchEvent/ForkEvent, which we discard.
        # Fetch a wider window so release/push/issue/PR events survive normalization.
        fetch_per_repo = min(100, max(keep_per_repo * 10, 50))
        for repo in self._config.tracked_repos:
            url = f"{GITHUB_API_BASE}/repos/{repo}/events"
            logger.info(
                "fetching github repo events",
                extra={
                    "run_id": context.run_id,
                    "source": self.name,
                    "stage": "fetch",
                    "status": "started",
                    "repo": repo,
                },
            )
            events = self._fetcher.get_json(url, params={"per_page": fetch_per_repo})
            if not isinstance(events, list):
                continue
            raw_ref = persist_json_payload(
                context.raw_payload_dir,
                context.persist_raw_payloads,
                self.name,
                context.run_id,
                repo.replace("/", "_"),
                events,
            )
            repo_items = parse_github_events(
                repo, events, context.run_id, self._config.keywords, raw_ref=raw_ref
            )[:keep_per_repo]
            logger.info(
                "github repo events normalized",
                extra={
                    "run_id": context.run_id,
                    "source": self.name,
                    "stage": "normalize",
                    "status": "completed",
                    "repo": repo,
                    "item_count": len(repo_items),
                },
            )
            items.extend(repo_items)
        return items[: context.max_items]


def _normalize_event(
    repo: str,
    event: dict[str, Any],
    run_id: str,
    event_type: str,
    raw_ref: str | None = None,
) -> BriefItem | None:
    event_id = str(event.get("id", "")).strip()
    actor = event.get("actor", {}) or {}
    payload = event.get("payload", {}) or {}
    repo_name = (event.get("repo", {}) or {}).get("name", repo)
    created_at_raw = str(event.get("created_at", "")).strip()
    published_at = _parse_datetime(created_at_raw) if created_at_raw else None
    actor_name = actor.get("login")
    html_url = f"https://github.com/{repo_name}"
    summary = None
    title = None

    if event_type == "ReleaseEvent":
        release = payload.get("release", {}) or {}
        title = f"{repo_name} released {release.get('tag_name', 'a release')}"
        summary = release.get("name") or release.get("body") or "New repository release."
        html_url = release.get("html_url") or html_url
    elif event_type == "PushEvent":
        commits = payload.get("commits", []) or []
        if not commits:
            return None
        first_commit = commits[0]
        sha = first_commit.get("sha", "")[:7]
        title = f"{repo_name} received {len(commits)} new commits"
        summary = first_commit.get("message") or f"Latest commit {sha}"
        html_url = first_commit.get("url", "").replace("api.github.com/repos", "github.com").replace("/commits/", "/commit/") or html_url
    elif event_type == "IssuesEvent":
        issue = payload.get("issue", {}) or {}
        title = f"{repo_name} issue update: {issue.get('title', 'Untitled issue')}"
        summary = issue.get("body") or payload.get("action", "Issue updated")
        html_url = issue.get("html_url") or html_url
    elif event_type == "PullRequestEvent":
        pr = payload.get("pull_request", {}) or {}
        title = f"{repo_name} pull request: {pr.get('title', 'Untitled PR')}"
        summary = pr.get("body") or payload.get("action", "Pull request updated")
        html_url = pr.get("html_url") or html_url
    else:
        return None

    return BriefItem(
        run_id=run_id,
        source="github",
        source_item_id=event_id,
        source_type="repo",
        title=title,
        url=parse_http_url(html_url),
        authors=[actor_name] if actor_name else [],
        published_at=published_at,
        content_text=summary,
        summary_short=_trim_summary(summary),
        engagement=Engagement(comments=(payload.get("size") if isinstance(payload.get("size"), int) else None)),
        tags=[repo_name, event_type],
        topics=["repo_updates"],
        metadata={
            "source_id": event_id,
            "fetch": {"provider": "github", "repo": repo_name},
            "github": {
                "repo": repo_name,
                "event_type": event_type,
                "actor": actor_name,
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
