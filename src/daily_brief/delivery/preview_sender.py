from __future__ import annotations

from pathlib import Path

from daily_brief.delivery.preview import write_preview
from daily_brief.models.digest import Digest


def preview_digest(digest: Digest, outbox_dir: Path) -> str:
    return write_preview(digest, outbox_dir)
