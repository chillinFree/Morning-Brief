from __future__ import annotations

from importlib.resources import files

from daily_brief.summarization.schemas import BriefDraft


def build_brief_prompt(draft: BriefDraft) -> str:
    template = (
        files("daily_brief.summarization.templates")
        .joinpath("brief_summary_prompt.txt")
        .read_text(encoding="utf-8")
    )
    rendered_sections: list[str] = []
    for section in draft.sections:
        rendered_sections.append(f"Section: {section.name}")
        for item in section.items:
            rendered_sections.append(f"- Title: {item.title}")
            rendered_sections.append(f"  Source: {item.source}")
            rendered_sections.append(f"  URL: {item.url}")
            rendered_sections.append(
                f"  Summary: {item.summary_short or item.content_text or item.title}"
            )
    return template.format(subject=draft.subject, sections="\n".join(rendered_sections))
