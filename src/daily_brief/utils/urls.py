from __future__ import annotations

from pydantic import HttpUrl, TypeAdapter

_HTTP_URL_ADAPTER = TypeAdapter(HttpUrl)


def parse_http_url(url: str) -> HttpUrl:
    return _HTTP_URL_ADAPTER.validate_python(url)
