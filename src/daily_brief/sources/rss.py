from __future__ import annotations

import logging
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree as ET

from daily_brief.config.settings import HttpConfig, RssSourceConfig
from daily_brief.models.brief import BriefItem
from daily_brief.sources.base import BriefSource, SourceFetchContext
from daily_brief.sources.filtering import filter_items
from daily_brief.utils.http import HttpFetcher
from daily_brief.utils.raw_capture import persist_text_payload
from daily_brief.utils.urls import parse_http_url

ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}
logger = logging.getLogger(__name__)


def parse_rss_feed(
    xml_text: str,
    feed_url: str,
    run_id: str,
    keywords: list[str],
    raw_ref: str | None = None,
) -> list[BriefItem]:
    root = ET.fromstring(xml_text)
    if root.tag.endswith("rss"):
        items = _parse_rss_channel(root, feed_url, run_id, raw_ref)
    elif root.tag.endswith("feed"):
        items = _parse_atom_feed(root, feed_url, run_id, raw_ref)
    else:
        raise ValueError("Unsupported feed format")
    return filter_items(items, keywords)


class RssFeedSource(BriefSource):
    name = "rss"

    def __init__(
        self,
        config: RssSourceConfig,
        http_config: HttpConfig,
        fetcher: HttpFetcher | None = None,
    ) -> None:
        self._config = config
        self._fetcher = fetcher or HttpFetcher(http_config)

    def fetch(self, context: SourceFetchContext) -> list[BriefItem]:
        items: list[BriefItem] = []
        for feed_url in self._config.feeds:
            logger.info(
                "fetching rss feed",
                extra={
                    "run_id": context.run_id,
                    "source": self.name,
                    "stage": "fetch",
                    "status": "started",
                    "feed_url": feed_url,
                },
            )
            xml_text = self._fetcher.get_text(feed_url)
            raw_ref = persist_text_payload(
                context.raw_payload_dir,
                context.persist_raw_payloads,
                self.name,
                context.run_id,
                _safe_feed_name(feed_url),
                xml_text,
                "xml",
            )
            parsed_items = parse_rss_feed(xml_text, feed_url, context.run_id, self._config.keywords, raw_ref=raw_ref)
            logger.info(
                "rss feed normalized",
                extra={
                    "run_id": context.run_id,
                    "source": self.name,
                    "stage": "normalize",
                    "status": "completed",
                    "feed_url": feed_url,
                    "item_count": len(parsed_items),
                },
            )
            items.extend(parsed_items[: self._config.max_items_per_feed])
        return items[: context.max_items]


def _parse_rss_channel(root: ET.Element, feed_url: str, run_id: str, raw_ref: str | None) -> list[BriefItem]:
    items: list[BriefItem] = []
    channel = root.find("channel")
    if channel is None:
        return items
    feed_title = _node_text(channel.find("title")) or feed_url
    for item_node in channel.findall("item"):
        link = _node_text(item_node.find("link"))
        title = _node_text(item_node.find("title"))
        guid = _node_text(item_node.find("guid")) or link
        if not title or not link:
            continue
        description = _node_text(item_node.find("description"))
        author = _node_text(item_node.find("author"))
        published_at = _parse_optional_date(_node_text(item_node.find("pubDate")))
        items.append(
            BriefItem(
                run_id=run_id,
                source="rss",
                source_item_id=guid,
                source_type="news",
                title=title,
                url=parse_http_url(link),
                authors=[author] if author else [],
                published_at=published_at,
                content_text=description,
                summary_short=description,
                tags=[feed_title],
                topics=["rss"],
                metadata={
                    "source_id": guid,
                    "fetch": {"provider": "rss", "feed_url": feed_url},
                    "rss": {"feed_title": feed_title},
                },
                raw_ref=raw_ref,
            )
        )
    return items


def _parse_atom_feed(root: ET.Element, feed_url: str, run_id: str, raw_ref: str | None) -> list[BriefItem]:
    items: list[BriefItem] = []
    feed_title = _node_text(root.find("atom:title", ATOM_NS)) or feed_url
    for entry in root.findall("atom:entry", ATOM_NS):
        title = _node_text(entry.find("atom:title", ATOM_NS))
        entry_id = _node_text(entry.find("atom:id", ATOM_NS))
        link_node = entry.find("atom:link[@rel='alternate']", ATOM_NS) or entry.find("atom:link", ATOM_NS)
        link = link_node.attrib.get("href") if link_node is not None else None
        if not title or not link:
            continue
        summary = _node_text(entry.find("atom:summary", ATOM_NS)) or _node_text(entry.find("atom:content", ATOM_NS))
        author = _node_text(entry.find("atom:author/atom:name", ATOM_NS))
        updated = _node_text(entry.find("atom:updated", ATOM_NS))
        items.append(
            BriefItem(
                run_id=run_id,
                source="rss",
                source_item_id=entry_id or link,
                source_type="news",
                title=title,
                url=parse_http_url(link),
                authors=[author] if author else [],
                published_at=_parse_optional_date(updated),
                content_text=summary,
                summary_short=summary,
                tags=[feed_title],
                topics=["rss"],
                metadata={
                    "source_id": entry_id or link,
                    "fetch": {"provider": "rss", "feed_url": feed_url},
                    "rss": {"feed_title": feed_title},
                },
                raw_ref=raw_ref,
            )
        )
    return items


def _node_text(node: ET.Element | None) -> str | None:
    if node is None or node.text is None:
        return None
    text = " ".join(node.text.split())
    return text or None


def _parse_optional_date(value: str | None) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return parsedate_to_datetime(value).astimezone(UTC)


def _safe_feed_name(feed_url: str) -> str:
    return (
        feed_url.replace("https://", "")
        .replace("http://", "")
        .replace("/", "_")
        .replace("?", "_")
        .replace("&", "_")
        .replace("=", "_")
    )
