from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from daily_brief.config.settings import AppSettings
from daily_brief.delivery.base import EmailSender
from daily_brief.delivery.registry import build_senders
from daily_brief.graph.artifacts import WorkflowArtifactStore
from daily_brief.graph.context import DeliveryTarget, WorkflowDependencies
from daily_brief.graph.nodes import MorningBriefNodes
from daily_brief.graph.state import MorningBriefState
from daily_brief.llm.extractive import ExtractiveWorkflowReasoner
from daily_brief.models.digest import Digest


def _make_settings() -> AppSettings:
    return AppSettings.model_validate(
        {
            "email": {"provider": "feishu"},
            "feishu": {"enabled": True, "webhook_url": "https://example.com/hook"},
        }
    )


def test_build_senders_always_includes_console_for_feishu() -> None:
    senders = build_senders(_make_settings())
    providers = [target.provider for target in senders]
    assert "feishu" in providers
    assert "console" in providers


def test_build_senders_no_duplicate_console_when_provider_is_console() -> None:
    settings = AppSettings.model_validate({"email": {"provider": "console"}})
    providers = [target.provider for target in build_senders(settings)]
    assert providers.count("console") == 1


class _BoomSender(EmailSender):
    def send(self, digest: Digest) -> str:
        raise ValueError("simulated webhook failure")

    def preview(self, digest: Digest) -> str | None:
        return None


class _OkSender(EmailSender):
    def __init__(self) -> None:
        self.sent = False

    def send(self, digest: Digest) -> str:
        self.sent = True
        return "ok-id"

    def preview(self, digest: Digest) -> str | None:
        return None


def _make_digest() -> Digest:
    return Digest(
        run_id="run-1",
        timezone_name="America/New_York",
        subject="[Daily Brief] 2026-06-10",
        overview="overview",
        sections=[],
        html_body="<p>html</p>",
        text_body="text",
        generated_at=datetime(2026, 6, 10, 8, 0, tzinfo=UTC),
    )


def test_deliver_output_continues_when_one_channel_fails(tmp_path: Path) -> None:
    ok_sender = _OkSender()
    settings = AppSettings.model_validate(
        {
            "database": {"outbox_dir": tmp_path / "outbox"},
            "workflow": {"artifact_root": tmp_path / "runs"},
        }
    )
    dependencies = WorkflowDependencies(
        settings=settings,
        source=None,  # type: ignore[arg-type] - unused for this node
        reasoner=ExtractiveWorkflowReasoner(),
        senders=[
            DeliveryTarget(provider="feishu", sender=_BoomSender()),
            DeliveryTarget(provider="console", sender=ok_sender),
        ],
        artifact_store=WorkflowArtifactStore(run_dir=tmp_path / "runs" / "run-1"),
    )
    nodes = MorningBriefNodes(dependencies)
    state: MorningBriefState = {
        "run_id": "run-1",
        "dry_run": False,
        "digest": _make_digest(),
        "stage_history": [],
    }

    update = nodes.deliver_output(state)

    results = {result.provider: result.status for result in update["delivery_results"]}
    # The failing Feishu channel is recorded as failed but does not abort the run,
    # and the console/outbox channel still delivers successfully.
    assert results["feishu"] == "failed"
    assert results["console"] == "sent"
    assert ok_sender.sent is True
