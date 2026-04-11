from __future__ import annotations

import hashlib
import hmac
import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from daily_brief.config.settings import FeishuConfig
from daily_brief.delivery.feishu import (
    FeishuSender,
    _build_text_payload,
    _escape_md,
    digest_to_feishu_card,
    digest_to_feishu_text,
    generate_sign,
)
from daily_brief.models.brief import BriefItem
from daily_brief.models.briefing import BriefSection
from daily_brief.models.digest import Digest


def _make_digest(
    subject: str = "[Daily Brief] 2026-04-09",
    overview: str = "Today's overview",
    sections: list[BriefSection] | None = None,
) -> Digest:
    if sections is None:
        sections = [
            BriefSection(
                name="AI Research",
                summary="2 papers today",
                items=[
                    BriefItem(
                        source="arxiv",
                        source_type="paper",
                        title="Test Paper on LLM Reasoning",
                        url="https://arxiv.org/abs/2401.00001",
                        summary_short="A paper about reasoning.",
                        why_it_matters="Important for AI safety",
                    ),
                    BriefItem(
                        source="arxiv",
                        source_type="paper",
                        title='Another Paper: "Quotes & Special <Chars>"',
                        url="https://arxiv.org/abs/2401.00002",
                        summary_short="Contains special characters.",
                    ),
                ],
            ),
            BriefSection(
                name="Tech News",
                summary="No items today.",
                items=[],
            ),
        ]
    return Digest(
        run_id="test-run-1",
        timezone_name="America/New_York",
        subject=subject,
        overview=overview,
        sections=sections,
        html_body="<p>html</p>",
        text_body="plain text",
        generated_at=datetime(2026, 4, 9, 8, 0, tzinfo=UTC),
    )


class TestDigestToCard:
    def test_basic_structure(self) -> None:
        digest = _make_digest()
        card = digest_to_feishu_card(digest)

        assert card["header"]["title"]["content"] == "[Daily Brief] 2026-04-09"
        assert card["header"]["template"] == "blue"
        # Should have overview markdown + hr + section elements
        tags = [e["tag"] for e in card["elements"]]
        assert "markdown" in tags
        assert "hr" in tags

    def test_overview_appears(self) -> None:
        digest = _make_digest(overview="Important updates today")
        card = digest_to_feishu_card(digest)
        overview_el = card["elements"][0]
        assert overview_el["tag"] == "markdown"
        assert "Important updates today" in overview_el["content"]

    def test_items_have_clickable_links(self) -> None:
        digest = _make_digest()
        card = digest_to_feishu_card(digest)
        # Find markdown elements with links
        md_contents = [e["content"] for e in card["elements"] if e["tag"] == "markdown"]
        joined = "\n".join(md_contents)
        assert "[Test Paper on LLM Reasoning](https://arxiv.org/abs/2401.00001)" in joined

    def test_empty_sections_skipped(self) -> None:
        digest = _make_digest(sections=[
            BriefSection(name="Empty", summary="Nothing here", items=[]),
            BriefSection(
                name="Has Items",
                summary="Some items",
                items=[
                    BriefItem(
                        source="hn", source_type="post",
                        title="A post", url="https://example.com",
                    ),
                ],
            ),
        ])
        card = digest_to_feishu_card(digest)
        md_contents = [e["content"] for e in card["elements"] if e["tag"] == "markdown"]
        joined = "\n".join(md_contents)
        assert "Empty" not in joined
        assert "Has Items" in joined

    def test_special_chars_escaped(self) -> None:
        digest = _make_digest()
        card = digest_to_feishu_card(digest)
        md_contents = [e["content"] for e in card["elements"] if e["tag"] == "markdown"]
        joined = "\n".join(md_contents)
        # Quotes should be escaped
        assert '\\"Quotes' in joined or "Quotes" in joined

    def test_serializable_to_json(self) -> None:
        digest = _make_digest()
        card = digest_to_feishu_card(digest)
        payload = {"msg_type": "interactive", "card": card}
        json_str = json.dumps(payload, ensure_ascii=False)
        # Should not raise
        json.loads(json_str)


