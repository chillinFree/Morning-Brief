from __future__ import annotations

import logging
from datetime import UTC, datetime
from urllib.parse import quote_plus
from xml.etree import ElementTree as ET

from daily_brief.config.settings import ArxivSourceConfig, HttpConfig
from daily_brief.models.brief import BriefItem
from daily_brief.sources.base import BriefSource, SourceFetchContext
from daily_brief.sources.filtering import filter_items
from daily_brief.utils.http import HttpFetcher
from daily_brief.utils.raw_capture import persist_text_payload
from daily_brief.utils.urls import parse_http_url

ARXIV_API_URL = "https://export.arxiv.org/api/query"
ATOM_NS = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
logger = logging.getLogger(__name__)


def parse_arxiv_feed(
    xml_text: str,
    run_id: str,
    categories: list[str],
    keywords: list[str],
    raw_ref: str | None = None,
) -> list[BriefItem]:
    root = ET.fromstring(xml_text)
    items: list[BriefItem] = []
    for entry in root.findall("atom:entry", ATOM_NS):
        entry_id = _require_text(entry, "atom:id")
        title = _compact_whitespace(_require_text(entry, "atom:title"))
        summary = _compact_whitespace(_require_text(entry, "atom:summary"))
        authors = [node.text.strip() for node in entry.findall("atom:author/atom:name", ATOM_NS) if node.text]
        published_at = _parse_datetime(_require_text(entry, "atom:published"))
        primary_category = entry.find("arxiv:primary_category", ATOM_NS)
        category = primary_category.attrib.get("term", "") if primary_category is not None else ""

        item = BriefItem(
            run_id=run_id,
            source="arxiv",
            source_item_id=entry_id.rsplit("/", 1)[-1],
            source_type="paper",
            title=title,
            url=parse_http_url(entry_id),
            authors=authors,
            published_at=published_at,
            content_text=summary,
            summary_short=summary,
            tags=[category] if category else [],
            topics=[category] if category else [],
            metadata={
                "source_id": entry_id,
                "fetch": {"provider": "arxiv", "categories": categories},
                "arxiv": {
                    "primary_category": category,
                    "all_categories": [node.attrib.get("term", "") for node in entry.findall("atom:category", ATOM_NS)],
                },
            },
            raw_ref=raw_ref,
        )
        items.append(item)
    return filter_items(items, keywords)


class ArxivSource(BriefSource):
    name = "arxiv"

    def __init__(
        self,
        config: ArxivSourceConfig,
        http_config: HttpConfig,
        fetcher: HttpFetcher | None = None,
    ) -> None:
        self._config = config
        self._fetcher = fetcher or HttpFetcher(http_config)

    def fetch(self, context: SourceFetchContext) -> list[BriefItem]:
        category_query = " OR ".join(f"cat:{quote_plus(category)}" for category in self._config.categories)
        params = {
            "search_query": category_query,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
            "start": 0,
            "max_results": min(context.max_items, self._config.max_results),
        }
        logger.info(
            "fetching arxiv feed",
            extra={"run_id": context.run_id, "source": self.name, "stage": "fetch", "status": "started"},
        )
        xml_text = self._fetcher.get_text(ARXIV_API_URL, params=params)
        raw_ref = persist_text_payload(
            context.raw_payload_dir,
            context.persist_raw_payloads,
            self.name,
            context.run_id,
            "feed",
            xml_text,
            "xml",
        )
        items = parse_arxiv_feed(
            xml_text=xml_text,
            run_id=context.run_id,
            categories=self._config.categories,
            keywords=self._config.keywords,
            raw_ref=raw_ref,
        )[: context.max_items]
        logger.info(
            "arxiv fetch completed",
            extra={
                "run_id": context.run_id,
                "source": self.name,
                "stage": "normalize",
                "status": "completed",
                "item_count": len(items),
            },
        )
        return items


def _compact_whitespace(value: str) -> str:
    return " ".join(value.split())


def _require_text(node: ET.Element, path: str) -> str:
    target = node.find(path, ATOM_NS)
    if target is None or target.text is None:
        raise ValueError(f"Missing XML field: {path}")
    return target.text.strip()


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
