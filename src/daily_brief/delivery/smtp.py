from __future__ import annotations

import smtplib
from pathlib import Path

from daily_brief.config.settings import EmailConfig
from daily_brief.delivery.base import EmailSender
from daily_brief.delivery.message_builder import build_mime_message
from daily_brief.delivery.preview import write_preview
from daily_brief.models.digest import Digest


class SmtpEmailSender(EmailSender):
    def __init__(self, config: EmailConfig, outbox_dir: Path) -> None:
        self._config = config
        self._outbox_dir = outbox_dir

    def send(self, digest: Digest) -> str:
        if (
            not self._config.smtp_host
            or not self._config.smtp_username
            or not self._config.smtp_password
        ):
            raise ValueError(
                "SMTP_HOST, SMTP_USERNAME, and SMTP_PASSWORD are required for SMTP delivery."
            )
        if self._config.preview_before_send:
            write_preview(digest, self._outbox_dir)
        message = build_mime_message(digest, self._config)
        with smtplib.SMTP(self._config.smtp_host, self._config.smtp_port) as client:
            if self._config.smtp_use_tls:
                client.starttls()
            client.login(self._config.smtp_username, self._config.smtp_password)
            client.sendmail(self._config.sender, self._config.recipients, message.as_string())
        return "smtp-sent"

    def preview(self, digest: Digest) -> str:
        return write_preview(digest, self._outbox_dir)
