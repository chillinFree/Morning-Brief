from __future__ import annotations

from zoneinfo import ZoneInfo

from jinja2 import Environment, PackageLoader, select_autoescape

from daily_brief.models.briefing import DailyBrief
from daily_brief.models.digest import Digest

_ENV = Environment(
    loader=PackageLoader("daily_brief", "rendering/templates"),
    autoescape=select_autoescape(["html", "xml"]),
)


def render_digest(brief: DailyBrief, timezone_name: str) -> Digest:
    html_template = _ENV.get_template("digest.html.j2")
    text_template = _ENV.get_template("digest.txt.j2")
    local_timestamp = brief.generated_at.astimezone(ZoneInfo(timezone_name))
    html_body = html_template.render(
        subject=brief.subject,
        overview=brief.overview,
        sections=brief.sections,
        generated_at=local_timestamp,
        timezone_name=timezone_name,
    )
    text_body = text_template.render(
        subject=brief.subject,
        overview=brief.overview,
        sections=brief.sections,
        generated_at=local_timestamp,
        timezone_name=timezone_name,
    )
    return Digest(
        run_id=brief.run_id,
        timezone_name=timezone_name,
        subject=brief.subject,
        overview=brief.overview,
        sections=brief.sections,
        html_body=html_body,
        text_body=text_body,
    )
