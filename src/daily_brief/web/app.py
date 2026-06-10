"""FastAPI web app that displays the daily morning brief.

The web layer is a thin presentation surface on top of the existing
``DailyBriefPipeline``. It never duplicates pipeline logic: it reads runs,
digests, and workflow stage artifacts that the pipeline already persists, and
it triggers new runs through the same code path the CLI uses.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from daily_brief.config.settings import AppSettings
from daily_brief.logging.setup import configure_logging
from daily_brief.orchestration.options import ExecutionOptions
from daily_brief.orchestration.pipeline import DailyBriefPipeline

_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


@dataclass
class TriggerState:
    """In-memory status for the most recent web-triggered run."""

    status: str = "idle"  # idle | running | completed | failed
    run_id: str | None = None
    message: str = ""
    mode: str = ""
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "status": self.status,
                "run_id": self.run_id,
                "message": self.message,
                "mode": self.mode,
                "updated_at": self.updated_at.isoformat(),
            }

    def begin(self, mode: str) -> bool:
        with self._lock:
            if self.status == "running":
                return False
            self.status = "running"
            self.mode = mode
            self.message = f"Workflow running ({mode})..."
            self.run_id = None
            self.updated_at = datetime.now(UTC)
            return True

    def finish(self, status: str, run_id: str | None, message: str) -> None:
        with self._lock:
            self.status = status
            self.run_id = run_id
            self.message = message
            self.updated_at = datetime.now(UTC)


def _run_pipeline_async(
    pipeline: DailyBriefPipeline, options: ExecutionOptions, state: TriggerState
) -> None:
    try:
        run = pipeline.run(options)
        if run.status == "completed":
            message = f"Run {run.id} completed with {run.item_count} items."
        else:
            message = f"Run {run.id} finished with status '{run.status}'."
            if run.error_message:
                message += f" {run.error_message}"
        state.finish("completed", run.id, message)
    except Exception as exc:  # noqa: BLE001 - surface any failure to the UI
        state.finish("failed", None, f"Run failed: {exc}")


def _run_to_dict(run: Any) -> dict[str, Any]:
    return {
        "id": run.id,
        "target_date": run.target_date.isoformat(),
        "timezone": run.timezone_name,
        "mode": run.mode,
        "dry_run": run.dry_run,
        "status": run.status,
        "item_count": run.item_count,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "error_message": run.error_message,
    }


def create_app(settings: AppSettings | None = None) -> FastAPI:
    app_settings = settings or AppSettings.load()
    configure_logging(app_settings.logging)
    pipeline = DailyBriefPipeline.from_settings(app_settings)
    templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))
    trigger_state = TriggerState()

    app = FastAPI(title="Morning Brief", docs_url="/api/docs", redoc_url=None)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/", response_class=HTMLResponse)
    def dashboard(request: Request) -> HTMLResponse:
        runs = pipeline.list_runs(limit=30)
        latest = pipeline.latest_run_with_digest()
        latest_run_id = latest.id if latest is not None else None
        completed = sum(1 for r in runs if r.status == "completed")
        total_items = sum(r.item_count for r in runs)
        return templates.TemplateResponse(
            request,
            "dashboard.html",
            {
                "runs": runs,
                "latest_run_id": latest_run_id,
                "trigger": trigger_state.snapshot(),
                "stats": {
                    "run_count": len(runs),
                    "completed": completed,
                    "total_items": total_items,
                },
                "provider": app_settings.summarizer.provider,
                "delivery": app_settings.email.provider,
                "timezone": app_settings.app.timezone,
            },
        )

    @app.get("/runs/{run_id}", response_class=HTMLResponse)
    def run_detail(request: Request, run_id: str) -> HTMLResponse:
        run = pipeline.get_run(run_id)
        if run is None:
            return templates.TemplateResponse(
                request, "not_found.html", {"run_id": run_id}, status_code=404
            )
        has_digest = pipeline.get_digest_record(run_id) is not None
        stages = pipeline.stage_artifacts(run_id)
        return templates.TemplateResponse(
            request,
            "detail.html",
            {
                "run": run,
                "has_digest": has_digest,
                "stages": stages,
            },
        )

    @app.get("/runs/{run_id}/digest.html", response_class=HTMLResponse)
    def run_digest(run_id: str) -> HTMLResponse:
        html = pipeline.get_digest_html(run_id)
        if html is None:
            return HTMLResponse(
                "<p style='font-family:sans-serif;padding:2rem;color:#64748b'>"
                "No rendered digest is available for this run yet.</p>",
                status_code=404,
            )
        return HTMLResponse(html)

    @app.get("/api/runs")
    def api_runs(limit: int = 30) -> JSONResponse:
        runs = pipeline.list_runs(limit=max(1, min(limit, 200)))
        return JSONResponse([_run_to_dict(run) for run in runs])

    @app.get("/api/trigger-status")
    def api_trigger_status() -> JSONResponse:
        return JSONResponse(trigger_state.snapshot())

    @app.post("/run")
    def trigger_run(mode: str = Form("dry-run")) -> RedirectResponse:
        dry_run = mode != "send"
        options = ExecutionOptions(mode="manual", dry_run=dry_run, force_send=not dry_run)
        label = "dry-run" if dry_run else "send"
        if trigger_state.begin(label):
            thread = threading.Thread(
                target=_run_pipeline_async,
                args=(pipeline, options, trigger_state),
                daemon=True,
            )
            thread.start()
        return RedirectResponse(url="/", status_code=303)

    return app
