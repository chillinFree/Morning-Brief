from __future__ import annotations

from daily_brief.models.brief import BriefItem


def explain_why_it_matters(item: BriefItem) -> str:
    topic = item.section or "General"
    if topic == "AI research":
        return "Recent research aligned with your AI focus and likely worth scanning before the broader news cycle catches up."
    if topic == "Open-source / GitHub":
        return "This repo activity can affect your tooling stack, dependencies, or implementation options."
    if topic == "Tech news":
        return "This looks like a higher-signal industry update with potential impact on AI products, infra, or benchmarks."
    if topic == "Applications / grad-related":
        return "This may influence application timing, positioning, or admissions expectations."
    if topic == "Sports / NBA":
        return "Relevant to your personal-interest bucket and useful for a quick morning catch-up."
    return "This surfaced as one of the more relevant items in today's brief."
