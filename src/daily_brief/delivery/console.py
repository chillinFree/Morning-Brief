from __future__ import annotations

from pathlib import Path

from daily_brief.delivery.base import EmailSender
from daily_brief.delivery.preview import write_preview
from daily_brief.models.digest import Digest


class ConsoleEmailSender(EmailSender):
    def __init__(self, outbox_dir: Path) -> None:
        self._outbox_dir = outbox_dir
        self._outbox_dir.mkdir(parents=True, exist_ok=True)

    def send(self, digest: Digest) -> str:
        html_path = self._outbox_dir / f"{digest.run_id}.html"
        text_path = self._outbox_dir / f"{digest.run_id}.txt"
        html_path.write_text(digest.html_body, encoding="utf-8")
        text_path.write_text(digest.text_body, encoding="utf-8")
        return str(html_path)

    def preview(self, digest: Digest) -> str:
        return write_preview(digest, self._outbox_dir)
