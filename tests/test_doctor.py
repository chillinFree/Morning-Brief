from __future__ import annotations

from pathlib import Path

from daily_brief.config.settings import AppSettings
from daily_brief.orchestration.doctor import run_doctor


def test_doctor_reports_course_demo_ready_for_local_setup(tmp_path: Path) -> None:
    source_path = tmp_path / "sample.json"
    source_path.write_text("[]", encoding="utf-8")
    settings = AppSettings.model_validate(
        {
            "database": {
                "url": f"sqlite:///{tmp_path / 'brief.db'}",
                "raw_payload_dir": tmp_path / "raw",
                "outbox_dir": tmp_path / "outbox",
            },
            "source": {
                "file": {"enabled": True, "path": source_path},
                "arxiv": {"enabled": False},
                "github": {"enabled": False},
                "github_trending": {"enabled": False},
                "hackernews": {"enabled": False},
                "rss": {"enabled": False},
            },
            "email": {"provider": "console", "recipients": ["demo@example.com"]},
            "workflow": {
                "artifact_root": tmp_path / "runs",
                "checkpoint_enabled": True,
                "checkpoint_path": tmp_path / "runs" / "checkpoints" / "workflow.pkl",
            },
            "summarizer": {"provider": "extractive"},
            "feishu": {"enabled": False},
        }
    )

    report = run_doctor(settings)

    assert report.overall_status in {"ok", "warn"}
    assert report.course_demo_ready is True
    checkpoint_check = next(check for check in report.checks if check.name == "checkpoint")
    assert checkpoint_check.status == "ok"

