from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from daily_brief.delivery.preview_sender import preview_digest
from daily_brief.delivery.subject import generate_subject_line
from daily_brief.models.brief import BriefItem
from daily_brief.models.briefing import BriefSection, DailyBrief
from daily_brief.rendering.renderer import render_digest


def test_generate_subject_line_uses_active_sections() -> None:
    brief = DailyBrief(
        run_id="run-1",
        subject="[Daily Brief]",
        generated_at=datetime(2026, 4, 8, 12, 0, tzinfo=UTC),
        overview="overview",
        sections=[
            BriefSection(name="AI research", summary="summary", items=[_item("Paper")]),
            BriefSection(name="Tech news", summary="summary", items=[_item("News")]),
        ],
        markdown_body="body",
    )

    subject = generate_subject_line("[Daily Brief]", brief, "America/New_York")

    assert "AI research" in subject
    assert "Tech news" in subject


def test_render_digest_and_preview_write_files(tmp_path: Path) -> None:
    brief = DailyBrief(
        run_id="run-2",
        subject="[Daily Brief] 2026-04-08",
        generated_at=datetime(2026, 4, 8, 12, 0, tzinfo=UTC),
        overview="Executive summary",
        sections=[
            BriefSection(name="AI research", summary="Research summary", items=[_item("Paper")]),
            BriefSection(
                name="Sports / NBA", summary="No notable updates in this section today.", items=[]
            ),
        ],
        markdown_body="markdown",
    )

    digest = render_digest(brief, "America/New_York")
    preview_path = preview_digest(digest, tmp_path)

    assert Path(preview_path).exists()
    html = Path(preview_path).read_text(encoding="utf-8")
    assert "Executive Summary" in html
    assert "Why it matters" in html
    assert "No notable updates in this section today." in html


def _item(title: str) -> BriefItem:
    return BriefItem(
        source="arxiv",
        source_type="paper",
        title=title,
        url="https://arxiv.org/abs/1234.5678",
        summary_short="Short summary",
        why_it_matters="Why this matters",
    )
