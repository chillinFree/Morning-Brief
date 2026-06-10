from __future__ import annotations

import json
import logging
from pathlib import Path

from pydantic import ValidationError

from daily_brief import resources
from daily_brief.models.brief import BriefItem
from daily_brief.sources.base import BriefSource, SourceFetchContext
from daily_brief.utils.raw_capture import persist_text_payload

logger = logging.getLogger(__name__)


class FileBriefSource(BriefSource):
    name = "file"

    def __init__(self, file_path: Path) -> None:
        self._file_path = file_path

    def _load_raw_text(self) -> str:
        """Read the configured file, falling back to the bundled demo sample."""
        if self._file_path.is_file():
            return self._file_path.read_text(encoding="utf-8")
        logger.info(
            "file source input not found; using bundled demo sample",
            extra={"configured_path": str(self._file_path)},
        )
        return resources.sample_brief_items_text()

    def fetch(self, context: SourceFetchContext) -> list[BriefItem]:
        raw_text = self._load_raw_text()
        raw_items = json.loads(raw_text)
        raw_ref = persist_text_payload(
            context.raw_payload_dir,
            context.persist_raw_payloads,
            self.name,
            context.run_id,
            "input",
            raw_text,
            "json",
        )
        items: list[BriefItem] = []
        for raw_item in raw_items[: context.max_items]:
            try:
                item = BriefItem.model_validate(raw_item)
            except ValidationError as exc:
                raise ValueError(f"Invalid item in {self._file_path}: {exc}") from exc
            item.run_id = context.run_id
            item.metadata.setdefault("fetch", {})["provider"] = self.name
            item.raw_ref = raw_ref or str(self._file_path)
            items.append(item)
        return items
