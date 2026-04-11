from __future__ import annotations

from daily_brief.config.settings import AppSettings


def test_default_settings_load() -> None:
    settings = AppSettings()
    assert settings.app.max_items > 0
    assert isinstance(settings.source.file.enabled, bool)
    assert isinstance(settings.source.arxiv.enabled, bool)
    assert settings.email.provider in ("console", "gmail_api", "smtp", "feishu")
