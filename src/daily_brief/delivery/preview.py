from __future__ import annotations

from pathlib import Path

from daily_brief.models.digest import Digest


def write_preview(digest: Digest, outbox_dir: Path) -> str:
    outbox_dir.mkdir(parents=True, exist_ok=True)
    html_path = outbox_dir / f"{digest.run_id}.preview.html"
    text_path = outbox_dir / f"{digest.run_id}.preview.txt"
    html_path.write_text(digest.html_body, encoding="utf-8")
    text_path.write_text(digest.text_body, encoding="utf-8")
    return str(html_path)
