from __future__ import annotations

import base64
from pathlib import Path

from daily_brief.config.settings import EmailConfig
from daily_brief.delivery.base import EmailSender
from daily_brief.delivery.message_builder import build_mime_message
from daily_brief.delivery.preview import write_preview
from daily_brief.models.digest import Digest

GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"


class GmailApiEmailSender(EmailSender):
    def __init__(self, config: EmailConfig, outbox_dir: Path) -> None:
        self._config = config
        self._outbox_dir = outbox_dir

    def send(self, digest: Digest) -> str:
        if self._config.preview_before_send:
            write_preview(digest, self._outbox_dir)

        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build

        creds = None
        token_file = self._config.gmail_token_file
        if token_file.exists():
            creds = Credentials.from_authorized_user_file(  # type: ignore[no-untyped-call]
                str(token_file),
                [GMAIL_SEND_SCOPE],
            )
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(self._config.gmail_credentials_file),
                    [GMAIL_SEND_SCOPE],
                )
                creds = flow.run_local_server(port=0)
            token_file.parent.mkdir(parents=True, exist_ok=True)
            token_file.write_text(creds.to_json(), encoding="utf-8")

        service = build("gmail", "v1", credentials=creds)
        mime_message = build_mime_message(digest, self._config)
        raw_message = base64.urlsafe_b64encode(mime_message.as_bytes()).decode("utf-8")
        response = (
            service.users()
            .messages()
            .send(userId=self._config.gmail_user_id, body={"raw": raw_message})
            .execute()
        )
        return str(response["id"])

    def preview(self, digest: Digest) -> str:
        return write_preview(digest, self._outbox_dir)
