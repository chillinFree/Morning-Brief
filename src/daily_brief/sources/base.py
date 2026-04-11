from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from daily_brief.models.brief import BriefItem


@dataclass(slots=True)
class SourceFetchContext:
    run_id: str
    max_items: int
    raw_payload_dir: Path | None = None
    persist_raw_payloads: bool = False


class BriefSource(ABC):
    name: str

    @abstractmethod
    def fetch(self, context: SourceFetchContext) -> list[BriefItem]:
        raise NotImplementedError
