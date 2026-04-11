from __future__ import annotations

import logging
from datetime import UTC, date, datetime
from typing import cast
from zoneinfo import ZoneInfo

from daily_brief.config.settings import AppSettings
from daily_brief.delivery.base import EmailSender
from daily_brief.delivery.registry import build_senders
from daily_brief.delivery.subject import generate_subject_line
from daily_brief.graph.artifacts import WorkflowArtifactStore
from daily_brief.graph.builder import build_morning_brief_graph, workflow_mermaid
from daily_brief.graph.checkpoints import LocalFileCheckpointSaver
from daily_brief.graph.context import WorkflowDependencies
from daily_brief.graph.state import MorningBriefState
from daily_brief.llm.registry import build_reasoner
from daily_brief.models.brief import BriefItem
from daily_brief.models.briefing import BriefSection, DailyBrief
from daily_brief.models.digest import Digest
from daily_brief.models.run import RunRecord
from daily_brief.orchestration.options import ExecutionOptions
from daily_brief.rendering.renderer import render_digest
from daily_brief.sources.base import BriefSource
from daily_brief.sources.registry import build_source
from daily_brief.storage.models import RunTable
from daily_brief.storage.repository import BriefRepository
from daily_brief.storage.sqlite import init_db, make_session_factory, session_scope
from daily_brief.utils.urls import parse_http_url

logger = logging.getLogger(__name__)


