from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from pathlib import Path
from typing import Any

import httpx

from daily_brief.config.settings import FeishuConfig
from daily_brief.delivery.base import EmailSender
from daily_brief.delivery.preview import write_preview
from daily_brief.models.digest import Digest

logger = logging.getLogger(__name__)

# Feishu interactive card has a content limit of ~30KB per message.
# We split into multiple messages when the payload exceeds this threshold.
_MAX_CARD_BYTES = 28_000


class FeishuSender(EmailSender):
    def __init__(self, config: FeishuConfig, outbox_dir: Path) -> None:
        self._config = config
        self._outbox_dir = outbox_dir

    def send(self, digest: Digest) -> str:
        write_preview(digest, self._outbox_dir)

        webhook_url = self._config.webhook_url
        if not webhook_url:
            raise ValueError("FEISHU_WEBHOOK_URL is not configured")

        msg_type = self._config.message_type
        if msg_type == "text":
            payload = _build_text_payload(digest, self._config.secret)
            results = [_post_webhook(webhook_url, payload)]
        else:
            # interactive card — may need multiple messages if content is long
            results = _send_card_messages(webhook_url, digest, self._config.secret)

        message_ids = [r.get("data", {}).get("message_id", "ok") for r in results]
        return ",".join(message_ids)

    def preview(self, digest: Digest) -> str:
        return write_preview(digest, self._outbox_dir)


# ---------------------------------------------------------------------------
# Public helpers (exposed for testing)
# ---------------------------------------------------------------------------


def generate_sign(secret: str) -> tuple[str, str]:
    """Generate Feishu webhook signature.

    Returns (timestamp, sign) where sign = HMAC-SHA256(secret, timestamp + newline + secret).
    """
    timestamp = str(int(time.time()))
    string_to_sign = f"{timestamp}\n{secret}"
    sign = hmac.new(
        string_to_sign.encode("utf-8"), digestmod=hashlib.sha256
    ).hexdigest()
    return timestamp, sign


def digest_to_feishu_card(digest: Digest) -> dict[str, Any]:
    """Convert a Digest to a Feishu interactive card payload (msg_body only)."""
    elements: list[dict[str, Any]] = []

    # Overview section
    if digest.overview:
        elements.append(
            {
                "tag": "markdown",
                "content": _escape_md(digest.overview),
            }
        )
        elements.append({"tag": "hr"})

    # Each BriefSection becomes a group
    for section in digest.sections:
        if not section.items:
            continue

        # Section header
        section_header = _escape_md(f"**{section.name}**")
        if section.summary:
            section_header += f"\n{_escape_md(section.summary)}"

        elements.append({"tag": "markdown", "content": section_header})

        # Items
        item_lines: list[str] = []
        for item in section.items:
            title = _escape_md(item.title)
            link = f"[{title}]({item.url})"
            line = f"- {link}"
            if item.summary_short:
                line += f"\n  {_escape_md(item.summary_short)}"
            item_lines.append(line)

        if item_lines:
            elements.append({"tag": "markdown", "content": "\n".join(item_lines)})

        elements.append({"tag": "hr"})

    # Remove trailing hr
    while elements and elements[-1].get("tag") == "hr":
        elements.pop()

    # Date footer
    elements.append(
        {
            "tag": "note",
            "elements": [
                {
                    "tag": "plain_text",
                    "content": f"Generated at {digest.generated_at.strftime('%Y-%m-%d %H:%M')} ({digest.timezone_name})",
                }
            ],
        }
    )

    card = {
        "header": {
            "title": {"tag": "plain_text", "content": digest.subject},
            "template": "blue",
        },
        "elements": elements,
    }
    return card