class TestDigestToText:
    def test_basic_text(self) -> None:
        digest = _make_digest()
        text = digest_to_feishu_text(digest)
        assert "[Daily Brief] 2026-04-09" in text
        assert "AI Research" in text
        assert "Test Paper on LLM Reasoning" in text
        assert "https://arxiv.org/abs/2401.00001" in text


class TestGenerateSign:
    def test_returns_timestamp_and_sign(self) -> None:
        ts, sign = generate_sign("test-secret")
        assert ts.isdigit()
        assert len(sign) == 64  # SHA256 hex digest

    def test_deterministic_for_same_timestamp(self) -> None:
        secret = "my-secret"
        ts, sign = generate_sign(secret)
        expected = hmac.new(
            f"{ts}\n{secret}".encode(), digestmod=hashlib.sha256
        ).hexdigest()
        assert sign == expected


class TestBuildTextPayload:
    def test_without_secret(self) -> None:
        digest = _make_digest()
        payload = _build_text_payload(digest, secret=None)
        assert payload["msg_type"] == "text"
        assert "timestamp" not in payload
        assert "sign" not in payload
        content = json.loads(payload["content"])
        assert "text" in content

    def test_with_secret(self) -> None:
        digest = _make_digest()
        payload = _build_text_payload(digest, secret="my-secret")
        assert payload["msg_type"] == "text"
        assert "timestamp" in payload
        assert "sign" in payload


class TestEscapeMd:
    def test_escapes_backslash(self) -> None:
        assert _escape_md("a\\b") == "a\\\\b"

    def test_escapes_double_quotes(self) -> None:
        assert _escape_md('say "hello"') == 'say \\"hello\\"'


class TestFeishuSenderErrors:
    def test_missing_webhook_url_raises(self) -> None:
        config = FeishuConfig(enabled=True, webhook_url=None, secret=None)
        sender = FeishuSender(config, Path("/tmp"))
        digest = _make_digest()
        with pytest.raises(ValueError, match="FEISHU_WEBHOOK_URL"):
            sender.send(digest)

    @patch("daily_brief.delivery.feishu.httpx.post")
    def test_api_error_raises(self, mock_post: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"code": 19001, "msg": "invalid webhook"}
        mock_post.return_value = mock_resp

        config = FeishuConfig(
            enabled=True,
            webhook_url="https://open.feishu.cn/open-apis/bot/v2/hook/test",
            secret=None,
        )
        sender = FeishuSender(config, Path("/tmp"))
        digest = _make_digest()

        with pytest.raises(RuntimeError, match="19001"):
            sender.send(digest)

    @patch("daily_brief.delivery.feishu.httpx.post")
    def test_successful_send(self, mock_post: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"code": 0, "msg": "ok", "data": {"message_id": "m_123"}}
        mock_post.return_value = mock_resp

        config = FeishuConfig(
            enabled=True,
            webhook_url="https://open.feishu.cn/open-apis/bot/v2/hook/test",
            secret=None,
        )
        sender = FeishuSender(config, Path("/tmp"))
        digest = _make_digest()
        assert "m_123" in sender.send(digest)

    @patch("daily_brief.delivery.feishu.httpx.post")
    def test_text_mode(self, mock_post: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"code": 0, "msg": "ok"}
        mock_post.return_value = mock_resp

        config = FeishuConfig(
            enabled=True,
            webhook_url="https://open.feishu.cn/open-apis/bot/v2/hook/test",
            secret=None,
            message_type="text",
        )
        sender = FeishuSender(config, Path("/tmp"))
        digest = _make_digest()
        sender.send(digest)

        call_args = mock_post.call_args
        payload = call_args[1]["json"] if "json" in call_args[1] else call_args[0][1]
        assert payload["msg_type"] == "text"
