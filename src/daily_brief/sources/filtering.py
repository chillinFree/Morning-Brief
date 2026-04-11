from __future__ import annotations

from daily_brief.models.brief import BriefItem


def matches_keywords(texts: list[str | None], keywords: list[str]) -> bool:
    if not keywords:
        return True
    haystack = " ".join(text for text in texts if text).lower()
    return any(keyword.lower() in haystack for keyword in keywords)


def filter_items(items: list[BriefItem], keywords: list[str]) -> list[BriefItem]:
    if not keywords:
        return items
    filtered: list[BriefItem] = []
    for item in items:
        if matches_keywords([item.title, item.summary_short, item.content_text], keywords):
            filtered.append(item)
    return filtered
