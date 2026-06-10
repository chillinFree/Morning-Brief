from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import typer

from daily_brief import resources
from daily_brief.config.paths import daily_brief_home
from daily_brief.config.settings import AppSettings
from daily_brief.delivery.preview_sender import preview_digest
from daily_brief.logging.setup import configure_logging
from daily_brief.main import run_once
from daily_brief.orchestration.doctor import run_doctor
from daily_brief.orchestration.options import ExecutionOptions
from daily_brief.orchestration.pipeline import DailyBriefPipeline
from daily_brief.scheduler_entry import run_scheduler
from daily_brief.storage.sqlite import init_db

app = typer.Typer(help="Daily Brief Agent CLI.")


def _load_pipeline() -> tuple[AppSettings, DailyBriefPipeline]:
    settings = AppSettings.load()
    configure_logging(settings.logging)
    return settings, DailyBriefPipeline.from_settings(settings)


@app.command("show-config")
def show_config() -> None:
    settings = AppSettings.load()
    typer.echo(json.dumps(settings.model_dump(mode="json"), indent=2))


@app.command("init")
def init_workspace(
    here: bool = typer.Option(
        False,
        "--here",
        help="Scaffold in the current directory instead of the per-user home (~/.daily-brief).",
    ),
    force: bool = typer.Option(
        False, "--force", help="Overwrite existing .env and sample data files."
    ),
) -> None:
    """Scaffold a ready-to-run workspace (.env + sample data + database).

    This is the recommended first command after ``pip install``. It works from
    any directory and writes everything needed for the zero-config demo.
    """
    target = Path.cwd() if here else daily_brief_home()
    target.mkdir(parents=True, exist_ok=True)

    env_path = target / ".env"
    if env_path.exists() and not force:
        typer.echo(f".env already exists at {env_path} (use --force to overwrite)")
    else:
        env_path.write_text(resources.default_env_text(), encoding="utf-8")
        typer.echo(f"Wrote {env_path}")

    sample_path = target / "data" / "sample_brief_items.json"
    sample_path.parent.mkdir(parents=True, exist_ok=True)
    if sample_path.exists() and not force:
        typer.echo(f"Sample data already exists at {sample_path}")
    else:
        sample_path.write_text(resources.sample_brief_items_text(), encoding="utf-8")
        typer.echo(f"Wrote {sample_path}")

    settings = AppSettings.load()
    configure_logging(settings.logging)
    init_db(settings.database)
    typer.echo(f"Initialized database at {settings.database.url}")
    typer.echo("")
    typer.echo("Workspace ready. Try:")
    typer.echo("  daily-brief dry-run        # full pipeline, writes a preview (no email sent)")
    typer.echo("  daily-brief preview-email  # render an email preview")
    typer.echo("  daily-brief doctor         # readiness checks")
    typer.echo("  daily-brief serve          # web dashboard at http://127.0.0.1:8000")


@app.command("init-db")
def init_database() -> None:
    settings = AppSettings.load()
    configure_logging(settings.logging)
    init_db(settings.database)
    typer.echo(f"Initialized database at {settings.database.url}")


@app.command("run-now")
def run_now(
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Render and persist a run without sending email."
    ),
    force: bool = typer.Option(
        False, "--force", help="Allow sending even if today's brief was already sent."
    ),
) -> None:
    run_id = run_once(options=ExecutionOptions(mode="manual", dry_run=dry_run, force_send=force))
    typer.echo(f"Completed run {run_id}")


@app.command("run-once")
def run_once_command(
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Render and persist a run without sending email."
    ),
    force: bool = typer.Option(
        False, "--force", help="Allow sending even if today's brief was already sent."
    ),
) -> None:
    run_id = run_once(options=ExecutionOptions(mode="manual", dry_run=dry_run, force_send=force))
    typer.echo(f"Completed run {run_id}")


@app.command("dry-run")
def dry_run_command(
    force: bool = typer.Option(False, "--force", help="Ignore duplicate-run protection."),
) -> None:
    run_id = run_once(options=ExecutionOptions(mode="manual", dry_run=True, force_send=force))
    typer.echo(f"Completed dry run {run_id}")


@app.command("backfill-date")
def backfill_date(
    target_date: str = typer.Argument(..., help="Backfill target date in YYYY-MM-DD format."),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Render and persist a run without sending email."
    ),
    force: bool = typer.Option(
        True, "--force/--no-force", help="Allow sending for a date that already has a delivery."
    ),
) -> None:
    parsed_date = date.fromisoformat(target_date)
    run_id = run_once(
        options=ExecutionOptions(
            mode="backfill",
            target_date=parsed_date,
            dry_run=dry_run,
            force_send=force,
        )
    )
    typer.echo(f"Completed backfill run {run_id} for {parsed_date.isoformat()}")


