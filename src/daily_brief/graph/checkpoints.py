from __future__ import annotations

import pickle
from collections import defaultdict
from collections.abc import Sequence
from datetime import date, datetime
from pathlib import Path
from threading import RLock
from typing import Any

from langgraph.checkpoint.memory import InMemorySaver
from pydantic import BaseModel


class LocalFileCheckpointSaver(InMemorySaver):
    """Persist LangGraph checkpoints to a local pickle file.

    This keeps the implementation practical for a local-first course demo while
    still using LangGraph's real checkpoint interface. The saver mirrors the
    in-memory implementation but flushes the checkpoint store to disk after each
    checkpoint/write update so runs are inspectable and resumable between process
    restarts.
    """

    def __init__(self, path: Path) -> None:
        super().__init__()
        self._path = path
        self._lock = RLock()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._load()

    @property
    def path(self) -> Path:
        return self._path

    def checkpoint_count(self) -> int:
        return sum(
            len(checkpoints)
            for namespaces in self.storage.values()
            for checkpoints in namespaces.values()
        )

    def put(
        self,
        config: Any,
        checkpoint: Any,
        metadata: Any,
        new_versions: Any,
    ) -> Any:
        result = super().put(
            config,
            _checkpoint_safe(checkpoint),
            _checkpoint_safe(metadata),
            _checkpoint_safe(new_versions),
        )
        self._persist()
        return result

    def put_writes(
        self,
        config: Any,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        safe_writes = [(channel, _checkpoint_safe(value)) for channel, value in writes]
        super().put_writes(config, safe_writes, task_id, task_path)
        self._persist()

    def _load(self) -> None:
        if not self._path.exists():
            return
        with self._lock:
            payload = pickle.loads(self._path.read_bytes())
            self.storage = _restore_storage(payload.get("storage", {}))
            self.writes = _restore_defaultdict(payload.get("writes", {}))
            self.blobs = dict(payload.get("blobs", {}))

    def _persist(self) -> None:
        payload = {
            "storage": _plain_nested_dict(self.storage),
            "writes": _plain_nested_dict(self.writes),
            "blobs": dict(self.blobs),
        }
        temp_path = self._path.with_suffix(self._path.suffix + ".tmp")
        with self._lock:
            temp_path.write_bytes(pickle.dumps(payload))
            temp_path.replace(self._path)


def _plain_nested_dict(value: Any) -> Any:
    if isinstance(value, defaultdict):
        return {key: _plain_nested_dict(item) for key, item in value.items()}
    if isinstance(value, dict):
        return {key: _plain_nested_dict(item) for key, item in value.items()}
    return value


def _restore_storage(
    value: dict[str, dict[str, dict[str, tuple[tuple[str, bytes], tuple[str, bytes], str | None]]]]
) -> defaultdict[str, dict[str, dict[str, tuple[tuple[str, bytes], tuple[str, bytes], str | None]]]]:
    storage: defaultdict[
        str,
        dict[str, dict[str, tuple[tuple[str, bytes], tuple[str, bytes], str | None]]],
    ] = defaultdict(lambda: defaultdict(dict))
    for thread_id, namespaces in value.items():
        namespace_map: defaultdict[
            str, dict[str, tuple[tuple[str, bytes], tuple[str, bytes], str | None]]
        ] = defaultdict(dict)
        for checkpoint_ns, checkpoints in namespaces.items():
            namespace_map[checkpoint_ns] = dict(checkpoints)
        storage[thread_id] = namespace_map
    return storage


def _restore_defaultdict(
    value: dict[Any, dict[Any, Any]]
) -> defaultdict[Any, dict[Any, Any]]:
    restored: defaultdict[Any, dict[Any, Any]] = defaultdict(dict)
    for key, inner in value.items():
        restored[key] = dict(inner)
    return restored


def _checkpoint_safe(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {key: _checkpoint_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_checkpoint_safe(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_checkpoint_safe(item) for item in value)
    if isinstance(value, set):
        return sorted(_checkpoint_safe(item) for item in value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value
