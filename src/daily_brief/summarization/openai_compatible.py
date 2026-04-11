from __future__ import annotations

import json

import httpx

from daily_brief.config.settings import SummarizerConfig
from daily_brief.summarization.base import BriefSummarizer
from daily_brief.summarization.prompt_builder import build_brief_prompt
from daily_brief.summarization.schemas import BriefDraft, BriefSummary


class OpenAICompatibleSummarizer(BriefSummarizer):
    def __init__(self, config: SummarizerConfig) -> None:
        self._config = config
        headers = {"Authorization": f"Bearer {config.api_key}"} if config.api_key else {}
        self._client = httpx.Client(
            base_url=config.base_url.rstrip("/"),
            timeout=config.request_timeout_seconds,
            headers=headers,
        )

    def summarize_brief(self, draft: BriefDraft) -> BriefSummary:
        if not self._config.api_key:
            raise ValueError("SUMMARIZER_API_KEY is required for the openai_compatible summarizer.")
        prompt = build_brief_prompt(draft)
        response = self._client.post(
            "/chat/completions",
            json={
                "model": self._config.model,
                "temperature": self._config.temperature,
                "response_format": {"type": "json_object"},
                "messages": [
                    {
                        "role": "system",
                        "content": "You summarize daily briefs into concise JSON with keys overview and sections.",
                    },
                    {"role": "user", "content": prompt},
                ],
            },
        )
        response.raise_for_status()
        payload = response.json()
        content = payload["choices"][0]["message"]["content"]
        return BriefSummary.model_validate(json.loads(content))
