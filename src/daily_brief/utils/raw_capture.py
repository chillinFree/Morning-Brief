from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def persist_text_payload(
    root_dir: Path | None,
    enabled: bool,
    source: str,
    run_id: str,
    artifact_name: str,
    payload: str,
    suffix: str,
) -> str | None:
    if not enabled or root_dir is None:
        return None
    source_dir = root_dir / source / run_id
    source_dir.mkdir(parents=True, exist_ok=True)
    path = source_dir / f"{artifact_name}.{suffix}"
    path.write_text(payload, encoding="utf-8")
    return str(path)


def persist_json_payload(
    root_dir: Path | None,
    enabled: bool,
    source: str,
    run_id: str,
    artifact_name: str,
    payload: Any,
) -> str | None:
    if not enabled or root_dir is None:
        return None
    source_dir = root_dir / source / run_id
    source_dir.mkdir(parents=True, exist_ok=True)
    path = source_dir / f"{artifact_name}.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return str(path)