@app.command("preview-email")
def preview_email(
    target_date: str | None = typer.Option(
        None, "--date", help="Override target brief date in YYYY-MM-DD format."
    ),
) -> None:
    settings, pipeline = _load_pipeline()
    parsed_date = date.fromisoformat(target_date) if target_date else None
    digest = pipeline.preview_digest(
        ExecutionOptions(mode="preview", target_date=parsed_date, dry_run=True)
    )
    preview_path = preview_digest(digest, settings.database.outbox_dir)
    typer.echo(f"Preview written to {preview_path}")


@app.command("show-graph")
def show_graph() -> None:
    _, pipeline = _load_pipeline()
    typer.echo(pipeline.mermaid_diagram())


@app.command("doctor")
@app.command("docter", hidden=True)
def doctor(
    strict: bool = typer.Option(
        False, "--strict", help="Exit with code 1 if any readiness check fails."
    ),
    as_json: bool = typer.Option(
        False, "--json", help="Print the doctor report as JSON."
    ),
) -> None:
    settings = AppSettings.load()
    configure_logging(settings.logging)
    report = run_doctor(settings)
    if as_json:
        typer.echo(json.dumps(report.to_dict(), indent=2))
    else:
        typer.echo(f"overall: {report.overall_status}")
        typer.echo(f"course_demo_ready: {str(report.course_demo_ready).lower()}")
        for check in report.checks:
            typer.echo(f"[{check.status}] {check.name}: {check.message}")
            if check.details:
                typer.echo(json.dumps(check.details, indent=2))
    if strict and report.overall_status == "fail":
        raise typer.Exit(code=1)


@app.command("send-test-email")
def send_test_email(
    force: bool = typer.Option(True, "--force/--no-force", help="Always allow sending test email."),
) -> None:
    settings, pipeline = _load_pipeline()
    digest = pipeline.build_test_digest()
    sender = pipeline.sender_for()
    if hasattr(sender, "preview"):
        sender.preview(digest)
    external_id = sender.send(digest)
    typer.echo(f"Sent test message via {settings.email.provider}: {external_id}")


@app.command("send-test-feishu")
def send_test_feishu(
    force: bool = typer.Option(True, "--force/--no-force", help="Always allow sending test message."),
) -> None:
    settings, pipeline = _load_pipeline()
    digest = pipeline.build_test_digest()
    sender = pipeline.sender_for("feishu")
    if hasattr(sender, "preview"):
        sender.preview(digest)
    external_id = sender.send(digest)
    typer.echo(f"Sent test message via feishu: {external_id}")


@app.command("list-runs")
def list_runs(limit: int = typer.Option(20, "--limit", min=1, max=200)) -> None:
    _, pipeline = _load_pipeline()
    rows = pipeline.list_runs(limit=limit)
    data = [
        {
            "id": row.id,
            "target_date": row.target_date.isoformat(),
            "timezone": row.timezone_name,
            "mode": row.mode,
            "dry_run": row.dry_run,
            "status": row.status,
            "item_count": row.item_count,
            "started_at": row.started_at.isoformat(),
            "completed_at": row.completed_at.isoformat() if row.completed_at else None,
            "error_message": row.error_message,
        }
        for row in rows
    ]
    typer.echo(json.dumps(data, indent=2))


@app.command("schedule")
def schedule() -> None:
    settings = AppSettings.load()
    configure_logging(settings.logging)
    run_scheduler(settings)


@app.command("serve")
def serve(
    host: str = typer.Option("127.0.0.1", "--host", help="Host interface to bind."),
    port: int = typer.Option(8000, "--port", min=1, max=65535, help="Port to listen on."),
    reload: bool = typer.Option(False, "--reload", help="Enable autoreload for development."),
) -> None:
    """Serve the Morning Brief web dashboard."""
    import uvicorn

    if reload:
        uvicorn.run("daily_brief.web.app:create_app", host=host, port=port, reload=True, factory=True)
        return
    from daily_brief.web.app import create_app

    typer.echo(f"Serving Morning Brief dashboard at http://{host}:{port}")
    uvicorn.run(create_app(), host=host, port=port)


if __name__ == "__main__":
    app()
