from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel

_STAGE_ORDER = {
    "ingest_sources": 1,
    "clean_and_dedup": 2,
    "lightweight_rank": 3,
    "llm_evaluate_items": 4,
    "select_items": 5,
    "relax_selection": 6,
    "plan_brief": 7,
    "summarize_sections": 8,
    "render_markdown": 9,
    "deliver_output": 10,
    "persist_artifacts": 11,
}


class WorkflowArtifactStore:
    def __init__(self, run_dir: Path, enabled: bool = True) -> None:
        self._run_dir = run_dir
        self._enabled = enabled
        if enabled:
            self._run_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def create(cls, root_dir: Path, run_id: str, target_date: date) -> WorkflowArtifactStore:
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        run_dir = root_dir / f"{target_date.isoformat()}_{timestamp}_{run_id}"
        return cls(run_dir=run_dir, enabled=True)

    @property
    def run_dir(self) -> Path:
        return self._run_dir

    def save_stage(self, stage: str, payload: Any) -> Path | None:
        if not self._enabled:
            return None
        order = _STAGE_ORDER.get(stage, 99)
        return self.save_json(f"{order:02d}_{stage}.json", payload)

    def save_json(self, name: str, payload: Any) -> Path | None:
        if not self._enabled:
            return None
        path = self._run_dir / name
        path.write_text(json.dumps(_to_jsonable(payload), indent=2, sort_keys=True), encoding="utf-8")
        return path

    def save_text(self, name: str, payload: str) -> Path | None:
        if not self._enabled:
            return None
        path = self._run_dir / name
        path.write_text(payload, encoding="utf-8")
        return path


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value
