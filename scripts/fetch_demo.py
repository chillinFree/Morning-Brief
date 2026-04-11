from __future__ import annotations

import json

from daily_brief.config.settings import AppSettings
from daily_brief.logging.setup import configure_logging
from daily_brief.sources.base import SourceFetchContext
from daily_brief.sources.registry import build_source


def main() -> None:
    settings = AppSettings.load()
    configure_logging(settings.logging)
    source = build_source(settings)
    items = source.fetch(SourceFetchContext(run_id="demo-run", max_items=settings.app.max_items))
    normalized = [item.model_dump(mode="json") for item in items]
    print(json.dumps(normalized, indent=2))


if __name__ == "__main__":
    main()
