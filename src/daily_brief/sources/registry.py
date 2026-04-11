from __future__ import annotations

from daily_brief.config.settings import AppSettings
from daily_brief.sources.arxiv import ArxivSource
from daily_brief.sources.base import BriefSource
from daily_brief.sources.composite import CompositeBriefSource
from daily_brief.sources.file_source import FileBriefSource
from daily_brief.sources.github import GitHubRepoUpdatesSource
from daily_brief.sources.github_trending import GitHubTrendingReposSource
from daily_brief.sources.hackernews import HackerNewsSource
from daily_brief.sources.rss import RssFeedSource


def build_source(settings: AppSettings) -> BriefSource:
    sources: list[BriefSource] = []
    if settings.source.file.enabled:
        sources.append(FileBriefSource(settings.source.file.path))
    if settings.source.arxiv.enabled:
        sources.append(ArxivSource(settings.source.arxiv, settings.http))
    if settings.source.github.enabled:
        sources.append(GitHubRepoUpdatesSource(settings.source.github, settings.http))
    if settings.source.github_trending.enabled:
        sources.append(GitHubTrendingReposSource(settings.source.github_trending, settings.http))
    if settings.source.hackernews.enabled:
        sources.append(HackerNewsSource(settings.source.hackernews, settings.http))
    if settings.source.rss.enabled:
        sources.append(RssFeedSource(settings.source.rss, settings.http))
    return CompositeBriefSource(sources)
