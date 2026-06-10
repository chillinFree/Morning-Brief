from __future__ import annotations

import logging

from daily_brief.aggregation.diversity import interleave_by_key, source_channel
from daily_brief.models.brief import BriefItem
from daily_brief.sources.base import BriefSource, SourceFetchContext

logger = logging.getLogger(__name__)


class CompositeBriefSource(BriefSource):
    name = "composite"

    def __init__(self, sources: list[BriefSource]) -> None:
        self._sources = sources

    def fetch(self, context: SourceFetchContext) -> list[BriefItem]:
        collected: list[BriefItem] = []
        for source in self._sources:
            try:
                collected.extend(source.fetch(context))
            except Exception:
                logger.exception(
                    "source fetch failed",
                    extra={
                        "run_id": context.run_id,
                        "source": source.name,
                        "stage": "fetch",
                        "status": "failed",
                    },
                )
        # Interleave by source so the ``max_items`` cap keeps every feed
        # represented instead of letting whichever source runs first (arXiv)
        # monopolise all the slots.
        return interleave_by_key(
            collected,
            key=source_channel,
            limit=context.max_items,
        )
