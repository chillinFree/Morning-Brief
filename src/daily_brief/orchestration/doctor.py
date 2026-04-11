from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from daily_brief.config.settings import AppSettings


@dataclass(slots=True)
class DoctorCheck:
    name: str
    status: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class DoctorReport:
    overall_status: str
    course_demo_ready: bool
    checks: list[DoctorCheck]

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall_status": self.overall_status,
            "course_demo_ready": self.course_demo_ready,
            "checks": [
                {
                    "name": check.name,
                    "status": check.status,
                    "message": check.message,
                    "details": check.details,
                }
                for check in self.checks
            ],
        }


def run_doctor(settings: AppSettings) -> DoctorReport:
    checks = [
        _check_database(settings),
        _check_runs_root(settings),
        _check_checkpoint_backend(settings),
        _check_sources(settings),
        _check_reasoner(settings),
        _check_delivery(settings),
        _check_course_demo(settings),
    ]
    if any(check.status == "fail" for check in checks):
        overall_status = "fail"
    elif any(check.status == "warn" for check in checks):
        overall_status = "warn"
    else:
        overall_status = "ok"
    course_demo_ready = not any(
        check.status == "fail" and check.name in {"runs", "checkpoint", "sources", "delivery"}
        for check in checks
    )
    return DoctorReport(
        overall_status=overall_status,
        course_demo_ready=course_demo_ready,
        checks=checks,
    )


def _check_database(settings: AppSettings) -> DoctorCheck:
    db_url = settings.database.url
    if db_url.startswith("sqlite:///"):
        db_path = Path(db_url.removeprefix("sqlite:///"))
        return DoctorCheck(
            name="database",
            status="ok",
            message="SQLite database path is configured.",
            details={"url": db_url, "path": str(db_path)},
        )
    return DoctorCheck(
        name="database",
        status="warn",
        message="Database URL is non-SQLite; local demo assumptions may differ.",
        details={"url": db_url},
    )


def _check_runs_root(settings: AppSettings) -> DoctorCheck:
    root = settings.workflow.artifact_root
    root.mkdir(parents=True, exist_ok=True)
    run_dirs = [path for path in root.iterdir() if path.is_dir()] if root.exists() else []
    latest = max(run_dirs, key=lambda path: path.stat().st_mtime).name if run_dirs else None
    return DoctorCheck(
        name="runs",
        status="ok",
        message="Workflow artifact root is ready.",
        details={
            "artifact_root": str(root),
            "run_directory_count": len(run_dirs),
            "latest_run_dir": latest,
        },
    )


def _check_checkpoint_backend(settings: AppSettings) -> DoctorCheck:
    if not settings.workflow.checkpoint_enabled:
        return DoctorCheck(
            name="checkpoint",
            status="warn",
            message="LangGraph checkpoint backend is disabled.",
            details={},
        )
    path = settings.workflow.checkpoint_path
    path.parent.mkdir(parents=True, exist_ok=True)
    return DoctorCheck(
        name="checkpoint",
        status="ok",
        message="Local file-backed LangGraph checkpoint backend is configured.",
        details={"path": str(path)},
    )


def _check_sources(settings: AppSettings) -> DoctorCheck:
    enabled_sources: list[str] = []
    if settings.source.file.enabled:
        enabled_sources.append("file")
    if settings.source.arxiv.enabled:
        enabled_sources.append("arxiv")
    if settings.source.github.enabled:
        enabled_sources.append("github")
    if settings.source.github_trending.enabled:
        enabled_sources.append("github_trending")
    if settings.source.hackernews.enabled:
        enabled_sources.append("hackernews")
    if settings.source.rss.enabled:
        enabled_sources.append("rss")

    if not enabled_sources:
        return DoctorCheck(
            name="sources",
            status="fail",
            message="No sources are enabled.",
            details={},
        )

    file_source_ok = settings.source.file.path.exists() if settings.source.file.enabled else None
    status = "ok"
    message = "Source configuration is usable."
    if enabled_sources == ["file"]:
        status = "warn"
        message = "Only the local file source is enabled. This is fine for demos."
    if settings.source.file.enabled and not file_source_ok:
        status = "fail"
        message = "File source is enabled but the input file does not exist."

    return DoctorCheck(
        name="sources",
        status=status,
        message=message,
        details={
            "enabled_sources": enabled_sources,
            "file_source_path": str(settings.source.file.path),
            "file_source_exists": file_source_ok,
        },
    )