class DailyBriefPipeline:
    def __init__(
        self,
        settings: AppSettings,
        source: BriefSource,
    ) -> None:
        self._settings = settings
        self._source = source
        self._reasoner = build_reasoner(settings.summarizer)
        self._senders = build_senders(settings)
        self._checkpointer = self._build_checkpointer()
        self._session_factory = make_session_factory(settings.database)

    @classmethod
    def from_settings(cls, settings: AppSettings) -> DailyBriefPipeline:
        init_db(settings.database)
        return cls(settings=settings, source=build_source(settings))

    def run(self, options: ExecutionOptions | None = None) -> RunRecord:
        execution = options or ExecutionOptions()
        target_date = execution.target_date or self._resolve_target_date()
        run = RunRecord(
            target_date=target_date,
            timezone_name=self._settings.app.timezone,
            mode=execution.mode,
            dry_run=execution.dry_run,
            force_send=execution.force_send,
        )
        artifact_store = self._create_artifact_store(run.id, target_date)

        with session_scope(self._session_factory) as session:
            repository = BriefRepository(session)
            repository.create_run(run)

        try:
            if self._should_skip_duplicate_send(run):
                run.status = "skipped_duplicate"
                run.completed_at = datetime.now(UTC)
                run.error_message = (
                    "Send already completed for this target date. Use --force to override."
                )
                with session_scope(self._session_factory) as session:
                    repository = BriefRepository(session)
                    repository.complete_run(run)
                logger.info(
                    "skipping duplicate send",
                    extra={
                        "run_id": run.id,
                        "status": run.status,
                        "target_date": str(run.target_date),
                        "mode": run.mode,
                    },
                )
                return run

            final_state = self._execute_graph(run, execution, artifact_store)
            run.item_count = len(final_state.get("ingested_items", []))
            run.status = "completed"
            run.completed_at = datetime.now(UTC)
            self._persist_success(run, final_state)
        except Exception as exc:
            logger.exception(
                "daily brief run failed",
                extra={
                    "run_id": run.id,
                    "status": "failed",
                    "target_date": str(run.target_date),
                    "mode": run.mode,
                },
            )
            artifact_store.save_json(
                "run_error.json",
                {
                    "run_id": run.id,
                    "target_date": run.target_date,
                    "mode": run.mode,
                    "dry_run": run.dry_run,
                    "error_type": exc.__class__.__name__,
                    "message": str(exc),
                },
            )
            run.status = "failed"
            run.completed_at = datetime.now(UTC)
            run.error_message = str(exc)
            with session_scope(self._session_factory) as session:
                repository = BriefRepository(session)
                repository.complete_run(run)
            raise

        logger.info(
            "daily brief run completed",
            extra={
                "run_id": run.id,
                "status": run.status,
                "target_date": str(run.target_date),
                "mode": run.mode,
                "item_count": run.item_count,
                "artifact_dir": str(artifact_store.run_dir),
            },
        )
        return run

    def preview_digest(self, options: ExecutionOptions | None = None) -> Digest:
        execution = options or ExecutionOptions(mode="preview", dry_run=True)
        target_date = execution.target_date or self._resolve_target_date()
        run = RunRecord(
            target_date=target_date,
            timezone_name=self._settings.app.timezone,
            mode=execution.mode,
            dry_run=True,
            force_send=execution.force_send,
        )
        artifact_store = self._create_artifact_store(run.id, target_date)
        final_state = self._execute_graph(run, execution, artifact_store)
        digest = final_state.get("digest")
        if digest is None:
            raise ValueError("Workflow completed without producing a digest.")
        return digest

    def build_test_digest(self, target_date: date | None = None) -> Digest:
        resolved_date = target_date or self._resolve_target_date()
        now = datetime.now(UTC)
        brief = DailyBrief(
            run_id=RunRecord(
                target_date=resolved_date, timezone_name=self._settings.app.timezone, mode="test"
            ).id,
            subject=f"{self._settings.email.subject_prefix} {resolved_date.isoformat()}",
            generated_at=now,
            overview="Test delivery for the Daily Brief Agent. This verifies rendering and email delivery without relying on live sources.",
            sections=[
                BriefSection(
                    name="AI research",
                    summary="One sample item to verify rendering and email transport.",
                    items=[
                        BriefItem(
                            source="system",
                            source_type="news",
                            title="Daily Brief Agent test item",
                            url=parse_http_url("https://example.com/daily-brief-test"),
                            summary_short="This is a synthetic item used to validate delivery.",
                            why_it_matters="Confirms that the final delivery stage is operational end to end.",
                            section="AI research",
                        )
                    ],
                )
            ],
            markdown_body="",
        )
        brief = brief.model_copy(
            update={
                "subject": generate_subject_line(
                    self._settings.email.subject_prefix,
                    brief,
                    self._settings.app.timezone,
                )
            }
        )
        return render_digest(brief, self._settings.app.timezone)

    def list_runs(self, limit: int = 20) -> list[RunTable]:
        with session_scope(self._session_factory) as session:
            repository = BriefRepository(session)
            return repository.list_runs(limit=limit)

    def mermaid_diagram(self) -> str:
        return workflow_mermaid()

    def checkpoint_path(self) -> str | None:
        if self._checkpointer is None:
            return None
        return str(self._checkpointer.path)

    def sender_for(self, provider: str | None = None) -> EmailSender:
        if provider is None:
            return self._senders[0].sender
        for target in self._senders:
            if target.provider == provider:
                return target.sender
        raise ValueError(f"Configured sender not found for provider: {provider}")

    def _create_artifact_store(self, run_id: str, target_date: date) -> WorkflowArtifactStore:
        root_dir = self._settings.workflow.artifact_root
        root_dir.mkdir(parents=True, exist_ok=True)
        return WorkflowArtifactStore.create(root_dir=root_dir, run_id=run_id, target_date=target_date)

    def _execute_graph(
        self,
        run: RunRecord,
        execution: ExecutionOptions,
        artifact_store: WorkflowArtifactStore,
    ) -> MorningBriefState:
        artifact_store.save_json(
            "run_request.json",
            {
                "run_id": run.id,
                "target_date": run.target_date,
                "timezone_name": run.timezone_name,
                "mode": run.mode,
                "dry_run": run.dry_run,
                "force_send": run.force_send,
                "provider": self._settings.summarizer.provider,
                "delivery_targets": [target.provider for target in self._senders],
            },
        )

        dependencies = WorkflowDependencies(
            settings=self._settings,
            source=self._source,
            reasoner=self._reasoner,
            senders=self._senders,
            artifact_store=artifact_store,
            checkpointer=self._checkpointer,
        )
        workflow = build_morning_brief_graph(dependencies)
        initial_state: MorningBriefState = {
            "run_id": run.id,
            "target_date": run.target_date,
            "timezone_name": run.timezone_name,
            "mode": execution.mode,
            "dry_run": execution.dry_run,
            "force_send": execution.force_send,
            "subject_prefix": self._settings.email.subject_prefix,
            "artifact_dir": str(artifact_store.run_dir),
            "stage_history": [],
            "errors": [],
        }
        final_state = workflow.invoke(
            initial_state,
            config={
                "configurable": {
                    "thread_id": run.id,
                    "checkpoint_ns": "morning_brief",
                }
            },
        )
        if not isinstance(final_state, dict):
            raise TypeError("LangGraph workflow returned a non-dict state payload.")
        return cast(MorningBriefState, final_state)

    def _build_checkpointer(self) -> LocalFileCheckpointSaver | None:
        if not self._settings.workflow.checkpoint_enabled:
            return None
        return LocalFileCheckpointSaver(self._settings.workflow.checkpoint_path)

    def _persist_success(self, run: RunRecord, state: MorningBriefState) -> None:
        brief = state.get("brief")
        digest = state.get("digest")
        if brief is None or digest is None:
            raise ValueError("Workflow completed without producing the final brief and digest.")

        with session_scope(self._session_factory) as session:
            repository = BriefRepository(session)
            repository.save_items(self._flatten_items(brief))
            repository.save_digest(digest)
            if not run.dry_run:
                for delivery_result in state.get("delivery_results", []):
                    if delivery_result.external_id is None:
                        continue
                    repository.save_delivery(
                        run_id=run.id,
                        provider=delivery_result.provider,
                        recipient=", ".join(self._settings.email.recipients),
                        external_id=delivery_result.external_id,
                    )
            repository.complete_run(run)

    def _resolve_target_date(self) -> date:
        return datetime.now(ZoneInfo(self._settings.app.timezone)).date()

    def _should_skip_duplicate_send(self, run: RunRecord) -> bool:
        if run.force_send or run.dry_run:
            return False
        with session_scope(self._session_factory) as session:
            repository = BriefRepository(session)
            return repository.has_sent_for_date(run.target_date, run.timezone_name)

    @staticmethod
    def _flatten_items(brief: DailyBrief) -> list[BriefItem]:
        return [item for section in brief.sections for item in section.items]
