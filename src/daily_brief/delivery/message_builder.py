from __future__ import annotations

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from daily_brief.config.settings import EmailConfig
from daily_brief.models.digest import Digest


def build_mime_message(digest: Digest, config: EmailConfig) -> MIMEMultipart:
    message = MIMEMultipart("alternative")
    message["Subject"] = digest.subject
    message["From"] = config.sender
    message["To"] = ", ".join(config.recipients)
    if config.reply_to:
        message["Reply-To"] = config.reply_to
    message.attach(MIMEText(digest.text_body, "plain", "utf-8"))
    message.attach(MIMEText(digest.html_body, "html", "utf-8"))
    return message