def _check_reasoner(settings: AppSettings) -> DoctorCheck:
    provider = settings.summarizer.provider
    if provider == "extractive":
        return DoctorCheck(
            name="reasoner",
            status="ok",
            message="Extractive reasoning is configured. No external API key is required.",
            details={"provider": provider},
        )
    if settings.summarizer.api_key:
        return DoctorCheck(
            name="reasoner",
            status="ok",
            message="LLM reasoning provider has an API key configured.",
            details={"provider": provider, "base_url": settings.summarizer.base_url},
        )
    return DoctorCheck(
        name="reasoner",
        status="fail",
        message="LLM reasoning provider is configured without an API key.",
        details={"provider": provider, "base_url": settings.summarizer.base_url},
    )


def _check_delivery(settings: AppSettings) -> DoctorCheck:
    provider = settings.email.provider
    if provider == "console":
        return DoctorCheck(
            name="delivery",
            status="ok",
            message="Console delivery is configured. Ideal for a local course demo.",
            details={"provider": provider, "outbox_dir": str(settings.database.outbox_dir)},
        )
    if provider == "feishu":
        if settings.feishu.webhook_url:
            return DoctorCheck(
                name="delivery",
                status="ok",
                message="Feishu delivery is configured.",
                details={"provider": provider},
            )
        return DoctorCheck(
            name="delivery",
            status="fail",
            message="Feishu delivery requires FEISHU_WEBHOOK_URL.",
            details={"provider": provider},
        )
    if provider == "gmail_api":
        credentials_ok = settings.email.gmail_credentials_file.exists()
        return DoctorCheck(
            name="delivery",
            status="ok" if credentials_ok else "fail",
            message=(
                "Gmail API credentials file is present."
                if credentials_ok
                else "Gmail API delivery requires a credentials file."
            ),
            details={
                "provider": provider,
                "credentials_file": str(settings.email.gmail_credentials_file),
            },
        )
    if provider == "smtp":
        smtp_ready = bool(settings.email.smtp_host and settings.email.smtp_username)
        return DoctorCheck(
            name="delivery",
            status="ok" if smtp_ready else "fail",
            message="SMTP delivery is configured." if smtp_ready else "SMTP delivery is incomplete.",
            details={"provider": provider, "smtp_host": settings.email.smtp_host},
        )
    return DoctorCheck(
        name="delivery",
        status="warn",
        message="Unknown delivery provider configured.",
        details={"provider": provider},
    )


def _check_course_demo(settings: AppSettings) -> DoctorCheck:
    ready = (
        settings.source.file.enabled
        and settings.source.file.path.exists()
        and settings.workflow.checkpoint_enabled
        and settings.email.provider == "console"
    )
    return DoctorCheck(
        name="course_demo",
        status="ok" if ready else "warn",
        message=(
            "Configuration is aligned with a local course demo."
            if ready
            else "For the easiest demo, enable the file source, console delivery, and checkpoints."
        ),
        details={
            "recommended_demo_setup": {
                "file_source_enabled": settings.source.file.enabled,
                "file_source_exists": settings.source.file.path.exists(),
                "delivery_provider": settings.email.provider,
                "checkpoint_enabled": settings.workflow.checkpoint_enabled,
                "artifact_root": str(settings.workflow.artifact_root),
            }
        },
    )
