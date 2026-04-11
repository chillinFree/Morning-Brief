from __future__ import annotations

import sqlite3
from pathlib import Path

from daily_brief.config.settings import AppSettings
from daily_brief.orchestration.options import ExecutionOptions
from daily_brief.orchestration.pipeline import DailyBriefPipeline


def test_pipeline_persists_run_digest_and_delivery(tmp_path: Path) -> None:
    db_path = tmp_path / "brief.db"
    raw_dir = tmp_path / "raw"
    outbox_dir = tmp_path / "outbox"
    source_path = tmp_path / "sample.json"
    source_path.write_text(
        """[
          {
            "source": "arxiv",
            "source_type": "paper",
            "title": "A test paper",
            "url": "https://arxiv.org/abs/1234.5678",
            "authors": ["Test Author"],
            "summary_short": "A short test summary."
          },
          {
            "source": "rss",
            "source_type": "news",
            "title": "A second test item",
            "url": "https://example.com/test-news",
            "summary_short": "Another short summary."
          }
        ]""",
        encoding="utf-8",
    )

    settings = AppSettings.model_validate(
        {
            "database": {
                "url": f"sqlite:///{db_path}",
                "raw_payload_dir": raw_dir,
                "outbox_dir": outbox_dir,
            },
            "source": {
                "file": {"enabled": True, "path": source_path},
                "arxiv": {"enabled": False},
                "github": {"enabled": False},
                "github_trending": {"enabled": False},
                "hackernews": {"enabled": False},
                "rss": {"enabled": False},
            },
            "email": {
                "provider": "console",
                "sender": "daily-brief@example.com",
                "recipients": ["test@example.com"],
                "subject_prefix": "[Integration Brief]",
            },
            "feishu": {"enabled": False},
            "summarizer": {"provider": "extractive"},
        }
    )

    pipeline = DailyBriefPipeline.from_settings(settings)
    run = pipeline.run(ExecutionOptions(mode="manual"))

    connection = sqlite3.connect(db_path)
    try:
        run_count = connection.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
        digest_count = connection.execute("SELECT COUNT(*) FROM digests").fetchone()[0]
        delivery_count = connection.execute("SELECT COUNT(*) FROM deliveries").fetchone()[0]
        item_count = connection.execute("SELECT COUNT(*) FROM brief_items WHERE run_id = ?", (run.id,)).fetchone()[0]
    finally:
        connection.close()

    assert run.status == "completed"
    assert run_count == 1
    assert digest_count == 1
    assert delivery_count == 1
    assert item_count >= 1


def test_pipeline_dry_run_persists_run_without_delivery(tmp_path: Path) -> None:
    db_path = tmp_path / "brief.db"
    raw_dir = tmp_path / "raw"
    outbox_dir = tmp_path / "outbox"
    source_path = tmp_path / "sample.json"
    source_path.write_text(
        """[
          {
            "source": "arxiv",
            "source_type": "paper",
            "title": "A dry-run test paper",
            "url": "https://arxiv.org/abs/9999.9999",
            "summary_short": "A short test summary."
          }
        ]""",
        encoding="utf-8",
    )

    settings = AppSettings.model_validate(
        {
            "database": {
                "url": f"sqlite:///{db_path}",
                "raw_payload_dir": raw_dir,
                "outbox_dir": outbox_dir,
            },
            "source": {
                "file": {"enabled": True, "path": source_path},
                "arxiv": {"enabled": False},
                "github": {"enabled": False},
                "github_trending": {"enabled": False},
                "hackernews": {"enabled": False},
                "rss": {"enabled": False},
            },
            "email": {
                "provider": "console",
                "sender": "daily-brief@example.com",
                "recipients": ["test@example.com"],
                "subject_prefix": "[Integration Brief]",
            },
            "feishu": {"enabled": False},
            "summarizer": {"provider": "extractive"},
        }
    )

    pipeline = DailyBriefPipeline.from_settings(settings)
    run = pipeline.run(ExecutionOptions(mode="manual", dry_run=True))

    connection = sqlite3.connect(db_path)
    try:
        delivery_count = connection.execute("SELECT COUNT(*) FROM deliveries").fetchone()[0]
        run_row = connection.execute(
            "SELECT dry_run, status FROM runs WHERE id = ?",
            (run.id,),
        ).fetchone()
    finally:
        connection.close()

    assert run.status == "completed"
    assert delivery_count == 0
    assert run_row == (1, "completed")
