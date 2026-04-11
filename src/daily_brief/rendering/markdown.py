from __future__ import annotations

from daily_brief.models.briefing import BriefSection


def render_markdown_brief(subject: str, overview: str, sections: list[BriefSection]) -> str:
    lines = [f"# {subject}", "", overview, ""]
    for section in sections:
        lines.append(f"## {section.name}")
        lines.append(section.summary)
        lines.append("")
        for item in section.items:
            lines.append(f"- [{item.title}]({item.url})")
            if item.summary_short:
                lines.append(f"  - {item.summary_short}")
            if item.why_it_matters:
                lines.append(f"  - Why it matters: {item.why_it_matters}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"
