from __future__ import annotations

from datetime import date
from pathlib import Path

from daily_brief.config.settings import AppSettings
from daily_brief.main import run_once
from daily_brief.orchestration.options import ExecutionOptions
from daily_brief.orchestration.pipeline import DailyBriefPipeline


def test_run_once_creates_outbox_files(tmp_path: Path) -> None:
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
                "file": {
                    "enabled": True,
                    "path": source_path,
                },
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
                "subject_prefix": "[Test Brief]",
            },
            "feishu": {"enabled": False},
            "ranking": {
                "max_items_per_topic": 5,
                "max_total_items": 10,
            },
            "summarizer": {"provider": "extractive"},
        }
    )

    run_id = run_once(settings)

    assert (outbox_dir / f"{run_id}.html").exists()
    assert (outbox_dir / f"{run_id}.txt").exists()
    assert isinstance(run_id, str)
    assert run_id


def test_duplicate_send_protection_skips_second_send(tmp_path: Path) -> None:
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
                "subject_prefix": "[Test Brief]",
            },
            "feishu": {"enabled": False},
            "summarizer": {"provider": "extractive"},
        }
    )

    pipeline = DailyBriefPipeline.from_settings(settings)
    first = pipeline.run(ExecutionOptions(mode="manual", target_date=date(2026, 4, 8)))
    second = pipeline.run(ExecutionOptions(mode="manual", target_date=date(2026, 4, 8)))

    assert first.status == "completed"
    assert second.status == "skipped_duplicate"
