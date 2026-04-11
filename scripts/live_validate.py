from __future__ import annotations

import json
from datetime import datetime, timezone

import httpx

from daily_brief.config.settings import AppSettings
from daily_brief.logging.setup import configure_logging
from daily_brief.sources.arxiv import ArxivSource
from daily_brief.sources.base import SourceFetchContext
from daily_brief.sources.github import GitHubRepoUpdatesSource
from daily_brief.sources.hackernews import HackerNewsSource
from daily_brief.sources.rss import RssFeedSource


def _validate_source(name: str, source, context: SourceFetchContext) -> dict[str, object]:
    try:
        items = source.fetch(context)
        normalization_ok = all(
            item.source == name or (name == "github" and item.source == "github") for item in items
        )
        return {
            "source": name,
            "fetch_succeeded": True,
            "item_count": len(items),
            "normalization_succeeded": normalization_ok,
            "auth_or_rate_limit_issue": None,
            "sample_ids": [item.source_item_id for item in items[:5]],
        }
    except httpx.HTTPStatusError as exc:
        issue = {
            "status_code": exc.response.status_code,
            "url": str(exc.request.url),
        }
        if exc.response.status_code in {401, 403, 429}:
            issue["rate_limit_remaining"] = exc.response.headers.get("X-RateLimit-Remaining")
            issue["rate_limit_reset"] = exc.response.headers.get("X-RateLimit-Reset")
        return {
            "source": name,
            "fetch_succeeded": False,
            "item_count": 0,
            "normalization_succeeded": False,
            "auth_or_rate_limit_issue": issue,
        }
    except Exception as exc:
        return {
            "source": name,
            "fetch_succeeded": False,
            "item_count": 0,
            "normalization_succeeded": False,
            "auth_or_rate_limit_issue": {"error": type(exc).__name__, "message": str(exc)},
        }


def main() -> None:
    settings = AppSettings.load()
    configure_logging(settings.logging)
    run_id = f"live-validate-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    context = SourceFetchContext(
        run_id=run_id,
        max_items=settings.app.max_items,
        raw_payload_dir=settings.database.raw_payload_dir,
        persist_raw_payloads=settings.http.persist_raw_payloads,
    )

    sources = [
        ("arxiv", ArxivSource(settings.source.arxiv, settings.http)),
        ("github", GitHubRepoUpdatesSource(settings.source.github, settings.http)),
        ("hackernews", HackerNewsSource(settings.source.hackernews, settings.http)),
        ("rss", RssFeedSource(settings.source.rss, settings.http)),
    ]
    results = [_validate_source(name, source, context) for name, source in sources]
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
