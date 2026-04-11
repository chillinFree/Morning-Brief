from __future__ import annotations

from collections import OrderedDict

from daily_brief.models.brief import BriefItem


def group_by_topic(items: list[BriefItem]) -> dict[str, list[BriefItem]]:
    grouped: dict[str, list[BriefItem]] = OrderedDict()
    for item in items:
        topic = item.section or "General"
        grouped.setdefault(topic, []).append(item)
    return grouped