def digest_to_feishu_text(digest: Digest) -> str:
    """Convert a Digest to plain text for Feishu text message."""
    lines: list[str] = [digest.subject, "", digest.overview, ""]

    for section in digest.sections:
        if not section.items:
            continue
        lines.append(f"【{section.name}】")
        if section.summary:
            lines.append(section.summary)
        for item in section.items:
            lines.append(f"  - {item.title}")
            lines.append(f"    {item.url}")
            if item.summary_short:
                lines.append(f"    {item.summary_short}")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _build_text_payload(digest: Digest, secret: str | None) -> dict[str, Any]:
    text = digest_to_feishu_text(digest)
    payload: dict[str, Any] = {
        "msg_type": "text",
        "content": json.dumps({"text": text}, ensure_ascii=False),
    }
    if secret:
        timestamp, sign = generate_sign(secret)
        payload["timestamp"] = timestamp
        payload["sign"] = sign
    return payload


def _build_card_payload(card: dict[str, Any], secret: str | None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "msg_type": "interactive",
        "card": card,
    }
    if secret:
        timestamp, sign = generate_sign(secret)
        payload["timestamp"] = timestamp
        payload["sign"] = sign
    return payload


def _send_card_messages(
    webhook_url: str, digest: Digest, secret: str | None
) -> list[dict[str, Any]]:
    """Send digest as one or more card messages, splitting if content is too long."""
    full_card = digest_to_feishu_card(digest)
    full_payload = _build_card_payload(full_card, secret)

    # If it fits in one message, send directly
    payload_bytes = json.dumps(full_payload, ensure_ascii=False).encode("utf-8")
    if len(payload_bytes) <= _MAX_CARD_BYTES:
        return [_post_webhook(webhook_url, full_payload)]

    # Otherwise split sections across multiple messages
    logger.info("Feishu card payload too large (%d bytes), splitting into parts", len(payload_bytes))
    return _send_split_cards(webhook_url, digest, secret)


def _send_split_cards(
    webhook_url: str, digest: Digest, secret: str | None
) -> list[dict[str, Any]]:
    """Split digest into multiple card messages when content exceeds size limit."""
    results: list[dict[str, Any]] = []

    # First message: overview + header
    overview_elements: list[dict[str, Any]] = []
    if digest.overview:
        overview_elements.append({"tag": "markdown", "content": _escape_md(digest.overview)})

    if overview_elements:
        card = {
            "header": {
                "title": {"tag": "plain_text", "content": digest.subject},
                "template": "blue",
            },
            "elements": overview_elements,
        }
        payload = _build_card_payload(card, secret)
        results.append(_post_webhook(webhook_url, payload))

    # Then one message per section
    for section in digest.sections:
        if not section.items:
            continue
        elements: list[dict[str, Any]] = []

        section_header = _escape_md(f"**{section.name}**")
        if section.summary:
            section_header += f"\n{_escape_md(section.summary)}"
        elements.append({"tag": "markdown", "content": section_header})

        item_lines: list[str] = []
        for item in section.items:
            title = _escape_md(item.title)
            link = f"[{title}]({item.url})"
            line = f"- {link}"
            if item.summary_short:
                line += f"\n  {_escape_md(item.summary_short)}"
            item_lines.append(line)

        elements.append({"tag": "markdown", "content": "\n".join(item_lines)})

        card = {
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": f"{digest.subject} - {section.name}",
                },
                "template": "blue",
            },
            "elements": elements,
        }
        payload = _build_card_payload(card, secret)
        results.append(_post_webhook(webhook_url, payload))

    return results


def _post_webhook(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    """POST to Feishu webhook and return response JSON."""
    resp = httpx.post(
        url,
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=15.0,
    )
    body = resp.json()
    if not isinstance(body, dict):
        raise ValueError("Feishu webhook response must be a JSON object.")
    code = body.get("code", -1)
    if code != 0:
        msg = body.get("msg", "unknown error")
        raise RuntimeError(
            f"Feishu webhook error: code={code}, msg={msg}, HTTP status={resp.status_code}"
        )
    logger.info(
        "Feishu webhook sent successfully",
        extra={"status_code": resp.status_code, "response": body},
    )
    return body


def _escape_md(text: str) -> str:
    """Escape special characters that could break Feishu markdown or JSON."""
    # Replace backslash first to avoid double-escaping
    text = text.replace("\\", "\\\\")
    # Escape double quotes for JSON safety within markdown content
    text = text.replace('"', '\\"')
    return text
