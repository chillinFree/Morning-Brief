from __future__ import annotations

import logging

from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED, JobExecutionEvent
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from daily_brief.config.settings import AppSettings
from daily_brief.main import run_once
from daily_brief.orchestration.options import ExecutionOptions

logger = logging.getLogger(__name__)


def build_scheduler(settings: AppSettings) -> BlockingScheduler:
    scheduler = BlockingScheduler(timezone=settings.app.timezone)
    trigger = CronTrigger(
        hour=settings.app.digest_hour,
        minute=settings.app.digest_minute,
        timezone=settings.app.timezone,
    )
    scheduler.add_job(
        run_once,
        trigger=trigger,
        kwargs={"settings": settings, "options": ExecutionOptions(mode="scheduled")},
        id="daily-brief",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=settings.app.scheduler_misfire_grace_seconds,
        replace_existing=True,
    )
    scheduler.add_listener(_log_scheduler_event, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)
    return scheduler


def run_scheduler(settings: AppSettings) -> None:
    scheduler = build_scheduler(settings)
    scheduler.start()


def main() -> None:
    settings = AppSettings.load()
    run_scheduler(settings)


def _log_scheduler_event(event: JobExecutionEvent) -> None:
    if event.exception:
        logger.error(
            "scheduled daily brief job failed",
            extra={"status": "failed", "job_id": event.job_id},
            exc_info=(type(event.exception), event.exception, event.exception.__traceback__),
        )
    else:
        logger.info(
            "scheduled daily brief job finished",
            extra={"status": "completed", "job_id": event.job_id},
        )


if __name__ == "__main__":
    main()
