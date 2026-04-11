from __future__ import annotations

from daily_brief.config.settings import AppSettings
from daily_brief.delivery.base import EmailSender
from daily_brief.delivery.console import ConsoleEmailSender
from daily_brief.delivery.feishu import FeishuSender
from daily_brief.delivery.gmail_api import GmailApiEmailSender
from daily_brief.delivery.smtp import SmtpEmailSender
from daily_brief.graph.context import DeliveryTarget


def build_sender(settings: AppSettings) -> EmailSender:
    if settings.email.provider == "console":
        return ConsoleEmailSender(settings.database.outbox_dir)
    if settings.email.provider == "feishu":
        return FeishuSender(settings.feishu, settings.database.outbox_dir)
    if settings.email.provider == "gmail_api":
        return GmailApiEmailSender(settings.email, settings.database.outbox_dir)
    if settings.email.provider == "smtp":
        return SmtpEmailSender(settings.email, settings.database.outbox_dir)
    raise ValueError(f"Unsupported email provider: {settings.email.provider}")


def build_senders(settings: AppSettings) -> list[DeliveryTarget]:
    primary_provider = settings.email.provider
    targets = [DeliveryTarget(provider=primary_provider, sender=build_sender(settings))]
    if settings.feishu.enabled and primary_provider not in {"console", "feishu"}:
        targets.append(
            DeliveryTarget(
                provider="feishu",
                sender=FeishuSender(settings.feishu, settings.database.outbox_dir),
            )
        )
    return targets
