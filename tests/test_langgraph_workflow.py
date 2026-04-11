from __future__ import annotations

import json
from pathlib import Path

from daily_brief.config.settings import AppSettings
from daily_brief.orchestration.options import ExecutionOptions
from daily_brief.orchestration.pipeline import DailyBriefPipeline


def _write_sample_source(path: Path) -> None:
    path.write_text(
        """[
          {
            "source": "arxiv",
            "source_type": "paper",
            "title": "A reasoning paper for LLM agents",
            "url": "https://arxiv.org/abs/1234.5678",
            "authors": ["Test Author"],
            "summary_short": "A paper about reasoning-heavy agent workflows.",
            "published_at": "2026-04-08T08:00:00Z"
          },
          {
            "source": "github",
            "source_type": "repo",
            "title": "transformers released a new inference runtime",
            "url": "https://github.com/huggingface/transformers/releases/tag/v1",
            "summary_short": "Release notes for a new inference runtime.",
            "published_at": "2026-04-08T09:00:00Z"
          },
          {
            "source": "rss",
            "source_type": "news",
            "title": "AI infra benchmark roundup",
            "url": "https://example.com/benchmark-roundup",
            "summary_short": "Coverage of new AI infra benchmarks and deployment tradeoffs.",
            "published_at": "2026-04-08T10:00:00Z"
          }
        ]""",
        encoding="utf-8",
    )


def _build_settings(tmp_path: Path, source_path: Path, **workflow_overrides: object) -> AppSettings:
    return AppSettings.model_validate(
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
            "email": {
                "provider": "console",
                "sender": "daily-brief@example.com",
                "recipients": ["test@example.com"],
                "subject_prefix": "[Graph Brief]",
            },
            "summarizer": {"provider": "extractive"},
            "workflow": {
                "artifact_root": tmp_path / "runs",
                "checkpoint_path": tmp_path / "runs" / "checkpoints" / "workflow.pkl",
                **workflow_overrides,
            },
        }
    )


def test_langgraph_run_persists_artifacts(tmp_path: Path) -> None:
    source_path = tmp_path / "sample.json"
    _write_sample_source(source_path)
    settings = _build_settings(tmp_path, source_path)

    pipeline = DailyBriefPipeline.from_settings(settings)
    run = pipeline.run(ExecutionOptions(mode="manual", dry_run=True))

    artifact_root = tmp_path / "runs"
    run_dirs = [path for path in artifact_root.iterdir() if path.is_dir() and path.name != "checkpoints"]
    assert run.status == "completed"
    assert len(run_dirs) == 1
    run_dir = run_dirs[0]
    assert (run_dir / "01_ingest_sources.json").exists()
    assert (run_dir / "09_render_markdown.json").exists()
    assert (run_dir / "brief.md").exists()
    assert (run_dir / "state.final.json").exists()
    assert (tmp_path / "runs" / "checkpoints" / "workflow.pkl").exists()


def test_langgraph_workflow_uses_fallback_branch(tmp_path: Path) -> None:
    source_path = tmp_path / "sample.json"
    _write_sample_source(source_path)
    settings = _build_settings(
        tmp_path,
        source_path,
        include_threshold=0.99,
        fallback_include_threshold=0.3,
        min_selected_items=3,
    )

    pipeline = DailyBriefPipeline.from_settings(settings)
    run = pipeline.run(ExecutionOptions(mode="manual", dry_run=True))

    artifact_root = tmp_path / "runs"
    run_dir = next(path for path in artifact_root.iterdir() if path.is_dir() and path.name != "checkpoints")
    select_payload = json.loads((run_dir / "05_select_items.json").read_text(encoding="utf-8"))
    relax_payload = json.loads((run_dir / "06_relax_selection.json").read_text(encoding="utf-8"))

    assert run.status == "completed"
    assert select_payload["payload"]["needs_fallback"] is True
    assert relax_payload["payload"]["selected_count"] >= 3
