from __future__ import annotations

from zoneinfo import ZoneInfo

from daily_brief.models.briefing import DailyBrief


def generate_subject_line(prefix: str, brief: DailyBrief, timezone_name: str) -> str:
    local_time = brief.generated_at.astimezone(ZoneInfo(timezone_name))
    active_sections = [section.name for section in brief.sections if section.items]
    if active_sections:
        headline = " | ".join(active_sections[:2])
        return f"{prefix} {local_time:%Y-%m-%d} | {headline}"
    return f"{prefix} {local_time:%Y-%m-%d}"
