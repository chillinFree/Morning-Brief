from __future__ import annotations

import logging

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
        return collected[: context.max_items]
