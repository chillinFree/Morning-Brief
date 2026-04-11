from __future__ import annotations

from daily_brief.config.settings import AppSettings
from daily_brief.logging.setup import configure_logging
from daily_brief.orchestration.options import ExecutionOptions
from daily_brief.orchestration.pipeline import DailyBriefPipeline


def run_once(settings: AppSettings | None = None, options: ExecutionOptions | None = None) -> str:
    app_settings = settings or AppSettings.load()
    configure_logging(app_settings.logging)
    pipeline = DailyBriefPipeline.from_settings(app_settings)
    result = pipeline.run(options or ExecutionOptions())
    return result.id
