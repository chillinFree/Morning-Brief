from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from daily_brief.models.brief import BriefItem
from daily_brief.sources.base import BriefSource, SourceFetchContext
from daily_brief.utils.raw_capture import persist_text_payload


class FileBriefSource(BriefSource):
    name = "file"

    def __init__(self, file_path: Path) -> None:
        self._file_path = file_path

    def fetch(self, context: SourceFetchContext) -> list[BriefItem]:
        raw_text = self._file_path.read_text(encoding="utf-8")
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
