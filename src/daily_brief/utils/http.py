from __future__ import annotations

from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from daily_brief.config.settings import HttpConfig


class HttpFetcher:
    def __init__(self, config: HttpConfig, headers: dict[str, str] | None = None) -> None:
        base_headers = {"User-Agent": config.user_agent}
        if headers:
            base_headers.update(headers)
        self._client = httpx.Client(timeout=config.timeout_seconds, headers=base_headers)
        self._attempts = config.max_retries + 1

    def close(self) -> None:
        self._client.close()

    def get_text(self, url: str, params: dict[str, Any] | None = None) -> str:
        @retry(
            reraise=True,
            stop=stop_after_attempt(self._attempts),
            wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
            retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
        )
        def _get() -> str:
            response = self._client.get(url, params=params)
            response.raise_for_status()
            return response.text

        return _get()

    def get_json(self, url: str, params: dict[str, Any] | None = None) -> Any:
        @retry(
            reraise=True,
            stop=stop_after_attempt(self._attempts),
            wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
            retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
        )
        def _get() -> Any:
            response = self._client.get(url, params=params)
            response.raise_for_status()
            return response.json()

        return _get()
